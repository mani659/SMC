# MODE A — LTF RETURN-STRUCTURE ENTRY DESIGN LOCK

> **DESIGN / POLICY — NOT EDGE / NOT AUTHORIZATION TO SHIP.**
> ONE dated design lock for ONE LTF return-structure entry
> representation family for Mode A, per the owner ruling below. The
> proximal-edge family (FR-3.1 HTF zone-edge limits, RL-1
> `pullback_shelf`, RL-2 `retrace_mid`, RL-3 `edge_plus_wait`, the
> prior reactive-admission R1–R6 path) is RETIRED from active
> experimentation by that ruling and appears here only as the control
> baseline for the pre-registered measure. Nothing here changes a
> product limit, trigger, gate, or constant; nothing claims
> expectancy, win-rate or edge; no parameter of any retired family is
> retuned. Acceptance is the Architect's; until then this is a policy
> paper only.

**Date:** 2026-10-14 · **Authority:** Lead Architect; **owner ruling
2026-10-14 (binding, substance reproduced in §2 — not reopened here)**
after `06_RESEARCH/ENTRY_REPRESENTATION_MEASURE_NOTE.md`
(all three candidates FAIL as frozen). Composes with the owner plan
`00_LOCKED/OWNER_PLAN_MULTI_TF_TRANSLATION_2026-10-13.md`. **Downstream
gate:** Architect acceptance → **offline feasibility measure only**
(kill criteria frozen first; PASS_MEASURE is a discussion unlock,
never a ship decision) — before any code. Product wiring NOT started.
**LOGIC_CHANGED: NO** — docs only: no `04_SRC/smc` edit,
`locked_constants.py` untouched, no live wiring, no M15 product
decision TF, no ML, no Mode B.

---

## 1. Status / Authority / Non-Goals

- **Status:** DESIGN_LOCKED pending Architect acceptance; ONE family
  specified (§4); next gate = the offline feasibility measure (§6) on
  its own dated task. Product limit change NOT started.
- **Non-goals (binding):**
  - No HTF-edge limits: the HTF (H4/H1) proximal edge sets nothing in
    this family; it is context only.
  - No mid-zone fishing: the entry limit is the near edge of a
    measured LTF structure, never a free interior price, never
    adapted to outcomes.
  - No market orders as default (and none at all in the measure): a
    limit that does not sit strictly on the protected side of the
    proof-close market is a DATA_GAP candidate, not a market order.
  - No Mode B, no ML, no gate loosening for sample size.
  - No proactive pre-proof limits: nothing exists before the LTF
    proof event.
  - No expectancy claims anywhere.
  - No revive of the retired families: no parameter retune of the
    proximal-edge family (FR-3.1 edge, RL-1/2/3, R1–R6); they are
    measured ONLY as the frozen control in §6.

## 2. Intended Mode A Story (owner ruling, short)

**HTF thesis + location context → LTF proof (timing) → entry from LTF
return structure.**

The H4/H1 POI supplies *which* theses exist and *where* the operator
cares (directional context). It does NOT supply the entry price. The
M5 proof event (Stage-3 directional completion against the swept side
of the HTF thesis) supplies *when* the story may act. The entry itself
is constructed from the LTF structure the proof leg leaves behind —
the displacement FVG (and, secondarily, the origin OB) — which by
construction sits near the post-proof market. This is exactly what
the measured evidence supports: proof mass is real (585/1,093
coincident episodes; first-proof mix F 477 / A 56 / B 46 / E 5 / C 1),
while HTF-edge presentation is the binding failure (P1 median gap
8.27 ATR at proof; 86.6% zone-edge-and-far; all three edge-family
candidates FAIL as frozen).

## 3. Definitions

- **HTF context vs LTF entry structure:** the HTF zone bounds, pillar
  state, and §5 validity classify and timestamp theses; they do not
  and may not set, shift, or bias the entry price. The LTF (M5)
  structure IS the entry geometry; only its own edges may appear in
  the limit formula.
