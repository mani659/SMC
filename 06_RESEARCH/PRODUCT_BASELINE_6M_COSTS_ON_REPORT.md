# PRODUCT BASELINE 6M — COSTS-ON REPORT (DIAGNOSTIC)

> **DIAGNOSTIC ONLY — NOT EDGE.**
> Three trades closed on this window. No win rate, profit factor, net,
> drawdown, or per-trigger number below supports or refutes any claim
> about the strategy — in either direction. A losing n = 3 book is as
> uninterpretable as a winning one. This report proves the costs-on
> seams hold over a longer window and records the book honestly.

**Date:** 2026-10-11 · **Authority:** Lead Architect window-extension directive (post pilot acceptance).
**BASELINE_6M_STATUS: PASS** (determinism pair byte-identical; seams proven; metrics reported, not read).
**Scope:** measurement only. No parameter search, no WF/MC, no threshold/strategy/locked-constant change.

---

## 1. Window and config (identical to pilot except the window)

| Item | Value |
|---|---|
| M1 load warm-up from | 2025-05-01 00:00 UTC (one month, same pattern as the pilot) |
| Exec window | **2025-06-01 00:00 → 2025-11-30 23:55 UTC** (35,725 M5 bars) |
| Data | `07_DATA/XAUUSD_M1.parquet` (canonical; fail-loud if missing — present) |
| Stack | frozen `phase3_structure_funnel.run`, imported not forked: H4+H1 required detect (0 batch errors) + D1→M8 (W1 not in this composition), M5 exec, structural TP feed (`tp_source` audit-only), current §5a seek |
| Account / sessions / EOD / news / Trigger D | identical to pilot (10,000.0 / 1% / pip 10.0 / 0.01–0.10 lots; ASIA+LONDON+NEW_YORK; Friday EOD; `news_events=[]`; D unfireable by ruling) |
| `dry_run` | N/A (backtest) |

**Costs ON explicit** (ruled values, verbatim in `summary.json`): commission **0.0** (no schedule, never invented) / slippage **1.0 pt** (all exits except take-profit) / half-spread **on** / fallback **0.26** (runner spread unknown on every leg — all spread legs priced at fallback) / swap deferred (0.0, `bars_held` logged).
Script: same `06_RESEARCH/scripts/product_baseline_pilot.py` with window args
(`--load-from 2025-05-01 --exec-from 2025-06-01 --exec-to 2025-11-30 --tag product_baseline_6m`).

## 2. Determinism — PASS

| Artifact | run1 SHA-256 (prefix) | run2 | Byte-identical |
|---|---|---|---|
| `trades.csv` | `8c0c5d11…` | same | **yes** |
| `report.json` | `9ce2855a…` | same | **yes** |

Full hashes in `summary.json`. Semantic funnel equality (excluding runtime/tag): **equal**. No tolerance needed — cost floats are deterministic. Runtimes: 881.8 s / 896.0 s (~40 M5 bars/s sustained on the long window, vs ~100 on the 3-month pilot — the per-batch detection cost dominates as the prefix history deepens; recorded for full-5y planning, not optimized).

## 3. Funnel (run1; run2 identical)

| Stage | Count |
|---|---|
| M5 bars processed | 35,725 |
| HTF batches (new-H1 cadence) | 2,979 (0 errors) |
| merged POIs | 43,004 |
| passed validation | 2,021 (P2:fail 37,745 · P3:fail 2,031 · P1:fail 1,207) |
| **armed** | **30** (H4 19 / H1 6 / D1 5; **M8 28**) |
| duplicates suppressed | 1,991 (skipped_tracked 0) |
| scanned POIs | 501 |
| **routes** | **10** (F 9, C 1; M8 10) |
| placed (limits) | 4 |
| R9 intents armed / placed / expired | 7 / 3 / 0 |
| **fills → trades closed** | **3 → 3** |
| blocked by reason | session 4, `skip_place_far_from_zone` 14 (all other gates 0) |

M8 reading (stated plainly, not proven): M8 arms (28/30) and routes (10/10) — the provisioned path is live in the funnel — but M8-as-a-working-trade-engine is **not** established here: fills remain almost none and no per-M8 fill attribution is claimed.

## 4. Trade metrics + cost totals (n = 3 — reported, not read)

