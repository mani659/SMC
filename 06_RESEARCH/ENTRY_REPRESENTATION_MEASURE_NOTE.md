# ENTRY-REPRESENTATION MEASURE — RL-1 UNDER TEST vs CONTROL / RL-2 / RL-3

> **DIAGNOSTIC — NOT EDGE / NOT AUTHORIZATION TO SHIP.**
> This note scores the accepted design's candidate limit rules
> (`00_LOCKED/ENTRY_REPRESENTATION_DESIGN.md`, ACCEPTED 2026-10-14) as
> counterfactual limit recomputations on the frozen 6m populations.
> Counts support no expectancy, win-rate or edge claim in any
> direction. No product limit, Trigger F, FR-3.1, routing, or
> locked-constant change is proposed or authorized; the reactive
> admission measure R1–R6 stays CLOSED (its artifacts supply join keys
> only). `PASS_MEASURE` for any rule would unlock an Architect
> implement discussion only — never a ship decision.

**Date:** 2026-10-14 · **Authority:** Lead Architect directive after
the entry-representation design acceptance. **Scope:** research script
+ tests only — `LOGIC_CHANGED: NO`; no `04_SRC/smc` decision-path
edit; `locked_constants.py` diff remains the pre-existing dated
spread-grade amendment only.

---

## 1. Frozen method (design §5 applied verbatim + operational pins)

| Item | Value |
|---|---|
| Script | `06_RESEARCH/scripts/entry_representation_measure.py` (imports the entry-rep study's frozen rows + the reactive module's grid/ATR/edge helpers; forks nothing) |
| Populations | P0 = 10 frozen product routes; P1 = 268 armed+coincident rows (reused row-for-row from the true-frame study artifacts); P2 report flag only |
| Rules × rows | CONTROL (FR-3.1 status quo) · RL-1 `pullback_shelf` (PRIMARY under test) · RL-2 `retrace_mid` · RL-3 `edge_plus_wait` — scored separately, **no stacking**; TP/SL construction unchanged (limit only) |
| Reference | true proof-bar close (primary, verified exec→grid frame) + arm-bar close (secondary); ATR = SMA(TR,14) at the referenced bar |
| RL-1 (k=1.0, frozen) | shelf = proof-close ± 1.0×ATR with the design's three guard rails (protected side / no zone tunneling / no proof-extreme overshoot); any guard failure → CONTROL limit kept and the fallback **counted** |
| RL-2 (parameter-free) | midpoint of the measured displacement leg: span start = last bar within the frozen `LEG_SPAN_LOOKBACK = 96` M5 bars whose [low, high] contains the proximal edge; no touch found → DATA_GAP (span never invented) |
| RL-3 | limit formula = CONTROL verbatim; deferred presentation = first bar in [proof, proof+rest] where the NAMED `market_reentered_zone` rule holds **and** the limit is within 1.0×ATR of the close; missing lifetime → DATA_GAP |
| Paper path (disclosed secondary) | P0: rule limit + recorded SL/TP through the frozen near-miss route semantics; P1: touch-only (`FILLED_NO_RESOLVE` / `EXPIRED_NO_FILL`, SL/TP never invented); CONTROL/RL-1/RL-2 lifetime = [proof, proof+rest]; RL-3 = its own presentation span with remaining lifetime |
| Determinism | dual runs byte-identical (`entry_representation_measure_run2` mirror is the receipt); no wall-clock in artifacts |

**Disclosure — lifetime window convention:** the paper path anchors
lifetimes at the proof/first-presentation bar (the study frame), not at
the near-miss study's actual `placed_bar` (intent-inherited, e.g.
`poi-073511`'s 6-bar intent clock). A route whose product fill came
from a later placed bar can read `EXPIRED_NO_FILL` here that read
`SL_HIT` there (1/3 control fills). Immaterial to the overlap kill
(2/3 retained per rule below) but stated plainly: this is a
re-anchored reconstruction, not the product's fill ledger.

## 2. Per-rule results (P1 = 268, true proof-bar reference)

| Metric | CONTROL | **RL-1 (primary)** | RL-2 | RL-3 |
|---|---:|---:|---:|---:|
| median gap_atr (proof) | **8.27** | **7.73** | 4.77* | 8.27 (limit unchanged) |
| p25 / p75 gap_atr | 4.50 / 14.02 | 3.22 / 13.53 | 1.84 / 8.28* | 4.50 / 14.02 |
| median gap_atr (arm bar) | 13.80 | 13.80 | 13.74* | 13.80 |
| share ≤ 1.0 ATR | 4.1% | **12.3%** | 3.4%* | 4.1% |
| share ≤ 2.0 ATR (report band) | 7.8% | 18.3% | 7.1%* | 7.8% |
| rule DATA_GAP rate | 0% | 0% | **73.5%** | 0% |
| fallback rows (guard) | — | **235/268** (guard3 194, guard2 41) | 0 | 0 |
| fill overlap (of 3) | 2/3 | 2/3 | 2/3 | 2/3 |
| paper EXPIRED rate (lifetime path, P1) | 13.1% (n=268) | 11.6% (n=268) | 0.0% (n=71*) | 1.2% (n=81 presented) |
| P0 median gap_atr (routes) | 5.80 | 5.80 | 0.75 | 5.80 |
| **VERDICT (first-fired)** | **FAIL_STILL_FAR** | **FAIL_STILL_FAR** | **FAIL_NO_NEAR_MASS** | **FAIL_STILL_FAR** |

