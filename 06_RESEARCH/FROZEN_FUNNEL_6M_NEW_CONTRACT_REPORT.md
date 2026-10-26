# FROZEN-WINDOW FUNNEL MEASUREMENT (6 MONTHS) — NEW SEEK/SCAN CONTRACT (Option B)

> **DIAGNOSTIC ONLY — NOT PERFORMANCE.** This is a wider frozen-window
> measurement under the accepted seek/scan redesign (§5a). No expectancy,
> edge, win-rate, or quality claim is made or implied anywhere in this
> report. All PnL is diagnostic with n=3 trades.

**Status:** PASS — dual-run deterministic (`trades.csv` + `report.json`
byte-identical, SHA-256 match; semantic funnel equal) · no production
logic changed (composition imported, not forked) · window frozen, not
widened or cherry-picked.
**Date:** 2026-10-05 · **Directive:** Lead Architect wider diagnostic
window (6 months) before paper/ops consideration — still frozen, still
measurement only.

## 1. Window (frozen — do-not-widen honored)

| Bound | Value |
|---|---|
| M1 load (warm-up) | 2025-05-01 |
| Execution window | 2025-06-01 → 2025-11-30 (6 months M5) |
| Exec bars | 35,725 M5 (H1 3,504 · H4 947 · D1 184 loaded) |
| Data source | canonical `07_DATA/XAUUSD_M1.parquet` (fail-loud on absence — no softening) |

Aligns exactly with the D1/H4/LTF/Stage3 structure-pack window. This is a
*superset* of the 3-month frozen window (which it doubling-contains as its
Sep–Nov tail) — the 3-month funnel numbers are therefore a direct nested
anchor.

## 2. Machine (identical product path — nothing patched)

Identical to the 3-month funnel: `phase3_structure_funnel.run` imported —
`MultiTFProductRuntime.run_batch` (H4+H1 detection, D1→M8) →
`PipelineEngine.arm_at` (**§5a posture classification**) →
`PipelineAdapter.generate_candidates` (**post-redesign `_may_route`**) →
`BacktestRunner` (RiskEngine gates → pending limits → R9 IntentBook →
manage). No strategy code, threshold, or locked constant touched.
Harness instrumentation (FR-4 wrap pattern, restored in `finally`):
posture log on `arm_at`. The script is an extension of
`frozen_funnel_new_contract.py` (window constants, paths, anchors only).

Runtimes: run1 864.3 s, run2 878.7 s.

## 3. Funnel (run1; run2 semantically identical)

| Stage | Count | Notes |
|---|---:|---|
| HTF batches | 2,979 | 0 batch errors |
| Detected raw | 44,922 H4 + 51,093 H1 = 96,015 | |
| Merged | 43,004 | (1,991 duplicates suppressed) |
| Pillar outcomes | 2,021 PASS · 37,745 P2:fail · 2,031 P3:fail · 1,207 P1:fail | histogram as frozen |
| **Armed** | **30** (28 M8) | by TF: H4 19 · H1 6 · D1 5 |
| Scans | 501 | |
| **Routes** | **10** — F 9 · C 1 | |
| Placed | 4 (all 4 with TP) | + 7 R9 intents armed, 3 intents placed, 0 expired |
| **Fills** | **3** | |
| **Trades closed** | **3** (F 2 · C 1) | |

**Seek posture mix on the 30 armed POIs:** `CLEAN_ARM` 30 ·
`IN_ZONE_AT_ARM` 0 · `VIOLATION_AT_ARM` 0.

**Route trigger mix:** F 9, C 1 — F-dominant, exactly as in the 3-month
nested window (8:1 → 9:1). The single C route reproduces the 3-month
result's character (the redesign keeps the scan open to the give-up
deadline under Trigger C's tight §24 window).

## 4. Trade outcomes (n=3 — diagnostic, NOT performance)

| Trigger | POI | Entry anchor | Exit | PnL (diagnostic) |
|---|---|---|---|---|
| F | poi-014146 (M8) | `zone_edge_reanchor` | stop_loss | **−2.9105** |
| C | poi-047805 (M8) | absent | stop_loss | **−0.3728** |
| F | poi-073511 (M8) | `zone_edge_reanchor` | stop_loss | **+0.0715** (BE scratch) |

- **Exit mix:** stop_loss 3 (of which **BE-scratch subset 1** — the
  break-even latch signature, |pnl| < 0.15). No TP exit, no Friday close,
  no other exit kind.
