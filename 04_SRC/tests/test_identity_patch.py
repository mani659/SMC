"""Export/identity patch — logging-only enrichment (no decision change).

Proves: model tags flow route → candidate → order → position → trade →
export; displacement/pillar context flows when supplied and stays unknown
otherwise; BE modifies preserve identity; old construction (no new kwargs)
still works; entry/SL/trigger mapping is byte-identical with or without the
new kwargs.
"""

from types import SimpleNamespace

from smc.backtest.export import to_csv, to_json
from smc.backtest.orders import PendingOrderBook
from smc.backtest.pipeline_bridge import candidate_from_route, pillar_path_summary
from smc.backtest.positions import PositionStore
from smc.backtest.reports import TradeRecord
from smc.backtest.runner import CandidateEntry
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.paper.runner import _TrackedPending
from smc.triggers.base_trigger import TriggerSignal
from smc.triggers.trigger_router import TriggerRoute

TF = Timeframe.M5


def _route(models=None):
    poi = POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
        models=models if models is not None else [ModelType.M1, ModelType.M5],
    )
    signal = TriggerSignal(
        trigger=TriggerType.F_BOS_OB, direction=Direction.LONG,
        entry_price=100.1, stop_reference=99.9, completion_index=7,
        expiry_bars=20, detail="t", data={},
    )
    return TriggerRoute(poi=poi, bar=7, signal=signal)


class _FakeDisp:
    def __init__(self, magnitude_atr):
        self.magnitude_atr = magnitude_atr


def test_bridge_fills_model_tags_always():
    cand = candidate_from_route(_route())
    assert cand.model_tags == ("M1", "M5")
    assert cand.disp_magnitude_atr is None
    assert cand.pillar_path is None


def test_bridge_propagates_context_without_changing_decisions():
    route = _route()
    plain = candidate_from_route(route)
    enriched = candidate_from_route(
        route, displacement=_FakeDisp(1.3),
        pillar_path="PASS:1+2+3+4+5;inducement=1.0",
    )
    # Identity only — the tradeable mapping is identical.
    assert (enriched.direction, enriched.entry_price, enriched.sl_price,
            enriched.trigger, enriched.route_id, enriched.score,
            enriched.poi_id) == (
        plain.direction, plain.entry_price, plain.sl_price,
        plain.trigger, plain.route_id, plain.score, plain.poi_id)
    assert enriched.model_tags == ("M1", "M5")
    assert enriched.disp_magnitude_atr == 1.3
    assert enriched.pillar_path == "PASS:1+2+3+4+5;inducement=1.0"


def test_bridge_empty_models_is_unknown_not_invented():
    cand = candidate_from_route(_route(models=[]))
    assert cand.model_tags is None


def test_pillar_path_summary_pass_fail_none():
    pillar = SimpleNamespace(pillar=1)
    passed = SimpleNamespace(passed=True, pillar_results=[pillar, SimpleNamespace(pillar=2)],
                             inducement_modifier=1.0)
    assert pillar_path_summary(passed) == "PASS:1+2;inducement=1.0"
    fail = SimpleNamespace(
        passed=False,
        first_failure=SimpleNamespace(pillar=2, name="displacement",
                                      status=SimpleNamespace(name="FAIL"),
                                      detail="displacement < 0.5x ATR (hard fail)"),
    )
    out = pillar_path_summary(fail)
    assert out.startswith("FAIL@2:displacement:FAIL:")
    assert "hard fail" in out
    assert pillar_path_summary(None) is None


def test_modify_sl_preserves_identity():
    store = PositionStore()
    pos = store.open(
        direction=Direction.LONG, volume=0.1, entry_price=100.1, sl=99.9,
        tp=None, entry_bar=3, entry_at=None, symbol="XAUUSDm",
        poi_id="p1", trigger=TriggerType.F_BOS_OB,
        model_tags=("M1", "M5"), pillar_path="PASS:1+2+3+4+5;inducement=1.0",
        disp_magnitude_atr=1.3,
    )
    updated = store.modify_sl(pos.ticket, 100.05)
    assert updated.model_tags == ("M1", "M5")
    assert updated.pillar_path == "PASS:1+2+3+4+5;inducement=1.0"
    assert updated.disp_magnitude_atr == 1.3
    assert updated.sl == 100.05  # the modify itself still applies


