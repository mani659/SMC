"""Swing validity decision gate (LOCKED_DECISIONS §19).

CORE RULE: a swing is ONLY valid if price later breaks the Base Candle's
OPPOSITE extreme AND closes beyond it.

* Swing HIGH (bullish base candle): valid when a later candle CLOSES below
  the base candle's LOW (a wick below alone is INVALID).
* Swing LOW (bearish base candle): valid when a later candle CLOSES above
  the base candle's HIGH (a wick above alone is INVALID).

A two-bar reversal that does not break + close beyond the base candle's
opposite extreme does NOT confirm the swing (§19 "two-bar reversal trap").
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.core.candle import Candle

__all__ = ["SwingValidation", "validate_swing", "is_valid_swing"]


@dataclass(frozen=True, slots=True)
class SwingValidation:
    """Outcome of the §19 decision gate.

    ``pierce_index`` is the first candle whose WICK crossed the base
    candle's opposite extreme; ``confirm_index`` is the first candle whose
    BODY CLOSED beyond it. The swing is valid iff ``confirm_index`` is set.
    """

    is_valid: bool
    pierce_index: int | None = None
    confirm_index: int | None = None


def validate_swing(
    candles: list[Candle],
    base_index: int,
    is_high: bool,
    end_index: int | None = None,
) -> SwingValidation:
    """Validate a swing per §19 by scanning candles after its base candle.

    Parameters
    ----------
    candles:
        Chronological candle series (must extend past ``base_index``).
    base_index:
        Index of the swing's Base Candle (§18).
    is_high:
        ``True`` for a swing high (opposite extreme = base candle LOW),
        ``False`` for a swing low (opposite extreme = base candle HIGH).
    end_index:
        Exclusive scan limit; defaults to ``len(candles)``.
    """
    end = len(candles) if end_index is None else min(end_index, len(candles))
    base = candles[base_index]

    if is_high:
        opposite = base.low
        wick_beyond = lambda c: c.low < opposite          # noqa: E731
        close_beyond = lambda c: c.close < opposite       # noqa: E731
    else:
        opposite = base.high
        wick_beyond = lambda c: c.high > opposite         # noqa: E731
        close_beyond = lambda c: c.close > opposite       # noqa: E731

    pierce_index: int | None = None
    confirm_index: int | None = None
    for index in range(base_index + 1, end):
        candle = candles[index]
        if pierce_index is None and wick_beyond(candle):
            pierce_index = index
        if close_beyond(candle):
            confirm_index = index
            break

    return SwingValidation(
        is_valid=confirm_index is not None,
        pierce_index=pierce_index,
        confirm_index=confirm_index,
    )


def is_valid_swing(
    candles: list[Candle],
    base_index: int,
    is_high: bool,
    end_index: int | None = None,
) -> bool:
    """Convenience boolean wrapper over :func:`validate_swing`."""
    return validate_swing(candles, base_index, is_high, end_index).is_valid