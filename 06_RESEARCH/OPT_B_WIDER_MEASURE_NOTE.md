# OPT-B WIDER MENU MEASURE — OFF vs ON, BOTH FROZEN WINDOWS

**Status:** `WIDER_OPT_B_STATUS: PASS` (measurement complete, 2 windows × 2 flags)
**Authority:** Lead Architect "WIDER MENU MEASURE — OPT-B OFF vs ON" (GO)
**Date:** 2026-11-05
**Predecessor:** `06_RESEARCH/OPT_B_CONFIRM_IMPLEMENTATION_NOTE.md` (8-POI sample)

```
LOGIC_CHANGED: NO   — research harness + note only; no product code, no R7/R9,
                      no threshold, no locked constant, no live flag change
SHIPPED CONFIG: config/live_demo.json → enable_opt_b_same_bar_confirm = false
                (unchanged; this study did NOT flip it)
```

> **DIAGNOSTIC — NOT EDGE — NOT A PERFORMANCE CLAIM.** Nothing here measures
> PnL, risk, fills or expectancy. n is a count of confirmation-geometry events,
> not trades.

---

## 1. What was measured (frozen, unchanged composition)

Same `ProductMenuEngine` path and frozen label rules as the OPT-B implementation
note and the POI timing study — no retune of anything:

* **Arming:** frozen `MultiTFProductRuntime` (D1/H4/H1/M15 detection) at its
  new-H1-close cadence, arming POIs into a `PipelineEngine`.
* **Episode:** first closed detection bar after the arm satisfying the locked R2
  sweep rule (one first episode per POI).
* **Replay:** fresh `ProductMenuEngine` per episode per flag, driven through
  `on_execution_bar` with a 600-bar seed prefix (same as the predecessor).
* **Label:** `timing_label` — distance from the confirmation bar close to the
  nearest zone edge vs the locked FR-3/R7 band (`ZONE_REFINEMENT_ATR × ATR`):
  `ON_WINDOW` / `LATE` / `BEYOND_STOP_SIDE`.

**Definitions (pinned so the numbers are auditable):**

| term | definition |
|---|---|
| `n_armed` | POIs armed by the frozen runtime in the window (all menu detection TFs) |
| `n_episodes_probed` | first episodes obtained from those armed POIs |
| `n_with_confirm_or_route` | **union denominator** — episodes where ≥1 flag produced a confirmation (win) before expiry |
| `confirmed` | that flag's own winning episodes (the percentage base) |
| `ON_WINDOW_pct`, `LATE_pct` | share of **that flag's confirmed wins** in each label |
| `expired` | no confirmation before the tier deadline — **excluded** from label percentages, reported separately |

Percentages are therefore over confirmed wins, not over armed POIs. Episodes
that expire under one flag and confirm under the other are counted in each
flag's own base and are visible in the transition matrices (§6).

**Exact ranges + bar counts** (from each `summary_<window>.json`):

| window | load from | exec from | exec to | M1 | M5 | M15 | H1 | H4 | D1 | runtime |
|---|---|---|---|---|---|---|---|---|---|---|
| **W1 primary** | 2025-05-01 | **2025-06-01** | **2025-11-30 23:59** | 208,692 | 41,743 | 13,915 | 3,481 | 941 | 183 | 5,253 s (1.5 h) |
| **W2 secondary** | 2023-11-01 | **2023-12-01** | **2025-05-31 23:59** | 559,016 | 111,831 | 37,280 | 9,327 | 2,523 | 491 | 96,851 s (26.9 h) |

No `--exec-from` override was used (the 8-POI sample *did* use `exec_from =
2025-10-01` — see §7). Both windows are the frozen timing-study windows; data
coverage was verified against `07_DATA/XAUUSD_M1.parquet` (1,768,123 rows,
2021-04-12 → 2026-04-10) and no missing-data warnings occurred.

Arming cost is O(n²) (full-prefix re-batch at every H1 close), which is why W2
(18-month prefix, 3× the H1 bars) took ~18× longer than W1.

---

## 2. W1 — PRIMARY (2025-06-01 → 2025-11-30)

`n_armed 84` · `episodes probed 73` · `n_with_confirm_or_route 64`

| metric | OFF (shipped) | ON (OPT-B) |
|---|---|---|
| confirmed wins | 60 | 60 |
| expired | 13 | 13 |
| **ON_WINDOW** | **29 — 48.33 %** | **29 — 48.33 %** |
| **LATE** | **19 — 31.67 %** | **15 — 25.00 %** |
| BEYOND_STOP_SIDE | 12 (20.00 %) | 16 (26.67 %) |
| median zone distance at confirm | 0.73 ATR | 0.60 ATR |
| p90 zone distance at confirm | 6.26 ATR | 5.02 ATR |
| median LATE distance | 2.15 ATR | 3.93 ATR |
| same-bar wins (ON only) | 0 by construction | **10** |

