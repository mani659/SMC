# POST-DEDUP NEW-ARM QUALITY SAMPLE — LEG 6 (DIAGNOSTIC)

**Date:** 2026-10-20 · **Authority:** Architect ACCEPT of LEG 5b (armed 30 → 606; not edge) · **HOLDs honoured:** P2 FVG · FILL_PATH_HEALTHY · dedup lifecycle shipped.
**This is a measurement, not an edge claim.** No rule was changed, no threshold searched, zero product logic touched. `LOGIC_CHANGED: NO` for this leg; `locked_constants.py` diff EMPTY (verified via `git diff --stat`).

---

## 1. Question

The LEG 5b lifecycle retirement multiplied arms 30 → 606. Legacy class reasoning could not tell whether the new arms are merely re-detections of dead theses (noise) or a genuinely different class of entries. This leg characterises the **post-arm fate** of the lifecycle-enabled arm class (B) versus the class that exists under append-only dedup (A) — **arm → route → place → fill conversion only, never PnL** — on the SAME frozen 6m window the Architect accepted in LEG 5b (exec M5 2025-06-01 → 2025-11-30, M1 loaded from 2025-05-01).

## 2. Method (pre-registered, then two recorded amendments)

### 2.1 Baseline: what was pre-frozen in the script docstring
* **Cohort A** — arms that would still occur under append-only dedup (first successful arm per episode key / equivalent reconstructable definition; target ≈ 30).
* **Cohort B** — complement: arms that exist only because a prior owner key was retired; membership proved via the *blocker-retire join* (the overlapping registered predecessor retired strictly before the arm bar).
* Interpretation bands: B vs A deltas on arm→route and arm→fill within ±10 pp → `NEW_ARMS_SIMILAR_TO_LEGACY`; both ≤ −10 pp → `WEAKER`; both ≥ +10 pp → `STRONGER`; opposite signs → `MIXED`; identity-gate failure → `INCONCLUSIVE_IDENTITY_GAP`.
* Capture integrity gates: arms 606 / registers 606 / routes 219 / places 65 / retires 606; `trades.csv` byte-identical (SHA-256 `8eecd3b9…371b0`) to the LEG 5b run1.

