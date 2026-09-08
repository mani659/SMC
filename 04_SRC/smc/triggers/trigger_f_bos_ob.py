"""Trigger F — BOS + OB Continuation (R1 §7 Trigger F, LOCKED §24).

LOCATION: price is in an established trend (confirmed BOS) in the POI's
direction.

TRIGGER (R1 §7):
  1. BOS confirms trend continuation (body close beyond the prior swing in
     the POI direction);
  2. An unmitigated Order Block exists at the origin of the BOS impulse —
     V1: the nearest candle BEFORE the BOS candle whose body opposes the
     trend (R1 §3.1 OB = last opposing candle before the impulse), zone =
     its full wick range;
  3. Price retraces to the OB zone (first touch).

ENTRY: LIMIT at the OB PROXIMAL edge (the edge the retracement reaches
first — zone top when approaching a demand OB from above, zone bottom when
approaching a supply OB from below; R1 allows the proximal edge or the 50%
midpoint — V1 picks the proximal edge).
STOP: beyond the OB DISTAL edge.
EXPIRY: first touch only (TRIGGER_F_EXPIRY = 1) — a signal fires at the
first retracement bar that reaches the OB and cannot be re-armed.
"""

from __future__ import annotations

from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.core.swing import Swing
from smc.triggers.base_trigger import Trigger, TriggerContext, TriggerSignal
from smc.triggers.trigger_expiry import window_bars_for

__all__ = ["BosObContinuationTrigger"]


class BosObContinuationTrigger(Trigger):
    """§R1-F trend continuation: limit at the OB proximal edge on first touch."""

    type = TriggerType.F_BOS_OB
    name = "f_bos_ob"

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        bar = context.current_bar
        if bar < context.from_bar:
            return None
        zone = context.poi.zone
        is_long = zone.direction is Direction.LONG

        bos_index = _first_bos(context, bar, is_long)
        if bos_index is None:
            return None
        ob = _origin_ob(context, bos_index, is_long)
        if ob is None:
            return None
        top = max(ob.high, ob.low)
        bottom = min(ob.high, ob.low)
        if top <= bottom:
            return None

        # Retracement: first bar strictly after the BOS whose range reaches
        # the OB proximal edge — it must be THIS bar (first-touch semantics).
        touched: int | None = None
        for index in range(bos_index + 1, bar + 1):
            candle = context.candles[index]
            if (candle.low <= top) if is_long else (candle.high >= bottom):
                touched = index
                break
        if touched != bar:
            return None

        if is_long:
            entry, stop = top, bottom
        else:
            entry, stop = bottom, top
        return TriggerSignal(
            trigger=TriggerType.F_BOS_OB,
            direction=zone.direction,
            entry_price=entry,
            stop_reference=stop,
            completion_index=bar,
            expiry_bars=window_bars_for(TriggerType.F_BOS_OB),
            detail=f"BOS at bar {bos_index}; first touch of origin OB at bar {bar}",
            data={"bos_index": bos_index, "ob_index": _ob_index(context, bos_index, is_long)},
        )


def _first_bos(context: TriggerContext, bar: int, is_long: bool) -> int | None:
    """The FIRST BOS bar in ``[from_bar, bar]`` closing beyond the prior swing.

    The prior swing is the most recent §19-valid structural swing of the
    broken polarity BEFORE the candidate bar (a swing high for LONG).
    Returns the EARLIEST qualifying bar — the actual breakout — so the OB
    origin and the retracement scan stay anchored to one event. (Router
    scans chronologically; later continuation bars re-evaluating the same
    OB produce no new first-touch signal.)
    """
    for candidate in range(context.from_bar + 1, bar + 1):
        swing = _last_valid_swing(context.swings, is_high=is_long, before=candidate)
        if swing is None:
            continue
        close = context.candles[candidate].close
        if (close > swing.level) if is_long else (close < swing.level):
            return candidate
    return None


def _origin_ob(
    context: TriggerContext, bos_index: int, is_long: bool
) -> Candle | None:
    """Nearest opposing-bodied candle before the BOS bar (V1 OB definition)."""
    index = _ob_index(context, bos_index, is_long)
    if index is None:
        return None
    return context.candles[index]


def _ob_index(context: TriggerContext, bos_index: int, is_long: bool) -> int | None:
    for index in range(bos_index - 1, context.from_bar - 1, -1):
        candle = context.candles[index]
        opposing = candle.close < candle.open if is_long else candle.close > candle.open
        if opposing:
            return index
    return None


def _last_valid_swing(
    swings: list[Swing], is_high: bool, before: int
) -> Swing | None:
    """Most recent §19-valid swing of one polarity strictly before ``before``."""
    candidates = [
        s for s in swings if s.is_high == is_high and s.is_valid and s.candle_index < before
    ]
    return max(candidates, key=lambda s: s.candle_index, default=None)
