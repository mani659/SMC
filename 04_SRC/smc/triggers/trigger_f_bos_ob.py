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

ENTRY (FR-3.1): LIMIT anchored to the routed POI zone. The OB proximal
edge remains the REFERENCE price, but the resting limit is
``zone_anchored_entry(zone, reference)`` — an on-zone OB keeps the
proximal-edge entry bit-exactly (pre-FR-3.1 behavior); an OB outside the
routed thesis zone re-anchors to the nearest zone edge (the PROXIMAL edge
for the reachable shapes: LONG with the OB above the zone -> top; SHORT
with the OB below the zone -> bottom) so the HTF thesis still routes onto
its zone instead of being silently rejected off-zone.
STOP: beyond the OB DISTAL edge (0.3×ATR buffer) when the entry is the
proximal edge (unchanged); for a RE-ANCHORED entry the stop reference is
the zone's own DISTAL edge (same 0.3×ATR buffer) so the stop always sits
on the protective side of the entry — a stop left on a detached OB would
land on the wrong side of the re-anchored limit.
EXPIRY: first touch only (TRIGGER_F_EXPIRY = 1) — a signal fires at the
first retracement bar that reaches the OB and cannot be re-armed.
"""

from __future__ import annotations

from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.core.swing import Swing
from smc.triggers.base_trigger import (
    Trigger, TriggerContext, TriggerSignal, context_atr, entry_within_zone,
    structural_sl, zone_anchored_entry,
)
from smc.triggers.trigger_expiry import window_bars_for

__all__ = ["BosObContinuationTrigger"]


class BosObContinuationTrigger(Trigger):
    """§R1-F trend continuation: first-touch OB signal, limit anchored to
    the routed POI zone (FR-3.1 — proximal-edge reference, direction-aware
    anchor; on-zone OBs keep the classic proximal-edge entry bit-exactly)."""

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

        # FR-3.1: the resting limit is anchored INTO the routed POI zone at
        # the DIRECTION-PROXIMAL edge (LONG -> zone high, SHORT -> zone
        # low). The OB proximal edge stays the reference (on-zone OBs are
        # bit-identical to the pre-FR-3.1 rule); a detached OB re-anchors
        # to the proximal edge and the stop reference moves to the zone's
        # distal edge so the stop remains on the protective side.
        atr = context_atr(context, bar)
        if is_long:
            reference = top
            entry = zone_anchored_entry(zone.direction, zone.bottom, zone.top, reference)
            stop_reference = bottom if entry == top else zone.bottom
        else:
            reference = bottom
            entry = zone_anchored_entry(zone.direction, zone.bottom, zone.top, reference)
            stop_reference = top if entry == bottom else zone.top
        stop = structural_sl(stop_reference, zone.direction, atr)
        # Degenerate-geometry guard: the stop must sit strictly on the
        # protective side of the entry. A flat zone with unknowable ATR
        # would yield stop == entry — a zero SL distance, which the sizing
        # path (risk_lots) rejects with an exception; such a signal is not
        # a trade. (With ATR present the 0.3×ATR buffer keeps the distance
        # positive even for a flat zone.)
        if zone.direction is Direction.LONG and not stop < entry:
            return None
        if zone.direction is not Direction.LONG and not stop > entry:
            return None
        # FR-3: the routed entry must belong to its POI thesis zone
        # (±0.5×ATR locked tolerance). The gate stays the last line of
        # defense — the anchor makes standard fixtures pass pre-gate;
        # it does not widen what the gate accepts.
        if not entry_within_zone(entry, zone, atr):
            return None
        re_anchored = entry != reference
        anchor = "ob_proximal" if not re_anchored else "zone_edge_reanchor"
        return TriggerSignal(
            trigger=TriggerType.F_BOS_OB,
            direction=zone.direction,
            entry_price=entry,
            stop_reference=stop,
            completion_index=bar,
            expiry_bars=window_bars_for(TriggerType.F_BOS_OB),
            detail=(
                f"BOS at bar {bos_index}; first touch of origin OB at bar {bar}; "
                f"entry anchor {anchor}"
            ),
            data={"bos_index": bos_index,
                  "ob_index": _ob_index(context, bos_index, is_long),
                  "entry_anchor": anchor},
        )


def _first_bos(context: TriggerContext, bar: int, is_long: bool) -> int | None:
    """The FIRST BOS bar in ``[from_bar, bar]`` closing beyond the prior swing.

    The prior swing is the most recent §19-valid structural swing of the
    broken polarity BEFORE the candidate bar (a swing high for LONG).
    Returns the EARLIEST qualifying bar — the actual breakout — so the OB
    origin and the retracement scan stay anchored to one event. (Router
    scans chronologically; later continuation bars re-evaluating the same
    OB produce no new first-touch signal.)

    Phase C perf: with the context's swing index supplied, each per-bar
    "last valid swing" scan is a bisect lookup over the SAME selection.
    """
    swing_index = getattr(context.hints, "swing_index", None)
    original = swing_index.original if swing_index is not None else None
    for candidate in range(context.from_bar + 1, bar + 1):
        if original is not None:
            swing = original.last_valid(is_long, candidate)
        else:
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
