# PHASE C — INDEPENDENT PERF-PATCH AUDIT

**Status:** COMPLETE (static + dynamic; boundary probe evidence below)
**Auditor:** independent review pass, 2026-09-15 (read-only vs production runs)
**Subject:** everything added after the Phase B PASS — the Option B
performance patches (P1/P1b/P2/P3), the segmented 5-year baseline runner,
and the verdict machinery.
**Production impact:** none. The audit never modified production code or
run artifacts; its own processes (audit tests, suite rerun, boundary
probe) ran alongside the live pair, which continued in lockstep
throughout (verified before/after).

---

## 1. Scope and method

- Full `git diff vs HEAD` review of every changed file (22 tracked + 4 new source files), each classified Phase C perf vs Phase B BE-latch fix.
- Semantics re-derivation for every hoisted computation against its batch original (fold identity, window scoping, tie order, interval endpoints, polarity flips).
- Dynamic evidence: fresh-seed equivalence battery (new file `test_phase_c_audit_equivalence.py`, 14 tests), full-suite rerun (551 passed), Wilder warm-up convergence probe on real data, warm-up margin probe on the real plan, boundary probe on real October data, dual-run byte comparison of the completed 2021 segments.

## 2. Static review — verified exact-equivalence claims

| # | Patch | Equivalence argument | Verdict |
|---|---|---|---|
| 1 | Adapter scan cursor (one chronological pass per POI) | Evaluations at bar b read only candles ≤ b (state extended first); loop start moves, anchor `from_bar=arm` preserved | OK |
| 2 | §24 give-up retirement (`_routed.add`) | `_routed` has exactly one reader (the scan gate, line 146); §5 feed unaffected | OK |
| 3 | `SeriesState` ATR/RSI folds | Step-exact replicas of `atr_series`/`rsi_series` (same seed sums, same op order → bit-identical floats); warm-up `None` placement identical | OK |
| 4 | Inverted-space ATR/RSI from the same fold | True range is inversion-invariant (max of |x| quantities); negating closes swaps gain/loss sequences → `rsi_values_inverted` ≡ `rsi_series(inverted)` | OK |
| 5 | §27 candidate on bar extension | First decidable candidate at prefix `2N+1` = batch scan start; one candidate per extension, same windows, same §18 base rule | OK |
| 6 | §19 confirmation heaps | Batch confirms at FIRST close beyond base opposite extreme scanning from `base_index+1`; initial validation at candidate evaluation (exactly the batch call) + heap pops for later first-confirms = monotone events; threshold + seq tie-break = batch order | OK |
| 7 | `SwingIndex` queries | Polarity-separated base-sorted lists; `last_valid`/`last_two`/`minor_lows_between`/`sorted_up_to` reproduce the linear scans' selections including creation-order ties (ties cannot collapse across polarities) | OK |
| 8 | Mirror artifacts | Field-identical to `choch_classifier._invert_candles/_invert_swings`; consumers read only mirrored fields | OK |
| 9 | Driver stage0 hoists (per-window ATR + FVG, `check_displacement(…, atr=, fvgs=)`) | Same-input/same-output reuse; supplied-ATR read is AFTER the sweep-index bounds check; warm-up `None` aligns with legacy `latest_atr` fallback (`None` → `magnitude_atr=None`, not 0.0) | OK |
| 10 | `raw.sweeps` reuse in `validate_window` | `detect_sweeps` is read-only on `LiquidityLevel` (verified); computed before `detect_pois` in both legacy and patched order | OK |
| 11 | `WindowCache` suffix arrays | `min/max_close_suffix[k]` ≡ the per-candidate re-scan comparison set; `N+1` length, ±inf empty-suffix sentinels preserve "no close ⇒ not mitigated" | OK |
| 12 | Pillar-1 cached FVG list | Consumers filter on geometry/direction only; timeframe stamp difference (window TF vs M5 default) is inert metadata in BOTH consumers | OK |
| 13 | Trigger A/C/E/F + CHOCH hints | Every hint read has a verified legacy fallback (`hints=None` or missing field → in-place path); trigger E selects the hint matching the supplied series' space (`candles is context.candles` identity test is correct because the bearish branch passes `context.candles` itself) | OK |
| 14 | `atr_band_half_width(atr_values=…)` | `atr_values[up_to-1]` ≡ `latest_atr(candles[:up_to])` by fold identity; out-of-range → legacy path | OK |
| 15 | Runner segmentation + warm-up | Interior segments process bars ≥ their first own bar with 2,880 context bars; detection windows and (per CHECK-1) indicator state match the continuous run; `--max-bars` caps OWN bars, never truncates warm-up | OK |
| 16 | Deterministic merge | Absolute-bar rebase `start_bar + entry_bar − own_start` ≡ canonical index; concatenated close-order metrics = frozen `reports.py` helper semantics; id patch covers the single `uuid4` import site (verified) | OK |
| 17 | Verdict watcher | Coverage = merged bars == canonical count; byte identity on exports; recursive runtime strip; invariant gate; Trigger D | OK |

