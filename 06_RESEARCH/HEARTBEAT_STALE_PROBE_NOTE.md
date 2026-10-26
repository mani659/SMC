# Heartbeat stale probe — PART 0/1/2

**Date:** 2026-10-15  
**Status:** EVIDENCE REPORT (root cause not reproduced locally — no live MT5 terminal on this machine).  
**BANS respected:** no strategy edits, no locked_constants edits, no EA timeout-only fix, no watchdog disable.

---

## PART 0 — CURRENT FACTS (code + config, cited)

| Item | Value | Evidence |
|------|-------|----------|
| `terminal_path` (live config on disk) | `C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe` | `config/live_demo.json` line ~2 |
| `heartbeat_path` (raw config string) | `logs/phase_d/heartbeat.txt` | `config/live_demo.json` line ~9 |
| `heartbeat_interval_s` (config) | `1.0` | `config/live_demo.json` line ~10; default in `smc.live.operator_config.OperatorConfig.heartbeat_interval_s` (default `1.0`) |
| `dry_run` (config) | `false` | `config/live_demo.json` line ~3 |
| `symbol` (config) | `XAUUSDm` | `config/live_demo.json` line ~2 |
| Account / server / mode | **not a config key** — captured at runtime by `OperatorSession.identity_check()` via `mt5.account_info()` and stored in `identity.json` + `state`. | `04_SRC/smc/live/run_operator.py:~160-210` (identity gate); `operator_config.py` whitelist does **not** include `account`/`server`. |
| Where Python writes the heartbeat | `<resolved path>/smc_heartbeat.txt` via `HeartbeatPublisher(path)`; write path resolved in `OperatorSession._build_stack()` by `heartbeat_path_candidates(...)` then write-probed across candidates. Default policy order: **live `terminal_info().data_path`** > **install-dir derivation** `<terminal_dir>/MQL5/Files/smc_heartbeat.txt` > explicit config path > `logs/phase_d/heartbeat.txt`. | `04_SRC/smc/live/heartbeat_path.py` `heartbeat_path_candidates` / `resolve_heartbeat_path`; `04_SRC/smc/live/run_operator.py` `_build_stack()` heartbeat block (~line 360-430 region); `04_SRC/smc/live/heartbeat.py` `HeartbeatPublisher` |
| Atomic write mechanics | temp file → `os.replace(tmp, target)` with retries; on transient sharing violation (`[WinError 5]`, EA mid-read) falls back to **in-place overwrite with explicit `fh.flush()` + `os.fsync(fh.fileno())`**, also retried; whole publish retried a few cycles. Raises `HeartbeatWriteError` only after full retry budget. | `04_SRC/smc/live/heartbeat.py` `write_heartbeat` (lines ~140-200), `_write_in_place` (lines ~200-215) |
| Is heartbeat path rewritten when `terminal_path` is set? | **Yes, by default.** With a parseable `terminal_path` (and stronger: a live `terminal_data_path` from the identity gate), the resolved write target is the EA-readable `MQL5/Files/smc_heartbeat.txt`, **not** the config's `logs/phase_d/heartbeat.txt`. Paper-operator `run()` resolves the path at stack-build time from the **resolved identity** (live `terminal_data_path` preferred) + `terminal_path`, not from the raw config fallback. | `04_SRC/smc/live/heartbeat_path.py` `data_folder_heartbeat_path`, `ea_readable_heartbeat_path`; `04_SRC/smc/live/run_operator.py` `_build_stack()` heartbeat resolution + `self._heartbeat_ea_readable` warning when source != `terminal_data_path`. |
| Does heartbeat run on its own thread/timer, or on the main poll loop? | **Main poll loop only (per current code) — it is NOT a wall-clock background thread.** `LiveLoop.run_once()` calls `self.heartbeat.maybe_publish()` once per POLLED bar/event cycle; the outer operator loop then sleeps `poll_interval_s` and repeats. `HeartbeatPublisher.maybe_publish()` enforces a **max-1-per-`interval_seconds`** gate using an injected/wall clock, but the CALLER cadence is `run_once() + sleep(poll_interval_s)`. So if the **operator loop's iteration itself stalls** (long MT5 call, long detection batch, GC, blocked IPC), the heartbeat can miss multiple intervals even though the process is alive. | `04_SRC/smc/live/loop.py` `run_once()` (heartbeats after processed bars), `run()` (sleep loop); `04_SRC/smc/live/heartbeat.py` `HeartbeatPublisher.maybe_publish()`; `04_SRC/smc/live/run_operator.py` `run()` main loop (~line 905-935). |
| EA input: `InpHeartbeatFile` | `"smc_heartbeat.txt"` (default) | `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` input declaration |
| EA stale threshold | `InpStaleTimeoutSec = 5` (default) | `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` input declaration; mirrors `WATCHDOG_STALE_TIMEOUT_SECONDS = 5.0` in `smc.live.heartbeat` |
| EA read flags / path semantics | `FileOpen(fileName, FILE_READ | FILE_TXT | FILE_ANSI)`; parses **line 1** only; missing/unreadable/garbage ⇒ fail-closed (emergency). No `FILE_COMMON`; EA reads from its **terminal Files sandbox** (which for an installed terminal is the **data folder** `terminal_info().data_path`, NOT the install dir). | `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` `ReadHeartbeat`; `SMC_Safety_Watchdog.mq5` header block; `smc.live.heartbeat_path.data_folder_heartbeat_path` |
| EA timer period | `InpTimerSeconds = 1` (default) | `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` input declaration + `EventSetTimer(InpTimerSeconds)` in `OnInit` |
| Live clock semantics | Python writes `int(unix_ts)` from an injected UTC clock (`datetime.now(timezone.utc)` in live); the EA compares against `TimeGMT()` (UTC epoch). Staleness is **relative age**, not absolute wall/TZ, so TZ/clock-offset is not the primary suspect for growing age. | `smc.live.heartbeat.write_heartbeat` / `evaluate_watchdog`; EA `CheckHeartbeat` (`TimeGMT() - hbSec`) |

