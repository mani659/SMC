"""Phase 1 — Structural swing detection (§27 N-bar + §18/§19 gates)."""

import pytest

from smc.config.timeframe import Timeframe
from smc.detection.structural_swing_detector import detect_swings


def _zigzag_rows(points, step=4, wick=0.1):
    """Monotonic legs between ``points``; each leg spans ``step`` candles.

    The last candle of each leg is a clean fractal extreme (3 bars on each
    side for LTF N=3 when ``step >= 4``).
    """
    rows = []
    previous = points[0]
    for target in points[1:]:
        for t in range(step):
            open_ = previous if not rows else rows[-1][3]
            close = previous + (target - previous) * (t + 1) / step
            rows.append((open_, max(open_, close) + wick, min(open_, close) - wick, close))
        previous = target
    return rows


def test_detects_ltf_swings_with_default_n(candle_factory):
    rows = _zigzag_rows([100, 104, 96, 104, 95])
    candles = candle_factory(rows, Timeframe.M1)
    swings = detect_swings(candles, Timeframe.M1)

    # Expected (from the geometry): two equal tops at 104.1 and one bottom at
    # 95.9, all later swept + closed beyond -> valid.
    assert len(swings) == 3
    tops = [s for s in swings if s.is_high]
    bottoms = [s for s in swings if not s.is_high]
    assert len(tops) == 2 and len(bottoms) == 1

    for top in tops:
        assert top.level == pytest.approx(104.1)
        assert top.is_valid
        assert top.confirmed_index is not None
        assert top.base_candle is candles[top.candle_index]

    bottom = bottoms[0]
    assert bottom.level == pytest.approx(95.9)
    assert bottom.is_valid
    assert bottom.confirmed_index is not None
    assert bottom.base_candle is candles[bottom.candle_index]


def test_detects_swing_high_and_low_candle_indices(candle_factory):
    rows = _zigzag_rows([100, 104, 96, 104, 95])
    candles = candle_factory(rows, Timeframe.M1)
    swings = detect_swings(candles, Timeframe.M1)
    # Extremes land on the last bar of each leg: idx 3 (top), 7 (bottom), 11 (top).
    assert {s.candle_index for s in swings} == {3, 7, 11}


def test_insufficient_data_returns_empty(candle_factory):
    rows = _zigzag_rows([100, 104], step=2)  # 2 bars < 2*3+1
    candles = candle_factory(rows, Timeframe.M1)
    assert detect_swings(candles, Timeframe.M1) == []


def test_n_follows_timeframe_class_per_section_27(candle_factory):
    # Same 16-bar geometry: M1/M15 (LTF, N=3) find all 3 swings; D1 (HTF,
    # N=5) needs extremes to sit inside [5, len-5], which only the bottom
    # at idx 7 satisfies.
    rows = _zigzag_rows([100, 104, 96, 104, 95])
    candles = candle_factory(rows, Timeframe.M1)

    ltf = detect_swings(candles, Timeframe.M15)  # LTF class -> N=3
    assert len(ltf) == 3

    htf = detect_swings(candles, Timeframe.D1)  # HTF class -> N=5
    assert len(htf) == 1
    assert not htf[0].is_high
    assert htf[0].level == pytest.approx(95.9)


def test_invalid_n_raises(candle_factory):
    rows = _zigzag_rows([100, 104, 96, 104, 95])
    candles = candle_factory(rows, Timeframe.M1)
    with pytest.raises(ValueError):
        detect_swings(candles, Timeframe.M1, n=0)


def test_explicit_n_override(candle_factory):
    # N=1 finds more extremes than N=3 on the same geometry.
    rows = _zigzag_rows([100, 104, 96, 104, 95], step=2)
    candles = candle_factory(rows, Timeframe.M1)
    assert len(detect_swings(candles, Timeframe.M1, n=1)) > len(
        detect_swings(candles, Timeframe.M1, n=3)
    )