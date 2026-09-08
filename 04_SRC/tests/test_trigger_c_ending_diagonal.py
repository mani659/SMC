"""Phase 4 — Trigger C: Ending Diagonal Wave-5 Throw-Under (R1 §7).

Fixture: contracting-style 5-wave DOWN diagonal into a demand (LONG) POI
zone [97.0, 100.5]. Extremes: w1 low 102.0 (6), w2 high 103.0 (10), w3 low
100.5 (14), w4 high 101.6 (18), w5 low 98.6 (22) — wave 5 throws UNDER the
lower boundary line through (6, 102.0)/(14, 100.5), whose value at bar 22 is
99.0. Bar 23 closes BACK ABOVE 99.0 → buy at the boundary sweep.
"""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_c_ending_diagonal import EndingDiagonalTrigger

TF = Timeframe.M5

_ANCHORS = [
    (0, 103.5), (6, 102.0), (10, 103.0), (14, 100.5), (18, 101.6), (22, 98.6),
]
_BOUNDARY_AT_W5 = 99.0  # lower boundary value at bar 22 (throw-under level)


def _rows(reclaim_close: float = 99.6):
    rows: list[tuple] = []
    for index in range(23):
        current, nxt = None, None
        for j, (idx, price) in enumerate(_ANCHORS):
            if idx <= index:
                current = (idx, price)
            else:
                nxt = (idx, price)
                break
        if nxt is None or current[0] == nxt[0]:
            price = current[1]
        else:
            t = (index - current[0]) / (nxt[0] - current[0])
            price = current[1] + (nxt[1] - current[1]) * t
        rows.append((price, price + 0.2, price - 0.25, price))
    # Bar 23: the reclaim candle after the wave-5 throw.
    rows.append((reclaim_close - 0.2, reclaim_close + 0.2, reclaim_close - 0.4, reclaim_close))
    return rows


def _swings(candles, swing_factory):
    return [
        swing_factory(candles, 6, False, level=102.0),   # w1 low
        swing_factory(candles, 10, True, level=103.0),   # w2 high
        swing_factory(candles, 14, False, level=100.5),  # w3 low
        swing_factory(candles, 18, True, level=101.6),   # w4 high
        swing_factory(candles, 22, False, level=98.6),   # w5 low (throw-under)
    ]


def _ctx(candles, swings, bar=23, from_bar=6):
    poi = POI(
        zone=Zone(top=100.5, bottom=97.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M8],
    )
    return TriggerContext(poi=poi, candles=candles, swings=swings, bar_index=bar, from_bar=from_bar)


def test_throw_under_reclaim_fires(candle_factory, swing_factory):
    candles = candle_factory(_rows(), timeframe=TF)
    signal = EndingDiagonalTrigger().evaluate(_ctx(candles, _swings(candles, swing_factory)))
    assert signal is not None
    assert signal.trigger is TriggerType.C_ENDING_DIAGONAL
    assert signal.direction is Direction.LONG
    assert signal.entry_price == _BOUNDARY_AT_W5  # limit at the boundary sweep
    assert signal.stop_reference == 98.6  # beyond the Wave-5 wick
    assert signal.completion_index == 23
    assert signal.expiry_bars == 3


def test_no_signal_while_still_under_boundary(candle_factory, swing_factory):
    candles = candle_factory(_rows(reclaim_close=98.6), timeframe=TF)  # no reclaim
    assert EndingDiagonalTrigger().evaluate(_ctx(candles, _swings(candles, swing_factory))) is None


def test_no_signal_when_diagonal_away_from_zone(candle_factory, swing_factory):
    candles = candle_factory(_rows(), timeframe=TF)
    poi = POI(
        zone=Zone(top=110.0, bottom=109.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M8],
    )
    ctx = TriggerContext(
        poi=poi, candles=candles, swings=_swings(candles, swing_factory),
        bar_index=23, from_bar=6,
    )
    assert EndingDiagonalTrigger().evaluate(ctx) is None


def test_no_signal_without_terminal_throw(candle_factory, swing_factory):
    candles = candle_factory(_rows(), timeframe=TF)
    swings = [
        swing_factory(candles, 6, False, level=102.0),
        swing_factory(candles, 10, True, level=103.0),
        swing_factory(candles, 14, False, level=100.5),
        swing_factory(candles, 18, True, level=101.6),
        swing_factory(candles, 22, False, level=99.6),  # ABOVE the boundary 99.0
    ]
    assert EndingDiagonalTrigger().evaluate(_ctx(candles, swings)) is None
