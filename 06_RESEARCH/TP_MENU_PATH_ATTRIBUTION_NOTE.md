# TP Source Attribution — MENU path (measurement only)

**Diagnostic only — does NOT validate profitability or edge.** Read-only join over the same
5 plan-complement ledger submits (menu `queue_menu_candidate` → `submit_entry`), window
`2024-04-01..2024-05-01` (warmup `2023-12-01`), `07_DATA/XAUUSD_M1.parquet`. No TP rule,
constant, threshold or tier change (`LOGIC_CHANGED=NO`); no forced structural TP.
Multi-TF tier policy unchanged.

## Counts
- `N_EVENTS` (menu submits): **5**
- `TP_STRUCTURAL_PRESENT_COUNT`: **0**
- `TP_ATR_FALLBACK_COUNT`: **5**
- `tp_source` distribution: `{'atr_fallback': 5}`

## Per-submit attribution
| # | poi_id | det→conf | trigger | tp_source | tp_price | structural_target |
|---:|---|---|---|---|---|---|
| 0 | 4bcbaef0-ec26-41a8-9066-fbca076e8a34 | H4→M5 | F_BOS_OB | `atr_fallback` | 2248.7930184086417 | absent |
| 1 | e172c22e-7914-40fb-bb24-062e316c1785 | H4→M15 | F_BOS_OB | `atr_fallback` | 2353.726516643724 | absent |
| 2 | 7de39ddd-187f-492e-b836-3a3a21b23383 | H4→M15 | F_BOS_OB | `atr_fallback` | 2396.2467281736235 | absent |
| 3 | 257bd700-6d68-42fe-8780-6171fdf4c555 | M15→M1 | F_BOS_OB | `atr_fallback` | 2365.302912382871 | absent |
| 4 | b09446c2-0b49-4258-8903-3197da9c521b | H4→M5 | F_BOS_OB | `atr_fallback` | 2331.0995271961874 | absent |

## Feed gap (one sentence)
Menu path never feeds a structural target: ProductMenuEngine._candidate builds the plan with candidate_from_route(route, ..., atr=atr) and no structural_target, so resolve_take_profit always takes the 4xATR fallback; only the adapter-only path (PipelineAdapter.generate_candidates, pipeline_adapter.py:283) computes structural_tp_target(...) from the route's swing index.

## Static evidence (plan-forming call sites)
- `ProductMenuEngine._candidate` → `candidate_from_route(route, pillar_path=..., atr=atr)`:
  `structural_target` passed = **False**
- `PipelineAdapter.generate_candidates` computes `structural_tp_target(...)`:
  **True** (adapter-only feed)
- `TriggerSignal` carries a structural target field: **False**
  (fields: trigger, direction, entry_price, stop_reference, completion_index, expiry_bars, detail, data)
- `CandidateEntry` carries `structural_target`: **False**
  (provenance is `tp_source`: True)

## Reading
The menu plan's TP provenance is therefore structurally explainable: absent input → `atr_fallback`
by construction, not a rejected structural candidate. Whether the menu path *should* feed
`structural_tp_target(...)` (same selector + lookahead ban as the adapter) is an Architect design
decision, **not** made here and **not** implied by these counts. Small n (5), single window.

## Artifacts
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\plan_complement_ledger\plan_complement_ledger.csv` (input, gitignored results)
- `D:\Gold Scripts\MQL5\SMC\06_RESEARCH\results\plan_complement_ledger\tp_menu_path_attribution.json`
