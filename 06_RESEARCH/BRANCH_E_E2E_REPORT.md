# BRANCH E — E2E REPORT (product path only)

**Verdict: `DARK_IN_WINDOW`** (class (a): no qualifying pattern under a frozen
rule — not a bug, not a mis-wire, not arm starvation).
**`LOGIC_CHANGED: NO`** · **`CODE_CHANGED: NO`**
**E completions: 0** · **E routes: 0** · **E fills: 0**
**Window:** exec 2025-09-01 → 2025-11-30 UTC (M5), warm-up 2025-08-01 — the same
frozen liveness window.
**Authority:** Lead Architect *BRANCH E — E2E engineering (product path only)*.
**Phase 0 pack:** `06_RESEARCH/BRANCH_E_ROOT_CAUSE.md`.

---

## 1. One-line answer

Trigger E is correctly admitted and evaluated, and it never completes because the
frozen §2 "equal high" tolerance (**4.5 pips = 0.45 price units**) is far tighter
than H1 structure: across three months the nearest adjacent pair of structural
H1 swing highs is **6.7 pips** apart and **0 of 92** adjacent pairs are within
tolerance. Of 101,252 (bar × POI) evaluations the funnel reaches "RSI divergence
at the zone" only in near-miss rows, and never reaches the equality gate — so the
branch is dark for **pattern absence**, not for wiring.

---

## 2. Funnel — before / after

| Stage | Before (liveness, 2026-11-25) | After (this audit) |
|---|---:|---:|
| D1 POIs armed | 68 | **68 (reproduced)** |
| (bar × POI) E opportunities scanned | not measured | **101,252** |
| second high ≥ first high | not measured | 30,180 |
| **within §2 EQH tolerance (0.45)** | not measured | **0** |
| second high at the POI zone | not measured | 0 |
| RSI divergence present | not measured | 0 |
| E completions (superset scan, real trigger) | **0** | **0** |
| E routes | **0** | **0** |
| C3 rejects | 0 | 0 (nothing reached C3) |
| Placed / fills | **0 / 0** | **0 / 0** |

No funnel re-run of the 3-month product path was performed and none is claimed.
The arming phase reproduces the audited 68-arm D1 census exactly
(`BATCH_ERRORS = 0`, `MENU_ERRORS = 0`); the E scan is a deliberate **superset** of
the menu's coverage (every H1 bar × every armed D1 POI, `from_bar = 0`), and the
staged funnel agrees with the real trigger to the signal.

---

## 3. Root cause (single statement)

> **E requires two structural H1 swing highs to be "equal" within the frozen §2
> EQH tolerance (0.45 price units). H1 swing highs in this window are never that
> close — the tightest adjacent pair is 0.67 — so the double-top pattern does not
> exist and no candidate can reach the zone, RSI or neckline gates.**

Supporting numbers: `BRANCH_E_ROOT_CAUSE.md` §4 (staged funnel, swing spacing,
179 near-miss pairs).

---

## 4. Code citations (the whole E path)

| Step | Where | What decided E |
|---|---|---|
| Tier membership | `product_menu_mtf.py:239-254` | E ∈ `_DAY_TRIGGERS`; **excluded** from `_TIER_ADF` ⇒ D1→H1 only |
| Router population | `product_menu_mtf.py:701-712` | DAY router built from the tier tuple, all six triggers |
| Matrix | `compatibility_matrix.py:29-42`, `:52-56` | no forbidden cell; E `structural` at every model; grade = same-bar tie-break only |
| Pattern | `trigger_e_rsi_divergence.py:160-215` (`_detect`) | two most recent highs, `h2 ≥ h1`, **EQH tolerance**, second peak at the zone ± 0.5 ATR, RSI(14) divergence, first neckline break |
| Equality rule | `utils/pips.py:67` → `locked_constants.py:98` (`EQH_EQL_TOLERANCE = 4.5` pips; `XAUUSD_PIP_SIZE = 0.1`) | 0.45 price units |
| RSI | `utils/rsi.py` (Wilder, MT5 `iRSI`) | indicator parameter, not the blocker (37 near-miss rows already diverge) |
| Expiry | `locked_constants.py:177` (`TRIGGER_E_EXPIRY = 15`) | carried on the signal; the trigger emits only on the break bar, so it is inert here |
| Downstream | `_win` → `candidate_from_route` | never reached: 0 completions ⇒ no route ⇒ no C3 sample, no risk, no placement |

---

## 5. Architect options (none implemented)

