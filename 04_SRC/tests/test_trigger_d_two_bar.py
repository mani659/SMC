"""Phase 4 — Trigger D: Two-Bar Reversal (§10/§24, R1 §7)."""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_d_two_bar import TwoBarReversalTrigger

TF = Timeframe.M5
# POI: bearish (supply) zone. Bearish engulfing at idx2 (vol 300 < prior 500)
# → the entry bar immediately following is idx3.
_ROWS = [
    (119.8, 120.2, 119.6, 120.0),         # 0 filler
    (120.0, 120.6, 119.9, 120.4, 500.0),  # 1 engulfed (bullish)
    (120.9, 121.3, 119.9, 120.0, 300.0),  # 2 engulfing (bearish) at zone
    (120.0, 120.3, 119.7, 119.9, 400.0),  # 3 entry bar (immediately following)
]


def _ctx(candles, zone_direction=Direction.SHORT, bar=3, from_bar=2):
    poi = POI(
        zone=Zone(top=121.0, bottom=120.0, direction=zone_direction, timeframe=TF),
        models=[ModelType.M6],
    )
    return TriggerContext(poi=poi, candles=candles, swings=[], bar_index=bar, from_bar=from_bar)


def test_bearish_engulfing_fires_on_next_bar(candle_factory):
    candles = candle_factory(_ROWS, timeframe=TF)
    signal = TwoBarReversalTrigger().evaluate(_ctx(candles))
    assert signal is not None
    assert signal.trigger is TriggerType.D_TWO_BAR_REVERSAL
    assert signal.direction is Direction.SHORT
    assert signal.completion_index == 3
    assert signal.expiry_bars == 1
    # Limit at 50% of the engulfing body (120.9+120.0)/2 — never a market order.
    assert signal.entry_price == 120.45
    assert signal.stop_reference == 121.3  # beyond the pattern extreme


def test_no_signal_without_volume_confirmation(candle_factory):
    rows = list(_ROWS)
    rows[2] = (120.9, 121.3, 119.9, 120.0, 600.0)  # volume NOT lower
    candles = candle_factory(rows, timeframe=TF)
    assert TwoBarReversalTrigger().evaluate(_ctx(candles)) is None


def test_no_signal_on_direction_mismatch(candle_factory):
    candles = candle_factory(_ROWS, timeframe=TF)
    ctx = _ctx(candles, zone_direction=Direction.LONG)  # bullish POI, bearish engulfing
    assert TwoBarReversalTrigger().evaluate(ctx) is None


def test_no_signal_outside_poi_zone(candle_factory):
    rows = [
        (119.8, 120.2, 119.6, 120.0),
        (120.0, 120.6, 119.9, 120.4, 500.0),
        (122.9, 123.3, 121.9, 122.0, 300.0),  # engulfing far above the zone
        (122.0, 122.3, 121.7, 121.9),
    ]
    candles = candle_factory(rows, timeframe=TF)
    assert TwoBarReversalTrigger().evaluate(_ctx(candles)) is None


def test_bullish_engulfing_fires_at_long_poi(candle_factory):
    rows = [
        (120.0, 120.4, 119.8, 120.2),
        (120.2, 120.6, 119.9, 120.1, 500.0),  # engulfed (bearish)
        (119.5, 120.6, 119.2, 120.5, 300.0),  # engulfing (bullish) at zone
        (120.4, 120.8, 120.1, 120.6),
    ]
    candles = candle_factory(rows, timeframe=TF)
    poi_ctx = _ctx(candles, zone_direction=Direction.LONG)
    signal = TwoBarReversalTrigger().evaluate(poi_ctx)
    assert signal is not None
    assert signal.direction is Direction.LONG
    assert signal.entry_price == (119.5 + 120.5) / 2
    assert signal.stop_reference == 119.2
