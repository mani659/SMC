# BRANCH C — E2E REPORT (product path only)

**Verdict: `DEFER_RECOMMENDED`** (factual state: **BLOCKED** — unreachable by
construction, not scarcity and not a tunable).
**`LOGIC_CHANGED: NO`** · **`CODE_CHANGED: NO`**
**C completions: 0** · **C routes: 0** · **C fills: 0**
**Window:** exec 2025-09-01 → 2025-11-30 UTC (M5), warm-up 2025-08-01 — the same
frozen liveness window.
**Authority:** Lead Architect *BRANCH C — E2E engineering (product path only)*.
**Phase 0 pack:** `06_RESEARCH/BRANCH_C_ROOT_CAUSE.md`.

---

## 1. One-line answer

Trigger C cannot fire on the product path at all. It is wired only on the DAY
tier, i.e. confirmed on **H1**, where the frozen structural swing rule
(`N_BAR_HTF = 5`) makes a swing visible only five bars after its fractal, while
C's frozen §24 window allows the signal only **three** bars after the sweep
candle. Every candidate is therefore expired before the trigger can see it —
measured: **361** ending diagonals in the window, **minimum terminal age 5**,
**0** signals from the real `evaluate()` over 1,489 H1 bars × 68 armed D1 POIs.

---

## 2. Funnel — before / after

