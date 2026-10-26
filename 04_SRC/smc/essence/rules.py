"""Pure rule functions for the ESSENCE contract v1 slice.

ESSENCE V1 SLICE — NOT FULL COMPLEX REWRITE.

Every function is PURE over its arguments (no clock, no state, no MT5) and
implements the SIGNED contract stage rules:

* §2 sweep     — wick beyond the HTF level + close back inside; a close
                 beyond the level is a breakout (invalidation), never a
                 sweep. The level for essence is the HTF zone itself (the
                 mapping's zone-level transposition of the locked §2
                 discipline — the follow-up F6 zone-sweep verdict).
* §3 confirm   — signed set C, ending diagonal (the §15-preferred pattern),
                 read on M1: read-only port of the shipped Trigger C
                 semantics (`smc.triggers.wave_structure.find_ending_diagonal`
                 + the frozen §13 zone band + the first-reclaim-close rule)
                 over the essence M1 execution series. B and E are not in
                 the signed set and can never fire here (allow-list).
* §5 stop      — 2–5 pips beyond the M1 structure (the wave-5 terminal
                 wick); the slice places at the band floor (2.0 pips) and
                 validates the result inside the signed band.
* §6 target    — macro HTF target = the near edge of the nearest active
                 OPPOSITE-direction HTF zone strictly beyond the entry; a
                 trade whose target cannot reach 1:5 is blocked, never
                 downgraded.
"""

from __future__ import annotations

import math

from dataclasses import dataclass

from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.zone import Zone
from smc.essence.constants import (
    ESSENCE_ATR_PERIOD,
    ESSENCE_CONFIRM_KINDS,
    ESSENCE_CONFIRM_KIND_ED,
    ESSENCE_ED_TERMINAL_EXPIRY,
    ESSENCE_MIN_RR,
    ESSENCE_SL_MIN_PIPS,
    ESSENCE_ZONE_BAND_ATR,
)
from smc.triggers.trigger_expiry import signal_expired
from smc.triggers.wave_structure import find_ending_diagonal
from smc.utils.atr import atr_series
from smc.utils.pips import pips_to_price

__all__ = [
    "is_zone_sweep",
    "is_zone_violation",
    "confirm_kind_allowed",
    "EdCandidate",
    "find_ed_confirm",
    "essence_stop",
    "essence_target",
    "risk_reward",
    "rr_gate_ok",
    "zone_band_half_width",
    "m1_atr_series",
]


# ---------------------------------------------------------------------- #
# §2 — the level-level sweep (zone-level transposition of the locked rule)
# ---------------------------------------------------------------------- #
def is_zone_sweep(bar: Candle, zone: Zone) -> bool:
    """SIGNED §2 sweep at the HTF zone: wick pierces beyond the level
    extreme and the BODY closes back inside it.

    LONG (demand): the bar's LOW pierces below ``zone.bottom`` and its
    BODY closes back above it. SHORT (supply) is mirrored. A bar that
    *closes* beyond the extreme is NOT a sweep (breakout — never eligible),
    per the locked sweep discipline.
    """
    if zone.direction is Direction.LONG:
        return bar.low < zone.bottom and bar.close > zone.bottom
    return bar.high > zone.top and bar.close < zone.top


def is_zone_violation(bar: Candle, zone: Zone) -> bool:
    """SIGNED §2 breakout clause: a BODY close beyond the level extreme is
    a breakout, not a sweep — it invalidates a swept-but-unconfirmed
    setup on that level."""
    if zone.direction is Direction.LONG:
        return bar.close < zone.bottom
    return bar.close > zone.top


# ---------------------------------------------------------------------- #
# §3 — signed confirm set C allow-list + ending-diagonal confirm on M1
# ---------------------------------------------------------------------- #
def confirm_kind_allowed(kind: str) -> bool:
    """Signed set-C allow-list: only patterns in ``ESSENCE_CONFIRM_KINDS``
    may complete an essence entry (this slice wires the preferred ending
    diagonal; F/D/A are in the signed set but unwired; B/E are out)."""
    return kind in ESSENCE_CONFIRM_KINDS


@dataclass(frozen=True, slots=True)
class EdCandidate:
    """A confirmed ending-diagonal at the zone (Trigger C port, M1)."""

    confirm_idx: int               # the M1 bar whose close reclaimed the boundary
    boundary: float                # LIMIT price (the boundary sweep level)
    terminal_idx: int              # wave-5 terminal extreme M1 index
    terminal_level: float          # wave-5 terminal wick (the §5 stop anchor)


def zone_band_half_width(atr_value: float | None) -> float:
    """Trigger C's zone-context band half-width: frozen §13 multiplier × ATR."""
    if atr_value is None:
        return 0.0
    return ESSENCE_ZONE_BAND_ATR * float(atr_value)


def m1_atr_series(m1: list[Candle]) -> list:
    """Wilder ATR over the M1 execution series (frozen period, no new number)."""
    return atr_series(m1, ESSENCE_ATR_PERIOD)


