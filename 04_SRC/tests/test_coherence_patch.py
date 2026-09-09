"""Coherence patch tests (Phase 7 prep) — CR1 detection driver, I1 shared
state machine, I2 running equity, CR2 paper close guards, I4 retention.

Every test exercises REAL frozen code (PipelineEngine, ValidationPipeline,
POIStateMachine, BacktestRunner, PaperRunner, the M1/M2 model detectors,
structural swing detection); the paper fakes are the established ones from
``test_paper_runner`` (fake connector + stub adapter over the real
OrderManager / PositionManager).
"""

from datetime import timedelta

import pytest

from smc.backtest.bar_loop import BarLoop
from smc.backtest.data_feed import CandleSeries
from smc.backtest.orders import PendingOrderBook
from smc.backtest.pipeline_adapter import PipelineAdapter, _Workflow
from smc.backtest.positions import PositionStore
from smc.backtest.runner import BacktestRunner, CandidateEntry, RunnerConfig
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.detection.displacement_checker import DisplacementResult, check_displacement
from smc.detection.structural_swing_detector import detect_swings
from smc.orchestration.detection_driver import DetectionDriver, DetectionRun
from smc.orchestration.engine import PipelineEngine
from smc.risk.risk_engine import RiskEngine
from smc.validation.state_machine import POIStateMachine
from smc.validation.validation_pipeline import ValidationPipeline
from test_paper_runner import START, _bar, _candidate, _make_runner, _pos, _seed

TF = Timeframe.M5


# ---------------------------------------------------------------------- #
# Recipe helpers (M1 origin-base recipe — real structural swings detected)
# ---------------------------------------------------------------------- #
def _m1_rows():
    """Calm drift → origin swing low 98.6 → bullish FVG impulse + BOS."""
    rows = []
    price = 100.0
    for _ in range(15):
        open_ = price
        close = open_ - 0.02
        rows.append((open_, open_ + 0.075, open_ - 0.075, close))
        price = close
    open_ = rows[10][3] - 0.05
    rows[10] = (open_, 100.0, open_ - 0.15, open_)          # swing high 100.0
    rows[14] = (99.0, 99.2, 98.6, 99.0)                     # origin swing low
    rows.append((99.2, 100.3, 99.1, 100.1))                 # impulse 1
    rows.append((100.05, 100.9, 99.95, 100.7))              # impulse 2
    rows.append((100.6, 101.3, 100.55, 101.1))              # impulse 3 (FVG+BOS)
    return rows


DISPLACEMENT_PRE = [(100.5, 101.5, 99.5, 100.5)] * 15


def _long_displacement(candle_factory) -> DisplacementResult:
    """A passing §3 LONG displacement (the M4 test's canonical recipe)."""
    candles = candle_factory(
        DISPLACEMENT_PRE
        + [
            (99.8, 100.5, 98.2, 99.6),
            (100.0, 102.5, 100.3, 100.8),
            (101.0, 103.5, 102.0, 103.2),
        ]
    )
    return check_displacement(candles, Direction.LONG, sweep_index=15, bos_level=101.2)


def _m1_poi() -> POI:
    return POI(
        zone=Zone(top=99.2, bottom=98.6, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M1],
    )


# ---------------------------------------------------------------------- #
# CR1 — detection driver: candles → validated/armed POIs
# ---------------------------------------------------------------------- #
def test_driver_produces_validated_armed_poi_from_synthetic_candles(candle_factory):
    candles = candle_factory(_m1_rows())
    displacement = _long_displacement(candle_factory)

    engine = PipelineEngine()
    driver = DetectionDriver(TF)
    result = driver.run(
        candles,
        engine=engine,
        # Pillar-2 injection seam (M4 contract): the provider sees the
        # FINAL post-detect POI ids, so the map always matches.
        displacement_provider=lambda pois, run: {p.id: displacement for p in pois},
        arm_bar=len(candles) - 1,
    )

    # Real Stage 0/1: swings detected by the driver itself, no model skipped.
    assert result.run.swings, "driver must detect structural swings itself"
    assert result.skipped_models == {}
    assert len(result.detected) >= 1  # M1 (+M2) fired on the recipe

    # At least one POI merged → validated → armed through the engine.
    assert len(result.passed) >= 1
    poi = result.passed[0]
    assert poi.state is POIState.FRESH                       # armed (CREATED→FRESH)
    assert engine.episode(poi) is not None                   # episode bookkeeping
    assert poi.id in {p.id for p in engine.tracked_pois()}   # arm-order registry

    # The §5 machine owns the armed POI: a first touch → TESTED.
    touch = Candle(
        timestamp=candles[-1].timestamp + timedelta(minutes=5),
        open=98.8, high=99.1, low=98.4, close=98.9, timeframe=TF,
    )
    assert engine.feed_bar(poi, touch) == POIState.TESTED.value
    assert not engine.state_machine.can_trade(poi)


