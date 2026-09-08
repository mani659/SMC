"""Phase 6 M2 — position store: open on fill, apply SL/TP closes, explicit close.

Also guards the M1/M2 backtest modules against any MT5 import (Option A:
the backtest core never touches the broker).
"""

from datetime import datetime, timedelta, timezone

import pytest

from smc.backtest.fill_model import CloseKind
from smc.backtest.orders import PendingOrderBook
from smc.backtest.positions import BacktestPosition, PositionStore
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction

NOW = datetime(2026, 3, 12, 13, 0, tzinfo=timezone.utc)


def _bar(minute_offset: int, low: float, high: float) -> Candle:
    stamp = NOW + timedelta(minutes=5 * minute_offset)
    mid = (low + high) / 2
    return Candle(
        timestamp=stamp, open=mid, high=high, low=low, close=mid, timeframe=Timeframe.M5
    )


def _open(store: PositionStore, **overrides):
    kwargs = dict(
        direction=Direction.LONG,
        volume=0.1,
        entry_price=100.0,
        sl=99.0,
        tp=102.0,
        entry_bar=10,
        entry_at=NOW,
        poi_id="poi-1",
    )
    kwargs.update(overrides)
    return store.open(**kwargs)


# ---------------------------------------------------------------------- #
# Opening
# ---------------------------------------------------------------------- #
def test_open_assigns_deterministic_tickets():
    store = PositionStore()
    first = _open(store)
    second = _open(store, entry_price=101.0)
    assert first.ticket == 1 and second.ticket == 2
    assert first.entry_at == NOW
    assert first.poi_id == "poi-1"


def test_open_rejects_bad_volume():
    with pytest.raises(ValueError):
        _open(PositionStore(), volume=0.0)


def test_open_positions_lists_in_fill_order():
    store = PositionStore()
    _open(store, entry_price=100.0)
    _open(store, entry_price=101.0)
    assert [p.entry_price for p in store.open_positions()] == [100.0, 101.0]


# ---------------------------------------------------------------------- #
# SL/TP application
# ---------------------------------------------------------------------- #
def test_apply_bar_closes_at_tp_and_records_win():
    store = PositionStore()
    position = _open(store)  # sl 99.0 / tp 102.0
    closed = store.apply_bar(_bar(1, low=100.5, high=102.2), bar_index=11)
    assert len(closed) == 1
    record = closed[0]
    assert record.position is position
    assert record.kind == CloseKind.TAKE_PROFIT
    assert record.win is True
    assert record.exit_price == pytest.approx(102.0)
    assert record.exit_bar == 11
    assert record.exit_at == NOW + timedelta(minutes=5)
    assert store.open_positions() == []
    assert store.closed_positions() == [record]


def test_apply_bar_closes_at_sl_and_records_loss():
    store = PositionStore()
    _open(store)
    closed = store.apply_bar(_bar(1, low=98.8, high=100.4), bar_index=11)
    assert closed[0].kind == CloseKind.STOP_LOSS
    assert closed[0].win is False
    assert closed[0].exit_price == pytest.approx(99.0)


def test_apply_bar_same_bar_sl_tp_sl_wins():
    store = PositionStore()
    _open(store)
    closed = store.apply_bar(_bar(1, low=98.5, high=102.5), bar_index=11)
    assert closed[0].kind == CloseKind.STOP_LOSS  # locked same-bar rule
    assert closed[0].win is False


def test_apply_bar_leaves_untouched_positions_open():
    store = PositionStore()
    _open(store)
    assert store.apply_bar(_bar(1, low=99.5, high=101.5), bar_index=11) == []
    assert len(store) == 1


def test_apply_bar_multiple_positions_deterministic_order():
    store = PositionStore()
    a = _open(store, entry_price=100.0)          # sl 99.0
    b = _open(store, entry_price=101.0, sl=100.0)  # sl 100.0
    closed = store.apply_bar(_bar(1, low=99.5, high=101.4), bar_index=11)
    # Only b's SL (100.0) is inside [99.5, 101.4]; a's SL (99.0) is not.
    assert [c.position.ticket for c in closed] == [b.ticket]
    assert closed[0].position is b
    assert store.open_positions() == [a]


