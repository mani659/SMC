# HEARTBEAT UNREADABLE SILENCE NOTE — LIVE OPS POST-FIX-A AUDIT & DEBOUNCE (2026-10-19)

**Date:** 2026-10-19  
**Authority:** Lead Architect dated ruling 2026-10-19 (EA debounce + rate-limit authorized).  
**Scope:** Live-ops heartbeat reliability, MT5 watchdog EA debounce, alert hygiene.  
**HARD BANS HONORED:**
- No strategy / pillars / triggers / Mode T / `locked_constants.py` changes (`locked_constants.py` diff: EMPTY).
- Watchdog safety is NOT disabled; dead-Python emergency protection remains active.
- `InpStaleTimeoutSec` NOT raised to huge values.
- POI scarcity (armed 0, H4/H1 .../0) is OUT OF SCOPE.

---

## 1. PART 0 — VERIFICATION: WAS FIX A ACTUALLY RUNNING?

### Findings & Evidence:
1. **PID 5332 Lifecycle:**
   - Started at: `2026-10-17 10:31:24 UTC` (PID 5332).
   - In-repo source code modification time for Fix A (`04_SRC/smc/live/heartbeat.py`): `2026-10-17 10:12:10 UTC`.
   - `__pycache__` compiled time: `2026-10-17 10:13:40 UTC`.
   - The live operator process was restarted at `10:31:24 UTC` and **was running the updated code** (Fix A non-truncating `O_RDWR` + `HeartbeatRunner` independent thread B1).
2. **EA Log & Alerts Timeline (2026-10-18 → 2026-10-19):**
   - The operator ran continuously from seq 1 to seq 173,975 (~48 hours unbroken runtime).
   - Alerts recorded in MT5 EA logs:
     - `10-18 00:03:35` (recovered at `00:03:36`, seq 48147)
     - `10-18 03:46:43` (recovered at `03:46:44`, seq 61354)
     - `10-18 04:19:55` (recovered at `04:19:56`, seq 63319)
     - `10-18 08:13:50` (recovered at `08:13:51`, seq 77163)
     - `10-18 08:27:10` (recovered at `08:27:11`, seq 77951)
     - `10-18 09:54:25` (recovered at `09:54:26`, seq 83115)
     - `10-18 12:07:00` (recovered at `12:07:01`, seq 91009)
     - `10-18 13:33:43` (recovered at `13:33:44`, seq 96165)
     - `10-18 18:02:46` (recovered at `18:02:47`, seq 112164)
     - `10-18 19:16:45` (recovered at `19:16:46`, seq 116541)
     - `10-18 19:26:13` (recovered at `19:26:14`, seq 117101)
     - `10-18 20:28:45` (recovered at `20:28:46`, seq 120801)
     - `10-19 01:40:56` (recovered at `01:40:57`, seq 139277)
     - `10-19 03:24:27` (recovered at `03:24:28`, seq 145414)
     - `10-19 03:49:48` (recovered at `03:49:49`, seq 146917)
     - `10-19 09:29:39` (recovered at `09:29:40`, seq 167066)
     - `10-19 09:58:58` (recovered at `09:58:59`, seq 168811)
   - Every single event recovered on the **very next second** (1-tick blip).
   - Python errors in log: 0. Heartbeat writer never hung.
3. **Verdict:**
   - **FIX_A_IN_PROCESS:** **YES**

---

## 2. PART 1 — ROOT CAUSE OF REMAINING "UNREADABLE" ALERTS

### EA Code Path: `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5`
- Line 93–97:
  ```mql5
  if(!ReadHeartbeat(InpHeartbeatFile, hbSec, seq))
  {
     Emergency("heartbeat unreadable");
     return;
  }
  ```
- Line 118–120:
  ```mql5
  int h = FileOpen(fileName, FILE_READ | FILE_TXT | FILE_ANSI);
  if(h == INVALID_HANDLE)
     return (false);
  ```

