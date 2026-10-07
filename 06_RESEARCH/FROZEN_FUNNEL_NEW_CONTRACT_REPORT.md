# FROZEN-WINDOW FUNNEL MEASUREMENT — NEW SEEK/SCAN CONTRACT (Option B)

**Status:** PASS — dual-run deterministic (trades.csv + report.json byte-identical, SHA-256 match; semantic funnel equal) · suite **805 passed** (unchanged) · `locked_constants.py` diff **empty** · **no production logic changed** (composition imported, not forked).
**Date:** 2026-10-05 · **Directive:** Lead Architect frozen-window funnel measurement under the accepted seek/scan redesign (Option B).
**Diagnostic banner:** this is **identification/measurement only — NOT performance**. All PnL is diagnostic with n=2 trades; no expectancy, edge, win-rate or quality claim is made or implied anywhere in this report.

---

## 1. Window (frozen — not widened, not cherry-picked)

| Bound | Value |
|---|---|
| M1 load (warm-up) | 2025-08-01 |
| Execution window | 2025-09-01 → 2025-11-30 (3 months M5) |
| Exec bars | 17,840 M5 |
| Data source | canonical `07_DATA/XAUUSD_M1.parquet` (fail-loud on absence) |

Identical to the accepted Phase 4 window — the comparison anchor is exact, not a window family.

## 2. Machine (the current product path — nothing patched)

`MultiTFProductRuntime.run_batch` (C1 product seam: H4+H1 detection, D1→M8, new-H1-close cadence) → `PipelineEngine.arm_at` (**new**: posture classification `arm_at(..., arm_candle=)`) → `PipelineAdapter.generate_candidates` (**post-redesign**: `_may_route` with seek-to-give-up, REVALIDATION gate via `market_reentered_zone`) → `BacktestRunner` (RiskEngine gates → pending limits → R9 IntentBook → manage). Composition imported from the frozen `phase3_structure_funnel.run` — the redesign is measured by *running it*, not by patching. Harness instrumentation (FR-4 wrap pattern, restored in `finally`): posture log on `arm_at`, route/trigger counters on `scan_route` + `candidate_from_route`, pillar first-failure histogram on `validate_multi`.

Config frozen (identical to Phase 4): equity 10,000 · risk_fraction 0.01 · spread 0.0 · news dormant · sessions ASIA/LONDON/NY · `diag_flags: none` (zone gate / R7 / R9 all live).

## 3. Funnel (run1; run2 semantically identical)

| Stage | Count | Notes |
|---|---:|---|
| HTF batches | 1,488 | 0 batch errors |
| Detected raw | 22,472 H4 + 22,650 H1 | |
| Merged | 20,898 | |
| Pillar outcomes | 839 PASS · 18,308 P2:fail · 1,029 P3:fail · 722 P1:fail | histogram as frozen |
| **Armed** | **18** (15 M8) | Phase 4 baseline: 17 (14 M8) |
| Scans | 256 | |
| **Routes** | **9** — F 8 · C 1 | **Phase 4 baseline: 8 (all F)** — the change: +1 Trigger C route (never before routed in any product window) |
| Placed | 2 (both with TP) | + 6 R9 intents armed, 1 intent placed, 0 expired |
| **Fills** | **2** | **Phase 4 baseline: 1** |
| **Trades closed** | **2** | |

**Seek posture mix on the 18 armed POIs:** `CLEAN_ARM` 18 · `IN_ZONE_AT_ARM` 0 · `VIOLATION_AT_ARM` 0.

**Route trigger mix:** F 8, C 1. **The C route is the redesign's direct fingerprint**: Trigger C's frozen §24 window (`sweep candle + 3 bars`) is far tighter than the old touch+1 seek ever allowed; under the new contract the scan stays open to the give-up deadline and the first C completion in product history routed. n=1 — reported, not celebrated.

## 4. Trade outcomes (n=2 — diagnostic, NOT performance)

| Trigger | POI | Entry anchor | TP | Exit | PnL (diagnostic) |
|---|---|---|---|---|---|
| C | poi-001022 (H4, M8) | absent | 3477.754 | stop_loss | **−0.3728** |
| F | poi-024420 (D1, M8) | `zone_edge_reanchor` | 4275.664 | stop_loss | **+0.0715** (BE scratch) |

