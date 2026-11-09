"""Product multi-TF menu engine tests (policy: PRODUCT_POLICY_MULTI_TF_CONFIRMATION).

Pins the locked menu contract:

1. the tier table is DATA (tier name / detection TF / confirmation TFs / 20-bar
   expiry on the DETECTION TF) and the engine exposes the menu streams;
2. no confirmation without a prior CLOSED R2 sweep of the POI zone;
3. a sweep opens exactly ONE one-shot window on that tier's confirmation TFs
   (H4 → M5/M15, DAY → H1 only — an ineligible stream is never evaluated);
4. the window expires after 20 detection-TF bars without a confirmation;
5. the first valid confirmation wins, consumes the sweep and produces the
   frozen bridge candidate with the menu identity stamp.

.. note::
   Rebuilt 2026-11-08 after the file was lost to a corruption event (only
   lines 120-249 survived); assertions are taken from the surviving fragment
   and the locked policy document.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.config.model_type import ModelType
from smc.orchestration.product_menu_mtf import (
    MENU_EXPIRY_BARS,
    PRODUCT_MENU_DETECTION_TIMEFRAMES,
    PRODUCT_MENU_PILLAR_PATH,
    PRODUCT_MENU_TIERS,
    MenuEpisodeStatus,
    ProductMenuEngine,
    menu_covers,
)
from smc.triggers.base_trigger import (
    Trigger,
    TriggerContext,
    TriggerSignal,
)
from smc.triggers.trigger_router import TriggerRouter

BASE = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
H4_CLOSE = BASE + timedelta(hours=4)

ZONE_LOW = 2490.0
ZONE_HIGH = 2500.0


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
class StubTrigger(Trigger):
    """Fires on every evaluation with a configurable completion index."""

    type = TriggerType.A_CHOCH

    def __init__(self, fire: bool = True, completion_offset: int = 0) -> None:
        self.calls = 0
        self.fire = fire
        self.completion_offset = completion_offset

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        self.calls += 1
        if not self.fire:
            return None
        index = context.bar_index + self.completion_offset
        candle = context.candles[context.bar_index]
        return TriggerSignal(
            trigger=TriggerType.A_CHOCH,
            direction=Direction.LONG,
            entry_price=candle.close + 0.5,
            stop_reference=candle.low - 1.0,
            completion_index=index,
            expiry_bars=10,
            detail="stub-fire",
            data={"stub_index": index},
        )


def _bar(tf: Timeframe, offset_minutes: float, *, low=2485.0, high=2505.0,
         close=2500.0, open_=2496.0) -> Candle:
    return Candle(
        timestamp=BASE + timedelta(minutes=offset_minutes),
        open=open_, high=high, low=low, close=close, timeframe=tf,
    )


def _sweep(tf: Timeframe, offset_minutes: float = 0.0) -> Candle:
    """LONG sweep of the 2490..2500 demand zone: wick below, body back inside."""
    return _bar(tf, offset_minutes, low=2485.0, high=2498.0, close=2492.0)


def _calm(tf: Timeframe, offset_minutes: float) -> Candle:
    """Entirely inside the zone (no sweep geometry)."""
    return _bar(tf, offset_minutes, low=2491.0, high=2499.0, close=2495.0)


def _confirm(tf: Timeframe, offset_minutes: float, *, close=2497.0) -> Candle:
    return _bar(tf, offset_minutes, low=2491.0, high=2499.0, close=close)


def _demand_poi(tf: Timeframe = Timeframe.H4, poi_id: str = "poi-1") -> POI:
    zone = Zone(top=ZONE_HIGH, bottom=ZONE_LOW, direction=Direction.LONG,
                timeframe=tf)
    return POI(
        zone=zone, models=[ModelType.M8], score=3.0, state=POIState.CREATED,
        m8_kind="demand_supply", id=poi_id,
    )


def _engine(tier_tf: Timeframe = Timeframe.H4, *, fire: bool = True):
    engine = ProductMenuEngine(symbol="TEST")
    stub = StubTrigger(fire=fire)
    engine._router = TriggerRouter(triggers=[stub])
    poi = _demand_poi(tier_tf)
    assert engine.register_armed(poi, tier_tf) is True
    return engine, stub, poi


# --------------------------------------------------------------------------- #
# 1. Tier table is pinned (the menu is data, not logic)
# --------------------------------------------------------------------------- #
def test_tier_table_matches_the_locked_menu():
    table = {
        tier.name: (tier.detection_tf, tier.confirmation_tfs, tier.expiry_bars)
        for tier in PRODUCT_MENU_TIERS
    }
    assert table == {
        "DAY": (Timeframe.D1, (Timeframe.H1,), 20),
        "H4": (Timeframe.H4, (Timeframe.M5, Timeframe.M15), 20),
        "H1": (Timeframe.H1, (Timeframe.M5, Timeframe.M1), 20),
        "M15": (Timeframe.M15, (Timeframe.M1,), 20),
    }
    assert PRODUCT_MENU_DETECTION_TIMEFRAMES == (
        Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15)
    assert MENU_EXPIRY_BARS == 20


def test_engine_exposes_menu_streams():
    engine = ProductMenuEngine(symbol="TEST")
    assert engine.detection_timeframes == (
        Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15)
    assert engine.confirmation_timeframes == (
        Timeframe.H1, Timeframe.M5, Timeframe.M15, Timeframe.M1)
    assert engine.tier_for(Timeframe.D1).confirmation_tfs == (Timeframe.H1,)
    assert engine.tier_for(Timeframe.M1) is None


def test_menu_covers_requires_all_four_tiers():
    assert menu_covers((Timeframe.M15, Timeframe.H1, Timeframe.D1, Timeframe.H4))
    assert not menu_covers((Timeframe.H4, Timeframe.H1))
    assert not menu_covers((Timeframe.D1, Timeframe.H4, Timeframe.H1))
    assert not menu_covers(())


def test_register_armed_refuses_a_non_menu_timeframe():
    engine = ProductMenuEngine(symbol="TEST")
    assert engine.register_armed(_demand_poi(Timeframe.M1), Timeframe.M1) is False
    assert engine.register_armed(_demand_poi(Timeframe.H4), Timeframe.H4) is True


# --------------------------------------------------------------------------- #
# 2. Sweep gate: no confirmation without a prior CLOSED sweep
# --------------------------------------------------------------------------- #
def test_no_sweep_no_episode_and_no_winner():
    engine, _, _ = _engine(Timeframe.H4)
    for index in range(1, 26):
        engine.on_execution_bar(
            {Timeframe.H4: [_calm(Timeframe.H4, 240 * i) for i in range(index)]},
            as_of=BASE + timedelta(hours=4 * index),
        )
    assert engine.episodes() == ()
    assert engine.winners == []
    assert engine.active_count() == 0


def test_sweep_opens_one_shot_window():
    engine, _, poi = _engine(Timeframe.H4)
    engine.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]}, as_of=H4_CLOSE)
    episodes = engine.episodes()
    assert len(episodes) == 1
    episode = episodes[0]
    assert episode.poi_id == poi.id
    assert episode.tier.name == "H4"
    assert episode.status is MenuEpisodeStatus.ACTIVE
    assert episode.sweep_index == 0
    assert episode.sweep_close_ts == H4_CLOSE
    assert engine.sweeps_total == 1


def test_window_expires_after_the_locked_detection_bar_count():
    """20 detection-TF bars after the sweep close the window (no confirm)."""
    engine, _, _ = _engine(Timeframe.H4)
    engine.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]}, as_of=H4_CLOSE)
    bars = [_sweep(Timeframe.H4)]
    for offset in range(1, MENU_EXPIRY_BARS + 2):
        # bar ``offset`` opens 4h * offset after the sweep bar's OPEN (so it
        # closes strictly after the sweep close) and the feed is closed-bar
        # honest at ``as_of`` = its close.
        bars.append(_calm(Timeframe.H4, 240 * offset))
        engine.on_execution_bar(
            {Timeframe.H4: list(bars)},
            as_of=BASE + timedelta(hours=4 * (offset + 1)),
        )
        episode = engine.episodes()[0]
        if offset <= MENU_EXPIRY_BARS:
            assert episode.status is MenuEpisodeStatus.ACTIVE, offset
        else:
            assert episode.status is MenuEpisodeStatus.EXPIRED, offset
    assert engine.winners == []
    assert engine.active_count() == 0


# --------------------------------------------------------------------------- #
# 3. Per-tier confirmation TFs (the mapping the brief asked to pin)
# --------------------------------------------------------------------------- #
def test_h4_tier_confirms_on_m15():
    engine, _, _ = _engine(Timeframe.H4)
    engine.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]}, as_of=H4_CLOSE)
    bar = _confirm(Timeframe.M15, 300)               # opens 05:00, closes 05:15
    winners = engine.on_execution_bar(
        {Timeframe.M15: [bar]}, as_of=BASE + timedelta(hours=5, minutes=15)
    )
    assert len(winners) == 1
    winner = winners[0]
    assert winner.tier_name == "H4"
    assert winner.detection_tf is Timeframe.H4
    assert winner.confirmation_tf is Timeframe.M15
    assert winner.candidate.pillar_path == PRODUCT_MENU_PILLAR_PATH


def test_h4_tier_confirms_on_m5():
    engine, _, _ = _engine(Timeframe.H4)
    engine.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]}, as_of=H4_CLOSE)
    bar = _confirm(Timeframe.M5, 241)                # 04:01 → 04:06
    winners = engine.on_execution_bar(
        {Timeframe.M5: [bar]}, as_of=BASE + timedelta(hours=4, minutes=6)
    )
    assert len(winners) == 1
    assert winners[0].confirmation_tf is Timeframe.M5


def test_day_tier_confirms_on_h1_only():
    engine, _, _ = _engine(Timeframe.D1)
    day_close = BASE + timedelta(days=1)
    engine.on_execution_bar({Timeframe.D1: [_sweep(Timeframe.D1)]},
                            as_of=day_close)
    winners = engine.on_execution_bar(
        {Timeframe.H1: [_confirm(Timeframe.H1, 1500)]},   # 25:00 → 26:00
        as_of=BASE + timedelta(hours=26),
    )
    assert len(winners) == 1
    assert winners[0].confirmation_tf is Timeframe.H1


def test_day_tier_ignores_m5_confirmation():
    engine, stub, _ = _engine(Timeframe.D1)
    engine.on_execution_bar({Timeframe.D1: [_sweep(Timeframe.D1)]},
                            as_of=BASE + timedelta(days=1))
    winners = engine.on_execution_bar(
        {Timeframe.M5: [_confirm(Timeframe.M5, 1500)]},
        as_of=BASE + timedelta(hours=25, minutes=10),
    )
    assert winners == []
    assert stub.calls == 0                # ineligible stream never evaluated
    assert engine.active_count() == 1


# --------------------------------------------------------------------------- #
# 4. One-shot discipline + frozen bridge identity
# --------------------------------------------------------------------------- #
def test_win_consumes_the_sweep_and_the_poi_never_rearms():
    engine, _, poi = _engine(Timeframe.H4)
    engine.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]}, as_of=H4_CLOSE)
    engine.on_execution_bar(
        {Timeframe.M15: [_confirm(Timeframe.M15, 300)]},
        as_of=BASE + timedelta(hours=5, minutes=15),
    )
    assert len(engine.winners) == 1
    assert engine.episodes()[0].status is MenuEpisodeStatus.WON
    # the consumed POI cannot open a second window
    assert engine.register_armed(poi, Timeframe.H4) is False
    bars = [_sweep(Timeframe.H4), _sweep(Timeframe.H4, 240)]
    engine.on_execution_bar({Timeframe.H4: bars}, as_of=BASE + timedelta(hours=8))
    assert len(engine.episodes()) == 1


def test_winner_stamp_carries_the_menu_identity():
    engine, _, poi = _engine(Timeframe.H4)
    engine.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]}, as_of=H4_CLOSE)
    winners = engine.on_execution_bar(
        {Timeframe.M15: [_confirm(Timeframe.M15, 300)]},
        as_of=BASE + timedelta(hours=5, minutes=15),
    )
    stamp = json.loads(winners[0].candidate.signal_data_json)["product_menu"]
    assert stamp["menu"] == PRODUCT_MENU_PILLAR_PATH
    assert stamp["tier"] == "H4"
    assert stamp["detection_tf"] == "H4"
    assert stamp["confirmation_tf"] == "M15"
    assert stamp["poi_id"] == poi.id
    assert stamp["zone"] == [ZONE_LOW, ZONE_HIGH]
    assert stamp["sweep_ts"] == BASE.isoformat()


def test_no_trigger_fire_keeps_the_window_open_until_expiry():
    engine, stub, _ = _engine(Timeframe.H4, fire=False)
    engine.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]}, as_of=H4_CLOSE)
    winners = engine.on_execution_bar(
        {Timeframe.M15: [_confirm(Timeframe.M15, 300)]},
        as_of=BASE + timedelta(hours=5, minutes=15),
    )
    assert winners == []
    assert stub.calls >= 1                # the stream WAS evaluated
    assert engine.active_count() == 1
