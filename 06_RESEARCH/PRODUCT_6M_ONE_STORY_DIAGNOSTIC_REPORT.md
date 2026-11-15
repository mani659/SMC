# PRODUCT 6-MONTH MENU + ONE-STORY DIAGNOSTIC

**DIAGNOSTIC ONLY — NOT PERFORMANCE. No edge claim, no ranking, no gate or threshold change, no ship recommendation. Every number below is a book-shape count on the frozen diagnostic configuration (spread 0.0, news dormant, all sessions, cost model dormant) — the same machine-completeness config as PFE-2, explicitly NOT cost realism.**

- **Status:** measurement complete; one-story guard ON (shipped intake seam, `04_SRC/smc/risk/story_guard.py`, locked 2026-11-15).
- **Script:** `06_RESEARCH/scripts/product_6m_one_story_diag.py` driving the PFE-2 harness (`06_RESEARCH/scripts/phase3_structure_funnel.py`, `--composition menu`) unchanged except a one-line additive measurement surface (`story_counters` in the summary).
- **Composition:** MENU product path only (`ProductMenuEngine` sweep → one-shot LTF confirmation → `PipelineAdapter.queue_menu_candidate` → same risk/order seam), one-story guard at intake, structural TP / §5a selector and risk unchanged. No seek run, no parameter search, no post-hoc filter.

## 1. Window (frozen; PFE-2 conventions, dual run)

The continuous 6-month menu run is documented infeasible (PFE-2 §1.1 — quadratic menu bookkeeping, stopped before any funnel was read; no product code changed to work around it). The menu evidence therefore reuses the PFE-2 frozen bounded windows verbatim, each dual-run:

| Window | Exec (UTC) | Load | M5 bars |
|---|---|---|---|
| jun | 2025-06-01 22:00:00 -> 2025-06-10 23:55:00 | 2025-05-01 | 1,956 |
| sep | 2025-09-01 00:00:00 -> 2025-09-10 23:55:00 | 2025-05-01 | 2,178 |
| oct | 2025-10-01 00:00:00 -> 2025-10-10 20:55:00 | 2025-05-01 | 2,184 |

**Documented deviation:** this is a three-window frozen sample of the six months (Jun / Sep / Oct 2025 10-day windows), not a continuous 2025-06-01 → 2025-11-30 run — identical bounds per pair, dual-run. November 2025 has no bounded menu window in the established record and none was added here (same residual as PFE-2).

## 2. Funnel (menu, guard ON)

| Metric | Jun 1-10 | Sep 1-10 | Oct 1-10 (primary) |
|---|---|---|---|
| htf_batches | 162 | 181 | 181 |
| batch_errors | 1 | 1 | 1 |
| merged_pois | 4320 | 6725 | 6363 |
| passed_validation | 149 | 438 | 238 |
| armed | 60 | 170 | 97 |
| armed_m8 | 58 | 80 | 49 |
| menu_episodes | 22 | 25 | 30 |
| menu_winners | 18 | 3 | 23 |
| menu_submitted | 5 | 2 | 7 |
| placed | 4 | 1 | 4 |
| fills | 4 | 1 | 4 |
| menu_errors | 0 | 0 | 0 |
| stories_claimed | 5 | 2 | 7 |
| duplicate_story_dropped (intake) | 13 | 1 | 16 |

`routes` is 0 in every window (menu-covered POIs, scan dormant — as in PFE-2). `menu_submitted` is the post-guard intake count (PFE-2 pre-guard submission happened directly from winners).

## 3. Unique stories vs raw fills (the answer)

| | Raw fills | Unique plans | Identical-plan groups |
|---|---|---|---|
| jun | 4 | 4 | 0 |
| sep | 1 | 1 | 0 |
| oct | 4 | 4 | 0 |
| **combined** | **9** | **9** | **0** |

Plan identity = the locked story_guard rules 2-6 (direction · trigger · entry · SL · TP exact floats · overlapping zone), applied mechanically to the trades; no tolerance invented, unknown geometry never collapsed.

**Multi-fill check:** identical-plan groups after the guard = **0** (must be 0); groups with overlapping hold intervals = **0** (must be 0). The guard's own intake counters show the spray was dropped before the risk gate, so a duplicate never sized and never minted a ticket.

## 4. Mix tables (book shape)

| Mix | Value |
|---|---|
| Trigger mix on fills | A 1, F 8 |
| Direction mix on fills | long 5, short 4 |
| model_tags on fills | M1+M7+M8 1, M4 2, M4+M5+M7+M8 1, M5 2, M5+M8 1, M8 2 |
| Detection-TF mix on fills | D1 1, H4 1, M15 7 |
| Fills by month | 2025-06 4, 2025-09 1, 2025-10 4 |
| Exit close_kind | stop_loss 8, take_profit 1 |
| Exit tp_source | atr_fallback 3, structural_swing 6 |
| Routes by trigger | jun: none; sep: none; oct: none |
| Armed by detection TF | jun: H4 15, H1 2, D1 19, M15 24; sep: H4 49, H1 21, D1 61, M15 39; oct: H4 11, H1 8, M15 15, D1 63 |

## 5. Comparison — pre-guard PFE-2 vs guard ON (same plan key, both sides)

| | Raw fills | Unique plans |
|---|---|---|
| PFE-2 pre-guard (same three windows) | 27 | 8 |
| This run, guard ON | 9 | 9 |

Per window pre-guard unique plans: jun 4, sep 1, oct 3; the guard reduces the book to exactly the distinct plans (the duplicates never place).

**Nuance — post-guard 9 unique plans vs pre-guard 8 (documented, not a contradiction):** the two books are not subsets of each other. Pre-guard, the F-spray itself tripped the one-story circuit breaker, which then *blocked other legitimate plans* — so some distinct plans that never got a chance pre-guard are precisely the ones the guard now lets through (9 fills in, 9 unique plans out, `placed == fills` in every window). The guard removes the spray, so the breaker never trips, and the book is *both* deduplicated *and* slightly different in composition. This is exactly the intake-vs-breaker interaction the one-story design predicted; it is recorded here as book-shape evidence only.

## 6. Determinism

| Window | trades.csv | report.json | funnel_summary |
|---|---|---|---|
| jun | PASS (byte-identical) | PASS (byte-identical) | PASS |
| sep | PASS (byte-identical) | PASS (byte-identical) | PASS |
| oct | PASS (byte-identical) | PASS (byte-identical) | PASS |

## 7. Is the engine a single storyline?

**SINGLE_STORYLINE_ENGINE: NO** — evidence: trigger mix on fills: A 1, F 8; direction mix on fills: long 5, short 4; detection-tier mix on fills: D1 1, H4 1, M15 7; fills by month: 2025-06 4, 2025-09 1, 2025-10 4.

This is a statement about the diagnostic book shape only, not about forward edge or quality; n is small (see the funnel table) and the windows are 10-day samples.

## 8. Residuals

- Continuous 6-month menu run remains infeasible without a performance-only harness engagement (PFE-2 §1.1 stands); this report is the three-window frozen sample.
- November 2025 carries no bounded menu window in the established record.
- Warm-up asymmetry (D1/H4/H1 carry load_from; M15/M5/M1 start at exec), window-end queued entries, and fresh menu state per window — carried verbatim from PFE-2.
- `POSTURE` extras: not re-measured here (UNKNOWN, honestly — only the already-instrumented funnel counters are reported).

**No expectancy claim, no PnL claim, no ship recommendation. O1-O5 remain CLOSED status-quo; C3/SL/TP policy and thresholds untouched; `locked_constants.py` untouched.**
