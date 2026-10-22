# F ENTRY SELECTIVITY + POST-EXIT PATH (TRACK B RESEARCH)

> **DIAGNOSTIC ONLY — NOT PERFORMANCE / NOT EDGE.**
> Every table below describes small, single-regime samples with frozen
> descriptive labels. No table recommends, implies, or justifies a live
> filter, gate, or threshold. The separation verdict (§7) is a
> measurement-routing decision only: which F slices to measure on the
> next backtest re-run — not a rule to ship.

**Date:** 2026-10-11 · **Authority:** Lead Architect Track B directive (research/logging only).
**F_SELECTIVITY_STATUS: PASS** (script + artifacts + 8 new tests green; no decision-logic change).
**Scope:** research only. No `04_SRC/smc/` decision-logic change (triggers/risk/pillars untouched), no locked-constant edit, no threshold fishing, no WF/MC.

---

## 1. Method (frozen before measurement — nothing iterated)

**Timing labels — Rule v1 verbatim** (`F_TIMING_DISCRIMINATOR_NOTES.md`):
trailing-30-M1-bar range, Wilder ATR(14) SMA-seeded, direction-adjusted
`chase_pos` (1 = extreme in trade direction); `chop` if 30-bar range <
1.5×ATR; `late_chase` if chase ≥ 0.80; `mid_move` if chase ≥ 0.45;
else `structured_pullback`; degenerate range/ATR → `unclear`. Zone
relation on a separate axis (INSIDE / above NN% / below NN% / unknown).
Reimplemented dependency-free in `06_RESEARCH/scripts/f_selectivity_post_exit.py`
(identical math — proven by fidelity check §6); the original
`f_timing_labels.py` (pandas, hardcoded paths) was not forked.

**Post-exit taxonomy — `hypothesis_outcome_study.classify` reused verbatim
via import** for TP-bearing rows (same 5 labels, same 0.25 analytics
divider, same BE-scratch-first order). Rows WITHOUT a TP level cannot
reach the TP-path branches (never defaulted): they run the same
MFE-only restriction — BE-scratch → MFE_ONLY; MFE_R < 0.25 →
REJECTED; MFE > 0 → MFE_ONLY; else REJECTED.

**Frozen horizon: H = 100 M5 bars** (~one trading day; 5× the product's
20-bar give-up scale). Fewer than 100 M5 bars after exit in-series →
DATA_GAP, strict (never extrapolated). Forward scan on M5 (product exec
series); labels + excursion on M1 (honest_r convention).

**Honest R: |entry − original_sl|, STRICT** — missing/degenerate
denominator → R empty (never a BE-modified working stop). Excursion
referenced to the **fill price** (not bar close) — bit-identical to the
published honest_r table on overlap (§6).

**Identity + pooling:** unique trade = entry+exit minute + direction +
entry price (minute- and float-normalized, so spelling variants collide;
run-local tickets never participate). Per-label pooled stats use the
verify pool (F only); product-era rows are labeled + listed individually
(n = 2 pools nothing); non-F triggers are side counts only
(unlabeled by design).

## 2. Samples (paths + SHAs in `summary.json`)

