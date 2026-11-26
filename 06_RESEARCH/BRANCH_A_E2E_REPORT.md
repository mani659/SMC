# BRANCH A — E2E REPORT (product path only)

**Verdict: `DEFER_RECOMMENDED`** (factual state: **BLOCKED** by intentional policy).
**`LOGIC_CHANGED: NO`** · **`CODE_CHANGED: NO`** · **A fills: 0** · **A routes: 3**
**Window:** exec 2025-09-01 → 2025-11-30 (M5), warm-up 2025-08-01 — the same frozen
liveness window, not re-picked.
**Authority:** Lead Architect *BRANCH A — E2E engineering (product path only)*.
**Phase 0 pack:** `06_RESEARCH/BRANCH_A_ROOT_CAUSE.md`.

---

## 1. One-line answer

Trigger A was never blocked by a wiring defect. In the frozen window its **only three
routes** were killed by two intentional product rules — the **LOCKED §2 session gate
(2)** and the **locked ONE-STORY duplicate rule (1)** — and the backtest product
composition submits each confirmation **once** by documented design, so each kill was
final for that route. Making A fill would require a **policy ruling**, not an
engineering repair.

---

## 2. Funnel — before / after

| Stage | Before (measured 2026-11-25) | After |
|---|---:|---:|
| Non-`None` completions | 9 | **9 (not re-run)** |
| Distinct POIs | 6 | 6 |
| C3 `not_in_between` rejects | 6 | 6 |
| Routes | 3 | 3 |
| Risk-seam submissions | 2 | 2 |
| Intake drops (ONE-STORY) | 1 | 1 |
| Placed | **0** | **0** |
| Fills | **0** | **0** |

**There is no "after" run, and none is claimed.** No code was changed, so a re-run
would only re-measure the same composition; spending another ~77 minutes of compute
to reproduce an unchanged funnel was not done. The distinct-POI and route values
above are the Phase-0 re-read of the existing artifacts (`winners.csv`,
`blocks.csv`, `completions.csv`, `summary.json`), not a second run.

---

## 3. Root cause (single statement)

> **A's confirmations die at the risk seam on a single submission.** All three A
> routes in the window reached the entry pipeline; two were submitted at a bar close
> in the LOCKED §2 **20:00–24:00 UTC no-session gap** (2025-11-18 20:15, 2025-11-26
> 23:10), and the third was an **identical duplicate plan** of the first and was
> retired at adapter intake by the locked ONE-STORY rule. Because `BacktestRunner`
> does not advertise `supports_candidate_outcomes`, the F7 retry seam is inert on this
> path, so neither session block was re-attempted on a later bar.

Supporting facts: `9 completions = 6 C3 rejects + 3 routes`; `3 routes = 2 session
blocks + 1 ONE-STORY drop`; `menu_submitted 32 vs 39 routes` decomposes exactly to 6 F
+ 1 A intake drops; no A order exists in `orders.csv`, so no A fill was possible.
Full per-event table and citations: `BRANCH_A_ROOT_CAUSE.md` §2–§4.

---

## 4. Code citations (the whole A path)

| Step | Where | Behaviour that decided A |
|---|---|---|
| Tier membership | `product_menu_mtf.py:239-254` | A is in `_TIER_ADF` (H4/H1/M15) and the DAY set — **not** excluded |
| Confirmation | `product_menu_mtf.py` `_route_for` / `_win` | 9 completions; 6 returned `None` at `_candidate` (C3) |
| C3 gate | `product_menu_mtf.py` `_candidate`; `in_between` via `candidate_from_route(completion_price=…)` | 6 completions closed outside the POI body → `rejected_<tf>_not_in_between` |
| Intake dedupe | `pipeline_adapter.py` `queue_menu_candidate` → `_duplicate_story` → `_drop_duplicate_poi`; rule in `risk/story_guard.py` | `poi-005169` collapsed into `poi-004984` (same direction/trigger/entry/SL/TP/overlapping zone) |
| Session gate | `risk/risk_engine.py:215-218` (`BLOCK_SESSION`), called from `backtest/runner.py` `_process_entries` | 2 routes blocked at 20:15 / 23:10 UTC |
| Session definition | `utils/timestamps.py:14-16`; `config/locked_constants.py:104-109` | Asia 00–07, London 07–13, NY 13–20 UTC; 20:00–24:00 = no session |
| No retry | `pipeline_adapter.py:565-567` (+ `_menu_deadline`, `_resubmit_menu_pending`); `paper/runner.py:245` | F7 pending is created only for outcome-reporting runners; `BacktestRunner` is not one |

