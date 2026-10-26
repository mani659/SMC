"""Model 3 — CHOCH Baseline Retest (R1 §5, LOCKED_DECISIONS §9/§17/§20).

Consumes the CHOCH Rule 1/2/3 classification at the last bar and emits a
POI at the broken level per §9/§20:

  Rule 1 (standard)   -> broken last swing of the main trend
  Rule 2 (inside body)-> broken intermediate level (last swing intact)
  Rule 3 (inside wick)-> wick-pierced level (weakest, KEPT)

Sub-variants 3a/3b/3c share the single ModelType.M3 equal tag (§1); the
specific rule is available through the classifier for research logging.
"""

from __future__ import annotations

from smc.config.model_type import ModelType
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.poi.base_model import POIModel, zone_for_level, zone_for_swing
from smc.poi.choch_classifier import ChochRule, classify_choch_at

__all__ = ["M3ChochRetest"]


class M3ChochRetest(POIModel):
    """Retest POI at the broken level after a CHOCH (rules 1/2/3)."""

    tag = ModelType.M3

    def detect(
        self,
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
    ) -> list[POI]:
        if not candles:
            return []
        ch = classify_choch_at(candles, swings)
        if ch is None:
            return []

        if ch.direction is Direction.SHORT:
            matches = [s for s in swings if not s.is_high and s.level == ch.broken_level]
        else:
            matches = [s for s in swings if s.is_high and s.level == ch.broken_level]
        match = max(matches, key=lambda s: s.candle_index, default=None)
        if match is not None:
            zone = zone_for_swing(match, ch.direction, self.timeframe, candles, self.atr_period)
        else:
            zone = zone_for_level(
                ch.broken_level, ch.direction, self.timeframe, candles, len(candles) - 1,
                self.atr_period,
            )
        return [self._new_poi(zone)]