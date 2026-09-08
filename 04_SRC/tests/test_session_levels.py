"""Phase 1 — Session high/low levels (§2 Asia/London/NY UTC windows)."""

from datetime import date

import pytest

from smc.config.timeframe import Timeframe
from smc.core.enums import LiquidityType, PoolType
from smc.detection.session_levels import detect_session_levels
from smc.utils.timestamps import Session

ASIA_HOURS = list(range(0, 7))
LONDON_HOURS = list(range(7, 13))
NY_HOURS = list(range(13, 20))
ALL_HOURS = list(range(24))


def _one_day_hourly_rows():
    """Hourly candles over 2026-01-01 00:00–23:00 UTC (24 bars)."""
    return [
        (low + 2.0, high, low, high - 1.0)
        for hour in ALL_HOURS
        for (high, low) in [(100.0 + hour, 96.0 + hour)]
    ]


def _expected(hours, base_high=100.0, base_low=96.0):
    highs = [base_high + h for h in hours]
    lows = [base_low + h for h in hours]
    return max(highs), min(lows)


def test_detects_all_three_sessions_highs_and_lows(candle_factory):
    rows = _one_day_hourly_rows()
    candles = candle_factory(rows, Timeframe.H1)  # starts 2026-01-01 00:00 UTC
    levels = detect_session_levels(candles, Timeframe.H1)

    assert len(levels) == 6  # 3 sessions x (BSL high + SSL low)

    for session, hours in (
        (Session.ASIA, ASIA_HOURS),
        (Session.LONDON, LONDON_HOURS),
        (Session.NEW_YORK, NY_HOURS),
    ):
        expected_high, expected_low = _expected(hours)
        session_levels = [lv for lv in levels if _session_of(lv) is session]
        assert len(session_levels) == 2
        bsl = next(lv for lv in session_levels if lv.pool is PoolType.BSL)
        ssl = next(lv for lv in session_levels if lv.pool is PoolType.SSL)
        assert bsl.type is LiquidityType.SESSION
        assert ssl.type is LiquidityType.SESSION
        assert bsl.level == pytest.approx(expected_high)
        assert ssl.level == pytest.approx(expected_low)


def _session_of(level):
    """Recover the session from the formed_at hour (test helper)."""
    hour = level.formed_at.hour
    if hour < 7:
        return Session.ASIA
    if hour < 13:
        return Session.LONDON
    return Session.NEW_YORK


def test_20_00_to_24_00_utc_excluded(candle_factory):
    rows = _one_day_hourly_rows()
    candles = candle_factory(rows, Timeframe.H1)
    levels = detect_session_levels(candles, Timeframe.H1)
    # No level may be formed during the 20:00–24:00 "no session" gap.
    for level in levels:
        assert level.formed_at.hour < 20


def test_session_filter(candle_factory):
    candles = candle_factory(_one_day_hourly_rows(), Timeframe.H1)
    levels = detect_session_levels(
        candles, Timeframe.H1, session=Session.LONDON
    )
    assert len(levels) == 2
    assert all(_session_of(lv) is Session.LONDON for lv in levels)


def test_day_filter(candle_factory):
    candles = candle_factory(_one_day_hourly_rows(), Timeframe.H1)
    assert len(detect_session_levels(candles, Timeframe.H1, day=date(2026, 1, 1))) == 6
    assert detect_session_levels(
        candles, Timeframe.H1, day=date(2026, 1, 2)
    ) == []


def test_level_stamped_with_detection_timeframe(candle_factory):
    candles = candle_factory(_one_day_hourly_rows(), Timeframe.H1)
    levels = detect_session_levels(candles, Timeframe.H1)
    assert all(lv.timeframe is Timeframe.H1 for lv in levels)