"""Trigger B — Leading Diagonal (5-wave initiation) (R1 §7 Trigger B).

LOCATION: price swept liquidity and a validated POI is active.

TRIGGER (R1 §7):
  1. A 5-wave IMPULSE structure forms OUT of the POI (new trend initiation)
     — deterministic V1 extraction in ``smc.triggers.wave_structure``;
  2. Fibonacci retracement from the Wave-1 origin to the Wave-5 extreme;
  3. Entry at the Fibonacci 50%–61.8% pullback zone (Wave-2 retracement of
     the completed impulse).

ENTRY: LIMIT at the 50% level of the retracement band (V1 — the first edge
the pullback reaches; the band and the deeper 61.8% edge are exposed in
``data``).  STOP: beyond the Wave-1 origin.
EXPIRY: TRIGGER_B_EXPIRY (30 bars) after Wave 5 completion (§24).

⚠️ Subjective (v5 flowchart): wave counting is approximated by the
deterministic V1 chain rules in ``wave_structure``; revisit against
research data in Phase 6.
"""

from __future__ import annotations

from smc.core.enums import Direction, TriggerType
from smc.triggers.base_trigger import Trigger, TriggerContext, TriggerSignal
from smc.triggers.trigger_expiry import signal_expired, window_bars_for
from smc.triggers.wave_structure import find_impulse

__all__ = ["LeadingDiagonalTrigger"]

# ---------------------------------------------------------------------------
# UNFROZEN — R1 §7 Trigger B / v5 flowchart: "Fibonacci 50%-61.8% retracement".
# Spec numbers cited from R1 (source of truth) but NOT transcribed into
# locked_constants.py, whose header restricts itself to LOCKED_DECISIONS.md
# Rev 5 values. Pending authorization before live use.
# ---------------------------------------------------------------------------
FIB_MIN = 0.50   # shallower retracement edge (50%)
FIB_MAX = 0.618  # deeper retracement edge (61.8%)


class LeadingDiagonalTrigger(Trigger):
    """§R1-B 5-wave initiation: limit in the 50–61.8% retracement zone."""

    type = TriggerType.B_LEADING_DIAGONAL
    name = "b_leading_diagonal"

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        bar = context.current_bar
        if bar < context.from_bar:
            return None
        zone = context.poi.zone
        is_long = zone.direction is Direction.LONG

        impulse = find_impulse(context.swings, zone.direction, bar)
        if impulse is None:
            return None
        if impulse.wave5_index < context.from_bar:
            return None  # impulse must post-date the POI arming
        if signal_expired(
            impulse.wave5_index, window_bars_for(TriggerType.B_LEADING_DIAGONAL), bar
        ):
            return None
        if impulse.height <= 0.0:
            return None

        if is_long:
            entry = impulse.wave5_level - FIB_MIN * impulse.height
            deep = impulse.wave5_level - FIB_MAX * impulse.height
            inside = deep <= context.candles[bar].close <= entry
            earlier = any(
                context.candles[k].close <= entry
                for k in range(impulse.wave5_index + 1, bar)
            )
        else:
            entry = impulse.wave5_level + FIB_MIN * impulse.height
            deep = impulse.wave5_level + FIB_MAX * impulse.height
            inside = entry <= context.candles[bar].close <= deep
            earlier = any(
                context.candles[k].close >= entry
                for k in range(impulse.wave5_index + 1, bar)
            )
        if not inside or earlier:
            return None  # first close INTO the band (or no pullback yet)

        return TriggerSignal(
            trigger=TriggerType.B_LEADING_DIAGONAL,
            direction=zone.direction,
            entry_price=entry,
            stop_reference=impulse.origin_level,
            completion_index=bar,
            expiry_bars=window_bars_for(TriggerType.B_LEADING_DIAGONAL),
            detail=(
                f"5-wave {zone.direction.value} impulse (bar {impulse.wave5_index}); "
                f"pullback into fib band {deep:.2f}-{entry:.2f}"
            ),
            data={
                "wave5_index": impulse.wave5_index,
                "origin_level": impulse.origin_level,
                "fib_band": (deep, entry),
            },
        )
