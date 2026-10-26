"""Phase C scope probe — measure sub-component costs for the perf-patch decision.

1. cProfile scan_liquidity + engine.validate separately (plateau window).
2. Time O(L) trigger-evaluation primitives at FULL-series scale (1.7M bars):
   rsi_series, candle inversion, atr_series, linear scans — the constants
   that decide whether the adapter hint path is mandatory.
"""

from __future__ import annotations

import cProfile
import io
import pstats
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import phase_b_fidelity_backtest as pb  # noqa: E402


def _dump(stats, n, label):
    buf = io.StringIO()
    pstats.Stats(stats, stream=buf).sort_stats("tottime").print_stats(n)
    lines = buf.getvalue().splitlines()
    start = next((i for i, l in enumerate(lines) if "ncalls" in l), 0)
    print(f"\n--- {label} (tottime) ---")
    print("\n".join(lines[max(0, start - 1): start + n + 2]))


def main() -> int:
    from_ts = datetime(2025, 10, 1, tzinfo=timezone.utc)
    to_ts = datetime(2025, 10, 31, tzinfo=timezone.utc) + timedelta(days=1) - timedelta(minutes=1)
    candles = pb.load_window(from_ts, to_ts)
    window = candles[-2880:]

    from smc.detection.liquidity_scanner import ALL_FAMILIES as _ALL_FAMILIES
    from smc.detection.liquidity_scanner import scan as scan_liquidity
    from smc.orchestration.engine import PipelineEngine

    # --- scan_liquidity alone ---
    scan_liquidity(window, pb.TF, include=_ALL_FAMILIES)
    prof = cProfile.Profile()
    prof.enable()
    for _ in range(5):
        scan_liquidity(window, pb.TF)
    prof.disable()
    _dump(prof, 14, "scan_liquidity x5")

    # --- engine.validate alone (POIs from a fresh detect) ---
    driver = pb.DetectionDriver(pb.TF)
    engine = PipelineEngine()
    raw = driver.stage0(window)
    pois, _ = driver.detect_pois(window, raw.swings, raw.liquidity_levels)
    engine.validate(pois, window, raw.swings, raw.liquidity_levels,
                    displacement_map=driver.attribute_displacement(pois, raw),
                    merge_first=True, atr_period=14)
    prof2 = cProfile.Profile()
    prof2.enable()
    for _ in range(5):
        fresh = PipelineEngine()
        fresh.validate(pois, window, raw.swings, raw.liquidity_levels,
                       displacement_map=driver.attribute_displacement(pois, raw),
                       merge_first=True, atr_period=14)
    prof2.disable()
    _dump(prof2, 14, "engine.validate x5")

    # --- O(L) primitives at full-series scale (5-year, 1.7M bars) ---
    print("\n--- O(L) primitives on the FULL canonical series ---")
    full = pb.load_window(datetime(2021, 4, 12, tzinfo=timezone.utc),
                          datetime(2026, 4, 10, tzinfo=timezone.utc) + timedelta(days=1))
    print(f"full bars: {len(full)}")
    from smc.utils.rsi import rsi_series
    from smc.utils.atr import atr_series, latest_atr
    from smc.core.candle import Candle

    t0 = time.perf_counter(); atr_series(full, 14); t1 = time.perf_counter()
    print(f"atr_series(1.7M): {t1 - t0:.3f} s")
    t0 = time.perf_counter(); rsi_series(full); t1 = time.perf_counter()
    print(f"rsi_series(1.7M): {t1 - t0:.3f} s")
    t0 = time.perf_counter()
    inv = [Candle(timestamp=c.timestamp, open=-c.open, high=-c.low, low=-c.high,
                  close=-c.close, volume=c.volume, timeframe=c.timeframe) for c in full]
    t1 = time.perf_counter()
    print(f"invert candles (1.7M): {t1 - t0:.3f} s (allocs={len(inv)})")
    t0 = time.perf_counter()
    s = 0.0
    for c in full:
        s += c.close
    t1 = time.perf_counter()
    print(f"linear scan 1.7M (repr. _first_after/comps): {t1 - t0:.3f} s")
    # per-eval cost of latest_atr on a mid-run prefix (what current_atr does per bar)
    mid = len(full) // 2
    t0 = time.perf_counter(); latest_atr(full[:mid], 14); t1 = time.perf_counter()
    print(f"latest_atr(prefix 884k): {t1 - t0:.3f} s  (x1.7M bars = "
          f"{(t1 - t0) * 1_768_123 / 86400:.1f} days just for current_atr)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
