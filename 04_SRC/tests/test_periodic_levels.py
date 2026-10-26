"""Phase 1 — PDH/PDL and PWH/PWL periodic levels (§2)."""

from datetime import datetime, timezone

import pytest

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import LiquidityType, PoolType
from smc.detection.periodic_levels import detect_periodic_levels


def _day_candles(day_map, hours=(0, 6, 12, 18)):
    """One candle per (day, hour) with the given high/low extremes.

    ``day_map``: ``{day_of_month: (high, low)}`` within January 2026
    (Jan 5 2026 is a Monday).
    """
    candles = []
    for day, (high, low) in sorted(day_map.items()):
        for hour in hours:
            mid = (high + low) / 2.0
            candles.append(
                Candle(
                    timestamp=datetime(2026, 1, day, hour, tzinfo=timezone.utc),
                    open=mid,
                    high=high,
                    low=low,
                    close=mid,
                    timeframe=Timeframe.H1,
                )
            )
    return candles


WEEK = {
    5: (1050.0, 1005.0),   # Mon
    6: (1090.0, 995.0),    # Tue (week high & low)
    7: (1070.0, 1010.0),   # Wed
    8: (1080.0, 1020.0),   # Thu
    9: (1040.0, 1010.0),   # Fri (last day of week 1)
    12: (1100.0, 990.0),   # Mon of week 2
}


def _by_type(levels, type_, pool):
    return [lv for lv in levels if lv.type is type_ and lv.pool is pool]


def test_previous_day_and_week_levels(candle_factory):
    candles = _day_candles(WEEK)
    levels = detect_periodic_levels(
        candles, Timeframe.H1, as_of=datetime(2026, 1, 13, tzinfo=timezone.utc)
    )

    # PDH/PDL = Jan 12 (previous completed trading day); PWH/PWL = week 1.
    pdh = _by_type(levels, LiquidityType.PREVIOUS_DAY, PoolType.BSL)
    pdl = _by_type(levels, LiquidityType.PREVIOUS_DAY, PoolType.SSL)
    pwh = _by_type(levels, LiquidityType.PREVIOUS_WEEK, PoolType.BSL)
    pwl = _by_type(levels, LiquidityType.PREVIOUS_WEEK, PoolType.SSL)
    assert len(pdh) == len(pdl) == len(pwh) == len(pwl) == 1

    assert pdh[0].level == pytest.approx(1100.0)
    assert pdl[0].level == pytest.approx(990.0)
    assert pwh[0].level == pytest.approx(1090.0)  # week high on Tue, not Fri
    assert pwl[0].level == pytest.approx(995.0)


def test_default_as_of_is_last_candle(candle_factory):
    candles = _day_candles(WEEK)  # last candle Jan 12 18:00
    levels = detect_periodic_levels(candles, Timeframe.H1)
    assert len(levels) == 4
    # Previous completed day is Jan 9 (Jan 12 itself is not yet complete).
    assert next(lv for lv in levels if lv.pool is PoolType.BSL
                and lv.type is LiquidityType.PREVIOUS_DAY).level == pytest.approx(1040.0)


def test_reference_within_same_week_omits_week_levels(candle_factory):
    candles = _day_candles({5: WEEK[5], 6: WEEK[6], 7: WEEK[7]})
    levels = detect_periodic_levels(
        candles, Timeframe.H1, as_of=datetime(2026, 1, 8, tzinfo=timezone.utc)
    )
    # Day levels only: Jan 7 is the previous completed day; week 1 has not
    # completed before Jan 8 (it is still the current week).
    assert len(levels) == 2
    pdh = _by_type(levels, LiquidityType.PREVIOUS_DAY, PoolType.BSL)
    assert pdh[0].level == pytest.approx(1070.0)
    assert not _by_type(levels, LiquidityType.PREVIOUS_WEEK, PoolType.BSL)


def test_no_completed_prior_period_returns_empty(candle_factory):
    candles = _day_candles({5: WEEK[5]})
    levels = detect_periodic_levels(
        candles, Timeframe.H1, as_of=datetime(2026, 1, 5, 12, tzinfo=timezone.utc)
    )
    assert levels == []


def test_weekend_gap_skips_to_last_trading_day(candle_factory):
    candles = _day_candles({5: WEEK[5], 6: WEEK[6]})
    # as_of Monday Jan 12 00:00 -> previous completed day with data is Fri Jan 9
    # (not Sun Jan 11, which has no candles).
    candles += _day_candles({9: WEEK[9]})
    levels = detect_periodic_levels(
        candles, Timeframe.H1, as_of=datetime(2026, 1, 12, tzinfo=timezone.utc)
    )
    pdh = _by_type(levels, LiquidityType.PREVIOUS_DAY, PoolType.BSL)
    assert pdh[0].level == pytest.approx(1040.0)