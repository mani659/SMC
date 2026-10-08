"""Track A residual E1 — entry_anchor end-to-end export (logging only).

Proves: the trigger signal's ``entry_anchor`` flows signal → candidate →
pending order → position (verbatim through BE/modify_sl) → TradeRecord →
CSV/JSON export as a first-class column/key, AND stays inside
``signal_data_json``. Absent anchor stays ``None``/empty — never invented.
Decisions (entry/SL/TP mapping) are untouched.
"""

import json
from types import SimpleNamespace

from smc.backtest.export import to_csv, to_json
from smc.backtest.orders import PendingOrderBook
from smc.backtest.pipeline_bridge import candidate_from_route
from smc.backtest.positions import PositionStore
from smc.backtest.reports import TradeRecord
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.triggers.base_trigger import TriggerSignal
from smc.triggers.trigger_router import TriggerRoute

TF = Timeframe.M5


def _route(anchor):
    poi = POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M8],
    )
    data = {"entry_anchor": anchor} if anchor is not None else {}
    signal = TriggerSignal(
        trigger=TriggerType.F_BOS_OB, direction=Direction.LONG,
        entry_price=100.1, stop_reference=99.9, completion_index=7,
        expiry_bars=20, detail="t", data=data,
    )
    return TriggerRoute(poi=poi, bar=7, signal=signal)


def _metrics():
    return SimpleNamespace(
        n_trades=1, n_wins=0, n_losses=1, win_rate=0.0, gross_profit=0.0,
        gross_loss=0.01, profit_factor=0.0, net_pnl=-0.01, max_drawdown=0.01,
        avg_win=None, avg_loss=-0.01)


def test_bridge_extracts_entry_anchor_first_class():
    cand = candidate_from_route(_route("zone_edge_reanchor"))
    assert cand.entry_anchor == "zone_edge_reanchor"
    # Anchor is ALSO inside the serialized signal data (inspector ease).
    assert json.loads(cand.signal_data_json)["entry_anchor"] == "zone_edge_reanchor"


def test_bridge_entry_anchor_ob_proximal():
    cand = candidate_from_route(_route("ob_proximal"))
    assert cand.entry_anchor == "ob_proximal"


def test_bridge_absent_anchor_is_none_not_invented():
    cand = candidate_from_route(_route(None))
    assert cand.entry_anchor is None


def test_bridge_anchor_not_a_string_stays_none():
    route = _route("zone_edge_reanchor")
    route.signal.data["entry_anchor"] = 7  # non-string in signal data
    cand = candidate_from_route(route)
    assert cand.entry_anchor is None  # never coerced, never invented


def test_bridge_anchor_does_not_change_decisions():
    route = _route(None)
    plain = candidate_from_route(route)
    route.signal.data["entry_anchor"] = "zone_edge_reanchor"
    anchored = candidate_from_route(route)
    # Same route object — only the anchor differs (poi/route identity hold).
    assert (anchored.direction, anchored.entry_price, anchored.sl_price,
            anchored.trigger, anchored.score, anchored.poi_id) == (
        plain.direction, plain.entry_price, plain.sl_price,
        plain.trigger, plain.score, plain.poi_id)
    assert plain.entry_anchor is None
    assert anchored.entry_anchor == "zone_edge_reanchor"


def test_anchor_flows_order_to_position():
    cand = candidate_from_route(_route("zone_edge_reanchor"))
    book = PendingOrderBook()
    order = book.place(
        direction=cand.direction, entry_price=cand.entry_price,
        sl=cand.sl_price, tp=cand.tp_price, volume=0.1, placed_bar=3,
        placed_at=None, poi_id=cand.poi_id, trigger=cand.trigger,
        original_sl=cand.original_sl, zone_low=cand.zone_low,
        zone_high=cand.zone_high, signal_data_json=cand.signal_data_json,
        entry_anchor=cand.entry_anchor,
    )
    store = PositionStore()
    pos = store.open(
        direction=order.direction, volume=order.volume,
        entry_price=order.entry_price, sl=order.sl, tp=order.tp,
        entry_bar=5, entry_at=None, poi_id=order.poi_id,
        trigger=order.trigger, original_sl=order.original_sl,
        zone_low=order.zone_low, zone_high=order.zone_high,
        signal_data_json=order.signal_data_json,
        entry_anchor=order.entry_anchor,
    )
    assert pos.entry_anchor == "zone_edge_reanchor"