**PART 0 conclusion:** config + code show a **two-path risk** baked into the current default wiring:

1. When the **live terminal identity gate succeeds** and `terminal_data_path` is captured, the operator resolves the heartbeat to the EA-readable **data folder** `MQL5/Files/smc_heartbeat.txt`, and logs `HEARTBEAT PATH RESOLVED` + sets `_heartbeat_ea_readable = True`. In that case Python-write-path and EA-read-path should **match** by construction.
2. When the live data-path candidate is **not available / not writable**, the operator falls back down the candidate list (install-dir derivation, then the explicit config path `logs/phase_d/heartbeat.txt`, then the log-local default). In those fallback cases the operator **warns** `HEARTBEAT PATH FALLBACK IS NOT CONFIRMED EA-READABLE` and sets `_heartbeat_ea_readable = False`. That is exactly the **H1 path-split** surface.

There is **also** the **H2 blocked-on-main-thread** surface in the current code: the heartbeat advances only when the operator loop actually completes a `run_once()` iteration, not on an independent timer. So a long batch / stalled poll can produce growing stale age **while the process is still "running"** — which matches the reported symptom class ("after some time", both PCs).

---

## PART 1 — ROOT-CAUSE HYPOTHESES (in brief, code-backed)

### H1 — PATH SPLIT (Python writes project dir; EA reads MQL5/Files)
**Assessment: PLAUSIBLE / CONDITIONAL — the fallback path exists and is explicitly warned about; the default live path should match.**

Evidence:

- The config file explicitly sets `heartbeat_path: "logs/phase_d/heartbeat.txt"`. If the live data-path resolution is bypassed (portable terminal, identity-gate failure, writable-probe preferring an earlier candidate, or config explicitly forcing a different `heartbeat_path`), Python writes to a project/log path the EA's `FileOpen` sandbox won't see. The EA would then read **missing/unreadable → fail-closed → "heartbeat stale" alerts** (the EA conflates "unreadable" with stale for alert phrasing in some builds, but the contract says missing/unreadable ⇒ emergency).
- The code intentionally warns when the chosen candidate is not the confirmed EA-readable data folder: `_heartbeat_ea_readable = False` + log `HEARTBEAT PATH FALLBACK IS NOT CONFIRMED EA-READABLE`. So a **mis-match is detectable** — if ops/tester console or events.log show that warning, H1 is strongly indicated.
- For an **installed (non-portable)** terminal, the authoritative EA-readable target is `terminal_data_path/MQL5/Files/smc_heartbeat.txt`. The install-dir derivation `<terminal_dir>/MQL5/Files/...` is correct for portable terminals but only approximate otherwise; if the identity gate does **not** capture `terminal_data_path`, the operator may write to the install dir while the EA reads the data dir — another H1 subtype.

