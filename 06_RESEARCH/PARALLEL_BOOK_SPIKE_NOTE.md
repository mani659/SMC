# PARALLEL BOOK SPIKE — implementation note (dead by default)

**Status: SPIKE PASS — `SPIKED`, `PROD_DEFAULTS_CHANGED: NO`.**
Design authority: `06_RESEARCH/PARALLEL_DEDICATED_PATH_DESIGN.md`.
Evidence: `R0_TRIGGER_ADMISSION_MAP.md`, `R1_PURE_TAG_BOOKS_REPORT.md`,
`BCE_STARVATION_PROBE_REPORT.md`.

No edge claim. No stop redesign. No locked-constant edit. No default menu
change. The parallel path is reachable only from an explicit operator config
key (`parallel_books`), which is empty in every shipped config.

---

## 1. What was implemented

### 1.1 Book layer — `04_SRC/smc/orchestration/parallel_books.py`

| Object | Contract |
|---|---|
| `BookConfig(book_id, tag, detection_tiers, symbol)` | data only: a book is `(symbol, tag, detection_tier_set, confirm_tf_map)`. `confirm_tf_map` is **read off the shipped `MenuTier`** — a book may not invent confirmation geometry. |
| `BookConfig.menu_tiers()` | the shipped tiers narrowed to `trigger_types=(tag,)` — exactly the object R1 injected, promoted from runtime patch to configuration. `PROD` returns the shipped table verbatim. |
| `resolve_book_selection(None / [] / "F" / ["F","B"] / ["PROD"] / dict / BookConfig)` | empty → `()` = today's single menu. `D` is refused (R-K). Unknown tags/tiers/duplicates fail loud at config load. |
| `cross_book_plan_key` / `same_cross_book_plan` | executable-plan identity **without the trigger** (direction, exact entry/SL/TP, overlapping zone). Two tags confirming the same order are the same order. |
| `ParallelBookMenu` | drop-in multiplexer with the surface the live loop / adapters already use: `register_armed`, `retire`, `set_state_source`, `on_execution_bar`, `tier_for`, `detection_timeframes`, `confirmation_timeframes`, `episodes`, `counters`, plus `_armed` / `_consumed` / `_episodes` for `PipelineAdapter.menu_covers_poi`. |

Rules honoured:

* **R-A (one story PER BOOK).** Each book owns its own `ProductMenuEngine`
  instance → its own `_armed`, its own episodes, its own one-shot `_consumed`.
  A win in book B cannot consume book F's POI or close its window. The
  adapter's plan-level story guard is untouched (it keys on trigger, so it never
  arbitrates between two tags).
* **R-K.** `D` is refused with the feed reason.
* **Shared envelope.** The layer owns **no** risk component; all books run
  through the same runner/`RiskEngine`, so one breaker, one daily loss, one
  same-level and one sweep memory per account.
* **Cross-book identical plan (R-H).** Suppressed with a
  `cross_book_duplicate` counter and a machine-readable event; never a silent
  second ticket.
* **R-B (opposite direction).** Left OPEN as the design requires: coexistence is
  counted (`cross_opposite_direction`) and journalled, not blocked.
* **R-J.** The winning route's `direction` rides on the candidate; no inference
  is needed for journal identity.
* **R-D (identity).** Every emitted candidate is stamped `book_id` /
  `book_tag`; `smc.execution.order_identity` turns that into an
  `SMC-<TAG>-` comment prefix. `PROD` / unstamped candidates keep their comment
  **byte-identically**.

### 1.2 One production-code change the spike required

`ProductMenuEngine.tier_for` now resolves against the instance's own `tiers`
first, with the module map kept as the fallback. The engine was documented as
instance-scoped but actually read the module-level `_TIER_BY_DETECTION`, which
is why R1 had to patch a module global — impossible for N books in one process.
For the shipped default tier set the lookup result is **identical**, so this is
a no-op for production; all 1,544 tests pass unchanged.

### 1.3 Flag / config surface

* `operator_config`: new whitelisted key `parallel_books` (default `()`),
  validated eagerly via `resolve_book_selection` (typos and `D` fail at load).
