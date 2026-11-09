# Plan-Complement Ledger — sweep + confirm → plan (Measurement Only)

**Diagnostic only — does NOT validate profitability or edge.** Menu `ProductMenuEngine` / `queue_menu_candidate` → `submit_entry` path only (not adapter-only). Read-only; no OPT-2, no band/R7/pillar/threshold tuning, OPT-B false. `LOGIC_CHANGED=NO`. Plan completeness/consistency are **geometry/field checks only** (not a claim sweep+confirm "works" without Architect review of the sample).

## Goal
Record whether HTF/structure arm + sweep + LTF confirm → winner/submit produces a coherent trade PLAN (entry/SL/TP identity) and how often, with human-readable rows.

## Scope / data
- Window `2024-04-01 .. 2024-05-01` (warmup `2023-12-01`), `07_DATA/XAUUSD_M1.parquet` (fail-loud). Same spine/method as S2b/OPT-4 (runtime-feasible); extend if runtime allows.
- Path: menu `run_batch` → `register_armed` → `on_execution_bar` → `queue_menu_candidate` → `submit_entry` capture. `place_or_queue=submitted(harness)` = delivered to submit_entry in measurement harness (live runner may still block; not measured here).

## Summary
- `N_EVENTS` (menu submits): **5** | `REGISTER_ARMED` **14** | `SWEEPS` **27** | `N_WINNERS` **5**
- `PCT_PLAN_COMPLETE` (entry+SL+TP all finite): **100.0%** (5/5)
- `PCT_PLAN_CONSISTENT` (among complete; pure geometry: SL/TP on correct side of entry): **100.0%** (5/5)
- Breakdown by trigger: `{'F_BOS_OB': {'n': 5, 'complete': 5, 'consistent': 5}}`
- Breakdown by det/confirm TF: `{'H4/M5': {'n': 2, 'complete': 2, 'consistent': 2}, 'H4/M15': {'n': 2, 'complete': 2, 'consistent': 2}, 'M15/M1': {'n': 1, 'complete': 1, 'consistent': 1}}`
- Top gaps: `[('t_arm_not_stamped', 5)]` (missing TP/fields = incomplete plan, **not** a fix-thresholds instruction)

## Human sample (for Architect review — "would this plan match flowchart intent?")
Count: 5 (up to 10 / all if n≤10)

| # | poi_id | tier | det→conf | trigger | zone dir [low,high] | t_sweep / t_confirm | confirm label | plan (entry/sl/tp; tp_src, sl_src, orig_sl, anchor) | complete/consistent | place_or_queue | notes |
|---:|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 4bcbaef0-ec26-41a8-9066-fbca076e8a34 | H4 | H4→M5 | F_BOS_OB | short [2243.755,2265.585] | sweep=2024-04-02T08:00:00+00:00 confirm=2024-04-02T12:30:00+00:00 | ON_WINDOW | entry=2257.655 sl=2260.122648619352 tp=2248.7930184086417 (tp_src=atr_fallback, sl_src=None, orig_sl=2260.122648619352, anchor=ob_proximal) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |
| 1 | e172c22e-7914-40fb-bb24-062e316c1785 | H4 | H4→M15 | F_BOS_OB | short [2373.195,2378.248] | sweep=2024-04-18T04:00:00+00:00 confirm=2024-04-18T14:00:00+00:00 | ON_WINDOW | entry=2373.195 sl=2379.7081362517206 tp=2353.726516643724 (tp_src=atr_fallback, sl_src=None, orig_sl=2379.7081362517206, anchor=zone_edge_reanchor) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |
| 2 | 7de39ddd-187f-492e-b836-3a3a21b23383 | H4 | H4→M15 | F_BOS_OB | long [2375.205,2377.155] | sweep=2024-04-19T12:00:00+00:00 confirm=2024-04-19T18:00:00+00:00 | LATE | entry=2377.155 sl=2373.773120386978 tp=2396.2467281736235 (tp_src=atr_fallback, sl_src=None, orig_sl=2373.773120386978, anchor=zone_edge_reanchor) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |
| 3 | 257bd700-6d68-42fe-8780-6171fdf4c555 | M15 | M15→M1 | F_BOS_OB | long [2338.125,2364.135] | sweep=2024-04-26T19:00:00+00:00 confirm=2024-04-26T20:30:00+00:00 | BEYOND_STOP_SIDE | entry=2364.135 sl=2338.037406571285 tp=2365.302912382871 (tp_src=atr_fallback, sl_src=None, orig_sl=2338.037406571285, anchor=zone_edge_reanchor) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |
| 4 | b09446c2-0b49-4258-8903-3197da9c521b | H4 | H4→M5 | F_BOS_OB | long [2321.985,2323.995] | sweep=2024-04-29T00:00:00+00:00 confirm=2024-04-29T06:45:00+00:00 | LATE | entry=2323.995 sl=2321.452160460286 tp=2331.0995271961874 (tp_src=atr_fallback, sl_src=None, orig_sl=2321.452160460286, anchor=zone_edge_reanchor) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |

## Caveats
- `t_arm` not stamped in `product_menu`; reported as gap note (honest). Small n (same window). Consistency is geometric only (directional side checks). No expectancy, no edge, no PnL. **Do not claim sweep+confirm "works" from plan_complete alone without Architect review of the sample.**

## Artifacts (gitignored)
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\plan_complement_ledger\plan_complement_ledger.csv`
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\plan_complement_ledger\plan_complement_summary.json`