def test_old_construction_without_new_kwargs_still_works():
    cand = CandidateEntry(direction=Direction.LONG, entry_price=100.1, sl_price=99.9)
    assert cand.model_tags is None and cand.pillar_path is None
    assert cand.disp_magnitude_atr is None
    book = PendingOrderBook()
    order = book.place(direction=Direction.LONG, entry_price=100.1, sl=99.9,
                       tp=None, volume=0.1, placed_bar=1, placed_at=None)
    assert order.model_tags is None
    tracked = _TrackedPending(ticket=9, poi_id=None, trigger=None, route_id=None,
                              fvg_context=None, sweep_level=None, placed_at=None)
    assert tracked.model_tags is None and tracked.pillar_path is None


def _trade_record():
    return TradeRecord(
        ticket=1, direction=Direction.LONG, symbol="XAUUSDm", volume=0.1,
        entry_price=100.1, exit_price=99.9, sl=99.9, tp=None, entry_bar=3,
        exit_bar=5, entry_at="2025-10-01T00:00:00+00:00",
        exit_at="2025-10-01T00:02:00+00:00", close_kind="stop_loss",
        win=False, pnl=-0.02, poi_id="p1", trigger="F",
        route_id="p1:F@7", model_tags=("M1", "M5"),
        pillar_path="PASS:1+2+3+4+5;inducement=1.0", disp_magnitude_atr=1.3,
    )


def test_export_csv_appends_identity_columns(tmp_path):
    report = SimpleNamespace(trades=[_trade_record()])
    path = tmp_path / "trades.csv"
    to_csv(report, path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].endswith("model_tags,pillar_path,disp_magnitude_atr,"
                             "original_sl,zone_low,zone_high,signal_data_json,"
                             "entry_anchor,tp_source")  # appended: E1 + structural TP
    assert lines[0].startswith("ticket,direction,symbol")  # old order kept
    assert lines[1].endswith("M1+M5,PASS:1+2+3+4+5;inducement=1.0,1.3,,,,,,")


def test_export_csv_unknown_identity_is_empty_cells(tmp_path):
    blank = TradeRecord(
        ticket=2, direction=Direction.SHORT, symbol="XAUUSDm", volume=0.1,
        entry_price=100.1, exit_price=100.2, sl=100.2, tp=None, entry_bar=3,
        exit_bar=4, entry_at="t", exit_at="t", close_kind="stop_loss",
        win=False, pnl=-0.01, poi_id=None, trigger=None, route_id=None,
    )
    report = SimpleNamespace(trades=[blank])
    path = tmp_path / "trades.csv"
    to_csv(report, path)
    assert path.read_text(encoding="utf-8").splitlines()[1].endswith(",,,")


def test_bridge_original_sl_equals_placement_sl_and_zone_bounds():
    route = _route()
    cand = candidate_from_route(route)
    # original_sl is the placement stop by construction (BE must never move it).
    assert cand.original_sl == cand.sl_price == 99.9
    assert cand.zone_low == 100.0
    assert cand.zone_high == 100.2
    assert cand.signal_data_json is None  # empty data stays unknown, not "{}"


def test_bridge_signal_data_json_carries_trigger_geometry():
    route = _route()
    route.signal.data["wave5_index"] = 41
    cand = candidate_from_route(route)
    import json
    assert json.loads(cand.signal_data_json) == {"wave5_index": 41}
    # Decisions untouched by the new kwargs (route_id/poi_id hold fresh
    # uuids per _route() call, so compare the tradeable mapping only).
    plain = candidate_from_route(_route())
    assert (cand.direction, cand.entry_price, cand.sl_price, cand.trigger,
            cand.score) == (plain.direction, plain.entry_price,
                            plain.sl_price, plain.trigger, plain.score)