- **Proof event:** the episode's FIRST coincidence proof from the
  frozen artifacts (`episode_coincidence.csv`: `first_coinc_bar`,
  `first_coinc_trigger`, within H = 48 M5 bars of the thesis
  reference — the coincidence study's own de-duplicated choice,
  reused verbatim, never re-detected). Directionally eligible =
  the recorded trigger letter's completion direction agrees with the
  episode's HTF thesis direction (parsed from the census `direction`
  column); all letters A–F are eligible and *reported* (no letter
  fishing). Justification: the coincidence artifacts are the only
  frozen proof ledger; re-deriving proofs would reopen detection.
- **Return structure (the geometric object):** an M5 displacement
  FVG — a 3-candle gap formed on the leg that produced the proof —
  or, secondarily, the origin OB of that leg's BOS (definitions in
  §4b). Both are M5 objects; no other timeframe's structure builds
  the limit. M5 is executed and detected already (the product's own
  trigger machinery derives exactly these shapes), so the family is
  measurable with read-only imports of product detectors.

## 4. Normative Specification — the family (one primary + one alternate)

### (a) Proof event + directional eligibility
Proof = the episode's first-coincidence row (frozen field set above).
Eligible iff: direction parses (LONG/SHORT agreement with the HTF
thesis), `first_coinc_bar` resolves to a true grid bar in the verified
exec→grid frame, and the stage-3 completion exists. Otherwise the
episode is a DATA_GAP candidate (fail-closed).

### (b) The LTF structure used for entry
- **PRIMARY (one): the NEAREST M5 displacement FVG of the proof leg.**
  Concretely: a 3-candle FVG (candle1.high < candle3.low for a
  bullish leg; candle1.low > candle3.high for a bearish leg) with all
  three bars inside the frozen lookback window
  **[proof − 48, proof]** (a deliberate REUSE of the frozen
  H_PROOF = 48 coincidence horizon — no new constant), created by the
  leg in the thesis direction, chosen as the formation whose third
  bar is latest (nearest the proof). Directional side: LONG theses ->
  bullish-leg FVG below the proof-close market; SHORT -> bearish-leg
  FVG above it.
- **ALTERNATE (one, clearly secondary and measurable): the origin OB
  of that leg's BOS** — the product's own Trigger-F origin-OB shape
  (read-only import), same 48-bar window, same directional side.
- **Selection rule (fail-closed):** if the primary FVG cannot yield a
  resting limit under (c)'s strict-side rule, the alternate OB is
  evaluated; if neither qualifies -> the candidate is
  `STRUCT_UNAVAILABLE` (a counted DATA_GAP-stratum row; the family
  does NOT widen its geometry to save rows; no market-order fallback).

