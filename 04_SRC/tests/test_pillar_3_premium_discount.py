"""Phase 3 — Pillar 3 (Premium/Discount): §6 dealing-range gate.

The dealing range [100, 110] is built from §19-valid swings. Pillar 3 is the
SOLE owner of the 45%/55% hard reject: LONG must be < 45% (discount), SHORT
must be > 55% (premium), 45–55% equilibrium = REJECT. No dealing range =
UNAVAILABLE (never a silent pass).
"""

from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, POIState
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.poi.deal_range import compute_dealing_range
from smc.validation.pillar import PillarStatus, ValidationContext
from smc.validation.pillar_3_premium_discount import PremiumDiscountPillar

TF = Timeframe.M5


def _ctx(swings, poi) -> ValidationContext:
    return ValidationContext(
        poi=poi,
        candles=[],
        swings=swings,
        liquidity_levels=[],
        dealing_range=compute_dealing_range(swings),
    )


def _poi(top: float, bottom: float, direction: Direction) -> POI:
    return POI(
        zone=Zone(top=top, bottom=bottom, direction=direction, timeframe=TF),
        models=[],
        state=POIState.CREATED,
    )


def _swings(candles, swing_factory):
    return [
        swing_factory(candles, 5, True, level=110.0),
        swing_factory(candles, 3, False, level=100.0),
    ]


def test_long_in_discount_passes(candle_factory, swing_factory):
    candles = candle_factory([(100, 100, 100, 100)] * 10, timeframe=TF)
    result = PremiumDiscountPillar().run(_ctx(_swings(candles, swing_factory), _poi(104.0, 102.0, Direction.LONG)))
    assert result.status is PillarStatus.PASS
    assert result.data["region"] == "discount"


def test_short_in_premium_passes(candle_factory, swing_factory):
    candles = candle_factory([(100, 100, 100, 100)] * 10, timeframe=TF)
    result = PremiumDiscountPillar().run(_ctx(_swings(candles, swing_factory), _poi(108.0, 106.0, Direction.SHORT)))
    assert result.status is PillarStatus.PASS
    assert result.data["region"] == "premium"


def test_long_in_premium_fails(candle_factory, swing_factory):
    candles = candle_factory([(100, 100, 100, 100)] * 10, timeframe=TF)
    result = PremiumDiscountPillar().run(_ctx(_swings(candles, swing_factory), _poi(108.0, 106.0, Direction.LONG)))
    assert result.status is PillarStatus.FAIL


def test_equilibrium_reject_band_fails_both_directions(candle_factory, swing_factory):
    candles = candle_factory([(100, 100, 100, 100)] * 10, timeframe=TF)
    eq = _poi(106.0, 104.0, Direction.LONG)  # midpoint 105 = 50% of the range
    for poi in (eq, _poi(106.0, 104.0, Direction.SHORT)):
        result = PremiumDiscountPillar().run(_ctx(_swings(candles, swing_factory), poi))
        assert result.status is PillarStatus.FAIL
        assert result.data["region"] == "equilibrium"


def test_no_dealing_range_is_unavailable(candle_factory):
    candles = candle_factory([(100, 100, 100, 100)] * 10, timeframe=TF)
    ctx = ValidationContext(
        poi=_poi(104.0, 102.0, Direction.LONG),
        candles=[],
        swings=[],
        liquidity_levels=[],
        dealing_range=None,  # compute_dealing_range([]) == None
    )
    result = PremiumDiscountPillar().run(ctx)
    assert result.status is PillarStatus.UNAVAILABLE
    assert "None" in result.detail or "no confirmed" in result.detail
