"""PARALLEL BOOKS — FULL-YEAR BT STATUS (read-only, one-shot, never relaunches).

Prints the answer to "is the detached year run still going, and how far?":

    PID alive?   |  runs_done/24  |  last heartbeat  |  verdict present?  |  EXIT_CODE

Reads only these artifacts (all gitignored) under the results dir:

    pid.txt         harness PID written at launch
    heartbeat.json  {phase, run, runs_done, runs_total, utc, alive}  (20 s refresh)
    verdict.json    written by the last run when every check passes
    EXIT_CODE.txt   written on process exit (0 = all checks passed)
    */.done         one marker per finished run (12 segments x 2 hypotheses = 24)

It does not execute, resume or touch the harness: no file is written, no
process is started or stopped, and it is safe to run while the backtest is
replaying (the 20 s heartbeat means a value can lag by up to 20 s; that is fine).

Usage (from the repo root, or from this scripts/ dir — paths resolve either way):

    python 06_RESEARCH/scripts/parallel_books_full_bt_status.py
    python 06_RESEARCH/scripts/parallel_books_full_bt_status.py --out <results-dir>
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path

EXPECTED_RUNS = 24  # 12 adjacent calendar-month segments x 2 direction hypotheses
STILL_ACTIVE = 259  # GetExitCodeProcess sentinel for a live process


def _default_out() -> Path:
    # 06_RESEARCH/scripts/parallel_books_full_bt_status.py -> <repo>/06_RESEARCH/results/...
    here = Path(__file__).resolve()
    research = here.parent.parent
    return research / "results" / "parallel_books_full_bt"


def pid_alive(pid: int) -> bool:
    """True if the PID exists, without signalling or killing it."""
    if pid <= 0:
        return False
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            # Access denied still means the process exists.
            return kernel32.GetLastError() == 5
        try:
            code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _read_json(path: Path) -> dict | None:
    raw = _read_text(path)
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only status of the full-year parallel-books BT.")
    ap.add_argument("--out", default=None, help="results dir (default: 06_RESEARCH/results/parallel_books_full_bt)")
    args = ap.parse_args(argv)

    out = Path(args.out).expanduser().resolve() if args.out else _default_out()
    if not out.is_dir():
        print(f"results dir not found: {out}")
        print("STATUS: NO_ARTIFACTS (the run was never launched here)")
        return 0

    pid_txt = _read_text(out / "pid.txt") or ""
    try:
        pid = int(pid_txt.splitlines()[0].strip())
    except (ValueError, IndexError):
        pid = 0

    alive = pid_alive(pid) if pid else False

    hb = _read_json(out / "heartbeat.json") or {}
    runs_total = hb.get("runs_total") or EXPECTED_RUNS
    runs_done_hb = hb.get("runs_done")
    done_markers = sorted(out.glob("*/*/.done"))  # <segment>/<run>/.done

    verdict = _read_json(out / "verdict.json")
    verdict_ok = None if verdict is None else bool(verdict.get("pass"))
    exit_txt = _read_text(out / "EXIT_CODE.txt")
    exit_code = None
    if exit_txt:
        try:
            exit_code = int(exit_txt.splitlines()[0].strip())
        except (ValueError, IndexError):
            exit_code = None

    if verdict is not None and exit_code == 0:
        status = "COMPLETE (PASS)"
    elif verdict is not None and exit_code is not None and exit_code != 0:
        status = "COMPLETE (FAIL - checks did not all pass)"
    elif alive:
        status = "IN_FLIGHT"
    elif not pid and not hb and not done_markers:
        status = "NO_RUN_ARTIFACTS (nothing launched in this dir)"
    else:
        status = "DEAD / INCOMPLETE (no successful verdict)"

    hb_utc = hb.get("utc") or "-"
    hb_phase = hb.get("phase") or "-"
    hb_run = hb.get("run") or "-"

    print("PARALLEL BOOKS - FULL-YEAR BT STATUS (read-only)")
    print(f"results dir : {out}")
    print(f"PID         : {pid or '-'}  (pid.txt)")
    print(f"ALIVE       : {'YES' if alive else 'NO'}")
    print(f"runs_done   : {runs_done_hb if runs_done_hb is not None else '-'}/{runs_total}"
          f"   (.done markers: {len(done_markers)}/{EXPECTED_RUNS})")
    print(f"heartbeat   : {hb_utc}   phase={hb_phase}  run={hb_run}  alive={hb.get('alive')}")
    if done_markers:
        per_seg: dict[str, int] = {}
        for marker in done_markers:
            seg = marker.parent.parent.name
            per_seg[seg] = per_seg.get(seg, 0) + 1
        print("finished    : " + ", ".join(f"{seg} {n}/2" for seg, n in per_seg.items()))
    print(f"verdict.json: {'PRESENT (pass={})'.format(verdict_ok) if verdict is not None else 'absent'}")
    print(f"EXIT_CODE   : {exit_code if exit_code is not None else 'absent'}")
    print(f"STATUS      : {status}")
    if status == "IN_FLIGHT":
        print("NOTE        : this script only observes; it never resumes or kills the run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
