"""Phase 6 M5 — core reports: metrics, breakdowns, exports (pure projection).

The metric fixtures are hand-computed synthetic closed-trade sets (the
numbered expectations below are verified by hand, not derived). The
integrated-path tests run the M4 pipeline runner and check that the
report's trade list / identity fields / blocked counts match what the
stores and logs actually recorded. Determinism: identical inputs →
identical report objects AND byte-identical JSON.
"""

import json
from datetime import datetime, timezone

import pytest

from smc.backtest.export import to_csv, to_json
from smc.backtest.reports import (
    UNATTRIBUTED,
    BacktestReport,
    build_report,
)
from smc.backtest.runner import BlockedEntry, RunnerResult
from smc.core.enums import Direction

# ---------------------------------------------------------------------- #
# Synthetic closed-trade fixtures (hand-computed expectations)
# ---------------------------------------------------------------------- #
T0 = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)


def _result_from_pnls(pnls, *, triggers=None, pois=None, blocked=None, route_ids=None):
    """A RunnerResult-shaped fixture without touching the trading stores."""
    from smc.backtest.positions import BacktestPosition, ClosedPosition

    closed = []
    for index, pnl in enumerate(pnls):
        trigger = triggers[index] if triggers else None
        poi_id = pois[index] if pois else None
        position = BacktestPosition(
            ticket=index + 1,
            direction=Direction.LONG,
            volume=1.0,
            entry_price=100.0,
            sl=None,
            tp=None,
            entry_bar=index,
            entry_at=T0,
            symbol="XAUUSD.x",
            poi_id=poi_id,
            trigger=trigger,
        )
        closed.append(
            ClosedPosition(
                position=position,
                exit_price=100.0 + pnl,  # LONG, volume 1 → pnl == delta
                exit_bar=index + 1,
                exit_at=T0,
                kind="take_profit" if pnl > 0 else "stop_loss",
                win=pnl > 0,
                realized_pnl=pnl,
            )
        )
    return RunnerResult(
        closed=closed,
        blocked=list(blocked or []),
        route_ids=dict(route_ids or {}),
    )


class TestCoreMetrics:
    def test_pf_win_rate_net_on_synthetic_set(self):
        # P/L sequence: +60, -40, +25, -40, +15
        # wins [60, 25, 15] → GP 100, avg 33.33..; losses [-40, -40] → GL 80, avg 40
        # PF 1.25; win_rate 3/5 = 0.6; net +20
        report = build_report(_result_from_pnls([60.0, -40.0, 25.0, -40.0, 15.0]))
        m = report.metrics
        assert m.n_trades == 5
        assert m.n_wins == 3 and m.n_losses == 2
        assert m.win_rate == pytest.approx(0.6)
        assert m.gross_profit == pytest.approx(100.0)
        assert m.gross_loss == pytest.approx(80.0)  # positive magnitude
        assert m.profit_factor == pytest.approx(1.25)
        assert m.net_pnl == pytest.approx(20.0)
        assert m.avg_win == pytest.approx(100.0 / 3.0)
        assert m.avg_loss == pytest.approx(40.0)

    def test_profit_factor_zero_loss_case_is_none(self):
        # Only winners → gross_loss 0 → PF undefined → None (never inf).
        report = build_report(_result_from_pnls([10.0, 20.0]))
        assert report.metrics.profit_factor is None
        assert report.metrics.max_drawdown == pytest.approx(0.0)

    def test_max_drawdown_on_known_equity_path(self):
        # Equity path: +100 → 100, -150 → -50, +200 → 150, -30 → 120
        # peak 100 → trough -50 = DD 150; later peak 150 → trough 120 = 30.
        report = build_report(_result_from_pnls([100.0, -150.0, 200.0, -30.0]))
        assert report.metrics.max_drawdown == pytest.approx(150.0)

    def test_max_drawdown_starting_in_loss(self):
        # First trade a loss: peak stays 0 until equity recovers above 0.
        # -40 → -40 (DD 40), +90 → 50 (peak 50), -70 → -20 (DD 70).
        report = build_report(_result_from_pnls([-40.0, 90.0, -70.0]))
        assert report.metrics.max_drawdown == pytest.approx(70.0)


