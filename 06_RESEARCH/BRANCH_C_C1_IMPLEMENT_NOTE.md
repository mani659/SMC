# BRANCH C — C1 IMPLEMENTATION NOTE (observability-anchored expiry)

**Status:** IMPLEMENTED + RE-MEASURED. Architect accepted **C1** from
`06_RESEARCH/BRANCH_C_DESIGN_LOCK.md`.
**`LOGIC_CHANGED: YES`** — one behavioural change, scoped to Trigger C's expiry
anchor (no constant, no tier, no other trigger).
**Window (unchanged):** exec 2025-09-01 → 2025-11-30 UTC (M5, 17,840 bars),
warm-up 2025-08-01. No re-pick, no extension.
**Suite:** 1,564 passed / 7 skipped (`cd 04_SRC && PYTHONPATH=. python -m pytest -q`).

---

## 1. What changed

Trigger C's §24 clock moved from the diagonal's terminal candle to the bar the
terminal becomes **observable**:

```
anchor_index = terminal_index + N(confirm_tf)
legal bars   = anchor_index … anchor_index + TRIGGER_C_EXPIRY_EXTRA
```

`TRIGGER_C_EXPIRY_EXTRA = 3` and `N_BAR_HTF = 5` are **unchanged**; `N` is read
from the frozen §27 lookup (`Timeframe.n_bar_confirmation`), and the timeframe
comes from the swings' own `Swing.timeframe`.

On the product DAY tier (D1 → H1) the legal terminal ages are therefore
**5, 6, 7, 8** instead of the arithmetically impossible `≤ 3`.

**Before / after on the same wiring**

| | Before | After |
|---|---|---|
| Clock start | `terminal_index` | `terminal_index + N(confirm_tf)` |
| Legal H1 terminal age | `≤ 3` (unreachable: freshest swing is 5) | `5 … 8` |
| `evaluate()` completions (superset scan) | **0** | **3** |
| C routes / fills (product path) | 0 / 0 | **0 / 0** (see §5 — frozen downstream gates) |

---

## 2. Code (3 files)

| File | Change |
|---|---|
| `04_SRC/smc/triggers/trigger_expiry.py` | New `ending_diagonal_anchor(terminal_index, timeframe)` = `terminal_index + Timeframe.n_bar_confirmation(timeframe)`. `window_bars_for`, `signal_expired`, `poi_give_up_bars` untouched. Module docstring records amendment C1. |
| `04_SRC/smc/triggers/trigger_c_ending_diagonal.py` | Replaced `signal_expired(diagonal.terminal_index, 3, bar)` with the anchor form: `if bar < anchor: return None`, then `signal_expired(anchor, 3, bar)`. Adds `known_at` to `signal.data`. Header documents the rule. |
| `06_RESEARCH/scripts/branch_c_geometry.py` | Research harness updated for the post-C1 world: completion band 1–3 (was `== 0`), product-path C funnel (routes/placed/fills) + per-completion route diagnostics, C1-window census key. |

**Timeframe source (the trap the design note flagged).** `trigger_router.evaluate_at`
never populates `TriggerContext.execution_timeframe` (`trigger_router.py:123-129`),
so that field stays `M5` even on an H1 confirmation series. The implementation
reads `context.swings[-1].timeframe` — the series the swings were detected on —
so H1 yields `N = 5`. Reading `execution_timeframe` would silently use `N = 3`
and leave C near-unreachable; `test_n_source_is_swing_timeframe_not_execution_timeframe`
pins this.

**Lookahead safety.** The anchor is index arithmetic (`terminal_index + N`) on
data at or before the evaluation bar. It only *delays* expiry; it never admits a
bar the swing series does not already contain, `find_ending_diagonal` still sees
the closed-prefix swings, and the reclaim ordering is unchanged. Conservative
bound: the §18 base candle of a swing low may precede its fractal by one bar, so
the anchor can be up to one bar early — it can only shorten C's life.

**Nothing else touched.** `locked_constants.py` values unchanged; no tier table,
`_TIER_ADF`, `_DAY_TRIGGERS`, `MENU_EXPIRY_BARS`, C3, sessions, EQH, ATR band,
risk/execution, or any A/B/D/E/F trigger. `git diff -- 04_SRC/smc/config` empty.

---

## 3. Tests

New/updated in `04_SRC/tests/`:

| Test | Pins |
|---|---|
| `test_ending_diagonal_anchor_uses_frozen_swing_n` | `+5` for D1/H4/H1/W1, `+3` for M30/M15/M5/M1 (reuses §27; no new number) |
| `test_ending_diagonal_legal_window_is_anchor_to_anchor_plus_three` | legal `anchor … anchor+3`, dead at `anchor+4` |
| `test_h1_fires_at_first_observable_bar` | age **5** (bar 27 from terminal 22) completes; `known_at == 27` |
| `test_h1_fires_at_last_legal_age_8` | age **8** completes (window is finite, not open-ended) |
| `test_h1_rejects_age_4` | age 4 rejected (before knowability) |
| `test_h1_rejects_age_9` | age 9 rejected (past the frozen 3) |
| `test_n_source_is_swing_timeframe_not_execution_timeframe` | H1 series at age 3 rejected while `execution_timeframe` is M5 → proves `N=5` came from the swings |
| M5 fixture tests (4) | existing semantics preserved: reclaim-only emission, zone context, throw-under, entry/stop, `expiry_bars == 3`; completion moved to the first legal bar (25 = 22 + 3) |