def _disp(direction: Direction, bos_index: int) -> DisplacementResult:
    return DisplacementResult(
        direction=direction, bos=True, fvg=True, magnitude=1.0,
        magnitude_atr=1.5, atr=0.5, passed=True, hard_fail=False,
        is_preferred=True, bos_index=bos_index,
    )


def test_driver_attributes_most_recent_same_direction_displacement():
    driver = DetectionDriver(TF)
    long_early = _disp(Direction.LONG, 4)
    long_late = _disp(Direction.LONG, 9)
    short = _disp(Direction.SHORT, 6)
    run = DetectionRun(
        swings=[], liquidity_levels=[],
        sweeps=[],
        displacements=[(4, long_early), (6, short), (9, long_late)],
    )
    long_poi = POI(zone=Zone(top=101.0, bottom=100.0, direction=Direction.LONG, timeframe=TF))
    short_poi = POI(zone=Zone(top=99.0, bottom=98.0, direction=Direction.SHORT, timeframe=TF))

    attributed = driver.attribute_displacement([long_poi, short_poi], run)
    assert attributed[long_poi.id] is long_late   # most recent LONG (sweep 9)
    assert attributed[short_poi.id] is short      # its own direction (sweep 6)

    # No same-direction sweep → NO entry (Pillar 2 rejects — never invented).
    only_short = DetectionRun([], [], [], [(6, short)])
    assert driver.attribute_displacement([long_poi], only_short) == {}


def test_driver_rejects_poi_without_matching_sweep_via_pillar_2(candle_factory):
    """Honest fail: a LONG POI with only a SHORT sweep has no displacement
    and is rejected by Pillar 2 (UNAVAILABLE) — the driver never fabricates."""
    candles = candle_factory(_m1_rows())
    swings = detect_swings(candles, TF)
    driver = DetectionDriver(TF)
    engine = PipelineEngine()
    pois, _ = driver.detect_pois(candles, swings, [])
    long_poi = next(p for p in pois if p.zone.direction is Direction.LONG)
    run = DetectionRun(swings, [], [], [(6, _disp(Direction.SHORT, 6))])
    assert driver.attribute_displacement([long_poi], run) == {}

    passed, results = engine.validate(
        [long_poi], candles, swings, [], displacement_map={}, merge_first=False
    )
    assert passed == []
    assert results[0].first_failure is not None
    assert results[0].first_failure.pillar == 2


# ---------------------------------------------------------------------- #
# I1 — ONE §5 state machine shared by engine and validation pipeline
# ---------------------------------------------------------------------- #
def test_engine_and_pipeline_share_one_state_machine(candle_factory):
    candles = candle_factory(_m1_rows())
    swings = detect_swings(candles, TF)
    displacement = _long_displacement(candle_factory)

    machine = POIStateMachine()
    engine = PipelineEngine(state_machine=machine)
    assert engine.pipeline.state_machine is machine

    # validate → arm happens on the SHARED machine.
    poi = _m1_poi()
    passed, _ = engine.validate(
        [poi], candles, swings, [],
        displacement_map={poi.id: displacement}, merge_first=False,
    )
    assert len(passed) == 1 and passed[0].state is POIState.FRESH
    assert machine.current(passed[0]) is POIState.FRESH

    # feed through the engine flips the state the PIPELINE's machine sees.
    touch = Candle(
        timestamp=candles[-1].timestamp + timedelta(minutes=5),
        open=98.8, high=99.1, low=98.4, close=98.9, timeframe=TF,
    )
    assert engine.feed_bar(passed[0], touch) == POIState.TESTED.value
    assert machine.current(passed[0]) is POIState.TESTED
    assert engine.pipeline.state_machine.current(passed[0]) is POIState.TESTED
    assert not engine.state_machine.can_trade(passed[0])

    # expiry path observes the same machine.
    poi2 = _m1_poi()
    engine.arm_at(poi2, arm_bar=0)
    assert machine.expire_unfilled(poi2, bars_open=12) is POIState.TESTED
    assert engine.pipeline.state_machine.current(poi2) is POIState.TESTED

    # Default construction shares too; two DIFFERENT machines is a loud error.
    default = PipelineEngine()
    assert default.state_machine is default.pipeline.state_machine
    with pytest.raises(ValueError):
        PipelineEngine(pipeline=ValidationPipeline(), state_machine=POIStateMachine())
    engine_from_pipeline = PipelineEngine(
        pipeline=ValidationPipeline(state_machine=machine)
    )
    assert engine_from_pipeline.state_machine is machine


