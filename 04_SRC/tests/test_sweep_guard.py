"""Phase 5 — failed-sweep re-entry guard tests (synthetic per-direction state)."""

from smc.config.locked_constants import (
    SWEEP_GUARD_COOLDOWN_BARS,
    SWEEP_GUARD_ZONE_ATR,
)
from smc.risk.sweep_guard import SweepGuard, SweepGuardState

ATR = 10.0
ZONE = SWEEP_GUARD_ZONE_ATR * ATR  # 5.0 at ATR=10


def test_blocked_within_zone_inside_cooldown():
    guard = SweepGuard()
    guard.record_failed_sweep(sweep_level=100.0, bar_index=10, is_long=True)
    assert guard.is_blocked(sweep_level=100.5, atr=ATR, current_bar=11, is_long=True) is True


def test_allowed_outside_zone():
    guard = SweepGuard()
    guard.record_failed_sweep(sweep_level=100.0, bar_index=10, is_long=True)
    assert guard.is_blocked(sweep_level=100.0 + ZONE + 0.01, atr=ATR, current_bar=11, is_long=True) is False


def test_allowed_after_cooldown_elapses():
    guard = SweepGuard()
    guard.record_failed_sweep(sweep_level=100.0, bar_index=10, is_long=True)
    bar = 10 + SWEEP_GUARD_COOLDOWN_BARS
    assert guard.is_blocked(sweep_level=100.0, atr=ATR, current_bar=bar, is_long=True) is False


def test_boundary_zone_edge_is_blocked():
    guard = SweepGuard()
    guard.record_failed_sweep(sweep_level=100.0, bar_index=10, is_long=True)
    assert guard.is_blocked(sweep_level=100.0 + ZONE, atr=ATR, current_bar=11, is_long=True) is True


def test_no_recorded_failure_never_blocks():
    guard = SweepGuard()
    assert guard.is_blocked(sweep_level=100.5, atr=ATR, current_bar=11, is_long=True) is False
    assert guard.is_blocked(sweep_level=100.5, atr=ATR, current_bar=11, is_long=False) is False


def test_zero_atr_never_blocks():
    guard = SweepGuard()
    guard.record_failed_sweep(sweep_level=100.0, bar_index=10, is_long=True)
    assert guard.is_blocked(sweep_level=100.5, atr=0.0, current_bar=11, is_long=True) is False


def test_directions_are_independent():
    guard = SweepGuard()
    guard.record_failed_sweep(sweep_level=100.0, bar_index=10, is_long=True)
    # SHORT side has no failure recorded → not blocked.
    assert guard.is_blocked(sweep_level=100.5, atr=ATR, current_bar=11, is_long=False) is False
    # LONG side IS blocked.
    assert guard.is_blocked(sweep_level=100.5, atr=ATR, current_bar=11, is_long=True) is True


def test_short_direction_blocks_independently():
    guard = SweepGuard()
    guard.record_failed_sweep(sweep_level=200.0, bar_index=20, is_long=False)
    assert guard.is_blocked(sweep_level=200.5, atr=ATR, current_bar=21, is_long=False) is True
    assert guard.is_blocked(sweep_level=200.5, atr=ATR, current_bar=21, is_long=True) is False


def test_reset_day_clears_both_directions():
    guard = SweepGuard()
    guard.record_failed_sweep(sweep_level=100.0, bar_index=10, is_long=True)
    guard.record_failed_sweep(sweep_level=200.0, bar_index=10, is_long=False)
    guard.reset_day()
    assert guard.is_blocked(sweep_level=100.0, atr=ATR, current_bar=11, is_long=True) is False
    assert guard.is_blocked(sweep_level=200.0, atr=ATR, current_bar=11, is_long=False) is False


def test_replayable_with_injected_state():
    state = SweepGuardState(
        failed_sweep_level_long=100.0,
        failed_sweep_bar_long=10,
        failed_sweep_level_short=0.0,
        failed_sweep_bar_short=0,
    )
    guard = SweepGuard(state=state)
    assert guard.is_blocked(sweep_level=100.5, atr=ATR, current_bar=11, is_long=True) is True
    assert guard.is_blocked(sweep_level=100.5, atr=ATR, current_bar=11, is_long=False) is False