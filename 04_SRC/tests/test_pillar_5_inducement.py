"""Phase 3 — Pillar 5 (Inducement): soft scoring only (§7).

EQH/EQL pools (Phase 1 liquidity levels) or unconfirmed minor swings sitting
between current price and the POI zone = 100% score; without any = 70%.
Pillar 5 NEVER rejects (soft by design).
"""

from smc.config.locked_constants import (
    INDUCEMENT_WITHOUT_SCORE,
    INDUCEMENT_WITH_SCORE,
)
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, LiquidityType, POIState, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.validation.pillar import PillarStatus, ValidationContext
from smc.validation.pillar_5_inducement import InducementPillar

TF = Timeframe.M5


def _poi(direction: Direction) -> POI:
    if direction is Direction.LONG:
        zone = Zone(top=100.2, bottom=100.0, direction=direction, timeframe=TF)
    else:
        zone = Zone(top=101.7, bottom=101.5, direction=direction, timeframe=TF)
    return POI(zone=zone, models=[], state=POIState.CREATED)


def _ctx(candles, poi, levels=None, swings=None) -> ValidationContext:
    return ValidationContext(
        poi=poi,
        candles=candles,
        swings=swings or [],
        liquidity_levels=levels or [],
    )


def _ssl_level(price: float) -> LiquidityLevel:
    return LiquidityLevel(
        type=LiquidityType.EQUAL_HIGHS_LOWS, level=price, pool=PoolType.SSL, timeframe=TF
    )


def _bsl_level(price: float) -> LiquidityLevel:
    return LiquidityLevel(
        type=LiquidityType.EQUAL_HIGHS_LOWS, level=price, pool=PoolType.BSL, timeframe=TF
    )


def test_long_with_equal_lows_in_front_scores_full(candle_factory):
    candles = candle_factory([(100.5, 100.7, 100.4, 100.6)], timeframe=TF)
    ctx = _ctx(candles, _poi(Direction.LONG), levels=[_ssl_level(100.4)])
    result = InducementPillar().run(ctx)
    assert result.status is PillarStatus.PASS
    assert result.score_modifier == INDUCEMENT_WITH_SCORE
    assert result.data["kinds"] == ["equal_lows"]


def test_long_with_minor_swing_low_in_front_scores_full(candle_factory, swing_factory):
    candles = candle_factory([(100.5, 100.7, 100.4, 100.6)] * 2, timeframe=TF)
    minor = swing_factory(candles, 0, False, level=100.4, is_valid=False)
    ctx = _ctx(candles, _poi(Direction.LONG), swings=[minor])
    result = InducementPillar().run(ctx)
    assert result.status is PillarStatus.PASS
    assert result.score_modifier == INDUCEMENT_WITH_SCORE
    assert result.data["kinds"] == ["minor_swing_low"]


def test_short_with_equal_highs_in_front_scores_full(candle_factory):
    candles = candle_factory([(100.8, 101.1, 100.7, 101.0)], timeframe=TF)
    ctx = _ctx(candles, _poi(Direction.SHORT), levels=[_bsl_level(101.3)])
    result = InducementPillar().run(ctx)
    assert result.status is PillarStatus.PASS
    assert result.score_modifier == INDUCEMENT_WITH_SCORE
    assert result.data["kinds"] == ["equal_highs"]


def test_without_inducement_is_soft_seventy_percent(candle_factory):
    candles = candle_factory([(100.5, 100.7, 100.4, 100.6)] * 2, timeframe=TF)
    result = InducementPillar().run(_ctx(candles, _poi(Direction.LONG)))
    assert result.status is PillarStatus.FAIL  # R1 vocabulary: reduced score
    assert result.score_modifier == INDUCEMENT_WITHOUT_SCORE  # ... but never a rejection
    assert result.data["kinds"] == []


def test_level_inside_zone_is_not_inducement(candle_factory):
    # The SSL pool at 100.05 sits INSIDE the LONG zone [100.0, 100.2], not in
    # front of it -> not an inducement structure.
    candles = candle_factory([(100.5, 100.7, 100.4, 100.6)], timeframe=TF)
    ctx = _ctx(candles, _poi(Direction.LONG), levels=[_ssl_level(100.05)])
    result = InducementPillar().run(ctx)
    assert result.status is PillarStatus.FAIL
    assert result.score_modifier == INDUCEMENT_WITHOUT_SCORE


def test_no_candles_is_unavailable():
    ctx = _ctx([], _poi(Direction.LONG))
    result = InducementPillar().run(ctx)
    assert result.status is PillarStatus.UNAVAILABLE
