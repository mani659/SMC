"""Phase 4 — PipelineEngine: merge → validate → arm → trigger → execute.

Reuses the Phase 3 all-pillars-passing fixture (FVG zone [100.0, 100.2] on a
21-bar M5 series, valid dealing range [99, 105], injected displacement).
"""

from datetime import datetime, timedelta, timezone

import pytest

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, LiquidityType, POIState, PoolType, TriggerType
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.detection.displacement_checker import check_displacement
from smc.execution.order_manager import (
    ORDER_TYPE_BUY_LIMIT,
    ORDER_TYPE_SELL_LIMIT,
    OrderKind,
    OrderManager,
    OrderRequest,
    TRADE_ACTION_PENDING,
)
from smc.execution.session_filter import Session
from smc.orchestration.engine import PipelineEngine, build_limit_request
from smc.triggers.base_trigger import TriggerContext, TriggerSignal
from smc.triggers.trigger_d_two_bar import TwoBarReversalTrigger
from smc.triggers.trigger_router import TriggerRoute
from smc.validation.validation_pipeline import ValidationDecision

TF = Timeframe.M5
CALM = [(99.5, 99.7, 99.3, 99.6)]

SUCCESS_ROWS = CALM * 15 + [
    (99.9, 100.0, 99.7, 99.9),       # c1: first FVG candle
    (100.0, 100.1, 99.6, 100.0),     # c2: middle candle
    (100.15, 100.35, 100.2, 100.3),  # c3: FVG [100.0, 100.2]
    (100.3, 100.4, 100.1, 100.35),
    (100.35, 100.5, 100.3, 100.45),
    (100.45, 100.6, 100.4, 100.55),
]
PRE_DISP = [(100.5, 101.5, 99.5, 100.5)] * 15


def _fvg_poi(models=None):
    return POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
        models=models or [ModelType.M1, ModelType.M2],
    )


def _range_swings(candles, swing_factory):
    return [
        swing_factory(candles, 3, True, level=105.0),
        swing_factory(candles, 4, False, level=99.0),
    ]


def _displacement(candle_factory):
    candles = candle_factory(
        PRE_DISP
        + [
            (99.8, 100.5, 98.2, 99.6),
            (100.0, 102.5, 100.3, 100.8),
            (101.0, 103.5, 102.0, 103.2),
        ]
    )
    return check_displacement(candles, Direction.LONG, sweep_index=15, bos_level=101.2)


def _ssl(price: float) -> LiquidityLevel:
    return LiquidityLevel(
        type=LiquidityType.EQUAL_HIGHS_LOWS, level=price, pool=PoolType.SSL, timeframe=TF
    )


def test_merge_then_validate_passes_with_displacement(
    candle_factory, swing_factory
):
    candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
    swings = _range_swings(candles, swing_factory)
    engine = PipelineEngine()

    # Two overlapping same-direction POIs (M1 + M5 tags) → one merged POI.
    overlapping = [_fvg_poi([ModelType.M1]), _fvg_poi([ModelType.M5])]
    merged = engine.merge(overlapping)
    assert len(merged) == 1
    assert set(merged[0].models) == {ModelType.M1, ModelType.M5}

    displacement = _displacement(candle_factory)
    passed, results = engine.validate(
        merged,
        candles,
        swings,
        [_ssl(100.3)],
        displacement_map={merged[0].id: displacement},
        merge_first=False,
    )
    assert len(passed) == 1
    assert passed[0].state is POIState.FRESH  # armed by the Phase 3 pipeline
    assert passed[0].score == pytest.approx(2.0)  # §1 score from two tags
    assert results[0].decision is ValidationDecision.PASS


def test_missing_displacement_rejects_fail_fast(candle_factory, swing_factory):
    candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
    engine = PipelineEngine()
    passed, results = engine.validate(
        [_fvg_poi()],
        candles,
        _range_swings(candles, swing_factory),
        [_ssl(100.3)],
        displacement_map={},  # Pillar 2 injection seam — nothing supplied
        merge_first=False,
    )
    assert passed == []
    assert results[0].decision is ValidationDecision.REJECTED


def test_validation_scoring_not_overwritten(candle_factory, swing_factory):
    candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
    poi = _fvg_poi()
    poi.score = 3.0  # pre-scored by an earlier stage — pipeline must not clobber
    displacement = _displacement(candle_factory)
    engine = PipelineEngine()
    passed, _ = engine.validate(
        [poi],
        candles,
        _range_swings(candles, swing_factory),
        [_ssl(100.3)],
        displacement_map={poi.id: displacement},
        merge_first=False,
    )
    assert passed[0].score == pytest.approx(3.0)


