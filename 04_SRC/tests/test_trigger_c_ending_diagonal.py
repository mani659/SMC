"""Phase 4 — Trigger C: Ending Diagonal Wave-5 Throw-Under (R1 §7).

Fixture: contracting-style 5-wave DOWN diagonal into a demand (LONG) POI
zone [97.0, 100.5]. Extremes: w1 low 102.0 (6), w2 high 103.0 (10), w3 low
100.5 (14), w4 high 101.6 (18), w5 low 98.6 (22) — wave 5 throws UNDER the
lower boundary line through (6, 102.0)/(14, 100.5), whose value at bar 22 is
99.0.

§24 amendment C1: the validity clock starts when the terminal is OBSERVABLE
(``terminal + N(confirm_tf)``), not at the terminal candle. On the M5 fixture
(N=3) the first legal bar is 25; on H1 (N=5) it is 27. Bars after the terminal
close back under the boundary until the reclaim bar under test, so each case
exercises the FIRST reclaim at a chosen age.
"""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_c_ending_diagonal import EndingDiagonalTrigger

TF = Timeframe.M5
TF_H1 = Timeframe.H1

_ANCHORS = [
    (0, 103.5), (6, 102.0), (10, 103.0), (14, 100.5), (18, 101.6), (22, 98.6),
]
_BOUNDARY_AT_W5 = 99.0  # lower boundary value at bar 22 (throw-under level)
_TERMINAL = 22
_UNDER = 98.4  # close strictly below the boundary (no reclaim yet)


def _rows(reclaim_at: int, reclaim_close: float = 99.6):
    """Bars 0..``reclaim_at``; the first close back above 99.0 is ``reclaim_at``."""
    rows: list[tuple] = []
    for index in range(reclaim_at + 1):
        if index > _TERMINAL:
            close = reclaim_close if index == reclaim_at else _UNDER
            rows.append((close - 0.2, close + 0.2, close - 0.4, close))
            continue
        current, nxt = None, None
        for idx, price in _ANCHORS:
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
    return rows


def _swings(candles, swing_factory):
    return [
        swing_factory(candles, 6, False, level=102.0),   # w1 low
        swing_factory(candles, 10, True, level=103.0),   # w2 high
        swing_factory(candles, 14, False, level=100.5),  # w3 low
        swing_factory(candles, 18, True, level=101.6),   # w4 high
        swing_factory(candles, 22, False, level=98.6),   # w5 low (throw-under)
    ]


def _ctx(candles, swings, frame=TF, zone_top=100.5, zone_bottom=97.0):
    poi = POI(
        zone=Zone(top=zone_top, bottom=zone_bottom, direction=Direction.LONG,
                  timeframe=frame),
        models=[ModelType.M8],
    )
    return TriggerContext(
        poi=poi,
        candles=candles,
        swings=swings,
        bar_index=len(candles) - 1,   # evaluate on the last closed bar
        from_bar=6,
    )


def _evaluate(reclaim_at, frame=TF, candle_factory=None, swing_factory=None):
    candles = candle_factory(_rows(reclaim_at), timeframe=frame)
    return EndingDiagonalTrigger().evaluate(
        _ctx(candles, _swings(candles, swing_factory), frame=frame)
    )


# --------------------------------------------------------------------------- #
# M5 fixture (N = 3): first legal bar = 22 + 3 = 25
# --------------------------------------------------------------------------- #
def test_throw_under_reclaim_fires(candle_factory, swing_factory):
    signal = _evaluate(25, TF, candle_factory, swing_factory)
    assert signal is not None
    assert signal.trigger is TriggerType.C_ENDING_DIAGONAL
    assert signal.direction is Direction.LONG
    assert signal.entry_price == _BOUNDARY_AT_W5  # limit at the boundary sweep
    assert signal.stop_reference == 98.6  # beyond the Wave-5 wick
    assert signal.completion_index == 25  # first legal bar (terminal 22 + N 3)
    assert signal.expiry_bars == 3
    assert signal.data["known_at"] == 25
    assert signal.data["terminal_index"] == 22


def test_no_signal_while_still_under_boundary(candle_factory, swing_factory):
    # Bars after the terminal (23, 24) still close under the boundary.
    candles = candle_factory(_rows(24), timeframe=TF)
    assert EndingDiagonalTrigger().evaluate(
        _ctx(candles, _swings(candles, swing_factory))
    ) is None


def test_no_signal_when_diagonal_away_from_zone(candle_factory, swing_factory):
    candles = candle_factory(_rows(25), timeframe=TF)
    ctx = _ctx(
        candles, _swings(candles, swing_factory),
        zone_top=110.0, zone_bottom=109.0,
    )
    assert EndingDiagonalTrigger().evaluate(ctx) is None


def test_no_signal_without_terminal_throw(candle_factory, swing_factory):
    candles = candle_factory(_rows(25), timeframe=TF)
    swings = [
        swing_factory(candles, 6, False, level=102.0),
        swing_factory(candles, 10, True, level=103.0),
        swing_factory(candles, 14, False, level=100.5),
        swing_factory(candles, 18, True, level=101.6),
        swing_factory(candles, 22, False, level=99.6),  # ABOVE the boundary 99.0
    ]
    assert EndingDiagonalTrigger().evaluate(_ctx(candles, swings)) is None


# --------------------------------------------------------------------------- #
# H1 fixture (N = 5): legal ages 5..8, i.e. bars 27..30 for terminal 22
# --------------------------------------------------------------------------- #
def test_h1_fires_at_first_observable_bar(candle_factory, swing_factory):
    signal = _evaluate(27, TF_H1, candle_factory, swing_factory)
    assert signal is not None
    assert signal.completion_index == 27
    assert signal.data["known_at"] == 27  # 22 + N_BAR_HTF (5)


def test_h1_rejects_age_4(candle_factory, swing_factory):
    assert _evaluate(26, TF_H1, candle_factory, swing_factory) is None


def test_h1_fires_at_last_legal_age_8(candle_factory, swing_factory):
    signal = _evaluate(30, TF_H1, candle_factory, swing_factory)
    assert signal is not None
    assert signal.completion_index == 30
    assert signal.data["known_at"] == 27


def test_h1_rejects_age_9(candle_factory, swing_factory):
    assert _evaluate(31, TF_H1, candle_factory, swing_factory) is None


def test_n_source_is_swing_timeframe_not_execution_timeframe(
    candle_factory, swing_factory
):
    """H1 series at age 3: legal only if N were mis-read as 3 (the M5 default).

    ``TriggerContext.execution_timeframe`` defaults to M5 and the router never
    populates it, so reading it would admit this bar. N must come from the
    swings' own timeframe (H1 → 5), which rejects it.
    """
    candles = candle_factory(_rows(25), timeframe=TF_H1)
    ctx = _ctx(candles, _swings(candles, swing_factory), frame=TF_H1)
    assert ctx.execution_timeframe is TF  # the trap this test pins
    assert EndingDiagonalTrigger().evaluate(ctx) is None
