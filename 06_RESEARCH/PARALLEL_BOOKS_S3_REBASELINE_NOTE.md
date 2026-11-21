# PARALLEL BOOKS — S3 RESEARCH RE-BASELINE (post-R1) — 2026-11-20

**Status:** PARTIAL — pre-R1 baseline recorded authoritatively; post-R1 re-run is
detached and in flight. Refined figures land when it finishes.
**S2 admission:** F, B, C, E, A (D out) — `PARALLEL_BOOKS_S2_ADMISSION_RULING.md`.
**Identity in force:** Architect R1 (`same_cross_book_plan` = direction + entry limit).
**Scope:** research harness only. NOT live, NOT a threshold change, NOT expectancy.

> `pnl_net_sum_diagnostic` in every artifact is an accounting residue. **It is never a
> performance claim.** Nothing here says the strategy works.

---

## 1. Method — which numbers are authoritative

| Number | Source | Identity |
|---|---|---|
| Fill / route union by book (§2) | **Existing year verdict** `parallel_books_full_bt/verdict.json` (24/24 runs, generated 2026-11-20T11:07Z) | **pre-R1** (run before the S1b fix) |
| Double-lot count (§3) | Same verdict | pre-R1: 1. **post-R1 expected 0 — pending the re-run** |
| Product-fill gap (§4) | Same verdict (`product_anchor_losses`) | pre-R1 |
| Shared-risk skips (§5) | Same verdict (`blocked_by_reason`) | pre-R1; per-book M-4 not surfaced by that harness version |

The existing run already used the S2-admitted set (F,B,C,E,A), the same product_1y
window (exec 2024-11-01..2025-10-31, warm-up from 2024-09-01) and the same 12-segment
tiling. What it does **not** include is R1, which landed in S1b after the run started.

**Re-run launched:** `06_RESEARCH/results/parallel_books_s3_rerun`, detached
(`parallel_books_s3_rerun_launch.ps1`), PID recorded in `pid.txt`, same window and the
same resume-`.done` rules (a relaunch skips any finished run). Expected runtime ~45 h
(the pre-R1 run took 164,114 s). Until it finishes, §2–§5 are the **pre-R1** baseline.

---

## 2. Authoritative fill / route union by book (pre-R1)

24/24 runs present (12 segments x LONG/SHORT). Fills are unique-timestamp events and
add across segments; route (winner) counts are unioned by `(segment, poi, trigger,
sweep_ts)` and are **not** a year total of menu bookkeeping.

| Book | Fills | Routes | Long / Short fills | Detection TF mix |
|---|---:|---:|---|---|
| F | 353 | 1,132 | 186 / 167 | H4 53, M15 223, H1 64, D1 13 |
| B | 241 | 840 | 127 / 114 | M15 152, H1 59, H4 30 |
| C | 185 | 795 | 106 / 79 | M15 132, H1 44, H4 9 |
| E | 156 | 646 | 84 / 72 | M15 97, H1 46, H4 13 |
| A | 53 | 358 | 31 / 22 | H1 21, M15 18, H4 14 |
| **Union** | **988** | **3,771** | 534 / 454 | — |

All five books exercised (>= 1 fill). `fills_by_book` equals `fills_by_trigger` in the
pre-R1 run (each book is a pure tag).

---

## 3. Isolation

| Check | Pre-R1 result | Post-R1 expectation |
|---|---|---|
| `CROSS_TAG_LEAK` | **NO** | NO (identity change is cross-book only; tag purity untouched) |
| Unattributed fills | **0** | 0 |
| Cross-book double-lot (harness key: direction/entry/SL/TP/entry_at) | **1** — `long, entry 2905.155, SL 2905.519052, TP 2911.310756, 2025-03-06 14:05` owned by E and F | **0 expected** — R1 collapses direction+entry before either fills |
| `cross_book_duplicate_skips` | **0** (dedup never fired) | **> 0 expected** — the positive signal that dedup now fires |
| `adapter_duplicate_story_cross_book` | **0** | > 0 possible (same rule at the adapter backstop) |
| `poi_outside_books` | **0** | 0 (M-3 unchanged; F carries all tiers) |

### R1 delta is larger than the one double-lot → full re-run required

Scanning all 24 `fills.csv` for the **R1 identity** (same direction + same exact
`entry_price`, across distinct books) finds **4 collision groups**, not 1:

