"""Phase 4 — Trigger F: BOS + OB continuation (R1 §7, §24 first-touch)."""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_f_bos_ob import BosObContinuationTrigger

TF = Timeframe.M5

# Uptrend: valid swing high 101.0 (idx6) → bearish OB candle idx9
# (zone [100.5, 101.6]) → BOS idx10 (close 101.9 > 101.0, low stays above the
# OB top so it does NOT touch) → pullback idx11 (low 101.62 > 101.6) → first
# touch of the OB top at idx12 (low 100.4).
_ROWS = [
    (99.0, 99.6, 98.9, 99.5),      # 0
    (99.5, 100.1, 99.4, 100.0),    # 1
    (100.0, 100.6, 99.9, 100.5),   # 2
    (100.5, 101.0, 100.4, 100.9),  # 3
    (100.9, 101.4, 100.8, 101.3),  # 4
    (101.3, 101.6, 101.2, 101.5),  # 5
    (101.5, 101.8, 101.4, 101.7),  # 6 swing-high area (level 101.0 supplied)
    (101.7, 101.9, 101.3, 101.4),  # 7 pullback candle A
    (101.4, 101.7, 100.9, 101.1),  # 8 pullback candle B
    (101.1, 101.6, 100.5, 100.7),  # 9 OB (bearish) — zone [100.5, 101.6]
    (101.8, 102.0, 101.66, 101.9),  # 10 BOS: close 101.9 > 101.0, low above OB
    (101.9, 101.95, 101.62, 101.7),  # 11 pullback (no touch yet)
    (101.6, 101.7, 100.4, 101.0),   # 12 FIRST touch of the OB top (101.6)
]


def _ctx(candles, swings, direction=Direction.LONG, bar=12, from_bar=8):
    zone = Zone(top=103.0, bottom=102.2, direction=direction, timeframe=TF)
    poi = POI(zone=zone, models=[ModelType.M5])
    return TriggerContext(poi=poi, candles=candles, swings=swings, bar_index=bar, from_bar=from_bar)


def test_bullish_first_touch_of_origin_ob(candle_factory, swing_factory):
    candles = candle_factory(_ROWS, timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    signal = BosObContinuationTrigger().evaluate(_ctx(candles, swings))
    assert signal is not None
    assert signal.trigger is TriggerType.F_BOS_OB
    assert signal.direction is Direction.LONG
    assert signal.entry_price == 101.6  # OB proximal edge (top)
    assert signal.stop_reference == 100.5  # OB distal edge
    assert signal.completion_index == 12
    assert signal.expiry_bars == 1


def test_no_signal_before_first_touch(candle_factory, swing_factory):
    candles = candle_factory(_ROWS, timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    ctx = _ctx(candles, swings, bar=11)  # pullback has not reached the OB yet
    assert BosObContinuationTrigger().evaluate(ctx) is None


def test_no_signal_without_bos(candle_factory, swing_factory):
    rows = list(_ROWS)
    rows[10] = (101.8, 101.9, 100.8, 100.9)
    rows[11] = (101.0, 101.3, 100.6, 100.9)
    rows[12] = (101.2, 101.5, 100.4, 100.9)  # no close ever exceeds 101.0
    candles = candle_factory(rows, timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    assert BosObContinuationTrigger().evaluate(_ctx(candles, swings)) is None


def test_no_signal_without_origin_ob(candle_factory, swing_factory):
    rows = list(_ROWS)
    rows[8] = (100.9, 101.7, 100.8, 101.2)  # bullish → not an OB
    rows[9] = (100.9, 101.9, 100.8, 101.8)  # bullish → not an OB
    candles = candle_factory(rows, timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    assert BosObContinuationTrigger().evaluate(_ctx(candles, swings)) is None
