# ENTRY-REPRESENTATION STUDY — WHY DO LIMITS SIT FAR FROM THE MARKET?

> **DIAGNOSTIC — NOT EDGE / NOT AUTHORIZATION TO SHIP.**
> This note explains **why** candidate entry limits sit far from the
> post-impulse market on the frozen 6m window (near-miss median closest
> approach ~26 units; the closed admission measure's R4 failed 138/268
> rows on proximity). Distribution + stratified counts only. No new
> entry rule, no threshold work, no admission redesign; every proposed
> representation change lives in a max-5 hypothesis list below, each
> explicitly **NOT implemented in this task**.

**Date:** 2026-10-14 · **Authority:** Lead Architect directive (tightened
prompt) overriding any drift back to the closed reactive-admission
measure. **Scope:** research script + tests only. `LOGIC_CHANGED: NO`
— no `04_SRC/smc` decision-path change, `locked_constants.py` diff
empty, no live/paper change, no M15, no ML.

---

## 1. Question, populations, method (frozen before the run)

**Classify the limit-vs-market gap as MECHANICAL (limit construction),
LIFECYCLE (arm/proof timing), BOTH, or INCONCLUSIVE.**

| Item | Value |
|---|---|
| Script | `06_RESEARCH/scripts/entry_representation_study.py` |
| P0 | the 10 product routes of the frozen 6m book (`near_miss_counterfactual/candidates.csv`; 3 fills / 7 untaken) |
| P1 | 268 armed+coincident rows — the population-1 rows of the frozen `reactive_admission_measure/rows.csv`, reused row-for-row (asserted, not re-derived) |
| P2 (report-only stratum) | P1 rows that failed the admission's R4 only (r1/r2/r3 PASS, r4 FAIL): **138** — exactly the published R4-losses count |
| limit | the frozen `would_be_limit` (recorded route entry for routed rows; else FR-3.1 direction-proximal edge: LONG→zone_high, SHORT→zone_low) |
| **Primary reference** | close of the **TRUE proof bar** — P1 rows/artifacts carry exec-frame bar indexes; true grid index = exec + **6018** (the parent measure's own asserted warm-up offset, reused, never re-pinned) |
| Secondary references | close of the true arm bar; for P0 also the route's first presentation (its proof ref by construction) |
| gap_atr | gap_price ÷ SMA(TR,14) ending AT that bar (the admission measure's disclosed convention, recomputed with its frozen helper) |
| ATR bar sanity | P1 `atr_at_proof` output columns were generated on the wrong frame by the closed measure — recomputed here at the true bar; convention unchanged |
| Zone | `zone_source = armed_record` for all 268 P1 rows; route records for P0 |
| Fail-closed | any missing field → empty gap columns + DATA_GAP; prices never invented |
| Determinism | dual runs byte-identical (`run2` mirror is the receipt); no wall-clock in artifacts |

### Frame verification (asserted, never assumed)
For **every** P0 route, and sampled P1 episodes: `grid[bar + 6018].timestamp`
equals the artifact's own bar timestamp exactly. The reactive rows'
`proof_bar` / `armed_bar` and the near-miss candidates'
`first_present_bar` are all in the **exec frame**; the same conversion
maps all of them onto the step-3 M5 grid (42,296 bars).

---

## 2. Result — the gap is real, large, and largely mechanical

### 2.1 Distributions (primary reference: true proof bar)

| Population | n | p25 | median | p75 |
|---|---:|---:|---:|---:|
| **P1 gap_atr_proof** | 268 | **4.50** | **8.27** | 14.02 |
| P0 gap_atr_proof (routes) | 10 | 1.82 | 5.80 | 11.73 |
| P1 gap_price_proof (units) | 268 | 13.98 | **21.76** | 44.36 |
| P0 gap_price_proof (units) | 10 | 5.56 | 19.47 | 60.47 |
| P1 gap_atr at **arm** bar | 268 | 7.65 | **13.80** | 17.66 |

- **Only 4.1% of P1 rows (11/268) have gap_atr ≤ 1.0 at the true proof
  bar** — the R4 threshold lives in the extreme left tail, and the
  market moves *further* from the zone by the arm bar (median 13.8 ATR),
  so waiting deepens the gap; nothing mean-reverts toward the
  zone-edge limit before presentation.
- **P0 routes that actually filled are the geometry outliers:** the 3
  control fills sit at gap_atr_proof **1.28 / 1.68 / 2.25** — well under
  the P1 median of 8.27. Fill happens when the representation happens
  to land near the market.

### 2.2 Verdict family (frozen rule applied verbatim)

| Input | Value |
|---|---|
| mech (M1 share: limit exactly on proximal edge AND gap > 1 ATR) | **86.6%** (232/268) |
| life (proof_before_arm share) | **23.9%** (64/268) |
| completeness gate (share with computable gap) | 1.000 (0 DATA_GAP rows) |
| **VERDICT_FAMILY** | **BOTH** (both shares ≥ 0.20) |

Both mechanisms carry mass. The **dominant** one is mechanical by a wide
margin: in 232 of 268 rows the limit is *by construction* the zone edge
reached on the impulse leg (`on_edge`), and it sits >1 ATR (median ~8
ATR) from the market at the very proof bar that nominally justifies it.

### 2.3 Strata

| Stratum | n | median gap_atr | pct ≤ 1.0 |
|---|---:|---:|---:|
| trigger **F** | 211 | 8.70 | 3.8% |
| trigger other | 57 | 6.43 | 5.3% |
| armed **at/before** proof | 204 | 8.82 | 2.9% |
| armed **after** proof | 64 | 6.95 | 7.8% |
| limit_source recorded_route_entry | 9 | 3.24 | 22.2% |
| limit_source zone_proximal_armed_record | 259 | 8.61 | 2.3% |

Readings, counts not stories: (a) Trigger-F rows — the bulk — are the
farthest; (b) rows armed *after* their proof are somewhat closer (6.95
vs 8.82 ATR) — the impulse has advanced toward the zone by arm time —
consistent with the lifecycle stratum being a *reachability* problem
(64/268 theses unreachable reactively at all) rather than a separate
geometry; (c) **routed rows (recorded entries) are dramatically closer
than the zone-edge fallback** (median 3.24, 22% ≤ 1 ATR): the 9 routed
limit placements are chosen relative to the live market, while the
unrouted fallback simply parks the limit on the stale zone edge.

### 2.4 Mechanism counts (frozen definitions)

| Mechanism | Count | Note |
|---|---:|---|
| M1_zone_edge_far | **232 / 268** (86.6%) | limit exactly on_edge AND gap_atr_proof > 1.0 |
| M1_near | 10 | on-edge but within 1 ATR |
| M1_off_edge | 26 | limit not exactly at the proximal edge |
| M1 DATA_GAP | 0 | fail-closed path never fired |
| M2 (re-anchor, P0-only, recoverable) | 9 on_edge / 10 routes (+1 not evaluable) | every routed entry sits exactly on the FR-3.1 proximal edge |
| M3_no_return_20 | 58 (**citation only**) | published closed-measure R3 count; never recomputed here |
| M4_proof_after_arm | **64 / 268** | cross-check: matches the published R1 count exactly ✓ |

### 2.5 Control fills — the 3 full geometry cases

| Route | dir/trig | entry vs zone | gap_atr @ proof | gap_atr @ arm | armed→proof bars |
|---|---|---|---:|---:|---:|
| poi-014146:F@5653 | S/F | on_edge | 1.28 | 0.37 | −7 |
| poi-047805:C@18278 | S/C | **inside** | 1.68 | 0.96 | −3 |
| poi-073511:F@27542 | L/F | on_edge | 2.25 | 2.03 | −3 |

All three: proof precedes arm (routed from a live trigger), and all
three sit ≤ 2.3 ATR from market — the geometry tail that fills. The one
non-F trigger (C) is also the only entry recorded strictly *inside* the
zone rather than exactly on its edge.

### 2.6 Zone width (hypothesis-H5 input)

| Stratum | n | median zone_width_atr |
|---|---:|---:|
| on_edge_far | 232 | 15.9 |
| not_on_edge_far | 36 | 17.7 |

Width does **not** separate the strata (H5 not supported by this
window's data; wide zones are not what makes the far-gap).

---

## 3. Instrument residual disclosed (not fixed, not re-opened here)

While verifying frames (assertion step, §1), one finding about the **closed**
reactive-admission measure's own artifacts must be recorded, exactly the
way the near-miss note recorded its `intents_expired=0` counter residual:

- The reactive rows' `presentation_bar` / `presentation_ts` (and the
  `atr_at_proof` column) were produced while the measure's market
  geometry evaluated at grid index `first_coinc_bar − 6018` — a grid
  index 6018 slots **earlier** than the artifact's own `first_coinc_ts`
  timestamp (verified by exact timestamp comparison on multiple rows;
  e.g. `poi-h4-25e747aa`: `grid[5436]` → 2025-05-28 08:55 yet its
  published `proof_ts` is 2025-06-27 06:55 = `grid[5436+6018]`).
- Quantified by this study's shifted-frame disclosure columns: 18/268
  rows change side of the 1.0-ATR line between frames
  (pct ≤ 1.0 ATR: 4.1% true vs 2.6% shifted). **No admission verdict,
  rule, or threshold is re-derived from this; the measure's
  FAIL_TIGHT verdict stays CLOSED as directed.** If the Architect wants
  the closed measure's own R3/R4 inference re-run on the verified frame,
  that needs its own dated decision.
- This study therefore did **not** reuse the closed measure's
  presentation columns anywhere: P1 presentation refs are unavailable by
  design (disclosed limitation), and P0 presentation uses each route's
  own ts-asserted `first_present_bar`.

---

## 4. Hypothesis list (max 5 — all NOT implemented in this task)

| # | Claim | Support in this run | Refute evidence that would kill it |
|---|---|---|---|
| H1 | **Mechanical anchor:** FR-3.1 places every candidate limit exactly on the *impulse-leg* proximal edge, so at the proof bar the limit is against the retracement path — the far-gap is constructed, not drifted. | M1 = 232/268 (86.6%); all 9 routed entries exactly on_edge; routed entries (market-relative) median 3.24 ATR vs 8.61 for the zone-edge fallback | material share of rows with *inside-zone* limits that still show gap > 1 ATR at the true proof bar |
| H2 | **Lifecycle:** 64/268 theses arm after their first coincident proof — a reachability loss-rate that compounds with (does not replace) the geometry problem. | M4 = 64 exactly (cross-check ✓); armed-after-proof rows still 6.95 ATR far at proof | the 64 armed-after-proof rows uniformly inside 1 ATR |
| H3 | **Nothing is missing:** the frozen artifacts carry limit/zone/ATR for the whole P1 population (completeness 1.000), so a representation redesign has real inputs to work with. | 0 DATA_GAP rows | gap completeness < 0.70 |
| H4 | **Instrument residual:** the closed measure's market geometry ran on grid indexes 6018 slots earlier than its own published timestamps; 18/268 rows flip across the 1-ATR line between frames. Resolving it is a dated re-run decision, not reachable here. | side-changes = 18; pct ≤ 1.0: 4.1% (true) vs 2.6% (shifted) | zero side changes and presentation columns matching true-frame indexes |
| H5 | Zone width (in ATR) conditions the far-gap (wide zones ⇒ mid-zone placement would matter). | **NOT supported here:** on_edge_far rows' widths are not wider (15.9 vs 17.7 median) | width separation of the two strata by a wide margin |

No hypothesis is promoted: none was tuned post-run, and none is
allowed to become a rule without a dated design + its own admission
measure pass.

---

## 5. Honesty rules honored

- P1 DATA_GAP rate on gap_atr = 0.0% (< 30% INCONCLUSIVE gate). The
  verdict family is computed, not dodged.
- No "move the limit to mid-zone" recommendation anywhere: the routed
  rows' better geometry is *reported* (stratum 2.3), not generalized.
- R3's 58 cited only as a published count; the admission measure was
  not re-run and its verdict not revisited.
- n is large descriptively (268/268) but this stays one 6m window, one
  instrument, one feed: counts support no expectancy, rate, or edge claim.

## 6. Limitations (binding on any reuse)

- Primary/reference definition is *this study's own freeze*: true
  proof-bar close. Which reference a future design wants (proof, arm,
  presentation) is a design decision, not a measurement output.
- The P1 presentation reference is **not measured at all** (the closed
  measure's presentation columns are unusable pending the H4 residual,
  and re-deriving presentation would re-run admission logic) —
  disclosed; the gap-at-arm secondary reference partially covers the
  temporal dimension (median 13.8 ATR, worse than proof).
- ATR convention SMA(TR,14) is a measure convention; product path uses
  SeriesState ATR (thresholds here are measure constants, not locked).
- P0 n=10 (3 fills) is a census, not a sample; its strata (22% ≤ 1 ATR)
  are illustrative only.
- Frame conversion (+6018) is asserted against artifact timestamps, not
  re-derived from any product code path; a different future warm-up
  offset would need re-verification (asserted fail-fast at runtime).

## 7. Artifacts, tests, governance, NEXT

- Script: `06_RESEARCH/scripts/entry_representation_study.py` (imports
  the frozen parent ATR helper + offset constant; forks nothing; no
  grid search; fail-closed; secrets-free read-only research).
- Results (local-only, gitignored):
  `06_RESEARCH/results/entry_representation/{rows.csv, summary.json}` —
  278 data rows (10 P0 + 268 P1) with true-frame gap columns,
  shifted-frame disclosure columns, mechanism flags, strata fields;
  `summary.json` carries frozen method, distributions, strata,
  mechanism counts, control-fill geometry, verdict family, max-5
  hypotheses. Dual-run byte-identical (`entry_representation_run2`
  mirror is the receipt; rows sha `3ec1720b…`, summary sha `42e203b8…`).
- Tests: `04_SRC/tests/test_entry_representation_study.py` — **14**
  tests (exec→grid conversion, fail-closed gap paths, on-edge/far-edge
  states, MECH flag boundary at exactly 1.0 ATR, proof_before_arm,
  percentiles, frozen family branches with all INCONCLUSIVE/BOTH
  gates, R4-only stratum flag, artifact schema pins, ≤5 hypotheses
  each NOT-implemented, parent-offset reuse pin). Suite green.
- Governance: `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`,
  `CHANGELOG.md` — docs-only, `LOGIC_CHANGED: NO`, the
  locked-constants diff stays the pre-existing dated 2026-10-11
  spread-grade amendment only, no `04_SRC/smc` decision-path change
  (the only `04_SRC` addition is the test file).
- **NEXT: Architect review of entry representation only.** Nothing in
  this note opens the closed admission study; the H4 frame residual is
  recorded for its own dated decision if the Architect wants the
  closed measure re-run on the verified frame. Any representation
  redesign arrives as its own dated design + pre-registered rules
  **before any code**, and would need its own admission-measure pass.

---

**RETURN BLOCK**

```
ENTRY_REP_STATUS: PASS
WINDOW: frozen 6m (exec 2025-06-01 -> 2025-11-30; grid 42,296 M5 bars, offset 6018 asserted)
N_P0_ROUTES: 10
N_P1: 268
MEDIAN_GAP_ATR_P0: 5.80
MEDIAN_GAP_ATR_P1: 8.27
PCT_P1_GAP_ATR_LE_1: 0.041
PROOF_BEFORE_ARM_SHARE_P1: 0.239 (64/268, matches published count)
DOMINANT_MECHANISM: BOTH (mech 86.6% on_edge_far dominates; life 23.9%)
HYPOTHESES_N: 5
VERDICT_FAMILY: BOTH
NOTE_PATH: 06_RESEARCH/ENTRY_REPRESENTATION_NOTE.md
SUITE: full repo suite green (all prior 1097 + 14 new tests)
LOCKED_CONSTANTS_DIFF: empty
LOGIC_CHANGED: NO
HANDOFF_UPDATED: YES
NEXT_READY: Architect review of entry representation
```
