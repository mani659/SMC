"""Phase 2 — Dealing range + premium/discount/equilibrium (§6)."""

import pytest

from smc.poi.deal_range import (
    classify_region,
    compute_dealing_range,
    range_position,
    DealRangeRegion,
)


def _range(candle_factory, swing_factory, highs, lows):
    """Build swings + dealing range from (index, level) pairs."""
    candles = candle_factory([(100, 100, 100, 100)] * 20)
    swings = []
    for index, level in highs:
        swings.append(swing_factory(candles, index, True, level=level))
    for index, level in lows:
        swings.append(swing_factory(candles, index, False, level=level))
    return swings


def test_recent_high_and_low_form_the_range(candle_factory, swing_factory):
    swings = _range(
        candle_factory,
        swing_factory,
        highs=[(2, 105.0), (6, 108.0)],
        lows=[(1, 100.0), (4, 102.0)],
    )
    dealing = compute_dealing_range(swings)
    assert dealing is not None
    assert dealing.high == 108.0
    assert dealing.low == 102.0
    assert dealing.high_index == 6
    assert dealing.low_index == 4


def test_fallback_to_window_extremes_when_recent_pair_unusable(candle_factory, swing_factory):
    # Most recent high (104) is below the most recent low (105) -> unusable.
    swings = _range(
        candle_factory,
        swing_factory,
        highs=[(2, 106.0), (6, 104.0)],
        lows=[(1, 100.0), (8, 105.0)],
    )
    dealing = compute_dealing_range(swings)
    assert dealing is not None
    assert dealing.high == 106.0
    assert dealing.low == 100.0


def test_no_range_when_one_side_missing(candle_factory, swing_factory):
    swings = _range(candle_factory, swing_factory, highs=[(2, 105.0)], lows=[])
    assert compute_dealing_range(swings) is None
    assert compute_dealing_range([]) is None


def test_range_position_zero_to_one(candle_factory, swing_factory):
    swings = _range(
        candle_factory, swing_factory, highs=[(5, 110.0)], lows=[(3, 100.0)]
    )
    dealing = compute_dealing_range(swings)
    assert dealing is not None
    assert range_position(100.0, dealing) == pytest.approx(0.0)
    assert range_position(110.0, dealing) == pytest.approx(1.0)
    assert range_position(105.0, dealing) == pytest.approx(0.5)


def test_region_classification_uses_frozen_bands(candle_factory, swing_factory):
    swings = _range(
        candle_factory, swing_factory, highs=[(5, 110.0)], lows=[(3, 100.0)]
    )
    dealing = compute_dealing_range(swings)
    assert dealing is not None
    # < 45% discount, > 55% premium, 45-55% equilibrium (reject band).
    assert classify_region(103.0, dealing) is DealRangeRegion.DISCOUNT
    assert classify_region(107.0, dealing) is DealRangeRegion.PREMIUM
    assert classify_region(105.0, dealing) is DealRangeRegion.EQUILIBRIUM
    assert classify_region(104.5, dealing) is DealRangeRegion.EQUILIBRIUM  # exactly 45%
