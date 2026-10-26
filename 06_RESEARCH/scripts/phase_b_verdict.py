"""POST-V1 PHASE B — determinism-pair verdict (post-run verification).

Waits for the two full-October runs (run1/run2, launched detached) to
finish, then verifies the plan §4 exit criteria against the artifacts:

  1. Determinism: trades.csv + report.json byte-identical between runs;
     summary.json identical excluding the two runtime fields.
  2. All summary invariants OK (no_fill_after_expiry, one_shot_per_poi,
     fill_at_limit_price, trigger_d_zero, no_poi_trades_twice,
     be_once_per_trade, bars_processed_nonzero).
  3. Both runs PASS (script exit logic) and bars_processed nonzero.
  4. Funnel non-zero-or-explained: every stage counter > 0 or its reason
     is stated in FUNNEL_EXPLANATIONS below.

Writes 06_RESEARCH/results/phase_b_verdict.json and prints a summary.
Read-only with respect to the run artifacts.

Run from the repo root:

    python 06_RESEARCH/scripts/phase_b_verdict.py [--nowait]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "06_RESEARCH" / "results"
RUNS = ("phase_b_run1", "phase_b_run2")

# Every funnel counter the plan §4 requires to be non-zero OR explained.
# Reasons mirror the report's §3 explanation column — keep in sync.
FUNNEL_EXPLANATIONS = {
    "expired_section23": "give-up backstop (Trigger A 20 M5 bars) binds before §23 (M1=30); counted under expired_give_up",
    "violated_pulls": "no armed POI was VIOLATED while a limit rested in-window; VIOLATED→pull tested by unit tests",
    "hard_cancelled_news": "news_events=[] — §11 dormant by default (plan §9, stated in every report)",
    "friday_closes": "in-window positions never open at Friday 20:00 UTC (CloseKind count over closed trades)",
    "positions_still_open": "end-of-window book position, not a throughput stage: 0 = flat at the final bar (every position closed in-window), which is the expected clean state",
}

# Fields excluded from the summary.json cross-run comparison.
RUNTIME_FIELDS = {"runtime_seconds", "bars_per_second"}

# A run is "stalled" when its log has not grown for this long AND its
# summary.json is absent. Sized from the backtest's progress cadence: it
# prints one [progress] line per 500 bars with flush=True, so at the measured
# full-window steady state (~0.44 bars/s, ~2.3 s/bar) lines land every
# ~19-21 min. 45 min = >2x headroom without masking a real crash for long.
# (The original 20-min value false-aborted at 17:29 on 2026-09-12 for
# exactly this reason while both runs were healthy.)
STALL_MINUTES = 45


def load_run(name: str) -> dict:
    with open(RESULTS / name / "summary.json", encoding="utf-8") as handle:
        return json.load(handle)


def run_done(run: str) -> bool:
    """A run is complete iff the backtest script wrote its summary.json
    (its final artifact action). Platform-independent."""
    return (RESULTS / run / "summary.json").exists()


def log_stalled(run: str) -> bool:
    log = RESULTS / f"{run}.log"
    if not log.exists():
        return True
    age_min = (time.time() - log.stat().st_mtime) / 60
    return age_min > STALL_MINUTES


def wait_for_runs() -> None:
    while True:
        pending = [r for r in RUNS if not run_done(r)]
        if not pending:
            return
        stalled = [r for r in pending if log_stalled(r)]
        if stalled:
            print(f"[abort] no log growth for {STALL_MINUTES} min and no summary: "
                  f"{', '.join(stalled)} — run crashed? Inspect the logs.", flush=True)
            raise SystemExit(3)
        print(f"[wait] still running: {', '.join(pending)} — sleeping 10 min", flush=True)
        time.sleep(600)


def _strip_runtime(obj: object) -> object:
    """Recursively drop runtime-only fields (timing is not deterministic).
    Runtime fields live NESTED inside funnel (funnel.runtime_seconds /
    funnel.bars_per_second), so the summary comparison must strip at every
    depth — the original top-level-only exclusion false-FAILED the pair on
    2026-09-13 with the sole diff funnel.runtime_seconds."""
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
    parser.add_argument("--nowait", action="store_true", help="do not wait for runs; verify now")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not args.nowait:
        wait_for_runs()
    missing = [r for r in RUNS if not run_done(r)]
    if missing:
        print(f"[abort] summaries missing: {', '.join(missing)} — rerun after the pair finishes.",
              flush=True)
        return 3

    verdict: dict = {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": {}}
    ok = True

    for run in RUNS:
        summary = load_run(run)
        verdict["checks"][f"{run}_pass"] = bool(summary.get("pass"))
        verdict["checks"][f"{run}_bars"] = summary["window"]["bars_processed"]
        ok = ok and bool(summary.get("pass")) and summary["window"]["bars_processed"] > 0

    # 1. Byte-identical exports.
    for name in ("trades.csv", "report.json"):
        a = (RESULTS / "phase_b_run1" / name).read_bytes()
        b = (RESULTS / "phase_b_run2" / name).read_bytes()
        same = a == b
        verdict["checks"][f"byte_identical_{name}"] = same
        ok = ok and same

    # 2. summary.json identical excluding runtime fields.
    s1, s2 = load_run("phase_b_run1"), load_run("phase_b_run2")
    diffs = summary_equal_ex_runtime(s1, s2)
    verdict["checks"]["summary_identical_ex_runtime"] = not diffs
    if diffs:
        verdict["checks"]["summary_diff_keys"] = diffs
    ok = ok and not diffs

    # 3. Funnel non-zero-or-explained (run1 is the record copy).
    funnel = s1["funnel"]
    unexplained = [
        key for key, value in funnel.items()
        if isinstance(value, int) and value == 0 and key not in FUNNEL_EXPLANATIONS
    ]
    verdict["checks"]["funnel_unexplained_zero_stage"] = unexplained
    ok = ok and not unexplained

    # 4. Plan §4 structural checks (mirror the report §9 table).
    invariants = s1["invariants"]
    bad_invariants = {k: v for k, v in invariants.items() if v != "OK"}
    verdict["checks"]["invariants_bad"] = bad_invariants
    ok = ok and not bad_invariants

    by_trigger = s1["by_trigger_trades"]
    d_zero = by_trigger.get("D", 0) == 0
    verdict["checks"]["trigger_d_zero"] = d_zero
    ok = ok and d_zero

    verdict["verdict"] = "PASS" if ok else "FAIL"
    verdict["criteria"] = {
        "determinism_byte_identical": verdict["checks"]["byte_identical_trades.csv"]
        and verdict["checks"]["byte_identical_report.json"],
        "invariants_all_ok": not bad_invariants,
        "funnel_nonzero_or_explained": not unexplained,
        "trigger_d_zero": d_zero,
        "bars_nonzero": verdict["checks"]["phase_b_run1_bars"] > 0
        and verdict["checks"]["phase_b_run2_bars"] > 0,
    }

    out = RESULTS / "phase_b_verdict.json"
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(verdict, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
