# TP-DISTANCE vs EXIT-CLASS CORRELATION — FOUR WINDOWS

**DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION.**

Authority: Architect 2026-10-21 (optional follow-on to `EXIT_ANATOMY_DIAGNOSTIC_REPORT`).
Windows: **W1** `2024-06-01 → 2024-11-30` n=75 · **W2** `2024-12-01 → 2025-05-31` n=44 · **W3** `2025-06-01 → 2025-11-30` n=58 · **W4** `2025-12-01 → 2026-03-31` n=55 — **232 trades, four non-overlapping 6-month windows.**
Mode: **OBSERVATION ONLY** — `LOGIC_CHANGED: NO` under `04_SRC/smc/**`; `locked_constants.py` diff **EMPTY**; no TP/SL/BE/trail parameter search, no "optimal R" tuning; no expectancy/scale language; no F-kill; windows were not moved; suite NOT_RUN (no shipped code path surfaced).

W2 and W3 are the prior books (W2 = prior Window B, W3 = prior Window A) **reused byte-stable**; W1 and W4 are **new captures** through the same imported post-ZoneDedup composition, each captured twice for determinism (§1).

---

## 0. Question

The prior leg found a two-point association: median `TP_DISTANCE_R` ~0.64R in Window A (TARGET-heavy) vs ~1.00R in Window B (SOFT_STOP-heavy), with `SL_WHILE_TP_VALID = 0` in both books. **Does TP distance in R systematically track exit class across four windows — or was the A/B difference a two-point coincidence?**

---

## 1. Provenance + integrity (checked before any aggregate was read)

| check | W1 | W2 | W3 | W4 |
|---|---|---|---|---|
| book | **new capture** `tp_distance_exit_class/W1/run1` | reused `post_dedup_edge_stability/run1` | reused `zone_dedup_lifecycle/run1` | **new capture** `tp_distance_exit_class/W4/run1` |
| `trades.csv` md5 | `b9044a195cc0…` | `f74eba395165…` | `476884250d60…` | `8254c4688da1…` |
| n | 75 | 44 | 58 | 55 |
| dual-run determinism (run1 vs run2) | **trades.csv + report.json + funnel counts byte-identical** | n/a (reused) | n/a (reused) | **trades.csv + report.json + funnel counts byte-identical** |
| M1 warm-up (≥1 month before exec start) | 2024-05-01 | 2024-11-01 | 2025-05-01 | 2025-11-01 |
| M5 series rebuilt (composition loader, read-only) | 35,721 bars | 34,919 bars | 35,725 bars | 23,381 bars |
| missing series / zero-bar windows (fail-loud) | 0 | 0 | 0 | 0 |
| recomputed MFE/MAE vs stored `trades_enriched*.csv` | n/a (new capture) | 44/44 exact, **0 mismatches** | 58/58 exact, **0 mismatches** | n/a (new capture) |
| tp-touch walk vs frozen honest path (max favourable price) | **0 mismatches** | **0 mismatches** | **0 mismatches** | **0 mismatches** |
| `TP_DISTANCE_R` NA (no `original_sl` or no `tp`) | **0** | **0** | **0** | **0** |
| `SL_WHILE_TP_VALID` (stop exits whose TP was touched earlier) | 0 / 53 | 0 / 28 | 0 / 28 | 0 / 30 |

Every trade in all four windows has both an `original_sl` and a `tp`, so `TP_DISTANCE_R` is complete (232/232) — no NA path was exercised.

The `SL_WHILE_TP_VALID = 0` result is a **coherence** finding, not a missed-profit claim: with a resting TP, a pre-exit TP touch could not exist. It is reported because it confirms the books are internally consistent across the two new captures as well as the two reused ones.

**W4 completeness:** the parquet covers through `2026-04-10T20:59:00+00:00`; W4's window ends `2026-03-31`, so W4 is a **complete** 6-month window. The brief's "last complete 6m in data" fallback was therefore not needed, and the drop-W4 recomputation in §6 is a robustness check rather than the mandated partial-year sensitivity.

**Chronology of the pre-registration:** the script — including the metric definitions, the bucket edges, the per-window criteria and the label rule below — was written at `10:29:44` and the W1/W4 captures started at `10:31` (log file creation). The rule was fixed in code before any new window existed, and was not revised afterwards.

