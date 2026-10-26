# HEARTBEAT FIX A + OPERATOR RESILIENCE (B1–B4) — IMPLEMENTATION NOTE

**Date:** 2026-10-17
**Authority:** Lead Architect dated ruling 2026-10-17.
**Scope:** heartbeat write path + live-operator resilience. **No** strategy/pillars/
triggers/Mode T change; `locked_constants.py` untouched; watchdog safety NOT disabled;
`InpStaleTimeoutSec` NOT raised; EA 2-tick debounce NOT implemented; no unrelated Python
killed; no claim the POI board is fixed.
**LOGIC_CHANGED:** NO (decision logic). Live-ops only.
**Base commit:** `9b649d5` (edits are uncommitted working-tree changes; commit gate not
granted this engagement).

---

## 1. Problem (why the EA kept alerting "heartbeat unreadable")

The MQL5 watchdog (`05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5`) reads
`MQL5/Files/smc_heartbeat.txt` once per second. It has two distinct fail-closed
branches: **stale** (readable but old) and **unreadable** (missing / unparseable).
The 2026-10-15..17 alerts were **unreadable**, self-healing within ~1 s:

- `10-17 08:54:36 EMERGENCY (heartbeat unreadable)` → `08:54:37 healthy again (seq 143772)`
- `10-17 09:27:26` → `09:27:27 (seq 145718)`
- one continuous Python session (PID 18456, started 10-15 16:33 UTC, seq ~145,700 by
  10-17 ≈ 40 h at 1/s) — the writer never actually stopped.

**Root cause:** the atomic `os.replace` path is safe (a reader sees OLD *or* NEW), but the
**in-place fallback used `Path.open("w")`, which truncates the file to 0 bytes before the
payload is written.** An EA 1 Hz read landing in that truncate→rewrite window saw an
EMPTY file → "unreadable". Each false "unreadable" triggers the EA `Emergency()` branch
(close ALL scoped positions + delete ALL scoped pendings) — harmless while flat, but with
`dry_run:false` a 1-second collision could wrongly flatten a live demo trade.

The 10-15 count also included **22 genuine stale** events (a real 16:07–16:31 gap before
the session came up) — those were legitimate, not this bug.

## 2. Fix A — non-truncating in-place write

`04_SRC/smc/live/heartbeat.py::_write_in_place` rewritten:

- open `os.O_RDWR | os.O_CREAT | O_BINARY` (no truncation; **`O_BINARY` is mandatory** —
  the Windows CRT defaults `os.open()` to TEXT mode, which rewrites `\n`→`\r\n` and
  corrupts the tail under `ftruncate`);
- `lseek(0)` → write the full payload → `fsync` (best effort) → `ftruncate` to the exact
  payload length (removes any stale tail).
- The atomic temp + `os.replace` path is unchanged and still preferred; the payload
  format is unchanged (`<unix_ts> <seq>\nstate=…\n`).

The file is now never momentarily empty: a concurrent 1 Hz reader always sees a parseable
first line (previous record or new one). **No `.mq5` change was required.**

## 3. B1 — heartbeat independence (own thread)

- `HeartbeatPublisher` is now lock-guarded (`threading.Lock`) for concurrent writers.
- New `HeartbeatRunner` (`04_SRC/smc/live/heartbeat.py`): a daemon thread that publishes
  every `max(0.05, min(0.5, interval/2))` s, **touching only the heartbeat file, never
  MT5**, so a main poll-thread block (slow MT5 call, multi-second HTF batch) can no longer
  freeze the watchdog sequence. It publishes once immediately on `start()` and logs
  (signature-rate-limited) transient write failures, retrying next tick.
- Wired in `run_operator._build_stack` / `run()` (started after `LiveLoop.start()`), and
  stopped first in `_shutdown()` so the single `state=shutdown` marker written by
  `LiveLoop.stop()` is never overwritten by a late "running" tick.
- The main poll loop keeps its own `maybe_publish` and remains the fail-closed authority
  (`HeartbeatWriteError` there still aborts the session).

## 4. B2 — MT5 auto-reconnect (capped backoff)

