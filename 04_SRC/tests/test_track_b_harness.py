"""Track-B harness tests — annotation carriage only (Tier-1).

Proves the research-measurement seam: frozen timing labels + post-exit
classes ride closed trades into TradeRecord / CSV / JSON / summary
groups WITHOUT changing any number, decision, or threshold. All series
and fills are synthetic; no MT5; no expectancy assertion anywhere.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HARNESS_PATH = (Path(__file__).resolve().parents[2]
                 / "06_RESEARCH" / "scripts" / "f_selectivity_post_exit.py")


def _load_harness():
    spec = importlib.util.spec_from_file_location(
        "f_selectivity_post_exit", _HARNESS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["f_selectivity_post_exit"] = module
    spec.loader.exec_module(module)
    return module


def _candle(ts, o, h, l, c, tf):
    from smc.core.candle import Candle
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, timeframe=tf)


def _series():
    """Synthetic M1 climb (90 -> 110 over bars 0..29, then flat) + M5 grid."""
    from smc.backtest.data_feed import CandleSeries
    from smc.config.timeframe import Timeframe
    t0 = datetime(2025, 10, 1, tzinfo=timezone.utc)
    m1 = []
    for i in range(60):
        price = 90.0 + min(i, 29) * (20.0 / 29.0)
        m1.append(_candle(t0 + timedelta(minutes=i),
                          price - 0.05, price + 0.35, price - 0.05, price + 0.3,
                          Timeframe.M1))
    m5 = [_candle(t0 + timedelta(minutes=5 * j),
                  100.0, 100.5, 99.5, 100.0, Timeframe.M5)
          for j in range(160)]
    return m1, CandleSeries(m5, Timeframe.M5), t0


def _close_long(entry_idx=30, exit_idx=40, kind="stop_loss", exit_price=100.0,
                tp=None, trigger="F", sl=100.0):
    from smc.backtest.positions import PositionStore
    from smc.core.enums import Direction
    m1, _m5, t0 = _series()
    store = PositionStore()
    pos = store.open(
        direction=Direction.LONG, volume=0.1, entry_price=110.0,
        sl=sl, tp=tp, entry_bar=entry_idx,
        entry_at=t0 + timedelta(minutes=entry_idx), symbol="XAUUSDm",
        trigger=trigger, zone_low=108.0, zone_high=112.0,
        original_sl=sl,
    )
    return store.close(ticket=pos.ticket, exit_price=exit_price,
                       exit_bar=exit_idx,
                       exit_at=t0 + timedelta(minutes=exit_idx), kind=kind)


# --------------------------------------------------------------------------- #
# 1. Label attached for a synthetic F close (frozen Rule v1, reused import)
# --------------------------------------------------------------------------- #
def test_f_close_gets_frozen_label_and_zone():
    pack = _load_harness()
    m1, m5, _t0 = _series()
    closed = _close_long()
    ann = pack.annotate_product_trades([closed], m1=m1, m5=m5)
    got = ann[closed.position.ticket]
    # Entry 110.0 sits at the top of the trailing 30-bar 90..110 climb
    # with a wide range -> Rule v1 late_chase, INSIDE its zone.
    assert got["f_timing_label"] == "late_chase"
    # No TP level + flat aftermath (MFE_R 0.035 < 0.25, full-SL pnl) ->
    # frozen restriction rejects.
    assert got["post_exit_class"] == "REJECTED"


def test_direction_enum_normalized():
    pack = _load_harness()
    assert pack._dir_name(__import__(
        "smc.core.enums", fromlist=["Direction"]).Direction.SHORT) == "short"
    assert pack._dir_name("LONG") == "long"
    assert pack._trigger_letter("f_bos_ob") == "F"
    assert pack._trigger_letter("F") == "F"
    assert pack._trigger_letter(None) == "?"


# --------------------------------------------------------------------------- #
# 2. Unknown path — no series, no invention
# --------------------------------------------------------------------------- #
def test_empty_m5_yields_data_gap_without_crash():
    pack = _load_harness()
    m1, _m5, _t0 = _series()
    closed = _close_long()
    ann = pack.annotate_product_trades([closed], m1=m1, m5=[])
    got = ann[closed.position.ticket]
    assert got["post_exit_class"] == "DATA_GAP"
    assert got["f_timing_label"] == "late_chase"  # M1 labels need no M5


def test_unannotated_report_folds_to_unknown_buckets(tmp_path):
    from smc.backtest.export import to_csv, to_json
    from smc.backtest.reports import build_report
    from smc.backtest.runner import RunnerResult
    closed = _close_long()
    report = build_report(RunnerResult(closed=[closed], blocked=[],
                                       route_ids={}))
    (trade,) = report.trades
    assert trade.f_timing_label is None and trade.post_exit_class is None
    assert set(report.by_timing_label) == {"unknown"}
    assert set(report.by_post_exit_class) == {"DATA_GAP"}
    to_csv(report, tmp_path / "t.csv")
    to_json(report, tmp_path / "r.json")
    header = (tmp_path / "t.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header.endswith("f_timing_label,post_exit_class")
    payload = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert payload["trades"][0]["f_timing_label"] is None
    assert "by_timing_label" in payload and "by_post_exit_class" in payload


# --------------------------------------------------------------------------- #
# 3. No number changes when annotations are added
# --------------------------------------------------------------------------- #
def test_annotations_do_not_move_pnl_or_metrics():
    from smc.backtest.reports import build_report
    from smc.backtest.runner import RunnerResult
    pack = _load_harness()
    m1, m5, _t0 = _series()
    closed = _close_long()
    plain = build_report(RunnerResult(closed=[closed], blocked=[],
                                      route_ids={}))
    ann = pack.annotate_product_trades([closed], m1=m1, m5=m5)
    annotated = build_report(RunnerResult(closed=[closed], blocked=[],
                                          route_ids={}), annotations=ann)
    assert annotated.metrics == plain.metrics
    assert annotated.trades[0].pnl == plain.trades[0].pnl
    assert annotated.trades[0].pnl_net == plain.trades[0].pnl_net
    assert set(annotated.by_trigger) == set(plain.by_trigger)
    # ... but the annotation groups now carry the measured buckets.
    assert set(annotated.by_timing_label) == {
        annotated.trades[0].f_timing_label}
    assert set(annotated.by_post_exit_class) == {
        annotated.trades[0].post_exit_class}


def test_non_f_trigger_unlabeled_but_classified():
    pack = _load_harness()
    m1, m5, _t0 = _series()
    closed = _close_long(trigger="B")
    ann = pack.annotate_product_trades([closed], m1=m1, m5=m5)
    got = ann[closed.position.ticket]
    assert got["f_timing_label"] is None      # labels are F-only by design
    assert got["post_exit_class"] in ("REJECTED", "MFE_ONLY", "DATA_GAP",
                                      "SL_THEN_TP_PATH", "TP_REACHED")


def test_from_closed_kwargs_direct():
    from smc.backtest.reports import TradeRecord
    closed = _close_long()
    rec = TradeRecord.from_closed(closed, f_timing_label="mid_move",
                                  post_exit_class="MFE_ONLY")
    assert rec.f_timing_label == "mid_move"
    assert rec.post_exit_class == "MFE_ONLY"
    bare = TradeRecord.from_closed(closed)
    assert bare.f_timing_label is None and bare.post_exit_class is None


def test_harness_banner_present():
    pack = _load_harness()
    assert "NOT" in pack.TRACK_B_BANNER and "filter" in pack.TRACK_B_BANNER


def test_namespaced_report_shape_untouched():
    # build_report without annotations keeps the exact legacy contract
    # plus additive empty groups (same pattern as the cost-model change).
    from smc.backtest.reports import build_report
    from smc.backtest.runner import RunnerResult
    report = build_report(RunnerResult(closed=[], blocked=[], route_ids={}))
    assert report.by_timing_label == {} and report.by_post_exit_class == {}
    assert report.metrics.net_pnl == 0.0
