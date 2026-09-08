"""Phase 4 — OrderManager: request mapping + result parsing (fake connector)."""

import pytest

from smc.core.enums import Direction
from smc.execution.order_manager import (
    ORDER_TYPE_BUY,
    ORDER_TYPE_BUY_LIMIT,
    ORDER_TYPE_SELL,
    ORDER_TYPE_SELL_LIMIT,
    OrderKind,
    OrderManager,
    OrderRequest,
    TRADE_ACTION_PENDING,
    TRADE_ACTION_REMOVE,
)


class FakeConnector:
    def __init__(self, retcode=10008, order=555):
        self.sent: list[dict] = []
        self.retcode = retcode
        self.order = order

    def order_send(self, request: dict):
        self.sent.append(request)
        return {"retcode": self.retcode, "order": self.order, "comment": "ok"}


def _request(direction=Direction.LONG, kind=OrderKind.LIMIT, price=101.5):
    return OrderRequest(
        symbol="XAUUSD.x",
        kind=kind,
        direction=direction,
        volume=0.5,
        price=price,
        sl=100.0,
        tp=None,
        comment="t",
    )


def test_place_limit_maps_to_pending_buy_limit():
    connector = FakeConnector()
    manager = OrderManager(connector)
    result = manager.place_limit(_request())
    assert result.success and result.placed and result.ticket == 555
    sent = connector.sent[0]
    assert sent["action"] == TRADE_ACTION_PENDING
    assert sent["type"] == ORDER_TYPE_BUY_LIMIT
    assert sent["price"] == 101.5
    assert sent["sl"] == 100.0
    assert sent["volume"] == 0.5


def test_place_limit_sell_maps_to_sell_limit():
    connector = FakeConnector()
    manager = OrderManager(connector)
    manager.place_limit(_request(direction=Direction.SHORT, price=200.0))
    sent = connector.sent[0]
    assert sent["type"] == ORDER_TYPE_SELL_LIMIT


def test_place_market_maps_to_deal_type():
    connector = FakeConnector()
    manager = OrderManager(connector)
    result = manager.place_market(_request(kind=OrderKind.MARKET))
    assert result.success
    assert connector.sent[0]["type"] == ORDER_TYPE_BUY


def test_place_limit_rejects_market_request():
    connector = FakeConnector()
    manager = OrderManager(connector)
    with pytest.raises(ValueError):
        manager.place_limit(_request(kind=OrderKind.MARKET))


def test_cancel_order_removes_ticket():
    connector = FakeConnector()
    manager = OrderManager(connector)
    result = manager.cancel_order(42)
    assert result.success
    sent = connector.sent[0]
    assert sent["action"] == TRADE_ACTION_REMOVE
    assert sent["order"] == 42


def test_failed_retcode_is_not_success():
    connector = FakeConnector(retcode=10004)  # requote/reject family
    manager = OrderManager(connector)
    result = manager.place_limit(_request())
    assert not result.success


def test_modify_order_cancels_then_replaces():
    connector = FakeConnector()
    manager = OrderManager(connector)
    result = manager.modify_order(42, _request(price=102.0))
    assert result.success
    assert connector.sent[0]["action"] == TRADE_ACTION_REMOVE
    assert connector.sent[1]["action"] == TRADE_ACTION_PENDING
    assert connector.sent[1]["price"] == 102.0
