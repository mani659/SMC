"""FR-2 structural SL/TP routing — R4/R5 implementation tests.

Covers: resolve_take_profit policy (structural-else-4×ATR), structural_sl
math by hand, F buffered placement on a warmed-up fixture, bridge TP
wiring incl. original_sl, backtest fill-model TP hits with SL-first
preserved, and the original_sl/BE contract. No thresholds invented here —
the FR-2 interim numbers live in base_trigger and are imported, never
redefined.
"""

from datetime import datetime, timezone

from smc.backtest.fill_model import CloseKind, evaluate_position_bar
from smc.backtest.pipeline_bridge import candidate_from_route, resolve_take_profit
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.triggers.base_trigger import (
    FR2_SL_BUFFER_ATR,
    FR2_TP_ATR_MULTIPLE,
    TriggerContext,
    structural_sl,
)
from smc.triggers.trigger_f_bos_ob import BosObContinuationTrigger
from smc.triggers.trigger_router import TriggerRoute
from smc.triggers.base_trigger import TriggerSignal
from smc.utils.atr import latest_atr

TF = Timeframe.M5


def test_interim_constants_have_expected_values():
    # Pinned so any future formal §28 lock diff is explicit, not silent.
    assert FR2_SL_BUFFER_ATR == 0.3
    assert FR2_TP_ATR_MULTIPLE == 4.0


def test_resolve_tp_fallback_both_directions():
    assert resolve_take_profit(100.0, Direction.LONG, 0.5) == 102.0
    assert resolve_take_profit(100.0, Direction.SHORT, 0.5) == 98.0


def test_resolve_tp_structural_used_when_valid():
    assert resolve_take_profit(100.0, Direction.LONG, 0.5,
                               structural_target=106.0) == 106.0
    assert resolve_take_profit(100.0, Direction.SHORT, 0.5,
                               structural_target=94.0) == 94.0


def test_resolve_tp_invalid_structural_falls_back():
    # Wrong-sided, non-finite, and unusable inputs all fall back (never None
    # while ATR is knowable; never an invented fill level).
    assert resolve_take_profit(100.0, Direction.LONG, 0.5,
                               structural_target=95.0) == 102.0
    assert resolve_take_profit(100.0, Direction.SHORT, 0.5,
                               structural_target=105.0) == 98.0
    assert resolve_take_profit(100.0, Direction.LONG, 0.5,
                               structural_target=float("inf")) == 102.0
    assert resolve_take_profit(100.0, Direction.LONG, 0.5,
                               structural_target="nonsense") == 102.0


def test_resolve_tp_without_atr_is_none():
    assert resolve_take_profit(100.0, Direction.LONG, None) is None
    assert resolve_take_profit(100.0, Direction.SHORT, 0.0) is None
    assert resolve_take_profit(100.0, Direction.LONG, -1.0) is None


def test_structural_sl_hand_values_and_guards():
    assert structural_sl(100.0, Direction.LONG, 2.0) == 99.4
    assert structural_sl(100.0, Direction.SHORT, 2.0) == 100.6
    assert structural_sl(100.0, Direction.LONG, None) == 100.0
    assert structural_sl(100.0, Direction.SHORT, 0.0) == 100.0
    assert structural_sl(100.0, Direction.LONG, -3.0) == 100.0
    assert structural_sl(100.0, Direction.LONG, float("nan")) == 100.0


_CALM = [(99.0, 99.2, 98.8, 99.0)] * 15
_F_ROWS = [
    (99.0, 99.6, 98.9, 99.5),
    (99.5, 100.1, 99.4, 100.0),
    (100.0, 100.6, 99.9, 100.5),
    (100.5, 101.0, 100.4, 100.9),
    (100.9, 101.4, 100.8, 101.3),
    (101.3, 101.6, 101.2, 101.5),
    (101.5, 101.8, 101.4, 101.7),
    (101.7, 101.9, 101.3, 101.4),
    (101.4, 101.7, 100.9, 101.1),
    (101.1, 101.6, 100.5, 100.7),
    (101.8, 102.0, 101.66, 101.9),
    (101.9, 101.95, 101.62, 101.7),
    (101.6, 101.7, 100.4, 101.0),
]


def _warming_ctx(candle_factory, swing_factory):
    candles = candle_factory(_CALM + _F_ROWS, timeframe=TF)
    swings = [swing_factory(candles, 21, True, level=101.0)]
    # FR-3: thesis zone sits ON the trigger OB ([100.5, 101.6]) so the
    # proximal-edge entry satisfies entry↔zone containment.
    zone = Zone(top=101.6, bottom=100.5, direction=Direction.LONG, timeframe=TF)
    poi = POI(zone=zone, models=[ModelType.M5])
    return candles, TriggerContext(poi=poi, candles=candles, swings=swings,
                                   bar_index=27, from_bar=23)


def test_f_placement_sl_carries_buffer_when_atr_known(candle_factory,
                                                      swing_factory):
    candles, ctx = _warming_ctx(candle_factory, swing_factory)
    signal = BosObContinuationTrigger().evaluate(ctx)
    assert signal is not None
    assert signal.entry_price == 101.6  # proximal edge unchanged
    expected = structural_sl(100.5, Direction.LONG, latest_atr(candles[:28]))
    assert signal.stop_reference == expected
    assert signal.stop_reference < 100.5  # buffer actually applied


def test_bridge_tp_fallback_and_original_sl(candle_factory, swing_factory):
    candles, ctx = _warming_ctx(candle_factory, swing_factory)
    signal = BosObContinuationTrigger().evaluate(ctx)
    assert signal is not None
    route = TriggerRoute(poi=ctx.poi, bar=27, signal=signal)
    atr = latest_atr(candles[:28])
    cand = candidate_from_route(route, atr=atr)
    assert cand.tp_price == signal.entry_price + 4.0 * atr
    assert cand.original_sl == signal.stop_reference  # placement SL, buffered
    assert cand.sl_price == signal.stop_reference
    # No ATR → same None path as the old always-None behavior (documented).
    assert candidate_from_route(route).tp_price is None


def test_fill_model_hits_tp_and_keeps_sl_first():
    def bar(high, low):
        return Candle(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                      open=100.0, high=high, low=low, close=100.5,
                      timeframe=TF)
    hit = evaluate_position_bar(Direction.LONG, 99.0, 101.0,
                                bar(high=102.0, low=100.5))
    assert hit.closed and hit.kind == CloseKind.TAKE_PROFIT
    assert hit.price == 101.0 and hit.win is True
    both = evaluate_position_bar(Direction.LONG, 99.0, 101.0,
                                 bar(high=102.0, low=98.0))
    assert both.closed and both.kind == CloseKind.STOP_LOSS  # SL-first kept
    short_hit = evaluate_position_bar(Direction.SHORT, 101.0, 99.0,
                                      bar(high=100.5, low=98.0))
    assert short_hit.closed and short_hit.kind == CloseKind.TAKE_PROFIT


def test_trigger_signal_contract_untouched():
    # FR-2 adds no fields to TriggerSignal: TP/ATR ride bridge kwargs.
    import dataclasses
    names = {f.name for f in dataclasses.fields(TriggerSignal)}
    assert "tp_price" not in names and "atr" not in names
