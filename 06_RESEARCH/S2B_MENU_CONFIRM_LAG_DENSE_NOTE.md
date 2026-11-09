# S2b — Denser Menu Funnel + Confirm-Lag (Measurement Only)

**Diagnostic only — not performance/edge.** OPT-B false, OPT-2 deferred, W1 context_only. No pillar/threshold tuning. No threshold fishing to inflate n. `LOGIC_CHANGED=NO`.

## Method (same menu spine)
`MultiTFProductRuntime.run_batch` → `menu.register_armed` (sparse cadence, every 48 M15 steps, fixed) + dense M15-timeline `menu.on_execution_bar` (closed detection/confirmation streams) → winner → `queue_menu_candidate` → `submit_entry`. Not adapter-only.

## Window / data
- `D:\Gold Scripts\MQL5\SMC\07_DATA\XAUUSD_M1.parquet` (fail-loud if missing)
- Window `2024-04-01 .. 2024-05-01` (warmup `2023-12-01`), XAUUSD. Detection TFs D1/H4/H1/M15. Tiers DAY(D1→H1), H4(H4→M5,M15), H1(H1→M5,M1), M15(M15→M1).

## Funnel (true counts)
- `REGISTER_ARMED`: **14**
- `SWEEPS` (`menu.sweeps_total`): **27**
- `N_WINNERS`: **5** (deduped episode/route/confirm_tf) | `QUEUE_SUBMITS`: **5**
- Soft target n>=20: **not met (true n=5; no threshold fishing)**

## Lag (detection-TF bars, `sweep_close < bar_close <= t_confirm`)
- n=5, min=0.0, p25=0.0, **median=0.0**, **p75=1.0**, max=5.0

## Label mix / zone relation (`product_menu.label_at_confirm`, timing-study taxonomy)
- `LABEL_MIX`: `{'ON_WINDOW': 2, 'LATE': 2, 'BEYOND_STOP_SIDE': 1}`
- `CONFIRM_OUTSIDE_BAND_PCT` (LATE or BEYOND_STOP_SIDE over known labels): **60.0%** (known n=5). ON_WINDOW=inside band/window; LATE/BEYOND_STOP_SIDE=outside band; UNLOCATABLE excluded. Exact raw-zone geometry beyond label = NA.
- By det_tf: `{'H4': 4, 'M15': 1}` | By tier: `{'H4': 4, 'M15': 1}` | By trigger: `{'F': 5}`

## Artifacts (gitignored)
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\s2b_menu_confirm_lag_dense\s2b_menu_winners.csv`
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\s2b_menu_confirm_lag_dense\s2b_menu_confirm_lag_dense_summary.json`

## Errors
[]
