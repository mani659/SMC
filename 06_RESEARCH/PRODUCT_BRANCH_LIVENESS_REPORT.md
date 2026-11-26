# PRODUCT BRANCH LIVENESS — per-trigger funnel audit (product menu path)

**Status:** COMPLETE 2026-11-25. **`LOGIC_CHANGED: NO`** — measurement only.
**Scope:** functional milestone only — can each Stage-3 trigger branch complete the
product funnel? **No expectancy, no PF, no edge, no retune.**
**Authority:** Lead Architect instruction *BRANCH LIVENESS AUDIT — product path only*.

- Harness: `06_RESEARCH/scripts/product_branch_liveness.py` (reuses the frozen
  `menu_trade_funnel` composition; instrumentation restored in `finally`)
- Artifacts (gitignored): `06_RESEARCH/results/product_branch_liveness/`
  (`summary.json`, `winners.csv`, `orders.csv`, `fills.csv`, `blocks.csv`,
  `completions.csv`, `run.log`, `pytest.log`)
- Run: single continuous run, `PLACED == FILLED` chain end-to-end,
  `BATCH_ERRORS=0`, `MENU_ERRORS=0`, elapsed **4,594 s (76.6 min)**, M5 bars
  processed **17,840**.

---

## 1. Product composition (surveyed, code-cited)

The operator/live-shaped product path is the **sweep → LTF confirmation menu**,
not the research seek scan. Composition as measured:

| Element | Value | Code |
|---|---|---|
| Detection TFs (POI/structure) | **D1, H4, H1, M15** | `product_menu_mtf.py:222-227` `PRODUCT_MENU_TIERS`; `product_menu_mtf.py:230-232` |
| Execution TF | **M5** | `multi_tf_runtime.py:327-336` (`execution_timeframe=M5`), harness `EXEC_TF` |
| Confirmation / trigger-scan TFs | **H1** (DAY tier), **M5+M15** (H4), **M5+M1** (H1), **M1** (M15) | `product_menu_mtf.py:222-227` |
| Trigger registration in the router | `default_triggers()` returns **all six A–F** (`trigger_router.py:54-64`); the menu then filters per tier | `trigger_router.py:54`; `product_menu_mtf.py:701-712` `_router_for` |
| Tier trigger subsets | **DAY = A–F** (`_DAY_TRIGGERS = tuple(TriggerType)`); **H4/H1/M15 = A, D, F** (`_TIER_ADF`) | `product_menu_mtf.py:239-254` |
| Hard disable (code/data) | **Trigger D**: requires `engulfer.volume < engulfed.volume` (`trigger_d_two_bar.py:56-57`); the XAUUSD M1 feed has **volume == 0.0 on 1,768,123/1,768,123 bars**, so `0 < 0` is false — D cannot fire (A5 ruling on record) | `trigger_d_two_bar.py:56-57`; data check this run |
| Session gate | **all sessions allowed** (`ASIA, LONDON, NEW_YORK`) | harness `RunnerConfig.allowed_sessions` (frozen FR-4 convention) |
| News gate | **dormant** (`news_events=[]`) | same |
| Spread / cost | `spread_price=0.0`, default `CostConfig` — machine-completeness, not cost realism | same |
| W1 | **not in the arm path**; optional M8 context only (`OPTIONAL_W1_TIMEFRAME`), and the harness does not provision it | `multi_tf_runtime.py:64-69`, `:321-332` |
| D1 → M8 | D1 and H4 are forwarded to M8 (`supply_d1_to_m8=True` by default) | `multi_tf_runtime.py:335`, `:479-500` |
| Runner entrypoint | `product_branch_liveness.py` → `MultiTFProductRuntime.run_batch` → `ProductMenuEngine.register_armed/on_execution_bar` → `PipelineAdapter.queue_menu_candidate` → `BacktestRunner` (`BarLoop` on M5) | harness `run()`; `menu_trade_funnel.MenuCycle` |

