# PARALLEL DEDICATED BOOKS — DESIGN ↔ IMPLEMENTATION AUDIT

**Status: AUDIT ONLY — `LOGIC_CHANGED: NO`.** No production default changed, no threshold/SL/TP
edit, no `locked_constants.py` diff, no full backtest run, no test weakened. This document adds
findings only; every claim below is read from the shipped modules, from the spike's own tests,
or reproduced by a read-only probe recorded in §3.

Scope audited: `06_RESEARCH/PARALLEL_DEDICATED_PATH_DESIGN.md` (design),
`04_SRC/smc/orchestration/parallel_books.py`, `04_SRC/smc/execution/order_identity.py`,
`ProductMenuEngine.tier_for`, the `parallel_books` operator wiring, placement comment hooks,
`04_SRC/tests/test_parallel_books.py`, `06_RESEARCH/scripts/parallel_book_spike.py`,
`06_RESEARCH/PARALLEL_BOOK_SPIKE_NOTE.md`, and the artifacts under
`06_RESEARCH/results/parallel_book_spike/`.

---

## 1. Executive verdict

The spike is a **faithful implementation of the design's menu-layer intent** and its measured
claims check out to the digit. Default parity is genuine, not asserted: the shipped menu and the
`["PROD"]` book produced identical winner and fill sets on the same bars, with identical anchor
counts and a +0.8 % / +0.7 % runtime delta. Book isolation at the menu level is real (one
`ProductMenuEngine` per book, own `_armed`, own `_consumed`, own episodes), the identity key
correctly excludes the trigger, `D` is refused in the documented string form, and the note does
**not** over-claim year-scale results or "double-lot proven on data".

It is **not promotable as-is** beyond a dry-run smoke, for three reasons that sit between the
book layer and the shipped pipeline:

1. **The cross-book dedupe is not end-to-end (CRITICAL).** `ParallelBookMenu` forgets an admitted
   plan when its *menu window* closes, and the only backstop left — the adapter's one-story guard
   — includes the trigger in plan identity, so it can never match a second tag. A second book
   confirming the same executable plan after the first window closed produces a **second ticket**.
   Reproduced by probe (§3.2): two identical `CrossBookPlanKey`s emitted, `cross_book_duplicates`
   = 0. The code's own justification for the window pruning ("the adapter's own story guard still
   covers the resting/open order") is factually wrong.
2. **`R-K` is enforced on one config shape only (MAJOR).** `resolve_book_selection` refuses `"D"`
   as a string but accepts `{"book_id": "D", "tag": "D", "detection_tiers": ["M15"]}` — the dict
   form `operator_config` also accepts. Probe (§3.1) confirms the D book is constructed.
3. **The adapter is book-blind at POI granularity (MAJOR).** Per-book menus emit correctly, but
   `_menu_pending`, `_workflows`, `_claimed_pois`, `_routed` and `seal_story` are keyed by
   `poi_id` alone. Two books winning on the *same* POI with *different* plans (allowed: R-H only
   collapses identical plans) collide on one pending slot, so one book's confirmation is silently
   replaced — with no counter, violating design §8.1-3 ("no unattributed gap").

**AUDIT_STATUS: PASS_WITH_FINDINGS. 1 CRITICAL, 5 MAJOR, 8 MINOR.**

---

## 2. A–J audit table

