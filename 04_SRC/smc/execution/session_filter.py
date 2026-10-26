"""Session filter — trading-session gate (LOCKED_DECISIONS §2).

Asia 00:00–07:00, London 07:00–13:00, NY 13:00–20:00 UTC (frozen §2 hours,
sourced from ``smc.config.locked_constants`` through
``smc.utils.timestamps``). The hours 20:00–24:00 UTC belong to no session.

Which sessions the strategy trades is a CONFIGURATION choice (Phase 6/7
runners decide) — this module only decides whether a UTC timestamp is
inside one of the caller-supplied allowed sessions. All-session callers
pass the three sessions.
"""

from __future__ import annotations

from smc.utils.timestamps import Session, detect_session, to_utc

__all__ = ["ALL_SESSIONS", "is_allowed_session"]

ALL_SESSIONS = (Session.ASIA, Session.LONDON, Session.NEW_YORK)


def is_allowed_session(
    timestamp,
    allowed_sessions: list[Session] | tuple[Session, ...] = ALL_SESSIONS,
) -> bool:
    """True when ``timestamp`` (UTC-normalized) falls in an allowed session.

    Returns False outside any session (20:00–24:00 UTC) and for any session
    not listed in ``allowed_sessions``.
    """
    session = detect_session(to_utc(timestamp))
    return session is not None and session in allowed_sessions
