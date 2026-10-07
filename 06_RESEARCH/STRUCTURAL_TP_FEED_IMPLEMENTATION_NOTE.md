# STRUCTURAL TP FEED — IMPLEMENTATION NOTE

**Date:** 2026-10-05 · **Authority:** Lead Architect implementation
directive after design acceptance. Implements
`06_RESEARCH/STRUCTURAL_TP_FEED_DESIGN.md` (DESIGN_LOCK_STATUS: PASS,
accepted 2026-10-05, with the two constant rulings recorded in its
addendum). **IMPL_STATUS: PASS.**

> **DIAGNOSTIC ONLY — NOT PERFORMANCE.** n=2 trades on one frozen window.
> The PnL delta below is an artifact of the frozen config and this
> window, not evidence of edge. No expectancy claim is made anywhere.

## 1. What was implemented

- **`smc/backtest/pipeline_bridge.py`** — new pure selector
  `structural_tp_target(swings, entry_price, direction, atr,
  placement_bar, max_age_bars=None)`: among §19-valid swings
  (confirmed, `confirmed_index < placement_bar` — strictly before the
  decision bar), LONG picks the nearest valid swing high strictly beyond
  `entry + STRUCTURAL_TP_MIN_ATR × atr`, SHORT mirrored; recency
  tie-break on equal levels; optional documented age bound
  (`max_age_bars`); absent/invalid ATR → `None` (fail to fallback).
  Interim constant `STRUCTURAL_TP_MIN_ATR = 0.25` (Architect-accepted,
  same class as FR-2 constants, pinned in tests, pending formal § lock).
  `candidate_from_route` gains a `tp_source` audit tag
  (`"structural_swing"` when the structural branch was used verbatim,
  else `"atr_fallback"`). `resolve_take_profit` untouched.
- **`smc/backtest/pipeline_adapter.py`** — the existing
  `candidate_from_route` call site now feeds
  `structural_target=structural_tp_target(...)` computed on the SAME
  §19-confirmed place-time prefix the scan consumed
  (`state.swing_index.original`), with the documented age bound
  (`poi_give_up_bars()` — a CPU/age cap, not give-up semantics).
- **Provenance threading (E1 pattern, appended backward-compatible):**
  `tp_source` rides CandidateEntry → `PendingOrder` →
  `BacktestPosition` (preserved verbatim on BE `modify_sl`) →
  `TradeRecord` → `trades.csv` appended column + `report.json` key.
  Audit only — never read by risk/fill/BE logic (test-enforced).
- **Design-note addendum** records the Architect's two constant rulings
  verbatim.

## 2. Not changed

