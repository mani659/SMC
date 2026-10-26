# PRODUCT 6M REFRESH — COSTS ON + TRACK-B COLUMNS (DIAGNOSTIC)

> **DIAGNOSTIC ONLY — NOT EDGE.**
> Three trades closed on this window. No win rate, profit factor, net,
> drawdown, per-trigger, per-label, or per-outcome number below supports
> or refutes any claim about the strategy — in either direction. This
> report proves the refreshed stack (mapped spread-grade thresholds +
> Track-B columns) measures identically to its predecessor, and records
> the book honestly.

**Date:** 2026-10-11 · **Authority:** Lead Architect 6m-refresh directive (measurement only).
**REFRESH_6M_STATUS: PASS** (determinism pair byte-identical; columns populated; metrics reported, not read).
**Scope:** measurement only — no optimization, no gates, no threshold fishing, no locked-constant edit this task.

---

## 1. Window and config (identical to prior 6m except the stack moved on)

| Item | Value |
|---|---|
| M1 load warm-up from | 2025-05-01 00:00 UTC |
| Exec window | **2025-06-01 00:00 → 2025-11-30 23:55 UTC** (35,725 M5 bars) |
| Data | `07_DATA/XAUUSD_M1.parquet` (canonical; fail-loud if missing — present) |
| Stack | frozen `phase3_structure_funnel.run`, imported not forked: H4+H1 required detect (0 batch errors) + D1→M8 (W1 not in this composition), M5 exec, structural TP feed, current §5a seek |
| Account / sessions / EOD / news / Trigger D | 10,000.0 / 1% / pip 10.0 / 0.01–0.10 lots; ASIA+LONDON+NEW_YORK; Friday EOD; `news_events=[]`; D unfireable (A5) |
| Costs ON explicit (ruled) | commission **0.0** / slippage **1.0 pt** (ex-TP) / half-spread **on** / fallback **0.26** / swap deferred |
| Spread grade | **mapped thresholds** (A+≥3/A≥2/B≥1/C<1 — current constants; see §6 for the measured effect: none) |
| Track-B columns | populated via the harness (`annotate_product_trades` over the run's own series) |
| `dry_run` | N/A (backtest) |

Script: same `06_RESEARCH/scripts/product_baseline_pilot.py` with 6m args
(`--tag product_6m_refresh_track_b`, out root `results/product_6m_refresh_track_b`).

## 2. Funnel: batches → armed → routes → fills → trades (run1; run2 identical)

| Stage | Count |
|---|---|
| M5 bars processed | 35,725 |
| HTF batches (new-H1 cadence) | 2,979 (0 errors) |
| merged POIs | 43,004 |
| passed validation | 2,021 (P2:fail dominates, as before) |
| **armed** | **30** (M8 28) |
| scanned POIs | 501 |
| **routes** | **10** (F 9, C 1; M8 10) |
| placed (limits) | 4 |
| R9 intents armed / placed / expired | 7 / 3 / 0 |
| **fills → trades closed** | **3 → 3** |
| blocked by reason | session 4, `skip_place_far_from_zone` 14 |

## 3. Cost totals + gross vs net

| Metric | Gross (ledger) | Costs / net |
|---|---|---|
| Trades closed | 3 (WR 0.667, PF 0.157 — **n = 3, meaningless**) | — |
| Net PnL (ledger) | −2.4537 | — |
| Max drawdown (ledger) | 2.9105 | — |
| Commission paid | — | **$0.00** (no schedule) |
| Spread paid | — | **$0.78** (fallback legs) |
| Slippage paid | — | **$2.00** (two SL exits) |
| Swap paid | — | $0.00 (deferred) |
| **Total cost** | — | **$2.78** |
| **Net PnL after cost (ledger)** | — | **−2.7317** |

## 4. Per-trigger + tp_source mix

| Slice | n | Gross net | After-cost net | Cost USD |
|---|---|---|---|---|
| Trigger F | 2 | −2.8389 | −3.0909 | 2.52 |
| Trigger C | 1 | +0.3852 | +0.3592 | 0.26 |
| `tp_source = atr_fallback` | 2 | −2.8389 | −3.0909 | (same rows as F) |
| `tp_source = structural_swing` | 1 | +0.3852 | +0.3592 | (same row as C) |

## 5. Tables by f_timing_label and post_exit_class (n, outcomes)

By timing label (from `report.json`, costs-on):

| f_timing_label | n | Wins | Gross net | After-cost net | Cost USD |
|---|---|---|---|---|---|
| structured_pullback | 2 | 1 | −2.8389 | −3.0909 | 2.52 |
| unknown (non-F row, by design) | 1 | 1 | +0.3852 | +0.3592 | 0.26 |

By post-exit class:

| post_exit_class | n | After-cost net |
|---|---|---|
| REJECTED | 1 | −3.0365 |
| SL_THEN_TP_PATH | 1 | −0.0545 |
| TP_REACHED | 1 | +0.3592 |

Row-level (matches the Track-B study exactly): t1 F pullback/REJECTED;
t2 C unlabeled/TP_REACHED (structural_swing); t3 F pullback/SL_THEN_TP_PATH
(atr_fallback, BE-stop then TP touch). Both F rows structured_pullback
(chase 0.12 / −0.10, INSIDE zone) — listed, never pooled.

## 6. Compare to prior 6m costs-on (trade count / net) + spread-grade effect

Prior 6m (pre-map thresholds, no Track-B columns): 3 trades, gross
−2.4537, costs $2.78, net −2.7317, funnel 30 armed / 10 routes / 3 fills.
Refresh (mapped thresholds + Track-B columns): **identical on every
count** — same 3 tickets, same triggers, same pnl/costs to the last
decimal; legacy metrics keys byte-equal; funnel 30 / 10 / 3 unchanged.

**SPREAD_GRADE_EFFECT: none.** One-line reason: the composition runs
`spread_price=0.0`, which leaves the §28.5 gate off entirely, so
re-tiering its tolerance cannot change route admission — confirmed
empirically by the identical funnel and trade list. (The mapped
thresholds matter the moment a nonzero spread price is configured;
that configuration is a future ruling, not this run.) The only
artifact deltas vs the prior 6m are additive: the two Track-B columns
per trade row and the two group sections per report.

## 7. Determinism + artifacts

Pair verdict: **PASS** — `trades.csv` + `report.json` byte-identical
across run1/run2 (SHA-256 in `summary.json`), semantic funnel equal,
no tolerance needed (cost floats + annotations are deterministic pure
functions). Runtimes ≈ 880–990 s (~40 M5 bars/s sustained).
Artifacts (local-only, gitignored): `06_RESEARCH/results/product_6m_refresh_track_b/`
— `run1/`, `run2/` (funnel_summary, trades.csv, report.json,
sample_audit, funnel_by_day, armed_records) + root `summary.json`
(banner, full config incl. explicit costs, SHAs, funnel, metrics,
costs, mixes).

## 8. Explicit statements (bans compliance)

- **late_chase is NOT filtered** — here or anywhere: both F rows in
  this book are structured_pullback, and no decision logic reads
  either annotation column (structural fact, covered by suite).
- No strategy/threshold fishing; no locked-constant edit this task;
  no expectancy or "system is profitable" language anywhere above —
  the losing n = 3 book is evidence of nothing (no confidence
  interval exists) and authorizes no change.

---

```
REFRESH_6M_STATUS: PASS
WINDOW: 2025-06-01 -> 2025-11-30 (35,725 M5 bars; M1 warm-up from 2025-05-01)
TRADES: 3 (F:2, C:1 — identical tickets/economics to prior 6m)
TOTAL_COST_USD: 2.78 (commission 0.00 + spread 0.78 + slippage 2.00 + swap 0.00)
NET_PNL_AFTER_COST: -2.7317 ledger (gross -2.4537)
BY_TIMING: {structured_pullback: 2, unknown: 1}
BY_POST_EXIT: {REJECTED: 1, SL_THEN_TP_PATH: 1, TP_REACHED: 1}
DETERMINISM: PASS (byte-identical pair, semantic funnel equal)
SPREAD_GRADE_EFFECT: none (gate off at spread_price=0.0 — re-tiering cannot change admission; confirmed by identical funnel/trades)
REPORT_PATH: 06_RESEARCH/PRODUCT_6M_REFRESH_TRACK_B_REPORT.md
SUITE: 955 (unchanged — measurement only)
LOCKED_CONSTANTS_DIFF: empty
```
