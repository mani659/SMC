"""Phase C runtime reality check — profile one plateau detection window.

Profiles `DetectionDriver.stage0` + `PipelineEngine.validate` over a full
2,880-bar late-October window (the Phase B steady-state shape) to attribute
the ~1.34 s/bar to its components. Read-only; writes nothing.

    python 06_RESEARCH/scripts/phase_c_profile.py
"""

from __future__ import annotations

import cProfile
import io
import pstats
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import phase_b_fidelity_backtest as pb  # noqa: E402


def main() -> int:
    from_ts = datetime(2025, 10, 1, tzinfo=timezone.utc)
    to_ts = datetime(2025, 10, 31, tzinfo=timezone.utc) + timedelta(days=1) - timedelta(minutes=1)
    print("loading October...", flush=True)
    candles = pb.load_window(from_ts, to_ts)
    window = candles[-2880:]
    print(f"window: {len(window)} bars ending {window[-1].timestamp}", flush=True)

    driver = pb.DetectionDriver(pb.TF)
    engine = pb.PipelineEngine()

    # warm-up (JIT-free but imports/caches settle)
    driver.validate_window(window, engine=engine, merge_first=True)

    prof = cProfile.Profile()
    prof.enable()
    driver.validate_window(window, engine=engine, merge_first=True)
    prof.disable()

    buf = io.StringIO()
    stats = pstats.Stats(prof, stream=buf)
    stats.sort_stats("cumulative").print_stats(22)
    out = buf.getvalue()
    # print only the interesting block
    lines = out.splitlines()
    start = next((i for i, l in enumerate(lines) if "ncalls" in l), 0)
    print("\n".join(lines[max(0, start - 1): start + 26]))

    buf2 = io.StringIO()
    stats2 = pstats.Stats(prof, stream=buf2)
    stats2.sort_stats("tottime").print_stats(18)
    lines2 = buf2.getvalue().splitlines()
    start2 = next((i for i, l in enumerate(lines2) if "ncalls" in l), 0)
    print("\n--- by tottime ---")
    print("\n".join(lines2[max(0, start2 - 1): start2 + 22]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
