# MODE A — LTF-RETURN SELECTION-BREADTH AMENDMENT (selection: candidate-set → filter → rank → one)

> **DESIGN / POLICY — NOT EDGE / NOT AUTHORIZATION TO SHIP.**
> The ONE permitted dated design amendment to
> `00_LOCKED/MODE_A_LTF_RETURN_ENTRY_DESIGN.md`, enabling exactly one
> FINAL offline feasibility measure of the active Mode A LTF-return
> representation branch. This amendment tests ONE deterministic
> broadened-selection representation — it introduces no new geometry
> family, no new strategy, and no second chance for any retired rule.
> Nothing here changes product logic, a trigger, a gate, a stop, a
> constant, or wiring; nothing claims expectancy, win-rate, or edge;
> nothing reinterprets or reopens the prior measure's verdict.
> Acceptance is the Architect's; until then this is a policy paper
> only.

**Date:** 2026-10-14 · **Authority:** Lead Architect, under the owner
ruling recorded in `POST_V1_ACTIVE_TODO.md` / `SESSION_HANDOFF.md`
(Mode A = HTF context + LTF return entry; proximal-edge family
retired). Amends: `00_LOCKED/MODE_A_LTF_RETURN_ENTRY_DESIGN.md` §4b/§4c
selection rule and §6 verdict design **only**; every other section of
that design stands frozen. **LOGIC_CHANGED: NO** — docs only; no
`04_SRC/smc` edit, no `locked_constants.py` edit, no live/paper config,
no test or research-script change in this task, no touch of any frozen
artifact. Product wiring NOT started.

**DESIGN_LOCKED pending Architect acceptance. NEXT after acceptance =
ONE final offline feasibility measure** (its own dated read-only task;
kill criteria per this amendment, frozen NOW, before its script is
written or run). No further amendment is permitted before that final
measure; a further amendment requires the measure to be run as-is
first.

---

## 1. Status / Provenance / Non-Goals

- **Status:** DESIGN_LOCKED pending Architect acceptance; ONE final
  feasibility measure to follow.
- **Provenance (frozen, restated without reinterpretation):** the
  prior singular-nearest-formation measure
  (`06_RESEARCH/LTF_RETURN_FEASIBILITY_NOTE.md`) was correctly executed
  under its frozen singular-selection rule and returned the frozen
  verdict **`INCONCLUSIVE`**: `data_gap_rate_p1` = 45.1% (> the frozen
  0.30 gate) because 121/268 rows were `STRUCT_UNAVAILABLE`, while the
  147 structured rows showed the intended near-market representation
  (median gap **0.638 ATR** at proof; OB-alternate subset 0.26) versus
  the retired control (8.275). **That verdict stands exactly as
  recorded: the readable subset is evidence, not a pass, and this
  amendment does not, cannot, and must not be read as upgrading it.**
- **Diagnosis (the single cause this amendment addresses):** the
  45.1%/`STRUCT_UNAVAILABLE` mass was a **representation-coverage
  failure of a singular-selection rule** (by the frozen rule the ONE
  nearest-the-proof formation was decisive even when other same-leg
  formations would have preserved the story), not missing data — the
  prior measure's own gap classes (missing proof/direction/ATR/
  lifetime) fired 0 times.
- **Aim:** test ONE deterministic broadened selection representation
  (candidate set → filter → rank → exactly one selection) against the
  SAME frozen populations, windows, semantics, and unchanged
  product rules. Not a new geometry family; not a menu; not another
  variant vessel.
- **Non-goals (binding):** no HTF-edge limit under any new name; no
  mid-zone / interior / floating limit; no market orders; no Mode B;
  no ML; no gate softening; no FVG/OB hybrid; no multiple concurrent
  candidates per episode; no expectancy claim; no product or live
  wiring from any verdict; no window widening; no informal sequential
  fallback ("try the next FVG"); no threshold tuning after any result.

## 2. Normative Selection Specification (frozen verbatim)

### 2.1 Candidate set (condition set CS)

