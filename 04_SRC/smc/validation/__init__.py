"""Phase 3: 5-Pillar Validation — refinement, displacement, P/D, freshness, inducement.

Stage 2 per LOCKED_DECISIONS §3/§5/§6/§7/§13 and R1 §6. Pillars 1–4 are hard
gates (run 1→5, short-circuit on first non-pass); Pillar 5 (inducement) is
soft (100% with inducement / 70% without, never a rejection). The pipeline
arms validated POIs (CREATED → FRESH) and assigns the §1 confluence quality
score via ``smc.poi.confluence_scorer.score_poi``.
"""

from smc.validation.pillar import (
    Pillar,
    PillarResult,
    PillarStatus,
    ValidationContext,
)
from smc.validation.pillar_1_zone_refinement import ZoneRefinementPillar
from smc.validation.pillar_2_displacement import DisplacementPillar
from smc.validation.pillar_3_premium_discount import PremiumDiscountPillar
from smc.validation.pillar_4_freshness import FreshnessPillar
from smc.validation.pillar_5_inducement import InducementPillar
from smc.validation.state_machine import (
    IllegalTransitionError,
    POIStateMachine,
    expiry_bars_for,
)
from smc.validation.validation_pipeline import (
    ValidationDecision,
    ValidationPipeline,
    ValidationResult,
    default_pillars,
)

__all__ = [
    "DisplacementPillar",
    "FreshnessPillar",
    "IllegalTransitionError",
    "InducementPillar",
    "POIStateMachine",
    "Pillar",
    "PillarResult",
    "PillarStatus",
    "PremiumDiscountPillar",
    "ValidationContext",
    "ValidationDecision",
    "ValidationPipeline",
    "ValidationResult",
    "ZoneRefinementPillar",
    "default_pillars",
    "expiry_bars_for",
]
