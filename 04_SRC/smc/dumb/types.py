"""Record types for DUMB FLOWCHART V1.

DUMB IMPLEMENTATION — DIAGNOSTIC — NOT EDGE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from smc.config.timeframe import Timeframe
from smc.core.enums import Direction

__all__ = ["DumbTrade"]


@dataclass(slots=True)
class DumbTrade:
    """R4–R6 — one admitted trade with its locked decision trail.

    ``pnl`` is in raw price units per 1 unit of XAU (book-internal, costs 0,
    DIAGNOSTIC ONLY — same convention as the COMPLEX diagnostic books).
    """

    ticket: int
    zone_poi_id: str
    detection_tf: Timeframe
    zone_kind: str
    direction: Direction
    entry_idx: int                  # index into the full M5 series
    entry_ts: datetime
    entry_price: float              # confirm bar close (R4)
    zone: tuple[float, float]       # (zone_bottom, zone_top) of the level (R1)
    sweep_ts: datetime              # sweep bar that anchored the setup (R2)
    confirm_ts: datetime            # reclaim bar (R3)
    sl_price: float                 # R5: sweep extreme − buffer·ATR (LONG +)
    tp_price: float                 # R6: entry ± DUMB_TP_R_MULTIPLE × 1R
    r_stop: float                   # 1R = |entry − SL|
    atr_at_entry: float
    exit_idx: int | None = None
    exit_ts: datetime | None = None
    exit_price: float | None = None
    close_kind: str | None = None   # take_profit / stop_loss / end_of_data
    bars_held: int = 0
    pnl: float = 0.0