| # | Question | Verdict | Evidence |
|---|---|---|---|
| **A** | Default parity / no accidental multi-book | **PASS** | `parallel_books: tuple = ()` (`operator_config.py` L195); whitelisted key L86; eager validation L329-353; `run_operator._build_stack` L535-556 selects `ParallelBookMenu` only when `books` is non-empty, else `ProductMenuEngine`. No shipped config sets the key (repo-wide JSON grep: 0 hits). `PROD` book returns `PRODUCT_MENU_TIERS` verbatim (`BookConfig.menu_tiers` L181-190; test L253-262). Parity artifact: identical winner sets (22/22 L, 19/19 S), identical fills (11/11, 12/12), identical anchor (12/11/1) both hypotheses, `differences` all empty. `tier_for` (L422-434) reads own `tiers` first, module map as fallback — identical for the shipped tier set (suite unchanged). |
| **B** | Book isolation / no cross-book POI theft | **PARTIAL** | Menus: one `ProductMenuEngine` per book (`parallel_books.py` L333-345), own armed/episodes/consumed; `confirmation_order_key` race exists only inside a book. Tested: `test_a_win_in_one_book_does_not_consume_another_books_poi` (L266-287). **But** the adapter below the menu keeps one slot per `poi_id` (`_menu_pending[str(poi_id)]` L397, `_settle_menu_candidate` L462-471, `_workflows` L667, `seal_story(pid)` L671) → two books' plans from the same POI cannot both survive (finding **MAJOR-2**). |
| **C** | One-story per book (R-A) / residual global one-shot | **PARTIAL** | Per-book one-shot is real (test L266-287; separate `_consumed` sets). The adapter's story guard remains global but is plan-keyed **including the trigger** (`risk/story_guard.py` rule 4, `same_story`), so it never arbitrates between two tags — the note's claim is accurate. Residual global, POI-keyed state: `_menu_claimed_pois`, `_routed`, `_workflows`, `_menu_pending`, `_scan_cursor` — correct as a POI one-shot, wrong as a per-book container (MAJOR-2). |
| **D** | Cross-book double-lot: key + all entry paths | **PARTIAL** | Key is right: direction + exact entry/SL/TP + zone overlap, **trigger excluded** (`CrossBookPlanKey` L253-262, `same_cross_book_plan` L281-302; tested L293-315 incl. unknown-geometry never collapsing). Suppression path returns one ticket with `cross_book_duplicate` + owner event (L544-590; tested L318-338). **Two gaps**: (a) memory is window-scoped → CRITICAL-1; (b) the check runs only on `ParallelBookMenu.on_execution_bar` output, so candidates from the adapter's legacy seek path (no book stamp) are outside it (MAJOR-3). Comment hook is at every book placement choke point: backtest `_place_accepted` L571 (also used by R9 intents via `_place_due_intents` L620), paper runner L729/L764/L1077/L1130. |
| **E** | Shared risk envelope | **PASS** (attribution gap noted) | The layer owns no risk component (`__init__` signature, tested L409-414); one `RiskEngine` per operator stack (`run_operator` L505) and one per replay (harness `_run`). Shared same-level memory blocks both books, fresh engine does not (test L417-435). Counter-example search: no per-book breaker/daily-loss/guard construction anywhere. **Gap (MAJOR-4):** risk blocks are counted by reason only (`blocked_by_reason`), never by book, so design §8.3-7 ("each block attributed to the book that hit it") is unmet; the note itself calls the skips "shared-envelope evidence, not book-specific". |
| **F** | Identity: comment/magic | **PASS (with honest non-wiring)** | `SMC-<TAG>-<base>` for a non-PROD book, truncated to 31 chars keeping the prefix (`order_identity.py` L74-89); `PROD`/unstamped returns the base verbatim (L84-85; tested L378-397). Magic implemented (`book_magic` L92-103) and **not wired** — declared as such in note §1.4 and §8-5. |
| **G** | D exclusion (R-K) | **FAIL** | String form refused (`EXCLUDED_TAGS` check L226-227; test L243-245). Dict form bypasses it: `_coerce_book` L207-224 resolves the tag from `_TRIGGER_BY_LETTER` and never consults `EXCLUDED_TAGS` → `D` book constructed (probe §3.1). |
| **H** | Measurement honesty | **PASS** (1 minor traceability) | Every note number re-derived from artifacts: parity 22/22, 11/11, 19/19, 12/12 + anchors, runtimes 487.2/491.3/390.1/393.0 s; books 807.9 + 640.3 s; union fills 54 = B 25 / F 29; per-book detection mixes B {M15 13, H1 8, H4 4} / F {M15 18, H4 5, H1 5, D1 1}; direction mixes B 10 L/15 S, F 20 L/9 S; skips 4/4, 1/1, 3/7, 1/0; story drops 103 (L)/44 (S); duplicates 0; opposite 29+16=45. Parity window is genuinely 10 trading days (`menu_bar_count` 2880, anchor cut 2025-02-17T08:55Z). The note explicitly refuses year-scale and "proven on data" claims. Only defect: the R1 comparison "(B/MID 20 fills, F/MID 28 fills)" is the **LONG-only** R1 run, while the spike's 25/29 are two-hypothesis unions — a mismatched comparison basis, not an over-claim. |
| **I** | Open rulings that block "promote all" | **6 open** | R-B (coexistence is counted, not *ruled*); R-D magic (comment only); R-G runtime (two books 1448 s vs 1080 s single-tag sum = 1.34×; six-book budget unproven); R-J (menu-winner plumbing only — armed records still export no direction, so the harness still runs two hypotheses); R-L (no code guardrail ties books to dry_run/shadow — MAJOR-5); R-I (inherited single limits, never explicitly ruled). R-A/R-E/R-H/R-K are implemented (R-K with the G gap), R-F is configuration. |
| **J** | Promote readiness | see §5 | Smoke F+B dry-run: **YES (conditional)**. Research BT with `[F,B,C,E,A]`: **AFTER_FIXES**. Live/default: **NO**. |

