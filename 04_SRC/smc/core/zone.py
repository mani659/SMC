"""Zone dataclass — price zone with direction and timeframe."""

from __future__ import annotations

from dataclasses import dataclass

from smc.config.timeframe import Timeframe
from smc.core.enums import Direction

__all__ = ["Zone"]


@dataclass(frozen=True, slots=True)
class Zone:
    """A price zone defined by its top and bottom boundaries."""

    top: float
    bottom: float
    direction: Direction
    timeframe: Timeframe = Timeframe.M5

    def __post_init__(self) -> None:
        if self.top < self.bottom:
            raise ValueError("Zone.top must be >= Zone.bottom")

    @property
    def height(self) -> float:
        return self.top - self.bottom

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2.0

    def contains(self, price: float) -> bool:
        """True when price is inside the zone (inclusive)."""
        return self.bottom <= price <= self.top

    def distance_from(self, price: float) -> float:
        """Absolute price distance to the zone; 0.0 when inside it."""
        if price < self.bottom:
            return self.bottom - price
        if price > self.top:
            return price - self.top
        return 0.0