# ENTRY-REPRESENTATION DESIGN — ALTERNATIVE LIMIT-CONSTRUCTION RULES

> **DESIGN / POLICY — NOT EDGE / NOT AUTHORIZATION TO SHIP.**
> A dated design lock proposing exactly three alternative limit-
> construction rules for Mode A reactive entry flow, each offline-
> measurable with pre-registered kill criteria BEFORE any product
> implement. Nothing here changes a product limit, gate, constant, or
> trigger; nothing claims expectancy, win-rate or edge; nothing re-
> opens the closed reactive-admission measure (FAIL_TIGHT stays
> closed). Acceptance is the Architect's; until then this is a policy
> paper only.

**Date:** 2026-10-14 · **Authority:** Lead Architect, after
`06_RESEARCH/ENTRY_REPRESENTATION_NOTE.md` (PASS;
`VERDICT_FAMILY: BOTH`, mechanical dominant) and the tightened
directive 2026-10-14. Composes with the owner plan
`00_LOCKED/OWNER_PLAN_MULTI_TF_TRANSLATION_2026-10-13.md` (binding
ordered work; its §6 "representation gap dominates → escalate to
admission/translation design" additional kill rule) and the closed
measure notes. **LOGIC_CHANGED: NO** — docs only: no `04_SRC/smc`
edit, `locked_constants.py` untouched, no live/limit change, no M15,
no ML, no Mode B.

**DESIGN_LOCKED pending Architect acceptance.** Product limit change
NOT started. NEXT after acceptance = the offline representation
measure of the chosen primary rule (section 5), as its own dated task.

---

## 1. Status / Authority / Non-Goals

- **Status:** DESIGN_LOCKED pending Architect acceptance; measure
  before any implement prompt; product limit change NOT started.
- **Non-goals (binding):**
  - No mid-zone fishing: no rule floats a limit freely inside or
    around the zone box to fish for fills; every rule is a fixed
    transformation of measured structure (section 4 definitions are
    exact, parameter-free or one frozen constant).
  - No reactive-admission reopen: R1–R6 and their FAIL_TIGHT verdict
    are closed; this design does not soften, re-time, or re-threshold
    any R*.
  - No Mode B, no ML, no "just use market orders" (a limit resting at
    the market touch is a market order in disguise and is banned).
  - No proactive pre-sweep limits as a V1 default: all rules react to
    a completed LTF proof on an existing HTF thesis; nothing places
    before the proof exists.
  - No expectancy claim anywhere: the rules change *where* a resting
    limit sits; they are not asserted to be more profitable.

## 2. Problem Restatement (evidence-cited, short)

- **Mechanical (dominant):** the measured entry book puts the limit on
  the FR-3.1 direction-proximal zone edge — the shelf the *impulse
  leg* built. After displacement, the market closes far above/below
  that edge: P1 median gap **8.27 ATR (21.76 units)** at the true
  proof-bar close; only **4.1%** of rows within 1.0 ATR;
  **86.6%** (232/268) are the exact `on_edge`-and-far shape
  (ENTRY_REPRESENTATION_NOTE §2.1–§2.2).
- **Lifecycle (secondary, compounder):** 64/268 theses arm only after
  their first coincident proof; waiting to arm does not close the gap —
  it deepens it (median gap at the arm bar **13.8 ATR** vs 8.27 at
  proof). The near-miss census independently found the market never
  touched 6 of 7 untaken route limits even within 100 bars.
- **The fill tail is real but thin:** the 3 control fills sit at
  gap_atr 1.28 / 1.68 / 2.25 — the geometry tail; routed (market-
  relative) entries run median 3.24 ATR vs 8.61 for the zone-edge
  fallback. Product fills occur only where the representation
  accidentally lands near the market.
- Zone **width does not** separate the strata (15.9 vs 17.7 ATR
  medians) — "wide zones" is not the story; **where the limit is
  anchored** is.

## 3. Definitions

- **Signal geometry vs placement price:** the trigger defines a signal
  (direction, stop reference, structural validity). The *limit* —
  where the resting order sits — is a separate construction today made
  by FR-3.1 `zone_anchored_entry` (proximal edge; on-zone references
  pass through bit-exactly). These rules replace **only** the limit
  construction on routed candidates; the trigger, its letter, the FR-2
  SL/TP derivation skeleton, and the FR-3 **gate** (entry belongs to
  the routed POI zone ± the frozen §13 tolerance) remain separate.
  Where a rule's limit deliberately leaves the zone box, the rule must
  carry its own explicit replacement gate (stated per rule); the
  FR-3 gate stays for every candidate a rule does not apply to.
- **Reference market price for "near":** PRIMARY = **the close of the
  true proof bar** (P1: the artifact's proof bar in the verified exec→
  grid frame; P0: the route's first presentation — the same frozen
  convention and verified frame as ENTRY_REPRESENTATION_NOTE, whose
  disclosure §3 and frame ruling this design abides by). Justification:
  it is the moment the theorem is asserted ("proof completed"), it is
  measurable on the whole frozen population (gap completeness 1.000),
  and it is where the closed measure's own R4 asymmetry bit
  (`limit_far_from_market` 138/268). Presentation-time "near" is a
  **reporting band only** in the measure (§5) until the frame residual
  (note §3, H4) has a dated re-run decision; it must not gate anything
  in V1 of this design's measure.
- **ATR convention:** SMA(TR,14) ending at the referenced bar
  (measure convention, disclosed; measure constants, never locked
  values, until a dated constant ruling follows a measure PASS).
- **Compatibility summary:** FR-3 gate — stays, except inside the
  single rule that explicitly replaces limit construction (its own
  gate stated in §4); R7 (`skip_place_far_from_zone`) — unchanged, and
  expected to fire *less* under closer-limit rules because the same
  distance check is satisfied by construction; R9
  (`PlaceIntent`/`IntentBook`) — unchanged in machinery; RL-3 (§4.3)
  is a *present-condition refinement* layered on the existing R9
  arming, not a redesign of it; §11 one-shot, §28 risk, pillars,
  matrix, trigger letters — all unchanged (§7).

## 4. Candidate Rules (exactly three)

For each rule: formal definition, difference from FR-3.1, failure mode
addressed, and explicit non-claims. All rules act on a **routed or
accepted candidate** for an existing thesis (armed POI + completed LTF
proof in the candidate's direction); none invents a thesis.

### 4.1 RL-1 `pullback_shelf` — PRIMARY RECOMMENDATION (mechanical)

- **Definition (exact):** let `C = close(true proof bar)`, `A = ATR(proof bar)`.
  - LONG:  `limit = C − k·A`
  - SHORT: `limit = C + k·A`
  with the single frozen measure constant **k = 1.0** (pre-registered
  here, before any run; not tunable post-run).
- **Guard rails (its own gate, replacing FR-3.1 anchoring only for
  this rule's candidates):**
  1. The shelf must sit on the protected side: LONG `limit < close of
     any placement-time bar`; SHORT `limit > close` (it must be a
     resting limit, never an immediate fill — the anti-market-order
     non-goal is enforced structurally).
  2. The shelf must not tunnel through the thesis: LONG `limit ≥ zone
     distal edge`, SHORT `limit ≤ zone distal edge` (entering through
     the whole zone is invalidation territory, not an entry).
  3. The shelf must not sit beyond the proof bar's adverse extreme:
     LONG `limit ≥ proof-bar low`, SHORT `limit ≤ proof-bar high`.
     If any guard fails → the candidate keeps the FR-3.1 proximal-edge
     limit (fail-closed fallback; the rule never widens what is
     tradable, it only relocates the limit inside an already-valid
     thesis).
- **Difference from FR-3.1:** reference moves from the *stale zone
  edge* to the *market at the proof event*. By construction
  `|limit − C| = k·A` at proof — the measured failure mode
  (`limit_far_from_market`, 86.6% > 1 ATR) cannot occur at the
  reference bar.
- **Failure mode addressed:** MECHANICAL. (It does not and cannot
  address the 64/268 armed-after-proof lifecycle mass; RL-3 does.)
- **Explicit non-claims:** no expectancy claim; closer limits plausibly
  fill *more often by adverse selection too* (an early shelf fill means
  the retracement depth assumption was wrong) — this is a stated risk
  to be measured as paper EXPIRED/TP/SL mixes, not argued away. The
  stop reference stays the FR-2 structural/OB rule; with the limit off
  the zone edge the entry-to-stop distance and therefore R multiples
  change per row — that is *reported* by the measure, never claimed.

### 4.2 RL-2 `retrace_mid` — parameter-free alternative (mechanical)

- **Definition (exact):** let `E = FR-3.1 proximal edge` (unchanged
  scan semantics), `X = extreme of the displacement leg at the true
  proof bar` (LONG: max of bar-highs over [zone-edge-formation bar,
  proof bar]; SHORT: min of bar-lows over the same span; the leg span
  is the zone's own referenced formation window — measured, not
  invented).
  - LONG:  `limit = midpoint(E, max(E, X))`
  - SHORT: `limit = midpoint(E, min(E, X))`
- **Difference from FR-3.1:** the limit sits halfway *back toward the
  market* along the very leg the proof completed, instead of at the
  leg's foot on the stale edge. Parameter-free (the 50% level is the
  fixed transform, not a fitted threshold; no grid exists).
- **Not mid-zone fishing (explicit):** the value is a deterministic
  function of the measured leg per row — it never floats freely inside
  the zone box, never adapts to outcomes, and is fully computable
  offline before any outcome is known.
- **Failure mode addressed:** MECHANICAL (fetches the limit toward the
  market proportionally to how far the displacement actually ran).
- **Explicit non-claims:** same as RL-1; additionally no claim that 50%
  is privileged — it is a fixed, pre-registered transform whose NUMBERS
  are measured, not a tuned parameter (changing it post-run is banned).

### 4.3 RL-3 `edge_plus_wait` — placement-only complement (lifecycle)
    (the single permitted "keep proximal edge + defer placement" rule)

- **Definition (exact):** the limit is **unchanged** — FR-3.1
  proximal edge verbatim. The only change is the presentation
  condition for an already-accepted candidate: in place of the
  immediate placement, the candidate is presented (and only then
  placed) on the first bar within the product's own R8 rest lifetime
  (`rest_bars_for`, unchanged) where BOTH hold:
  1. the design's NAMED rule `market_reentered_zone` evaluates true
     (band path on close OR limit touch), and
  2. `|limit − close(bar)| ≤ 1.0 × ATR(bar)` (the same proximity guard
     constant the closed measure used — reused, not re-tuned).
  If no such bar occurs before the lifetime ends → the candidate
  expires unplaced (R9 machinery: `EXPIRED`, unchanged semantics, R9
  clock/dedupe/one-shot all retained).
- **Difference from FR-3.1:** none in price construction — this is
  explicitly **not a new limit formula**. It separates *signal
  geometry* from *placement price timing* and confirms a valid signal
  is only presented while the market is near it.
- **Failure mode addressed:** LIFECYCLE/placement (the 64/268
  armed-after-proof rows and the preserve-the-path property; also the
  near-miss finding that far limits were never touched — this rule
  stops *presenting* what the market is not near).
- **Explicit non-claims:** no claim it revives the closed reactive-
  admission path — the admission question (which theses get accepted
  at all) stays closed; this rule only governs the presentation
  moment of already-valid candidates. No expectancy claim; presenting
  later can lose the early fill (the near-miss `poi-022254` lifetime
  class is exactly this trade-off, n=1 there).

## 5. Pre-Registered Offline Measure (before any implement)

Frozen now, run as its own dated task after acceptance, on the **same
frozen 6m populations** (P0 = 10 routes; P1 = 268 armed+coincident
rows; P2 report-only = the 138 R4-failure rows) and the **same
verified exec→grid frame** as ENTRY_REPRESENTATION_NOTE. Read-only
counterfactual limit recomputation only — no product wiring, no scan
re-run, no detection change.

- **Per rule (each evaluated separately and reported separately; no
  blending):** recompute the rule's would-be limit per row (fail-
  closed; a guard-failing row falls back to the FR-3.1 edge and is
  *counted* as a fallback, never dropped silently), then compute:
  1. median / p25 / p75 `gap_atr` at the true proof bar (primary),
     and at the arm bar (secondary);
  2. share of P1 rows with `gap_atr ≤ 1.0` and with `≤ 2.0`
     (**reporting bands only** — bands never gate a rule);
  3. **fill overlap:** of the 3 control fills, how many re-check as
     fillable within the route's own rest lifetime under the rule's
     limit (frozen near-miss touch semantics);
  4. paper `EXPIRED_NO_FILL` rate over the product rest lifetime
     under the rule's limit (frozen near-miss helpers; zone-edge rows
     as in the closed measure's secondary pass);
  5. fallback count (guard failures) and, for RL-3, presentation-time
     proximity stats within the R8 lifetime (descriptive only).
- **Kill criteria (frozen first-fired order, before the run; the
  numbers below are the frozen thresholds, not tunings):**
  - `median gap_atr(P1) ≥ 6.0` → **FAIL_STILL_FAR**
  - `share(gap_atr ≤ 1.0) < 0.10` → **FAIL_NO_NEAR_MASS**
  - `0` fill overlap with the 3 control fills (when evaluable) →
    **FAIL_BASELINE**
  - `paper EXPIRED_NO_FILL > 0.90` when evaluable n ≥ 20 →
    **FAIL_UNFILLABLE**
  - P1 DATA_GAP rate > 0.20 → **INCONCLUSIVE**
  - otherwise → **PASS_MEASURE** (unlocks an Architect implement
    discussion only; still no result-authoritative wiring).
- **Method notes:** the reference bar for RL-1/RL-2 is the true proof
  bar (verified frame); the measure inherits the note's frame ruling —
  the closed measure's presentation columns stay unused; DATA_GAP rows
  are counted, never filled; no post-hoc constant movement (k = 1.0
  and the 50% transform are frozen in this note now).

## 6. Interaction with Admission / Seek

- This design does **not** revive the FAIL_TIGHT reactive-admission
  path; that study's verdict stands closed and its thresholds are not
  referenced as decision inputs here.
- **Stance (recommended): representation first, then admission.** The
  measured admission failure was dominated by R4's proximity guard
  refusing zone-edge limits the market was far from; a reworked
  *representation* changes the input that guard evaluates. A future
  admission redesign attempt (its own dated design, after this
  measure) should therefore be sequenced AFTER a representation
  measure PASS, not in parallel and not before.
- RL-3 is the only rule that touches presentation timing; it stays
  inside the existing accept→arm→present pipeline (R9) and does not
  introduce a second admission layer.

## 7. Explicit Non-Changes

- Pillars, pillar matrix, §28 risk, trigger letter definitions: unchanged.
- FR-3 zone-membership gate: unchanged, except inside RL-1's own
  stated guard rails for that rule's candidates only (gate remains
  the last line of defense for every other candidate).
