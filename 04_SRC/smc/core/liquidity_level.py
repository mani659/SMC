"""LiquidityLevel dataclass — one of the 8 Stage 0A liquidity level types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from smc.config.timeframe import Timeframe
from smc.core.enums import LiquidityType, PoolType

__all__ = ["LiquidityLevel"]


@dataclass
class LiquidityLevel:
    """A liquidity level (or pool) eligible for sweep detection (§2).

    Mutable so that detectors can record ``swept_at`` when a sweep is
    confirmed; ``level`` is the price of the pool extreme.
    """

    type: LiquidityType
    level: float
    pool: PoolType
    timeframe: Timeframe = Timeframe.M5
    formed_at: datetime | None = None
    swept_at: datetime | None = None

    @property
    def is_swept(self) -> bool:
        return self.swept_at is not None