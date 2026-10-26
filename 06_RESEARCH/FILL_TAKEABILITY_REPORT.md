# FILL / TAKEABILITY STUDY (LEG 3) — WHEN A ROUTE IS PLACED, CAN THE MARKET FILL IT?

> **DIAGNOSTIC — NOT EDGE.**
> The primary window produced **4 placed orders / 3 fills / 1 expiry**; the
> 18-month secondary produced **14 placed / 14 fills**. Two windows are
> reported separately and never pooled. Counts of this size support no
> expectancy, win-rate, or profit-factor claim in either direction — and
> `FILL_PATH_HEALTHY` answers a conversion question, not a quality one. No
> gate was loosened, no threshold moved, no lifetime or re-anchor widened, no
> product decision path was touched, and nothing below authorizes a change.

**Date:** 2026-10-19 · **Authority:** Lead Architect owner plan
`00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md` **LEG 3**.
**FILL_TAKEABILITY_STATUS: PASS** — the capture reproduces the frozen 6m
composition byte-identically, every placement in both windows is accounted for
by exactly one fate, and the label is applied by the rule written before the
runs. **LABEL: `FILL_PATH_HEALTHY`** (basis: secondary, `F = 14/14`,
`X = 0/14`).
**Scope:** read-only measurement. `LOGIC_CHANGED: NO` — no `04_SRC/smc` decision
path edited, `locked_constants.py` diff **empty**, no pillar/P2/FVG/trigger
change, no expiry or `ZONE_REFINEMENT` widening, no multi-symbol, no ML.

---

## 1. Question and the pre-registered rule

LEG 1 killed the P2/FVG hypothesis as the *selection* problem (R-HOLD
`HOLD_P2_FVG`), and LEG 1's placement-side study found the placement gates
removed only paths the market never came back to touch. The remaining frequency
drag sits one step later: **ARM → ROUTE → PLACE → FILL**. When a route *is*
placed, how often would price have allowed a fill under the frozen fill model,
and what ends the orders that never fill?

The rule below was written into the owner plan **before** any run of this leg:

- the frozen **6m window is the primary basis**; if it has **< 10 placed
  orders** the **secondary window** is the basis; neither reaching 10 →
  `INCONCLUSIVE_LOW_N`. **Windows are never pooled.**
- the label uses only placed orders: `F = filled / placed`; `X` = share of
  placed orders that either touched only **after** the product lifetime ended
  **or** ended within **0.5 × ATR** of their limit at that moment.
- `FILL_PATH_HEALTHY` = `F ≥ 0.5 and X < 0.25`;
  `FILL_PATH_IS_BOTTLENECK` = `F < 0.5 and X ≥ 0.5`; otherwise `MIXED`.

## 2. Method (frozen before running)

