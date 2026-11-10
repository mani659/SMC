# Menu-path trade funnel — 1 month (2024-04-01 → 2024-05-01)

`LOGIC_CHANGED: NO` (research harness + note only). No production logic, no locked
constants, no OPT-B, no OPT-2, no structural TP, no threshold/tier/trigger retune.

**Stage metric = trades exist / explained (countable closes or a clear drop reason),
not PnL / not edge.** `NET_PL_DIAGNOSTIC` below is a raw `price * volume` sum
labelled **NOT performance, NOT edge**.

## Source of truth (reproducible, artifact-derived)

- Script: `06_RESEARCH/scripts/menu_trade_funnel.py`
- Artifacts (gitignored): `06_RESEARCH/results/menu_trade_funnel_1m/{funnel_summary.json,trades.csv,drops.csv,run.log}`
- Command: `MENU_FUNNEL_OUT=06_RESEARCH/results/menu_trade_funnel_1m MENU_FUNNEL_LABEL=menu_trade_funnel_1m PYTHONPATH=04_SRC python 06_RESEARCH/scripts/menu_trade_funnel.py`
- Data: `07_DATA/XAUUSD_M1.parquet` (warmup 2023-12-01). Fail-loud on missing/invalid data.
- M1 spine: `load_m1` reused from `06_RESEARCH/scripts/plan_complement_ledger.py`.
- Deterministic run: 43 batches, `BATCH_ERRORS=0`, `MENU_ERRORS=0`, `EXEC_BARS_RUN=6072` (M5), `ELAPSED_SECONDS=1115.8`.

## Funnel (every plan accounted for)

| Stage | Count | Notes |
|---|---:|---|
| Armed POIs (total) | 45 | `armed_pois_live_at_end=31` |
| Menu sweeps (episodes) | 17 | `sweeps_out_of_window=0`, `sweeps_pre_arm=0`, `armed_without_ts=0` |
| Winners / plans | 14 | `menu_submitted=14` (no F7 retry path in backtest; see limitations) |
| Accepted / placed | 10 | `placed_with_tp=10`, `placed_resting` peak 10 |
| Blocked (no order) | 5 | `session=2`, `skip_place_far_from_zone=3` (runner `blocked_log` reason codes) |
| Filled | 9 | `cancel_calls_raw=10`, `withdrawn_before_fill=1` |
| Closed | 9 | `open_at_end=0`, `resting_at_end=0` |
| Drops after plan (not closed) | 5 | stage mix over winners: `closed=9, blocked=2, r7_deferred=2, placed=1` |

Menu counters: `detection_bars=12835, confirm_bars=186, confirm_bars_evaluated=1890, episodes=17, expired=3, winners_total=14, menu_blocked_by_state=0`. R9 intents: `armed=3, intent_expired_no_reentry=1, placed=1, dropped_portfolio_friday=1`. R7 re-entry: 1 placed then closed as `r7_reentry:stop_loss` (ticket 4 / `poi-001433`).

**Filled == 9 (≥ 3–7) ⇒ stage success threshold met.** No wider window required. This is a plumbing/count diagnostic, not edge.

## Per-plan outcome (drops.csv, 14 winners)

| # | POI | Tier | Det/Conf | Dir | Stage | Reason | Ticket |
|---:|---|---|---|---|---|---|---|
| 1 | poi-000178 | M15 | M15/M1 | SHORT | closed | stop_loss | 1 |
| 2 | poi-000963 | M15 | M15/M1 | LONG | closed | stop_loss | 2 |
| 3 | poi-001356 | M15 | M15/M1 | SHORT | blocked | session | — |
| 4 | poi-001360 | M15 | M15/M1 | SHORT | r7_deferred | intent_expired_no_reentry | — |
| 5 | poi-001433 | H4 | H4/M5 | SHORT | closed | r7_reentry:stop_loss | 4 |
| 6 | poi-001648 | H4 | H4/M5 | SHORT | closed | stop_loss | 3 |
| 7 | poi-001293 | M15 | M15/M1 | SHORT | closed | take_profit | 5 |
| 8 | poi-001877 | H4 | H4/M15 | LONG | r7_deferred | dropped_portfolio_friday | — |
| 9 | poi-001802 | M15 | M15/M1 | LONG | closed | stop_loss | 6 |
| 10 | poi-001876 | H4 | H4/M5 | LONG | closed | stop_loss | 7 |
| 11 | poi-000707 | M15 | M15/M1 | LONG | closed | stop_loss | 8 |
| 12 | poi-001402 | H1 | H1/M5 | LONG | blocked | session | — |
| 13 | poi-002256 | M15 | M15/M1 | SHORT | closed | stop_loss | 9 |
| 14 | poi-002445 | M15 | M15/M1 | LONG | placed | withdrawn_before_fill | 10 |

