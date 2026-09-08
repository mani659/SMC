"""Displacement check (LOCKED_DECISIONS §3).

A displacement is the impulsive move that follows a liquidity sweep:

* Required: BOS (a candle CLOSES beyond the prior swing extreme in the
  direction of the move) AND a fair value gap (3-candle imbalance, §3) AND
  a move magnitude of at least ``DISPLACEMENT_MIN_ATR`` (1× ATR).
* Hard fail: magnitude below ``DISPLACEMENT_HARD_FAIL`` (0.5× ATR).
* Preferred: magnitude above ``DISPLACEMENT_PREFERRED_ATR`` (1.5× ATR).

V1 MEASUREMENT DEFINITION (documented measurement choice — NOT a frozen
threshold): displacement is measured from sweep extreme → BOS close,
compared against the PRE-SWEEP Wilder ATR (bars strictly before the sweep
candle, so the impulse never inflates its own reference). Recorded in
00_LOCKED/SESSION_HANDOFF.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.config.locked_constants import (
    DISPLACEMENT_HARD_FAIL,
    DISPLACEMENT_MIN_ATR,
    DISPLACEMENT_PREFERRED_ATR,
)
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.detection.fvg_detector import detect_fvgs
from smc.utils.atr import latest_atr

__all__ = ["DisplacementResult", "check_displacement"]


@dataclass(frozen=True, slots=True)
class DisplacementResult:
    """Outcome of the §3 displacement evaluation."""

    direction: Direction
    bos: bool                # BOS close beyond the prior swing extreme
    fvg: bool                # directional FVG formed within the move
    magnitude: float | None  # price distance of the move
    magnitude_atr: float | None  # magnitude in pre-move ATR units
    atr: float | None        # pre-move ATR used for scaling
    passed: bool             # bos AND fvg AND magnitude >= DISPLACEMENT_MIN_ATR
    hard_fail: bool          # magnitude < DISPLACEMENT_HARD_FAIL (0.5× ATR)
    is_preferred: bool       # magnitude > DISPLACEMENT_PREFERRED_ATR (1.5× ATR)
    bos_index: int | None    # index of the first BOS candle, if any


def check_displacement(
    candles: list[Candle],
    direction: Direction,
    sweep_index: int,
    bos_level: float,
    atr_period: int = 14,
) -> DisplacementResult:
    """Evaluate displacement over the candles following a sweep.

    Parameters
    ----------
    candles:
        Chronological candle series including the sweep candle and the
        subsequent impulse.
    direction:
        Move direction: ``LONG`` after an SSL (sell-side) sweep, ``SHORT``
        after a BSL (buy-side) sweep.
    sweep_index:
        Index of the sweep candle (its extreme anchors the measurement).
    bos_level:
        Price of the PRIOR swing extreme that the impulse must break by
        body close (prior swing low for ``LONG``, prior swing high for
        ``SHORT``).
    atr_period:
        ATR smoothing period for the pre-move reference value.
    """
    if not 0 <= sweep_index < len(candles):
        raise IndexError(f"sweep_index {sweep_index} out of range")

    sweep = candles[sweep_index]
    # V1: ATR over bars BEFORE the sweep only (measurement definition).
    atr = latest_atr(candles[:sweep_index], atr_period)

    def _first_bos() -> int | None:
        if direction is Direction.LONG:
            for i in range(sweep_index + 1, len(candles)):
                if candles[i].close > bos_level:
                    return i
        else:
            for i in range(sweep_index + 1, len(candles)):
                if candles[i].close < bos_level:
                    return i
        return None

    bos_index = _first_bos()

    def _magnitude() -> float | None:
        """V1 definition: sweep extreme -> BOS close (or best close if no BOS)."""
        if bos_index is not None:
            end = candles[bos_index].close
        else:
            closes_after = [c.close for c in candles[sweep_index + 1 :]]
            if not closes_after:
                return None
            end = max(closes_after) if direction is Direction.LONG else min(closes_after)
        if direction is Direction.LONG:
            return end - sweep.low
        return sweep.high - end

    magnitude = _magnitude()
    magnitude_atr = magnitude / atr if (magnitude is not None and atr is not None) else None

    fvg = False
    if bos_index is not None:
        for f in detect_fvgs(candles):
            if (
                f.start_index >= sweep_index
                and f.start_index <= bos_index
                and f.zone.direction is direction
            ):
                fvg = True
                break

    passed = (
        bos_index is not None
        and fvg
        and magnitude_atr is not None
        and magnitude_atr >= DISPLACEMENT_MIN_ATR
    )
    hard_fail = magnitude_atr is not None and magnitude_atr < DISPLACEMENT_HARD_FAIL
    is_preferred = magnitude_atr is not None and magnitude_atr > DISPLACEMENT_PREFERRED_ATR

    return DisplacementResult(
        direction=direction,
        bos=bos_index is not None,
        fvg=fvg,
        magnitude=magnitude,
        magnitude_atr=magnitude_atr,
        atr=atr,
        passed=passed,
        hard_fail=hard_fail,
        is_preferred=is_preferred,
        bos_index=bos_index,
    )