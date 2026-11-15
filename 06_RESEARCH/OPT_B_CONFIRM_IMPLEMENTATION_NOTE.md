# OPT-B — HYBRID SAME-BAR / AS-OF CONFIRMATION: IMPLEMENTATION NOTE

**Status:** `OPT_B_STATUS: MEASURED` (flag implemented, tested, measured)
**Authority:** Lead Architect "IMPLEMENT OPT-B — HYBRID SAME-BAR / AS-OF CONFIRM AFTER SWEEP" (GO)
**Design lock:** `06_RESEARCH/PARALLEL_CONFIRMATION_DESIGN.md` §5 (OPT-B), accepted.
**Date:** 2026-11-04

```
LOGIC_CHANGED: confirmation eligibility timing ONLY (product menu path),
                behind a DEFAULT-OFF flag
R7 / R9 / risk / pillars / locked constants: UNCHANGED (diff empty)
SHIPPED CONFIG: config/live_demo.json → enable_opt_b_same_bar_confirm = false
```

---

## 1. What the flag does

`ProductMenuEngine(symbol, same_bar_asof=False)`
↔ config key `enable_opt_b_same_bar_confirm` (default `false`, boolean, coerced
and typo-guarded by the existing strict config whitelist).

**OFF (default, shipped):** the serial anchor is untouched, byte-for-byte —
eligibility starts at the first confirmation-TF bar closing **at/after the sweep
bar's close** (`_first_close_at_or_after(sweep_close_ts)`), and the evaluated bar
index remains the historical stream tail.

**ON:** the lower anchor moves to the **close of the confirmation-TF bar that
carries the sweep extreme** (deepest pierce of the zone inside the sweep
detection bar), and the evaluated bar is addressed at **its own index**:

```
eligible confirm bar b  ⇔  b.close_ts >  wick_bar_close
                       and b.close_ts ≤  as_of            (unchanged guard)
                       and the POI is not consumed        (unchanged, one-shot)
from_index (trigger A/D/E "post-dates" anchor) = first close > wick_bar_close
```

Everything else in the locked contract is untouched: the R2 sweep is still
required to open the window, only `tier.confirmation_tfs` are evaluated, expiry
still counts **20 detection-TF bars**, the A/D/F set is unchanged, and the first
valid win still consumes the episode.

## 2. Where the code changed

| file | change |
|---|---|
| `04_SRC/smc/orchestration/product_menu_mtf.py` | `same_bar_asof` constructor flag (default `False`); `MenuEpisode.sweep_anchor` (per-confirm-TF cached anchor); `_opt_b_from_index` / `_sweep_anchor_close` / `_bar_index` / `_first_close_after`; the eligibility branch in `_evaluate_confirm_bar` and the OPT-B-only index addressing |
| `04_SRC/smc/live/operator_config.py` | `enable_opt_b_same_bar_confirm: bool = False` field, `ALLOWED_KEYS` entry, `_coerce_bool` parse |
| `04_SRC/smc/live/run_operator.py` | passes the flag to `ProductMenuEngine`; the menu activation log line gains `opt_b_same_bar=` |
| `config/live_demo.json` | `"enable_opt_b_same_bar_confirm": false` (explicit, so the posture is visible and never implicit) |
| `04_SRC/tests/test_product_menu_opt_b.py` | 13 tests (below) |

No other module is touched. The adapter/P1 path (`PipelineAdapter`) is **not
modified at all** — no shared helper was extracted, so there is nothing that
could drift when the flag is off.

## 3. Two implementation decisions that needed a ruling from the code (not invented knobs)

1. **Tie on the extreme.** If the sweep extreme is touched by more than one
   confirmation bar inside the sweep bar, the anchor is the **last** such bar.
   Rationale: a re-pierce of the same price is part of the same liquidity grab,
   so a body that forms between the two touches is not "after the sweep". Using
   the first touch would make the window longer but would admit pre-grab
   structures; the conservative reading is the correct one for a design whose
   entire point is ordering. (Tested: `test_flag_on_anchor_is_the_last_bar_touching_the_extreme`.)
