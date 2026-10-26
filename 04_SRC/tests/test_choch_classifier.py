"""Phase 2 — CHOCH Rule 1/2/3 classifier API tests (§17, §20)."""

from smc.core.enums import Direction
from smc.poi.choch_classifier import ChochRule, classify_choch_at

# Each row is (open, high, low, close); indexes are noted per fixture.


def _rule1_rows():
    """Uptrend, valid low L=99.0 (idx4), valid high H=100.8 (idx8),
    H swept (wick above, body back) at idx10, then body close below L at idx13."""
    return [
        (100.0, 100.2, 99.8, 99.9),   # 0
        (99.9, 100.1, 99.6, 99.7),    # 1
        (99.7, 99.9, 99.4, 99.5),     # 2
        (99.5, 99.7, 99.2, 99.3),     # 3
        (99.3, 99.6, 99.0, 99.4),     # 4 L low 99.0
        (99.4, 99.8, 99.3, 99.7),     # 5
        (99.7, 100.2, 99.6, 100.1),   # 6
        (100.1, 100.6, 100.0, 100.5),  # 7
        (100.5, 100.8, 100.3, 100.6),  # 8 H high 100.8
        (100.6, 101.0, 100.5, 100.9),  # 9
        (100.9, 101.3, 100.5, 100.6),  # 10 sweep of H
        (100.4, 100.7, 100.1, 100.2),  # 11
        (100.0, 100.3, 99.4, 99.6),    # 12
        (99.4, 99.6, 98.5, 98.7),      # 13 body close below 99.0
    ]


def _swings(candles, swing_factory, entries):
    return [
        swing_factory(candles, idx, is_high, level=level, is_valid=is_valid)
        for idx, is_high, level, is_valid in entries
    ]


def test_rule1_standard_bearish(candle_factory, swing_factory):
    candles = candle_factory(_rule1_rows())
    swings = _swings(
        candles,
        swing_factory,
        [(4, False, 99.0, True), (8, True, 100.8, True)],
    )
    result = classify_choch_at(candles, swings, bar_index=13)
    assert result is not None
    assert result.direction is Direction.SHORT
    assert result.rule is ChochRule.RULE_1_STANDARD
    assert result.broken_level == 99.0
    assert result.break_index == 13
    assert result.sweep_index == 10


def test_rule2_inside_body_bearish(candle_factory, swing_factory):
    rows = [
        (100.0, 100.2, 99.6, 99.7),    # 0
        (99.7, 99.9, 99.4, 99.5),      # 1
        (99.5, 99.7, 99.2, 99.3),      # 2
        (99.3, 99.6, 99.0, 99.4),      # 3 last valid low 99.0
        (99.4, 99.8, 99.3, 99.7),      # 4
        (99.7, 100.2, 99.6, 100.1),    # 5
        (100.1, 100.6, 100.0, 100.5),  # 6
        (100.5, 100.9, 100.4, 100.8),  # 7
        (100.8, 101.2, 100.6, 101.0),  # 8 last valid high 101.2
        (101.0, 101.5, 100.7, 100.8),  # 9 sweep of high
        (100.6, 100.9, 100.0, 100.2),  # 10
        (100.0, 100.3, 99.6, 99.8),    # 11 minor (unconfirmed) low 99.6
        (99.9, 100.2, 99.7, 99.95),    # 12
        (99.6, 99.8, 99.2, 99.45),     # 13 close below 99.6, above 99.0
    ]
    candles = candle_factory(rows)
    swings = _swings(
        candles,
        swing_factory,
        [
            (3, False, 99.0, True),
            (8, True, 101.2, True),
            (11, False, 99.6, False),  # intermediate, NOT §19-valid
        ],
    )
    result = classify_choch_at(candles, swings, bar_index=13)
    assert result is not None
    assert result.direction is Direction.SHORT
    assert result.rule is ChochRule.RULE_2_INSIDE_BODY
    assert result.broken_level == 99.6
    assert result.break_index == 13


def test_rule3_inside_wick_bearish(candle_factory, swing_factory):
    rows = _rule1_rows()
    rows[13] = (99.2, 99.5, 98.4, 99.2)  # wick below 99.0, body closes back above
    candles = candle_factory(rows)
    swings = _swings(
        candles,
        swing_factory,
        [(4, False, 99.0, True), (8, True, 100.8, True)],
    )
    result = classify_choch_at(candles, swings, bar_index=13)
    assert result is not None
    assert result.direction is Direction.SHORT
    assert result.rule is ChochRule.RULE_3_INSIDE_WICK
    assert result.broken_level == 99.0
    assert result.break_index == 13


def test_rule1_bullish_via_price_inversion(candle_factory, swing_factory):
    rows = [
        (100.0, 100.4, 99.8, 100.2),   # 0
        (100.2, 100.7, 100.0, 100.5),  # 1
        (100.5, 101.1, 100.4, 100.9),  # 2
        (100.9, 101.5, 100.7, 101.3),  # 3 last valid high 101.5
        (101.3, 101.6, 101.0, 101.2),  # 4
        (101.1, 101.4, 100.8, 100.9),  # 5
        (100.9, 101.1, 100.5, 100.6),  # 6
        (100.6, 100.8, 100.1, 100.2),  # 7
        (100.2, 100.4, 99.5, 99.9),    # 8 last valid low 99.5
        (99.9, 100.1, 99.4, 99.8),     # 9 sweep of low (wick below, close above)
        (99.8, 100.0, 99.6, 99.7),     # 10
        (99.7, 100.0, 99.5, 99.9),     # 11
        (100.0, 100.4, 99.8, 100.2),   # 12
        (100.3, 102.0, 100.1, 101.8),  # 13 body close above 101.5
    ]
    candles = candle_factory(rows)
    swings = _swings(
        candles,
        swing_factory,
        [(3, True, 101.5, True), (8, False, 99.5, True)],
    )
    result = classify_choch_at(candles, swings, bar_index=13)
    assert result is not None
    assert result.direction is Direction.LONG
    assert result.rule is ChochRule.RULE_1_STANDARD
    assert result.broken_level == 101.5
    assert result.break_index == 13


def test_no_break_returns_none(candle_factory, swing_factory):
    rows = _rule1_rows()
    rows[13] = (99.6, 99.9, 99.3, 99.7)  # drift: no close below 99.0, no wick either
    candles = candle_factory(rows)
    swings = _swings(
        candles,
        swing_factory,
        [(4, False, 99.0, True), (8, True, 100.8, True)],
    )
    assert classify_choch_at(candles, swings, bar_index=13) is None


def test_no_sweep_of_final_extreme_returns_none(candle_factory, swing_factory):
    rows = _rule1_rows()
    rows[10] = (100.9, 101.1, 100.6, 101.0)  # no wick above 100.8 -> no sweep
    candles = candle_factory(rows)
    swings = _swings(
        candles,
        swing_factory,
        [(4, False, 99.0, True), (8, True, 100.8, True)],
    )
    assert classify_choch_at(candles, swings, bar_index=13) is None
