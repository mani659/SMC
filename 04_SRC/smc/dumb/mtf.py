"""DUMB-MTF sequential episode clock — diagnostic demo path only.

This is deliberately a small state machine, not another detector, trigger
router, risk engine, or order book.  Callers retain ownership of zone feeds,
closed-bar confirmation geometry, and demo execution.  The machine records the
new policy: in-zone primary first, boundary fallback only after primary expiry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from smc.config.timeframe import Timeframe

__all__ = [
    "DUMB_MTF_POLICIES",
    "DumbMtfEpisode",
    "DumbMtfEpisodeKey",
    "DumbMtfPolicy",
    "DumbMtfStatus",
    "DumbMtfStateMachine",
]


@dataclass(frozen=True, slots=True)
class DumbMtfPolicy:
    """One source family and its confirmation race with a single clock owner."""

    source_timeframe: Timeframe
    confirmation_timeframes: tuple[Timeframe, ...]
    clock_timeframe: Timeframe

    def __post_init__(self) -> None:
        if self.clock_timeframe not in self.confirmation_timeframes:
            raise ValueError("clock timeframe must be an eligible confirmation timeframe")


# Architect ruling, 2026-10-25: the finer confirmation timeframe owns the
# episode's one clock.  This avoids independent M5/M15 or M1/M5 deadlines.
DUMB_MTF_POLICIES = (
    DumbMtfPolicy(Timeframe.D1, (Timeframe.H1,), Timeframe.H1),
    DumbMtfPolicy(Timeframe.H4, (Timeframe.M5, Timeframe.M15), Timeframe.M5),
    DumbMtfPolicy(Timeframe.H1, (Timeframe.M1, Timeframe.M5), Timeframe.M1),
    DumbMtfPolicy(Timeframe.M15, (Timeframe.M1,), Timeframe.M1),
)


@dataclass(frozen=True, slots=True)
class DumbMtfEpisodeKey:
    """Distinct POI/source event identity; same direction alone never merges."""

    symbol: str
    direction: str
    source_timeframe: Timeframe
    poi_id: str
    source_event_id: str

    @property
    def value(self) -> str:
        return "|".join((self.symbol, self.direction, self.source_timeframe.name,
                         self.poi_id, self.source_event_id))


class DumbMtfStatus(str, Enum):
    IN_ZONE_PRIMARY = "IN_ZONE_PRIMARY"
    BOUNDARY_FALLBACK = "BOUNDARY_FALLBACK"
    EXPIRED_NO_ENTRY = "EXPIRED_NO_ENTRY"
    EXPIRED_SWEEP_TIMEOUT = "EXPIRED_SWEEP_TIMEOUT"
    INVALIDATED_STRUCTURE = "INVALIDATED_STRUCTURE"
    WON = "WON"


@dataclass(slots=True)
class DumbMtfEpisode:
    key: DumbMtfEpisodeKey
    policy: DumbMtfPolicy
    zone_entry_clock_bar: int
    status: DumbMtfStatus = DumbMtfStatus.IN_ZONE_PRIMARY
    sweep_clock_bar: int | None = None
    winner_route_id: str | None = None
    winner_timeframe: Timeframe | None = None
    history: list[str] = field(default_factory=lambda: ["IN_ZONE_PRIMARY"])

    @property
    def episode_id(self) -> str:
        return self.key.value


class DumbMtfStateMachine:
    """Enforces the provisional 6/16-bar sequential clock ruling.

    The caller supplies monotonically increasing *closed-bar indexes* for the
    policy clock timeframe.  A confirmation at exactly ``start + limit`` is
    eligible; expiry occurs only when the next clock bar arrives.  This
    matches the existing DUMB inclusive expiry convention.
    """

    PRIMARY_BARS = 6
    FALLBACK_BARS = 16

    def __init__(self, policies: Iterable[DumbMtfPolicy] = DUMB_MTF_POLICIES) -> None:
        policy_list = tuple(policies)
        self._policies = {p.source_timeframe: p for p in policy_list}
        if len(policy_list) != len(self._policies):
            raise ValueError("one policy per source timeframe is required")
        self._episodes: dict[str, DumbMtfEpisode] = {}

    def start_primary(self, key: DumbMtfEpisodeKey, clock_bar: int) -> tuple[DumbMtfEpisode, bool]:
        """Open a primary episode at first POI-zone penetration/touch."""
        policy = self._policies.get(key.source_timeframe)
        if policy is None:
            raise ValueError(f"no DUMB-MTF policy for {key.source_timeframe.name}")
        existing = self._episodes.get(key.value)
        if existing is not None:
            existing.history.append("duplicate_primary_ignored")
            return existing, False
        episode = DumbMtfEpisode(key=key, policy=policy, zone_entry_clock_bar=clock_bar)
        self._episodes[episode.episode_id] = episode
        return episode, True

    def advance_clock(self, timeframe: Timeframe, closed_bar: int) -> list[DumbMtfEpisode]:
        """Apply inclusive primary/fallback expiry on one closed clock bar."""
        changed: list[DumbMtfEpisode] = []
        for episode in self._episodes.values():
            if episode.policy.clock_timeframe is not timeframe:
                continue
            if episode.status is DumbMtfStatus.IN_ZONE_PRIMARY:
                if closed_bar > episode.zone_entry_clock_bar + self.PRIMARY_BARS:
                    episode.status = DumbMtfStatus.BOUNDARY_FALLBACK
                    episode.history.append("EXPIRED_NO_ENTRY")
                    changed.append(episode)
            elif (
                episode.status is DumbMtfStatus.BOUNDARY_FALLBACK
                and episode.sweep_clock_bar is not None
                and closed_bar > episode.sweep_clock_bar + self.FALLBACK_BARS
            ):
                episode.status = DumbMtfStatus.EXPIRED_SWEEP_TIMEOUT
                episode.history.append("EXPIRED_SWEEP_TIMEOUT")
                changed.append(episode)
        return changed

    def record_boundary_sweep(self, episode_id: str, clock_bar: int) -> DumbMtfEpisode | None:
        """Arm fallback only after primary expiry; never in parallel."""
        episode = self._episodes.get(episode_id)
        if episode is None or episode.status is not DumbMtfStatus.BOUNDARY_FALLBACK:
            return episode
        if episode.sweep_clock_bar is None:
            episode.sweep_clock_bar = clock_bar
            episode.history.append("BOUNDARY_FALLBACK")
        return episode

    def confirm(self, episode_id: str, timeframe: Timeframe, route_id: str) -> DumbMtfEpisode | None:
        """Make the first eligible closed-stream route the one episode winner."""
        episode = self._episodes.get(episode_id)
        if episode is None or episode.status not in (
            DumbMtfStatus.IN_ZONE_PRIMARY,
            DumbMtfStatus.BOUNDARY_FALLBACK,
        ):
            return episode
        if timeframe not in episode.policy.confirmation_timeframes:
            episode.history.append("ineligible_confirmation_ignored")
            return episode
        if episode.status is DumbMtfStatus.BOUNDARY_FALLBACK and episode.sweep_clock_bar is None:
            episode.history.append("fallback_confirmation_before_sweep_ignored")
            return episode
        episode.status = DumbMtfStatus.WON
        episode.winner_timeframe = timeframe
        episode.winner_route_id = route_id
        episode.history.append(f"WON_{timeframe.name}_{route_id}")
        return episode

    def invalidate(self, episode_id: str, reason: str) -> DumbMtfEpisode | None:
        episode = self._episodes.get(episode_id)
        if episode is not None and episode.status in (
            DumbMtfStatus.IN_ZONE_PRIMARY,
            DumbMtfStatus.BOUNDARY_FALLBACK,
        ):
            episode.status = DumbMtfStatus.INVALIDATED_STRUCTURE
            episode.history.append(f"INVALIDATED_STRUCTURE_{reason}")
        return episode

    def get(self, episode_id: str) -> DumbMtfEpisode | None:
        return self._episodes.get(episode_id)