- FR-2 SL/TP derivation skeleton: unchanged (structural stop
  reference retained; TP coupling is an open question, §8).
- R7, R8, R9 machinery: unchanged (R9 hosts RL-3's present-condition
  only; no new lifecycle states; the existing `EXPIRED` path suffices).
- `locked_constants.py`: untouched; ATR convention and any constant
  promoted to product permanence would require a separate dated
  constant ruling after a measure PASS.

## 8. Open Questions for the Architect (max 5)

1. **Primary rule** for the first offline measure: this design
   recommends **RL-1 `pullback_shelf`** (it confronts the measured gap
   most directly by construction), with RL-2 as the parameter-free
   alternative and RL-3 as the placement complement — the choice is
   the Architect's to ratify or override.
2. **Structural TP coupling:** does TP remain coupled to the limit
   choice today (zone/wick-anchored TP off the *entry*) or drift with
   RL-1/RL-2 limits? (Measured RR shifts per row must be reported
   either way before any coupling ruling.)
3. **Stop reference when the limit leaves the zone edge:** OB distal
   (FR-2 as-is) vs zone distal — which one governs when RL-1/RL-2 move
   the limit toward the market (section 3 states the skeleton stays;
   the *reference* selection is the open question).
4. Rule order in a product candidate set: if more than one rule
   eventually passes, is RL-3 layered onto RL-1/RL-2 (combined) or are
   they exclusive alternatives?
