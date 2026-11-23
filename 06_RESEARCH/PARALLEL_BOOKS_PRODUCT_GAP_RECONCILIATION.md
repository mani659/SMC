# PARALLEL BOOKS — PRODUCT-FILL GAP RECONCILIATION (post-R1) — 2026-11-23

**Status:** `PASS` — the reconciliation pass is complete: **56/56** missing product rows assigned
one mechanism bucket, **0 unexplained**, **0 data gaps**.
**Not implied:** the product-superset *gate* is not passed. This note explains the gap; it does
not close it, and it does not authorise ignoring it.
**Authority:** `PARALLEL_BOOKS_S3_REBASELINE_NOTE.md` §4 +
`06_RESEARCH/results/parallel_books_s3_rerun/verdict.json` (`product_anchor_losses`: 56 missing over 21/24 runs).
**Scope:** read-only artifact join. No replay, no strategy change, no threshold, no expectancy.
`pnl_net` in the source artifacts is accounting residue — **never a performance claim**.

---

## 1. Method

### 1.1 Sources (no second product definition)

| Role | Path |
|---|---|
| Product anchor (the exact file the year harness compared against) | `06_RESEARCH/results/product_1y_one_story/run1/<seg>/trades.csv` |
| Multi-book post-R1 flows | `06_RESEARCH/results/parallel_books_s3_rerun/<seg>/books_F-B-C-E-A_<hyp>/{fills.csv, winners.json, run_metrics.json}` |
| Pre-R1 evidence | `06_RESEARCH/results/parallel_books_full_bt/<seg>/books_F-B-C-E-A_<hyp>/fills.csv` |
| Reconciliation harness | `06_RESEARCH/scripts/product_gap_recon.py` (read-only) |
| Machine output | `06_RESEARCH/results/product_gap_recon/{missing_fills.csv, recon.json}` (gitignored results tree) |

### 1.2 Join key

The harness' own `fill_key`, i.e. exactly the key the year verdict used for
`missing_product_fills`:

```
(poi_id, trigger, entry_at, entry_price rounded 6dp, direction)
```

Key quality checks, all run before classification:

