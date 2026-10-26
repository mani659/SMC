# NEAR-MISS COUNTERFACTUAL — P2 FVG / BOS (LEG 1)

> **DIAGNOSTIC — NOT EDGE.**
> Every number below is a description of path geometry on one instrument,
> one feed, one six-month window. There is no expectancy, win-rate, Sharpe,
> profit-factor or "edge proven" claim in this document, and nothing here
> authorizes a threshold, pillar, trigger, Mode T or live-decision change.

**Date:** 2026-10-19 · **Authority:** `00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md`
(LEG 1, owner pre-registered populations) · **Context:** live `armed = 0` probe
(`06_RESEARCH/LIVE_PRODUCT_FUNNEL_PROBE_NOTE.md`: Pillar 2 kills ~88% of
candidates, mostly *missing directional FVG*).
**Measurement only.** `LOGIC_CHANGED: NO` — no `04_SRC/smc` edit, no MQL5 edit,
`locked_constants.py` untouched, no threshold search, no multi-symbol work.

```
LEG1_STATUS: PASS
INTERPRETATION: HOLD_P2_FVG
```

---

## 1. Question

The flowchart's toolkit reads as an OR of SMC tools; the code as implemented is
an AND-gauntlet — BOS **and** directional FVG **and** magnitude ≥ 1× ATR. Pillar 2
removes ~88% of candidates, mostly for the missing FVG. Did that gate cut off a
**better** class of paths than it admitted, or only paths no better than the ones
it kept? This leg measures forward path geometry for the three pre-registered
populations. It proposes nothing.

## 2. Window and data

| Item | Value |
|---|---|
| Data | `07_DATA/XAUUSD_M1.parquet` (canonical; loaded, not re-derived) |
| Load (warm-up) | 2025-05-01 → exec end |
| Execution window | **2025-06-01 → 2025-11-30** M5 — the frozen 6m product window of `FROZEN_FUNNEL_6M_POST_TP_REPORT.md` |
| Execution bars | 35,725 M5 bars (first exec bar 2025-06-01 22:00 UTC) |
| Detection timeframes | H4 + H1 (product seam); M5 is the measurement clock |
| Composition | `phase3_structure_funnel.run` **imported, not forked** — the frozen product composition (C1 seam, engine, adapter, runner) |

**Integrity — the capture reproduces the frozen funnel exactly** (measured by
replaying the same composition with logging-only wrappers installed):

| Counter | Frozen 6m (`FROZEN_FUNNEL_6M_POST_TP_REPORT`) | This capture | Match |
|---|---:|---:|---|
| HTF batches | 2,979 | 2,979 | ✓ |
| Merged candidates | 43,004 | 43,004 | ✓ |
| Passed validation | 2,021 | 2,021 | ✓ |
| Armed | 30 | 30 | ✓ |
| Routes | 10 | 10 | ✓ |
| Fills | 3 | 3 | ✓ |

Pillar first-failure histogram: `P2 37,745 · P1 1,207 · P3 2,031 · PASS 2,021`
(P2 share 87.77%, identical to the published baseline). Capture runtime 887.7 s.

## 3. Definitions (production code, quoted not re-derived)

| Field | Source | Production meaning |
|---|---|---|
| pass | `smc.validation.validation_pipeline.ValidationResult.passed` | Pillars 1–4 hard + 5 soft all passed → armed |
| first failure | `ValidationResult.first_failure` (`pillar`, `detail`) | first P1–P4 non-pass, short-circuit |
| BOS | `smc.detection.displacement_checker.check_displacement` → `DisplacementResult.bos` (`bos_index`) | a candle **body close** beyond the prior swing extreme (`most_recent_swing` of the move direction), within the detection window |
| FVG | same module → `DisplacementResult.fvg` | a same-direction 3-candle FVG whose `start_index` lies between the sweep index and the BOS index |
| magnitude | same module → `DisplacementResult.magnitude_atr` | (sweep extreme → BOS close) ÷ **pre-sweep** Wilder ATR(14) |
| P2 fail text | `smc.validation.pillar_2_displacement.DisplacementPillar` | `"missing BOS (no body close beyond the prior swing)"`, `"missing directional FVG"`, `"displacement below 1× ATR"`, `"displacement < 0.5× ATR (hard fail)"` |
| ATR (R unit) | `smc.utils.atr.atr_series(..., 14)` on M5 | Wilder RMA, first `period` bars `None` |

