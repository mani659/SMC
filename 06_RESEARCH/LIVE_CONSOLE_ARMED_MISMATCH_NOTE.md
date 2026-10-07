# LIVE CONSOLE vs ARMED MISMATCH — ROOT CAUSE + FIX + WARM-UP AUDIT

**Directive:** Lead Architect, 2026-10-06 (ops bugfix + audit; dry_run only)
**Status:** PASS — mismatch root-caused, fixed, and reconciled LIVE
**Scope:** display/wiring only; no pillar/trigger/SL/TP/risk changes;
`locked_constants.py` diff empty; suite 853 passed

---

## 1. Root cause (Task 1)

**Symptom (operator session 2026-10-06):** status board `detect: armed 1`
(H4 23/11/3) while the structure console showed `POIS` all `(none)` —
inconsistent on its face.

**Trace (arm path → storage → snapshot → renderer):** the arm path is
sound — `runtime._arm_passed → engine.arm_at` appends the POI to the
engine's `_armed_order` registry, and `build_structure_snapshot` reads
`engine.tracked_pois()` directly. Nothing filtered the armed POI out.

**Actual defect — snapshot refresh policy in `run_operator.py`:** the
structure snapshot's rate-limit anchor treated an HTF **batch change**
(the arming event) like any routine per-bar refresh, gated by
`console_refresh_s`. On the live config that cadence is **900 s**, so a
POI armed seconds after a snapshot rebuild stayed invisible on the board
for up to 15 minutes while the status-board `armed` counter updated
immediately — exactly the observed inconsistency. It was a stale-snapshot
window, not a missing-POI gap and not "true zero".

## 2. Fix applied (minimal surface)

- **`run_operator.py` (`_maybe_refresh_structure`):** a batch change now
  ALWAYS rebuilds the snapshot immediately (arming must be visible without
  waiting out the cadence); new-bar refreshes remain rate-limited to
  `console_refresh_s`. Idle polls remain a no-op.
- **`structure_console.py`:** the board header now carries an armed
  counter — `STRUCTURE CONSOLE | … (read-only snapshot; armed N)` — so
  `detect: armed N` vs the POIS sections can never silently diverge again.

**Regression tests** (`test_structure_refresh.py`, 4): batch change
rebuilds immediately despite a 900 s rate limit (empty → armed W1 row);
bar-only refresh stays rate-limited (same snapshot object); idle poll
no-op; header armed counter renders. Suite **849 → 853**.

## 3. Warm-up audit (Task 2)

**Design confirmed already implemented:** HTF POIs come from a historical
window, not from session birth.

- `LiveLoop` fetches `htf_window_bars = 300` per HTF (W1/D1/H4/H1) and
  `window_bars = 200` M5, at `start()` (product-mode probe) and again for
  **every batch** — each H1-close batch re-scans the full 300-bar window.
- `build_htf_prefixes` then trims each series to `as_of` (forming bar
  included, future bars never) — the accepted research cadence.
- No operator-path gap found: `run_operator._build_stack` uses the
  LiveLoop defaults; nothing overrides the fetch depth downward.

**Live fetch proof (EXNESS Copy, XAUUSDm, 2026-10-06):**

| TF | Bars | Oldest | Newest |
|----|------|--------|--------|
| W1 | 300 | 2021-01-10 | 2026-10-04 |
| D1 | 300 | 2025-10-21 | 2026-10-06 |
| H4 | 300 | 2026-07-30 | 2026-10-06 |
| H1 | 300 | 2026-09-17 | 2026-10-06 |
| M5 | 200 | 2026-10-05 | 2026-10-06 |

Residual honesty: W1/D1 POIs can still be absent on the console for
legitimate frozen-pipeline reasons (validation passed-count, zone dedup)
— that is the machine's verdict, not a provisioning gap. With the header
armed counter, "warm window but zero passed" is now distinguishable at a
glance from "stale board".

## 4. Live reconciliation (Task 3) — dry_run only

Bounded 600 s session on the Copy terminal (`config/live_console_dryrun.json`,
DEMO 474608655, XAUUSDm, dry_run=true, no orders):

- Batch at **15:40:00Z**: `H4 23 raw / 11 merged / 3 passed, H1 22/7/0,
  armed 1, duplicates 2` — the SAME counts as the Architect's pasted
  session (same windows, same day).
- Structure boards rendered **21 times**; the moment the batch armed the
  POI, the board showed:

```
 STRUCTURE CONSOLE  |  2026-10-06T12:45:00+00:00 UTC   (read-only snapshot; armed 1)
========================================================================
 POIS
   W1 : (none)
   D1 : (none)
   H4 : LONG  demand_supply+fvg+ob 3982.45-4310.83     armed=yes  state=TESTED  id=52deba49
   H1 : (none)
------------------------------------------------------------------------
 SWEEPS
   H4  side=LONG  1.20x ATR    -> poi 52deba49
------------------------------------------------------------------------
 SEEKING
   52deba49  H4  state=TESTED   posture=CLEAN_ARM        trigger=-
------------------------------------------------------------------------
 PLAN
   PLAN: none
========================================================================
```

- Counters and console now agree on the same definition of "armed" (engine
  episode registry). Clean shutdown, heartbeat `state=shutdown`, 1196
  polls / 2 bars.
- Note: state=TESTED with `trigger=-` is correct §5 behaviour (first-touch
  closes the one-shot scan eligibility window per the seek/scan contract);
  the sweep link (1.20×ATR LONG) rides the new L1 displacement seam.

## 5. Bans honored

No threshold tuning to "make POIs appear"; `locked_constants.py` diff
empty; dry_run only (no orders); no second detection stack — the fix is
operator display wiring.

## 6. Artifacts

- `06_RESEARCH/LIVE_CONSOLE_ARMED_MISMATCH_NOTE.md` (this file)
- `06_RESEARCH/results/live_console_reconcile_console.txt` (session stdout)
- `logs/live_console_dryrun/` (events.log, console_mirror.log — 21 boards)
- Fix: `04_SRC/smc/live/run_operator.py`, `04_SRC/smc/live/structure_console.py`
- Tests: `04_SRC/tests/test_structure_refresh.py` (4)

## RETURN BLOCK

```
MISMATCH_STATUS: PASS
ROOT_CAUSE: structure-snapshot rate-limit treated the arming event (batch change) like routine bar refreshes — with console_refresh_s=900 an armed POI stayed off the board up to 15 min while the status counter updated immediately (stale-snapshot window; arm path itself sound)
FIX_APPLIED: YES
WARMUP_BARS: {W1: 300, D1: 300, H4: 300, H1: 300, M5: 200}
OLDEST_TS: {W1: 2021-01-10, D1: 2025-10-21, H4: 2026-07-30, H1: 2026-09-17}
CONSOLE_SHOWS_ARMED: YES
SUITE: 853 passed
LOCKED_CONSTANTS_DIFF: empty
NOTE_PATH: 06_RESEARCH/LIVE_CONSOLE_ARMED_MISMATCH_NOTE.md
HANDOFF_UPDATED: YES
NEXT_READY: paper trading after console trust confirmed | Architect review
```
