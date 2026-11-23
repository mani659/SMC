# PARALLEL BOOKS — S3 RESEARCH RE-BASELINE (post-R1) — 2026-11-23

**Status:** PARTIAL — isolation PASS (double-lot 0, cross-tag leak NO); product-superset OPEN (53-run-equivalent gap residual remains).
**S2 admission:** F, B, C, E, A (D out) — `PARALLEL_BOOKS_S2_ADMISSION_RULING.md`.
**Identity in force:** Architect R1 (`same_cross_book_plan` = direction + entry limit).
**Scope:** research harness only. NOT live, NOT a threshold change, NOT expectancy.

> `pnl_net_sum_diagnostic` in every artifact is an accounting residue. **It is never a
> performance claim.** Nothing here says the strategy works.

---

## 1. Method — authoritative source

| Number | Source | Identity |
|---|---|---|
| Fill / route union by book (§2) | **Post-R1 rerun verdict** `parallel_books_s3_rerun/verdict.json` (24/24 runs, generated 2026-11-23T06:26:21Z, exit 1 = product gap only) | **post-R1 authoritative** |
| Double-lot / dedupe (§3) | Same post-R1 verdict | post-R1 authoritative |
| Product-fill gap (§4) | Same post-R1 verdict (`product_anchor_losses`) | post-R1 authoritative |
| Shared-risk skips (§5) | Same post-R1 verdict (`shared_risk_skips`, `shared_risk_skips_by_book`) | post-R1 authoritative; M-4 per-book attribution surfaced |
| Pre-R1 comparison (§2.1, §3) | Prior year verdict `parallel_books_full_bt/verdict.json` (24/24 runs, generated 2026-11-20T11:07Z) | pre-R1 reference only |

Post-R1 rerun: `06_RESEARCH/results/parallel_books_s3_rerun`, same product_1y window (exec 2024-11-01..2025-10-31, load 2024-09-01, 12 adjacent calendar-month segments x LONG/SHORT), same resume-`.done` rules, admitted set F,B,C,E,A. Runtime 164,006.6 s. `verdict.pass=false` solely because `checks.no_product_fill_lost=false`; all other checks PASS.

---

## 2. Authoritative fill / route union by book (post-R1)

24/24 runs present. Fills are unique-timestamp events and add across segments; route (winner) counts are unioned by `(segment, poi, trigger, sweep_ts)` and are **not** a year total of menu bookkeeping.

| Book | Fills | Routes | Long / Short fills | Detection TF mix | pnl_net_sum_diagnostic (residue, NOT performance) |
|---|---:|---:|---|---|---:|
| F | 351 | 1,129 | 184 / 167 | H4 53, M15 222, H1 64, D1 12 | -56.650977 |
| B | 241 | 840 | 127 / 114 | M15 152, H1 59, H4 30 | -23.233695 |
| C | 185 | 795 | 106 / 79 | M15 132, H1 44, H4 9 | -8.140395 |
| E | 156 | 646 | 84 / 72 | M15 97, H1 46, H4 13 | -0.373211 |
| A | 53 | 355 | 31 / 22 | H1 21, M15 18, H4 14 | -4.963591 |
| **Union** | **986** | **3,765** | 532 / 454 | — | — |

All five books exercised (>= 1 fill). `fills_by_book` equals `fills_by_trigger` (each book is a pure tag). `cross_tag_leak = NO`, `unattributed_fills = 0`, `poi_outside_books = 0`.

### 2.1 Pre-R1 → post-R1 comparison

