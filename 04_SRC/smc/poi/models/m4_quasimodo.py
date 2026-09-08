"""Model 4 — Quasimodo Level / QML (R1 §5, LOCKED_DECISIONS §14).

Bearish QML: Left Shoulder high -> neck (swing low) -> Head (higher high) ->
body close below the neckline -> retest of the LEFT SHOULDER level. The POI
zone is the FULL WICK RANGE of the left shoulder [LS low, LS high] (§14).

Bullish QML mirrors on lows: Left Shoulder low -> neck (swing high) -> Head
(lower low) -> body close above the neckline -> retest of the left shoulder.
"""

from __future__ import annotations

from smc.config.model_type import ModelType
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.poi.base_model import POIModel, first_close_beyond, zone_for_swing

__all__ = ["M4Quasimodo"]


class M4Quasimodo(POIModel):
    """Quasimodo reversal at the left-shoulder full-wick range (§14)."""

    tag = ModelType.M4

    def detect(
        self,
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
    ) -> list[POI]:
        if not candles:
            return []
        end = len(candles) - 1
        for index in range(len(swings) - 3, -1, -1):
            a, b, c = swings[index], swings[index + 1], swings[index + 2]
            # Bearish: LS(high), neck(low), head(higher high).
            if (
                a.is_high and not b.is_high and c.is_high
                and a.is_valid and b.is_valid
                and c.level > a.level
                and a.candle_index < b.candle_index < c.candle_index <= end
            ):
                if first_close_beyond(
                    candles, c.candle_index + 1, b.level, above=False
                ) is not None:
                    zone = zone_for_swing(a, Direction.SHORT, self.timeframe, candles, self.atr_period)
                    return [self._new_poi(zone)]
            # Bullish: LS(low), neck(high), head(lower low).
            if (
                not a.is_high and b.is_high and not c.is_high
                and a.is_valid and b.is_valid
                and c.level < a.level
                and a.candle_index < b.candle_index < c.candle_index <= end
            ):
                if first_close_beyond(
                    candles, c.candle_index + 1, b.level, above=True
                ) is not None:
                    zone = zone_for_swing(a, Direction.LONG, self.timeframe, candles, self.atr_period)
                    return [self._new_poi(zone)]
        return []