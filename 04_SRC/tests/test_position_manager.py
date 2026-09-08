"""Phase 4 — PositionManager: snapshots, SL/TP moves, closes (fake connector)."""

from smc.core.enums import Direction
from smc.execution.position_manager import PositionManager


class FakeConnector:
    def __init__(self, positions=None):
        self.positions = positions or []
        self.sent: list[dict] = []
        self.next_retcode = 10009

    def positions_get(self, symbol=None):
        return self.positions

    def order_send(self, request: dict):
        self.sent.append(request)
        return {"retcode": self.next_retcode, "order": 0, "comment": "ok"}


def _mt5_position(ticket=1, direction=0, volume=0.1, price=100.0, sl=0.0, tp=0.0):
    # dict form mirrors the MT5 position named-tuple attributes
    return {
        "ticket": ticket,
        "symbol": "XAUUSD.x",
        "type": direction,  # 0 = BUY
        "volume": volume,
        "price_open": price,
        "sl": sl,
        "tp": tp,
    }


def test_list_positions_maps_snapshot():
    connector = FakeConnector(positions=[_mt5_position(ticket=7, direction=0, sl=99.0)])
    snapshots = PositionManager(connector).list_positions()
    assert len(snapshots) == 1
    s = snapshots[0]
    assert s.ticket == 7
    assert s.direction is Direction.LONG
    assert s.volume == 0.1
    assert s.sl == 99.0
    assert s.tp is None


def test_modify_sl_sends_sltp_action():
    connector = FakeConnector(
        positions=[_mt5_position(ticket=7, direction=0, sl=99.0, tp=105.0)]
    )
    manager = PositionManager(connector)
    assert manager.modify_sl(7, 98.5)
    sent = connector.sent[0]
    assert sent["action"] == 6  # TRADE_ACTION_SLTP
    assert sent["position"] == 7
    assert sent["sl"] == 98.5


def test_modify_sl_does_not_clear_tp():
    # C1 regression: the SL move must re-send the CURRENT TP, not 0.0.
    connector = FakeConnector(
        positions=[_mt5_position(ticket=7, direction=0, sl=99.0, tp=105.0)]
    )
    manager = PositionManager(connector)
    assert manager.modify_sl(7, 98.5)
    sent = connector.sent[0]
    assert sent["tp"] == 105.0  # current TP preserved — never 0.0


def test_modify_tp_does_not_clear_sl():
    # C1 regression: the TP move must re-send the CURRENT SL, not 0.0.
    connector = FakeConnector(
        positions=[_mt5_position(ticket=7, direction=0, sl=99.0, tp=105.0)]
    )
    manager = PositionManager(connector)
    assert manager.modify_tp(7, 106.0)
    sent = connector.sent[0]
    assert sent["sl"] == 99.0  # current SL preserved — never 0.0
    assert sent["tp"] == 106.0


def test_modify_without_protective_level_sends_zero_for_that_field_only():
    # A position with NO TP keeps sending tp=0.0 (nothing to preserve), while
    # its SL is re-sent untouched on a TP move.
    connector = FakeConnector(
        positions=[_mt5_position(ticket=7, direction=0, sl=99.0, tp=0.0)]
    )
    manager = PositionManager(connector)
    assert manager.modify_sl(7, 98.5)
    assert connector.sent[0]["tp"] == 0.0  # position genuinely has no TP
    assert manager.modify_tp(7, 106.0)
    assert connector.sent[1]["sl"] == 99.0


def test_modify_unknown_ticket_raises_instead_of_clobbering():
    # C1: with no position to read the opposite protective price from, the
    # manager must NOT send a request that would zero the other field.
    connector = FakeConnector(positions=[])
    manager = PositionManager(connector)
    try:
        manager.modify_sl(7, 98.5)
        raised = False
    except ValueError:
        raised = True
    assert raised
    assert connector.sent == []  # nothing was sent to the broker


def test_close_position_sends_opposite_deal():
    connector = FakeConnector()
    manager = PositionManager(connector)
    # Closing a LONG position sends a SELL (type 1).
    assert manager.close_position(7, Direction.LONG, volume=0.1)
    sent = connector.sent[0]
    assert sent["action"] == 1  # TRADE_ACTION_DEAL
    assert sent["type"] == 1  # ORDER_TYPE_SELL
    assert sent["volume"] == 0.1
