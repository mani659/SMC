"""Phase 5 — Friday EOD guard tests (once-per-Friday force-close decision)."""

from datetime import datetime, timedelta, timezone

from smc.config.locked_constants import FRIDAY_EOD_CLOSE_HOUR_UTC
from smc.risk.friday_eod import FridayEod, FridayEodState

# Friday 2026-09-04 (weekday 4), a minute before the close hour.
FRIDAY_EARLY = datetime(2026, 9, 4, FRIDAY_EOD_CLOSE_HOUR_UTC - 1, 0, tzinfo=timezone.utc)
FRIDAY_AT = datetime(2026, 9, 4, FRIDAY_EOD_CLOSE_HOUR_UTC, 0, tzinfo=timezone.utc)
FRIDAY_LATE = datetime(2026, 9, 4, FRIDAY_EOD_CLOSE_HOUR_UTC + 1, 0, tzinfo=timezone.utc)
SATURDAY = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
MONDAY = datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc)


def test_no_close_before_friday_hour():
    guard = FridayEod()
    assert guard.should_force_close(FRIDAY_EARLY) is False
    assert guard.state.closed_this_friday is False


def test_close_fires_at_friday_hour():
    guard = FridayEod()
    assert guard.should_force_close(FRIDAY_AT) is True
    assert guard.state.closed_this_friday is True


def test_only_once_per_friday():
    guard = FridayEod()
    assert guard.should_force_close(FRIDAY_AT) is True
    assert guard.should_force_close(FRIDAY_LATE) is False


def test_resets_on_non_friday_bar():
    guard = FridayEod()
    guard.should_force_close(FRIDAY_AT)  # latch set
    assert guard.should_force_close(SATURDAY) is False
    assert guard.state.closed_this_friday is False
    # Re-arms for next Friday.
    next_friday = FRIDAY_AT + timedelta(days=7)
    assert guard.should_force_close(next_friday) is True


def test_resets_on_friday_before_hour_after_latch():
    guard = FridayEod()
    guard.should_force_close(FRIDAY_AT)
    assert guard.should_force_close(FRIDAY_EARLY) is False
    assert guard.state.closed_this_friday is False
    assert guard.should_force_close(FRIDAY_AT) is True  # fires again same day


def test_monday_never_fires():
    guard = FridayEod()
    assert guard.should_force_close(MONDAY) is False


def test_explicit_reset_rearms():
    guard = FridayEod()
    guard.should_force_close(FRIDAY_AT)
    guard.reset()
    assert guard.state.closed_this_friday is False
    assert guard.should_force_close(FRIDAY_AT) is True


def test_naive_datetime_treated_as_utc():
    naive = datetime(2026, 9, 4, FRIDAY_EOD_CLOSE_HOUR_UTC, 0)
    guard = FridayEod()
    assert guard.should_force_close(naive) is True


def test_replayable_with_injected_state():
    state = FridayEodState(closed_this_friday=True)
    guard = FridayEod(state=state)
    assert guard.should_force_close(FRIDAY_AT) is False  # already closed