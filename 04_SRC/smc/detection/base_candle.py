"""Base Candle identification algorithm (LOCKED_DECISIONS §18).

A Base Candle is the candle that creates the structural extreme (high or
low) at a swing point.

* Bullish trend (swing high): the candle whose HIGH is the swing high —
  NOT the candle before or after.
* Bearish trend (swing low): the candle whose LOW is the swing low, with a
  special rule — if the NEXT candle's wick creates the lower low, the
  preceding bearish candle is still the Base Candle (institutional selling
  intent), provided that next candle closes back at/above the bearish
  candle's low.

There is deliberately NO symmetric exception for swing highs: §18 states
the bullish case is always the single candle whose high IS the extreme.
"""

from __future__ import annotations

from smc.core.candle import Candle

__all__ = ["find_base_candle_index"]


def find_base_candle_index(
    candles: list[Candle],
    extreme_index: int,
    is_high: bool,
) -> int:
    """Return the index of the Base Candle for a swing extreme.

    Parameters
    ----------
    candles:
        Chronological candle series. ``candles[extreme_index]`` must hold
        the extreme being classified (highest high for ``is_high=True``,
        lowest low for ``is_high=False``).
    extreme_index:
        Index of the candle whose high/low IS the swing extreme.
    is_high:
        ``True`` for a swing high, ``False`` for a swing low.

    Returns
    -------
    The index of the Base Candle per §18. For a swing high this is always
    ``extreme_index``. For a swing low it may be ``extreme_index - 1`` when
    the §18 bearish wick rule applies.
    """
    if not 0 <= extreme_index < len(candles):
        raise IndexError(f"extreme_index {extreme_index} out of range")
    if is_high:
        # Bullish trend: the one candle whose HIGH is the swing high.
        return extreme_index

    candle = candles[extreme_index]
    # Bearish trend special rule (§18): if the candle BEFORE the extreme is
    # bearish and THIS candle's wick creates the lower low while its body
    # closes back at/above the bearish candle's low, the bearish candle is
    # the Base Candle (institutional selling intent).
    if extreme_index > 0:
        previous = candles[extreme_index - 1]
        if (
            previous.is_bearish
            and candle.low < previous.low
            and candle.close >= previous.low
        ):
            return extreme_index - 1
    return extreme_index