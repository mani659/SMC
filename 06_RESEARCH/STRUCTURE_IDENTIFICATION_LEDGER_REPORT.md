# STRUCTURE IDENTIFICATION LEDGER — REPORT

**Status:** PASS · generated 2026-09-25 14:44 UTC · measurement + export + charts only (V1.1 baseline freeze in force).

**Purpose:** let a human and an external expert score whether the code identifies OB / FVG / S&D / LTF confirms the way the locked flowchart says, BEFORE paper trading is treated as anything beyond ops.

---

## 1. Window & composition

- Exec window: **2025-06-01T00:00:00+00:00 → 2025-11-30T23:00:00+00:00** (35725 M5 bars)
- Detection: H4 + H1 (M8 fed D1 when available) · Execution: M5
- union of tiled chunk exec windows; each chunk ran the same unified composition with its own warm-up
- HTF batches: 2979 · batch errors: 0
- Runtime: 29.2s

**Assembly:** tiled chunks — see the assembly notes at the end of §7 for why a single run is not feasible. Exec windows tile the LOCKED range exactly.

| chunk | exec window | M5 bars | HTF batches | rows added |
|---|---|---:|---:|---:|
| chunkA | 2025-06-01T22:00:00+00:00 → 2025-08-31T23:55:00+00:00 | 17885 | 1491 | 6769 |
| chunkB | 2025-09-01T00:00:00+00:00 → 2025-11-30T23:55:00+00:00 | 17840 | 1488 | 6478 |

Driver modules (unchanged — logging-only wrappers restored in `finally`):

- `smc.orchestration.multi_tf_runtime.MultiTFProductRuntime.run_batch`
- `smc.orchestration.multi_tf.MultiTFDetectionDriver.validate_multi`
- `smc.orchestration.detection_driver.DetectionDriver.stage0/detect_pois/validate_window`
- `smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply._zones`
- `smc.orchestration.engine.PipelineEngine.arm_at/scan_route`
- `smc.backtest.pipeline_adapter.PipelineAdapter`
- `smc.backtest.runner.BacktestRunner`
- `smc.backtest.reports.build_report`

## 2. Module ↔ flowchart map

| Flowchart concept | Code module(s) | event_type | Notes |
|---|---|---|---|
| Liquidity levels (Stage 0A) | `smc.detection.liquidity_scanner.scan → session/periodic/eqh/structural` | `liquidity_level` | per-TF level, price anchor = level price |
| Liquidity sweep | `smc.detection.sweep_detector.detect_sweeps` | `sweep` | wick-pierce + body-close; linked to its level via related_event_id |
| Fair value gap (LTF/HTF detect) | `smc.detection.fvg_detector.detect_fvgs` | `fvg` | 3-candle imbalance zone on the detection TF |
| Displacement (§3) | `smc.detection.displacement_checker.check_displacement` | `displacement` | BOS + FVG + ≥1×ATR; magnitude_atr recorded |
| Order block (HTF, M8 path) | `smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply._zones (kind=ob)` | `poi_raw` | candle before the FVG; labelled ob ONLY when the code yields it |
| Supply / demand (HTF, M8 path) | `…m8_htf_demand_supply._zones (kind=demand_supply)` | `poi_raw` | single last opposing candle before a ≥1×ATR impulse; HTF vs LTF in notes |
| POI models M1–M7 | `smc.orchestration.detection_driver.detect_pois` | `poi_raw` | pre-merge raw model output (one tag per POI) |
| Confluence merge (§1) | `smc.poi.confluence_scorer.merge_overlapping (via PipelineEngine.validate)` | `poi_merged` | same-direction overlapping zones → union of tags |
| Pillars 1–5 | `smc.validation.validation_pipeline.ValidationPipeline` | `pillar_pass / pillar_reject` | first hard failure recorded; PASS path summarised |
| Arm (§5 CREATED→FRESH + §24 anchor) | `smc.orchestration.engine.PipelineEngine.arm_at` | `poi_armed` | zone-episode dedup (ZoneDedup); arm_bar anchors the give-up window |
| LTF trigger routing (A–F on M5) | `smc.orchestration.engine.PipelineEngine.scan_route → smc.triggers.trigger_router` | `route_ltf` | chronological first-valid; entry limit + stop reference |
| Intent lifecycle (R9) | `smc.backtest.intents.IntentBook.events` | `intent` | armed/placed/expired/replaced/dropped transitions |
| Execution fill | `smc.backtest.runner.BacktestRunner → reports.build_report` | `fill` | limit fill; ticket/route_id/close_kind/pnl recorded |

