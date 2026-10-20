# TECHNICAL OWNER PLAN — POST-PROBE (SCARCITY)

**Date:** 2026-10-19
**Owner authority:** this file is the binding ordered work list for the post-probe
scarcity track. It was reconstructed from the owner's posted LEG 1/LEG 2 text
(no source copy of `TECHNICAL_OWNER_PLAN_POST_PROBE.md` existed in the tree at
placement time); the LEG text below is verbatim in substance.
**Baseline:** frozen Mode A, `v1.1` runtime contract, commit `9b649d5` working tree.
**Constraint:** measurement only. No production rule change is authorized by LEG 1.

---

## Context (from `06_RESEARCH/LIVE_PRODUCT_FUNNEL_PROBE_NOTE.md`)

- Live `armed = 0` is the expected state under the frozen contract.
- Pillar 2 (Displacement) is the dominant killer: ~88% of candidates, mostly
  *missing directional FVG* (72.2% of all rejections), then *missing BOS body-close*
  (15.9%).
- The flowchart's toolkit intent reads as an OR-toolkit; the code as implemented
  is an AND-gauntlet (BOS **and** FVG **and** magnitude ≥ 1× ATR).
- Whether that AND-gauntlet removes *good* paths or only untakeable ones is the
  open question this plan measures.

---

## LEG 1 — NEAR-MISS COUNTERFACTUAL (P2 FVG / BOS) — MEASURE

**Status: [x] PASS — 2026-10-19. See `06_RESEARCH/NEAR_MISS_P2_FVG_COUNTERFACTUAL_REPORT.md`
(INTERPRETATION: `HOLD_P2_FVG`; n_A 54 / n_B 88 / n_C 7; suite 1174).**

Scope: MEASURE only. No production rule change.

### Hard bans

- `locked_constants.py` untouched
- No pillar / trigger / Mode T / live decision changes
- No threshold search / no trial loops
- No expectancy, Sharpe, or "edge proven" language
- No multi-symbol work

### Data

- `07_DATA/XAUUSD_M1.parquet` (canonical)
- Reuse production pillar definitions from code (validation pipeline; Pillar 2
  displacement: BOS, FVG, magnitude)
- Window: the frozen 6m product baseline window (`FROZEN_FUNNEL_6M_*`): exec
  `2025-06-01 → 2025-11-30` M5, M1 load from `2025-05-01`
- Fail loud if data missing

### Pre-registered populations (do not redefine after results)

- **A — STRICT PASS:** candidates that pass the frozen pillars through the P1–P4
  hard path (same "passed" notion as the research funnel).
- **B — P2 NEAR-MISS PRIMARY (FVG absent):** P2 fail reason includes missing
  directional FVG **and** BOS present (production definition) **and** displacement
  magnitude ≥ 1.0× ATR (production definition).
- **C — P2 NEAR-MISS SECONDARY (optional, separate tables):** strong displacement
  path but BOS fails body-close (wick-only). Reported separately; never pooled
  into the B headline.

Document the exact code functions/fields used for BOS, FVG, ATR, magnitude.

### Anchor and metrics

- Single anchor per candidate: displacement-complete bar **or** first P2-fail bar —
  one rule, documented.
- From the anchor, in POI direction: MFE and MAE in price and in R.
- R definition: stop distance if reconstructable; else 1× ATR at anchor — documented.
- Horizons H ∈ {20, 50, 100} in M5 bars (M1 scaled equivalently; documented).
- Per population: n, median MFE/MAE at each H, % MFE ≥ 1R / ≥ 2R at each H,
  optional p25/p75.
- Compare A vs B (and C) with tables only — no p-hacking.

### Interpretation (allowed labels only)

Exactly one: `HOLD_P2_FVG` | `AMEND_CANDIDATE` | `INCONCLUSIVE`, with one short
paragraph why. No implementation proposal carrying new numbers unless labelled
"illustrative only, not a ruling".

### Deliverables

