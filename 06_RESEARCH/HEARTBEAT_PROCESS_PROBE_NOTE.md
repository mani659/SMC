# HEARTBEAT PROCESS PROBE NOTE — live Python / heartbeat / reconnect (2026-10-15)

Read-only probe. **Nothing killed, restarted, or edited in `04_SRC`.** Design-only R1–R4 (implement only on explicit owner "implement").
Probe time: 2026-10-15 ~16:22 UTC. Note: `events.log` line timestamps read as **local (≈UTC+3) labeled `Z`** (cosmetic) —
cross-checked against process creation times and the embedded `checked_at_utc` (13:33:06Z). UTC equivalents below are converted.

## PART A — process table (observed, not hypothesized)

| PID | Age | Memory | Cmd line summary | Likely role | Heartbeat target (inferred) | Action |
|-----|-----|--------|------------------|-------------|------------------------------|--------|
| 18456 | ~2h49m (started 13:33 UTC) | 52.9 MB, CPU 29.4 s | `python "04_SRC\smc\live\run_operator.py" --config "config\live_demo.json"`; parent cmd 25720 = `run_live.bat` (repo root) | **SMC operator — THIS demo session, HEALTHY** | EA sandbox `…\Terminal\6FE84665…\MQL5\Files\smc_heartbeat.txt` — **FRESH** (mtime = probe second, seq ~10068, `state=running`, 1/s) | **LEAVE** (healthy). Restart only with owner OK if it ever freezes |
| 10248 | ~4 d (since 10/11 14:56 UTC) | 22.3 MB, CPU 2001 s | `python -u scripts\forward\quantforge_forward_supervisor.py --mode forward`; parent = `run_quantforge_forward.bat` | Other project, long-running (other terminal/bot) | none | **LEAVE_ALONE** |
| 25108 | ~4 d | 8 MB, CPU 1792 s | multiprocessing child of 10248 (`spawn_main`) | Other-project worker | none | **LEAVE_ALONE** |
| 21492 | ~2h25m (started 13:58 UTC) | 16.9 MB, CPU 1.2 s | `scripts\dashboard_server.py 8080`; parent PID exited (reparented, still healthy) | Other project dashboard | none | **LEAVE_ALONE** |

- **No zero-cmdline, orphan, or tiny-0%-CPU Pythons exist right now.** The premise's "two tiny 0% Pythons" do not match current state
  (smallest residents are 8 MB w/ 1792 s CPU and 16.9 MB — both accounted for above).
- Cmdlines are repo-relative (`04_SRC\…`, `scripts\…`), so cwds differ per project; SMC's resolves to `D:\Gold Scripts\MQL5\SMC` via `run_live.bat` (`cd /d "%~dp0"`, `run_live.bat:8`).
- PID 18456's cmdline carries no terminal path, but `events.log` proves the match: `MT5 STARTUP terminal_path='…EXNESS - Copy\terminal64.exe'`,
  identity MATCH (DEMO 474608655, XAUUSDm, `dry_run:false`, `require_demo:true`), `terminal_data_path=…\6FE84665…`,
  `HEARTBEAT PATH RESOLVED: …\6FE84665…\MQL5\Files\smc_heartbeat.txt (source: terminal_data_path)`.
- Disk: EA file fresh (see above); `logs/phase_d/heartbeat.txt` frozen since 10-07 (legacy fallback path, superseded — **anyone watching
  that file sees "frozen" forever by design**); glob finds **exactly one** `smc_heartbeat.txt` across all terminal data dirs.
- Console tail: `seq 10068 age 0.5s state running`, JUDGEMENT flat (no armed POI), positions/pendings 0; last HTF batch 16:00 UTC
  (H4 20/6/0, H1 20/7/0, armed 0). An earlier session (PID 8160, 12:01–~13:00 UTC, also `dry_run:false`) preceded the current one.
- Effective config of the RUNNING session is `dry_run:false` (SESSION START + identity facts); demo trading is armed. File on disk is now
  `dry_run:false` per owner request.

## PART B — code findings (file:line)

1. **Publisher, single-threaded.** `HeartbeatPublisher` (`04_SRC/smc/live/heartbeat.py:319-367`); interval gate in `maybe_publish`
   (`:352-358`); sole caller is `LiveLoop.run_once` (`04_SRC/smc/live/loop.py:221-222`); constructed in
   `OperatorSession._build_stack` (`04_SRC/smc/live/run_operator.py:436-438`). No `threading`/`Thread`/`Timer`/`asyncio` anywhere in
   `04_SRC/smc/live` (grep: only an EA-`OnTimer` docstring mention). **Heartbeat rides the main poll loop — HB_MAIN_THREAD_ONLY: YES.**
2. **Poll loop error policy** (`run_operator.py:972-1037`): `run_once` raising `HeartbeatWriteError` → CRITICAL + `SystemExit`
   (`:976-988`, fail-closed by design); **any other exception → log once per signature, `sleep(1)`, `continue`** (`:989-1009`);
   recovery is logged (`POLL RECOVERED`, `:1010-1016`). Copy-rates/API-error → connector returns `None`/raises via `_call`
   (`04_SRC/smc/data/mt5_connector.py:161-208`; `PermissionError` → `MT5CallError`, `:197-199`); loop treats `None` as "no bars"
   (`loop.py:245-246,397-399`). Missing-HTF is caught *inside* `_detect_and_arm` → `arm_errors++`, returns 0, heartbeat still
   publishes that iteration (`loop.py:281-287`). Display reads (`symbol_info_tick`, positions) go through `_mt5_call`
   (`run_operator.py:507-535`): IPC blip → `None` → unknown (never stale/zero), poll continues (`:625-633`).
