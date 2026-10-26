"""Phase 4 — Trigger B: Leading Diagonal (5-wave initiation) (R1 §7).

Fixture: 5-wave UP impulse out of the POI (extremes at idx 4/8/12/16/20/24,
origin 100.0 → wave-5 106.0, height 6.0), then a pullback that first closes
into the 50–61.8% band [102.292, 103.0] at idx 28.
"""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_b_leading_diagonal import LeadingDiagonalTrigger

TF = Timeframe.M5

_ORIGIN = 100.0
_WAVE5 = 106.0
# Retracement anchors AFTER the wave-5 high: closes stay above the 50% band
# until idx 28, whose close (102.8) first enters [wave5-0.618*6, wave5-0.5*6].
_ANCHORS = [
    (4, 100.2), (8, 102.2), (12, 100.8), (16, 104.2), (20, 101.8), (24, 106.2),
    (25, 105.4), (26, 104.6), (27, 103.6), (28, 102.8),
]


def _rows():
    rows: list[tuple] = []
    for index in range(29):
        # piecewise-linear close path through the anchors
        current, nxt = None, None
        for j, (idx, price) in enumerate(_ANCHORS):
            if idx <= index:
                current = (idx, price)
            else:
                nxt = (idx, price)
                break
        if current is None:
            price = _ANCHORS[0][1]  # flat before the first retracement anchor
        elif nxt is None or current[0] == nxt[0]:
            price = current[1]
        else:
            t = (index - current[0]) / (nxt[0] - current[0])
            price = current[1] + (nxt[1] - current[1]) * t
        rows.append((price, price + 0.25, price - 0.25, price))
    return rows


def _swings(candles, swing_factory):
    return [
        swing_factory(candles, 4, False, level=_ORIGIN),
        swing_factory(candles, 8, True, level=102.0),
        swing_factory(candles, 12, False, level=100.8),
        swing_factory(candles, 16, True, level=104.0),
        swing_factory(candles, 20, False, level=101.8),
        swing_factory(candles, 24, True, level=_WAVE5),
    ]


def _ctx(candles, swings, bar=28, from_bar=4):
    poi = POI(
        zone=Zone(top=100.5, bottom=99.2, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M1],
    )
    return TriggerContext(poi=poi, candles=candles, swings=swings, bar_index=bar, from_bar=from_bar)


def test_bullish_pullback_into_fib_band(candle_factory, swing_factory):
    candles = candle_factory(_rows(), timeframe=TF)
    signal = LeadingDiagonalTrigger().evaluate(_ctx(candles, _swings(candles, swing_factory)))
    assert signal is not None
    assert signal.trigger is TriggerType.B_LEADING_DIAGONAL
    assert signal.direction is Direction.LONG
    assert signal.entry_price == 103.0  # 50% retracement level (first band edge)
    assert signal.stop_reference == _ORIGIN  # below the Wave-1 origin
    assert signal.completion_index == 28
    assert signal.expiry_bars == 30
    assert signal.data["wave5_index"] == 24


def test_no_signal_before_pullback_reaches_band(candle_factory, swing_factory):
    candles = candle_factory(_rows(), timeframe=TF)
    ctx = _ctx(candles, _swings(candles, swing_factory), bar=27)  # close 103.6 > 103
    assert LeadingDiagonalTrigger().evaluate(ctx) is None


def test_no_signal_when_pullback_pierces_through_band(candle_factory, swing_factory):
    rows = _rows()
    rows[28] = (102.0, 102.2, 101.8, 102.0)  # close below the 61.8% deep edge
    candles = candle_factory(rows, timeframe=TF)
    ctx = _ctx(candles, _swings(candles, swing_factory))
    assert LeadingDiagonalTrigger().evaluate(ctx) is None


def test_no_signal_without_five_wave_impulse(candle_factory, swing_factory):
    candles = candle_factory(_rows(), timeframe=TF)
    swings = _swings(candles, swing_factory)[:-2]  # only 4 extremes remain
    ctx = _ctx(candles, swings)
    assert LeadingDiagonalTrigger().evaluate(ctx) is None
