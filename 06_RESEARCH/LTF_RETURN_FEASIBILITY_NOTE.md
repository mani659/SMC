# LTF-RETURN FEASIBILITY MEASURE — Mode A entry representation (read-only)

> **DIAGNOSTIC — NOT EDGE / NOT AUTHORIZATION TO SHIP.**
> The accepted design's pre-registered feasibility gate
> (`00_LOCKED/MODE_A_LTF_RETURN_ENTRY_DESIGN.md` §4 + §6, applied
> verbatim, first-fired order) executed on the frozen 6m populations.
> Counts support no expectancy, win-rate or edge claim. No product
> limit, trigger, gate, or constant change is proposed or authorized;
> nothing is wired. `PASS_FEASIBILITY` would have been a discussion
> unlock only — it did not fire; the frozen verdict is below.

**Date:** 2026-10-14 · **Authority:** Architect acceptance (final for
this measure): HTF POI context only; entry limit from LTF return
structure (primary = M5 displacement-FVG of the qualifying proof leg;
origin OB = report-only alternate, never hybrid); strict protected-
side rule at the true proof close or `STRUCT_UNAVAILABLE`; FR-2
distal / engine §5 / product rest lifetime reused exactly; no HTF-
zone-membership carve-out (intersection is a *label column*, never a
filter); confirmation TF = M5; same frozen P0/P1 populations and
verified true-frame convention (+6018) as the accepted entry-
representation study. **LOGIC_CHANGED: NO** — research script + tests
only.

---

## 1. Frozen method (design §6 operationalized; no tuning)

