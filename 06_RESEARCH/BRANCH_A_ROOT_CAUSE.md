# BRANCH A — ROOT CAUSE (Phase 0 pack, product path only)

**Status:** COMPLETE 2026-11-26. **`LOGIC_CHANGED: NO`** — no code change in this phase.
**Scope:** why Trigger A (CHOCH reversal) produced **0 placements / 0 fills** on the
product path in the frozen liveness window. One branch only; F is reference and was
not touched.
**Authority:** Lead Architect *BRANCH A — E2E engineering (product path only)*.
**Upstream evidence:** `06_RESEARCH/PRODUCT_BRANCH_LIVENESS_REPORT.md`; artifacts
`06_RESEARCH/results/product_branch_liveness/` (gitignored).
**Pre-registered window (unchanged, not re-picked):** warm-up M1 from 2025-08-01;
exec **2025-09-01 00:00 → 2025-11-30 23:59 UTC** on M5 (17,840 bars), 124 detection
batches. Single continuous run, 4,594.2 s, `BATCH_ERRORS=0`, `MENU_ERRORS=0`.

---

## 1. A's funnel, exactly

| Stage | Count | Source |
|---|---:|---|
| Non-`None` completions observed | **9** | `completions.csv`, `summary.BY_TRIGGER.A.completed_signals` |
| Distinct POIs with a completion | **6** | `summary.BY_TRIGGER.A.distinct_pois_with_completion` |
| Rejected by the C3 in-between gate | **6** | `summary.BY_TRIGGER.A.gate_rejected_c3` |
| Routes (menu winners) | **3** | `winners.csv` rows 37–39 |
| Reached the runner's risk seam | **2** | `blocks.csv` (2 `session` rows) |
| Dropped at adapter intake (ONE-STORY) | **1** | arithmetic + absence of any runner row |
| Placed | **0** | `orders.csv` has no A ticket |
| Fills | **0** | `fills.csv` has no A ticket |

`9 = 6 C3 rejects + 3 routes`, and `3 routes = 2 risk blocks + 1 intake drop`.
No A candidate ever reached `PendingOrderBook.place`, so no A fill was possible.

---

## 2. Every A event, with its exact reason and code path

Bar indices below are as recorded by the instrumentation (M1 index for the M15 tier,
M5 index for H4/H1 tiers); they are **not** comparable across rows.

| # | POI | Det/Conf | Completion (UTC close) | Outcome | Reason string / path |
|---|---|---|---|---:|---|
| 1 | `poi-001034` | M15/M1 | — (bar 41,053) | C3 reject | `candidate_from_route(..., completion_price=…)` → `None`; menu records `rejected_M1_not_in_between` |
| 2 | `poi-003595` | H4/M5 | — (bar 14,303) | C3 reject | same gate (`not_in_between`) |
| 3 | `poi-003595` | H4/M5 | — (bar 14,851) | C3 reject | same gate (`not_in_between`) |
| 4 | `poi-002883` | H1/M5 | — (bar 17,334) | C3 reject | same gate (`not_in_between`) |
| 5 | `poi-004034` | H4/M5 | — (bar 20,646) | C3 reject | same gate (`not_in_between`) |
| 6 | `poi-004034` | H4/M5 | — (bar 20,923) | C3 reject | same gate (`not_in_between`) |
| 7 | `poi-004984` | H4/M5 | **2025-11-18 20:15** | **route → risk block** | `blocked_by="session"` at bar 21,451 |
| 8 | `poi-005169` | H4/M5 | **2025-11-18 20:15** | **route → intake drop** | ONE-STORY duplicate of `poi-004984` (no runner row, no ticket) |
| 9 | `poi-004034` | H4/M5 | **2025-11-26 23:10** | **route → risk block** | `blocked_by="session"` at bar 23,130 |

Note that `poi-004034` completed three times: twice outside the POI body (C3) and, on
the third try (2025-11-26), inside it — and that third one is the route the session
gate then blocked.

---

## 3. Route-by-route detail

### 3.1 `poi-004984` — session gate (route 1 of 3)

