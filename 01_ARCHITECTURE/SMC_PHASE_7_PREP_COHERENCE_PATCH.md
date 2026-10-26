# Phase 7 Prep — Coherence Patch Design Note

Status: COMPLETE (all 510 tests green — 501 pre-existing + 9 new coherence-patch tests)
Scope: the seam-level prerequisites the cross-phase audit (Conditional GO) required before Phase 7. No MQL5 watchdog, no walk-forward / Monte Carlo, no O(bars²) redesign — those remain Phase 7 / V1.1.

---

## 1. Detection driver (CR1) — where it lives and what it does

**Location:** `04_SRC/smc/orchestration/detection_driver.py` — `DetectionDriver`.

This closes the Stage 0/1 → Stage 2 handoff that previously existed only as unit-test recipes. The driver is a production path from raw candle history to validated, armed POIs, composed ENTIRELY from existing frozen pieces:

```
candles (+ optional HTF series for M8)
  → swings            smc.detection.structural_swing_detector.detect_swings
  → liquidity levels  smc.detection.liquidity_scanner.scan
  → sweeps            smc.detection.sweep_detector.detect_sweeps
  → displacement      smc.detection.displacement_checker.check_displacement
  → M1–M8 detect      smc.poi.model_registry.build_registry
  → merge + validate  PipelineEngine.validate
  → arm_at            PipelineEngine.arm_at
```

Key semantics:

* **Displacement attribution (auto path)** — `attribute_displacement`: a POI is attributed the displacement of the MOST RECENT sweep (by candle index) whose direction matches the POI's zone direction (SSL sweep → LONG impulse, BSL sweep → SHORT impulse). The BOS level is the most recent prior swing extreme of the move direction (`most_recent_swing`, strictly before the sweep candle). A POI with NO preceding same-direction sweep gets NO displacement entry → **Pillar 2 rejects it (UNAVAILABLE, fail-fast)** — the driver never invents displacement. Documented residual: the sweep→impulse attribution is V1 recency+direction; per-POI deal-level attribution is the Phase-7 live driver's concern.
* **Injection seams (M4 contract preserved)** — `swings` / `liquidity_levels` / `displacement_map` can be supplied by an external Stage 0; `displacement_provider(pois, run)` receives the FINAL post-detect POI list so an externally computed map never mismatches freshly-detected POI ids.
* **Model failures are skips, not crashes** — a model whose `detect` raises on the window is recorded in `DriverResult.skipped_models` (tag → reason); the run continues.
* **Determinism / purity** — no MT5, no wall clock, no randomness; `arm_bar` defaults to the last window index (the §24 anchor) and is caller-overridable in bar-loop use.
* **No production wiring added in this patch** — the driver is the reusable batch surface; the per-bar rolling-window driver (backtest and paper/live) is Phase 7 (the runners continue to use `PipelineAdapter` for the per-bar loop).

## 2. Paper win/loss on close (CR2) — honest local determination

`smc/paper/runner.py` now feeds closed-trade outcomes into the risk guards instead of leaving paper fully disconnected:

