"""POI dataclass — zone + equal-weight model tags + freshness/quality state.

Per LOCKED_DECISIONS §1, all model tags are equal and coexist on the same
level; the quality score grows with the number of independent tags.
Freshness follows the §5 state machine (CREATED → FRESH → TESTED/VIOLATED).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from smc.config.model_type import ModelType
from smc.core.enums import POIState
from smc.core.zone import Zone

__all__ = ["POI"]


@dataclass
class POI:
    """A point of interest: a zone tagged by one or more model types."""

    zone: Zone
    models: list[ModelType] = field(default_factory=list)
    score: float = 0.0
    state: POIState = POIState.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    touch_count: int = 0
    htf_overlap: bool = False  # §21/§26: D1+H4 Demand/Supply overlap flag
    id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def model_count(self) -> int:
        return len(self.models)

    def add_model(self, model: ModelType) -> None:
        """Tag this POI with a model (equal-weight; duplicates ignored)."""
        if model not in self.models:
            self.models.append(model)