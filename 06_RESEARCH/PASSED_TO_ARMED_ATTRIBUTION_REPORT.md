# PASSED → ARMED ATTRIBUTION (LEG 4) — WHY VALIDATED POIs NEVER ARM

> **DIAGNOSTIC — NOT EDGE.**
> Event counts here are *validation batches*, not independent structures: the
> frozen composition re-validates the same zones on every H1 close, so 2,021
> passes decompose into **30** episodes. Nothing below is a rate, an
> expectancy, a win-rate, or a profit claim, and **nothing below authorizes a
> change**: no gate was loosened or tightened, no dedup, expiry, zone band,
> pillar, trigger or posture rule was touched, and no arm-policy patch is
> proposed. The leg measures which disposition the product itself took for
> every pass.

**Date:** 2026-10-20 · **Authority:** Lead Architect owner plan
`00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md` **LEG 4**.
Prior rulings: **LEG 1** `HOLD_P2_FVG` · **LEG 2** `R-HOLD` · **LEG 3**
`FILL_PATH_HEALTHY`.
**PASSED_ARMED_STATUS: PASS** — the capture reproduces the frozen 6m composition
exactly (2,979 batches / 43,004 merged / 2,021 passed / 30 armed), every pass
lands in exactly one pre-registered bucket, the composition's own
`duplicates_suppressed` and `skipped_tracked` counters are reproduced id-for-id,
and the label is applied by the rule written before the run.
**LABEL: `ARM_FILTER_IS_BOTTLENECK`** · **WIRING_BUG: NO**.
**Scope:** read-only measurement. `LOGIC_CHANGED: NO` — no `04_SRC/smc`
decision path edited, `locked_constants.py` diff **empty**, no pillar / P2 /
FVG / trigger / expiry / zone-band change, no multi-symbol, no ML.

---

## 1. Question and the pre-registered rule

LEG 3 closed the placement side: when the product places a limit, the market
fills it (`FILL_PATH_HEALTHY`; 14/14 in the 18m secondary). Scarcity therefore
sits earlier — **PASS → ARM**, where the frozen funnel reports
`passed_validation = 2,021` against `armed = 30` (1.5%). This leg asks one
question only: *for every validation PASS in the frozen product path, which
gate did it hit, and how much of the loss is each gate responsible for?*

The label rule was fixed **before** the run:

- `INCONCLUSIVE_LOW_N` — fewer than 50 PASS events.
- Wiring holes are never hidden behind a filter label: `DATA_GAP` +
  `SKIP_OTHER` above **1%** of passes ⇒ **`MIXED`** with `WIRING_BUG: YES`.
- `DEDUP_DOMINATED` — dedup ≥ 50% of passes **and** the matches are
  same-episode: median **coverage** of the PASS zone by its blocker ≥ **0.50**.
- `ARM_FILTER_IS_BOTTLENECK` — dedup ≥ 50% but the matches are **not**
  same-episode (median coverage < 0.50), or the combined
  dedup+freshness+posture+give-up+one-shot+registry+TF+merge share ≥ 50% with
  no single bucket reaching 50%.
- `FRESHNESS_DOMINATED` — freshness/touch ≥ 50%.
- `ARM_PATH_HEALTHY` — no bucket ≥ 50% and wiring clean.
- `MIXED` — otherwise.

`coverage` = overlap ÷ width of the **PASS** zone. 1.0 means the passing zone
lies entirely inside (or exactly on) the already-armed zone — the same
structure re-emitted; 0.0 means the two zones share a single edge. It is a
geometric measure of *sameness*, not an outcome claim.

## 2. Method (frozen before running)

