"""Core enums: TriggerType, LiquidityType, POIState, Direction, PoolType.

All values are anchored to LOCKED_DECISIONS.md sections (§2, §5, §12, §24).
"""

from __future__ import annotations

from enum import Enum

__all__ = ["TriggerType", "LiquidityType", "POIState", "Direction", "PoolType"]


class TriggerType(Enum):
    """LTF entry triggers A–F (§12, §24). Chronological first-valid wins."""

    A_CHOCH = "A"                  # CHOCH Reversal
    B_LEADING_DIAGONAL = "B"       # Leading Diagonal
    C_ENDING_DIAGONAL = "C"        # Ending Diagonal (preferred for Model 8)
    D_TWO_BAR_REVERSAL = "D"       # Two-Bar Reversal
    E_RSI_DIVERGENCE = "E"         # RSI Divergence
    F_BOS_OB = "F"                 # BOS + OB Continuation


class LiquidityType(Enum):
    """The 8 valid Stage 0A liquidity level types (§2 Master Classification)."""

    SESSION = "session"                    # Asia / London / NY session H/L
    PREVIOUS_DAY = "previous_day"          # PDH / PDL
    PREVIOUS_WEEK = "previous_week"        # PWH / PWL
    EQUAL_HIGHS_LOWS = "equal_highs_lows"  # EQH / EQL (≤ 4.5 pip tolerance)
    STRUCTURAL_SWING = "structural_swing"  # Base-Candle-confirmed swing H/L
    POI_LEVEL = "poi_level"                # POI Order Block / FVG boundary sweep
    DEMAND_SUPPLY_BOUNDARY = "demand_supply_boundary"  # HTF D/S zone extreme sweep
    ORDER_BLOCK_BOUNDARY = "order_block_boundary"      # OB extreme wick sweep


class POIState(Enum):
    """POI freshness state machine (§5). TESTED and VIOLATED are terminal."""

    CREATED = "created"
    FRESH = "fresh"
    TESTED = "tested"      # touched → deactivated forever (1-touch rule)
    VIOLATED = "violated"  # closed beyond without touching


class Direction(Enum):
    """Trade / zone direction."""

    LONG = "long"
    SHORT = "short"


class PoolType(Enum):
    """Directional liquidity pool (§2 "Directional Pool" column).

    BSL/SSL are the buy-side / sell-side stop pools; the remaining values
    are the special-purpose pools defined for the fallback sweep types.
    """

    BSL = "bsl"                  # Buy-side liquidity (above highs)
    SSL = "ssl"                  # Sell-side liquidity (below lows)
    MAJOR_STRUCTURAL = "major_structural"  # Structural swing BSL/SSL
    POI = "poi"                  # POI liquidity pool (OB & FVG)
    EXTREME_ZONE = "extreme_zone"  # Demand & Supply boundary
    OB_EXTREME = "ob_extreme"    # Order Block boundary extreme