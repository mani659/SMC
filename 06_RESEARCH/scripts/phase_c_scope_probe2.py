"""Phase C scope probe #2 — honest timings (no cProfile inflation).

A. Plateau-window stage0 pieces, 10 reps each:
   detect_swings / scan_liquidity / detect_sweeps / full stage0 /
   validate_window(with fresh displacement) / pillar-1 share.
B. Consumer costs at FULL-series scale (1.7M prefix):
   classify_choch_at (one evaluation), rsi_series, _invert_candles,
   _last_two-style comprehension over the full-prefix swing list,
   detect_swings(full prefix) once (initial incremental state build),
   atr_series(full) once.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import phase_b_fidelity_backtest as pb  # noqa: E402


def _t(label, fn, reps=1):
    fn()  # warmup
    t0 = time.perf_counter()
    for _ in range(reps):
        out = fn()
    dt = (time.perf_counter() - t0) / reps
    print(f"{label}: {dt * 1000:.1f} ms  (x{reps})")
    return out


def main() -> int:
    from_ts = datetime(2025, 10, 1, tzinfo=timezone.utc)
    to_ts = datetime(2025, 10, 31, tzinfo=timezone.utc) + timedelta(days=1) - timedelta(minutes=1)
    candles = pb.load_window(from_ts, to_ts)
    window = candles[-2880:]

    from smc.detection.liquidity_scanner import scan as scan_liquidity
    from smc.detection.sweep_detector import detect_sweeps
    from smc.detection.structural_swing_detector import detect_swings
    from smc.orchestration.engine import PipelineEngine
    from smc.validation.pillar_1_zone_refinement import ZoneRefinementPillar
    from smc.validation.pillar import ValidationContext

    print("=== A. plateau-window pieces (2880 bars) ===")
    swings = _t("detect_swings", lambda: detect_swings(window, pb.TF), 10)
    levels = _t("scan_liquidity", lambda: scan_liquidity(window, pb.TF), 10)
    _t("detect_sweeps", lambda: detect_sweeps(window, levels), 10)
    driver = pb.DetectionDriver(pb.TF)
    _t("DetectionDriver.stage0 (full)", lambda: driver.stage0(window), 5)

    engine = PipelineEngine()
    _t(
        "validate_window (full, fresh engine)",
        lambda: driver.validate_window(window, engine=PipelineEngine(), merge_first=True),
        5,
    )

    # pillar-1 alone on the detected POIs
    raw = driver.stage0(window)
    pois, _skipped = driver.detect_pois(window, raw.swings, raw.liquidity_levels)
    disp_map = driver.attribute_displacement(pois, raw)
    pillar = ZoneRefinementPillar()
    ctxs = [
        ValidationContext(
            poi=p, candles=window, swings=raw.swings,
            liquidity_levels=raw.liquidity_levels, dealing_range=None,
            displacement=disp_map.get(p.id), atr_period=14,
        )
        for p in pois
    ]
    _t(f"pillar-1 x{len(ctxs)} POIs", lambda: [pillar.run(c) for c in ctxs], 10)

    print("\n=== B. full-series scale (1.7M bars) ===")
    full = pb.load_window(
        datetime(2021, 4, 12, tzinfo=timezone.utc),
        datetime(2026, 4, 10, tzinfo=timezone.utc) + timedelta(days=1),
    )
    print(f"full bars: {len(full)}")
    from smc.poi.choch_classifier import _invert_candles, classify_choch_at
    from smc.utils.atr import atr_series
    from smc.utils.rsi import rsi_series

    full_swings = _t("detect_swings(full prefix) [once]", lambda: detect_swings(full, pb.TF), 1)
    print(f"  -> {len(full_swings)} swings in the full prefix")
    _t("atr_series(full) [once]", lambda: atr_series(full, 14), 1)
    _t("rsi_series(full) [once]", lambda: rsi_series(full), 1)
    _t("_invert_candles(full) [per-eval today]", lambda: _invert_candles(full), 1)

    # consumer-style scans over the full-prefix swing list
    def _last_two_like():
        lows = [s for s in full_swings if not s.is_high and s.is_valid]
        highs = [s for s in full_swings if s.is_high and s.is_valid]
        return (
            max(lows, key=lambda s: s.candle_index, default=None),
            max(highs, key=lambda s: s.candle_index, default=None),
        )

    _t("_last_two-style scan over full swing list", _last_two_like, 3)
    _t(
        "classify_choch_at(full prefix, last bar)",
        lambda: classify_choch_at(full, full_swings, len(full) - 1),
        1,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
