"""Pillar 3 — Premium / Discount (§6, R1 §6 Pillar 3).

The dealing range is COUPLED to the POI detection timeframe (§6). The zone
position of a bullish POI must be in the DISCOUNT region (< 45% of the
range); a bearish POI must be in the PREMIUM region (> 55%). The 45–55%
equilibrium band is REJECTED.

OWNERSHIP BOUNDARY (audit 2026-09-07): this pillar is the SOLE owner of the
§6 45%/55% hard reject. ``deal_range.py`` only classifies the region
(``classify_region``); this pillar applies the direction-specific
pass/fail. When ``compute_dealing_range()`` returns ``None`` the pillar is
UNAVAILABLE — never a silent pass.

V1 rule: the POI price level is the zone midpoint.
"""

from __future__ import annotations

from smc.core.enums import Direction
from smc.poi.deal_range import DealRangeRegion, classify_region
from smc.validation.pillar import Pillar, PillarResult, PillarStatus, ValidationContext

__all__ = ["PremiumDiscountPillar"]


class PremiumDiscountPillar(Pillar):
    """§6 dealing-range gate: buy in discount (<45%), sell in premium (>55%)."""

    number = 3
    name = "premium_discount"

    def run(self, context: ValidationContext) -> PillarResult:
        dealing_range = context.dealing_range
        if dealing_range is None:
            return PillarResult(
                pillar=self.number,
                name=self.name,
                status=PillarStatus.UNAVAILABLE,
                detail=(
                    "no confirmed dealing range on the POI detection "
                    "timeframe (compute_dealing_range returned None)"
                ),
            )

        level = context.poi.zone.midpoint
        region = classify_region(level, dealing_range)
        data = {
            "level": level,
            "range_high": dealing_range.high,
            "range_low": dealing_range.low,
            "region": region.value,
        }
        direction = context.poi.zone.direction
        if direction is Direction.LONG and region is DealRangeRegion.DISCOUNT:
            return self._pass(data)
        if direction is Direction.SHORT and region is DealRangeRegion.PREMIUM:
            return self._pass(data)

        reason = f"POI {direction.value} in {region.value} region of the dealing range"
        return PillarResult(
            pillar=self.number,
            name=self.name,
            status=PillarStatus.FAIL,
            detail=reason,
            data=data,
        )

    def _pass(self, data: dict) -> PillarResult:
        return PillarResult(
            pillar=self.number,
            name=self.name,
            status=PillarStatus.PASS,
            detail="POI is on the correct side of the dealing range",
            data=data,
        )