**P0 honesty — product path ≠ full research superset.** The product menu arms a
POI only after an R2 sweep, and only four of the six triggers are confirmable on
the H4/H1/M15 tiers. B/C/E are confirmable **only on the DAY (D1→H1) tier**.
The research superset (seek scan + pure-tag books) can route B/C/E on any tier;
those results are **book-scoped and are not used here as liveness evidence**
(secondary comparison only, §7).

---

## 2. Window (declared before any count was read)

- **Warm-up:** M1 from **2025-08-01** (UTC).
- **Exec bounds:** **2025-09-01 00:00 → 2025-11-30 23:59 UTC inclusive**
  (M5; 17,840 execution bars). Detection batches: every 48th M15 close
  (**124 batches**, frozen plan-complement cadence).
- **Why this window:** it is the LOCKED Phase-4 product calendar
  (`phase4_unified_backtest.py`: load 2025-08-01, exec 2025-09-01 → 2025-11-30),
  i.e. an already-used product-shaped window, not a new pick. No window
  shopping after counts: the run is a single continuous pass with no restarts.
- Data fail-loud: `07_DATA/XAUUSD_M1.parquet` required; all six streams
  (D1/H4/H1/M15/M5/M1) resampled from the same M1 spine.

**Continuity caveat (method, not result):** the menu path is known to be
super-linear under many live episodes (documented in PFE-2 §1.1 / product_1y).
This run reproduced that: 284 bars/s cold → ~3.5 bars/s by bar 17,000. It still
completed the full window in one pass, so the counts below are from a
**continuous** run, not a tiled one.

---

## 3. Funnel counts

### 3.1 Totals

| Stage | Count |
|---|---:|
| Armed POIs (total, accepted registrations) | **160** |
| — by detection TF | D1 **68** · H4 **29** · H1 **18** · M15 **45** |
| — still live at window end | 116 |
| Menu episodes opened | **82** |
| — expired unfilled (`episodes_expired`) | 41 |
| — won (`winners_total`) | **39** |
| — still ACTIVE at end | 2 |
| Confirmation bars evaluated | 21,952 |
| Routes (winners / candidates emitted) | **39** |
| Submitted to the risk seam (`menu_submitted`) | 32 |
| Placed (accepted into the book) | **24** |
| Fills | **21** |
| Closed | 21 (SL 16 / TP 5) |
| Blocked pre-place (`blocked_log`) | **10** — `session` 8, `skip_place_far_from_zone` 2 |
| Expired unfilled (§23) | **3** |
| Withdrawn before fill | **2** |
| Open at window end | 0 |

**Unfilled arithmetic:** 24 placed − 21 filled = **3 placements never filled**
(verified ticket-by-ticket: every fill ticket ⊆ the 24 placement tickets). The
book's own counters report 3 §23 expiries and 2 cancellations before fill; they
sum to 5 against 3 unfilled placements because they are not persisted per ticket
in this instrumentation (one ticket is recorded by both surfaces). **The
unfilled total is 3, not 5**; no placement is unaccounted for.

`NET_PL_DIAGNOSTIC` = `n_closed=21`, raw `price*volume` sum **−8.324965** —
**raw ledger units, NOT performance, NOT edge** (zero spread/cost).

### 3.2 Per trigger

`completed_signals` counts every non-`None` completion the router observed on any
scanned confirmation bar/TF. Because a tier evaluates **all** its confirmation
TFs and keeps only the earliest completion, a completion on the losing TF is
counted but produces neither a route nor a C3 rejection (this is why F's
67 completions do not decompose into 36 routes + 21 rejects).

| | completed_signals | distinct POIs | routes | C3 gate rejects | placed | fills | closed | blocked_pre_place | §23 expired | withdrawn |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **A** | 9 | 6 | 3 | 6 | 0 | 0 | 0 | 2 (`session` 2) | 0 | 0 |
| **B** | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| **C** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **D** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **E** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **F** | 67 | 43 | 36 | 21 | 24 | 21 | 21 | 8 (`session` 6, `skip_far` 2) | 3 | 2 |

Completion and route shape by tier:

- Completions: `F|M15/M1 39`, `F|D1/H1 13`, `F|H4/M5 7`, `F|H1/M5 3`,
  `F|H1/M1 3`, `F|H4/M15 2`, `A|H4/M5 7`, `A|H1/M5 1`, `A|M15/M1 1`,
  `B|D1/H1 5`.
