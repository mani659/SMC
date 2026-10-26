"""Phase 2: POI Classification — M1–M8 modular tags, confluence, CHOCH.

Stage 1/1b implementations per LOCKED_DECISIONS §1/§4/§8/§9/§17/§20-§22/§26.
All eight models are EQUAL tags; no model suppresses or overrides another.
"""

from smc.poi.base_model import POIModel
from smc.poi.choch_classifier import ChochBreak, ChochRule, classify_choch_at
from smc.poi.confluence_scorer import (
    ConfluenceScore,
    ConfluenceTier,
    merge_overlapping,
    quality_tier,
    score_poi,
)
from smc.poi.deal_range import (
    DealRangeRegion,
    DealingRange,
    classify_region,
    compute_dealing_range,
    range_position,
)
from smc.poi.model_registry import ModelRegistry, build_registry

__all__ = [
    "ChochBreak",
    "ChochRule",
    "ConfluenceScore",
    "ConfluenceTier",
    "DealRangeRegion",
    "DealingRange",
    "ModelRegistry",
    "POIModel",
    "build_registry",
    "classify_choch_at",
    "classify_region",
    "compute_dealing_range",
    "merge_overlapping",
    "quality_tier",
    "range_position",
    "score_poi",
]