def find_ed_confirm(
    zone: Zone,
    bar_idx: int,
    m1: list[Candle],
    swings_view: list,
    atr_value: float | None,
) -> EdCandidate | None:
    """Ending-diagonal confirm at ``bar_idx`` on the M1 series — a read-only
    port of the shipped Trigger C semantics to the essence M1 path.

    Requires: a 5-wave ending diagonal travelling INTO the zone (opposite
    the trade direction), whose terminal extreme rests inside the zone ± the
    §13 band, whose terminal throw is recent (frozen Trigger-C window), and
    whose swept boundary line is first reclaimed by the CLOSE of
    ``bar_idx`` (no earlier reclaim after the terminal — the reversal
    commitment, exactly as Trigger C).
    """
    if bar_idx <= 0 or bar_idx >= len(m1):
        return None
    zone_dir = zone.direction
    diag_dir = Direction.SHORT if zone_dir is Direction.LONG else Direction.LONG
    diag = find_ending_diagonal(swings_view, diag_dir, bar_idx)
    if diag is None:
        return None
    if diag.terminal_index > bar_idx:
        return None
    if signal_expired(diag.terminal_index, ESSENCE_ED_TERMINAL_EXPIRY, bar_idx):
        return None

    band = zone_band_half_width(atr_value)
    if not (zone.bottom - band <= diag.terminal_level <= zone.top + band):
        return None

    boundary = diag.boundary_touch_level
    close = m1[bar_idx].close
    if zone_dir is Direction.LONG:
        reclaimed = close > boundary
        earlier = any(
            m1[k].close > boundary
            for k in range(diag.terminal_index + 1, bar_idx)
        )
    else:
        reclaimed = close < boundary
        earlier = any(
            m1[k].close < boundary
            for k in range(diag.terminal_index + 1, bar_idx)
        )
    if not reclaimed or earlier:
        return None
    return EdCandidate(
        confirm_idx=bar_idx,
        boundary=boundary,
        terminal_idx=diag.terminal_index,
        terminal_level=diag.terminal_level,
    )


# ---------------------------------------------------------------------- #
# §5 — the signed stop band (2–5 pips beyond the M1 structure)
# ---------------------------------------------------------------------- #
def essence_stop(direction: Direction, terminal_level: float) -> tuple[float, float]:
    """SL = the M1 structure (wave-5 terminal wick) ± the signed band floor.

    Returns ``(sl_price, sl_pips)`` where ``sl_pips`` is the buffer actually
    applied (a value inside the signed 2–5 pip band). Raises ``ValueError``
    for a nonsensical (non-finite) input.
    """
    if not (math.isfinite(terminal_level) and math.isfinite(ESSENCE_SL_MIN_PIPS)):
        raise ValueError("non-finite stop anchor")
    buffer = pips_to_price(ESSENCE_SL_MIN_PIPS)
    if direction is Direction.LONG:
        return terminal_level - buffer, ESSENCE_SL_MIN_PIPS
    return terminal_level + buffer, ESSENCE_SL_MIN_PIPS


# ---------------------------------------------------------------------- #
# §6 — macro HTF target + the hard 1:5 gate
# ---------------------------------------------------------------------- #
def essence_target(zone_refs: list[tuple], direction: Direction, entry_price: float):
    """Nearest active OPPOSITE-direction HTF zone edge as the macro target.

    ``zone_refs`` is a list of ``(bottom, top, zoning_direction)`` tuples of
    the ACTIVE zone set at confirm time. LONG demands a supply structure
    strictly ABOVE the entry (target = its bottom edge); SHORT is mirrored.
    Returns ``(target_price, ref_description)`` or ``(None, None)`` when no
    usable opposite structure exists — the trade is then BLOCKED
    (``MISSING_TARGET``), never silently downgraded.
    """
    best: tuple[float, str] | None = None
    for bottom, top, zdir in zone_refs:
        if zdir is direction:
            continue                     # only opposite-direction structure
        if direction is Direction.LONG:
            target = bottom              # near edge of a supply zone above
            if target <= entry_price:
                continue
        else:
            target = top                 # near edge of a demand zone below
            if target >= entry_price:
                continue
        frac = "low" if direction is Direction.LONG else "high"
        ref = f"opposite-zone:{frac}"
        if best is None or (direction is Direction.LONG and target < best[0]) or (
            direction is Direction.SHORT and target > best[0]
        ):
            best = (target, ref)
    if best is None:
        return None, None
    return best


def risk_reward(direction: Direction, entry: float, stop: float, target: float) -> float:
    """Planned risk:reward for the (entry, stop, target) triple."""
    if direction is Direction.LONG:
        risk = entry - stop
        reward = target - entry
    else:
        risk = stop - entry
        reward = entry - target
    if risk <= 0.0:
        return 0.0
    return reward / risk


def rr_gate_ok(rr: float) -> bool:
    """SIGNED §6 hard gate: the target must reach the minimum 1:5."""
    return rr >= ESSENCE_MIN_RR
