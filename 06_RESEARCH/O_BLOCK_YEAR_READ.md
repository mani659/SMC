# O-BLOCK YEAR RE-READ (P2) — PRE-REGISTRATION + RESULTS

**Date:** 2026-11-24 · **Status:** see return block · **`LOGIC_CHANGED: NO`**
**Scope:** measurement and documentation only. Read-only against S3 / entry-quality / product_1y
artifacts and the canonical M1 parquet.
**Standing inputs:** P0 `SUPERSET_OPEN_BOOK_SCOPE_ONLY` (book findings are book-scoped, never
product claims); P1 PASS (root pytest + summary gap closed).
**Authority for each decision:** the dated ruling note that locked it — `OPEN_DECISION_O1_C3_BOUNDARY_ANATOMY.md`,
`OPEN_DECISION_O2_HTF_SWEEP_STAGE.md`, `OPEN_DECISION_O3_MULTI_ZONE_PRIORITY.md`,
`OPEN_DECISION_O4_SL_MAE_BENCHMARK.md`, `OPEN_DECISION_O5_TP_STRUCTURAL_VS_FALLBACK.md`, and the
binding register `OPEN_DECISIONS_RESEARCH_AGENDA.md`.

**What this pack is not:** it does not reopen O1–O5, propose a change, rank books, or read PnL.
The only permitted labels are `STANDS`, `INPUTS_CHANGED`, `UNDERDETERMINED`.

---

## 0. METHOD NOTE — written before any table was computed

Two rules governed this pack and are stated here so they cannot be adjusted after the fact:

1. **Each O-item is recomputed with its own original operational definition, verbatim.** Where the
   original pack pre-registered an edge, a ratio, a path convention or a bucket, that value is used
   unchanged. No new threshold is introduced into any product rule; no bucket edge is retuned.
2. **If a needed input is not on disk at year scale, the O-item is `UNDERDETERMINED`.** No proxy is
   substituted, no rule is re-derived from a different column, and no missing field is inferred.
   This is the failure mode the pack exists to prevent (the alternative — a redefined join that
   merely looks like the original — is how a "re-read" silently becomes a new study).

### 0.1 Population

The year universe is the **post-R1 S3 multi-book census actually on disk**
(`06_RESEARCH/results/parallel_books_s3_rerun/`): 24 runs (12 month segments × 2 direction
hypotheses), books F, B, C, E, A (D excluded by R-K).

| Quantity | Value | Source |
|---|---|---|
| Fills (unique union) | **986** (F 351 · B 241 · C 185 · E 156 · A 53) | `verdict.json` `fills_union` / `fills_by_book` |
| Routes (C3 evaluations, unique union) | **3,765** (F 1,129 · B 840 · C 795 · E 646 · A 355) | `verdict.json` `routes_union` / `routes_by_book` |
| Runs present | 24 / 24 | `verdict.json` `runs_present` |
| Segments | 12 adjacent calendar months, exec 2024-11-01 → 2025-10-31 UTC | `verdict.json` `window` |

**Segment tiling, stated honestly:** the year is 12 adjacent month segments, each with fresh menu
state (a continuous year replay is documented infeasible, `PRODUCT_1Y` §1.1). Therefore **armed
counts and winners are not summable across segments** — only fill/route *identities* (unique
timestamp events) are. Nothing in this pack adds armed counts together, and no "year armed total"
is quoted. The secondary population (`product_1y_one_story`, product path) carries 3,731 armed POI
records across the same 12 segments; that number is a row count of 12 separate runs, not a year
armed figure.

The original O1–O5 packs measured the **product path** in one October window (n = 11 fills, 441
armed, 149 routes). Two populations are therefore reported where the data allows:
**PRIMARY = the S3 book census (book-scoped, P0)**, and a labelled **SECONDARY = product_1y
product-path census (239 fills)** used only to show whether the *product* population moved.

### 0.2 Materiality rule (reporting only, never a product threshold)

`INPUTS_CHANGED` requires a pre-declared materiality rule, otherwise the label is a mood. The rule
below is a **reporting** rule over the ruled statistic; it changes no code, no gate and no constant,
and it is not a lock input:

- **O4:** `INPUTS_CHANGED` if the median SL distance or median MAE moves **≥ 25 % relative** to the
  ruled value, or the MAE ≤ 30-pip share moves **≥ 10 percentage points**.
- **O5:** `INPUTS_CHANGED` if the fallback share moves **≥ 25 % relative** to the ruled 27.3 %.

