"""Phase 4 — §11 news guard tests."""

from datetime import datetime, timedelta, timezone

from smc.execution.news_guard import (
    HIGH_IMPACT_EVENTS,
    NewsEvent,
    should_block_entry,
    should_hard_cancel,
)

NOW = datetime(2026, 3, 12, 13, 0, tzinfo=timezone.utc)


def _event(kind, minutes_from_now):
    return NewsEvent(kind=kind, at=NOW + timedelta(minutes=minutes_from_now))


def test_hard_cancel_within_pre_window():
    assert should_hard_cancel(NOW, [_event("NFP", 10)])
    assert should_hard_cancel(NOW, [_event("CPI", 15)])
    assert should_hard_cancel(NOW, [_event("FOMC", 0)])


def test_no_cancel_outside_window_or_after_release():
    assert not should_hard_cancel(NOW, [_event("NFP", 16)])
    assert not should_hard_cancel(NOW, [_event("NFP", -5)])


def test_non_high_impact_event_ignored():
    assert not should_hard_cancel(NOW, [_event("Retail Sales", 10)])


def test_block_extends_through_reevaluation():
    assert should_block_entry(NOW, [_event("CPI", 10)])
    # 20 minutes after the release → still inside the 30-minute re-eval window.
    after = NOW + timedelta(minutes=50)  # event at +10 → +50 = 40 min after? no
    assert not should_block_entry(after, [_event("CPI", 10)])
    inside = NOW + timedelta(minutes=30)  # event +10 → +30 = 20 min after → blocked
    assert should_block_entry(inside, [_event("CPI", 10)])
    # 45 minutes after the release → free.
    clear = NOW + timedelta(minutes=55)
    assert not should_block_entry(clear, [_event("CPI", 10)])


def test_high_impact_set():
    assert HIGH_IMPACT_EVENTS == {"CPI", "NFP", "FOMC"}
