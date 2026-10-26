# COST MODEL — DESIGN LOCK (TIER-1)

**Date:** 2026-10-11 · **Authority:** Lead Architect Tier-1 directive (design lock before any long re-run or optimization).
**Status:** DESIGN ONLY — no code written, no constant touched, no threshold changed.
**Design lock status:** PROPOSED — requires Architect acceptance before implementation. Next after acceptance: implement cost model, then product baseline V2 (`06_RESEARCH/PRODUCT_BASELINE_V2_PLAN.md`).
**Evidence base:** `06_RESEARCH/QUANT_AUDIT_2026-10-08.md` §2-C2 (no commission/slippage/swap anywhere in code; baseline effectively zero-cost); `06_RESEARCH/PHASE_C_BASELINE_REPORT.md` §2 (frozen config `spread_price: 0.0`); code reads cited per section (`04_SRC/smc/backtest/fill_model.py`, `positions.py`, `runner.py`, `reports.py`, `risk/risk_engine.py`, `risk/spread_grading.py`, `execution/lot_sizing.py`).

---

## 1. Problem: the current baseline is effectively zero-cost

The frozen Phase C baseline (761 trades, PF 0.344, net −4.78% equity) was computed with **no trading cost charged on any fill**:

- `RunnerConfig.spread_price = 0.0` leaves the §28.5 spread gate off, and the gate is in any case a **binary entry block, not a per-fill charge** — `spread` appears in `backtest/*` only as the gate input (`backtest/runner.py:163-166,231,269-276,472,695-697`); `fill_model.py`, `orders.py` and `execution/*` contain zero `spread` references.
- Fills occur at the exact limit price (`fill_model.fill_price`, `fill_model.py:58-67`) with same-bar SL-first tie-breaks (`fill_model.py:112-129`) — conservative on price, silent on cost.
- `PositionStore._close` (`backtest/positions.py:250-272`) computes `realized_pnl` from price difference × sign × volume only; `BacktestRunner._record_close` (`backtest/runner.py:723-727`) adds it straight to equity. No commission, slippage, or swap term exists anywhere in `04_SRC` (verified: the only `commission|slippage|swap` hits in code are an MT5 order-deviation param, a geometry docstring, and a math proof — none is a backtest charge).
- The standing project language already admits this: the Phase C report calls the baseline a **"zero-cost upper bound"** (spread enters only through the gate, never worsens a fill).

Consequence: every headline number is the most optimistic accounting the stack can produce. No positive claim can be credible until costs exist; and because the gross baseline is already negative, the cost model's job is **honest measurement, not rescue** — costs make a negative book more negative, and that is the point.

## 2. Cost components for XAUUSD

All components are **additive charges applied at fill/close time. Fill prices never move** (the conservative limit-fill model is preserved; costs are a separate ledger, not price worsening).

### 2a. Commission — per lot, per side (PLACEHOLDER, blocking)

- Unit: account-currency (USD) per 1.0 lot per side (entry leg and exit leg charged separately).
- Value: **`<TBD — broker schedule>`**. Exness commission is account-type-dependent (Standard accounts are typically spread-only with zero commission; Zero/Raw-Spread accounts charge commission per lot per side on top of raw spreads). The baseline config MUST declare the account type whose schedule is used; MT5 does not expose commission programmatically, so the value is read once from the broker's published schedule and pinned in the run manifest.
- Blocking rule: **no costed baseline number is quoted until this placeholder is filled.** A run with commission unset reports costs as `unknown`, never as zero.

### 2b. Slippage model — FIXED POINTS for V1 (ATR fraction and none considered and ruled below)

- V1 rule: a fixed charge in **price points**, applied on **stop-loss exits and forced closes** (Friday EOD, circuit-breaker closes) only. Limit entries and limit TP exits cannot slip adversely by construction (fill at limit or better; the model already fills at limit, which is the conservative side), so charging slippage there would double-count conservatism already present.
- Value: **`<TBD — fixed points per affected exit leg>`**. Research precedent (not a default): the R6 experiment used `SLIPPAGE_PTS = 1.0` as a research-only sensitivity (`06_RESEARCH/scripts/smc_r6_bos_ob_m4_experiment.py:22`). The V1 default is adopted only by Architect ruling after broker measurement (demo/live divergence log) or explicit acceptance of the precedent as a conservative stand-in.
- Rejected alternatives (recorded so they are not re-litigated silently):
  - *ATR fraction*: couples the cost model to a volatility estimator and makes costs regime-dependent in a way that is harder to audit per fill. Deferred to post-V1, if ever.
  - *None (no slippage)*: optimistic; contradicts the conservative-defaults requirement. Rejected.

### 2c. Spread cost — half-spread per fill leg from reconstructed series (fallback constant TBD)

