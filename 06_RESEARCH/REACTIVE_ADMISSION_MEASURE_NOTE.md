# REACTIVE ADMISSION — OFFLINE COUNTERFACTUAL MEASURE (R1–R6, research only)

> **DIAGNOSTIC — NOT EDGE / NOT AUTHORIZATION TO SHIP.**
> This note reports what the accepted reactive-admission rule set R1–R6
> (`00_LOCKED/REACTIVE_ADMISSION_DESIGN.md`) would have admitted, as a
> counterfactual classifier on the frozen 6m artifacts. Counts of 3 (and 3+8+11
> across phases) support no expectancy, win-rate or edge claim in any
> direction. Nothing here authorizes a routing, live, or paper change.

**Date:** 2026-10-13 · **Authority:** Lead Architect owner plan
`00_LOCKED/OWNER_PLAN_MULTI_TF_TRANSLATION_2026-10-13.md` §6 **step 4** and
`00_LOCKED/REACTIVE_ADMISSION_DESIGN.md` §5 (pre-registered measurement
protocol; the design is DESIGN_LOCKED/accepted, the measure is its §5 gate).
**Composes with:** the near-miss study (`PLACEMENT_NOT_PRIMARY`,
`06_RESEARCH/NEAR_MISS_COUNTERFACTUAL_NOTE.md`, whose frozen fill helpers this
script imports verbatim) and the coincidence count (`COINCIDENCE_MASS_PRESENT`,
`06_RESEARCH/COINCIDENCE_COUNT_NOTE.md`, whose 585-row population this study
reuses row-for-row).
**Scope:** research scripts + tests only. `LOGIC_CHANGED: NO` — no
`04_SRC/smc` admission/scan/route change, no locked-constants edit, no
live/paper change, no M15, no ML.

---

## 1. Question and pre-registered verdicts

**Does the accepted reactive rule set, applied offline to the frozen 6m book,
admit enough armed+coincident candidates to be worth an implement prompt —
without destroying the product's own baseline paths?**

Kill criteria are the design's own §5.3 thresholds, applied verbatim and not
softened:

1. `N_would_admit(Pop1) < 8` → **FAIL_TIGHT** (under-selective / wrong rule).
2. `N_would_admit ≥ 25` AND counterfactual `EXPIRED_NO_FILL > 85%` →
   **FAIL_REPRESENTATION** (orders still placed impossibly far from the
   market).
3. `0` overlap with the 3 control fills (rows evaluable) → **FAIL_BASELINE**
   (the rule destroyed the baseline decision path instead of generalizing it).
4. `N_would_admit > 150` → **FAIL_FLOOD** (indiscriminate gate).
5. Pop-1 DATA_GAP rate > 0.20 → **INCONCLUSIVE** (not enough readable data).
Otherwise → **PASS_MEASURE** — which does **not** authorize live wiring; it
only unlocks Architect review of a possible implement prompt.

## 2. Method (frozen in the script header before the run)

