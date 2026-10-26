"""Phase 3 — Pillar 1 (Zone Refinement): unmitigated OB/FVG within ±0.5× ATR (§13).

All fixtures use calm 0.4-range bars (ATR = 0.4) with a single bullish FVG
zone [100.0, 100.2] built from three impulse candles.
"""

from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, POIState
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.validation.pillar import PillarStatus, ValidationContext
from smc.validation.pillar_1_zone_refinement import ZoneRefinementPillar

TF = Timeframe.M5
CALM = [(99.5, 99.7, 99.3, 99.6)]  # range 0.4 -> ATR(14) = 0.4


def _rows(with_fvg: bool = True, mitigate: bool = False):
    rows = CALM * 15
    if with_fvg:
        rows += [
            (99.9, 100.0, 99.7, 99.9),      # 15 c1: first FVG candle (high 100.0)
            (100.0, 100.1, 99.6, 100.0),    # 16 c2: middle candle (no side gaps)
            (100.15, 100.35, 100.2, 100.3),  # 17 c3: third.low 100.2 > c1.high -> FVG [100.0,100.2]
        ]
    if mitigate:
        rows.append((100.1, 100.2, 99.7, 99.7))  # close below 100.0 -> FVG mitigated
    return rows


def _poi(top: float, bottom: float) -> POI:
    return POI(
        zone=Zone(top=top, bottom=bottom, direction=Direction.LONG, timeframe=TF),
        models=[],
        state=POIState.CREATED,
    )


def _run(candles, poi):
    return ZoneRefinementPillar().run(
        ValidationContext(poi=poi, candles=candles, swings=[], liquidity_levels=[])
    )


def test_fvg_overlap_is_unmitigated_refinement(candle_factory):
    candles = candle_factory(_rows(with_fvg=True), timeframe=TF)
    result = _run(candles, _poi(100.2, 100.0))
    assert result.status is PillarStatus.PASS
    assert "fvg" in result.data["refinements"]


def test_ob_counts_as_refinement(candle_factory):
    # POI zone = the OB candle (idx 14, full range [99.3, 99.7]) that precedes
    # the FVG's first candle; the FVG zone itself sits outside the band.
    candles = candle_factory(_rows(with_fvg=True), timeframe=TF)
    result = _run(candles, _poi(99.7, 99.3))
    assert result.status is PillarStatus.PASS
    assert result.data["refinements"] == ["ob"]


def test_naked_level_fails(candle_factory):
    # POI far above the FVG: no OB/FVG within ±0.5× ATR -> naked level.
    candles = candle_factory(_rows(with_fvg=True), timeframe=TF)
    result = _run(candles, _poi(104.2, 104.0))
    assert result.status is PillarStatus.FAIL
    assert result.data["refinements"] == []


def test_mitigated_fvg_does_not_refine(candle_factory):
    # The only overlapping FVG was closed through (close 99.7 < 100.0) after
    # it formed -> no UNMITIGATED element remains -> naked level.
    candles = candle_factory(_rows(with_fvg=True, mitigate=True), timeframe=TF)
    result = _run(candles, _poi(100.2, 100.0))
    assert result.status is PillarStatus.FAIL
    assert result.data["refinements"] == []


def test_unavailable_without_sufficient_data(candle_factory):
    # Two candles: not enough to detect FVGs.
    short = candle_factory(_rows(with_fvg=False)[:2], timeframe=TF)
    assert _run(short, _poi(100.2, 100.0)).status is PillarStatus.UNAVAILABLE
    # Five calm bars: FVGs possible but no ATR(14) history yet.
    no_atr = candle_factory(CALM * 5, timeframe=TF)
    assert _run(no_atr, _poi(100.2, 100.0)).status is PillarStatus.UNAVAILABLE