SL policy (FR-2 `FR2_SL_*` constants, buffers), trigger A–F evaluation
bodies, pillars, detection, RiskEngine, BE/PureRunner/FVG-invalidation
semantics, `locked_constants.py` (diff empty — the interim constant is
module-level in `pipeline_bridge.py`, same class as FR-2's). The 30-pip
statement remains a MAE review yardstick (policy C) — no order path.

## 3. Tests

`04_SRC/tests/test_structural_tp_feed.py` — **24 tests, all passing:**
selector known-cases (LONG/SHORT nearest-in-price, no-swing → None,
below-guard → None, wrong-side ignored, recency tie-break, unconfirmed /
invalid / confirmed-at-placement-bar / non-finite excluded, age bound,
missing ATR), interim-constant pin, `resolve_take_profit` semantics
unchanged, provenance threading candidate→order→position (BE-preserving)
→TradeRecord→CSV/JSON, legacy-candidates default `None`, and the
audit-only guard (no `tp_source` reads in `smc/risk/**`).
Two pre-existing header-end assertions
(`test_identity_patch.py`, `test_residual_a_e1_entry_anchor.py`) were
updated for the appended `tp_source` column — the same documented
convention the E1 task used when it appended `entry_anchor`; column-order
(backward-compat) assertions retained and strengthened.

## 4. Measurement — frozen 3-month window, dual run

Window: M1 load 2025-08-01, exec 2025-09-01→11-30 (identical to the
pre-feed funnel — a direct before/after anchor). Composition imported
(`phase3_structure_funnel.run`), placed-order auditing via a harness
wrap of `PendingOrderBook.place` (FR-4 pattern, restored in `finally`).
Artifacts: `06_RESEARCH/results/structural_tp_feed/{run1,run2}/` +
`summary.json`; console `results/_tpf_console.log`.

| Metric | Pre-feed funnel | **With structural TP feed** |
|---|---|---|
| Routes | 9 {F 8, C 1} | 9 {F 8, C 1} — unchanged |
| Placed | 2 | 2 |
| **TP non-null on placed** | 100% | **100%** |
| **Structural share (placed)** | — | **50.0%** (1/2) |
| **4×ATR fallback share (placed)** | 100% | **50.0%** (1/2) |
| Fills / trades | 2 / 2 | 2 / 2 |
| Exit mix | stop_loss 2 (BE-scratch 1) | **take_profit 1** + stop_loss 1 (BE-scratch 1) |
| Net P/L (diagnostic) | −0.3013 | +0.4567 |
| Determinism | PASS | **PASS** (trades.csv + report.json byte-identical; trades.csv SHA-256 `00ee227e93ddf52d…`) |

Per-trade detail (run1 = run2):
- **poi-001022 (Trigger C, SHORT, entry 3490.257):** structural first-swing
  TP 3486.405 (guard-passing nearest low) — **HIT → take_profit +0.3852**.
  Pre-feed the same trade closed **stop_loss −0.3728** (4×ATR target ≈
  3459 never reached). This is the feed's mechanism working end-to-end:
  nearer structural target reached before the stop.
- **poi-024420 (Trigger F, LONG, entry 4244.725):** no qualifying swing →
  4×ATR fallback (4275.664) — **byte-identical to pre-feed** (BE scratch
  +0.0715, exit stop_loss). Fallback path provably unchanged.

## 5. Honest reading

- **Structural share 50% at n=2 placed** — no distribution claim; the
  selector + fallback are proven by tests, the split by two instrumented
  placed orders.
- **The C-trade exit flip (SL → TP)** is one trade on one window. It
  demonstrates the mechanism, not an edge. n=2 net +0.4567 vs −0.3013
  carries zero statistical meaning.
- **Exit-mix delta is the expected geometry change** (design §8 risk 2):
  a nearer structural target converts some would-be SL/BE-scratch exits
  into TP hits — and will conversely cause some would-be-runner trades
  to exit early. Both directions must be watched on any future wider
  diagnostic window before any Architect conclusion.
- No tuning occurred: the selector, guard, and age bound are exactly as
  locked in the accepted design; no threshold was adjusted to influence
  the shares.

## 6. Remaining risks (from design §8, unchanged)

Sparse-swing fallback dominance on other windows; tight-TP early exits
on choppy structures; zone-edge re-anchor interaction; PARTIAL quality
tagging still a separate track; `STRUCTURAL_TP_MIN_ATR` + the age-bound
reinterpretation still pending formal § lock (interim, pinned in tests).

---

**Artifacts:** harness `06_RESEARCH/scripts/structural_tp_feed_measurement.py`;
results `06_RESEARCH/results/structural_tp_feed/` (dual-run artifacts +
`summary.json` + per-run `placed_audit.json`); design
`06_RESEARCH/STRUCTURAL_TP_FEED_DESIGN.md` (with rulings addendum);
production diff: `pipeline_bridge.py`, `pipeline_adapter.py`,
`runner.py`, `orders.py`, `positions.py`, `reports.py`, `export.py`;
tests `tests/test_structural_tp_feed.py` (+2 documented header-assertion
updates). **No strategy is validated; nothing is promoted to live.**
