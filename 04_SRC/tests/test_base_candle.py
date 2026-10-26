"""Phase 1 — Base Candle identification (LOCKED_DECISIONS §18)."""

import pytest

from smc.detection.base_candle import find_base_candle_index


def test_swing_high_uses_extreme_candle_itself(candle_factory):
    # Bullish trend: base = the candle whose HIGH is the swing high,
    # regardless of body colour — "NOT the candle before or after".
    candles = candle_factory(
        [
            (100.0, 101.0, 99.0, 100.5),   # before
            (104.0, 105.0, 103.0, 104.5),  # extreme high 105.0 (bullish body)
            (104.5, 104.8, 103.5, 104.0),  # after
        ]
    )
    assert find_base_candle_index(candles, extreme_index=1, is_high=True) == 1

    # The extreme candle may itself be bearish (long upper wick) — still the base.
    candles = candle_factory(
        [
            (100.0, 101.0, 99.0, 100.5),
            (104.0, 105.0, 103.2, 103.5),  # bearish body, but HIGH = extreme
            (103.5, 104.0, 102.8, 103.0),
        ]
    )
    assert find_base_candle_index(candles, extreme_index=1, is_high=True) == 1


def test_swing_low_normal_case_bearish_candle(candle_factory):
    # Bearish candle whose own LOW is the swing low -> base is that candle.
    candles = candle_factory(
        [
            (101.0, 101.5, 100.0, 100.8),
            (100.8, 101.0, 98.0, 98.5),  # bearish, low 98.0 = extreme
            (98.5, 99.5, 98.3, 99.2),
        ]
    )
    assert find_base_candle_index(candles, extreme_index=1, is_high=False) == 1


def test_swing_low_special_rule_previous_bearish_is_base(candle_factory):
    # §18 special rule: previous candle is bearish, next candle's WICK makes
    # the lower low but closes back at/above the bearish candle's low ->
    # the bearish candle remains the Base Candle.
    candles = candle_factory(
        [
            (100.0, 100.4, 99.4, 99.5),   # bearish candle (close < open)
            (99.3, 100.0, 98.8, 99.6),    # wick 98.8 < 99.4, close 99.6 >= 99.4
            (99.6, 100.1, 99.5, 100.0),
        ]
    )
    assert find_base_candle_index(candles, extreme_index=1, is_high=False) == 0


def test_special_rule_not_applied_when_body_closes_below(candle_factory):
    # Extreme candle closes BELOW the previous bearish candle's low -> it made
    # the lower low with its own body, so IT is the base candle.
    candles = candle_factory(
        [
            (100.0, 100.4, 99.4, 99.5),  # bearish
            (99.3, 99.9, 98.8, 99.0),    # close 99.0 < 99.4 (breakdown)
            (99.0, 99.6, 98.9, 99.4),
        ]
    )
    assert find_base_candle_index(candles, extreme_index=1, is_high=False) == 1


def test_special_rule_not_applied_when_previous_candle_bullish(candle_factory):
    # The §18 exception requires the PRECEDING candle to be bearish.
    candles = candle_factory(
        [
            (99.0, 100.2, 98.9, 100.1),  # bullish (close > open)
            (99.8, 100.4, 98.8, 100.0),  # wick 98.8 lower low
            (100.0, 100.6, 99.9, 100.5),
        ]
    )
    assert find_base_candle_index(candles, extreme_index=1, is_high=False) == 1


def test_extreme_index_out_of_range_raises(candle_factory):
    candles = candle_factory([(100.0, 101.0, 99.0, 100.0)])
    with pytest.raises(IndexError):
        find_base_candle_index(candles, extreme_index=5, is_high=True)