*RL-2's rows marked * are computed over the **71 usable rows only**
(197/268 = 73.5% DATA_GAP) — see the honesty note below.

## 3. The findings (counts, not stories)

- **RL-1's own guard rails bind the rule.** The k=1.0 shelf stands
  only for 33/268 P1 rows: 194 guard failures come from guard 3
  (the shelf would sit inside the proof bar's adverse extreme —
  8.27-ATR gaps mean the proof bar's own down-range exceeds the 1-ATR
  shelf offset on most rows), 41 from guard 2 (shelf would tunnel the
  zone's distal edge). The 87.7%-fallback rule therefore leaves the
  book nearly CONTROL-shaped: median 7.73 vs 8.27, near-mass share
  4.1% → 12.3%, EXPIRED rate 13.1% → 11.6%, all three fill rows still
  evaluable with 2/3 retained. **Verdict: FAIL_STILL_FAR** (median
  7.73 ≥ 6.0) — the primary rule as frozen does not fetch the limit
  near the market; its failures are honest design rejections, silently
  widening nothing.
- **RL-2 cannot be honestly read on this window.** 73.5% of P1 rows
  have no proximal-edge touch anywhere in the 96-bar frozen lookback —
  the displacement leg is not recoverable at that lookback on this
  population. Per the frozen first-fired order its verdict is
  FAIL_NO_NEAR_MASS (share ≤ 1.0 = 3.4% < 10%), **but the same
  evaluation trips the design's own ≥ 20% INCONCLUSIVE gate** (73.5% ≫
  20%): "no near mass" cannot be distinguished from "span
  unmeasurable". The non-failing subset (n=71) does show the expected
  geometry (median 4.77, p25 1.84, P0 routes 0.75) — suggestive, but
  not readable as a rule verdict. **No threshold was moved to rescue
  it**; a longer lookback would be a design amendment, not a measure fix.
- **RL-3 defers but the market does not come back.** Its limit is
  CONTROL-identical, so its proof-gap stats are CONTROL-identical and
  kill 1 fires. The mechanism it owns shows: only **81/268** theses
  ever present inside the R8 lifetime under re-entry+proximity
  (median 12 bars to presentation; 187 expire un-presented). The
  81 presented rows fill at 98.8% within their remaining lifetime
  (touch-only semantics) — but presentation itself is the bottleneck,
  exactly the closed measure's R3 finding reappearing under its own
  named rule. **Verdict: FAIL_STILL_FAR** (no stacking; reported
  side-by-side as directed).
- **CONTROL baseline reproduces the study:** median 8.27, 4.1%
  ≤ 1.0 ATR, 2/3 fills retained, 13.1% expired — the scored baseline
  matches the entry-representation study's numbers row-for-row (its
  own proof-gap column), confirming the frame and helper reuse.

## 4. Kill matrix (design §5, first-fired order)

| Kill | CONTROL | RL-1 | RL-2 | RL-3 |
|---|---|---|---|---|
| 1 median ≥ 6.0 → FAIL_STILL_FAR | fired (8.27) | **fired (7.73)** | not fired (4.77 n=71) | fired (8.27) |
| 2 share ≤ 1.0 < 10% → FAIL_NO_NEAR_MASS | would fire | not fired (12.3%) | **fired (3.4%)** | would fire |
| 3 0 fill overlap (evaluable) → FAIL_BASELINE | 2/3 | 2/3 | 2/3 | 2/3 |
| 4 paper EXPIRED > 90% at n ≥ 20 → FAIL_UNFILLABLE | 13.1% | 11.6% | 0.0% (n=71) | 1.2% (n=81) |
| 5 DATA_GAP > 20% → INCONCLUSIVE | 0% | 0% | **73.5% (also tripped)** | 0% |
| **VERDICT** | FAIL_STILL_FAR | **FAIL_STILL_FAR** | FAIL_NO_NEAR_MASS | FAIL_STILL_FAR |

