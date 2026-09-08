"""Deterministic V1 wave-structure extraction for Trigger B/C.

Leading (B) and Ending (C) diagonals need 5-wave counting — the most
subjective trigger requirement (DEVELOPMENT_PLAN Phase 4 "Missing design
decisions"; v5 flowchart marks B ⚠️ and C ⚠️). This module pins down a
DETERMINISTIC V1 approximation over the §27 structural swings so the
triggers are machine-testable; it is NOT an Elliott-wave engine and should
be revisited against research data in Phase 6.

V1 definitions (documented, no invented thresholds):

* A chain is the strictly-alternating run of swing extremes ending at the
  most recent swing of the terminal polarity (same-polarity minor swings
  are skipped — the same consecutive-swing simplification Model 4 uses).
* ``find_impulse(direction)``: ``direction`` = the direction the impulse
  TRAVELS (= the trade direction out of the POI for Trigger B). An up
  impulse is chain ``[low0, high1, low2, high3, low4, high5]`` with rising
  highs (high3 > high1, high5 > high3) and rising lows (low2 > low0,
  low4 > low2); the mirror image handles down impulses.
* ``find_ending_diagonal(direction)``: ``direction`` = the direction the
  diagonal TRAVELS INTO the zone (the OLD trend — opposite the trade). An
  ending diagonal into a demand zone travels DOWN (terminal throw-under of
  the lower boundary); into a supply zone it travels UP (terminal
  throw-over of the upper boundary). The terminal extreme throws beyond
  the swept boundary line.
* Down-diagonals are detected directly; up-diagonals/up-impulses via price
  inversion (the ``choch_classifier`` pattern), so each geometric path is
  written once.
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.core.enums import Direction
from smc.core.swing import Swing

__all__ = [
    "WaveExtreme",
    "Impulse",
    "Diagonal",
    "find_impulse",
    "find_ending_diagonal",
]

_MAX_SWINGS = 60  # backward scan bound (V1 window — caller-supplied series)


@dataclass(frozen=True, slots=True)
class WaveExtreme:
    """One wave endpoint: a swing extreme (index/level/polarity)."""

    index: int
    level: float
    is_high: bool

    @property
    def is_low(self) -> bool:
        return not self.is_high


@dataclass(frozen=True, slots=True)
class Impulse:
    """A 5-wave impulse in ``direction`` ending at ``wave5``.

    ``origin_level`` is the start of the impulse (Wave-1 origin) — the
    Trigger B stop reference (below origin for LONG).
    """

    direction: Direction
    origin_index: int
    origin_level: float
    wave5_index: int
    wave5_level: float
    peak_level: float
    extremes: tuple[WaveExtreme, ...]

    @property
    def height(self) -> float:
        """Full peak-to-origin price distance of the impulse."""
        return abs(self.peak_level - self.origin_level)


@dataclass(frozen=True, slots=True)
class Diagonal:
    """A contracting ending diagonal ending with a terminal throw.

    ``boundary_touch_level`` is the V1 entry reference: the value of the
    swept boundary line at the terminal extreme (Trigger C entry/stop area).
    """

    direction: Direction
    terminal_index: int
    terminal_level: float
    boundary_touch_level: float
    converging: bool
    extremes: tuple[WaveExtreme, ...]


def _sorted_swings(swings: list[Swing], up_to_index: int) -> list[Swing]:
    """Chronological swings at/before ``up_to_index`` (index-bounded)."""
    result = [s for s in swings if s.candle_index <= up_to_index]
    result.sort(key=lambda s: s.candle_index)
    return result


def _alternating_chain(
    swings: list[Swing],
    up_to_index: int,
    terminal_is_high: bool,
    length: int,
) -> list[WaveExtreme]:
    """Most recent strictly-alternating chain of ``length`` extremes.

    Walks backwards from the most recent swing of ``terminal_is_high``
    polarity, accepting each swing whose polarity alternates from the last
    accepted one (same-polarity minor swings are skipped).
    """
    wanted = terminal_is_high
    chain: list[WaveExtreme] = []
    for swing in reversed(_sorted_swings(swings, up_to_index)):
        if len(chain) >= length:
            break
        if swing.is_high == wanted:
            chain.append(WaveExtreme(swing.candle_index, swing.level, swing.is_high))
            wanted = not wanted
    chain.reverse()
    return chain


def _invert(swings: list[Swing], up_to_index: int) -> tuple[list[Swing], int]:
    """Price-invert swings for bearish symmetry (levels negated, polarities flipped)."""
    inverted: list[Swing] = []
    for swing in _sorted_swings(swings, up_to_index):
        inverted.append(
            Swing(
                is_high=not swing.is_high,
                level=-swing.level,
                candle_index=swing.candle_index,
                base_candle=swing.base_candle,
                timeframe=swing.timeframe,
                is_valid=swing.is_valid,
            )
        )
    return inverted, up_to_index


# --------------------------------------------------------------------------- #
# Impulse (Trigger B) — bullish implemented directly
# --------------------------------------------------------------------------- #
def _find_up_impulse(swings: list[Swing], up_to_index: int) -> Impulse | None:
    chain = _alternating_chain(swings, up_to_index, terminal_is_high=True, length=6)
    if len(chain) < 6:
        return None
    low0, high1, low2, high3, low4, high5 = chain
    if not (
        high1.is_high and not low2.is_high and high3.is_high
        and not low4.is_high and high5.is_high
    ):
        return None
    # Alternation pattern check (chain is already alternating — sanity).
    if not (high3.level > high1.level and high5.level > high3.level):
        return None  # rising highs: waves 1 < 3 < 5
    if not (low2.level > low0.level and low4.level > low2.level):
        return None  # rising lows: pullbacks hold progress
    return Impulse(
        direction=Direction.LONG,
        origin_index=low0.index,
        origin_level=low0.level,
        wave5_index=high5.index,
        wave5_level=high5.level,
        peak_level=high5.level,
        extremes=(low0, high1, low2, high3, low4, high5),
    )


def find_impulse(
    swings: list[Swing], direction: Direction, up_to_index: int
) -> Impulse | None:
    """Most recent 5-wave impulse in ``direction`` ending at/before the bar.

    LONG is detected directly; SHORT on inverted swings (mirrored back).
    """
    if direction is Direction.LONG:
        return _find_up_impulse(swings, up_to_index)
    inverted, index = _invert(swings, up_to_index)
    up = _find_up_impulse(inverted, index)
    if up is None:
        return None
    return Impulse(
        direction=Direction.SHORT,
        origin_index=up.origin_index,
        origin_level=-up.origin_level,
        wave5_index=up.wave5_index,
        wave5_level=-up.wave5_level,
        peak_level=-up.peak_level,
        extremes=tuple(
            WaveExtreme(e.index, -e.level, not e.is_high) for e in up.extremes
        ),
    )


# --------------------------------------------------------------------------- #
# Contracting ending diagonal (Trigger C) — terminal-throw variant
# --------------------------------------------------------------------------- #
def _line_value(p1: tuple[float, float], p2: tuple[float, float], x: float) -> float:
    """Linear interpolation between two (x, y) points at ``x``."""
    x1, y1 = p1
    x2, y2 = p2
    if x2 == x1:
        return y1
    return y1 + (y2 - y1) * (x - x1) / (x2 - x1)


def _find_down_diagonal(swings: list[Swing], up_to_index: int) -> Diagonal | None:
    # Bearish terminal = wave 5 ends at a swing LOW.
    chain = _alternating_chain(swings, up_to_index, terminal_is_high=False, length=5)
    if len(chain) < 5:
        return None
    w1, w2, w3, w4, w5 = chain
    if not (w1.is_low and w2.is_high and w3.is_low and w4.is_high and w5.is_low):
        return None
    if not (w3.level < w1.level):
        return None  # waves make downward progress into the zone
    # Boundary lines: upper through the two highs, lower through the lows
    # w1/w3 extended to w4 (contracting check) and w5 (throw-under check).
    upper = (float(w2.index), w2.level), (float(w4.index), w4.level)
    lower = (float(w1.index), w1.level), (float(w3.index), w3.level)

    gap_start = _line_value(*upper, float(w1.index)) - w1.level
    gap_end = _line_value(*upper, float(w5.index)) - _line_value(*lower, float(w5.index))
    converging = gap_end < gap_start

    # Throw-under: wave 5 pierces the lower boundary line at its own bar.
    boundary_at_w5 = _line_value(*lower, float(w5.index))
    if not (w5.level < boundary_at_w5):
        return None
    return Diagonal(
        direction=Direction.SHORT,
        terminal_index=w5.index,
        terminal_level=w5.level,
        boundary_touch_level=boundary_at_w5,
        converging=converging,
        extremes=(w1, w2, w3, w4, w5),
    )


def find_ending_diagonal(
    swings: list[Swing], direction: Direction, up_to_index: int
) -> Diagonal | None:
    """Most recent contracting ending diagonal ending at/before the bar.

    SHORT (terminal throw-under of a downtrend) is detected directly; LONG
    (terminal throw-over of an uptrend) on inverted swings, mirrored back.
    """
    if direction is Direction.SHORT:
        return _find_down_diagonal(swings, up_to_index)
    inverted, index = _invert(swings, up_to_index)
    down = _find_down_diagonal(inverted, index)
    if down is None:
        return None
    return Diagonal(
        direction=Direction.LONG,
        terminal_index=down.terminal_index,
        terminal_level=-down.terminal_level,
        boundary_touch_level=-down.boundary_touch_level,
        converging=down.converging,
        extremes=tuple(
            WaveExtreme(e.index, -e.level, not e.is_high) for e in down.extremes
        ),
    )
