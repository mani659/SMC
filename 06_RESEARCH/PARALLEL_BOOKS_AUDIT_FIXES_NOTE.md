# PARALLEL BOOKS — AUDIT FIXES (C-1, M-1, M-2, M-3, M-5)

**Status: FIXES APPLIED — `LOGIC_CHANGED: YES` behind the dead-by-default
`parallel_books` flag only.** No production default flipped (the shipped
`live_demo.json` never sets the key; `parallel_books` is still `()`), no
`locked_constants` value touched, no threshold/SL/TP/edge work, no full-year
backtest, no expectancy language.

Parent document: `06_RESEARCH/PARALLEL_BOOKS_DESIGN_IMPL_AUDIT.md` (findings
only, 2026-11-18). This note records what was fixed, how it was proved, and
what remains open.

---

## 1. What changed

### C-1 (CRITICAL) — cross-book double-lot

Two independent layers now enforce R-H, and neither is time-scoped:

1. **Durable cross-book plan registry** — `CrossBookPlanRegistry` in
   `04_SRC/smc/orchestration/parallel_books.py`. `ParallelBookMenu` no longer
   prunes admitted plans against `MenuWinner.window_end_ts`
   (`_prune_plans` is gone). A plan is remembered from the moment a book
   admits it until the plan stops being live:
   - identity = `CrossBookPlanKey` (direction + exact entry/SL/TP + zone
     overlap — **trigger excluded**), unknown geometry never stored;
   - `window_end` is kept as reporting metadata only, never as a timer;
   - `release_plan(<book>|<poi>)` is the single release seam, called by the
     adapter when a claim dies (workflow dropped, window closed unplaced, zone
     violated, POI retired, or a placed plan that no longer trades);
   - same-book entries never dedupe against themselves (`recall(...,
     book_id=...)`), so a single `PROD` book is behaviourally unchanged;
   - counters: `cross_book_plans_live`, existing `cross_book_duplicates` and
     `cross_book_duplicate` events (owner book / owner POI).

2. **Adapter backstop that does not rely on the trigger** —
   `PipelineAdapter._duplicate_story` (`04_SRC/smc/backtest/pipeline_adapter.py`)
   keeps the locked ONE-STORY check as-is (`story_key`/`same_story`, trigger
   included) and adds a second check on the **trigger-excluded** key for
   book-stamped candidates against every LIVE claim — resting order, open
   position, pending confirmation, in-flight workflow/queued winner. A drop
   increments `duplicate_story_cross_book` (aggregate
   `duplicate_story_dropped` + the per-path counter also increment), so the
   skip reason is machine-readable instead of silent.

Claims now carry `cross` (the trigger-excluded key) and `book_id`, and are
released on the same liveness clock as before. When a sealed claim is pruned
because its plan no longer trades, the registry entry is released in the same
step — so a *later, genuinely new* identical plan is still allowed (liveness,
not "forever").

### M-1 — R-K exclusion on every config form

`_coerce_book` now refuses an excluded tag **after** the tag letter is
resolved (dict entries) and refuses an excluded `book_id`, for strings, dicts
and `BookConfig` instances alike (`_refuse_excluded`). The string preset path
keeps its original message.

### M-2 — adapter state keyed by route identity

Pending confirmation slots, story claims and their settle/seal/release are
keyed by `<book>|<poi>` for book-stamped candidates and by the bare POI id
otherwise (`_route_key`). Consequences:

- two books winning on the SAME POI with DIFFERENT plans keep two independent
  pending slots and two independent claims (previously one silently overwrote
  the other);
- `notify_candidate_outcome` / `on_candidate_accepted` settle and seal only
  the route that placed (previously `seal_story(poi)` sealed every claim of
  that POI);
- legacy keys are byte-identical (`test_f5_f7_menu_lifecycle.py` untouched);
- a bare POI id passed to the settle/seal seams still resolves to that POI's
  slot(s), so older callers keep their meaning;
- two books still cannot own the same executable plan — that is C-1's guard.

### M-3 — no legacy seek fall-through outside the books

`ParallelBookMenu.refuses_uncovered_tiers = True`. The adapter's
`_outside_book_tiers(poi)` returns True when the multiplexer owns the menu,
nothing covers the POI, and `tier_for(zone_tf)` is `None` — i.e. the POI's
detection tier is carried by no selected book. Such a POI is **not** routed
through the archived single-menu seek path: it is marked routed, counted once
in `menu_counters()["poi_outside_books"]`, and never arms a workflow. The
shipped single `ProductMenuEngine` does not opt in, so its seek path is
unchanged.

### M-5 — R-L operator guardrail

- `operator_config`: new whitelisted key / field
  `allow_parallel_books_live` (default `False`). Loading a config with a
  non-empty `parallel_books` and `dry_run: false` without the flag raises
  `ConfigError` at load time (before any terminal connection).
- `run_operator._build_stack`: the same condition aborts the stack with a loud
  `SystemExit` even when the config object was built in code (tests, scripts),
  so the guardrail is not config-file-only.
- Default posture is unchanged: no books ⇒ no flag needed; books ⇒ dry-run
  unless the operator explicitly accepts live multi-book placement.

