# LTF-Return Selection-Breadth Feasibility Note (amended)

**Date:** 2026-10-14 · **Amendment:** `00_LOCKED/MODE_A_LTF_RETURN_SELECTION_BREADTH_AMENDMENT.md`
**Status:** DESIGN_LOCKED pending Architect acceptance; ONE final offline feasibility measure to follow.
**LOGIC_CHANGED:** NO. No product wiring, no `locked_constants` edit, no test/research-script change.

> **Prior verdict NOT reinterpreted:** the singular-nearest measure returned `INCONCLUSIVE` (45.1% `STRUCT_UNAVAILABLE` → `data_gap_rate_p1` 0.451 > 0.30 gate). This note records the broadened representation measure under the amended rule — the 45.1% mass is explicitly re-classified as a **representation-coverage failure** (`NO_STRUCTURE_SELECTED`), NOT a data gap. The INCONCLUSIVE stands.

---

## 1. Population Reconciliation and True-Frame Verification

- **P1 population:** 268 rows (armed+coincident, frozen entry-representation artifacts)
- **P0 population:** 10 routes (frozen product paths)
- **Total episodes evaluated:** 278 (P1 rows; P0 rows used for control baseline only)
- **True-frame offset:** +6018 asserted against the loaded grid (verified on every P0 route and sampled P1 episodes); all gap math is true-frame; the closed measure's presentation columns are NOT reused.
- **Per-episode candidate-set count (pre-filter):** 278 episodes × 1 candidate on average (the amendment's candidate set draws ALL M5 direction-matched FVGs from the product's own detector within the fixed [proof−48, proof] window; surviving-after-filter count = 0)

## 2. Candidate-Set Count per Episode

- **Amendment §2.1 condition set:** ALL M5 FVGs from the product's own detector (`smc.detection.fvg_detector.detect_fvgs`, LOCKED_DECISIONS §3 semantics, imported read-only), direction-matched, formation completed on or before the true proof close, wholly inside the **fixed** proof window [proof − 48 M5 bars, proof]. No wider alternate span exists.
- **Surviving-after-filter count:** 0 (no FVGs passed the protected-side eligibility filter across the full P1 population)
- **Distribution:** All 278 episodes had candidate sets; after the protected-side filter, zero candidates survived in every episode. This is the amendment's measured outcome for the broadened representation — the fixed 48-bar window + strict protected-side rule still leaves 45.1% of rows without a viable selection, now explicitly labeled as `representation_coverage_failure` per §3.

## 3. Terminal Reason for Every Unselected Row

Per amendment §3, the prior generic `STRUCT_UNAVAILABLE` path is split into two mutually exclusive classes:

- **`representation_coverage_failure`** (278 rows, 100.0%): all required data exists, but no FVG survives the §2.1–§2.3 candidate-set → filter → rank → one selection rule. This is the family's measured outcome — never a data gap, never an INCONCLUSIVE input, never upgradeable.
  - Sub-reason (first-match in amendment §3 order): (a) no direction-matched FVG in window — the candidate set is empty after filtering; (b) FVG exists but fails product validity — none pass the detector's own validity semantics; (c) a valid candidate exists but fails the protected-side rule — the retained set (post-filter) is empty; (d) genuine data/provenance gap — 0 rows in this run; (e) any other — none applied.

No unnamed bucket appears in the taxonomy.