| Item | Value |
|---|---|
| Script | `06_RESEARCH/scripts/reactive_admission_measure.py` |
| Row set | one row per coincident episode (H=48) — the 585 rows of `coincidence_count/episode_coincidence.csv` reused verbatim; candidate proof = the episode's FIRST coincidence (the coincidence study's own de-duplicated choice); one would-be candidate per episode (R6 episode-level) |
| Populations (asserted) | **Pop 1 = 268** armed+coincident (`filled`/`routed`/`armed_never_routed`/`armed_never_routed_zone_only`); **Pop 2 = 208** (`never_armed` AND in the 474 decomposition with `in_accepted_packs=True`); **Pop 3 = 109** remaining. Populations 2–3 are **report-only** — evaluated under all six rules, headline `would_admit=False` by Phase-1 scope, with a `would_admit_phase2` report column (R2–R6 outcome) |
| Rules | the design's R1–R6 as literal predicates (below); every missing field → FAIL-CLOSED `would_admit=False` + `DATA_GAP` — prices/times never invented |
| R1 thesis | Phase-1 = armed in the product run AND armed at/before the proof bar (reactive arm-only scope; armed-after-proof = legit `FAIL`, not a gap) |
| R2 proof | Stage-3 completion exists (the candidate proof) + parseable direction; completion proofs are evaluated against the episode's own POI, so alignment is inherent |
| R3 timing | proof within `H_PROOF=48` of the anchor (the coincident flag itself) AND the market returns to the zone band within `H_RETURN=20` M5 bars of the proof **including the proof bar itself** (in-zone-at-presentation is present, not failure) |
| R4 location | presentation bar = first bar in the return window satisfying the design's NAMED rule `market_reentered_zone` (imported from `smc.risk.fill_regime_policy`); proximity guard `|would_be_limit − close| ≤ 1.0 × ATR` at that bar |
| R5 filters | late-chase at the presentation bar (range > 1.5×ATR AND close beyond the zone away from entry); session = `is_allowed_session` with the product's ASIA/LONDON/NEW_YORK set; invalidation = the ENGINE's own §5 semantics — a full adverse gap VIOLATES only when the zone was never touched before it (touched = TESTED; the engine never violates a TESTED zone) |
| R6 one-shot | a product route presented strictly before the presentation bar consumed the episode one-shot → FAIL; the route presented at/after the presentation bar is the episode's own proposal (that is the overlap population) |
| Zone bounds / limit | armed-record refined bounds for all 268 Pop-1 rows (the armed box, per the episode-store refinement-adopt ruling — `zone_source=armed_record` on every row); would-be limit = the recorded route entry for routed episodes, else the zone proximal edge (design R4 fallback: LONG → zone_high, SHORT → zone_low) |
| ATR | SMA(14) of true range ending at the bar (measure convention, disclosed; the product path uses SeriesState ATR) |
| Paper outcome (secondary) | frozen near-miss fill semantics via `near_miss_counterfactual` helpers (imported, not re-derived); route rows simulate with recorded entry/sl/tp (TP_HIT/SL_HIT/EXPIRED_NO_FILL/OPEN_UNRESOLVED); zone-edge rows test limit-touch over `rest_bars_for` lifetime only (FILLED_NO_RESOLVE — SL/TP never invented) |
| Grid | Step-3 warm-up-inclusive M5 (42,296 bars); warm-up offset asserted at runtime = **6018**, never assumed |
| Determinism | dual run byte-identical (`rows.csv` + `summary.json` SHA-256 match) — no wall-clock field in the summary |

## 3. Integrity

| Check | Result |
|---|---|
| Population split asserted | 268 / 208 / 109 = 585 ✓ (exact, hardcoded assert in script) |
| Warm-up offset | 6018 asserted against the loaded grid ✓ (42296 bars) |
| DATA_GAP on Pop 1 | **0 rows** (0.0% — every required field present in the artifacts) |
| Determinism | dual-run `rows.csv` + `summary.json` **byte-identical** ✓ |
| Fill-simulation calibration | near-miss control verified separately (frozen helpers reproduce the 3 control fills 3/3 per that study); here the 3 control rows are analytically evaluable (identity fields gap-free) ✓ |
| Kill-criterion evaluation | every branch unit-tested (§6) |

## 4. Result — the funnel (Population 1, 268 armed+coincident)

| Stage | Rows | Lost (first failing rule) |
|---|---:|---|
| Armed at proof (reactive reach) | 204 | **64** thesis not armed at proof → R1 |
| Return to zone within 20 bars of proof | 146 | **58** no return in window → R3 |
| Presentation passes proximity (≤1 ATR) | 8 | **138** limit far from market → R4 |
| Exclusions pass | 3 | **5** (zone_violated 4, session+violated 1 → R5) |
| One-shot unconsumed | **3** | **0** first-fail R6 |
| **N_would_admit (Pop 1)** | **3** | 64+58+138+5 = 265 + 3 = 268 ✓ (no gaps) |

Signature: `R4:limit_far_from_market` (138) is the single largest rule
failure — the design's own proximity guard refuses the would-be zone-edge
limit when the presentation bar's close sits more than 1.0 ATR from it (the
in-zone-or-touch presentation mechanics pass, the near-miss study's ~26-unit
representation gap reappears in rule form). `R3:no_return_in_window` (58)
captures theses whose proof never returned price to the zone in 20 bars.
64 theses armed only AFTER their first proof — unreachable by a reactive
(arm-only) rule at that proof, i.e. **proactive mass, not reactive**.

