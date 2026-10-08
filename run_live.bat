@echo off
rem ============================================================
rem SMC Phase D operator pack launcher (single terminal, demo).
rem Usage: double-click or run from the repo root.
rem Ctrl+C stops the session cleanly (heartbeat shutdown marker).
rem ============================================================
setlocal
cd /d "%~dp0"

set CONFIG=config\live_demo.json
set ENTRYPOINT=04_SRC\smc\live\run_operator.py

if not exist "%CONFIG%" (
    echo LAUNCHER ERROR: config not found: %CD%\%CONFIG%
    goto fail
)
if not exist "%ENTRYPOINT%" (
    echo LAUNCHER ERROR: entrypoint not found: %CD%\%ENTRYPOINT%
    goto fail
)

set PYTHON_EXE=python
where %PYTHON_EXE% >nul 2>nul
if errorlevel 1 (
    echo LAUNCHER ERROR: python not found on PATH - activate the project
    echo environment or edit PYTHON_EXE in this launcher.
    goto fail
)

rem No repo venv exists; use the system interpreter. If a venv is added
rem later, activate it here before the entrypoint call.
rem
rem Console cadence: the status board prints once at startup, then every
rem console_refresh_s seconds (default 900 = 15 min in config\live_demo.json).
rem Edit that key to change it; heartbeat, polling, and backend logs are
rem unaffected.

%PYTHON_EXE% "%ENTRYPOINT%" --config "%CONFIG%"
set RC=%errorlevel%
echo.
echo [launcher] operator session exited with code %RC%
if not "%RC%"=="0" goto fail
pause
exit /b 0

:fail
echo.
echo [launcher] see messages above; fix the cause and relaunch.
pause
exit /b 1
