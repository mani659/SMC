# BRANCH C — ROOT CAUSE (Phase 0 pack, product path only)

**Status:** COMPLETE 2026-11-26. **`LOGIC_CHANGED: NO`**, no code change.
**Scope:** why Trigger C (Ending Diagonal) produced **0 completions / 0 routes /
0 fills** on the product path in the frozen liveness window.
**Authority:** Lead Architect *BRANCH C — E2E engineering (product path only)*.
**Upstream evidence:** `06_RESEARCH/PRODUCT_BRANCH_LIVENESS_REPORT.md` §1, §3.2
(C = DARK, 0 completions; 68 D1 POIs armed).
**Window (re-used, not re-picked):** exec 2025-09-01 → 2025-11-30 UTC on M5,
warm-up 2025-08-01.

---

## 1. One-line answer

Trigger C is **unreachable by construction on the product path**: it is evaluated
only on the DAY tier, i.e. on the **H1** confirmation series, where a structural
swing exists only **5 bars** (`N_BAR_HTF`) after its fractal, while C's frozen
§24 window allows the signal only **3 bars** after the sweep candle. A terminal
younger than 5 H1 bars can never appear in the swing list, so `signal_expired`
rejects **every** candidate before the zone/reclaim logic is even interesting.
This is arithmetic, not scarcity: the window contains **361** ending-diagonal
observations, the minimum terminal age is **5**, and the real trigger returns
**0** signals across **1,489 H1 bars × 68 armed D1 POIs**.

---

## 2. Admission — which tiers/TFs may emit C (Phase 0 Q1)

| Fact | Value | Code |
|---|---|---|
| Tier membership | C is in `_DAY_TRIGGERS = tuple(TriggerType)` | `04_SRC/smc/orchestration/product_menu_mtf.py:239-254` |
| C excluded from other tiers | `_TIER_ADF = (A, D, F)` — B, C, E are **not** in it | same lines |
| DAY tier confirmation | `MenuTier("DAY", Timeframe.D1, (Timeframe.H1,), …)` | `product_menu_mtf.py:247` |
| Router population | `_router_for(tier)` filters `default_triggers()` by the tier tuple → the DAY router has all six, C included | `product_menu_mtf.py:701-712` |
| Matrix eligibility | §15 defines **no** incompatible cell; C is `preferred` at M8 and `structural`/`uncommon` elsewhere, and `allowed` is always `True` | `04_SRC/smc/triggers/compatibility_matrix.py:29-42`, `:52-56` |
| Armed population | **68 D1 POIs** (62 LONG zones, 6 SHORT) | reproduced: `results/branch_c_geometry/summary.json` `D1_ARMS` |

**Conclusion:** C is legally admissible on every armed D1 POI. Admission is not
the blocker — this is **not** case (c).

---

## 3. Method and validation

Harness: `06_RESEARCH/scripts/branch_c_geometry.py` (research-only, no
production edit; every patch restored in `finally`).

1. **Arming phase** — the identical product composition
   (`menu_trade_funnel.MenuCycle`, `ProductMenuEngine`, `MultiTFProductRuntime`,
   `BacktestRunner`) driven over the full window (17,840 M5 bars, 124 batches).
   The confirmation *scan* is stubbed for H4/H1/M15 (C is inadmissible there) and
   runs for real on D1, so arming, sweeps, episode lifecycle and §5 state are the
   production behaviour. `register_armed` is wrapped read-only to record the arm
   census. **Fail-loud:** D1 arms must equal the liveness **68** — observed 68.
2. **Swing availability** — `detect_swings` loops
   `range(window, len(candles) - window)`
   (`04_SRC/smc/detection/structural_swing_detector.py:59`), so a fractal at
   index `i` first exists when bar ≥ `i + N`. The script derives that
   availability from the same fractal predicate and **verifies it against
   `detect_swings(prefix)` at five sampled bars** (fail-loud).