* **Runner-issued closes (exact P/L)** — Friday EOD and risk `EXIT` closes exit at the bar-close price (the same convention as the backtest runner's risk exits): win/loss is `exit_price vs entry_price` and is fed exactly → `record_result`, plus `record_failed_sweep` when the trade carried a sweep level and the close was a loss.
* **Broker closes (bar-range determination)** — a position that disappears from `positions_get` is matched against THIS closed bar's range:
  * SL pierced (`bar.low <= sl` for LONG / `bar.high >= sl` for SHORT) → `stop_loss`, loss → `record_result(False)` + `record_sl_close(sl_level, bar_index)` (+ sweep guard when tracked);
  * TP reached (`bar.high >= tp` for LONG / `bar.low <= tp` for SHORT) → `take_profit`, win → `record_result(True)`;
  * a bar reaching neither level (or both — SL-first is the same-bar tie-break, mirroring the backtest fill model) → **UNKNOWN, no guard fed** (the honest V1 limitation stays: the closing deal's exact price/kind/P/L is not reconstructed from MT5 history; that is the Phase-7 upgrade).
* `_TrackedPosition` now carries `tp` (captured from the broker snapshot at fill) so TP outcomes are determinable.
* KPI `trade_closed` records carry the determined `win` / `kind` (`None` only for ambiguous closes).

## 3. Backtest running equity (I2) — units documented

`BacktestRunner` no longer sizes every decision from static `RunnerConfig.equity`:

* `_equity` starts at `config.equity` and moves with realized P/L on every close: `equity += realized_pnl × pip_value_per_lot`.
* **Units (documented choice):** `realized_pnl` is raw price×volume; multiplying by `pip_value_per_lot` converts it to the account-currency units `equity` already uses — the exact inverse of the sizing formula's divisor (`sl_distance × pip_value_per_lot`). A +1.0 raw P/L close on a pip-value-10 symbol adds 10.0 to equity.
* Sizing (`_process_entries`) reads `current_equity()` — verified by a test: after a 3.0-price-unit win on 0.05 lots, equity 50.0 → 51.5 and the next trade sizes 0.051 lots (vs 0.05), crossing the 0.001 lot grid.
* Paper sizing is unchanged — it already reads broker account equity (`connector.account_info()`), the live-truth equivalent.

## 4. Terminal-state retention (I4) — the rule

`PipelineEngine.prune_terminal(retain_ids)` drops TESTED/VIOLATED POIs from the arm indexes (`_episodes` + `_armed_order`) when their id is not retained; the shared state machine's per-id store is deliberately left intact (shared with the validation pipeline; a pruned id costs nothing). Returns the pruned ids.

`PipelineAdapter.prune_terminal_pois(retain_ids, bar_index)` adds the adapter-side safety: **workflow-live POIs are always retained** (a routed candidate awaiting its risk verdict must never be orphaned) and, when `bar_index` is given, **TESTED POIs still inside the first-touch routing window (touch bar + 1) are retained** — they may still produce their first workflow on this bar (pruning them there would orphan the route the scan is about to create — caught and fixed during this patch's test work).

The runners call it once per bar before the pipeline scan:
* `BacktestRunner.on_bar` (step 6) — retain ids of POIs with resting orders (`orders.active()`) or open positions (`positions.open_positions()`);
* `PaperRunner._entry_step` — retain ids from tracked pendings / positions.

## 5. Single §5 state machine (I1)

`PipelineEngine.__init__` now guarantees ONE `POIStateMachine`:

* no arguments → one machine created and shared into the validation pipeline;
* `state_machine=` supplied → the pipeline adopts it;
* `pipeline=` supplied → the engine adopts the pipeline's machine;
* both supplied but DIFFERENT instances → `ValueError` (a loud error, never a silent split-brain).

Verified by test: validate → arm → feed → expire all observe the same machine from both the engine and the pipeline side.

## 6. `execute_route` cleanup (I3)

`PipelineEngine.execute_route` is now explicitly marked **live-helper / superseded as the placement seam**: the shipped runners do not call it (backtest places through `PendingOrderBook`, paper through `BrokerAdapter` — both build `OrderRequest` at their own boundaries with `comment` = the §11 route identity). Retained for tests and direct live use; `build_limit_request` remains its single request builder — no third construction path was added.

## 7. Files changed

| File | Change |
|---|---|
| `04_SRC/smc/orchestration/detection_driver.py` | NEW — CR1 driver |
| `04_SRC/smc/orchestration/engine.py` | I1 single machine; I4 `prune_terminal`; I3 `execute_route` docstring |
| `04_SRC/smc/backtest/pipeline_adapter.py` | I4 `prune_terminal_pois` (workflow/touch-window safe) |
| `04_SRC/smc/backtest/runner.py` | I2 running equity + per-bar prune call |
| `04_SRC/smc/paper/runner.py` | CR2 close outcomes + `tp` tracking + per-bar prune call |
| `04_SRC/tests/test_coherence_patch.py` | NEW — 9 tests |
| `01_ARCHITECTURE/SMC_PHASE_7_PREP_COHERENCE_PATCH.md` | this note |

## 8. Residual limitations deferred to Phase 7 (no blocking questions)

* **Detection → POI attribution granularity:** displacement attribution is sweep-direction + recency (V1); per-trade deal-level attribution needs the live driver's rolling window.
* **Paper close P/L:** ambiguous closes (no SL/TP reachable on the closing bar) stay unrecorded; full MT5 deal-history reconstruction is the Phase-7 upgrade.
* **Rolling-window wiring:** the driver is batch; the per-bar live/backtest driver and M8's full multi-TF expansion are Phase 7.
* **POI `created_at` / id determinism:** POIs still default to wall-clock `created_at` and random uuid ids (pre-existing I4 note); byte-identical identity requires the caller to inject them from the run clock — unchanged in this patch.
* **O(bars²) prefix rescanning:** unchanged (documented in the cross-phase audit); incremental swing/scan state is a Phase-7 performance item.