"""Model 1 — Origin Demand / Supply Base (R1 §5, LOCKED_DECISIONS §1).

Bullish: a §19-valid swing LOW (the origin) from which price moved away
with BOS (close beyond the prior swing high) + a bullish FVG + displacement
>= DISPLACEMENT_MIN_ATR. POI = the origin zone; buy there.
Bearish: the mirror on a valid swing HIGH with displacement down.
"""

from __future__ import annotations

from smc.config.locked_constants import DISPLACEMENT_MIN_ATR
from smc.config.model_type import ModelType
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.poi.base_model import (
    POIModel,
    atr_up_to,
    first_close_beyond,
    has_directional_fvg_after,
    most_recent_swing,
    zone_for_swing,
)

__all__ = ["M1OriginBase"]


class M1OriginBase(POIModel):
    """Origin demand (bullish) / supply (bearish) retest setup."""

    tag = ModelType.M1

    def detect(
        self,
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
    ) -> list[POI]:
        pois: list[POI] = []
        bullish = self._detect_side(candles, swings, Direction.LONG)
        bearish = self._detect_side(candles, swings, Direction.SHORT)
        if bullish is not None:
            pois.append(bullish)
        if bearish is not None:
            pois.append(bearish)
        return pois

    def _detect_side(
        self,
        candles: list[Candle],
        swings: list[Swing],
        direction: Direction,
    ) -> POI | None:
        origin = most_recent_swing(swings, is_high=(direction is Direction.SHORT))
        if origin is None or not origin.is_valid:
            return None
        i0 = origin.candle_index
        if i0 <= 0 or i0 >= len(candles) - 1:
            return None

        # Prior opposite swing = BOS reference level.
        opposite = most_recent_swing(
            swings, is_high=(direction is not Direction.SHORT), before_index=i0
        )
        if opposite is None:
            return None

        above = direction is Direction.LONG
        break_index = first_close_beyond(
            candles, i0 + 1, opposite.level, above=above
        )
        if break_index is None:
            return None

        atr = atr_up_to(candles, i0, self.atr_period)
        if atr is None:
            return None
        if not has_directional_fvg_after(candles, i0, direction, self.timeframe):
            return None

        # Displacement away from the origin (frozen 1x ATR minimum).
        if direction is Direction.LONG:
            move = max(c.high for c in candles[i0 + 1 :]) - origin.level
        else:
            move = origin.level - min(c.low for c in candles[i0 + 1 :])
        if move < DISPLACEMENT_MIN_ATR * atr:
            return None

        zone = zone_for_swing(origin, direction, self.timeframe, candles, self.atr_period)
        return self._new_poi(zone)