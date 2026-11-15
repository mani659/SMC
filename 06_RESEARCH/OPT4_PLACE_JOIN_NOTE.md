# OPT-4 — PLACE-SIDE DISTANCE + R7 VERDICT (LOGGING-ONLY, JOIN REPORT)

**Status:** `OPT4_STATUS: PASS` (submit-seam logging + join smoke complete)
**Authority:** Lead Architect — GO, "IMPLEMENT OPT-4 — PLACE-SIDE DISTANCE +
R7 VERDICT (LOGGING ONLY)", binding design
`06_RESEARCH/CONFIRM_VS_ZONE_DESIGN.md` (OPT-4)
**Predecessor:** `06_RESEARCH/OPT1_CONFIRM_MEASURE_NOTE.md` (confirm-side
stamps + `menu_confirm` KPI — unchanged by this task)
**Policy:** `06_RESEARCH/POLICY_OPT_B_FLAG_2026-11-07.md` — OPT-B flag stays
**`false`**; R7 logic unchanged; **NO OPT-2 implemented**

```
LOGIC_CHANGED: NO   — submit-seam logging / KPI / export only. The R7 guard
                      boolean (`zone_place_allowed`), risk verdicts, R9
                      intents and every place/skip outcome are byte-stable
                      (pinned by the pre-existing fixtures + this task's
                      byte-stability tests).
```

> **JOIN REPORT — NOT EDGE — NOT A PERFORMANCE CLAIM.** The table below is a
> count of geometry and verdicts. No PnL, no expectancy, no edge language, and
> **no strategy-improvement claim** is made or implied anywhere.

---

## PART 1 — WHAT WAS IMPLEMENTED (files:function)

### `04_SRC/smc/paper/runner.py` — the submit seam, append-only fields

* **Module-level pure helpers (logging-only):**
  * `_place_distance_atr(candidate, market_close, atr)` — **the SAME OPT-1
    convention** (nearest zone edge, `0.0` inside, in ATR) delegated to the
    product-side helper `completion_zone_edge_distance_atr`
    (`product_menu_mtf.py`) — one formula, one source of truth (unit test
    pins parity for identical inputs). `None` when zone close or ATR is
    unresolvable — never invented. The zone bounds come from the candidate's
    `zone_low`/`zone_high` (already on `CandidateEntry`; not re-parsed).
  * `_menu_stamp_fields(candidate)` — parses the winner's existing
    `signal_data_json`["product_menu"] stamp and carries the join keys
    `label_at_confirm` + `completion_ts` (all-`None` honestly for
    adapter-path candidates without a stamp).
