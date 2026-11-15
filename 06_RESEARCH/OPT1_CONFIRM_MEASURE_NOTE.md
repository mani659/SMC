# OPT-1 — CONFIRM vs ZONE MEASURE ENRICHMENT (IMPLEMENTED, LOGGING-ONLY)

**Status:** `OPT1_STATUS: PASS` (enrichment implemented + smoke measure run)
**Authority:** Lead Architect — GO, "IMPLEMENT OPT-1 — CONFIRM vs ZONE MEASURE
ENRICHMENT (NO DECISION CHANGE)", 2026-11-07
**Binding design:** `06_RESEARCH/CONFIRM_VS_ZONE_DESIGN.md` (OPT-1 recommended
and accepted) · **Policy:** `06_RESEARCH/POLICY_OPT_B_FLAG_2026-11-07.md`
(the OPT-B flag stays **`false`** — untouched)

```
LOGIC_CHANGED: NO   — decision / eligibility / placement paths are untouched;
                      the enrichment is logging / export / KPI fields only.
                      No reject-on-LATE (OPT-2 is explicitly NOT implemented),
                      no new band thresholds, no R7/R9 change.
```

> **MEASURE NOTE — NOT EDGE — NOT A PERFORMANCE CLAIM.** This note describes
> export plumbing and a logging-path verification only. No PnL, no expectancy,
> no edge, and **no strategy-improvement claim of any kind is made or implied**.

---

## PART 1 — WHAT WAS IMPLEMENTED (files:function)

### `04_SRC/smc/orchestration/product_menu_mtf.py`

* **Pure helpers (module level, unit-tested):**
  * `completion_zone_edge_distance_atr(zone_low, zone_high, close, atr)` —
    the **ONE chosen formula**, frozen from the timing-study convention
    (`poi_timing_early_late_study.zone_edge_distance`,
    `06_RESEARCH/scripts/poi_timing_early_late_study.py:160`):
    **distance to the NEAREST zone edge, `0.0` inside (inclusive), divided by
    ATR**. Returns `None` when zone bounds or ATR are unresolvable — never
    invented.
  * `completion_timing_label(direction, zone_low, zone_high, close, atr,
    band_atr=None)` — the **frozen timing-study taxonomy mirrored
    product-side** (no import of 06_RESEARCH into product code):
    `ON_WINDOW` (nearest-edge distance ≤ band), `LATE` (beyond the band on the
    displacement side — away from the protective stop: above the zone for
    LONG, below for SHORT), `BEYOND_STOP_SIDE` (beyond the band on the
    opposite side), `OTHER` (direction maps to neither long nor short),
    `UNLOCATABLE` (zone/ATR missing). The default band is the **locked
    `ZONE_REFINEMENT_ATR = 0.5`** read from
    `smc/config/locked_constants.py:128` — a read-only use; the
    `locked_constants.py` diff is **empty** (verified).
* **Engine:`_completion_metrics(route, tf, series, zone)`** — resolves
  `route.signal.completion_index` in the confirm-TF closed stream,
  `completion_close` = that bar's close, `atr_at_confirm` = **Wilder prefix
  ATR at the completion index** (`latest_atr(series[:index+1], atr_period)` —
  closed bars only, **no lookahead**, independent of the pre-existing
  TP-fallback ATR which is untouched), plus distance and label.
  `Engine:_unlocatable_completion()` returns an honest all-`None` dict with
  label `UNLOCATABLE` when the completion index is out of range.
* **Engine:`_candidate(...)` stamp extension** — the existing
  `product_menu` `signal_data_json` stamp (already carried into
  pendings/positions by the runner) gains:
  `zone_direction`, `completion_index`, `completion_ts` (close-ts of the
  completing confirm-TF bar), `completion_close`, `atr_at_confirm`,
  `distance_at_confirm_atr`, `label_at_confirm`.
  `confirmation_tf` and `sweep_ts` were already present (unchanged).

### `04_SRC/smc/live/loop.py`

* **`LiveLoop:_record_menu_confirm_kpi(winners, now)`** — **one structured KPI
  record per menu winner** (`event="menu_confirm"`, one per winner) written
  through the runner's existing `KPILogger.record(...)` (`kpi_logger.py:78`),
  carried verbatim from the winner's enrich stamp: `episode_id`, `poi_id`,
  `tier`, `detection_tf`, `confirmation_tf`, `trigger`, `route_id`,
  `sweep_ts`, `completion_ts`, `completion_close`, `atr_at_confirm`,
  `distance_at_confirm_atr`, `label_at_confirm`.
  **Audit-only** — the KPI log is never read by a risk verdict, a placement or
  an eligibility decision (same class as the existing `entry_blocked` /
  `place_skip` records); the call is try/except-guarded so a logging failure
  can never affect the trading path, and a KPI-less runner simply skips it.