- Plan (from `winners.csv`): H4 tier, `H4/M5`, **SHORT**, entry **4073.375**, SL
  **4083.6034388930066**, TP **4055.6624814265797**; armed 2025-10-28 19:45, swept
  2025-11-14 08:00, confirmed **2025-11-18 20:15 UTC**.
- Reject: `04_SRC/smc/risk/risk_engine.py:215-218` —
  `if request.allowed_sessions is not None and not is_allowed_session(request.now, …):
  return EntryDecision(action=HOLD, blocked_by=BLOCK_SESSION)`.
  Called from the entry step of `04_SRC/smc/backtest/runner.py` (`_process_entries`),
  which appends the `BlockedEntry(blocked_by="session", …)` row.
- Why 20:15 is outside: `04_SRC/smc/utils/timestamps.py:14-16` and
  `04_SRC/smc/config/locked_constants.py:104-109` — Asia 00–07, London 07–13,
  NY 13–20 UTC, end-exclusive; **20:00–24:00 UTC belong to no session**
  (`detect_session` returns `None`, `in_session` is `False`).

### 3.2 `poi-005169` — ONE-STORY intake drop (route 2 of 3)

- Plan: **identical** to `poi-004984` on every value the rule reads — H4 tier, `H4/M5`,
  SHORT, entry 4073.375, SL 4083.6034388930066, TP 4055.6624814265797, same
  confirmation bar 21,451 (both winners were produced by the same batch).
- Reject: `04_SRC/smc/backtest/pipeline_adapter.py` `queue_menu_candidate` →
  `_duplicate_story(candidate, source="menu")` → `_drop_duplicate_poi(candidate)`.
  The rule itself is `04_SRC/smc/risk/story_guard.py:1-30` (locked 2026-11-15):
  same direction + overlapping zone + same trigger + exact entry/SL/TP.
- Proof that this is the dropped route (not inference from a count alone):
  1. `menu_submitted = 32` while `routes = 39` → **exactly 7** winners never reached
     the risk seam, and `queue_menu_candidate` has exactly one non-submitting exit
     (the duplicate branch; `candidate is None` returns before the increment).
  2. The runner-facing side reconciles to 30 F + 2 A: 24 F placements (22 immediate
     + 2 via R9 intents) + 6 F `session` blocks + 2 F `skip_place_far_from_zone`
     blocks + 2 A `session` blocks = **32 submissions**. Therefore F contributed 6
     intake drops and A contributed **1**.
  3. `poi-005169` is the only A route with neither a ticket nor a `blocked_log` row.
  4. `same_story` requires known, overlapping zone bounds; had the predicate not held,
     the candidate would have been submitted and produced a runner row (it has
     none). The drop therefore proves the predicate held.

### 3.3 `poi-004034` — session gate (route 3 of 3)

- Plan: H4 tier, `H4/M5`, **LONG**, entry **4167.225**, SL **4161.0897888156605**,
  TP **4177.027815791187**; armed 2025-10-16 11:45, swept 2025-11-26 08:00,
  confirmed **2025-11-26 23:10 UTC**.
- Reject: same gate and same code as §3.1 (`BLOCK_SESSION`, `risk_engine.py:215-218`,
  blocked row at bar 23,130). 23:10 UTC is in the 20:00–24:00 no-session gap.

---

## 4. Why the session blocks were not retried (and why that is as-coded)

This is the only place a "wiring" reading was plausible, so it is recorded explicitly.

- `04_SRC/smc/backtest/pipeline_adapter.py:565-567` — F7 pending/resubmission is
  armed **only** when the runner advertises `supports_candidate_outcomes`.
- Only `PaperRunner` advertises it (`04_SRC/smc/paper/runner.py:242-245`).
  `BacktestRunner` does not — so `queue_menu_candidate` submits once and never
  creates a `_menu_pending` slot. Measured: `menu_retry_blocked=0`,
  `menu_resubmitted=0`, `menu_pending=0`, `menu_expired_unplaced=0`.
- This is **documented product behaviour**, not a regression:
  `06_RESEARCH/R0_TRIGGER_ADMISSION_MAP.md:73-76` — "the research `BacktestRunner`
  does not report per-candidate outcomes (`supports_candidate_outcomes` absent) →
  historical one-submit semantics — this is the as-coded product_1y behavior";
  `06_RESEARCH/MENU_TRADE_FUNNEL_1M_NOTE.md:75` records the same for the backtest
  harness; `06_RESEARCH/F5_F7_LIFECYCLE_NOTE.md:74-77` states retry is the
  live/paper path.

