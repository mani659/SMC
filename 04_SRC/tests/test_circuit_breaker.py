"""Phase 5 — circuit breaker tests (v25 consecutive-loss pause, synthetic state)."""

from datetime import datetime, timedelta, timezone

from smc.config.locked_constants import (
    CIRCUIT_BREAKER_LOSS_COUNT,
    CIRCUIT_BREAKER_PAUSE_HOURS,
)
from smc.risk.circuit_breaker import CircuitBreaker, CircuitBreakerState

T0 = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def test_no_block_below_loss_count():
    cb = CircuitBreaker()
    for _ in range(CIRCUIT_BREAKER_LOSS_COUNT - 1):
        cb.record_result(win=False, at=T0)
        assert cb.is_blocked(T0) is False


def test_blocks_after_loss_count_consecutive_losses():
    cb = CircuitBreaker()
    for _ in range(CIRCUIT_BREAKER_LOSS_COUNT):
        cb.record_result(win=False, at=T0)
    assert cb.is_blocked(T0) is True
    assert cb.state.active is True
    assert cb.state.consecutive_losses == CIRCUIT_BREAKER_LOSS_COUNT


def test_block_persists_within_pause_window():
    cb = CircuitBreaker()
    for _ in range(CIRCUIT_BREAKER_LOSS_COUNT):
        cb.record_result(win=False, at=T0)
    later = T0 + timedelta(hours=CIRCUIT_BREAKER_PAUSE_HOURS - 1)
    assert cb.is_blocked(later) is True


def test_releases_after_pause_window_elapses():
    cb = CircuitBreaker()
    for _ in range(CIRCUIT_BREAKER_LOSS_COUNT):
        cb.record_result(win=False, at=T0)
    after = T0 + timedelta(hours=CIRCUIT_BREAKER_PAUSE_HOURS)
    assert cb.is_blocked(after) is False
    assert cb.state.active is False
    assert cb.state.locked_at is None


def test_win_resets_counter_and_releases():
    cb = CircuitBreaker()
    for _ in range(CIRCUIT_BREAKER_LOSS_COUNT):
        cb.record_result(win=False, at=T0)
    assert cb.is_blocked(T0) is True
    cb.record_result(win=True, at=T0 + timedelta(minutes=5))
    assert cb.state.consecutive_losses == 0
    assert cb.is_blocked(T0 + timedelta(minutes=5)) is False


def test_win_before_trigger_keeps_breaker_inactive():
    cb = CircuitBreaker()
    cb.record_result(win=False, at=T0)
    cb.record_result(win=True, at=T0 + timedelta(minutes=5))
    cb.record_result(win=False, at=T0 + timedelta(minutes=10))
    assert cb.state.consecutive_losses == 1
    assert cb.is_blocked(T0 + timedelta(minutes=10)) is False


def test_reset_day_clears_counter_and_releases():
    cb = CircuitBreaker()
    for _ in range(CIRCUIT_BREAKER_LOSS_COUNT):
        cb.record_result(win=False, at=T0)
    assert cb.is_blocked(T0) is True
    cb.reset_day()
    assert cb.state.consecutive_losses == 0
    assert cb.state.active is False
    assert cb.is_blocked(T0) is False


def test_replayable_with_injected_state():
    state = CircuitBreakerState(
        consecutive_losses=CIRCUIT_BREAKER_LOSS_COUNT,
        active=True,
        locked_at=T0,
    )
    cb = CircuitBreaker(state=state)
    assert cb.is_blocked(T0) is True
    after = T0 + timedelta(hours=CIRCUIT_BREAKER_PAUSE_HOURS)
    assert cb.is_blocked(after) is False


def test_naive_datetimes_are_treated_as_utc():
    naive = datetime(2026, 9, 7, 12, 0)
    cb = CircuitBreaker()
    for _ in range(CIRCUIT_BREAKER_LOSS_COUNT):
        cb.record_result(win=False, at=naive)
    assert cb.is_blocked(naive) is True