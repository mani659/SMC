"""Phase 4 — §24 trigger expiry window tests."""

from smc.core.enums import TriggerType
from smc.triggers.trigger_expiry import poi_give_up_bars, signal_expired, window_bars_for


def test_window_mapping_matches_frozen_constants():
    assert window_bars_for(TriggerType.A_CHOCH) == 20
    assert window_bars_for(TriggerType.B_LEADING_DIAGONAL) == 30
    assert window_bars_for(TriggerType.C_ENDING_DIAGONAL) == 3
    assert window_bars_for(TriggerType.D_TWO_BAR_REVERSAL) == 1
    assert window_bars_for(TriggerType.E_RSI_DIVERGENCE) == 15
    assert window_bars_for(TriggerType.F_BOS_OB) == 1


def test_poi_give_up_uses_trigger_a_window():
    assert poi_give_up_bars() == 20


def test_signal_expired_boundaries():
    # completion at bar 5, expiry 1 → live through bar 6, dead at bar 7.
    assert not signal_expired(5, 1, 5)
    assert not signal_expired(5, 1, 6)
    assert signal_expired(5, 1, 7)
    # completion at bar 5, expiry 20 → live until bar 25.
    assert not signal_expired(5, 20, 25)
    assert signal_expired(5, 20, 26)
