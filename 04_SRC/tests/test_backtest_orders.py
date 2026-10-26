"""Phase 6 M2 — pending order book: place/cancel/expire, deterministic tickets."""

from datetime import datetime, timezone

import pytest

from smc.backtest.orders import PendingOrderBook
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType

NOW = datetime(2026, 3, 12, 13, 0, tzinfo=timezone.utc)


def _place(book: PendingOrderBook, **overrides):
    kwargs = dict(
        direction=Direction.LONG,
        entry_price=100.0,
        sl=99.0,
        tp=102.0,
        volume=0.1,
        placed_bar=10,
        placed_at=NOW,
        poi_id="poi-1",
        trigger=TriggerType.A_CHOCH,
    )
    kwargs.update(overrides)
    return book.place(**kwargs)


# ---------------------------------------------------------------------- #
# Placement + identity
# ---------------------------------------------------------------------- #
def test_place_returns_order_with_deterministic_ticket():
    book = PendingOrderBook()
    first = _place(book)
    second = _place(book, entry_price=101.0)
    assert first.ticket == 1
    assert second.ticket == 2  # monotonically increasing, no randomness
    assert first.direction is Direction.LONG
    assert first.entry_price == pytest.approx(100.0)
    assert first.poi_id == "poi-1"
    assert first.trigger is TriggerType.A_CHOCH


def test_ticket_sequence_starts_at_injected_first_ticket():
    book = PendingOrderBook(first_ticket=500)
    assert _place(book).ticket == 500
    assert _place(book).ticket == 501


def test_place_rejects_bad_volume_and_price():
    book = PendingOrderBook()
    with pytest.raises(ValueError):
        _place(book, volume=0.0)
    with pytest.raises(ValueError):
        _place(book, entry_price=-1.0)


def test_active_lists_in_placement_order():
    book = PendingOrderBook()
    _place(book, entry_price=100.0)
    _place(book, entry_price=101.0)
    _place(book, entry_price=102.0)
    assert [o.entry_price for o in book.active()] == [100.0, 101.0, 102.0]
    assert len(book) == 3


# ---------------------------------------------------------------------- #
# Cancellation
# ---------------------------------------------------------------------- #
def test_cancel_removes_order_by_ticket():
    book = PendingOrderBook()
    order = _place(book)
    cancelled = book.cancel(order.ticket)
    assert cancelled is order
    assert book.active() == []
    assert book.cancel(order.ticket) is None  # already gone — no error


def test_cancel_unknown_ticket_returns_none():
    book = PendingOrderBook()
    assert book.cancel(999) is None


def test_remove_is_idempotent():
    book = PendingOrderBook()
    order = _place(book)
    book.remove(order)
    book.remove(order)  # second remove is a no-op
    assert book.active() == []


# ---------------------------------------------------------------------- #
# Expiry
# ---------------------------------------------------------------------- #
def test_section23_expiry_m5_twelve_bars():
    book = PendingOrderBook()
    early = _place(book, placed_bar=0)
    late = _place(book, placed_bar=5)
    # bars_open for `early` at bar 11 = 12 → expired; `late` = 7 → resting.
    cancelled = book.expired_by_section23(current_bar=11, timeframe=Timeframe.M5)
    assert cancelled == [early]
    assert [o.ticket for o in book.active()] == [late.ticket]


def test_section23_boundary_is_inclusive():
    book = PendingOrderBook()
    order = _place(book, placed_bar=0)
    # bars_open = 11 at bar 10 → still resting (12 is the frozen limit);
    # bars_open = 12 at bar 11 → expired. Mirrors the state machine's
    # expire_unfilled(poi, bars_open=11 → FRESH / 12 → TESTED) test.
    assert book.expired_by_section23(current_bar=10, timeframe=Timeframe.M5) == []
    assert book.expired_by_section23(current_bar=11, timeframe=Timeframe.M5) == [order]


def test_section23_no_rule_for_h1_never_expires():
    book = PendingOrderBook()
    order = _place(book, placed_bar=0)
    # H1+ has no frozen §23 rule — the runner decides, the book never invents one.
    assert book.expired_by_section23(current_bar=10_000, timeframe=Timeframe.H1) == []
    assert book.active() == [order]


def test_give_up_expiry_backstop():
    book = PendingOrderBook()
    order = _place(book, placed_bar=0)
    # poi_give_up_bars() = 20 (Trigger A window); bars_open uses the SAME
    # convention as POIStateMachine.expire_unfilled — placement bar counts
    # as the first open bar, so bars_open = 20 at current_bar 19.
    assert book.expired_by_give_up(current_bar=18) == []  # bars_open 19
    assert book.expired_by_give_up(current_bar=19) == [order]  # bars_open 20


def test_multiple_orders_expire_deterministically():
    book = PendingOrderBook()
    a = _place(book, placed_bar=0)
    b = _place(book, placed_bar=2)
    c = _place(book, placed_bar=4)
    cancelled = book.expired_by_section23(current_bar=13, timeframe=Timeframe.M5)
    # bars_open = current_bar - placed_bar + 1 → a=14, b=12, c=10 at bar 13:
    # a and b are at/over the frozen 12, c is not.
    assert cancelled == [a, b]  # placement order preserved
    assert [o.ticket for o in book.active()] == [c.ticket]