**Option 1 — ACCEPT E as DARK on the DAY tier (recommended for the frozen book).**
Record E as wired, eligible and pattern-starved; no code, no constant, no tier
change. Consequence: E stays outside any "all branches fill" claim.

**Option 2 — DEFER E.** Park it with A/B/C until the tier question is ruled.

**Option 3 — Rule what "equal high" means for a pattern.** §2's 4.5-pip tolerance
is a **liquidity-cluster** definition; E reuses it as the definition of a
double-top peak. A dated ruling could define a pattern-specific equality (or a
fraction of ATR), which changes what E trades. Not implemented; needs a master-card
supersession and its own measurement contract.

**Option 4 — Rule a shorter confirmation timeframe for E.** E is only confirmable
on D1→H1 today; the R1 pure-tag books show E firing on M5/M15/M1 confirmations
(E book **183 fills**, 116 M15-based) and **0 of 270** windows on the D1 tier.
Adding a shorter-N confirmation TF to the DAY tier is a frozen tier-table change
(locked 2026-10-26) and must state whether the other five triggers keep H1 only.

**Option 5 — Retire E from the product path.** If the book does not need RSI
divergence on the daily tier, remove it from `_DAY_TRIGGERS` and say so on the
card.

**Refused on principle:** widening `EQH_EQL_TOLERANCE`, shortening the RSI period,
widening the zone band, loosening C3/session/TP-age, or force-routing a signal the
frozen detector does not emit. Each converts a frozen contract into a fill.

---

## 6. Why no code changed

1. The branch is correctly wired: E is admitted on the DAY tier, matrix-eligible on
   every model, registered in the router, and evaluated on 101,252 opportunities.
2. The failure is a **frozen tolerance meeting price structure**, class (a). The
   constant is not mis-wired against its locked text, and the trigger's reuse is
   documented in its own header.
3. There is no (b): RSI is the production Wilder fold, 37 near-miss pairs already
   satisfy the divergence condition, and the staged funnel reproduces the real
   trigger exactly (0 = 0).
4. There is no (c): no flag, allow-list or tier setting excludes E from the armed
   population.
5. Phase 1 authorises a fix only for (b)/(c); retuning RSI or the equality
   tolerance to manufacture a fill is explicitly banned.

No `04_SRC` file, no `locked_constants.py` value, no tier table and no
`parallel_books` / live default was touched. The new harness
(`06_RESEARCH/scripts/branch_e_geometry.py`) is research-only and writes
gitignored artifacts. No test was added because no production behaviour changed.

---

## 7. What "LIVE" would require (definition kept honest)

Success was **≥1 E-attributed fill on the product path in the pre-registered
window**. E has 0 completions across a superset of the menu's coverage, so the
chain cannot complete without a ruling on option 3, 4 or 5. The window was **not**
extended to chase a fill, and no threshold was moved.

---

## 8. Limits

- Superset scan (`from_bar = 0`): more permissive than production, so 0 there
  implies 0 in production; it does not model episode consumption or window expiry.
- Swing availability derived from the production fractal predicate and verified at
  five sampled bars, not all 1,489.
- The spacing statistic (0 of 92 adjacent pairs ≤ 4.5 pips) is window-specific.
  The verdict is `DARK_IN_WINDOW`; "structurally impossible forever" is **not**
  claimed.
- The 179 near-miss rows are deduplicated per (POI, peak pair); they are a
  diagnostic, not a routed population.
- No expectancy, PF, win-rate or edge statement is made.

---

## 9. Governance

- Deliverables: this report + `06_RESEARCH/BRANCH_E_ROOT_CAUSE.md` + harness
  `06_RESEARCH/scripts/branch_e_geometry.py`; artifacts
  `06_RESEARCH/results/branch_e_geometry/` (gitignored: `summary.json`,
  `e_gate_funnel.csv`, `e_near_miss.csv`, `run.log`).
- Run: 120.5 s, 17,840 M5 bars, 124 batches, `BATCH_ERRORS = 0`,
  `MENU_ERRORS = 0`, `D1_ARMS = 68`, `CHECKED_BAR_POI = 101,252`.
- Full suite re-run green (1,557 passed / 7 skipped); `git diff -- 04_SRC` empty;
  `locked_constants.py` untouched.
- `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`, `CHANGELOG.md` updated.
- **NEXT = Architect accept E verdict → formal D OFF note + full-book engineering
  scorecard.** A/B/C stay DEFER, D stays OFF (volume), F untouched; no
  implementation is authorised by this report.