---

## 2. Pre-registration (fixed in code before W1/W4 were captured)

Per trade, identical to `exit_anatomy_diagnostic`: `R_stop = |entry − original_sl|`, `R_tp = |tp − entry|`, **`TP_DISTANCE_R = R_tp / R_stop`** (NA if either missing), `EXIT_CLASS ∈ {TARGET_TP, SOFT_SL_OR_BE, HARD_SL, OTHER}`, `MFE_R`, `hold_bars`.

Distance buckets (fixed): **near** `TP_DISTANCE_R ≤ 0.75` · **mid** `0.75 < d ≤ 1.25` · **far** `d > 1.25`.

Per-window criteria (each evaluated only when its inputs are non-empty; an empty-input criterion is NA and counts as neither satisfied nor violated):

- **C1** near→TARGET: `TARGET rate(near) > TARGET rate(far)`
- **C2** far→SOFT: `SOFT rate(far) > SOFT rate(near)`
- **C3** far→HARD: `HARD rate(far) > HARD rate(near)`
- **C4** class order (supporting only, not required): median `TP_DISTANCE_R` among `TARGET_TP` exits is below the median among `HARD_SL` **and** below the median among `SOFT_SL_OR_BE`

A window **TRACKS** iff C1 **and** (C2 or C3) are satisfied and evaluable; **INVERTS** iff C1 is evaluable and not satisfied; **INCONCLUSIVE** if C1 is not evaluable; **TOO_SMALL** (excluded from the tally) if fewer than 10 trades carry a known distance.

Overall label (exactly one, mechanical): usable = {TRACKS, INVERTS}; usable < 3 → `DATA_GAP_BLOCKING`; TRACKS ≥ 3 → `DISTANCE_TRACKS_EXIT_CLASS`; INVERTS ≥ TRACKS → `DISTANCE_WEAK_OR_NOISE`; otherwise → `DISTANCE_WINDOW_SPECIFIC`.

"Tracks" was defined by the Architect as the same qualitative pattern in ≥3 of 4 windows — nearer targets → higher TARGET share, farther → higher SOFT/HARD — without requiring statistical significance. No p-value, test statistic or confidence interval is computed anywhere in this leg.

---

## 3. Per-window results

| | W1 | W2 | W3 | W4 |
|---|---|---|---|---|
| range | 2024-06 → 2024-11 | 2024-12 → 2025-05 | 2025-06 → 2025-11 | 2025-12 → 2026-03 |
| n | 75 | 44 | 58 | 55 |
| **median `TP_DISTANCE_R`** | 0.868 | **1.000** | 0.643 | 0.584 |
| `TARGET_TP` | 21 (0.280) | 16 (0.364) | **30 (0.517)** | 24 (0.436) |
| `SOFT_SL_OR_BE` | 24 (0.320) | **20 (0.455)** | 9 (0.155) | 2 (0.036) |
| `HARD_SL` | 29 (0.387) | 8 (0.182) | 19 (0.328) | **28 (0.509)** |
| `OTHER` (friday_eod) | 1 (0.013) | 0 | 0 | 1 (0.018) |
| median hold (bars) | 4 | 4.5 | 2 | 4 |
| median `MFE_R` | 0.351 | 0.812 | 0.502 | 0.342 |
| C1 near→TARGET | ✅ | ✅ | ✅ | ✅ |
| C2 far→SOFT | ✅ | ✅ | ✅ | ✅ |
| C3 far→HARD | ✅ | ✅ | ✅ | ✅ |
| C4 class order (supporting) | ✅ | ✅ | ✅ | ✅ |
| **window label** | **TRACKS** | **TRACKS** | **TRACKS** | **TRACKS** |

The two new windows are not clones of the two reused ones: W1 is the only window where **hard stops dominate** (0.387) *and* the TP share is the lowest of the four (0.280); W4 has the highest hard-stop share (0.509) and almost no soft exits (2 of 55).

---

## 4. Within-window distance buckets (the core evidence)

