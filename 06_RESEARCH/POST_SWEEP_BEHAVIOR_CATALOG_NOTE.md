# POST-SWEEP BEHAVIOR CATALOG (DIAGNOSTIC)

> **DIAGNOSTIC — behavior map, not edge.**
> 174 swept episodes read for post-sweep structure: triggers fire on
> every episode, displacement/FVG touch most, discrete CHOCH breaks
> are scarce (15.5%), zones are touched nearly always and violated
> nearly as often. No threshold was changed, no gate follows, no
> production code was touched. No table supports or refutes edge or
> licenses any filter.

**Date:** 2026-10-11 · **Authority:** Lead Architect directive (after A4 scoring close-out).
**POST_SWEEP_STATUS: PASS** (script + artifacts + 6 new tests green; rerun byte-identical).
**LOGIC_CHANGED: NO** (detectors/classifier/triggers only CALLED, under `04_SRC` + research tests).

---

## 1. Method + population splits (frozen)

174 episodes: **(a)** 41 A4-contained rows measured on MATCHED ARMED
bounds (ruling) + **(b)** 133 A2/A3 rows on census bounds; 97
partials held out (identity contested). Trigger completions re-run in
Step-3 scan mode (SeriesState M5 + TriggerRouter + episode POI,
from_bar = sweep, EVERY completion in (sweep, sweep+48]);
**(b)-row firsts reproduce Step-3 exactly (0 mismatches)** —
same evaluation, proven. Displacement/FVG/BOS from accepted LTF rows
(ts in window + zone overlap + thesis direction; no magnitude column
exists — presence only). FVG mitigation = first M5 touch of gap
bounds. CHOCH per bar on growing prefixes (no future info; no MSS
detector exists — stated absent). Zone touch/violation on M5,
(sweep, sweep+100]. Routes/fills joined from Step-4 lifecycle.
Horizons frozen: triggers 48, everything else 100 (both reused).
Script: `06_RESEARCH/scripts/post_sweep_behavior_catalog.py`.

## 2. Behavior table: event → n → % → median bars after sweep (DIAGNOSTIC)

| Behavior (thesis-aligned, post-sweep) | n / 174 | % | Median first (M5 bars) |
|---|---|---|---|
| trigger completion (any) | 174 | 100.0 | 17 |
| displacement | 136 | 78.2 | 8 |
| BOS-tagged displacement | 136 | 78.2 | 8 |
| CHOCH break | 27 | 15.5 | 27 |
| FVG formed | 152 | 87.4 | — (formation offsets not retained; see mitigation) |
| FVG mitigated (touched) | 152 | 87.4 | 8 |
| zone touched | 162 | 93.1 | 2 |
| zone violated (adverse close) | 156 | 89.7 | 0 |
| ever routed / placed / filled | 0 / 0 / 0 | — | — |

Trigger mix over 215 completions: **F 161 / A 32 / B 18 / C 2 / E 2**
(episodes carrying each: F 159 / A 22 / B 18 / C 2 / E 2). Unaligned
LTF rows in-window: 2,235 (side count — direction filter working as
designed, not hidden).

## 3. Flowchart alignment (expected Stage 2→3 vs observed — DIAGNOSTIC)

Expected: sweep → displacement/BOS → FVG → CHOCH → trigger (mostly F)
→ route. Observed: triggers fire on **every** episode (F on 159/174),
displacement on 78%, FVG forms on 87% and is touched on all of those,
zones are touched on 93% (median 2 bars) — but discrete CHOCH breaks
appear on only 15.5%, violations on 89.7% (median offset 0: the next
bar already closes adversely for half the episodes), and **product
routes/fills attach to none of these 174 rows** (all 16 routes + 3
fills sit outside these populations — partials and B rows). In short:
every flowchart ingredient *except a discrete structure break and
product admission* is abundant post-sweep; the machine sees the same
ingredients the expert sequence names, yet converts ~none. No edge
claim follows in either direction — abundance of ingredients is not
evidence of tradeability, and absence of fills is not evidence
against the fragments (nobody priced them).

## 4. Explicit non-goals + NEXT (DIAGNOSTIC)

No threshold/pillar/trigger/SL-TP/risk change was made or is proposed
here; no Mode B; no expectancy/PF/edge language; no auto-promote
filter from any count above; charts skipped by design. **NEXT:
Architect review of post-sweep map** — candidate follow-ons owned by
Architect: FVG fill-through (vs touch) definition, CHOCH-at-scale on
the verify pool, near-vs-far adverse contrasts with pre-registered
rules.

## 5. Verification + limitations (binding — DIAGNOSTIC)

- (b)-row firsts reproduce Step-3 exactly (0 mismatches over 133).
- Rerun byte-identical (CSV + summary).
- 6 tests (alignment, overlap, touch runs, violation strictness both
  sides, mitigation, level parsing, frozen horizons); mid-build they
  caught two real defects (aliased detector lists; first-touch offset
  stuck at 0) — recorded, fixed, rerun.
- FVG formation-offset medians not retained (mitigation offsets
  cover timing); touch/violation reads saturate like all 100-bar
  zone measurements (same family as the decomposed saturation
  finding); single 6m window, single feed.

---

**Artifacts:** `06_RESEARCH/scripts/post_sweep_behavior_catalog.py` ·
`06_RESEARCH/results/post_sweep_behavior_catalog/`
(`behavior_per_episode.csv` 174 rows, `summary.json` with frozen
rules + tables + cross-check) · tests
`04_SRC/tests/test_post_sweep_behavior_catalog.py` (6).