### Hypotheses Evaluation & Ranking:
- **H3. FileOpen sharing violation / transient lock treated as unreadable (RANK 1 - PRIMARY CAUSE):**
  - In Windows, when Python publishes a heartbeat, Strategy 1 attempts `os.replace(tmp, target)`. Under Windows NT, `MoveFileEx` / `ReplaceFile` acquires a lock requiring delete sharing. If MQL5 `FileOpen(..., FILE_READ)` is called at that millisecond, or if `FileOpen` is held open, `FileOpen` returns `INVALID_HANDLE` (error 5004 / 5002 - sharing violation).
  - Crucially, `ReadHeartbeat()` returns `false` on `INVALID_HANDLE`.
  - The EA previously treated ANY single `false` as an immediate, unconditional `Emergency("heartbeat unreadable")`.
- **H5. EA Alert spam even when next tick is healthy (no debounce) (RANK 2 - CO-PRIMARY CAUSE):**
  - Without any temporal debounce (N=1), a transient sub-millisecond lock collision triggers a full terminal Alert, prints to Experts log, and executes emergency position closing — even though 1 second later the file is completely readable and healthy.
- **H1. Residual empty/partial read (RANK 3 - MITIGATED):**
  - Fix A closed the truncate window. However, when `os.replace` is denied, fallback `_write_in_place` uses `O_RDWR` which never empties the file. But Strategy 1 (`os.replace`) was still attempted first every second.
- **H2. Parse failure (RANK 4 - RULED OUT):**
  - Content on disk is strictly `<unix_ts> <seq>\nstate=running\n`. Tested clean.
- **H4. Wrong file (RANK 5 - RULED OUT):**
  - Path resolves to exact terminal Files directory.

---

## 3. PART 2 — IMPLEMENTATION DETAILS

### P2a. Python (`04_SRC/smc/live/heartbeat.py`)
- Rate-limited and signature-deduplicated fallback logging (`_replace_blocked_signatures`) so in-place fallbacks do not clutter logs.
- Clean temp file unlinking with suppressed sharing errors.
- Added debounce parameters to pure Python specification `evaluate_watchdog` (`consecutive_unreadable`, `unreadable_debounce_ticks`).

### P2b. EA Debounce (`05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5`)
- **Debounce N=3 ticks:**
  - Added `g_consecutiveBadTicks`.
  - A transient unreadable read increments `g_consecutiveBadTicks` and logs to Experts log (`PrintFormat("SMC watchdog: heartbeat unreadable on tick (consecutive=%d/%d)", ...)`).
  - Only when `g_consecutiveBadTicks >= 3` (~3 seconds at 1 Hz timer) does the EA invoke `Emergency("unreadable")`.
  - Any successful read immediately clears `g_consecutiveBadTicks = 0`.
- **Stale Fail-Closed Maintained:**
  - `age > InpStaleTimeoutSec` immediately invokes `Emergency("stale (Ns)")` without debounce, preserving rapid protection against truly dead/hung Python processes.

### P2c. Alert Hygiene & Flood Limits
- **Alert Flood Gate:**
  - Added `ALERT_FLOOD_INTERVAL_SEC = 300` (5 minutes).
  - Alerts are fired on first entry into emergency, and rate-limited to at most once per 5 minutes while emergency remains active.
- **Alert Double Text Cleaned:**
  - Fixed format: `Alert("SMC Safety Watchdog: Python heartbeat ", reason, " — emergency protection active");`
  - In `Emergency()`, reason passed is `"unreadable"` or `"stale (Ns)"`, eliminating redundant `"heartbeat heartbeat"` alert string.

---

## 4. PART 3 — TEST SUITE VERIFICATION
- Pytest suite: **1174 passed** (including new `test_watchdog_decision_unreadable_debounce`).
- Zero diff against `locked_constants.py`.
- No strategy logic changed.