| Run | Direction | Entry | Books | Note |
|---|---|---:|---|---|
| mar25 LONG | long | 2905.155 | E, F | the flagged double-lot (same SL/TP/entry_at) |
| mar25 SHORT | long | 2905.155 | E, F | same entry, different SL/TP or entry_at → not flagged pre-R1 |
| jul25 LONG | long | 3328.048 | A, F | same entry, different SL/TP or entry_at |
| oct25 LONG | long | 4040.015 | F, B | same entry, different SL/TP or entry_at |

So R1 does **not** merely remove the one flagged event: up to 3 further second-book
plans would be suppressed. Because suppression happens at admission (winner) through a
durable registry, a suppressed plan can also change one-story consumption, position
slots and the shared risk envelope downstream — effects a static fills scan cannot
simulate. **Authoritative post-R1 `fills_by_book` therefore requires the re-run**, which
is why one is in flight rather than a verdict-level arithmetic adjustment.

---

## 4. Product-fill gap (~60 → **53** measured)

The earlier "≈60" was an approximation. The verdict's `product_anchor_losses` sum to
**53 missing product fills** across **19 of 24 runs** (product anchor: 414 product fills
total; 1,230 replayed fills compared).

Status: **OPEN / PARTIAL.**

- Tier coverage: **0** (`poi_outside_books = 0` every run) — ruled out.
- Cross-book dedupe: **0** skips all year (pre-R1) — ruled out as a *pre-R1* cause.
- Remainder: split between one-story-guard displacement and segment tiling; **not yet
  per-fill reconciled**.
- Plan to close: per-fill join of each run's `fills.csv` against the product anchor
  `trades.csv` on `(direction, entry_at/entry_price)`, then classify each missing row as
  (a) suppressed by the same-book one-story guard, (b) outside the run's exec window /
  warm-up tiling, or (c) unexplained. This is a read-only artifact analysis; it does not
  need a new backtest.

Note: R1 can only *increase* suppressions; it cannot reduce the product-anchor gap.
The re-run will re-measure it (still expected > 0 because of the one-story/tiling
causes, which R1 does not touch).

---

## 5. Shared risk skips (pre-R1)

From `verdict.shared_risk_skips` (sum over 24 runs):

| Reason | Count |
|---|---:|
| circuit_breaker | 198 |
| session | 200 |
| skip_place_far_from_zone | 17 |
| same_level | 15 |

**M-4 per-book attribution:** the pre-R1 harness aggregated `blocked_by_reason` only,
so per-book numbers are not available for this baseline. The harness now reads
`report.blocked_by_book` (spike summary + `_run_checks` + verdict key
`shared_risk_skips_by_book`), so the in-flight re-run will carry
`book_id → reason → count` (unknown book ids fold into `"unattributed"`). That is an
attribution field only — no decision change.

---

## 6. Explicit statements

```text
PROD_DEFAULTS_CHANGED: NO
  - config/live_demo.json has no parallel_books key -> () (single menu).
  - No installer/live multi-book default. No locked_constants edit.
DIAGNOSTIC_PNL: NOT PERFORMANCE (accounting residue only; no expectancy/edge claim).
S2 PROMOTION: NONE (research harness only; R-L still gates non-dry-run).
```

---

## 7. Return block

```text
S3_STATUS: PARTIAL (pre-R1 baseline authoritative; post-R1 re-run in flight)
FILLS_BY_BOOK: {F:353, B:241, C:185, E:156, A:53}  (union 988; pre-R1)
ROUTES_BY_BOOK: {F:1132, B:840, C:795, E:646, A:358}  (union 3771; pre-R1)
DOUBLE_LOT: 1 pre-R1 / 0 expected post-R1 (pending re-run)
PRODUCT_GAP_60: OPEN (measured 53 missing over 19/24 runs; tier 0, dedupe 0, remainder one-story/tiling)
RERUN: YES (detached, out=06_RESEARCH/results/parallel_books_s3_rerun, resume-.done)
PROD_DEFAULTS_CHANGED: NO
NOTE_PATH: 06_RESEARCH/PARALLEL_BOOKS_S3_REBASELINE_NOTE.md
HANDOFF_UPDATED: YES
NEXT_READY: Architect review → entry representation / OOS / paper as ruled
```