* Wins gained OFF→ON **4**, wins lost OFF→ON **4** → confirmed count unchanged.
* ON_WINDOW is **identical** (29/60); the LATE share falls 6.67 pp, but
  BEYOND_STOP_SIDE rises by 4 and the LATE survivors are *further* out
  (3.93 vs 2.15 ATR).

## 3. W2 — SECONDARY (2023-12-01 → 2025-05-31)

`n_armed 216` · `episodes probed 190` · `n_with_confirm_or_route 169`

| metric | OFF (shipped) | ON (OPT-B) |
|---|---|---|
| confirmed wins | 152 | 150 |
| expired | 37 | 40 |
| no winner before deadline | 1 | 0 |
| **ON_WINDOW** | **73 — 48.03 %** | **67 — 44.67 %** |
| **LATE** | **44 — 28.95 %** | **37 — 24.67 %** |
| BEYOND_STOP_SIDE | 35 (23.03 %) | 46 (30.67 %) |
| median zone distance at confirm | 0.59 ATR | 0.60 ATR |
| p90 zone distance at confirm | 7.47 ATR | 6.62 ATR |
| median LATE distance | 2.91 ATR | 1.94 ATR |
| same-bar wins (ON only) | 0 by construction | **29** |

* Wins gained OFF→ON **17**, lost **19** → confirmed count **−2**.
* ON_WINDOW **falls 3.36 pp**; LATE falls 4.28 pp; BEYOND_STOP_SIDE rises by 11.

## 4. Combined (count-weighted totals — not an average of percentages)

| metric | OFF | ON | Δ |
|---|---|---|---|
| confirmed wins | 212 | 210 | −2 |
| expired | 50 | 53 | +3 |
| **ON_WINDOW** | **102 — 48.11 %** | **96 — 45.71 %** | **−2.40 pp** |
| **LATE** | **63 — 29.72 %** | **52 — 24.76 %** | **−4.96 pp** |
| BEYOND_STOP_SIDE | 47 — 22.17 % | 62 — 29.52 % | +7.35 pp |
| wins gained / lost | — | 21 / 23 | −2 |
| same-bar wins (ON only) | — | **39** | — |

Across 263 episodes (526 flag-episodes) the ON_WINDOW share **does not improve** and the
confirmed count is slightly lower. The LATE share does fall consistently in
both windows — but see §6 for where those wins actually go.

---

## 5. Per-confirmation-TF win counts (context, not a claim)

W1 OFF: M1 32 won (19 ON_WINDOW), M5 16 (6), M15 9 (3), H1 3 (1).
W1 ON: M1 31 (16), M5 17 (8), M15 8 (3), H1 4 (2).
W2 OFF: M1 91 won (51 ON_WINDOW), M5 43 (14), M15 8 (2), H1 10 (6).
W2 ON: M1 87 (45), M5 40 (14), M15 11 (3), H1 12 (5).

The M1 tier carries most wins; OPT-B neither adds nor removes a tier.

---

## 6. What actually happens to the wins (transition matrix)

Paired per episode, OFF label → ON label (expired episodes shown as EXPIRED):

**W1 (73 episodes)**

| OFF \ ON | ON_WINDOW | LATE | BEYOND | EXPIRED |
|---|---|---|---|---|
| ON_WINDOW (29) | 20 | 2 | 5 | 2 |
| LATE (19) | 6 | 10 | 2 | 1 |
| BEYOND (12) | 1 | 1 | 9 | 1 |
| EXPIRED (13) | 2 | 2 | 0 | 9 |

**W2 (190 episodes)**

| OFF \ ON | ON_WINDOW | LATE | BEYOND | EXPIRED |
|---|---|---|---|---|
| ON_WINDOW (73) | 54 | 2 | 8 | 9 |
| LATE (44) | 5 | 32 | 4 | 3 |
| BEYOND (35) | 2 | 0 | 26 | 7 |
| EXPIRED (37) | 6 | 3 | 8 | 20 |

Rows and columns each total 190 episodes; every pairing class is accounted for.

**Reading it honestly:** of the 63 OFF LATE wins, only **11 (17 %)** become
ON_WINDOW under OPT-B; 42 stay LATE, 6 become BEYOND_STOP_SIDE and 4 expire.
Meanwhile ON loses **13 ON_WINDOW wins to BEYOND_STOP_SIDE**, **11 to expiry**
and 4 to LATE. Net ON_WINDOW = −6 across the combined 263 episodes.

**Same-bar class is not inherently good:** of the 39 same-bar wins ON creates,
only 16 (41 %) are ON_WINDOW; 16 are BEYOND_STOP_SIDE and 7 are LATE.
W1: 5 / 3 / 2. W2: 11 / 13 / 5.

---

## 7. vs the original 8-POI sample