## 5. Populations and overlap

| Population | n | would_admit (Phase 1) | would_admit_phase2 (report-only) |
|---|---:|---:|---:|
| Pop 1 — armed + coincident | 268 | **3** | n/a (all carried as Pop-1) |
| Pop 2 — validated+coincident (never armed) | 208 | 0 (R1 scope) | 11 |
| Pop 3 — other coincident | 109 | 0 (R1 scope) | 3 |
| Total | 585 | 3 | 14 |

- **Overlap with the product's 16 routes: 0** (ids: none).
- **Overlap with the 3 control fills: 0** — and the 3 fill rows ARE evaluable
  (`fills_evaluable=True`): one died immediately on R1 (proof precedes arm;
  fills established arm→route→fill only later in process time), one returned
  in-window but failed the R4 proximity guard at its presentation bar, one had
  no return in the window. Under Phase-1 reactive timing the product's own
  best outcomes are unreachable at their first proofs — the rule set would
  replace the baseline path, not extend it.

## 6. Kill-criteria verdict

```
KILL_CRITERIA_VERDICT: FAIL_TIGHT
  kill1  fired: N_would_admit(Pop1) = 3 < 8          -> under-selective / wrong rule
  kill2  not evaluated path: n < 25 (no EXPIRED rate trigger)
  kill3  fired: overlap with the 3 control fills = 0 (rows evaluable)
         -> destroyed baseline path rather than generalizing it
  kill4  not fired: 3 <= 150
  DATA_GAP rate Pop-1 = 0.00 (INCONCLUSIVE gate clear)
  verdict rule (frozen): first fired in design order 1-4 names the verdict;
  both kill1 and kill3 fired, ordered kill1 -> FAIL_TIGHT
```

**Reading (composition, not new claims).** The two fired kills mirror the two
facts already on record: (a) kill3 is the near-miss verdict in rule form —
the reactive rule admits essentially nothing the product's own path already
produced, and *specifically loses the 3 control fills* because their proofs
predate their arms (nothing proactive is licensed at those moments) and
because the proximity guard rejects the zone-edge limit placement the product
actually uses; (b) kill1 says the literal R1–R6 as frozen admits a handful.
The one place the rule set shows life is the R4 proximity funnel: 8 of the 146
returned theses pass proximity — small, but above the zero the raw near-miss
representation would produce mechanically. Whatever survives review of this
measure, **the binding finding is timing-provenance**: the reactive-vs-arm
order (64 armed-after-proof rows; control fills unreachable) is the dominant
structural cost of Phase-1 scope, and R4's proximity guard is the dominant
geometry cost. No gate, threshold, or rule variant is proposed, tuned, or
authorized by this note — the ban on post-hoc R* improvement stands.

**Secondary paper outcome (disclosed, tiny n).** The 3 admitted Pop-1
candidates all touched their would-be limit within the product rest lifetime
(`FILLED_NO_RESOLVE` — SL/TP do not exist for unarmed candidates and were
never invented). EXPIRED_NO_FILL rate on the evaluable Pop-1 admits: 0.0
(n=3). Nothing inferable at n=3; reported for completeness only.

## 7. Populations 2–3 (report only, never Phase-1 pass/fail)

`would_admit_phase2` (R2–R6 pass, 0 unexplained gaps): **11 of 208** (Pop 2)
and **3 of 109** (Pop 3). These are the same mass the coincidence study
already characterized: real, but tiny under the rule set as written — the
valid admission question is again not "are proofs present" but "what
presentation mechanic would survive R4". No decision follows from these
columns in this task.

## 8. Limitations (binding on any reuse)

- **Counterfactual classifier, not a replay of the reactive engine:** rates
  are evaluated on saved artifacts + one honest series re-load; no scan/order
  machinery is re-run. The fill semantics are the near-miss frozen helpers
  (control-reproduced there), applied to first-proof candidates.