### Episode clustering (the one measurement choice that moves counts)

The product re-validates the whole HTF prefix every hour, so one structural
setup appears in dozens of consecutive batches (liberal — over-counts events in
one episode; conservative — avoids the same-zone-is-a-different-candidate claim).
One validation **event** = one merged POI in one batch; the headline unit is an
**episode cluster** built with the product's own `ZoneDedup` rule
(`smc.orchestration.multi_tf_runtime.ZoneDedup.seen`: same direction + overlapping
span), applied per detection timeframe in chronological order, keeping the first
zone of each episode. Anchors are always taken from that episode's retained row.

## 4. Pre-registered populations (frozen before the run, unchanged after)

| Pop | Definition | n (episodes) | by TF | long / short |
|---|---|---:|---|---|
| **A** | strict pass — the candidate ever passed all pillars | **54** | H4 17 · H1 37 | 37 / 17 |
| **B** | never passed; P2 first failure detail = *missing directional FVG*; BOS present; magnitude ≥ 1.0× ATR | **88** | H4 48 · H1 40 | 57 / 31 |
| **C** | never passed; P2 first failure = *missing BOS*; magnitude ≥ 1.0× ATR; break **wick-only** (wick beyond the production prior swing, never a body close) | **7** | H1 7 | 5 / 2 |

A ∩ B = 0 and A ∩ C = 0 by construction (A = ever passed; B/C = never passed).
Population C is reported separately and is **never pooled** into the B headline.

Model-tag texture (episodes carrying ≥1 tag): A `M8 51 · M7 19 · M1 15 · M4 8`;
B `M8 79 · M2 7 · M4 5 · M1 3`; C `M8 7`. Event rows: 43,004; clusters: 166;
events per cluster p50 = 84 (max 4,849) — that repetition is why clustering exists.

## 5. Anchor, R, horizons — one rule

| Rule | Value |
|---|---|
| Anchor | the M5 bar of the **first evaluation event that defines the population** — A: first PASS; B: first qualifying FVG-absent P2 fail; C: first qualifying wick-only P2 BOS fail |
| Forward window | starts on the **next** M5 bar (`anchor+1`); end-of-series rows with incomplete windows are reported as clipped and excluded from the statistics |
| Direction | POI zone direction (the thesis the candidate expresses) |
| R | **1 × Wilder ATR(14) on M5 at the anchor** — uniform for all populations. Stop distance is not reconstructable for never-routed candidates (no SL exists pre-route), so one honest rule is used rather than inventing brackets |
| MFE / MAE | max close-to-high / close-to-low excursion in price and in R over the horizon. This is *observed excursion*, not a trade simulation: no order, no fill, no stop-first ordering |
| Horizons | H20 / H50 / H100 M5 bars |

## 6. Results — full tables

MFE/MAE are medians in R unless stated. `clip` = rows whose horizon ran past
2025-11-30 and are excluded from the statistics.

### 6.1 Population A — strict pass (n = 54)

| H | n | clip | median MFE_R | p25 | p75 | median MFE (price) | median MAE_R | median MAE (price) | % MFE ≥ 1R | % MFE ≥ 2R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 54 | 0 | 2.40 | 1.14 | 5.16 | 8.08 | 0.96 | 3.17 | 79.6 | 55.6 |
| 50 | 54 | 0 | 4.04 | 1.78 | 7.20 | 14.26 | 1.59 | 6.66 | 92.6 | 74.1 |
| 100 | 53 | 1 | 5.97 | 4.03 | 7.48 | 20.34 | 4.00 | 11.92 | 92.5 | 88.7 |

### 6.2 Population B — FVG-absent near-miss, BOS + ≥1× ATR (n = 88)

