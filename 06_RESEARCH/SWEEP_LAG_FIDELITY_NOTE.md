# SWEEP-LAG FIDELITY NOTE — MENU vs ADAPTER (measure only — anchor before OPT-2)

**Date:** 2026-11-08 (2) · **Status:** measure only, `LOGIC_CHANGED: NO`
**Script:** `06_RESEARCH/scripts/sweep_lag_study.py` · **Artifacts:** `06_RESEARCH/results/sweep_lag/`
(`summary_primary.json`, `episodes_menu.csv`, `episodes_adapter.csv`)
**Banner:** DIAGNOSTIC PROBE — NOT EDGE — NOT A PERFORMANCE CLAIM. Counts and geometry only —
no PnL, no expectancy, no OPT-2, no R7 change, no detector retune. Menu and adapter tables are
**never blended**; no blended LATE% headline anywhere in this note.

**Window family (same as OPT-1/OPT-4 smokes):** frozen **primary** window, exec-from
**2025-10-01** (the `opt_b_confirm_measure` harness's primary subset, unchanged). Arming was
**reused verbatim from the OPT-4 checkpoint**
(`06_RESEARCH/results/confirm_vs_zone_opt4/arming_primary_2025-10-01.pkl`, 36 armed POIs —
same window + same cut, asserted by filename; no cross-window blending). 30 first episodes over
36 armed POIs. No sweep time is invented anywhere; missing data is labelled `DATA_GAP` /
`NO_FULL_R2_IN_WINDOW` (fail loud on structural anomalies).

---

## Definitions (EXACT, frozen)

**`t_pierce` (EXACT, stated in full):** on the POI's detection-TF series, the FIRST closed bar
after `arm_ts` whose extreme pierces the zone edge in the sweep direction **without** the R2
close-back condition — LONG (demand): `bar.low < zone.bottom`; SHORT (supply): `bar.high >
zone.top`. This is the **pierce half of the locked R2 rule** (`smc.dumb.rules.is_sweep`,
verbatim) — not an approximation. Pierce search window: post-`arm_ts` bars **up to and including
the stamp bar's index** (prefix-bounded, no lookahead); the stamp bar always satisfies the
pierce half, so a pierce exists by construction for any stamped episode.

**Sweep stamp bar (EXACT):** the first closed bar post-`arm_ts` satisfying the FULL frozen R2
rule (pierce AND body close back inside). PATH A: the engine's own stamp. PATH B: post-hoc
probe, labelled PROBE.

- **S1 `lag_bars`** = index(stamp bar) − index(`t_pierce`) on the detection TF.
- **S1 `lag_atr`** = |stamp-bar extreme (LONG low / SHORT high) − pierce-bar extreme| / ATR,
  where **ATR = Wilder RMA (`smc.utils.atr.latest_atr`), period 14** (the menu engine's own
  `atr_period` / `PaperConfig.atr_period`), computed **at the stamp bar index over the CLOSED
  PREFIX only** (no lookahead). By construction `lag_atr = 0.0` when the stamp bar IS the
  first pierce.
- **S2 (MENU, OPT-1 fields):** `lag_bars_confirm_tf` = (completion_ts − sweep_close_ts)
  in minutes / the winner's confirmation-TF minutes; `lag_m5_minutes` = raw minutes;
  `lag_atr` = |completion_close − sweep-bar CLOSE| / `atr_at_confirm` (the OPT-1 Wilder
  confirm-TF prefix ATR at the completion bar). Expired / no-completion ⇒ **DATA_GAP**.
- **S3 (place):** already measured by the OPT-4 join — cited below, not re-litigated.
- **Adapter-arm-to-pierce (probe extra):** `arm_to_pierce_bars` = pierce index − arm index
  (the adapter-relevant latency, since adapter confirm anchors to `arm_ts`).

**Integrity (all asserted on every menu episode — zero failures):** the engine's stamp carries
the SAME `poi_id`, the SAME zone bounds, and the SAME `sweep_ts` as the harness attribution;
the OPT-1 stamp's `sweep_ts` equals the episode record on winners; no conflicting sweeps
encountered.

---

## PATH A — MENU (engine's own sweep stamps; `episodes_menu.csv`)

30 episodes (23 won / 7 expired — identical mix to the OPT-1 smoke, as expected on the same
window family).

### S1 — detection lag (n=30)

| stat | `lag_bars` | `lag_atr` |
|---|---|---|
| median | **1.0** | **0.0663** |
| p90 | 99.0 | 0.9261 |
| max | 432 (M15) | 2.7176 (`c01fe677`, lag 10 bars) |

Distribution: `0 bars: 12/30 (40%) · 1 bar: 6/30 (20%) · ≥2 bars: 12/30 (40%)`.

Full lag list (bars): 0 ×12, 1 ×6, 2, 3, 8, 10, then a deep tail **19, 28, 62, 67, 99, 123,
206, 432** — i.e. **18/30 (60%) stamped within 1 detection bar of the first pierce**, while
**8/30 (27%) are ≥19 bars late** (range 19–432).

### S2 — confirm lag (won rows; 7 expired ⇒ DATA_GAP, never invented)

| stat | n | median | p90 | min | max |
|---|---|---|---|---|---|
| `lag_bars_confirm_tf` | 23 | **46.0** | 374.0 | — | — |
| `lag_m5_minutes` (raw) | 23 | **72.0** | 2975.0 | 2.0 | 16,920 (H1 confirm) |
| `lag_atr` | 23 | **1.3245** | 5.0643 | 0.0593 | 24.3963 |

### Reading

The menu stamp is **deterministic and integrity-clean, and mostly concurrent**: at the median
1 detection bar / 0.066 ATR past the first pierce; 60% within 1 bar. The heavy tail is **the
R2 definition itself, not a detection defect**: R2 requires the pierce bar to also CLOSE back
inside the zone. When the first wick beyond the edge *closes beyond* (deep violation), no full
R2 exists yet; close-back can arrive many bars later, on a bar whose extreme is far beyond the
zone edge (e.g. `f5636387` M15 SHORT: first pierce 4,163.248 vs zone top 4,150.448, stamp
432 bars later at 4,181.865). On those episodes the stamp — and therefore ANY confirm/place
measurement anchored to it — is inherently a late-day clock. That is the locked design doing
exactly what it locked; fixing it would be a detector retune (banned).

---

## PATH B — ADAPTER (PROBE only; `episodes_adapter.csv`)

**The adapter has NO sweep gate and NO sweep stamp in product** (frozen design; adapter confirm
metrics anchor to `arm_ts` by construction) — so **sweep-attribution lag is N/A as a corruption
source for this path**. The table below is a PROBE of what a sweep-anchored clock WOULD have
read: first full frozen-R2 bar post-arm, capped at the menu's 20-detection-bar expiry window for
comparability. PROBE rows are never blended with menu rows.

| stat | n | median | p90 |
|---|---|---|---|
| probe `lag_bars` (pierced→full R2) | 10 | **1.0** | 2.0 |
| probe `lag_atr` | 10 | **0.0092** | 0.4952 |
| `arm_to_pierce_bars` | 10 | **1.0** | 10.0 |

Distribution (n=10): `0 bars: 5 · 1 bar: 3 · ≥2 bars: 2` (max lag 8 bars).
Probe outcome mix: **10/36 (27.8%) full R2 within the window · 26/36 (72.2%)
`NO_FULL_R2_IN_WINDOW`**.

### Reading

Where a full R2 exists inside the window it is nearly anchored (median 1 bar, 0.0092 ATR);
`arm→pierce` is also short (median 1 bar). So an adapter-side sweep-anchored clock would not be
"late-stamped" — for **26/36 armed POIs it would not exist at all** within the 20-bar
comparability window (a missing anchor, never a late one, and never invented here). The
adapter's LATE rates quoted in the frozen timing study (`poi_timing_early_late_study.py`,
~34-ATR / ~77% LATE figures) are anchored to `arm_ts` and describe confirm-TF completion
distance — they are **not** sweep-stamp corruption and must not be restated as such.

