"""Phase 0 validation — ATR computes correctly on synthetic data."""

from datetime import datetime, timedelta, timezone

import pytest

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.utils.atr import atr_series, latest_atr

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candles(ohlc_list):
    candles = []
    for index, (open_, high, low, close) in enumerate(ohlc_list):
        candles.append(
            Candle(
                timestamp=START + timedelta(minutes=5 * index),
                open=open_,
                high=high,
                low=low,
                close=close,
                timeframe=Timeframe.M5,
            )
        )
    return candles


def _constant_range_candles(count, high=10.0, low=8.0, close=9.0):
    """Every candle has range 2.0; ATR must converge to exactly 2.0."""
    return _candles([(close, high, low, close)] * count)


def test_atr_of_constant_range_is_constant():
    candles = _constant_range_candles(30)
    series = atr_series(candles, period=14)
    assert len(series) == 30
    # First 13 values are the warm-up (None), the 14th seeds the Wilder RMA.
    assert series[:13] == [None] * 13
    assert all(value == 2.0 for value in series[13:])
    assert latest_atr(candles, period=14) == 2.0


def test_atr_seed_is_simple_average():
    # TRs: 2, 4, 6 -> seed = (2+4+6)/3 = 4.0 with period=3.
    candles = [
        (9.0, 10.0, 8.0, 9.0),    # TR 2
        (9.0, 12.0, 8.0, 9.0),    # TR max(4, |12-9|=3, |8-9|=1) = 4
        (9.0, 15.0, 9.0, 9.0),    # TR max(6, 6, 0) = 6
    ]
    series = atr_series(_candles(candles), period=3)
    assert series == [None, None, 4.0]
    assert latest_atr(_candles(candles), period=3) == 4.0


def test_wilder_smoothing_after_seed():
    # TRs: 2, 4, 6, then one more TR=2 with period=3:
    # seed 4.0 -> (4*2 + 2)/3 = 3.333...
    candles = [
        (9.0, 10.0, 8.0, 9.0),
        (9.0, 12.0, 8.0, 9.0),
        (9.0, 15.0, 9.0, 9.0),
        (9.0, 10.0, 8.0, 9.0),
    ]
    series = atr_series(_candles(candles), period=3)
    assert series[-1] is not None
    assert abs(series[-1] - 10.0 / 3.0) < 1e-9


def test_atr_requires_minimum_data():
    candles = _constant_range_candles(10)
    assert latest_atr(candles, period=14) is None
    assert atr_series(candles, period=14) == [None] * 10


def test_atr_true_range_uses_previous_close_gaps():
    # Gap up: previous close 9, today H=20 L=10 -> TR = max(10, |20-9|=11, 1) = 11.
    candles = _candles([(9.0, 10.0, 8.0, 9.0), (10.0, 20.0, 10.0, 19.0)])
    # period=2 -> seed = (2 + 11) / 2 = 6.5; first value is warm-up None.
    assert atr_series(candles, period=2) == [None, 6.5]
    # period=1 -> ATR tracks the latest true range exactly (2.0 then 11.0).
    assert atr_series(candles, period=1) == [2.0, 11.0]
    assert latest_atr(candles, period=1) == 11.0


def test_invalid_period_raises():
    candles = _constant_range_candles(5)
    with pytest.raises(ValueError):
        atr_series(candles, period=0)