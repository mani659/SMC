"""C3 — in-between entry validity (master card §3.4).

An LTF trigger completion is a VALID entry only when the trigger fired AND
the completion bar's price sits inside the routed POI zone body. This module
is the single shared geometry for that rule: no tolerance band, no median
gate, no new number — plain inclusive containment over the zone's existing
``bottom``/``top`` bounds.

Consumers (C3): :func:`smc.backtest.pipeline_bridge.candidate_from_route`
is the one choke point every placement candidate passes through, so the
adapter and the product menu inherit the gate from a single call.
"""

from __future__ import annotations

__all__ = ["NOT_IN_BETWEEN", "price_inside_zone", "trigger_in_between"]

#: Machine-readable reject token (log/audit — never an eligibility input).
NOT_IN_BETWEEN = "not_in_between"


def price_inside_zone(price: float, zone_low: float, zone_high: float) -> bool:
    """True when ``price`` is inside ``[zone_low, zone_high]`` (inclusive).

    Fails closed: unparseable / NaN inputs and inverted bounds
    (``zone_low > zone_high``) return False — unlocatable geometry is never
    a valid entry.
    """
    try:
        value = float(price)
        low = float(zone_low)
        high = float(zone_high)
    except (TypeError, ValueError):
        return False
    if not high >= low:  # inverted or NaN bounds -> unlocatable
        return False
    return low <= value <= high


def trigger_in_between(
    *,
    zone_low: float,
    zone_high: float,
    completion_price: float,
) -> bool:
    """Master card §3.4 in-between gate: completion inside the POI body.

    ``completion_price`` is the completion bar's CLOSE (the frozen C3
    definition — see ``candidate_from_route``); it is compared against the
    zone's inclusive bounds. Purely geometric; no ATR tolerance, no median.
    """
    return price_inside_zone(completion_price, zone_low, zone_high)
