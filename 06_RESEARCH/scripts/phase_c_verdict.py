"""POST-V1 PHASE C — determinism-pair verdict (post-run verification).

Waits for the two segmented 5-year baseline runs (run1/run2, launched
detached) to finish, then verifies the Phase C completion criteria
against the artifacts:

  1. Coverage: merged bars_processed == the full canonical bar count
     (full available period processed — no segment skipped).
  2. Determinism: merged trades.csv + report.json byte-identical
     between the runs; merged summary.json identical excluding the
     runtime fields (recursive strip — runtime fields live nested in
     the funnel dict).
  3. Invariants: the merged summary carries the per-segment invariant
     verdicts — PASS requires exactly {"all_segments": "OK"}.
  4. Trigger D = 0 (A5 ruling binding).

Writes 06_RESEARCH/results/phase_c_verdict.json and prints a summary.
Read-only with respect to the run artifacts.

Run from the repo root:

    python 06_RESEARCH/scripts/phase_c_verdict.py [--nowait]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "06_RESEARCH" / "results"
RUNS = ("phase_c_baseline_run1", "phase_c_baseline_run2")
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"

# Runtime-only fields excluded from the cross-run summary comparison
# (timing is not deterministic); the strip is RECURSIVE — the Phase B
# pair false-FAILED when the strip was top-level-only while
# runtime_seconds lives nested inside funnel.
RUNTIME_FIELDS = {"runtime_seconds", "bars_per_second"}


def load_merged_summary(run: str) -> dict:
    with open(RESULTS / run / "merged" / "summary.json", encoding="utf-8") as handle:
        return json.load(handle)


def run_done(run: str) -> bool:
    """Complete iff the runner wrote the MERGED summary (its final action)."""
    return (RESULTS / run / "merged" / "summary.json").exists()


def canonical_bar_count() -> int:
    frame = pd.read_parquet(PARQUET, columns=["timestamp"])
    return len(frame)


def log_stalled(run: str) -> bool:
    log = RESULTS / f"{run}.log"
    if not log.exists():
        return True
    age_min = (time.time() - log.stat().st_mtime) / 60
    # Segment progress lines print every 2000 bars; at the calibrated
    # deep-prefix steady state a line lands at most every ~15 min, and a
    # segment LOAD + run can add quiet minutes. 60 min = generous without
    # masking a real crash for long.
    return age_min > 60


def wait_for_runs() -> None:
    while True:
        pending = [r for r in RUNS if not run_done(r)]
        if not pending:
            return
        stalled = [r for r in pending if log_stalled(r)]
        if stalled:
            print(f"[abort] no log growth for 60 min and no merged summary: "
                  f"{', '.join(stalled)} — run crashed? Inspect the logs.", flush=True)
            raise SystemExit(3)
        print(f"[wait] still running: {', '.join(pending)} — sleeping 15 min", flush=True)
        time.sleep(900)


def _strip_runtime(obj: object) -> object:
    if isinstance(obj, dict):
        return {k: _strip_runtime(v) for k, v in obj.items() if k not in RUNTIME_FIELDS}
    if isinstance(obj, list):
        return [_strip_runtime(v) for v in obj]
    return obj


def summary_equal_ex_runtime(a: dict, b: dict) -> list[str]:
    a, b = _strip_runtime(a), _strip_runtime(b)
    diffs: list[str] = []
    for key in sorted(set(a) | set(b)):
        if json.dumps(a.get(key), sort_keys=True) != json.dumps(b.get(key), sort_keys=True):
            diffs.append(key)
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nowait", action="store_true", help="verify now; do not wait")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not args.nowait:
        wait_for_runs()
    missing = [r for r in RUNS if not run_done(r)]
    if missing:
        print(f"[abort] merged summaries missing: {', '.join(missing)}", flush=True)
        return 3

    verdict: dict = {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": {}}
    ok = True

    s1, s2 = load_merged_summary(RUNS[0]), load_merged_summary(RUNS[1])

    # 1. Coverage: merged bars == canonical bars; all segments present.
    expected_bars = canonical_bar_count()
    for run, s in ((RUNS[0], s1), (RUNS[1], s2)):
        bars = s["window"]["bars_processed"]
        full = bars == expected_bars
        verdict["checks"][f"{run}_bars"] = bars
        verdict["checks"][f"{run}_covers_full_period"] = full
        ok = ok and full

    # 2. Byte-identical merged exports.
    for name in ("trades.csv", "report.json"):
        a = (RESULTS / RUNS[0] / "merged" / name).read_bytes()
        b = (RESULTS / RUNS[1] / "merged" / name).read_bytes()
        same = a == b
        verdict["checks"][f"byte_identical_{name}"] = same
        ok = ok and same

    # 3. Merged summary identical ex-runtime.
    diffs = summary_equal_ex_runtime(s1, s2)
    verdict["checks"]["summary_identical_ex_runtime"] = not diffs
    if diffs:
        verdict["checks"]["summary_diff_keys"] = diffs
    ok = ok and not diffs

    # 4. Invariants: per-segment verdicts must be exactly all-OK.
    invariants = s1["invariants"]
    bad = {k: v for k, v in invariants.items() if v != "OK"}
    verdict["checks"]["invariants_bad"] = bad
    ok = ok and not bad

    # 5. Trigger D = 0 (any D-prefixed trigger key).
    d_trades = sum(v for k, v in s1["by_trigger_trades"].items()
                   if k.startswith("D"))
    verdict["checks"]["trigger_d_trades"] = d_trades
    d_ok = d_trades == 0
    verdict["checks"]["trigger_d_zero"] = d_ok
    ok = ok and d_ok

    verdict["metrics"] = {
        "n_trades": s1["metrics"]["n_trades"],
        "win_rate": s1["metrics"]["win_rate"],
        "net_pnl": s1["metrics"]["net_pnl"],
        "profit_factor": s1["metrics"]["profit_factor"],
        "max_drawdown": s1["metrics"]["max_drawdown"],
        "by_trigger_trades": s1["by_trigger_trades"],
    }
    verdict["verdict"] = "PASS" if ok else "FAIL"
    verdict["criteria"] = {
        "full_period_processed": all(
            verdict["checks"][f"{r}_covers_full_period"] for r in RUNS
        ),
        "determinism_byte_identical": (
            verdict["checks"]["byte_identical_trades.csv"]
            and verdict["checks"]["byte_identical_report.json"]
        ),
        "invariants_all_ok": not bad,
        "trigger_d_zero": d_ok,
    }

    out = RESULTS / "phase_c_verdict.json"
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(verdict, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
