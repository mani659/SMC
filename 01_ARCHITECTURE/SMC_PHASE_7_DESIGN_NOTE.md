# Phase 7 — Live Readiness + MQL5 Safety Watchdog — Design Note

Status: COMPLETE (all 519 tests green — 510 pre-existing + 9 new Phase 7 tests)
Architecture: **Option A locked** — Python owns ALL trading logic; MQL5 is ONLY a Safety Watchdog (no entry logic, no trade management, no strategy code in MQL5).

---

## 1. Heartbeat transport (file — why, and the exact format)

**Transport: a single plain-text FILE** (`smc_heartbeat.txt`, configurable). Redis was considered and rejected for V1 — the project has no Redis deployment and the MQL5 EA cannot read Redis without a third-party socket library. A file both sides can see is the least-movable contract, and the EA reads it with `FileOpen(..., FILE_READ|FILE_TXT|FILE_ANSI)` — zero dependencies.

**Format (stable — the EA parses line 1 only):**

```
<unix_epoch_seconds> <monotonic_sequence>
state=<running|shutdown>
```

- `unix_epoch_seconds` — UTC epoch written by Python's (injected) clock; the EA compares it against `TimeGMT()` (also UTC epoch). Timezone rule: **both sides use UTC** — no server/local time confusion.
- `sequence` — monotonically increasing writer counter (observability: operators can confirm the writer is alive and progressing).
- `state` — `running` while the loop is alive; `shutdown` written once on a CLEAN stop. The watchdog does NOT read it — it is operator-only diagnostics.

**Wiring:** Python writes to `LiveConfig.heartbeat_path`; the EA reads the same file from the terminal's `MQL5\Files\` directory (`InpHeartbeatFile`). For demo, point the Python path at `<terminal_data>\MQL5\Files\smc_heartbeat.txt` (or set both sides to `FILE_COMMON`-style paths). Writes are atomic-ish (temp file + rename) so the EA never reads a torn record.

**Fail-closed:** missing, unreadable, or garbage heartbeat == stale. A dead Python cannot write a fresh heartbeat, and a corrupted file is no safer to trust — the watchdog must act on anything it cannot positively confirm.

## 2. Timeout values (UNFROZEN operational defaults — not trading thresholds)

| Value | Default | Where |
|---|---|---|
| Heartbeat interval | 1 s | `smc/live/heartbeat.py` (`HEARTBEAT_INTERVAL_SECONDS`), `LiveConfig.heartbeat_interval` |
| Watchdog stale timeout | 5 s | `smc/live/heartbeat.py` (`WATCHDOG_STALE_TIMEOUT_SECONDS`), `LiveConfig.watchdog_timeout`, EA `InpStaleTimeoutSec` |
| EA timer period | 1 s | EA `InpTimerSeconds` |
| Bar poll interval | 0.5 s | `LiveConfig.poll_interval` |
| Detection window | 200 bars | `LiveConfig.window_bars` |

The project had no existing heartbeat constants — these are new, documented as **UNFROZEN operational timing** (not risk thresholds, so the "thresholds only from `locked_constants`" rule is untouched).

## 3. Live loop structure (`smc/live/loop.py` — `LiveLoop`)

Composition, not a rewrite — the same frozen stack as backtest/paper:

```
connector (MT5Connector or fake)
  → poll new closed bars (execution timeframe, copy_rates_from_pos)
  → rolling detection window (200 bars) → DetectionDriver.validate_window
       → arm ONLY newly-passed POIs into the engine
         (episode exists → never re-armed; §24 arm-bar + §11 one-shot stay)
  → PaperRunner.run_one_cycle(bar) — the M6 bar-close cycle with the REAL
       PipelineAdapter (scan → risk gate → broker limit) over the REAL
       OrderManager/PositionManager
  → HeartbeatPublisher.maybe_publish() every iteration (interval-bounded)
```

