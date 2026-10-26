# POST-V1 PHASE B — SHORT FIDELITY BACKTEST REPORT

**Status:** CLOSED — **PASS** (2026-09-14). Full-October determinism pair complete (`phase_b_run1/` + `phase_b_run2/`, 31,619 bars each, 2025-10-01 → 2025-10-31): exports byte-identical, all §4 invariants OK, Trigger D = 0, machine verdict `phase_b_verdict.json` = PASS. During execution a quadratic per-bar cost in the adapter scan path was diagnosed (py-spy) and fixed with three equivalence-preserving patches (suite 529→532), proven semantics-preserving by a byte-identical Oct 1–3 golden re-run (`phase_b_golden_check/`) — details §7.4. Two verdict-script fixes (recursive runtime-strip; `positions_still_open` explanation) disclosed in §7.4.
**Script:** `06_RESEARCH/scripts/phase_b_fidelity_backtest.py` · post-run verifier `06_RESEARCH/scripts/phase_b_verdict.py`
**Active plan:** `00_LOCKED/POST_V1_PLAN_OF_ACTION.md` §4 (Phase B)
**Datasets:** canonical `07_DATA/XAUUSD_M1.parquet` via the only sanctioned loader (`smc.data.parquet_loader.load_ohlcv_parquet`) — SHA-256 `e5d730ea…d17fee9` (Phase A record)
**Artifacts:** `06_RESEARCH/results/phase_b_run1/` + `phase_b_run2/` (full-October determinism pair, in flight — relaunched 2026-09-13 on patched code; first attempt aborted, logs preserved as `phase_b_oct_full_aborted{1,2}.log`) · `phase_b_golden_check/` (patched-code rerun of Oct 1–3 — BYTE-IDENTICAL to run1; semantics-preservation proof) · `phase_b_oct_short_run1/2/` (Oct 1–3 completed pair, byte-identical) · `phase_b_smoke/` + `phase_b_smoke2/` (Oct 1 completed smoke pair, byte-identical)

---

## 1. Window selection (plan §4)