def test_be_modify_preserves_original_sl_and_zone():
    store = PositionStore()
    pos = store.open(
        direction=Direction.LONG, volume=0.1, entry_price=100.1, sl=99.9,
        tp=None, entry_bar=3, entry_at=None, symbol="XAUUSDm",
        original_sl=99.9, zone_low=100.0, zone_high=100.2,
        signal_data_json='{"a": 1}',
    )
    updated = store.modify_sl(pos.ticket, 100.05)
    assert updated.sl == 100.05  # working SL moves ...
    assert updated.original_sl == 99.9  # ... placement SL does not
    assert updated.zone_low == 100.0
    assert updated.zone_high == 100.2
    assert updated.signal_data_json == '{"a": 1}'


def test_export_appends_geometry_columns(tmp_path):
    rec = _trade_record()
    report = SimpleNamespace(trades=[rec])
    path = tmp_path / "trades.csv"
    to_csv(report, path)
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert "original_sl,zone_low,zone_high,signal_data_json,entry_anchor" in header
    import json
    jpath = tmp_path / "report.json"
    metrics = SimpleNamespace(n_trades=1, n_wins=0, n_losses=1, win_rate=0.0,
                              gross_profit=0.0, gross_loss=0.01, profit_factor=0.0,
                              net_pnl=-0.01, max_drawdown=0.01, avg_win=None,
                              avg_loss=-0.01)
    full = SimpleNamespace(metrics=metrics, by_trigger={}, by_poi={},
                           blocked_by_reason={}, trades=[rec])
    to_json(full, jpath)
    trade = json.loads(jpath.read_text(encoding="utf-8"))["trades"][0]
    assert trade["original_sl"] is None  # _trade_record predates geometry
    assert trade["zone_low"] is None
    assert trade["signal_data_json"] is None


def test_from_closed_carries_placement_geometry():
    from smc.backtest.reports import TradeRecord as TR

    store = PositionStore()
    pos = store.open(
        direction=Direction.LONG, volume=0.1, entry_price=100.1, sl=99.9,
        tp=None, entry_bar=3, entry_at=None, symbol="XAUUSDm",
        poi_id="p1", trigger=TriggerType.F_BOS_OB,
        model_tags=("M1",), pillar_path="PASS:1+2+3+4+5;inducement=1.0",
        disp_magnitude_atr=2.0, original_sl=99.9, zone_low=100.0,
        zone_high=100.2, signal_data_json='{"w": 1}',
    )
    closed = store.close(pos.ticket, exit_price=99.9, exit_bar=5,
                         exit_at=None, kind="stop_loss")
    rec = TR.from_closed(closed, route_id="p1:F@7")
    assert rec.original_sl == 99.9
    assert (rec.zone_low, rec.zone_high) == (100.0, 100.2)
    assert rec.signal_data_json == '{"w": 1}'
    assert rec.model_tags == ("M1",)


def test_export_json_carries_identity_keys(tmp_path):
    metrics = SimpleNamespace(n_trades=1, n_wins=0, n_losses=1, win_rate=0.0,
                              gross_profit=0.0, gross_loss=0.01, profit_factor=0.0,
                              net_pnl=-0.01, max_drawdown=0.01, avg_win=None,
                              avg_loss=-0.01)
    report = SimpleNamespace(metrics=metrics, by_trigger={}, by_poi={},
                             blocked_by_reason={}, trades=[_trade_record()])
    path = tmp_path / "report.json"
    to_json(report, path)
    import json
    trade = json.loads(path.read_text(encoding="utf-8"))["trades"][0]
    assert trade["model_tags"] == ["M1", "M5"]
    assert trade["pillar_path"] == "PASS:1+2+3+4+5;inducement=1.0"
    assert trade["disp_magnitude_atr"] == 1.3
