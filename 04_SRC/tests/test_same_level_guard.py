"""Phase 5 — same-level SL re-entry guard tests (synthetic state)."""

from smc.config.locked_constants import (
    SAME_LEVEL_GUARD_ATR,
    SAME_LEVEL_GUARD_COOLDOWN_BARS,
)
from smc.risk.same_level_guard import SameLevelGuard, SameLevelGuardState

ATR = 10.0
ZONE = SAME_LEVEL_GUARD_ATR * ATR  # 1.5 at ATR=10


def test_blocked_within_zone_inside_cooldown():
    guard = SameLevelGuard()
    guard.record_close(sl_level=100.0, bar_index=10)
    # new SL within zone, and only 1 bar since close (< cooldown)
    assert guard.is_blocked(new_sl=100.5, atr=ATR, current_bar=11) is True


def test_allowed_outside_zone():
    guard = SameLevelGuard()
    guard.record_close(sl_level=100.0, bar_index=10)
    assert guard.is_blocked(new_sl=100.0 + ZONE + 0.01, atr=ATR, current_bar=11) is False


def test_allowed_after_cooldown_elapses():
    guard = SameLevelGuard()
    guard.record_close(sl_level=100.0, bar_index=10)
    # exactly cooldown bars later → not blocked even at the exact SL
    bar = 10 + SAME_LEVEL_GUARD_COOLDOWN_BARS
    assert guard.is_blocked(new_sl=100.0, atr=ATR, current_bar=bar) is False


def test_boundary_zone_edge_is_blocked():
    guard = SameLevelGuard()
    guard.record_close(sl_level=100.0, bar_index=10)
    # exactly zone distance away → blocked (<= semantics)
    assert guard.is_blocked(new_sl=100.0 + ZONE, atr=ATR, current_bar=11) is True


def test_no_recorded_sl_never_blocks():
    guard = SameLevelGuard()
    assert guard.is_blocked(new_sl=100.5, atr=ATR, current_bar=11) is False


def test_zero_atr_never_blocks():
    guard = SameLevelGuard()
    guard.record_close(sl_level=100.0, bar_index=10)
    assert guard.is_blocked(new_sl=100.5, atr=0.0, current_bar=11) is False


def test_recording_new_close_updates_reference_level():
    guard = SameLevelGuard()
    guard.record_close(sl_level=100.0, bar_index=10)
    guard.record_close(sl_level=105.0, bar_index=12)
    # reference is now 105.0 → a new SL near 100.5 is far outside the zone
    assert guard.is_blocked(new_sl=100.5, atr=ATR, current_bar=13) is False
    assert guard.is_blocked(new_sl=105.0 + ZONE, atr=ATR, current_bar=13) is True


def test_reset_clears_reference_for_daily_rollover():
    guard = SameLevelGuard()
    guard.record_close(sl_level=100.0, bar_index=10)
    assert guard.is_blocked(new_sl=100.5, atr=ATR, current_bar=11) is True
    guard.reset()  # v25 resets g_lastSLLevel on a new day
    assert guard.state.last_sl_level == 0.0
    assert guard.is_blocked(new_sl=100.5, atr=ATR, current_bar=11) is False


def test_replayable_with_injected_state():
    state = SameLevelGuardState(last_sl_level=100.0, last_sl_close_bar=10)
    guard = SameLevelGuard(state=state)
    assert guard.is_blocked(new_sl=100.5, atr=ATR, current_bar=11) is True