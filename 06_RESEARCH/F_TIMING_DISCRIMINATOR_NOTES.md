# F-TIMING DISCRIMINATOR NOTES (research annotation, NOT a live gate)

**Status:** COMPLETE 2026-09-20 · labels are research annotations; no live gates proposed, no thresholds touched, no strategy changes.
**Script:** `06_RESEARCH/scripts/f_timing_labels.py` (rule v1, frozen below).
**Population:** all 37 unique F setups from the instrumented verify window (deduped; honest denominators via original_sl throughout).
**Outputs:** `06_RESEARCH/results/f_timing/f_timing_labels.csv` (per-setup features + label + zone relation + honest MFE join) + `f_timing_summary.json`.
**Stratified charts re-rendered** with zone rectangles + original_sl display (`results/trade_inspector/stratified/`).

---

## 1. Rule v1 definitions (reproducible)

Per setup, trailing 30 M1 bars before entry: range hi/lo, Wilder ATR(14) at entry, direction-adjusted `chase_pos` (1 = extreme in trade direction: long `(entry-lo)/(hi-lo)`, short `(hi-entry)/(hi-lo)`):

| Label | Rule |
|-------|------|
| `chop` | 30-bar range < 1.5× ATR |
| `late_chase` | chase_pos ≥ 0.80 |
| `mid_move` | 0.45 ≤ chase_pos < 0.80 |
| `structured_pullback` | chase_pos < 0.45 |
| `unclear` | degenerate range / missing data |

Zone relation (independent axis, already in export): INSIDE / above-below + % of zone height.

## 2. Label distribution (n = 37)

late_chase 23 · mid_move 13 · structured_pullback 1 · chop 0 · unclear 0.

## 3. Eyeball validation (11 chart-viewed setups)

| Ticket | Eyeball | Rule (cp) | Verdict |
|--------|---------|-----------|---------|
| 8, 28, 48, 92 | late_chase | late_chase (0.90–1.00) | EXACT (4) |
| 11 | late_chase | mid_move (0.539) | adjacent, borderline |
| 14 | mid_move | late_chase (0.97) | adjacent, rule arguably righter (97% extreme) |
| 63 | mid_move | late_chase (0.812) | adjacent, just over the 0.80 line |
| 53 | structured_pullback (V-recovery) | mid_move (0.697) | MISS — V-shapes re-enter high; rule blind to path shape |
| 1 | pullback-ish | late_chase (0.871) | MISS-ish — entry sat 87% up a drop leg, not at an origin |
| 87, 115 | chop | mid_move (0.77–0.79) | MISS — chop rule never fires (30-bar ranges always > 1.5×ATR here) |

4 exact, 5 adjacent/borderline, 2 systematic miss classes: (a) chop needs a better operationalization than range/ATR (direction-change count or compression shape — future work, NOT retuned here); (b) V-recovery pullbacks re-enter high, so pure position-in-range undercounts true pullback structure. Rule v1 kept frozen with these misses disclosed.

## 4. Honest-R by label (full n = 37 coverage via honest_r join)

| Label | n | Median MFE_R honest | % ≥ 1R honest |
|-------|---|---------------------|---------------|
| late_chase | 23 | **0.03** | **13.0** |
| mid_move | 13 | **1.17** | **61.5** |
| structured_pullback | 1 | 1.23 | 100.0 |

Despite crude rules and borderline wobble, the timing axis separates outcomes by an order of magnitude: mid-move entries reach 1R at 61.5% vs 13% for chases. Small-n and single-window — directional evidence for a discriminator, not a validated filter.

## 5. B note (separate, not mixed into F stats)

B setups were not labeled (F-only script). Stratified B charts stand as rendered: shelf-centered entries decided by stop placement vs the shelf; Phase C B holds show the same shape across years. No timing-label claims for B.

## 6. Conclusions / next

- The F book's weakness concentrates in chase-position entries (23/37 setups, 0.03R median). Timing position is the sharpest known discriminator — sharper than model tags (which flicker) or sessions (no effect).
- Zone-entry distance stays an independent axis: 10/11 stratified entries sit outside recorded zones regardless of timing label; the merge-artifact hypothesis (widest-zone retention) is untested and owned by a future export/logic review, not this study.
- Inspector now draws zone rectangles + distance readouts and prefers original_sl (sidecars carry `sl_display_source`, `zone_relation`).
- Next (Lead Architect pick): (a) pullback-shape refinement (V-recovery detector) + chop operationalization on a wider stratified sample; (b) F-timing × session matrix at larger n; (c) Phase D ops. None of this is a live gate until the §6 promotion bar is met with walk-forward evidence.

---

*End of timing notes. Labels live in `results/f_timing/`; charts re-rendered with zone readout. No redesign proposed.*
