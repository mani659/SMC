"""Phase 4 — §2 session gate tests."""

from datetime import datetime, timezone

from smc.execution.session_filter import is_allowed_session
from smc.utils.timestamps import Session


def _utc(hour):
    return datetime(2026, 3, 12, hour, 0, tzinfo=timezone.utc)


def test_asia_morning_allowed():
    assert is_allowed_session(_utc(2), [Session.ASIA])
    assert not is_allowed_session(_utc(2), [Session.LONDON])


def test_london_window():
    assert is_allowed_session(_utc(8), [Session.LONDON])
    assert not is_allowed_session(_utc(8), [Session.NEW_YORK])


def test_ny_afternoon():
    assert is_allowed_session(_utc(14), [Session.NEW_YORK])
    assert not is_allowed_session(_utc(14), [Session.ASIA])


def test_closed_hours_allowed_nowhere():
    assert not is_allowed_session(_utc(22), [Session.ASIA, Session.LONDON, Session.NEW_YORK])


def test_default_allows_any_session():
    assert is_allowed_session(_utc(3))  # default = all sessions
    assert is_allowed_session(_utc(19))