| Item | Value |
|---|---|
| Primary window | M1 warm-up from **2025-05-01**; exec **2025-06-01 → 2025-11-30** M5 (**35,725** exec bars) — the frozen 6m product window used by Phase 3 / FR-4 / LEG 1 |
| Secondary window | M1 warm-up from **2023-11-01**; exec **2023-12-01 → 2025-05-31** M5 (**105,864** exec bars) — 18 months, wholly disjoint from the primary |
| Composition | `phase3_structure_funnel.run` **imported, not forked**, with the pilot's explicit `CostConfig` (commission 0.0 / slippage 1 pt / half-spread on / fallback 0.26) — identical to the frozen 6m refresh |
| Capture seam | logging-only class wraps, restored in `finally`: `BacktestRunner.__init__`, `PendingOrderBook.place` (every accepted placement, verbatim geometry), and the order book's `on_bar` / `fills` / `expire` / `poi_cancel` / `cancel_all` / `set_atr` / Friday / news hooks (lifecycle events only). Nothing is re-decided: the seam records what the frozen runner already did |
| Fill semantics | touch = fill **at the limit price** (inclusive), mirrored from `smc.backtest.fill_model` and test-cross-checked against it |
| Eligibility | placement runs at runner step 6 (after fills) → the placement bar is **never** fill-eligible: eligible bars are `placed_bar+1 .. placed_bar+rest_bars-2`, `rest_bars` taken from the order itself (`rest_bars_for(detection_tf, is_m8, M5)` or the R9 intent's own clock) — one rule for every placed row |
| Expiry ordering | expiry runs at step 3 of a later bar, before fills → an order whose last eligible bar is `k` cannot fill at `k+1`; fates are derived from the run's own expiry/cancel events, not assumed |
| Fates (exclusive) | `FILLED` / `TOUCHED_ONLY_AFTER_EXPIRY` / `NEVER_TOUCHED_IN_LIFE` / `CANCELLED_OTHER` (portfolio or POI cancel) / `TOUCHED_WHILE_LIVE_UNFILLED` (integrity anomaly, flagged not classified) / `DATA_GAP`. Missing SL or TP → `DATA_GAP`, never invented |
| Distance scale | ATR = the per-bar ATR the runner itself fed to its gates (`set_atr` seam), captured at placement; near-miss threshold **0.5 × ATR** |
| Counterfactual | sensitivity only: the same order given **+12 / +24 / +48** extra eligible bars, resolved stop-first on the frozen same-bar rule. **Not a proposal** |
| Runaway horizon | descriptive only: 400 M5 bars from placement, answering "did price ever come back", independent of the product lifetime |
| Route strand | routes deduped by `route_id`; every presentation's `blocked_by` taken from the runner's own `blocked_log` (delta-aligned to the candidate list, order-preserving); R9 intent lifecycle read from `IntentBook.events` |
| Unplaced geometry | a **separate population** (never enters the placed-order fates or the label): each unplaced route anchored on its **first presentation bar** with its own R8 lifetime, walked to its first touch, closest approach, and the +12/+24/+48 extensions |

Script: `06_RESEARCH/scripts/fill_takeability_study.py`
(`--capture` runs the composition under the seam; `--analyze-only` re-reads the
saved capture so every table reproduces without rerunning the capture —
verified **byte-identical** on both windows; `--combine` applies the
pre-registered basis rule).

### 2.1 Window re-pin (disclosed before any secondary result existed)

The secondary was first launched as a **24-month** window (2023-06-01 →
2025-05-31). The frozen composition's per-bar cost grows with the POI history
it has accumulated, so the run's bar rate fell from 74 to ~6 bars/s and the
full window projected to ~8 h. It was stopped at bar **62,000 / 141,403** with
**no summary written** — no fate, cause, median, or label had been computed or
seen (`secondary_24m_ABORTED.log` keeps the progress log). The secondary was
then **re-pinned to 18 months** (2023-12-01 → 2025-05-31) on the owner's
instruction, still before any secondary result existed. The re-pin is a
**window-length** decision made under a runtime constraint, not a choice
informed by fill outcomes; the primary/ secondary basis rule and the label
thresholds were unchanged, and the two windows are still never pooled.

## 3. Integrity (the seam changed nothing)

| Check | Result |
|---|---|
| `trades.csv` vs frozen 6m run | **byte-identical** (SHA-256 `2cd4e4f1c79fcaef…`) |
| `report.json` vs frozen 6m run | **byte-identical** (SHA-256 `b9516af739f7ae56…`) |
| Determinism | a second full capture (`primary_rerun/`) reproduced both files **byte-identically**; the analysis is a pure function of the saved capture |
| Funnel reproduced | 2,979 HTF batches / 43,004 merged POIs / 2,021 passed / **30 armed** / **10 routes** / **4 placed** / **3 fills** — exactly the frozen funnel |
| Placements captured vs runner | **4 / 4** |
| Terminal records captured vs placements | **4 / 4** — `unaccounted_placements: []`, `double_terminal: []` |
| Fill without a live touch | **0** (`fill_without_touch: 0`) |
| Blocked-log delta alignment | every presented candidate matched its block record or had none — the seam raises rather than guess |

## 4. Primary window — the placed-order census (4 rows)

| ticket | route_id | trig / TF | dir | limit | SL | TP | lifetime (bars) | placed bar | eligible window | bars used | fate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | poi-014146:F@5653 | F / D1 · M8 | short | 3281.298 | 3310.403 | 3271.862 | 43 (intent) | 5658 | 5659–5699 (41) | 1 | **FILLED** |
| 2 | poi-034151:F@13349 | F / H4 · M8 | long | 3376.625 | 3373.416 | 3380.275 | 34 (intent) | 13363 | 13364–13395 (32) | — | **TOUCHED_ONLY_AFTER_EXPIRY** |
| 3 | poi-047805:C@18278 | C / H4 · M8 | short | 3490.257 | 3493.985 | 3486.405 | 48 | 18278 | 18279–18324 (46) | 18 | **FILLED** |
| 4 | poi-073511:F@27542 | F / D1 · M8 | long | 4244.725 | 4177.035 | 4275.664 | 6 (intent) | 27584 | 27585–27588 (4) | 1 | **FILLED** |

Fate census: **`{FILLED: 3, TOUCHED_ONLY_AFTER_EXPIRY: 1}`** — no
`NEVER_TOUCHED_IN_LIFE`, no portfolio/POI cancel, no anomaly, no `DATA_GAP`.
The only non-fill expired by **§23** (`expired_section23`).

### 4.1 The one non-fill, in full

`poi-034151` is the whole of the primary's non-fill population:

- placed 13363 → first eligible bar 13364; the limit is missed by **0.744**
  price units = **0.156 × ATR** *on that very first eligible bar*;
- price then leaves, and the route expires by §23 at bar 13396 with the clock
  spent (32 eligible bars);
- price returns to the limit at bar **13684** — **289 bars after** expiry,
  **322 bars after** placement. Under the counterfactual extensions (+12 /
  +24 / +48) it **still does not fill**; it is not a "we were one bar short"
  case, it is a "the market came back a day and a half later" case.

### 4.2 Medians and the counterfactual (sensitivity, not a proposal)

| Median | Value |
|---|---|
| eligible bars granted | **36.5** |
| bars from placement to fill (filled rows) | **1** (1, 18, 1) |
| placed TP distance | **0.745 R** |
| closest approach while live | **0.0** (three fills at the limit; the non-fill 0.744) |
| bars from expiry to the first touch (the one non-fill) | **289** |

Counterfactual table (base = the 1 placed order that did not fill):

| extension | touched incrementally | % of non-filled touched | resolution |
|---|---|---|---|
| +12 bars | **0 / 1** | 0% | — |
| +24 bars | **0 / 1** | 0% | — |
| +48 bars | **0 / 1** | 0% | — |

**Reading:** on the primary window the clock is *not* what ends placements in a
recoverable way. Three of four placed orders fill within 1, 18 and 1 eligible
bars; the fourth missed by a sixth of an ATR on its first eligible bar and
then stayed away for ~1.5 days. Extending its life by 1–4× would have changed
nothing.

## 5. Route strand — where the 10 routes went

| Strand | Count |
|---|---|
| routed (deduped by `route_id`) | **10** (trigger F 9, C 1) |
| placed | **4** |
| filled | **3** |
| routes never placed | **6** |
| block events (runner `blocked_log`) | **18** = `skip_place_far_from_zone` **14** + `session` **4** |
| R9 intents | armed **7** · placed **3** · `intent_expired_no_reentry` **4** |

First-block census of the 6 never-placed routes: R7 far **4**
(`poi-008541`, `poi-022254`, `poi-068169`, `poi-068170`) · session **2**
(`poi-079448`, `poi-088517`). This is the same 18-event / 6-route picture LEG 1
reported, reproduced from a second, independent capture seam.

## 6. The unplaced routes — separate geometry population (not in the label)

Anchored at each route's **first presentation bar** with its own R8 lifetime:

| route_id | TF | limit | eligible bars | touched in life | closest approach | in ATR | first touch |
|---|---|---|---|---|---|---|---|
| poi-008541:F@3427 | H4 | 3404.848 | 46 | no | 16.643 | 5.75 | never (≤400) |
| poi-022254:F@8840 | H4 | 3332.625 | 46 | no | 2.823 | 1.96 | **+42 bars after the clock** |
| poi-068169:F@25650 | D1 | 3920.485 | 46 | no | 101.880 | 27.54 | never (≤400) |
| poi-068170:F@25650 | D1 | 3995.775 | 46 | no | 26.590 | 7.19 | never (≤400) |
| poi-079448:F@29701 | H4 | 4043.618 | 46 | no | 77.403 | 7.64 | never (≤400) |
| poi-088517:F@32994 | H1 | 4158.685 | 46 | no | 52.390 | 8.77 | never (≤400) |

**0 of 6** unplaced routes touched their own limit inside the lifetime they
would have been granted; median closest approach **39.49** price units
(**7.42 × ATR**). Only `poi-022254` touches at all, **42 bars after** its
clock — the LEG 1 lifetime-class exception, unchanged and still n = 1. Granting
+12 / +24 bars recovers **none** of the six.

## 7. Primary-window label basis

`n_placed = 4 < 10` → the primary window **cannot carry a directional label**
by the pre-registered rule, whatever its numbers look like. The secondary
window is therefore the label basis (see §8). For the record, the primary's
own cells are `F = 0.75`, `X = 0.25` — i.e. it would have landed in `MIXED`
on the letter of the rule, which is exactly why the `n ≥ 10` gate exists:
four orders cannot separate a clock cost from a coin flip.

## 8. Secondary window (18m) — the label basis

| Item | Value |
|---|---|
| Window | exec **2023-12-01 → 2025-05-31** M5 (**105,864** bars; M1 warm-up from 2023-11-01) |
| Funnel | 8,829 HTF batches / 137,685 merged / 6,626 passed / **81 armed** / **31 routes** / **14 placed** / **14 fills** |
| Runtime | 15,312.6 s capture; 131 lifecycle events |
| Fates | **`{FILLED: 14}`** — 0 expiries, 0 cancels, 0 anomalies, 0 `DATA_GAP` |
| Integrity | placements 14 / terminal records 14 · `unaccounted_placements: []` · `double_terminal: []` · `fill_without_touch: 0` |
| Blocked events | **61** = `skip_place_far_from_zone` **40** + `session` **21** (17 routes never placed; first reason R7 far 14, session 3) |
| R9 intents | armed **21** · placed **6** · `intent_expired_no_reentry` **12** · `dropped_portfolio_friday` **3** |

### 8.1 The 14 placed orders

| # | route_id | trig / TF | dir | lifetime (bars) | eligible bars | filled at bar | TP (R) |
|---|---|---|---|---|---|---|---|
| 1 | poi-000452:A@193 | A / H1 | long | 48 | 46 | **1** | 1.311 |
| 2 | poi-000454:A@193 | A / H1 | long | 36 | 34 | **1** | 1.311 |
| 3 | poi-000458:A@193 | A / D1 | long | 48 | 46 | **1** | 1.311 |
| 4 | poi-000461:A@193 | A / H4 | long | 48 | 46 | **1** | 1.311 |
| 5 | poi-052062:F@20285 | F / H4 | short | 48 | 46 | **1** | 0.408 |
| 6 | poi-052607:F@20472 | F / D1 | long | 48 | 46 | **5** | 1.919 |
| 7 | poi-059796:F@23150 | F / H4 | short | 48 | 46 | **1** | 2.904 |
| 8 | poi-080423:F@30700 | F / H1 | short | 21 | 19 | **1** | 0.227 |
| 9 | poi-118201:F@44406 | F / H1 | short | 48 | 46 | **1** | 3.481 |
| 10 | poi-136663:A@51137 | A / H1 | long | 48 | 46 | **24** | 3.271 |
| 11 | poi-155232:B@57652 | B / H1 | long | 48 | 46 | **1** | 1.000 |
| 12 | poi-220780:F@79944 | F / H4 | long | 46 | 44 | **1** | 2.100 |
| 13 | poi-231807:F@83668 | F / H1 | short | 48 | 46 | **1** | 0.326 |
| 14 | poi-253069:F@90947 | F / H1 | long | 48 | 46 | **1** | 2.790 |

Medians: **eligible bars 46** · **bars to fill 1** (12 of 14 at the first
eligible bar; the two exceptions at 5 and 24) · placed TP distance **1.311 R** ·
closest approach while live **0** (every order filled). Counterfactual
`n_base = 0` — there is no non-filled order to extend.

### 8.2 What happened after the fills (path only — NOT edge)

Exit mix on the 14 fills: **`{stop_loss: 8, take_profit: 6}`**, bars held 1–19.
That mix is reported for completeness and is **not** a profitability, win-rate
or expectancy claim: the passes are gross-path labels with no cost model, and
`FILL_PATH_HEALTHY` says only that placement converts to fill — half of these
fills went on to stop out.

### 8.3 Two caveats that qualify `n = 14`

- **Clustering.** The 14 orders come from **14 distinct POIs but only 11
distinct placement bars**; four of them (`poi-000452/454/458/461`) are armed at
the *same* H1 close on bar 193 and share identical geometry. The
pre-registered rule counts **placed orders**, so the label stands as defined —
but the effective independent-episode count is ~11, not 14. Disclosed, not
adjusted; no post-hoc de-duplication rule may be invented now.
- **Triggers differ from the primary.** This window carries `A` (5) and `B` (1)
as well as `F` (8); the primary carried only `F`/`C`. The 18m window is a
broader regime sample, which is exactly why pooling with the primary would be
wrong — and why the two are reported side by side, not summed.

## 9. Pre-registered label

```
FILL_TAKEABILITY_STATUS: PASS
BASIS: secondary (primary n_placed = 4 < 10)
F = 14/14 = 1.00        X = 0/14 = 0.00
LABEL: FILL_PATH_HEALTHY
  reason: F >= 0.50 and X < 0.25 — placed orders fill; the clock/proximity
          kills none of them.
```

The primary window does not contradict this: 3 of its 4 placements also filled,
and its single miss was a 0.156 × ATR miss on the first eligible bar followed by
a return **289 bars after** expiry — no extension up to +48 would have taken it.
Both windows agree on the direction of the answer even though only one of them
is allowed to carry the label.

### 9.1 Where the funnel actually loses volume

Reading the two windows side by side (never pooled):

| Stage | Primary (6m) | Secondary (18m) |
|---|---|---|
| merged POIs → passed validation | 2,021 / 43,004 = **4.7%** | 6,626 / 137,685 = **4.8%** |
| passed → armed | 30 / 2,021 = **1.5%** | 81 / 6,626 = **1.2%** |
| armed → routed | 10 / 30 = **33%** | 31 / 81 = **38%** |
| routed → placed | 4 / 10 = **40%** | 14 / 31 = **45%** |
| placed → filled | 3 / 4 = **75%** | 14 / 14 = **100%** |

On the fill question this is the whole finding: **PLACE → FILL is the least
lossy stage in the product.** The volume is lost much earlier (validation, and
passed → armed), where LEG 1 already measured the P2 kill at 87.77% and this
leg reproduces it at 4.7–4.8% surviving validation. No fill-model, lifetime or
gate change is indicated by this leg, and none is authorized.

## 10. Limitations (binding on any reuse)

- **`n = 14` placed (secondary) / 4 (primary)** — one instrument, one feed, two
  disjoint windows. Nothing here is a rate, an expectancy, or an edge; the
  exit mix in §8.2 is gross-path only.
- **Clustered placements** (§8.3): 14 orders sit on 11 placement bars, four of
  them one episode. The label is computed on orders because that is what the
  rule says; a reader must not mistake `14` for 14 independent setups.
- **`FILL_PATH_HEALTHY` is a statement about conversion, not quality.** 8 of
  the 14 secondary fills stopped out (6 reached TP). The label must never be
  quoted as support for "the entries are good".
- **A limit fill is modelled at the limit price** (the frozen lock), so the
  fill measurement cannot see queue position, partial fills, or slippage on
  entry — those are cost-model questions outside this leg.
- **Window length was re-pinned once** (§2.1) under a runtime constraint, with
  no results in hand; the 24-month run is disclosed as aborted. Any reuse must
  carry that sentence with it.
- **The secondary capture was not re-run** (4.25 h): capture-level
determinism is proven on the primary (§3). The secondary's *analysis* is
deterministic — re-running `--analyze-only` on the saved capture reproduced
`summary.json` and `orders_fate.csv` **byte-identically**.
- **`route_level_unplaced` is null on the secondary** — the route-geometry
  population (§6) is anchored to the primary's frozen 6m capture and is not
  extrapolated to the 18m window.
- Session/R7 blocks in the secondary are far more numerous (61 events) and are
  reported as counts only; this leg did not re-derive their counterfactuals.

## 11. Artifacts, governance, NEXT

- Script: `06_RESEARCH/scripts/fill_takeability_study.py` — `--capture`,
  `--analyze-only`, `--combine`; imports the frozen composition, forks nothing.
- Results (local-only, gitignored): `06_RESEARCH/results/fill_takeability/` —
  `summary.json` (primary), `orders_fate.csv` (primary, 4 rows),
  `summary_all.json` (the basis rule's output: `basis=secondary`),
  `capture_meta.json`, `events.jsonl.gz`, `primary_rerun/` (determinism),
  `secondary_18m/{summary.json,orders_fate.csv,capture_meta.json,events.jsonl.gz,_funnel_capture/}`,
  `secondary_18m.log`, `secondary_24m_ABORTED.log` (the disclosed aborted run),
  `_funnel_capture/` (the run's own funnel/trades/report artifacts).
- Tests: `04_SRC/tests/test_fill_takeability.py` (21: fill-model agreement,
  eligible-window arithmetic incl. the placement bar never being eligible,
  expiry-before-fill ordering, fate exclusivity and priority, near-miss ATR
  scaling, counterfactual window clamping, stop-first resolution, label
  branches incl. the `n < 10` gate and `X` boundary, banner/logic lock).
  Suite **1195 passed (EXIT=0)**.
- Governance: `LOGIC_CHANGED: NO` · `locked_constants.py` diff **empty** ·
  expiry/gate widening **NO** · multi-symbol **NO** · edge claim **NO**.

```
FILL_TAKEABILITY_STATUS: PASS
WINDOW_PRIMARY: 2025-06-01 -> 2025-11-30 M5 (35,725 bars; M1 warm-up from 2025-05-01)
WINDOW_SECONDARY: 2023-12-01 -> 2025-05-31 M5 (105,864 bars; M1 warm-up from 2023-11-01) [re-pinned from 24m, no results seen]
N_ARMED: 30 (primary) / 81 (secondary)
N_ROUTES: 10 / 31
N_PLACED: 4 / 14
N_FILLED: 3 / 14
FATES_PRIMARY: {FILLED: 3, TOUCHED_ONLY_AFTER_EXPIRY: 1}
FATES_SECONDARY: {FILLED: 14}
MEDIANS_PRIMARY: eligible 36.5 bars | bars_to_fill 1 | TP 0.745R | after-end touch 289 bars
MEDIANS_SECONDARY: eligible 46 bars | bars_to_fill 1 | TP 1.311R
COUNTERFACTUAL: primary +12/+24/+48 = 0/0/0 of 1 non-filled; secondary n_base 0
LABEL: FILL_PATH_HEALTHY (basis: secondary; F=1.00, X=0.00, n=14)
NOTE_PATH: 06_RESEARCH/FILL_TAKEABILITY_REPORT.md
SUITE: 1195 passed
LOCKED_CONSTANTS_DIFF: empty
LOGIC_CHANGED: NO
NEXT_READY: Architect ruling only — no gate, lifetime, fill-model or representation change is proposed by this leg
```