| window · bucket | n | share of window | TARGET rate | SOFT rate | HARD rate |
|---|---|---|---|---|---|
| **W1** · ≤0.75R | 36 | 0.480 | 0.472 | 0.278 | 0.222 |
| W1 · 0.75–1.25R | 11 | 0.147 | 0.364 | 0.364 | 0.273 |
| W1 · >1.25R | 28 | 0.373 | **0.000** | 0.357 | **0.643** |
| **W2** · ≤0.75R | 14 | 0.318 | **0.714** | 0.214 | 0.071 |
| W2 · 0.75–1.25R | 14 | 0.318 | 0.286 | 0.429 | 0.286 |
| W2 · >1.25R | 16 | 0.364 | 0.125 | **0.688** | 0.188 |
| **W3** · ≤0.75R | 31 | 0.535 | **0.677** | 0.097 | 0.226 |
| W3 · 0.75–1.25R | 10 | 0.172 | 0.600 | 0.100 | 0.300 |
| W3 · >1.25R | 17 | 0.293 | 0.176 | 0.294 | **0.529** |
| **W4** · ≤0.75R | 28 | 0.509 | **0.679** | 0.000 | 0.321 |
| W4 · 0.75–1.25R | 9 | 0.164 | 0.222 | 0.111 | 0.667 |
| W4 · >1.25R | 18 | 0.327 | 0.167 | 0.056 | **0.722** |

The gradient is **monotone in every window**: the TARGET rate falls from near to far without exception (0.472→0.000 · 0.714→0.125 · 0.677→0.176 · 0.679→0.167), and the HARD rate rises in every window. W1's far bucket is the sharpest case: 28 trades beyond 1.25R and **not one** reached its target.

---

## 5. Pooled buckets (test 2 — all four windows, 232 trades)

| bucket | n | TARGET rate | SOFT rate | HARD rate | class counts |
|---|---|---|---|---|---|
| ≤ 0.75R | 109 | **0.615** | 0.147 | 0.229 | TP 67 · HARD 25 · SOFT 16 · OTHER 1 |
| 0.75–1.25R | 44 | 0.364 | 0.273 | 0.364 | TP 16 · HARD 16 · SOFT 12 |
| > 1.25R | 79 | **0.101** | 0.342 | 0.544 | HARD 43 · SOFT 27 · TP 8 · OTHER 1 |

Pooled gradient: **0.615 → 0.364 → 0.101** TARGET rate across the three buckets, with HARD rising 0.229 → 0.364 → 0.544. The middle bucket behaves as expected — it is where the exit mix turns over from targets toward stops.

---

## 6. Rank test (test 1) and the sensitivity (test 3) — including one disagreement

**Rank by median `TP_DISTANCE_R` (ascending, nearest first):** W4 (0.584) → W3 (0.643) → W1 (0.868) → W2 (1.000).
**Rank by TARGET share (descending):** W3 (0.517) → W4 (0.436) → W2 (0.364) → W1 (0.280).
**Rank by SOFT share (ascending):** W4 (0.036) → W3 (0.155) → W1 (0.320) → W2 (0.455).

| | all four windows | without W4 |
|---|---|---|
| distance order vs TARGET order | **do not agree** | **do not agree** |
| distance order vs SOFT order | **agree exactly** | **agree exactly** |
| Spearman(distance, TARGET share) | **−0.6** | −0.5 |
| Spearman(distance, SOFT share) | **+1.0** | +1.0 |
| label | `DISTANCE_TRACKS_EXIT_CLASS` | `DISTANCE_TRACKS_EXIT_CLASS` (unchanged, 3/3 TRACKS) |

**This is the honest complication in the leg, and it is recorded rather than smoothed over.** The *within-window* relationship holds in 4 of 4 windows (§4), but the *window-level* summary statistic does not order the windows by TARGET share: W1 has the third-farthest median distance and simultaneously the **lowest** TARGET share of the four, and W2 has the farthest median distance yet the **second-lowest** TARGET share. The rank correlation for distance vs SOFT share is perfect (+1.0) in both the full and the drop-W4 view.

So: **"a nearer target is more often hit" is robust; "a window with a larger median TP distance has a lower TARGET share" is not.** The window median is a lossy summary of placement — it discards the placement *mix*, and the mix matters: W1's near bucket is 48 % of its book but its near-bucket TARGET rate is only 0.472 against 0.68–0.71 in the other three windows, and 37 % of its book sits beyond 1.25R where nothing was hit.