3. **Reconnect: NONE.** `connect()` runs once at startup (`loop.py:160-175`, `run_operator.py:943-944` → `SystemExit` on false);
   no `ensure_connected` / re-initialize / retry-backoff exists anywhere (grep: no files). A mid-session terminal death surfaces as
   per-poll `OSError` → `POLL FAILED` → keep polling **without ever re-initializing**. AUTO_RECONNECT_EXISTS: **NO**.
4. **Hang ⇒ frozen `state=running`.** If a call *blocks* (MT5 IPC hang inside `copy_rates`, or a multi-second HTF batch inside `run_once`),
   `maybe_publish` (`loop.py:221`) is never reached — seq freezes with `state=running` on disk while the PID stays listed.
   Raised exceptions do NOT freeze (loop keeps publishing next iteration). HANG_LEAVES_STATE_RUNNING: **YES** (block case).
5. **Shutdown marker is clean-exit-only.** `LiveLoop.stop → publish_shutdown` (`loop.py:193-201`); invoked from `run()`'s `finally`
   (`loop.py:234-235`) and `OperatorSession._shutdown` (`run_operator.py:1241-1242`), which runs in `run()`'s `finally`
   (`:1032-1037`) on Ctrl+C, max-seconds, **and** on heartbeat-abort. A kill/segfault/power-loss writes nothing → last `state=running`
   goes stale → EA emergency. Shutdown-write failure is caught and logged, shutdown still finishes (`:1243-1255`).

Failure modes:

| Mode | Process in Task Manager | Heartbeat file | EA sees |
|------|-------------------------|----------------|---------|
| block/hang in MT5 call or batch | present (CPU may be 0 or stuck) | frozen, `state=running` | **stale** → emergency |
| raised per-poll error (incl. MT5 disconnect) | present, looping | keeps publishing (1 s sleeps between) | healthy (until/unless writes themselves fail) |
| heartbeat total-write failure | exits (SystemExit, code 3) | frozen, `state=running` | **stale** → emergency |
| path fallback (wrong file) | present, healthy | *wrong file* updates; EA file frozen | **stale** → emergency |
| clean exit (Ctrl+C / max-seconds / abort) | gone | `state=shutdown` | ages to stale → policy (fail-closed by design) |
| crash / kill | gone or zombie | frozen, `state=running` | **stale** → emergency |

## Root-cause ranking for the described symptom (file frozen 15+ min + EA stale + "Python still listed")

Current state is **healthy** (fresh file, seq advancing 1/s), so this ranks the *described* symptom against today's evidence:

1. **Session-boundary gap (most likely):** an older operator stops/crashes (e.g. PID 8160's 12:01–13:00 UTC session, or the 10-13 abort shape:
   replace + in-place both denied → exit 3) while *unrelated* Pythons (10248/25108/21492) stay listed — "Python still listed" ≠ SMC alive.
   The EA file then freezes `state=running` and alerts stale. Discriminator: `events.log` SESSION START/STOP + EA-file mtime vs process creation time.
2. **Staring at the wrong file:** `logs/phase_d/heartbeat.txt` is frozen since 10-07 by design (superseded path). Anyone monitoring it sees a
   permanent "frozen" file. Discriminator: only `…\6FE84665…\MQL5\Files\smc_heartbeat.txt` is EA-read.
3. **True block/hang** (MT5 IPC hang or >5 s batch on the main thread): PID present, seq frozen `state=running`. Discriminator: `console_mirror.log`
   stops advancing AND `events.log` shows no POLL FAILED (a *raised* error would log + recover). Not observed today.
4. **EA reading a different file:** ruled out — exactly one `smc_heartbeat.txt` exists across all terminal sandboxes.

## PART C — minimal resilience spec (DESIGN ONLY — implement only on owner "implement")

- **R1. Heartbeat independence.** Publish on its own timer/thread (or equivalent) so an MT5-block or multi-second batch can never push seq age
  past the ~5 s EA timeout. Main-loop failures must either keep publishing or write `state=error`/`shutdown` — never silently freeze `state=running`.
  (Does not touch strategy; cadence 1 s and file format unchanged.)
- **R2. MT5 reconnect.** On `copy_rates`/terminal loss: log loudly, back off, re-run `connect()` + identity re-check against the same
  `terminal_path`, then resume the loop. Default: do NOT start a second operator for the same magic+terminal (double-Python would fight over one
  heartbeat file — `events.log` already warns "use one active Python owner per terminal").
- **R3. Single-instance guard (optional, config-flag).** Lock/PID file keyed on `terminal_path`+`magic`; a second launch warns and exits instead of
  two writers interleaving seq on one file.
- **R4. Startup banner.** Print resolved heartbeat path + EA basename + `HB independent: yes/no` at session start (path half already exists via
  `HEARTBEAT PATH RESOLVED:`; add the independence flag so the EA-stale triage is one glance).

Bans honored: no watchdog disable, no stale-timeout inflation as the fix, no killing unrelated Pythons, `locked_constants`/strategy untouched.
