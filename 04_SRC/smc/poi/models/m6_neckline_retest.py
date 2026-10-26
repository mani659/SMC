"""Model 6 — Neckline / Double Top-Bottom Retest (R1 §5).

Bearish double top: high A -> neck (swing low) -> high B (B ~ A within the
frozen EQH tolerance) -> body close below the neckline -> retest of the
neckline from below. POI zone = the neck swing's range; direction SHORT.

Bullish double bottom mirrors on equal lows with the neck = swing high.
"""

from __future__ import annotations

from smc.config.locked_constants import EQH_EQL_TOLERANCE
from smc.config.model_type import ModelType
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.poi.base_model import POIModel, first_close_beyond, zone_for_swing
from smc.utils.pips import pips_to_price

__all__ = ["M6NecklineRetest"]


class M6NecklineRetest(POIModel):
    """Double top/bottom neckline retest."""

    tag = ModelType.M6

    def detect(
        self,
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
    ) -> list[POI]:
        if not candles:
            return []
        end = len(candles) - 1
        tolerance = pips_to_price(EQH_EQL_TOLERANCE)
        for index in range(len(swings) - 3, -1, -1):
            a, b, c = swings[index], swings[index + 1], swings[index + 2]
            # Bearish double top: A(high) neck(low) B(high), tops ~equal.
            if (
                a.is_high and not b.is_high and c.is_high
                and a.is_valid and b.is_valid
                and abs(a.level - c.level) <= tolerance
                and a.candle_index < b.candle_index < c.candle_index <= end
            ):
                if first_close_beyond(
                    candles, c.candle_index + 1, b.level, above=False
                ) is not None:
                    return [self._new_poi(
                        zone_for_swing(b, Direction.SHORT, self.timeframe, candles, self.atr_period)
                    )]
            # Bullish double bottom: A(low) neck(high) B(low), bottoms ~equal.
            if (
                not a.is_high and b.is_high and not c.is_high
                and a.is_valid and b.is_valid
                and abs(a.level - c.level) <= tolerance
                and a.candle_index < b.candle_index < c.candle_index <= end
            ):
                if first_close_beyond(
                    candles, c.candle_index + 1, b.level, above=True
                ) is not None:
                    return [self._new_poi(
                        zone_for_swing(b, Direction.LONG, self.timeframe, candles, self.atr_period)
                    )]
        return []