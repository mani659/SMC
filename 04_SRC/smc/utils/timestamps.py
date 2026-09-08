"""UTC conversion and session detection (Asia / London / NY).

Session windows are frozen in LOCKED_DECISIONS §2 and read from
``smc.config.locked_constants`` (single source of truth):

    Asia   00:00–07:00 UTC
    London 07:00–13:00 UTC
    NY     13:00–20:00 UTC

Hours are inclusive of the start and exclusive of the end, so 07:00 belongs
to London and 13:00 belongs to NY. Times between 20:00 and 24:00 UTC belong
to no session (``detect_session`` returns ``None``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from smc.config.locked_constants import (
    ASIA_END_HOUR_UTC,
    ASIA_START_HOUR_UTC,
    LONDON_END_HOUR_UTC,
    LONDON_START_HOUR_UTC,
    NY_END_HOUR_UTC,
    NY_START_HOUR_UTC,
)

__all__ = ["Session", "to_utc", "detect_session", "in_session"]


class Session(Enum):
    """Trading sessions (LOCKED_DECISIONS §2)."""

    ASIA = "asia"
    LONDON = "london"
    NEW_YORK = "new_york"


def to_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC.

    Naive datetimes are assumed to already be UTC (MT5 server times should
    be converted at the data boundary — Phase 1 note).
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def detect_session(value: datetime) -> Session | None:
    """Return the session containing ``value`` (UTC), or ``None`` at
    20:00–24:00 UTC and outside any defined session."""
    hour = to_utc(value).hour
    if ASIA_START_HOUR_UTC <= hour < ASIA_END_HOUR_UTC:
        return Session.ASIA
    if LONDON_START_HOUR_UTC <= hour < LONDON_END_HOUR_UTC:
        return Session.LONDON
    if NY_START_HOUR_UTC <= hour < NY_END_HOUR_UTC:
        return Session.NEW_YORK
    return None


def in_session(value: datetime, session: Session) -> bool:
    """True when ``value`` (UTC-normalized) falls inside ``session``."""
    return detect_session(value) is session