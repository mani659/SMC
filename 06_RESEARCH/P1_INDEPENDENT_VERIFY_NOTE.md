# P1 Independent Verification + Stratified Re-score Pack

`LOGIC_CHANGED: NO` — research only. No edits under `04_SRC/smc/**`, no `locked_constants` changes, no retunes, no P2, no family acceptance.

Second-model verification of `P1_CHART_CONTRACT_AND_WRONG_EXTREME_AUDIT.md`. Prior conclusions were re-derived, not trusted.

## 1) Period definitions actually used (code citations)

| Family | Period resolved from | Definition | Code source |
|---|---|---|---|
| PDH/PDL | `formed_at` UTC date | `[day 00:00, day+1 00:00)` UTC calendar day; bar included when `period_start <= bar_ts < period_end` (end exclusive) | `04_SRC/smc/detection/periodic_levels.py` (`_aggregate` daily bucket by `candle.timestamp.date()`, `completed_days = d < reference.date()`) |
| PWH/PWL | Monday of `formed_at` date | `[Mon 00:00, Mon+7d 00:00)` — Monday-anchored, end exclusive | same file (`_monday`, weekly bucket, `completed_weeks = w < _monday(reference.date())`) |
| Session H/L | `formed_at` hour | Locked §2 windows on the UTC date: Asia 00–07, London 07–13, NY 13–20; 20:00–24:00 belongs to no session; end exclusive | `04_SRC/smc/utils/timestamps.py` (`detect_session`) + `smc.config.locked_constants` hour constants |
| EQH/EQL | cluster members | Span `[first touch, last touch]`; label must equal `max(BSL)/min(SSL)` of member swing levels and all members within tolerance | `04_SRC/smc/detection/eqh_eql_detector.py` (`_cluster`, `detect_equal_levels`); tolerance `EQH_EQL_TOLERANCE = 4.5` pips → `pips_to_price` = **0.45 price units** (`smc/utils/pips.py`) |
| Structural swing | `formed_at` = **base candle** | Not period-scoped. `Swing.timestamp` returns `base_candle.timestamp`, while `level` is the N-bar swing candle extreme | `04_SRC/smc/core/swing.py` (`timestamp -> base_candle.timestamp`); `04_SRC/smc/detection/structural_swing_detector.py` (`level = candle.high/low`, `base_index = find_base_candle_index(...)`) |

Tick/price quantum: 2-decimal quote, `TICK = 0.01`. Equality is exact float match (`<= 1e-9`), stricter than one tick.

## 2) Recompute vs prior audit — agreement table

Independent recompute: 25 rows = 5 Architect-flagged cases + 20 deterministic random rows (4 per family, seed 20261111). Periods were re-resolved from locked rules only; `max(high)`/`min(low)` were computed by direct bar iteration over `[start, end)`, **not** by calling the production `_aggregate()`.

| Family | Rows | EXACT_MATCH | WRONG_EXTREME | OUT_OF_PERIOD | SERIES_GAP | Prior-audit agreement |
|---|---:|---:|---:|---:|---:|---|
| pwh_pwl | 6 | 6 | 0 | 0 | 0 | 6/6 |
| session | 6 | 6 | 0 | 0 | 0 | 6/6 |
| pdh_pdl | 4 | 4 | 0 | 0 | 0 | 4/4 |
| eqh_eql | 4 | 4 | 0 | 0 | 0 | 4/4 |
| structural_swing | 5 | 5 | 0 | 0 | 0 | 5/5 |
| **Total** | **25** | **25** | **0** | **0** | **0** | **25/25** |

`INDEPENDENT_WRONG_EXTREME_N = 0`. Deterministic dual-run: recompute CSV SHA256 equal.

The five flagged cases:

| Case | Event | Label | Period | True extreme | Verdict |
|---|---|---|---:|---|---|
| V1 PWH SSL | `pwh_pwl_0327` | 3301.195 | week 2025-06-02 → 06-09 | low 3301.195 @ 06-02 01:55 | EXACT |
| V2 PWH SSL | `pwh_pwl_0345` | 3344.748 | week 2025-08-04 → 08-11 | low 3344.748 @ 08-04 01:25 | EXACT |
| V3 Session Asia BSL | `session_0378` | 3345.198 | Asia 06-02 00:00–07:00 | high 3345.198 @ 06:45 | EXACT |
| V4 Session Asia BSL | `session_0504` | 3334.348 | Asia 07-01 00:00–07:00 | high 3334.348 @ 06:52 | EXACT |
| V5 Structural SSL | `structural_swing_1172` | 3327.275 | base candle 07-02 04:00 | level found on H4 extreme bar within 5d | EXACT |

## 3) Discrepancy analysis — prior audit overstated its evidence (methodology, not prices)

No price/label discrepancy was found. The prior audit's **methods** had four defects that this pack corrects. These are evidence defects, not production defects.

