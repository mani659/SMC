# POST-V1 PHASE C — FULL 5-YEAR BASELINE REPORT

**Status:** **CONDITIONALLY ACCEPTED — diagnostic baseline** (2026-09-19). The frozen V1 stack was run over the full canonical 5-year M1 series as a **dual-run determinism pair**; coverage, byte-identity, invariants and Trigger D = 0 all verified **against the final merged artifacts** (re-stamped 2026-09-19 09:55:10, see §3). Lead Architect ruling recorded: the segment-boundary carry limitation is **accepted for the V1 diagnostic baseline with mandatory documentation** (§7) — this is *not* a silent approval, and it does **not** claim continuous-run identity.
**Plan:** `00_LOCKED/POST_V1_PLAN_OF_ACTION.md` §5 (Phase C). Report name per the closeout instruction; the plan's shorthand for this document is `PHASE_C_BASELINE.md`.
**Scripts:** runner `06_RESEARCH/scripts/phase_c_baseline_backtest.py` (segmented execution over the frozen Phase B machinery imported unchanged) · verdict `06_RESEARCH/scripts/phase_c_verdict.py` · evidence scripts added for this closeout: `phase_c_breakdowns.py`, `phase_c_boundary_quant.py`, `phase_c_spread_calibration.py`, `phase_c_spread_sens_launch.ps1`
**Artifacts:** `06_RESEARCH/results/phase_c_baseline_run{1,2}/` (segments + merged) · `phase_c_verdict.json` · `phase_c_breakdowns.json` · `phase_c_boundary_quant.json` · `phase_c_spread_calibration.json` · `phase_c_spread_sens_*` (sensitivity, §8)

**Binding:** the numbers below are a **diagnostic reference point for the frozen V1**, not an edge claim, not a tuning target, and not an authorization to redesign or scale. A losing baseline authorizes evidence review (§11), nothing else.

---

## 1. Execution design and window

| Item | Value |
|---|---|
| Window | **2021-04-12 11:00 → 2026-04-10 20:59 UTC** (full canonical range, no trimming) |
| Bars processed | **1,768,123** in *both* runs (== canonical parquet row count) |
| Segmentation | 6 calendar-year segments: 2021 (partial), 2022, 2023, 2024, 2025, 2026 (partial) |
| Per-segment own bars | 257,032 / 354,629 / 349,866 / 355,893 / 354,432 / 96,271 |
| Warm-up context | 2,880 bars injected for interior segments (2021 and 2026 edge segments run with 0 warm-up; 2026 is the tail) |
| State model | fresh engine/runner per segment — **no cross-segment state carry by construction** (see §7 for the accepted consequence) |
| Checkpoint/resume | manifest fingerprint (tag, spread, window, bars); completed segments are loaded from artifacts on relaunch |
| Merge | segment trades concatenated in segment order with absolute bar indices, segment-prefixed POI ids, chained equity |
| Interruptions | one unlogged session-level suspension (2026-09-16 ~16:45 local) killed the pair + watcher; relaunched under the auto-relaunch supervisor; completed 2021–2023 segments resumed byte-identically, 2024 recomputed from segment start |

## 2. Frozen config and fingerprints

```json
{
  "equity": 10000.0,
  "risk_fraction": 0.01,
  "pip_value_per_lot": 10.0,
  "min_lots": 0.01,
  "lot_step": 0.01,
  "spread_price": 0.0,
  "news_events": [],
  "allowed_sessions": ["asia", "london", "new_york"],
  "timeframe": "M1"
}
```

| Fingerprint (sha256) | Value |
|---|---|
| config canonical JSON | `2f632571d7f20f7207da0ba72b30b8a7d3079e0023b9106b509a2867845eedb1` |
| canonical parquet `07_DATA/XAUUSD_M1.parquet` | `e5d730eae5af8348ac38f46f31e9ee6e1a481cbeaaa57cda342b9e56fd17fee9` (matches the Phase A record) |
| runner `phase_c_baseline_backtest.py` | `f4701d37d13a86c0a0d0f91303736d6eebf6d6f2f9b1e9d10980c9a0757c8288` |
| frozen machinery `phase_b_fidelity_backtest.py` | `3f746212367179d069c58bf31236381335e37f6c2b11b5d15464af831a16b48d` |