The Spearman values are descriptive rank statistics on four points. No significance is claimed or implied.

---

## 7. Where the windows actually differ: target *source*

`TP_DISTANCE_R` split by the book's own `tp_source` column (structural swing vs ATR fallback) — this is the sharpest cut in the leg:

| window | source | n | exit classes | median `TP_DISTANCE_R` | median hold |
|---|---|---|---|---|---|
| W1 | structural_swing | 48 | TP 19 · HARD 15 · SOFT 14 | **0.449** | 6 |
| W1 | atr_fallback | 27 | HARD 14 · SOFT 10 · TP 2 · OTHER 1 | 2.315 | 3 |
| W2 | structural_swing | 33 | SOFT 15 · TP 12 · HARD 6 | **1.000** | 2 |
| W2 | atr_fallback | 11 | TP 4 · SOFT 5 · HARD 2 | 1.701 | 14 |
| W3 | structural_swing | 43 | TP 27 · HARD 12 · SOFT 4 | **0.508** | 1 |
| W3 | atr_fallback | 15 | HARD 7 · SOFT 5 · TP 3 | 2.175 | 8 |
| W4 | structural_swing | 40 | HARD 18 · TP 22 | **0.469** | 2.5 |
| W4 | atr_fallback | 15 | HARD 10 · SOFT 2 · TP 2 · OTHER 1 | 1.836 | 11 |

**The ATR-fallback targets are essentially the same everywhere** (median 1.70R – 2.32R across all four windows). The window-to-window difference is concentrated in the **structural** targets: 0.449R (W1), 0.508R (W3), 0.469R (W4) — and **1.000R in W2**. The prior leg's "Window B's structural targets sat a median 1.0R out versus 0.51R in A" is therefore confirmed *and* shown to be a **W2-specific condition**, not a general alternation between windows: three of the four windows place structural targets at ~0.45–0.51R.

W2 is also the only window where soft stops dominate (0.455) and the only one whose far bucket is soft-dominated (0.688 soft vs 0.188 hard); W4's far bucket is the mirror image (0.722 hard, 0.056 soft). The *distance* bucket predicts *whether a target is hit*; it does **not** predict *which kind of stop* ends the trade — that is decided by the trailing behaviour, which is exactly what the prior leg found.

---

## 8. Interpretation (pre-registered rule, applied mechanically)

```
usable windows (TRACKS or INVERTS): 4
TRACKS: 4    INVERTS: 0
→ TRACKS >= 3  ⇒  DISTANCE_TRACKS_EXIT_CLASS
```

**`INTERPRETATION: DISTANCE_TRACKS_EXIT_CLASS`** — the same qualitative pattern (nearer targets → higher TARGET share; farther → higher SOFT/HARD) is present in **4 of 4** windows, above the ≥3-of-4 bar set by the Architect. The label survives the drop-W4 sensitivity unchanged (3/3).

### What this label does and does not say

- **It says:** conditioned on the target that was actually placed, its distance in R is a consistent, monotone predictor of which exit class the trade ends in — in every window, with no exceptions, and with a clean pooled gradient (0.615 / 0.364 / 0.101 TARGET rate from near to far). The prior leg's two-point observation was not a coincidence.
- **It does not say:** that distance *causes* the exit mix, that the window-level exit mix is explained by the window's median distance (§6 shows it is not), or that placing targets nearer would improve any outcome. No such rule change is proposed here — it is out of scope and explicitly banned by this leg's brief.
- **The association is partly mechanical, and this is stated plainly:** `TARGET_TP` *is* the event of reaching the target that was placed, and `TP_DISTANCE_R` is the distance to that same target, so a nearer target is a priori easier to reach. The leg's informational content is therefore (i) that the gradient is present and consistent in every window rather than in one or two, and (ii) the negative result in §6 that the window-median does **not** explain the window-level mix — which tempers, rather than strengthens, the prior leg's target-geometry mechanism reading.
- **The 4/4 consistency is also consistent with a single shared construction** (the same composition, the same target-placement rule, four draws from the same process) — four windows are four samples of one process, not four independent replications of a rule.