Documented intent for the one-submit behaviour:
`06_RESEARCH/R0_TRIGGER_ADMISSION_MAP.md:73-76` ("historical one-submit semantics —
this is the as-coded product_1y behavior"), `06_RESEARCH/MENU_TRADE_FUNNEL_1M_NOTE.md:75`,
`06_RESEARCH/F5_F7_LIFECYCLE_NOTE.md:74-77` (retry is the live/paper path).

---

## 5. Architect options (none implemented)

**Option 1 — ACCEPT as product behaviour (recommended for this window).**
Record A as *session-gated on the H4 tier*, i.e. `ROUTED_ONLY` is the truthful product
answer for 2025-09→11. No code, no constant, no window change. Consequence: A stays
outside any "all branches fill" claim; the programme claim stays multi-branch
**routing** / single-branch **filling**.

**Option 2 — Rule F7 backtest parity (dated lifecycle change; not A-only).**
Enable `supports_candidate_outcomes` on `BacktestRunner` and settle outcomes at its
terminal points, so a session/news/breaker block resubmits the same confirmation until
its menu window closes — the behaviour `queue_menu_candidate`'s own docstring states as
the contract ("a risk gate … must not silently destroy a confirmation that is still
inside its window") and that `PaperRunner` already implements.
- It does **not** widen sessions or weaken ONE-STORY: the same gate is re-run on each
  bar, and the 20:15/23:10 confirmations would simply be retried into the next Asia
  bar.
- It is **global**: the 6 F `session` blocks and any future branch would retry too, so
  F's frozen LIVE reference numbers would change. It therefore needs an explicit
  ruling and a re-baseline, not an engineer's silent flip.
- Expected effect on A is **unmeasured** and is not claimed here; it would require the
  same-window re-run after the ruling.

**Option 3 — DEFER A.** Suspend the "A must fill" milestone until a window or policy
ruling says what A is for. No code.

**Option 4 — Change the session policy.** Would require a dated LOCKED §2
supersession. Engineering does **not** propose it: the two blocks are late-NY/after-hours
confirmations, not a misconfigured allow-list (the harness already allows all three
sessions, and `is_allowed_session` cannot admit 20:00–24:00 without changing §2).

---

## 6. Why no code changed

1. Every A death is class **(a) intentional policy** (`BRANCH_A_ROOT_CAUSE.md` §5);
   the task's Phase-1 rule says stop before implementing a policy change.
2. The only genuine wiring candidate (F7) is **not A-isolated** and would alter F's
   frozen reference funnel; enabling it is a product-lifecycle decision.
3. No threshold, session, tier, TP/SL/age/rank or zone-quality change is warranted by
   the evidence, and each is banned in this task.

No test was added because no behaviour changed. No `04_SRC` file, no
`locked_constants.py` value and no `parallel_books` / live default was touched.

---

## 7. What "LIVE" would require (definition kept honest)

Success was defined as **≥1 A fill in the pre-registered window, with chain
completion → route → place → fill attributed to Trigger A**. That chain was not
completed and cannot be without a policy ruling. `BLOCKED`/`DEFER_RECOMMENDED` is
reported rather than a fabricated LIVE: A has 0 placements, not 0-by-instrumentation.

---

## 8. Limits

- Single run from the liveness audit; no determinism/byte-identity claim, and no
  re-run in this task.
- Attribution of the third route to ONE-STORY is by the intake-path arithmetic and the
  absence of any runner row (the guard logs an aggregate counter, not a per-winner
  row). The argument is spelled out in `BRANCH_A_ROOT_CAUSE.md` §3.2 so it can be
  challenged.
- No expectancy, PF, win-rate or edge statement is made anywhere in this report.
  `NET_PL_DIAGNOSTIC` from the liveness run remains a raw `price × volume` label, not
  performance, and is not used here.

---

## 9. Governance

- Deliverables: this report + `06_RESEARCH/BRANCH_A_ROOT_CAUSE.md`; no new harness, no
  new artifacts (the liveness artifacts are re-read, not regenerated).
- `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`, `CHANGELOG.md` updated.
- **NEXT = Architect accept A verdict → Branch B only.** Branch B must not start before
  the A ruling.
