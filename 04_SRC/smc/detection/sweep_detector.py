"""Liquidity sweep detection (LOCKED_DECISIONS §2, sweep principles).

A sweep of a liquidity level is confirmed by a single candle that:

* BSL pool (buy stops above resistance): the candle's WICK pierces ABOVE
  the level (``high > level``) and its BODY closes back BELOW it
  (``close < level``).
* SSL pool (sell stops below support): the candle's WICK pierces BELOW the
  level (``low < level``) and its BODY closes back ABOVE it
  (``close > level``).

This is the "wick-pierce + body-close" confirmation: the stops resting just
beyond the level are consumed and price is rejected back to the protected
side. A candle that closes beyond the level (a genuine breakout) is NOT a
sweep.

Levels are scanned only from candles AFTER their ``formed_at`` (when set),
so a level cannot sweep itself at the bar that created it.
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.core.candle import Candle
from smc.core.enums import PoolType
from smc.core.liquidity_level import LiquidityLevel

__all__ = ["SweepResult", "detect_sweep", "detect_sweeps"]


@dataclass(frozen=True, slots=True)
class SweepResult:
    """A confirmed sweep of one liquidity level by one candle."""

    level: LiquidityLevel
    candle_index: int
    candle: Candle

    @property
    def pool(self) -> PoolType:
        return self.level.pool


def detect_sweep(
    candles: list[Candle],
    level: LiquidityLevel,
    start_index: int = 0,
) -> SweepResult | None:
    """Return the first confirmed sweep of ``level`` (or ``None``).

    ``start_index`` overrides the automatic ``formed_at`` bound — pass it
    when the level's formation index is known but ``formed_at`` is unset.
    """
    first = start_index
    if level.formed_at is not None:
        first = max(first, _first_after(candles, level.formed_at))

    if level.pool is PoolType.BSL:
        def is_sweep(c: Candle) -> bool:
            return c.high > level.level and c.close < level.level
    else:

        def is_sweep(c: Candle) -> bool:
            return c.low < level.level and c.close > level.level

    for index in range(first, len(candles)):
        candle = candles[index]
        if is_sweep(candle):
            return SweepResult(level=level, candle_index=index, candle=candle)
    return None


def detect_sweeps(
    candles: list[Candle],
    levels: list[LiquidityLevel],
) -> list[SweepResult]:
    """Detect the first sweep of each level; levels not swept are skipped.

    Results are returned in candle order (ties broken by input order).
    """
    results = [r for r in (detect_sweep(candles, lv) for lv in levels) if r is not None]
    results.sort(key=lambda r: r.candle_index)
    return results


def _first_after(candles: list[Candle], timestamp) -> int:
    """Index of the first candle whose timestamp is strictly after ``ts``."""
    for index, candle in enumerate(candles):
        if candle.timestamp > timestamp:
            return index
    return len(candles)