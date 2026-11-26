# BRANCH E — ROOT CAUSE (Phase 0 pack, product path only)

**Status:** COMPLETE 2026-11-26. **`LOGIC_CHANGED: NO`**, no code change.
**Scope:** why Trigger E (double top/bottom + RSI divergence) produced **0
completions / 0 routes / 0 fills** on the product path in the frozen liveness
window.
**Authority:** Lead Architect *BRANCH E — E2E engineering (product path only)*.
**Upstream evidence:** `06_RESEARCH/PRODUCT_BRANCH_LIVENESS_REPORT.md` §1, §3.2
(E = DARK, 0 completions; 68 D1 POIs armed).
**Window (re-used, not re-picked):** exec 2025-09-01 → 2025-11-30 UTC on M5,
warm-up 2025-08-01.

---

## 1. One-line answer

E is wired and eligible on every armed D1 POI, is evaluated on **101,252**
(bar × POI) opportunities, and dies at a single gate: the frozen **§2 EQH
equality tolerance of 4.5 pips (0.45 price units)**. On H1 in this window the
**nearest adjacent pair of structural swing highs is 6.7 pips apart** (median
184 pips), and **0 of 92** adjacent pairs are within tolerance — so no double
top exists to diverge from. The trigger is not broken; the pattern it requires
never occurs at H1 scale under the frozen equality rule.

---

## 2. Admission — where E may evaluate (Phase 0 Q1)

| Fact | Value | Code |
|---|---|---|
| Tier membership | E ∈ `_DAY_TRIGGERS = tuple(TriggerType)` | `04_SRC/smc/orchestration/product_menu_mtf.py:239-254` |
| Excluded elsewhere | `_TIER_ADF = (A, D, F)` — B, C, **E** are not in it | same lines |
| DAY tier confirmation | `MenuTier("DAY", Timeframe.D1, (Timeframe.H1,), …)` | `product_menu_mtf.py:247` |
| Router population | `_router_for(tier)` builds from the tier tuple → DAY router has all six, E included | `product_menu_mtf.py:701-712` |
| Matrix eligibility | No §15 cell is forbidden; E is `structural` at every model and `allowed` is always true | `04_SRC/smc/triggers/compatibility_matrix.py:29-42`, `:52-56` |
| Armed population | **68 D1 POIs** (62 LONG zones, 6 SHORT) | reproduced: `results/branch_e_geometry/summary.json` |

**Conclusion:** admission is not the blocker. E is legally eligible on every
armed D1 POI — **not** case (c).

---

## 3. Method and validation

Harness: `06_RESEARCH/scripts/branch_e_geometry.py` (research-only; every patch
restored in `finally`).

1. **Arming phase** — the same product composition as the Branch C pack
   (`menu_trade_funnel.MenuCycle`, `ProductMenuEngine`, `MultiTFProductRuntime`,
   `BacktestRunner`), full window (17,840 M5 bars, 124 batches). The
   confirmation scan is stubbed for H4/H1/M15 (E is inadmissible there) and runs
   for real on D1. `register_armed` is wrapped read-only. **Fail-loud:** D1 arms
   must equal the liveness **68** — observed 68.
2. **Swing availability** — the H1 view available at each bar is derived from the
   same fractal predicate `detect_swings` uses (`structural_swing_detector.py:59`,
   `range(window, len-window)` ⇒ a fractal at `i` first exists at bar `i+N`,
   `N = N_BAR_HTF = 5`) and **verified against `detect_swings(prefix)`** at five
   sampled bars (fail-loud).
3. **Superset scan** — for every H1 bar of the window and every armed D1 POI the
   **real `RsiDivergenceTrigger.evaluate`** is called with `from_bar = 0`
   (no episode anchor, no menu window). Hints supply the Wilder ATR/RSI prefix
   series and the pre-mirrored candles/swings, so the production code path runs
   unmodified. 101,252 evaluations.
4. **Staged funnel** — the same gates as `_detect` are replicated in production
   order for every (bar, POI), so each death is attributed to one gate, and the
   staged result is compared with the real trigger (must agree).

Run: `BATCH_ERRORS = 0`, `MENU_ERRORS = 0`, 120.5 s, `ANALYSIS_OK`.

---

## 4. The staged funnel (the decisive numbers)

| Stage | Gate (production order) | Pass count |
|---|---|---:|
| S0 | (bar × POI) opportunities | **101,252** |
| S1 | two H1 swing highs exist before the bar | 101,252 |
| S2 | second high **≥** first high | 30,180 |
| **S3** | **§2 EQH equality: `|h2 − h1| ≤ 4.5 pips` (0.45)** | **0** |
| S4 | second high at the POI zone (± 0.5 ATR) | 0 |
| S5 | second high post-arm | 0 |
| S6 | RSI(14) divergence `r2 < r1` | 0 |
| S7 | neckline break at this bar (first) | **0** |

Real `RsiDivergenceTrigger.evaluate` over the same 101,252 opportunities:
**0 signals** — staging and production agree exactly.

### Why S3 is empty (swing spacing, H1, window)