---

## 9. Limitations

1. **n = 75 / 44 / 58 / 55 (232 total).** Every share is descriptive. No significance test, no confidence interval, no power argument is made or implied.
2. **Four windows are one process, sampled four times.** Agreement across them shows stability of the observed pattern, not independence.
3. **The pooled bucket gradient is partly mechanical** (distance to the target governs the difficulty of reaching it) — see §8.
4. **The window-level rank test disagrees with the within-window result** (§6) and is reported with equal prominence; the label is defined on the within-window pattern only, exactly as pre-registered.
5. **Bar-level resolution.** Intrabar ordering is unknowable from M5 bars: same-bar TP touches are excluded from `SL_WHILE_TP_VALID` and counted separately; `HARD_SL` vs `SOFT_SL_OR_BE` uses the book's realised pnl, not path reconstruction.
6. **`TP_DISTANCE_R` uses the book's own `tp` column** and `original_sl` as the risk denominator — no independent re-derivation of structural targets was attempted (that would be a different study).
7. **Costs sanitized to 0** in all four books; no PnL, expectancy, scale or profitability quantity is computed or discussed in this leg.
8. **Detection-TF anatomy is still not stored on fills**, so exit class cannot be split by the timeframe that produced the POI.
9. **`OTHER` is a single `friday_eod` close** in W1 and W4 (1 trade each) — it is reported, never merged into a stop or target class.
10. **No independent replication of the captures exists.** Determinism is established *within* this leg (run1 vs run2 byte-identical for W1 and W4), which is a reproducibility check, not a third-party reproduction.

---

## Return block

Values below are the exact values stored in `summary.json` (4 dp); the body tables are rounded to 3 dp for reading.

```
TP_DIST_CORR_STATUS: PASS
WINDOWS: W1 2024-06-01 -> 2024-11-30 n=75 · W2 2024-12-01 -> 2025-05-31 n=44 · W3 2025-06-01 -> 2025-11-30 n=58 · W4 2025-12-01 -> 2026-03-31 n=55
MEDIAN_TP_DISTANCE_R: {W1: 0.8676, W2: 1.0, W3: 0.6426, W4: 0.5841}
TARGET_SHARE: {W1: 0.28, W2: 0.3636, W3: 0.5172, W4: 0.4364}
SOFT_SHARE: {W1: 0.32, W2: 0.4545, W3: 0.1552, W4: 0.0364}
HARD_SHARE: {W1: 0.3867, W2: 0.1818, W3: 0.3276, W4: 0.5091}
BUCKET_TARGET_RATES: {leq_0.75: 0.6147, mid_0.75_1.25: 0.3636, gt_1.25: 0.1013}   (pooled, n=232)
INTERPRETATION: DISTANCE_TRACKS_EXIT_CLASS
DETERMINISM_NEW_CAPTURES: PASS
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
SUITE: NOT_RUN
REPORT_PATH: 06_RESEARCH/TP_DISTANCE_EXIT_CLASS_CORRELATION_REPORT.md
NEXT_READY: Architect review
```

**Artefacts:** `06_RESEARCH/results/tp_distance_exit_class/summary.json` (per-window tables, criteria, rank test, pooled buckets, sensitivity, determinism) and `trades_all_windows.csv` (232 per-trade rows: window, class, `R_stop`, `R_tp`, `TP_DISTANCE_R`, distance bucket, `MFE/MAE_R`, `MFE_VS_TP`, `SL_WHILE_TP_VALID`, hold, `tp_source`); new captures under `W1/` and `W4/` (`run1`/`run2`, byte-identical). Script: `06_RESEARCH/scripts/tp_distance_exit_class_correlation.py` (imports the composition and the frozen helpers; re-runnable with `--analyze-only`).

**NEXT_READY (detail):** the correlation question is answered for four windows. The open question it hands back is *not* a rule question but a measurement one — the window median is not a sufficient statistic, so the discriminating quantity is target *placement* (distance relative to the structure that produced it, and the placement mix), which the prior leg flagged as the measurement leg. That is an Architect call; no exit rule, threshold or product line was touched, and none is proposed.
