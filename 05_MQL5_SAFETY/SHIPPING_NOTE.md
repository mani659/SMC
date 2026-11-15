# OPERATOR SHIPPING NOTE — v1.1-test.8

The tester pack (`dist/SMC_v1.1-test.8_tester.zip`) ships **one** EA source:
`mql5/SMC_Safety_Watchdog.mq5`. The build script copies ONLY
`SMC_Safety_Watchdog` (`.ex5` if present, else `.mq5`) out of `05_MQL5_SAFETY/` —
deprecated or reference sources (`SMC_Structure_Draw.mq5`, `SmartMoneyConcepts.mq5`,
the visual twin) are never packaged.

## Heartbeat location (the thing that makes "heartbeat stale" false)

The EA reads `InpHeartbeatFile` (default `smc_heartbeat.txt`) from the terminal's
**DATA folder sandbox**, i.e.:

```
<terminal data folder>\MQL5\Files\smc_heartbeat.txt
```

For an installed terminal that is `%APPDATA%\MetaQuotes\Terminal\<instance>\MQL5\Files`,
**not** the folder holding `terminal64.exe`. The operator derives it at session start:

1. live `mt5.terminal_info().data_path` (authoritative; observed 2026-11-15:
   `C:\Users\User10\AppData\Roaming\MetaQuotes\Terminal\6FE846653CB9AC4D5ACECF98EF447F40`);
2. else `<dir of terminal64.exe>/MQL5/Files/smc_heartbeat.txt`;
3. else the config `heartbeat_path`;
4. else `logs/phase_d/heartbeat.txt` (and the operator says the EA may not see it).

Each candidate is write-probed at startup, so a Program Files ACL degrades loudly
instead of leaving the watchdog blind. The tester config therefore ships **without**
`heartbeat_path` — there is nothing for a tester to get wrong, and pointing it at
`logs/` would make the EA blind.

Before sending the zip to testers:

1. If `SMC_Safety_Watchdog.ex5` is absent from the pack (this build ships `.mq5`
   only), the tester compiles it: open `mql5/SMC_Safety_Watchdog.mq5` in MetaEditor
   (F4 in MetaTrader) → F7 → refresh Navigator → attach to the `XAUUSDm` M5 chart
   with Algo Trading enabled.
2. Confirm the EA input `InpHeartbeatFile` is left at `smc_heartbeat.txt`.
3. Ship the zip + `TESTER_SETUP_GUIDE.pdf` together, and note demo trading is ON
   (`dry_run=false`, demo only; `require_demo=true` blocks real accounts).

**ONE EA since 2026-10-22 (companion-EA merge):** the structure-draw duty is INSIDE
`SMC_Safety_Watchdog.mq5` (v1.20) — compile once, attach once. All draw inputs
default on (`InpEnableStructureDraw=true`, file `smc_structure_draw.txt`, prefix
`SMC_SD_`); it reads the same `MQL5/Files` sandbox and paints only — a bad/missing
draw file can never trigger the emergency.

## Observed live proof (2026-11-15, demo account 474608655 @ Exness-MT5Trial15)

`run_operator.py --config logs/ops_smoke/ops_smoke.json --max-seconds 90`:

- identity gate PASS on DEMO (`require_demo=true`, `dry_run=true`);
- `HEARTBEAT PATH RESOLVED: ...\Terminal\6FE846…\MQL5\Files\smc_heartbeat.txt
  (source: terminal_data_path)`;
- file content `1794743890 35` + `state=running`, mtime age **0.9 s** while running;
- console board printed (`POIS` / `JUDGEMENT: flat …`).

Operational note: use ONE active Python owner per terminal. A leftover operator
process (or a bat-test venv) keeps the watchdog quiet and competing IPC clients
produce spurious `PermissionError(13)`.

This file is NOT copied into the tester zip (build script only takes the watchdog
`.mq5`/`.ex5`).
