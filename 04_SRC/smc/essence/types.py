"""Record + feed types for the ESSENCE contract v1 slice.

ESSENCE V1 SLICE — NOT FULL COMPLEX REWRITE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.core.zone import Zone

__all__ = ["EssenceTrade", "EssenceZoneEntry"]


@dataclass(slots=True)
class EssenceZoneEntry:
    """One active emitted HTF zone episode (the contract §1 level).

    W1 is context-only per the runtime amendment; the level set is the M8
    emitter's own W1/D1/H4 (H1 is signed but has no emitter — mapping
    follow-up F11).
    """

    poi_id: str
    detection_tf: Timeframe
    zone: Zone
    kind: str                      # m8 facet: ob / demand_supply / fvg
    valid_from_ts: datetime        # M1 bar timestamp at which essence saw it
    bottom: float
    top: float


@dataclass(slots=True)
class EssenceTrade:
    """One essence v1 trade with its full expert-scoring identity.

    ``pnl`` is in raw price units per 1 unit of XAU (book-internal, costs 0,
    DIAGNOSTIC ONLY — the same convention as the COMPLEX/DUMB diagnostic
    books). Identity exports everything §8 scores: level (zone + TF),
    sweep (ts/extreme), confirm (kind + boundary + terminal), entry (style
    LIMIT, TF = M1, ts), stop (price + pips within the signed band), TP/
    manage (target reference, RR, BE flag, close kind).
    """

    ticket: int
    zone_poi_id: str
    detection_tf: Timeframe
    zone_kind: str
    direction: Direction
    # level
    zone: tuple[float, float]          # (zone_bottom, zone_top)
    # sweep
    sweep_ts: datetime
    sweep_extreme: float
    # confirm (set C: ending diagonal in this slice)
    confirm_kind: str
    confirm_idx: int
    confirm_ts: datetime
    entry_level: float                 # the ED boundary = the LIMIT price
    terminal_idx: int                  # wave-5 terminal M1 index
    # entry
    entry_idx: int                     # limit FILL bar
    entry_ts: datetime
    entry_price: float                 # always the limit price (touch = fill)
    # stop (§5: 2–5 pips beyond the M1 structure)
    sl_price: float                    # mutates on the BE move
    sl_pips_buffer: float
    # target (§6: macro HTF, min 1:5)
    tp_price: float
    target_ref: tuple[str, float]      # (ref description, ref price)
    rr_planned: float
    r_stop: float
    atr_at_entry: float
    # manage
    limit_placed_idx: int
    limit_expiry_bars: int
    be_applied: bool = False
    # exit
    exit_idx: int | None = None
    exit_ts: datetime | None = None
    exit_price: float | None = None
    close_kind: str | None = None      # stop_loss / take_profit / end_of_data
    bars_held: int = 0
    pnl: float = 0.0
