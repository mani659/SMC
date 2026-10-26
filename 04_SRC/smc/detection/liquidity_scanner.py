"""Liquidity scanner — Stage 0A orchestrator (LOCKED_DECISIONS §2).

Runs the Phase 1 sub-detectors and merges their output into a single
``LiquidityLevel`` list. Families currently produced (in §2 table order):

1. ``session``  — Asia/London/NY session highs & lows (BSL/SSL)
2. ``periodic`` — PDH/PDL and PWH/PWL (BSL/SSL)
3. ``equal``    — EQH/EQL clusters within the frozen pip tolerance (BSL/SSL)
4. ``structural`` — Base-Candle-confirmed structural swings (§19-valid only)

The remaining §2 level types (POI_LEVEL, DEMAND_SUPPLY_BOUNDARY,
ORDER_BLOCK_BOUNDARY) depend on POI zones and are produced in Phase 2+.

Multi-label readiness: families routinely co-label the SAME price region
(e.g. a session high, an equal-high cluster and a structural swing all at
104.10). The returned list deliberately preserves these overlapping
LiquidityLevels — per §1 all models are equal tags, so deduplication and
confluence scoring are the job of the Phase 2 POI layer, not the scanner.
"""

from __future__ import annotations

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import LiquidityType
from smc.core.liquidity_level import LiquidityLevel
from smc.detection.eqh_eql_detector import detect_equal_levels
from smc.detection.periodic_levels import detect_periodic_levels
from smc.detection.session_levels import detect_session_levels
from smc.detection.structural_swing_detector import detect_swings

__all__ = ["scan", "ALL_FAMILIES"]

ALL_FAMILIES = ("session", "periodic", "equal", "structural")


def scan(
    candles: list[Candle],
    timeframe: Timeframe,
    include: tuple[str, ...] = ALL_FAMILIES,
) -> list[LiquidityLevel]:
    """Scan candles for all Phase 1 liquidity level families.

    Parameters
    ----------
    candles:
        Chronological UTC candles (the detection window).
    timeframe:
        Detection timeframe (drives the frozen N-bar window and is stamped
        on every level).
    include:
        Family filter; default is all of :data:`ALL_FAMILIES`.

    Returns
    -------
    Levels grouped by family in §2 table order (session, periodic, equal,
    structural); within a family levels are chronological. Structural
    levels are emitted only for swings that passed the §19 gate.
    """
    unknown = set(include) - set(ALL_FAMILIES)
    if unknown:
        raise ValueError(f"Unknown liquidity family: {sorted(unknown)}")

    levels: list[LiquidityLevel] = []

    if "session" in include:
        levels.extend(detect_session_levels(candles, timeframe))
    if "periodic" in include:
        levels.extend(detect_periodic_levels(candles, timeframe))
    if "equal" in include or "structural" in include:
        swings = detect_swings(candles, timeframe)
        if "equal" in include:
            levels.extend(detect_equal_levels(swings, timeframe))
        if "structural" in include:
            for swing in swings:
                if not swing.is_valid:
                    continue
                levels.append(
                    LiquidityLevel(
                        type=LiquidityType.STRUCTURAL_SWING,
                        level=swing.level,
                        pool=swing.pool,
                        timeframe=timeframe,
                        formed_at=swing.timestamp,
                    )
                )
    return levels