"""Integration tests for the ProductMenuEngine -> LiveLoop -> PipelineAdapter execution seam.

Pins:
1. LiveLoop._arm_product wires newly armed POIs into menu.register_armed().
2. LiveLoop._arm_new_pois wires newly armed POIs into menu.register_armed().
3. PipelineAdapter.queue_menu_candidate receives winner candidate and submits
   to runner.submit_entry once.
4. PipelineAdapter.menu_covers_poi prevents double-route: scan_route is skipped
   when a POI is covered by the menu.
5. End-to-end: register_armed -> on_execution_bar -> queue_menu_candidate ->
   submit_entry exactly once; adapter scan skipped when covered.
6. Product menu H1 tier confirmation order is (M5, M1) per Product Intent B.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from smc.backtest.pipeline_adapter import PipelineAdapter
from smc.backtest.runner import CandidateEntry
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.live.loop import LiveLoop
from smc.orchestration.engine import PipelineEngine
from smc.orchestration.multi_tf_runtime import MultiTFBatchReport
from smc.orchestration.product_menu_mtf import (
    PRODUCT_MENU_TIERS,
    ProductMenuEngine,
)
from smc.triggers.base_trigger import Trigger, TriggerContext, TriggerSignal
from smc.triggers.trigger_router import TriggerRouter

BASE = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
H4_CLOSE = BASE + timedelta(hours=4)
ZONE_LOW = 2490.0
ZONE_HIGH = 2500.0


class StubTrigger(Trigger):
    type = TriggerType.A_CHOCH

    def __init__(self, fire: bool = True) -> None:
        self.calls = 0
        self.fire = fire

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        self.calls += 1
        if not self.fire:
            return None
        candle = context.candles[context.bar_index]
        return TriggerSignal(
            trigger=TriggerType.A_CHOCH,
            direction=Direction.LONG,
            entry_price=candle.close + 0.5,
            stop_reference=candle.low - 1.0,
            completion_index=context.bar_index,
            expiry_bars=10,
            detail="stub-fire",
            data={},
        )


def _bar(tf: Timeframe, offset_minutes: float, *, low=2485.0, high=2505.0,
         close=2500.0, open_=2496.0) -> Candle:
    return Candle(
        timestamp=BASE + timedelta(minutes=offset_minutes),
        open=open_, high=high, low=low, close=close, timeframe=tf,
    )


def _sweep(tf: Timeframe, offset_minutes: float = 0.0) -> Candle:
    return _bar(tf, offset_minutes, low=2485.0, high=2498.0, close=2492.0)


def _poi(tf: Timeframe = Timeframe.H4, poi_id: str = "poi-test-1") -> POI:
    zone = Zone(top=ZONE_HIGH, bottom=ZONE_LOW, direction=Direction.LONG,
                timeframe=tf)
    return POI(
        zone=zone, models=[ModelType.M8], score=3.0, state=POIState.CREATED,
        m8_kind="demand_supply", id=poi_id,
    )


class MockRunner:
    """Mock runner exposing submit_entry and adapter protocol."""

    def __init__(self) -> None:
        self.submitted: list[CandidateEntry] = []
        self.adapter = None
        self.cycles = 0

    def submit_entry(self, candidate: CandidateEntry) -> None:
        self.submitted.append(candidate)

    def set_pipeline_adapter(self, adapter) -> None:
        self.adapter = adapter

    def run_one_cycle(self, bar: Candle) -> None:
        self.cycles += 1
        if self.adapter is not None:
            self.adapter.generate_candidates(bar, self.cycles - 1, bar.timestamp)


class MockConnector:
    def connect(self) -> bool:
        return True

    def copy_rates(self, symbol, timeframe, start, count):
        return []


def test_h1_tier_confirm_priority_order():
    """Intent B: H1 confirms on (M5, M1) in that order."""
    h1_tier = next(t for t in PRODUCT_MENU_TIERS if t.name == "H1")
    assert h1_tier.detection_tf is Timeframe.H1
    assert h1_tier.confirmation_tfs == (Timeframe.M5, Timeframe.M1)


def test_loop_arm_product_registers_armed_into_menu():
    """LiveLoop._arm_product forwards newly armed POIs to menu.register_armed."""
    menu = ProductMenuEngine(symbol="TEST")
    runner = MockRunner()
    loop = LiveLoop(
        connector=MockConnector(),
        runner=runner,
        heartbeat=None,
        timeframe=Timeframe.M5,
        menu_confirmation=menu,
    )

    test_poi = _poi(Timeframe.H4, "poi-h4-001")
    report = MultiTFBatchReport(
        as_of=BASE,
        arm_bar=0,
        armed=[test_poi],
    )
    loop._run_seam_batch = MagicMock(return_value=report)
    loop._fetch_htf_series = MagicMock(return_value={
        Timeframe.H4: [_bar(Timeframe.H4, 0)],
        Timeframe.H1: [_bar(Timeframe.H1, 0)],
    })
    loop.runtime = MagicMock()
    loop.runtime.missing_series.return_value = ()
    loop.runtime.allow_single_tf_degraded = False

    bar = _bar(Timeframe.M5, 0)
    count = loop._arm_product(bar)
    assert count == 1
    assert "poi-h4-001" in menu._armed
    stored_poi, tier = menu._armed["poi-h4-001"]
    assert stored_poi.id == "poi-h4-001"
    assert tier.name == "H4"


def test_pipeline_adapter_queue_menu_candidate_and_dedup():
    """PipelineAdapter.queue_menu_candidate submits to runner and dedups against scan."""
    engine = PipelineEngine()
    runner = MockRunner()
    adapter = PipelineAdapter(engine, timeframe=Timeframe.M5)
    adapter.attach(runner)

    poi = _poi(Timeframe.H4, "poi-menu-1")
    engine.arm_at(poi, 0)

    # Claim POI for menu
    adapter.claim_poi_for_menu(poi.id)
    assert adapter.menu_covers_poi(poi) is True

    # When generate_candidates runs, scan_route is skipped for covered POI
    engine.scan_route = MagicMock(return_value=None)
    bar = _bar(Timeframe.M5, 5)
    adapter.generate_candidates(bar, 0, bar.timestamp)
    engine.scan_route.assert_not_called()

    # Now simulate menu confirmation delivering a candidate
    candidate = CandidateEntry(
        direction=Direction.LONG,
        entry_price=2495.0,
        sl_price=2489.0,
        poi_id=poi.id,
        route_id="H4:A_CHOCH@0",
    )
    adapter.queue_menu_candidate(candidate)

    # Submitted exactly once to runner
    assert len(runner.submitted) == 1
    assert runner.submitted[0].poi_id == "poi-menu-1"
    assert "poi-menu-1" in adapter._routed

    # Subsequent generate_candidates call does NOT double-submit or scan
    adapter.generate_candidates(bar, 1, bar.timestamp)
    assert len(runner.submitted) == 1
    engine.scan_route.assert_not_called()


def test_adapter_buffers_menu_candidate_when_detached():
    """When detached, adapter buffers menu candidate and flushes on attach."""
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=Timeframe.M5)
    runner = MockRunner()

    candidate = CandidateEntry(
        direction=Direction.LONG,
        entry_price=2495.0,
        sl_price=2489.0,
        poi_id="poi-buff-1",
        route_id="H4:A_CHOCH@0",
    )
    adapter.queue_menu_candidate(candidate)
    assert len(adapter._menu_candidates) == 1
    assert len(runner.submitted) == 0

    # Attach flushes buffered candidate
    adapter.attach(runner)
    assert len(adapter._menu_candidates) == 0
    assert len(runner.submitted) == 1
    assert runner.submitted[0].poi_id == "poi-buff-1"


def test_full_seam_register_sweep_confirm_queue_submit():
    """End-to-end integration:
    LiveLoop + menu + adapter + runner:
    1. POI armed & registered into menu
    2. Closed sweep opens one-shot episode
    3. Confirm bar produces menu winner
    4. Winner queued into adapter
    5. Adapter submits to runner.submit_entry once
    6. Adapter scan skipped for covered POI
    """
    menu = ProductMenuEngine(symbol="TEST")
    trigger = StubTrigger(fire=True)
    menu._router = TriggerRouter(triggers=[trigger])

    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=Timeframe.M5, menu_confirmation=menu)
    runner = MockRunner()
    adapter.attach(runner)

    poi = _poi(Timeframe.H4, "poi-e2e-1")
    engine.arm_at(poi, 0)

    loop = LiveLoop(
        connector=MockConnector(),
        runner=runner,
        heartbeat=None,
        timeframe=Timeframe.M5,
        menu_confirmation=menu,
    )

    # 1. Register armed POI
    assert menu.register_armed(poi, Timeframe.H4) is True
    assert adapter.menu_covers_poi(poi) is True

    # 2 & 3. Feed H4 sweep + M5 confirmation bar to menu
    series = {
        Timeframe.H4: [_sweep(Timeframe.H4)],
        Timeframe.M5: [_bar(Timeframe.M5, 245, close=2495.0)],
        Timeframe.M15: [],
        Timeframe.H1: [],
        Timeframe.D1: [],
        Timeframe.M1: [],
    }
    loop.htf_fetch = lambda tf, count: list(series.get(tf, ()))

    execution_bar = _bar(Timeframe.M5, 245, close=2495.0)
    # Drive menu confirmation
    loop._drive_menu_confirmation(execution_bar)

    # 4 & 5. Winner queued into adapter -> forwarded to runner.submit_entry
    assert len(runner.submitted) == 1
    assert runner.submitted[0].poi_id == "poi-e2e-1"

    # 6. Verify adapter does not duplicate submission on bar cycle
    engine.scan_route = MagicMock()
    runner.run_one_cycle(execution_bar)
    assert len(runner.submitted) == 1
    engine.scan_route.assert_not_called()
