# Plan-Complement Chart Pack — 5 menu-path plan submits (visual sample only)

**Diagnostic only — does NOT validate profitability, edge, or that the flowchart is correct.**
Rendered read-only from `06_RESEARCH/results/plan_complement_ledger/plan_complement_ledger.csv`
(menu `queue_menu_candidate` submits only, window `2024-04-01..2024-05-01`, warmup `2023-12-01`,
`07_DATA/XAUUSD_M1.parquet`). `LOGIC_CHANGED=NO` for this pack. OPT-B false, OPT-2 off,
no pillar/R7/threshold/TP-rule edits; multi-TF tier policy unchanged.

## What each chart shows
- **Top panel** — detection-TF context (sweep ±35 bars): HTF zone band [low, high], sweep vline
  (orange dashed), confirm vline (blue dotted), plan entry/SL/TP lines.
- **Bottom panel** — confirmation-TF context (confirm ±60 bars): same overlays.
- **Caption** — poi_id, tier, det→conf, trigger, confirm label, `tp_source`, `entry_anchor`,
  `plan_complete` / `plan_consistent`, place_or_queue.
- Timestamps in captions are UTC; charts use the ledger's own recorded sweep/confirm stamps
  (nothing re-derived). Visual language follows `generate_d1_poi_pack` /
  `ltf_confirmation_pack` (candle colors, zone band, footer disclaimer).

## Charts (all 5 of 5)
| # | file | tier | det→conf | trigger | confirm label | tp_source | entry_anchor | complete/consistent |
|---:|---|---|---|---|---|---|---|---|
| 0 | `plan_00_H4_M5_4bcbaef0.png` | H4 | H4→M5 | F_BOS_OB | ON_WINDOW | `atr_fallback` | `ob_proximal` | YES/YES |
| 1 | `plan_01_H4_M15_e172c22e.png` | H4 | H4→M15 | F_BOS_OB | ON_WINDOW | `atr_fallback` | `zone_edge_reanchor` | YES/YES |
| 2 | `plan_02_H4_M15_7de39ddd.png` | H4 | H4→M15 | F_BOS_OB | LATE | `atr_fallback` | `zone_edge_reanchor` | YES/YES |
| 3 | `plan_03_M15_M1_257bd700.png` | M15 | M15→M1 | F_BOS_OB | BEYOND_STOP_SIDE | `atr_fallback` | `zone_edge_reanchor` | YES/YES |
| 4 | `plan_04_H4_M5_b09446c2.png` | H4 | H4→M5 | F_BOS_OB | LATE | `atr_fallback` | `zone_edge_reanchor` | YES/YES |

Paths: `06_RESEARCH/results/plan_complement_charts/<file>` (gitignored results dir).
Generator: `06_RESEARCH/scripts/plan_complement_charts.py`.

## How to review (human)
For each chart ask only: *would this plan (entry / SL / TP geometry vs the zone, sweep and
confirm bars) match the flowchart's sweep → confirm → plan intent?* Answer CORRECT / PARTIAL /
WRONG in the chart score; geometry PASS from the ledger is **not** flowchart validation.

## Caveats
- Same 5-row sample as the plan-complement ledger; single one-month window; no expectancy, no
  PnL, no edge measurement here.

## Residual (Task C — `t_arm` stamp) — SKIPPED, not trivial
`t_arm` stays unstamped on the `product_menu` stamp. `ProductMenuEngine.register_armed(poi,
 detection_tf)` takes no clock/`as_of`, `MenuEpisode` records only the sweep time, and `POI.created_at`
 is a wall-clock construction default (meaningless in a replay). Doing this properly needs a
 signature change plus threading `as_of` through 9 call sites (2 in `smc/live/loop.py`, 6 tests,
 1 research script) — not a logging-only one-liner. Parked as residual; no behaviour change made.
