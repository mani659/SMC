"""Trigger E — Double Top/Bottom + RSI Divergence (R1 §7 Trigger E).

LOCATION: price has reached a validated POI.

TRIGGER (R1 §7):
  1. A structural DOUBLE TOP (bearish) / DOUBLE BOTTOM (bullish) forms;
  2. The second peak/trough occurs at the POI zone;
  3. RSI(14) diverges: price makes an equal/higher high while RSI makes a
     lower high (bearish), or an equal/lower low while RSI makes a higher
     low (bullish). RSI is the Wilder RSI from ``smc.utils.rsi`` (matches
     MT5 ``iRSI``); period 14 is an indicator parameter (R1 citation).

ENTRY (V1, R1 offers either): LIMIT at the NECKLINE once the neckline
break is confirmed by a body close beyond it.
STOP: beyond the pattern extreme (the second peak/trough).
EXPIRY: TRIGGER_E_EXPIRY (15 bars) after pattern completion.

Bearish (double top) is evaluated directly; the bullish double bottom
mirrors price, swings and the POI zone into the inverted space, runs the
same code path, and mirrors the resulting levels back (the
``choch_classifier`` pattern).
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.core.swing import Swing
from smc.core.zone import Zone
from smc.triggers.base_trigger import (
    Trigger,
    TriggerContext,
    TriggerSignal,
    atr_band_half_width,
)
from smc.triggers.trigger_expiry import window_bars_for
from smc.utils.pips import within_pip_tolerance
from smc.utils.rsi import rsi_series

__all__ = ["RsiDivergenceTrigger"]


@dataclass(frozen=True, slots=True)
class _DoublePattern:
    """Working-space double-top fields (bearish shape in that space)."""

    entry: float     # neckline level
    stop: float      # second peak level (beyond the pattern extreme)
    completion: int  # neckline-break bar
    peak1_index: int
    peak2_index: int
    rsi1: float
    rsi2: float


class RsiDivergenceTrigger(Trigger):
    """§R1-E double top/bottom + RSI(14) divergence: limit at the neckline."""

    type = TriggerType.E_RSI_DIVERGENCE
    name = "e_rsi_divergence"

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        bar = context.current_bar
        if bar < context.from_bar:
            return None
        if context.poi.zone.direction is Direction.SHORT:
            pattern = _detect(
                context,
                context.candles,
                context.swings,
                bar,
                context.poi.zone,
            )
            if pattern is None:
                return None
            return TriggerSignal(
                trigger=TriggerType.E_RSI_DIVERGENCE,
                direction=Direction.SHORT,
                entry_price=pattern.entry,
                stop_reference=pattern.stop,
                completion_index=pattern.completion,
                expiry_bars=window_bars_for(TriggerType.E_RSI_DIVERGENCE),
                detail=(
                    f"double top with bearish RSI divergence "
                    f"({pattern.rsi1:.1f} -> {pattern.rsi2:.1f})"
                ),
                data={
                    "peak1_index": pattern.peak1_index,
                    "peak2_index": pattern.peak2_index,
                },
            )
        # Bullish: run the same detection in the mirrored space.
        zone = context.poi.zone
        inverted_zone = Zone(
            top=-zone.bottom, bottom=-zone.top, direction=zone.direction
        )
        pattern = _detect(
            context,
            _invert_candles(context.candles),
            _invert_swings(context.swings),
            bar,
            inverted_zone,
        )
        if pattern is None:
            return None
        return TriggerSignal(
            trigger=TriggerType.E_RSI_DIVERGENCE,
            direction=Direction.LONG,
            entry_price=-pattern.entry,
            stop_reference=-pattern.stop,
            completion_index=pattern.completion,
            expiry_bars=window_bars_for(TriggerType.E_RSI_DIVERGENCE),
            detail=(
                f"double bottom with bullish RSI divergence "
                f"({100.0 - pattern.rsi2:.1f} -> {100.0 - pattern.rsi1:.1f})"
            ),
            data={
                "peak1_index": pattern.peak1_index,
                "peak2_index": pattern.peak2_index,
            },
        )


def _detect(
    context: TriggerContext,
    candles: list[Candle],
    swings: list[Swing],
    bar: int,
    zone: Zone,
) -> _DoublePattern | None:
    """Double-top detection in one price space (bearish shape)."""
    highs = [s for s in swings if s.is_high and s.candle_index < bar]
    highs.sort(key=lambda s: s.candle_index)
    if len(highs) < 2:
        return None
    h1, h2 = highs[-2], highs[-1]
    # 1) Equal-or-higher second high within the §2 EQH tolerance.
    if h2.level < h1.level:
        return None
    if not within_pip_tolerance(h1.level, h2.level):
        return None
    # The pattern must belong to the current POI episode.
    if h2.candle_index < context.from_bar:
        return None
    # 2) Second peak at the POI zone (within the V1 0.5×ATR band).
    band = atr_band_half_width(candles, bar)
    if not (zone.bottom - band <= h2.level <= zone.top + band):
        return None
    # 3) RSI divergence: lower RSI at the equal/higher second high.
    rsi = rsi_series(candles)
    r1 = rsi[h1.candle_index] if h1.candle_index < len(rsi) else None
    r2 = rsi[h2.candle_index] if h2.candle_index < len(rsi) else None
    if r1 is None or r2 is None or not r2 < r1:
        return None
    # Neckline = lowest low between the peaks; break = first body close below.
    neckline = min(c.low for c in candles[h1.candle_index + 1 : h2.candle_index + 1])
    if any(candles[i].close < neckline for i in range(h2.candle_index + 1, bar)):
        return None  # the neckline break already happened
    if not candles[bar].close < neckline:
        return None
    return _DoublePattern(
        entry=neckline,
        stop=h2.level,
        completion=bar,
        peak1_index=h1.candle_index,
        peak2_index=h2.candle_index,
        rsi1=r1,
        rsi2=r2,
    )


def _invert_candles(candles: list[Candle]) -> list[Candle]:
    """Price-inverted copy (bull <-> bear geometry) for bullish symmetry."""
    inverted: list[Candle] = []
    for candle in candles:
        inverted.append(
            Candle(
                timestamp=candle.timestamp,
                open=-candle.open,
                high=-candle.low,
                low=-candle.high,
                close=-candle.close,
                volume=candle.volume,
                timeframe=candle.timeframe,
            )
        )
    return inverted


def _invert_swings(swings: list[Swing]) -> list[Swing]:
    inverted: list[Swing] = []
    for swing in swings:
        inverted.append(
            Swing(
                is_high=not swing.is_high,
                level=-swing.level,
                candle_index=swing.candle_index,
                base_candle=swing.base_candle,
                timeframe=swing.timeframe,
                is_valid=swing.is_valid,
                confirmed_index=swing.confirmed_index,
            )
        )
    return inverted