## 2. Deliberately NOT done

- **M-4** (risk blocks not attributed per book) is outside this engagement's
  required-fix list and is still OPEN. `blocked_by_reason` remains
  account-level; a journal still cannot say "which book hit the breaker".
- **Minors m-1…m-8** from the audit are untouched except m-2 (the `window_end
  is None` pruning defect disappears with `_prune_plans`). `_events` is still
  unbounded, `assert_tag_purity` is still harness-only, `winners` still
  concatenates suppressed winners, design line citations still drifted.
- No live default multi-book, no book-list default change, no smoke run, no
  research/full backtest, no threshold or edge work in this engagement.

## 3. Probes (re-run against the patched code)

All read-only, `cd 04_SRC && PYTHONPATH=.`, no data written.

| # | Probe | Before (audit) | After (now) |
|---|---|---|---|
| 1 | `resolve_book_selection([{'book_id':'D','tag':'D','detection_tiers':['M15']}])` | `ACCEPTED [(D, D, ('M15',))]` | `ValueError: book D is excluded … (R-K)`; `{'tag':'D'}` also refused |
| 2 | B plan at t0, F confirms the same fixed plan 8 days later (`window_end` 2026-11-05 12:00Z) | `emitted [('F','poi-1'),('F','poi-2')]`, `cross_book_duplicates = 0` | `emitted []`, `cross_book_duplicates = 2`, `books_emitted {'B':1,'F':0}`, `cross_book_plans_live = 1`, both events `owner_book='B'` |
| 3 | adapter intake, same plan, other tag (`story_key` cannot match) | 2 queued, `duplicate_story_dropped = 0` | 1 submitted, `duplicate_story_cross_book = 1`, `duplicate_story_menu = 1` |
| 4 | mid-only books (`B`) + D1 POI through `generate_candidates` | routed by the legacy seek path (no book stamp, no dedupe) | `scan_route` calls 0, `active_workflows {}`, `poi_outside_books = 1` |

## 4. Tests added (`04_SRC/tests/test_parallel_books.py`, 21 → 32)

- M-1: `test_m1_dict_book_form_refuses_D_R_K` (4 refusing shapes + a legal
  dict entry still resolving).
- C-1: `test_c1_second_book_is_blocked_after_the_first_books_window_closed`
  (asserts the later confirmation is genuinely past `window_end_ts`, then
  one ticket, counted reason, `F` emitted 0);
  `test_c1_registry_remembers_across_time_until_the_plan_is_released`;
  `test_c1_registry_is_freed_when_the_placed_plan_ends`;
  `test_c1_adapter_blocks_a_cross_tag_plan_the_story_key_cannot_see`.
- M-2: `test_m2_two_books_on_one_poi_keep_independent_pending_slots` (two
  slots, two claims, one book's placement settles only its own, the other
  still retries); `test_m2_legacy_unstamped_keys_are_byte_identical`.
- M-3: `test_m3_mid_only_books_never_seek_a_D1_poi` (no scan, no workflow,
  counted once across two bars); `test_m3_the_shipped_single_menu_keeps_its_seek_path`;
  `test_m3_a_book_covered_tier_is_not_skipped`.
- M-5: `test_m5_multi_book_live_needs_the_explicit_posture_flag`
  (refused / flag accepted / dry-run default).

No existing test was modified, skipped or weakened.

## 5. Verification

```text
cd 04_SRC && PYTHONPATH=. python -m pytest -q
1555 passed, 7 skipped in 4.65s        (was 1544 passed / 7 skipped; +11 tests)

cd 04_SRC && PYTHONPATH=. python -m pytest -q tests/test_parallel_books.py
32 passed

git diff -- 00_LOCKED/locked_constants.py 04_SRC/smc/config
(empty)
```

**Not run:** the `['F','B']` dry-run smoke, any backtest (research or full
year), any live/paper session, any MT5 interaction. The C-1 guard is now
unit- and probe-proven; it still has **zero data firings** (feb25 produced no
cross-book duplicates), so no claim is made that it changed behaviour on the
measured month.

## 6. Promote matrix (after fixes)

| Target | Verdict | Notes |
|---|---|---|
| Smoke — `books=["F","B"]`, `dry_run=true` | **YES** | C-1/M-1/M-2/M-3/M-5 closed at code level; default still single-menu. |
| Research BT — `[F,B,C,E,A]` | **YES for R-H/M-3 safety** (unchanged caveats) | D1 POIs are no longer silently routed outside the book layer. R-G six-book runtime budget still unproven; R-B, R-D, R-I, R-J still open rulings. |
| Installer / live default | **NO** | `parallel_books` default stays `()`; live multi-book needs `allow_parallel_books_live=true` plus the default-enable ruling, R-D, R-G, F4 envelope, M-4 attribution. |

## 7. Next

1. Architect: dry-run `["F","B"]` smoke → promote ruling.
2. Then the research BT with `[F,B,C,E,A]` (measure runtime and cross-book
   counters; R-G budget).
3. M-4 (per-book risk attribution) and the remaining minors before any
   installer/default discussion.