For ONE eligible episode/proof event, the candidate set = **all** M5
FVGs of the product's own detector (`smc.detection.fvg_detector.
detect_fvgs`, LOCKED_DECISIONS §3 semantics and validity, imported
read-only) that satisfy **every** condition:

1. **TF:** M5 only.
2. **Direction:** FVG direction matches the accepted thesis/proof
   direction (bullish FVG for LONG theses; bearish for SHORT).
3. **Validity:** the existing product FVG definition and validity
   semantics exactly; **no new maturity rule and no new constant**.
4. **Completed by proof:** the complete three-candle formation is
   known on or before the **true proof close** — i.e. the third
   candle index ≤ the true proof bar (all formation bars read at or
   before the proof bar; strictly no future bar informs any input).
5. **Window:** the formation lies wholly inside the existing fixed
   proof window `[proof − 48 M5 bars, proof]`. **The 48-bar interval
   is fixed; no wider alternate span exists.**

### 2.2 Eligibility filter (condition F)

From the candidate set, retain only FVGs whose **chosen near edge**
(accepted semantics: LONG = zone/top edge = low(c3); SHORT =
zone/bottom edge = high(c3)) is **strictly on the protected side of
the true proof-bar close** (LONG: near edge < close(proof); SHORT:
near edge > close(proof)).

No HTF proximal edge, no mid-zone value, no future bar, no inferred
geometry, and no fallback limit may enter this calculation.

### 2.3 Rank and selection (R1–R4; one selection; no iteration)

This is **candidate-set → filter → rank → one selection**, NOT an
iterative "try the next FVG" process. Rank all surviving FVGs:

- **R1 (primary):** smaller *completed-formation bar distance* to the
  true proof bar, where the completed-formation bar is the third
  candle (`start_index + 2`) and distance = `proof_bar − (start_index
  + 2)` (≥ 0), smaller better.
- **R2:** smaller absolute price distance `|near_edge − close(proof)|`.
- **R3:** more recent formation-end timestamp (the third candle's
  timestamp, larger is better; on the frozen M5 grid this is
  informationally consistent with R1 and acts as a semantic restatement).
- **R4 (final deterministic tie-break):** stable detector/source order
  — the position of the formation in `detect_fvgs`' chronological
  emission order, earlier position wins.

Select **exactly one** highest-ranked candidate per episode at proof:
the sole primary FVG candidate for that episode. Rationale (frozen):
R1 honors the design's intent that the proof's own completion leg
carries the entry; R2 keeps the selection near-market; R3/R4 make
any tie deterministic. If **no candidate survives** the filter →
`STRUCT_UNAVAILABLE` (see §3 for its now-precise meaning). **At most
one concurrent candidate, order, or hypothetical ticket per episode** —
one selection per episode; the episode's single selection is final for
the measure (the rest-lifetime retest semantics of design §4e, reused
unchanged, govern the would-be order evaluation of that single
selection).

### 2.4 Origin OB — report-only, exactly bounded

The origin OB remains a **clearly separated, report-only alternate**:

- Pairing (YES, permitted, without affecting the primary FVG verdict):
  the product's own **R1 §3.1 origin-OB pairing** — the candle
  immediately before the first candle of the **SELECTED** FVG, if that
  candle index exists within the same window, reported with the
  product's own validity semantics AS-IS.
- It is recorded as line items (counts, gaps, geometry descriptives)
  on rows WITH a selection; rows without a selection get **no OB
  rescue of any kind** — the OB is never evaluated as a fallback limit,
  never substitutes, never stacks, never blends into a hybrid entry
  rule, and never enters ANY kill/verdict computation. Its section in
  the report must be physically separated from the primary result.

## 3. Verdict-Input Taxonomy (the prior measure's conflation, now split)

Replace the prior generic `STRUCT_UNAVAILABLE`-as-data-gap path with
two separate terminal classes, **mutually exclusive, each row exactly
one**:

- **TRUE data/provenance gap** (`DATA_GAP_PROVENANCE`): required source
  data is genuinely missing/unreadable — missing/unparseable
  episode  identity or proof fields, a true proof bar outside the
  loaded grid range, missing/unreadable ATR at a required bar, or any
  missing component of the mandated provenance (timestamps/ATR/proof
  identity) that the frozen inputs should have carried. Fail-closed:
  never inferred, never substituted.
- **Representation coverage failure** (`NO_STRUCTURE_SELECTED`): all
  required data exists, but no FVG survives  §2.1–§2.3. This is the family's measured outcome for that row — **never**
  a data gap, never an INCONCLUSIVE input, never upgradeable. From this
  section on, the row label `STRUCT_UNAVAILABLE` MEANS
  `NO_STRUCTURE_SELECTED` and nothing else.

Named terminal sub-reasons (mutually exclusive, first-match in this
order) for reporting purposes:
  (a) *no direction-matched FVG in window* — the candidate set is
      empty;
  (b) candidates exist but *fail product validity* — none pass the
      detector's own validity semantics;
  (c) a valid candidate exists but *fails the protected-side rule* —
      the retained set (post-filter) is empty;
  (d) *genuine data/provenance gap* per the TRUE class above;
  (e) *any other* reason must be given a new explicit named constant
      in the measure BEFORE running (no unnamed buckets).

## 4. Final Pre-Registered Verdict Design (numeric gates, frozen BEFORE the script)

**Denominator rule (one, frozen):** `full P1` = all 268 population-1
rows of the frozen entry-representation artifacts, unchanged. Every
share/intensity gate below uses full-P1 denominators **except** the
median gate, which by the accepted design is computed over
**structured rows only** (rows with a selection); each reported figure
must state its denominator on the same line.

**Definitions frozen:**
- `STRUCT_FOUND / full P1` = rows with exactly one selected FVG under
  §2.3 (the OB never appears in this numerator).
- `true_data_gap_rate / full P1` = rows terminal-classified
  `DATA_GAP_PROVENANCE` **only** (`NO_STRUCTURE_SELECTED` never counts).
- Structured-row proof gap = gap_atr of the selected near edge vs the
  true proof-bar close (verified exec→grid frame).
- Near-market mass = full-P1 share with gap_atr ≤ 1.0 (inclusive;
  ≤ 2.0 reported as a band, never a gate). Rows without a selected
  structure have no gap_atr and contribute **0 to the numerator**
  (fail-closed); the denominator remains full P1.
- Retention = of the **3 control fills** (the frozen entry-rep census:
  poi-014146, poi-073511, poi-047805 — the same three every prior
  measure scored), count whose SELECTED-structure limit is touched
  within the route's own rest lifetime by a completed touch simulation
  without a DATA_GAP_PROVENANCE outcome.

**Frozen numeric criteria and first-fired order (frozen before any
script is written or run; first match in THIS order names the
verdict):**

| # | Condition (evaluated in order) | Verdict |
|---|---|---|
| 0 | **Control-gate evaluability precondition:** fewer than **all 3** control-fill rows are evaluable (each: selection exists, finite pivot gap, completed touch run with no `DATA_GAP_PROVENANCE`) | `INCONCLUSIVE` — reason `CONTROL_GATE_UNEVALUABLE` (explicitly recorded; a thin or unevaluable control can NEVER be silently described as passing, and no later gate may mask this branch) |
| 1 | `true_data_gap_rate / full P1 > 0.10` | `INCONCLUSIVE` — only genuine provenance gaps feed this |
| 2 | `STRUCT_FOUND / full P1 < 0.70` | `FAIL_COVERAGE` |
| 3 | full-P1 share with gap ≤ 1.0 ATR `< 0.50` | `FAIL_NO_NEAR_MASS` |
| 4 | median proof gap among structured rows `> 2.0 ATR` | `FAIL_STILL_FAR` |
| 5 | all 3 fills evaluable **and** retention `== 0` | `FAIL_BASELINE` |
| 6 | pre-registered paper-expiry gate: among defined-lifetime paths (rows with `NO_STRUCTURE_SELECTED` **or** `DATA_GAP_PROVENANCE` excluded), `n ≥ 20` **and** paper `EXPIRED_NO_FILL` rate `> 0.85` | `FAIL_UNFILLABLE` |
| — | every gate (2–5, with 0 and 1 clear) passes | `PASS_FEASIBILITY` |

`PASS_FEASIBILITY` means **Architect discussion only**; it never
authorizes implementation, wiring, or any product change. The frozen
thresholds (0.10, 0.70, 0.50, 2.0, n ≥ 20, 0.85) are design constants
of THIS amendment — frozen now; no post-hoc movement under any outcome.

## 5. Frozen Non-Changes and the Recorded Impurity

The final measure retains unchanged: HTF context is context ONLY (the
HTF proximal edge is not an input to the LTF-return limit); FR-2
distal stop reference; engine §5 lifecycle/invalidation semantics;
the existing product rest lifetime; FR-3, R7, session rules, §28 risk
policy; existing trigger/pillar/POI/routing rules; no market orders.

**Recorded impurity (explicit):** the selected M5 FVG limit may
coexist with existing FR-2/HTF-oriented stop geometry — i.e., the
entry may sit away from the exact range that the current FR-2
structural stop was built around. THIS MEASURE ASSESSES ENTRY
REPRESENTATION COVERAGE AND NEARNESS ONLY. It neither names nor
authorizes a stop redesign; any stop-side consequence is a later
Architect decision after a PASS, never part of this measure or its
verdict.

## 6. Required Reporting Design (the final measure MUST report, separately; full-P1 denominators where applicable — each figure states its denominator)

1. Population reconciliation and true-frame verification (offset
   asserted, per-row grid index provenance).
2. **Candidate-set count per episode** (the §2.1 set size), plus the
   surviving-after-filter count — reported as distributions.
3. Terminal reason for **every** unselected row, from the frozen
   taxonomy of §3, mutually exclusive and named (a)–(e); no unnamed
   bucket may appear.
4. Selected-candidate **rank/tie-break provenance**: which rank keys
   decided the selection (R1/R2/R3/R4 usage histogram), making the
   selection auditable without re-running.
5. Structured-row proof-gap distribution (median/p25/p75 + per-row
   columns), denominator stated.
6. Full-P1 near-market mass (≤ 1.0 ATR gate figure; ≤ 2.0 band figure),
   denominator stated.
7. **Coverage rate** (STRUCT_FOUND / full P1), denominator stated.
8. HTF-context-zone intersection **as a label only** (never a filter,
   never a price input).
9. Separately reported origin-OB alternate (§2.4), physically apart
   from the primary section.
10. Control-fill evaluability and retention (the §4 gate-0/5 inputs),
    each fill's evaluation named.
11. Exact first-fired kill evaluation log (each gate's evaluation and
    the fired rule).
12. Determinism (dual-run byte-identical artifacts) and
    **no-lookahead checks** (every structural/rank/gap input
    demonstrably uses only bars ≤ the proof bar; asserted, not assumed).

## 7. Governance and Finality — Prohibited Binding

This amendment explicitly PROHIBITS, for the final measure and any use
of its artifacts:

1. Widening the 48-bar window (no wider alternate span exists).
2. Informal sequential FVG fallback ("try the next FVG" iteration) —
   the rule is strictly candidate-set → filter → rank → one.
3. Threshold tuning after results (all constants frozen above).
4. Using an HTF-edge limit under a new name (no HTF-bound input to the
   limit; label-only zone intersection).
5. Multiple candidates/orders/hypothetical tickets per episode.
6. Hybrid FVG/OB limit construction (the OB is report-only, §2.4).
7. Changing stop logic during this measure (impurity recorded, §5).
8. Product/live/paper wiring from pass OR fail; any implement prompt
   requires separate Architect rulings after a PASS, per design §8
   open questions. `PASS_FEASIBILITY` is a discussion unlock only.

**Finality:** a FAILURE of the subsequent final measure (any
`FAIL_*` verdict) retires active **Mode A LTF-return representation**
work only — it does NOT declare Mode A, SMC detection, POI/sweep/proof
evidence, or the broader project invalid; those lines of evidence
remain standing.

## 8. Self-Audit

This amendment is **one bounded final selection-breadth experiment,
not a new strategy family**: one selection rule (§2), one verdict
lattice (§4), one frozen denominator scheme (§6 reporting rule 6 +
§4), no new geometry, no new TF, no new constant, no second chance for
retired families, and a single exit (the final measure) with a single
finality statement (§7). The verdict design splits coverage from data
readability so that neither class can masquerade as the other; the
control-gate precondition makes thin evaluability an explicit
INCONCLUSIVE, never a quiet pass; and every gate's denominator is
frozen and must be printed on the same line as its figure.

**RETURN BLOCK**

```
LTF_RETURN_AMENDMENT_STATUS: PASS
AMENDMENT_PATH: 00_LOCKED/MODE_A_LTF_RETURN_SELECTION_BREADTH_AMENDMENT.md
PRIMARY_RULE_NAME: candidate-set → filter → rank(R1 distance/R2 proximity/R3 recency/R4 source order) → one selection
MEASURE_GATES_SUMMARY: control-unevaluable(<3) -> INCONCLUSIVE; true-gap>0.10 -> INCONCLUSIVE; coverage<0.70 -> FAIL_COVERAGE; near-share<0.50 -> FAIL_NO_NEAR_MASS; median(structured)>2.0 -> FAIL_STILL_FAR; 0-retained(3 evaluable) -> FAIL_BASELINE; expired>0.85@n>=20 -> FAIL_UNFILLABLE; else PASS_FEASIBILITY (discussion unlock only)
OPEN_QUESTIONS_N: 0 (all prior design §8 questions frozen unchanged)
HANDOFF_UPDATED: YES
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: Architect acceptance -> ONE final offline feasibility measure per this amendment
```
