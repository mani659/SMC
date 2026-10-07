# F-TIMING WIDER-SAMPLE VALIDATION (frozen v1, no retune)

**Status:** COMPLETE 2026-09-20 · validation only, rules imported frozen (any drift would be an import error, not a silent retune).
**Script:** `06_RESEARCH/scripts/f_timing_wider.py` (imports PRE_BARS/CHOP_ATR_MULT/CHASE_HI/CHASE_LO from `f_timing_labels`; honest MFE with original_sl; timestamp-anchored bars).
**Sample:** 64 pooled unique F setups from verify_w0 (Oct 1–8) + verify_w1 (Oct 1–15), deduplicated cross-window by (direction, entry, original_sl) keeping the earliest fill. Windows overlap in time — dedup is load-bearing and reported. NOT generalized beyond instrumented October flow.
**Outputs:** `06_RESEARCH/results/f_timing_wider/f_timing_wider_labels.csv` + `f_timing_wider_summary.json`.
**Cost note:** verify_w1 (15,180 bars) needed a ~1h run budget; artifacts write once at completion (no partial saves on timeout kill — rerun from scratch if interrupted).

---

## 1. Label counts (frozen v1)

| Label | Wider n=64 | Original n=37 |
|-------|-----------|---------------|
| late_chase | 42 (65.6%) | 23 (62.2%) |
| mid_move | 19 (29.7%) | 13 (35.1%) |
| structured_pullback | 3 (4.7%) | 1 (2.7%) |
| chop / unclear | 0 / 0 | 0 / 0 |

Mix is stable: chase-dominant (~2/3), mid (~1/3), pullback rare. Chop rule still never fires (consistent v1 behavior, still a known miss class).

## 2. Honest MFE_R by label (original_sl denominators)

| Label | n | Median MFE_R (was) | % ≥ 1R (was) | % ≥ 2R |
|-------|---|--------------------|--------------|--------|
| late_chase | 42 | 0.23 (0.03) | 26.2 (13.0) | 11.9 |
| mid_move | 19 | 1.05 (1.17) | 57.9 (61.5) | 15.8 |
| structured_pullback | 3 | 1.23 (1.23) | 66.7 (100.0) | 33.3 |

## 3. Stability verdict: YES (separation survives, magnitude moderated)

- Rank order preserved on both median and ≥1R rate: pullback ≥ mid_move ≫ late_chase.
- Mid_move rate essentially identical (57.9% vs 61.5%); median 1.05 vs 1.17.
- Chase ≥1R doubled in absolute terms (13.0% → 26.2%) but remains less than half the mid rate, with median 0.23R vs 1.05R (~4.5× gap). At n=42 vs 23 this moderation reads as sampling noise plus October-regime breadth, not rule decay.
- Pullback still n=3 — no inference licensed; direction only.
- **RETUNE_ALLOWED: NO.** Rule text untouched; constants imported, not copied.

## 4. What this licenses / does not license

- Licensed: treating chase-position as a negative timing flag and mid-move as the relatively healthier entry shape in F-flow research notes; prioritizing pullback-shape refinement + chop operationalization as open rule work.
- Not licensed: any live gate, any threshold change, any claim beyond instrumented October M1 flow, any per-family expectancy statement (still small-n, single regime, no walk-forward).

---

*End of wider validation. Next: Lead Architect pick (timing follow-ons vs Phase D ops). No code, threshold, or strategy changes made or proposed.*
