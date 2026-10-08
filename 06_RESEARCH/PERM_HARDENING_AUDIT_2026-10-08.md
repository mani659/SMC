# Independent Audit — PermissionError Operator Hardening

**Date:** 2026-10-08
**Auditor:** Independent verification agent (not the implementer)
**Method:** Re-read the design note, source, tests, and governance docs; ran the focused
operator tests and the full suite; inspected the committed baseline (`git show HEAD:...`)
to separate *proven* changes from narrative.

**Artifacts reviewed**

- Design note: `docs/superpowers/specs/2026-10-08-permission-error-operator-hardening-design.md`
  (committed in `2011d9b`).
- Code: `04_SRC/smc/live/run_operator.py`, `04_SRC/smc/data/mt5_connector.py`,
  `04_SRC/smc/live/loop.py`, `04_SRC/smc/live/heartbeat.py`,
  `04_SRC/smc/live/heartbeat_path.py`.
- Tests: `04_SRC/tests/test_perm_hardening.py`, `test_mt5_connector.py`,
  `test_heartbeat_path.py`, `test_operator_pack.py`, `test_live_phase7.py`,
  `test_console_events.py`, `test_require_demo_gate.py`.
- Governance: `00_LOCKED/SESSION_HANDOFF.md` (2026-10-08 entry), `00_LOCKED/CHANGELOG.md`.

---

## 1. Root-cause honesty

**Classification: HYPOTHESIS_ONLY — correctly stated, but one documentation claim is
stronger than its evidence.**

The tester report supplied no traceback or operation name. Both the design note and the
handoff explicitly say the historical `PermissionError(13)` "cannot be attributed
conclusively." The handoff ranks candidates and labels the `copy_rates_from_pos` path as
"most plausible" (not proven). That is honest and appropriately hedged; no finding here.

**Caveat (documentation overreach).** The handoff's item 2 calls the following *"confirmed
operator code defects"*:

- `_on_poll` calling `symbol_info_tick` / `positions_get` once outside an intended wrapper
  and then again inside it, and
- the MT5 error logger referencing an undefined `mt5`.

These defects are **not present in the committed baseline**. `git show
HEAD:04_SRC/smc/live/run_operator.py` contains **no** `_mt5_call` and **no**
`_log_mt5_error` at all — it calls `self._mt5.symbol_info_tick(cfg.symbol)` (L296) and
`connector.positions_get(cfg.symbol)` (L322) directly, once. The "double call" and
"undefined `mt5`" can therefore only have existed as transient intermediates created *and*
removed inside this same uncommitted change. Presenting them as pre-existing confirmed
defects overstates the evidence. This does **not** change the runtime root-cause verdict
(which remains not-proven), but the wording should be corrected.

## 2. Instrumentation

**PASS.**

- Poll-path MT5 reads are each wrapped exactly once: `_on_poll` calls
  `self._mt5_call("symbol_info_tick", ...)` and `self._mt5_call("positions_get", ...)`. No
  direct `self._mt5.<api>()` data calls remain (only `self._mt5 = connector._mt5()` and the
  guarded `self._mt5.last_error()` inside `_log_mt5_error`).
- On failure the operator logs `operation=mt5.<name>`, `terminal_path`, `python_pid`,
  `error=`, `last_error=`, and a real traceback
  (`exc_info=(type(exc), exc, exc.__traceback__)`).
- The connector's `_call` boundary logs `operation`, `terminal_path`, `python_pid`,
  `error`, `last_error`, and `exc_info=True`, and re-raises a `PermissionError` as
  `MT5CallError` carrying operation + terminal path.
- Heartbeat write errors carry the operation step ("write temporary file" /
  "replace heartbeat target") and the full target + temp paths.
- The earlier undefined-`mt5` defect is gone: `_log_mt5_error` uses `self._mt5` and guards
  the `last_error()` call against a second failure.
