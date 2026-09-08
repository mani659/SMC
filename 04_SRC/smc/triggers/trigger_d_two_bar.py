"""Trigger D — Two-Bar Reversal (LOCKED §10/§24, R1 §7 Trigger D).

LOCATION: price has reached a validated POI.

TRIGGER (R1 §7, frozen):
  1. Two-candle reversal pattern (ENGULFING) forms within the POI zone;
  2. Volume of the engulfing candle < volume of the preceding candle
     (frozen confirmation — no volume data ⇒ no signal in V1);
  3. Entry on the bar immediately following the engulfing.

ENTRY (FROZEN §10): LIMIT order at 50% of the engulfing body — NEVER a
market order (``TRIGGER_D_ENGULFING_FILL``).
STOP: beyond the extreme of the two-bar pattern.
EXPIRY: bar immediately following only (TRIGGER_D_EXPIRY = 1).

Direction: bullish engulfing at a bullish POI → buy; bearish at a bearish
POI → sell.
"""

from __future__ import annotations

from smc.config.locked_constants import TRIGGER_D_ENGULFING_FILL
from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.triggers.base_trigger import Trigger, TriggerContext, TriggerSignal
from smc.triggers.trigger_expiry import window_bars_for

__all__ = ["TwoBarReversalTrigger"]


class TwoBarReversalTrigger(Trigger):
    """§10 two-bar engulfing: limit at 50% of the engulfing body."""

    type = TriggerType.D_TWO_BAR_REVERSAL
    name = "d_two_bar"

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        bar = context.current_bar
        # Entry bar = the bar immediately FOLLOWING the engulfing candle.
        engulf = bar - 1
        prior = bar - 2
        if prior < 0 or engulf < context.from_bar:
            return None
        candles = context.candles
        engulfer = candles[engulf]
        engulfed = candles[prior]
        direction = _engulfing_direction(engulfer, engulfed)
        if direction is None:
            return None
        if direction is not context.poi.zone.direction:
            return None
        if not _overlaps_zone(engulfer, context.poi.zone.top, context.poi.zone.bottom):
            return None
        # Frozen confirmation: engulfing candle's volume < preceding candle.
        if not (engulfer.volume < engulfed.volume):
            return None

        mid = (engulfer.open + engulfer.close) / 2.0
        entry = mid  # 50% of the engulfing body (frozen §10)
        stop = _pattern_extreme(engulfer, engulfed, direction)
        return TriggerSignal(
            trigger=TriggerType.D_TWO_BAR_REVERSAL,
            direction=direction,
            entry_price=entry,
            stop_reference=stop,
            completion_index=bar,  # fires on the bar immediately following
            expiry_bars=window_bars_for(TriggerType.D_TWO_BAR_REVERSAL),
            detail=(
                f"{direction.value} engulfing at bar {engulf} "
                f"(volume {engulfer.volume:.0f} < {engulfed.volume:.0f})"
            ),
            data={"engulfing_index": engulf, "body_fill": TRIGGER_D_ENGULFING_FILL},
        )


def _engulfing_direction(engulfer: Candle, engulfed: Candle) -> Direction | None:
    """Direction when ``engulfer`` fully engulfs the prior body, else None."""
    if engulfer.close < engulfer.open:  # bearish engulfing
        if engulfer.open >= engulfed.close and engulfer.close <= engulfed.open:
            return Direction.SHORT
        return None
    # bullish engulfing
    if engulfer.open <= engulfed.close and engulfer.close >= engulfed.open:
        return Direction.LONG
    return None


def _overlaps_zone(candle: Candle, zone_top: float, zone_bottom: float) -> bool:
    """True when the candle's range intersects the POI zone (pattern in zone)."""
    return candle.low <= zone_top and candle.high >= zone_bottom


def _pattern_extreme(
    engulfer: Candle, engulfed: Candle, direction: Direction
) -> float:
    """Stop beyond the two-bar pattern extreme."""
    if direction is Direction.LONG:
        return min(engulfer.low, engulfed.low)
    return max(engulfer.high, engulfed.high)