| H | n | clip | median MFE_R | p25 | p75 | median MFE (price) | median MAE_R | median MAE (price) | % MFE ≥ 1R | % MFE ≥ 2R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 88 | 0 | 1.90 | 0.99 | 3.69 | 8.22 | 1.40 | 5.32 | 75.0 | 47.7 |
| 50 | 88 | 0 | 2.85 | 1.85 | 5.11 | 11.84 | 2.20 | 6.94 | 81.8 | 70.5 |
| 100 | 88 | 0 | 4.94 | 2.15 | 9.15 | 18.50 | 3.46 | 14.37 | 89.8 | 77.3 |

### 6.3 Population C — wick-only BOS near-miss, ≥1× ATR (n = 7, separate)

| H | n | clip | median MFE_R | p25 | p75 | median MFE (price) | median MAE_R | median MAE (price) | % MFE ≥ 1R | % MFE ≥ 2R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 7 | 0 | 0.88 | 0.88 | 3.45 | 4.78 | 2.70 | 14.79 | 42.9 | 42.9 |
| 50 | 7 | 0 | 2.95 | 1.25 | 4.00 | 8.88 | 2.70 | 16.27 | 71.4 | 57.1 |
| 100 | 7 | 0 | 2.95 | 1.25 | 4.10 | 8.88 | 6.06 | 18.36 | 71.4 | 57.1 |

### 6.4 A vs B side by side (tables only — no other statistic was computed)

| H | A med MFE_R | B med MFE_R | A %≥1R | B %≥1R | A %≥2R | B %≥2R | A med MAE_R | B med MAE_R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 2.40 | 1.90 | 79.6 | 75.0 | 55.6 | 47.7 | 0.96 | 1.40 |
| 50 | 4.04 | 2.85 | 92.6 | 81.8 | 74.1 | 70.5 | 1.59 | 2.20 |
| 100 | 5.97 | 4.94 | 92.5 | 89.8 | 88.7 | 77.3 | 4.00 | 3.46 |

A is at or above B on every favourable cell at every horizon, and B carries the
*larger typical adverse excursion* at H20 and H50. C sits below both on the
favourable side and above both on the adverse side (median MAE 2.70R / 6.06R).

### 6.5 Disclosed half-window split (descriptive, not a second test)

| Segment | Pop | n | H50 med MFE_R | H50 %≥1R | H100 med MFE_R | H100 %≥1R |
|---|---|---:|---:|---:|---:|---:|
| Jun–Aug | A | 20 | 3.49 | 100.0 | 6.66 | 100.0 |
| Jun–Aug | B | 15 | 2.82 | 80.0 | 5.41 | 86.7 |
| Sep–Nov | A | 34 | 4.82 | 88.2 | 5.97 | 87.9 |
| Sep–Nov | B | 73 | 2.89 | 82.2 | 4.85 | 90.4 |

The direction never inverts for the primary cell at H50; at H100 in the second
half the +1R rate is a coin-flip apart at this n, while the median MFE still
favours A. Reported for honesty; no threshold, no further slicing.

## 7. Interpretation rule (written before the run) and its result

The pre-registered rule, stated before the capture:

> Compare A and B at H50 and H100. If B's median MFE in R is **≥ 1.5 ×** A's
> **and** B's %MFE ≥ 1R is **≥ 10 pp** higher at **both** horizons, the gate is
> shown to cut a better class → `AMEND_CANDIDATE`. If B's median MFE is **no
> higher** and its %≥1R is **no higher** at both horizons → `HOLD_P2_FVG`.
> Anything else, or n_B below 30 → `INCONCLUSIVE`.

Result: at H50, B is 0.71× A's median MFE and 10.8 pp *lower* on %≥1R; at H100,
0.83× and 2.7 pp lower. Both horizons land in the HOLD branch.

```
INTERPRETATION: HOLD_P2_FVG
```

