"""Phase 1 — Swing validity gate (LOCKED_DECISIONS §19).

A swing is valid only when price breaks the Base Candle's OPPOSITE extreme
and CLOSES beyond it. Wick-only pierces and two-bar reversals are INVALID.
"""

from smc.detection.swing_validator import is_valid_swing, validate_swing


# --- Swing HIGH (opposite extreme = base candle LOW) ---------------------


def test_swing_high_valid_when_close_below_base_low(candle_factory):
    # Base candle (idx 2) low = 99.0; candle 5 closes below 99.0 -> valid.
    candles = candle_factory(
        [
            (100.0, 101.0, 99.5, 100.6),
            (100.6, 101.2, 99.8, 101.0),
            (101.0, 101.6, 99.0, 100.9),  # base candle: low 99.0
            (100.9, 101.3, 99.6, 101.1),
            (101.1, 101.4, 99.4, 101.2),
            (101.2, 101.2, 98.7, 98.6),   # breaks + closes below 99.0
            (98.6, 99.2, 98.4, 98.8),
        ]
    )
    result = validate_swing(candles, base_index=2, is_high=True)
    assert result.is_valid
    assert result.confirm_index == 5
    assert result.pierce_index == 5  # same candle wick-pierced then closed beyond


def test_swing_high_invalid_on_wick_only(candle_factory):
    # Candle wicks below 99.0 but closes back above -> INVALID (no close beyond).
    candles = candle_factory(
        [
            (100.0, 101.0, 99.5, 100.6),
            (100.6, 101.2, 99.8, 101.0),
            (101.0, 101.6, 99.0, 100.9),  # base candle: low 99.0
            (101.2, 101.3, 98.7, 99.3),   # wick 98.7 < 99.0, close 99.3 above
            (99.3, 99.8, 99.1, 99.5),     # never closes below 99.0 again
        ]
    )
    result = validate_swing(candles, base_index=2, is_high=True)
    assert not result.is_valid
    assert result.confirm_index is None
    assert result.pierce_index == 3


def test_two_bar_reversal_alone_does_not_confirm(candle_factory):
    # §19 "two-bar reversal trap": reversal candles that do not break AND
    # close beyond the base candle's low do not validate the swing.
    candles = candle_factory(
        [
            (100.0, 101.0, 99.5, 100.6),
            (101.0, 101.6, 99.0, 100.9),  # base candle: low 99.0
            (100.9, 101.0, 99.2, 99.8),   # reversal down, low still above 99.0
            (99.8, 100.5, 99.5, 100.3),   # reversal up
        ]
    )
    assert not is_valid_swing(candles, base_index=1, is_high=True)


# --- Swing LOW (opposite extreme = base candle HIGH) ----------------------


def test_swing_low_valid_when_close_above_base_high(candle_factory):
    candles = candle_factory(
        [
            (100.0, 100.8, 99.2, 100.5),
            (100.5, 101.1, 99.0, 100.6),
            (99.8, 101.0, 99.3, 99.9),   # base candle: high 101.0
            (99.9, 100.2, 99.5, 99.8),
            (99.8, 100.4, 99.6, 99.9),
            (99.9, 101.4, 99.7, 101.3),  # closes above 101.0 -> valid
        ]
    )
    result = validate_swing(candles, base_index=2, is_high=False)
    assert result.is_valid
    assert result.confirm_index == 5


def test_swing_low_invalid_on_wick_above(candle_factory):
    candles = candle_factory(
        [
            (100.0, 100.8, 99.2, 100.5),
            (99.8, 101.0, 99.3, 99.9),   # base candle: high 101.0
            (99.9, 101.3, 99.6, 100.8),  # wick 101.3 above, close 100.8 below
            (100.8, 101.0, 100.4, 100.9),
        ]
    )
    result = validate_swing(candles, base_index=1, is_high=False)
    assert not result.is_valid
    assert result.confirm_index is None
    assert result.pierce_index == 2


def test_validator_requires_data_after_base(candle_factory):
    candles = candle_factory(
        [
            (101.0, 101.6, 99.0, 100.9),  # base only, nothing after
        ]
    )
    result = validate_swing(candles, base_index=0, is_high=True)
    assert not result.is_valid
    assert result.pierce_index is None
    assert result.confirm_index is None