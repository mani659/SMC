# POI KPI REPORT — FROZEN-WINDOW STRUCTURE SPINE

Status: **MEASUREMENT** (not performance, not go-live, no expectancy claim).
Window: **2025-06-01T00:00:00+00:00 → 2025-11-30T23:59:59+00:00** UTC (exec M5; warm-up load 2025-05-01, matching the P2a/P2b/structure-ledger convention).

## 1. Scope / pipeline

Product spine, imported (never forked):

- `smc.orchestration.multi_tf_runtime.MultiTFProductRuntime.run_batch`
- `smc.orchestration.multi_tf.MultiTFDetectionDriver.validate_multi`
- `smc.orchestration.engine.PipelineEngine`
- `smc.backtest.pipeline_adapter.PipelineAdapter`
- `smc.backtest.runner.BacktestRunner`

Composition: new-H1-close batches → H4+H1 detection (D1→M8 context) → merged POI → 5 hard pillars → arm → scan/route → risk/placement → fills.
Extra instrumentation: a wrapper around `MultiTFDetectionDriver.validate_multi` records each merged POI's identity + pillar path; restored in `finally`.

Bans honoured: no threshold edits, no detector/trigger/pillar formula edits, no EQH-in-pool, no live terminal, no expectancy/PF language.

## 2. Funnel

| stage | count |
| --- | ---: |
| detected_raw_H1 | 51088 |
| detected_raw_H4 | 44914 |
| merged_H1 | 23490 |
| merged_H4 | 20508 |
| passed_H1 | 1577 |
| passed_H4 | 568 |
| detected_raw_total | 96002 |
| merged_total | 43998 |
| passed_total | 2145 |
| armed | 632 |
| routes | 230 |
| placed | 0 |
| fills | 61 |

Armed by TF: `{"H4": 180, "H1": 316, "D1": 136}` · routes by trigger: `{"F": 209, "A": 9, "B": 10, "E": 2}`.

## 3. Pillar first-fail breakdown (measurement, not a fix list)

| pillar | label | count | pct |
| --- | --- | ---: | ---: |
| P2:fail | PILLAR 2 FAIL - DISPLACEMENT (fail) | 38612 | 87.7585% |
| PASS | PASS | 2145 | 4.8752% |
| P3:fail | PILLAR 3 FAIL - PREMIUM/DISCOUNT (fail) | 2092 | 4.7548% |
| P1:fail | PILLAR 1 FAIL - ZONE REFINEMENT (fail) | 1149 | 2.6115% |

## 4. Arm / route / fill chain

- merged POIs: 43998 · passed: 2145 · armed: 632
- routes: 230 · placed: see `funnel.csv` · fills: 61
- Per-POI chain: `armed_routes_fills.csv` (routed/trigger/entry/SL/TP/filled/close_kind).

## 5. Pool link (descriptive join only — not a gate)

Rates: `{"NO": 628, "YES": 4}` (YES / NO / UNKNOWN).
Lookback = `poi_give_up_bars()` M5 bars before the arm bar; nearest same-side active P2a level by distance to the POI zone; hit from P2b attribution. UNKNOWN means no same-side active level at the arm instant — never forced.

## 6. Chart index + stratification

48 charts under `06_RESEARCH/results/poi_kpi_pack/charts/` (index: `charts/index.csv`). Each figure has the HTF series panel plus the M5 window around the event, the POI zone rectangle and the arm marker.
Stratification: armed POIs first, then PASS-unarmed, then first-fail rows, round-robin across (pillar, kind) buckets so F-routes do not dominate.
Labels use flowchart vocabulary (ORDER BLOCK / DEMAND-SUPPLY ZONE / FVG / PILLAR n FAIL).

### Scoring rubric (human / Architect)

CORRECT | PARTIAL | WRONG | UNCLEAR — geometric zone, label kind, directional sense vs flowchart. The pack never auto-scores as expert truth.

## 7. Determinism

`{"run2_present": true, "summary_semantic_equal": true, "funnel_rows_equal": true, "poi_rows_equal": true, "excluded_fields": ["runtime_seconds", "tag"], "funnel_summary_sha_run1": "82e5f99c0e23f842510d16e27e78436f5b96036c266e8d2eb3a5a7d6d645e127", "funnel_summary_sha_run2": "ef5957ef49d14d74d12ef210573c544bbe866fac77bf98a933197c0d72f1cace"}`

Dual run of the same composition (run1/run2); only `runtime_seconds` and the run `tag` are excluded from the comparison. `funnel_rows_equal` compares the funnel rows derived from each run, `poi_rows_equal` compares every captured POI row (identity, zone, pillar path, arm/route/fill chain).

## 8. Residuals

- `entry_anchor` is not exported by this composition (honest `n/a`).
- Pool link covers armed POIs only; UNKNOWN rates are reported, not resolved.
- Charts are identification panels; no trade is implied by an armed POI.
- `06_RESEARCH/results/` is gitignored by repo policy (same as prior packs); the artifacts live locally under `06_RESEARCH/results/poi_kpi_pack/`.

## 9. Explicit

**Not performance. Not go-live. No expectancy, PF or win-rate claim.** No threshold was tuned in response to these numbers.
