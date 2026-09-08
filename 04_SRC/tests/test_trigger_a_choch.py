"""Phase 4 — Trigger A: M1/M5 CHOCH Reversal (§9/§12, R1 §7)."""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_a_choch import ChochReversalTrigger

TF = Timeframe.M5

# Bullish CHOCH fixture (same geometry as the Phase 2 Rule-1 bullish test):
# valid high 101.5 (idx3), valid low 99.5 (idx8), SSL sweep (idx9),
# body close above 101.5 at idx13.
_BULLISH_ROWS = [
    (100.0, 100.4, 99.8, 100.2),    # 0
    (100.2, 100.7, 100.0, 100.5),   # 1
    (100.5, 101.1, 100.4, 100.9),   # 2
    (100.9, 101.5, 100.7, 101.3),   # 3 last valid high 101.5
    (101.3, 101.6, 101.0, 101.2),   # 4
    (101.1, 101.4, 100.8, 100.9),   # 5
    (100.9, 101.1, 100.5, 100.6),   # 6
    (100.6, 100.8, 100.1, 100.2),   # 7
    (100.2, 100.4, 99.5, 99.9),     # 8 last valid low 99.5
    (99.9, 100.1, 99.4, 99.8),      # 9 sweep of low (wick below, body back)
    (99.8, 100.0, 99.6, 99.7),      # 10
    (99.7, 100.0, 99.5, 99.9),      # 11
    (100.0, 100.4, 99.8, 100.2),    # 12
    (100.3, 102.0, 100.1, 101.8),   # 13 body close above 101.5
]


def _ctx(candles, swings, zone_direction=Direction.LONG, bar=13, from_bar=8):
    poi = POI(
        zone=Zone(top=100.0, bottom=98.0, direction=zone_direction, timeframe=TF),
        models=[ModelType.M1],
    )
    return TriggerContext(
        poi=poi, candles=candles, swings=swings, bar_index=bar, from_bar=from_bar
    )


def _swings(candles, swing_factory):
    return [
        swing_factory(candles, 3, True, level=101.5),
        swing_factory(candles, 8, False, level=99.5),
    ]


def test_bullish_choch_fires_at_long_poi(candle_factory, swing_factory):
    candles = candle_factory(_BULLISH_ROWS, timeframe=TF)
    signal = ChochReversalTrigger().evaluate(
        _ctx(candles, _swings(candles, swing_factory))
    )
    assert signal is not None
    assert signal.trigger is TriggerType.A_CHOCH
    assert signal.direction is Direction.LONG
    assert signal.entry_price == 101.5  # broken structural level (§9 retest)
    assert signal.completion_index == 13
    assert signal.expiry_bars == 20
    assert signal.stop_reference == 99.4  # sweep candle low (beyond the head)


def test_no_signal_when_sweep_predates_poi_arming(candle_factory, swing_factory):
    candles = candle_factory(_BULLISH_ROWS, timeframe=TF)
    ctx = _ctx(candles, _swings(candles, swing_factory), from_bar=12)
    assert ChochReversalTrigger().evaluate(ctx) is None


def test_no_signal_on_direction_mismatch(candle_factory, swing_factory):
    candles = candle_factory(_BULLISH_ROWS, timeframe=TF)
    ctx = _ctx(candles, _swings(candles, swing_factory), zone_direction=Direction.SHORT)
    assert ChochReversalTrigger().evaluate(ctx) is None


def test_no_signal_before_the_break_bar(candle_factory, swing_factory):
    candles = candle_factory(_BULLISH_ROWS, timeframe=TF)
    ctx = _ctx(candles, _swings(candles, swing_factory), bar=12)
    assert ChochReversalTrigger().evaluate(ctx) is None