### 2.2 Capture 1 — lifecycle run (as shipped)
Logging-only class-level seams on `_arm_passed`, `_retire_dead_keys`, `ZoneDedup.register/retire`, `generate_candidates`, `candidate_from_route`, `PendingOrderBook.place/expired_*`, `BacktestRunner.cancel_*`, `BacktestRunner.result` (all restored in `finally`; the funnel's own counters unchanged). Runtime 946.8 s.

**Integrity — all pass:** arms 606 · registers 606 · routes 219 · places 65 · retires 606 · `trades.csv` SHA-256 **byte-identical to LEG 5b run1** (proves the reads changed nothing). Cap: `results/post_dedup_new_arm_quality/capture/events.jsonl.gz` (606 arm rows, per-arm zone/det-TF/disp/ATR).

### 2.3 Amendment 1 (recorded, evidence-backed): LEG-4-frozen gate replaced by a counterfactual anchor
The pre-registered gate demanded `n_A == 30` AND the A id set equals LEG 4's frozen `armed_records.json`. A pure append-only **replay over the lifecycle run's own arm stream** yielded n_A = 25 with 3 extra firsts and 8 LEG-4 ids never arming at all — but the replay cannot answer "would the arm exist under append-only", because the two runs' arm streams are not commensurate after the first retirement.

Resolution: run a genuine **append-only counterfactual capture** (same composition; the *only* difference is `PipelineAdapter._retire_dead_keys` — the sole retirement seam, both `dedup.retire` call sites inside it — no-op'd, restored in `finally`):

| | LEG 4 frozen (append-only, older composition) | Counterfactual (append-only, TODAY's composition) |
|---|---|---|
| armed | 30 | **30** |
| routes | 10 | **10** |
| placed | 4 | **4** |
| fills | 3 | **3** (F2, C1) |
| expired | (1 s23) | 1 (s23) |
| retires | — | 0 |
| **armed ids** | 30 ids | **30 ids, SET-EQUAL to LEG 4's** (`cf_ids_equal_LEG4: true, LEG4_reproduced_in_cf: 30`) |

Runtime 875.1 s. The counterfactual reproduces **LEG 4's funnel counts and full id set exactly**, making it the valid in-composition realization of the pre-registered cohort-A definition. This is the stronger gate and it **passes**; the original gate fired on stream-commensurability, not on identity weakness (documented, not post-hoc label shopping — every gate result is retained in `summary.json`).

### 2.4 Final cohort assignment (direct membership, no proxy)
* **A (n = 30)** — lifecycle arms matched 1:1 to a counterfactual arm. Pass 1: exact identity (same poi id + arm bar + direction — deterministic ids); Pass 2: remaining cf spaces claim their earliest unclaimed overlapping lifecycle arm (same direction, inclusive-span overlap = the dedup's own predicate). All 30 cf spaces claimed exactly once; zero cf spaces left without a lifecycle heir.
* **B (n = 576)** — lifecycle arms with no counterfactual counterpart.

### 2.5 Amendment 2 (recorded): blocker-retire join extended with displacement proof
The naive first-match blocker join (pre-registered) failed for 5 of 576 B arms. Inspection:

* `poi-047069`, `poi-059079` — **false gaps**: same poi id, bar and zone are armed in BOTH runs (exact A identity the greedy pass initially mis-assigned); fixed by Pass-1 exact matching.
* `poi-006662`, `poi-033642`, `poi-054982` — **true displacement arms**: their zone-space is occupied in the append-only world (cf blockers `poi-006543` / `poi-025028` — spaces whose legacy first never armed in the lifecycle run), AND *every* prior overlapping lifecycle arm was give-up-retired strictly before the arm bar (e.g. poi-006662 arm_bar 2652; whole predecessor chain retired ≤ 2649). These arms exist **only** because retirement released the space — causal proof now stated per arm.

Final join result: **573 B via rule (a)** first-match-retire, **3 via rule (b)** displacement, **0 unverified** → `b_join_gaps: 0`.

## 3. Cohort composition (606 = 30 + 576)

| | A (append-only class) | B (lifecycle-enabled) |
|---|---|---|
| n | 30 | 576 |
| det TF | H1 25 · H4 5 | H1 413 · H4 163 |
| long / short | 16 / 14 | 461 / 115 |
| double-arm on a live key | **0** (strict-ordered replay of the whole lifecycle registry) | — |

## 4. Post-arm funnel (measured in the lifecycle run)

| Stage | A (n=30) | B (n=576) |
|---|---|---|
| routed | 10 — **33.33 %** | 209 — **36.28 %** |
| placed | 2 (6.67 %) | 63 (10.94 %) |
| filled | 2 — **6.67 %** | 56 — **9.72 %** |
| expired (§23) | 0 | 7 (1.22 %) |
| cancelled (violated/portfolio) | 0 | 0 |
| still resting at window end | 0 | 0 |
| never routed | 20 (66.67 %) | 367 (63.72 %) |

Cross-checks: routes 10 + 209 = 219 ✓ · placed 2 + 63 = 65 ✓ · fills 2 + 56 = 58 ✓ · fate gaps 0. (Two A/B "routed without scan-bar" route events travelled a non-`generate_candidates` seam — timing rows n: A 8, B 153.)

**Interpretation (pre-registered bands):** Δarm→route = **+2.95 pp**, Δarm→fill = **+3.05 pp** — both inside ±10 pp → **`NEW_ARMS_SIMILAR_TO_LEGACY`**. "Stronger/weaker" here means conversion only, **not PnL / expectancy / edge**.

## 5. Trigger mix on routes

| | A | B |
|---|---|---|
| F (BOS/OB) | 9 | 188 |
| A | 0 | 9 |
| B | 0 | 8 |
| C | 1 | 1 |
| E | 0 | 3 |

The product's route mix is dominated by Trigger F in both classes (90 % A, 89.9 % B) — the new arms are **not** sneaking in through a different (weaker) trigger family.

## 6. Exit mix on fills (counts only, no edge)

| | A (2 fills) | B (56 fills) |
|---|---|---|
| take_profit | 1 | 29 |
| stop_loss | 1 | 27 |

B's TP/SL split (51.8 % / 48.2 %) is essentially the coin-flip shape the legacy class shows at n=2 under the accepted fill path — **no adverse exit signature is introduced by the new arm class.**

## 7. Optional geometry & timing (descriptive, both measured at arm time)

| | A | B |
|---|---|---|
| median zone width | 42.105 | 47.197 |
| median zone width / ATR(at arm) | 10.587 | 14.374 |
| median disp magnitude (ATR; n present) | 2.129 (30/30) | 1.866 (576/576) |
| median arm→route bars (routed with scan-bar) | 10.5 (n=8) | 12 (n=153) |
| median arm→fill bars (filled) | 33.5 (n=2) | 14.0 (n=56) |

New arms are somewhat wider relative to ATR with slightly smaller displacement, yet convert to fills *at least as fast* — the wait-for-fill burden did not worsen.

## 8. Dedup health

* **Double-arm on a live key: 0** (strict chronological replay of the lifecycle registry over all 606 arms vs live keys; every retirement applied).
* Retire counter exactness: 606 retire events / 606 registered arms / 606 arms — conservation holds (registered = arms; retired_total exact in the event stream; the `summary.json` sweep-audit seam nuance from LEG 5b is superseded by direct event evidence).

## 9. Limitations (read before acting on this)

1. **Window-bound** — one 6m XAUUSD window; the differences (+2.95/+3.05 pp) are small and could drift.
2. **A is small (n=30)** — every A percentage rides on one-arm steps (3.3 pp granularity). The B fill-median (14 bars) vs A (33.5 bars) rests on n=2.
3. **A's fate is its fate inside the lifecycle environment** (shared risk budget with 576 other arms); the *counterfactual* run's own funnel (30→10→4 placed→3 fills, F2/C1) is reported in §2.3 for the pure append-only contrast. Both are given; neither is pooled.
4. The append-only counterfactual is a **research harness seam** (retirement no-op'd), not a shipped configuration. It was used only to define membership; the headline metrics are measured in the as-shipped lifecycle run.
5. Coarse zones measured at detection time; `disp` present for 100 % of arms (no missing-pair caveat).
6. **No edge/expectancy claim anywhere**; no optimization or threshold search was performed; arming/dedup untouched throughout this leg.

## 10. Artifacts

| Artifact | Path |
|---|---|
| Report | `06_RESEARCH/POST_DEDUP_NEW_ARM_QUALITY_REPORT.md` |
| Script | `06_RESEARCH/scripts/post_dedup_new_arm_quality.py` |
| Lifecycle capture | `06_RESEARCH/results/post_dedup_new_arm_quality/capture/events.jsonl.gz` + `capture_meta.json` |
| Append-only counterfactual | `…/capture/events_append_only.jsonl.gz` + `capture_meta_append_only.json` + `_cf_append_only_capture/` funnel |
| Summary + cohort tables | `06_RESEARCH/results/post_dedup_new_arm_quality/results/summary.json` · `cohorts.csv` (606 rows) |
| Lifecycle funnel capture | `06_RESEARCH/results/post_dedup_new_arm_quality/_funnel_capture/` (byte-identical `trades.csv`) |

**NEXT READY:** Architect ruling on the new-arm class (ops soak / hold density / further research).

---

### Return block

```
NEW_ARM_QUALITY_STATUS: PASS
WINDOW: 2025-06-01 -> 2025-11-30
N_A: 30  N_B: 576
PCT_ARM_TO_ROUTE_A: 33.33  PCT_ARM_TO_ROUTE_B: 36.28
PCT_ARM_TO_FILL_A: 6.67   PCT_ARM_TO_FILL_B: 9.72
TRIGGER_MIX_B: {F:188, A:9, B:8, C:1, E:3}
EXIT_MIX_FILLS: {A: {take_profit:1, stop_loss:1}, B: {take_profit:29, stop_loss:27}}
DOUBLE_ARM_LIVE: 0
INTERPRETATION: NEW_ARMS_SIMILAR_TO_LEGACY
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
SUITE: NOT_RUN
REPORT_PATH: 06_RESEARCH/POST_DEDUP_NEW_ARM_QUALITY_REPORT.md
NEXT_READY: Architect ruling on new-arm class (ops soak / hold density / further research)
```
