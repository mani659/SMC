"""Fair Value Gap (FVG) detection — 3-candle imbalance (LOCKED_DECISIONS §3).

A FVG forms across a 3-candle set (c1, c2, c3) when c1 and c3 do not
overlap, leaving an unfilled gap that price rushed through:

* Bullish FVG: ``low(c3) > high(c1)`` → gap zone ``[high(c1), low(c3)]``,
  direction LONG (price was bid up through the zone).
* Bearish FVG: ``high(c3) < low(c1)`` → gap zone ``[high(c3), low(c1)]``,
  direction SHORT (price was offered down through the zone).

The zone is a ``smc.core.Zone`` with the detection timeframe; ``start_index``
is the index of the first candle of the 3-candle set.
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.zone import Zone

__all__ = ["FVG", "detect_fvgs"]


@dataclass(frozen=True, slots=True)
class FVG:
    """One detected fair value gap."""

    zone: Zone
    start_index: int  # index of the first candle of the 3-candle set


def detect_fvgs(
    candles: list[Candle],
    timeframe: Timeframe = Timeframe.M5,
) -> list[FVG]:
    """Detect all 3-candle fair value gaps in the series.

    Parameters
    ----------
    candles:
        Chronological candle series; at least 3 candles are required.
    timeframe:
        Detection timeframe stamped on each gap zone.

    Returns
    -------
    FVG list in chronological order of the middle candle.
    """
    fvgs: list[FVG] = []
    for middle in range(1, len(candles) - 1):
        first = candles[middle - 1]
        third = candles[middle + 1]

        if third.low > first.high:
            fvgs.append(
                FVG(
                    zone=Zone(
                        top=third.low,
                        bottom=first.high,
                        direction=Direction.LONG,
                        timeframe=timeframe,
                    ),
                    start_index=middle - 1,
                )
            )
        elif third.high < first.low:
            fvgs.append(
                FVG(
                    zone=Zone(
                        top=first.low,
                        bottom=third.high,
                        direction=Direction.SHORT,
                        timeframe=timeframe,
                    ),
                    start_index=middle - 1,
                )
            )
    return fvgs