### Deliberately NOT implemented this pass

* **`distance_at_place_atr` / `r7_verdict`** (OPT-4 fold-in, optional): the
  design note's place-side dual export would touch the runner's submit/skip
  seam (`runner.py:864-896`). The R7 guard is byte-frozen this pass per the
  directive ("R7 unchanged"), so those two optional fields are **deferred until
  a follow-up logging pass touches the place seam**. Documented honestly rather
  than smuggled in.

---

## PART 2 — TESTS (`04_SRC/tests/test_confirm_vs_zone_opt1.py`, 13 tests)

* Stamp fields populate on a synthetic H4-sweep → M15-confirm win
  (`completion_ts` == the M15 bar's close-ts, `completion_close == 2497.0`,
  Wilder seed ATR `8.0`, distance `0.0`, label `ON_WINDOW`).
* Pure label semantics: LATE above-zone for LONG / below-zone for SHORT,
  mirrored BEYOND_STOP_SIDE, band edge inclusive at exactly `0.5 × ATR`, the
  locked `ZONE_REFINEMENT_ATR` read-not-changed pin, `OTHER`, `UNLOCATABLE`.
* Distance formula pinned: nearest edge, `0.0` inside, inverted bounds
  normalised, `None` for unresolvable inputs.
* No-ATR no-invention: a 1-bar confirm stream → `atr_at_confirm=None`,
  distance `None`, label `UNLOCATABLE` (completion close still materialised
  honestly); out-of-range completion index → all-None `UNLOCATABLE`.
* `menu_confirm` KPI recorded via the loop fixture (one record per winner,
  audit-only, KPI-less runner never fatals).
* OPT-B default stays `False` (engine + `config/live_demo.json` raw check).
* **Suite: 1475 passed** (baseline 1462 + 13; golden menu routing tests green —
  unchanged assertions `zone`, `sweep_ts`, `tier`, identity fields still pass).

---

## PART 3 — SMOKE MEASURE (frozen primary subset)

* Frozen harness reused verbatim (`opt_b_confirm_measure.py`: `load_series`,
  `arm_pois`, `first_episodes`, `_seed`, `_close_ts`, `EPISODE_SEED_BARS=600`)
  — **unchanged, imported, not copied**. Replays each first episode on the
  **default path only** (`same_bar_asof=False` — flag OFF per policy); the
  exported stamp values are **the product engine's own output, never
  re-derived by the script**.
* Window: `primary`, `--exec-from 2025-10-01` (the frozen primary-subset cut).
* **Artifacts:** `06_RESEARCH/results/confirm_vs_zone_opt1/
  summary_primary.json` + `confirms_primary.csv` (30 rows) + `run_log.txt`.

| metric | value |
|---|---|
| episodes probed | 30 (first episode per POI; 36 armed POIs) |
| won | **23** |
| expired / no_winner | 7 / 0 |
| **SMOKE_N (labelled wins with non-null distance)** | **23 of 23 wins** |
| `atr_at_confirm` non-null | 23 of 23 |
| label mix (wins) | **ON_WINDOW 13 · LATE 5 · BEYOND_STOP_SIDE 5** |
| median `distance_at_confirm_atr` (wins) | 0.1974 ATR |
| by confirmation TF (wins) | M1 12 · M5 7 · H1 2 · M15 2 |

Verification against the directive:

* `n > 0` rows with non-null `distance_at_confirm_atr`: **yes — 23/23** wins ✔
* Label distribution present across three taxonomy buckets ✔
* **No claim of strategy improvement is made** — this run changes nothing and
  measures nothing but the logging path; the label mix above is a *count*,
  not an outcome. ❌ no improvement claim ✔ none made
* The pre-existing wider-measure numbers stand unchanged (ON_WINDOW combined
  48.11 %→45.71 %, confirms 212→210 — cited, not re-measured here).
* Caveats carried in `summary_primary.json`: first episode per POI only;
  bounded confirm-stream seed; stamps are product output; no placement/fills/
  R7/PnL measured.

---

## PART 4 — NEXT

Architect review of the enriched labels (`confirms_primary.csv` +
`menu_confirm` KPI events live going forward). **OPT-2 only if the enriched
data warrants it** — no reject-on-LATE was implemented and none is proposed
here. The deferred OPT-4 place-side fields (`distance_at_place_atr`,
`r7_verdict`) remain the natural follow-up logging pass if the Architect
wants the submit-bar frame materialised too.