1. `06_RESEARCH/NEAR_MISS_P2_FVG_COUNTERFACTUAL_REPORT.md`
2. `06_RESEARCH/results/near_miss_p2_fvg/summary.json` + candidates csv
3. `06_RESEARCH/scripts/near_miss_p2_fvg_study.py`
4. SESSION_HANDOFF + CHANGELOG + this checkbox when PASS
5. Return block (`LEG1_STATUS` … `NEXT_READY: LEG 2 Architect ruling only`)

---

## LEG 2 — ARCHITECT RULING (LEG 1)

**Status: [x] DONE — R-HOLD `HOLD_P2_FVG`** (FVG gate stays; admitting the
FVG-absent class is NOT authorized).

The architect read the LEG 1 report and held the gate. LEG 1 produced no
implementation proposal. No threshold, pillar, trigger, or mode change was
made. Any future change must land as its own dated design ruling with its own
proof register entry.

---

## LEG 3 — FILL / TAKEABILITY STUDY

**Status: [x] DONE — `FILL_PATH_HEALTHY` (basis: secondary 18m, `F = 14/14`,
`X = 0/14`, `n = 14`; primary 6m `n = 4` → below the `n ≥ 10` gate).**
Report `06_RESEARCH/FILL_TAKEABILITY_REPORT.md`; measurement only, no
proposal. Disclosed deviation: the secondary was re-pinned from 24 months to
18 months under a runtime constraint **before any secondary result existed**
(report §2.1).

**Premise (from R-HOLD):** scarcity is real; admitting the FVG-absent class is
not authorized; the remaining frequency drag is likely ARM → ROUTE → PLACE →
FILL rather than P2 alone. Prior work showed routes with 0 fills in some
windows and limit-at-zone / §23 expiry friction.

**Original goal (kept for the record):** quantify takeability of product entries — when a route/place exists,
how often would price have allowed a fill under the frozen fill model, and what
kills fills (never touch, touch after expiry, runaway, session, ...)?

**Hard bans (this leg):** `locked_constants.py` untouched; no pillar / P2 / FVG
/ trigger decision change; no widening of `ZONE_REFINEMENT`, expiry, or
re-anchor; no expectancy/edge claims; no multi-symbol; `LOGIC_CHANGED: NO` on
the decision path (logging-only wrappers allowed).

**Deliverables:** `06_RESEARCH/FILL_TAKEABILITY_REPORT.md`;
`06_RESEARCH/results/fill_takeability/{summary.json,orders_fate.csv}`;
`06_RESEARCH/scripts/fill_takeability_study.py`; handoff/changelog; return
block with `N_ARMED / N_ROUTES / N_PLACED / N_FILLED`, fate counts, medians,
and exactly one of `FILL_PATH_HEALTHY | FILL_PATH_IS_BOTTLENECK | MIXED |
INCONCLUSIVE_LOW_N`.

**Rule (pre-registered before the runs):** the frozen 6m window is the primary
basis; if it has < 10 placed orders the secondary window is the basis; neither
reaching 10 → `INCONCLUSIVE_LOW_N`. Windows are never pooled. The label uses
only placed orders: `F = filled/placed`; `X` = share of placed orders that
touched only after the product lifetime ended or ended within 0.5×ATR of their
limit at that moment. `FILL_PATH_HEALTHY` = F ≥ 0.5 and X < 0.25;
`FILL_PATH_IS_BOTTLENECK` = F < 0.5 and X ≥ 0.5; otherwise `MIXED`.

---

## LEG 4 — PASSED → ARMED ATTRIBUTION

**Status: [x] DONE — `ARM_FILTER_IS_BOTTLENECK` · `WIRING_BUG: NO`.**
Report `06_RESEARCH/PASSED_TO_ARMED_ATTRIBUTION_REPORT.md`; measurement only,
no proposal, no arm-policy patch.

**Premise:** LEG 3 cleared PLACE → FILL. Validation survival ~4.7%, and of the
passes only ~1.2–1.5% arm, so ~98.5% of validated POIs never enter the
seek/scan book. This leg measures that stage only.