def test_modify_sl_preserves_entry_anchor():
    store = PositionStore()
    pos = store.open(
        direction=Direction.LONG, volume=0.1, entry_price=100.1, sl=99.9,
        tp=None, entry_bar=3, entry_at=None, symbol="XAUUSDm",
        original_sl=99.9, zone_low=100.0, zone_high=100.2,
        signal_data_json='{"a": 1}', entry_anchor="zone_edge_reanchor",
    )
    updated = store.modify_sl(pos.ticket, 100.05)
    assert updated.sl == 100.05
    # Same placement-geometry invariant as original_sl: BE moves must
    # never clear the anchor provenance.
    assert updated.entry_anchor == "zone_edge_reanchor"
    assert updated.original_sl == 99.9
    assert updated.signal_data_json == '{"a": 1}'


def test_from_closed_carries_entry_anchor():
    store = PositionStore()
    pos = store.open(
        direction=Direction.LONG, volume=0.1, entry_price=100.1, sl=99.9,
        tp=None, entry_bar=3, entry_at=None, symbol="XAUUSDm",
        poi_id="p1", trigger=TriggerType.F_BOS_OB,
        entry_anchor="zone_edge_reanchor",
    )
    closed = store.close(pos.ticket, exit_price=99.9, exit_bar=5,
                         exit_at=None, kind="stop_loss")
    rec = TradeRecord.from_closed(closed, route_id="p1:F@7")
    assert rec.entry_anchor == "zone_edge_reanchor"


def test_export_csv_appends_entry_anchor_column(tmp_path):
    rec = TradeRecord(
        ticket=1, direction=Direction.LONG, symbol="XAUUSDm", volume=0.1,
        entry_price=100.1, exit_price=100.3, sl=99.9, tp=None, entry_bar=3,
        exit_bar=9, entry_at="t", exit_at="t", close_kind="take_profit",
        win=True, pnl=0.2, poi_id="p1", trigger="f_bos_ob", route_id="p1:F@7",
        entry_anchor="zone_edge_reanchor",
    )
    report = SimpleNamespace(trades=[rec])
    path = tmp_path / "trades.csv"
    to_csv(report, path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].endswith("signal_data_json,entry_anchor,tp_source")  # appended, compat (structural TP col after E1)
    assert lines[1].endswith(",zone_edge_reanchor,")  # anchor cell + empty tp_source cell


def test_export_json_carries_entry_anchor_key(tmp_path):
    rec = TradeRecord(
        ticket=1, direction=Direction.LONG, symbol="XAUUSDm", volume=0.1,
        entry_price=100.1, exit_price=100.3, sl=99.9, tp=None, entry_bar=3,
        exit_bar=9, entry_at="t", exit_at="t", close_kind="take_profit",
        win=True, pnl=0.2, poi_id="p1", trigger="f_bos_ob", route_id="p1:F@7",
        entry_anchor="zone_edge_reanchor",
    )
    report = SimpleNamespace(metrics=_metrics(), by_trigger={}, by_poi={},
                             blocked_by_reason={}, trades=[rec])
    path = tmp_path / "report.json"
    to_json(report, path)
    trade = json.loads(path.read_text(encoding="utf-8"))["trades"][0]
    assert trade["entry_anchor"] == "zone_edge_reanchor"


def test_export_absent_anchor_is_empty_and_null():
    rec = TradeRecord(
        ticket=1, direction=Direction.LONG, symbol="XAUUSDm", volume=0.1,
        entry_price=100.1, exit_price=100.3, sl=99.9, tp=None, entry_bar=3,
        exit_bar=9, entry_at="t", exit_at="t", close_kind="take_profit",
        win=True, pnl=0.2, poi_id=None, trigger=None, route_id=None,
    )
    assert rec.entry_anchor is None  # legacy construction still works