* `run_operator._build_stack`: `parallel_books` non-empty → `ParallelBookMenu`,
  empty → `ProductMenuEngine` (today's path, untouched). The active book list is
  logged at startup.
* No shipped config (`config/live_demo.json`, tester pack) sets the key.

### 1.4 Order identity

`book_comment(candidate, base)` → `SMC-<TAG>-<base>` (truncated to the MT5
31-char comment width) for a dedicated book; unchanged otherwise. Wired at the
single placement choke points (`BacktestRunner._place_accepted`, both paper
`OrderRequest` sites and the pending-order mirror). `book_magic(base, index)` is
implemented and tested but **not wired** into any default — magic changes need
architect sign-off (R-D).

---

## 2. Measurement method

* Seam: the R1 replay seam unchanged — product_1y armed universe →
  `engine.arm_at` + `menu.register_armed` at the armed bar →
  `menu.on_execution_bar` over closed-prefix streams (`MENU_WARMUP_BARS=300`) →
  winners → `PipelineAdapter.queue_menu_candidate` → production
  `BacktestRunner` (risk gate, placement, fills, positions). No detection
  re-run (menus gate confirmation only). No stop/SL/TP change.
* Books exercised: **F** `{DAY,H4,H1,M15}` and **B** `{H4,H1,M15}`, both with
  `trigger_types=(tag,)`; one shared runner/`RiskEngine`.
* Direction: armed records export none, so both hypotheses run (Scan 1B / R1
  convention); filled POIs use their TRUE product direction. Fill counts are
  **union upper bounds**, not production-equivalent counts.
* Window: **feb25** (product_1y exec 2025-02-01 → 2025-02-28 UTC, load from
  2024-09-01) — a MID-heavy month (R1 B/MID 20 fills, F/MID 28 fills). The full
  year is not re-run here: R1's year took 18.9 h wall and a single month's PROD
  replay is 3,000–4,300 s per hypothesis.
* Default parity slice: **first 10 trading days of feb25** (anchor cut
  `2025-02-17T08:55Z`), same process, same bars, same POIs, both variants.

Artifacts (gitignored): `06_RESEARCH/results/parallel_book_spike/`
(`parity_feb25_*.json`, `summary_feb25_F,B.json`, per-run `summary.json` /
`trades.csv` / `fills.csv` / `winners.json`).
Harness: `06_RESEARCH/scripts/parallel_book_spike.py`.

---

## 3. Default parity (single menu vs `books=["PROD"]`)

| Quantity | Shipped menu (L / S) | PROD book (L / S) | Verdict |
|---|---|---|---|
| armed POIs | 169 / 169 | 169 / 169 | equal |
| winners (identity `poi+trigger+sweep_ts`) | 22 / 19 | 22 / 19 | **identical sets** |
| fills (plan identity) | 11 / 12 | 11 / 12 | **identical sets** |
| product-fill anchor in slice | 12 / replayed 11 / missing 1 | 12 / replayed 11 / missing 1 | **identical** |
| runtime | 487.2 s / 390.1 s | 491.3 s / 393.0 s | +0.8 % / +0.7 % |

`winners_only_plain`, `winners_only_prod_book`, `fills_only_plain`,
`fills_only_prod_book` are all empty in BOTH hypotheses. The single anchor miss
(1 of 12) is the known single-hypothesis replay artifact from R1 (a product fill
reproduced under the other direction hypothesis) and is **identical in both
variants**, so it is not a book-layer regression. Method limit: parity is a
same-process A/B on the first 10 trading days per hypothesis (a full-month PROD
A/B is ~1.5 h), not a year-scale replay.

---

## 4. Per-book flow on the MID-heavy month

| Book | winners L/S | placed L/S | fills L/S | fills (union) | trigger mix of fills | detection mix (union) |
|---|---|---|---|---|---|---|
| **B** | 70 / 46 | — | 18 / 16 | **25** | `{B: 100 %}` | H4 4 · M15 13 · H1 8 |
| **F** | 86 / 47 | — | 26 / 21 | **29** | `{F: 100 %}` | H4 5 · M15 18 · H1 5 · D1 1 |
| total | 156 / 93 | 45 / 37 | 44 / 37 | **54** | — | H4 9 · M15 31 · H1 13 · D1 1 |

* **B fills > 0 when enabled** (25 union) — the production mix gives B zero.
  This reproduces R1's existence claim on the live seam, per book.
* **Per-book purity**: the filled-trade trigger mix equals the book's tag in
  every run; `ParallelBookMenu.assert_tag_purity()` is a fail-loud check.
  **CROSS_TAG_LEAK: NO.**
* Episode counts differ per book (L: B 243 / F 253) because each book opens its
  own windows — no book consumes another's POI.
* Direction mix (union): B long 10 / short 15, F long 20 / short 9 — the two
  books are not clones of one another.
* Adapter skips are shared-envelope evidence, not book-specific: circuit breaker
  4 (L) / 4 (S), same-level 1 / 1, session 3 / 7, far-from-zone 1 / 0.
* One-story guard (unchanged, plan-level): 103 duplicate drops (L) / 44 (S).
* Runtime: 807.9 s (L) + 640.3 s (S) for both books in one process (R1 single-tag
  MID reference: B 486 s + F 593 s for the same month), i.e. the book layer adds
  roughly one extra engine pass, not a second strategy stack.

---

## 5. Cross-book findings

* **CROSS_BOOK_DOUBLE_LOT: NO — 0 blocked.** In this month B and F never
  confirmed the *same* executable plan, so the dedupe gate had nothing to
  suppress. That is a data result, not a proof the gate is unnecessary: the
  gate is proven by unit tests
  (`test_identical_plan_from_two_books_places_one_ticket`), where it emits one
  ticket and counts `cross_book_duplicate` with owner/loser ids. The gate stays
  mandatory.
* **Opposite-direction coexistence is common**: 29 (L) / 16 (S) counted events
  where a book confirmed while another book held an opposite-direction plan on
  an overlapping zone. Under R-B = ALLOW nothing is blocked (as designed); the
  events are journalled per book. This is exactly the case the design said R1
  never measured.
* Same-symbol, same-feed, fixed book order (B before F) — journals replay
  deterministically.

---

## 6. Tests

`04_SRC/tests/test_parallel_books.py` (21 tests):

| Area | Assertions |
|---|---|
| default parity | empty selection → `()`; `PROD` book == `PRODUCT_MENU_TIERS`; instance-scoped `tier_for` with module fallback preserved; multiplexer never leaks a tier across books |
| book definition | shipped geometry preserved (detection TF, confirmation TFs, expiry), only `trigger_types` narrowed; F carries DAY; `D` refused (R-K); unknown/duplicate refused; a book cannot arm a tier it does not carry |
| isolation (R-A) | one book's win leaves the other's POI unconsumed and its window ACTIVE |
| cross-book dedupe (R-H) | identity ignores the trigger; identical plan → one ticket + counter + owner event; opposite direction is a different order; unknown geometry never collapsed |
| purity | a pure book emitting another letter fails loud (`CROSS_TAG_LEAK`) |
| identity (R-D) | `SMC-B-…` prefix, 31-char width, production/unstamped comments byte-identical, deterministic magic offset |
| shared envelope | the layer has no risk component; one `RiskEngine`'s same-level memory blocks both books, a fresh engine does not |

Full suite: **1,544 passed, 7 skipped** (was 1,523 / 7; +21).

---

## 7. Non-goals (kept)

No expectancy/PnL claim (the `pnl_net_sum` in artifacts is diagnostic only). No
SL/TP redesign. No locked-constant or matrix edit (`git diff -- 00_LOCKED
04_SRC/smc/config` empty). No production menu default change. No shipped config
enables books. No D path. Only the rulings needed for a safe spike were
implemented (R-A, R-H, R-J plumbing, R-D comment prefix, R-K, shared envelope);
R-B/R-E/R-F/R-G/R-I/R-L remain open.

---

## 8. Limits and next

1. **One month, two hypotheses.** The full year is not re-run (R1: 18.9 h wall);
   the feb25 numbers are existence/flow evidence, not expectancy.
2. **Parity slice is 10 trading days**, same-process A/B — a full-month or
   year-scale parity replay is the Phase 3 gate.
3. **Cross-book dedupe did not fire on data** (0). It is unit-proven; a window
   where two tags confirm the same plan is needed to demonstrate it live.
4. **Runtime**: two books cost ~1.35× the sum of the single-tag runs in one
   process; a six-book demo needs the R-G budget (active-episode cap or the
   swing-recompute caching seam) before it is shippable.
5. **Magic is not wired** (R-D sign-off), and the comment prefix is proven in
   the order path but not yet reviewed on a statement.

NEXT = Architect review → decide demo flag set (F+B, or demo as-is).