| Measure | Highs | Lows |
|---|---:|---:|
| Structural swings in the window | 93 | 93 |
| Adjacent pairs | 92 | 92 |
| Minimum adjacent gap | **0.67 (6.7 pips)** | 0.137 (1.4 pips) |
| 10th percentile gap | 2.75 (27.5 pips) | 1.83 |
| Median gap | 18.41 (184 pips) | 21.27 |
| Adjacent pairs **≤ 0.45** | **0** | **1** |
| Any-two pairs | 4,278 | 4,278 |
| Any-two pairs ≤ 0.45 | 2 (0.13 and 0.43) | 5 |

The two high pairs inside the tolerance are **not adjacent**, so the trigger's
`highs[-2], highs[-1]` (V1 "two most recent highs") cannot reach them: the
binding constraint is the **equality tolerance**, not the recency simplification.

### Near misses (Phase 0 Q3)

- **179** distinct (POI, peak-pair) combinations have the second high **at the
  zone** across **36 of the 68** D1 POIs — the zone geometry is not the problem.
- **Closest** zone-relevant double top: **13.93 pips** apart (3.1× the 4.5-pip
  tolerance); median **250.3 pips**; 10th percentile 60.2 pips.
- **37** of those 179 already show the required **RSI divergence** (`r2 < r1`).
- **0** of 179 are within the EQH tolerance.

So the pattern fails for one reason only: two H1 swing highs are never close
enough in price to count as "equal" under the frozen §2 rule.

---

## 5. Classification: (a) / (b) / (c) / (d)

| Candidate | Verdict | Basis |
|---|---|---|
| (a) no pattern by design in window | **ACCEPTED** | the trigger is wired, eligible and evaluated 101,252 times; the frozen equality gate removes every candidate |
| (b) RSI / path bug | **Rejected** | RSI series is the production Wilder fold; 37 near-miss pairs reach the divergence test; staged funnel == real trigger; unit tests green |
| (c) tier/matrix excludes E | **Rejected** | E is in `_DAY_TRIGGERS`, all six triggers registered, matrix forbids no cell, 68 POIs armed |
| (d) window too short | **Not evidenced** | the nearest adjacent high pair in three months is 1.5× the tolerance; extending the calendar window is not a remedy that the data supports |

**Intentional, cited rules involved:**

| Rule | Value | Authority |
|---|---|---|
| "Equal high" tolerance | `EQH_EQL_TOLERANCE = 4.5` pips = **0.45 price units** | `locked_constants.py:98`; `utils/pips.py:37,67` |
| E pattern | double top/bottom, second peak at POI, RSI divergence, neckline break | `trigger_e_rsi_divergence.py:14-29, 160-215`; R1 §7 |
| E expiry | `TRIGGER_E_EXPIRY = 15` bars | `locked_constants.py:177` |

The trigger header explicitly cites "within the §2 EQH tolerance" — the reuse is
deliberate and documented, so the constant is **not** mis-wired against its
locked text.

**Secondary defect noted (not the cause).** E reports `completion_index = bar`
(the neckline-break bar) and never self-limits against `expiry_bars`; the router
only ever sees the break bar, so this is inert here, but it means the 15-bar
window is carried, not enforced. Recorded for completeness, no action.

---

## 6. Secondary comparison — research-book E history (not product liveness)

- **R1 pure-tag books** (`06_RESEARCH/R1_PURE_TAG_BOOKS_REPORT.md`, recorded in
  `CHANGELOG.md:252`): the E book produced **183 fills / 646 routes** on MID
  tiers (M5/M15/M1 confirmations; **116 of its 183 fills are M15-based**), while
  the **D1 tier completed B/C/E in 0 of 270 windows even with the full alphabet
  as-coded** ("H1 confirmation on D1 zones never produces them").
- **S3 post-R1 re-baseline:** E **156 fills** in the union book set
  (`CHANGELOG.md:154`).
- These are different trade definitions and different tiers — **not** liveness
  evidence. They are cited only because they show the detector works where the
  confirmation timeframe's price structure is dense enough for two swing highs to
  land within 0.45, and that the DAY/H1 tier produces none.

---

## 7. Phase-1 gate decision

Every E death is class **(a)**: the branch is correctly wired and the pattern is
absent under a frozen rule. Per the task's Phase-1 rule ("only (b)/(c)"), **no
code was changed**; retuning the RSI lookback, the equality tolerance or the
zone band to manufacture a fill is banned.

The one question an Architect could rule on is **scope**, not a value: §2's
4.5-pip tolerance is defined for **liquidity clusters** (EQH/EQL levels); E
reuses it as the definition of an "equal high" for a **double-top pattern**. If
a double top is meant to be a wider structure, the ruling would define a
pattern tolerance (or move E to a shorter confirmation TF) — that changes what E
trades, so it is a policy decision, not a repair. Options are in
`06_RESEARCH/BRANCH_E_E2E_REPORT.md` §5.

**Bans honoured:** no expectancy/PF criterion, no D volume proxy, no
C3/session/TP-age loosening, no RSI/equality/zone retune, no
`locked_constants.py` or `04_SRC` edit, no A/B/C/D/F body touched.

---

## 8. Limits

- The superset scan uses `from_bar = 0` and does not model episode one-shot
  consumption or menu-window expiry; it is deliberately more permissive than
  production, so 0 there implies 0 in production.
- Swing availability is derived and verified at five sampled bars, not all 1,489.
- One window and one instrument. The spacing statistic (0 of 92 adjacent H1 pairs
  within 4.5 pips) is window-specific; the claim is "no pattern in this window",
  not "impossible forever".
- No expectancy, PF, win-rate or edge statement is made.