- `PermissionError` is never silently swallowed: poll reads record one loud error and set
  the display value to unknown (`spread=None`, `open_positions=None`), the connector
  re-raises, heartbeat failures terminate the session.

**Minor:** `_mt5_call` catches `(OSError, ValueError)`. A `ValueError` (e.g. a genuine
bad-argument programming error) is folded into the same non-fatal "IPC blip" path and
returned as `None`, which can mask a real bug as an "unknown" display value. Narrowing to
`OSError` (which already covers `PermissionError`/`MT5CallError`) would be safer.

## 3. Policy — fail-closed heartbeat, dedup & recovery

**HEARTBEAT_FAIL_CLOSED: PASS.**

- Startup (`_build_stack`) write-probes each candidate in order
  (`terminal_data_path` → install-dir → config → project default). If **all** probes fail,
  it raises `SystemExit` before polling. Unwritable candidates log a warning and fall
  through.
- Runtime: `write_heartbeat` raises `HeartbeatWriteError(PermissionError)`; `run_once` →
  heartbeat publish propagates it; `OperatorSession.run` catches `HeartbeatWriteError`
  **before** the generic handler, records the error, and raises `SystemExit`. No stale
  heartbeat is reported as healthy.
- Fallback outside the live data-folder sandbox sets `_heartbeat_ea_readable = False` and
  the board shows `running (EA path unconfirmed)`; a loud warning is logged. Fallback
  writeability and EA visibility are treated as separate facts — as the design requires.

**DEDUP_AND_RECOVERY: PASS.**

- `_mt5_call` → `_log_mt5_error` appends exactly one `state["errors"]` entry per distinct
  `(type, str)` signature per operation; identical repeats are `debug`-suppressed. Success
  pops the signature and logs `MT5 CALL RECOVERED`.
- The poll loop similarly dedups with `_last_poll_error_signature` and logs `POLL RECOVERED`.
- `read_heartbeat` dedups read failures and logs recovery — intentional fail-closed at the
  watchdog level.

**No undefined names in error paths:** verified — no bare `mt5` remains.

## 4. Concurrency

- Guidance, not hard enforcement: startup logs
  `MT5 STARTUP terminal_path=... python_pid=...; use one active Python owner per terminal`,
  and `connect()` logs the initialize attempt with path + PID. Identity facts and
  `identity.json` carry `mt5_python_pid`.
- No formal one-process API rule is asserted; the handoff correctly cites MetaQuotes'
  `initialize()` docs as describing connection setup only. No lock was invented. This
  matches the committed design.

## 5. Tests

**PASS (with one coverage caveat).**

- Focused: `pytest tests/test_perm_hardening.py tests/test_mt5_connector.py
  tests/test_heartbeat_path.py tests/test_operator_pack.py tests/test_live_phase7.py -q`
  → **74 passed**.
- Full suite (`python -m pytest -q` from `04_SRC`) → **914 passed, 0 failed** in ~2.8 s.
  This matches the handoff's "74 focused / 914 full" claim exactly.
- Tests exercise the real call path, not just error-string bookkeeping:
  `_session` drives the real `_on_poll`/`identity_check`/`run`; the connector test drives
  real `MT5Connector.copy_rates`; heartbeat tests drive `write_heartbeat`/`read_heartbeat`.
  `test_operator_positions_read_is_called_once_and_unknown_on_error` pins
  `call_count == 1`; `test_operator_poll_deduplicates_permission_and_continues` pins one
  error across three polls plus recovery.
- **Coverage gap:** no live-MT5 test exists (CI cannot run a terminal). The real
  permission fault has never been reproduced here — the tests are fake-based only, as the
  design specifies. This is the residual risk behind the ship advice.

## 6. Regressions

- `dry_run` / `require_demo` / identity-dir mismatch gates are unchanged; the DEMO gate and
  dir comparison still run in `identity_check` and `test_require_demo_gate.py` passes.
- Event-driven console is intact (`test_console_events.py` passes); no return to timed
  full-repaint spam.
