"""Model 7 — Equal Resistance Shelf Retest (R1 §5, LOCKED_DECISIONS §8).

REACTIVE shelf setup: after a sharp drop from a higher high, a single bounce
creates a resistance shelf (swing high), price then breaks BELOW the
bounce-origin low, and the retest of the shelf becomes the POI.

* Bearish: earlier high X > shelf B > low A; close below A after B.
* Bullish: earlier low X < shelf B(low) < high A; close above A after B.

Distinct from Model 5 (proactive equal extremes): M7 is one reactive shelf
formed by a bounce, not two equal extremes.
"""

from __future__ import annotations

from smc.config.model_type import ModelType
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.poi.base_model import POIModel, first_close_beyond, zone_for_swing

__all__ = ["M7EqualResistance"]


class M7EqualResistance(POIModel):
    """Reactive bounce-shelf retest after an expansion (§8)."""

    tag = ModelType.M7

    def detect(
        self,
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
    ) -> list[POI]:
        if not candles:
            return []
        end = len(candles) - 1
        for index in range(len(swings) - 2, -1, -1):
            a, b = swings[index], swings[index + 1]
            if not (a.is_valid and b.is_valid):
                continue
            # Bearish: a = bounce-origin LOW, b = reactive shelf HIGH above it.
            if (
                not a.is_high and b.is_high
                and b.level > a.level
                and a.candle_index < b.candle_index <= end
                and self._has_earlier_high_above(swings, a.candle_index, b.level)
            ):
                if first_close_beyond(
                    candles, b.candle_index + 1, a.level, above=False
                ) is not None:
                    return [self._new_poi(
                        zone_for_swing(b, Direction.SHORT, self.timeframe, candles, self.atr_period)
                    )]
            # Bullish: a = rally high, b = pullback support shelf LOW below it.
            if (
                a.is_high and not b.is_high
                and b.level < a.level
                and a.candle_index < b.candle_index <= end
                and self._has_earlier_low_below(swings, a.candle_index, b.level)
            ):
                if first_close_beyond(
                    candles, b.candle_index + 1, a.level, above=True
                ) is not None:
                    return [self._new_poi(
                        zone_for_swing(b, Direction.LONG, self.timeframe, candles, self.atr_period)
                    )]
        return []

    @staticmethod
    def _has_earlier_high_above(swings: list[Swing], before: int, level: float) -> bool:
        """The sharp drop must come from an earlier high above the shelf."""
        return any(
            s.is_high and s.candle_index < before and s.level > level for s in swings
        )

    @staticmethod
    def _has_earlier_low_below(swings: list[Swing], before: int, level: float) -> bool:
        """The rally must start from an earlier low below the support shelf."""
        return any(
            not s.is_high and s.candle_index < before and s.level < level for s in swings
        )