| Stage | Before (liveness, 2026-11-25) | After (this audit) |
|---|---:|---:|
| D1 POIs armed | 68 | **68 (reproduced)** |
| Ending diagonals observable at H1 | not measured | **361** |
| ...with terminal age ≤ 3 bars (C's window) | not measured | **0** |
| C `evaluate()` completions (superset scan) | 0 | **0** |
| C routes | **0** | **0** |
| C3 rejects | 0 | 0 (nothing reached C3) |
| Placed / fills | **0 / 0** | **0 / 0** |

No re-run of the 3-month menu funnel was performed, and none is claimed. The
arming phase reproduces the audited 68-arm D1 census exactly (`BATCH_ERRORS = 0`,
`MENU_ERRORS = 0`), and the C scan is a deliberate **superset** of what the menu
evaluated: every H1 bar of the window × every armed D1 POI × `from_bar = 0`.

---

## 3. Root cause (single statement)

> **The DAY tier confirms C on H1; H1 structural swings need 5 bars
> (`N_BAR_HTF`) before they exist, but C's §24 expiry allows only 3 bars after
> the sweep candle. `detect_swings` never returns a terminal younger than 5
> bars, so `signal_expired` rejects every ending diagonal before the zone and
> reclaim checks matter.**

The inequality: allowed `bar ≤ terminal + 3`; achievable `bar ≥ terminal + 5`.
This fails on every bar of every window — a longer calendar window cannot help.

Numbers, histograms and the nearest miss: `BRANCH_C_ROOT_CAUSE.md` §4–§5.

---

## 4. Code citations (the whole C path)

| Step | Where | What decided C |
|---|---|---|
| Tier membership | `product_menu_mtf.py:239-254` | C ∈ `_DAY_TRIGGERS`; **excluded** from `_TIER_ADF` ⇒ D1→H1 only |
| Router population | `product_menu_mtf.py:701-712` | DAY router built from the tier tuple, all six triggers |
| Matrix | `compatibility_matrix.py:29-42`, `:52-56` | no forbidden cell; C is PREFERRED at M8; grade affects tie-break only |
| Swing existence | `structural_swing_detector.py:52-59` | fractal at `i` is reported only for `i ≤ len−1−N`; `N = N_BAR_HTF = 5` (`locked_constants.py:167`) |
| Diagonal extraction | `wave_structure.py:248-303` | most-recent alternating 5-chain + throw-under; `terminal_index = w5.index` (the §18 **base candle**) |
| Expiry | `trigger_c_ending_diagonal.py:57-62`; `trigger_expiry.py:50,76` | `signal_expired(terminal, 3, bar)` ⇒ dead for `bar > terminal + 3` |
| Zone context | `trigger_c_ending_diagonal.py:64-77` | terminal within zone ± 0.5×ATR (frozen §13 multiplier) |
| Reclaim | `trigger_c_ending_diagonal.py:79-99` | first close back across the boundary line |
| Downstream | `product_menu_mtf._win` → `pipeline_bridge.candidate_from_route` | never reached: 0 completions ⇒ no route ⇒ no C3 sample, no risk, no placement |

Unit tests do not catch this: `test_trigger_c_ending_diagonal.py` injects
hand-built swings whose `candle_index` is one bar before the evaluated bar — a
state `detect_swings` cannot produce on H1.

---

## 5. Architect options (none implemented)

**Option 1 — ACCEPT the branch as structurally off (recommended for the frozen
book).** Record C as *unreachable on the DAY/H1 wiring*; no code, no constant,
no tier change. Consequence: C stays outside any "all branches fill" claim, and
the expert-card line `TRIGGER_C_LIVE: YES` must be read as "implemented and
routable", not "can fire".

**Option 2 — DEFER C.** Park it until the §24/§27 conflict is ruled. No code.
(This report's `DEFER_RECOMMENDED`.)

**Option 3 — Rule C's expiry from observability.** Effective validity =
3 bars after the pattern becomes detectable (`terminal + N + 3`), preserving
"3 bars of life" while acknowledging the frozen 5-bar confirmation. Changes the
meaning of the locked §24 anchor for C only; needs a dated master-card
supersession. On this window it would have produced **3 completions on
2025-11-25 09:00 UTC**, of which 2 pass C3 (`poi-005144`, `poi-007302`) — those
then face the menu window, risk, session and spread gates, so no fill is
guaranteed.

**Option 4 — Rule a C-specific confirmation TF.** Add M15 or M5 (N=3) to the
DAY tier's confirmation TFs for C only, or give C its own tier. This changes the
frozen menu tier table (locked 2026-10-26) and must state whether the other five
triggers keep H1-only confirmation.

**Option 5 — Retire C from the product path.** If the expert book does not need
ending diagonals, remove C from `_DAY_TRIGGERS` and say so on the card, instead
of carrying a branch that cannot fire. A documentation/claim decision, not an
engineering one.

**Refused on principle:** raising `TRIGGER_C_EXPIRY_EXTRA` to force fills,
lowering `N_BAR_HTF`, loosening C3, widening `ZONE_REFINEMENT_ATR`, or
force-routing a signal the frozen detector cannot emit. Each converts a frozen
contract into a fill.

---

## 6. Why no code changed

1. The root cause is **class (b) unreachable code**, but the repair is not an
   engineering choice: all four repairs (options 3–4 plus the two constant
   changes) alter a **frozen** rule — §24's number, §27's number, or the locked
   tier table.
2. The constant `3` is **not mis-wired** against the locked text: the code
   implements "sweep candle + 3" exactly. The conflict is between two
   independently frozen rules, so changing either is a policy act.
3. The task bans threshold fishing to create fills, and Phase 1 authorises a fix
   only when the failure is a genuine mis-wire. Here the mis-wire is a
   **specification-level** contradiction that requires an Architect ruling.
4. Nothing downstream is implicated: with 0 completions there is no C3 reject,
   no route, no risk/session/spread/placement behaviour to inspect.

No `04_SRC` file, no `locked_constants.py` value, no tier table and no
`parallel_books` / live default was touched. The new harness
(`06_RESEARCH/scripts/branch_c_geometry.py`) is research-only and writes
gitignored artifacts. No test was added because no production behaviour changed;
the existing C unit tests remain green (see §9).

---

## 7. What "LIVE" would require (definition kept honest)

Success was **≥1 C-attributed fill on the product path in the pre-registered
window**. C has 0 completions — not 0 routes after a completion, but no signal
at all — so the chain cannot complete without an Architect ruling on option 3, 4
or 5. `BLOCKED` / `DEFER_RECOMMENDED` is reported rather than a fabricated fill,
and the window was **not** extended to chase one.

---

## 8. Limits

- The superset scan uses `from_bar = 0` and does not model episode one-shot
  consumption, menu-window expiry or the F6 state gate; it is deliberately
  *more* permissive than production, so 0 there implies 0 in production.
- The counterfactual run is instrumentation (`signal_expired` forced `False`);
  its 3 signals were not carried through the menu window, risk or order book.
- Swing availability is derived from the same fractal predicate as
  `detect_swings` and verified against `detect_swings(prefix)` at five sampled
  bars; the full prefix-vs-derived equality on all 1,489 bars was not asserted.
- One window, one instrument (XAUUSD), one tier map. The arithmetic, however, is
  window-independent: it follows from N=5 and expiry=3 alone.
- No expectancy, PF, win-rate or edge statement is made.

---

## 9. Governance

- Deliverables: this report + `06_RESEARCH/BRANCH_C_ROOT_CAUSE.md` + harness
  `06_RESEARCH/scripts/branch_c_geometry.py`; artifacts
  `06_RESEARCH/results/branch_c_geometry/` (gitignored: `summary.json`,
  `c_pattern_census.csv`, `c_would_fire.csv`, `run.log`).
- Run: 117.6 s, 17,840 M5 bars, 124 batches, `BATCH_ERRORS = 0`,
  `MENU_ERRORS = 0`, `D1_ARMS = 68`.
- Full suite re-run green (1,557 passed / 7 skipped); `git diff -- 04_SRC` empty;
  `locked_constants.py` untouched.
- `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`, `CHANGELOG.md` updated.
- **NEXT = Architect accept C verdict → Branch E only.** A and B stay closed
  (DEFER); D and F untouched; no implementation is authorised by this report.
