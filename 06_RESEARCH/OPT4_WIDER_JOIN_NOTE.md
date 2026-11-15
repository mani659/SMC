# OPT-4 WIDER JOIN — MENU PATH ONLY (measurement)

**Date:** 2026-11-08 (3) · **Status:** measure only, `LOGIC_CHANGED: NO`
**Script:** `06_RESEARCH/scripts/opt4_wider_join.py` · **Artifacts:**
`06_RESEARCH/results/confirm_vs_zone_opt4_wider/` (`summary_primary.json`,
`join_primary.csv`, `arming_primary_natural.pkl`, `run.log`)
**Banner:** DIAGNOSTIC PROBE — NOT EDGE — NOT A PERFORMANCE CLAIM. Counts and geometry only —
no PnL, no expectancy, no OPT-2 implementation, no R7 change, no detector retune.

---

## Scope and authority

Resume of the **wider OPT-4 place×R7 join on the MENU path only**, resumed on the sweep-lag
fidelity ruling (2026-11-08 (2), `06_RESEARCH/SWEEP_LAG_FIDELITY_NOTE.md`):
**`ANCHOR_VERDICT: ANCHOR_PATH_SPECIFIC`** — the menu sweep stamp was verified integrity-clean,
deterministic and median-concurrent with the first pierce (deep tail = the frozen R2
close-back definition, not a detection defect); wider measurement could proceed on that stamp.
**The ADAPTER PATH IS EXCLUDED from this join by construction** (no sweep gate, no sweep stamp
in product — sweep-lag N/A as its corruption source); it is never blended into any table below.

Everything else carried over frozen: OPT-B flag stays **`false`**
(`POLICY_OPT_B_FLAG_2026-11-07`); R7 verdicts are **READ** through the REAL frozen
`smc.risk.fill_regime_policy.zone_place_allowed` (never re-implemented, never changed); no
OPT-2; OPT-1/OPT-4 conventions reused verbatim.

## Window (wider, as directed)

Same frozen **primary** window family as the OPT-1/OPT-4 smokes, **without the smoke's
exec-from override** — i.e. the **natural pack-aligned span**:

| field | value |
|---|---|
| load_from | 2025-05-01 |
| **exec_from** | **2025-06-01** |
| **exec_to** | **2025-11-30** |

