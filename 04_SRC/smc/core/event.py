"""Event dataclass — the shared event envelope for the pipeline/backtest bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

__all__ = ["Event"]


@dataclass(frozen=True, slots=True)
class Event:
    """One domain event.

    ``type`` is a short string identifier (e.g. ``"bar_closed"``,
    ``"swing_confirmed"``, ``"poi_created"``). The event-bus contract is
    designed in Phase 6 (backtest: in-process bus; live: Redis Streams).
    """

    type: str
    timestamp: datetime
    payload: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))