"""Swing dataclass — structural swing with Base Candle validity gate.

Per LOCKED_DECISIONS §18/§19, a swing only exists once the Base Candle's
OPPOSITE extreme is broken with a body close. ``is_valid`` is therefore
``False`` until that confirmation is observed (Phase 1 detection sets it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import PoolType

__all__ = ["Swing"]


@dataclass
class Swing:
    """A structural swing point anchored to its Base Candle (§18/§19)."""

    is_high: bool                      # True = swing high, False = swing low
    level: float                       # The extreme price (high or low)
    candle_index: int                  # Index of the Base Candle in its series
    base_candle: Candle                # The candle that created the extreme
    timeframe: Timeframe = Timeframe.M5
    is_valid: bool = False             # Confirmed via Base Candle gate (§19)
    confirmed_index: int | None = None  # Index of the confirming candle, if any

    @property
    def is_low(self) -> bool:
        return not self.is_high

    @property
    def pool(self) -> PoolType:
        """BSL for swing highs, SSL for swing lows (§2 directional pool)."""
        return PoolType.BSL if self.is_high else PoolType.SSL

    @property
    def timestamp(self) -> datetime:
        return self.base_candle.timestamp