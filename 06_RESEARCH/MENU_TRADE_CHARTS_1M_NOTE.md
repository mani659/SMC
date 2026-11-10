# Menu trade chart pack — 9 closed fills (1m, 2024-04)

`LOGIC_CHANGED: NO`. Quality review after stage-success fills. **No PnL ranking, not edge.**

Source: `06_RESEARCH/results/menu_trade_funnel_1m/trades.csv` + `drops.csv` (joined by `poi_id`).
Charts (gitignored): `06_RESEARCH/results/menu_trade_charts_1m/` (9 charts).
Script: `06_RESEARCH/scripts/menu_trade_charts.py` (deterministic rerun of the same menu-path harness to recover zone/stamps).

## Index — 9 closed paths

| # | Ticket | POI | Route | Tier | Det→Conf | Dir | Trigger | TP src | Exit | BE | PnL raw | Chart | Zone (recovered) | Sweep | Confirm |
|---:|---:|---|---|---|---|---|---|---|---|---|---:|---|---|---|---|
| 1 | 1 | poi-000178 | poi-000178:F@116282 | M15 | M15→M1 | SHORT | TriggerType.F_BOS_OB | atr_fallback | stop_loss | NO | -0.070841 | `ticket_1_poi-000178.png` | n/a | 2024-04-02T09:30:00+00:00 | 2024-04-02T10:45:00+00:00 |
| 2 | 2 | poi-000963 | poi-000963:F@124693 | M15 | M15→M1 | LONG | TriggerType.F_BOS_OB | atr_fallback | stop_loss | NO | -0.323456 | `ticket_2_poi-000963.png` | n/a | 2024-04-10T12:30:00+00:00 | 2024-04-10T12:55:00+00:00 |
| 3 | 3 | poi-001648 | poi-001648:A@26796 | H4 | H4→M5 | SHORT | TriggerType.A_CHOCH | atr_fallback | stop_loss | NO | -0.121574 | `ticket_3_poi-001648.png` | n/a | 2024-04-19T00:00:00+00:00 | 2024-04-19T06:15:00+00:00 |
| 4 | 4 | poi-001433 | poi-001433:A@26796 | H4 | H4→M5 | SHORT | TriggerType.A_CHOCH | atr_fallback | stop_loss | NO | -0.121574 | `ticket_4_poi-001433.png` | n/a | 2024-04-19T00:00:00+00:00 | 2024-04-19T06:15:00+00:00 |
| 5 | 5 | poi-001802 | poi-001802:F@135400 | M15 | M15→M1 | LONG | TriggerType.F_BOS_OB | atr_fallback | take_profit | NO | 0.463942 | `ticket_5_poi-001802.png` | n/a | 2024-04-22T06:45:00+00:00 | 2024-04-22T07:25:00+00:00 |
| 6 | 6 | poi-001876 | poi-001876:F@27112 | H4 | H4→M5 | LONG | TriggerType.F_BOS_OB | atr_fallback | stop_loss | NO | -0.222591 | `ticket_6_poi-001876.png` | n/a | 2024-04-22T04:00:00+00:00 | 2024-04-22T09:35:00+00:00 |
| 7 | 7 | poi-000707 | poi-000707:F@136516 | M15 | M15→M1 | LONG | TriggerType.F_BOS_OB | atr_fallback | stop_loss | YES | 0.030914 | `ticket_7_poi-000707.png` | n/a | 2024-04-23T01:45:00+00:00 | 2024-04-23T03:00:00+00:00 |
| 8 | 8 | poi-002256 | poi-002256:F@140789 | M15 | M15→M1 | SHORT | TriggerType.F_BOS_OB | atr_fallback | stop_loss | NO | -0.042897 | `ticket_8_poi-002256.png` | n/a | 2024-04-26T04:30:00+00:00 | 2024-04-26T05:15:00+00:00 |
| 9 | 9 | poi-002445 | poi-002445:F@141970 | M15 | M15→M1 | LONG | TriggerType.F_BOS_OB | atr_fallback | stop_loss | NO | -1.021072 | `ticket_9_poi-002445.png` | n/a | 2024-04-29T01:15:00+00:00 | 2024-04-29T01:55:00+00:00 |

## 5 non-closed plans (drop reasons, table only)

| # | POI | Tier | Det→Conf | Dir | Stage | Reason | Ticket |
|---:|---|---|---|---|---|---|---|
| 3 | poi-001356 | M15 | M15/M1 | SHORT | blocked | session | — |
| 4 | poi-001360 | M15 | M15/M1 | SHORT | r7_deferred | intent_expired_no_reentry | — |
| 8 | poi-001877 | H4 | H4/M15 | LONG | r7_deferred | dropped_portfolio_friday | — |
| 12 | poi-001402 | H1 | H1/M5 | LONG | blocked | session | — |
| 14 | poi-002445 | M15 | M15/M1 | LONG | placed | withdrawn_before_fill | 10 |

## Read me

- Each chart: detection TF panel (candles, recovered zone band when available, sweep/confirm/entry/exit marks) + confirmation TF panel (candles, entry/SL(original)/TP/exit levels and marks).
- Human scoring target: **CORRECT / PARTIAL / WRONG** vs flowchart (eyes only). No automated score, no PnL ranking.
- Limitations: 1m window (2024-04), zero spread/cost, backtest F7 retry not exercised, `LOT_MAX_SAFETY` capped all 9 lots. Zone/sweep/confirm/trigger shown only where recoverable from the deterministic rerun/menu stamp; unavailable fields marked `n/a` (not guessed).

