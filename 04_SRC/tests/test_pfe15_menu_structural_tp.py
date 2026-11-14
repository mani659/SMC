"""PFE-1.5 — menu path must carry the §21b structural TP like the seek path.

The audit (``06_RESEARCH/PFE1_PRODUCT_VS_INTENDED_AUDIT.md`` P0-2) found the
menu bridge calling ``candidate_from_route`` without ``structural_target``, so
every menu confirmation took the 4×ATR fallback while the seek adapter fed the
first-swing selector. These tests pin the parity fix:

1. a menu winner whose confirmation series carries a §19-valid swing beyond the
   entry gets ``tp_source == "structural_swing"`` and that swing as its TP;
2. with no qualifying swing the frozen 4×ATR fallback is used and tagged
   ``atr_fallback`` — the fallback itself is unchanged;
3. the selector is the SAME helper the seek adapter imports
   (``pipeline_bridge.structural_tp_target``), never a second swing rule.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.orchestration import product_menu_mtf
from smc.orchestration.product_menu_mtf import ProductMenuEngine
from smc.triggers.base_trigger import FR2_TP_ATR_MULTIPLE, Trigger, TriggerContext, TriggerSignal
from smc.triggers.trigger_router import TriggerRouter

BASE = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
H4_CLOSE = BASE + timedelta(hours=4)
ZONE_LOW = 2490.0
ZONE_HIGH = 2500.0


class StubTrigger(Trigger):
    type = TriggerType.A_CHOCH

    def __init__(self) -> None:
        self.fire = False

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        if not self.fire:
            return None
        candle = context.candles[context.bar_index]
        return TriggerSignal(
            trigger=TriggerType.A_CHOCH,
            direction=Direction.LONG,
            entry_price=candle.close + 0.5,
            stop_reference=candle.low - 1.0,
            completion_index=context.bar_index,
            expiry_bars=10,
            detail="stub-fire",
            data={},
        )


def _bar(tf: Timeframe, offset_minutes: float, *, low=2485.0, high=2505.0,
         close=2500.0, open_=2496.0) -> Candle:
    return Candle(
        timestamp=BASE + timedelta(minutes=offset_minutes),
        open=open_, high=high, low=low, close=close, timeframe=tf,
    )


def _sweep(tf: Timeframe) -> Candle:
    return _bar(tf, 0.0, low=2485.0, high=2498.0, close=2492.0)


def _confirm(tf: Timeframe, offset_minutes: float) -> Candle:
    return _bar(tf, offset_minutes, low=2491.0, high=2499.0, close=2497.0)


def _poi(tf: Timeframe = Timeframe.H4) -> POI:
    zone = Zone(top=ZONE_HIGH, bottom=ZONE_LOW, direction=Direction.LONG,
                timeframe=tf)
    return POI(zone=zone, models=[ModelType.M8], score=3.0,
               state=POIState.CREATED, m8_kind="demand_supply", id="poi-tp-1")


def _swing(level: float, confirmed_index: int = 0):
    return SimpleNamespace(level=level, is_valid=True,
                           confirmed_index=confirmed_index, candle_index=0)


CONFIRM_BARS = 20          # enough history for the Wilder ATR prefix


def _menu_then_confirm() -> tuple[ProductMenuEngine, StubTrigger]:
    engine = ProductMenuEngine(symbol="TEST")
    stub = StubTrigger()
    engine._router = TriggerRouter(triggers=[stub])
    assert engine.register_armed(_poi(Timeframe.H4), Timeframe.H4) is True
    engine.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]},
                            as_of=H4_CLOSE)
    # warm-up confirm bars, no trigger: the one-shot window stays open
    bars = [_confirm(Timeframe.M15, 300 + 15 * i) for i in range(CONFIRM_BARS)]
    engine.on_execution_bar(
        {Timeframe.M15: bars},
        as_of=BASE + timedelta(hours=5, minutes=15 * CONFIRM_BARS),
    )
    return engine, stub


def _win(engine: ProductMenuEngine, stub: StubTrigger):
    stub.fire = True                     # completion at the warm-up end
    winners = engine.on_execution_bar(
        {Timeframe.M15: [_confirm(Timeframe.M15, 300 + 15 * CONFIRM_BARS)]},
        as_of=BASE + timedelta(hours=5, minutes=15 * (CONFIRM_BARS + 1)),
    )
    assert len(winners) == 1
    return winners[0].candidate


def test_menu_winner_uses_structural_swing_when_available(monkeypatch):
    engine, stub = _menu_then_confirm()
    monkeypatch.setattr(ProductMenuEngine, "_swings_for",
                        lambda self, ctf: [_swing(2505.0, confirmed_index=0)])
    candidate = _win(engine, stub)
    assert candidate.tp_source == "structural_swing"
    assert candidate.tp_price == 2505.0
    assert candidate.entry_price < candidate.tp_price


def test_menu_winner_falls_back_to_four_atr_without_a_swing(monkeypatch):
    engine, stub = _menu_then_confirm()
    monkeypatch.setattr(ProductMenuEngine, "_swings_for",
                        lambda self, ctf: [])
    candidate = _win(engine, stub)
    assert candidate.tp_source == "atr_fallback"
    # frozen fallback unchanged: entry ± FR2_TP_ATR_MULTIPLE × ATR
    atr = candidate.tp_price - candidate.entry_price
    assert atr > 0
    from smc.utils.atr import latest_atr

    series = engine._confirm[Timeframe.M15]
    expected = FR2_TP_ATR_MULTIPLE * float(latest_atr(series, engine.atr_period))
    assert abs(atr - expected) < 1e-6


def test_menu_bridge_reuses_the_seek_selector():
    """No second swing rule: the bridge calls the shared helper."""
    import inspect

    source = inspect.getsource(product_menu_mtf.ProductMenuEngine._candidate)
    assert "structural_tp_target(" in source
    assert "poi_give_up_bars()" in source
