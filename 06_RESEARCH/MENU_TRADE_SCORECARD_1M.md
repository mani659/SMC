# Menu Trade Scorecard + Entry-SL Diagnostic — 1m (2024-04-01 → 2024-05-01)

`LOGIC_CHANGED: NO`. Measurement-only review of the 9 closed fills from `menu_trade_funnel_1m` (zero spread/cost, `LOT_MAX_SAFETY` capped all 9, backtest F7 retry not exercised). **Stage metric = trades exist / explained; not PnL.**

Rubric: flowchart story (HTF/M15 zone + sweep + LTF confirm + sensible plan), **not** PnL.

Source: `06_RESEARCH/results/menu_trade_funnel_1m/trades.csv`, chart pack `06_RESEARCH/results/menu_trade_charts_1m/`, note `06_RESEARCH/MENU_TRADE_CHARTS_1M_NOTE.md`.

## Human scorecard (9 closed trades)

| Ticket | Path | Trigger | Exit | Score | Why |
|--------|------|---------|------|--------|-----|
| **1** | M15→M1 SHORT | F | SL | **PARTIAL** | Machinery works; entry/SL almost on top of each other (~0.7 pt) → noise stop, not a real short thesis. TP close; never a clean SMC short. |
| **2** | M15→M1 LONG | F | SL | **WRONG** | Long into a **breakdown** (large red displacement). Confirm/entry after structural failure — failed demand, not reclaim. |
| **3** | H4→M5 SHORT | **A CHOCH** | SL | **PARTIAL** | Only non-F trade; H4 context after a major high is plausible for short. Entry mid-chop after dump; tight SL → quick stop. Idea direction OK, execution weak. |
| **4** | H4→M5 SHORT | **A CHOCH** | SL | **PARTIAL** | Same family as #3 (same geometry/levels). Same read: OK HTF bias, poor LTF plan quality. Treat as **one setup class**, not two independent wins for diversity. |
| **5** | M15→M1 LONG | F | **TP** | **PARTIAL** | Only TP. Long after selloff into a base; M1 climbs to ATR TP. Workable scalp story, still F + ATR, not strong HTF demand reclaim. |
| **6** | H4→M5 LONG | F | SL | **WRONG** | Long near **end of selloff / lower highs** on H4; M5 rolls over through entry to SL. Knife-catch continuation long. |
| **7** | M15→M1 LONG | F | SL (BE scratch) | **PARTIAL** | Dip-buy after flush; small BE-style win. Process OK, edge of “catch knife then scratch.” |
| **8** | M15→M1 SHORT | F | SL | **WRONG** | Short while M1 is **grinding up**; SL tagged quickly. Against immediate momentum. |
| **9** | M15→M1 LONG | F | SL | **WRONG** | Long after sharp dump; entry above bounce, SL hit in chop. No clean hold of demand. |

## Tally

| Label | Count |
|--------|--------|
| **CORRECT** | **0** |
| **PARTIAL** | **5** (1, 3, 4, 5, 7) — 3 & 4 same class |
| **WRONG** | **4** (2, 6, 8, 9) |

**Stage success (trades exist) stands. Flowchart quality: not validated** — 0 CORRECT, majority weak or failed thesis.

## Patterns (actionable, not retune)

