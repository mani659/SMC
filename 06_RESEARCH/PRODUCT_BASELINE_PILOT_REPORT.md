# PRODUCT BASELINE PILOT — COSTS-ON REPORT (STAGED, 3-MONTH WINDOW)

> **DIAGNOSTIC ONLY — NOT PERFORMANCE / NOT EDGE.**
> Two trades closed on this window. No win rate, profit factor, net, or
> per-trigger number below supports or refutes any claim about the
> strategy. This report proves the costs-on measurement seams and the
> determinism pair — nothing else.

**Date:** 2026-10-11 · **Authority:** Lead Architect staged-pilot directive (post cost-model PASS).
**PILOT_STATUS: PASS** (determinism pair byte-identical; seams proven; metrics reported, not read).
**Scope:** measurement only. No parameter search, no WF/MC, no threshold/strategy change; `locked_constants.py` diff empty.

---

## 1. Window and config (frozen for this pilot)

| Item | Value |
|---|---|
| M1 load warm-up from | 2025-08-01 00:00 UTC |
| Exec window | **2025-09-01 00:00 → 2025-11-30 23:55 UTC** (17,840 M5 bars; the Phase 4 window) |
| Data | `07_DATA/XAUUSD_M1.parquet` (canonical; fail-loud if missing — present) |
| Execution | M5 (`RunnerConfig.timeframe=M5`) |
| Detection | H4 + H1 required via `MultiTFProductRuntime` (loud fail, 0 batch errors); D1 forwarded to M8 when available; **W1 not in this composition** (resample set is M5/H1/H4/D1) |
| M8 | provisioned via the product runtime path |
| Structural TP | feed as wired (`structural_swing` vs `atr_fallback`, `tp_source` audit-only) |
| Seek contract | current §5a (redesign accepted 2026-10-05) |
| Account | equity 10,000.0, risk 1%, `pip_value_per_lot` 10.0, lots 0.01/0.01 step, `LOT_MAX_SAFETY` 0.10 (unchanged) |
| Sessions | ASIA + LONDON + NEW_YORK; Friday EOD active; `news_events=[]` |
| `dry_run` | N/A (backtest; `dry_run` is a live/paper concept) |
| Trigger D | compiled, structurally unfireable (A5 ruling) |

**Costs ON explicit** (Architect ruling 2026-10-11; recorded verbatim in `summary.json`):

| Parameter | Pilot value |
|---|---|
| `apply_costs` | true |
| `commission_usd_per_lot_per_side` | **0.0** (no broker schedule on file — never invented) |
| `slippage_points` | **1.0** (every exit except take-profit) |
| `apply_half_spread` | true |
| `spread_fallback_price` | **0.26** (runner `spread_price=0.0` = unknown on every leg this run, so all spread legs priced at fallback) |
| swap | deferred (0.0; `bars_held` logged per trade) |

Composition: `phase3_structure_funnel.run` imported, not forked
(`MultiTFProductRuntime.run_batch` at new-H1-close cadence → `PipelineEngine` arm →
`PipelineAdapter` scans → `BacktestRunner` risk/pending-limits/R9-intents/manage).
The only addition vs the Phase 4 wrapper is the explicit `CostConfig` above
(optional hook, measurement-only); script: `06_RESEARCH/scripts/product_baseline_pilot.py`
(+ 6-line optional cost hook in `phase3_structure_funnel.py`, default-absent = legacy path).

## 2. Determinism — PASS

| Artifact | run1 SHA-256 | run2 | Byte-identical |
|---|---|---|---|
| `trades.csv` | `6b479888…9af5e` | same | **yes** |
| `report.json` | `464a9d52…8682` | same | **yes** |

Full hashes in `summary.json`. Semantic funnel equality (excluding runtime/tag): **equal**.
Cost floats are deterministic pure arithmetic — no tolerance was needed; exact byte identity holds with costs on.
Runtimes: run1 183.6 s, run2 188.9 s (≈100 M5 bars/s on this machine).

## 3. Funnel (run1; run2 identical)

| Stage | Count |
|---|---|
| M5 bars processed | 17,840 |
| HTF batches (new-H1 cadence) | 1,488 (0 errors) |
| detected raw H4 / H1 | 22,472 / 22,650 |
| merged H4 / H1 | 10,579 / 10,319 (20,898 total) |
| passed validation | 839 (P2:fail 18,308 · P3:fail 1,029 · P1:fail 722 dominate) |
| **armed** | **18** (H4 6 / H1 8 / D1 4; **M8 15**) |
| duplicates suppressed | 821 |
| scanned POIs | 256 |
| **routes** | **9** (F 8, C 1; M8 8) |
| placed (limits) | 2 (both with TP) |
| R9 intents armed / placed / expired | 6 / 1 / 0 |
| **fills → trades closed** | **2 → 2** |
| blocked by reason | session 4, `skip_place_far_from_zone` 12 (all other gates 0) |