`TOP_DROPS` (non-closed only): `session=2, intent_expired_no_reentry=1, dropped_portfolio_friday=1, withdrawn_before_fill=1`.

## Exits (closed trades, trades.csv)

- `EXIT_MIX`: `stop_loss=8, take_profit=1` (9 closed). `BE_SCRATCH_DERIVED=1` (ticket 7 / `poi-000707`, LONG, stop moved off `original_sl` and closed at moved level, `bars_held=13`, `+0.030914` raw — derived from a moved stop, not guessed). No other BE scratch.
- `LOTS_AT_SAFETY_CAP=9/9` (all `volume=0.1`, locked `LOT_MAX_SAFETY=0.10` binds every trade). `price_at_risk_raw` (placed-size, `|entry-original_sl|*volume`, ledger units) recorded per trade; the safety cap means intended risk fraction is not what the position carries on tight stops (diagnostic, not adjusted).
- All 9 trade `poi_id`s ⊆ winner `poi_id`s; all 9 have a `route_id`. No adapter-scan contamination. All `tp_source=atr_fallback`.
- `NET_PL_DIAGNOSTIC`: `n_closed=9, sum_realized_pnl_raw=-1.429148` — **raw price*volume sum, NOT performance, NOT edge** (zero spread/cost).

## Blocked / drop classification

- `blocked/session` (2): runner `blocked_log` reason `session` — no order placed.
- `blocked/skip_place_far_from_zone` (3 in blocked counts): runner `blocked_log` reason `skip_place_far_from_zone` — no order placed.
- `r7_deferred/intent_expired_no_reentry` (1): R9 intent armed, no re-entry placement before intent expiry.
- `r7_deferred/dropped_portfolio_friday` (1): R9 intent dropped by portfolio Friday handling.
- `placed/withdrawn_before_fill` (1): order placed (ticket 10) then cancelled/withdrawn before fill (`cancel_calls_raw=10` total over filled+withdrawn).
- `closed/r7_reentry:stop_loss` (1): placed via R9 re-entry path, later stopped out (counted as a closed outcome, not a drop).

## Limitations & conventions (read before comparing)

- **Single submit, no F7 in backtest:** `BacktestRunner` has no `supports_candidate_outcomes`, so each winner is submitted once via `queue_menu_candidate` immediate drain (`MENU_RETRY` all retry counters 0 except `menu_submitted=14`). Live-only F7 accept/retry/resubmit is not exercised here.
- **Zero spread + cost:** backtest pricing/cost model; `cost_usd=0.0`. Diagnostic only.
- **Armed 45 vs post_f5f7's 13:** this harness runs the full path (batch → I4/F6 prune+retire of the armed state → menu). 45 is total armed POIs registered over the month; 31 remained live at end. Not comparable to the ledger's net armed snapshot without the same lifecycle accounting.
- **`as_of` = bar close:** `MultiTFProductRuntime` and menu are fed at M5 close (`_close_ts`), matching the ledger convention (not the live loop's open stamp).
- **Batch cadence:** every 48th M15 close (frozen ledger cadence), 43 batches for the 2024 M15 bars in-window.
- **M1 confirmations sampled at M5 closes:** menu confirmation evaluated on execution-bar (M5) closes; `confirm_bars_evaluated=1890`.
- **Entry-touch vs fill:** 5/9 fills occur on bars where the limit price is outside `[low,high]` of that bar record in the sampled check (runner fill semantics govern acceptance); exits verified inside/consistent with exit bars per kind. Treat as runner-ordering detail, not a hand adjustment.
- **LOT_MAX_SAFETY cap:** binds all 9 trades (0.10 lots) — sizing/risk is capped by the locked safety limit regardless of distance-derived size.
- No MT5 terminal / live smoke in scope.

## Verification

- Harness smoke: 320-bar timestamp-bounded run produced consistent artifacts (separate out dir).
- Classifier unit-shaped checks (POI-keyed, R7/withdrawn/fill-consumption cases) passed during development.
- Suite (this repo state): `1437 passed, 6 skipped` (`PYTHONPATH=04_SRC python -m pytest -q 04_SRC/tests --ignore=04_SRC/tests/test_review_merge_smoke.py`).
- `04_SRC/smc/config/locked_constants.py` unchanged vs `HEAD` and `baseline_pre_fix`.
- `LOGIC_CHANGED: NO`.