* **The R7 fork is enriched in place (the fork's boolean outcome untouched):**
  * guard FAILS → the existing `place_skip` KPI record gains
    `r7_verdict=SKIP_PLACE_FAR_FROM_ZONE` (the EXISTING machine-readable
    constant — no new code), `distance_at_place_atr`, and the stamp join
    keys; the accompanying `_note_block(..., atr, market_close)` row gains
    `r7_verdict` + `distance_at_place_atr` too (`record_event=False`
    unchanged — the place_skip record remains the single event).
  * guard PASSES → **one new audit record `place_placed`** per accepted
    decision (recorded at the decision point, before the dry-run/broker
    mechanics, so `dry_run=True` runs are captured with `dry_run: true`):
    `r7_verdict="placed"` + `distance_at_place_atr` + stamp join keys. The
    already-written `order_ack` / `fill` records stay untouched.
  * risk-side block (before R7) → the existing `entry_blocked` record gains
    `r7_verdict=<decision.blocked_by>` (the existing code, e.g. `session`)
    and `distance_at_place_atr` when computable.
* Every record is write-only telemetry: nothing reads them for a decision
  (same class as `entry_blocked` / `place_skip` / `menu_confirm`).

---

## PART 2 — TESTS (`04_SRC/tests/test_confirm_vs_zone_opt4.py`, 11 tests)

* Place path logs distance + verdict when R7 places (`place_placed`,
  `r7_verdict="placed"`, in-zone distance `0.0`; order still placed).
* skip_far path logs skip verdict + distance when R7 skips (`place_skip`,
  `r7_verdict=SKIP_PLACE_FAR_FROM_ZONE`, distance `5.6` — the seam's own
  Wilder ATR; nothing placed, R9 intent armed, one-shot unburned —
  byte-stable vs the pre-change fixture expectations).
* The verdict class follows the SAME seam boolean (placed vs skip contexts
  never diverge).
* Menu-stamp join keys flow onto both skip and placed records; adapter-path
  candidates without a stamp yield `None` (no invention).
* Risk-block record carries `r7_verdict=BLOCK_SESSION` + distance.
* Dry-run records the placed verdict with `dry_run: true`.
* Helper parity with the OPT-1 formula + honest-`None` cases.
* OPT-B engine default OFF + `config/live_demo.json` flag still `false`.
* **Suite: 1486 passed** (baseline 1475 + 11; golden R7/R8/R9/blocked-surface
  fixtures all green — no new skips, no outcome drift).

---

## PART 3 — JOIN SMOKE (frozen primary window family)

Same frozen harness as OPT-1 (`opt_b_confirm_measure.py` arm/episode
machinery, unchanged; arming now checkpointed so the multi-hour phase is
reusable). Per won episode, the **submit approximation** is the first closed
M5 bar at/after `completion_ts` (live, the loop queues the winner the moment
it appears, so the runner evaluates it on that first closed M5 bar);
`distance_at_place_atr` / `atr_at_place` use the Wilder prefix ATR
(period 14 — `PaperConfig.atr_period`'s default, the seam's own parameter),
and **`r7_verdict` is computed through the REAL frozen guard
`zone_place_allowed`** — never re-implemented. Risk-side blocks are NOT
modelled (join is conditional on an accepted risk verdict; documented
caveat), and R9-deferred later placements are out of scope (at-submit join).

**Artifacts:** `06_RESEARCH/results/confirm_vs_zone_opt4/`
(`summary_primary.json`, `join_primary.csv` — 30 rows, `run_log.txt`,
`arming_primary_2025-10-01.pkl` checkpoint).

### JOIN TABLE — label_at_confirm × r7_verdict (primary, exec-from 2025-10-01, 30 episodes → 23 verdict-ed wins)

| label_at_confirm | n | placed | skip_far_from_zone | median confirm dist (ATR) | median place dist (ATR) |
|---|---|---|---|---|---|
| ON_WINDOW | 13 | 12 | 1 | 0.0000 | 0.0000 |
| LATE | 5 | 0 | **5** | 1.3388 | 2.6079 |
| BEYOND_STOP_SIDE | 5 | 1 | 4 | 2.5794 | 2.2024 |

* n placed / skipped: **LATE 0 placed / 5 skipped**; BEYOND_STOP_SIDE 1
  placed / 4 skipped.
* Confirm-vs-place medians by label: ON_WINDOW stays 0 by both references;
  for LATE the place-time reference is FARTHER than the completion reference
  (market kept running away: 1.34 → 2.61 ATR); for BEYOND_STOP_SIDE the
  place-time reference sat slightly closer than completion (2.20 vs 2.58) —
  geometry counts only, no outcome attached.

### Hypothesis check — "R7 already filters most LATE" (report only)

* **Result: `INSUFFICIENT`** — 5 of 5 LATE completions were R7-skipped at
  submit, but LATE n = 5 is far below the pre-registered n ≥ 10 bar, so this
  is a directional observation, NOT a statistical finding. The design note's
  Phase-2 survey (§2.4) already predicted the mechanism (completion-grade
  displacement biases closes far from the zone; the R7 reference is the
  same direction of travel); the join data is consistent with it. **No
  expectancy claim; OPT-2 remains NOT implemented** and its decision belongs
  to the Architect reading this table.

---

## PART 4 — NEXT

Architect reads the join table (this note + `join_primary.csv`) and rules
**OPT-2 yes/no**. Options documented in `06_RESEARCH/CONFIRM_VS_ZONE_DESIGN.md`
Part 3 (OPT-2's known interplay: moving an LATE gate upstream would also
suppress LATE-at-confirm cases whose place-time close fell back inside the
band — this smoke measures the at-submit frame; an R9-later-placement frame
(`intent_place` outcomes) would be the natural extension if the Architect
wants the deferred side of the picture first).
