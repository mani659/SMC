"""Pure rule functions for DUMB FLOWCHART V1 (sweep → confirm → entry).

DUMB IMPLEMENTATION — DIAGNOSTIC — NOT EDGE.

Every function here is PURE over its arguments (no clock, no state, no MT5)
and implements R2 / R3 / R5 / R6 of the accepted design lock verbatim.
The execution loop (`smc.dumb.runner`) composes these with the locked
conservative fill semantics of `smc.backtest.fill_model`.
"""

from __future__ import annotations

from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.zone import Zone
from smc.dumb.constants import DUMB_SL_BUFFER_ATR, DUMB_TP_R_MULTIPLE

__all__ = [
    "is_sweep",
    "is_confirm",
    "zone_level_side",
    "is_expired",
    "compute_sl_tp",
]


def is_sweep(bar: Candle, zone: Zone) -> bool:
    """R2 — one bar wick beyond the zone extreme + close back inside.

    LONG (demand zone): the bar's LOW pierces below ``zone.bottom`` and its
    BODY closes back above it. SHORT (supply zone): the bar's HIGH pierces
    above ``zone.top`` and its BODY closes back below it. A bar that closes
    beyond the extreme is NOT a sweep — it is the genuine-breakout case the
    locked sweep discipline (`smc.detection.sweep_detector`) explicitly
    rejects.
    """
    if zone.direction is Direction.LONG:
        return bar.low < zone.bottom and bar.close > zone.bottom
    return bar.high > zone.top and bar.close < zone.top


def is_confirm(bar: Candle, zone: Zone) -> bool:
    """R3 — the RECLAIM: close strictly through the zone midpoint.

    LONG: ``close > (bottom + top) / 2``; SHORT: ``close < mid``. The sweep
    bar itself is never eligible (handled by the runner's bar ordering);
    eligibility beyond that is the runner's job (expiry, inside-zone check).
    """
    mid = (zone.bottom + zone.top) / 2.0
    if zone.direction is Direction.LONG:
        return bar.close > mid
    return bar.close < mid


def zone_level_side(zone: Zone) -> Direction:
    """The trade direction implied by the zone (R1: demand → LONG / supply → SHORT)."""
    return zone.direction


def is_expired(setup_sweep_idx: int, bar_idx: int) -> bool:
    """R3 — expiry: no confirm by bar ``sweep_idx + 12`` drops the setup.

    The confirm window is INCLUSIVE of bar ``sweep_idx + 12``; a bar at
    ``sweep_idx + 12 + 1`` or later means the setup expired at the close of
    ``sweep_idx + 12`` and the zone re-arms on the next sweep.
    """
    return bar_idx > setup_sweep_idx + 12


def compute_sl_tp(
    direction: Direction,
    entry_price: float,
    sweep_extreme: float,
    atr: float,
) -> tuple[float, float]:
    """R5 + R6 — SL beyond the sweep extreme; TP fixed `DUMB_TP_R_MULTIPLE` × 1R.

    LONG: ``SL = sweep_low - DUMB_SL_BUFFER_ATR × atr``; ``1R = entry − SL``;
    ``TP = entry + DUMB_TP_R_MULTIPLE × 1R``. SHORT is mirrored. Returns
    ``(sl, tp)``.
    """
    buffer = DUMB_SL_BUFFER_ATR * atr
    if direction is Direction.LONG:
        sl = sweep_extreme - buffer
        risk = entry_price - sl
    else:
        sl = sweep_extreme + buffer
        risk = sl - entry_price
    if risk <= 0:
        raise ValueError(f"non-positive 1R ({risk}) — sweep extreme on the wrong side of entry")
    tp = entry_price + DUMB_TP_R_MULTIPLE * risk * (1 if direction is Direction.LONG else -1)
    return sl, tp