3. **Superset C scan** — for **every H1 bar of the window** and **every armed D1
   POI**, the *real* `EndingDiagonalTrigger.evaluate` is called with
   `from_bar = 0` (no episode anchor, no menu window, no consumption). This is a
   strict superset of the bars the menu evaluated. `find_ending_diagonal` is
   memoised per (bar, direction) and the Wilder ATR prefix series is passed via
   `hints`; the hint identity (`atr_values[bar-1] == latest_atr(h1[:bar])`) is
   spot-checked (fail-loud).
4. **Expiry counterfactual** — the same scan with `signal_expired` forced
   `False`, to measure how late the pattern actually becomes observable.
   Instrumentation only; no change is proposed.

Run: `BATCH_ERRORS = 0`, `MENU_ERRORS = 0`, 117.6 s, `ANALYSIS_OK`.

---

## 4. The arithmetic (the decisive evidence)

Frozen rules involved:

| Rule | Value | Authority |
|---|---|---|
| H1 structural swing confirmation | `N_BAR_HTF = 5` bars each side | `locked_constants.py:167`; `detect_swings` `range(window, len-window)` |
| C validity window | `TRIGGER_C_EXPIRY_EXTRA = 3` — "sweep candle + 3" | `locked_constants.py:175`; `trigger_expiry.py:50` |
| Expiry test | dead when `current_bar > terminal_index + 3` | `trigger_expiry.py:76` |
| C's call | `signal_expired(diagonal.terminal_index, 3, bar)` | `trigger_c_ending_diagonal.py:57-62` |

Because `detect_swings` needs `N` bars to the **right** of a fractal before the
swing exists, the freshest swing in the list at bar `b` has
`candle_index ≤ b − 5`. C's expiry admits only `bar ≤ terminal_index + 3`.
Therefore **`b ≤ (b − 5) + 3 = b − 2` is required — false for every `b`.** The
branch cannot fire on H1 in *any* window, for *any* POI, with *any* price path.

For a swing **low** the §18 base candle may be one bar *before* the fractal
(`base_candle.py:61-72`), which only makes the terminal older (age 6).

Measured on the frozen window:

| Metric | Value |
|---|---:|
| Ending-diagonal observations (H1 bars, either direction) | **361** (235 LONG / 126 SHORT; 247 converging) |
| Distinct H1 bars carrying a diagonal | 361 |
| **Minimum terminal age at observation** | **5 bars** |
| 10th percentile / median / max terminal age | 6 / 12 / 37 bars |
| Observations with age ≤ 3 (inside the frozen window) | **0** |
| Real `evaluate()` completions (superset scan) | **0** |
| Counterfactual completions with expiry ignored | **3** (all one diagonal, one bar) |
| Counterfactual minimum terminal age | **6 bars** |

Age histogram head: `5:20, 6:25, 7:25, 8:25, 9:25, 10:25, 11:25, 12:21 …` — the
distribution starts *above* the allowed 3 and never reaches it.

---

## 5. The nearest miss (what the window actually costs)

The three counterfactual signals are one diagonal, one bar:

| Fact | Value |
|---|---|
| Completion bar | **2025-11-25 09:00 UTC** (H1 bar 1891) |
| Terminal index / age | 1885 / **6 bars** (3 bars past the last legal bar 1888) |
| Zone direction | SHORT (up-diagonal throw-over) |
| POIs | `poi-004989`, `poi-005144`, `poi-007302` |
| Entry / stop | 4121.840 / 4155.585 |
| Completion close | 4115.709 |
| C3 `in_between` | **True** for `poi-005144` (4043.618–4154.435) and `poi-007302` (4055.248–4211.495); False for `poi-004989` (4161.165–4218.505 → close below the body) |

So the pattern, the zone context and the C3 containment gate are all satisfiable
in this window — **only the 3-bar expiry blocks them**, and by exactly 3 bars on
this occasion.

---

## 6. Classification: (a) / (b) / (c) / (d)

