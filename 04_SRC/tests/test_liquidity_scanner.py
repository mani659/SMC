"""Phase 1 — Liquidity scanner orchestration (Stage 0A, §2)."""

import pytest

from smc.config.timeframe import Timeframe
from smc.core.enums import LiquidityType, PoolType
from smc.detection.liquidity_scanner import ALL_FAMILIES, scan
from smc.detection.structural_swing_detector import detect_swings


def _zigzag_rows(points, step=4, wick=0.1):
    rows = []
    previous = points[0]
    for target in points[1:]:
        for t in range(step):
            open_ = previous if not rows else rows[-1][3]
            close = previous + (target - previous) * (t + 1) / step
            rows.append((open_, max(open_, close) + wick, min(open_, close) - wick, close))
        previous = target
    return rows


def test_unknown_family_raises(candle_factory):
    candles = candle_factory([(100.0, 101.0, 99.0, 100.0)])
    with pytest.raises(ValueError):
        scan(candles, Timeframe.M1, include=("session", "bogus"))


def test_scan_returns_all_phase1_families(candle_factory):
    # Zigzag over one UTC day: session H/L (Asia), equal highs at the two
    # 104.1 tops, and three structurally valid swings.
    rows = _zigzag_rows([100, 104, 96, 104, 95])
    candles = candle_factory(rows, Timeframe.M1)  # 2026-01-01 00:00 UTC
    levels = scan(candles, Timeframe.M1)

    assert len(levels) == 6  # 2 session + 1 equal + 3 structural

    by_type = {}
    for level in levels:
        by_type.setdefault(level.type, []).append(level)

    session_levels = by_type[LiquidityType.SESSION]
    assert len(session_levels) == 2
    assert {lv.pool for lv in session_levels} == {PoolType.BSL, PoolType.SSL}
    assert all(lv.timeframe is Timeframe.M1 for lv in levels)

    equal = by_type[LiquidityType.EQUAL_HIGHS_LOWS]
    assert len(equal) == 1
    assert equal[0].pool is PoolType.BSL
    assert equal[0].level == pytest.approx(104.1)

    structural = by_type[LiquidityType.STRUCTURAL_SWING]
    assert len(structural) == 3
    # Structural levels mirror the valid swings from the sub-detector.
    valid_swings = [s for s in detect_swings(candles, Timeframe.M1) if s.is_valid]
    assert {lv.level for lv in structural} == {s.level for s in valid_swings}
    assert {lv.pool for lv in structural} == {s.pool for s in valid_swings}


def test_include_filter_restricts_families(candle_factory):
    rows = _zigzag_rows([100, 104, 96, 104, 95])
    candles = candle_factory(rows, Timeframe.M1)

    session_only = scan(candles, Timeframe.M1, include=("session",))
    assert session_only and all(
        lv.type is LiquidityType.SESSION for lv in session_only
    )

    structural_only = scan(candles, Timeframe.M1, include=("structural",))
    assert structural_only and all(
        lv.type is LiquidityType.STRUCTURAL_SWING for lv in structural_only
    )
    assert len(structural_only) == 3

    equal_only = scan(candles, Timeframe.M1, include=("equal",))
    assert len(equal_only) == 1
    assert equal_only[0].type is LiquidityType.EQUAL_HIGHS_LOWS

    empty = scan(candles, Timeframe.M1, include=("periodic",))
    assert empty == []  # no prior day/week in the data


def test_all_families_constant():
    assert ALL_FAMILIES == ("session", "periodic", "equal", "structural")


def test_flat_market_produces_no_swing_families(candle_factory):
    rows = [(100.0, 101.0, 99.0, 100.5)] * 30
    candles = candle_factory(rows, Timeframe.M1)
    levels = scan(candles, Timeframe.M1)
    # Session levels exist, but no swings / equal highs can form on a flat tape.
    assert all(
        lv.type is LiquidityType.SESSION for lv in levels
    )
    assert len(levels) == 2