Pre-R1 baseline (24/24 runs, same window/set): fills `{F:353, B:241, C:185, E:156, A:53}` union **988**, routes `{F:1132, B:840, C:795, E:646, A:358}` union **3,771**. Post-R1 authoritative: fills `{F:351, B:241, C:185, E:156, A:53}` union **986**, routes `{F:1129, B:840, C:795, E:646, A:355}` union **3,765**. The delta is **-2 fills** (both F, -2 long) and **-6 routes** (F -3, A -3), consistent with R1 collapsing cross-book direction+entry collisions at admission before fill/slot consumption. The 4 collision groups identified pre-rerun (mar25 LONG E+F @2905.155, mar25 SHORT-hyp E+F @2905.155, jul25 LONG A+F @3328.048, oct25 LONG F+B @4040.015) motivated the full rerun; the observed net fill delta is small and book-localized, but because suppression is admission-time and can cascade through one-story/risk state, the rerun verdict — not arithmetic — is authoritative.

---

## 3. Isolation

| Check | Pre-R1 result | Post-R1 authoritative | Status |
|---|---|---|---|
| `CROSS_TAG_LEAK` | NO | **NO** | PASS |
| Unattributed fills | 0 | **0** | PASS |
| Unwanted cross-book double-lots | 1 — `long, entry 2905.155, SL 2905.519052, TP 2911.310756, 2025-03-06 14:05` owned by E and F | **0** (`unwanted_double_lots={}`, `checks.no_cross_book_double_lot=true`) | PASS |
| `cross_book_duplicate_skips` | 0 (dedup never fired) | **8** | PASS (dedup firing as designed under R1) |
| `adapter_duplicate_story_cross_book` | 0 | **0** | PASS |
| `poi_outside_books` | 0 | **0** | PASS |
| `all_books_exercised` | true | **true** | PASS |
| `all_runs_present` | true | **true** | PASS |

**DOUBLE_LOT: 0 (PASS).** R1 identity (direction + exact entry limit) collapsed the pre-R1 double-lot and the other collision groups at admission; no unwanted cross-book double-lot remains in the post-R1 year verdict.

---

## 4. Product-fill gap — OPEN / PARTIAL

`checks.no_product_fill_lost = false`. The post-R1 verdict records **56 missing product fills** across **21 of 24 runs** (442 per-run anchor comparisons over 239 unique product fills; 1,327 replayed fills compared in those runs). Status remains **OPEN / PARTIAL** (product-superset gate not satisfied).

Residual by run:

| Run | Missing | Product fills | Replayed |
|---|---:|---:|---:|
| nov24/LONG | 4 | 21 | 68 |
| nov24/SHORT | 4 | 21 | 52 |
| dec24/LONG | 2 | 12 | 43 |
| feb25/LONG | 4 | 23 | 70 |
| feb25/SHORT | 6 | 23 | 63 |
| mar25/LONG | 1 | 14 | 43 |
| mar25/SHORT | 1 | 14 | 56 |
| apr25/LONG | 1 | 18 | 53 |
| apr25/SHORT | 1 | 18 | 57 |
| may25/LONG | 5 | 30 | 75 |
| may25/SHORT | 3 | 30 | 75 |
| jun25/LONG | 2 | 19 | 53 |
| jun25/SHORT | 2 | 19 | 63 |
| jul25/LONG | 2 | 27 | 71 |
| jul25/SHORT | 6 | 27 | 78 |
| aug25/LONG | 2 | 22 | 70 |
| aug25/SHORT | 1 | 22 | 82 |
| sep25/LONG | 2 | 18 | 60 |
| sep25/SHORT | 1 | 18 | 58 |
| oct25/LONG | 2 | 23 | 69 |
| oct25/SHORT | 4 | 23 | 68 |
| **Total** | **56** | **442** | **1,327** |

> Total correction 2026-11-23: the earlier `414 / 1,230` totals were arithmetic slips; the per-run
> rows above and in the verdict were always correct. `442` counts each segment's product fills
> once per hypothesis run (239 unique product fills; 21 loss-runs only, so the three clean runs'
> 117 replayed fills are outside the `1,327`).

Classification (unchanged from S3 pre-rerun analysis, still not per-fill reconciled):