- The §28.5 gate stays exactly as-is (entry block only). The cost model adds what the gate never charged: **half the prevailing spread per fill leg** (entry leg at the fill bar, exit leg at the close bar), in price units, converted to ledger units per §4.
- Source hierarchy: (1) tick-reconstructed per-bar spread series from the 12.9 GB tick file (`bid/ask` present, window-matched to M1 — `DATA_ACCEPTANCE_REPORT.md` confirms reconstructability); (2) fallback constant **`<TBD>`** only if reconstruction is ruled out — candidate on record: **0.26 price units**, measured in sampled live windows (quant audit m9), usable as the fallback **only by explicit ruling**, never by silent default.
- Friday-EOD and breaker closes use the same half-spread leg costing (they are real exits).

### 2d. Swap — DEFERRED, with reason and a backfill path

- V1 charges **no swap**. Reasons: (1) overnight funding is broker-schedule-specific including triple-Wednesday conventions — another placeholder that would block V1 on the same schedule document as commission, with more convention surface; (2) the strategy flattens weekly (Friday EOD force-close), so weekend carry is structurally absent and the residual is multi-day intraday holds only; (3) commission + spread + slippage dominate the cost attribution for this holding profile and must land first.
- Honesty guard (this is what makes deferral acceptable rather than optimistic): the export **logs holding duration per trade now** (`bars_held`, and calendar days derived from bar timestamps — appended columns, backward compatible, same E1 pattern), so swap can be applied **retroactively without re-running** once the schedule is pinned. A deferred cost that cannot be backfilled would be a hidden optimism; a logged-and-backfillable one is a sequenced measurement.
- Revisit trigger: after commission + spread + slippage are merged and the first costed baseline exists.

## 3. Where costs apply in the stack (fill only; not detection)

Detection, pillars, triggers, routing, and the risk gate are untouched — costs exist strictly downstream of the fill:

| Seam | Change (implementation phase, not this note) | Unchanged |
|---|---|---|
| `backtest/positions.py` `PositionStore._close` (:250-272) | compute per-close cost breakdown and `net_realized_pnl`; `ClosedPosition` gains additive cost fields | gross `realized_pnl` formula; SL-first/TP logic; `original_sl` preservation |
| `backtest/runner.py` `BacktestRunner._record_close` (:723-727) | equity accumulates **net** realized; gross retained for attribution | equity identity otherwise (`_equity`, `current_equity`) |
| `backtest/reports.py` `TradeRecord.from_closed` + `build_report` | `pnl` stays gross-verbatim for backward compat; **new `pnl_net` + `cost_*` columns**; report aggregates both (costs-on headline, costs-off attribution) | existing gross columns byte-stable |
| `backtest/export.py` CSV/JSON | appended cost columns + `bars_held` (E1 append pattern; readers using `.get` unaffected) | column order of existing fields |
| New pure module (proposed: `smc/backtest/cost_model.py`) | deterministic `CostModel` (params in, per-leg charges out; no bar access except the spread value handed to it) | — |
| Paper runner | V1: log-only — record broker-visible costs per fill for the divergence log; model parity is a follow-on (see §8) | order placement, sizing, dry_run semantics |

Explicitly out of the cost path: `fill_model.py` (prices), `orders.py` (resting prices), `risk_engine.py` (gate decisions), `execution/lot_sizing.py` (sizing inputs — lots are computed pre-cost from SL distance; costs do not resize positions).

## 4. Accounting units vs the existing realized_pnl / equity path

The existing path, in the code's own arithmetic:

- `realized_pnl = (exit_price − entry_price) × direction_sign × volume_lots` — **price×volume ledger units** (`positions.py:261-262`).
- `equity += realized_pnl × pip_value_per_lot` with `pip_value_per_lot = 10.0`, `equity` starting at `10_000.0` (`runner.py:154-156,723-727`). Worked example in code units: 0.10 lots, $1.00 favorable move → `realized_pnl = 0.1` → equity `+0.1 × 10.0 = +$1.00`.

Cost-model conversion rule (locked by unit test at implementation):

- Every cost component is first computed in **account currency (USD)**: `commission_usd = rate_per_lot_per_side × lots × sides`, `spread_usd = half_spread_price × lots × <same USD-per-(price×lot) factor the book already uses>`, `slippage_usd = slip_points × lots`.
- Conversion uses the **existing divisor, redefined nowhere**: `cost_ledger_units = cost_usd / pip_value_per_lot`; `net_realized_pnl = realized_pnl − cost_ledger_units`; equity accumulates the net.
- The divisor (`pip_value_per_lot`) stays exactly what the sizing/equity path already uses. The cost model introduces no new currency factor, no new lot definition, no repricing of the gross book. A unit test locks the identity `equity_delta == (gross − costs) × pip_value_per_lot` on synthetic closes (see §7).

## 5. Defaults for V1 research (conservative, not optimistic)

