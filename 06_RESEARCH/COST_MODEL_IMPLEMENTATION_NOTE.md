# COST MODEL V1 — IMPLEMENTATION NOTE

**Date:** 2026-10-11 · **Authority:** Lead Architect acceptance 2026-10-11 (design lock `COST_MODEL_DESIGN.md` + `PRODUCT_BASELINE_V2_PLAN.md` with the rulings table).
**IMPL_STATUS: PASS.** Suite **917 → 938** (21 new, zero regressions); `locked_constants.py` diff empty.
**Diagnostic only — no expectancy, PnL, win-rate, or edge claim is made anywhere in this note or the code.**

---

## 1. What was built (fill-only additive ledger; prices unchanged)

A pure, deterministic cost pricer plus fill/close/report/export seams. No detection, pillar, trigger, routing, risk-gate, sizing, fill-price, SL/TP, or locked-constant logic was touched.

| Seam (file) | Change |
|---|---|
| `smc/backtest/cost_model.py` (NEW, stdlib-only + `CloseKind`) | `CostConfig` (measurement config, NOT a locked constant) + `CostModel` (bound pricer) + `CostBreakdown` + pure helpers (`resolve_leg_spread`, `slippage_in_scope`, `net_ledger`, `normalize_spread`) |
| `smc/backtest/positions.py` | `BacktestPosition.entry_spread_price` (appended, None = unknown; copied verbatim by `modify_sl`); `ClosedPosition` += 6 cost legs + `bars_held` (appended, zero/None defaults); `PositionStore.bind_cost_model()` (unbound = legacy zero-cost path); `open`/`apply_bar`/`close` accept optional spread kwargs (defaults preserve all existing call sites) |
| `smc/backtest/runner.py` | `RunnerConfig.cost: CostConfig` (appended, default-constructed); runner binds the store's pricer at construction; entry/exit spreads threaded from `_spread_price` at fill/close (SL+TP physical, risk exits, Friday/breaker closes); `_record_close` moves equity by `(realized_pnl − cost_ledger) × pip_value_per_lot` (identical to legacy when costs are zero) |
| `smc/backtest/reports.py` | `TradeRecord` += 7 cost fields (appended); `CoreMetrics` += 6 cost totals (appended, gross fields untouched); `GroupMetrics` += `net_pnl_after_cost` + `total_cost_usd` (appended); `build_report` aggregates both books |
| `smc/backtest/export.py` | CSV header/rows += 7 appended cost columns; JSON trades += 7 keys; metrics JSON += 6 totals; group dicts += 2 net keys (append-only contract preserved) |
| `04_SRC/tests/test_cost_model.py` (NEW, 21 tests) | arithmetic identities, zero-cost regression, both sides, fallback path, loud-fail, runner integration, report/export contract — arithmetic only, no MT5 |
| 3 existing test files (tails/fakes only) | `test_structural_tp_feed.py`, `test_identity_patch.py`, `test_residual_a_e1_entry_anchor.py`: export-tail assertions extended to the new appended columns; metrics fakes carry the new total fields. No expectation, threshold, or behavior assertion changed |

**Cost fields (COST_FIELDS):** per trade/close — `commission_usd, spread_cost_usd, slippage_usd, swap_usd (= 0.0 V1), cost_usd, pnl_net, bars_held` (+ `cost_ledger` on the close record); aggregates — `total_commission_usd, total_spread_cost_usd, total_slippage_usd, total_swap_usd, total_cost_usd, net_pnl_after_cost`.

## 2. Semantics locked in code (per the rulings)

