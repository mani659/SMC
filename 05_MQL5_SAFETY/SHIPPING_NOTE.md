# OPERATOR SHIPPING NOTE — v1.1-test.6

The tester pack (`dist/SMC_v1.1-test.6_tester.zip`) ships `mql5/SMC_Safety_Watchdog.mq5`
AND the operator-compiled `mql5/SMC_Safety_Watchdog.ex5` (both present in the source tree
under `05_MQL5_SAFETY/`; the build script copies whichever of `.mq5`/`.ex5` exist).

Before sending the zip to testers:

1. If the `.ex5` is absent from the pack, compile `SMC_Safety_Watchdog.mq5` to
   `SMC_Safety_Watchdog.ex5` in MetaEditor (local machine — never in CI) and re-run
   `python AUTO_BUILD_RELEASE.py`.
2. Confirm both watchdog files are listed in the zip's `mql5/` folder.
3. Ship the zip + `TESTER_SETUP_GUIDE.pdf` together, and note demo trading is ON
   (`dry_run=false`, demo only; `require_demo=true` blocks real accounts).

Tester EA input: leave `InpHeartbeatFile` at its default (`smc_heartbeat.txt`) —
the Python side writes the heartbeat to the terminal data-folder
`MQL5/Files/smc_heartbeat.txt` automatically (derived from the live
`terminal_info().data_path`, else `terminal_path` in `config/live_tester.json`).

**ONE EA since 2026-10-22 (companion-EA merge):** the structure-draw duty is
now INSIDE `SMC_Safety_Watchdog.mq5` (v1.20) — compile once, attach once. All
draw inputs default on (`InpEnableStructureDraw=true`, file
`smc_structure_draw.txt`, prefix `SMC_SD_`); it reads the same `MQL5/Files`
sandbox and paints only — a bad/missing draw file can never trigger the
emergency. `SMC_Structure_Draw.mq5` is **DEPRECATED — do not ship, do not
attach** (kept only as reference source; if the build script would copy it,
remove it from the pack's `mql5/` folder). Owner checklist before any tester
shipping: `06_RESEARCH/MT5_STRUCTURE_DRAW_NOTE.md` §4b.

Operational note: use ONE active Python owner per terminal. A leftover operator
process (or a bat-test venv) keeps the watchdog quiet and competing IPC clients
produce spurious `PermissionError(13)`.

This file is NOT copied into the tester zip (build script only takes `.mq5`/`.ex5`).
