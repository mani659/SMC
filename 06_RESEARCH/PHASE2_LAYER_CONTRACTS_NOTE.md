# PHASE 2 — LAYER / PILLAR CONTRACT TESTS NOTE

**Status:** COMPLETE 2026-09-23 (Choice 1 sequence, Phase 2 of 4).
**Scope:** machine-checkable contracts only — known synthetic inputs → required PASS / FAIL / UNAVAILABLE with stable reason tokens. NOT expectancy research, NOT chart discretion, NOT a backtest. Zero production-logic changes; zero threshold edits.
**Evidence:** `04_SRC/tests/test_phase2_layer_contracts.py` (28 tests) · suite **726 passed** (698 → 726, +28) · population snapshot `06_RESEARCH/results/phase2_contracts/snapshot.json`.

---

## 1. Contract matrix → test node ids

### Stage 0c detectors (§2 rules)

| Contract | Behavior pinned | Test node |
|---|---|---|
| D-SWEEP-1 | SSL wick-pierce + close-back → `SweepResult` present, index/pool correct | `TestSweepContracts::test_d_sweep_1_ssl_wick_pierce_close_back_detects` |
| D-SWEEP-0 | No pierce / breakdown close → NO sweep (breakout exclusion) | `TestSweepContracts::test_d_sweep_0_no_pierce_no_sweep` |
| D-FVG-1 | Classic 3-candle gap → FVG zone [c1.high, c3.low], LONG direction, start_index | `TestFvgContracts::test_d_fvg_1_classic_gap_detected_with_direction` |
| D-FVG-0 | Contiguous c1/c3 overlap → empty FVG list | `TestFvgContracts::test_d_fvg_0_contiguous_overlap_no_fvg` |
| D-DISP-1 | BOS + directional FVG + ≥1×ATR → passed, magnitude recorded, bos_index | `TestDisplacementContracts::test_d_disp_1_valid_displacement_passes_with_magnitude` |
| D-DISP-0 | Magnitude < 0.5×ATR → hard_fail; injected into Pillar 2 → FAIL with the hard token | `TestDisplacementContracts::test_d_disp_0_below_hard_fail_is_not_valid_for_pillar_2` |
| (extra) | BOS without directional FVG → FAIL, token `missing directional FVG` | `TestDisplacementContracts::test_d_disp_bos_without_fvg_fails_with_token` |

### Pillars 1–5 (§6 R1 vocabulary, §7 soft rule)

| Contract | Behavior pinned | Test node |
|---|---|---|
| P1-FAIL | No unmitigated OB/FVG within ±0.5×ATR → FAIL, token `naked level` | `TestPillar1ZoneRefinement::test_p1_fail_naked_level` |
| P1-UNAVAIL | < 3 candles → UNAVAILABLE, token `insufficient candles` | `TestPillar1ZoneRefinement::test_p1_unavailable_insufficient_candles` |
| P2-UNAVAIL | No displacement map entry → UNAVAILABLE → pipeline REJECT (fail-fast) | `TestPillar2Displacement::test_p2_unavailable_no_map_entry` |
| P2-FAIL (hard) | Hard-fail displacement → FAIL, token `displacement < 0.5` | `TestPillar2Displacement::test_p2_fail_hard_fail_token` |
| P2-FAIL (BOS) | bos=False result → FAIL, token `missing BOS` | `TestPillar2Displacement::test_p2_fail_missing_bos_token` |
| P2-PASS | Valid injected result → PASS, token `BOS + directional FVG` | `TestPillar2Displacement::test_p2_pass_valid_injected_result` |
| P3-FAIL | LONG POI in PREMIUM → FAIL, token `region of the dealing range`, data.region=`premium` | `TestPillar3PremiumDiscount::test_p3_fail_wrong_region` |
| P3-PASS | LONG POI in DISCOUNT → PASS, data.region=`discount` | `TestPillar3PremiumDiscount::test_p3_pass_discount_for_long` |
| P3-UNAVAIL | No confirmed dealing range → UNAVAILABLE (never silent pass) | `TestPillar3PremiumDiscount::test_p3_unavailable_without_range` |
| P4-PASS | CREATED/FRESH state → PASS, state token in detail AND data | `TestPillar4Freshness::test_p4_pass_created_context` |
| P4-FAIL | TESTED state → FAIL, token `no second-touch trades` | `TestPillar4Freshness::test_p4_fail_tested_poi` |
| P5-SOFT | No inducement → pillar FAIL + 0.7 modifier, but PIPELINE still PASSes (modifier < 1.0) | `TestPillar5Inducement::test_p5_soft_fail_does_not_reject_pipeline` |
| P5-WITH | SSL pool strictly between zone top and last close → PASS, modifier 1.0 | `TestPillar5Inducement::test_p5_with_inducement_full_score` |

### Cross-layer handoffs