Config notes (recorded, not invented): `spread_price=0.0` leaves the §28.5 gate off — this run **is** the baseline, sensitivity is separate (§8); `news_events=[]` leaves §11 news dormant; sessions gate entries to 00:00–20:00 UTC; Friday EOD 20:00 UTC active; Trigger D compiled but structurally unfireable (Phase A ruling A5). Reproduce any table below with `python 06_RESEARCH/scripts/phase_c_breakdowns.py`.

## 3. Coverage, determinism and invariant verification

Re-run of the verifier against the **current** merged artifacts (not the earlier stamp) — `phase_c_verdict.json`:

| Check | run1 | run2 |
|---|---|---|
| bars_processed | 1,768,123 | 1,768,123 |
| covers full period | ✔ | ✔ |
| `trades.csv` byte-identical | **✔** | |
| `report.json` byte-identical | **✔** | |
| summary identical excluding runtime fields | **✔** | |
| invariants (`all_segments`) | `OK` (no non-OK key) | |
| Trigger D trades | **0** | |
| **verdict** | **PASS** | |

Timing note for audit honesty: the original verdict was stamped 01:01:24 while the pair's final merge re-wrote `merged/` at 01:26/01:30 (a relaunch found all six segments complete and re-merged deterministically). The PASS was therefore **re-proven against the on-disk bytes at 09:55:10** — same criteria, same result.

## 4. Kill funnel (plan §5 required output)

| Stage | Count | Note |
|---|---|---|
| bars_processed | 1,768,123 | full period, both runs |
| pois_detected_raw | 10,682,651 | pre-merge detections |
| validation_events / pass | 6,256,227 / 928,436 | ≈ 14.8 % pass |
| pois_armed_unique | 5,166 | geometric merge (§7.3) |
| routes_produced | 981 | §11 workflow creations |
| entries_placed | 792 | one-shot respected; `violated_pulls` = 0 |
| positions_opened | 761 | 792 placed − 31 expired_give_up (§24) |
| positions_still_open | 0 | flat at every segment end and at window end (§7) |
| be_modifies_applied | 193 | BE latch (§28.1) |
| expired_give_up / expired_section23 | 31 / 0 | `hard_cancelled_news` = 0 |
| friday_closes | 7 | §28.4 EOD force-close |
| blocked_by_reason | session **612**, circuit_breaker **266** | every other gate (news, same-level, sweep, spread, min-lots) fired **0** times |
| first_failure_histogram | pillar_2_fail 4,777,402 · pillar_1_fail 123,040 · pillar_3_fail 427,314 · pillar_2_unavailable 34 · pillar_1_unavailable 1 | funnel is not silently zeroed |

## 5. Core metrics (diagnostic baseline)

| Metric | Value |
|---|---|
| Trades closed | **761** (194 with positive P/L / 567 negative) |
| Win rate (P/L > 0) | **25.49 %** |
| Net P/L (raw price × volume units) | **−47.81** |
| Profit factor | **0.344** (gross win / gross loss; never `inf` — a loss-bearing book) |
| Average win / average loss | +0.1292 / −0.1285 |
| Max drawdown (closed-trade equity) | **49.15** |
| Equity (account view) | 10,000.00 → **9,521.85** (−478.15 currency = −4.78 %) |
| Close kinds | stop_loss **754** · friday_eod **7** · take_profit **0** |
| Volume | **0.10 lots on every single trade** (see §10.1) |

Unit discipline: `pnl` is raw *price × volume*; the account view multiplies by `pip_value_per_lot` (10.0). Both are reported so the shape (PF/WR/DD) is never confused with account magnitude.

## 6. Breakdowns

### 6.1 Per year / per segment (from the merged summary, cross-checked against the trade list)

| Segment | Trades | Wins | Win rate | Net P/L | PF | Max DD | Blocked (session / breaker) |
|---|---|---|---|---|---|---|---|
| 2021 (Apr–Dec) | 75 | 16 | 21.3 % | −1.543 | 0.471 | 1.88 | 84 / 37 |
| 2022 | 112 | 25 | 22.3 % | −6.619 | **0.034** | 6.62 | 139 / 4 |
| 2023 | 99 | 21 | 21.2 % | **+0.442** | **1.098** | 4.02 | 61 / 43 |
| 2024 | 173 | 49 | 28.3 % | **+7.074** | **1.714** | 3.73 | 156 / 86 |
| 2025 | 246 | 70 | 28.5 % | **−32.576** | **0.032** | 32.58 | 142 / 65 |
| 2026 (Jan–Apr) | 56 | 13 | 23.2 % | −14.592 | **0.031** | 14.67 | 30 / 31 |