## 3. Dedup rule

One row per unique structural event. The dedup key is (event_type-scope, detection_tf, direction, rounded zone/level bounds, event timestamp) — for liquidity levels the family + `formed_at` are added; for the pillar layer the SCOPE is `pillar_outcome` so a geometry that alternates PASS/REJECT across batches still yields ONE row. The first observation fixes the row; later observations only bump `observed=N` (and flag `observed_event_types` on verdict flicker).

## 4. Volumes

### 4.1 Events by type (unique rows)

| event_type | rows | raw observations |
|---|---:|---:|
| `sweep` | 2041 | 1260827 |
| `fvg` | 802 | 597429 |
| `liquidity_level` | 4320 | 1554189 |
| `poi_raw` | 1418 | 1338099 |
| `poi_merged` | 1745 | 39210 |
| `poi_armed` | 31 | 31 |
| `displacement` | 1117 | 1260827 |
| `pillar_reject` | 1669 | 37381 |
| `pillar_pass` | 76 | 1829 |
| `route_ltf` | 10 | 10 |
| `intent` | 16 | 16 |
| `fill` | 2 | 2 |
| **total** | **13247** | **6089850** |

### 4.2 Events by type × detection timeframe

| event_type | D1 | H1 | H4 |
|---|---:|---:|---:|
| `sweep` | 0 | 1168 | 873 |
| `fvg` | 0 | 626 | 176 |
| `liquidity_level` | 0 | 2817 | 1503 |
| `poi_raw` | 151 | 414 | 853 |
| `poi_merged` | 0 | 1032 | 713 |
| `poi_armed` | 6 | 10 | 15 |
| `displacement` | 0 | 602 | 515 |
| `pillar_reject` | 0 | 967 | 702 |
| `pillar_pass` | 0 | 65 | 11 |
| `route_ltf` | 4 | 4 | 2 |
| `intent` | 8 | 6 | 2 |
| `fill` | 1 | 1 | 0 |

### 4.3 Funnel (machine counters)

| stage | count |
|---|---:|
| detected_raw | {'H4': 44922, 'H1': 46879} |
| merged | {'H4': 19206, 'H1': 20004} |
| passed_validation | {'H4': 454, 'H1': 1244} |
| armed | {'H4': 15, 'H1': 10, 'D1': 6} |
| armed_m8 | 27 |
| routes | 10 |
| placed | 2 |
| fills | 2 |

## 5. Review sample index

Sample charts: `review_sample/` (44 PNG) — stratified, spread evenly across the window.