The predecessor note reported, on the *same* primary window definition but with
a smoke override `--exec-from 2025-10-01` (i.e. one month, not six):

| | OFF | ON |
|---|---|---|
| confirmed wins | 6 | 6 |
| ON_WINDOW | 5 — **83.33 %** | 6 — **100 %** |
| LATE | 1 — 16.67 % | 0 — 0 % |
| expired | 2 | 2 |

**That result does not replicate at window scale.** With 60 (W1) and 152/150
(W2) confirmed wins instead of 6:

* ON_WINDOW: 83.33 % → 100 % becomes **48.33 % → 48.33 %** (W1) and
  **48.03 % → 44.67 %** (W2).
* LATE does not reach 0 %; it goes 31.67 % → 25.00 % and 28.95 % → 24.67 %.

The 8-POI sample was 6 wins on one month of data — a single LATE episode
flipping moves it 16.7 pp. It should not be used to size the effect, and the
"100 % ON_WINDOW" figure should be retired from decision-making.

---

## 8. R7 observability — not observable, not changed

`r7_observable: false` is pinned in both summaries. R7 is a **PLACE** guard on
the routed candidate; this harness places nothing (confirmation geometry only),
so R7 skips cannot be counted here. OPT-B does not modify R7, and **no R7
claim is made in either direction** — neither "fixed" nor "worsened". Measuring
R7 requires the placement path, which is a different harness.

## 9. Adapter / P1 path — explicitly OUT OF SCOPE

OPT-B only changes the product menu path's confirmation anchor. The adapter/P1
path (`PipelineAdapter.generate_candidates`) has no sweep gate and was already
as-of-complete; it is unaffected by construction and was **not re-run**. The
876-event adapter timing study's 77 % LATE is **not** evidence about this change
and is excluded from every table above.

---

## 10. Honesty / caveats

1. **Confirmation geometry only.** No placement, fills, R7/R9, risk or PnL.
2. **First episode per POI only**; later episodes after expiry are out of scope.
3. **Bounded seed (600 bars)** per confirmation stream — no long-history replay.
4. **Percentages are over confirmed wins**, so a flag that confirms fewer wins
   can look "better" on a percentage; the confirmed counts are reported beside
   every percentage for that reason.
5. **No stability claim from the 8-POI sample** — and equally, 212 vs 210
   confirmed wins across two windows is not a trade sample; it cannot support
   an edge or expectancy claim.
6. **W2 is a single 18-month window**, not independent evidence from W1's
   regime; the two windows are adjacent and share 2025 data conventions.
7. Runtime: W2's 26.9 h is a harness-cost artefact (O(n²) arming), not a
   correctness signal; both windows wrote complete summaries with zero errors.

---

## 11. Recommendation to the Architect

**KEEP THE LIVE FLAG OFF (`enable_opt_b_same_bar_confirm: false`).**

Grounds, in order of weight:

1. The headline effect from the small sample **does not reproduce**: ON_WINDOW
   48.11 % → 45.71 % combined (flat in W1, −3.36 pp in W2).
2. Confirmed wins do **not** increase: 212 → 210, with 2 more expiries.
3. The LATE reduction (−4.96 pp) is real but **misleading in isolation**: only
   17 % of OFF LATE wins become ON_WINDOW; the rest stay LATE or move to
   BEYOND_STOP_SIDE / expiry, and ON separately loses 13 ON_WINDOW wins to
   BEYOND_STOP_SIDE.
4. The structurally new same-bar class is **not** a quality win: 41 % of those
   39 wins are already beyond the stop side.

If the Architect still wants to explore OPT-B, the useful next measurement is
**placement-aware** (does the same-bar confirmation class survive R7 and reach
a valid entry?), not a wider repeat of this geometry harness. This study cannot
answer that, and the flag should stay OFF until something can.

**NEXT = Architect decision only. No live flag flip is part of this pass.**

---

## 12. Reproduce

```
PYTHONPATH=04_SRC python -X utf8 06_RESEARCH/scripts/opt_b_confirm_wider_measure.py --window primary
PYTHONPATH=04_SRC python -X utf8 06_RESEARCH/scripts/opt_b_confirm_wider_measure.py --window secondary
PYTHONPATH=04_SRC python -X utf8 06_RESEARCH/scripts/opt_b_confirm_wider_measure.py --compose-only
```

Artifacts: `06_RESEARCH/results/opt_b_confirm_wider/`
(`summary_primary.json`, `summary_secondary.json`, `summary_both_windows.json`,
`episodes_{primary,secondary}_{off,on}.csv`, `{primary,secondary}_run.log`).
The harness imports the frozen functions from `opt_b_confirm_measure.py`
(`load_series`, `arm_pois`, `first_episodes`, `measure_episode`, `summarise`)
rather than re-implementing them, so labels and composition stay frozen.