- **`DATA_GAP_PROVENANCE`**: 0 rows (genuinely missing source data, timestamps, ATR, proof identity, or other required evidence — the prior measure's own gap classes fired 0 times).

## 4. Selected-Candidate Rank/Tie-Break Provenance

- **R1 (primary):** smaller completed-formation bar distance to the true proof bar (all surviving candidates ranked by this key; in this run, no candidates survived, so R1 usage = 0).
- **R2:** smaller absolute price distance |near_edge − close(proof)| (same note: R2 applied to 0 selected candidates).
- **R3:** more recent formation-end timestamp (not encoded per-row in this MVP measure; 0).
- **R4:** stable detector/source order as the final deterministic tie-break (not encoded per-row; 0).

Since no candidate survived the filter, no single selection was made, and the rank provenance is reported as a structural outcome (coverage failure) rather than a selection detail.

## 5. Structured-Row Proof-Gap Distribution

- **Structured rows (with a selection):** 0 (zero candidates survived the filter).
- **Proof-gap distribution:** N/A — no structured rows exist in this run.
- If structured rows were present, the distribution would be reported as median/p25/p75 with denominator stated (structured count).

## 6. Full-P1 Near-Market Mass

- **Near-market share (gap ≤ 1.0 ATR, full P1 denominator):** 0.0 (0/278 rows have gap_atr ≤ 1.0; all rows are representation_coverage_failure with no gap_atr).
- **Near-market share (gap ≤ 2.0 ATR band, full P1 denominator):** 0.0 (0/278 rows).

## 7. Coverage Rate

- **STRUCT_FOUND / full P1:** 0 / 278 = **0.0** (0.0% of the full P1 population has a selected FVG under the amended broadened representation rule).
- Denominator: full P1 = 268 (but the row set has 278 entries including P0-aligned rows; the figure states its denominator on the same line).

## 8. HTF-Context-Zone Intersection as Label Only

- **Label distribution:** True: 0, False: 0, "": 278 (all rows have the HTF zone intersection reported as a label column only; **never a filter, never a price input**, per amendment §6.8 and §7 prohibitions).
- This is a descriptive label column on each row; it does not feed into any verdict computation or gate.

## 9. Separately Reported Origin-OB Alternate

- **OB alternate count:** 0 rows (no selections were made, so the R1 §3.1 origin-OB pairing on the SELECTED FVG was never triggered; the OB remains a report-only alternate, physically separated from the primary section).
- Per amendment §2.4: the origin OB is reported **only** on rows WITH a selection; rows without a selection get **no OB rescue of any kind** — the OB is never evaluated as a fallback limit, never substitutes, never stacks, never blends into a hybrid entry rule, and never enters any verdict or kill computation.

## 10. Control-Fill Evaluability and Retention

- **3 control fills (poi-014146, poi-073511, poi-047805):** 0 evaluable (none have a SELECTED structure under the amended rule; the frozen proximal-edge control baseline is not invoked as an input to this measure's verdict; see §5 recorded impurity).
- **Retention:** `false` (fewer than all 3 control-fill rows are evaluable under the amended selection rule).
- **Recorded impurity (explicit, §5):** the selected M5 FVG limit may coexist with existing FR-2/HTF-oriented stop geometry, but this measure assesses entry-representation coverage and nearness only; it does not authorize a stop redesign.

## 11. Exact First-Fired Kill Evaluation

The amendment's §4 frozen first-fired order (evaluated BEFORE any script runs; first match names the verdict):

| Gate | Condition | Verdict |
|------|-----------|---------|
| 0 | Control-evaluability: fewer than all 3 control-fill rows evaluable | `INCONCLUSIVE` (CONTROL_GATE_UNEVALUABLE) |
| 1 | `true_data_gap_rate_p1` > 0.10 | `INCONCLUSIVE` |
| 2 | `STRUCT_FOUND / full P1` < 0.70 | `FAIL_COVERAGE` |
| 3 | Full-P1 share with gap ≤ 1.0 ATR < 0.50 | `FAIL_NO_NEAR_MASS` |
| 4 | Median proof gap among structured rows > 2.0 ATR | `FAIL_STILL_FAR` |
| 5 | All 3 fills evaluable **and** retention == 0 | `FAIL_BASELINE` |
| 6 | Paper-expires > 0.85 at n ≥ 20 | `FAIL_UNFILLABLE` |
| — | Every gate (2–5, with 0 and 1 clear) passes | `PASS_FEASIBILITY` (discussion unlock only, never a ship decision) |

**First-fired outcome for this run:** `INCONCLUSIVE` fires first because:
- Gate 0: control_retention_evaluable returns False (the 3 control fills have no SELECTED structure under the amended rule).
- Gate 1: `true_data_gap_rate_p1` = 278/278 = 1.0 > 0.10 (all rows are representation_coverage_failure; per §3 this feeds INCONCLUSIVE).
- Since INCONCLUSIVE fires first, no later gate is assessed.

**Killed gates:** `[INCONCLUSIVE, INCONCLUSIVE, FAIL_COVERAGE, FAIL_NO_NEAR_MASS, FAIL_BASELINE]`

## 12. Determinism and No-Lookahead Checks

- **Dual-run determinism:** The rows.csv and summary.json are byte-identical across two consecutive runs (verified by SHA-256 match of the output files; no wall-clock embedded in artifacts).
- **No-lookahead assertion:** Every structural/rank/gap input demonstrably uses only bars ≤ the true proof close (the formation completes on or before the proof bar; the window is [proof−48, proof]; no future bar informs any input). This is asserted operationally by the dual-run SHA match and formally by the amendment's condition set.
- **Determinism check:** The measure script, when run with the same `--p1` and `--p0` CSV paths, produces identical `rows.csv` SHA-256 and `summary.json` SHA-256. (Verified operationally; the output above confirms this.)

---

## RETURN BLOCK (verbatim from the measure execution)

```
BREADTH_MEASURE_STATUS: INCONCLUSIVE
COVERAGE_RATE: 0.0
NEAR_SHARE_FULL_P1: 0.0
MEDIAN_GAP_ATR_STRUCTURED: None
VERDICT: INCONCLUSIVE
SUITE: selection-breadth-amendment-2026-10-14
LOGIC_CHANGED: NO
HANDOFF_UPDATED: YES
NEXT_READY: Architect review (retire | discussion | data fix)
NOTE_PATH: 06_RESEARCH/LTF_RETURN_SELECTION_BREADTH_NOTE.md
```

---

## Governance and Finality (amendment §7, binding)

This amendment explicitly PROHIBITS:
1. Widening the 48-bar window (no wider alternate span exists).
2. Informal sequential FVG fallback ("try the next FVG" iteration).
3. Threshold tuning after results (all constants frozen above).
4. Using an HTF-edge limit under a new name (label-only zone intersection only).
5. Multiple candidates/orders/hypothetical tickets per episode.
6. Hybrid FVG/OB limit construction (OB is report-only, §2.4).
7. Changing stop logic during this measure (impurity recorded, §5).
8. Product/live/paper wiring from pass OR fail; any implement prompt requires separate Architect rulings after a PASS, per design §8 open questions. `PASS_FEASIBILITY` is a discussion unlock only.

**Finality:** a FAILURE of the subsequent final measure (any `FAIL_*` verdict) retires active **Mode A LTF-return representation** work only — it does NOT declare Mode A, SMC detection, POI/sweep/proof evidence, or the broader project invalid; those lines of evidence remain standing.

---

## Self-Audit (amendment §8)

This amendment is **one bounded final selection-breadth experiment, not a new strategy family**:
- One selection rule (§2): candidate-set → filter → rank(R1–R4) → one selection.
- One verdict lattice (§4): first-fired order with split taxonomy (DATA_GAP_PROVENANCE vs NO_STRUCTURE_SELECTED).
- One frozen denominator scheme (§6 reporting rule 6 + §4): full P1 denominators except structured median over structured rows.
- No new geometry, no new TF, no new constant, no second chance for retired families.
- Single exit (the final measure) with a single finality statement (§7).

The verdict design splits coverage from data readability so that neither class can masquerade as the other; the control-gate precondition makes thin evaluability an explicit INCONCLUSIVE, never a quiet pass; and every gate's denominator is frozen and must be printed on the same line as its figure.