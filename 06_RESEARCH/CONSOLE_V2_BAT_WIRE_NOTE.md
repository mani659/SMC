# CONSOLE V2 — BAT WIRE NOTE (probe + fix, 2026-11-02)

**Authority:** Lead Architect "PROBE + WIRE CONSOLE V2 INTO MAIN run_live.bat PATH" (GO)
**Scope:** display / telemetry only. `LOGIC_CHANGED: NO` (no strategy, thresholds,
arming, `locked_constants`).

---

## 1. Probe findings (read-only first)

| Question | Finding |
|---|---|
| A) V2 code presence | **PRESENT and fully wired in `04_SRC`**: `structure_console.py` (STRUCTURE SCAN from `MultiTFBatchReport.scan`), `operator_console.py` (`mtf:` block + `scan: N candidate row(s) (NOT armed - see STRUCTURE SCAN)`), `run_operator.py` (`_maybe_refresh_structure` rebuild-on-batch + rate-limited on new bars; `_refresh_mtf_board`). Tests exist (`test_console_v2_scan.py`). Not only in tests/docs. |
| B) Launch path | Repo-root `run_live.bat`: `python 04_SRC\smc\live\run_operator.py --config config\live_demo.json` with `cd /d "%~dp0"` (repo root). V2 lives in the SAME tree the bat executes. `dist\run_live.bat` (2026-10-08) is a stale standalone pack, but the root bat never references it. Config: `strategy_mode "DUMB_MTF_H4"`, `dry_run false`, `console_mode "event"`, `console_refresh_s 30`. |
| C) What prints | Verified from the LIVE session's `logs/phase_d/console_mirror.log` (PID 3948, started 2026-11-02 12:00:57 local = 09:00:57Z, i.e. AFTER the V2 edits of 10:15-10:18 local — the process already ran V2 code): status board with `detect: htf batches 0 · (no batch yet)`, NO `mtf:` block, NO `scan:` line, NO STRUCTURE console; JUDGEMENT boards only. Judgement omitting SCAN is intentional (frozen block list, V2 note §7). |
| D) Root cause | **Mode, not wiring:** in `DUMB_MTF_H4` the live loop runs ONLY the dumb slice (`_drive_dumb_mtf`); the product multi-TF batch path never runs, so `loop.htf_batches` stays 0 FOREVER and `adapter.engine is None` → `_maybe_refresh_structure` early-returned → `state["structure"]` stayed `None` forever. Every V2 data source (batches / `report.scan` / engine armed book) is structurally absent in this mode. |

Conclusion: the operator log looking "pre-V2" was CORRECT console behavior for
the configured mode; no amount of waiting populates the boards.

## 2. What changed (display only)

1. **DUMB-slice structure snapshot** (`structure_console.py`: new
   `build_dumb_mtf_snapshot`, pure + read-only; renderer gains an optional
   mode-note line). The dumb slice DOES own two read-only inventories, now
   surfaced in the SAME V2 snapshot shape:
   - SCAN = the DUMB H4 zone book (merged detector geometry from the
     dumb-owned read-only M8 H4 scan, replaced per closed H4 slice — exactly
     the batch-scan shape; CANDIDATES, banned words respected).
   - pois = the same zones annotated with the DUMB sequential-episode status
     (`armed=yes` iff a live episode exists: IN_ZONE_PRIMARY /
     BOUNDARY_FALLBACK / WON; honest states, e.g. EXPIRED_SWEEP_TIMEOUT).
2. **`run_operator.py`**: `_maybe_refresh_structure` now builds the dumb-slice
   snapshot when the adapter owns no engine and the session has a dumb feed
   (`scan_total` + `armed_by_tf` published → the status board's
   `scan: N candidate row(s)` line lights up honestly). The structure-draw
   publisher is deliberately skipped in this branch (that file feeds the
   CHART draw EA = product locked-Pillar book only).
3. **Mode notes (Part 1.4 UX)**: after the identity gate the session prints
   once + mirrors:
   - product multi-TF modes: `waiting for first HTF batch - SCAN/ARMED
     inventories populate after batch` (auto-cleared when batches flow);
   - DUMB slice: `DUMB_MTF_H4 slice mode: product MTF batches never run here
     (htf batches stays 0); STRUCTURE SCAN below lists the DUMB-MTF H4 zone
     book` — also pinned as a `note:` line on every status board.
4. **JUDGEMENT board untouched** (frozen block list by design lock).
5. `state` gains `mode_note` (display key only); none of these keys is ever
   read by strategy/risk.

## 3. How to verify

```text
run_live.bat
  -> wait for the first H4 slice refresh (STRUCTURE/ARMED/SCAN section
     appears after the first dumb zone book; some zones appear immediately
     on the first refresh when in-zone history exists)
  -> look for "STRUCTURE SCAN  (candidates - NOT armed)" and the status
     board line "scan: N candidate row(s)  (NOT armed - see STRUCTURE SCAN)"
  -> [console] mode note appears once right after the startup banner; the
     status board carries the same note while product batches are 0
```

Sample dumb-slice board (rendered from fakes, ASCII only):

```text
========================================================================
 STRUCTURE CONSOLE  |  2026-11-02 09:xx UTC   (read-only snapshot; armed 0)
========================================================================
 DUMB-MTF H4 slice - zone book from the dumb-owned read-only M8 H4 scan; episode annotations are the DUMB slice book, NOT the product locked-Pillar engine book
 STRUCTURE SCAN  (candidates - NOT armed)
   Locked POI definition NOT applied - not tradeable / not seeking
   H4 : 2 candidate(s)  demand_supply 1 | fvg 1
      LONG  demand_supply  3304.80-3312.57     t=n/a
      SHORT fvg            3268.10-3275.90     t=n/a
------------------------------------------------------------------------
 ARMED POI  (locked definition only)
   W1/D1/H1 : (none)
   H4 : LONG  demand_supply  3304.80-3312.57  armed=no  state=n/a ...
========================================================================
```

(`t=n/a` is honest — the dumb zone book carries no timestamps; product scan
rows carry real `created_at`.)

## 4. Verification status

- Full pytest suite: **1378 passed** (includes 5 new tests in
  `04_SRC/tests/test_console_v2_dumb_console.py`: scan-row shape, episode
  arm/expire honesty via the real state machine, read-only strict fake,
  renderer purity, and the status-board note line). Console V2 family
  (`test_console_v2_scan.py`, `test_structure_console.py`,
  `test_console_events.py`, `test_mode_t_console_markers.py`) all green.
- Stdout contract: covered by fake/unit tests only — **no live dry-run was
  launched** because a LIVE operator session (`python run_operator.py --config
  config\live_demo.json`, PID 3948, `dry_run=false`) was already running at
  probe time; launching a second session into the same terminal/account was
  deliberately avoided. The fix takes effect at the operator's next restart
  via `run_live.bat`.

## 5. Bans honoured

- No pillar / trigger / risk / threshold change; no arming forced; no
  `locked_constants` edit (diff empty); `LOGIC_CHANGED: NO`.
- Nothing was switched between strategy modes: `DUMB_MTF_H4` remains the
  configured slice; the dumb module files were NOT edited (the builder reads
  feed/machine read-only from the live layer).
- SCAN rows never say armed/POI/signals/entry/tradeable; the dumb snapshot
  note explicitly separates the slice book from the product locked-Pillar book.
- Judgement board block list unchanged.
