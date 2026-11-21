# PARALLEL BOOKS — S1 CLOSEOUT NOTE (2026-11-20)

**Status:** PARTIAL — M-4 PASS; double-lot OPEN (root-caused, fix needs Architect ruling);
product-fill gap explained but not fully bucketed.
**Inputs:** `PARALLEL_BOOKS_FULL_BT_REPORT.md` (FAIL, 2 gates), the year-run artifacts
(`mar25` slice inspected), `parallel_books.py`, `pipeline_adapter.py`, `runner.py`,
`reports.py`.
**Suite:** 1,555 passed / 7 skipped / 1 xfailed. `locked_constants` + `04_SRC/smc/config`
diff empty. `parallel_books` default still `()`.
**LOGIC_CHANGED:** YES — M-4 only (book_id stamp on risk blocks + report/export
breakdown). No decision logic, no threshold, no gate change.

---

## 1. Double-lot reproduction and root cause

**Observed:** `verdict.unwanted_double_lots` — one entry:
`'long'|2905.155|2905.519052|2911.310756|'2025-03-06 14:05:00+00:00'` owned by
`E` and `F`.

**Artifact trace (mar25 LONG):** two different POIs produced the identical executable
order:

| POI | Book | Sweep | Window end | Fill bar |
|---|---|---|---|---|
| poi-004611 | E (and C) | 2025-03-06 10:00 | 15:15 | 14:05 |
| poi-004482 | E, F (and B) | 2025-03-06 13:45 | 19:00 | 14:05 |

Both fills: direction long, entry 2905.155, SL 2905.519, TP 2911.311, entry_at
2025-03-06 14:05. Cross-book duplicate skips that year: **0**. Adapter
`duplicate_story_cross_book`: **0**. The dedup never fired on this pair (or any pair).

**Root cause — identity mismatch between the harness and the code:**

- The harness flags a double-lot on `(direction, entry, SL, TP, entry_at)` — i.e.
  the *executable order*. No zone, no trigger.
- The code's `same_cross_book_plan` (parallel_books.py) collapses two plans only when
  `direction`, `entry_price`, `sl`, `tp` match **AND** the two POIs' zone bounds are
  known **and** `zones_overlap(...)` is true. Unknown (None) zones → never collapse;
  non-overlapping zones → never collapse.
- The two POIs above have different zone geometries (different sweep_ts / window_end),
  so their zones either do not overlap or one side is incomplete → `same_cross_book_plan`
  returns False → both plans are admitted → both fill → double-lot per the harness.

In other words: the dedup is *correct per its own design* (zone overlap required) but
its identity is **stricter than the executable order**, so it misses the exact case the
harness (and the product) calls a double-lot. This is a design tension, not an
implementation slip: the zone gate exists to avoid merging two genuinely different
theses that happen to share entry/SL/TP.

**Why the safety rule is not trivially dropped:** `test_cross_book_identity_ignores_the_trigger_letter`
encodes `unknown geometry is never collapsed` (sl_price=None → key None; zone None →
not collapsed). Dropping the zone gate would make two plans with identical entry/SL/TP
but unrelated zones collapse, which can over-dedupe a legitimate second trade. The
year run's `cross_book_duplicate_skips = 0` shows the gate is currently *too* strict
(never fired), while the 1 double-lot shows it is also *too* loose in the sense that
the harness still counts a miss.

**Fix options (Architect ruling required — not applied):**

1. **Drop the zone gate** from `same_cross_book_plan` (collapse on
   direction+entry+SL+TP only). Eliminates the observed class of double-lot; risk is
   over-dedupe when two distinct POIs share an executable order by coincidence.
2. **Add entry_at / fill-bar to the code identity** so the dedup only fires on the
   same bar, matching the harness's `entry_at` clause. Narrower; does not change
   zone semantics.
3. **Align the harness** to the code (include zone in `_plan_key` and only flag when
   zones overlap). Then the observed pair is not a double-lot by definition. Cheapest,
   but redefines the gate post-hoc.

**Current state:** none applied. `same_cross_book_plan` unchanged; the safety rule and
its test intact. An `xfail` test (`test_s1_double_lot_zone_gap_documented`) pins the
gap so it cannot be silently forgotten. DOUBLE_LOT = OPEN.

---

## 2. The 60 missing product fills

**Observed:** every one of the 24 runs lost 1–6 product fills; total ≈ 60
(`product_anchor_losses`). `poi_outside_books = 0` (M-3), so no POI was dropped for
uncovered tier.