5. The presentation-time metric (and any R4-adjacent geometry) in the
   measure needs the ENTRY_REPRESENTATION_NOTE H4 frame residual
   resolved by a dated re-run decision of the closed measure — ratify
   sequencing now or defer to its own task?

## 9. Self-Check & Governance Audit

- Rules are crisp (each an exact formula + guard rails, one frozen
  constant, one parameter-free, one formula-free), measurable offline
  on frozen populations, with frozen kill criteria registered BEFORE
  the run.
- Bans held: no mid-zone fishing (every limit is a fixed transform of
  measured structure); no admission reopen; no market-order shape; no
  Mode B / ML; no product code in this task; no threshold grid after
  this note; no expectancy claim; banner carried above.
- Governance: SESSION_HANDOFF / POST_V1_ACTIVE_TODO / CHANGELOG
  updated this date; product limit change NOT started; NEXT after
  Architect acceptance = the offline representation measure (section
  5) as its own dated read-only task.

**RETURN BLOCK**

```
ENTRY_REP_DESIGN_STATUS: PASS
DESIGN_PATH: 00_LOCKED/ENTRY_REPRESENTATION_DESIGN.md
CANDIDATE_RULES_N: 3
PRIMARY_RULE_NAME: RL-1 pullback_shelf
MEASURE_KILL_SUMMARY: median gap_atr(P1) >= 6 -> FAIL_STILL_FAR; share <= 1.0 ATR < 10% -> FAIL_NO_NEAR_MASS; 0 fill overlap (evaluable) -> FAIL_BASELINE; paper EXPIRED > 90% at n >= 20 -> FAIL_UNFILLABLE; DATA_GAP > 20% -> INCONCLUSIVE
OPEN_QUESTIONS_N: 5
HANDOFF_UPDATED: YES
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: Architect acceptance -> offline representation measure
```