**Result:** 2,021 passes / 30 armed; the disposition histogram is
`SKIP_DEDUP_EPISODE 1,991 (98.52%)` + `ARMED 30 (1.48%)` and **nothing else**
(`SKIP_TRACKED 0`, all seven code-absent gates 0, `SKIP_OTHER 0`,
`DATA_GAP 0`). Integrity reproduces the frozen counters and id sets exactly.
Episode view: the 2,021 events are **30** episodes (median 30.5 events each,
max 539), each armed exactly once. Dedup geometry: median coverage **0.461**,
identical bounds 11.5%, **49.8%** of suppressions come from a zone armed
≥ 30 days earlier (median age 29.5 d, max 140.3 d), 11 events on a zero-area
edge touch. Mechanism, from code: the engine's registry is pruned every bar
(I4) while `ZoneDedup` has no removal API, so a long-dead episode keeps
suppressing overlapping same-direction zones.

**Hard bans (this leg):** `locked_constants.py` untouched; no pillar / P2 /
FVG / trigger / expiry / zone-band change; no arm-policy change; no
"arm more POIs" patch; no expectancy/edge claims; no multi-symbol;
`LOGIC_CHANGED: NO` (logging-only wrappers, restored in `finally`).

**Deliverables:** report; `06_RESEARCH/results/passed_to_armed/{summary.json,
pass_disposition.csv,pass_events.jsonl.gz}`;
`06_RESEARCH/scripts/passed_to_armed_study.py`;
`04_SRC/tests/test_passed_to_armed_attribution.py`; handoff/changelog.

**NEXT (Architect ruling — no silent implement):** hold the filter as written,
or design-lock episode retirement (dedup releases when the episode dies), or
design-lock an explicit sameness rule (coverage/age). Each needs its own dated
ruling, its own pre-registered measure, and its own proof register entry.

---

## LEG 5 — ZONE DEDUP ↔ EPISODE LIFECYCLE (DESIGN LOCK → IMPLEMENTED)

**Status: [x] DONE — `DESIGN_LOCK_STATUS: PASS`; [x] LEG 5b implementation done
2026-10-20 per the Architect ACCEPT (note
`06_RESEARCH/ZONE_DEDUP_LIFECYCLE_IMPLEMENTATION_NOTE.md`): frozen 6m dual run —
integrity exact (2,979 / 43,004 / 2,021), `retired_total` 606, ARMED 30 → 606
(+576), `SKIP_DEDUP_EPISODE` 1,991 → 1,415 (−576, exact conservation), `trades.csv`
/ `report.json` byte-identical, no double-arm of a live episode, suite
1,220 → 1,236 (EXIT=0), `locked_constants.py` diff empty,
`LOGIC_CHANGED: YES` (dedup lifecycle only). NEXT: Architect review of the
post-implement funnel.**
Note `06_RESEARCH/ZONE_DEDUP_LIFECYCLE_DESIGN.md`. Authority: Architect ruling
**R-ARM** 2026-10-20 (`ARM_FILTER_IS_BOTTLENECK` — intentional dedup; lifetime
too long). Prior HOLDs untouched (LEG 1 `HOLD_P2_FVG`, LEG 3
`FILL_PATH_HEALTHY`).

**Design delivered (R1–R7 + R8 residual):** owner-attributed key at arm
(`register` keeps the unchanged 6 dp geometry and adds the owning `poi.id`);
`seen` unchanged and owner-blind; ONE id-based `retire(owner_id)` whose
predicate is "no live obligation — no resting order, no open position, **no
alive R9 intent**, no in-flight workflow — AND (`VIOLATED` or
`bar_index > arm_bar + poi_give_up_bars()`)", evaluated in the existing per-bar
prune step (`PipelineAdapter.prune_terminal_pois`), before the scan and after
that bar's arm batch; keys stay **shared** across detection TFs; edge-touch kept
as residual; **no new constant, TTL, age or coverage rule**. Acceptance gates
A–F pre-registered: integrity exact, `retired_total ≥ 1` (zero invalidates the
run), `SKIP_DEDUP` falls and `ARMED > 30` reported as **deltas not targets**,
≤ 1 concurrent arm per live key, byte-identical dual run, `SKIP_TRACKED = 0`,
suite green, `LOGIC_CHANGED: YES` declared for the implement leg.