**Why, in one paragraph.** On the frozen six-month window the FVG-absent
near-miss episodes — which are BOS-confirmed and displace at least one ATR —
travel *less* favourably and *more* adversely than the episodes the full pillar
chain admits, from a first-fail anchor, at every horizon and at both tail
thresholds. The gate is not shown to be cutting off a better class of paths here;
if anything, the class it removes is the weaker one on excursion geometry. That is
a statement about *path geometry*, not about tradeability: neither arm was
simulated, neither carries a cost model, and no claim is made about whether
either arm could be entered, filled, or held.

Consequence, stated plainly: this leg produces **no** pillar, FVG, BOS or
threshold proposal, and none is authorized. The one signalling that warrants an
owner/Architect look is elsewhere — C (wick-only BOS breaks) shows the lowest
favourable excursion of any population, which is consistent with the gate doing
useful work there, not with loosening it.

## 8. What this does NOT show (binding on any reuse)

- **No trade simulation.** MFE/MAE are observed excursion from a first-fail
  anchor; there is no entry, no fill, no stop-first ordering, no BE stop, no
  costs, no Friday/portfolio intervention. A large MFE is not a takeable path.
- **Anchor asymmetry, disclosed.** A is anchored at the first PASS evaluation
  and B at the first *qualifying* fail — both are delayed relative to the
  structural event itself (the sweep/BOS), and A's gate chain can only pass
  *after* the same displacement evidence B is missing. The comparison therefore
  measures "what the market did after each class was decided", not "what each
  class could have traded".
- **Window and feed.** One instrument (XAUUSDm-resampled canonical M1), one
  broker feed, one six-month window. No second window, no second symbol, no
  walk-forward. n_A = 54, n_B = 88, n_C = 7 are episode counts, not independent
  trials, and no confidence interval is claimed.
- **Episode clustering is a measurement choice.** Per-TF clustering (headline)
  gives A/B/C = 54/88/7; the product's cross-TF rule (direction + overlap
  regardless of TF) gives 40/40/6 over 90 clusters. Both point the same way; the
  headline uses the per-TF convention because the research funnel counts per TF.
- **B is defined on the fail text and the displacement fields**, so it inherits
  any quirk of the prefix-attribution rule (`attribute_displacement` assigns the
  most recent same-direction sweep of the window). That is the production rule;
  the study does not correct it.
- **No "edge" language applies.** Nothing here is a rate, an expectancy, or a
  performance verdict, and the frozen product path was not altered by one line.

## 9. Artifacts

- Script: `06_RESEARCH/scripts/near_miss_p2_fvg_study.py` — `--capture` drives
  the frozen composition with two logging-only wrappers
  (`MultiTFProductRuntime.run_batch`, `DetectionDriver.validate_window`, both
  restored in `finally`); `--analyze-only` re-reads the saved capture and
  regenerates every table deterministically.
- Results (gitignored by convention): `06_RESEARCH/results/near_miss_p2_fvg/`
  — `summary.json` (banner, window, definitions, capture stats, integrity vs
  frozen 6m, populations, tables, interpretation, guard flags),
  `candidates.csv` (one row per episode-cluster anchor with every MFE/MAE cell),
  `events.jsonl.gz` (the raw 43,004 validation events),
  `capture_meta.json`, `capture.log`, and the composition's own
  `_funnel_capture/` artifacts.
- Re-run cost: ~15 minutes for the capture (2,979 batches), seconds for
  `--analyze-only`.

```
LEG1_STATUS: PASS
WINDOW: exec 2025-06-01 -> 2025-11-30 M5 (35,725 bars; M1 load from 2025-05-01)
N_A: 54  N_B: 88  N_C: 7
MEDIAN_MFE_H50_A: 4.04R
MEDIAN_MFE_H50_B: 2.85R
PCT_MFE_GE_1R_H50_A: 92.6%
PCT_MFE_GE_1R_H50_B: 81.8%
INTERPRETATION: HOLD_P2_FVG
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
SUITE: 1174 passed (re-run after this note; EXIT=0)
REPORT_PATH: 06_RESEARCH/NEAR_MISS_P2_FVG_COUNTERFACTUAL_REPORT.md
NEXT_READY: LEG 2 Architect ruling only
```