| Sample | Rows | Unique trades | F | Fields present |
|---|---|---|---|---|
| product-6m (costs-on run1) | 3 | 3 | 2 | all (tp, tp_source, original_sl, costs) |
| pilot + posttp r1/r2 | 2 + 3 + 3 | **0 new** (all 8 re-find product rows) | — | duplicates, dropped with record |
| verify-w0 (Oct 1–8) | 115 | 39 | 36* | original_sl + zones; **tp null on all rows** |
| verify-w1 (Oct 1–15) | 216 | 30 new (re-finds w0's full set) | 28* | same shape as w0 |
| **verify pool (deduped)** | 331 | **69 (64 F + 5 B)** | **64** | — |
| phase-c-5y (merged) | 761 | side counts only | 659 | **NO original_sl, NO tp on any row** → honest R and TP-path outcomes uncomputable; no per-trade rows emitted, nothing faked |

\* F split implied by totals (64 verify F; B = 5 side rows).

**Dedupe transparency:** 1,103 book rows → 72 unique trades (270 dropped as
byte-identical re-recordings: pilot 2 + posttp 6 of product-6m; w0 76
internal + w1 186 of which 115 re-find w0's rows). The verify books
over-arm per bar without dedup, so identical fills repeat under many
tickets (cf. the FLOWCHART_MATCH over-arming finding) — collapsing them
is what makes n honest. Phase C contributes trigger mix (F 659 / B 70 /
A 29 / E 2 / C 1) and close mix (754 stop_loss + 7 friday_eod) only.

## 3. Selectivity labels (verify F, n = 64 — DIAGNOSTIC ONLY)

| Label | n | Median MFE_R | Median MAE_R | % ≥ 1R | % ≥ 2R | Exit mix | Median hold M1 (M5) |
|---|---|---|---|---|---|---|---|
| late_chase | 42 | **0.23** | 1.38 | **26.2%** | 11.9% | all stop_loss | 0 / (0) |
| mid_move | 19 | **1.05** | 1.18 | **57.9%** | 15.8% | all stop_loss | 3 / (1) |
| structured_pullback | 3 | 1.23 | 1.15 | 66.7% | 33.3% | all stop_loss | 2 / (0) |
| chop / unclear | 0 / 0 | — | — | — | — | — | — |

Zone axis (verify F): **below 26 / above 38 / INSIDE 0** — verify entries
sit outside their zones without exception (vs both product F rows
INSIDE — listed, not pooled). All verify exits are stop_loss (exit-mix
column has zero variance here — stated, not hidden).

## 4. Post-exit outcomes (DIAGNOSTIC ONLY)

| Outcome | All (72) | F (66) | Notes |
|---|---|---|---|
| REJECTED | 21 | 20 | 19 verify (MFE_R < 0.25, non-scratch) + product t1; frozen BE-default absorbs near-zero-loss rows first (see below) |
| SL_THEN_TP_PATH | 1 | 1 | product t3 (BE-stop exit, TP touched strictly after exit) |
| TP_REACHED | 1 | 0 | product C row (take-profit exit) |
| MFE_ONLY | 49 | 45 | all 45 F are verify rows (39 via frozen BE-default + 6 measured MFE_R ≥ 0.25); + 4 non-F side rows |
| DATA_GAP | 0 | 0 | no truncated horizons, no unresolvable timestamps |

\* MFE_ONLY F = 45: 44 verify + ... (19 verify REJECTED + 44 verify MFE_ONLY + product t3 SL_THEN_TP + t1 REJECTED = 64 + ... ; non-F MFE_ONLY 4.)

Composition truthfully stated: **39 of 64 verify-F exits take the frozen
BE-scratch default** (|pnl| < 0.15 + stop_loss → MFE_ONLY before any R
evaluation), so the outcome split is dominated by that inherited rule,
not by measured rejection. The independent prior taxonomy agrees only
partially (16 be_scratch of 69 + gave_back/instant_stop/no_follow_through
classes) — cross-check reported, rule kept frozen regardless.

Cross-tab highlights (counts): REJECTED = late_chase 14 + mid_move 4 +
pullback 1 (+ product pullback t1, atr_fallback) + 1 non-F (B);
MFE_ONLY spread across all labels (chase 28 / mid 15 / pullback 2; + 4 non-F side rows);
tp_source = "unknown" for every verify row (pre-TP-feed books) vs
product's atr_fallback 2 / structural_swing 1; close_kind all stop_loss
on verify rows.

Product-era rows (listed, never pooled): t1 F short pullback INSIDE,
MFE_R 0.12, REJECTED (atr_fallback, stop_loss); t2 C TP_REACHED
(structural_swing); t3 F long pullback INSIDE, MFE_R 0.31,
SL_THEN_TP_PATH (atr_fallback, BE-stop exit, TP touched after exit).

## 5. Fidelity checks (port validation — all pass)

- **(a) Labels 37/37 exact** vs the prior `f_timing_labels.csv` (same tickets, same M1 series, same constants).
- **(b) Honest R 37/37 to 4dp** vs the honest_r table (identical inputs and ops; diffs ≤ 5e-5 = CSV rounding only). This check caught and fixed a real convention error during the build (bar-close vs fill reference — §6 of the build log in git history is not needed; the note below records it).
- **(c) Zone relation 64/64** on F rows vs stop_vs_structure (5 non-F rows unlabeled by this study's design — the only "mismatches," by construction).

Convention correction recorded honestly: the first run referenced
excursion to the entry-bar close (inherited helper default) and
disagreed with honest_r by up to 3R; switching to the fill reference —
the honest_r convention — reproduced the published table bit-for-bit.
The outcome divider for TP-absent rows operates on that same R, so
tables and outcomes cannot disagree (the prior classifier runs
verbatim only on TP-bearing rows).

## 6. Interpretation limits (read before §7)

1. **Single regime:** the verify pool is 15 days of October 2025, one
   M1-execution pre-TP-feed book, all exits stop_loss. Any separation is
   single-regime evidence, not a general filter.
2. **Product n = 2F:** labeled and listed, never pooled; no percentage is
   computed on n = 2.
3. **TP paths exist only where TP levels exist** (3 product rows);
   verify rows test the MFE/REJECTED restriction only.
4. **BE-default dominance** (39/64) shapes the outcome split by frozen
   rule, not by measurement; an independent taxonomy is narrower.
5. **Phase C (659 F) contributes nothing measurable** — no original_sl,
   no tp. The largest F book is structurally unusable for honest-R or
   path work until re-run with the export patches.
6. **Hold bars coarse** (M5 medians 0/1/0 for M1-executed trades; M1
   medians 0/3/2 also reported).
7. **No gate, no threshold, no live rule** follows from any table here.

## 7. Separation verdict + expected use

**SEPARATION: YES (reproduced) — late_chase (n = 42: 26.2% ≥ 1R, median
0.23R) vs mid_move (n = 19: 57.9% ≥ 1R, median 1.05R), with frozen
rules on deduped unique trades, reproducing the prior wider-study
numbers exactly. Caveats: single Oct-2025 regime, 15-day M1 book,
pre-TP-feed, all-SL exits, no OOS — still not a live rule.**

**GATE_RECOMMENDED: CANDIDATE_ONLY** (with the caveats above): the
late_chase-vs-rest timing character is the measurement axis to carry
into the next backtest re-run — i.e., future books must preserve the
fields that make this slice measurable (original_sl, zone bounds,
entry/exit timestamps, TP level + tp_source, entry_anchor where
emitted) — NOT a filter to ship, tune, or gate anything tomorrow.

**What to measure next (the directive's expected use):** (a) the same
frozen labels + H = 100 post-exit scan on the next TP-bearing book with
n (does the chase/rest split survive with TP paths present?); (b) the
BE-scratch default's share outside this slow week (is 39/64 a regime
artifact?); (c) M8-attributed F rows separately once fills exist;
(d) a second regime before any candidate hardens further.

---

**Artifacts:** `06_RESEARCH/scripts/f_selectivity_post_exit.py` (new;
imports `hypothesis_outcome_study` classifiers, forks nothing) ·
`06_RESEARCH/results/f_selectivity_post_exit/` (`trades_f_selectivity.csv`
72 rows × 27 columns, `summary.json` with manifest SHAs, frozen params,
tables, cross-tabs, limitations) · tests
`04_SRC/tests/test_f_selectivity_post_exit.py` (8: Rule-v1 boundaries,
zone cases, honest-R strictness, fill-reference lock, no-TP branch,
truncation/unresolvable DATA_GAP, identity normalization).
