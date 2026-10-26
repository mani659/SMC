"""PHASE C SUPERVISOR — auto-relaunch watchdog for the 5-year baseline pair.

Incident 2026-09-16: the in-flight pair + verdict watcher died silently with
the machine's session (~16:45 local — no reboot, no crash record, no OOM,
session-level suspend/termination fingerprint via the watcher's freeze/resume
signature) and stayed dead ~19 h until manual relaunch. This supervisor makes
that recovery automatic.

What it does, every CHECK_INTERVAL_S:
  1. Verifies run1 / run2 / watcher are alive (recorded PID present as a
     python process AND its Windows start-time FileTime matches the recorded
     one — guards against PID reuse).
  2. Relaunches any dead component with its exact recorded command as a
     DETACHED_PROCESS (children outlive this supervisor; the runner's
     manifest-fingerprint resume makes restarts cheap and deterministic).
  3. Force-restarts a component whose process is alive but whose log has
     been silent > STALE_LOG_KILL_S (wedged), after a post-relaunch grace.
  4. Completion-aware: never relaunches a run whose merged/summary.json
     exists, nor the watcher once phase_c_verdict.json exists; exits cleanly
     when the whole Phase C package is complete.

Deployment net (defense in depth):
  - this process runs detached (pythonw) with a single-instance lock,
  - a Windows scheduled task ("SMC_phase_c_guard", every 5 min) re-invokes
    phase_c_guard_hidden.vbs, which runs phase_c_guard.bat in a fully hidden
    window (wscript style 0) — no console flash — and the bat starts a
    supervisor if none is alive,
  - phase_c_guard_hidden.vbs also sits in the user's Startup folder (logon
    cover, also hidden).

Audit log: 06_RESEARCH/results/phase_c_supervisor.log (one line per cycle).
All real output goes to the audit log — the script never depends on stdout
(pythonw has none).

Usage:
  adopt already-running processes, then run one check and exit:
    python 06_RESEARCH/scripts/phase_c_supervisor.py --adopt RUN1_PID RUN2_PID WATCHER_PID --once
  fresh daemon start (nothing running or state lost):
    pythonw 06_RESEARCH/scripts/phase_c_supervisor.py
  single check then exit:
    python 06_RESEARCH/scripts/phase_c_supervisor.py --once

Removal after Phase C closes:
    schtasks /Delete /TN SMC_phase_c_guard /F
    delete phase_c_guard_hidden.vbs and phase_c_guard.bat from this folder,
    and phase_c_guard_hidden.vbs from the Startup folder.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "06_RESEARCH" / "results"
STATE_PATH = RESULTS / "phase_c_supervisor_state.json"
SUPERVISOR_LOG = RESULTS / "phase_c_supervisor.log"

CHECK_INTERVAL_S = 300        # one verification cycle every 5 minutes
STALE_LOG_KILL_S = 7200       # alive but log silent 2 h -> force restart
RELAUNCH_GRACE_S = 900        # skip staleness kill for 15 min after a relaunch
CREATE_NO_WINDOW = 0x08000000  # console-less child: no window flash when spawned from pythonw
DETACHED = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW


def _log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    if sys.stdout is not None:
        print(line, flush=True)
    with SUPERVISOR_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _filetimes(pids: list[int]) -> dict[int, int | None]:
    """Windows process start times as FileTime ints; None = not found."""
    out: dict[int, int | None] = {}
    if not pids:
        return out
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        f"Get-Process -Id {','.join(map(str, pids))} | "
        "ForEach-Object { Write-Output ('{0} {1}' -f $_.Id, $_.StartTime.ToFileTime()) }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=30,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {pid: None for pid in pids}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit():
            out[int(parts[0])] = int(parts[1])
    for pid in pids:
        out.setdefault(pid, None)
    return out


def _python_pids() -> set[int]:
    """PIDs of every python.exe / pythonw.exe process (tasklist, no WMI)."""
    try:
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=30,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    pids: set[int] = set()
    for row in csv.reader(proc.stdout.splitlines()):
        if len(row) >= 2 and row[0].lower().rsplit(".", 1)[0] in ("python", "pythonw"):
            try:
                pids.add(int(row[1]))
            except ValueError:
                continue
    return pids


def _child_exe() -> str:
    """The console python.exe sibling of this interpreter (pythonw-safe)."""
    exe = Path(sys.executable)
    sibling = exe.with_name("python.exe")
    return str(sibling) if sibling.exists() else str(exe)


COMPONENTS: dict[str, dict] = {
    "run1": {
        "argv_tail": [
            "06_RESEARCH/scripts/phase_c_baseline_backtest.py",
            "--tag", "run1",
            "--out-root", "06_RESEARCH/results/phase_c_baseline_run1",
        ],
        "log": RESULTS / "phase_c_baseline_run1.log",
        "done": lambda: (RESULTS / "phase_c_baseline_run1" / "merged" / "summary.json").exists(),
    },
    "run2": {
        "argv_tail": [
            "06_RESEARCH/scripts/phase_c_baseline_backtest.py",
            "--tag", "run2",
            "--out-root", "06_RESEARCH/results/phase_c_baseline_run2",
        ],
        "log": RESULTS / "phase_c_baseline_run2.log",
        "done": lambda: (RESULTS / "phase_c_baseline_run2" / "merged" / "summary.json").exists(),
    },
    "watcher": {
        "argv_tail": ["06_RESEARCH/scripts/phase_c_verdict.py"],
        "log": RESULTS / "phase_c_verdict_watcher.log",
        "done": lambda: (RESULTS / "phase_c_verdict.json").exists(),
    },
}
ORDER = ("run1", "run2", "watcher")


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _launch(key: str, state: dict) -> None:
    """Start component `key` fully detached; record pid + start FileTime."""
    spec = COMPONENTS[key]
    with spec["log"].open("ab") as fh:
        proc = subprocess.Popen(
            [_child_exe(), *spec["argv_tail"]],
            cwd=str(REPO_ROOT),
            stdout=fh,
            stderr=subprocess.STDOUT,
            creationflags=DETACHED,
            close_fds=True,
        )
    pid = proc.pid
    time.sleep(3.0)  # let the process come up so StartTime is queryable
    ft = _filetimes([pid]).get(pid)
    state[key] = {"pid": pid, "filetime": ft, "launched_at": time.time()}
    _log(f"[RELAUNCH] {key} -> pid {pid} (filetime {ft})")


def _alive(key: str, state: dict, ppids: set[int], fts: dict[int, int | None]) -> bool:
    entry = state.get(key)
    if not entry:
        return False
    pid = entry.get("pid")
    if pid not in ppids:
        return False
    recorded = entry.get("filetime")
    return recorded is None or fts.get(pid) == recorded


def _cycle(state: dict) -> None:
    """One verification pass over all components (relaunch/kill as needed)."""
    ppids = _python_pids()
    known_pids = [state[k]["pid"] for k in ORDER if state.get(k, {}).get("pid")]
    fts = _filetimes(known_pids)
    for key in ORDER:
        spec = COMPONENTS[key]
        done = spec["done"]()
        alive = _alive(key, state, ppids, fts)
        entry = state.get(key, {})
        if done:
            _log(f"[done] {key}: artifacts complete (process alive={alive}) — no relaunch")
            continue
        if not alive:
            _log(f"[DEAD] {key} (pid {entry.get('pid')}) — relaunching")
            _launch(key, state)
            continue
        age_min = (time.time() - spec["log"].stat().st_mtime) / 60 if spec["log"].exists() else 999.0
        launched_ago = time.time() - entry.get("launched_at", 0)
        if age_min * 60 > STALE_LOG_KILL_S and launched_ago > RELAUNCH_GRACE_S:
            _log(f"[STALE] {key} alive but log silent {age_min:.0f} min — killing pid {entry['pid']}")
            subprocess.run(
                ["taskkill", "/F", "/PID", str(entry["pid"])],
                capture_output=True, timeout=30,
                creationflags=CREATE_NO_WINDOW,
            )
            time.sleep(2.0)
            _launch(key, state)
        else:
            _log(f"[ok] {key} pid={entry['pid']} log_age={age_min:.1f} min")


def _other_supervisor_alive(state: dict) -> bool:
    sup = state.get("supervisor")
    if not sup:
        return False
    mine = os.getpid()
    if sup.get("pid") == mine:
        return False
    fts = _filetimes([sup["pid"]])
    recorded = sup.get("filetime")
    alive = sup["pid"] in _python_pids() and (
        recorded is None or fts.get(sup["pid"]) == recorded
    )
    return alive


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase C auto-relaunch supervisor")
    parser.add_argument("--adopt", nargs=3, metavar=("RUN1_PID", "RUN2_PID", "WATCHER_PID"),
                        help="record already-running component PIDs instead of launching")
    parser.add_argument("--once", action="store_true", help="one check cycle, then exit")
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    state = _load_state()

    if _other_supervisor_alive(state):
        _log(f"[exit] supervisor already alive (pid {state['supervisor']['pid']}) — nothing to do")
        return

    if args.adopt:
        ppids = _python_pids()
        fts = _filetimes([int(p) for p in args.adopt])
        for key, raw in zip(ORDER, args.adopt):
            pid = int(raw)
            spec = COMPONENTS[key]
            if pid in ppids:
                state[key] = {"pid": pid, "filetime": fts.get(pid), "launched_at": time.time()}
                _log(f"[adopt] {key} pid={pid} (filetime {fts.get(pid)})")
            else:
                _log(f"[adopt] {key} pid={pid} NOT alive — launching fresh")
                _launch(key, state)

    # take/refresh the single-instance lock
    my_ft = _filetimes([os.getpid()]).get(os.getpid())
    state["supervisor"] = {"pid": os.getpid(), "filetime": my_ft}
    _save_state(state)
    _log(f"[start] supervisor pid={os.getpid()} mode={'once' if args.once else 'daemon'}")

    while True:
        _cycle(state)
        state["supervisor"] = {"pid": os.getpid(), "filetime": my_ft}
        _save_state(state)
        complete = all(spec["done"]() for spec in COMPONENTS.values())
        if complete:
            _log("[complete] merged summaries + verdict present — supervisor exiting. "
                 "Cleanup: schtasks /Delete /TN SMC_phase_c_guard /F")
            return
        if args.once:
            return
        time.sleep(CHECK_INTERVAL_S)


if __name__ == "__main__":
    main()