- `MT5Connector.is_alive()` — cheap positive liveness probe (`terminal_info() is not
  None`); catches the silent drop where most MT5 calls return `None` with no exception.
- `MT5Connector.reconnect()` — best-effort `shutdown()` reset then `connect()` on the
  **same `terminal_path`**; reuses the same connector (**no second process** for the same
  magic/terminal).
- `run_operator`:
  - the poll loop probes `is_alive()` (only when the connector exposes it — fakes skip it)
    and routes any poll exception through `_attempt_reconnect`;
  - backoff `RECONNECT_BACKOFF_SECONDS = (1, 2, 5)` capped; `RECONNECT_MAX_ATTEMPTS = 10`;
  - after a successful reconnect `_verify_reconnect_gate` re-asserts the same terminal dir
    and (when `require_demo`) a DEMO account — a real mismatch aborts;
  - after `RECONNECT_MAX_ATTEMPTS` consecutive hard failures → `SystemExit` with
    `MAJOR: giving up reconnect after N consecutive failures: …` (non-zero exit).
- Constants live in the live module (`run_operator.py`), **not** `locked_constants`.

## 5. B3 — console noise policy

- New structured one-liners to stdout (and mirrored) for `[poll-error]`,
  `[poll-recovered]`, and `[reconnect] … attempt=n/max … retry_in=…s` /
  `[reconnect] … RECONNECTED`.
- Identical reconnect signatures print at most once per
  `RECONNECT_LOG_INTERVAL_SECONDS = 30` s; a state change always prints. Every line is
  still written to `events.log`.

## 6. B4 — startup banner

`render_startup_banner` gained `heartbeat_path`, `hb_independent`, `auto_reconnect`.
`run_operator.run()` prints the resolved EA-readable heartbeat path plus
`HB independent: YES` and `auto-reconnect: YES` (or `NO`/`n/a`).

## 7. Tests

- `04_SRC/tests/test_perm_hardening.py`:
  - `test_write_in_place_never_exposes_empty_file_to_reader` (Fix A: file is never empty
    at fsync time — exactly the window the old `"w"` opened);
  - `test_write_in_place_removes_stale_tail` (ftruncate to exact length);
  - `test_operator_poll_failure_reconnects_and_resumes` (fake connector; reconnect once,
    counter reset, `MT5 RECONNECTED` in events);
  - `test_operator_reconnect_gives_up_after_max_attempts` (`SystemExit`,
    `MAJOR: giving up reconnect`).
- `04_SRC/tests/test_live_phase7.py`:
  - `test_heartbeat_runner_publishes_independently_of_main_thread`.
- `04_SRC/tests/test_operator_pack.py`:
  - `test_render_startup_banner_reports_heartbeat_and_reconnect`.

**Suite:** 1167 → **1173 passed** (EXIT 0). `locked_constants.py` diff: **empty**.

## 8. Operator soak checklist (no MT5 required to be open for the first two)

1. `python 04_SRC/smc/live/run_operator.py --config config/live_demo.json` (or
   `run_live.bat`) — confirm the banner shows the resolved `smc_heartbeat.txt` path,
   `HB independent: YES`, `auto-reconnect: YES`.
2. Watch `MQL5\Logs\<today>.log` for ≥15 min with the EA attached: expected
   **zero** `heartbeat unreadable` from empty-file windows; `heartbeat healthy again`
   only after a real stale gap.
3. `Get-Content …\MQL5\Files\smc_heartbeat.txt` repeatedly — line 1 must always parse
   (`<epoch> <seq>`) and the seq must climb ~1/s even while the console is quiet.
4. Optional reconnect drill (owner-controlled): close/restart the terminal — expect
   `[reconnect] … attempt=1/10 …` then `RECONNECTED` and poll recovery; a terminal left
   down for all 10 attempts must exit with `MAJOR: giving up reconnect`.

## 9. Out of scope (deferred)

Empty POI / 0-passed-armed STRUCTURE board, marker-zone presence when nothing is armed,
and Mode T enablement are **deferred**; this task makes the heartbeat robust and the
operator self-healing only.
