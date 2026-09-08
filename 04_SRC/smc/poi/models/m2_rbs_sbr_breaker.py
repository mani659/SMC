"""Model 2 — RBS / SBR Breaker Flip (R1 §5, LOCKED_DECISIONS §1).

Bullish RBS: a swing HIGH is broken ABOVE by body close -> retest of the
broken level from above (buy the flip). Bearish SBR: a swing LOW is broken
BELOW by body close -> retest from below (sell the flip). Both sides use
the most recent qualifying structural swing of each side.
"""

from __future__ import annotations

from smc.config.model_type import ModelType
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.poi.base_model import POIModel, first_close_beyond, most_recent_swing, zone_for_swing

__all__ = ["M2RbsSbrBreaker"]


class M2RbsSbrBreaker(POIModel):
    """Broken-level flip retest (RBS buy / SBR sell)."""

    tag = ModelType.M2

    def detect(
        self,
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
    ) -> list[POI]:
        pois: list[POI] = []
        # Bullish RBS: break ABOVE the most recent valid swing high.
        high = most_recent_swing(swings, is_high=True)
        if high is not None and high.is_valid and high.candle_index < len(candles) - 1:
            if first_close_beyond(candles, high.candle_index + 1, high.level, above=True) is not None:
                pois.append(
                    self._new_poi(
                        zone_for_swing(high, Direction.LONG, self.timeframe, candles, self.atr_period)
                    )
                )
        # Bearish SBR: break BELOW the most recent valid swing low.
        low = most_recent_swing(swings, is_high=False)
        if low is not None and low.is_valid and low.candle_index < len(candles) - 1:
            if first_close_beyond(candles, low.candle_index + 1, low.level, above=False) is not None:
                pois.append(
                    self._new_poi(
                        zone_for_swing(low, Direction.SHORT, self.timeframe, candles, self.atr_period)
                    )
                )
        return pois