| Contract | Behavior pinned | Test node |
|---|---|---|
| H-MERGE | Overlapping same-direction POIs → ONE POI: tag union, widest zone, earliest id; opposite-direction / disjoint never merge | `TestMergeHandoff::test_h_merge_*` (3 tests) |
| H-ATTR (latest) | Two same-direction displacements → the LATER run entry wins (`is` identity) | `TestAttributionHandoff::test_h_attr_latest_same_direction_sweep_wins` |
| H-ATTR (omit) | POI direction with no matching sweep → key omitted (never invented) | `TestAttributionHandoff::test_h_attr_no_matching_sweep_omits_key` |
| H-ATTR (end-to-end) | Omitted key → engine.validate → REJECTED at Pillar 2 UNAVAILABLE | `TestAttributionHandoff::test_h_attr_pipeline_rejects_when_omitted` |
| H-ROUTER | Scan returns ≤ 1 route (chronological first-valid), or None; deterministic on repeat | `TestRouterHandoff::test_h_router_*` (2 tests) |

---

## 2. Reason tokens (stable strings asserted by the tests)

| Pillar | Status | Token (owned by the pillar module — drift breaks the test) |
|---|---|---|
| P1 | FAIL | `naked level` |
| P1 | UNAVAILABLE | `insufficient candles` |
| P2 | UNAVAILABLE | `no displacement result` |
| P2 | FAIL | `displacement < 0.5` (hard) · `missing BOS` · `missing directional FVG` · `displacement below 1× ATR` |
| P2 | PASS | `BOS + directional FVG` |
| P3 | FAIL | `region of the dealing range` (+ `data["region"]` ∈ {premium, discount, equilibrium}) |
| P4 | FAIL | `no second-touch trades` (+ `data["state"]` = lowercase POIState value, also embedded in detail) |
| P5 | FAIL (soft) | `70% score` (modifier = `INDUCEMENT_WITHOUT_SCORE` from locked_constants) |

---

## 3. Population snapshot (optional §2d — RUN)

- Script: `06_RESEARCH/scripts/phase2_contract_population_snapshot.py`
- Output: `06_RESEARCH/results/phase2_contracts/snapshot.json`
- Window: 2025-10-01 → 2025-10-15 (14 days), H4+H1 detection series, one snapshot step per new H4 close, via the existing per-TF `DetectionDriver.validate_window` (the frozen driver behind the C1 seam).
- Counts (read-only, no PnL): detected_raw 1,294 → merged 946 → **passed 82** (8.7% of merged).
- **Pillar first-failure histogram: P2:fail 797 (84.3%) · P1:fail 37 (3.9%) · P3:fail 30 (3.2%).**
- Pillar status histogram: P1 pass 909 / fail 37; P2 pass 112 / fail 797; P3 pass 82 / fail 30; P4 pass 82; P5 pass 78 / fail 4 (soft).
- Reading: Pillar 2 (displacement) dominates first failures in the population — consistent with the attribution honesty rule (a POI whose direction has no same-direction sweep gets NO entry → UNAVAILABLE/FAIL, never invented). No action item; this is documentation, not tuning input.
- One degenerate early window (H1 prefix of 1 bar) skipped loudly (`IndexError` caught + reported); 268/269 windows processed.

---

## 4. Gaps — contracts not yet enforceable without production changes (list only, NOT fixed)

1. **P4 historical-scan equivalence** — Pillar 4 gates on POI state only (documented V1 boundary); a contract that a FRESH-at-validation POI was untouched *since creation* would need a candle-rescan mode in the pillar (production change). Current contract pins the state-based semantics as-coded.
2. **P5 trendline inducement** — documented as not machine-testable from OHLCV in V1; no contract possible without a new detector (out of scope).
3. **Trigger-level contracts** — the router contract is a smoke (single route / determinism); per-trigger (A–F) geometry contracts belong to the existing per-trigger test files and are not duplicated here.
4. **M8 HTF overlap bonus contract** — `score_poi`'s +0.10 M8 bonus is exercised only implicitly through the pipeline; a dedicated contract would need an M8 fixture with `htf_overlap=True` (covered in the model fixture tests instead).
5. **Seam-level pillar histogram** — `MultiTFBatchReport` carries counts only by contract §2 design; per-POI pillar results are visible only on the driver path (the snapshot uses it). A pillar histogram *through the seam* would need a report-field change (production surface).

---

## 5. Files

- Tests: `04_SRC/tests/test_phase2_layer_contracts.py` (28 tests, one file — node ids in §1)
- Snapshot: `06_RESEARCH/scripts/phase2_contract_population_snapshot.py` + `06_RESEARCH/results/phase2_contracts/snapshot.json`
- Suite: **726 passed** (698 baseline + 28), zero regressions, zero production edits (`git diff` on `04_SRC/smc/` untouched by this task)