The aggregate verdict is driven by **2025**: −32.58 of the −47.81 total (68 %), with a max DD of 32.58 on a single year. Two of six segments are profitable.

### 6.2 Per trigger

| Trigger | Trades | Share | Wins | Win rate | Net P/L | PF | Avg win / avg loss |
|---|---|---|---|---|---|---|---|
| A | 29 | 3.8 % | 7 | 24.1 % | −2.770 | 0.044 | +0.018 / −0.132 |
| B | 70 | 9.2 % | 35 | 50.0 % | −12.171 | 0.212 | +0.094 / −0.441 |
| C | 1 | 0.1 % | 1 | 100 % | +0.089 | n/a (no loss) | +0.089 / — |
| D | **0** | 0 % | 0 | — | — | — | — |
| E | 2 | 0.3 % | 0 | 0 % | −0.204 | 0.0 | — / −0.102 |
| F | 659 | **86.6 %** | 151 | 22.9 % | −32.759 | 0.397 | +0.143 / −0.107 |

Consequences that must travel with these numbers: **C, D and E carry no statistical evidence** (1, 0 and 2 trades); **F is 87 % of all flow**, so the baseline is effectively a single-trigger verdict; and A/B lose for a different reason than F (A/B: rare small BE-locked wins against large stop-outs; F: many small losses at a 23 % hit rate).

### 6.3 Per direction and exit mechanism

| Direction | Trades | Win rate | Net P/L | PF |
|---|---|---|---|---|
| long | 402 | 28.4 % | −33.058 | 0.111 |
| short | 359 | 22.3 % | −14.757 | 0.586 |

Exit mechanism: 754 stop-loss exits (**187 of which closed with positive P/L** — BE-modified stops locking the buffer) and 7 Friday-EOD closes, all profitable. `be_modifies_applied` = 193 ≈ 187 + 6, internally coherent.

## 7. Segment-boundary limitation — ACCEPTED AND DOCUMENTED (Lead Architect ruling)

**The limitation.** The segmented runner starts a fresh engine per calendar year, so episode / one-shot state does **not** carry across a segment boundary. The independent perf audit proved the mechanism on real October data (`06_RESEARCH/PHASE_C_PERF_AUDIT.md` §5): splitting a continuous window at an interior bar lost **1 of the 6** post-boundary trades (`CARRY_LOSS = 1`), with prefix identity otherwise exact.

**Why accepted.** A continuous 5-year dual-run was operationally infeasible before the perf work (≈ 27 days/run, O(bars²) prefix rescans); the segmented design is the approved execution mode; and the economic conclusion is already decisively negative, so boundary artifacts cannot flip the qualitative result.

**Quantification on the shipped artifacts** (`phase_c_boundary_quant.json`):

| Question | Answer |
|---|---|
| Positions silently dropped at a segment end | **0** — `positions_opened` = trades exported = 761 in every segment, `positions_still_open` = 0 at all six segment ends (including the two midweek boundaries 2024→25 and 2025→26) |
| Trades within ±1 day of a boundary | 0 (0.0 %) |
| Within ±3 days | 21 (2.8 %), net −1.242, PF 0.123 |
| Within ±7 days | 56 (7.4 %), net −4.364, PF 0.047 |
| Within ±14 days | 97 (12.7 %), net −7.987, PF 0.036 |
| Aggregate with **all** ±14-day boundary trades deleted | 664 trades, net **−39.83**, PF **0.383** — the shape is unchanged |
| Distance from each segment's last exit to its boundary | 2021: 691.6 h · 2022: 63.3 h · 2023: 76.5 h · 2024: 138.6 h · 2025: 39.4 h · 2026: n/a (window end) |
| Per-segment trades before own start (warm-up zone) | **0 in every segment** — first entry lands past own start by 2021 +1,010 · 2022 +71 · 2023 +243 · 2024 +83 · 2025 +62 · 2026 +896 bars; merge offsets verified `local + (own_start − 2,880) == absolute` for all 761 trades; per-segment tickets unique, `route_id` globally unique 761/761 |

**Lead Architect ruling (2026-09-19): ACCEPT for the V1 diagnostic baseline, with this documentation — option (a).** Rationale: a continuous 5-year dual-run was operationally infeasible pre-perf work; the segmented design is the approved execution mode; the economic conclusion is decisively negative, so boundary artifacts cannot flip the qualitative result. Consequences of the ruling: the earlier 2026-09-15 Option-B instruction (implement a warm-up-overlap trim on the merge) is closed as **moot** — zero warm-up-zone trades exist (table above) — and the boundary-overlap re-merge is retained only as a documented contingency for any future research-grade re-run. This is an accept-and-document ruling, not silent approval, and no continuous-run identity is claimed anywhere in this report.

