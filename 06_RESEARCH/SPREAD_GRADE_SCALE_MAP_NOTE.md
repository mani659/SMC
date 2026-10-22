# SPREAD-GRADE SCALE MAP — DATED FIX NOTE (OPTION MAP)

**Date:** 2026-10-11 · **Authority:** Lead Architect directive (Option MAP — recalibrate thresholds to the tag-count scale; no new 0–10 scorer).
**SPREAD_GRADE_STATUS: PASS.** Suite **955 passed** (no count change — existing tests updated, none added); no entry/trigger/pillar logic change; no expectancy claim.
**Scope:** one locked constant + its docs + its pinning tests. Nothing else.

---

## 1. Problem (quant audit M4, confirmed in-tree)

`score_poi` / the confluence score is effectively tag-count scale
(~1..n: `poi/confluence_scorer.py` — `score = tag count + bonus`;
`pipeline_bridge.py` threads it as "tag count"), while
`SPREAD_GRADE_SCORE_THRESHOLDS` used 0–10-style cutoffs (A+: 8, A: 5,
B: 3). A/A+ grades were effectively unreachable in practice, so the
§28.5 spread gate ran a tier stricter than designed on every entry.

## 2. The map (implemented exactly as ruled)

| Grade | Old (superseded 0–10 style) | New (tag-count scale) |
|---|---|---|
| A+ | score ≥ 8 | **score ≥ 3** |
| A | score ≥ 5 | **score ≥ 2** |
| B | score ≥ 3 | **score ≥ 1** |
| C | score < 3 | **score < 1 (else C)** |

Dict order / highest-tier-first evaluation preserved (`A+ → A → B → C`;
`grade_for_score` logic untouched — it reads the constant, so the fix
is data-only). `SPREAD_MAX_ATR` (0.15) and `SPREAD_GRADE_MULTIPLIERS`
(1.5/1.0/0.7/C 0.5) unchanged (no change required, none made).

Behavioral consequence, stated plainly: entries scoring 1–2 tags now
grade B/A (previously C), 3+ tags grade A+ (previously B-or-below).
The gate is looser-or-equal on every score — this restores the
designed tolerance; it is not validated as "better" (no backtest was
run for this note, and none is claimed).

## 3. Files changed (4, all required by the ruling)

1. `04_SRC/smc/config/locked_constants.py` — the one constant
   (old map recorded as superseded in the inline comment).
2. `04_SRC/smc/risk/spread_grading.py` — module + `grade_for_score`
   docstrings updated to the tag-count scale (docs of locked
   behavior; zero logic change).
3. `00_LOCKED/LOCKED_DECISIONS.md` §28.5 — thresholds row amended with
   the dated ruling, the tag-count statement, and the superseded map
   (so the old scale is never restored by accident).
4. Tests pinning the old map (directive-authorized updates, no
   expectation re-valued beyond the ruled map):
   `04_SRC/tests/test_locked_constants.py` (exact-value pin → new map),
   `04_SRC/tests/test_spread_grading.py` (boundaries now 3→A+ / 2→A /
   1→B / 0→C asserted against the real `grade_for_score`; ordering and
   ATR-scaling cases re-pointed at on-scale scores).

## 4. Not changed (bans compliance)

No new quality-score engine; no `SPREAD_MAX_ATR` change; no
entry/trigger/pillar/risk/sizing/fill change (`grade_for_score`'s loop
and every caller are byte-identical in behavior except through the
constant); no expectancy claim; paper runner untouched.

## 5. Verification

- `test_spread_grading.py` + `test_locked_constants.py`: green.
- Full suite: **955 passed**, zero regressions — notably, no other
  test asserted gate behavior at mid scores, so the rescaling broke
  nothing outside its pinning tests.
- `locked_constants.py` diff: **exactly one constant**
  (`SPREAD_GRADE_SCORE_THRESHOLDS`; verified in §6).

## 6. locked_constants diff (changed names only)

```
SPREAD_GRADE_SCORE_THRESHOLDS
```

---

**NEXT_READY: Architect review → next product window or 5y plan.**