class TestTradeList:
    def test_trade_record_fields_and_route_id_projection(self):
        route_ids = {2: "poi-x:d_two_bar_reversal@3"}
        report = build_report(_result_from_pnls([10.0, -5.0], route_ids=route_ids))
        assert len(report.trades) == 2
        first, second = report.trades
        assert first.ticket == 1
        assert first.direction is Direction.LONG
        assert first.entry_price == pytest.approx(100.0)
        assert first.pnl == pytest.approx(10.0)
        assert first.win is True
        assert first.close_kind == "take_profit"
        assert first.route_id is None  # no identity recorded → None, never invented
        assert second.route_id == "poi-x:d_two_bar_reversal@3"

    def test_trigger_normalization_from_enum(self):
        from smc.core.enums import TriggerType

        report = build_report(
            _result_from_pnls([10.0], triggers=[TriggerType.D_TWO_BAR_REVERSAL])
        )
        assert report.trades[0].trigger == "D"  # the enum's frozen value


class TestBreakdowns:
    def test_per_trigger_aggregation(self):
        from smc.core.enums import TriggerType

        report = build_report(
            _result_from_pnls(
                [60.0, -40.0, 25.0, -40.0, 15.0],
                triggers=[
                    TriggerType.D_TWO_BAR_REVERSAL,
                    TriggerType.D_TWO_BAR_REVERSAL,
                    TriggerType.A_CHOCH,
                    TriggerType.A_CHOCH,
                    None,  # unattributed bucket (M3 seam had no trigger)
                ],
            )
        )
        by_trigger = report.by_trigger
        assert set(by_trigger) == {"D", "A", UNATTRIBUTED}
        d = by_trigger["D"]
        assert d.n_trades == 2 and d.n_wins == 1
        assert d.net_pnl == pytest.approx(20.0)
        assert d.profit_factor == pytest.approx(1.5)  # 60 / 40
        a = by_trigger["A"]
        assert a.n_trades == 2 and a.net_pnl == pytest.approx(-15.0)
        assert a.profit_factor == pytest.approx(0.625)  # 25 / 40
        u = by_trigger[UNATTRIBUTED]
        assert u.n_trades == 1 and u.net_pnl == pytest.approx(15.0)

    def test_per_poi_aggregation_uses_preserved_identity_only(self):
        report = build_report(
            _result_from_pnls(
                [30.0, -20.0],
                pois=["poi-1", None],
            )
        )
        assert set(report.by_poi) == {"poi-1", UNATTRIBUTED}
        assert report.by_poi["poi-1"].net_pnl == pytest.approx(30.0)
        assert report.by_poi[UNATTRIBUTED].n_losses == 1

    def test_no_model_tags_invented(self):
        # Model tags live on the POI object, not the close record — the
        # report must not fabricate them (no per-model section exists).
        report = build_report(_result_from_pnls([10.0], pois=["poi-1"]))
        assert not hasattr(report, "by_model")


class TestBlockedVisibility:
    def test_blocked_counts_by_reason(self):
        blocked = [
            BlockedEntry(bar_index=1, now=T0, blocked_by="session"),
            BlockedEntry(bar_index=2, now=T0, blocked_by="session"),
            BlockedEntry(bar_index=3, now=T0, blocked_by="news"),
        ]
        report = build_report(_result_from_pnls([10.0], blocked=blocked))
        assert report.blocked_by_reason == {"news": 1, "session": 2}