# ---------------------------------------------------------------------- #
# I2 — backtest running equity from realized P/L drives sizing
# ---------------------------------------------------------------------- #
def _equity_runner():
    return BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=RunnerConfig(
            equity=50.0, risk_fraction=0.01, pip_value_per_lot=10.0,
            min_lots=0.001, lot_step=0.001,
        ),
    )


def test_backtest_running_equity_changes_sizing_after_a_win(candle_factory):
    rows = [
        (100.5, 101.0, 100.4, 100.6),   # 0: place trade 1 (no fill)
        (100.0, 100.4, 99.9, 100.2),    # 1: fill @ 100.0
        (100.3, 103.2, 100.2, 103.0),   # 2: TP 103 hit → win (realized +0.15)
        (102.9, 103.3, 102.8, 103.1),   # 3: place trade 2 (sized from 51.5)
        (100.0, 100.4, 99.8, 100.1),    # 4: fill @ 100.0
        (100.3, 103.5, 100.2, 103.4),   # 5: TP 103 hit → win
    ]
    candles = candle_factory(rows)
    series = CandleSeries(candles, TF)
    runner = _equity_runner()
    loop = BarLoop(series, runner)

    def _cand():
        return CandidateEntry(
            direction=Direction.LONG, entry_price=100.0, sl_price=99.0,
            tp_price=103.0, score=10.0,
        )

    runner.submit_entry(_cand())
    loop.run(end_timestamp=candles[0].timestamp)                        # bar 0
    loop.run(start_timestamp=candles[1].timestamp,
             end_timestamp=candles[2].timestamp)                        # fill + win
    assert runner.current_equity() == pytest.approx(51.5)

    runner.submit_entry(_cand())                                        # sized at 51.5
    loop.run(start_timestamp=candles[3].timestamp)                      # bars 3-5

    closed = runner.result().closed
    assert len(closed) == 2
    # Trade 1: 50 × 1% / (1.0 × 10) = 0.05 lots; equity after win = 51.5.
    assert closed[0].position.volume == pytest.approx(0.05)
    assert closed[0].win
    # Trade 2 is sized from the RUNNING equity: 51.5 × 1% / 10 = 0.0515 → 0.051.
    assert closed[1].position.volume == pytest.approx(0.051)
    assert closed[1].position.volume > closed[0].position.volume
    assert runner.current_equity() == pytest.approx(51.5 + 3.0 * 0.051 * 10.0)


# ---------------------------------------------------------------------- #
# CR2 — paper close outcomes feed the risk guards (honest local P/L)
# ---------------------------------------------------------------------- #
def test_paper_sl_close_feeds_breaker_and_same_level_guard():
    runner, adapter, connector = _make_runner()
    adapter._candles = _seed()
    adapter.queue(_candidate())                              # entry 100 / SL 99
    runner.run_one_cycle(_bar(START, _seed_row()))           # place pending 1001

    connector.positions.append(_pos(7001, comment="poi-1:D@3"))
    runner.run_one_cycle(_bar(START + timedelta(minutes=5), _seed_row()))  # fill
    assert 7001 in runner._positions and runner._positions[7001].sl == 99.0

    # Broker closes it; the bar pierces the tracked SL → honest loss.
    connector.positions.clear()
    sl_bar = _bar(START + timedelta(minutes=10), (99.5, 100.2, 98.4, 99.8))
    runner.run_one_cycle(sl_bar)

    assert 7001 not in runner._positions
    # Circuit breaker fed the loss; same-level guard recorded the SL level.
    assert runner.risk.circuit_breaker.state.consecutive_losses == 1
    assert runner.risk.same_level_guard.state.last_sl_level == pytest.approx(99.0)
    closed = [r for r in runner.kpi.records if r.event == "trade_closed"][-1]
    assert closed.fields["win"] is False
    assert closed.fields["kind"] == "stop_loss"


