# Plan-Complement Ledger — sweep + confirm → plan (Measurement Only)

**Diagnostic only — does NOT validate profitability or edge.** Menu `ProductMenuEngine` / `queue_menu_candidate` → `submit_entry` path only (not adapter-only). Read-only; no OPT-2, no band/R7/pillar/threshold tuning, OPT-B false. `RUN=post_f1f2`, `LOGIC_CHANGED=YES (F1 closed-bar HTF; F2 full confirmation evaluation)`. Plan completeness/consistency are **geometry/field checks only** (not a claim sweep+confirm "works" without Architect review of the sample).

## Goal
Record whether HTF/structure arm + sweep + LTF confirm → winner/submit produces a coherent trade PLAN (entry/SL/TP identity) and how often, with human-readable rows.

## Scope / data
- Window `2024-04-01 .. 2024-05-01` (warmup `2023-12-01`), `07_DATA/XAUUSD_M1.parquet` (fail-loud). Same spine/method as S2b/OPT-4 (runtime-feasible); extend if runtime allows.
- Path: menu `run_batch` → `register_armed` → `on_execution_bar` → `queue_menu_candidate` → `submit_entry` capture. `place_or_queue=submitted(harness)` = delivered to submit_entry in measurement harness (live runner may still block; not measured here).
- Funnel counters (measurement only): `{'detection_bars_seen': 12835, 'confirm_bars_seen': 185604, 'confirm_bars_evaluated': 2154, 'episodes_opened': 13, 'episodes_expired': 6, 'sweeps_out_of_window': 0, 'sweeps_total': 13, 'episodes_total': 13, 'winners_total': 7, 'active_episodes': 0, 'armed_pois': 13}`.

## Summary
- `N_EVENTS` (menu submits): **7** | `REGISTER_ARMED` **13** | `SWEEPS` **13** | `N_WINNERS` **7**
- `PCT_PLAN_COMPLETE` (entry+SL+TP all finite): **100.0%** (7/7)
- `PCT_PLAN_CONSISTENT` (among complete; pure geometry: SL/TP on correct side of entry): **100.0%** (7/7)
- Breakdown by trigger: `{'F_BOS_OB': {'n': 7, 'complete': 7, 'consistent': 7}}`
- Breakdown by det/confirm TF: `{'M15/M1': {'n': 6, 'complete': 6, 'consistent': 6}, 'H4/M15': {'n': 1, 'complete': 1, 'consistent': 1}}`
- Top gaps: `[('t_arm_not_stamped', 7)]` (missing TP/fields = incomplete plan, **not** a fix-thresholds instruction)

## Human sample (for Architect review — "would this plan match flowchart intent?")
Count: 7 (up to 10 / all if n≤10)

| # | poi_id | tier | det→conf | trigger | zone dir [low,high] | t_sweep / t_confirm | confirm label | plan (entry/sl/tp; tp_src, sl_src, orig_sl, anchor) | complete/consistent | place_or_queue | notes |
|---:|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 629e85ea-95ff-4619-9699-7a790906235d | M15 | M15→M1 | F_BOS_OB | short [2243.755,2265.035] | sweep=2024-04-02T09:30:00+00:00 confirm=2024-04-02T10:44:00+00:00 | ON_WINDOW | entry=2262.635 sl=2263.3434124424343 tp=2259.5841792841434 (tp_src=atr_fallback, sl_src=None, orig_sl=2263.3434124424343, anchor=ob_proximal) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |
| 1 | 34444ce2-eb81-4c2a-9391-590a7d941974 | M15 | M15→M1 | F_BOS_OB | long [2338.125,2364.135] | sweep=2024-04-11T12:30:00+00:00 confirm=2024-04-11T14:17:00+00:00 | ON_WINDOW | entry=2339.618 sl=2337.189590380532 tp=2345.804050339349 (tp_src=atr_fallback, sl_src=None, orig_sl=2337.189590380532, anchor=ob_proximal) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |
| 2 | 1f2e72a1-141c-4cc6-9124-5da50e56f544 | M15 | M15→M1 | F_BOS_OB | short [2337.725,2381.945] | sweep=2024-04-15T19:00:00+00:00 confirm=2024-04-15T20:03:00+00:00 | BEYOND_STOP_SIDE | entry=2337.725 sl=2382.2994889554247 tp=2334.6520967893716 (tp_src=atr_fallback, sl_src=None, orig_sl=2382.2994889554247, anchor=zone_edge_reanchor) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |
| 3 | d1dd8488-12a3-4e3a-8457-55c84476edfe | M15 | M15→M1 | F_BOS_OB | short [2382.685,2400.575] | sweep=2024-04-19T17:00:00+00:00 confirm=2024-04-19T17:39:00+00:00 | ON_WINDOW | entry=2398.245 sl=2399.0483903213562 tp=2394.442931933945 (tp_src=atr_fallback, sl_src=None, orig_sl=2399.0483903213562, anchor=ob_proximal) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |
| 4 | 0599f116-5fa3-46f0-a9ff-07182798eb8b | H4 | H4→M15 | F_BOS_OB | long [2375.205,2377.155] | sweep=2024-04-19T12:00:00+00:00 confirm=2024-04-19T18:00:00+00:00 | LATE | entry=2377.155 sl=2373.773120386978 tp=2396.2467281736235 (tp_src=atr_fallback, sl_src=None, orig_sl=2373.773120386978, anchor=zone_edge_reanchor) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |
| 5 | e8cf704b-0b28-4784-8d30-db3d0017ca32 | M15 | M15→M1 | F_BOS_OB | long [2295.985,2330.345] | sweep=2024-04-23T01:45:00+00:00 confirm=2024-04-23T02:59:00+00:00 | ON_WINDOW | entry=2302.905 sl=2300.558477677937 tp=2309.7171811303033 (tp_src=atr_fallback, sl_src=None, orig_sl=2300.558477677937, anchor=ob_proximal) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |
| 6 | 1160691c-24eb-4ded-a425-c7977909a330 | M15 | M15→M1 | F_BOS_OB | short [2324.555,2336.345] | sweep=2024-04-26T04:30:00+00:00 confirm=2024-04-26T05:12:00+00:00 | ON_WINDOW | entry=2335.315 sl=2335.7439671509433 tp=2333.404184496488 (tp_src=atr_fallback, sl_src=None, orig_sl=2335.7439671509433, anchor=ob_proximal) | complete=YES consistent=YES | submitted(harness) | t_arm_not_stamped |

## Caveats
- `t_arm` not stamped in `product_menu`; reported as gap note (honest). Small n (same window). Consistency is geometric only (directional side checks). No expectancy, no edge, no PnL. **Do not claim sweep+confirm "works" from plan_complete alone without Architect review of the sample.**

## Artifacts (gitignored)
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\plan_complement_ledger_post_f1f2\plan_complement_ledger.csv`
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\plan_complement_ledger_post_f1f2\plan_complement_summary.json`