def test_m8_uses_the_same_state_machine(candle_factory, swing_factory):
    candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
    poi = _fvg_poi([ModelType.M8])
    displacement = _displacement(candle_factory)
    engine = PipelineEngine()
    passed, _ = engine.validate(
        [poi],
        candles,
        _range_swings(candles, swing_factory),
        [_ssl(100.3)],
        displacement_map={poi.id: displacement},
        merge_first=False,
    )
    assert len(passed) == 1 and passed[0].state is POIState.FRESH
    engine.arm_at(passed[0], arm_bar=20)
    # First touch → TESTED (no special-casing for M8).
    touch = Candle(
        timestamp=candles[-1].timestamp + timedelta(minutes=5),
        open=100.0, high=100.0, low=99.6, close=99.9, timeframe=TF,
    )
    assert engine.feed_bar(passed[0], touch) == POIState.TESTED.value
    assert not engine.state_machine.can_trade(passed[0])
    # A later bar cannot resurrect the POI.
    later = Candle(
        timestamp=touch.timestamp + timedelta(minutes=5),
        open=99.8, high=100.4, low=99.7, close=100.1, timeframe=TF,
    )
    assert engine.feed_bar(passed[0], later) == POIState.TESTED.value


def test_route_builds_only_limit_orders(candle_factory, swing_factory):
    # Two-bar reversal route (Trigger D — never a market order, §10).
    rows = [
        (120.0, 120.4, 119.8, 120.2),
        (120.2, 120.6, 119.9, 120.1, 500.0),
        (119.5, 120.6, 119.2, 120.5, 300.0),
        (120.4, 120.8, 120.1, 120.6),
    ]
    candles = candle_factory(rows, timeframe=TF)
    poi = POI(
        zone=Zone(top=121.0, bottom=120.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M6],
    )
    ctx = TriggerContext(poi=poi, candles=candles, swings=[], bar_index=3, from_bar=2)
    signal = TwoBarReversalTrigger().evaluate(ctx)
    assert signal is not None

    route = TriggerRoute(poi=poi, bar=3, signal=signal)
    request = build_limit_request(poi, route, volume=0.1)
    assert request.kind is OrderKind.LIMIT
    assert request.price == (119.5 + 120.5) / 2


class _FakeConnector:
    def __init__(self):
        self.sent: list[dict] = []
        self.next_retcode = 10008

    def order_send(self, request: dict):
        self.sent.append(request)
        return {"retcode": self.next_retcode, "order": 555, "comment": "ok"}


def test_execute_route_places_pending_limit(candle_factory, swing_factory):
    connector = _FakeConnector()
    manager = OrderManager(connector, symbol="XAUUSD.x")
    engine = PipelineEngine(order_manager=manager)

    poi = _fvg_poi()
    signal = TriggerSignal(
        trigger=TriggerType.A_CHOCH,
        direction=Direction.LONG,
        entry_price=101.5,
        stop_reference=99.4,
        completion_index=20,
        expiry_bars=20,
    )
    route = TriggerRoute(poi=poi, bar=20, signal=signal)
    engine.arm_at(poi, arm_bar=19)
    outcome = engine.execute_route(
        route, volume=0.5, now=datetime(2026, 3, 12, 13, 0, tzinfo=timezone.utc)
    )
    assert outcome.blocked is None
    assert outcome.order_result is not None and outcome.order_result.placed
    request = connector.sent[0]
    assert request["action"] == TRADE_ACTION_PENDING
    assert request["type"] == ORDER_TYPE_BUY_LIMIT
    assert request["price"] == 101.5


def _news_gate_route(engine: PipelineEngine) -> TriggerRoute:
    poi = _fvg_poi()
    signal = TriggerSignal(
        trigger=TriggerType.A_CHOCH, direction=Direction.LONG, entry_price=100.0,
        stop_reference=99.0, completion_index=1, expiry_bars=20,
    )
    route = TriggerRoute(poi=poi, bar=1, signal=signal)
    engine.arm_at(poi, arm_bar=0)
    return route


def test_execute_route_blocked_by_news_and_session(candle_factory):
    from smc.execution.news_guard import NewsEvent

    now = datetime(2026, 3, 12, 13, 0, tzinfo=timezone.utc)

    engine = PipelineEngine()
    event = NewsEvent(kind="CPI", at=now + timedelta(minutes=10))
    outcome = engine.execute_route(_news_gate_route(engine), volume=0.1, news_events=[event], now=now)
    assert outcome.blocked == "news"
    assert outcome.request is None

    # Allowed sessions exclude the current one (13:00 UTC = NY).
    engine2 = PipelineEngine()
    route2 = _news_gate_route(engine2)
    outcome2 = engine2.execute_route(route2, volume=0.1, now=now, allowed_sessions=[Session.LONDON])
    assert outcome2.blocked == "session"


