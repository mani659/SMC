# STRUCTURE DRAW PROBE NOTE — no markers after 30+ min (2026-10-22)

**Banner: VISUALIZATION ONLY — NOT A STRATEGY CHANGE.** Read-only probe;
code fixed only where the file cannot physically land in the EA-readable
sandbox. Nothing touched in strategy, thresholds, `locked_constants`, or
heartbeat emergency behavior.

## Observed symptom

Owner attached the merged `SMC_Safety_Watchdog.mq5` (v1.20) to the XAU
demo chart; system running >30 min; **no `SMC_SD_*` structure objects on
the chart**. Timeframe switches do not help — draw is file-driven.

## Probing replayed, in order

### P1 — operator process / config

- Config: `config/live_demo.json`, loaded through
  `smc.live.operator_config.load_operator_config` (strict whitelist, no
  locked/unknown keys rejected).
- `terminal_path` = `C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe`
- `symbol` = `XAUUSDm`
- `magic` = `20260919`
- `dry_run` = `false`
- `require_demo` = `true`
- `structure_draw_enabled` = `true` (default)
- `structure_draw_path` = `""` (default — means "same EA-readable dir as
  the heartbeat")
- `marker_enabled` = `true`
- `marker_path` = `""`
- `heartbeat_path` = `logs/phase_d/heartbeat.txt` (the configured FALLBACK —
  see P2/P4)
- `heartbeat_interval_s` = `1.0`

Operator wiring is intact on the code side: `run_operator.py`'s
`_maybe_refresh_structure` → `_publish_structure_draw` fires on **every
structure refresh**, and `batch_changed` (a new HTF batch / arming event)
forces both the console board and the draw file from the same place.
So if the operator is running, the draw file *should* be rewritten on
every refresh. P6 is not the break.

### P2 — resolved write path (hardness)

Python resolves the draw file exactly the same way it resolves the
heartbeat, to the **terminal data folder sandbox**, not the project log
dir:

- `smc.live.structure_publish.resolve_structure_draw_path(terminal_path=...)`
  → `C:\Program Files\MetaTrader 5 EXNESS - Copy\MQL5\Files\smc_structure_draw.txt`
- Same parent as the heartbeat:
  `C:\Program Files\MetaTrader 5 EXNESS - Copy\MQL5\Files\smc_heartbeat.txt`
- Three files share that EA-readable parent:
  - `smc_heartbeat.txt`
  - `smc_structure_draw.txt`
  - `smc_markers.csv`

**Hard finding on THIS machine:** that sandbox folder does **not** exist.
`C:\Program Files\MetaTrader 5 EXNESS - Copy\MQL5` does not exist as a
subfolder of the terminal install dir, and `os.makedirs(...MQL5\Files)`
is `PermissionError: Access is denied`.

So on this machine, **neither `smc_heartbeat.txt` nor
`smc_structure_draw.txt` could have landed in the EA-readable sandbox
from a Python operator run started here** — there is no writable
`MQL5/Files/` under the configured terminal yet.

The only heartbeat file that *is* updating is the configured fallback,
`logs/phase_d/heartbeat.txt`. That file is real and fresh — but it lives
in the session log dir, which is **not** the EA's read sandbox. (The path
book already states the EA never reads that fallback.)

### P3 — file content

**File does not exist on this machine**, so there is nothing to inspect
for POI/SWEEP/SEEK/PLAN rows. The root cause is therefore upstream of
content: the publisher has no EA-readable dir to write into on this
machine. If a file *were* present but header-only, that would be a
different, later break (empty snapshot — no armed/tracked POIs). That is
not the situation here.

### P4 — heartbeat twin

- **On this machine: heartbeat twin is NOT updating in the EA-readable
  sandbox.** The data-folder `smc_heartbeat.txt` does not exist, and the
  `MQL5/Files/` parent does not exist.
- The only updating heartbeat on this machine is the **not-EA-readable**
  fallback in `logs/phase_d/`.
