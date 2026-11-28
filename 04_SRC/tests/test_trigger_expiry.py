"""Phase 4 — §24 trigger expiry window tests."""

from smc.config.timeframe import Timeframe
from smc.core.enums import TriggerType
from smc.triggers.trigger_expiry import (
    ending_diagonal_anchor,
    poi_give_up_bars,
    signal_expired,
    window_bars_for,
)


def test_window_mapping_matches_frozen_constants():
    assert window_bars_for(TriggerType.A_CHOCH) == 20
    assert window_bars_for(TriggerType.B_LEADING_DIAGONAL) == 30
    assert window_bars_for(TriggerType.C_ENDING_DIAGONAL) == 3
    assert window_bars_for(TriggerType.D_TWO_BAR_REVERSAL) == 1
    assert window_bars_for(TriggerType.E_RSI_DIVERGENCE) == 15
    assert window_bars_for(TriggerType.F_BOS_OB) == 1


def test_poi_give_up_uses_trigger_a_window():
    assert poi_give_up_bars() == 20


def test_ending_diagonal_anchor_uses_frozen_swing_n():
    # §27: D1/H4/H1/W1 are N=5; M30..M1 are N=3. No new constant is used.
    assert ending_diagonal_anchor(100, Timeframe.H1) == 105
    assert ending_diagonal_anchor(100, Timeframe.H4) == 105
    assert ending_diagonal_anchor(100, Timeframe.D1) == 105
    assert ending_diagonal_anchor(100, Timeframe.W1) == 105
    assert ending_diagonal_anchor(100, Timeframe.M15) == 103
    assert ending_diagonal_anchor(100, Timeframe.M5) == 103
    assert ending_diagonal_anchor(100, Timeframe.M1) == 103


def test_ending_diagonal_legal_window_is_anchor_to_anchor_plus_three():
    anchor = ending_diagonal_anchor(22, Timeframe.H1)  # 27
    expiry = window_bars_for(TriggerType.C_ENDING_DIAGONAL)  # frozen 3
    assert expiry == 3
    # Legal bars: 27..30 inclusive (terminal ages 5..8 on H1).
    for bar in range(anchor, anchor + expiry + 1):
        assert not signal_expired(anchor, expiry, bar), bar
    # Dead one bar later; the pre-anchor bars are rejected by the trigger.
    assert signal_expired(anchor, expiry, anchor + expiry + 1)


def test_signal_expired_boundaries():
    # completion at bar 5, expiry 1 → live through bar 6, dead at bar 7.
    assert not signal_expired(5, 1, 5)
    assert not signal_expired(5, 1, 6)
    assert signal_expired(5, 1, 7)
    # completion at bar 5, expiry 20 → live until bar 25.
    assert not signal_expired(5, 20, 25)
    assert signal_expired(5, 20, 26)