class TestEmptyRun:
    def test_empty_run_defined_zeros_no_crash(self):
        report = build_report(_result_from_pnls([]))
        m = report.metrics
        assert m.n_trades == 0
        assert m.win_rate == 0.0
        assert m.gross_profit == 0.0 and m.gross_loss == 0.0
        assert m.profit_factor is None
        assert m.net_pnl == 0.0
        assert m.max_drawdown == 0.0
        assert m.avg_win is None and m.avg_loss is None
        assert report.trades == ()
        assert report.by_trigger == {} and report.by_poi == {}
        assert report.blocked_by_reason == {}


class TestDeterminism:
    def test_identical_inputs_identical_report(self):
        kwargs = dict(
            triggers=["a", "b", "a"],
            pois=["p1", "p1", None],
            blocked=[BlockedEntry(bar_index=1, now=T0, blocked_by="session")],
            route_ids={3: "r3"},
        )
        a = build_report(_result_from_pnls([50.0, -30.0, 12.0], **kwargs))
        b = build_report(_result_from_pnls([50.0, -30.0, 12.0], **kwargs))
        assert a == b  # frozen dataclasses with dict fields → eq compares


# ---------------------------------------------------------------------- #
# Integrated path: report over a real M4 pipeline run
# ---------------------------------------------------------------------- #
def test_report_over_real_pipeline_run(candle_factory, swing_factory, tmp_path):
    """The full chain: pipeline → risk → fill → close → report → JSON/CSV."""
    from smc.backtest.bar_loop import BarLoop
    from smc.backtest.orders import PendingOrderBook
    from smc.backtest.pipeline_adapter import PipelineAdapter
    from smc.backtest.positions import PositionStore
    from smc.backtest.runner import BacktestRunner, RunnerConfig
    from smc.config.model_type import ModelType
    from smc.config.timeframe import Timeframe
    from smc.core.enums import LiquidityType, PoolType, TriggerType
    from smc.core.liquidity_level import LiquidityLevel
    from smc.core.poi import POI
    from smc.core.zone import Zone
    from smc.detection.displacement_checker import check_displacement
    from smc.orchestration.engine import PipelineEngine
    from smc.risk.risk_engine import RiskEngine
    from smc.utils.timestamps import Session

    tf = Timeframe.M5
    start = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)  # Thursday London
    calm = (100.4, 100.6, 100.3, 100.5)
    engulfed = (100.5, 100.55, 100.3, 100.4, 500.0)
    engulfer = (100.4, 100.6, 99.9, 100.5, 300.0)
    signal_bar = (100.4, 100.6, 100.3, 100.5)
    fill = (100.3, 100.5, 100.35, 100.45)
    stop_bar = (100.2, 100.4, 99.8, 99.85)  # hits the 99.9 stop → loss

    # Validate a real POI through the engine (same recipe as the M4 tests).
    engine = PipelineEngine()
    poi = POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=tf),
        models=[ModelType.M1],
    )
    candles = candle_factory(
        [(99.5, 99.7, 99.3, 99.6)] * 15
        + [
            (99.9, 100.0, 99.7, 99.9),
            (100.0, 100.1, 99.6, 100.0),
            (100.15, 100.35, 100.2, 100.3),
            (100.3, 100.4, 100.1, 100.35),
        ],
        timeframe=tf,
    )
    from smc.core.swing import Swing

    swings = [
        Swing(
            is_high=True,
            level=105.0,
            candle_index=3,
            base_candle=candles[3],
            timeframe=tf,
            is_valid=True,
        ),
        Swing(
            is_high=False,
            level=99.0,
            candle_index=4,
            base_candle=candles[4],
            timeframe=tf,
            is_valid=True,
        ),
    ]
    displacement = check_displacement(
        candle_factory(
            [(100.5, 101.5, 99.5, 100.5)] * 15
            + [
                (99.8, 100.5, 98.2, 99.6),
                (100.0, 102.5, 100.3, 100.8),
                (101.0, 103.5, 102.0, 103.2),
            ]
        ),
        Direction.LONG,
        sweep_index=15,
        bos_level=101.2,
    )
    passed, _ = engine.validate(
        [poi],
        candles,
        swings,
        [
            LiquidityLevel(
                type=LiquidityType.EQUAL_HIGHS_LOWS,
                level=100.3,
                pool=PoolType.SSL,
                timeframe=tf,
            )
        ],
        displacement_map={poi.id: displacement},
        merge_first=False,
    )
    assert len(passed) == 1
    poi = passed[0]
    engine.arm_at(poi, arm_bar=0)

    # Run the integrated pipeline over: pattern bars → fill bar → stop bar.
    rows = [calm, engulfed, engulfer, signal_bar, fill, stop_bar]
    series_candles = candle_factory(rows, timeframe=tf, start=start)
    from smc.backtest.data_feed import CandleSeries

    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=RunnerConfig(
            allowed_sessions=(Session.LONDON, Session.NEW_YORK)
        ),
    )
    loop = BarLoop(CandleSeries(series_candles, timeframe=tf), runner)
    adapter = PipelineAdapter(engine)
    adapter.set_candles(candle_factory(rows, timeframe=tf, start=start))
    adapter.attach(runner)
    runner.set_atr(2.0)
    loop.run()

    report = build_report(runner.result())

    # One trade: Trigger D fill at the 50% body (100.45), stopped at 99.9.
    assert report.metrics.n_trades == 1
    trade = report.trades[0]
    assert trade.trigger == "D"
    assert trade.poi_id == poi.id
    assert trade.entry_price == pytest.approx(100.45)
    assert trade.exit_price == pytest.approx(99.9)
    assert trade.win is False
    assert trade.close_kind == "stop_loss"
    assert trade.pnl == pytest.approx((99.9 - 100.45) * 0.10)  # policy-sized lots
    assert trade.route_id is not None
    assert trade.route_id.startswith(poi.id)
    assert trade.route_id.endswith(":D@3")
    assert report.metrics.net_pnl == trade.pnl
    # One losing trade → gross_profit 0, PF 0.0 (losses present, so defined).
    assert report.metrics.profit_factor == pytest.approx(0.0)
    assert report.by_trigger["D"].n_trades == 1

    # Exports: deterministic JSON, and CSV round-trips the trade row.
    json_path = tmp_path / "report.json"
    csv_path = tmp_path / "trades.csv"
    to_json(report, json_path)
    to_csv(report, csv_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metrics"]["n_trades"] == 1
    assert payload["trades"][0]["route_id"] == trade.route_id
    to_json(report, tmp_path / "report2.json")
    assert (json_path.read_bytes() == (tmp_path / "report2.json").read_bytes())
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("ticket,direction,symbol,volume")
    assert lines[1].split(",")[16] == "D"  # trigger column


def test_blocked_run_report_counts(candle_factory):
    """A session-blocked candidate shows up in blocked_by_reason (M4 path)."""
    from smc.backtest.bar_loop import BarLoop
    from smc.backtest.data_feed import CandleSeries
    from smc.backtest.orders import PendingOrderBook
    from smc.backtest.positions import PositionStore
    from smc.backtest.runner import BacktestRunner, RunnerConfig
    from smc.config.timeframe import Timeframe
    from smc.risk.risk_engine import RiskEngine
    from smc.utils.timestamps import Session

    start = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)  # no session
    candles = candle_factory([(100.4, 100.6, 100.3, 100.5)], timeframe=Timeframe.M5, start=start)
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=RunnerConfig(allowed_sessions=(Session.LONDON,)),
    )
    loop = BarLoop(CandleSeries(candles, timeframe=Timeframe.M5), runner)
    from smc.backtest.runner import CandidateEntry

    runner.submit_entry(
        CandidateEntry(direction=Direction.LONG, entry_price=100.0, sl_price=99.0)
    )
    loop.run()
    report = build_report(runner.result())
    assert report.metrics.n_trades == 0
    assert report.blocked_by_reason == {"session": 1}
    assert isinstance(report, BacktestReport)