| Item | Value |
|---|---|
| Execution window | **2025-10-01 00:00 → 2025-10-31 23:59 UTC** (1 month of M1, per plan's "1–3 months" band). Dataset reality: the last October bar is **2025-10-31 20:59** — 31,619 bars loaded; the 20:00–24:00 tail of the final Friday is part of the Phase A-classified NY-5pm rollover-hour omission, not missing execution |
| Selection rationale | Contains both regimes: a strong uptrend to new highs in the first half and a ranging retracement in the second half; full session coverage, two Fridays+EOD cycles, no month-boundary holiday distortion |
| Bars executed so far | smoke pair 1,380 (Oct 1) → short pair 4,020 (Oct 1–3) → **full-October pair 31,619 (in flight)** — the pipeline was validated at each scale before extending |
| Detection rolling window | 2,880 M1 bars (≈ 2 days) — sized so PDH/PDL and session-level weeks exist inside every window |
| Stack | load → rolling `DetectionDriver.validate_window` (arm ONLY new POIs — live-loop contract) → `PipelineAdapter` (real in-loop trigger scan, no lookahead `to_bar` cap) → `BacktestRunner` (locked per-bar order incl. §23/§24 expiry step) → `RiskEngine` → M2 fill/close model → `build_report` + CSV/JSON exports |

## 2. Frozen config (recorded verbatim — plan §5 will reuse this)

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

Notes (documented, not invented): `spread_price=0.0` leaves the §28.5 gate OFF (Phase C adds the SENSITIVITY-CHECK run); `news_events=[]` leaves §11 dormant (plan §9 states this in every report); sessions gate entries to 00:00–20:00 UTC (§2 — 20:00–24:00 belongs to no session); Friday EOD 20:00 UTC (§28.4) active; Trigger D compiled but structurally unfireable (A5 ruling).

## 3. Funnel counters (kill-funnel, plan §4)

Filled from `phase_b_run1/summary.json` (run2 semantically identical; only runtime fields differ):

| Stage | Count | Note |
|---|---|---|
| bars_processed | 31,619 | 2025-10-01 00:00 → 2025-10-31 20:59 UTC (Friday rollover-hour omission, Phase A-classified) |
| pois_detected_raw | 189,284 | pre-merge detections across cycles |
| pois_armed_unique | 237 | ZoneRegistry geometric merge (§7.3); validation pass events 15,470 / 120,482 (≈ 12.8%) |
| routes_produced | 49 | `candidate_from_route` invocations (new §11 workflow creations) |
| entries_placed | 42 | §11 one-shot respected; violated_pulls = 0 |
| positions_opened | 41 | 42 placed − 1 expired_give_up (§24) — the placed→filled gap, explained |
| expired_give_up / expired_section23 | 1 / 0 | hard_cancelled_news = 0; friday_closes = 0 |
| be_modifies_applied | 15 | equals n_wins exactly (§7.4) |
| positions_still_open | 0 | book flat at window end — end-state, not a throughput stage (explained) |

Every stage is non-zero or explained in writing ✓.

## 4. Core metrics

Filled from `phase_b_run1/summary.json` (`metrics` block; run2 identical):

- Equity: 10,000.00 → **9,923.42** (net P/L **−7.66**)
- Trades: **41** closed (15 wins / 26 losses) — win rate **36.59%**
- Profit factor: **0.0501** (gross win 0.40 vs gross loss −8.06; PF computed over a loss-bearing book — structurally sane, not `inf`)
- Max drawdown (closed-trade equity): **7.66**
- Close kinds: **41 × stop_loss** — TP never reached; every exit price equals the SL exactly (same-bar SL-first §4 rule verified over **all 41 trades**, not a sample — `06_RESEARCH/scripts/phase_b_sl_first_check.py`)
- The 15 "wins" are exactly the BE-modified positions (§28.1 BE at 1×ATR + buffer locks ≤ 0.06 each) — internally coherent: `be_modifies_applied` (15) == `n_wins` (15)

## 5. Per-trigger breakdown (Trigger D must be 0)

From `by_trigger_trades`: **A = 2 · B = 7 · F = 32 · D = 0 ✓** (expected 0 per the A5 ruling — all-zero volume makes `engulfer.volume < engulfed.volume` never true; confirmed structurally unfireable on the full window). F dominates attribution: 32/41 ≈ 78% of trades.

## 6. Determinism rerun

Method: the identical CLI invocation executed twice into `phase_b_run1/` and `phase_b_run2/`; `trades.csv` + `report.json` compared byte-for-byte (FC /b). POI ids are injected deterministically per run (`poi-NNNNNN` counter replacing the per-run `uuid4` — the evidence-run pattern the DetectionDriver documents), so identity strings in exports are stable across runs.

**Verdict: PASS.** `trades.csv` + `report.json` byte-identical between `phase_b_run1/` and `phase_b_run2/`. `summary.json` identical on every semantic field (recursive runtime-strip: only `funnel.runtime_seconds` 42,393.1 vs 42,320.7 s and `bars_per_second` differ). Machine verdict: `phase_b_verdict.json` → `"verdict": "PASS"` (written 2026-09-14 09:38 by `06_RESEARCH/scripts/phase_b_verdict.py`).

## 7. Anomalies / bugs found and dispositions

### 7.1 FIXED — §28.1 BE latch was shared, not per-trade (true integration bug)

**Found:** the 2025-10-01 smoke run (1,380 bars) tripped the `be_once_per_trade` invariant — one ticket was BE-modified TWICE.

**Root cause:** v25_DIAG was a single-position EA, so one shared `g_beMoved` flag was safe. The Python runners are multi-position: trade A's BE applies (latch set) → trade B fills → `on_trade_opened()` → `PureRunner.reset_trade()` cleared the SHARED flag → ATR grew → A re-proposed BE (`be_price` now improves the old BE) → the runner modified A's SL a second time. This violates the plan §4 invariant "BE: `on_be_applied()` fires only on a successful (improving) modify; never twice per trade".

**Fix (per plan §8: fix + regression test + note):**
- `PureRunnerState` gains a `latched: set` of trade keys; `be_moved_sl(..., trade_key=)` / `mark_be_applied(trade_key=)` key the one-shot per trade; `reset_trade()` no longer releases other trades' keys (legacy single-trade flag semantics unchanged for callers that omit the key).
- `RiskEngine.evaluate_exit(..., trade_key=)` + `on_be_applied(trade_key=)` thread the caller's identity; `on_trade_closed(trade_key)` releases the key on close (hygiene).
- `BacktestRunner` passes `position.ticket`; `PaperRunner` passes the position ticket at both the exit step and the success-confirm site.
- Regression tests: `04_SRC/tests/test_pure_runner_per_trade_latch.py` (4 tests: the exact failure shape, key-release isolation, legacy flag unchanged, engine hook threading). Suite 525 → **529 passed**.
- No frozen constant touched; no trigger/model/routing change.

### 7.2 FIXED (script-side, not stack) — routes counter

`adapter._routed` is a live set pruned by I4, so `len()` is not a cumulative count. The script now counts `candidate_from_route` invocations (exactly one per NEW §11 workflow creation). Stack untouched.

### 7.3 OBSERVED (no action) — funnel shape notes

- Model tags on armed POIs in the smoke window: M1/M5/M7 dominate; M3/M8 absent (M8 correctly emits nothing — the driver is fed M1 only; HTF provisioning stays deferred to V1.1 per plan).
- First-failure histogram is dominated by `pillar_2_fail` (displacement injection honest — only sweeps with a matching-direction displacement pass) and `pillar_1_fail`; consistent with the V1 design where Pillar 2 is the main gate.
- `pois_detected_raw` counts pre-merge detections across cycles; the geometric ZoneRegistry (same direction + overlapping zone = same episode) prevents re-arming the same zone from re-detections — this is script-side state, mirroring the live loop's "arm ONLY new POIs" rule.

### 7.4 CLOSED — anomalies from the full October runs

1. **FIXED (stack; performance-only, semantics proven preserved)** — the first full-October attempt (launched 2026-09-13 14:07) degraded to ~2.5 s/bar by bar ~12.5k (ETA blew out to days): `generate_candidates` re-ran O(prefix) swing detection plus per-trigger O(prefix) rebuilds (inverted candles/swings, RSI, ATR) for EVERY tracked POI on EVERY bar, and never-routed POIs stayed FRESH forever (nothing enforces the §24 give-up transition in the live path), so the re-scan spanned arm_bar→now every bar — quadratic in bar index. Diagnosed with py-spy (not guessed). Fix — three equivalence-preserving patches: (a) arm-anchored scan cursor: each §24-window bar is evaluated exactly once (scan start moves; context anchor stays `from_bar=arm_bar` — the critical distinction: triggers A/D/E use `from_bar` as the *episode anchor*, so moving it orphans patterns from their own episode); (b) deadline-anchored exhaustion: POIs past `arm_bar + poi_give_up_bars()` (20) stop rescanning (the §5 feed still runs); (c) `scan_route(scan_from=)` resume parameter in the engine. Suite 529 → **532** (`tests/test_adapter_scan_semantics.py` pins the scan contract). Semantics proof: golden re-run of Oct 1–3 reproduces the pre-patch pair **byte-identically** (trades.csv + report.json; `phase_b_golden_check/`).
2. **FIXED (verdict script only, no stack change)** — the checker's runtime-strip was top-level-only while `runtime_seconds`/`bars_per_second` live nested inside `funnel` (false FAIL on summary identity), and `positions_still_open = 0` (flat book at window end — an end-state, not a throughput stage) lacked a written explanation (false funnel FAIL). Both fixed in `phase_b_verdict.py`; re-run verdict: **PASS**.
3. **OBSERVED (no action)** — all 41 exits are exact-SL closes; the 15 wins are exactly the BE-modified positions (max win +0.06, §28.1 BE lock); TP is never reached in October. Coherence: `be_modifies_applied` == `n_wins` == 15.
4. **OBSERVED (no action)** — no crash, no zero-bar stage, no invariant tripped across 31,619 × 2 bars; window ends Friday 20:59 UTC (rollover-hour omission, Phase A-classified).

## 8. Runtime note (plan §5 asks for bars/sec as Phase E evidence)

Measured 2026-09-12, single machine, the two determinism invocations run as two OS processes in parallel (no contention observed: short pair finished 3,406 s vs 3,424 s, <1% apart):

| Scale | Bars | Avg bars/s | Dominant cost |
|---|---|---|---|
| Smoke (Oct 1) | 1,380 | 7.62 | detection window still ramping toward 2,880 |
| Short pair (Oct 1–3) | 4,020 | 1.18 | per-bar detection over the rolling window |
| Steady state (calibration) | — | ~0.87 | `validate_window` over the full 2,880-bar prefix measured at **1.149 s/bar-equivalent** (avg of 3 runs) |
| **Full October (post-patch, parallel pair)** | 31,619 | 0.75 | rolling-window re-validation (linear) |

Measured full-October: 42,393 s ≈ **11.8 h per run** with two parallel processes (0.75 bars/s). The pre-patch first attempt showed ~2.5 s/bar at bar ~12.5k and rising (quadratic — aborted, §7.4). The O(bars²) per-bar full-prefix trigger rescan was **removed** this session (§7.4 fix); the remaining dominant cost is the §24 rolling-window re-validation, linear in bars — that is the Phase E optimization evidence, now with a clean measured baseline.

## 9. PASS/FAIL against Phase B exit criteria (plan §4)

| Criterion | Status |
|---|---|
| Crash/exception mid-run | OK — none in either run (the 09-13 first attempt was aborted deliberately for performance, §7.4; not a crash) |
| Zero bars processed | OK — 31,619 bars × 2 |
| Every funnel stage non-zero or explained in writing | OK — §3 + §7.4 |
| §23/§24: fills never after expiry | OK (exact cancel→open linkage check, ≤ 18 bars) |
| §11 one-shot: ≤ 1 placement per POI | OK |
| §5 one-touch: no POI trades twice | OK |
| BE applied never twice per trade | **was FAIL → root-caused → fixed → OK** (§7.1) |
| Fill price == resting limit price | OK |
| Trigger D == 0 (A5) | OK |
| Determinism: byte-identical rerun | **PASS** — trades.csv + report.json identical; summary identical ex-runtime (§6) |

**Overall: PASS — Phase B CLOSED 2026-09-14. All plan §4 exit criteria met; Phase C cleared.**

## 10. What Phase B does NOT establish

This is a fidelity/debug gate, not a performance measurement: 1 month of M1 produces a handful of trades; no edge claim, no tuning, no scaling decision follows from these numbers. The diagnostic baseline is Phase C's 5-year run with this exact frozen config.