def test_realized_pnl_sign_and_magnitude():
    store = PositionStore()
    _open(store, volume=0.5, entry_price=100.0, sl=99.0, tp=102.0)
    win = store.apply_bar(_bar(1, low=100.5, high=102.2), bar_index=11)[0]
    assert win.realized_pnl == pytest.approx((102.0 - 100.0) * 0.5)
    _open(store, volume=0.5, entry_price=100.0, sl=99.0, tp=102.0)
    loss = store.apply_bar(_bar(2, low=98.8, high=100.4), bar_index=12)[0]
    assert loss.realized_pnl == pytest.approx((99.0 - 100.0) * 0.5)


def test_short_pnl_is_mirrored():
    store = PositionStore()
    _open(store, direction=Direction.SHORT, volume=1.0, entry_price=100.0, sl=101.0, tp=98.0)
    win = store.apply_bar(_bar(1, low=97.9, high=100.4), bar_index=11)[0]
    assert win.realized_pnl == pytest.approx((100.0 - 98.0) * 1.0)


# ---------------------------------------------------------------------- #
# Explicit runner-driven close
# ---------------------------------------------------------------------- #
def test_explicit_close_by_ticket():
    store = PositionStore()
    position = _open(store)
    record = store.close(
        position.ticket,
        exit_price=100.8,
        exit_bar=12,
        exit_at=NOW + timedelta(minutes=10),
        kind="risk_exit",
        win=True,
    )
    assert record.position is position
    assert record.kind == "risk_exit"
    assert record.exit_at == NOW + timedelta(minutes=10)
    assert store.open_positions() == []


def test_explicit_close_unknown_ticket_raises():
    with pytest.raises(KeyError):
        PositionStore().close(7, exit_price=1.0, exit_bar=0, exit_at=NOW, kind="x", win=True)


def test_closed_positions_accumulate_in_order():
    store = PositionStore()
    _open(store)
    first = store.apply_bar(_bar(1, low=100.5, high=102.2), bar_index=11)[0]
    _open(store)
    second = store.apply_bar(_bar(2, low=98.8, high=100.4), bar_index=12)[0]
    assert store.closed_positions() == [first, second]


# ---------------------------------------------------------------------- #
# Integration: book → fill → position (M2 primitives together)
# ---------------------------------------------------------------------- #
def test_book_fill_position_round_trip():
    book = PendingOrderBook()
    order = book.place(
        direction=Direction.LONG, entry_price=100.0, sl=99.0, tp=102.0,
        volume=0.2, placed_bar=0, placed_at=NOW, poi_id="poi-1",
    )
    # Bar 1 does not reach the limit; bar 2 touches → fill at limit price.
    miss = _bar(1, low=100.4, high=101.0)
    hit = _bar(2, low=99.9, high=101.0)
    from smc.backtest.fill_model import fill_price, limit_filled

    assert not limit_filled(order.direction, order.entry_price, miss)
    assert limit_filled(order.direction, order.entry_price, hit)
    assert fill_price(order.direction, order.entry_price, hit) == pytest.approx(100.0)

    book.remove(order)
    store = PositionStore()
    position = store.open(
        direction=order.direction, volume=order.volume,
        entry_price=fill_price(order.direction, order.entry_price, hit),
        sl=order.sl, tp=order.tp, entry_bar=2,
        entry_at=hit.timestamp, poi_id=order.poi_id,
    )
    assert position.ticket == 1
    # Bar 3 hits the TP.
    closed = store.apply_bar(_bar(3, low=100.2, high=102.3), bar_index=3)
    assert closed[0].position is position
    assert closed[0].win is True


# ---------------------------------------------------------------------- #
# No MT5 in the backtest core (Option A guard)
# ---------------------------------------------------------------------- #
def test_backtest_core_imports_no_mt5():
    import sys

    import smc.backtest
    import smc.backtest.bar_loop
    import smc.backtest.clock
    import smc.backtest.data_feed
    import smc.backtest.fill_model
    import smc.backtest.orders
    import smc.backtest.positions

    assert "MetaTrader5" not in sys.modules
    mt5_names = [name for name in sys.modules if name.lower().startswith("mt5")]
    assert mt5_names == []
