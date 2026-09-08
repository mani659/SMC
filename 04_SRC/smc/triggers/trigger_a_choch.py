"""Trigger A — M1/M5 CHOCH Reversal (LOCKED §9/§12, R1 §7 Trigger A).

LOCATION: price has reached a validated POI (FRESH). On the execution TF a
local swing forms and a CHOCH completes in the POI's direction.

TRIGGER (R1 §7):
  On M1/M5: local swing high/low within the POI zone → CHOCH confirmed
  (body close beyond the last swing in the POI direction) → entry on retest
  of the CHOCH level.
  Entry: LIMIT at the broken CHOCH level (§9 — broken structural level, not
  the origin OB).  Stop: beyond the liquidity sweep extreme (the Head).
  Expiry: TRIGGER_A_EXPIRY (20 M5 bars, §24).

The detector reuses the Phase 2 ``classify_choch_at`` (Rules 1/2/3, §17) so
no CHOCH logic is re-implemented. V1 location simplification: direction
match + CHOCH break AFTER the POI arm bar is required (the local-swing /
zone containment refinement is documented — see CHANGELOG notes).
"""

from __future__ import annotations

from smc.core.enums import Direction, TriggerType
from smc.poi.choch_classifier import classify_choch_at
from smc.triggers.base_trigger import Trigger, TriggerContext, TriggerSignal
from smc.triggers.trigger_expiry import window_bars_for

__all__ = ["ChochReversalTrigger"]


class ChochReversalTrigger(Trigger):
    """§9/§12 CHOCH reversal: limit at the broken level, SL beyond the sweep."""

    type = TriggerType.A_CHOCH
    name = "a_choch"

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        bar = context.current_bar
        if bar <= context.from_bar:
            return None
        choch = classify_choch_at(context.candles, context.swings, bar)
        if choch is None:
            return None
        if choch.direction is not context.poi.zone.direction:
            return None
        # The break (and its liquidity sweep) must post-date the POI arming.
        if choch.break_index < context.from_bar:
            return None
        if choch.sweep_index is not None and choch.sweep_index < context.from_bar:
            return None

        stop = _sweep_extreme(context, choch)
        return TriggerSignal(
            trigger=TriggerType.A_CHOCH,
            direction=choch.direction,
            entry_price=choch.broken_level,
            stop_reference=stop,
            completion_index=choch.break_index,
            expiry_bars=window_bars_for(TriggerType.A_CHOCH),
            detail=(
                f"CHOCH Rule {choch.rule.value} at bar {choch.break_index}; "
                f"entry retest of broken level {choch.broken_level:.2f}"
            ),
            data={
                "rule": choch.rule.value,
                "sweep_index": choch.sweep_index,
                "broken_level": choch.broken_level,
            },
        )


def _sweep_extreme(context: TriggerContext, choch) -> float:
    """Stop reference: the sweep candle's extreme beyond the head (§9).

    LONG (bullish break after an SSL sweep) stops below the sweep candle's
    low; SHORT stops above the sweep candle's high. V1: the structural
    extreme itself — a broker stops-level/spread buffer is applied at order
    build time (execution seam, Phase 4/5).
    """
    index = choch.sweep_index if choch.sweep_index is not None else choch.break_index
    candle = context.candles[index]
    if choch.direction is Direction.LONG:
        return candle.low
    return candle.high