Proposed defaults — effective only after Architect acceptance of this note (placeholders marked BLOCKING stop a costed run, they never silently become zero):

| Parameter | V1 default (proposed) | Direction of conservatism |
|---|---|---|
| Spread cost | half-spread per fill leg from the tick-reconstructed series; fallback constant TBD (candidate 0.26, ruling required) | costs present on every round trip |
| Commission | **BLOCKING placeholder** — no costed headline until the broker schedule value + account type are pinned in the manifest | missing cost is `unknown`, never 0 |
| Slippage | fixed points on SL exits + forced closes only; value TBD (research precedent 1.0 pt, ruling/measurement required) | adverse exits penalized; limit fills not double-penalized |
| Swap | 0 with `bars_held` logged for retroactive application | deferred openly, backfillable |
| Headline | **costs-on net**; costs-off gross retained beside it as the "upper bound" attribution | reader sees both, leads with net |
| Zero-cost runs | labeled `upper-bound / diagnostic`, never compared against costed runs as equals | Phase C language preserved |

## 6. What is NOT changed

- Entry logic (detection → pillars → triggers → routing → risk gate): byte-identical behavior with costs off; costs cannot block, resize, or retime any entry.
- SL/TP policy: structural TP feed as wired (`structural_swing` vs `atr_fallback` via `tp_source`, audit-only) plus the 4×ATR fallback; BE latch, FVG invalidation, Friday EOD, breaker — all untouched.
- Lot formula and its thresholds: §28.7 band (`RISK_PCT_MIN/MAX`), `LOT_MAX_SAFETY`, `min_lots`/`lot_step` — sizing inputs are pre-cost by design (§3).
- Fill prices and the conservative fill model (limit touch, SL-first same-bar, no partials).
- Spread-gate thresholds (§28.5 scale — the scale-mismatch question is a separate ruling track, see the companion plan note; this cost model neither fixes nor depends on it).
- Cost parameters live in **runner/research config, never in `locked_constants.py`**: they are measurement configuration, not strategy law. No new locked constant is created by this design.

## 7. Test plan (unit tests on cost application; no expectancy claims)

New test file at implementation (proposed `04_SRC/tests/test_cost_model.py`); every test asserts arithmetic/determinism only — **no test may assert profitability, expectancy, or any threshold on returns**:

1. Commission: synthetic closes across lots {0.01, 0.10, 1.00} × sides {LONG, SHORT} → `commission_usd == rate × lots × 2 legs` exactly; zero-lot/zero-rate edge cases.
2. Spread legs: half-spread at fill bar + half-spread at close bar; zero-spread → zero charge (preserves today's zero-cost behavior as a special case, labeled upper-bound).
3. Slippage scope: charged on SL exits and forced closes; **not** charged on limit entries or TP exits (same synthetic book, exit-reason parameterized).
4. Swap: always zero in V1; `bars_held` present on every exported close.
5. Ledger identity: `equity_delta == (gross − total_costs_ledger) × pip_value_per_lot` on synthetic closes; gross column unchanged vs pre-cost code path.
6. Config loud-fail: negative rates, negative slippage, missing commission value with costs enabled → constructor/config error, never silent zero.
7. Determinism: costed dual-run pair byte-identical (`trades.csv`/`report.json`) — extends the Phase C pair discipline to the net columns.
8. Paper logging (V1 scope): broker-visible commission/deal costs recorded per fill in the divergence log; model-vs-broker comparison deferred (see §8).

## 8. Open questions needing Architect ruling (list only)

1. Commission schedule: account type to declare (Standard spread-only vs Zero/Raw + commission) and the per-lot-per-side USD value(s) to pin; source document for the schedule.
2. Slippage value: adopt the 1.0 pt research precedent as the V1 default, or hold for broker-measured values from the divergence log first (with what interim value, if any)?
3. Spread fallback constant: accept 0.26 (sampled live windows) as the reconstruction-failure fallback, require a fuller spread-distribution study first, or block costed runs on reconstruction success?
4. Tick-spread reconstruction: approved as the V1 spread-cost source (12.9 GB tick, window-matched bid/ask), or is the fallback constant sufficient for V1?
5. Swap deferral accepted as sequenced (with `bars_held` backfill), or must schedule-derived swap block V1 alongside commission?
6. Config home: cost parameters in `RunnerConfig`, a separate `CostConfig` composed into it, or research-script-side only?
7. Paper-runner scope for V1: log-only divergence (proposed) vs full model parity on paper fills.
8. Spread-grade scale track: does the M4 ruling (separate track) need to land before, with, or after the cost model — or are the tracks independent?

---

```
COST_MODEL_DESIGN_STATUS: PROPOSED (acceptance required before implementation)
FILL_PRICES_CHANGED: NO (additive ledger only)
ENTRY_LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty (none proposed)
NEXT: Architect ruling on §8 → implement → unit tests per §7 → merge → product baseline V2
```
