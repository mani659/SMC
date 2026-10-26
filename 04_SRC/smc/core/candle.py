"""Candle dataclass — OHLCV bar with timestamp and timeframe."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from smc.config.timeframe import Timeframe

__all__ = ["Candle"]


@dataclass(frozen=True, slots=True)
class Candle:
    """One OHLCV bar. Timestamps are expected to be timezone-aware (UTC)."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    timeframe: Timeframe = Timeframe.M5

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body(self) -> float:
        """Absolute body size."""
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        """Full high-low range."""
        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        """Distance from body top to high (0 for bullish full-body candles)."""
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        """Distance from body bottom to low (0 for bearish full-body candles)."""
        return min(self.open, self.close) - self.low