"""Validation pipeline — runs the five pillars 1→5 for one POI (R1 §6, §10).

Rules (Phase 3 prompt / LOCKED_DECISIONS):
* Pillars run in order 1 → 5.
* Pillars 1–4 are HARD gates: FAIL or UNAVAILABLE ⇒ the POI is REJECTED and
  the pipeline short-circuits on the first non-pass (no later pillar runs).
  UNAVAILABLE (no data to decide) is deliberately NOT a pass — the caller
  must not silently accept what it could not check.
* Pillar 5 (inducement) is SOFT: it never rejects and always contributes a
  score modifier (``INDUCEMENT_WITH_SCORE`` with inducement /
  ``INDUCEMENT_WITHOUT_SCORE`` without, §7 — frozen constants, no literals).
* After a successful validation the POI is ARMED (CREATED → FRESH) through
  the state machine and its confluence quality score is assigned via the
  Phase 2 ``score_poi`` when not already set (§1).

The pipeline builds a :class:`ValidationContext` per POI; the dealing range
is auto-computed from the supplied swings through the Phase 2
``compute_dealing_range`` when none is passed (callers may pre-compute and
inject it instead). Displacement must be injected as a Phase 1
``DisplacementResult`` — see ``pillar_2_displacement``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from smc.config.locked_constants import (
    INDUCEMENT_WITHOUT_SCORE,
    INDUCEMENT_WITH_SCORE,
)
from smc.core.candle import Candle
from smc.core.enums import POIState
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.detection.displacement_checker import DisplacementResult
from smc.poi.confluence_scorer import score_poi
from smc.poi.deal_range import DealingRange, compute_dealing_range
from smc.validation.pillar import Pillar, PillarResult, PillarStatus, ValidationContext
from smc.validation.pillar_1_zone_refinement import ZoneRefinementPillar
from smc.validation.pillar_2_displacement import DisplacementPillar
from smc.validation.pillar_3_premium_discount import PremiumDiscountPillar
from smc.validation.pillar_4_freshness import FreshnessPillar
from smc.validation.pillar_5_inducement import InducementPillar
from smc.validation.state_machine import POIStateMachine

__all__ = [
    "ValidationDecision",
    "ValidationPipeline",
    "ValidationResult",
    "default_pillars",
]

_HARD_PILLARS = (1, 2, 3, 4)


class ValidationDecision(Enum):
    """Final decision for one POI after the pillar run."""

    PASS = "pass"          # pillars 1–4 passed; POI armed + scored
    REJECTED = "rejected"  # a hard pillar (1–4) failed or was unavailable


@dataclass(slots=True)
class ValidationResult:
    """Outcome of a full pillar run for one POI."""

    poi: POI
    decision: ValidationDecision
    pillar_results: list[PillarResult] = field(default_factory=list)
    quality_score: float | None = None  # §1 confluence score (set on PASS)
    inducement_modifier: float = INDUCEMENT_WITH_SCORE  # Pillar 5 modifier when it ran
    detail: str = ""

    @property
    def passed(self) -> bool:
        """True when the POI passed validation."""
        return self.decision is ValidationDecision.PASS

    @property
    def first_failure(self) -> PillarResult | None:
        """The hard pillar that rejected the POI (None when passed)."""
        if self.passed:
            return None
        return next(
            (
                r
                for r in self.pillar_results
                if r.pillar in _HARD_PILLARS and not r.passed
            ),
            None,
        )


def default_pillars() -> list[Pillar]:
    """The five pillars in run order 1 → 5."""
    return [
        ZoneRefinementPillar(),
        DisplacementPillar(),
        PremiumDiscountPillar(),
        FreshnessPillar(),
        InducementPillar(),
    ]


class ValidationPipeline:
    """Runs the 1→5 pillar chain for a POI and returns the decision."""

    def __init__(
        self,
        pillars: list[Pillar] | None = None,
        state_machine: POIStateMachine | None = None,
    ) -> None:
        self.pillars = pillars if pillars is not None else default_pillars()
        self.state_machine = state_machine if state_machine is not None else POIStateMachine()

    # ------------------------------------------------------------------ #
    def validate(
        self,
        poi: POI,
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
        *,
        dealing_range: DealingRange | None = None,
        displacement: DisplacementResult | None = None,
        atr_period: int = 14,
    ) -> ValidationResult:
        """Validate one POI through the pillar chain.

        ``dealing_range`` defaults to ``compute_dealing_range(swings)``
        (Phase 2 helper) when not supplied; pass ``None``-forcing swing sets
        to exercise the Pillar 3 UNAVAILABLE path.
        """
        context = ValidationContext(
            poi=poi,
            candles=candles,
            swings=swings,
            liquidity_levels=liquidity_levels,
            dealing_range=(
                compute_dealing_range(swings)
                if dealing_range is None
                else dealing_range
            ),
            displacement=displacement,
            atr_period=atr_period,
        )
        return self.run(context)

    def run(self, context: ValidationContext) -> ValidationResult:
        """Validate the POI carried by an already-built context."""
        poi = context.poi
        results: list[PillarResult] = []

        for pillar in self.pillars:
            result = pillar.run(context)
            results.append(result)
            # Short-circuit on the first HARD (1–4) non-pass.
            if result.pillar in _HARD_PILLARS and result.status is not PillarStatus.PASS:
                return ValidationResult(
                    poi=poi,
                    decision=ValidationDecision.REJECTED,
                    pillar_results=results,
                    detail=(
                        f"rejected by Pillar {result.pillar} "
                        f"({result.name}): {result.detail}"
                    ),
                )

        # All hard pillars passed → run produced pillar 5 as well.
        inducement = next(
            (
                r
                for r in results
                if r.pillar == 5 and r.score_modifier != INDUCEMENT_WITH_SCORE
            ),
            None,
        )
        quality = self._assign_quality_score(poi)
        return ValidationResult(
            poi=poi,
            decision=ValidationDecision.PASS,
            pillar_results=results,
            quality_score=quality,
            inducement_modifier=(
                inducement.score_modifier if inducement else INDUCEMENT_WITH_SCORE
            ),
            detail="all pillars passed; POI armed and confluence-scored",
        )

    # ------------------------------------------------------------------ #
    def _assign_quality_score(self, poi: POI) -> float | None:
        """§1 confluence score via Phase 2 ``score_poi``; arms the POI.

        Scoring only applies to tag-bearing POIs (empty ``models`` has no
        meaningful score). The score is written only when not already set
        (``poi.score == 0.0`` — a tagged POI's true score is always ≥ 1).
        """
        if not poi.models:
            return None
        computed = score_poi(poi).score
        if poi.score == 0.0:
            poi.score = computed
        if poi.state is POIState.CREATED:
            self.state_machine.arm(poi)  # CREATED → FRESH (tradeable)
        return poi.score