- Both files missing from the EA sandbox → consistent with one root cause:
  the terminal's `MQL5/Files/` sandbox has not been created/attached on
  this machine, so the operator cannot write either file where the EA
  reads it.

### P5 — EA side (documented; agent cannot see the MT5 chart)

The committed code side is consistent and unchanged from the merge lock:

- The draw duty is inside `SMC_Safety_Watchdog.mq5` (v1.20), timer order
  `CheckHeartbeat → UpdateMarkers → UpdateStructureDraw`.
- Draw inputs are all defaulted in the source (verified by grepping the
  MQL5 file, not the chart):
  - `InpEnableStructureDraw = true`
  - `InpStructureFile = "smc_structure_draw.txt"`
  - `InpStructureSymbol = ""` (chart symbol)
  - `InpDrawPrefix = "SMC_SD_"`
  - `InpMaxStructureAgeSec = 120`
  - `InpDrawPOI / InpDrawSweep / InpDrawSeek / InpDrawPlan = true`
- OnInit guard: if `InpDrawPrefix` is empty or equals `SMC_`, the draw
  duty auto-disables and logs it — owner should confirm the EA's Experts
  log says **structure draw ON**, not the disable message.
- The structure EA reads the **terminal data folder**, same as the
  heartbeat: `FileOpen(InpStructureFile, FILE_READ | FILE_TXT | FILE_ANSI)`
  from the EA's sandbox, default `smc_structure_draw.txt`.
- Draw duty fail-soft: missing/foreign/stale/mismatch → clears only
  `SMC_SD_*` objects, **never** an emergency.
- Owner cannot see the chart here; the 3-click verify is in the OWNER
  VERIFY section.

### P6 — live snapshot vs file

Code-side: the operator's refresh path is wired to publish the draw file
on the same event that updates the console board. There is no separate
"draw file only" path that could be silently broken while the board is
fine. So P6 is **not** the break on the code side; the break is that no
Python operator has actually written anything into the EA sandbox on this
machine (P2 hard failure).

## Root cause