## 3. Findings

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| F1 | LOW (latent) | `PipelineAdapter.current_atr`: a negative `bar_index` reads `atr_values[-1]` (last ATR) where the legacy slice returned `latest_atr(candles[:0])` = `None` → 0.0 | No production caller passes negative indices (runner feeds 0-based, `generate_candidates` guards `min(bar_index, len-1)`). Documented; fix optional post-Phase C |
| F2 | INFO | Merged `trades.csv` ticket numbers restart per segment (per-segment `PositionStore`) | Not a trade-identity problem: POI ids (`y<year>-NNNNNN`) and `route_id`s are segment-unique; report notes it |
| — | — | No HIGH/MEDIUM findings. No forbidden semantics change found anywhere in the diff (thresholds, fill rules, expiry/one-shot/BE behavior, constants untouched) | |

## 4. Dynamic evidence

| Check | Result |
|---|---|
| Full suite rerun (independent of the launch-time run) | 551 passed at audit time; **565** re-verified 2026-09-15 (551 + this audit's 14-test battery) |
| Fresh-seed audit battery (3 seeds + extremes: folds, swing isomorphism, index queries, mirror, one-tick/flat/spike regimes) | **14/14 passed** |
| Wilder warm-up convergence (real 30,210-bar window, 2,880-bar warm start) | ATR bit-identical from warm-bar **510**, RSI from **465** → PASS with 5.6× budget headroom |
| Warm-up margins at every real year boundary | 5,514–6,898 context bars available vs 2,880 required → PASS |
| Dual-run determinism, early | 2021 segment artifacts (trades.csv, report.json) **BYTE-IDENTICAL** across run1/run2; summary identical ex-runtime; all 7 invariants OK; Trigger D = 0 |
| Segment-boundary probe (real Oct 6–17 data: continuous vs split pair) | see §5 |
| Phase B-era files (`runner.py`, `paper/runner.py`, `risk_engine.py`, `pure_runner.py`) | Confirmed BE-latch-only changes (dated 2026-09-12), suite-covered, golden-pinned — not Phase C surface |

## 5. Boundary-probe evidence

Probes the runner's weakest claim — "fresh stack + warm-up = serial
semantics" — at a mid-week split (Oct 15 00:00) inside active episode
territory, real October data, frozen config:

- **PREFIX_IDENTITY:** seg1's trades must equal the continuous run's pre-boundary trades exactly (same cold start ⇒ the stack cannot know the series continues).
- **CARRY_LOSS:** continuous trades after the boundary missing from seg2 (episode/one-shot state loss across the boundary).
- **EXTRA (REARM):** seg2-only trades via the warm-up re-arm pathway.
- **positions_still_open** at each segment end (boundary P/L capture).

**Run 1 (completed 2026-09-15 11:46, log `06_RESEARCH/results/audit_boundary_probe.log`) — seg1 window DEFECTIVE** (see reconciliation below): reported `PREFIX_IDENTITY: False (17 vs 20)` — an artifact of the truncated seg1 window; CARRY_LOSS = 1, EXTRA = 0, REARM_DUP = 0, still_open 0/0.

**Run 2 (corrected windows, log `06_RESEARCH/results/audit_boundary_probe_v2.log`) — AUTHORITATIVE:**

- **CHECK 1 (fold convergence): PASS** — identical reproduction (ATR bit-identical from warm-bar 510, RSI from 465; budget 2,880; 5.6× headroom).
- **CHECK 2 (boundary): FINDING, narrowed to exactly one cause** — `PREFIX_IDENTITY: True (20 vs 20)`; continuous 26 trades (6 after-boundary) · seg1 20 · seg2 5; **CARRY_LOSS = 1** — the IDENTICAL trade tuple as Run 1, reproducible: `MISSING (LONG, 2025-10-15 05:32 UTC, 4189.975, 4188.995, stop_loss, −0.098)`; `EXTRA = 0`; `REARM_DUP = 0`; `positions_still_open: seg1=0 seg2=0`; funnel seg1 armed=106/placed=21 · seg2 armed=52/placed=5 · cont armed=155/placed=27 (placed 21+5 = 26 vs cont 27 — the delta IS the carry-loss route).
- **CHECK 3 (warm-up margins): PASS** — 5,514–6,898 context bars at every year boundary vs 2,880 required (identical reproduction).

**Reconciliation (auditor, same day; CONFIRMED by the Run 2 re-run):** the
PREFIX_IDENTITY mismatch was a
**probe defect, not a stack defect** — `load_frame("2025-10-06", "2025-10-14")`
bounds at midnight (`pd.Timestamp("2025-10-14")` = 00:00), silently truncating
seg1 at Oct 14 00:00 and shedding the 1,379 Oct-14 bars (`cont pre-boundary
9,660 = 8,281 + 1,379`, verified against the canonical parquet). Run 1
printed NO trade divergence (seg1's 17 trades were an exact entry-time
prefix of cont's 20) and seg1's flat book at Oct 14 00:00 matched the
continuous run's state at that bar. With inclusive full-day bounds the
Run 2 re-run yields PREFIX_IDENTITY **True (20 vs 20)** — empirical
confirmation. Probe fixed and disclosed; production runs never used this
probe's loader.

**What survives as a genuine finding (CARRY_LOSS = 1):**
`MISSING (LONG, 2025-10-15 05:32 UTC, 4189.975, 4188.995, stop_loss, −0.098)`
— one continuous trade whose episode/one-shot state crossed the Oct 15 00:00
boundary is not taken by seg2 (fresh stack; REARM_DUP = 0, so no phantom
compensating trade). This is the **documented fresh-stack-per-segment design**
acting exactly as declared — a boundary state-carry gap, not a semantics
regression. Materiality scoping over the real 5-year plan:

| Boundary | Weekday | Exposure |
|---|---|---|
| 2021→2022 | Fri Dec 31 | pre-flattened (Friday-EOD latch) |
| 2022→2023 | Fri Dec 30 | pre-flattened |
| 2023→2024 | Fri Dec 29 | pre-flattened |
| **2024→2025** | **Tue Dec 31** | **midweek — carry possible** |
| **2025→2026** | **Wed Dec 31** | **midweek — carry possible** |

(2021 evidence: completed segment `0_2021` — `positions_still_open = 0`,
`friday_eod = 1`.) The 2024→25 and 2025→26 segment ends therefore carry the
same gap class: positions still open at segment end are **dropped from the
merged trade list** (`BacktestRunner.result()` snapshots; neither the runner
nor `BarLoop` closes end-of-data positions — no "still_open" merge stage
exists).

## 6. Verdict

**AUDIT: PASS WITH FINDINGS** (downgraded from PASS per §5's pre-stated rule:
"a boundary FINDING would downgrade this verdict") — the Phase C perf patches
(P1–P3) remain value-exact to the frozen semantics on every claim re-derived
statically and re-tested dynamically (F1/F2 unchanged, LOW/INFO); production
runs verified healthy and byte-tracking each other throughout the audit
window. The downgrading finding is **NOT a patch regression**: it is the
segmented runner's documented fresh-stack-per-segment design losing
episode/one-shot state across boundaries (§5 CARRY_LOSS = 1 on a correctly
built window), with two of five year boundaries (2024→25, 2025→26) exposed
to the same class.

**Disposition — deferred to the Lead Architect** (this audit does not rule;
no mitigation was pre-documented anywhere in the repo). Recorded options:
(a) accept + document as a known baseline limitation (diagnostic baseline;
Phase E WF/MC caveat); (b) re-merge with a boundary-overlap trim (drop
per-segment trades whose `entry_bar < own_start` in the merge — semantics-
preserving bookkeeping, restores serial book faithfulness except for the
boundary state-carry itself); (c) any further comparison run is Phase E
territory. The IN-FLIGHT production pair is unaffected in-flight; the
materiality note applies at merge/verdict time.

*Probe fix note: `audit_boundary_probe.py` now uses inclusive full-day
bounds (first run's seg1 was midnight-truncated — §5 reconciliation; the
CARRY_LOSS result is unaffected by the fix and was REPRODUCED identically
by the corrected re-run).*
