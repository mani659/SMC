# S2 — Menu Confirm Lag (Measurement Only)

**Diagnostic only — not performance/edge.** OPT-B false, OPT-2 deferred, W1 context_only. No pillar/threshold tuning. `LOGIC_CHANGED=NO` (research script only).

## Scope
- Path: MENU spine only — `MultiTFProductRuntime.run_batch` → `menu.register_armed` (sparse cadence, every 48 M15 steps) + dense M15-timeline `menu.on_execution_bar` (closed detection/confirmation streams) → winner → `queue_menu_candidate` → `submit_entry` stub.
- Not adapter-only scan.
- Data: `D:\Gold Scripts\MQL5\SMC\07_DATA\XAUUSD_M1.parquet`
- Window: `2024-04-01 .. 2024-04-15` (warmup `2023-12-01`), XAUUSD, detection TFs `['D1', 'H4', 'H1', 'M15']`.
- Tiers: DAY(D1→H1), H4(H4→M5,M15), H1(H1→M5,M1), M15(M15→M1). Exec M5.

## Sample
- `N_WINNERS`: **1** (menu winners, deduped by episode/route/confirm_tf)
- `REGISTER_ARMED`: **9** | `QUEUE_SUBMITS`: **1**
- By tier: `{'H4': 1}` | By detection TF: `{'H4': 1}`

## Lag (detection-TF bars, sweep_close → confirm completion bar)
- n=1, min=0.0, p25=0.0, **median=0.0**, p75=0.0, max=0.0
- Lag = count of detection-TF bars with `sweep_close < bar_close <= t_confirm` (research measure; see CSV for per-winner `lag_bars_det_tf/confirm_tf/exec_m5`).

## Zone relation at confirm (from `product_menu.label_at_confirm`, timing-study taxonomy)
- `CONFIRM_OUTSIDE_BAND_PCT` (LATE or BEYOND_STOP_SIDE over known labels): **0.0%** (known n=1)
- `CONFIRM_OUTSIDE_ZONE_PCT` (same measurable definition; exact inside/outside raw zone beyond label is NA without extra geometry): **0.0%**
- Label counts: `{'ON_WINDOW': 1}`
- Mapping note: `ON_WINDOW` = within locked timing band/window; `LATE`/`BEYOND_STOP_SIDE` = outside band (displaced/beyond stop side). `UNLOCATABLE` excluded from %; treat as unknown.

## Artifacts (gitignored results ok)
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\s2_menu_confirm_lag\s2_menu_winners.csv`
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\s2_menu_confirm_lag\s2_menu_confirm_lag_summary.json`

## Bans honored
No OPT-2, OPT-B remains false, no pillar/threshold tuning, no profitability claims from lag stats.

## Errors
[]

## Run note
- **Small-n measurement slice:** window shortened to `2024-04-01..2024-04-15` (covers first proven winner region) for runnability in this environment; full 3-month extension was compute-heavy here. Method/path identical to confirm-smoke (menu spine only). **Extend window for denser lag distribution** before drawing any stronger timing conclusions. `n=1` is diagnostic only.
