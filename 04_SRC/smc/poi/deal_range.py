"""Dealing range + premium/discount classification (LOCKED_DECISIONS §6, R1 §3.4).

Dealing range (R1 §3.4, V1 update semantics documented):
    Range High = most recent §19-VALID structural swing high level
    Range Low  = most recent §19-VALID structural swing low level
    (both within the caller-supplied swing list/window).

If the recent high/low pair is unusable (high <= low, or one side missing),
fall back to the highest valid swing high and lowest valid swing low in the
window (window extremes). If still unusable -> ``None`` (no confirmed range).

Position within the range and the premium/discount/equilibrium regions use
the FROZEN thresholds: DISCOUNT_THRESHOLD (0.45), PREMIUM_THRESHOLD (0.55),
with 0.45-0.55 = EQUILIBRIUM (reject band). The actual §6 PASS/FAIL gate
runs in Phase 3 (Pillar 3); this module only computes + classifies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from smc.config.locked_constants import DISCOUNT_THRESHOLD, PREMIUM_THRESHOLD
from smc.core.swing import Swing

__all__ = [
    "DealRangeRegion",
    "DealingRange",
    "compute_dealing_range",
    "range_position",
    "classify_region",
]


class DealRangeRegion(Enum):
    """Position of a price within the dealing range (§6)."""

    DISCOUNT = "discount"      # < 45%  (bullish POIs belong here)
    PREMIUM = "premium"        # > 55%  (bearish POIs belong here)
    EQUILIBRIUM = "equilibrium"  # 45-55% (REJECT band — consolidation trap)


@dataclass(frozen=True, slots=True)
class DealingRange:
    """A confirmed dealing range on the POI detection timeframe."""

    high: float
    low: float
    high_index: int  # candle index of the range-high swing
    low_index: int   # candle index of the range-low swing

    @property
    def height(self) -> float:
        return self.high - self.low


def compute_dealing_range(swings: list[Swing]) -> DealingRange | None:
    """Dealing range from §19-valid structural swings (R1 §3.4 V1).

    Returns ``None`` when no usable confirmed range exists in the window.
    """
    valid_highs = [s for s in swings if s.is_high and s.is_valid]
    valid_lows = [s for s in swings if not s.is_high and s.is_valid]
    if not valid_highs or not valid_lows:
        return None

    recent_high = max(valid_highs, key=lambda s: s.candle_index)
    recent_low = max(valid_lows, key=lambda s: s.candle_index)
    if recent_high.level > recent_low.level:
        return DealingRange(
            high=recent_high.level,
            low=recent_low.level,
            high_index=recent_high.candle_index,
            low_index=recent_low.candle_index,
        )

    # Fallback: window extremes (documented V1).
    highest = max(valid_highs, key=lambda s: s.level)
    lowest = min(valid_lows, key=lambda s: s.level)
    if highest.level <= lowest.level:
        return None
    return DealingRange(
        high=highest.level,
        low=lowest.level,
        high_index=highest.candle_index,
        low_index=lowest.candle_index,
    )


def range_position(price: float, dealing_range: DealingRange) -> float:
    """Relative position of ``price`` inside the range: 0.0 at low, 1.0 at high."""
    return (price - dealing_range.low) / dealing_range.height


def classify_region(price: float, dealing_range: DealingRange) -> DealRangeRegion:
    """Classify a price into PREMIUM / DISCOUNT / EQUILIBRIUM (§6 thresholds)."""
    position = range_position(price, dealing_range)
    if position < DISCOUNT_THRESHOLD:
        return DealRangeRegion.DISCOUNT
    if position > PREMIUM_THRESHOLD:
        return DealRangeRegion.PREMIUM
    return DealRangeRegion.EQUILIBRIUM