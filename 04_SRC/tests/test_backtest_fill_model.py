"""Phase 6 M2 — fill model: touch semantics, fill price, SL/TP, SL-first rule."""

import pytest

from smc.backtest.fill_model import (
    CloseKind,
    evaluate_position_bar,
    fill_price,
    limit_filled,
    sl_hit,
    tp_hit,
)
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.config.timeframe import Timeframe


def _bar(low, high, open_=None, close=None):
    open_ = open_ if open_ is not None else (low + high) / 2
    close = close if close is not None else (low + high) / 2
    return Candle(
        timestamp=__import__("datetime").datetime(2026, 3, 12, 13, 0, tzinfo=__import__("datetime").timezone.utc),
        open=open_,
        high=high,
        low=low,
        close=close,
        timeframe=Timeframe.M5,
    )


# ---------------------------------------------------------------------- #
# Limit fills (touch semantics)
# ---------------------------------------------------------------------- #
def test_buy_limit_fills_when_low_touches_limit():
    # Limit 100.0; bar low 100.0 = exact touch → fills (inclusive).
    assert limit_filled(Direction.LONG, 100.0, _bar(low=100.0, high=101.0))


def test_buy_limit_fills_when_low_trades_through():
    assert limit_filled(Direction.LONG, 100.0, _bar(low=99.5, high=101.0))


def test_buy_limit_no_fill_when_low_stays_above():
    assert not limit_filled(Direction.LONG, 100.0, _bar(low=100.1, high=101.0))


def test_sell_limit_fills_when_high_touches_limit():
    assert limit_filled(Direction.SHORT, 102.0, _bar(low=101.0, high=102.0))
    assert limit_filled(Direction.SHORT, 102.0, _bar(low=101.0, high=102.5))


def test_sell_limit_no_fill_when_high_stays_below():
    assert not limit_filled(Direction.SHORT, 102.0, _bar(low=101.0, high=101.9))


def test_fill_price_is_always_the_limit_price():
    # Locked: fill at the limit — no better-of-open even when the bar gaps
    # far through the level (bar low 98.0 well below the 100.0 limit).
    bar = _bar(low=98.0, high=101.0, open_=100.8)
    assert limit_filled(Direction.LONG, 100.0, bar)
    assert fill_price(Direction.LONG, 100.0, bar) == pytest.approx(100.0)


def test_fill_price_raises_when_no_touch():
    with pytest.raises(ValueError):
        fill_price(Direction.LONG, 100.0, _bar(low=100.5, high=101.0))


# ---------------------------------------------------------------------- #
# SL / TP hits
# ---------------------------------------------------------------------- #
def test_sl_hit_long_and_short():
    assert sl_hit(Direction.LONG, 99.0, _bar(low=99.0, high=100.5))
    assert sl_hit(Direction.LONG, 99.0, _bar(low=98.5, high=100.5))
    assert not sl_hit(Direction.LONG, 99.0, _bar(low=99.1, high=100.5))
    assert sl_hit(Direction.SHORT, 101.0, _bar(low=100.0, high=101.0))
    assert not sl_hit(Direction.SHORT, 101.0, _bar(low=100.0, high=100.9))


def test_tp_hit_long_and_short():
    assert tp_hit(Direction.LONG, 102.0, _bar(low=100.0, high=102.0))
    assert not tp_hit(Direction.LONG, 102.0, _bar(low=100.0, high=101.9))
    assert tp_hit(Direction.SHORT, 99.0, _bar(low=99.0, high=100.5))
    assert not tp_hit(Direction.SHORT, 99.0, _bar(low=99.1, high=100.5))


# ---------------------------------------------------------------------- #
# Position bar evaluation + same-bar rule
# ---------------------------------------------------------------------- #
def test_no_close_when_range_misses_both_levels():
    decision = evaluate_position_bar(Direction.LONG, 99.0, 102.0, _bar(low=99.5, high=101.5))
    assert not decision.closed


def test_sl_only_close_is_a_loss_at_sl_price():
    decision = evaluate_position_bar(Direction.LONG, 99.0, 102.0, _bar(low=98.8, high=101.0))
    assert decision.closed
    assert decision.kind is CloseKind.STOP_LOSS or decision.kind == CloseKind.STOP_LOSS
    assert decision.kind == "stop_loss"
    assert decision.price == pytest.approx(99.0)
    assert decision.win is False


def test_tp_only_close_is_a_win_at_tp_price():
    decision = evaluate_position_bar(Direction.LONG, 99.0, 102.0, _bar(low=100.5, high=102.2))
    assert decision.closed
    assert decision.kind == "take_profit"
    assert decision.price == pytest.approx(102.0)
    assert decision.win is True


def test_same_bar_sl_and_tp_sl_wins():
    # Bar [98.5, 102.5] touches BOTH the 99.0 SL and the 102.0 TP —
    # locked rule: SL first (worst case), close at SL as a loss.
    decision = evaluate_position_bar(Direction.LONG, 99.0, 102.0, _bar(low=98.5, high=102.5))
    assert decision.closed
    assert decision.kind == "stop_loss"
    assert decision.price == pytest.approx(99.0)
    assert decision.win is False


def test_same_bar_rule_independent_of_evaluation_order():
    # Order-independence: the rule is explicit, not evaluation-order luck.
    bar = _bar(low=98.5, high=102.5)
    first = evaluate_position_bar(Direction.LONG, 99.0, 102.0, bar)
    second = evaluate_position_bar(Direction.LONG, 99.0, 102.0, bar)
    assert first == second  # pure function, deterministic


def test_short_same_bar_sl_and_tp_sl_wins():
    # SHORT: SL 101.0 above, TP 99.0 below; bar [98.5, 101.2] touches both.
    decision = evaluate_position_bar(Direction.SHORT, 101.0, 99.0, _bar(low=98.5, high=101.2))
    assert decision.closed
    assert decision.kind == "stop_loss"
    assert decision.price == pytest.approx(101.0)
    assert decision.win is False


def test_position_without_tp_never_closes_at_tp():
    decision = evaluate_position_bar(Direction.LONG, 99.0, None, _bar(low=99.2, high=110.0))
    assert not decision.closed  # huge bar, but no TP set and SL untouched


def test_position_without_sl_closes_only_at_tp():
    decision = evaluate_position_bar(Direction.LONG, None, 102.0, _bar(low=99.0, high=102.1))
    assert decision.closed
    assert decision.kind == "take_profit"