- Routes: `F` — M15 16 · DAY(D1/H1) 9 · H4/M5 7 · H1/M1 2 · H1/M5 1 ·
  H4/M15 1; `A` — H4/M5 3.

**Zero explanations (required).**

- **A (9 completions, 3 routes, 0 fills).** All three routes are H4/M5 A-CHOCH
  plans at the end of the window. Two were blocked by the **session** gate
  (`poi-004984` and `poi-004034`, both `blocked_by=session`). The third
  (`poi-005169`) has no `blocked_log` row and no book ticket; its plan is
  *identical* to `poi-004984` (same route bar/entry/SL/TP), and exactly **7 of
  the 39 winners** never reached the risk seam (`menu_submitted=32`). The
  attribution is therefore by elimination — **ONE-STORY intake retirement** (the
  dedupe does not log a per-winner row) — not by a direct per-winner record. No
  A order was ever placed, so no A fill was possible.
- **B (5 completions, 0 routes).** All five are **the same H1 bar**
  (H1 series index 1717: opens 2025-11-13 18:00, **closes 19:00 UTC** — see
  `BRANCH_B_ROOT_CAUSE.md` §1) completing B on five different armed **D1** POIs.
  Every one was rejected by the shared **C3 in-between containment gate**
  (`_candidate → None`, `not_in_between`) — a completion outside the POI body is
  not a valid confirmation. Signal exists; lifecycle stops at the gate.
- **C (0 completions).** C is wired (DAY tier, `tuple(TriggerType)`) and its
  router is constructed for that tier, but no C completion was observed on any
  scanned bar. 68 D1 POIs were armed, so this is not an arming starvation.
- **D (0 completions).** **OFF BY DESIGN on this feed**: `engulfer.volume <
  engulfed.volume` can never hold when every bar's volume is 0.0 (measured on
  the full dataset). No proxy was substituted (explicitly banned in this audit).
- **E (0 completions).** Same wiring status as C (DAY tier only); no E
  completion observed on any scanned bar in this window.
- **F (67 completions, 36 routes, 24 placed, 21 fills).** The only branch that
  reached the book. The 36 F routes decompose exactly: **6** retired at
  ONE-STORY intake (7 across both triggers), **6** blocked pre-place with no
  order (all `session`), and **24** placed. The 2 F R7
  `skip_place_far_from_zone` blocks (`poi-001278`, `poi-003397`) later re-placed
  through R9 intents, so they are inside the 24 placements, not losses. Of the
  24 placements, **21 filled** and 3 never filled (book counters: §23 expiries
  and cancellations — see the totals note; the unfilled count is authoritative).

---

## 4. Liveness verdict table

| Trigger | Verdict | Basis |
|---|---|---|
| **A** — CHOCH reversal | **ROUTED_ONLY** | 3 routes (H4/M5) on 2025-11-18 and 2025-11-26; 0 placed (2 session blocks, 1 ONE-STORY duplicate); 0 fills. |
| **B** — Leading diagonal | **SIGNAL_ONLY** | 5 completions on one H1 bar across 5 D1 POIs; 0 routes — all killed by the C3 in-between gate. |
| **C** — Ending diagonal | **DARK** | Wired only on the DAY tier; 0 completions in the window. |
| **D** — Two-bar reversal | **OFF_BY_DESIGN** | Code requires volume contraction; the feed is 0-volume on every bar. A5 ruling on record. |
| **E** — RSI divergence | **DARK** | Wired only on the DAY tier; 0 completions in the window. |
| **F** — BOS + OB continuation | **LIVE** | 36 routes, 24 placed, 21 filled, 21 closed across all four detection tiers. |

No expectancy, PF, or edge column exists by design.

---

## 5. Simultaneity

- **≥2 different trigger types producing a fill in the window? NO.** All 21
  fills are **F** (100.0 %).
- **≥2 different trigger types producing a route? YES.** **A (3)** and
  **F (36)** — 39 routes total.
- Dominant share of fills by trigger: **F 100.0 %** (21/21). No other trigger
  filled.

