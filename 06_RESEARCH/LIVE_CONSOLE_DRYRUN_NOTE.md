# LIVE STRUCTURE CONSOLE — BOUNDED DRY-RUN NOTE (EXNESS COPY)

**Directive:** Lead Architect, 2026-10-06 — Task 1 of the W/L1→L2 sequence
**Status:** PASS — ops validation only, no strategy logic changes
**Terminal:** `C:\Program Files\MetaTrader 5 EXNESS - Copy` (Phase D path)
**Account:** 474608655 @ Exness-MT5Trial15 — **DEMO** (require_demo=true refused REAL)
**Symbol:** **XAUUSDm** (from `config/live_demo.json` — the engine requests the
CONFIGURED symbol via the MT5 API; the open chart is irrelevant to the bot)
**Session configs:** `config/live_demo.json` (2 runs) + `config/live_console_dryrun.json`
(dedicated ops config: only cadence/log-dir differ — same terminal/symbol/magic/dry_run)
**dry_run:** true throughout — **no orders sent**

---

## 1. Contract-restoring bugfix found by this dry run (W1 = 32769, not 32768)

The pre-session MT5 probe caught a live failure the offline suite could not:

```
W1: 0 bars  last_error=(-2, 'Terminal: Invalid params')   # int 32768
D1/H4/H1/M5: 300 bars each                                 # fine
```

The MetaTrader5 Python package's `TIMEFRAME_W1` is **32769** (0x8001); the
weekly-provisioning enum had used 32768, which `copy_rates_from_pos`
rejects with "Invalid params" (32768 is valid for no MT5 timeframe
request). Fixed in `04_SRC/smc/config/timeframe.py` (`W1 = 32769`, with an
explanatory docstring note) + `test_enums.py` pin strengthened. After the
fix, the same probe returns **300 W1 bars**. A contract-restoring
data-boundary bugfix, explicitly in the spirit of the V1.1 freeze ("allowed
without a ruling"). Both notes (`WEEKLY_PROVISIONING_NOTE.md`,
`LIVE_STRUCTURE_CONSOLE_NOTE.md`) corrected.

## 2. Sessions run (three bounded sessions)

| # | Config | Window | Start (UTC) | Polls | Bars | Result |
|---|--------|--------|-------------|-------|------|--------|
| 1 | live_demo | 150 s | 14:15:09 | 299 | 0 | cold start anchors, no bar fell in window; clean stop |
| 2 | live_demo | 400 s | 14:18:10 | 797 | 1 | **real HTF batch at 14:20:00Z**, clean stop |
| 3 | live_console_dryrun | 420 s | 14:25:31 | 837 | 1 | batch at 14:30:00Z + **7 structure boards**, clean stop |

All three: identity gate PASS (path family match + DEMO), heartbeat running
during the session and **`state=shutdown` marker written on clean stop**.

## 3. Real HTF batch (session 3, 14:30:00Z, XAUUSDm)

```
MULTI_TF {"batches": 1, "as_of": "2026-10-06T11:30:00+00:00",
  "per_tf": {"H4": {"detected_raw": 22, "merged": 9, "passed": 0},
             "H1": {"detected_raw": 21, "merged": 8, "passed": 0}},
  "armed": 0, "duplicates": 0, "skipped_tracked": 0,
  "degraded": false, "missing": [], "errors": {}}
```

Live fetch depths (pre-session probe, 300 requested / returned):
W1 300 (~2020-10→2026-10, ~5.8 y), D1 300 (2025-10-21→2026-10-06),
H4 300, H1 300, M5 300.

## 4. Structure board (live, XAUUSDm)

```
 STRUCTURE CONSOLE  |  2026-10-06T11:30:00+00:00 UTC   (read-only snapshot)
========================================================================
 POIS
   W1 : (none)
   D1 : (none)
   H4 : (none)
   H1 : (none)
   (no armed POIs)
------------------------------------------------------------------------
 SWEEPS
   SWEEPS: none
------------------------------------------------------------------------
 SEEKING
   SEEKING: none
------------------------------------------------------------------------
 PLAN
   PLAN: none
========================================================================
```

## 5. Recorded observations (directive item 4/5)

- **POI counts by TF:** W1: 0, D1: 0, H4: 0, H1: 0 — **honest empty, not a
  FAIL.** The mechanism end-to-end is what this task proves: identity →
  W1/D1/H4/H1 live fetch (300 bars each) → real product batch → snapshot
  rebuild → board render → rate-limited cadence → clean shutdown + heartbeat
  shutdown marker. Zero armed POIs on a 9-merged HTF window is the machine's
  frozen validation verdict (same Pillar-1 rejection pattern the D1/H4 packs
  documented at scale: batch re-validation rejects naked levels) — nothing
  is fabricated to make the board look busy.
- **W1/D1 emptiness cause:** NOT cold-start/history depth (W1=300 bars ≈
  5.8 y, D1=300 ≈ 12 mo are provisioned) — it is zero *passed* POIs in this
  window (Pillar rejection), exactly the honest-empty case the console is
  designed to display.
- **Sweeps:** none. **Plan:** none (no candidate/route exists).
- Console mirror: 7 structure boards appended to
  `logs/live_console_dryrun/console_mirror.log`; raw stdout captured to
  `06_RESEARCH/results/live_console_dryrun_console.txt` (unbuffered `-u`).

## 6. Bans honored

No live orders (dry_run=true, `order_send` never invoked by the runner in
this mode); no `locked_constants.py` edits (diff empty); no multi-symbol
work — XAUUSDm only, per config. Suite 849 passed after the W1 enum fix.

## 7. Artifacts

- `06_RESEARCH/LIVE_CONSOLE_DRYRUN_NOTE.md` (this file)
- `06_RESEARCH/results/live_console_dryrun_console.txt` (session stdout)
- `logs/live_console_dryrun/` (events.log, console_mirror.log, kpi_records.jsonl)
- `config/live_console_dryrun.json` (dedicated ops config)

## RETURN BLOCK

```
CONSOLE_DRYRUN_STATUS: PASS
TERMINAL_IDENTITY: PASS
SYMBOL: XAUUSDm (configured; chart-independent)
BOARD_SEEN: YES
POI_COUNTS_BY_TF: {W1: 0, D1: 0, H4: 0, H1: 0}
SWEEPS: NONE
PLAN: none
SUITE: 849 passed (unchanged expected; enum pin strengthened for W1=32769)
LOCKED_CONSTANTS_DIFF: empty
NOTE_PATH: 06_RESEARCH/LIVE_CONSOLE_DRYRUN_NOTE.md
HANDOFF_UPDATED: YES
NEXT_READY: L2 setup identification ledger
```
