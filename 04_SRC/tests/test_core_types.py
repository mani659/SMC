"""Phase 0 validation — all core dataclasses instantiate correctly."""

from datetime import datetime, timezone

import pytest

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core import Candle, Direction, Event, LiquidityLevel, POI, Swing, Zone
from smc.core.enums import LiquidityType, POIState, PoolType

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


def _candle(**overrides):
    defaults = dict(
        timestamp=NOW,
        open=100.0,
        high=105.0,
        low=95.0,
        close=104.0,
        volume=100.0,
        timeframe=Timeframe.M5,
    )
    defaults.update(overrides)
    return Candle(**defaults)


def test_candle_instantiates_and_is_frozen():
    candle = _candle()
    assert candle.close == 104.0
    assert candle.is_bullish
    with pytest.raises(Exception):
        candle.close = 99.0  # frozen dataclass must reject mutation


def test_candle_derived_properties():
    candle = _candle(open=100.0, high=105.0, low=95.0, close=104.0)
    assert candle.is_bullish
    assert candle.body == 4.0
    assert candle.range == 10.0
    assert candle.upper_wick == 1.0
    assert candle.lower_wick == 5.0

    bear = _candle(open=104.0, high=105.0, low=95.0, close=96.0)
    assert bear.is_bearish
    assert bear.body == 8.0
    assert bear.upper_wick == 1.0
    assert bear.lower_wick == 1.0


def test_swing_instantiates():
    swing = Swing(
        is_high=True,
        level=105.0,
        candle_index=3,
        base_candle=_candle(high=105.0),
        timeframe=Timeframe.H1,
    )
    assert swing.is_high and not swing.is_low
    assert swing.is_valid is False
    assert swing.confirmed_index is None
    assert swing.pool is PoolType.BSL
    assert swing.timestamp == NOW

    low = Swing(
        is_high=False,
        level=95.0,
        candle_index=5,
        base_candle=_candle(low=95.0),
        is_valid=True,
        confirmed_index=9,
    )
    assert low.pool is PoolType.SSL
    assert low.is_valid and low.confirmed_index == 9


def test_zone_instantiates_and_validates():
    zone = Zone(top=105.0, bottom=100.0, direction=Direction.LONG)
    assert zone.height == 5.0
    assert zone.midpoint == 102.5
    assert zone.contains(102.5)
    assert not zone.contains(106.0)
    assert zone.distance_from(106.0) == 1.0
    assert zone.distance_from(99.0) == 1.0
    assert zone.distance_from(102.0) == 0.0

    with pytest.raises(ValueError):
        Zone(top=99.0, bottom=100.0, direction=Direction.LONG)


def test_liquidity_level_instantiates():
    level = LiquidityLevel(
        type=LiquidityType.EQUAL_HIGHS_LOWS,
        level=105.0,
        pool=PoolType.BSL,
        timeframe=Timeframe.M15,
        formed_at=NOW,
    )
    assert level.type is LiquidityType.EQUAL_HIGHS_LOWS
    assert not level.is_swept
    level.swept_at = NOW
    assert level.is_swept


def test_poi_instantiates_with_defaults():
    zone = Zone(top=100.0, bottom=98.0, direction=Direction.SHORT)
    poi = POI(zone=zone, models=[ModelType.M3], score=0.8)
    assert poi.state is POIState.CREATED
    assert poi.touch_count == 0
    assert poi.htf_overlap is False
    assert poi.model_count == 1
    assert len(poi.id) == 36  # uuid4 hex string

    poi.add_model(ModelType.M8)
    assert poi.model_count == 2
    poi.add_model(ModelType.M8)  # duplicate ignored
    assert poi.model_count == 2
    poi.state = POIState.TESTED
    assert poi.state is POIState.TESTED


def test_event_instantiates():
    event = Event(type="bar_closed", timestamp=NOW, payload={"close": 104.0})
    assert event.payload["close"] == 104.0
    assert event.type == "bar_closed"
    assert len(event.event_id) == 36

    bare = Event(type="ping", timestamp=NOW)
    assert bare.payload == {}