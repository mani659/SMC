# HONEST-R RECOMPUTE REPORT (original_sl denominator)

**Status:** COMPLETE 2026-09-20 · measurement only, no strategy/threshold changes.
**Script:** `06_RESEARCH/scripts/honest_r_recompute.py` (R1 path rules, dual denominators).
**Sample (labeled, NOT generalized):** 39 unique setups from the instrumented verify_w0 window (2025-10-01..08), deduplicated post-hoc by (direction, entry, original_sl) keeping the earliest fill — the verify run over-arms without ZoneRegistry dedup, so 115 rows collapse to 39. Bars timestamp-anchored (window-relative indices never touch the canonical series).
**Outputs:** `06_RESEARCH/results/honest_r_recompute/trades_honest_r.csv` (39 rows) + `honest_r_summary.json`.
**Method per setup:** walk own window; risk_honest = |entry − original_sl|; risk_working = |entry − working sl| (R1-replica denominator); MFE/MAE floored at 0; R3-taxonomy failure modes on honest MFE_R; Wilder ATR(14) stop ratios.

---

## 1. Headline numbers (n = 39; 8 BE-modified, 31 full-SL)

| Metric | Honest (original_sl) | Contaminated (working sl) | R1 book-level (blended, for reference) |
|--------|----------------------|---------------------------|----------------------------------------|
| Median MFE_R | **0.42** | 0.42 | 0.55 |
| Median MAE_R | 1.24 | — | 1.73 |
| % ≥ 1R | **30.8% (12)** | 38.5% (15) | 37.5% |
| % ≥ 2R | **5.1% (2)** | — | 27.9% |
| % ≥ 3R | **2.6% (1)** | — | 26.4% |
| Never favorable | 12 (30.8%) | — | 29.3% |
| Median stop/ATR | **0.85** | — | 0.72 blended / 0.84 honest-split |

## 2. How much did contamination inflate R multiples?

- At the median: barely (0.42 vs 0.42) — only 8/39 setups are BE-modified here.
- At the decision line: 3 setups flip across 1R (30.8% vs 38.5%) — and all three flips are BE-scratches with spectacular fake multiples: **10.74→0.76R, 13.25→0.42R, 12.52→0.74R** (tickets 8, 90, 93). The contamination mechanism is confirmed red-handed: BE-tightened denominators manufacture double-digit R out of sub-1R excursion.
- Full-SL-only honest (n=31): median MFE **0.23R**, 22.6% ≥1R — same neighborhood as the Phase C decontaminated split (0.18R / 17.1%), cross-sample consistency for the entry-weakness verdict.
- Stop/ATR honest 0.85 (F 0.84) confirms sub-ATR stops on true original stops; the 0.72 blended figure is retired, the 0.099 BE-level figure was never a stop at all.

## 3. Per-trigger splits (F/B/A minimum)

| Trigger | n | Med MFE_R honest | ≥1R honest | Med stop/ATR honest |
|---------|---|------------------|------------|---------------------|
| F | 37 | 0.42 | 32.4% | 0.84 |
| B | 2 | 0.27 | 0.0% | 2.69 (wide B stops in this window) |
| A | 0 | — | — | — |

Small-n by construction (labeled sample, not a baseline) — directions only, no family verdicts from this table alone.

## 4. Interpretation (plain answers)

1. **Inflation magnitude:** median-level effect small in mixed samples, catastrophic at the showcase level (10–13R → <1R on BE trades) and decisive at threshold lines that select "promising" trades — any future subset selection on contaminated R would cherry-pick BE artifacts.
2. **Entry-selection diagnosis HOLDS, strengthened:** honest full-SL medians (0.23R here, 0.18R Phase C split) are weaker than every blended number ever published; 30.8% never favorable reproduces R1's 29.3%; excursion dies steeply past 1R (5.1% ≥2R).
3. **F vs B unchanged:** F weak on honest stops (0.42R); B unmeasurable here (n=2, wide stops this window) — prior B conclusions (stop-timing, R2 SL-first 70/70) stand on Phase C evidence, untouched by this sample.
4. **Next stratified sample must:** (a) use original_sl exclusively (now exportable — never recompute from working sl again); (b) oversample F scratches vs instant-stops × sessions with honest denominators; (c) include B holds across years for the stop-timing question; (d) treat any MFE_R > 5 with suspicion until its denominator is verified original.

---

*End of honest-R report. All R-multiple work henceforth uses original_sl; blended-denominator figures are superseded where honest splits exist.*
