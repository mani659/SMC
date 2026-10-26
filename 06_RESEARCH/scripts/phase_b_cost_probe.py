"""PHASE B diagnostic — validate_window cost across the October window.

Samples driver.validate_window() at regular bar intervals using the same
window size, loader and engine as phase_b_fidelity_backtest.py, to measure
how per-bar detection cost evolves over the month (explains live-run rate
degradation and informs Phase C runtime planning).

Read-only with respect to run artifacts. Safe to run alongside the live
pair (the box has 8 logical cores; the two runs are single-threaded).

    python 06_RESEARCH/scripts/phase_b_cost_probe.py [step]
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

# The backtest module prints non-cp1252 glyphs on load; force UTF-8 first.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import phase_b_fidelity_backtest as pb  # noqa: E402


def main() -> int:
    step = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    from_ts = datetime(2025, 10, 1, tzinfo=timezone.utc)
    to_ts = datetime(2025, 10, 31, tzinfo=timezone.utc) + timedelta(days=1) - timedelta(minutes=1)
    candles = pb.load_window(from_ts, to_ts)
    print(f"loaded {len(candles)} bars", flush=True)

    window_bars = 2880  # matches the backtest CLI default (args.window_bars)
    driver = pb.DetectionDriver(pb.TF)
    engine = pb.PipelineEngine()
    armed_total = 0
    for end in range(window_bars + 120, len(candles), step):
        window = candles[end - window_bars:end]
        t0 = time.perf_counter()
        passed, results, _run, skipped, detected = driver.validate_window(
            window, engine=engine, merge_first=True
        )
        dt = time.perf_counter() - t0
        armed_total += len(passed)
        last_ts = candles[end - 1].timestamp.isoformat()
        print(
            f"bar {end:6d} ({last_ts[:16]}): validate_window {dt:6.2f} s  "
            f"passed={len(passed)} detected={len(detected)} armed_total={armed_total}",
            flush=True,
        )
        for poi in passed:
            engine.arm_at(poi, arm_bar=end)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