2. **Sparse feed fallback.** If no confirmation bar was observed inside the
   sweep detection bar (a caller feeding only the newest bar, or a data gap),
   there is no wick carrier to anchor on. OPT-B then **falls back to the prior
   sweep-close anchor** rather than blocking the window, so enabling the flag can
   never make a previously-confirmable episode unconfirmable.
   (Tested: `test_flag_on_keeps_post_sweep_bars_eligible`.)

The 1-bar edge case the brief anticipated does not arise in a normal feed: the
detection bar and every confirmation bar inside it close at or before the same
`as_of`, and `_new_closed` ingests the whole payload before the first evaluation,
so the wick is always fully known when an interior bar is evaluated. The only
pathological case is an out-of-order feed (a confirmation bar delivered after a
newer one), which `_new_closed` already drops — unchanged behaviour, and the
fallback above keeps it safe.

## 4. No-lookahead argument

* Every bar the engine evaluates is `close_ts <= as_of`; `_new_closed` enforces
  it and silently drops anything later (pre-existing guard, unchanged).
* The wick is derived **only** from bars of an already-closed detection bar.
* The trigger receives the stream prefix up to `as_of` and an index at or before
  the bar being decided; the router's contract is bar-index-bounded.
* Test `test_flag_on_never_reads_a_forming_bar` asserts that a bar whose close is
  after `as_of` is never seen by any trigger (max observed close timestamp ≤
  `as_of`, and the forming bar's close timestamp never appears).

## 5. Tests (13 new, `04_SRC/tests/test_product_menu_opt_b.py`)

Posture: `test_engine_default_is_the_serial_anchor`,
`test_live_demo_config_ships_the_flag_off`, `test_config_default_and_override`
(default False / `true` accepted / non-boolean rejected).

Prior behaviour with the flag OFF: `test_flag_off_ignores_the_sweep_bar_interior`
(no winner, no trigger body is even evaluated).

OPT-B eligibility: `test_flag_on_confirms_inside_the_sweep_bar_after_the_wick`,
`test_flag_on_still_rejects_the_wick_bar_itself`,
`test_flag_on_anchor_is_the_last_bar_touching_the_extreme`,
`test_flag_on_keeps_post_sweep_bars_eligible` (sparse-feed fallback).

Invariants: `test_flag_on_is_still_one_shot`,
`test_flag_on_never_reads_a_forming_bar`,
`test_flag_on_does_not_confirm_without_a_sweep`,
`test_flag_on_respects_detection_bar_expiry`.

Full suite: **1,462 passed** (was 1,449). `locked_constants.py` diff **empty**.

## 6. Measurement (Part 3)

Harness: `06_RESEARCH/scripts/opt_b_confirm_measure.py`
→ `06_RESEARCH/results/opt_b_confirm_measure/` (`summary_<window>.json`,
`episodes_<window>_{off,on}.csv`).

Method: the frozen product runtime arms POIs at its new-H1-close cadence with
the **full menu detection set** (D1/H4/H1/M15); each armed POI's first R2 sweep
becomes its first menu episode; a **fresh** `ProductMenuEngine` per episode per
flag is driven through the public `on_execution_bar` API and every winner is
labelled with the **same frozen rule as the timing study**
(`timing_label`, band = FR-3/R7 `ZONE_REFINEMENT_ATR × ATR`). Both flags see
byte-identical bars in the same process, so OFF↔ON is a controlled comparison.

<!--METRICS-->

## 7. What this note does NOT claim

No expectancy, no win-rate, no PnL: the measurement is confirmation geometry on
the menu path. It does not re-run the adapter/P1 population (OPT-B cannot reach
it — the adapter path has no sweep stage and is not modified), and it does not
touch R7: a late-but-confirmed route is still refused by the existing place
guard, exactly as before.

## 8. Posture

Flag **OFF** in `config/live_demo.json`. Enabling it live requires the Architect's
review of §6 and an explicit GO; nothing in this change flips a default, widens a
band, or enables a new trigger.
