"""Phase 3 — Pillar 2 (Displacement): consumes Phase 1 DisplacementResult (§3).

The pillar never recomputes — the caller injects the result of
``check_displacement`` (reused from Phase 1) for the POI's own sweep/BOS.
"""

from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, POIState
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.detection.displacement_checker import check_displacement
from smc.validation.pillar import PillarStatus, ValidationContext
from smc.validation.pillar_2_displacement import DisplacementPillar

TF = Timeframe.M5
PRE = [(100.5, 101.5, 99.5, 100.5)] * 15  # constant range 2 -> ATR(14) = 2.0


def _poi() -> POI:
    return POI(
        zone=Zone(top=101.2, bottom=100.8, direction=Direction.LONG, timeframe=TF),
        models=[],
        state=POIState.CREATED,
    )


def _run(displacement) -> "PillarResult":
    pillar = DisplacementPillar()
    ctx = ValidationContext(
        poi=_poi(), candles=[], swings=[], liquidity_levels=[], displacement=displacement
    )
    return pillar.run(ctx)


def _bullish_pass_result(candle_factory):
    candles = candle_factory(
        PRE
        + [
            (99.8, 100.5, 98.2, 99.6),    # sweep
            (100.0, 102.5, 100.3, 100.8),  # impulse
            (101.0, 103.5, 102.0, 103.2),  # FVG trio + BOS close > 101.2
        ]
    )
    return check_displacement(candles, Direction.LONG, sweep_index=15, bos_level=101.2)


def test_passing_displacement(candle_factory):
    result = _run(_bullish_pass_result(candle_factory))
    assert result.status is PillarStatus.PASS
    assert result.data["bos"] and result.data["fvg"]
    assert result.data["is_preferred"]


def test_hard_fail_below_half_atr(candle_factory):
    candles = candle_factory(
        PRE
        + [
            (99.8, 100.5, 98.2, 99.0),   # sweep
            (99.0, 99.4, 98.9, 99.1),    # weak follow-through
            (99.1, 99.3, 99.0, 99.1),
        ]
    )
    displacement = check_displacement(
        candles, Direction.LONG, sweep_index=15, bos_level=101.2
    )
    result = _run(displacement)
    assert result.status is PillarStatus.FAIL
    assert "hard fail" in result.detail
    assert displacement.magnitude_atr < 0.5


def test_missing_bos_or_fvg_fails(candle_factory):
    # Strong close beyond the level but no directional FVG -> FAIL (not hard fail).
    candles = candle_factory(
        PRE
        + [
            (99.8, 100.5, 98.2, 99.6),    # sweep
            (99.9, 100.8, 99.8, 100.7),   # overlaps -> no gap
            (101.0, 103.0, 100.4, 102.8),  # BOS close, no FVG
        ]
    )
    displacement = check_displacement(
        candles, Direction.LONG, sweep_index=15, bos_level=101.2
    )
    assert displacement.bos and not displacement.fvg
    result = _run(displacement)
    assert result.status is PillarStatus.FAIL
    assert "FVG" in result.detail


def test_missing_result_is_unavailable():
    result = _run(None)
    assert result.status is PillarStatus.UNAVAILABLE