- **Fill only; prices unchanged:** limit fills, SL-first same-bar, no partials — all intact. Costs never move, block, resize, or retime anything; `risk.record_result` still receives win-only outcomes.
- **Commission:** both legs on every close (V1 has no partials), USD-quoted, ledger-converted with the run's own `pip_value_per_lot`; default **0.0** until the operator pins a broker schedule (ruled).
- **Slippage:** fixed points, exit-leg only, charged on every exit **except take-profit** (resting-limit exits are provably slip-free; SL, risk exits, Friday EOD, and breaker closes all exit market-ish). Unknown kinds are charged (unknown exit = market exit until proven a limit).
- **Half-spread:** per leg from each leg's own spread; unknown spread (None or ≤ 0 — legacy `spread_price=0.0` means "gate off", never "zero spread") falls back to `spread_fallback_price` (0.26) when enabled.
- **Swap:** always 0.0 (deferred); `bars_held = exit_bar − entry_bar` recorded on every close so swap stays backfillable without a re-run.
- **Units (defined once):** spread/slippage natively price×volume ledger units; commission USD→ledger via ÷ `pip_value_per_lot`; `cost_usd = cost_ledger × pip_value_per_lot`; net = gross − ledger. Locked by unit test (`equity_delta == (gross − costs) × pip_value`).
- **Costs-on/off:** `apply_costs` master switch (default True); old behavior reproduces exactly with all costs zero — and, by §3, with the constructor defaults.

## 3. Defaults decision — one flagged deviation (needs no code change either way)

Specified research defaults (implement prompt) vs implemented constructor defaults:

| Parameter | Specified | Implemented | Status |
|---|---|---|---|
| `apply_costs` | ON | **True** | as specified |
| `commission_usd_per_lot_per_side` | 0.0 (ruled) | **0.0** | as ruled |
| `slippage_points` | "conservative research value from design note" | **0.0** | **FLAGGED — see below** |
| `spread_fallback_price` | 0.26 | **0.26** | as specified (value) |
| `apply_half_spread` | on (implied) | **False** | **FLAGGED — see below** |

**Why:** the design note's slippage value was "TBD (research precedent 1.0 pt, ruling required)" and the acceptance ruling set no value — so no nonzero default was ever ruled. More importantly, constructor defaults must preserve the frozen economics asserted by the 917 existing tests (exact-equity/gross assertions under default configs); silent nonzero defaults would rewrite those expectations without a ruling. Research runs set the research values explicitly — one config line each (`slippage_points=1.0`, `apply_half_spread=True`) — and the 21 new tests prove the charged paths exactly.
**Ask:** Architect confirms zero-preserving constructor defaults (recommended — no action), or rules explicit research defaults plus an approved procedure for updating the affected frozen expectations.

## 4. Not changed (bans compliance)

No entry/SL/TP/lot-threshold change (`LOT_MAX_SAFETY`, risk band, sizing path intact); no spread-grade threshold rewrite (untouched — separate track); no WF/MC; no locked-constant edit (cost params live on `RunnerConfig`, never in `locked_constants.py`); paper runner untouched (prompt-allowed; broker fills already carry real costs — parity is a follow-on, listed in the design note §8).

## 5. Verification

- New `test_cost_model.py`: **21 passed** (commission both-legs math; per-leg half-spread ledger math; slippage scope matrix incl. unknown-kind; swap zero; net identity; known/fallback/disabled spread paths; `apply_costs=False` zeros; default-config zeros; negative-config + bad-lots/pip loud-fail; unbound-store zeros + `bars_held`; entry-spread normalization + BE-modify preservation; SHORT-side signs; runner-level zero-config legacy-equity identity; runner-level exact costed TP math + net equity; costed SL slippage math; runner-level fallback path; report totals + group nets; CSV/JSON cost columns; zero-cost report identity).
- Full suite: **938 passed** (917 + 21), zero regressions. The only pre-existing test edits are export-tail/fake extensions (§1) — no frozen expectation was re-valued.
- `locked_constants.py` diff empty. No expectancy language anywhere in code, tests, or this note.

---

**NEXT_READY: staged product baseline pilot** (short window, costs on, determinism pair — NOT the full 5y yet; gated additionally on the §3 defaults confirmation only insofar as the pilot config must state its cost values explicitly).