(Series load printed: M1 208,692 · M5 41,743 · M15 13,915 · H1 3,481 · H4 941 · D1 183 bars —
identical load to the smokes; only the arming span widened.) Arming: 84 armed POIs in 2,979
H1-cadence batches (5,107.9 s), checkpointed to `arming_primary_natural.pkl` (a DIFFERENT
window+cut key than the OPT-4 smoke's `2025-10-01` checkpoint — never cross-blended). 73 first
episodes (frozen harness convention: first R2 sweep per armed POI) — all replayed. Fail-loud
guards on zero armed POIs / zero episodes fired nowhere. No sweep/completion time is invented;
absent fields are reported as absent.

## Method (identical code paths to the OPT-4 smoke — documented frame)

For each menu confirm win (the engine's own OPT-1 stamp):
- `label_at_confirm`, `distance_at_confirm_atr` — the frozen OPT-1 taxonomy
  (ON_WINDOW / LATE displace-side / BEYOND_STOP_SIDE / band = locked `ZONE_REFINEMENT_ATR`).
- **Submit frame = the first closed M5 execution bar at/after `completion_ts`** (the loop
  queues the winner the moment it appears, so live the runner evaluates it on that first closed
  M5 bar). This is the OPT-4 submit *approximation* — NOT a full-stack real submit: risk-side
  blocks (board/news/session/spread) are not modelled; R9-deferred later placements are out of
  scope (documented, as in the smoke).
- `distance_at_place_atr` on that bar — the ONE OPT-1 convention (nearest zone edge, 0 inside,
  in Wilder prefix ATR, period 14 = `PaperConfig.atr_period`).
- `r7_verdict` = `placed` / `SKIP_PLACE_FAR_FROM_ZONE` through the REAL frozen guard.
- S2 context (from the sweep-lag study's definitions): `sweep_close_ts → completion_ts` in raw
  minutes and confirm-TF bars.
- Analysis-only over stamps, **no trades placed**; CSV is byte-stable (fixed fields,
  deterministic episode order) — satisfies the byte-stable requirement (dual-run determinism
  not applicable since no placement engine runs).

## The wider join (full n — 73 episodes → 60 verdict-ed wins / 13 expired)

### Table 1 — label × r7_verdict counts (full wider n, menu only)

| label | n | placed | skip_far | skip rate |
|---|---|---|---|---|
| **ON_WINDOW** | 29 | **27** | 2 | 0.0690 |
| **LATE** | 19 | **1** | **18** | **0.9474** |
| **BEYOND_STOP_SIDE** | 12 | **3** | 9 | 0.7500 |
| (no other labels present; 0 rows missing a label) | | | | |

Verdict mix across all 60: 31 placed / 29 skip-far. Confirm-TF mix: ON_WINDOW M1 19 / M5 6 /
M15 3 / H1 1; LATE M5 8 / M15 5 / M1 4 / H1 2; BEYOND M1 9 / M5 2 / M15 1.

### Table 2 — median confirm vs place distance by label (ATR, place = submit frame)

| label | median confirm ATR | median place ATR | median S2 (confirm bars / raw min) |
|---|---|---|---|
| ON_WINDOW (n=29) | 0.0000 | 0.0000 | 31 / 48 |
| LATE (n=19) | 2.1470 | 2.6079 | 33 / 75 |
| BEYOND_STOP_SIDE (n=12) | 4.2641 | 3.1312 | 79 / 80 |

Geometry notes (counts and distances only, zero improvement/expectancy language):
- ON_WINDOW stays at-zone on both frames (0.0/0.0 medians) — R7 geometry lets ~93% through.
- LATE remains displaced on BOTH frames at the median (2.15 → 2.61 ATR): the submit-frame
  close does **not** typically return toward the zone, so R7's far-from-zone skip catches the
  LATE class at submit at a **94.7%** rate.
- BEYOND_STOP_SIDE sits far beyond the stop side at confirm (4.26 ATR) and is still ~3.13 ATR
  out at place — 75% skipped.
- The **single LATE row that R7 does NOT skip** (`poi b437e757…`, M1 long): 6.26 ATR LATE at
  confirm, but price back to **0.485 ATR** by the place frame → placed. This is exactly the
  OPT-2 interaction the binding design already flagged (an upstream LATE gate would also
  suppress LATE-at-confirm cases whose place-time close is in-band) — n=1 live example in the
  wider table, quoted as geometry, not advocacy.

## Pre-registered hypothesis (report only)

**`LATE_MOSTLY_SKIPPED_BY_R7`** — rule as directed: YES iff LATE n≥10 AND skip-far
rate ≥80%; else NO (n≥10) / INSUFFICIENT (n<10).

| | value |
|---|---|
| LATE n | **19** (above the n≥10 bar) |
| LATE placed | **1** |
| LATE skip_far | **18** |
| skip-far rate | **0.9474** |
| **verdict** | **YES** |

Comparison with the primary-subset smoke (2-month cut, exec-from 2025-10-01): LATE was
n=5 → 0 placed / 5 skipped, verdict INSUFFICIENT. The wider 6-month window moves LATE to
n=19 above the pre-registered bar with the same directional mix (1 placed / 18 skipped) —
the INSUFFICIENT caveat on the smoke is now addressed with the pack-aligned sample.

## Checklist vs the task brief

- Same primary family at minimum: **met** (natural full span of that family, preferred
  pack-aligned window); fail loud on missing data: **no failures**; analysis-only ⇒ byte-stable
  CSV (documented above).
- Reused OPT-4 conventions verbatim (REAL `zone_place_allowed`, first-M5-close-at/after-
  completion submit frame, one distance convention): **met**.
- Tables label × r7_verdict (full n), per-label placed/skips, medians by label: **met**.
- Adapter out of scope, never in a headline: **met** (menu rows only).
- No OPT-2 implementation, no R7/OPT-B behavior change, no detector retune, no PnL/edge
  claims: **met** — zero product edits this task (only `06_RESEARCH/` + `00_LOCKED/` files).

## Caveats (binding on any future citation)

1. Menu path only; adapter excluded per the sweep-lag `ANCHOR_PATH_SPECIFIC` ruling.
2. Submit frame is the OPT-4 approximation (first closed M5 bar at/after completion_ts);
   risk-side blocks not modelled; R9-deferred later placements out of scope.
3. First episode per armed POI only (frozen harness convention; 73/84 armed POIs produced one).
4. `n_other_verdict = 0` — every verdict was `placed` or `SKIP_PLACE_FAR_FROM_ZONE`; no
   conditional/unmodelled verdicts appear in the table.
5. Counts and geometry only — no expectancy, no edge, no PnL, no quality claim; the
   hypothesis verdict is a COUNT comparison, not an outcome claim.
