# HTF POST-SWEEP PATH ANALYSIS (DIAGNOSTIC)

> **DIAGNOSTIC — NOT EDGE.**
> 1,542 first-sweeps measured on frozen short horizons. No gate was
> loosened, no threshold moved, no production code touched. No table
> supports or refutes edge, authorizes live capital, or licenses any
> filter.

**Date:** 2026-10-11 · **Authority:** Lead Architect directive (read-only measurement).
**POST_SWEEP_STATUS: PASS** (script + artifacts + 6 new tests green; rerun byte-identical).
**Scope:** measurement only. `LOGIC_CHANGED: NO` (detectors only CALLED); locked_constants diff empty.

---

## 1. Frozen design (stated before running — DIAGNOSTIC)

Sample: UNIQUE level + FIRST sweep only in exec 2025-06-01 → 2025-11-30
(census `is_first_touch`; re-fires as side counts). Stratified by TF ×
level_family. Direction from census pool (BSL → downside, SSL → upside;
reporting only). Horizons {1,3,5,10} TF bars AFTER the sweep bar
(exclusive), plus one M5-translated secondary (H4→20, H1→5 M5 bars —
~0.4 native bars, shorter lens, labeled secondary). Reference: swept
level extreme in sweep direction (not the sweep close). Numeraires:
ATR(14) Wilder SMA-seeded on the series being read, at the sweep bar;
no R, no invented stops. reclaim_fail = first bar in-window closing
back beyond the level against the sweep close. Truncation strict
(metrics empty + note). Script:
`06_RESEARCH/scripts/htf_post_sweep_path.py` (imports census rows +
`wilder_atr_14`; forks nothing).

## 2. Sample + side counts (DIAGNOSTIC)

| TF | Total events | First-only (measured) | Re-fires (side count) |
|---|---|---|---|
| H4 | 9,139 | 759 | 8,380 |
| H1 | 23,482 | 783 | 22,699 |

35 M5-secondary reads truncated (H4 weekend-grid bars with no M5
counterpart — grid cause documented in §5; native horizons complete on
all 1,542 rows). Zero unresolvable bars.

## 3. H4 first-sweeps by horizon × family (DIAGNOSTIC)

n = 718 session / 37 structural / 4 equal. Columns: +1ATR hit rate /
+2ATR / median MFE_ATR / median MAE_ATR / adverse≥1ATR rate /
reclaim-fail rate / median bars to MFE, MAE.

| H | session hit1 / mfe / mae / adv / rec | structural hit1 / mfe / mae / adv / rec | equal (n=4, tiny) hit1 / rec |
|---|---|---|---|
| 1 | .34 / 0.75 / 0.02 / .06 / .26 | .32 / 0.87 / 0.06 / .00 / .27 | .00 / .50 |
| 3 | .59 / 1.14 / 0.32 / .22 / .47 | .57 / 1.09 / 0.34 / .24 / .43 | .00 / 1.00 |
| 5 | .68 / 1.38 / 0.52 / .33 / .56 | .76 / 1.45 / 0.37 / .30 / .49 | .00 / 1.00 |
| 10 | .76 / 1.75 / 0.93 / .49 / .68 | .86 / 1.97 / 0.84 / .41 / .62 | .50 / 1.00 |
| m5sec | .76 / 3.28 / 2.01 / .64 / .70 | .71 / 3.71 / 2.45 / .60 / .63 | .00 / 1.00 |

## 4. H1 first-sweeps by horizon × family (DIAGNOSTIC)

n = 588 session / 187 structural / 8 equal.

| H | session hit1 / mfe / mae / adv / rec | structural hit1 / mfe / mae / adv / rec | equal (n=8, tiny) hit1 / rec |
|---|---|---|---|
| 1 | .40 / 0.84 / 0.10 / .08 / .31 | .45 / 0.92 / 0.06 / .09 / .29 | .38 / .00 |
| 3 | .57 / 1.12 / 0.32 / .23 / .48 | .57 / 1.16 / 0.34 / .21 / .45 | .50 / .38 |
| 5 | .65 / 1.33 / 0.53 / .33 / .55 | .63 / 1.32 / 0.54 / .35 / .55 | .50 / .38 |
| 10 | .73 / 1.67 / 0.95 / .49 / .68 | .70 / 1.56 / 1.00 / .50 / .66 | .75 / .63 |
| m5sec | .71 / 1.89 / 0.77 / .45 / .56 | .70 / 2.15 / 0.82 / .44 / .57 | .75 / .50 |

## 5. KEY_READ (texture only — DIAGNOSTIC, no edge claim)

Continuation is common AND failure is common, and both grow with
horizon: at 1 bar, ~35–45% reach +1 ATR with adverse rates under 10%
and median extremes arriving in 1 bar; by 10 bars, +1ATR rates reach
~70–86% but adverse≥1ATR reaches ~40–50%, reclaim-fail exceeds 60%,
and median MAE converges to ~1 ATR while median MFE sits ~1.6–2.0.
The modal shape is fast small continuation (median time-to-MFE 1–2
bars at short horizons) followed by return through the level more
often than not — the "stopped early / path continued then reversed"
texture that resonates with (but does not evidence) the wick-tag
death and BE-scratch findings elsewhere. Nothing here is tradeable
as stated: favorable and adverse excursions arrive together, and the
tables contain no cost, no sizing, and no confidence interval that
excludes luck at these horizons.

## 6. STRUCTURAL_VS_SESSION (DIAGNOSTIC, no finding)

H4 structural reads modestly better than session on all three axes at
every horizon (h10: hit+1 86% vs 76%, adverse 41% vs 49%, reclaim 62%
vs 68%) at n = 37 with overlapping Wilson intervals — directional
texture, not a finding. H1 shows no advantage at all (h10 hit+1 70%
vs 73%, adverse 50% vs 49%, reclaim 66% vs 68%, n = 187 vs 588).
Equal-family n (4/8) is too small to read. Conclusion: no consistent
structural edge is demonstrated; the families cannot be separated on
these reads.

## 7. Weekend-grid note (measurement honesty — DIAGNOSTIC)

69 sweep rows sit on weekend bars. The H4 resample grid absorbs weekend
gaps into wide bars (e.g. 2025-06-01T20:00 spans Fri-close action;
verified genuine ticks, not phantom data), while M5 emits no
counterpart bar — hence the 35 M5-secondary truncations (strict rule,
all early-window weekend bars). Native-horizon reads are unaffected
(the bar exists with real ticks, identical to what the product sees).
First sweep 2025-06-01, last 2025-11-30: no pre-window leakage, no
truncation on native horizons.

## 8. Limitations (binding on reuse — DIAGNOSTIC)

- Direction is pool-reported bias, not a signal; reference is the
  swept extreme (intrabar path inside the sweep bar unmeasured).
- M5-secondary horizons are sub-native-bar lenses (~0.4 TF bars).
- Session dominance is constructional (daily levels near price).
- Re-fires excluded from main tables (event-weighted census
  companion holds them).
- Single 6m window, single feed; medians hide wide distributions —
  use the artifact CSV for any deeper cut, with pre-registered rules.

---

**Artifacts:** `06_RESEARCH/scripts/htf_post_sweep_path.py` (new) ·
`06_RESEARCH/results/htf_post_sweep_path/` (`sweeps_path.csv` 1,542
rows, `summary.json` with manifest SHAs + frozen params + tables) ·
tests `04_SRC/tests/test_htf_post_sweep_path.py` (6).
