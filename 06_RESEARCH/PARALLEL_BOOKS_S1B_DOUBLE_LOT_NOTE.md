# PARALLEL BOOKS — S1b DOUBLE-LOT CLOSEOUT (R1) — 2026-11-20

**Status:** PASS — double-lot FIXED per Architect R1.
**Source:** `PARALLEL_BOOKS_S1_CLOSEOUT_NOTE.md` §1; E+F long 2025-03-06 14:05.
**Suite:** 1,557 passed / 7 skipped / 0 xfailed. `locked_constants` + `04_SRC/smc/config`
diff empty. `parallel_books` default still `()` (key absent → `()`).
**LOGIC_CHANGED:** YES — cross-book identity only (`same_cross_book_plan`). No same-book
rule, no threshold, no gate, no S2 admission.

---

## 1. Ruling implemented

**R1 (binding):** two candidates share executable identity iff same direction and same
entry limit price (symbol when multi-symbol). Zone overlap is NOT required. While the
plan is live in `CrossBookPlanRegistry` / adapter claims, the second book is skipped and
counted. Release semantics unchanged when the plan ends. Same-book behaviour unchanged.

**Change (minimal, one function):** `same_cross_book_plan` in
`04_SRC/smc/orchestration/parallel_books.py` now returns:

```python
if a is None or b is None:
    return False
if a.direction != b.direction:
    return False
return a.entry_price == b.entry_price
```

Previously it also required equal SL/TP and known, overlapping zones. SL/TP and zone
bounds remain on `CrossBookPlanKey` for traceability/events but no longer gate identity.
`cross_book_plan_key` still returns `None` when entry/SL are unknown, so an unprovable
plan is never stored or collapsed (unchanged safety guard).

**Where it takes effect (both seams, no new code paths):**
- `ParallelBookMenu.on_execution_bar` → `_duplicate_owner` → `CrossBookPlanRegistry.recall`
  → `same_cross_book_plan`. Second book's winner is skipped and `cross_book_duplicates`
  incremented.
- `PipelineAdapter._duplicate_story` C-1 backstop over resting/pending/in-flight claims
  → `same_cross_book_plan`. Cross-book duplicate counted as
  `duplicate_story_cross_book`.

Release semantics unchanged: `CrossBookPlanRegistry.release` still forgets by
`book|poi` / POI id when the plan can no longer trade; `_release_menu_plan` follows the
same liveness clock.

---

## 2. E+F reproduction (unit fixture)

The known timestamp shape is reproduced at the key seam without a year run:

- poi-004611 / book E: long, entry 2500, zone 2490–2500.
- poi-004482 / book F: long, entry 2500, zone 2600–2610 (non-overlapping).
- `same_cross_book_plan(...)` → **True**.

And at the registry seam: `remember(E plan)` then `recall(F plan)` → owner E; E still
sees its own slot (`None`); `release("E|poi-004611")` frees it and F's recall → `None`.

Regression tests (previously the `xfail`):
- `test_s1b_double_lot_e_plus_f_non_overlapping_zones_collapses` — key identity.
- `test_s1b_registry_suppresses_second_book_with_a_different_zone` — registry + release.
- `test_cross_book_identity_ignores_the_trigger_letter` updated: unknown zone now
  collapses under R1 (direction+entry), while `sl_price=None` still yields `None`.

The pre-existing menu-seam test `test_identical_plan_from_two_books_places_one_ticket`
still pins one ticket + counter + owner/loser event.

---

## 3. Scope / non-changes

- Same-book one-story (`story_key`, `_duplicate_story` first branch) untouched — R1 only
  governs cross-book.
- Opposite-direction coexistence (R-B) untouched (counted, not blocked).
- No S2 admission promotion; no full-year re-run; no threshold/gate move; no production
  default change; `locked_constants` untouched.
- No expectancy language.

---

## 4. Return block

```text
S1B_STATUS: PASS
DOUBLE_LOT: FIXED (R1: cross-book identity = direction + entry limit; zone not required)
SUITE: 1557 passed, 7 skipped, xfailed=0
LOCKED_CONSTANTS_DIFF: empty
NOTE_PATH: 06_RESEARCH/PARALLEL_BOOKS_S1B_DOUBLE_LOT_NOTE.md
HANDOFF_UPDATED: YES
NEXT_READY: Architect S1b review → S2 only if PASS
```
