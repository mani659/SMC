# SEEK / SCAN CONTRACT REDESIGN — IMPLEMENTATION NOTE (Option B)

**Status:** IMPLEMENTED + MEASURED — `SEEK_SCAN_IMPL_MEASUREMENT: PASS` · suite **805 passed** (780 + 25 new) · `locked_constants.py` diff **empty** · double-run artifacts **byte-identical** (SHA-256 match).
**Date:** 2026-10-05 · **Binding design:** `06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md` (DESIGN_LOCK accepted 2026-10-05; rules R1–R5 are the specification — nothing invented beyond them).
**Window / inputs:** identical to the accepted Stage 3 + lifecycle packs (exec 2025-06-01 → 2025-11-30 UTC, warm-up 2025-03-01, M5 = 53,358 bars, 668 accepted structures, the 263-completion Stage 3 ledger reused from disk — nothing regenerated).
**Non-claims:** identification / pre-pillar router visibility only — pillars, risk, execution and fills were NOT run; no expectancy / PnL / win-rate / edge claims anywhere.

---

## 1. What was implemented (production surface)

**`smc/orchestration/engine.py`** (`PipelineEngine`):
- New `SeekPosture` enum: `CLEAN_ARM` / `IN_ZONE_AT_ARM` / `VIOLATION_AT_ARM` (design §3 R1.2).
- `arm_at(..., arm_candle=None)` classifies the arm bar into its initial posture (`_classify_arm_posture`: adverse close wins over touch; touch = inclusive `touches_zone` semantics; no candle → legacy `CLEAN_ARM`). Posture never changes arming, the §5 state, or the arm bar.
- `feed_bar` skips the ARM CANDLE itself (timestamp-matched) for non-CLEAN postures — the arming candle belongs to the HTF structure, not to fresh LTF price action (design R1.2a/R1.2b/R4.2). REVALIDATION continuation: a `VIOLATION_AT_ARM` episode that has not yet re-entered the zone treats a later non-touching adverse close as the arm-bar condition continued (the episode dies at give-up if it never re-enters); a wick contact is still a §5 touch. After re-entry (latched by the adapter), the standard feed applies — an adverse close is terminal (R4.1b, unchanged).

**`smc/backtest/pipeline_adapter.py`** (`PipelineAdapter`):
- `_may_route` replaced (design §3 R4.3/R2.3): a §5 TESTED state inside the seek span no longer closes the scan (the span ends at the give-up deadline, not at the touch; Trigger D's next-bar contract stays preserved by its own frozen `TRIGGER_D_EXPIRY`); VIOLATED is dead exactly as before.
- REVALIDATION gate (`_reentered_zone`): reuses the existing named rule `market_reentered_zone` — the R7 band path (close within frozen `ZONE_REFINEMENT_ATR × ATR` of the zone), limit-touch path off by contract (no limit exists pre-route). **Fail-closed on degenerate ATR**: the R7 guard's documented dormancy exists for placement; here the band IS the revalidation evidence, so warm-up ATR 0.0 keeps the gate closed (disclosed deviation from `zone_place_allowed`'s allow-on-uncomputable default — a route gate must not be vacuously satisfiable). The re-entry latch is written once to the engine episode (`revalidated_bar`) and moves the scan cursor to the re-entry bar (a pre-re-entry trigger completion does not route — the chronological scan starts at re-entry; the evaluation anchor stays at the arm bar).
- Give-up retirement moved BEFORE the seek gate and applied to **every posture**: a REVALIDATION episode that never re-enters retires its scan bookkeeping at `arm_bar + poi_give_up_bars()` instead of being re-derived per bar. Retirement semantics unchanged (only the scan retires; the §5 feed continues).
- One-shot identity untouched: `_routed` set + `_workflows` + `on_candidate_accepted` behave exactly as before; at most one route per episode.

**`smc/tests/test_coherence_patch.py`** — one assertion updated to the design: a touched POI is no longer pruned on the touch+1-window basis (R4.3 removed the routing role of the touch window); workflow-live retention unchanged.

**Untouched (verified by full-suite green + diffs):** detectors, pillars, trigger A–F evaluation bodies, trigger router, risk engine, fill model, order/position stores, PureRunner, paper runner, `locked_constants.py`, the §5 state machine transition table, R9 IntentBook semantics, live loop / multi-TF runtime.