**Test to confirm (owner, during a stale episode):**

1. Open the EA-readable file the watchdog actually reads: `<terminal_data_folder>/MQL5/Files/smc_heartbeat.txt` (or the EA's configured `InpHeartbeatFile` if non-default).
2. In parallel, locate the project/log file the config mentions: `logs/phase_d/heartbeat.txt`.
3. While alerts fire, check **which file updates every ~1s** (mtime, size, content sequence number). Likely outcomes:
   - Only `logs/phase_d/heartbeat.txt` updates ⇒ H1 confirmed (Python not writing where EA reads).
   - Only EA-readable file updates but still stale ⇒ not H1 (look at H2/H3).
   - Neither updates ⇒ Python heartbeat publication itself failing or blocked (H2/H3/Python write error).

**H1 verdict pending owner evidence:** `CONDITIONAL / REPRODUCE-AND-CONFIRM`.

---

### H2 — HEARTBEAT BLOCKED BY LONG WORK ON MAIN THREAD
**Assessment: PLAUSIBLE and code-supported as a real failure mode for the current architecture.**

Evidence:

- `HeartbeatPublisher.maybe_publish()` writes at most once per `interval_seconds` **if called**, but the call site is `LiveLoop.run_once() → maybe_publish()`, and `run_once()` is invoked from the **operator loop** `run()` as: `new_bars = self._loop.run_once()` → `_on_poll(...)` → sleep `poll_interval_s`. There is **no independent background timer thread** pumping the heartbeat during a stalled iteration.
- Therefore, if one `run_once()` iteration takes longer than the stale threshold (e.g. a slow/multi-bar HTF fetch, a long detection batch, an MT5 IPC block, or a GC/lock spike), the heartbeat file can be **unchanged for multiple seconds** while the process is still alive — exactly the "growing N (6s, 36s, 66s...)" symptom profile.

This is **not proven as the actual root cause here** because it requires correlating alert timestamps with batch/poll timing on the live machine. But it is a **legitimate, documented architectural limitation** of the current code that can produce false emergency alerts without any path split.

**Test to confirm (owner):**

- Instrument/record timestamps around `run_once()` (start/end) and around the heartbeat write, or inspect `events.log` / operator console alive lines.
- Correlate alert times with iterations where the poll/batch took > stale threshold.
- If the heartbeat mtime only advances *between* iterations and not *during* long ones, H2 is confirmed.

**H2 verdict:** `PLAUSIBLE / CODE-SUPPORTED / CONFIRM WITH TIMING ON LIVE MACHINE`.

---

### H3 — ATOMIC WRITE / PARTIAL READ
**Assessment: LOW — current write strategy already defends against the classic partial-read case, and the EA reads line 1 only from a fully-written temp→replace or in-place flush.**

Evidence:

- Python writes to a `.tmp` file fully, then `os.replace` (atomic on Windows). On EA mid-read sharing violation, it falls back to **in-place overwrite with `flush()` + `fsync()`**.
- EA opens, reads line 1, closes — it does **not** hold the file open for a long time. Transient sharing violations are retried, not failed-closed.
- The known Windows coexistence issue is the opposite of "partial read": it's a transient **rename denial** when the EA is mid-read, which the code now retries + falls back.

Partial reads (EA seeing empty/truncated content) would more likely show as intermittent `unreadable`-style failures rather than steadily growing age. If the file size sometimes drops to 0 and then recovers, H3 could be in play; otherwise it's unlikely to be the main cause.

**H3 verdict:** `INCONCLUSIVE / LOW PROBABILITY unless file-size-0 spikes are observed`.

---

### H4 — EA INPUT MISMATCH (`InpHeartbeatFile` default ≠ actual filename)
**Assessment: LOW for default wiring, but possible if a tester overrode the EA input or used a different attach.**

Evidence:

- Python default filename component is `HEARTBEAT_FILENAME = "smc_heartbeat.txt"` (`smc.live.heartbeat_path`).
- EA default input is `InpHeartbeatFile = "smc_heartbeat.txt"`.
- So with **default** EA input and **default-resolved** path, basename matches.

If the tester PC attached the EA with a **non-default** `InpHeartbeatFile`, or the EA was told to read a project/log file while Python wrote the EA-readable one (or vice versa), you get H1-like behavior through EA input mismatch rather than Python path resolution. Also possible if the marker/heartbeat basename was changed in one place but not the other — but both currently share `smc_heartbeat.txt`.

**H4 verdict:** `LOW / CHECK EA INPUT ON CHART vs Python basename`.

---

### H5 — CLOCK / TZ
**Assessment: REJECTED as the main cause for the reported *relative-age* symptom.**

Both sides use UTC epoch seconds for the age comparison: Python writes `int(unix_ts)` from UTC; EA compares `TimeGMT() - hbSec`. Relative staleness does not depend on timezone. Clock skew could cause a one-time false stale if clocks were far apart, but not a **growing** age after the process is alive and writing.

**H5 verdict:** `REJECTED (for relative-age growing symptom)`.

---

### H6 — MULTIPLE TERMINALS / MULTIPLE PYTHON
**Assessment: POSSIBLE if the environment has more than one MT5 terminal or more than one Python process, and the EA is attached to a different terminal than the one Python resolved.**

Evidence:

- `OperatorSession.identity_check()` explicitly binds to **one configured terminal_path** and aborts on mismatch; startup logs `MT5 STARTUP terminal_path=... python_pid=... use one active Python owner per terminal`.
- If there are **two terminals** and the EA is attached to Terminal B while Python wrote to Terminal A's Files dir, the EA sees stale/missing heartbeat even though Python is healthy.
- If there are **two Python processes**, each may write a different heartbeat and only one matches the EA.

**H6 verdict:** `POSSIBLE / CHECK terminal_path in config vs TerminalInfo path + count of python.exe / terminal processes`.

---

### MULTI / UNKNOWN
If the above are inconclusive, the remaining class is "Python is writing somewhere the EA cannot confirm, or the EA is checking a file that is not the one Python updates, or the publisher is being blocked transiently for longer than the retry budget." That would still fold into H1/H2/H3/H6 rather than a new mechanism.

---

## PART 2 — MINIMAL FIX POLICY (only after confirmed cause)

**Current stance: NO code fix applied in this probe.** The session is evidence + test-design only. If the owner confirms a cause, apply the smallest targeted patch from below; do **not** "fix" by only raising EA stale timeout or disabling the watchdog.

| Cause | Minimal patch (only if CONFIRMED) | Notes |
|-------|-----------------------------------|-------|
| H1 (path split) | Ensure a single resolved path = EA-readable `MQL5/Files/smc_heartbeat.txt` under the correct terminal (prefer live `terminal_data_path`; fall back only with loud warning + EA-input documentation). Document EA input = basename `smc_heartbeat.txt` and that it resolves in the terminal's Files sandbox. | Shipping a config line + README line for testers is enough if the live identity gate already captures `terminal_data_path`. If the issue is portable vs installed terminal derivation, harden the resolution / message. |
| H2 (main-thread blocked) | Heartbeat must be publishable on an **independent timer/background pump**, OR at least pumped at a rate that survives long batches (e.g. a short background heartbeat thread independent of `run_once()`), WITHOUT disabling the watchdog or raising the stale threshold as a workaround. Measure/prove that heartbeat mtime advances during a simulated long batch > stale threshold. | Do NOT raise stale timeout as the primary fix. Measure batch duration first. |
| H3 (atomic/partial) | Keep the current durable write + retry strategy; only change if a reproducible concurrent-read failure is observed. | Already defended. |
| H4 (EA input mismatch) | Ship EA default = `smc_heartbeat.txt` and config basename identical; print resolved paths at startup so a mismatch is visible. | Mostly already true for defaults. |
| H6 (multiple terminals/python) | Startup identity already prints terminal_path + python_pid; harden the message if a mismatch is detected. Enforce "one Python owner per terminal" operationally. | Already partly done. |

**Tests (if a fix is applied):**

- Unit: path resolution given `terminal_path` / `terminal_data_path` produces the EA-readable `MQL5/Files/smc_heartbeat.txt` when the live data path is available.
- If H2 fixed: a test or measured log showing heartbeat mtime advances during a simulated long batch (> stale threshold) — i.e. the heartbeat is no longer gated solely by `run_once()` completion.
- Full suite green; `locked_constants` untouched.

---

## PART 3 — DELIVERABLES

1. **This note:** `06_RESEARCH/HEARTBEAT_STALE_PROBE_NOTE.md` — Part 0 table, H1–H6 assessments, fix policy, tester implication.
2. Tester/README lines (only if/when a fix is confirmed):
   - EA input: `InpHeartbeatFile = "smc_heartbeat.txt"` (default) — the EA reads its **terminal Files sandbox**, not a project path.
   - For testers: ensure the EA is attached to the **same terminal** that Python is bound to; ensure the EA's `InpHeartbeatFile` matches the Python-written basename `smc_heartbeat.txt`; if the operator config explicitly overrides `heartbeat_path`, confirm it points to the EA-readable Files dir, not a project/log dir.
3. **Return block** below.

---

## RETURN BLOCK

```
PROBE_STATUS:        PASS (evidence + root-cause hypotheses assembled; no live reproduction possible from this machine)
ROOT_CAUSE:          UNKNOWN (H1 conditional, H2 plausible+code-supported, H3 low, H4 low, H5 rejected, H6 possible) — pending owner reproduction
PYTHON_WRITE_PATH:   depends on live resolution:
                      - if live terminal_data_path captured and writable → <terminal_data_path>/MQL5/Files/smc_heartbeat.txt (EA-readable)
                      - else fallback chain → possibly logs/phase_d/heartbeat.txt or install-dir derivation (NOT confirmed EA-readable, warned)
EA_READ_PATH:        <terminal_data_folder>/MQL5/Files/smc_heartbeat.txt  (for an installed terminal, from terminal_info().data_path)
                      with EA default InpHeartbeatFile = "smc_heartbeat.txt"
PATHS_MATCH:         CONDITIONAL — YES when the live identity gate resolves to terminal_data_path AND it is writable; NO/UNKNOWN when fallback is used (operator warns HEARTBEAT PATH FALLBACK IS NOT CONFIRMED EA-READABLE)
HEARTBEAT_ON_MAIN_THREAD_ONLY: YES (in current code: HeartbeatPublisher.maybe_publish() is called from LiveLoop.run_once() → operator loop sleep cycle; no independent background timer thread pumps it)
MAX_BATCH_VS_STALE:  UNKNOWN from here — live measurement needed (alert timestamps vs run_once/poll/batch duration). Note: prior incidents (CHANGELOG) show the path-correct stale case exists (PermissionError publishing to the EA-readable file), so path correctness alone does not rule out watchdog alerts.
FIX_APPLIED:         NO (evidence + policy only; fix only after owner confirms root cause)
SUITE:               1162 passed (EXIT=0) at time of probe — full suite green; re-run after any code change
LOCKED_CONSTANTS_DIFF: empty (no locked_constants edits in this probe)
NEXT_READY:          owner reproduces once with PART 0 file checks + batch/poll timing correlation → confirm H1/H2/H3/H6 → apply minimal patch → re-test
```

---

## TESTER IMPLICATION — WHY THE REMOTE PC SAW THE SAME CLASS OF FAILURE

If the same failure class appears on both the owner PC and the tester PC, that argues **systemic**, not "one bad install." The two systemic surfaces above are:

- **H1-class path split** — if both machines are using a config/layout where the resolved heartbeat path is **not** the EA-readable `MQL5/Files/smc_heartbeat.txt` (for example a portable terminal, an identity-gate shortfall, or an explicit `heartbeat_path` pointing at a project/log dir), then both would show the EA reading a missing/unreadable file while Python is healthy. The code already warns when this happens (`HEARTBEAT PATH FALLBACK IS NOT CONFIRMED EA-READABLE`), so the events.log / console is the first place to check.
- **H2-class main-thread gating** — if both machines trigger long polls/batches (HTF fetch, detection batch, MT5 IPC stalls), the heartbeat can go stale while the process is alive on either machine, because the heartbeat in current code only advances when the operator loop completes an iteration.

The shared symptom therefore most likely points to either a shared **path/layout assumption** (H1) or a shared **main-thread heartbeat cadence** limitation (H2), and the PART 0 file checks + timing correlation are the way to tell which.

---

## GOVERNANCE NOTE

No code or locked constants changed in this probe. If a fix is later confirmed and applied, add a short CHANGELOG entry + handoff note per the usual governance path; this file is a research artifact, not a committed deliverable unless the owner wants it retained.