- Tier coverage: **0** missing attributable to `poi_outside_books` (0 every run) — ruled out.
- Cross-book dedupe: pre-R1 0 skips; post-R1 **8** `cross_book_duplicate_skips` total. R1 can only increase suppression, so dedupe may explain a small additional fraction post-R1, but it cannot close the gap.
- Remainder: split between same-book one-story-guard displacement and segment tiling; **not yet per-fill reconciled**.

Closing plan (read-only, no new backtest): per-fill join of each run's `fills.csv` against the product anchor `trades.csv` on `(direction, entry_at/entry_price)`, classify each missing row as (a) same-book one-story suppression, (b) exec-window/warm-up tiling boundary, (c) cross-book R1 dedupe suppression, or (d) unexplained. This remains an artifact-analysis task.

**Reconciliation performed (2026-11-23):** `PARALLEL_BOOKS_PRODUCT_GAP_RECONCILIATION.md` —
join key `(poi_id, trigger, entry_at, entry_price@6dp, direction)`; **56/56 rows bucketed**, 0
unexplained: **C (R1 identity / re-attribution) 9, B (same POI traded under another trigger) 24,
F (route emitted, no fill) 23**; A/E/G 0; D not per-fill assignable (run-level co-factor only).
Run-level 56 = 40 unique product fills. Product-superset feasibility: **NO** under the locked
design (see that note §7). Nothing above is superseded; the gate stays OPEN.

---

## 5. Shared risk skips (post-R1)

From `verdict.shared_risk_skips` (sum over 24 runs):

| Reason | Count |
|---|---:|
| circuit_breaker | 198 |
| session | 199 |
| skip_place_far_from_zone | 17 |
| same_level | 15 |

Per-book attribution (M-4, surfaced by the rerun harness via `shared_risk_skips_by_book`; `skip_place_far_from_zone` is unattributed by design in the runner):

| Book | circuit_breaker | session | same_level | skip_place_far_from_zone |
|---|---:|---:|---:|---:|
| A | 17 | 15 | 0 | — |
| B | 39 | 43 | 0 | — |
| C | 50 | 39 | 3 | — |
| E | 35 | 58 | 2 | — |
| F | 57 | 44 | 10 | — |
| unattributed | — | — | — | 17 |

Attribution is diagnostic only — no decision change.

---

## 6. Explicit statements

```text
PROD_DEFAULTS_CHANGED: NO
  - config/live_demo.json has no parallel_books key -> () (single menu).
  - No installer/live multi-book default. No locked_constants edit.
DIAGNOSTIC_PNL: NOT PERFORMANCE (accounting residue only; no expectancy/edge claim).
S2 PROMOTION: NONE (research harness only; R-L still gates non-dry-run).
DOUBLE_LOT: 0 (PASS, post-R1 authoritative).
CROSS_TAG_LEAK: NO (PASS).
PRODUCT_GAP: OPEN (56 missing fills / 21 runs; product-superset gate FAIL).
```

---

## 7. Return block

```text
S3_STATUS: PARTIAL (isolation PASS, product-superset OPEN)
FILLS_BY_BOOK: {F:351, B:241, C:185, E:156, A:53}  (union 986; post-R1 authoritative)
ROUTES_BY_BOOK: {F:1129, B:840, C:795, E:646, A:355}  (union 3765; post-R1 authoritative)
DOUBLE_LOT: 0 (PASS; cross_book_duplicate_skips=8)
PRODUCT_GAP_60: OPEN (measured 56 missing over 21/24 runs; tier 0, dedupe small/additive-only, remainder one-story/tiling; not per-fill reconciled)
RERUN: COMPLETE (06_RESEARCH/results/parallel_books_s3_rerun/verdict.json, exit 1 = product gap only)
PROD_DEFAULTS_CHANGED: NO
NOTE_PATH: 06_RESEARCH/PARALLEL_BOOKS_S3_REBASELINE_NOTE.md
HANDOFF_UPDATED: YES
NEXT_READY: Architect review → product-gap per-fill reconciliation / entry representation / OOS / paper as ruled
```