def test_paper_tp_close_feeds_breaker_a_win():
    runner, adapter, connector = _make_runner()
    adapter._candles = _seed()
    adapter.queue(_candidate())
    runner.run_one_cycle(_bar(START, _seed_row()))
    connector.positions.append(_pos(7001, comment="poi-1:D@3"))
    connector.positions[0]["tp"] = 101.0   # broker reports a TP at fill time
    runner.run_one_cycle(_bar(START + timedelta(minutes=5), _seed_row()))
    assert runner._positions[7001].tp == 101.0
    connector.positions.clear()
    tp_bar = _bar(START + timedelta(minutes=10), (100.3, 101.5, 100.2, 101.4))
    runner.run_one_cycle(tp_bar)

    assert runner.risk.circuit_breaker.state.consecutive_losses == 0
    closed = [r for r in runner.kpi.records if r.event == "trade_closed"][-1]
    assert closed.fields["win"] is True
    assert closed.fields["kind"] == "take_profit"


def _seed_row():
    return (100.0, 101.0, 99.0, 100.0)


# ---------------------------------------------------------------------- #
# I4 — terminal-state retention (engine + adapter)
# ---------------------------------------------------------------------- #
def test_engine_prunes_terminal_pois_and_honours_retain():
    engine = PipelineEngine()

    def _arm():
        poi = _m1_poi()
        engine.arm_at(poi, arm_bar=0)
        return poi

    poi_tested = _arm()
    poi_violated = _arm()
    poi_fresh = _arm()

    touch = Candle(timestamp=START, open=98.8, high=99.1, low=98.4, close=98.9, timeframe=TF)
    assert engine.feed_bar(poi_tested, touch) == POIState.TESTED.value
    # LONG violation: the candle's range is entirely BELOW the zone bottom
    # (a close beyond the zone without ever touching it).
    viol = Candle(timestamp=START, open=98.2, high=98.5, low=98.0, close=98.3, timeframe=TF)
    assert engine.feed_bar(poi_violated, viol) == POIState.VIOLATED.value

    # retain keeps a terminal POI; everything else terminal is pruned.
    pruned = engine.prune_terminal(retain_ids={poi_tested.id})
    assert set(pruned) == {poi_violated.id}
    assert engine.episode(poi_violated) is None
    assert [p.id for p in engine.tracked_pois()] == [poi_tested.id, poi_fresh.id]

    # Once the retained POI's state resolves, it is pruned too.
    pruned2 = engine.prune_terminal()
    assert pruned2 == [poi_tested.id]
    assert [p.id for p in engine.tracked_pois()] == [poi_fresh.id]
    assert engine.prune_terminal() == []                     # FRESH never pruned


def test_adapter_keeps_workflow_live_and_touch_window_pois():
    engine = PipelineEngine()
    poi = _m1_poi()
    engine.arm_at(poi, arm_bar=0)
    engine.state_machine.transition(poi, POIState.TESTED)    # touched
    adapter = PipelineAdapter(engine)

    # A workflow-live TESTED POI is NEVER pruned (mid-flight one-shot).
    adapter._workflows[poi.id] = _Workflow(
        candidate=None, created_bar=1, completion_index=2, expiry_bars=1
    )
    assert adapter.prune_terminal_pois(set(), bar_index=5) == []
    assert engine.tracked_pois() == [poi]

    # Workflow consumed + beyond the touch window (touch bar + 1) → pruned.
    adapter._workflows.pop(poi.id)
    adapter._tested_bar[poi.id] = 1
    assert adapter.prune_terminal_pois(set(), bar_index=3) == [poi.id]
    assert engine.tracked_pois() == []
    assert poi.id not in adapter._workflows