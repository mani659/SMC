# A4 IDENTITY CHART CHECKLIST — REVIEW PACK NOTE

> **DIAGNOSTIC — identity review, NOT edge.**
> 56 chart panels so a human can score whether each A4 overlap
> candidate is the same footprint as an armed zone. No auto-scoring
> exists anywhere (by design); no threshold moved; no production code
> touched. No panel supports or refutes edge or licenses any filter.

**Date:** 2026-10-11 · **Authority:** Lead Architect Prompt 1 (after ARMING_FORENSICS_BUCKET_A_NOTE.md).
**A4_CHECKLIST_STATUS: PASS** (56/56 rendered, none skipped; 3 new tests green).
**LOGIC_CHANGED: NO** (constants import only, under `04_SRC` + research tests).

---

## 1. What is in the pack

`06_RESEARCH/results/a4_identity_chart_checklist/` — `charts/` (56
PNGs: **41 contained + 15 earliest-sweep partials**, deterministic
sweep-ts order; all 5 note examples verified inside), `index.csv` (one
row per chart: episode bounds, matched armed bounds, match kind,
first_seen/sweep/arm timestamps, **blank `human_verdict` + `notes`
columns**), `summary.json` (selection rule, window rule, verdict
values). Each panel: M5 candles, census episode zone (blue) vs matched
armed zone (orange, dashed edges), first-sweep bar (red solid), matched
arm bar (purple dashed, only when inside the ±90-bar window), plain
title + caption + footer.

## 2. Rubric — score each row exactly one (humans only)

| Verdict | Meaning (all must hold) |
|---|---|
| **SAME_FOOTPRINT** | Same side, bounds agree within bar noise, same HTF structure on sight — the census row and the armed POI are one footprint under two ids |
| **REFINEMENT_ONLY** | Same thesis/location, but the armed zone is a visibly tighter sub-range (pillar-refined) or a cleanly shifted re-anchoring — related, not identical |
| **DIFFERENT** | Different structures that merely overlap (different swings/origins, opposite sides of a wide band, unrelated highs/lows sharing a range) |
| **UNCLEAR** | Cannot tell from this panel (needs wider window, another TF, or data check — say what in notes) |

Guidance, not rules: containment + same-week arm leans SAME/REFINEMENT
until charts say otherwise; partial overlaps spanning hundreds of
dollars with distant arms lean DIFFERENT; when torn, pick UNCLEAR over
a forced verdict — an honest UNCLEAR beats a confident mislabel.

## 3. How to fill verdicts (then NEXT)

1. Open `index.csv`, fill `human_verdict` per row (exactly one of the
   four values above), add free text in `notes` where useful.
2. Send back tallies per match-kind (contained 41: how many SAME /
   REFINEMENT / DIFFERENT / UNCLEAR; partials 15: same split).
3. Then NEXT = post-sweep behavior catalog (Prompt 2): confirmed
   episodes whose A4 rows score SAME/REFINEMENT rejoin the admitted
   set for behavior measurement; DIFFERENT/UNCLEAR stay out or
   flagged — Architect decides the mapping, not this note.

## 4. Method + limits (binding — DIAGNOSTIC)

Selection frozen (all contained + earliest-15 partials, deduped,
sweep-ts ordered); window = first M5 bar at/after sweep ±90 bars
clamped, arm vline only when inside; house chart language (constants
only). M5 shows context around HTF zones — zone edges exact, sweep
bar exact. Script:
`06_RESEARCH/scripts/a4_identity_chart_checklist.py` (+3 tests:
selection priorities/dedupe/order, window clamps). No gate, no
threshold, no live rule follows.

---

**NEXT_READY: Human scoring → post-sweep behavior catalog.**
