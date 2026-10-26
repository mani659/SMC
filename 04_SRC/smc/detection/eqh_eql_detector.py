"""Equal Highs / Equal Lows detection (LOCKED_DECISIONS §2, §8).

Double/triple tops (BSL) or bottoms (SSL) whose swing levels are within the
frozen EQH/EQL tolerance are clustered into a single liquidity level.

* Tolerance: ``EQH_EQL_TOLERANCE`` (4.5 pips on XAUUSD) — converted to
  price units via ``smc.utils.pips``. No other threshold is applied.
* Clustering: swing highs (or lows) sorted by price; a level joins a
  cluster while it stays within tolerance of the cluster anchor. A cluster
  needs at least two members to become a level.
* Level price: the EXTREME of the cluster — the highest high for equal
  highs (BSL), the lowest low for equal lows (SSL) — matching the
  "Extreme Equal Highs" naming used by Model 5 (§8).
* Both top (BSL) and bottom (SSL) pools are tracked concurrently.
"""

from __future__ import annotations

from smc.config.locked_constants import EQH_EQL_TOLERANCE
from smc.config.timeframe import Timeframe
from smc.core.enums import LiquidityType, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.core.swing import Swing
from smc.utils.pips import pips_to_price

__all__ = ["detect_equal_levels"]


def _cluster(swings: list[Swing], is_high: bool) -> list[list[Swing]]:
    """Greedily cluster swings of one side by price within tolerance.

    Clusters are anchored at the cheapest member (lowest high / highest
    low); every subsequent member must stay within tolerance of that anchor
    (running bound, so a cluster never spans more than the tolerance).
    """
    tolerance = pips_to_price(EQH_EQL_TOLERANCE)
    key = (lambda s: s.level) if is_high else (lambda s: -s.level)
    ordered = sorted((s for s in swings if s.is_high == is_high), key=key)

    clusters: list[list[Swing]] = []
    for swing in ordered:
        if not clusters:
            clusters.append([swing])
            continue
        anchor = clusters[-1][0].level
        if is_high:
            within = swing.level <= anchor + tolerance
        else:
            within = swing.level >= anchor - tolerance
        if within:
            clusters[-1].append(swing)
        else:
            clusters.append([swing])
    return [c for c in clusters if len(c) >= 2]


def detect_equal_levels(
    swings: list[Swing],
    timeframe: Timeframe = Timeframe.M5,
) -> list[LiquidityLevel]:
    """Detect equal-high (BSL) and equal-low (SSL) liquidity levels.

    Parameters
    ----------
    swings:
        Swing highs/lows to cluster (typically the output of
        ``structural_swing_detector``). Validity per §19 is NOT required —
        an EQH/EQL pool exists at formation time, before any later break.
    timeframe:
        Detection timeframe stamped on each returned level.

    Returns
    -------
    One ``LiquidityLevel`` per cluster of two or more equal highs (pool
    ``BSL``, type ``EQUAL_HIGHS_LOWS``) or equal lows (pool ``SSL``).
    ``formed_at`` is the timestamp of the most recent member of the cluster.
    """
    levels: list[LiquidityLevel] = []
    for is_high in (True, False):
        for cluster in _cluster(swings, is_high):
            if is_high:
                level_price = max(s.level for s in cluster)
                pool = PoolType.BSL
            else:
                level_price = min(s.level for s in cluster)
                pool = PoolType.SSL
            formed_at = max(s.timestamp for s in cluster)
            levels.append(
                LiquidityLevel(
                    type=LiquidityType.EQUAL_HIGHS_LOWS,
                    level=level_price,
                    pool=pool,
                    timeframe=timeframe,
                    formed_at=formed_at,
                )
            )
    levels.sort(key=lambda lv: lv.formed_at or lv.level)
    return levels