- **0 duplicate keys** across the 239 product anchor fills.
- Per-run missing counts reproduce the verdict table exactly (script fails loud otherwise).
- **56 run-level rows = 40 unique product fills.** Sixteen product fills are missing in both
  hypothesis runs of their segment (each segment's product book is compared once per hypothesis),
  so the run-level 56 and the unique 40 are both reported, never mixed.
- POI ids are segment-scoped in this project, so no cross-segment POI collision can join two
  different trades.

### 1.3 Buckets and precedence

One primary bucket per missing fill, first match wins:

| Bucket | Definition | Evidence used |
|---|---|---|
| **C** | R1 identity collapse / re-attribution: the exact executable plan `(direction, entry_price, entry_at)` **filled in the run under another POI/trigger/book**, or the exact product key existed pre-R1 and not post-R1 | plan index over the run's own fills; pre-R1 fills |
| **B** | Story substitution: the same POI traded in the run under a **different trigger** (product trigger's plan itself never filled) | same-POI fills with a different trigger |
| **A** | Never admitted: the POI has **no menu winner at all** in the run | winners.json |
| **F** | Route emitted, no fill: the product `(poi, trigger)` is a menu winner but **no fill of that trigger exists anywhere in the run** | winners.json vs fills.csv |
| **G** | Unjoinable / unexplained | — |

D (shared risk) is **not assigned per fill**: the runner exports blocked reasons only as run
counters (`blocked_by_reason`, `blocked_by_book`), so there is no per-fill join. It is recorded
as a run-level co-factor (§5.2), not as a row bucket.

---

## 2. Result

### 2.1 Bucket totals

| Bucket | Run-level (56) | Unique product fills (40) | Share (run-level) |
|---|---:|---:|---:|
| **C** — R1 identity / re-attribution | **9** | 6 | 16.1% |
| **B** — same POI, different trigger traded | **24** | 16 | 42.9% |
| **A** — never admitted | **0** | 0 | 0% |
| **D** — shared risk (per-fill) | **0** (unattributable, §5.2) | 0 | — |
| **E** — segment tiling / boundary | **0** | 0 | 0% |
| **F** — routed, no fill of that trigger | **23** | 18 | 41.1% |
| **G** — unjoinable / unexplained | **0** | 0 | 0% |
| **Total** | **56** | **40** | 100% |

Missing fills by product trigger: **F 46 / A 10** — the same F-heavy mix as the product book
(226/239 fills are trigger F), i.e. the gap is not concentrated in an exotic trigger.

### 2.2 Per run

| Run | Missing | C | B | F | | Run | Missing | C | B | F |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|
| nov24/LONG | 4 | – | 4 | – | | jun25/LONG | 2 | – | 1 | 1 |
| nov24/SHORT | 4 | 1 | 2 | 1 | | jun25/SHORT | 2 | – | 1 | 1 |
| dec24/LONG | 2 | – | – | 2 | | jul25/LONG | 2 | – | – | 2 |
| feb25/LONG | 4 | 1 | 2 | 1 | | jul25/SHORT | 6 | – | 2 | 4 |
| feb25/SHORT | 6 | – | 4 | 2 | | aug25/LONG | 2 | – | 1 | 1 |
| mar25/LONG | 1 | 1 | – | – | | aug25/SHORT | 1 | – | 1 | – |
| mar25/SHORT | 1 | 1 | – | – | | sep25/LONG | 2 | 2 | – | – |
| apr25/LONG | 1 | – | – | 1 | | sep25/SHORT | 1 | 1 | – | – |
| apr25/SHORT | 1 | – | – | 1 | | oct25/LONG | 2 | – | 2 | – |
| may25/LONG | 5 | 1 | 1 | 3 | | oct25/SHORT | 4 | – | 2 | 2 |
| may25/SHORT | 3 | 1 | 1 | 1 | | **Total** | **56** | **9** | **24** | **23** |

`dec24/SHORT`, `jan25/LONG`, `jan25/SHORT` have zero missing product fills (as in the verdict).

---

## 3. Bucket C — R1 identity collapse / re-attribution (9)

The product fill was **reproduced economically**; its key moved because R1 arbitrates on
`(direction, entry limit)` across books, not on `(poi, trigger)`.

| Run | Product fill | Reproduced as | Note |
|---|---|---|---|
| mar25/LONG + mar25/SHORT | `poi-004482` F short 2025-03-06 14:05 @2905.155 | `poi-004611` **E** same plan | one of the 4 R1 collision groups; pre-R1 present |
| feb25/LONG | `poi-025011` F @2934.115 | `poi-024233` **F** same plan | same book, different POI id |
| may25/LONG + may25/SHORT | `poi-023540` A @3308.698 | `poi-004802` **A** same plan | |
| sep25/LONG + sep25/SHORT | `poi-010774` A @3624.755 | `poi-009443` **A** same plan | |
| sep25/LONG | `poi-020771` A @3654.875 | `poi-020089` **A** same plan | |
| nov24/SHORT | `poi-011898` F 2024-11-26 01:00 @2624.128 | pre-R1 only | admitted pre-R1, no route at all post-R1 → R1 admission suppression |

8 of the 9 have an exact same-plan fill in the same run (direction + limit + instant); the ninth
is present in the pre-R1 baseline and absent post-R1 with no route. These are **not lost flow** —
they are the same plan under a different attribution, or an R1 collapse. They cannot be counted
as "extra" multi-book flow either: the plan is one plan.

---

## 4. Bucket B — same POI traded under a different trigger (24)

For every one of these 24 rows:

- the product `(poi, trigger)` **was routed** (menu winner) — no availability failure;
- **no fill of that trigger exists anywhere in the run**;
- the same POI **did fill under a different trigger, in a different book** (24/24 cross-book, 0/24
  same-book);
- no same-plan re-attribution applies (else it would be bucket C).

Example: `nov24/LONG poi-013705` F short 2024-11-15 06:05 @2559.595. The run routed both
`F@F` and `B@B` on that POI at the same sweep; only **B** filled (06:35 @2559.021). The product
F plan never filled in the multi-book timeline.

Reading: the multi-book book set proposes several trigger stories on one POI and its shared
envelope/concurrency lets one of them reach price first; the product's single-menu row is then
represented by a sibling story, not by its own key. This is a **design consequence of parallel
books**, not a tag/tier/admission loss.

---

## 5. Bucket F — route emitted, no fill (23)

Every F row satisfies: `(poi, trigger)` **is** a menu winner, and **no fill of that trigger**
appears in the run, and no other trigger filled on that POI either. The route existed; the
multi-book activation path did not convert it into a fill.

### 5.1 Order-level co-factor (run counts, not per fill)

Across the 24 post-R1 runs: **1,508 orders placed → 1,444 fills = 64 placed-but-unfilled
orders**, the same order of magnitude as the 56-row gap. In the same runs the menu emitted 4,508
winners, of which 2,588 were dropped at intake as duplicate stories (`duplicate_story_menu`) and
429 entries were risk-blocked. So "winner → order → fill" is already lossy by design in this
harness; the missing product fills sit inside that lossy seam.

### 5.2 Shared risk (D) — measured only at run level

Post-R1 shared-risk counters over 24 runs: `circuit_breaker 198`, `session 199`,
`skip_place_far_from_zone 17`, `same_level 15` (`shared_risk_skips_by_book` gives A/B/C/E/F
attribution for the first three; `skip_place_far_from_zone` is unattributed in the runner).
Every one of the 21 gap runs has non-zero blocked entries, so shared risk is a plausible
**co-factor** inside bucket F — but the artifacts contain no per-entry block log, so it is **not**
assigned per fill. Claiming per-fill D counts would be invention.

---

## 6. Ruled out

| Bucket | Count | Why it is zero |
|---|---:|---|
| **A** never admitted | 0 | 55/56 missing rows had a winner for their POI; the single exception (`nov24/SHORT poi-011898`) is absent post-R1 *and* present pre-R1 → R1 suppression, assigned to C. `poi_outside_books = 0` in every run. |
| **E** segment tiling / boundary | 0 | All 56 entries fall inside their own segment's calendar month (checked); no missing row is an open-at-cut or adjacent-segment artifact. |
| **G** unjoinable | 0 | Every row resolved to C, B or F with recorded evidence. |
| **D** per fill | 0 (not assignable) | No per-entry block log in the artifacts; see §5.2. |

---

## 7. Can multi-book claim product-superset under the current design?

**No.** Under the locked design the multi-book replay is not a per-key superset of the product
book, and it cannot become one without disabling locked behaviour:

1. **R1 identity is coarser than the product key.** R1 collapses plans on `(direction, entry
   limit)` across books, so a product row can be traded as a sibling key (9 rows, bucket C). That
   is the intended fix, not a defect — but it means exact product-fill identity is the wrong gate.
2. **Parallel books deliberately route competing stories on one POI.** An alternative trigger's
   plan on the same POI can reach price first, and the product's key is then absent even though
   the POI traded (24 rows, bucket B).
3. **Shared risk and the story gate make the flow lossy before fills.** 2,588 story drops and 429
   risk blocks over the year, with 64 placed-but-unfilled orders (§5.1); a handful of product
   rows necessarily sit in that seam (23 rows, bucket F).

Bucket A = 0, B/C/F leave no unexplained residue and no admission loss. The honest formulation is
**flow containment, not key containment**: multi-book covers the same POI/plan space but not every
exact product fill row. That is an Architect re-ruling question (gate definition), not a bug to
paper over and not something this note closes.

---

## 8. Explicit statements

```text
PROD_DEFAULTS_CHANGED: NO
  - config/live_demo.json has no parallel_books key -> () (single menu).
  - No installer/live multi-book default. No locked_constants edit. No 04_SRC change.
REPLAY: NONE (read-only join of existing artifacts; no full-year or partial re-run).
DIAGNOSTIC_PNL: NOT PERFORMANCE (accounting residue only; no expectancy/edge claim).
PRODUCT_GAP: EXPLAINED (56/56 rows bucketed), NOT CLOSED — superset gate stays OPEN
  pending Architect ruling on the gate definition (§7).
```

---

## 9. Return block

```text
GAP_RECON_STATUS: PASS (56/56 rows explained, 0 unexplained; product gate still OPEN)
MISSING_N: 56 run-level = 40 unique product fills (239 anchor fills, 21/24 runs)
BUCKETS: {A:0, B:24, C:9, D:0 (per-fill unassignable; run-level co-factor), E:0, F:23, G:0}
  unique-fill view: {A:0, B:16, C:6, F:18, G:0}
JOIN_KEY: (poi_id, trigger, entry_at, entry_price@6dp, direction) — harness fill_key; 0 dup keys
SUPERSET_FEASIBLE: NO — R1 collapses product keys by (direction, entry limit), parallel books
  trade sibling stories on the same POI, and the shared story/risk seam drops plans before
  fills; per-key product identity is unattainable without disabling locked behaviour.
SUITE: unchanged (read-only harness script + docs; tests not rerun this turn)
LOCKED_CONSTANTS_DIFF: empty
NOTE_PATH: 06_RESEARCH/PARALLEL_BOOKS_PRODUCT_GAP_RECONCILIATION.md
HANDOFF_UPDATED: YES
NEXT_READY: Architect review → entry quality F&B / paper as ruled
```