1. **Circularity (major).** The prior audit computed `true_high/true_low` with `detect_periodic_levels._aggregate()` — the exact function that produced the labels — and for EQH it reused `_cluster()`. A mismatch was therefore impossible. Its `WRONG_EXTREME = 0` was guaranteed, not demonstrated. This verification iterates bars independently.
2. **`FULL_WEEK_PWH_PWL: YES` was false.** The prior renderer used `_slice_candles(..., before=1500, after=600)` ≈ 25 h / 10 h of M1 around `formed_at`, not a Mon→Mon week. The file existed, so the boolean passed, but no chart spanned a week. This pack sets `xlim` to exactly `[Monday 00:00, next Monday 00:00)` (verified on `A_prior_wrongs_pwh_pwl_pwh_pwl_0327.png`: x-axis 06-02 00:00 → 06-09 00:00, ~6 900 M1 bars / 672 M15 bars, ≥5 trading days).
3. **Structural audit was a hardcoded pass.** Every structural row was written with `flag=EXACT_MATCH` and empty `true_high/true_low` — no check was performed. This pack adds a real extreme-bar lookup.
4. **Structural `formed_at` is not the price bar.** `Swing.timestamp` returns the **base candle** timestamp; `level` comes from the N-bar swing candle. Any bar-identity check against `formed_at` fails spuriously (this is exactly what happened on `structural_swing_1236`: label 3997.658 vs base-candle low 4008.215). The correct check is "does the label price exist as an H4 high/low bar within the base-candle window", which is what this pack implements. **Recommendation (no code change made):** the research exporter should carry `extreme_bar_at` for structural rows so charts and audits do not need to re-derive it.

**Cause of the Architect's visual "deeper low visible" (V1/V2):** the deeper low is the *previous* Mon-anchored week's low, which lies outside the claimed period:

| Case | Claimed week | True week low | Previous week | Previous week low |
|---|---|---:|---|---:|
| V1 | 2025-06-02 → 06-09 | 3301.195 | 2025-05-26 → 06-02 | **3245.198** |
| V2 | 2025-08-04 → 08-11 | 3344.748 | 2025-07-28 → 08-04 | **3267.955** |

Any window that bleeds one week backwards shows a lower print and makes a correct PWL look wrong. With the exact Mon→Mon window, both charts are clean.

**Cause of "higher later" (V3/V4):** there is no higher high inside the locked session window (session high equals the label at 06:45 / 06:52). The higher print sits after 07:00 UTC — i.e. in London, a different session and a different level. Correct behavior, chart-context illusion.

**Semantic observation for Architect (not a defect):** EQH/EQL clusters can be temporally very wide. `eqh_eql_0002` spans 2025-04-16 → 2025-07-01 and `eqh_eql_0004` spans 2025-05-22 → 2025-07-07, even though member prices are within 0.35–0.43 (< 0.45 tolerance). The `_cluster()` greedy anchor permits this. Whether a 2.5-month-apart "equal high" is a meaningful liquidity level is a labeling-semantics decision for the Architect; no change was made.

## 4) Visual → audit join (summary)

`06_RESEARCH/results/p1_independent_verify/visual_to_audit_join.csv` — 17 rows, 17 matched (no `NO_MATCH`).

- 5 Architect WRONG/weak cases → all matched an exported event; prior `audit_flag` EXACT_MATCH; independent flag EXACT_MATCH.
- 12 controls (3 session [Asia low / Asia high / London], 3 structural BSL, 3 PDH/PDL, 3 PWH/PWL) → all EXACT_MATCH.

Note on V5: the exported structural `formed_at` (04:00) is the base candle, while the visual observation referenced 07:28 (the price low). Both refer to the same swing; see §3.4.

## 5) Pack paths + MANIFEST summary

`06_RESEARCH/results/p1_rescore_pack/` — `MANIFEST.csv`: **22 rows**, all `caption_ok=YES`, `bounds_drawn=YES`, zero placeholders.

| Section | Rows | Content |
|---|---:|---|
| `A_prior_wrongs/` | 5 | V1–V5 with period boundaries (full Mon→Mon week for PWH; session open/close; structural base-candle + extreme-bar markers) |
| `B_controls/` | 12 | 3 session (Asia low, Asia high, London), 3 structural BSL, 3 PDH/PDL with day bounds, 3 PWH/PWL with full Mon→Mon weeks |
| `C_eqh_clusters/` | 5 | EQH/EQL with every cluster touch plotted, span boundaries, `n_touches` |

Contract applied to every chart: level line; vertical period boundaries; caption with family, side, price, `period_id`, `formed_at`, source, audit flag and independent flag.

Other artifacts: `06_RESEARCH/results/p1_independent_verify/{recompute_sample.csv, recompute_summary.json, visual_to_audit_join.csv, run.log}`.

## 6) Status

- **P1 is NOT accepted.** This pack is evidence only; chart verdicts remain the Architect's.
- **P2 remains BLOCKED.**
- No detector, threshold, session, swing or tolerance change was made. `locked_constants.py` diff empty; no `04_SRC/smc/**` edits.

## 7) Recommended Architect focus list (max 10)

1. `A_prior_wrongs` PWH SSL 3301.195 (week Jun 2; prior-week low 3245.198) — confirms "deeper low" is out-of-period.
2. `A_prior_wrongs` PWH SSL 3344.748 (week Aug 4; prior-week low 3267.955).
3. `A_prior_wrongs` Session Asia BSL 3345.198 (Jun 2) — confirm no in-session higher high.
4. `A_prior_wrongs` Session Asia BSL 3334.348 (Jul 1).
5. `A_prior_wrongs` Structural SSL 3327.275 — base candle vs extreme bar; dominant-low judgment is separate.
6. `C_eqh_clusters` EQH 3345.548 (`eqh_eql_0004`, spread 0.35, span May→Jul).
7. `C_eqh_clusters` EQH 4030.385 (`eqh_eql_0008`, spread 0.43).
8. `C_eqh_clusters` EQL 3301.465 (`eqh_eql_0005`) — near-identical to PWH SSL 3301.195; check cross-family duplication.
9. `B_controls` PWH SSL 3763.665 (week Sep 29, full-week window).
10. `B_controls` PDH/PDL 3295.208 (Jun 1, day bounds).

## Repro

```bash
PYTHONPATH=04_SRC python 06_RESEARCH/scripts/p1_independent_verify.py
```
