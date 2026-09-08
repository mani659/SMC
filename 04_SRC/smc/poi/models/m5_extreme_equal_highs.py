"""Model 5 — Extreme Equal Highs / Supply Origin (R1 §5, LOCKED_DECISIONS §8).

PROACTIVE continuation setup: two+ swing highs/lows form an equal cluster
FIRST, then the cluster is broken. The zone spans the member candles' full
wick range; the POI is the retest of the broken equal level.

* Bearish (equal highs): a later body close below the cluster bottom.
* Bullish (equal lows): a later body close above the cluster top.

Distinct from Model 7 (reactive shelf): M5 needs two EQUAL extremes within
the frozen EQH tolerance; M7 keys off a single reactive bounce level.
"""

from __future__ import annotations

from smc.config.locked_constants import EQH_EQL_TOLERANCE
from smc.config.model_type import ModelType
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.core.zone import Zone
from smc.poi.base_model import POIModel
from smc.utils.pips import pips_to_price

__all__ = ["M5ExtremeEqualHighs"]


class M5ExtremeEqualHighs(POIModel):
    """Equal-extreme cluster broken proactively (§8)."""

    tag = ModelType.M5

    def detect(
        self,
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
    ) -> list[POI]:
        if not candles:
            return []
        pois: list[POI] = []
        for is_high, direction in ((True, Direction.SHORT), (False, Direction.LONG)):
            poi = self._detect_cluster(candles, swings, is_high, direction)
            if poi is not None:
                pois.append(poi)
        return pois

    def _detect_cluster(
        self, candles: list[Candle], swings: list[Swing], is_high: bool, direction: Direction
    ) -> POI | None:
        members = sorted(
            (s for s in swings if s.is_high == is_high and s.is_valid),
            key=lambda s: s.candle_index,
        )
        if len(members) < 2:
            return None
        tolerance = pips_to_price(EQH_EQL_TOLERANCE)

        # Most recent pair of the same side whose extremes are within tolerance.
        for index in range(len(members) - 2, -1, -1):
            first, second = members[index], members[index + 1]
            if abs(first.level - second.level) > tolerance:
                continue
            zone = self._cluster_zone(first, second, direction)
            if zone is None:
                continue
            last_index = second.candle_index
            if last_index >= len(candles) - 1:
                continue
            if direction is Direction.SHORT:
                broken = any(c.close < zone.bottom for c in candles[last_index + 1 :])
            else:
                broken = any(c.close > zone.top for c in candles[last_index + 1 :])
            if broken:
                return self._new_poi(zone)
        return None

    def _cluster_zone(
        self, first: Swing, second: Swing, direction: Direction
    ) -> Zone | None:
        """Zone = full wick union of the two member candles (V1 geometry)."""
        tops = [first.base_candle.high, second.base_candle.high, first.level, second.level]
        bottoms = [first.base_candle.low, second.base_candle.low]
        top, bottom = max(tops), min(bottoms)
        if top <= bottom:
            return None
        return Zone(top=top, bottom=bottom, direction=direction, timeframe=self.timeframe)