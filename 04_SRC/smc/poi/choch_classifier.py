"""CHOCH Rule 1/2/3 classifier (LOCKED_DECISIONS §17, §20).

Three distinct Change-of-Character types (expert — frozen):

  Rule 1 — Standard:  candle body CLOSES beyond the LAST SWING of the main
          trend (highest strength). Entry at the broken last swing level.
  Rule 2 — Inside Body: body CLOSES beyond an INTERMEDIATE (minor) level
          inside the correction while the last swing of the main trend is
          NOT broken (medium). Entry at the broken intermediate level.
  Rule 3 — Inside Wick: only a WICK pierces a structural level, no body
          close (lowest — KEPT). Entry at the wick-pierced level (§20).

The classifier is anchored on one candle (``bar_index``, typically the last
bar of a window) and requires the liquidity sweep of the final extreme
(stage 0A pre-condition) to have occurred first. Direction is detected
bearish directly and bullish via price inversion, so a single geometric
code path serves both sides.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from smc.core.candle import Candle
from smc.core.enums import Direction, LiquidityType, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.core.swing import Swing
from smc.detection.sweep_detector import detect_sweep

__all__ = ["ChochRule", "ChochBreak", "classify_choch_at"]


class ChochRule(Enum):
    """The three CHOCH types (§17), ranked strongest to weakest."""

    RULE_1_STANDARD = "rule_1"
    RULE_2_INSIDE_BODY = "rule_2"
    RULE_3_INSIDE_WICK = "rule_3"


@dataclass(frozen=True, slots=True)
class ChochBreak:
    """A CHOCH break of one type at one candle."""

    direction: Direction
    rule: ChochRule
    broken_level: float          # level used for entry placement (§9/§20)
    break_index: int             # candle that completed the break/pierce
    sweep_index: int | None      # liquidity sweep candle of the final extreme


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _invert_candles(candles: list[Candle]) -> list[Candle]:
    """Price-inverted copy: bull <-> bear geometry (high/low swap after sign)."""
    inverted: list[Candle] = []
    for candle in candles:
        inverted.append(
            Candle(
                timestamp=candle.timestamp,
                open=-candle.open,
                high=-candle.low,
                low=-candle.high,
                close=-candle.close,
                volume=candle.volume,
                timeframe=candle.timeframe,
            )
        )
    return inverted


def _invert_swings(swings: list[Swing]) -> list[Swing]:
    """Swings mirrored through price inversion (highs become lows)."""
    inverted: list[Swing] = []
    for swing in swings:
        inverted.append(
            Swing(
                is_high=not swing.is_high,
                level=-swing.level,
                candle_index=swing.candle_index,
                base_candle=_invert_candles([swing.base_candle])[0],
                timeframe=swing.timeframe,
                is_valid=swing.is_valid,
                confirmed_index=swing.confirmed_index,
            )
        )
    return inverted


def _last_two(swings: list[Swing], before_index: int) -> tuple[Swing | None, Swing | None]:
    """Most recent §19-VALID swing low & swing high strictly before a bar.

    The main-trend last swing (Rule 1) must be structural; unconfirmed
    swings are treated as INTERMEDIATE (minor) levels for Rule 2/3.
    """
    lows = [
        s for s in swings if not s.is_high and s.is_valid and s.candle_index < before_index
    ]
    highs = [
        s for s in swings if s.is_high and s.is_valid and s.candle_index < before_index
    ]
    last_low = max(lows, key=lambda s: s.candle_index, default=None)
    last_high = max(highs, key=lambda s: s.candle_index, default=None)
    return last_low, last_high


def _minor_lows(
    swings: list[Swing], after_index: int, before_index: int
) -> list[Swing]:
    """Unconfirmed (is_valid=False) swing lows inside (after, before)."""
    return [
        s
        for s in swings
        if not s.is_high
        and not s.is_valid
        and after_index < s.candle_index < before_index
    ]


def _bearish_classify(
    candles: list[Candle],
    swings: list[Swing],
    bar_index: int,
) -> ChochBreak | None:
    """Rule 1/2/3 for a bearish break at ``bar_index`` (uptrend reversal)."""
    bar = candles[bar_index]
    last_low, last_high = _last_two(swings, bar_index)
    if last_low is None or last_high is None:
        return None
    # Up-leg context: the most recent high must come after the last low.
    if last_high.candle_index <= last_low.candle_index:
        return None

    # 0) Liquidity sweep of the final high (BSL) — must precede the break.
    level = LiquidityLevel(
        type=LiquidityType.STRUCTURAL_SWING,
        level=last_high.level,
        pool=PoolType.BSL,
        timeframe=last_high.timeframe,
        formed_at=last_high.timestamp,
    )
    sweep = detect_sweep(candles, level)
    if sweep is None or sweep.candle_index >= bar_index:
        return None

    last_low_level = last_low.level

    # Rule 1: body close below the last low (last swing broken).
    if bar.close < last_low_level:
        if _any_close_below(candles, sweep.candle_index + 1, bar_index, last_low_level):
            return None  # the break happened earlier, not at bar_index
        return ChochBreak(
            direction=Direction.SHORT,
            rule=ChochRule.RULE_1_STANDARD,
            broken_level=last_low_level,
            break_index=bar_index,
            sweep_index=sweep.candle_index,
        )

    # Rule 2: body close below an intermediate minor low, last low NOT broken.
    minors = _minor_lows(swings, last_low.candle_index, bar_index)
    broken = [
        m
        for m in minors
        if bar.close < m.level < last_high.level
        and bar.close >= last_low_level
        and not _any_close_below(candles, sweep.candle_index + 1, bar_index, m.level)
    ]
    if broken:
        deepest = min(broken, key=lambda m: m.level)
        return ChochBreak(
            direction=Direction.SHORT,
            rule=ChochRule.RULE_2_INSIDE_BODY,
            broken_level=deepest.level,
            break_index=bar_index,
            sweep_index=sweep.candle_index,
        )

    # Rule 3: wick-only pierce of the last low (or an intermediate low).
    pierced = None
    if bar.low < last_low_level:
        pierced = last_low_level
    else:
        for m in sorted(minors, key=lambda m: m.level):
            if bar.low < m.level:
                pierced = m.level
                break
    if pierced is not None:
        return ChochBreak(
            direction=Direction.SHORT,
            rule=ChochRule.RULE_3_INSIDE_WICK,
            broken_level=pierced,
            break_index=bar_index,
            sweep_index=sweep.candle_index,
        )
    return None


def _any_close_below(
    candles: list[Candle], start: int, end: int, level: float
) -> bool:
    return any(candles[i].close < level for i in range(start, end))


def classify_choch_at(
    candles: list[Candle],
    swings: list[Swing],
    bar_index: int | None = None,
) -> ChochBreak | None:
    """Classify the CHOCH completed at ``bar_index`` (default: last bar).

    Bearish is evaluated directly; bullish is evaluated on price-inverted
    candles/swings and mirrored back. Returns ``None`` when no CHOCH
    completes at the given bar (no sweep, no break, or geometry mismatch).
    """
    if not candles:
        return None
    index = len(candles) - 1 if bar_index is None else bar_index
    if not 0 <= index < len(candles):
        raise IndexError(f"bar_index {index} out of range")

    bearish = _bearish_classify(candles, swings, index)
    if bearish is not None:
        return bearish

    inverted_candles = _invert_candles(candles)
    inverted_swings = _invert_swings(swings)
    bullish = _bearish_classify(inverted_candles, inverted_swings, index)
    if bullish is not None:
        return ChochBreak(
            direction=Direction.LONG,
            rule=bullish.rule,
            broken_level=-bullish.broken_level,
            break_index=bullish.break_index,
            sweep_index=bullish.sweep_index,
        )
    return None