| Metric | Gross (ledger) | Costs / net |
|---|---|---|
| Trades closed | 3 | — |
| Wins | 2 (WR 0.667 — **n = 3, meaningless**) | — |
| Profit factor | 0.157 gross (**n = 3, meaningless**) | — |
| Net PnL (ledger) | −2.4537 | — |
| Max drawdown (ledger) | 2.9105 (= the single full loss) | — |
| Avg win / avg loss | +0.2284 / −2.9105 | — |
| Commission paid | — | **$0.00** (no schedule) |
| Spread paid | — | **$0.78** (fallback legs) |
| Slippage paid | — | **$2.00** (two SL exits) |
| Swap paid | — | $0.00 (deferred) |
| **Total cost** | — | **$2.78** |
| **Net PnL after cost (ledger)** | — | **−2.7317** |

Trade anatomy (all rows, no narrative): t1 — F, `atr_fallback`, stop-loss exit 2025-06-30, gross −2.9105, cost $1.26, net −3.0365, held 117 bars; t2 — C, `structural_swing`, take-profit exit 2025-09-02, gross +0.3852, cost $0.26, net +0.3592, held 1 bar; t3 — F, `atr_fallback`, stop-loss exit 2025-10-20, gross +0.0715 (BE-moved stop), cost $1.26, net −0.0545, held 52 bars.

### Per-trigger and tp_source mix

| Slice | n | Gross net (ledger) | After-cost net (ledger) | Cost USD |
|---|---|---|---|---|
| Trigger F | 2 | −2.8389 | −3.0909 | 2.52 |
| Trigger C | 1 | +0.3852 | +0.3592 | 0.26 |
| `tp_source = atr_fallback` | 2 | −2.8389 | −3.0909 | (same rows as F) |
| `tp_source = structural_swing` | 1 | +0.3852 | +0.3592 | (same row as C) |

## 5. Cross-window consistency observation (not a proof)

The 6m run re-found the pilot's exact 2 Sep–Nov trades (identical entry/exit timestamps and economics: C 2025-09-02 13:45→13:50 +0.3852; F 2025-10-20 05:50→10:10 +0.0715) **despite the different load window** (05-01 vs 08-01, hence different batch-prefix histories) — plus one new June F loss. Sub-slice equality was never required (the Phase 4 caveat stands: different warm-up histories need not agree), so this is recorded as observed stability of those two fills, not as a determinism claim beyond the run1/run2 pair.

## 6. Explicit non-reads (bans compliance)

- No parameter was searched, tuned, or compared; cost values are the ruled pilot values.
- The losing book (PF 0.157 gross, net −2.7317 after cost, n = 3) is evidence of nothing — it neither refutes the concept (no confidence interval exists) nor authorizes any change (a losing baseline authorizes evidence review, nothing else).
- No WF/MC/bootstrap/CI was run or implied; the diagnostic stamp applies in full.
- No strategy, threshold, gate, sizing, fill-price, or locked-constant change was made for or by this run.

## 7. Limitations and next

- n = 3 fills over 6 months: the funnel is highly selective (30 armed → 10 routes → 4 placed → 3 fills); cost attribution at scale awaits a longer window, and M8's trade-engine question is still open for lack of fills.
- Commission $0.00 by ruling; a real schedule will move every net number when pinned.
- All spread legs priced at the 0.26 fallback; tick-reconstructed spreads remain a follow-on source decision.
- Throughput note for 5y planning: ~40 bars/s sustained here vs ~100 on the 3-month pilot — project from the long-window rate, not the short one.
- Artifacts (local-only, gitignored): `06_RESEARCH/results/product_baseline_6m/` — `run1/`, `run2/` (funnel_summary, trades.csv, report.json, sample_audit, funnel_by_day, armed_records) + root `summary.json` (banner, full config, SHAs, funnel, metrics, costs, mixes).
- **Next:** Architect review — authorize the full 5y product baseline, or open spread-grade / F-selectivity research. Still no threshold fishing.

---

```
BASELINE_6M_STATUS: PASS
WINDOW: 2025-06-01 -> 2025-11-30 (35,725 M5 bars; M1 warm-up from 2025-05-01)
TRADES: 3 (F:2 — one full SL loss, one BE-stop scratch; C:1 TP win)
TOTAL_COST_USD: 2.78 (commission 0.00 + spread 0.78 + slippage 2.00 + swap 0.00)
NET_PNL_AFTER_COST: -2.7317 ledger (gross -2.4537)
DETERMINISM: PASS (byte-identical trades.csv + report.json, semantic funnel equal)
SUITE: 938 (unchanged — measurement only; window args added to the pilot script)
LOCKED_CONSTANTS_DIFF: empty
```