**Bucketing (best effort from the artifacts; precise per-fill reconciliation not yet
run — see §4):**

| Bucket | Count | Evidence / reasoning |
|---|---:|---|
| Tier coverage (M-3) | 0 | `poi_outside_books = 0` in every run; F carries all tiers. |
| Cross-book dedupe (menu level) | 0 | `cross_book_duplicate_skips = 0` across the year; no plan was ever suppressed by the durable registry. |
| Adapter one-story guard (trigger-included `story_key`) | likely dominant | A product fill requires the product's multi-trigger menu to produce it; in the replay each trigger is owned by a pure-tag book. A book's candidate can be dropped by `_duplicate_story` when a same-trigger plan is already live, or by the §11 one-shot being consumed. This is the one path that can remove a product fill without an uncovered tier. |
| Segment tiling / boundary | possible (unquantified) | Per-segment `fills` sums to 1,448 vs the 988 union; warm-up fills are counted in run_metrics but not in the verdict union. Some "missing" product fills may be warm-up-window events that the anchor's exec-window comparison does not line up. |
| Other / unexplained | residual | not yet reconciled |

**Conclusion:** tier and cross-book dedupe are ruled out by the counters. The remaining
~60 are split between one-story-guard displacement and tiling, but the exact split is
not yet measured. No silent "ignore" — the gap is recorded as a real finding and is
the second gate that keeps S1 from passing.

---

## 3. M-4 — per-book risk-block attribution

**Change (code, `LOGIC_CHANGED: YES` behind no flag — pure attribution):**

- `runner.BlockedEntry`: new `book_id: str | None` field (default None; backward
  compatible). Populated from the candidate's `product_menu.book_id` stamp via
  `_candidate_book_id`, which reads `signal_data_json` only — never a decision field.
- `reports.BacktestReport`: new `blocked_by_book: dict[str, dict[str, int]]` field
  (book_id → reason → count; None/unknown book ids fold into the `"unattributed"`
  bucket so nothing is silently dropped). `blocked_by_reason` is unchanged.
- `export.to_json`: emits `blocked_by_book` (defensive `getattr` for stub reports).

**Invariance proof:** no decision logic touched. `blocked_by_reason` is byte-identical
to before (the blocked-entry reason is unchanged; only an attribution field was added).
Suite 1,555 passed / 7 skipped (+ 1 xfail) — no test weakened or deleted. The
integrated pipeline test and the blocked-run report test still assert
`blocked_by_reason == {"session": 1}` and pass. M-4 = PASS.

**Limitation:** the full-year harness stores `shared_risk_skips` from
`blocked_by_reason` only; per-book attribution is now available in the report but the
harness has not been updated to surface it. That is a reporting follow-up, not a
decision change, and does not affect S1's verdict.

---

## 4. What was NOT done (and why)

- No full-year re-run (banned unless required; the gap is root-caused from artifacts).
- No double-lot fix applied (needs an Architect ruling among the three options in §1).
- No threshold movement, no gate loosening, no `locked_constants` edit.
- No production default change (`parallel_books` still `()`).
- No entry-strategy work (S4) — S1 is not PASS.

---

## 5. Next ready

`Architect S1 review`. S2 (admission ruling) is licensed **only if** S1 passes — which
requires either (a) accepting the double-lot as a design consequence (option 3 in §1)
plus a per-fill reconciliation of the 60 fills, or (b) applying option 1/2 and
re-measuring on a minimal slice.

```text
S1_STATUS: PARTIAL
DOUBLE_LOT: OPEN — root cause: same_cross_book_plan requires zone overlap;
            E+F long 2025-03-06 14:05 had non-overlapping/unknown zones, so dedup
            never fired (0 cross-book skips all year). Fix options in §1 (Architect ruling).
PRODUCT_FILLS_60: explained buckets — tier 0, cross-book dedupe 0, remainder split
                  between one-story-guard displacement and segment tiling (unquantified;
                  per-fill reconciliation still pending).
M4: PASS — book_id stamped on BlockedEntry + report/export breakdown; invariance proven.
SUITE: 1555 passed, 7 skipped, 1 xfailed
LOCKED_CONSTANTS_DIFF: empty
NOTE_PATH: 06_RESEARCH/PARALLEL_BOOKS_S1_CLOSEOUT_NOTE.md
HANDOFF_UPDATED: YES
NEXT_READY: Architect S1 review → S2 only if S1 PASS
```