| Item | Value |
|---|---|
| Window | M1 warm-up from **2025-05-01**; exec **2025-06-01 → 2025-11-30** M5 (**35,725** exec bars) — the frozen 6m product window used by Phase 3 / FR-4 / LEG 1 / LEG 3 |
| Composition | `phase3_structure_funnel.run` **imported, not forked** — `MultiTFProductRuntime.run_batch` at the new-H1-close cadence → `PipelineEngine` arm → `PipelineAdapter` scans → `BacktestRunner` risk, with the frozen zero-cost machine-completeness config |
| Capture seam | logging-only class wraps, restored in `finally`: `MultiTFProductRuntime.run_batch` (batch context + the batch report's own armed / duplicates / skipped_tracked ids), `MultiTFDetectionDriver.validate_multi` (the exact per-TF `passed` list and `ValidationResult`s the arm loop will walk), `ZoneDedup.seen` / `.register` (the dedup verdict **and** the blocking zone), `PipelineEngine.episode` / `.arm_at` (the tracked check and the arm attempt, exception preserved and re-raised) |
| Attribution source | the product's own decisions — nothing is re-simulated. The arm loop in `_arm_passed` has exactly three gates, in order: `engine.episode(poi) is not None` → `dedup.seen(poi.zone)` → `engine.arm_at(poi, arm_bar)` |
| Buckets (pre-registered) | `ARMED`, `SKIP_DEDUP_EPISODE`, `SKIP_TRACKED`, `SKIP_FRESHNESS_TOUCH`, `SKIP_POSTURE`, `SKIP_GIVE_UP_EXPIRY`, `SKIP_ONE_SHOT`, `SKIP_REGISTRY_CAP`, `SKIP_TF_POLICY`, `SKIP_MERGE_ORDER`, `SKIP_OTHER` (with machine reason), `DATA_GAP`. Every PASS lands in exactly one; the seven buckets with no code path in the current arm loop are kept in the table and reported as **0** so the absence of a gate is evidence, not an omission |
| Episode view | every PASS event — armed or not — replayed through the product's own `ZoneDedup` predicate (same direction + inclusive overlap on 6dp bounds, first match wins, registration order). This is the honest structural unit; it is reported next to (never instead of) the event histogram |
| Secondary window | the LEG 3 18m window (**2023-12-01 → 2025-05-31**) was **not re-captured**: the primary already produces a ranking with three orders of magnitude of separation, and the identical composition measured **15,313 s (4.25 h)** for that window in LEG 3. §9 reports the independent corroboration LEG 3's own secondary already carries |

Script: `06_RESEARCH/scripts/passed_to_armed_study.py`
(`--capture` runs the composition under the seam; `--analyze-only` re-reads the
saved capture and reproduces every table — verified **byte-identical** on two
consecutive runs).

## 3. The arm path, from the code (not guessed)

`MultiTFProductRuntime._arm_passed` walks each detection TF's `passed` list and
applies **only**:

1. `engine.episode(poi) is not None` → `report.skipped_tracked` (the engine
   already tracks this POI **id**);
2. `dedup.seen(poi.zone)` → `report.duplicates` (`ZoneDedup`: same direction +
   overlapping zone, 6 dp bounds, **no expiry of any kind**);
3. `engine.arm_at(poi, arm_bar)` → armed, or `report.errors[poi.id]` when the
   §5 machine refuses the transition.

There is no freshness gate, no posture gate, no give-up/expiry gate, no
one-shot gate, no registry cap, no TF policy and no merge ranking on this path.
The funnel's own `skipped_tracked` counter therefore reads 0 by construction,
and all seven of those buckets are 0 here.

**The asymmetry that produces the histogram:** the engine's registry *is*
pruned — `PipelineAdapter.prune_terminal_pois` → `PipelineEngine.prune_terminal`
runs every bar (I4), releasing TESTED/VIOLATED episodes — while the runtime's
`ZoneDedup` has **no removal API at all** (`seen` / `register` / `__len__`
only). So a zone that armed once in June still suppresses every overlapping
same-direction zone in November, long after its episode died and was pruned
from the engine. `SKIP_TRACKED = 0` next to `SKIP_DEDUP_EPISODE = 1,991` is
that asymmetry showing up in the counts.

## 4. Funnel strip and integrity

| Stage | Count | Source |
|---|---|---|
| HTF batches | **2,979** | composition |
| merged POIs | **43,004** (14.4 / batch) | composition |
| **passed validation** | **2,021** (0.68 / batch) | composition |
| → `SKIP_DEDUP_EPISODE` | **1,991** | this leg |
| → `SKIP_TRACKED` | **0** | this leg |
| → `SKIP_OTHER` / `DATA_GAP` / all other buckets | **0** | this leg |
| **ARMED** | **30** | this leg = composition |
| routes / placed / fills (unchanged context) | 10 / 4 / 3 | composition |

| Integrity check | Result |
|---|---|
| pass events vs `funnel_summary.passed_validation` | **2,021 = 2,021** |
| armed vs `funnel_summary.armed` **and** every batch report's armed ids | **30 = 30**, id sets equal |
| dedup vs `funnel_summary.duplicates_suppressed` **and** report duplicates | **1,991 = 1,991**, id sets equal |
| tracked vs `funnel_summary.skipped_tracked` | **0 = 0**, id sets equal |
| one bucket per PASS / bucket sum = passes | **true / 2,021** |
| `batch_errors` | **0** |
| analysis determinism (`--analyze-only` twice) | `summary.json` + `pass_disposition.csv` **byte-identical** |

## 5. Ranking — every PASS, one bucket

| Bucket | Events | % of 2,021 passes | Gate exists in code? |
|---|---|---|---|
| `ARMED` | **30** | **1.48%** | yes |
| `SKIP_DEDUP_EPISODE` | **1,991** | **98.52%** | yes (`ZoneDedup.seen`) |
| `SKIP_TRACKED` | 0 | 0.00% | yes (`engine.episode`) — never fires |
| `SKIP_FRESHNESS_TOUCH` | 0 | 0.00% | **no** |
| `SKIP_POSTURE` | 0 | 0.00% | **no** |
| `SKIP_GIVE_UP_EXPIRY` | 0 | 0.00% | **no** |
| `SKIP_ONE_SHOT` | 0 | 0.00% | **no** |
| `SKIP_REGISTRY_CAP` | 0 | 0.00% | **no** |
| `SKIP_TF_POLICY` | 0 | 0.00% | **no** |
| `SKIP_MERGE_ORDER` | 0 | 0.00% | **no** |
| `SKIP_OTHER` (arm rejected) | 0 | 0.00% | yes (`arm_at` raise) — never fires |
| `DATA_GAP` | 0 | 0.00% | — |

**Top 3:** `SKIP_DEDUP_EPISODE` (1,991, 98.52%) · `ARMED` (30, 1.48%) ·
`SKIP_TRACKED` (0, 0.00%). Nothing else moves.

By detection TF (`detection_tf` = the batch that passed it; the funnel's
`armed_by_tf` instead groups by *zone* timeframe, hence 19 H4 / 6 H1 / 5 D1):

| Detection TF | passes | armed | dedup | distinct geometries |
|---|---|---|---|---|
| H1 | 1,556 | 26 | 1,530 | 137 |
| H4 | 465 | 4 | 461 | 39 |

### 5.1 Episode-clustered view (the honest structural unit)

| Metric | Value |
|---|---|
| episodes (PASS events clustered by the product's own dedup rule) | **30** |
| episodes with an armed member | **30** |
| episodes with **more than one** armed member | **0** |
| episodes never armed | **0** |
| median PASS events per episode | 30.5 (max **539**) |
| episodes spanning both detection TFs | 12 |
| share of all passes held by the five largest episodes | **62.9%** |

So the 2,021 passes are **30** price-band episodes, each armed exactly once.
The 1:1 map is *built with the same rule that produced the blockers*, so it is
a consistency check (no episode lost, none double-armed), not independent
evidence — the evidence about whether the rule is doing identity work or
filtering structures is the geometry in §5.2.

### 5.2 Is the dedup match the same episode?

| Metric | Value |
|---|---|
| dedup events with a resolved blocker | 1,991 / 1,991 |
| **median coverage of the PASS zone by its blocker** | **0.461** |
| coverage p10 / p90 | 0.128 / 1.000 |
| coverage ≥ 0.50 | 45.6% |
| coverage = 1.00 (PASS zone fully inside / exactly on blocker) | **22.8%** |
| **identical 6 dp bounds** | **11.5%** (229) |
| edge-contact only (coverage exactly 0.0) | 11 |
| coverage < 0.10 | 92 |
| same-batch dedup (H4 armed first, H1 zone same structure) | 2 |
| cross-batch dedup | 1,989 |
| distinct blockers (of the 30 armed zones) | 29 |
| **blocker age, median / max** | **29.5 days / 140.3 days** |
| blocked by a zone armed ≥ 30 days earlier | **991 (49.8%)** |
| blocked by a zone armed ≥ 90 days earlier | 227 |

Coverage bands (share of dedup events):

| Coverage band | events | % of dedup | distinct geoms | geoms never armed | median blocker age | median PASS zone width |
|---|---|---|---|---|---|---|
| 1.00 | 454 | 22.8% | 49 | 21 | 0.7 d | 31.6 |
| 0.75–1.00 | 150 | 7.5% | 17 | 17 | 32.6 d | 49.4 |
| 0.50–0.75 | 304 | 15.3% | 26 | 26 | 20.6 d | 61.7 |
| **0.25–0.50** | **716** | **36.0%** | 38 | 38 | **50.4 d** | 35.4 |
| **0.00–0.25** | **367** | **18.4%** | 34 | 34 | **40.2 d** | 38.7 |

Exact-geometry census: the 2,021 passes carry **166** distinct 6 dp geometries
(median re-emission **8×**, max **252×**); **30** of those geometries armed and
**136** never did. The count on either side is a bound, not a truth —
`ZoneDedup` is a union-find by overlap (so 30 clusters under-count distinct
structures) while exact 6 dp bounds drift as the prefix grows (so 166
geometries over-count them). Both bounds are reported; the geometric
distribution above is what decides the label.

## 6. Sample autopsy — 20 non-armed PASS rows

Deterministic selection: the dominant bucket spread from most-identical to
least-overlapping, then any other non-empty bucket. `blk` = the already-armed
zone the product's own predicate matched.

| # | as_of (UTC) | det TF | zone TF | dir | PASS zone | blk zone | cov | blk age | disposition |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-06-02 09:00 | H1 | D1 | LONG | 3205.78–3245.03 | 3205.78–3245.03 | 1.000 | 0.04 d | `SKIP_DEDUP_EPISODE` |
| 321 | 2025-07-15 11:00 | H1 | D1 | LONG | 3282.43–3320.95 | 3249.51–3325.32 | 1.000 | **42.8 d** | `SKIP_DEDUP_EPISODE` |
| 864 | 2025-08-19 05:00 | H1 | H4 | LONG | 3334.64–3339.35 | 3334.64–3339.35 | 1.000 | 0.08 d | `SKIP_DEDUP_EPISODE` |
| 1411 | 2025-10-09 13:00 | H1 | D1 | LONG | 3975.93–3995.78 | 3961.55–3995.78 | 1.000 | 0.33 d | `SKIP_DEDUP_EPISODE` |
| 1787 | 2025-10-30 06:00 | H4 | H4 | SHORT | 4043.62–4154.44 | 4043.62–4154.44 | 1.000 | 0.42 d | `SKIP_DEDUP_EPISODE` |
| 877 | 2025-08-20 09:00 | H1 | D1 | LONG | 3267.95–3334.60 | 3249.51–3325.32 | 0.861 | 78.7 d | `SKIP_DEDUP_EPISODE` |
| 1392 | 2025-10-09 09:00 | H1 | D1 | LONG | 3717.35–3779.00 | 3691.89–3759.03 | 0.676 | 16.0 d | `SKIP_DEDUP_EPISODE` |
| 882 | 2025-08-20 18:00 | H4 | D1 | LONG | 3267.95–3354.32 | 3249.51–3325.32 | 0.664 | 79.1 d | `SKIP_DEDUP_EPISODE` |
| 499 | 2025-07-22 05:00 | H1 | H1 | LONG | 3316.11–3332.26 | 3249.51–3325.32 | 0.570 | 49.5 d | `SKIP_DEDUP_EPISODE` |
| 819 | 2025-08-14 03:00 | H1 | H1 | SHORT | 3359.20–3408.68 | 3367.57–3391.93 | 0.492 | 70.9 d | `SKIP_DEDUP_EPISODE` |
| 87 | 2025-06-13 08:00 | H1 | H1 | LONG | 3321.16–3330.35 | 3249.51–3325.32 | 0.452 | 10.7 d | `SKIP_DEDUP_EPISODE` |
| 1096 | 2025-09-17 23:00 | H1 | H1 | LONG | 3340.76–3356.03 | 3350.40–3370.57 | 0.369 | 57.8 d | `SKIP_DEDUP_EPISODE` |
| 1603 | 2025-10-20 20:00 | H1 | H1 | LONG | 3340.76–3356.03 | 3350.40–3370.57 | 0.369 | 90.7 d | `SKIP_DEDUP_EPISODE` |
| 2003 | 2025-11-18 09:00 | H1 | H1 | LONG | 3340.76–3356.03 | 3350.40–3370.57 | 0.369 | **119.2 d** | `SKIP_DEDUP_EPISODE` |
| 471 | 2025-07-21 15:00 | H1 | H1 | LONG | 3309.57–3358.70 | 3249.51–3325.32 | 0.320 | 49.0 d | `SKIP_DEDUP_EPISODE` |
| 1756 | 2025-10-24 19:00 | H1 | D1 | LONG | 4014.76–4135.60 | 4001.03–4049.39 | 0.287 | 15.5 d | `SKIP_DEDUP_EPISODE` |
| 140 | 2025-06-15 23:00 | H1 | D1 | LONG | 3332.57–3391.20 | 3377.80–3391.20 | 0.229 | 2.6 d | `SKIP_DEDUP_EPISODE` |
| 1335 | 2025-09-29 17:00 | H4 | H4 | LONG | 3323.34–3338.85 | 3249.51–3325.32 | 0.128 | 119.0 d | `SKIP_DEDUP_EPISODE` |
| 1044 | 2025-09-03 15:00 | H4 | H4 | LONG | 3323.34–3342.03 | 3249.51–3325.32 | 0.106 | 93.0 d | `SKIP_DEDUP_EPISODE` |
| 1293 | 2025-09-24 12:00 | H1 | D1 | LONG | 3683.36–3691.89 | 3691.89–3759.03 | **0.000** | 1.2 d | `SKIP_DEDUP_EPISODE` |

Row 1293 is the tail of the rule in one line: the two zones share exactly one
boundary (3691.89) and **zero area**, yet `ZoneDedup.seen` returns True because
its predicate is inclusive on both edges (`known_top >= bottom and top >=
known_bottom`). Eleven events in the window are suppressed on that basis alone.

## 7. Time structure (descriptive only)

| Month | passes | armed | dedup | episodes first seen |
|---|---|---|---|---|
| 2025-06 | 239 | 10 | 229 | 10 |
| 2025-07 | 367 | 2 | 365 | 2 |
| 2025-08 | 334 | 3 | 331 | 3 |
| 2025-09 | 420 | 7 | 413 | 7 |
| 2025-10 | 438 | 7 | 431 | 7 |
| 2025-11 | 223 | 1 | 222 | 1 |

Pass volume almost doubles from June to October while arms do not; the
September–October rise in arms is new episodes starting in those months, not an
easing of the filter. Dedup events blocked by a zone armed ≥ 30 days earlier
are spread across the whole window (271 / 261 / 202 / 112 / 145 for
Jul–Nov).

## 8. Interpretation — one label

**`ARM_FILTER_IS_BOTTLENECK`** · **`WIRING_BUG: NO`**

The pre-registered rule fires on geometry: dedup suppresses **98.52%** of
passes, but the median PASS zone is only **46.1%** covered by the zone that
blocked it, only **11.5%** of matches are the same 6 dp bounds, and **49.8%** of
suppressions come from a zone armed **≥ 30 days** earlier. That is not the
signature of an idempotency gate re-seeing one structure; it is a permanent,
geometry-only registry folding *overlapping but not identical* ranges into old
episodes — a third of it (36.0%) at 25–50% coverage, another 18.4% at under 25%.

Two things must be said in the same breath, because they pull in opposite
directions:

1. **No wiring hole.** Every pass reached a gate, none raised, none is
   unattributed (`DATA_GAP = 0`, `SKIP_OTHER = 0`), 30 episodes produced 30
   arms with no double-arm, and the funnel's own counters are reproduced
   id-for-id. The arm *loop* behaves exactly as written.
2. **The filter it applies is doing more than identity.** `ZoneDedup` is the
   only gate that ever fires, it never expires an entry, and the engine's
   registry *is* pruned every bar — so the product reasons "this POI was
   already armed" from a set that no longer reflects anything the engine
   tracks. The 22.8% of dedups that are fully covered and the 11 events
   suppressed on a zero-area edge touch are the same mechanism at its two
   extremes.

Nothing here says the 1,991 suppressions were tradeable, and no counterfactual
"what would have armed instead" is computed — that would be a policy
proposal, which this leg is not authorized to make. The label names where the
loss is, not what to do about it.

## 9. Window coverage and corroboration

- **Primary only** for the geometry: the 6m window is the composition used by
  every prior leg, and its 2,021 passes support a ranking with three orders of
  magnitude of separation, so the pre-registered primary basis was not
  displaced.
- **Secondary not re-captured** (documented, not skipped silently): the
  identical composition cost **15,313 s (4.25 h)** for the 18m window in LEG 3,
  and the only question it could still answer — "does the coverage geometry
  replicate?" — is worth a separate owner decision, not an unattended rerun.
- **Independent corroboration already on disk:** LEG 3's own 18m secondary
  funnel (`results/fill_takeability/secondary_18m`) reads **6,626 passed / 81
  armed / 6,545 duplicates_suppressed** — 98.78% dedup and 1.22% armed, i.e.
  the same event-level shape in a wholly disjoint regime. It carries no
  coverage geometry, so it corroborates the *dominance*, not the label's
  geometric criterion.

## 10. Limitations (binding on any reuse)

1. **Events are not structures.** 2,021 passes are 30 episodes; any percentage
   quoted per *event* describes how often the detector re-emits, not how many
   opportunities were lost.
2. **Only one window carries the geometry.** The label's decisive statistic
   (median coverage, blocker age) is measured on the frozen 6m window only.
3. **Bounds drift.** Exact 6 dp geometry over-counts distinct structures
   (prefix-grown models revise bounds); overlap clusters under-count them.
   The two bounds (166 / 30) bracket the truth; neither is asserted as it.
4. **The cluster↔arm map is constructed, not discovered** (both use the same
   overlap rule) — it is a consistency check.
5. **Blocker age is time since the blocker armed**, not time since its episode
   died; the engine's prune is per-bar (I4) but the study does not log the
   prune time of each blocker, so the "died weeks ago" reading rests on the
   code fact that `ZoneDedup` never forgets, not on a per-row measurement.
6. **One symbol, one composition, zero-cost machine-completeness config.** No
   claim transfers to another symbol, cost model, or detection set.
7. **Order within a batch is a real decision input** (H4 is processed before
   H1), so the two same-batch suppressions are the documented H4-first effect,
   not an accident.

## 11. Artifacts and governance

| Artifact | Path |
|---|---|
| Report | `06_RESEARCH/PASSED_TO_ARMED_ATTRIBUTION_REPORT.md` |
| Script | `06_RESEARCH/scripts/passed_to_armed_study.py` |
| Capture (every PASS event, one JSONL line each) | `06_RESEARCH/results/passed_to_armed/pass_events.jsonl.gz` |
| Summary | `06_RESEARCH/results/passed_to_armed/summary.json` |
| Disposition CSV (2,021 rows) | `06_RESEARCH/results/passed_to_armed/pass_disposition.csv` |
| Composition output (funnel, trades) | `06_RESEARCH/results/passed_to_armed/_funnel_capture/` |
| Tests (25 pure-helper tests) | `04_SRC/tests/test_passed_to_armed_attribution.py` |

`locked_constants.py` diff **empty** · `LOGIC_CHANGED: NO` · no pillar / P2 /
FVG / trigger / expiry / zone-band change · no arm-policy patch · no
expectancy or edge claim · no multi-symbol.

## 12. NEXT (Architect)

The leg proposes nothing. It hands over one named suspect and three mutually
exclusive directions, each requiring its own dated ruling and its own proof
register entry **before** any code:

- **HOLD the arm filter as written** — "one arm per zone band per run" is
  accepted as the product's definition of an episode.
- **Design-lock episode retirement** — make the dedup registry release an
  entry when the episode it represents dies (the engine already prunes; the
  registry does not). This is a policy change and would need its own
  before/after measurement.
- **Design-lock a sameness rule** — replace "any overlap, inclusive, forever"
  with an explicit coverage/age criterion, again with its own measure first.

Until such a ruling, ARM remains the product's tightest single gate at
**1.48%** of validation passes, and LEG 3 already showed that what does arm
converts to a fill.