| file | event_id | event_type | chart_tf | detect_tf | ts_utc | direction | tags |
|---|---|---|---|---|---|---|---|
| 001_sweep_H1_20250601T2200_evt-687f151bf74a.png | `evt-687f151bf74a` | sweep | H1 | H1 | 2025-06-01T22:00:00+00:00 | LONG |  |
| 002_sweep_H1_20250622T2300_evt-64def7d1248e.png | `evt-64def7d1248e` | sweep | H1 | H1 | 2025-06-22T23:00:00+00:00 | SHORT |  |
| 003_sweep_H1_20250711T1400_evt-0cdce9244384.png | `evt-0cdce9244384` | sweep | H1 | H1 | 2025-07-11T14:00:00+00:00 | SHORT |  |
| 004_sweep_H4_20250731T0400_evt-44422608ad5a.png | `evt-44422608ad5a` | sweep | H4 | H4 | 2025-07-31T04:00:00+00:00 | LONG |  |
| 005_sweep_H4_20250819T0000_evt-879aa0eb42e3.png | `evt-879aa0eb42e3` | sweep | H4 | H4 | 2025-08-19T00:00:00+00:00 | LONG |  |
| 006_sweep_H1_20250915T1300_evt-2d061f387926.png | `evt-2d061f387926` | sweep | H1 | H1 | 2025-09-15T13:00:00+00:00 | SHORT |  |
| 007_sweep_H1_20251015T0200_evt-279aaa50cb4e.png | `evt-279aaa50cb4e` | sweep | H1 | H1 | 2025-10-15T02:00:00+00:00 | SHORT |  |
| 008_sweep_H4_20251107T1600_evt-3da8ea8e26a3.png | `evt-3da8ea8e26a3` | sweep | H4 | H4 | 2025-11-07T16:00:00+00:00 | SHORT |  |
| 009_fvg_H4_20250602T0000_evt-46c8ca8f84ff.png | `evt-46c8ca8f84ff` | fvg | H4 | H4 | 2025-06-02T00:00:00+00:00 | LONG |  |
| 010_fvg_H1_20250623T2000_evt-0b2947c4f6e8.png | `evt-0b2947c4f6e8` | fvg | H1 | H1 | 2025-06-23T20:00:00+00:00 | SHORT |  |
| 011_fvg_H1_20250715T2200_evt-82c80084b387.png | `evt-82c80084b387` | fvg | H1 | H1 | 2025-07-15T22:00:00+00:00 | LONG |  |
| 012_fvg_H1_20250808T0900_evt-049faf10eb96.png | `evt-049faf10eb96` | fvg | H1 | H1 | 2025-08-08T09:00:00+00:00 | SHORT |  |
| 013_fvg_H4_20250903T0800_evt-142bb903f2cf.png | `evt-142bb903f2cf` | fvg | H4 | H4 | 2025-09-03T08:00:00+00:00 | LONG |  |
| 014_fvg_H1_20250926T0200_evt-6f2008192dc4.png | `evt-6f2008192dc4` | fvg | H1 | H1 | 2025-09-26T02:00:00+00:00 | LONG |  |
| 015_fvg_H1_20251017T1900_evt-d60d3544e26f.png | `evt-d60d3544e26f` | fvg | H1 | H1 | 2025-10-17T19:00:00+00:00 | LONG |  |
| 016_fvg_H1_20251110T0200_evt-eb6623b50f58.png | `evt-eb6623b50f58` | fvg | H1 | H1 | 2025-11-10T02:00:00+00:00 | LONG |  |
| 017_poi_raw_H4_20250601T2000_evt-1a8c65a87d76.png | `evt-1a8c65a87d76` | poi_raw | H4 | H4 | 2025-06-01T20:00:00+00:00 | LONG | M8 |
| 018_poi_raw_H4_20250624T0000_evt-b97527e66de8.png | `evt-b97527e66de8` | poi_raw | H4 | H4 | 2025-06-24T00:00:00+00:00 | SHORT | M8 |
| 019_poi_raw_H4_20250716T0400_evt-9b2445a66ad6.png | `evt-9b2445a66ad6` | poi_raw | H4 | H4 | 2025-07-16T04:00:00+00:00 | SHORT | M8 |
| 020_poi_raw_D1_20250808T0000_evt-00301ee373c9.png | `evt-00301ee373c9` | poi_raw | D1 | D1 | 2025-08-08T00:00:00+00:00 | SHORT | M8 |
| 021_poi_raw_H4_20250902T0400_evt-1a791fd0036b.png | `evt-1a791fd0036b` | poi_raw | H4 | H4 | 2025-09-02T04:00:00+00:00 | LONG | M8 |
| 022_poi_raw_H4_20250924T0400_evt-edcea22ef918.png | `evt-edcea22ef918` | poi_raw | H4 | H4 | 2025-09-24T04:00:00+00:00 | SHORT | M8 |
| 023_poi_raw_H4_20251015T0800_evt-6026ffe80fbb.png | `evt-6026ffe80fbb` | poi_raw | H4 | H4 | 2025-10-15T08:00:00+00:00 | LONG | M8 |
| 024_poi_raw_H4_20251106T0400_evt-933608c264f8.png | `evt-933608c264f8` | poi_raw | H4 | H4 | 2025-11-06T04:00:00+00:00 | SHORT | M8 |
| 025_poi_armed_D1_20250602T0800_evt-1aac178215ba.png | `evt-1aac178215ba` | poi_armed | D1 | D1 | 2025-06-02T08:00:00+00:00 | LONG | M8 |
| 026_poi_armed_H4_20250613T0800_evt-b5268a9ca63e.png | `evt-b5268a9ca63e` | poi_armed | H4 | H4 | 2025-06-13T08:00:00+00:00 | LONG | M8 |
| 027_poi_armed_H4_20250627T1200_evt-ba0dc36abfb9.png | `evt-ba0dc36abfb9` | poi_armed | H4 | H4 | 2025-06-27T12:00:00+00:00 | SHORT | M1|M7|M8 |
| 028_poi_armed_H1_20250715T0300_evt-4429f905e80a.png | `evt-4429f905e80a` | poi_armed | H1 | H1 | 2025-07-15T03:00:00+00:00 | LONG | M5|M8 |
| 029_poi_armed_D1_20250901T0300_evt-715da8979b8d.png | `evt-715da8979b8d` | poi_armed | D1 | D1 | 2025-09-01T03:00:00+00:00 | LONG | M8 |
| 030_poi_armed_H4_20250902T1200_evt-859e9480c0a7.png | `evt-859e9480c0a7` | poi_armed | H4 | H4 | 2025-09-02T12:00:00+00:00 | SHORT | M8 |
| 031_poi_armed_H1_20251002T1600_evt-2771a4b9f59a.png | `evt-2771a4b9f59a` | poi_armed | H1 | H1 | 2025-10-02T16:00:00+00:00 | SHORT | M1 |
| 032_poi_armed_D1_20251020T0200_evt-dd4746ea92d9.png | `evt-dd4746ea92d9` | poi_armed | D1 | D1 | 2025-10-20T02:00:00+00:00 | LONG | M8 |
| 033_route_ltf_M5_20250618T0735_evt-42da15e9731c.png | `evt-42da15e9731c` | route_ltf | M5 | H4 | 2025-06-18T07:35:00+00:00 | SHORT | M8 |
| 034_route_ltf_M5_20250703T1340_evt-58f48dec66f2.png | `evt-58f48dec66f2` | route_ltf | M5 | H1 | 2025-07-03T13:40:00+00:00 | SHORT | M7 |
| 035_route_ltf_M5_20250901T0310_evt-be26980c6c1c.png | `evt-be26980c6c1c` | route_ltf | M5 | H1 | 2025-09-01T03:10:00+00:00 | LONG | M4 |
| 036_route_ltf_M5_20250901T0310_evt-e5188c4a9233.png | `evt-e5188c4a9233` | route_ltf | M5 | D1 | 2025-09-01T03:10:00+00:00 | LONG | M8 |
| 037_route_ltf_M5_20250901T0310_evt-1a54c09b036d.png | `evt-1a54c09b036d` | route_ltf | M5 | H1 | 2025-09-01T03:10:00+00:00 | LONG | M1|M7|M8 |
| 038_route_ltf_M5_20251009T0535_evt-22900c3f8232.png | `evt-22900c3f8232` | route_ltf | M5 | D1 | 2025-10-09T05:35:00+00:00 | LONG | M8 |
| 039_route_ltf_M5_20251009T0535_evt-78a165973ea9.png | `evt-78a165973ea9` | route_ltf | M5 | D1 | 2025-10-09T05:35:00+00:00 | LONG | M8 |
| 040_route_ltf_M5_20251020T0215_evt-c300c4b4813f.png | `evt-c300c4b4813f` | route_ltf | M5 | D1 | 2025-10-20T02:15:00+00:00 | LONG | M8 |
| 041_route_ltf_M5_20251029T2210_evt-6e015adf1adc.png | `evt-6e015adf1adc` | route_ltf | M5 | H4 | 2025-10-29T22:10:00+00:00 | SHORT | M1|M7|M8 |
| 042_route_ltf_M5_20251114T2035_evt-1b1e590a9ac6.png | `evt-1b1e590a9ac6` | route_ltf | M5 | H1 | 2025-11-14T20:35:00+00:00 | SHORT | M1|M4|M7|M8 |
| 043_fill_M5_20250703T1345_evt-06e8f6501c55.png | `evt-06e8f6501c55` | fill | M5 | H1 | 2025-07-03T13:45:00+00:00 | SHORT | M7 |
| 044_fill_M5_20251020T0550_evt-4b9392988717.png | `evt-4b9392988717` | fill | M5 | D1 | 2025-10-20T05:50:00+00:00 | LONG | M8 |