- **TP non-null rate on placed orders: 100%** (4/4) — the TP path is live
  on every placement.
- **Entry-anchor distribution (fills):** `zone_edge_reanchor` 2 (FR-3.1
  on-zone re-anchor), `absent` 1 (the C fill — Trigger C signals carry no
  `entry_anchor`; honest absence, never invented).
- **Net P/L diagnostic: −3.2117** (n=3 — NOT performance; one full-SL
  loss dominates. These numbers have no statistical meaning at n=3.)

## 5. Determinism

| Artifact | Byte-identical | SHA-256 (run1 = run2) |
|---|---|---|
| `trades.csv` | **YES** | `38c6e52063b025a0…73c64d633` |
| `report.json` | **YES** | `b9172fc73be0ad1a…5dd7bb` |

Semantic funnel equal (only `runtime_seconds`/`tag` differ). **VERDICT: PASS.**

## 6. Comparison anchors (diagnostic only)

| Anchor | Armed | Routes | Fills | Trades |
|---|---:|---|---:|---:|
| **Phase 4 pre-redesign (3-month window)** | 17 | 8 (all F) | 1 | 1 (BE scratch) |
| **New contract, nested 3-month window** | 18 | 9 (F 8 + C 1) | 2 | 2 |
| **This run — new contract, 6-month window** | **30** | **10 (F 9 + C 1)** | **3** | **3** |
| Stage 3 lifecycle pack (same 6-month window, pre-pillar replay) | — | 196 replay routes · OPEN_SCAN 78.33% | — | — |

Reading: doubling the window roughly doubled armed (18 → 30 over the
overlapping tail — the November half contributes ~12 additional arming
events) but routes go 9 → 10 and fills 2 → 3: the product path's pillar +
risk + R7/R8/R9 gates keep the routed population small and stable.
Trigger mix stays F-dominant with exactly one C route in both windows.
The 196-route number remains purely pre-pillar replay (pack window) — the
full product path filters exactly as designed.

## 7. Residual notes (honest)

1. **All 30 armed POIs are `CLEAN_ARM` — again.** The wider window did
   NOT exercise `IN_ZONE_AT_ARM` or `VIOLATION_AT_ARM` end-to-end on the
   product path. The armed population is pillar-filtered, and the
   pillar-passing structures that survive happen to arm clean across the
   entire 6 months. The posture machinery is live and instrumented, but
   its non-CLEAN branches remain exercised only by the unit/integration
   suite (25 tests) and the pack-window replay visibility (IN_ZONE 484 /
   VIOLATION 182 pre-pillar). This is a measurement fact, not a verdict
   on the machinery.
2. **Non-F routes remain thin:** one C route in 6 months, zero A/B/D/E
   routes. n=1 per non-F trigger — no conclusion drawable.
3. **The −0.3728 C trade** carries the same PnL signature as the 3-month
   window's C fill (−0.3728, anchor absent). This window is inclusive of
   that window's Sep–Nov tail; the two measurements share the same frozen
   config, so identical magnitudes are plausible and are reported as
   observed — no coincidence claim either way.
4. **7 R9 intents armed, 3 placed, 0 expired** — the intent path is live;
   the other 4 intents died with their POIs (dead-thesis drops),
   consistent with R9 semantics.
5. **n=3, all diagnostic.** Nothing here authorizes tuning, filtering,
   window changes, or paper-trading sign-off. The next legitimate step is
   the Architect's.

## 8. Explicit non-claims

- No expectancy, PnL, win-rate, edge, or quality claim. Net −3.2117 over
  3 trades is a diagnostic artifact of the frozen config, not a result.
- No threshold, window, or filter was changed; no strategy code touched;
  `locked_constants.py` diff empty (verified).
- The redesign's product-path visibility on this window: +1 route, +1
  fill, +1 trade vs the nested 3-month total; posture mix unchanged
  (all CLEAN). The pack-window replay remains the visibility evidence
  (78.33% OPEN_SCAN share).

---

**Artifacts:** `06_RESEARCH/results/frozen_funnel_6m_new_contract/`
(`summary.json`, `run1/` + `run2/` each with `funnel_summary.json`,
`funnel_by_day.csv`, `sample_audit.csv`, `armed_records.json`,
`posture_log.json`, `trades.csv`, `report.json`); harness
`06_RESEARCH/scripts/frozen_funnel_6m_new_contract.py`; console log
`06_RESEARCH/results/_6m_run_console.log`.