### (c) Limit construction formula (one line)
**limit = the near edge of the chosen M5 return structure, iff it sits
strictly on the protected side of the true proof-bar close**
(LONG: `limit = FVG top edge` and `limit < close(proof)`; SHORT:
`limit = FVG bottom edge` and `limit > close(proof)`; OB rows swap in
the OB's near edge by the same strict rule).

### (d) Stop reference + invalidation
- Stop reference = the structure's far edge (LONG: FVG's lower
  boundary / OB low; SHORT: FVG's upper boundary / OB high) — the FR-2
  structural-SL path unchanged (buffered per the existing
  `structural_sl` rule; no new constant).
- Invalidation: a full adverse close beyond the structure's far edge
  with no prior touch (the engine's existing §5 semantics) voids the
  candidate pre-fill; post-fill the existing §5/§28 machinery applies
  unchanged.
- Explicit coupling note: TP remains the product's existing structural
  construction (§8 open question on coupling) — the measure never
  invents a TP for P1 rows.

### (e) Return/retest window + expiry
- Retest window = `[proof, proof + rest_bars_for(detection_tf,
  is_m8, M5)]` — the product's own R8/rest lifetime, reused (named
  constant; none invented). The proof bar itself is included (the FVG
  is created by the leg the proof just completed; a market already
  inside the structure at proof does not happen under the strict-side
  rule, so inclusion is safe).
- Expiry: no touch inside the window -> the would-be candidate expires
  (paper `EXPIRED_NO_FILL` in the measure; no presentation, no order).
- New measure constants introduced: **none** (the only span is the
  reused H_PROOF = 48; the only lifetime is the reused product rest
  rule). Flag recorded here as demanded by the section contract.

### (f) Episode identity + one-shot interaction
- Identity: unchanged episode identity ((direction, detection_tf,
  m8_kind_class, zone bounds under overlap equivalence) — the
  shipped `ZoneDedup` rule). This family adds **attributes** to the
  episode record (proof ref, chosen structure geometry, structure
  kind FVG|OB), never a second identity.
- One-shot: ONE candidate per episode at its first proof (the
  artifacts' own de-duplication); the one-shot is consumed by the
  FIRST placement of the family's candidate; R9-style deferral is
  **not** part of this family (the retired `edge_plus_wait` concept
  informed the expiry choice only — not copied, its parameters were
  not retuned).
- The episode store stays observability-only (V1): the measure derives
  everything offline; no decision read is proposed.

### (g) Required data / provenance
All of the following must exist or the candidate is DATA_GAP
(never inferred): episode proof fields (frozen artifacts), direction,
true-frame proof bar + close/ATR (verified exec→grid frame, same
helper convention), M5 grid bars sufficient for the 48-bar lookback,
the chosen structure's four bounding prices (FVG: candle1.high,
candle3.low — or reverse; OB: its two edges), rest lifetime
(`rest_bars_for`). The measure derives the geometry with READ-ONLY
imports of the product's own M5 trigger/FVG detectors on the frozen
series (same discipline as all prior research scripts); it never
forks detection logic.

## 5. Compatibility

- **FR-3 zone-membership gate / R7 / session / risk §28 / pillars /
  triggers / one-shot: unchanged** — and deliberately NOT quietly
  carved: today's FR-3 gate requires a routed entry to belong to the
  routed HTF POI zone, and R7 skips far-from-zone placements. An LTF
  return-structure limit routinely sits outside the HTF box, so IF
  this family is ever wired, the zone-membership gate carve-out and
  R7's distance-check treatment of LTF-near limits must be ruled by
  the Architect (§8 Q1) — this design does NOT pre-carve them and
  does not implement anything. Session/news and §28 risk are untouched
  in feasibility and in any hypothetical implementation.
- **Relationship to the retired proximal-edge control:** the family is
  defined BY contrast — the HTF edge may not appear in the limit
  formula; the retired family's frozen numbers appear only as the
  §6 comparison baseline (CONTROL_proximal_edge column), never as a
  tuning reference. No parameter of the retired family is retuned.

## 6. Pre-Registered Offline Feasibility Measure + Kill Criteria

Feasibility first (mass, presentation, readability) — NOT expectancy.
Dated task after Architect acceptance; frozen NOW, before any run;
 populations reuse the frozen artifacts (P1 = the 268 armed+coincident
rows of the entry-representation study, same verified frame; P0 =
the 10 product routes as benchmark rows only; P2 report-only stratum
as before). One row per episode; one candidate per first proof;
fail-closed everywhere.

- **Metrics (per design section 6 contract):**
  1. Candidate mass: `struct_found` = P1 rows where the strict-side
     rule yields a limit (FVG primary or OB alternate);
  2. Near-market presentation: gap_atr of the structure limit vs the
     true proof-bar close (primary) and arm-bar close (secondary) —
     median / p25 / p75; share ≤ 1.0 / ≤ 2.0 (bands report, ≤ 2.0
     never gates);
  3. Structure strata: FVG-first vs OB-fallback counts and the letter
     mix of proven candidates (descriptive only);
  4. DATA_GAP rate on P1;
  5. Overlap with the 3 control fills: count of fill rows whose
     structure limit still touches within the route's own rest
     lifetime (evaluable = completed touch simulation without
     DATA_GAP);
  6. Optional, disclosed paper EXPIRED rate over the rest lifetime
     (touch-only for P1 — SL/TP never invented); the CONTROL
     proximal-edge column is scored identically for comparison.
- **Kill criteria (frozen first-fired order, tuned here and nowhere
  else):**
  1. P1 DATA_GAP rate > 0.30 -> **INCONCLUSIVE** (mass unreadable).
  2. median gap_atr(P1) > 2.0 -> **FAIL_STILL_FAR** (the family exists
     to fix presentation; the LTF structure must be near to count).
  3. share(gap_atr ≤ 1.0) < 0.50 -> **FAIL_NO_NEAR_MASS**.
  4. 0 of 3 control fills retained (when evaluable) ->
     **FAIL_BASELINE** (the family must not destroy the baseline
     geometry).
  5. paper EXPIRED rate > 0.85 among defined-lifetime rows at n ≥ 20
     -> **FAIL_UNFILLABLE**.
  Otherwise -> **PASS_FEASIBILITY** (discussion unlock ONLY; no ship;
  any implement needs the Architect's gate/routing rulings of §8
  answered first).

## 7. Open Questions for the Architect (max 5)

1. **FR-3 gate / R7 carve-out scope** if ever wired: which explicit
   ruling replaces the zone-membership gate for this family, given the
   HTF box is context (§5 states today's gates stand untouched)?
2. **Structure precedence:** is the FVG-first / OB-alternate
   precedence ratified, or should OB lead (accepting that F-proofs by
   construction sit touching their OB at first-touch semantics)?
3. **FVG maturity rule:** is a 3-candle displacement FVG accepted as
   "formed" at the proof bar (no post-proof mitigation test), or must
   the measure additionally verify zero touches inside the formation
   leg itself?
4. **TF authority:** M5-only return structures confirmed (no M15 and
   no M1) for Mode A?
5. **Rest-lifetime coupling:** the retest window reuses the product's
   R8/rest rule — ratified, or should the window be an independent
   measure constant with its own freeze?

## 8. Self-Check & Governance Audit

- ONE family, one primary structure (displacement FVG), one clearly
  secondary alternate (origin OB), exact formulas, explicit
  fail-closed selection, no invented constants (48-window and rest
  lifetime are named reuses), frozen numeric kills BEFORE any run,
  retired family used only as control.
- Bans held: no production entry code in this task; no threshold
  fishing (kills are frozen; bands never gate); no mid-zone fishing
  (true structural edges only); no market orders; no Mode B / ML; no
  expectancy language; banner carried above.
- Governance: SESSION_HANDOFF / POST_V1_ACTIVE_TODO / CHANGELOG
  updated this date (owner ruling recorded; proximal-edge family
  retired from active experiment; product wiring NOT started; NEXT =
  Architect acceptance -> offline feasibility measure).

**RETURN BLOCK**

```
LTF_RETURN_DESIGN_STATUS: PASS
DESIGN_PATH: 00_LOCKED/MODE_A_LTF_RETURN_ENTRY_DESIGN.md
PRIMARY_STRUCTURE: M5 displacement FVG of the proof leg (OB as clearly-secondary alternate)
LIMIT_RULE_ONE_LINE: limit = near edge of the chosen M5 return structure, iff strictly on the protected side of the true proof-bar close; else STRUCT_UNAVAILABLE (fail-closed)
MEASURE_KILL_SUMMARY: DATA_GAP>30% -> INCONCLUSIVE; median gap_atr>2.0 -> FAIL_STILL_FAR; share<=1.0<50% -> FAIL_NO_NEAR_MASS; 0/3 fill-retained (evaluable) -> FAIL_BASELINE; paper EXPIRED>85% at n>=20 -> FAIL_UNFILLABLE; else PASS_FEASIBILITY
OPEN_QUESTIONS_N: 5
HANDOFF_UPDATED: YES
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: Architect acceptance -> offline LTF-return feasibility measure
```