Both rules are anchored to the ruled numbers themselves (which are the pack's own inputs), so they
are not new thresholds in the product sense. Every comparison is printed with numerator and
denominator.

---

## 1. PRE-REGISTERED DEFINITIONS (per O-item, verbatim from the ruling)

### O1 — C3 reject / boundary anatomy

| Item | Pre-registered content |
|---|---|
| Original decision | **`KEEP_STATUS_QUO`** — agenda criterion: *"Keep status quo (no new path) if far/never-touched rejects dominate and edge-adjacent rejects are a negligible share."* |
| Original n / statistic | 149 C3 evaluations → **137 rejects (91.9 %)**; B1 EDGE_NEAR (≤ 0.25 ATR) 2 (1.5 %), B2 EDGE_WIDE (0.25–1.0 ATR) 2 (1.5 %), **B3 FAR (> 1.0 ATR) 133 (97.1 %)**, B4 touch-but-close-out 1 (0.7 %); median outside distance **35.9 ATR**; resting limit inside zone 112/137 |
| Operational definition to recompute | Per `not_in_between` reject: signed distance from the nearest zone edge ÷ **ATR at completion**, bucketed at the pack's own pre-registered edges (0.25, 1.0 ATR); B4 = completion bar **range** overlaps the zone while its **close** does not |
| Numerator / denominator | rejects in bucket / all C3 rejects (and all C3 evaluations) |
| Supplying artifact | per-reject ledger with `zone_low`, `zone_high`, completion close, ATR at completion, direction, trigger |
| Year-scale availability | **none.** S3 exports *fills* only (`trades.csv`, `fills.csv`); `verdict.json` carries route **counts** (3,765) with no geometry; `open_decisions/o1_c3_boundary/rejects.csv` is the October-only ledger of the original pack. Route = C3 evaluation, fill ≠ reject, so rejects cannot be recovered by subtraction |
| Verdict path | `UNDERDETERMINED` unless a year-scale per-reject ledger exists |

### O2 — HTF sweep: hard stage vs upstream-only

| Item | Pre-registered content |
|---|---|
| Original decision | **`KEEP_UPSTREAM_ONLY`** — agenda criterion: *"Keep upstream-only unless sweep-poor POIs are consistently and materially worse across both a route-rate and a path metric, with sufficient n … and only if the same measurement reproduces on a second window."* |
| Original n / statistic | 441 armed → **S+ 369 (83.7 %) / S− 72 (16.3 %)**; route rate **29.3 % vs 31.9 %**; pass-C3 12/108 vs 0/23; fills 11 vs 0; J2 loose 29.1 % vs 33.3 % |
| Operational definition to recompute | **J1 exactly as pre-registered:** same-direction Stage-0 sweep (BSL→short, SSL→long) whose level lies inside `[zone_low, zone_high]` on the POI's detection TF, sweep candle time ≤ arm time. Sweeps computed once on the maximal closed-bar series per TF, then time-filtered per arm (no lookahead) |
| Numerator / denominator | routed (or filled) arms in cohort / arms in cohort |
| Supplying artifact | per-armed-POI row with zone bounds, detection TF, **direction**, **arm timestamp**, routed/filled flag |
| Year-scale availability | partial: `product_1y_one_story/run1/<seg>/armed_records.json` gives 3,731 armed rows (12 segments) with zone bounds, `detection_tf` and `routed`/`entry` — but **no direction field and no arm timestamp** (only `armed_bar`, an index whose series binding is not recorded in the committed artifact). J1 is *defined* by direction (BSL→short / SSL→long) and by `candle time ≤ arm time`; both keys are missing |
| Verdict path | `UNDERDETERMINED` — the join cannot be formed verbatim, and inferring direction or arm time would be inventing the rule |

### O3 — Multi-zone priority

| Item | Pre-registered content |
|---|---|
| Original decision | **`KEEP_FIRST_ARMED_STATUS_QUO`** — agenda criterion: *"Keep first-armed if cluster outcomes are indistinguishable across rules or n is too small to separate them."* |
| Original n / statistic | 441 arms → 5 price-overlap clusters containing **441 (100 %)** arms (largest 271); CF1/CF2/CF3 each retained **0 of 11 fills**; same-batch view: 3 clusters / 6 arms / 0 same-direction pairs / 3 opposite-direction M15 pairs, dropping them retained 11/11 |
| Operational definition to recompute | Pre-registered overlap: **opposite direction + ranges intersect OR same direction + intersection / min(height) ≥ 0.50**; TF order D1 > H4 > H1 > M15; counterfactuals CF1 highest TF, CF2 tightest zone, CF3 earliest arm, fills carried per `poi_id` |
| Numerator / denominator | arms inside clusters / arms; fills kept / fills (11 originally) |
| Supplying artifact | per-arm zone bounds, TF, **direction**, arm batch/order, fill identity |
| Year-scale availability | zone bounds, TF and fill identity exist (`armed_records.json` + `trades.csv`), but **direction is absent** from the year armed ledger. The pre-registered relation branches on direction, so applying it would require inventing the direction of every non-filled arm. (The original pack's own DATA_GAP — no episode death time — would also persist) |
| Verdict path | `UNDERDETERMINED` |

### O4 — SL / MAE vs the ~30-pip benchmark

| Item | Pre-registered content |
|---|---|
| Original decision | **`KEEP_ATR_PRODUCT`** — agenda criterion: *"Keep ATR buffer unless a benchmark-distance analysis shows a consistent, reproducible pattern with enough n to state a rule."* |
| Original n / statistic | n = 11 fills; median SL **71.4 pips** (p25 61.1 / p75 79.1, min 32.7, max 120.5); median MAE **78.1 pips**; **MAE ≤ 30 pips 1/11 (9.1 %)**; **SL ≤ 30 pips 0/11**; clean stops 8/11 (72.7 %); median MAE ÷ SL **1.18** |
| Operational definition to recompute | **1 pip = 0.10 price; 30 pips = 3.00.** SL from **`original_sl`** (placement stop), never the BE-modified working `sl`. Path = entry bar → exit bar **inclusive**; LONG MAE = max(0, entry − min low), MFE = max(0, max high − entry); SHORT mirrored. Clean stop = stop-like `close_kind` **and** \|exit − `original_sl`\| ≤ 0.05. MAE includes the whole entry bar (overstates, never understates) |
| Numerator / denominator | fills with MAE ≤ 30 pips / fills; fills with SL ≤ 30 pips / fills |
| Supplying artifact | `trades.csv` (`entry_price`, `original_sl`, `exit_price`, `exit_bar`, `close_kind`) + M1 path |
| Path source note | the canonical M1 parquet is used instead of the pack's M5 slice. This **cannot change** MAE/MFE: both are `min low` / `max high` over the same interval, and the minimum of M1 lows over an interval equals the minimum of its M5 lows. Only the *bar at which* the extreme occurs would differ, which O4 does not use |
| Verdict path | computed on PRIMARY (S3, F like-for-like + pooled) and SECONDARY (product_1y) |

### O5 — TP: structural swing vs 4×ATR fallback

| Item | Pre-registered content |
|---|---|
| Original decision | **`KEEP_DUAL_TP_POLICY`** — agenda criterion: *"Keep the current rule (structural first, fallback otherwise) unless a reproducible measurement shows the structural branch is systematically wrong-sided or the fallback is demonstrably better on path quality."* |
| Original n / statistic | n = 11 fills → **structural 8 (72.7 %) / fallback 3 (27.3 %)**; hit TP **3/8 (37.5 %)** vs **0/3 (0.0 %)**; median `tp_dist` 6.11 vs 25.13; TP ÷ R **0.91 vs 3.52**; `mfe ÷ tp` **0.62 vs 0.22** |
| Operational definition to recompute | `tp_source` **read from the export only** (never inferred); `hit_tp` = `close_kind == take_profit` **or** \|exit − tp\| ≤ 0.05; `tp_dist` = \|tp − entry\|; R = \|entry − `original_sl`\|; TP ÷ R = `tp_dist` / R; `mfe ÷ tp_dist` from the same path as O4 |
| Numerator / denominator | fills by source / fills; TP hits in source / fills in source |
| Supplying artifact | `trades.csv` `tp_source`, `tp`, `entry_price`, `original_sl`, `exit_price`, `close_kind` |
| Verdict path | computed on PRIMARY (S3, F like-for-like + pooled) and SECONDARY (product_1y) |

---

## 2. RESULTS

**Script:** `06_RESEARCH/scripts/o_block_year_read.py` (read-only; deterministic, rerun md5-stable)
**Artifacts:** `06_RESEARCH/results/o_block_year_read/` (`summary.json`, `o4_o5_fills_s3.csv`,
`o4_o5_fills_product.csv`; results tree gitignored)

**Population reconciliation (done before any table):** S3 union **986** = `verdict.json`
`fills_union` exactly, per book F 351 · B 241 · C 185 · E 156 · A 53; product_1y **239** fills.
Route and fill identities are unique events; **no armed count is summed across segments**.

### 2.0 One measurement correction, recorded because it preceded any published number

The first pass used the O4 window as `[entry_at, exit_at]` on M1 data and produced a physical
impossibility: 87.9 % of stop-outs exited at their placement stop while the median stop-out's MAE
was **below** its own stop distance. Diagnosis: S3/product trade stamps are **M5 bucket opens**, so
a stop hit inside its entry bar is stamped `entry_at == exit_at` and the adverse extreme lives in
`[exit_at, exit_at + 5 min)`. The window is now the full exit bar (O4's own "exit bar inclusive"
read on M1). Validation after the fix: **0 / 566** clean stop-outs have MAE < their stop distance,
median \|MAE − stop\| 10.7 pips (positive by the documented whole-entry-bar convention), and the
F-book median stop in ATR (**1.16**) reproduces the audit's independent F risk/ATR (**1.16**).
No figure below comes from the uncorrected window.

### 2.1 O4 — SL / MAE vs the ~30-pip benchmark

| Population | n | median SL (pips) | median MAE (pips) | MAE ≤ 30 | SL ≤ 30 | clean stops | median MAE ÷ SL | median SL (ATR) |
|---|---|---|---|---|---|---|---|---|
| **RULED (Oct 2025)** | **11** | **71.4** | **78.1** | **1/11 (9.1 %)** | **0/11 (0 %)** | 8/11 (72.7 %) | 1.18 | not carried in the ruled artifact |
| S3 all books | 986 | **21.5** (p25 12.0 / p75 40.5) | 21.4 | 618/986 (62.7 %) | 623/986 (63.2 %) | 566/986 (57.4 %) — **566/644 (87.9 %) of stop-outs** | 1.13 | 1.63 |
| S3 F only | 351 | 19.6 (11.9 / 36.4) | 27.2 | 194/351 (55.3 %) | 242/351 (68.9 %) | 229/351 (65.2 %) | 1.30 | 1.16 |
| S3 B only | 241 | 40.6 (24.8 / 63.4) | 28.1 | 131/241 (54.4 %) | 80/241 (33.2 %) | 108/241 (44.8 %) | 0.77 | 2.90 |
| product_1y (product path) | 239 | 20.4 (13.3 / 37.6) | 26.2 | 130/239 (54.4 %) | 159/239 (66.5 %) | 154/239 (64.4 %) | 1.25 | 1.19 |

Exits: S3 644 stop-loss / 340 take-profit / 2 Friday-EOD; product_1y 174 / 65.

**O4 label: `INPUTS_CHANGED`.** By the pre-registered rule (median SL or MAE moving ≥ 25 %
relative, or the MAE ≤ 30 share moving ≥ 10 pp): median SL **71.4 → 20.4–21.5 pips (−70 % to
−71 %)**, SL ≤ 30 pips **0/11 (0 %) → 63–69 %**, MAE ≤ 30 pips **9.1 % → 54–63 %**. The ruled
premise — *"product stops are wider than the benchmark, everywhere; 30 pips is tighter than path
noise on 10/11 trades"* — does not describe the year population, where the benchmark is **wider**
than the median stop on two thirds of fills.

Two qualifications that belong in the same sentence, because they stop the label being over-read:

1. **The relative geometry is unchanged.** Median MAE ÷ SL is **1.13** (all) / **1.30** (F) /
   **1.25** (product path) against the ruled **1.18**, and 87.9 % of year stop-outs exit at their
   placement stop (8/8 in October). The ATR-buffer stop still sits where the path died.
2. **The pip statistic is not scale-invariant.** The year census spans entries from ~2,600 to
   ~4,000 while the October window sat near 4,000, and the stop in ATR units (1.16 F) equals the
   October book's own ATR multiple. The absolute−price movement accounts for part of the pip drop;
   this pack does not decompose it further and does not re-price any stop.

### 2.2 O5 — TP: structural swing vs 4×ATR fallback

| Population | n | structural | fallback | hit TP structural | hit TP fallback | median `tp_dist` S / F | median TP ÷ R S / F | median `mfe ÷ tp` S / F |
|---|---|---|---|---|---|---|---|---|
| **RULED (Oct 2025)** | **11** | 8 (72.7 %) | 3 (27.3 %) | 3/8 (37.5 %) | 0/3 (0 %) | 6.11 / 25.13 | 0.91 / 3.52 | 0.62 / 0.22 |
| S3 all books | 986 | 764 (77.5 %) | **222 (22.5 %)** | 317/764 (41.5 %) | 23/222 (10.4 %) | 1.50 / 5.37 | 0.72 / 2.46 | 1.11 / 0.28 |
| S3 F only | 351 | 222 (63.2 %) | **129 (36.8 %)** | 86/222 (38.7 %) | 5/129 (3.9 %) | 1.71 / 6.32 | 0.85 / 3.16 | 1.03 / 0.14 |
| S3 B only | 241 | 232 (96.3 %) | 9 (3.7 %) | 110/232 (47.4 %) | 1/9 (11.1 %) | 2.08 / 4.02 | 0.53 / 1.58 | 1.07 / 0.20 |
| product_1y (product path) | 239 | 155 (64.9 %) | **84 (35.1 %)** | 62/155 (40.0 %) | 3/84 (3.6 %) | 1.82 / 6.84 | 0.86 / 2.99 | 1.07 / 0.14 |

Per-book fallback share: F 36.8 % (129/351) · B 3.7 % (9/241) · C 2.2 % (4/185) · E 30.1 %
(47/156) · A 62.3 % (33/53). `none` / `unknown` = **0** in every population.

**O5 label: `INPUTS_CHANGED`.** By the pre-registered rule (fallback share moving ≥ 25 % relative):
**27.3 % → 36.8 %** on the like-for-like F book (**+35 % relative**, 129/351) and **35.1 %** on the
product-path census (84/239, +28.6 %). The ruled 73/27 proportion does not describe the year
population. What the ruling actually tested is reproduced, not overturned: structural is still the
majority branch, sits near the target (TP ÷ R 0.85 vs ruled 0.91) and converts (38.7 % vs 37.5 %),
while the fallback is still a far target (3.16 R vs 3.52) that rarely converts (3.9 % vs 0 %).
Absolute `tp_dist` is smaller for the same reason as O4 §2.1(2) — lower price levels and ATR over
the year window — so only the ratios are compared like-for-like.

### 2.3 O1 — C3 reject / boundary anatomy

| Item | Ruled (Oct 2025) | Year-scale | Label |
|---|---|---|---|
| C3 evaluations | 149 | **3,765 routes** (`verdict.json`) | — |
| `not_in_between` rejects | 137 (91.9 %) | **not measurable** | — |
| B1/B2/B3/B4 bucket shares | 1.5 / 1.5 / 97.1 / 0.7 % | **not measurable** | — |

**O1 label: `UNDERDETERMINED`.** The definition is fully recoverable (§1) but its inputs are not on
disk at year scale: the S3 census exports **fills** (`trades.csv` / `fills.csv`) and route
**counts** only, with no per-reject row carrying zone bounds, completion close and ATR at
completion. `open_decisions/o1_c3_boundary/rejects.csv` is the October-only ledger. The gap between
3,765 routes and 986 fills (**2,779 identities**) is **not** a reject count — it also contains
risk blocks, story drops and quality drops (`blocked_by_reason` per run is breaker/session/far-from-
zone only) — so subtracting would invent the denominator. No proxy distance and no entry-price
substitute was computed.

### 2.4 O2 — HTF sweep: hard stage vs upstream-only

| Item | Ruled (Oct 2025) | Year-scale | Label |
|---|---|---|---|
| Armed POIs | 441 | 3,731 rows / 12 segments — **not summable**, not a year armed total | — |
| S+ / S− shares | 83.7 % / 16.3 % | **not measurable** (J1 keys absent) | — |
| Route rate S+ / S− | 29.3 % / 31.9 % | **not measurable** | — |

**O2 label: `UNDERDETERMINED`.** The year armed ledger
(`product_1y_one_story/run1/<seg>/armed_records.json`) carries zone bounds, `detection_tf`,
`routed` and `entry` — but **no direction and no arm timestamp** (only `armed_bar`, an index whose
series binding the committed artifact does not record). J1 is *defined* by direction (BSL→short,
SSL→long) **and** by `candle time ≤ arm time`; both keys are missing, so forming the cohort would
mean inferring the very fields the join tests. Armed counts are also menu-state per segment and are
deliberately not added together.

### 2.5 O3 — Multi-zone priority

| Item | Ruled (Oct 2025) | Year-scale | Label |
|---|---|---|---|
| Arms in overlap clusters | 441 / 441 (100 %), 5 clusters | **not measurable** | — |
| CF1/CF2/CF3 fills retained | 0 / 11 each | **not measurable** | — |

**O3 label: `UNDERDETERMINED`.** The pre-registered overlap relation branches on direction
(*opposite direction + intersect* **or** *same direction + ≥ 50 % overlap*), and the year armed
ledger carries **no direction** for any arm. Applying the relation without it would silently
replace the ruled rule with a different one (range intersection only). The original pack's
own DATA_GAP — no episode death time, so price overlap ≠ simultaneous conflict — would also persist
at year scale.

### 2.6 Summary table

| O-item | Original statistic (n=11 window) | Year statistic | Label |
|---|---|---|---|
| O1 | 137/149 rejects; B3 97.1 %; B1+B4 2.2 % | not measurable — no per-reject ledger | **UNDERDETERMINED** |
| O2 | S+ 369/S− 72; route 29.3 % vs 31.9 % | not measurable — no direction / arm timestamp | **UNDERDETERMINED** |
| O3 | 441/441 in clusters; CF fills 0/11 | not measurable — no direction in armed ledger | **UNDERDETERMINED** |
| O4 | median SL 71.4 pips; SL≤30 0/11; MAE≤30 9.1 % | median SL 20.4–21.5 pips; SL≤30 63–69 %; MAE≤30 54–63 % | **INPUTS_CHANGED** |
| O5 | fallback 27.3 % (3/11) | fallback 36.8 % (129/351) F · 35.1 % (84/239) product | **INPUTS_CHANGED** |

Every O-item carries exactly one of the three labels; no fourth label is used.

---

## 3. EXPLICIT NON-CLAIMS

1. **No decision is reopened, changed or promoted.** O1–O5 remain CLOSED with their 2026-11-14
   labels. `INPUTS_CHANGED` means the ruled *input statistic* does not describe the year population;
   it does not assert that the label was wrong, and it authorises nothing.
2. **Book-scoped, per P0 (`SUPERSET_OPEN_BOOK_SCOPE_ONLY`).** The S3 census is a multi-book research
   universe, not the product. B/C/E/A findings are book findings. The product-superset question
   remains **OPEN**; nothing here closes it, and the product-path numbers are a labelled secondary
   population, not a product claim.
3. **No threshold, gate, constant or default changed.** `04_SRC` untouched, `locked_constants.py`
   diff empty, `parallel_books` default `()` unchanged, D still out.
4. **No performance statement.** No expectancy, PF, R-multiple ranking, book comparison by PnL or
   edge claim. Diagnostic PnL in the artifacts was not read as an input; `hit_tp` and MAE/MFE are
   geometry, not returns.
5. **Segment tiling is not a year replay.** Armed/winners counts are per-segment menu state and are
   not additive; only fill/route identities are. No "year armed" figure is quoted anywhere.
6. **The 30-pip and 1:5 markers remain review benchmarks.** Nothing here proposes a pinned stop, a
   ratio lock, a TP model, a stop-reference change or a zone-quality metric — those are P3–P5 and
   each needs its own dated design.

---

## 4. RETURN BLOCK

```text
P2_STATUS: PASS
POPULATION: 986 S3 fills / 3,765 routes (parallel_books_s3_rerun/verdict.json) + 239 product_1y fills
O1: UNDERDETERMINED — no year-scale per-reject ledger (zone bounds + completion close + ATR)
O2: UNDERDETERMINED — year armed ledger has no direction and no arm timestamp (J1 keys)
O3: UNDERDETERMINED — year armed ledger has no direction; the overlap relation branches on it
O4: INPUTS_CHANGED — median SL 71.4 -> 20.4-21.5 pips; SL<=30 0/11 -> 63-69%; MAE<=30 9.1% -> 54-63% (MAE/SL 1.13-1.30 vs 1.18 preserved)
O5: INPUTS_CHANGED — fallback 27.3% -> 36.8% F (129/351) / 35.1% product (84/239); shape preserved (structural 0.85R, hit 38.7%)
NEW_THRESHOLDS: NO
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: P3 stop-reference definition lock
```

**Bans honoured:** no `04_SRC` logic edit, no `locked_constants` edit, no stop-reference / TP /
zone-quality implementation, no live or paper run, no `parallel_books` default change, no
"therefore change O4/O5" statement, no O1–O5 reopen, no expectancy/PF language.
