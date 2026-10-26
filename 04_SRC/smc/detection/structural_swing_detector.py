"""Structural swing detection (LOCKED_DECISIONS §27 + §18 + §19).

A swing candidate is a fractal extreme: the bar's high/low exceeds all bars
in an N-bar window on BOTH sides (N-bar confirmation, §27). N is frozen —
5 for HTF (D1/H4/H1), 3 for LTF (M30 and below) — and read from
``smc.config.locked_constants`` through ``Timeframe.n_bar_confirmation``.

Ties on the RIGHT of a plateau resolve to the FIRST bar of the plateau
(left comparisons are strict, right comparisons are non-strict), so a flat
double-top/plateau is reported once rather than per equal bar.

Each candidate is anchored to its Base Candle (§18) and then passed through
the §19 validity gate over the available subsequent bars. Swings whose
opposite extreme has not yet been broken + closed beyond are returned with
``is_valid=False`` (they are structural *candidates* until confirmed).
"""

from __future__ import annotations

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.swing import Swing
from smc.detection.base_candle import find_base_candle_index
from smc.detection.swing_validator import validate_swing

__all__ = ["detect_swings"]


def detect_swings(
    candles: list[Candle],
    timeframe: Timeframe,
    n: int | None = None,
) -> list[Swing]:
    """Detect structural swing highs/lows with N-bar confirmation.

    Parameters
    ----------
    candles:
        Chronological candle series (timezone-aware, ascending).
    timeframe:
        Detection timeframe; selects the frozen N (§27) unless ``n`` is given.
    n:
        Explicit confirmation window override (bars each side). Defaults to
        ``Timeframe.n_bar_confirmation(timeframe)``.

    Returns
    -------
    ``Swing`` objects sorted by formation index, each with its Base Candle,
    the extreme price as ``level``, and §19 validity/confirm fields filled
    for the portion of history available.
    """
    window = Timeframe.n_bar_confirmation(timeframe) if n is None else n
    if window < 1:
        raise ValueError("n must be >= 1")
    if len(candles) < 2 * window + 1:
        return []

    swings: list[Swing] = []
    for index in range(window, len(candles) - window):
        candle = candles[index]

        left_highs = [c.high for c in candles[index - window : index]]
        right_highs = [c.high for c in candles[index + 1 : index + window + 1]]
        left_lows = [c.low for c in candles[index - window : index]]
        right_lows = [c.low for c in candles[index + 1 : index + window + 1]]

        is_swing_high = candle.high > max(left_highs) and candle.high >= max(right_highs)
        is_swing_low = candle.low < min(left_lows) and candle.low <= min(right_lows)

        for is_high in (True, False):
            if is_high and not is_swing_high:
                continue
            if not is_high and not is_swing_low:
                continue
            base_index = find_base_candle_index(candles, index, is_high)
            level = candle.high if is_high else candle.low
            validation = validate_swing(candles, base_index, is_high)
            swings.append(
                Swing(
                    is_high=is_high,
                    level=level,
                    candle_index=base_index,
                    base_candle=candles[base_index],
                    timeframe=timeframe,
                    is_valid=validation.is_valid,
                    confirmed_index=validation.confirm_index,
                )
            )
    return swings