| Item | Value |
|---|---|
| Script | `06_RESEARCH/scripts/ltf_return_feasibility_measure.py` |
| Base rows | the frozen `entry_representation/rows.csv` reused row-for-row (true-frame `proof_bar_grid` / `armed_bar_grid` / zone bounds / retired-control gaps) |
| Structure detection | the product's OWN detector `smc.detection.fvg_detector.detect_fvgs` (locked §3 3-candle semantics), imported read-only; origin-OB pairing per the product's R1 §3.1 (candle immediately before the FVG's first candle) |
| Selection (frozen §4b) | **THE** nearest-the-proof direction-matched FVG with all three candles inside `[proof−48, proof]` (REUSE of frozen H_PROOF=48; no new constant); limit = near edge (LONG: zone top; SHORT: zone bottom) **iff strictly on the protected side of the true proof close**; on failure the report-only OB of the **same** formation under the same strict rule; neither → `STRUCT_UNAVAILABLE` (fail-closed, never inferred, never an HTF-edge limit) |
| Maturity | the product detector's rules as-is (ratified Q3; no maturity constant added) |
| Retest window / expiry | `[proof, proof + rest lifetime]` (product rest lifetime reused via the frozen joins; no new constant); no touch → paper `EXPIRED_NO_FILL` (touch-only; SL/TP never invented) |
| HTF zone | `htf_zone_intersect` LABEL column only — never a filter, never a price input |
| Determinism | dual runs byte-identical (`ltf_return_feasibility_run2` mirror is the receipt); no wall-clock in artifacts |

**Build-time defect disclosed (caught by tests, fixed before final
artifacts):** the first implementation allowed the selection loop to
fall through to the *next-nearest* FVG when the nearest one failed the
strict-side rule. The frozen design fixes the primary as the
*singular* nearest formation — the deviation was caught by the focused
tests and corrected to the singular rule before the finalists were
written; two runs of the corrected code are byte-identical (rows sha
`abf56c15…`, summary sha `ade8f298…`).

## 2. Frozen population reconciliation

| Population | Expected | Observed | Source |
|---|---:|---:|---|
| P0 product routes | 10 | 10 ✓ | entry-rep rows (population=0) asserted in-script |
| P1 armed+coincident | 268 | 268 ✓ | entry-rep rows (population=1) asserted |
| Total rows written | 278 | 278 ✓ | one family row per episode (278 data rows) |
| Warm-up offset | 6018 | 6018 ✓ | asserted against the loaded grid (42,296 bars) |

## 3. Primary FVG feasibility funnel + terminal reasons

| Stage / reason | n | share |
|---|---:|---:|
| P1 rows analyzed | 268 | — |
| `STRUCT_FOUND_FVG` (primary FVG passed strict side) | **119** | 44.4% |
| `STRUCT_FOUND_OB` (report-only alternate passed) | **28** | 10.4% |
| `STRUCT_UNAVAILABLE` (no formation, or both edges fail strict side) | **121** | 45.1% |
| Missing rest lifetime / missing direction / other invention-gaps | **0** | 0.0% |

STRUCT_FOUND rows total **147/268 (54.9%)**.

## 4. Data-gap and STRUCT_UNAVAILABLE counts (fail-closed accounting)

- `data_gap_rows_p1` = **121** → `data_gap_rate_p1` = **45.1%** — every
  one of them a `STRUCT_UNAVAILABLE` selection outcome (never invented
  geometry). The 5 other gap classes (missing proof bar, direction,
  ATR, zone bounds, lifetime) fired **0** times on P1.
- Kill 1 (`DATA_GAP rate > 0.30 → INCONCLUSIVE`) therefore **fires**.

## 5. True-frame gap-at-proof distribution and near-market mass

| View | n | p25 | median | p75 | ≤ 1.0 ATR | ≤ 2.0 (band) |
|---|---:|---:|---:|---:|---:|---:|
| over **all 268** P1 rows (verdict denominator, per design) | 268 | — | **0.638** | — | **34.7%** | 50.0% |
| over the 147 STRUCT_FOUND rows (descriptive) | 147 | 0.272 | 0.638 | 1.246 | **63.3%** | ~83% |
| gap at the ARM bar (secondary; the wait deepens it) | 147 | — | **15.62** | — | — | — |
| CONTROL proximal edge (retired control, frozen) | 268 | — | 8.275 | — | 4.1% | — |

The **readable subset** shows exactly the near-market representation
the owner's story wants — median 0.638 ATR at the proof close, ~14×
closer than the retired HTF-edge control (8.275). But the verdict
denominator is the full frozen P1 population, and **45.1% of it has no
honest geometry under the frozen selection rule** — so the near-mass
share measured over all rows is 34.7% (< the frozen 50% kill), and the
family's headline cannot be honestly read as PASS.

## 6. HTF-context-zone intersection label (label only; no filter)

Of the 147 STRUCT_FOUND rows: **114 lie inside the episode's HTF
context zone, 33 do not** (label-only column; no row was filtered or
re-priced on this basis — accepted-ruling compliance).

## 7. Control-fill overlap (kill-4 gate)

| Fill route | chosen structure | limit | gap@proof | retest in window | verdict input |
|---|---|---:|---:|---|---|
| poi-014146:F@5653 | OB_alternate | 3279.355 | 0.39 ATR | touched ✓ | retained |
| poi-047805:C@18278 | STRUCT_UNAVAILABLE | — | — | — | **not evaluable** |
| poi-073511:F@27542 | FVG_primary | 4252.735 | 1.21 ATR | not touched in-window | not retained |

- Evaluable fills = **2** (not 3): the `poi-047805` proof leg (a
  C-trigger ending-diagonal class) produced **no direction-matched
  3-candle imbalance anywhere in its frozen window** — a smooth leg, no
  imbalance proveable → `STRUCT_UNAVAILABLE` (the honest fail-closed
  outcome; substituting or widening would violate the acceptance's
  "do not infer" instruction).
- **Kill 4's gate therefore cannot fire** (design §6 4: "0/3 … when
  evaluable" — only 2 evaluable). Stated plainly: the kill is
  **unprovable on this window**, not passed.
- Of the 2 evaluable: 1 retained (the OB-alternate row), 1 not
  retained.

## 8. Report-only OB alternate (clearly separated)

| View | n | median gap@proof | share ≤ 1.0 | role |
|---|---:|---:|---:|---|
| `OB_alternate` (only rows whose chosen structure was the OB) | 28 | **0.26 ATR** | 92.9% | **report-only** — no kill is evaluated on it, never combined with the primary (accepted ruling) |

The alternate exists only where the leg's own FVG failed the strict
side; its geometry is the tightest of all (the OB candle sits nearest
the impulse origin). It is evidence for a later design discussion,
never a second rule in this measure.

## 9. Exact first-fired kill/verdict

```
KILL_EVALUATION (design §6 verbatim, first-fired order):
  (1) DATA_GAP rate 0.451 > 0.30           -> INCONCLUSIVE          FIRED
  (2) median gap (readable) 0.638 <= 2.0   -> FAIL_STILL_FAR        not fired
  (3) share<=1.0 over P1 0.347 < 0.50      -> FAIL_NO_NEAR_MASS     fired (recorded)
  (4) fills evaluable = 2 (< 3)            -> gate unsatisfied      cannot fire
  (5) paper EXPIRED 0.143 <= 0.85 (n=147)  -> FAIL_UNFILLABLE       not fired

VERDICT: INCONCLUSIVE  (first-fired rule names the verdict)
```

**The verdict is INCONCLUSIVE — not PASS_FEASIBILITY.** Per the
pre-registered order the readability gate (kill 1) owns the name. The
verdict does NOT assert the family is bad: the 147 structured rows
show the near-market story working (median 0.638 ATR; the OB-alternate
subset 0.26; both order-of-magnitude closer than the retired control).
It says the frozen §4b selection rule cannot read the family
honestly on 45.1% of this population, and neither substituting
geometry nor widening the window was permitted.

## 10. What makes this inconclusive (the concrete limitation)

The inconclusiveness has ONE structural cause: **45.1% of P1 rows have
no direction-matched nearest-the-proof FVG whose near edge sits on the
protected side of the proof close inside the reused 48-bar lookback** —
some because the leg left no 3-candle imbalance (ending-diagonal class
legs), some because the FVG the leg did create had already been
retraced through by the proof close (near edge on the wrong side), with
the OB pair failing the same strict rule. Resolving it is a design
amendment decision (e.g. re-rating the singular-nearest rule, the
lookback pin, or a declared multi-formation precedence) — **explictly
out of scope here** by the no-post-hoc-change guardrail. Nothing was
softened to manufacture a PASS.

## 11. Limitations (binding on any reuse)

- Counterfactual reconstruction on frozen artifacts; not a product
  run; touch-only paper labels for P1 (`FILLED_NO_RESOLVE` has no
  SL/TP — never invented).
- One candidate per episode at its first proof; one 6m window, one
  instrument, one feed.
- The OB-alternate pairing is the product's literal R1 §3.1 rule
  applied to the singular nearest formation; other pairing readings
  exist and were not measured (banned post-hoc).
- Kill 4's gate was satisfiable only with 3 evaluable fills; 1 of 3
  was honestly un-proveable (`STRUCT_UNAVAILABLE`) — a structural
  limitation of the family on this window, disclosed rather than
  forced.
- The singular-primary correction (§1) changed selection counts vs the
  abandoned mid-build variant; the shipped artifacts are the
  corrected, test-verified, determinism-matched ones only.

## 12. Artifacts, tests, governance, NEXT

- Script: `06_RESEARCH/scripts/ltf_return_feasibility_measure.py`
  (read-only imports of the frozen studies + the product's own FVG
  detector; no fork, no grid search, no tuning).
- Results (local-only, gitignored):
  `06_RESEARCH/results/ltf_return_feasibility/{rows.csv, summary.json}`
  — 278 rows (per-episode structure geometry, gaps, bands,
  intersection label, paper labels, fail-closed reasons);
  `summary.json` carries the frozen constants, distribution views,
  the exact kill evaluation, the report-only alternate view, and the
  control baseline. Dual-run byte-identical (`_run2` mirror; rows sha
  `abf56c15…`, summary sha `ade8f298…`).
- Tests: `04_SRC/tests/test_ltf_return_feasibility_measure.py`
  (**8**) — constants pin (48-lookback reuse + the exact §6 kill
  numbers + the 268/10 populations), singular-nearest selection rule,
  strict-side + OB-alternate + the fail-closed UNAVAILABLE paths,
  label-only HTF-intersection, touch-only paper semantics with the
  frozen helper's range-touch contract, and the first-fired kill
  branches at exactly the frozen thresholds.
- Governance: `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`,
  `CHANGELOG.md` — docs-only, `LOGIC_CHANGED: NO`; `locked_constants.py`
  diff = the pre-existing dated spread-grade amendment only; **no
  production file changed** (the only `04_SRC` additions are the test
  files of these read-only measures).
- **NEXT: Architect review of the feasibility result.** The frozen
  verdict is INCONCLUSIVE on readability, with the readable subset
  promising (near-market by an order of magnitude). Any follow-up —
  re-rating the §4b selection breadth, re-pinning the window, or
  stopping here — must arrive as its own dated design amendment with
  re-frozen kills before any re-measure. Nothing else is authorized.

---

**RETURN BLOCK**

```
REP_MEASURE_STATUS: PASS (execution; pre-registered verdict = INCONCLUSIVE)
WINDOW: frozen 6m (exec 2025-06-01 -> 2025-11-30; grid 42,296 M5 bars, offset 6018 asserted)
N_P0: 10
N_P1: 268
PRIMARY_RULE_NAME: FVG_primary (M5 displacement FVG; OB_alternate report-only)
STRUCT_FOUND_P1: 147/268 (54.9%: FVG 119 + OB-alt 28) | STRUCT_UNAVAILABLE 121 (45.1%)
MEDIAN_GAP_ATR_P1: 0.638 (readable subset; verdict denominator = full P1)
PCT_LE_1_P1: 0.347 (over all P1) / 0.633 (over the 147 structured rows)
FILL_OVERLAP: 1/2 retained; 1/3 not evaluable (STRUCT_UNAVAILABLE; kill-4 gate unsatisfiable)
KILL_FIRED: [INCONCLUSIVE (0.451 > 0.30), FAIL_NO_NEAR_MASS (0.347 < 0.50)]
VERDICT: INCONCLUSIVE
NOTE_PATH: 06_RESEARCH/LTF_RETURN_FEASIBILITY_NOTE.md
SUITE: full repo suite green (prior 1119 + 8 new tests)
LOCKED_CONSTANTS_DIFF: empty
LOGIC_CHANGED: NO
HANDOFF_UPDATED: YES
NEXT_READY: Architect review -> feasible dated amendment OR stop
```