## 6. Scoring workflow

1. Open `events.csv` / `events.jsonl` (full ledger) and `review_sample/` (stratified charts).
2. Score each sampled event: **CORRECT / PARTIAL / WRONG / UNCLEAR** against the locked flowchart.
3. Only after scoring, treat paper as more than ops. Paper tests the live path; this ledger is the identification question.

## 7. Explicit limitations

- Read-only measurement: no threshold, pillar, trigger, zone-band, R7/R9 or locked-constant change; V1.1 baseline freeze unchanged (git diff proves it).
- The detection stack is driven with GROWING prefixes per timeframe (the accepted Phase 3/4 composition). Stage 0/1 therefore re-emits the whole prefix every batch; the ledger dedups by geometry so each unique event appears once, with `observed=N` recording how many batches re-emitted it and `observed_event_types` when a geometry alternates verdicts (the known detection flicker).
- Per-POI rows (`poi_raw`, `poi_merged`, `pillar_*`) close over the evolving prefix: their recorded verdict is the FIRST observation, not a live rolling-window replay. `poi_id` on those rows is the batch-local id at first observation; use `event_id` (a stable geometry hash) to key rows.
- M8's per-model output is captured by the kind-labelled zone hook, which is a superset of `M8.detect()` (detect keeps only the latest zone per kind); M8 is therefore excluded from the generic `poi_raw` model hook.
- `entry_anchor` is populated only when a trigger actually sets it (e.g. F); absent stays blank — never invented.
- Swing objects (`detect_swings`) are not in the controlled vocabulary; the swings feed the liquidity scanner and are visible only through the structural levels / sweeps they produce.
- Trigger D emits nothing on volume-less data (A5 ruling) — its absence here is the code's, not a measurement gap.
- No PnL interpretation, no edge claim: `fill` rows carry the trade's own recorded outcome fields for completeness only.