**Bottom line: no rule earns a PASS_MEASURE. RETURN: no implement
discussion is unlocked; the entry-representation program returns to
the Architect with this evidence.** The mechanical anchor problem is
unresolved by all three accepted candidates *as frozen* — RL-1's
guards route it back to the stale edge, RL-2's leg span is largely
unmeasurable at the frozen lookback, and RL-3 defers everything into
the same no-return gap. Notably, the fill rows stay retained under
every rule (2/3): nothing here destroys the product's baseline
geometry — the fail is "still far", not "baseline broken".

## 5. Honesty rules honored

- Kill thresholds, k=1.0, the 50% transform, and the 96-bar lookback
  were frozen in the script header **before** the run (and are pinned
  by tests); nothing was tuned after results.
- No rule stacking; RL-3's limit formula unchanged; TP/SL untouched.
- No expectancy language anywhere; counts and rates only; one 6m
  window, one feed, one instrument.
- No admission reopen: the closed measure provides join keys and
  rest-lifetime constants only.
- RL-2's 73.5% DATA_GAP is reported as a finding, not smoothed over;
  the note states both the frozen-order verdict and the
  INCONCLUSIVE-grade incompleteness.

## 6. Limitations (binding on any reuse)

- **Counterfactual reconstruction, not a product run:** limits are
  recomputed on the frozen artifacts; the paper path is touch/sim
  semantics, not fills.
- **Window-convention difference vs the near-miss study** (§1
  disclosure): proof-anchored lifetimes re-derive outcomes that can
  differ from the product's placed-bar ledger on 1/3 control fills.
- **RL-2's leg-span operationalization** (96-bar lookback, "last bar
  whose range contains the edge") is one frozen pin of the design's
  "formation window" wording; other pins could recover more rows —
  that is a design amendment decision, banned from this measure.
- ATR is the SMA(TR,14) measure convention; k/lookback/proximity are
  measure constants, never locked values.
- n counts are large but this is one 6m window; no CI, no edge claim.

## 7. Artifacts, tests, governance, NEXT

- Script: `06_RESEARCH/scripts/entry_representation_measure.py`.
- Results (local-only, gitignored):
  `06_RESEARCH/results/entry_representation_measure/{rows.csv,
  summary.json}` — 1,112 rows (278 episodes × 4 rules) with counter-
  factual limits, gaps, bands, fallbacks, presentation fields, paper
  outcomes, DATA_GAP reasons; `summary.json` carries the frozen
  constants, per-rule distributions, kills, verdicts, and the frozen
  disclosure fields. Dual-run byte-identical (`_run2` mirror; rows sha
  `b6daabf3…`, summary sha `75b4d0eb…`).
- Tests: `04_SRC/tests/test_entry_representation_measure.py` (**8**)
  — frozen constants pin, RL-1 formula + each guard + fail-closed
  direction, RL-2 midpoint + leg-span fail-closed, RL-3 immediate/
  deferred/none + fail-closed band, kill branches with exact
  boundaries (inclusive median at 6.0, strict-less near share, n=20
  gate, 90% strict-greater) and first-fired ordering, no post-hoc
  threshold drift. **Full suite green** (see governance).
- Governance: `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`,
  `CHANGELOG.md` — docs-only, `LOGIC_CHANGED: NO`; `locked_constants.py`
  diff = the pre-existing dated spread-grade amendment only; no
  `04_SRC/smc` decision-path edit (the only `04_SRC` addition is the
  test file).
- **NEXT: Architect review of the representation measure.** The three
  accepted candidates all fail as frozen; any next move (e.g. amending
  RL-1's guard rails, widening RL-2's leg span, or accepting the
  fill-retention result as the deliverable and stopping 2/3) must
  arrive as its own dated design amendment — none is proposed or
  authorized here.

---

**RETURN BLOCK**

```
REP_MEASURE_STATUS: PASS
WINDOW: frozen 6m (exec 2025-06-01 -> 2025-11-30; grid 42,296 M5 bars, offset 6018 asserted)
N_P0: 10
N_P1: 268
RL1_MEDIAN_GAP_ATR_P1: 7.73
RL1_PCT_LE_1_P1: 0.123
RL1_VERDICT: FAIL_STILL_FAR
RL2_VERDICT: FAIL_NO_NEAR_MASS (INCONCLUSIVE-grade: 73.5% DATA_GAP, disclosed)
RL3_VERDICT: FAIL_STILL_FAR
CONTROL_MEDIAN_GAP_ATR_P1: 8.27
FILL_OVERLAP_RL1: 2/3
NOTE_PATH: 06_RESEARCH/ENTRY_REPRESENTATION_MEASURE_NOTE.md
SUITE: full repo suite green (all prior 1111 + 8 new tests)
LOCKED_CONSTANTS_DIFF: empty
LOGIC_CHANGED: NO
HANDOFF_UPDATED: YES
NEXT_READY: Architect review of representation measure
```