| Candidate | Verdict | Basis |
|---|---|---|
| (a) no pattern by design in window | **Rejected** | 361 diagonals observed; 3 would complete if the window were longer |
| (b) bug / unreachable code | **ACCEPTED** | `N=5` swing lag vs `3`-bar expiry on the only confirmation TF ⇒ `evaluate()` can never return a signal |
| (c) tier/matrix excludes C | **Rejected** | C is in the DAY tier, all six triggers registered, matrix forbids no cell, 68 POIs armed |
| (d) needs a longer window | **Rejected as a remedy** | a longer *calendar* window cannot help: the inequality fails on every bar. Only a longer **bar count after the sweep** (≥ 5) or a shorter confirmation N (≤ 3) can |

**Root cause (single statement).** On the product path C's confirmation series is
H1, whose frozen structural swing confirmation (`N_BAR_HTF = 5`) is **longer than**
C's frozen §24 validity window (3 bars from the sweep candle), so the diagonal's
terminal swing is always already expired when it becomes observable.

**Secondary defect (does not change the verdict).** C expires from
`diagonal.terminal_index`, which is the **§18 base candle** index
(`wave_structure.py:262-271` → `Swing.candle_index`), not the fractal/sweep bar;
for a swing low that can be one bar earlier still. Fixing only this recovers at
most one bar and still leaves age ≥ 4 > 3.

---

## 7. Prior research-book C routes (secondary comparison only, Phase 0 Q4)

- The **essence v1 slice** runs the same ending-diagonal semantics on **native
  M1** (`N_BAR_LTF = 3`) and confirmed **51 ED** setups in its 6-month window
  (`06_RESEARCH/ESSENCE_V1_SLICE_NOTE.md:76,135`,
  `00_LOCKED/CHANGELOG.md` entry for the slice). At `N=3` the freshest swing is
  3 bars old, which is exactly the last legal C bar — reachable, and observed.
- At H1 (`N=5`) the same code path is unreachable. The difference is the
  confirmation N, not the instrument, the data or the zone population.
- These are **different trade definitions** (essence adds its own 1:5 gate and
  M1 limit model) and are **not** liveness evidence — cited only because they
  demonstrate the detector itself works where the arithmetic allows it.

---

## 8. Phase-1 gate decision

This is class **(b)** — unreachable code — but the repair is not an engineering
choice: every candidate fix changes a **frozen** rule.

| Candidate fix | What it changes | Status |
|---|---|---|
| 1. `TRIGGER_C_EXPIRY_EXTRA` ≥ 5 (or ≥ `N+3`) | locked §24 number | **policy ruling required** |
| 2. Shorten swing confirmation N for the C evaluation | locked §27 number | **policy ruling required** |
| 3. Add a shorter-N confirmation TF to the DAY tier (M15/M5) | frozen menu tier table (locked 2026-10-26) | **policy ruling required** |
| 4. Anchor C's expiry at pattern observability (`terminal + N + 3`) | redefines the §24 anchor | **policy ruling required** |

The constant `3` is **not** mis-wired against the locked text ("sweep candle +
3"): the implementation does exactly that. The contradiction is between two
independently frozen rules, so no code was changed here. Options and their
consequences are in `06_RESEARCH/BRANCH_C_E2E_REPORT.md` §5.

**Bans honoured:** no FIB/C3/session loosening, no D volume proxy, no expectancy
or PF criterion, no `locked_constants.py` edit, no A/B/D/E/F body touched, no
expert protocol.

---

## 9. Limits

- The superset scan evaluates C on every armed D1 POI at every H1 bar with
  `from_bar = 0`; it does not re-run the full 3-month menu funnel (the liveness
  run already did, and the arming census reproduces its 68 D1 arms). No
  determinism/byte-identity claim is made.
- The counterfactual is instrumentation, not a proposed change; its 3 signals
  did not pass the menu window, risk, session or spread gates (none was tested).
- No expectancy, PF, win-rate or edge statement is made.