- Heartbeat still prefers the EA-readable data-folder `MQL5/Files` target; the fallback is
  explicitly marked EA-unconfirmed.
- One connector is reused after identity validation (`self._connector or MT5Connector(...)`),
  so `LiveLoop.start()` does not trigger a second `initialize`.
- `git diff -- 04_SRC/smc/config/locked_constants.py` → **empty**.

## 7. Findings

**MAJOR (1)**

1. **The hardened connector is not under version control.** `04_SRC/smc/data/` (including
   `mt5_connector.py`) and `04_SRC/smc/live/heartbeat_path.py` are **untracked** (and not
   ignored), as is `04_SRC/tests/test_perm_hardening.py`. This removes any committed
   baseline for the connector: `git diff` cannot show what the hardening changed, the work
   is not recoverable from history, and an independent audit of the connector relies on the
   working tree alone. Commit the live data/connector package (and the new tests) before
   distributing.

**MINOR (4)**

2. Design note / handoff present the double-call and undefined-`mt5` defects as
   "confirmed" pre-existing code defects, but the committed baseline never contained
   `_mt5_call`/`_log_mt5_error`. Correct the wording to "transient intermediates during
   implementation."
3. `_mt5_call` swallows `ValueError` as non-fatal, which can mask a real programming error
   as an unknown display value. Prefer catching `OSError` only.
4. The `CHANGELOG.md` has **no 2026-10-08 entry** for this hardening (the handoff and the
   design note were updated; the changelog was not). Governance requires every change to be
   recorded here.
5. Residual by design: when the EA-readable data-folder path is unwritable but the local
   `logs/phase_d` fallback is writable, startup proceeds with `_heartbeat_ea_readable=False`.
   The watchdog then cannot see the heartbeat and will fail-closed (emergency close) while
   the bot keeps trading. This matches the committed design's "loud fallback" ruling and is
   disclosed on the board, but it is a real watchdog-blind window worth stating plainly.

**CRITICAL (0).** No safety hole found; no fix was applied during this audit.

## Residual risks (not soft-pedaled)

- The historical `PermissionError(13)` was never reproduced; the operation that raised it is
  still unknown. Ship with that disclosure and inspect `events.log` on the next tester run.
- No live-terminal test exists, so wrapper behavior under real `MetaTrader5` IPC is
  unverified here.
- Connector and new tests are uncommitted (MAJOR-1).
- Watchdog-blind fallback window (MINOR-5).

---

```
AUDIT_STATUS: PASS_WITH_CAVEATS
ROOT_CAUSE_CLAIM: HYPOTHESIS_ONLY
INSTRUMENTATION: PASS
HEARTBEAT_FAIL_CLOSED: PASS
DEDUP_AND_RECOVERY: PASS
DOUBLE_CALL_BUGS: FIXED
SUITE: 914 passed / 0 failed
LOCKED_CONSTANTS_DIFF: empty
SHIP_ADVICE: ship_with_disclosure
CRITICAL: 0
MAJOR: 1
MINOR: 4
TOP_FINDINGS: [1. Hardened MT5 connector (04_SRC/smc/data/) and heartbeat_path.py plus test_perm_hardening.py are untracked/unversioned — no committed baseline, so the connector diff cannot be audited and the work is unrecoverable from history. 2. Handoff/design assert the double _on_poll call and the undefined mt5 logger as "confirmed" pre-existing defects, but HEAD run_operator.py contains no _mt5_call/_log_mt5_error at all — they were transient intermediates within this change (root cause correctly remains HYPOTHESIS_ONLY). 3. No CHANGELOG entry for the 2026-10-08 hardening; minor over-broad ValueError swallowing in _mt5_call; and the disclosed watchdog-blind fallback window when only the non-EA-readable path is writable.]
REPORT_PATH: 06_RESEARCH/PERM_HARDENING_AUDIT_2026-10-08.md
LOGIC_CHANGED: NO
```