def test_execute_route_block_does_not_burn_one_shot(candle_factory):
    """I2 regression: a blocked route must NOT consume the §11 one-shot.

    The same POI may be re-attempted once the gate clears, and the accepted
    attempt is the one that marks it fired.
    """
    from smc.execution.news_guard import NewsEvent

    blocked_at = datetime(2026, 3, 12, 13, 0, tzinfo=timezone.utc)
    clear_at = blocked_at + timedelta(hours=2)  # far outside the §11 window
    event = NewsEvent(kind="CPI", at=blocked_at + timedelta(minutes=10))

    engine = PipelineEngine()
    route = _news_gate_route(engine)

    blocked = engine.execute_route(
        route, volume=0.1, now=blocked_at, news_events=[event]
    )
    assert blocked.blocked == "news"
    assert not engine.episode(route.poi).fired  # one-shot NOT consumed

    # Session gate blocks next; still not consumed.
    blocked2 = engine.execute_route(
        route,
        volume=0.1,
        now=clear_at,
        allowed_sessions=[Session.LONDON],  # 15:00 UTC is NY — not London
    )
    assert blocked2.blocked == "session"
    assert not engine.episode(route.poi).fired

    # Gate clears → the accepted attempt fires and consumes the one-shot.
    accepted = engine.execute_route(
        route, volume=0.1, now=clear_at, allowed_sessions=[Session.NEW_YORK]
    )
    assert accepted.blocked is None
    assert engine.episode(route.poi).fired

    # A second accepted attempt is rejected by the fired latch.
    outcome = engine.execute_route(route, volume=0.1, now=clear_at)
    assert outcome is accepted  # cached fired outcome


def test_execute_route_requires_injected_now(candle_factory):
    """I5: the clock is injected — omitting ``now`` must fail loudly."""
    engine = PipelineEngine()
    route = _news_gate_route(engine)
    with pytest.raises(TypeError):
        engine.execute_route(route, volume=0.1)  # no now= -> TypeError
    assert not engine.episode(route.poi).fired


def _risk_route(engine: PipelineEngine) -> TriggerRoute:
    poi = _fvg_poi()
    signal = TriggerSignal(
        trigger=TriggerType.A_CHOCH, direction=Direction.LONG, entry_price=100.0,
        stop_reference=99.0, completion_index=1, expiry_bars=20,
    )
    route = TriggerRoute(poi=poi, bar=1, signal=signal)
    engine.arm_at(poi, arm_bar=0)
    return route


def test_compute_risk_lots_goes_through_risk_policy(candle_factory):
    """C2 regression: sizing is the §28.7 policy path, not the raw formula.

    A risk fraction far below ``RISK_PCT_MIN`` must be clamped UP into the
    band, and an aggressive size must be capped at ``LOT_MAX_SAFETY`` — no
    public helper sizes outside the band or above the cap.
    """
    from smc.config.locked_constants import LOT_MAX_SAFETY, RISK_PCT_MAX, RISK_PCT_MIN

    engine = PipelineEngine()
    route = _risk_route(engine)

    # 0.001% requested → clamped UP to RISK_PCT_MIN (0.5%) → 0.05 lots
    # (equity kept small so the LOT_MAX_SAFETY cap does not mask the clamp).
    lots = engine.compute_risk_lots(
        route, equity=100, risk_fraction=0.00001,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01,
    )
    expected_floor = (100 * (RISK_PCT_MIN / 100.0)) / (1.0 * 10.0)
    assert lots == pytest.approx(expected_floor)
    assert 0.0 < lots <= LOT_MAX_SAFETY

    # Aggressive equity+SL → raw formula would blow past the cap; policy caps.
    lots = engine.compute_risk_lots(
        route, equity=1_000_000, risk_fraction=0.05,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01,
    )
    assert lots == pytest.approx(LOT_MAX_SAFETY)

    # Inside-band request passes through the same path (clamped to band max).
    lots = engine.compute_risk_lots(
        route, equity=10_000, risk_fraction=RISK_PCT_MAX / 100.0,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01,
    )
    assert lots == pytest.approx(0.10)  # 10_000 * 1% / (1.0 * 10.0)
    assert lots <= LOT_MAX_SAFETY
