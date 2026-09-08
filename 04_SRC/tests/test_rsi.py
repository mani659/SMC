"""Phase 4 — RSI(14) indicator tests (Trigger E dependency)."""

import pytest

from smc.utils.rsi import latest_rsi, rsi_series


def test_constant_advances_give_rsi_100(candle_factory):
    rows = [(100.0 + i * 0.5, 100.0 + i * 0.5, 99.9 + i * 0.5, 100.0 + i * 0.5) for i in range(20)]
    candles = candle_factory(rows)
    series = rsi_series(candles, period=14)
    assert series[:14] == [None] * 14  # warm-up
    assert series[-1] == pytest.approx(100.0)


def test_constant_declines_give_rsi_0(candle_factory):
    rows = [(100.0 - i * 0.5, 100.0 - i * 0.5, 99.9 - i * 0.5, 100.0 - i * 0.5) for i in range(20)]
    series = rsi_series(candle_factory(rows), period=14)
    assert series[-1] == pytest.approx(0.0)


def test_flat_prices_give_rsi_50(candle_factory):
    rows = [(100.0, 100.2, 99.8, 100.0)] * 20
    series = rsi_series(candle_factory(rows), period=14)
    assert series[-1] == pytest.approx(50.0)


def test_insufficient_data_returns_none(candle_factory):
    candles = candle_factory([(100.0, 100.1, 99.9, 100.0)] * 5)
    assert latest_rsi(candles, period=14) is None
    assert len(rsi_series(candles, period=14)) == 5
    assert rsi_series(candles, period=14) == [None] * 5


def test_mixed_series_between_bounds(candle_factory):
    rows = []
    price = 100.0
    for i in range(30):
        price += 0.3 if i % 3 else -0.2
        rows.append((price, price + 0.2, price - 0.2, price))
    value = latest_rsi(candle_factory(rows), period=14)
    assert value is not None
    assert 0.0 < value < 100.0