---

## S3 — place lag: citation only (OPT-4)

From `06_RESEARCH/OPT4_PLACE_JOIN_NOTE.md` (same window family, same stamps; join smoke over
30 episodes → 23 verdict-ed wins): **ON_WINDOW 13 = 12 placed / 1 skip (medians 0.0/0.0 ATR) ·
LATE 5 = 0 placed / 5 skipped (confirm 1.34 → place 2.61 ATR) · BEYOND_STOP_SIDE 5 = 1 placed /
4 skipped (2.58 → 2.20 ATR)**; hypothesis "R7 already filters most LATE" = **INSUFFICIENT**
(LATE n=5 < n≥10). No new place measurement here.

---

## Answers to the four required questions

**1) Is the menu sweep stamp roughly concurrent with the first pierce?**
At the median yes: **1.0 detection bar / 0.0663 ATR**, with 60% of episodes stamped within
1 bar. It is NOT universally concurrent: 40% of stamps are ≥2 bars past the first pierce and
27% are ≥19 bars late, up to 432 bars — deep-violation episodes where the R2 close-back
arrives long after the first wick-pierce. This follows from the frozen R2 definition
(pierce + close-back in one bar), all integrity asserts passed, and the stamping is
deterministic: a definition-driven tail, not a detection defect.

