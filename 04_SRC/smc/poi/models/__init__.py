"""The eight equal POI model detectors (M1–M8)."""

from smc.poi.models.m1_origin_base import M1OriginBase
from smc.poi.models.m2_rbs_sbr_breaker import M2RbsSbrBreaker
from smc.poi.models.m3_choch_retest import M3ChochRetest
from smc.poi.models.m4_quasimodo import M4Quasimodo
from smc.poi.models.m5_extreme_equal_highs import M5ExtremeEqualHighs
from smc.poi.models.m6_neckline_retest import M6NecklineRetest
from smc.poi.models.m7_equal_resistance import M7EqualResistance
from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply

__all__ = [
    "M1OriginBase",
    "M2RbsSbrBreaker",
    "M3ChochRetest",
    "M4Quasimodo",
    "M5ExtremeEqualHighs",
    "M6NecklineRetest",
    "M7EqualResistance",
    "M8HtfDemandSupply",
]