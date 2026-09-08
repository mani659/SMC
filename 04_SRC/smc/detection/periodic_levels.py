"""Periodic levels — PDH/PDL and PWH/PWL (LOCKED_DECISIONS §2).

* PDH/PDL: high/low of the most recent COMPLETED UTC trading day before
  ``as_of`` (calendar days without any candles — weekends, holidays — are
  skipped, so Monday sees Friday's levels).
* PWH/PWL: high/low of the most recent COMPLETED week before ``as_of``
  (weeks are Monday-anchored).

Candles are aggregated to day/week bars by their bar-open timestamp (UTC).
Both references always refer to periods that have fully closed before
``as_of``, so the levels are stable intraday.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import LiquidityType, PoolType
from smc.core.liquidity_level import LiquidityLevel

__all__ = ["detect_periodic_levels"]


def _monday(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _aggregate(candles: list[Candle]) -> tuple[dict, dict]:
    """Aggregate candles into per-day and per-week (Monday) extremes."""
    daily: dict[date, dict] = defaultdict(lambda: {"high": None, "low": None})
    weekly: dict[date, dict] = defaultdict(lambda: {"high": None, "low": None})
    for candle in candles:
        day = candle.timestamp.date()
        week = _monday(day)
        for bucket, key in ((daily, day), (weekly, week)):
            entry = bucket[key]
            if entry["high"] is None or candle.high > entry["high"][0]:
                entry["high"] = (candle.high, candle.timestamp)
            if entry["low"] is None or candle.low < entry["low"][0]:
                entry["low"] = (candle.low, candle.timestamp)
    return dict(daily), dict(weekly)


def detect_periodic_levels(
    candles: list[Candle],
    timeframe: Timeframe,
    as_of: datetime | None = None,
) -> list[LiquidityLevel]:
    """Detect PDH/PDL and PWH/PWL valid as of a reference moment.

    Parameters
    ----------
    candles:
        Chronological UTC candles spanning at least the previous day/week.
    timeframe:
        Timeframe of the supplied candles (stamped on the levels).
    as_of:
        Reference moment; defaults to the timestamp of the last candle.
        The previous completed day/week are computed against it.

    Returns
    -------
    Up to four LiquidityLevels: PDH (BSL), PDL (SSL), PWH (BSL), PWL (SSL).
    Families whose reference period is absent from the data are omitted.
    """
    reference = as_of or candles[-1].timestamp
    daily, weekly = _aggregate(candles)

    completed_days = [d for d in daily if d < reference.date()]
    completed_weeks = [w for w in weekly if w < _monday(reference.date())]

    levels: list[LiquidityLevel] = []
    day_entry = daily.get(max(completed_days)) if completed_days else None
    if day_entry is not None:
        high_price, high_time = day_entry["high"]
        low_price, low_time = day_entry["low"]
        levels.append(
            LiquidityLevel(
                type=LiquidityType.PREVIOUS_DAY,
                level=high_price,
                pool=PoolType.BSL,
                timeframe=timeframe,
                formed_at=high_time,
            )
        )
        levels.append(
            LiquidityLevel(
                type=LiquidityType.PREVIOUS_DAY,
                level=low_price,
                pool=PoolType.SSL,
                timeframe=timeframe,
                formed_at=low_time,
            )
        )

    week_entry = weekly.get(max(completed_weeks)) if completed_weeks else None
    if week_entry is not None:
        high_price, high_time = week_entry["high"]
        low_price, low_time = week_entry["low"]
        levels.append(
            LiquidityLevel(
                type=LiquidityType.PREVIOUS_WEEK,
                level=high_price,
                pool=PoolType.BSL,
                timeframe=timeframe,
                formed_at=high_time,
            )
        )
        levels.append(
            LiquidityLevel(
                type=LiquidityType.PREVIOUS_WEEK,
                level=low_price,
                pool=PoolType.SSL,
                timeframe=timeframe,
                formed_at=low_time,
            )
        )
    return levels