"""Phase 3 — Validation pipeline: 1→5 order, hard-fail short-circuit, scoring.

Success fixture: one bullish FVG zone [100.0, 100.2] on a 21-bar M5 series
(ATR = 0.4 → ±0.5×ATR band = ±0.2). POI zone == the FVG zone (Pillar 1 PASS),
a valid dealing range [99, 105] puts the POI midpoint 100.1 in DISCOUNT
(Pillar 3 PASS), the POI is CREATED (Pillar 4 PASS) and displacement is
injected from the Phase 1 checker (Pillar 2 PASS).
"""

from smc.config.locked_constants import (
    INDUCEMENT_WITHOUT_SCORE,
    INDUCEMENT_WITH_SCORE,
)
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, LiquidityType, POIState, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
import pytest

from smc.core.zone import Zone
from smc.detection.displacement_checker import check_displacement
from smc.validation.pillar import PillarStatus
from smc.validation.validation_pipeline import (
    ValidationDecision,
    ValidationPipeline,
)

TF = Timeframe.M5
CALM = [(99.5, 99.7, 99.3, 99.6)]

# 15 calm bars + one bullish FVG [100.0, 100.2] + approach bars (close 100.55).
SUCCESS_ROWS = CALM * 15 + [
    (99.9, 100.0, 99.7, 99.9),       # c1: first FVG candle
    (100.0, 100.1, 99.6, 100.0),     # c2: middle candle (no side gaps)
    (100.15, 100.35, 100.2, 100.3),  # c3: FVG [100.0, 100.2]
    (100.3, 100.4, 100.1, 100.35),   # approach
    (100.35, 100.5, 100.3, 100.45),  # approach
    (100.45, 100.6, 100.4, 100.55),  # last close 100.55
]

PRE_DISP = [(100.5, 101.5, 99.5, 100.5)] * 15


def _fvg_poi(state: POIState = POIState.CREATED) -> POI:
    return POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M1, ModelType.M2],
        state=state,
    )


def _naked_poi() -> POI:
    return POI(
        zone=Zone(top=104.2, bottom=104.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M1],
        state=POIState.CREATED,
    )


def _range_swings(candles, swing_factory):
    return [
        swing_factory(candles, 3, True, level=105.0),
        swing_factory(candles, 4, False, level=99.0),
    ]


def _passing_displacement(candle_factory):
    candles = candle_factory(
        PRE_DISP
        + [
            (99.8, 100.5, 98.2, 99.6),
            (100.0, 102.5, 100.3, 100.8),
            (101.0, 103.5, 102.0, 103.2),
        ]
    )
    return check_displacement(candles, Direction.LONG, sweep_index=15, bos_level=101.2)


def _ssl_level(price: float) -> LiquidityLevel:
    return LiquidityLevel(
        type=LiquidityType.EQUAL_HIGHS_LOWS, level=price, pool=PoolType.SSL, timeframe=TF
    )


def test_success_path_all_pillars(candle_factory, swing_factory):
    candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
    swings = _range_swings(candles, swing_factory)
    poi = _fvg_poi()
    result = ValidationPipeline().validate(
        poi,
        candles,
        swings,
        [_ssl_level(100.3)],  # inducement in front of the LONG zone (100.2, 100.55]
        displacement=_passing_displacement(candle_factory),
    )
    assert result.decision is ValidationDecision.PASS
    assert result.passed
    assert len(result.pillar_results) == 5
    assert all(r.status is PillarStatus.PASS for r in result.pillar_results)
    # §1 confluence score assigned from the two independent tags (M1 + M2).
    assert result.quality_score == pytest.approx(2.0)
    assert poi.score == pytest.approx(2.0)
    # POI armed CREATED -> FRESH by the state machine after validation.
    assert poi.state is POIState.FRESH
    assert result.inducement_modifier == INDUCEMENT_WITH_SCORE


def test_success_path_soft_inducement_seventy(candle_factory, swing_factory):
    candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
    poi = _fvg_poi()
    result = ValidationPipeline().validate(
        poi,
        candles,
        _range_swings(candles, swing_factory),
        [],  # no inducement structure
        displacement=_passing_displacement(candle_factory),
    )
    assert result.decision is ValidationDecision.PASS  # Pillar 5 never rejects
    assert result.inducement_modifier == pytest.approx(INDUCEMENT_WITHOUT_SCORE)
    assert poi.state is POIState.FRESH


def test_short_circuits_on_first_hard_fail(candle_factory, swing_factory):
    candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
    result = ValidationPipeline().validate(
        _naked_poi(),
        candles,
        _range_swings(candles, swing_factory),
        [],
        displacement=_passing_displacement(candle_factory),
    )
    assert result.decision is ValidationDecision.REJECTED
    assert len(result.pillar_results) == 1  # stopped at Pillar 1
    assert result.first_failure is not None and result.first_failure.pillar == 1


def test_rejected_when_displacement_hard_fails(candle_factory, swing_factory):
    candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
    weak = check_displacement(
        candle_factory(
            PRE_DISP
            + [
                (99.8, 100.5, 98.2, 99.0),
                (99.0, 99.4, 98.9, 99.1),
                (99.1, 99.3, 99.0, 99.1),
            ]
        ),
        Direction.LONG,
        sweep_index=15,
        bos_level=101.2,
    )
    assert weak.hard_fail
    result = ValidationPipeline().validate(
        _fvg_poi(),
        candles,
        _range_swings(candles, swing_factory),
        [],
        displacement=weak,
    )
    assert result.decision is ValidationDecision.REJECTED
    assert result.first_failure is not None and result.first_failure.pillar == 2
    assert len(result.pillar_results) == 2


def test_no_dealing_range_rejects_at_pillar_three(candle_factory, swing_factory):
    candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
    result = ValidationPipeline().validate(
        _fvg_poi(),
        candles,
        [],  # no valid high/low swings -> compute_dealing_range -> None
        [],
        displacement=_passing_displacement(candle_factory),
    )
    assert result.decision is ValidationDecision.REJECTED
    assert result.first_failure is not None and result.first_failure.pillar == 3
    assert result.first_failure.status is PillarStatus.UNAVAILABLE


def test_tested_poi_rejected_at_pillar_four(candle_factory, swing_factory):
    candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
    result = ValidationPipeline().validate(
        _fvg_poi(state=POIState.TESTED),
        candles,
        _range_swings(candles, swing_factory),
        [],
        displacement=_passing_displacement(candle_factory),
    )
    assert result.decision is ValidationDecision.REJECTED
    assert result.first_failure is not None and result.first_failure.pillar == 4


def test_already_scored_poi_is_not_overwritten(candle_factory, swing_factory):
    candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
    poi = _fvg_poi()
    poi.score = 9.0  # caller already scored it
    result = ValidationPipeline().validate(
        poi,
        candles,
        _range_swings(candles, swing_factory),
        [_ssl_level(100.3)],
        displacement=_passing_displacement(candle_factory),
    )
    assert result.decision is ValidationDecision.PASS
    assert result.quality_score == pytest.approx(9.0)
    assert poi.score == pytest.approx(9.0)