- **Exit mix:** stop_loss 2 (of which **BE-scratch subset 1** — the break-even latch signature, |pnl| < 0.15). No TP exit, no Friday close.
- **TP non-null rate on placed orders: 100%** (2/2) — the FR-2 TP path is live on every placement.
- **Entry-anchor distribution (fills):** `zone_edge_reanchor` 1 (FR-3.1 on-zone re-anchor), `absent` 1 (honest absence — anchor not set on that signal, never invented).
- **Net P/L diagnostic: −0.3013** (n=2 — NOT performance; the C trade's full-SL loss is larger than the F BE-scratch win; with n=2 these numbers have no statistical meaning whatsoever).

## 5. Determinism

| Artifact | Byte-identical | SHA-256 (run1 = run2) |
|---|---|---|
| `trades.csv` | **YES** | `f497649dcc90…dbfe31` |
| `report.json` | **YES** | `2d9c8471c079…93fa3` |

Semantic funnel equal (only `runtime_seconds`/`tag` differ). **VERDICT: PASS.**

## 6. Comparison anchors (diagnostic)

| Anchor | Armed | Routes | Fills | Trades |
|---|---:|---:|---:|---:|
| **Phase 4 pre-redesign (same window)** | 17 | 8 (all F) | 1 | 1 (BE scratch) |
| **This run (new contract)** | **18** | **9 (F8 + C1)** | **2** | **2** |
| Stage 3 lifecycle pack (6-month replay window, pre-pillar) | — | 196 replay routes, OPEN_SCAN 78.33% | — | — |

Reading: on the identical frozen window the redesign added +1 armed (arming rule untouched — the delta is the deterministic-POI-id boundary of the run, not a strategy change), +1 route (a Trigger C — new trigger family reaching the router), +1 fill, +1 trade. The big 196-route number lives in the *pre-pillar replay* on the 6-month pack window — the full product path (pillars, risk, R7/R8/R9) filters exactly as designed: 9 routes, 2 placed, 2 fills.

## 7. Residual notes (honest)

1. **The armed count moved 17 → 18** despite an untouched arming rule. Explanation: POI ids are deterministic per run (`install_deterministic_poi_ids`), and the composition's dedup/batch boundary is deterministic — the +1 is a real armed POI in this composition run, not noise; it is disclosed, not explained away. Zero arm-bar mismatches were the M4 invariant on the replay; this run measures the full product path where batch composition differs from the replay by design.
2. **All 18 armed POIs are `CLEAN_ARM`.** The failure modes the redesign targets (in-zone-at-arm 199, violation-at-arm 62) were measured on the June–November pack window's H4/D1 raw structures; the Phase 4 product path's pillar-filtered armed population happens to arm clean on this window. The posture machinery is live and instrumented (harness logs it) but this window exercises only the CLEAN_ARM branch end-to-end. The 78.33% visibility result remains the pack-window replay evidence.
3. **6 R9 intents armed, 1 placed, 0 expired** — the intent path is live; the other 5 intents died with their POIs (dead-thesis drops), consistent with R9 semantics.
4. **Entry-anchor `absent` on the C fill** — Trigger C signals carry no `entry_anchor` (FR-3.1 re-anchoring is a Trigger-F path). Honest absence; not a gap.
5. **n=2.** Nothing here authorizes any tuning, filter, or paper-trading step. The next legitimate step remains the Architect's.

## 8. Explicit non-claims

- No expectancy, PnL, win-rate, edge, or quality claim. Net −0.3013 over 2 trades is a diagnostic artifact of the frozen config, not a result.
- No threshold, window, or filter was changed; `locked_constants.py` diff empty; no strategy code touched.
- The redesign's visibility effect at product level on THIS window is +1 route family (C) and +1 fill; the larger visibility effect (78.33%) was measured on the pack-window replay (see the implementation note M1–M5).

---

**Artifacts:** `06_RESEARCH/results/frozen_funnel_new_contract/` (`summary.json`, `run1/` + `run2/` each with `funnel_summary.json`, `funnel_by_day.csv`, `sample_audit.csv`, `armed_records.json`, `posture_log.json`, `trades.csv`, `report.json`); harness `06_RESEARCH/scripts/frozen_funnel_new_contract.py`; log `frozen_funnel_new_contract.log`.

**RETURN BLOCK**

```
FUNNEL_STATUS: PASS
WINDOW: exec 2025-09-01 → 2025-11-30 (M1 load 2025-08-01; frozen, identical to Phase 4)
ARMED: 18 (15 M8)
ROUTES: 9 (F 8, C 1)
FILLS: 2
TRADES: 2
EXIT_MIX: {stop_loss: 2, be_scratch_subset: 1}
POSTURE_MIX: {CLEAN: 18, IN_ZONE: 0, VIOLATION: 0}
TP_NON_NULL_RATE: 100% (2/2 placed)
DETERMINISM: PASS (trades.csv + report.json byte-identical)
NET_PL_DIAGNOSTIC: -0.3013 (n=2 — NOT performance)
SUITE: 805 passed
LOCKED_CONSTANTS_DIFF: empty
REPORT_PATH: 06_RESEARCH/FROZEN_FUNNEL_NEW_CONTRACT_REPORT.md
HANDOFF_UPDATED: YES
NEXT_READY: Architect review of funnel results
```
