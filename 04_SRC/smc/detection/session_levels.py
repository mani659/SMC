"""Session high/low levels (LOCKED_DECISIONS §2).

Session windows are frozen in §2 and enforced via ``smc.utils.timestamps``:

    Asia   00:00–07:00 UTC
    London 07:00–13:00 UTC
    NY     13:00–20:00 UTC

Each candle is assigned to a session by its bar-open timestamp (UTC). The
high/low of every candle inside a (UTC day, session) window forms one BSL
high level and one SSL low level. Candles between 20:00 and 24:00 UTC
belong to no session and are skipped, matching ``detect_session``.

Day boundaries are UTC calendar days; bars are expected to already be
UTC-normalized at the data boundary.
"""

from __future__ import annotations

from datetime import date

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import LiquidityType, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.utils.timestamps import Session, detect_session

__all__ = ["detect_session_levels"]


def detect_session_levels(
    candles: list[Candle],
    timeframe: Timeframe,
    session: Session | None = None,
    day: date | None = None,
) -> list[LiquidityLevel]:
    """Compute session high/low levels over the provided candles.

    Parameters
    ----------
    candles:
        Chronological UTC candles to aggregate by (UTC day, session).
    timeframe:
        Session timeframe (the TF the candles were taken from).
    session:
        Optional filter — only levels for this session are returned.
    day:
        Optional filter — only levels for this UTC calendar day.

    Returns
    -------
    LiquidityLevel list: one BSL high and one SSL low per (day, session)
    group present in the data, ordered chronologically.
    """
    groups: dict[tuple[date, Session], list[Candle]] = {}
    for candle in candles:
        detected = detect_session(candle.timestamp)
        if detected is None:
            continue
        if session is not None and detected is not session:
            continue
        key = (candle.timestamp.date(), detected)
        if day is not None and key[0] != day:
            continue
        groups.setdefault(key, []).append(candle)

    levels: list[LiquidityLevel] = []
    for (group_day, group_session), group in sorted(
        groups.items(), key=lambda kv: (kv[0][0], kv[0][1].value)
    ):
        high_candle = max(group, key=lambda c: c.high)
        low_candle = min(group, key=lambda c: c.low)
        levels.append(
            LiquidityLevel(
                type=LiquidityType.SESSION,
                level=high_candle.high,
                pool=PoolType.BSL,
                timeframe=timeframe,
                formed_at=high_candle.timestamp,
            )
        )
        levels.append(
            LiquidityLevel(
                type=LiquidityType.SESSION,
                level=low_candle.low,
                pool=PoolType.SSL,
                timeframe=timeframe,
                formed_at=low_candle.timestamp,
            )
        )
    return levels