---

## 3. Read-only probes (reproduced findings)

All three ran against the shipped modules with `PYTHONPATH=.` in `04_SRC`; nothing was written to
source. Suite was re-run read-only (§6).

### 3.1 `R-K` bypass through the dict config form

```text
resolve_book_selection([{'book_id':'D','tag':'D','detection_tiers':['M15']}])
  → ACCEPTED [('D', 'D', ('M15',))]
resolve_book_selection(['D'])                → ValueError 'book D is excluded: ...'
```
`operator_config` accepts `list[str | dict]` (L333-334), so the accepted shape is reachable from
`live_demo`-style JSON.

### 3.2 Cross-book identical plan emitted twice after a menu window closes

Two books, fixed identical geometry (entry 2500 / SL 2490 / same zone), B confirms at t0, F
confirms the same plan for a new POI 8 days later:

```text
t0      emitted: [('B','poi-1')]                 window_end 2026-11-05 12:00Z
t+8d    emitted: [('F','poi-1'), ('F','poi-2')]  cross_book_duplicates = 0
same executable plan: True  (identical CrossBookPlanKey)
```

Root cause chain:

* `_prune_plans` (`parallel_books.py` L609-623) drops the plan once `as_of > window_end`.
* Its docstring claims "the adapter's own story guard still covers the resting/open order".
* `story_key`/`same_story` include `trigger` (`risk/story_guard.py`, rule 4) → a B plan and an
  F plan are **never** `same_story`, so the adapter cannot catch it.
* Probe 3 confirms the adapter independently: two cross-tag candidates with the identical plan
  queue as **2** candidates, `duplicate_story_dropped = 0`.

Design §3.3/R-H ("the account may not hold this plan twice") is therefore enforced only within a
single menu window and only within one bar's book loop.

### 3.3 Adapter book-blindness at POI granularity

`queue_menu_candidate` stores `self._menu_pending[str(poi_id)] = {...}` (L397) and
`_settle_menu_candidate` pops by `poi_id` (L464). With two books winning on the same POI — the
case R-H deliberately allows when the plans differ (different tag ⇒ different entry/SL geometry) —
the second winner overwrites the first pending confirmation. Evidence from the probe: both
candidates were submitted (`menu_submitted = 2`, `story_claims = 2`) while the pending map can
hold only one key; `on_candidate_accepted` then seals **every** claim with that owner (`seal_story`
loops by `owner == poi_id`), so both books' claims are sealed by one book's placement.

---

## 4. Findings

### CRITICAL