### Assembly / measurement notes

- ASSEMBLED FROM TILED CHUNKS. A single 6-month run is not feasible in one process: the accepted composition re-scans the growing HTF prefix every batch, measured at 0.67 s/batch at a 6-month prefix (base code, instrumentation ~11% on top) => ~20 min projected. The LOCKED window was therefore tiled into non-overlapping 3-month exec windows, each running the same unified multi-TF composition with its own warm-up; the union is exact because a row's own ts_utc was bounded by its chunk's window (retain_window).
- Chunk-level verdicts close over each chunk's own prefix, so a Sep-Nov geometry is first-observed against a >=1-month warm-up (the LOCKED Phase 4 load) rather than a 4-month one. Documented deviation from a single-run composition.
- Read-only measurement; no PnL interpretation; `fill` rows carry recorded outcome fields only.

## 8. Return block

```
LEDGER_STATUS: PASS
WINDOW: 2025-06-01T00:00:00+00:00 -> 2025-11-30T23:00:00+00:00 (2 tiled chunks)
EVENTS: 13247
BY_TYPE: {"displacement": 1117, "fill": 2, "fvg": 802, "intent": 16, "liquidity_level": 4320, "pillar_pass": 76, "pillar_reject": 1669, "poi_armed": 31, "poi_merged": 1745, "poi_raw": 1418, "route_ltf": 10, "sweep": 2041}
ARMED: 31
ROUTES: 10
FILLS: 2
REVIEW_PNGs: 44
LEDGER_PATH: 06_RESEARCH\results\structure_ledger_6m/
REPORT_PATH: 06_RESEARCH/STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md
LOGIC_CHANGED: NO
HANDOFF_UPDATED: NO
NEXT_READY: Owner/expert sample scoring -> then paper dry_run under V1.1 freeze
```

*End of report. No edge language, no threshold change, no paper trading.*