**2) Is adapter lag dominated by late sweep stamp vs late confirm?**
Neither term applies: **the adapter has no sweep stamp in product, so sweep-lag cannot corrupt
its clock** (confirm anchors to `arm_ts` by construction). The probe shows a would-be
sweep-anchored clock would read ~1 bar past the first pierce where a full R2 exists
(10/36), and would not exist at all otherwise (26/36 within the 20-bar cap). Adapter LATE
remains a confirm-TF-distance phenomenon relative to `arm_ts`, not sweep-stamp latency.

**3) This study's recommendation: ANCHOR_VERDICT**
**`ANCHOR_PATH_SPECIFIC`** — PATH A: the sweep stamp is the engine's exact first-full-R2
stamping, integrity-clean and median-concurrent (anchor fit for use on the menu path, with the
documented definition-driven deep tail); PATH B: **no sweep anchor exists in product at all**
— and introducing one there would be detection work, out of scope for OPT-2 under the current
bans. The two paths therefore need separate anchor rulings; a single "the sweep clock is/isn't
corrupt" verdict is not supported.

**4) RESUME_WIDER_OPT4?**
**`YES`** (this study's recommendation for the Architect ruling). Grounds: the sweep stamps the
wider measure would hang on are the same engine stamps verified here — integrity-asserted,
deterministic, median-concurrent, with the tail fully explained by the frozen R2 definition —
so a wider window measures the same locked machinery, not a corrupted clock. Caveat carried
into any wider run: the OPT-1/OPT-4 per-episode exports should be joined with `lag_bars` so
deep-violation (long-tail) episodes can be stratified — their confirm/place clocks are
inherently later **by definition**. No detector retune, no flag change, no timeout-band edits.

---

## Caveats (binding on any future citation)

1. Menu = the engine's own sweep stamps (OPT-1/OPT-4 machinery, default flag OFF; OPT-B flag
   frozen OFF per `POLICY_OPT_B_FLAG_2026-11-07`). Adapter table = PROBE, labelled as such,
   never blended with menu rows; no blended LATE% exists in this study.
2. The pierce rule is the exact pierce half of the locked R2; the stamp rule is the exact full
   frozen R2. No threshold was retuned.
3. ATR = Wilder RMA period 14 at the stated index over the closed prefix only.
4. The `PIERCE_NO_FULL_R2` case (probe runs without a full R2 in the 20-bar window) is an
   honest non-observation, not a lag value.
5. n=30 menu / 36 probe rows on one frozen window family — counts and geometry only; no
   expectancy, edge, hit-rate or improvement claim is made or implied.