**Code fact found in this leg (corrects LEG 4's wording):** the adapter's prune
retention test calls `_may_route(..., bar=None)`, whose legacy contract returns
True for **every FRESH or TESTED** POI (`pipeline_adapter.py:362-366, 442-445`),
so a TESTED episode is **never** pruned through the runner path — verified
read-only (armed at bar 0, give-up 20, still tracked at bars 25 / 500 / 5000).
"Retire when `prune_terminal` removes it" would therefore release only VIOLATED
keys, i.e. a minority of the suppression mass; R3 defines death on lifecycle
facts and leaves the engine's retention untouched.

**Hard bans (this leg):** no `04_SRC` change, no test change, no
`locked_constants` change, no pillar/trigger/fill/expiry/arm-policy edit, no
"arm everything that passes", no suite re-run (docs only).
`LOGIC_CHANGED: NO`.

**Deliverables:** the design note; handoff / changelog / todo entries; return
block (`DESIGN_LOCK_STATUS`, `DEDUP_API_SURFACE`, `REGISTER_ON`, `RETIRE_ON`,
`KEY_DEFINITION`, `MULTI_TF_KEYS`, `EDGE_TOUCH`, `LOGIC_CHANGED`,
`LOCKED_CONSTANTS_DIFF`, `NOTE_PATH`, `NEXT_READY`).

**NEXT (Architect):** accept the design → implementation prompt. That leg's
only authorised edit surface: `ZoneDedup` + its two `register` sites + the
adapter prune step + one registry bind. No silent implement.

---

## LEG 6 — POST-DEDUP NEW-ARM QUALITY SAMPLE (DIAGNOSTIC)

**Status: [x] DONE — `NEW_ARM_QUALITY_STATUS: PASS` 2026-10-20.
INTERPRETATION: `NEW_ARMS_SIMILAR_TO_LEGACY`.
Note `06_RESEARCH/POST_DEDUP_NEW_ARM_QUALITY_REPORT.md`;
script `06_RESEARCH/scripts/post_dedup_new_arm_quality.py`; results under
`06_RESEARCH/results/post_dedup_new_arm_quality/`. `LOGIC_CHANGED: NO`
(read-only, logging-only seams restored in `finally`); `locked_constants.py`
diff EMPTY; suite NOT_RUN (no shipped code surfaced). Authority: Architect
ACCEPT of LEG 5b; prior HOLDs untouched.**

**Measured (frozen 6m window, as-shipped lifecycle run):** lifecycle capture
byte-identical to the LEG 5b run (`trades.csv` `8eecd3b9…`), integrity exact
(606 arms / 606 registers / 219 routes / 65 places / 606 retires). Cohorts by
direct membership: A **30** (matched 1:1 to an append-only counterfactual
capture — same composition with the retirement seam no-op'd — whose funnel
(30→10→4 placed→3 fills, F2/C1) and whose **armed id set reproduce LEG 4's
exactly**), B **576** (573 via pre-registered first-match blocker-retire join,
3 via recorded displacement proof: cf-blocked space AND full give-up chain
retire < arm bar — `poi-006662/033642/054982`), join gaps **0**,
double-arm live **0**. Funnel: A routed 33.33% / filled 6.67%; B routed
36.28% / filled 9.72% → Δ +2.95 / +3.05 pp (inside the pre-registered ±10 pp
bands). Trigger mix B F188/A9/B8/C1/E3 — F-dominated like A (F9/C1). Exit mix:
A TP1/SL1; B TP29/SL27. Geometry/timing medians disclosed; **no edge,
expectancy or throttling claim anywhere; dedup and arming untouched.**

---

## Guardrails for the whole plan (LEG 3 through LEG 6 inherit them)

- Diagnostic, not edge: no rate, expectancy, or profitability claim from this work.
- Every artifact carries the `DIAGNOSTIC — NOT EDGE` banner.
- `LOGIC_CHANGED: NO` for LEG 1; `locked_constants.py` diff must be empty.
