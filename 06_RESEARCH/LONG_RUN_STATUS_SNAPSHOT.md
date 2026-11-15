# LONG-RUN STATUS SNAPSHOT — coupled_mtf full-menu diagnostic

**Classification (FINAL, 2026-11-01T07:15Z): COMPLETE** — python chain exited normally overnight.

## Final state
- `exit_reason.json`: `ALL_DONE_PASS`, exit_code **0**, timestamp 2026-10-31T21:54:22Z.
- run1 DONE 2026-10-31T15:48:15Z · run2 DONE 2026-10-31T21:54:22Z · both **35,725 / 35,725** frozen M5 bars, final bar `2025-11-30T23:55:00Z`, **2,953 events each**.
- Assemble: **PASS** — determinism PASS: `candidates.json` byte-identical across runs (independently hashed, SHA `31d4a736…`), `checkpoint_events.jsonl` byte-identical, run.json semantic identity True.
- `chain_stderr.log` EMPTY; no `ALERT_FAILURE.txt`; `ALERT_COMPLETION.txt` = "ALL DONE — PASS · Total: 12.1h | Determinism: PASS".
- Process: NONE (clean exit; stale heartbeat is expected post-exit).

## Results package
- Brief: `06_RESEARCH/FULL_MENU_DIAG_RESULTS_BRIEF.md` (executive tables + canonical paths + residuals).
- Primary artifact: `06_RESEARCH/results/coupled_mtf_full_menu_diag/summary.json` (chain-assembled combine).
- Funnel headline: 1,901 sweeps → 1,052 candidates → 693 placed / 443 filled; winners F 955 / A 97 / D 0; DAY 0; Def-B 0. **Diagnostic only, not performance / not edge.**

## Check history
- 2026-10-31 10:47Z — ALIVE_WORKING (run1 replay-to-checkpoint, replay reached ~14,298/15,500; PID 10356 heartbeat fresh; observe-only).
- 2026-10-31 17:19Z — RUNNING (run1 DONE 15:48Z; run2 at 19,000/35,725 bars, ~2.6 bars/s).
- 2026-11-01 07:15Z — **COMPLETE** (final; see above).
- 2026-11-01 08:19Z→14:39Z — Fill-leg CAPTURE pass in SEPARATE tree `06_RESEARCH/results/coupled_mtf_fill_leg_capture/` (logging-only instrumented runner; funnel counters identical 693 placed / 443 filled / 443 exits; diag `coupled_mtf_full_menu_diag/**` NOT touched, no force_rerun, no wipe). See SESSION_HANDOFF 2026-11-01 (3).

```text
CHECK_STATUS: PASS
PROCESS: COMPLETE (clean exit; PID history: 10356)
RUN1: bars=35725/35725 last_ts=2025-11-30T23:55:00Z DONE=Y events=2953
RUN2: bars=35725/35725 last_ts=2025-11-30T23:55:00Z DONE=Y events=2953
HEARTBEAT_AGE_MIN: stale-expected (process exited 2026-10-31T21:54Z)
STDERR_EMPTY: YES
DONE: run1=Y run2=Y assemble=Y
ACTION_TAKEN: NONE
SAFE: YES
```