1. **Trigger mix:** 7× F, 2× A (really **one** CHOCH short story). Still F-dominated.
2. **Stops:** 8/9 SL; many **entry≈SL** (esp. #1) → stops inside noise.
3. **TP:** ATR-only; the one TP (#5) is a small mean-reversion scalp.
4. **Fails:** longs into breakdowns (#2, #6, #9) and short into strength (#8).
5. **Tier:** M15→M1 produces more tickets; H4→M5 fewer, not clearly better by eye.

## Entry–SL / planned R:R diagnostic (per trade, from `trades.csv`)

Definitions (no threshold changes): `risk_pts = |entry_price - sl_at_entry|` (original SL), `reward_pts = |tp_price - entry_price|`, `planned_R = reward_pts / risk_pts` when `risk_pts > 0`. `sl_at_entry` is treated as original SL for all rows; ticket 7 is a BE scratch by exit (stop moved) but `risk_pts`/planned R use the original SL distance.

| Ticket | POI | Dir | Exit | Entry | Original SL | TP | risk_pts | reward_pts | planned_R | risk < 1.0 | risk < 0.05% price |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|:---:|:---:|
| 1 | poi-000178 | SHORT | stop_loss | 2262.635 | 2263.343412 | 2259.584179 | 0.708412 | 3.050821 | 4.3066 | YES | YES |
| 2 | poi-000963 | LONG | stop_loss | 2343.785 | 2340.550441 | 2356.779120 | 3.234559 | 12.994120 | 4.0173 | NO | NO |
| 3 | poi-001648 | SHORT | stop_loss | 2384.664 | 2385.879739 | 2373.134147 | 1.215739 | 11.529853 | 9.4838 | NO | NO |
| 4 | poi-001433 | SHORT | stop_loss | 2384.664 | 2385.879739 | 2373.134147 | 1.215739 | 11.529853 | 9.4838 | NO | NO |
| 5 | poi-001802 | LONG | take_profit | 2357.015 | 2356.192240 | 2361.654419 | 0.822760 | 4.639419 | 5.6388 | YES | YES |
| 6 | poi-001876 | LONG | stop_loss | 2361.075 | 2358.849094 | 2368.887086 | 2.225906 | 7.812086 | 3.5096 | NO | NO |
| 7 | poi-000707 | LONG | stop_loss (BE) | 2302.905 | 2300.558478 | 2309.717181 | 2.346522 | 6.812181 | 2.9031 | NO | NO |
| 8 | poi-002256 | SHORT | stop_loss | 2335.315 | 2335.743967 | 2333.404184 | 0.428967 | 1.910816 | 4.4545 | YES | YES |
| 9 | poi-002445 | LONG | stop_loss | 2338.038 | 2327.827277 | 2343.329233 | 10.210723 | 5.291233 | 0.5182 | NO | NO |

## Summary

- **N:** 9 trades (8 stop_loss, 1 take_profit; 1 BE-scratch derived by exit)
- **Median risk_pts:** **1.215739** (mean 2.489925, min 0.428967, max 10.210723)
- **Tight stops:** **3/9** with `risk_pts < 1.0` (tickets 1,5,8) — the same 3 are `< 0.05%` of entry price
- **Planned R distribution (all 9):** values [4.3066, 4.0173, 9.4838, 9.4838, 5.6388, 3.5096, 2.9031, 4.4545, 0.5182]; **median 4.3066**, min 0.5182 (ticket 9), max 9.4838 (tickets 3,4). Plans skew to high nominal R, but realized outcomes were 8 SL / 1 TP — consistent with tight/noise-vulnerable or structurally wrong stops rather than plan math.
- `stop_atr`: **not available** in `trades.csv` (no ATR column recorded); not computed.

**Read:** trade counting succeeded but geometry/plan quality did not — several stops are sub-point or otherwise non-viable vs noise, and the only low-R plan (ticket 9) also failed; no threshold/OPT retune applied.

## Changelog / Handoff

Human quality review (2026-11-10) scored the 9 closed 1m menu trades as **0 CORRECT / 5 PARTIAL / 4 WRONG** (tickets 3&4 same class), confirming stage success (fills/closes exist and explained) but **not validating flowchart idea quality** (F-dominated, 8/9 SL, longs into breakdowns/short into strength, ATR-only TP). This note adds a measurement-only entry–SL/planned-R diagnostic from `trades.csv` (median risk 1.215739 pts, 3/9 < 1.0 pt and < 0.05% price, planned-R median 4.3066 but realized 8 SL/1 TP) to quantify tight/noise-stop geometry; no production logic, thresholds, or tiers changed (`LOGIC_CHANGED: NO`). Next is architect choice: keep scorecard as docs baseline, optionally extend funnel-counts to 3m for volume only, or pursue a targeted stop-distance/geometry diagnostic — no edge/PnL chase or retune.
