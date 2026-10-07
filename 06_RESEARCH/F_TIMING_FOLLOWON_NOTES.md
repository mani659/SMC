# F-TIMING FOLLOW-ON NOTES (v2 research labels, NOT a live gate)

**Status:** COMPLETE 2026-09-20 · single-pass rules committed in code BEFORE running; no iteration, no tuning, no thresholds touched, no strategy changes.
**Script:** `06_RESEARCH/scripts/f_timing_followon.py` (v2 definitions §1; honest MFE with original_sl; timestamp-anchored bars).
**Sample:** same 64 pooled unique F setups as the wider validation (no new data — relabeling only).
**Outputs:** `06_RESEARCH/results/f_timing_followon/followon_labels.csv` (v1 + v2 labels side-by-side) + `followon_summary.json`.
**B:** untouched by design (F-only script; B verdicts stand on stratified + R2 evidence).

---

## 1. Pullback definition (v2)

`structured_pullback_v2` = V-shape recovery OR v1 calm tail (chase_pos < 0.45):
- **V-shape:** trailing 30-bar trough with drop ≥ 1.5×ATR from the pre-trough high AND entry recovered ≥ 50% of that drop.
- Rationale (a priori): ticket-53 shape — sharp drop, snap-back, retest entry. Stated before running; judged below on outcomes, not adjusted.

## 2. Chop definition (v2, first operationalization)

`chop` = ≥ 12 direction reversals in trailing 29 close steps AND |net displacement| < 1.0×ATR (oscillating + net-flat). Rule order: chop → pullback → chase ladder. Constants are conventional (40% reversal rate, 1-ATR flatness), NOT fitted — reported with this caveat.

## 3. Relabel counts (v1 → v2, n = 64)

| v1 \ v2 | late_chase 16 | mid_move 8 | structured_pullback 27 | chop 13 |
|---|---|---|---|---|
| late_chase 42 | 16 | 0 | **20** | 6 |
| mid_move 19 | 0 | 8 | 6 | 5 |
| structured_pullback 3 | 0 | 0 | 1 | 2 |

## 4. Separation check (honest MFE_R)

| v2 label | n | Median MFE_R | % ≥ 1R |
|---|---|---|---|
| late_chase | 16 | 0.00 | 12.5 |
| mid_move | 8 | 1.51 | 62.5 |
| structured_pullback | 27 | 0.80 | 48.1 |
| chop | 13 | 0.00 | 30.8 |

Chase-vs-rest separation survives (12.5% vs ~50–60%); mid_move identical to wider-validation (62.5%).

## 5. Verdicts (plain)

- **V-shape rule OVER-ADMITS — intent failed, reported not fixed.** 20 former chases migrate on intraday dips; migrant medians (drop 3.34×ATR, recovery 2.0×) show entries blowing THROUGH the pre-trough high — the rule measures rally-extension-with-dip, not pullback-to-level retest. All 20 migrants sit above their recorded zones. The rule is frozen as-documented; pullback-shape refinement stays OPEN and needs swing-anchored construction (drop from a confirmed swing extreme + retest location), not window min/max.
- **Migrants still separate (0.75 vs stayer-chase 0.0 median):** the rule accidentally measures momentum persistence, which carries mild signal — reported as an observation about momentum, NOT as pullback validation.
- **Chop rule FIRES (13 setups) but is unvalidated:** median 0.0 with 30.8% ≥1R; whether the reversal+flat definition carves a tradable regime or repackages noise is unknown — needs a dedicated chop-vs-trend outcome study, not assertion here.
- **Mid_move is the stablest bucket** across v1, wider, and v2 framings (62.5% twice, medians 1.17 → 1.51): entries neither extreme nor flat keep outperforming on honest excursion.
- **No live gate is licensed.** Nothing here meets any promotion bar (single regime, small-n, rule family admittedly crude).

## 6. Next (Lead Architect pick)

Pullback-shape v3 anchored on confirmed swing geometry (not window extrema) + chop-vs-trend outcome study + wider-regime coverage; or Phase D ops. Export needs for either: ORIGINAL sl (have it), zone bounds (have them), swing-anchored drop/recovery (needs swing indices persisted — export-patch follow-on candidate).

---

*End of follow-on. B untouched; thresholds untouched; one pass, no iteration.*
