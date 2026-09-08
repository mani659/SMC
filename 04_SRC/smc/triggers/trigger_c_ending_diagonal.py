"""Trigger C — Ending Diagonal Wave-5 Throw-Under/Over (R1 §7 Trigger C).

LOCATION: price swept liquidity and reached a validated POI at the END of a
trend (the 5-wave diagonal travels INTO the zone with the old trend).
Model 8's PREFERRED entry trigger at M1 (§15 ✓★).

TRIGGER (R1 §7):
  1. A contracting/expanding 5-wave diagonal forms into the POI zone
     (deterministic V1 extraction in ``smc.triggers.wave_structure``);
  2. Wave 5 pierces the boundary trendline — Throw-Under into a demand
     zone (buy) / Throw-Over into a supply zone (sell);
  3. Entry at the Wave 5 boundary trendline sweep — V1: when price CLOSES
     back inside the boundary after the throw (the reversal commitment).

ENTRY: LIMIT at the boundary trendline sweep level.
STOP: just beyond the Wave 5 extreme wick (the terminal extreme).
EXPIRY: sweep candle + TRIGGER_C_EXPIRY_EXTRA (3 bars, §24).

⚠️ Most subjective (v5 flowchart): manual review recommended; the V1 chain
rules in ``wave_structure`` are documented approximations to revisit in
Phase 6.
"""

from __future__ import annotations

from smc.core.enums import Direction, TriggerType
from smc.triggers.base_trigger import (
    Trigger,
    TriggerContext,
    TriggerSignal,
    atr_band_half_width,
)
from smc.triggers.trigger_expiry import signal_expired, window_bars_for
from smc.triggers.wave_structure import find_ending_diagonal

__all__ = ["EndingDiagonalTrigger"]


class EndingDiagonalTrigger(Trigger):
    """§R1-C ending diagonal: limit at the boundary sweep after Wave 5 throw."""

    type = TriggerType.C_ENDING_DIAGONAL
    name = "c_ending_diagonal"

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        bar = context.current_bar
        if bar < context.from_bar:
            return None
        zone = context.poi.zone
        is_long = zone.direction is Direction.LONG
        # The diagonal travels WITH the old trend INTO the zone: down into a
        # demand zone, up into a supply zone (opposite the trade direction).
        diagonal_direction = Direction.SHORT if is_long else Direction.LONG

        diagonal = find_ending_diagonal(context.swings, diagonal_direction, bar)
        if diagonal is None:
            return None
        if diagonal.terminal_index < context.from_bar:
            return None
        if signal_expired(
            diagonal.terminal_index,
            window_bars_for(TriggerType.C_ENDING_DIAGONAL),
            bar,
        ):
            return None

        # V1 zone-context check: the terminal extreme must reach the POI
        # zone (within the 0.5×ATR band, reuse of the frozen §13 multiplier).
        band = atr_band_half_width(context.candles, bar)
        if not (
            zone.bottom - band
            <= diagonal.terminal_level
            <= zone.top + band
        ):
            return None

        boundary = diagonal.boundary_touch_level
        close = context.candles[bar].close
        if is_long:
            # Demand zone: Throw-Under pierced the lower boundary; buy on the
            # first close BACK ABOVE it.
            reclaimed = close > boundary
            earlier = any(
                context.candles[k].close > boundary
                for k in range(diagonal.terminal_index + 1, bar)
            )
        else:
            # Supply zone: Throw-Over pierced the upper boundary; sell on the
            # first close BACK BELOW it.
            reclaimed = close < boundary
            earlier = any(
                context.candles[k].close < boundary
                for k in range(diagonal.terminal_index + 1, bar)
            )
        if not reclaimed or earlier:
            return None

        return TriggerSignal(
            trigger=TriggerType.C_ENDING_DIAGONAL,
            direction=zone.direction,
            entry_price=boundary,
            stop_reference=diagonal.terminal_level,
            completion_index=bar,
            expiry_bars=window_bars_for(TriggerType.C_ENDING_DIAGONAL),
            detail=(
                f"ending diagonal throw at bar {diagonal.terminal_index}; "
                f"close reclaimed boundary {boundary:.2f}"
            ),
            data={
                "terminal_index": diagonal.terminal_index,
                "converging": diagonal.converging,
                "boundary": boundary,
            },
        )
