# POI-LINKED SWEEP RATE — FLOWCHART STEP 2 (READ-ONLY NOTE)

> **DIAGNOSTIC — NOT EDGE.**
> Of 1,093 unique POI episodes, 946 are swept on their directional
> edge in-window. No threshold was changed, no gate follows, no
> production code was touched. No table supports or refutes edge or
> licenses any filter.

**Date:** 2026-10-11 · **Authority:** Lead Architect Step-2 directive (after HTF_POI_CENSUS_NOTE.md).
**POI_SWEEP_STATUS: PASS** (script + artifacts + 6 new tests green; rerun-stable).
**LOGIC_CHANGED: NO** for strategy (detector only CALLED with frozen params, under `04_SRC` + research tests).

---

## 1. Method (one line)

For each Step-1 episode, run the product `sweep_detector.detect_sweep`
(first + re-fires, advancing start_index) against its directional edge
as a `POI_LEVEL` (LONG→SSL on zone_low, SHORT→BSL on zone_high),
searching strictly after first_seen 00:00 UTC through 2025-11-30 on
the POI's own TF bars (primary) and M5 bars (secondary, same rule).

## 2. Sweep rate by group (primary: own TF)

| Group | Episodes | Swept | Rate | Median TF-bars to first sweep | Re-sweeps (side count) |
|---|---|---|---|---|---|
| H4 m1m7 | 75 | 56 | **74.7%** | 21.5 (~3.6 days) | 621 |
| H1 m1m7 | 196 | 163 | **83.2%** | 17.0 (~17 h) | 2,924 |
| M8←H4 | 659 | 605 | **91.8%** | 3.0 (~12 h) | 5,888 |
| M8←D1 | 137 | 106 | **77.4%** | 1.0 (~1 day) | 452 |
| M8←W1 | 26 | 16 | **61.5%** | 1.0 (~1 wk) | 21 |
| **Overall** | **1,093** | **946** | **86.5%** | — | 9,906 |

M5 secondary: 975 swept (89.2%) — at or above primary everywhere,
consistent with finer resolution catching everything the TF scan
catches plus wick noise (reported alongside, never averaged in).

## 3. Reading (descriptive only — DIAGNOSTIC)

**The idea does not die at Step 2.** 86.5% of POI episodes are swept
on their directional edge in-window, most quickly (M8-H4 median 3 H4
bars; H1 median 17 bars). The unswept remainder is 147 episodes
(H4 19 / H1 33 / M8-H4 54 / M8-D1 31 / M8-W1 10) — the only sub-pool
where "never swept" even applies. Step-3 LTF confirmation is therefore
where the funnel's mass must die, not here.

Two honesty notes that keep the rates from being misread as
foresight: (a) zones form where price is (first touch lands on the
arm bar almost universally — lifecycle audit), so early sweeps partly
measure mechanical proximity, not prediction; the rate quantifies
*interaction*, and interaction is what Step 3 needs as input.
(b) Opposite-side sweeps are unmeasured by design (different thesis);
re-sweep counts show edges re-fire constantly (M8-H4: 5,888 re-fires
over 605 swept episodes).

## 4. Verification

- Directional mapping unit-tested both sides + loud on unknown
  (a string/enum normalization bug that would have mis-sided every
  SHORT POI was caught and fixed during the build — recorded here,
  not hidden).
- formed_at bound, window-end bound, first-vs-refire ordering, and
  the SHORT mirror all covered by tests (6 passed).
- Rerun after the fix reproduced 946/975 exactly.
- Suite 985; `locked_constants.py` diff empty; no `04_SRC/smc` change.

## 5. Limitations (binding on Step 3 — DIAGNOSTIC)

- First-seen dating is day-granular (Step-1 rule); sweeps earlier the
  same day count from the day boundary.
- M5 secondary saturates on choppy zones (wick noise) — side column.
- M8-W1 n = 26 (deep history leg, thin by construction).
- No gate, no threshold, no live rule follows.

## 6. Pointer: NEXT = LTF confirmation on swept POIs (Step 3)

`sweeps_per_episode.csv` (1,093 rows with edge, first-sweep ts,
re-sweep counts, M5 secondary) joined to `poi_episodes.csv` is the
input: of swept POIs, how often does LTF confirmation appear — then
entry/outcome only.

---

**Artifacts:** `06_RESEARCH/scripts/poi_linked_sweep_rate.py` (new) ·
`06_RESEARCH/results/poi_linked_sweep_rate/` (`sweeps_per_episode.csv`
1,093 rows, `summary.json` with frozen rules + group tables) · tests
`04_SRC/tests/test_poi_linked_sweep_rate.py` (6).