**What is and is not claimed.** No dangling-position loss occurred in this run, so the *trade count* is exact (761 opened = 761 closed). What remains unquantified at the year boundaries is the **state-carry effect**: a trade that the continuous run would have fired just after a boundary may be missing, or replaced by a different POI firing later. The only measurement of that mechanism is the audit's probe (1 trade per split ≈ 17 % of its 6 post-boundary trades). Extrapolated over 5 boundaries in a book whose median month holds ~10 trades, the expected impact is a handful of trades — i.e. **below the resolution of every conclusion drawn in §5–§6**, and explicitly not a claim of continuous-run identity. If research-grade continuity is ever needed, it is a separate boundary-overlap re-merge patch, not a silent re-merge.

## 8. Spread sensitivity (§28.5 SENSITIVITY-CHECK, not a sweep)

The frozen baseline runs with the gate **off** (`spread_price = 0.0`); the as-is run remains *the* baseline. Because the gate is ATR-relative — accept when `spread ≤ 0.15 × ATR × grade_multiplier`, multipliers A+ 1.5 / A 1.0 / B 0.7 / C 0.5, both sides in **price units** — the ladder was calibrated from data rather than guessed (`phase_c_spread_calibration.json`, computed from the canonical M1 Wilder ATR(14) the detection driver publishes):

| Full series | ATR (price units) | Gate threshold — C | B | A | A+ |
|---|---|---|---|---|---|
| p5 / p50 / p95 | 0.208 / **0.568** / 2.620 | 0.016 / **0.043** / 0.196 | 0.022 / **0.060** / 0.275 | 0.031 / **0.085** / 0.393 | 0.047 / **0.128** / 0.589 |

ATR drifts ~7× across the period (2021 p50 ≈ 0.24 → 2026Q1 p50 ≈ 2.95), so the *same* absolute spread is binding in the early years and loose in the late ones — a single quarter cannot represent the gate's bite for the whole series, which is itself a finding (§10.4).

**Window:** **2023-02-01 → 2023-04-30** (84,470 bars, 89 days). Adequacy: ATR p50 0.490 / mean 0.585 against full-series p50 0.568 / mean 0.897 — the closest candidate window to the period medians (`phase_c_spread_calibration.json`); 41 baseline trades in the period, matching the sample size the Phase B fidelity window was accepted at; interior to the 2023 segment (31 days from the previous boundary, 8 months from the next); a near-neutral year (2023 PF 1.098) whose sign is the most decision-relevant thing a cost/gate change could flip.