**C-1 — Cross-book dedupe stops at the menu window; the only backstop is trigger-keyed, so an
identical plan can be placed twice.**
`04_SRC/smc/orchestration/parallel_books.py` L609-623 (`_prune_plans`, and its false
justification), L626-635 (`_duplicate_owner`); `04_SRC/smc/risk/story_guard.py` `same_story`
(trigger in identity); `04_SRC/smc/backtest/pipeline_adapter.py` L324-359 (`_duplicate_story`).
Reproduced: §3.2. Impact: exactly the R-H failure the design exists to prevent — one account,
two tickets, same direction/entry/SL/TP/zone. It did not fire on feb25 (0 duplicates), so the
measurement neither proves nor exercises the guarantee; the note's "gate is unit-proven" is
true only for same-bar/same-window confirmations.
**Fix (not applied):** scope the plan memory by *liveness*, not by menu window — prune against
`runner.story_live_plans()` / the adapter's live plan set (the seam R-A already uses), or add a
trigger-excluded cross-book plan guard inside `_duplicate_story` for book-stamped candidates.
Add a regression test: B plan at t0, window closed, F plan at t0+Δ → one ticket.

### MAJOR

**M-1 — `R-K` bypass via dict book entries.** `_coerce_book` L207-224 vs L226-227. Probe §3.1.
`D` must be refused after the tag letter is resolved, for every config shape.

**M-2 — Adapter state is keyed by POI, not (book, POI).** `pipeline_adapter.py` L397, L462-471,
L667, L671; probe §3.3. A second book's different-plan confirmation is silently replaced, with no
counter — design §8.1-3 forbids unattributed gaps. Either key the pending/workflow maps by
`(book_id, poi_id)` or refuse a second winner per POI per bar with a counted reason.

**M-3 — Tiers no book carries fall back to the legacy seek path.** `menu_covers_poi` L217-245
consults `menu.tier_for(zone_tf)`; `ParallelBookMenu.tier_for` L442-448 returns `None` when no
book carries the tier, so `pipeline_adapter.py` L549-556 opens the seek route for those POIs. With
a mid-only selection (`B`, `C`, `E`, `A`) every **D1** POI is routed outside the book layer: no
book stamp, no `SMC-<TAG>-` comment, no cross-book dedupe. `F+B` is safe (F carries DAY), and the
harness masks this by restricting its POI universe to covered tiers (`_reconstruct`, `covered`).
Either validate that the selection union covers all four shipped tiers, or count
`poi_outside_books` explicitly instead of silently re-enabling the archived path.

**M-4 — Risk blocks are not attributed per book.** Design §8.3-7 requires it; the artifacts carry
`blocked_by_reason` only (`runner` report), and the note concedes the skips are "shared-envelope
evidence, not book-specific". Journals cannot answer "which book hit the breaker".
**Fix:** stamp `book_id` on the risk verdict event for book-stamped candidates.

**M-5 — No guardrail implementing R-L (shadow/dry-run only).** `run_operator._build_stack`
L531-556 builds `ParallelBookMenu` for any non-empty list; with `cfg.dry_run = false` the operator
places **live** orders from multiple books. The default is safe (key empty everywhere), but the
spike's own ruling says shadow/dry_run until the envelope is ruled. Refuse (or loud-warn) when
`parallel_books` is non-empty and `dry_run` is false.

### MINOR

1. **m-1** Note §2 cites "R1 B/MID 20 fills, F/MID 28 fills" — those are the LONG-only R1 runs;
   the spike's 25/29 are two-hypothesis unions. Label the basis.
2. **m-2** A plan whose `window_end_ts` is `None` is never pruned (`_prune_plans`), so it can
   suppress a later identical plan indefinitely (and grows the list).
3. **m-3** `assert_tag_purity` (L495-509) is called by the harness only; the live multiplexer
   never asserts purity. Purity is structural (narrowed `trigger_types`), but the fail-loud check
   is not a runtime guarantee.
4. **m-4** `ParallelBookMenu.winners` (L408-414) concatenates every per-book winner, including
   ones the multiplexer suppressed. A reader summing `winners` overstates placed tickets;
   `book_emitted_counts` is the authoritative counter.
