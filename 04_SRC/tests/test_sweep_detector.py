"""Phase 1 — Sweep confirmation: wick-pierce + body close back (§2)."""

import pytest

from smc.core.enums import LiquidityType, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.detection.sweep_detector import SweepResult, detect_sweep, detect_sweeps


def _level(pool, price, formed_index=None, candles=None):
    return LiquidityLevel(
        type=LiquidityType.EQUAL_HIGHS_LOWS,
        level=price,
        pool=pool,
        formed_at=None if candles is None or formed_index is None else candles[formed_index].timestamp,
    )


def test_bsl_sweep_wick_above_close_below(candle_factory):
    candles = candle_factory(
        [
            (99.5, 99.8, 99.4, 99.7),    # approach below
            (99.7, 100.6, 99.4, 99.8),   # wick above 100.0, close back below
        ]
    )
    level = _level(PoolType.BSL, 100.0)
    result = detect_sweep(candles, level)
    assert result is not None
    assert result.candle_index == 1
    assert result.candle is candles[1]
    assert result.pool is PoolType.BSL


def test_bsl_breakout_is_not_a_sweep(candle_factory):
    # Closes ABOVE the level after piercing -> genuine breakout, not a sweep.
    candles = candle_factory(
        [
            (99.5, 99.8, 99.4, 99.7),
            (99.7, 100.6, 99.4, 100.4),
        ]
    )
    assert detect_sweep(candles, _level(PoolType.BSL, 100.0)) is None


def test_ssl_sweep_wick_below_close_above(candle_factory):
    candles = candle_factory(
        [
            (99.6, 99.9, 99.3, 99.5),
            (99.5, 99.9, 98.5, 99.2),   # wick below 99.0, close back above
        ]
    )
    result = detect_sweep(candles, _level(PoolType.SSL, 99.0))
    assert result is not None
    assert result.candle_index == 1


def test_ssl_breakdown_is_not_a_sweep(candle_factory):
    candles = candle_factory(
        [
            (99.6, 99.9, 99.3, 99.5),
            (99.5, 99.4, 98.5, 98.6),   # closes below 99.0 (breakdown)
        ]
    )
    assert detect_sweep(candles, _level(PoolType.SSL, 99.0)) is None


def test_forming_candle_cannot_sweep_itself(candle_factory):
    candles = candle_factory(
        [
            (99.0, 99.4, 98.8, 99.2),            # quiet context
            (100.3, 100.8, 100.1, 99.9),          # forming candle looks sweep-like
            (99.8, 100.5, 99.7, 99.6),            # real sweep after formation
        ]
    )
    level = _level(PoolType.BSL, 100.0, formed_index=1, candles=candles)
    result = detect_sweep(candles, level)
    assert result is not None
    assert result.candle_index == 2  # formed_at bound skips candles[1]


def test_detect_sweeps_returns_only_swept_levels_in_order(candle_factory):
    candles = candle_factory(
        [
            (99.5, 100.6, 99.3, 99.8),   # idx0: sweeps BSL 100.0
            (99.8, 100.2, 98.4, 99.6),   # idx1: sweeps SSL 98.8
            (99.6, 99.9, 99.5, 99.8),    # idx2: quiet
        ]
    )
    bsl = _level(PoolType.BSL, 100.0)
    ssl = _level(PoolType.SSL, 98.8)
    untouched = _level(PoolType.BSL, 101.5)
    results = detect_sweeps(candles, [bsl, ssl, untouched])
    assert len(results) == 2
    assert all(isinstance(r, SweepResult) for r in results)
    assert [r.candle_index for r in results] == [0, 1]
    assert results[0].level is bsl
    assert results[1].level is ssl