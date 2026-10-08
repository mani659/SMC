# PermissionError Operator Hardening Design

**Date:** 2026-10-08
**Scope:** Diagnose and harden `PermissionError(13, "Access is denied")` in the live MT5 operator.

## Evidence and current classification

The tester report does not contain a traceback or operation name, so it cannot establish which call raised the reported exception. The current code does, however, contain instrumentation defects that prevent reliable attribution:

- `OperatorSession._on_poll` makes `symbol_info_tick` and `positions_get` calls before invoking `_mt5_call`, then invokes them a second time. The unwrapped first call can raise before the intended handling runs.
- `_log_mt5_error` refers to an undefined `mt5` name when obtaining `last_error()`.
- Execution and HTF rates are fetched through `LiveLoop` and `MT5Connector.copy_rates`; failures reach the generic poll catch without an operation label or terminal path.
- The generic poll catch appends every failure to the error list and retries after a delay, with no duplicate suppression or recovery indication.
- Heartbeat writes use a temporary file and replace, with the target path in most wrapped `OSError` messages. A runtime write failure is nevertheless caught as a generic poll error and retried; startup also logs when every candidate probe fails but does not explicitly abort there.
- `test_perm_hardening.py` currently simulates accumulated error strings instead of invoking the actual failing wrapper/call paths.

The heartbeat path is resolved from the live `terminal_info().data_path` first, then terminal-install derivation, configured path, and a project-local fallback. The EA's installed-terminal sandbox is `<terminal data path>/MQL5/Files/`; a project-local fallback can be writable without being visible to the EA. Such a fallback must be reported as not watchdog-readable, not as a healthy heartbeat.

Severity depends on the operation:

| Operation | Classification |
| --- | --- |
| `initialize`, `terminal_info`, `account_info`, or symbol selection during identity/startup | Breaking: do not start without verified terminal/account identity. |
| Execution `copy_rates` | Non-fatal to the process for one transient poll; that poll cannot process newly fetched bars. Attribute it and show recovery. |
| HTF `copy_rates` | A missing required series prevents the product batch; do not silently arm with incomplete HTF input. Preserve the runtime's existing refusal policy. |
| `symbol_info_tick`, `positions_get` used for display | Non-fatal to polling; mark the affected status unknown/stale and log once per distinct failure. |
| Heartbeat file write | Breaking to watchdog protection: stop the session if publication fails; never represent it as fresh or silently keep trading without heartbeat publication. |

## Approaches considered

1. **Recommended: repair and complete the in-progress hardening.** Wrap the actual MT5 calls, eliminate duplicate bypass calls, add contextual and deduplicated diagnostics, preserve polling after transient market-data/observability failures, and fail closed when heartbeat publication is unavailable.
2. **Abort on every `PermissionError`.** Simple but turns transient read-side IPC blips into unnecessary session termination.
3. **Logging-only change.** Does not address error inflation, the bypassed wrapper, the undefined `mt5` reference, or heartbeat failure semantics.

Approach 1 is approved.

## Design

### MT5 call attribution and recovery

- Attribute each call at its boundary, including the public operation (`initialize`, `copy_rates` / `copy_rates_from_pos`, `symbol_info`, `symbol_info_tick`, `positions_get`, and identity calls), configured terminal executable path, current Python PID, and MT5 `last_error()` where obtainable.
- Preserve exception tracebacks in the diagnostic log for exceptions that escape an operation boundary; do not replace a concrete operation with a success-shaped `None`.
- Invoke each poll-time read once. A non-fatal read failure returns through the existing poll-resilience path only after it is recorded.
- Deduplicate repeated identical failures rather than appending one new operator error per poll. Emit an explicit recovery event when the failed operation succeeds again. Keep initialization/identity failures fatal.
- Record whether later polling resumes; a read-side IPC exception must not make the board claim that the failed read succeeded.

### Heartbeat behavior

- Keep the authoritative live target under `<terminal data path>/MQL5/Files/smc_heartbeat.txt`; retain ordered writable candidates only as a loud startup fallback.
- Include the operation and full target path in write failures. A startup with no writable destination aborts before polling. A runtime heartbeat write failure terminates the session rather than being swallowed by the generic retry loop.
- If a writable fallback is outside the EA's terminal data sandbox, state explicitly that watchdog visibility is unavailable; do not label it a healthy watchdog heartbeat.

### Concurrency and startup logging

- Log configured terminal executable path and Python PID before initialization and include both in session/identity artifacts.
- Recommend one active Python owner per terminal session to avoid competing IPC clients. The official MetaQuotes `initialize()` documentation describes establishing a connection and optionally launching the terminal; it does not state a formal one-process-per-terminal prohibition. This is therefore operational guidance, not a claimed package guarantee.
- Do not add a lock or stale-lock recovery mechanism in this change; the current evidence does not establish a safe cross-process lock protocol, and separate terminals are not a conflict.

### Validation

Add fake-based tests that exercise the real wrapped call path and assert:

- A `PermissionError` identifies the exact function and terminal path, includes `last_error` when available, and increments the operator error state only once while repeated.
- A later successful call is recorded as recovery and polling continues after a transient rates/read failure.
- `symbol_info_tick` and `positions_get` are each called once per poll.
- An MT5 initialization/identity error prevents startup.
- Heartbeat resolution prefers the terminal data-folder `MQL5/Files` path; failed startup probes or a later write denial produce an explicit path-bearing error and stop the session.
- No strategy thresholds, trading policy, or `locked_constants.py` are changed.

## Self-review

- No placeholder requirements remain.
- The fail-closed choice applies specifically to heartbeat/watchdog availability; transient read-side MT5 errors remain recoverable as approved.
- Fallback writeability and EA visibility are treated as separate facts.
- The work is limited to operational diagnostics, error counting, heartbeat reliability, tests, and the session handoff.
