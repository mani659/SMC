"""Phase 1 — Displacement check: BOS + FVG + magnitude vs ATR (§3)."""

import pytest

from smc.core.enums import Direction
from smc.detection.displacement_checker import check_displacement

PRE = [(100.5, 101.5, 99.5, 100.5)] * 15  # constant range 2 -> ATR(14) = 2.0


def test_passing_bullish_displacement_after_ssl_sweep(candle_factory):
    candles = candle_factory(
        PRE
        + [
            (99.8, 100.5, 98.2, 99.6),    # 15: SSL sweep (wick below 99)
            (100.0, 102.5, 100.3, 100.8),  # 16: impulse, close < BOS level
            (101.0, 103.5, 102.0, 103.2),  # 17: FVG trio + BOS close > 101.2
        ]
    )
    result = check_displacement(
        candles, Direction.LONG, sweep_index=15, bos_level=101.2
    )
    assert result.passed
    assert result.bos and result.bos_index == 17
    assert result.fvg
    assert result.atr == pytest.approx(2.0)
    assert result.magnitude == pytest.approx(5.0)
    assert result.magnitude_atr == pytest.approx(2.5)  # >= 1.0 -> pass
    assert result.is_preferred                        # > 1.5
    assert not result.hard_fail


def test_hard_fail_on_tiny_move(candle_factory):
    candles = candle_factory(
        PRE
        + [
            (99.8, 100.5, 98.2, 99.0),   # sweep
            (99.0, 99.4, 98.9, 99.1),    # weak follow-through
            (99.1, 99.3, 99.0, 99.1),
        ]
    )
    result = check_displacement(
        candles, Direction.LONG, sweep_index=15, bos_level=101.2
    )
    assert not result.passed
    assert not result.bos
    assert not result.fvg
    assert result.magnitude_atr is not None
    assert result.magnitude_atr < 0.5
    assert result.hard_fail  # < DISPLACEMENT_HARD_FAIL (0.5x ATR)


def test_bos_without_fvg_does_not_pass(candle_factory):
    # Strong close beyond the level but no 3-candle imbalance in the move
    # (the BOS candle's low 100.4 stays below the sweep candle's high 100.5,
    # so no gap forms between candles 15 and 17).
    candles = candle_factory(
        PRE
        + [
            (99.8, 100.5, 98.2, 99.6),    # sweep
            (99.9, 100.8, 99.8, 100.7),   # overlaps
            (101.0, 103.0, 100.4, 102.8), # BOS close 102.8 > 101.2, no FVG
        ]
    )
    result = check_displacement(
        candles, Direction.LONG, sweep_index=15, bos_level=101.2
    )
    assert result.bos and result.bos_index == 17
    assert not result.fvg
    assert not result.passed


def test_passing_bearish_displacement_after_bsl_sweep(candle_factory):
    candles = candle_factory(
        PRE
        + [
            (100.8, 101.9, 100.5, 100.5),  # 15: BSL sweep (wick above 101.6)
            (100.6, 101.0, 100.4, 100.9),  # 16: impulse
            (100.9, 99.6, 99.0, 99.2),     # 17: bearish FVG + BOS close < 100.8
        ]
    )
    result = check_displacement(
        candles, Direction.SHORT, sweep_index=15, bos_level=100.8
    )
    assert result.passed
    assert result.bos and result.bos_index == 17
    assert result.fvg
    assert result.magnitude == pytest.approx(2.7)
    assert result.magnitude_atr == pytest.approx(1.35)  # >= 1.0 -> pass
    assert not result.hard_fail


def test_insufficient_atr_history(candle_factory):
    candles = candle_factory(PRE + [(99.8, 100.5, 98.2, 99.6)])
    result = check_displacement(
        candles, Direction.LONG, sweep_index=3, bos_level=100.0
    )
    assert result.atr is None
    assert result.magnitude_atr is None
    assert not result.passed
    assert not result.hard_fail


def test_sweep_index_out_of_range_raises(candle_factory):
    candles = candle_factory(PRE)
    with pytest.raises(IndexError):
        check_displacement(candles, Direction.LONG, sweep_index=99, bos_level=101.2)