## 2. Clarification resolved with the Architect (pre-implementation)

The design note's "closes back inside the zone, reused verbatim from `market_reentered_zone`" was ambiguous — that rule offers an R7 band path and a limit-touch path (not applicable pre-route). Ruling obtained: **R7 band re-entry, adapter ATR**. Additionally, the design note's R2.2 governs the `IN_ZONE_AT_ARM` posture: **no re-entry gate** (the completion geometry itself is the surgical gate); only `VIOLATION_AT_ARM` is re-entry-gated. Both recorded here; the note's R2.2 text is the controlling specification.

## 3. Measurement — M1–M5 vs the accepted baselines

Harness: `06_RESEARCH/scripts/seek_scan_impl_measurement.py` — Pass OLD = the accepted instrumented §5 replay (`observe_routes_instrumented`, the before-facts + armed baseline); Pass NEW = `observe_seek_scan_contract`, a per-bar mirror of the redesigned production adapter (posture classification at arm, arm-candle skip, re-entry gate, touch-no-longer-terminates, give-up retirement per posture, one-shot route retirement). Artifacts: `06_RESEARCH/results/seek_scan_implementation/` (`events_seek_scan.csv` 263 × 17, `summary.json`). Double-run byte-identical.

| Metric | Result | Verdict |
|---|---|---|
| **M1 — OPEN_SCAN share** | **206/263 = 78.33%** (F-only 81.86%) vs baseline 0.76% | **BELOW the ≥80% target by 1.67 pp (5 rows)** — honest miss, see §4 |
| **M2 — prev-routed rows preserved** | both routed rows route again, **same completion bars** (`2025-07-13 22:10`, `2025-10-26 22:10`), both OPEN_SCAN | **PASS** |
| **M3 — median(completion − last_scanned)**, previously CLOSED rows | **0.0 bars** (n 244 used / 17 null; p25 0.0, p75 0.0); 204/261 previously-CLOSED rows now visible | **PASS (≤ +2)** |
| **M4 — armed-count invariant** | 668 = 668, **zero arm-bar mismatches**; routes 2 → **196** pre-pillar (29.34% of armed — below the 50% selectivity alarm) | **PASS** |
| **M5 — one-shot invariant** | 0 episodes with >1 route | **PASS** |

**Before → after funnel (the 263 completions):** OPEN_SCAN 2 (0.76%) → **206 (78.33%)**; CLOSED_TOUCH 199 + CLOSED_VIOL 62 → HIDDEN 57 with every row's reason machine-assigned: `routed_earlier` 27 (one-shot consumed by an earlier route — seek ended in SUCCESS), `never_reentered_arm_violation` 17 (REVALIDATION episodes that never closed back into the zone band inside the locked 20-bar horizon), `violation_after_live_seek` 13 (post-arm adverse close before completion — genuine invalidation, correctly still hidden). DATA_GAP 0 / NEVER_ARMED 0 / UNCLASSIFIED 0.

**Route mix of the 196 new-contract routes (pre-pillar):** F 159, A 21, B 8, E 6, C 4 — D remains 0 (structurally unreachable, A5, untouched). **Posture counts (668 armed):** IN_ZONE_AT_ARM 484, VIOLATION_AT_ARM 182, CLEAN_ARM 2.

**Engineering gates:** suite 780 → **805** (25 new tests in `test_seek_scan_contract.py`: three postures + violation-over-touch precedence + legacy no-candle path + short direction; arm-bar skip for both postures; post-arm touch recorded; post-arm adverse-close terminal for CLEAN/IN_ZONE; REVALIDATION continuation + post-re-entry terminal + wick-touch-recorded; TESTED not a scan terminator incl. give-up boundary; adapter end-to-end cursor advance; re-entry block/allow/latch/fail-closed-on-ATR/dead-episode/legacy two-arg; one-shot; locked constants `TRIGGER_A_EXPIRY == 20 == poi_give_up_bars()`). `locked_constants.py` git diff **empty**; trigger A–F + state-machine diffs **empty**.

## 4. Honest deviation: M1 at 78.33% vs the ≥80% target