## 4. Trade metrics + cost totals (n = 2 — reported, not read)

| Metric | Gross (ledger) | Costs / net |
|---|---|---|
| Trades closed | 2 | — |
| Wins | 2 (WR 1.0 — **n = 2, meaningless**) | — |
| Profit factor | **null** (zero-loss case → None by design, never inf) | — |
| Net PnL (ledger) | +0.4567 | — |
| Max drawdown (ledger) | 0.0 | — |
| Avg win / avg loss | +0.2284 / null | — |
| Commission paid | — | **$0.00** (no schedule) |
| Spread paid | — | **$0.52** (fallback legs) |
| Slippage paid | — | **$1.00** (one SL exit) |
| Swap paid | — | $0.00 (deferred) |
| **Total cost** | — | **$1.52** |
| **Net PnL after cost (ledger)** | — | **+0.3047** |

Trade anatomy (both rows, no narrative): ticket 1 — trigger C, `structural_swing` TP, take-profit exit, gross +0.3852, cost $0.26, net +0.3592, held 1 bar; ticket 2 — trigger F, `atr_fallback`, stop-loss exit, gross +0.0715, cost $1.26, net −0.0545, held 52 bars.

### Per-trigger and tp_source mix

| Slice | n | Gross net (ledger) | After-cost net (ledger) | Cost USD |
|---|---|---|---|---|
| Trigger C | 1 | +0.3852 | +0.3592 | 0.26 |
| Trigger F | 1 | +0.0715 | −0.0545 | 1.26 |
| `tp_source = structural_swing` | 1 | +0.3852 | +0.3592 | (same row as C) |
| `tp_source = atr_fallback` | 1 | +0.0715 | −0.0545 | (same row as F) |

## 5. Reference vs the Phase 4 frozen run (same window — reference only, NOT equality)

Phase 4 (2026-09-23, zero-cost, pre-§5a/structural-TP): 17 armed / 8 routes (all F) / 1 placed + 6 intents / 1 fill.
Pilot (current stack, costs on): 18 armed / 9 routes (8 F + 1 C) / 2 placed + 6 intents / 2 fills.
The deltas are attributable to post-September stack changes that postdate Phase 4 — the §5a seek redesign (arming/lifecycle) and the structural TP feed (route→placement) — plus the cost ledger (which changes no behavior). Same window, different stack version: the comparison calibrates drift, it does not validate either run.

## 6. Explicit non-reads (bans compliance)

- No parameter was searched, tuned, or compared at any trade count; the cost values are the ruled pilot values, not optimized ones.
- WR 1.0 / PF null / net signs on n = 2 are reported as arithmetic facts of two rows, never as edge, performance, or trigger evidence.
- No WF/MC/bootstrap/CI was run or implied; the diagnostic stamp (§5 of the baseline plan) applies in full.
- No strategy, threshold, gate, sizing, fill-price, or locked-constant change was made for or by this run. The only code touched before it: the cost model (accepted), plus a 6-line optional cost hook in the Phase 3 research script (absent = legacy path).

## 7. Limitations and next

- n = 2 fills: the pilot proves seams and determinism, not the book. Cost attribution at scale awaits a longer window.
- Commission is $0.00 by ruling (no schedule); a real schedule will move every net number — that is expected and desired.
- Spread legs all priced at the 0.26 fallback (runner spread unknown this run); tick-reconstructed spreads remain a follow-on source decision.
- W1 context is not in this composition; D1→M8 is.
- Artifacts (local-only, gitignored): `06_RESEARCH/results/product_baseline_pilot/` — `run1/`, `run2/` (funnel_summary, trades.csv, report.json, sample_audit, funnel_by_day, armed_records) + root `summary.json` (banner, full config, SHAs, funnel, metrics, costs, mixes).
- **Next:** Architect review of this pilot; the full 5y runs only after acceptance.

---

```
PILOT_STATUS: PASS
WINDOW: 2025-09-01 -> 2025-11-30 (17,840 M5 bars; load warm-up from 2025-08-01)
TRADES: 2 (C:1 TP exit, F:1 SL exit)
COSTS_ON: YES (commission 0.0 / slippage 1.0pt / half-spread on / fallback 0.26 / swap deferred)
TOTAL_COST_USD: 1.52 (commission 0.00 + spread 0.52 + slippage 1.00 + swap 0.00)
NET_PNL_AFTER_COST: +0.3047 ledger (gross +0.4567)
DETERMINISM: PASS (byte-identical trades.csv + report.json, semantic funnel equal)
SUITE: 938 (unchanged — no production/test code touched by the run)
LOCKED_CONSTANTS_DIFF: empty
```