**ROOT_CAUSE:** On this machine, the configured terminal's EA-readable
sandbox `C:\Program Files\MetaTrader 5 EXNESS - Copy\MQL5\Files\` does not
exist and is not writable from this Python process, so neither
`smc_structure_draw.txt` nor `smc_heartbeat.txt` could have been written
into the place the EA reads — the operator may be running into a different
(or no) terminal path, or the sandbox has never been created by a live EA
attach. Structure draw is therefore absent for an **environment/path**
reason, not a code/publish logic bug.

If the operator that is actually running is bound to a **different**
terminal, or `terminal_path` no longer matches the terminal the EA is
attached to, then the operator is writing into a sandbox the EA never
reads — same symptom, same class of fix: make the two sides point at the
same `terminal_path`.

**Empty-POI-file variant (documented, NOT this case):** if the EA-readable
file *exists* but is header-only, the root cause would be "no armed/tracked
POIs in the structure board right now", and the chart correctly shows
nothing. On this machine we cannot reach that variant yet because the file
does not exist at all.

## Evidence

- Config keys: `structure_draw_enabled=true`, `structure_draw_path=""`,
  `structure_draw_enabled` default is `true` in `operator_config.py`.
- Resolved Python paths:
  - draw → `C:\Program Files\MetaTrader 5 EXNESS - Copy\MQL5\Files\smc_structure_draw.txt`
  - heartbeat → `C:\Program Files\MetaTrader 5 EXNESS - Copy\MQL5\Files\smc_heartbeat.txt`
  - marker → `C:\Program Files\MetaTrader 5 EXNESS - Copy\MQL5\Files\smc_markers.csv`
- `MQL5/Files/` resolved parent exists on disk: **NO** (on this machine).
- `MQL5/` under the configured terminal install dir exists on disk:
  **NO** (`PermissionError` on attempted mkdir; not present in the
  terminal install folder children: `Bases, Config, Profiles, Sounds,
  Tester`).
- Only updating heartbeat on this machine: `logs/phase_d/heartbeat.txt`
  (config fallback; **not** EA-readable).
- EA draw inputs committed defaults (from `SMC_Safety_Watchdog.mq5`):
  `InpEnableStructureDraw=true`, `InpStructureFile="smc_structure_draw.txt"`,
  `InpDrawPrefix="SMC_SD_"`, `InpMaxStructureAgeSec=120`.
- Operator refresh wiring intact: `_maybe_refresh_structure` →
  `_publish_structure_draw` on every structure refresh; batch change forces
  board + file.

## Fix

This is an environment/path fix, not a strategy change. Do the minimal
thing that gets the file into the EA-readable sandbox; do **not** weaken
heartbeat emergency behavior and do **not** invent a draw file.

1. Confirm which terminal the EA is attached to and which terminal
   `terminal_path` points at. They must be the **same** terminal.
   - Committed config `terminal_path` =
     `C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe`
2. Make the EA-readable sandbox exist for that terminal. The normal way
   is to attach/launch the EA in that terminal at least once so the
   terminal creates its `MQL5/Files/` sandbox; if the terminal is already
   running, the sandbox may appear under the **data folder** rather than
   the install dir (`terminal_info().data_path` → `.../MQL5/Files/`), and
   the path policy already prefers that authoritative data path when
   available.
3. Run the operator against that same terminal with the matching
   `terminal_path`. The operator writes both `smc_heartbeat.txt` and
   `smc_structure_draw.txt` into that sandbox.
4. Retest (see OWNER_VERIFY). Do **not** manually copy the files into the
   sandbox as a permanent fix — that hides the real path/sandbox issue and
   will not survive a restart. Copying may be acceptable only as a
   one-shot diagnostic to prove the EA side can paint once a file exists.

If the owner actually meant "I attached the EA and it still shows nothing
after the file exists and updates", then root cause shifts to the empty
snapshot / armed-POI case (P3) and the fix is to wait for a batch/arm
event rather than edit anything. That variant is not established on this
machine yet.

No code change is required by this probe. If the owner later reports the
file exists and updates but the EA still shows nothing, then a minimal
patch would be a path/name mismatch between what Python writes and what
the EA's `InpStructureFile` reads — and that is an EA-input or config
issue, not a draw-logic issue.

## OWNER_VERIFY (after the fix)

1. In the EA attach GUI, confirm the structure inputs:
   - `InpEnableStructureDraw = true`
   - `InpStructureFile = smc_structure_draw.txt`
   - `InpDrawPrefix = SMC_SD_`
   - `InpStructureSymbol = ""`
   - `InpMaxStructureAgeSec = 120`
   - and the Experts log says "structure draw ON", not the
     `InpDrawPrefix` disable message.
2. Start the operator with the same `terminal_path`; confirm the
   EA-readable `MQL5/Files/` now contains a fresh
   `smc_structure_draw.txt` (and `smc_heartbeat.txt`).
3. On the chart, confirm `SMC_SD_*` zones/sweep/seek/plan appear and the
   armed labels update after an HTF batch.

## Hard bans honored

No threshold/strategy/`locked_constants` change. No fake zones. No weakening
of heartbeat emergency behavior.

## RETURN BLOCK

PROBE_STATUS: PASS
ROOT_CAUSE: On this machine the configured terminal's EA-readable
`MQL5/Files/` sandbox does not exist and is not writable, so neither
`smc_structure_draw.txt` nor `smc_heartbeat.txt` could be written where
the EA reads; the break is environment/path, not draw-logic.
FILE_EXISTS: NO
FILE_AGE_SEC: NA
POI_ROWS: NA (file does not exist on this machine)
SYMBOL_IN_FILE: NA (file does not exist on this machine)
HEARTBEAT_UPDATING: NO (in the EA-readable sandbox on this machine) —
the only updating heartbeat on this machine is the NOT-EA-readable
`logs/phase_d/` fallback
CODE_FIXED: NO
NOTE_PATH: 06_RESEARCH/STRUCTURE_DRAW_PROBE_NOTE.md
NEXT_READY: Owner retest the §4b checklist after pointing Python + EA at
the same terminal sandbox