**Ladder (paired, all runs cold-start on the identical window):** `0.00` (window reference) · `0.05` (≈ B-grade median threshold) · `0.15` (≈ above A+ p75) · `0.35` (the plan's documented representative retail XAUUSD value). Launcher: `06_RESEARCH/scripts/phase_c_spread_sens_launch.ps1`.

| Arm | `spread_price` | Trades (A/B/F) | Wins | WR | Net P/L | PF | Max DD | Spread-blocked | Invariants |
|---|---|---|---|---|---|---|---|---|---|
| sens0p00 — reference (gate off) | 0.00 | 52 (3/2/47) | 12 | 23.1 % | +3.215 | 2.280 | 2.348 | 0 | OK |
| sens0p05 | 0.05 | 22 (0/0/22) | 6 | 27.3 % | +4.224 | 3.860 | 1.349 | 175 | OK |
| sens0p15 | 0.15 | 2 (0/0/2) | 1 | 50.0 % | −0.062 | 0.185 | 0.076 | 215 | OK |
| sens0p35 — plan's representative value | 0.35 | **0** | 0 | — | 0 | — | 0 | 219 | OK |

Frozen-baseline floor for the same window (carried state, not an arm): **41 trades, net −1.971, PF 0.029**.

**Measurement note (cold-start delta).** Every arm runs the fresh stack from the window boundary — no warm-up context, no carried episode/one-shot state — so the 0.00 reference re-arms POIs the baseline's 2023 segment had already consumed in January: reference = 52 trades (31 common with the baseline slice, 18 reference-only, 7 baseline-only). The ladder is therefore read **arm vs arm**: all four arms share the identical pre-spread funnel (510,095 raw detections → 407 armed POIs → 54 routes; `positions_still_open` = 0; invariants OK in every arm), so every delta below is attributable to the spread gate alone. This is the same fresh-start mechanism as §7's boundary carry, quantified here as a benign measurement artifact.

**Reading (arm vs arm — the ladder measures flow reduction, not fill cost):** 0.00 → 0.05 removes 30 of 52 entries via 175 spread blocks and the surviving book's net *improves* (+3.215 → +4.224) — the gate removes losers first in this window. 0.15 leaves 2 trades. **0.35 — the plan's documented representative retail XAUUSD value — is a complete stop: all 54 routes spread-blocked (219 blocks), zero entries placed, equity never leaves 10,000.** The gate's 2023-median thresholds are ≈ 0.04–0.11 price units by grade (preamble table), so a 0.35 constant cannot pass any grade in this regime. For Phase D: on 2023-volatility XAUUSD with a real retail spread the frozen V1 places **no trades at all**; only the high-ATR 2025–2026 regime admits retail-scale spreads. Arms are labelled SENSITIVITY-CHECK per plan §5; the as-is run remains THE baseline; the absolute PFs of an 89-day near-neutral window are not comparable to the 5-year book — the deltas between arms are the sensitivity statement.

Ladder script: `python 06_RESEARCH/scripts/phase_c_spread_sens_launch.ps1` (arms resume by manifest; summaries under `06_RESEARCH/results/phase_c_spread_sens_sens0p{00,05,15,35}/merged/`).

**Interpretation of the mechanism (binding for Phase D).** `spread_price` enters the frozen stack **only** through the §28.5 entry gate — it never worsens a fill price. So this ladder measures **trade-flow reduction**, not cost degradation; the baseline's P/L is a **zero-cost upper bound** and live/demo performance will be worse than the baseline for three distinct reasons (gate-blocked flow, spread-widened fills, slippage on limit touch). Phase D's divergence log (§6 of the plan) must quantify all three.

## 9. Runtime decision and equivalence proof (plan §5 required output)

| Item | Value |
|---|---|
| Segment compute | 10.39 h (2021) + 15.29 h (2022) + 14.75 h (2023) + 15.84 h (2024) + 16.76 h (2025) + 4.40 h (2026) = **77.4 h per run** |
| Throughput | 1,768,123 bars / 77.4 h ≈ **6.3 bars/s (≈ 159 ms/bar)** at deep-prefix steady state; a 5,519-bar probe showed the pre-patch path decay to ~11 bars/s |
| Wall clock | dual pair launched 2026-09-14, finished 2026-09-19 after one machine-level interruption and one supervisor relaunch (checkpoint/resume preserved completed segments byte-identically) |
| Optimization status | the O(bars²) per-bar prefix rescan was replaced by the audited incremental `SeriesState` + detection-hoist patches (Option B, semantics-preserving). Equivalence proof: October golden replay vs the preserved Phase B pair — `trades.csv`/`report.json` **byte-identical**, summary identical ex-runtime; suite 532→551 at patch time, and **565 passed** when re-verified for this closeout (2026-09-19) |
| Remaining known cost | the adapter's per-bar scan is still the runtime driver; any further optimization belongs to evidence-gated Phase E work, and this baseline's 159 ms/bar is now the recorded justification (an order-of-magnitude part of it is warm-up/window recomputation, not tradeable work) |
| Memory | no OOM / WER / swap event was recorded across the 77.4 h run window (the one observed death was an unlogged session-level suspension, forensically ruled not a reboot, not OOM). Architecturally the per-bar footprint is O(window) — stats, not a peak-RSS measurement; no RSS figure is claimed because none was instrumented |

## 10. Anomalies and interpretation caveats (recorded, not fixed)

1. **The lot safety cap binds on 100 % of trades.** `LOT_MAX_SAFETY = 0.10` (§28.7) caps every computed size; all 761 trades are exactly 0.10 lots (1 distinct volume value in the whole export). Consequence: `risk_fraction = 0.01` is **inert** in this baseline — the risk-normalisation never reached the market because the cap binds first. The raw magnitudes are therefore nominal: −47.81 raw ≈ −478.15 account currency ≈ **−4.8 %** of the 10,000 equity, and max DD 49.15 raw ≈ **4.9 %** of equity. This does not change any shape metric (PF, WR, per-year ordering), but it does mean the baseline **cannot be read as a 1 %-risk-per-trade result**, and it re-tests the unfrozen Phase A caveat on `pip_value_per_lot` / pip size (A4). Any future sizing work is Phase E territory with a design note.
2. **No take-profit exits are possible by design.** `take_profit` = 0 and the exported `tp` column is empty on every trade: the frozen V1 exit model is BE-latched stop + FVG invalidation + Friday-EOD, with PureRunner TP in R-multiples deliberately excluded from the locked constants. The P/L shape is therefore a *structural* artefact — every winner is a BE-locked buffer, every loser a full stop distance — and not evidence about the entry logic's directional edge. PF/WR alone cannot distinguish "no edge" from "no exit model".
3. **`win` column vs `win_rate`.** The exported `win` flag means *closed at TP* (SL → false, runner-driven closes derived from price), so only 7 trades carry `win = 1`; `win_rate` in the summary is P/L-based (194/761 = 25.49 %). Both are correct; reading one as the other is a trap for downstream consumers.
4. **The §28.5 gate is ATR-relative while real spreads are absolute.** ATR drifts ~7× across the period, so the same broker spread blocks flow in 2021–2023 and passes in 2025–2026. A fixed absolute `spread_price` in the backtest is therefore regime-dependent — the sensitivity ladder is reported per window, and Phase D must feed a *live-measured* spread, not a constant.
5. **Only 2 of 6 segments are profitable and both boundary-exposed years are the loss years** (2025 −32.58, 2026 −14.59). The baseline's verdict is not stable across years: sign flips twice.
6. **Gates that never fired**: news, same-level, sweep, spread (gate off), min-lots all 0; blocked flow is entirely session (612) + circuit breaker (266). A/B/C/E per-trigger conclusions are additionally limited by sample size (§6.2).

## 11. Binding interpretation

- These results are a **diagnostic baseline of the frozen V1** — the reference point every future change is measured against (walk-forward, Monte-Carlo, patches). They are **not** an edge claim, a performance verdict on the strategy family, or a mandate for redesign.
- P/L is raw price × volume units; PF / DD / win-rate are the decision-relevant shapes. **A losing baseline authorizes Phase D and evidence-gated Phase E work — nothing else.** No parameter may be re-tuned and re-run as a "baseline"; that is Phase E with walk-forward/Monte-Carlo methodology and an architect ruling on record.
- The segment-boundary carry limitation is accepted **with** this documentation (§7) and is not to be described as continuous-run identity.
- Demo/paper is not cleared by this report; the sensitivity ladder and Phase D's divergence log are prerequisites.

## 12. Exit-criteria status (plan §5)

| Requirement | Status |
|---|---|
| Frozen config recorded + checksum | ✔ §2 |
| Full `BacktestReport` + CSV trade list + JSON export | ✔ per-segment + merged, both runs |
| Kill-funnel counts | ✔ §4 |
| Per-trigger and per-POI breakdowns | ✔ §6.2 (per-POI available in `report.json`; per-trigger tabulated) |
| Blocked-reason histogram | ✔ §4 |
| Equity curve (closed-trade) + max DD | ✔ §5 (max DD per segment §6.1) |
| Runtime + memory note (bars/sec for Phase E) | ✔ §9 |
| Spread sensitivity (≥3 spreads, representative window, adequacy) | ✔ §8 |
| Dual-run determinism, all invariants, Trigger D = 0 | ✔ §3 (re-stamped on final artifacts) |
| Boundary limitation documented | ✔ §7 (ruling: accept + document) |
| No warm-up-zone duplicates (trim closed as moot) | ✔ §7 — 0 per-segment entries before own start; merge offsets verified; `route_id` unique 761/761 |
| Determinism/build suite green | ✔ — `python -m pytest tests` from `04_SRC`: **565 passed** (2026-09-19) |
| Governance docs updated | ✔ — `POST_V1_PLAN_OF_ACTION.md`, `SESSION_HANDOFF.md`, `TODO.md`, `CHANGELOG.md` |

## 13. Reproduce and verify

```bash
python 06_RESEARCH/scripts/phase_c_verdict.py --nowait        # §3, writes phase_c_verdict.json
python 06_RESEARCH/scripts/phase_c_breakdowns.py              # §2, §5, §6
python 06_RESEARCH/scripts/phase_c_boundary_quant.py          # §7
python 06_RESEARCH/scripts/phase_c_spread_calibration.py      # §8 calibration
powershell -NoProfile -ExecutionPolicy Bypass \
  -File 06_RESEARCH/scripts/phase_c_spread_sens_launch.ps1    # §8 ladder (resumes by manifest)
python -m pytest tests                                        # suite discipline
```
