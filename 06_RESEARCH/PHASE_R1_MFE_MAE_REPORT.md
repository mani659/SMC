# TRACK R1 — MFE / MAE STUDY REPORT

**Status:** COMPLETE 2026-09-19 · offline diagnosis only, no strategy-code changes.
**Script:** `06_RESEARCH/scripts/r1_mfe_mae_study.py` (imports the data loader only — no detection/trigger/risk modules).
**Inputs:** `06_RESEARCH/results/phase_c_baseline_run1/merged/trades.csv` (761 rows) + canonical `07_DATA/XAUUSD_M1.parquet` via `smc.data.parquet_loader.load_ohlcv_parquet` (1,768,123 bars; bar-index alignment verified 12/12 pre-run).
**Outputs:** `06_RESEARCH/results/r1_mfe_mae/trades_mfe_mae.csv` (761 rows, 0 skipped) + `06_RESEARCH/results/r1_mfe_mae/r1_summary.json`.
**Method:** per trade, window = canonical bars [entry_bar .. exit_bar] inclusive; risk_distance = |entry − sl|; LONG: MFE = max(high−entry), MAE = max(entry−low) (mirrored for SHORT); excursions floored at 0 with never-favorable/never-adverse flags; bars_to_mfe = first bar attaining MFE (favorable trades only).

---

## 1. Overall MFE_R / MAE_R distributions (n = 761)

| Stat | MFE_R | MAE_R |
|------|-------|-------|
| Median | 0.55 | 1.73 |
| Mean | 20.73 | 3.32 |
| Never favorable / never adverse | 223 (29.3%) / 0 (0%) | — |

- Every trade went adverse at some point (never_adverse = 0); nearly a third never went favorable at any point in their window.
- Means are skew artifacts: a handful of multi-day holds on tight stops reach 500–2200R (max 2200.0R on a 2319-bar B hold, risk 0.022). Medians and threshold rates are the decision stats, not means.
- Measurement bias (disclosed): MFE is measured over full bar ranges including the entry bar's pre-fill path (fill occurs intrabar at the limit). This biases MFE *upward* — the weak-median conclusion below is therefore conservative, not flattered.

## 2. Threshold rates (% trades with MFE_R ≥ level)

| ≥1.0R | ≥1.5R | ≥2.0R | ≥3.0R |
|-------|-------|-------|-------|
| 37.45% (285) | 30.49% (232) | 27.86% (212) | 26.41% (201) |

Only ~38% of trades ever saw 1R of favorable excursion; ~26% saw 3R.

## 3. Per-trigger splits (F / B / A minimum; C n=1, E n=2 — counts only)

| Trigger | n | Median MFE_R | Median MAE_R | ≥1R | ≥2R | ≥3R | Median bars_to_mfe |
|---------|---|--------------|--------------|-----|-----|-----|--------------------|
| F | 659 | 0.55 | 1.75 | 36.1% | 25.5% | 23.8% | 0 |
| B | 70 | 6.12 | 1.86 | 50.0% | 50.0% | 50.0% | 6.5 |
| A | 29 | 0.54 | 1.42 | 37.9% | 27.6% | 27.6% | 2.0 |
| C | 1 | 33.64 | 1.17 | (1) | (1) | (1) | 14 |
| E | 2 | 0.31 | 1.16 | 0% | 0% | 0% | 0.0 |

- **B is the outlier:** half its trades reach ≥3R (median 6.12R) on long holds (median window 15 bars vs 2 for F). Excursion exists; the BE-only exit never harvests it.
- **F (86.6% of the book):** median 0.55R, 64% never reach 1R. Entry-side weakness dominates the aggregate.
- **A** mirrors F at small n. C/E carry no evidence.

## 4. Time-to-MFE distribution (R1b)

- Median bars_to_mfe over favorable trades: **1.0 bar** (F: 0, A: 2.0, B: 6.5).
- Median window: 2 bars (294/761 = 38.6% are single-bar windows — same-bar SL-first closes).
- Reading: when favorable excursion happens at all, it typically happens immediately (entry bar or next). B is the exception — slow-building excursion over multi-day holds.

## 5. Interpretation against ACTIVE_TODO §6 gates

- **Gate 6.1 (strong MFE + TP helps → exit primary): NOT cleared for the book as a whole.** Aggregate MFE is weak (median 0.55R, 29% never favorable). A blanket exit-model fix cannot rescue trades that never move favorably.
- **Gate 6.3 (mixed by trigger → family-level): CLEARED.** The book splits cleanly: B shows harvestable excursion (exit-model story); F/A show entry-side weakness (selection story). Diagnosis must proceed per family, not per book.
- **Gate 6.2 (weak MFE → entry primary): CLEARED for F/A** (87%+ of flow). R4 (Pillar-2 kill-sample) is now conditionally justified for F-routed POIs only — not for the book.

## 6. Is the R2 synthetic TP study justified next?

**YES.** R1 produces exactly the mixed picture R2 is designed to resolve: (a) test whether B's ≥3R excursion in 50% of its trades converts to expectancy under 1.5R/2R/3R fixed TPs; (b) confirm F is unrescuable even at low-R TPs (if F stays negative at 1.5R, the entry — not the exit — is the binding constraint for 87% of flow). R2 replays frozen entries/SL offline; it changes nothing in the live system.

---

*End of R1 report. Next: R2 synthetic TP counterfactuals (Track R, separate prompt). No locked-constant edits, no strategy-code changes made or proposed in this study.*