- **One 6m window, one feed, one grid; counts, not rates with error bars.**
- **Presentation-window reading:** the return window includes the proof bar
  (in-zone-at-proof) — a disclosure, frozen in the script header before the
  final run; excluding it would change stage counts, not the verdict family.
- **ATR convention** is SMA(TR,14) ending at the bar (measure constant,
  disclosed); the product path uses SeriesState ATR — the guard thresholds
  are measure constants, not locked values.
- **Zone bounds = armed-record refined bounds** for all Pop-1 rows
  (`zone_source` column; census bounds unused where an armed record exists).
- **R6 route-provenance** uses the near-miss `first_present_bar` as the
  one-shot consumption bar; intent-replacement nuance is below that
  resolution (disclosed; immaterial at n=0 admitted routed rows).
- **Verdict precedence** (first fired rule names the verdict) is an
  interpretation the design does not specify; both fired kills are recorded,
  and the verdict is robust: kill3 alone would be FAIL_BASELINE, kill1 alone
  FAIL_TIGHT, either way a FAIL.

## 9. Artifacts, tests, governance, NEXT

- Script: `06_RESEARCH/scripts/reactive_admission_measure.py` (imports the
  design's named rule + rest rule and the near-miss fill helpers; forks
  nothing; no grid search).
- Results (local-only, gitignored):
  `06_RESEARCH/results/reactive_admission_measure/{rows.csv, summary.json}`
  — rows.csv: 585 rows, per-row R1–R6 flags + reasons + gaps + paper
  column; summary.json: banner, frozen method, integrity, populations,
  funnel, failure-mode histogram, kill verdict. Dual-run byte-identical
  (`_run2` mirror for the determinism receipt).
- Tests: `04_SRC/tests/test_reactive_admission_measure.py` (**35**): frozen
  measure constants pinned; parsers; ATR arithmetic; population split;
  engine-true touch-first violation; golden R1–R6 admit path; fail-closed
  DATA_GAP for every missing field class; R4 boundary (inclusive at 1.0×ATR);
  R6 one-shot strictness; paper labels (NOT_ADMITTED / EXPIRED_NO_FILL /
  FILLED_NO_RESOLVE / SL_HIT / DATA_GAP); every kill-criterion branch incl.
  evaluable-gating and the n=8 boundary. Suite **1097 passed** (0 failed;
  +35 vs the last published count; the delta to the prior 1051 includes the
  episode-store V1 tests accepted since).
- Governance: `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`,
  `CHANGELOG.md` — `LOGIC_CHANGED: NO`, `locked_constants.py` diff empty
  (only the pre-existing dated spread-grade amendment), no `04_SRC/smc`
  decision-path edit (the only 04_SRC addition is the test file).
- **NEXT: Architect review of the measure only.** Per the design: FAIL_TIGHT
  kills the reactive-admission path as written — any redesign must arrive as
  its own dated design proposal with pre-registered rules, before any code.
  The standing measurement threads (entry representation, episode store) are
  unchanged.

---

**RETURN BLOCK**

```
ADMISSION_MEASURE_STATUS: PASS
WINDOW: exec 2025-06-01 -> 2025-11-30 (Step-3 grid 42,296 M5 bars, offset 6018 asserted)
N_POP1_ARMED_COINCIDENT: 268
N_WOULD_ADMIT_POP1: 3
N_WOULD_ADMIT_POP2: 11 (phase2 report-only)
N_WOULD_ADMIT_POP3: 3 (phase2 report-only)
OVERLAP_ROUTES: 0 (ids: none)
OVERLAP_FILLS: 0 (ids: none; fill rows analytically evaluable)
EXPIRED_NO_FILL_RATE_IF_COMPUTED: 0.0 (n=3, all admits touched; tiny n, nothing inferable)
KILL_FIRED: [kill1_under_selective (3 < 8), kill3_zero_control_overlap]
VERDICT: FAIL_TIGHT
NOTE_PATH: 06_RESEARCH/REACTIVE_ADMISSION_MEASURE_NOTE.md
SUITE: 1097 passed (0 failed; +35 new)
LOCKED_CONSTANTS_DIFF: empty
LOGIC_CHANGED: NO
HANDOFF_UPDATED: YES
NEXT_READY: Architect review of measure
```