The design's M1 target was stated as "≥ 80%, with the exact value reported" and explicitly made the upper bound data-dependent ("rows whose post-arm bars contain an adverse close before their completion remain hidden under R4.1b — correctly"). The measured value is **78.33%**: 5 rows short. The hidden population is fully explained (27 + 17 + 13 above, zero unexplained rows), and **M3's zero-median** plus **M2's identical route bars** show the visible population is not being clipped early — the miss is entirely rows the design itself intends to keep hidden (invalidation + one-shot success + never-revalidated). Per the design's own decision rule ("if the share is materially below target with a dominant violation-after-arm cause, that is an Architect decision point, not a tuning trigger"), this is **reported, not tuned**: no parameter was adjusted to clear 80%. The dominant residual cause is in fact `routed_earlier` (one-shot success), not invalidation.

**Architect decision point (recorded, not acted on):** whether 78.33% with a fully-attributed 21.67% residual satisfies Option B's intent, or whether the REVALIDATION gate / one-shot interaction warrants a follow-up ruling. No further code change is proposed here.

## 5. Risks & residuals (carried from the design, plus measured findings)

- **196 pre-pillar routes vs 2 before** — the selectivity alarm (50%) did not trip (29.34%), but this is the redesign working as specified: completions on still-valid zones are now routable candidates. Quality of those routes is NOT measured here (pillars/risk not run); the M4c-style review and any quality filter remain Architect decisions.
- **484/668 structures arm IN_ZONE_AT_ARM** — the dominant posture; these route without re-entry (design R2.2). If the Architect wants a freshness nuance there (e.g. requiring a trigger completion strictly after the arm bar — already the case: trigger anchors post-date arming), it is a ruling, not a tweak.
- **17 never-revalidated episodes** kept the deferred-VIOLATED treatment and died at give-up — by design; they remain hidden and their zones died legitimately.
- **`open_to_series_end` never fired** (all 263 completions resolved to OPEN_SCAN or an attributed hidden reason) — no window-boundary ambiguity remains.
- Unsolved by design, unchanged: quality/selectivity filters on newly visible completions; F-timing research posture (PAUSED, R6); §5 locked-doc amendment (see §6).

## 6. Required follow-up (out of scope here)

`LOCKED_DECISIONS.md` §5 ("strict 1-touch only… deactivated forever") no longer fully describes seek behaviour under the accepted redesign. A dated §5 amendment (seek-window clause: touch ends freshness-for-new-*freshness-bookkeeping*, not the seek; VIOLATION_AT_ARM deferral; revalidation gate) must accompany the Architect's acceptance of this implementation. This note does NOT amend the locked doc.

---

**RETURN BLOCK**

```
IMPL_STATUS: PASS
DESIGN_NOTE_REF: 06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md
MODULES_TOUCHED: [smc/orchestration/engine.py, smc/backtest/pipeline_adapter.py, tests/test_seek_scan_contract.py (new), tests/test_coherence_patch.py (1 assertion per design R4.3), 06_RESEARCH/scripts/seek_scan_impl_measurement.py (new)]
POSTURES_IMPLEMENTED: CLEAN_ARM|IN_ZONE_AT_ARM|VIOLATION_AT_ARM
ARM_BAR_TOUCH_TERMINATES: NO
REVALIDATION_USES: market_reentered_zone
OUTER_HORIZON: 20
NEW_CONSTANTS: none
SUITE: 805 passed
LOCKED_CONSTANTS_DIFF: empty
M1_OPEN_SCAN_SHARE: 78.33% (was 0.76%) — below the 80% target by 5 rows, fully attributed (routed_earlier 27 / never_reentered 17 / violation_after_live_seek 13), reported not tuned
M2_PREV_ROUTES_PRESERVED: YES
M3_MEDIAN_DELTA: 0.0
M4_ARMED_INVARIANT: PASS (668=668, 0 arm-bar mismatches; routes 2→196, selectivity 29.34% < 50% alarm)
M5_ONESHOT_INVARIANT: PASS (0 multi-route episodes)
NOTE_PATH: 06_RESEARCH/SEEK_SCAN_CONTRACT_IMPLEMENTATION_NOTE.md
HANDOFF_UPDATED: YES
NEXT_READY: Architect review of implementation + metrics
```
