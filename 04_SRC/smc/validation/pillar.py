"""Pillar contract + shared result/context types (Phase 3, R1 §6).

The five POI validation pillars are run in order 1→5 by the validation
pipeline. Pillars 1–4 are HARD gates (FAIL or UNAVAILABLE ⇒ POI rejected);
Pillar 5 (inducement) is SOFT — it never rejects, it only contributes a
score modifier (1.0 with inducement / 0.7 without, §7).

A :class:`ValidationContext` is the single input each pillar consumes; the
pipeline builds one per POI. Everything a pillar may need (candles, swings,
liquidity levels, the pre-computed dealing range / displacement result) is
passed in — pillars never reach for data the caller did not supply.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from smc.core.candle import Candle
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.detection.displacement_checker import DisplacementResult
from smc.poi.deal_range import DealingRange

__all__ = [
    "Pillar",
    "PillarResult",
    "PillarStatus",
    "ValidationContext",
]


class PillarStatus(Enum):
    """Outcome of one pillar evaluation (R1 §6 vocabulary)."""

    PASS = "pass"              # pillar requirement satisfied
    FAIL = "fail"              # pillar requirement NOT satisfied
    UNAVAILABLE = "unavailable"  # cannot be evaluated (no data / no context)


@dataclass(frozen=True, slots=True)
class PillarResult:
    """Outcome of one pillar for one POI.

    ``score_modifier`` is 1.0 for every pillar except Pillar 5, which
    returns 0.7 when no inducement structure is present (§7 — soft only,
    never a rejection).
    """

    pillar: int
    name: str
    status: PillarStatus
    detail: str = ""
    score_modifier: float = 1.0
    data: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """True when the pillar PASSED (UNAVAILABLE is not a pass)."""
        return self.status is PillarStatus.PASS


@dataclass(slots=True)
class ValidationContext:
    """Everything the five pillars may need to validate one POI.

    ``candles`` must be the POI detection-timeframe series (the zone's own
    timeframe). ``swings`` and ``liquidity_levels`` are Phase 1/0 outputs on
    that same timeframe. ``dealing_range`` (Phase 2 helper output) and
    ``displacement`` (Phase 1 ``check_displacement`` output) are pre-computed
    by the caller so pillars reuse detector results instead of re-computing
    blindly; the pipeline auto-computes the dealing range from ``swings``
    when none is supplied.
    """

    poi: POI
    candles: list[Candle]
    swings: list[Swing]
    liquidity_levels: list[LiquidityLevel]
    dealing_range: DealingRange | None = None
    displacement: DisplacementResult | None = None
    atr_period: int = 14


class Pillar(ABC):
    """Abstract base for all five validation pillars.

    Subclasses declare a 1-based ``number`` and a short ``name`` and
    implement :meth:`run`. Instances are stateless — all inputs arrive via
    the context, so pillars can be shared/reused across POIs.
    """

    number: int
    name: str

    @abstractmethod
    def run(self, context: ValidationContext) -> PillarResult:
        """Evaluate one pillar against the context and return its result.

        Pillars 1–4 return PASS / FAIL / UNAVAILABLE; Pillar 5 always
        returns PASS or FAIL (soft) and never rejects.
        """
        raise NotImplementedError
