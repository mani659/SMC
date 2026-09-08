"""Phase 1 — 3-candle Fair Value Gap detection (§3 imbalance)."""

import pytest

from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.detection.fvg_detector import detect_fvgs


def test_detects_bullish_fvg(candle_factory):
    candles = candle_factory(
        [
            (100.0, 101.0, 99.5, 100.5),   # c1: high 101.0
            (100.5, 101.8, 100.4, 101.6),  # c2 (middle)
            (101.6, 104.0, 102.0, 103.5),  # c3: low 102.0 > high(c1)
        ]
    )
    fvgs = detect_fvgs(candles, Timeframe.M5)
    assert len(fvgs) == 1
    fvg = fvgs[0]
    assert fvg.start_index == 0
    assert fvg.zone.direction is Direction.LONG
    assert fvg.zone.bottom == pytest.approx(101.0)   # high(c1)
    assert fvg.zone.top == pytest.approx(102.0)      # low(c3)
    assert fvg.zone.timeframe is Timeframe.M5
    assert fvg.zone.contains(101.5)


def test_detects_bearish_fvg(candle_factory):
    candles = candle_factory(
        [
            (103.0, 104.0, 102.5, 103.4),   # c1: low 102.5
            (103.4, 103.2, 101.8, 102.0),   # c2 (middle)
            (102.0, 100.5, 99.0, 100.2),    # c3: high 100.5 < low(c1)
        ]
    )
    fvgs = detect_fvgs(candles, Timeframe.M5)
    assert len(fvgs) == 1
    fvg = fvgs[0]
    assert fvg.zone.direction is Direction.SHORT
    assert fvg.zone.top == pytest.approx(102.5)      # low(c1)
    assert fvg.zone.bottom == pytest.approx(100.5)    # high(c3)


def test_overlapping_candles_produce_no_fvg(candle_factory):
    candles = candle_factory(
        [
            (100.0, 101.0, 99.5, 100.5),
            (100.5, 101.2, 99.9, 101.0),   # overlaps c1
            (101.0, 101.6, 100.4, 101.4),  # overlaps c2 (no gap)
        ]
    )
    assert detect_fvgs(candles, Timeframe.M5) == []


def test_multiple_fvgs_detected_in_order(candle_factory):
    candles = candle_factory(
        [
            (100.0, 101.0, 99.5, 100.5),   # FVG 1 (bullish), middle at idx 1
            (100.5, 101.8, 100.4, 101.6),
            (101.6, 104.0, 102.0, 103.5),
            (103.5, 104.2, 101.5, 104.0),  # overlaps candle 1 -> no gap here
            (103.8, 104.6, 103.5, 104.4),  # overlapping — no gap
            (104.0, 104.4, 103.9, 104.2),
        ]
    )
    fvgs = detect_fvgs(candles, Timeframe.M5)
    assert len(fvgs) == 1
    assert fvgs[0].start_index == 0


def test_too_few_candles_returns_empty(candle_factory):
    candles = candle_factory([(100.0, 101.0, 99.0, 100.0)])
    assert detect_fvgs(candles, Timeframe.M5) == []