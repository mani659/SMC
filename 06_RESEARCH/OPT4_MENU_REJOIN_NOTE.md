# OPT-4 — Menu-Path Rejoin (Measurement Only)

**Diagnostic only — not performance/edge.** No threshold/R7/pillar changes. OPT-B false, OPT-2 deferred. `LOGIC_CHANGED=NO`.

## Goal / scope
Recompute OPT-4-style place/zone taxonomy labels on **MENU `queue_menu_candidate` submits** (menu spine only, not adapter-only). Labels use the frozen taxonomy helpers (`completion_timing_label`, `completion_zone_edge_distance_atr`, `latest_atr`) — same convention as OPT-1/OPT-4 (nearest zone edge, 0 inside, Wilder prefix ATR; band = locked timing-study semantics). **R7 verdicts NOT recomputed/changed** (place frame is a submit approximation; risk-side blocks out of scope).

## Input / method
- Same spine as S2b: `run_batch` → `register_armed` → `on_execution_bar` → winner → `queue_menu_candidate` → `submit_entry` capture.
- Window `2024-04-01 .. 2024-05-01` (warmup `2023-12-01`), runtime-feasible, data `D:\Gold Scripts\MQL5\SMC\07_DATA\XAUUSD_M1.parquet` (fail-loud).
- **Confirm labels:** from winner `product_menu` stamp (`label_at_confirm`, `completion_ts`, zone, direction).
- **Submit/place-frame labels (OPT-4-style approximation):** first closed `M5` bar at/after `completion_ts`; label/distance via frozen helpers on that bar's close + Wilder prefix ATR(14). No trades placed.
- **Join keys:** submit_index, candidate poi/route/pillar_path, poi_id, tier, detection_tf, confirmation_tf, sweep_ts, completion_ts, zone [low,high], zone_direction.

## Counts / coverage
- `N_SUBMITS` (menu queue_menu_candidate → submit_entry): **5**
- `N_MENU_WINNERS`: **5** | `REGISTER_ARMED`: **14** | `SWEEPS`: **27**
- `LABEL_COVERAGE_PCT` (full = confirm label known/non-UNLOCATABLE **and** place-frame label known/non-UNLOCATABLE): **100.0%** (5/5)
- Gap reasons: `{}`

## Label mix
- Confirm (`label_at_confirm`): `{'ON_WINDOW': 2, 'LATE': 2, 'BEYOND_STOP_SIDE': 1}`
- Place/submit-frame (primary OPT-4 join labels): `{'ON_WINDOW': 3, 'LATE': 2}`
- Cross-tab confirm→place (no forced agreement): `{'ON_WINDOW->ON_WINDOW': 2, 'LATE->LATE': 2, 'BEYOND_STOP_SIDE->ON_WINDOW': 1}`

## Caveats
- Submit frame is an approximation (first closed exec bar at/after completion), not a full-stack broker place; risk-side blocks/R9-deferred placements out of scope. Menu path only. Counts/geometry labels only — no expectancy, no edge, no PnL. Small n (same window as S2b).

## Artifacts (gitignored)
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\opt4_menu_rejoin\opt4_menu_rejoin.csv`
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\opt4_menu_rejoin\opt4_menu_rejoin_summary.json`