Consequence: a confirmation whose single submission is blocked by a risk gate is
gone for that route — the gate is not re-run on a later bar. Since the two A blocks
happened at 20:15 and 23:10 UTC, a retry would have re-run the *same* gate on
subsequent bars and the first in-session bar would have been the honest test; that
test does not happen on the backtest path.

---

## 5. Classification (a) / (b) / (c)

| Event | Count | Class | Basis |
|---|---:|---|---|
| C3 `not_in_between` reject | 6 | **(a) intentional policy** | Shared C3 gate, LOCKED; menu choke point `product_menu_mtf.py` `_candidate` (returns `None` when `candidate_from_route(..., completion_price=…)` is `None`), recorded as `rejected_<tf>_not_in_between` |
| Session block at placement | 2 | **(a) intentional policy** | LOCKED_DECISIONS §2 hours; `risk_engine.py:215-218`; `locked_constants.py:104-109` |
| ONE-STORY duplicate drop | 1 | **(a) locked policy** | `story_guard.py` rule locked 2026-11-15; `pipeline_adapter.py` intake branch |
| One-submit (no F7 retry) | (affects both blocks) | **(a) as-coded composition** | Documented one-submit backtest semantics (§4 above) |

**No (b) bug and no (c) config defect was found.** In particular the session case is
**not** (c): the harness already allows *all three* sessions
(`allowed_sessions=(ASIA, LONDON, NEW_YORK)`), and no value of `allowed_sessions`
can admit 20:00–24:00 because `is_allowed_session` first requires
`detect_session(...) is not None` (`04_SRC/smc/execution/session_filter.py:24-32`).
Admitting those hours would require a **LOCKED §2 supersession**, i.e. a policy
change, not a config restore.

---

## 6. What was ruled out (so the pack is falsifiable)

- **Not an arming/census problem.** 29 H4 POIs were armed (160 armed total); A
  completed on H4 7 times and on H1/M15 once each. A is armed and its trigger fires.
- **Not a tier-exclusion problem.** A is in `_TIER_ADF` (H4/H1/M15) and in the DAY
  set (`product_menu_mtf.py:239-254`).
- **Not a menu-window problem.** All three winners were produced by the engine
  (`winners.csv` rows 37–39, `WON` episodes), so each completion was inside its
  `sweep_index + 20` detection-bar window.
- **Not a sizing / spread / breaker / same-level / R7 problem.** The only runner
  reason strings attached to A are `session` ×2; nothing else was reached.
- **Not a C3 mis-fire on the routed events.** The routed completions passed C3; the
  6 rejects are the completions whose close was outside the POI body.
- **Not a post-route expiry problem.** `expired_section23_unfilled=0`,
  `expired_give_up_unfilled=0`, `withdrawn_before_fill=0` for A — no A order existed.

---

## 7. Timing observation (fact, not a proposal)

All three A routes occur in the **last 8 trading days** of the window (2025-11-18 and
2025-11-26), and two of the three confirmation bar closes land in the 20:00–24:00 UTC
no-session gap. A is a low-frequency branch on this window (3 routes in 3 months), so
each single-attempt outcome is decisive for its verdict. This is reported as a shape
of the sample, not as a reason to widen anything.

---

## 8. Phase-1 gate decision

Every A death is class **(a)**. Per the task's Phase-1 rule — *"if all A deaths are
intentional policy (a): do NOT widen sessions or delete one-story … STOP before
implementing policy change"* — **no code was changed in this phase** and no
policy change is implemented. The two Architect-facing options that the evidence
supports (accept A as session-gated, or rule F7 backtest parity as a dated product
lifecycle change) are set out in `06_RESEARCH/BRANCH_A_E2E_REPORT.md` §5.

**Bans honoured in this pack:** no TP/SL/age/rank/zone-quality change, no trigger
B/C/D/E/F edit, no volume proxy for D, no session widening, no ONE-STORY softening,
no `locked_constants.py` change, no expectancy/PF language.