- **One engine, one §5 machine** — the driver validates into `adapter.engine` (the I1 single-machine guarantee holds live).
- **Integration contract order:** `start()` connects (refuses on failure) → `run_once()` per poll: new bars → validate/arm → one cycle → heartbeat. `run()` is the blocking loop (`run_once` + poll-interval sleep until `stop()`).
- **Cold start:** the first poll only records the latest bar timestamp; history is NOT replayed through the live cycle — only genuinely NEW closed bars (after startup) are processed.
- **Determinism:** `run_once()` is the testable seam (no sleep, no wall clock beyond the heartbeat's injected clock); bar timestamps come from the connector.

## 4. MQL5 Safety Watchdog EA (`05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5`)

**Responsibilities (MAY):**
- `OnTimer` (1 s) checks heartbeat freshness (`TimeGMT() − unix_ts > timeout`);
- stale/unreadable → **close ALL scoped positions at market** + **delete ALL scoped pending orders** + `Print`/`Alert` (emergency re-asserts at most every 30 s while stale);
- scoping: `InpMagicFilter` (0 = all) and `InpSymbolFilter` ("" = all);
- healthy heartbeat → **no trading actions whatsoever**.

**Responsibilities (MUST NOT — enforced by code review against this list):**
- no POI detection, no validation, no entries, no PureRunner/FVG management, no session/news/risk policy, no lot sizing, no strategy logic of any kind. The EA contains no strategy code — only the heartbeat decision + emergency flatten.

**Contract fidelity:** the EA implements exactly the tested Python decision `smc.live.heartbeat.evaluate_watchdog` (healthy → no action; stale → emergency; unreadable → emergency). The Python function is the reviewable spec; a change to one must be mirrored in the other (comment in both files).

## 5. Clean-shutdown behaviour

`LiveLoop.stop()` stops polling and writes a `state=shutdown` heartbeat. The watchdog does NOT distinguish clean shutdown from death — **both leave the heartbeat stale and trigger the emergency flatten** (fail-closed; a stopped Python cannot protect the account, so the watchdog must). The `shutdown` marker exists so operators can tell the two apart when reviewing logs; the safety behaviour is identical.

## 6. Manual EA validation checklist (EA code does not run in pytest)

1. **Attach on demo:** attach `SMC_Safety_Watchdog` to a demo chart with `InpStaleTimeoutSec=5`, `InpTimerSeconds=1`, `InpSymbolFilter=XAUUSD.x` (or ""), `InpMagicFilter` matching the Python `LiveConfig.magic` (or 0).
2. **Place the heartbeat file** at the terminal's `MQL5\Files\smc_heartbeat.txt` (write it manually first: `<epoch> 1` + `state=running`).
3. **Healthy path:** confirm the EA prints NOTHING and touches no positions/orders while the file is fresh (refresh the file every < 5 s, or run the Python loop).
4. **Stale path:** stop updating the file (or remove it). Within `InpStaleTimeoutSec` + timer period the EA must: close all scoped positions, delete all scoped pendings, print `SMC watchdog EMERGENCY (heartbeat stale...)`, and raise the Alert. Keep a dummy demo position + pending order to observe both actions.
5. **Recovery:** restore a fresh heartbeat → EA prints "heartbeat healthy again" and takes no further action.
6. **Unreadable path:** write garbage content → same emergency as stale (fail-closed).
7. **Scoping:** with `InpMagicFilter` set, a position with a different magic must NOT be closed.
8. **Restore the Python loop** and confirm the end-to-end file contract (Python writes every ~1 s, EA stays silent).

## 7. Files created / modified

| File | Change |
|---|---|
| `04_SRC/smc/live/config.py` | NEW — `LiveConfig` (demo-first defaults) + `live_config_from_dict` |
| `04_SRC/smc/live/heartbeat.py` | NEW — file format, publisher, staleness, `evaluate_watchdog` (EA spec) |
| `04_SRC/smc/live/loop.py` | NEW — `LiveLoop` (poll → driver validate/arm → PaperRunner cycle → heartbeat) |
| `04_SRC/smc/live/__init__.py` | placeholder → real API |
| `04_SRC/smc/orchestration/detection_driver.py` | `validate_window` (validate WITHOUT arming) extracted; `run` delegates |
| `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` | NEW — Safety Watchdog EA (heartbeat + emergency flatten only) |
| `04_SRC/tests/test_live_phase7.py` | NEW — 9 tests (heartbeat format/freshness, watchdog decision, publisher interval, live loop over fake connector, config) |
| `01_ARCHITECTURE/SMC_PHASE_7_DESIGN_NOTE.md` | this note |

## 8. Residual risks / Phase 7 limitations (documented, nothing faked)

- **EA not executed in CI** — MQL5 cannot run in pytest; the DECISION is tested in Python (`evaluate_watchdog`) and the EA is a thin mirror. Manual checklist (section 6) is the gate before any real-money/demo trust.
- **File transport requires co-location** — Python and the terminal must share the heartbeat file (same machine / shared path). Remote/VPS deployments need a shared mount or a transport change (later milestone).
- **Clock skew** — the EA compares `TimeGMT()` against Python-written UTC epoch; both UTC by contract, but a misconfigured system clock makes staleness wrong in one direction only (EA guards negative age by clamping to 0 — fail-safe, not fail-stale).
- **M8 HTF provisioning** — the live driver is fed the execution-timeframe window only; M8 emits nothing live until its D1/H4 series are wired (documented V1 limitation; registry registers M8 regardless).
- **No production alerting** (Telegram/email) — out of scope per brief; the EA's `Alert`/`Print` is the V1 surface.
- **O(bars²) per-bar window rescan** — accepted for the 200-bar demo window (perf redesign is a non-goal).
- **`connector.connect()` vs `initialize()`** — the live loop uses the real `MT5Connector.connect()` API; `PaperRunner.start()` (fake-`initialize()` convention) is not the loop's entry point (documented in the loop).