5. **m-5** Design line citations drifted after the `tier_for` change (design says `tier_for` L424 /
   `register_armed` L450-486; code is L422 / L460). Cosmetic but the doc is cited as authority.
6. **m-6** `self._events` (L389) grows without bound in a long session (one dict per
   opposite-direction/dedupe event).
7. **m-7** Dict book entries may set any tier set per tag (e.g. `B` with `DAY`), bypassing the
   evidence-based `TAG_BOOK_TIER_SETS`. Permissive, not validated.
8. **m-8** The note's runtime framing ("roughly one extra engine pass") is directionally right but
   the artifact ratio is 1448.2 / 1079.7 = **1.34×**; quote the ratio.

---

## 5. Promote matrix

| Target | Verdict | Preconditions |
|---|---|---|
| **Smoke — `books=["F","B"]`, `dry_run=true`** | **YES (conditional)** | Menu layer is sound; D1 coverage exists via F; defaults untouched. Must accept C-1 (unproven on data, 0 fires) and M-2 (silent per-POI collision) as known demo risks, and M-5 must be honoured manually. Do not use a mid-only selection until M-3 is fixed. |
| **Research BT — `[F,B,C,E,A]`** | **AFTER_FIXES** | M-3 must be resolved (A/B/C/E carry no DAY, so D1 POIs would route through the legacy seek path and pollute any production-shaped BT), and C-1 must be fixed or the run cannot claim R-H safety. R-G budget still unproven (six books). |
| **Installer / live default** | **NO** | Requires the default-enable ruling (design Phase 3), R-J on the production arm seam, R-D magic sign-off, R-G budget, R-L enforcement, F4 envelope, plus C-1/M-1/M-2 closed. |

---

## 6. Checks actually run

* `cd 04_SRC && PYTHONPATH=. python -m pytest -q tests/test_parallel_books.py` → **21 passed**.
* Full suite (read-only, same command without a filter) → recorded in §7.
* Probes §3.1–§3.3: read-only scripts, no source edits, no shared state mutated.
* Artifact re-derivation of every headline note number (§2-H) from
  `06_RESEARCH/results/parallel_book_spike/` (parity JSONs, `summary_feb25_F,B.json`, per-run
  `summary.json`, `fills.csv`, `winners.json`).
* **Not run:** any backtest, any live/paper session, any MT5 interaction, `locked_constants` diff
  beyond `git diff` (empty for `00_LOCKED`/`04_SRC/smc/config` in the spike commit), statement
  review of the `SMC-<TAG>-` comment (no live statement exists yet).

---

## 7. Suite result

```text
cd 04_SRC && PYTHONPATH=. python -m pytest -q
1544 passed, 7 skipped in 8.01s

python -m pytest -q tests/test_parallel_books.py
21 passed in 0.15s
```

Read-only re-run; no test was modified, skipped or weakened.

---

## 8. Recommended fix list (priority order; none applied in this audit)

1. **C-1** — liveness-scope the cross-book plan memory (or add a trigger-excluded plan guard for
   book-stamped candidates in `_duplicate_story`); regression test for "second book after window
   close".
2. **M-1** — enforce `EXCLUDED_TAGS` on the resolved tag in `_coerce_book`'s dict branch.
3. **M-2** — key adapter pending/workflow/claim state by `(book_id, poi_id)`, or count and refuse
   the second winner per POI per bar.
4. **M-3** — validate that the selected books' tier union covers the four shipped tiers (or count
   POIs that fall through to the legacy seek path).
5. **M-4** — carry `book_id` on risk-block events.
6. **M-5** — refuse/loud-warn `parallel_books` with `dry_run=false` (R-L).
7. **m-1…m-8** — note/doc wording, unbounded `_events`, `window_end=None` pruning, live purity
   assertion, `winners` semantics, tier-set validation.

No drive-by edits were made: the only CRITICAL is not "tiny", and the audit's mandate is
findings-first. `LOGIC_CHANGED: NO`.