Regression: all A/B/D/E/F trigger and expiry tests unchanged and green; full
suite **1,564 passed / 7 skipped** (was 1,557 / 7 — 7 new tests).

---

## 4. Re-measure — completions (same frozen window)

`PYTHONPATH=04_SRC python -u 06_RESEARCH/scripts/branch_c_geometry.py`
(1.9 min, 17,840 M5 bars, 124 batches, `BATCH_ERRORS = 0`, `MENU_ERRORS = 0`,
D1 arms **68** reproduced — `ANALYSIS_OK`, no problems).

| Metric | Value |
|---|---:|
| Ending-diagonal observations (H1) | 361 |
| Minimum terminal age | 5 |
| Observations inside the **C1** window (ages 5–8) | 95 |
| Observations inside the pre-C1 window (age ≤ 3) | 0 |
| **Real `evaluate()` completions (superset, `from_bar=0`)** | **3** |
| Expiry-ignored counterfactual | 3 (identical set) |
| Completion terminal age | **6** (all three) |
| Completion bar | **2025-11-25 09:00 UTC** (H1), terminal 1885 |

The band check (1–3) passed with no fail-loud trigger, and the real scan is a
subset of the counterfactual exactly as C1 requires.

---

## 5. Re-measure — routes / fills, and why they are 0

`C routes: 0 · placed: 0 · fills: 0` on the product path. The three completions
are one diagonal and three SHORT D1 zones; each dies at a **frozen downstream
gate**, not at C's reachability (diagnostics from the harness's own episode log):

| POI | Episode | What stopped the route |
|---|---|---|
| `poi-004989` | DAY episode open (`armed_DAY_sweep@89`), still **ACTIVE** at window end | **C3 `not_in_between`** — completion close **4115.709** vs zone **4161.165–4218.505**; the close is ~1.2 % below the zone body. Two H1 rejections recorded. |
| `poi-005144` | DAY episode **WON by Trigger F at H1 completion bar 1746** | **one-shot**: F consumed the episode **145 H1 bars before** C's pattern existed (bar 1891). Chronological first-valid (§12) behaves as designed. (C3 would have passed: 4115.709 is inside 4043.618–4154.435.) |
| `poi-007302` | **no episode** in the window | armed but never swept → no confirmation window was ever opened (§24/F5/R2 sweep gate). |

So the branch is **reachable but not live in this window**: 3 completions, 0
routes. No gate was loosened to convert them, and no counterfactual fill is
claimed. This is the honest residual: C1 fixed C's own arithmetic; the remaining
obstacles are C3, the one-shot race with F, and sweep availability — all frozen.

---

## 6. What is now true (claim discipline)

- **Reachable:** yes — C emits on the DAY/H1 wiring when a diagonal terminal is
  observable and a first reclaim occurs inside its 3-bar life.
- **Live (fills):** **no** on this window (0 routes). `TRIGGER_C_LIVE: YES` must
  read "implemented, routable **and reachable**", not "fills".
- **Constants:** `TRIGGER_C_EXPIRY_EXTRA = 3`, `N_BAR_HTF = 5`, `N_BAR_LTF = 3`,
  `MENU_EXPIRY_BARS = 20` — all unchanged.
- No expectancy, PF, win-rate or edge statement is made.

---

## 7. Limits

- The completion count is a **superset** scan (`from_bar = 0`, no menu window,
  no consumption); it bounds reachability, it is not a product route count.
- Routes/fills come from the same product composition but only the DAY tier's
  confirmation scan runs (H4/H1/M15 tiers stubbed, 41,237 scan calls); C is
  inadmissible there, so nothing is lost for this question.
- One window, one instrument, one tier map. The arithmetic (N=5 on H1) is
  window-independent; the *count* is not.
- The `terminal_age_at_first_possible_bar` column stays `null` (unused).
- No determinism/byte-identity claim: the harness was run once after the change
  (counts are integer and the band check is deterministic in construction).

---

## 8. Governance

- Docs: this note; `LOCKED_DECISIONS` **§24b** (dated C-only anchor amendment)
  + §24a reading + register row **A11**; `SESSION_HANDOFF.md`,
  `POST_V1_ACTIVE_TODO.md` (C status → `REACHABLE_NOT_LIVE`), `CHANGELOG.md`.
- **NEXT = Architect accept the C verdict (reachable, not live in this window) →
  formal D OFF note + full-book engineering scorecard.** No further C work is
  authorised: A/B stay DEFER, E DARK_IN_WINDOW, D OFF, F untouched.
