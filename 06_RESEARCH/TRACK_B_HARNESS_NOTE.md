# TRACK-B HARNESS — PRODUCT BACKTEST ANNOTATION WIRING (NOTE)

**Date:** 2026-10-11 · **Authority:** Lead Architect harness directive (post Track-B acceptance).
**HARNESS_STATUS: PASS.** Suite **946 → 955** (9 new); `locked_constants.py` diff empty.
**Explicit, upfront: these annotations are research measurements carried on trade rows. They are NOT trading filters, NOT gates, NOT thresholds — no decision logic anywhere reads them, and this note authorizes none.**

---

## 1. Goal (what this is and is not)

Every future product backtest trade row / summary carries the Track-B
research fields so chase-vs-mid and post-exit path are read off the
artifacts instead of re-discovered by hand. Measurement wiring only:
no live gates, no threshold tuning, no change to entry/SL/TP decisions,
no expectancy claim.

## 2. Frozen rule sources (import paths — reused, not re-tuned)

All annotation logic is imported, never duplicated or retuned:

- `06_RESEARCH/scripts/f_selectivity_post_exit.py` —
  `timing_label` + `zone_relation` (frozen Rule v1: trailing-30-M1,
  Wilder ATR(14) SMA-seeded, 0.80/0.45 cuts) · `honest_r` (strict
  |entry − original_sl|, fill-referenced) · `wilder_atr_14` ·
  `post_exit` + `classify_no_tp` (frozen H = 100 M5 horizon, strict
  truncation DATA_GAP) · constants `PRE_BARS / CHOP_ATR_MULT /
  CHASE_HI / CHASE_LO / HORIZON_BARS` · new entry point
  `annotate_product_trades` (this harness; reuses the above pieces) ·
  `TRACK_B_BANNER`.
- `06_RESEARCH/scripts/hypothesis_outcome_study.py` —
  `classify / max_favorable / max_adverse` (via the former; TP-bearing
  rows run the prior classifier verbatim).

`04_SRC/smc/` contains **zero** Track-B logic: it carries data fields
only (direction of dependency stays research-imports-product).

## 3. Seam (single, after trade close)

`reports.build_report(result, annotations=...)` — the composition
computes `{ticket: {"f_timing_label", "post_exit_class"}}` post-run
over its own loaded series and passes the map in; `TradeRecord.from_closed`
takes the two values as keyword-only optionals (absent = `None` =
unannotated). Per trade:

- `f_timing_label`: frozen Rule v1 character for **F rows only**
  (`None`/empty otherwise — labels are F-only by design); degenerate
  geometry yields `"unclear"` (computed, distinct from unannotated).
- `post_exit_class`: frozen post-exit taxonomy for **every** row
  (any trigger); TP-absent rows run the documented TP-path-free
  restriction with the same labels/thresholds/order.

Composition wiring: `phase3_structure_funnel.run` annotates
`result.closed` over its loaded M1 slice (warm-up included for ATR
seed + trailing windows) and M5 exec list, then builds the report
with the map (+ banner line in the funnel notes). Post-exit needs up
to 100 M5 bars after exit: exits inside the horizon tail of the
composition's own series classify DATA_GAP (strict, documented).

## 4. Column list (append-only contract preserved)

Trade row (CSV + JSON), appended after `bars_held`:

| Column | Values | Empty means |
|---|---|---|
| `f_timing_label` | `late_chase` / `mid_move` / `structured_pullback` / `chop` / `unclear` (F rows) | not annotated, or non-F row (by design) |
| `post_exit_class` | `TP_REACHED` / `SL_THEN_TP_PATH` / `MFE_ONLY` / `REJECTED` / `DATA_GAP` | not annotated |

Report JSON top level, additive sections: `by_timing_label`,
`by_post_exit_class` (same `GroupMetrics` shape incl. net fields;
`None` folds into `"unknown"` / `"DATA_GAP"` single buckets when
unannotated). Metrics, gross columns, and fill prices are untouched —
annotated vs unannotated reports are identical except the two fields
and their groups (test-locked).

## 5. Null semantics (never invent)

- No series supplied (or ticket missing from the map) → fields `None` →
  CSV empty cells, groups fold to `"unknown"` / `"DATA_GAP"`.
- Series supplied but geometry unresolvable (entry/exit off-series,
  degenerate range/ATR, horizon truncated) → computed `"unclear"` /
  `DATA_GAP` with the reason in the study CSV's note column.
- Non-F rows never receive timing labels (empty by design, not by gap).

## 6. Verification

- 9 new tests (`04_SRC/tests/test_track_b_harness.py`): synthetic F
  close end-to-end (frozen late_chase + REJECTED on fixed geometry),
  Direction-enum normalization, empty-series DATA_GAP without crash,
  unannotated-report unknown buckets, annotated-vs-plain metric/pnl
  identity, non-F unlabeled-but-classified, `from_closed` kwargs,
  banner presence, legacy empty-report shape. Arithmetic/contract
  only — no MT5, no expectancy assertions.
- 4 pre-existing export-tail assertions extended to the appended
  columns (same justified contract evolution as the cost-model change;
  no expectation re-valued).
- Composition smoke (this note's proof): `phase3_structure_funnel`
  on exec 2025-09-01 → 2025-09-05 (1,326 M5 bars, 111 batches, 17.9 s)
  → 7 armed → 4 routes → **1 fill → 1 trade (C, TP exit)** with
  `post_exit_class=TP_REACHED`, empty `f_timing_label` (non-F),
  both group sections populated, gross economics byte-identical to
  the unannotated path. Artifacts (local-only):
  `06_RESEARCH/results/track_b_harness_smoke/`.
- Full suite **955 passed**; `locked_constants.py` diff empty; no
  trigger/risk/pillar/sizing/fill change; paper runner untouched.

## 7. Load discipline + limitations

- M1 must start well before the first entry (ATR-14 seed + 30-bar
  trailing window); entries inside the seed window label `"unclear"`
  by rule. The composition's month-long warm-up satisfies this.
- Cross-study ATR histories can differ in late decimals if load
  windows differ (documented; determinism pairs are unaffected —
  same series both runs).
- Horizon tail: any exit within 100 M5 bars of the composition's
  series end is DATA_GAP by the strict rule (extends the window, not
  the rule, to reduce these).
- BE-scratch default (|pnl| < 0.15 + stop_loss → MFE_ONLY first) and
  the 0.25 analytics divider are inherited frozen — outcome splits on
  scratch-heavy books reflect the rule, disclosed per the Track-B
  report.

## 8. Bans compliance

No route filtered by late_chase (nothing reads the fields); no
locked-constants trading-threshold edit (annotation params live in
research code); no expectancy claim; triggers/risk/pillars byte- and
behavior-identical (suite proves it).

---

**NEXT_READY: spread-grade scale (A)** (or Architect-ordered window).