So the functional claim “all branches producing trades” is **not** met on the
product path in this window, and it is **not** met for the weaker claim “all
branches routing” either (C/D/E produced nothing; B produced signals only).

---

## 6. Method, determinism, limitations

- **Instrumentation (FR-4 style, restored in `finally`):** read-only wrappers on
  (a) each of the six trigger classes' `evaluate` — counts every non-`None`
  completion with letter/detection-TF/confirm-TF/POI, never altering a return
  value; (b) `ProductMenuEngine._candidate` — counts C3 rejections per trigger;
  (c) `ProductMenuEngine.register_armed` — counts armed POIs by detection TF;
  plus recording subclasses of the production order book / position store that
  persist the production `trigger` field per placement and per fill. No strategy
  module, constant, tier or threshold was edited; `locked_constants.py` diff is
  empty.
- **Single run — no byte-identity claim.** The frozen harness supports no dual
  run (and a 3-month dual pass would double a 76-minute job). Determinism is
  therefore **not** claimed; `LOGIC_CHANGED: NO` is the only guarantee.
- **Attribution surfaces differ** (routes from `MenuWinner`, placements from the
  order book, blocks from `blocked_log`, expiries from the order book): they are
  reported as observed and reconciled where the seams allow, not forced into a
  single arithmetic identity. `menu_submitted=32` vs 39 winners is the ONE-STORY
  intake drop, not a lost count.
- **Session gate at 100 %** is a frozen FR-4 convention (all sessions allowed);
  the 8 `session` blocks are the runner's session window for entry, not the
  audit's gate. No news gate is active.
- **Zero spread/cost**: diagnostic only (backtest convention).
- **B completions vs the earlier BCE starvation probe** (`06_RESEARCH/
  BCE_STARVATION_PROBE_REPORT.md`, 2026-11-16): that replay reported **0 B/C/E
  H1 confirmations for all of product_1y** (exec to 2025-10-31). This audit's
  window extends to **2025-11-30** and observes **5 B completions on
  2025-11-13**, none of which routed. The two statements are about different
  windows; the audit does not revise the probe. What is common to both: **no
  B/C/E branch reaches a route without a DAY-tier confirmation, and none
  reached a fill.**
- **Checks run:** full suite `python -m pytest -q` → **1,557 passed, 7 skipped**
  (root `pytest.ini`); `git diff -- 04_SRC` empty; `locked_constants.py` diff
  empty; artifacts are gitignored.

---

## 7. What this is not

- Not an expectancy, PF, win-rate or edge measurement. `NET_PL_DIAGNOSTIC` is a
  raw `price × volume` sum with zero spread/cost and is labelled as such.
- Not a claim about the research superset. Parallel/pure-tag books produced
  B/C/E fills (book-scoped, `parallel_books=()` unchanged); those are **not**
  product liveness evidence and were not used as such.
- Not a proposal to enable, wire or “fix” any branch. D was **not** replaced by
  a price-only proxy; C/E were **not** given a wider tier; B was **not** given a
  pass through the C3 gate.
- No `04_SRC` behaviour change, no `locked_constants.py` change, no
  `parallel_books` / live-default change.

---

## 8. Branch rulings required (Architect)

1. **A** — ROUTED_ONLY is a gate/dedupe outcome: 2 of 3 routes died to the
   session gate, 1 to ONE-STORY. Decide: acceptable (documented as
   session-gated on the H4 tier) or a wiring gap.
2. **B** — SIGNAL_ONLY: the branch completes but never survives C3. Decide:
   document as C3-gated (no branch work) or open a B-specific question.
3. **C / E** — DARK in the window with only DAY-tier confirmation. Decide:
   document as structurally rare (no branch work), or rule that the DAY tier
   needs a liveness follow-up (e.g. a longer window) before any claim.
4. **D** — OFF_BY_DESIGN on a 0-volume feed. Decide: leave documented, or rule a
   volume-free variant as separate design work (explicitly out of scope here).
5. **Programme** — the product path has **one** filling branch (F). Any
   “multi-branch” product claim must be withdrawn or restated as “multi-branch
   **routing**, single-branch **filling** in 2025-09→11.”
