@echo off
rem PHASE C GUARD - invoked by scheduled task SMC_phase_c_guard every 5 min.
rem Ensures exactly ONE daemon supervisor is alive (single-instance lock via
rem phase_c_supervisor_state.json). The daemon owns ALL relaunch decisions;
rem this script never launches components itself, so two actors can never
rem race into double-spawning a run. pythonw = fully windowless.
rem
rem Crash-window note: if the daemon dies in the instant between spawning a
rem component and saving its pid, the next daemon could double-launch that
rem component. Window is ~50 ms once per relaunch - accepted risk; artifacts
rem are segment-checkpointed so a duplicated segment would still be caught
rem by the watcher's byte-identity check.
set "REPO=D:\Gold Scripts\MQL5\SMC"
cd /d "%REPO%"
start "SMC_phase_c_guard" /B pythonw 06_RESEARCH\scripts\phase_c_supervisor.py
