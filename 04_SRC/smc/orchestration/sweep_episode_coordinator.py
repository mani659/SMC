"""Policy-driven, closed-bar sweep episodes for multi-timeframe execution.

This module deliberately does not own trigger geometry, risk, or order
placement.  It creates a durable causal parent for a closed source sweep and
arbitrates the eligible confirmation streams before a single candidate is sent
to those existing layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterable

from smc.config.timeframe import Timeframe

__all__ = [
    "DEFAULT_SWEEP_CONFIRMATION_POLICIES",
    "ClosedSweep",
    "Confirmation",
    "EpisodeStatus",
    "SweepConfirmationPolicy",
    "SweepEpisode",
    "SweepEpisodeCoordinator",
    "SweepEpisodeKey",
]


@dataclass(frozen=True, slots=True)
class SweepConfirmationPolicy:
    """Which closed confirmation streams may resolve one source sweep."""

    source_timeframe: Timeframe
    confirmation_timeframes: tuple[Timeframe, ...]

    def __post_init__(self) -> None:
        if not self.confirmation_timeframes:
            raise ValueError("a sweep policy needs at least one confirmation timeframe")
        if len(set(self.confirmation_timeframes)) != len(self.confirmation_timeframes):
            raise ValueError("confirmation timeframes must be unique")


# Policy is data, not a collection of bespoke pipelines.  Expiry remains a
# caller-owned duration until the product owner locks each pair's value.
DEFAULT_SWEEP_CONFIRMATION_POLICIES = (
    SweepConfirmationPolicy(Timeframe.D1, (Timeframe.H1,)),
    SweepConfirmationPolicy(Timeframe.H4, (Timeframe.M5, Timeframe.M15)),
    SweepConfirmationPolicy(Timeframe.H1, (Timeframe.M1, Timeframe.M5)),
    SweepConfirmationPolicy(Timeframe.M15, (Timeframe.M1,)),
)


@dataclass(frozen=True, slots=True)
class SweepEpisodeKey:
    """Stable duplicate boundary: one source event, not one direction."""

    symbol: str
    direction: str
    source_timeframe: Timeframe
    poi_identity: str
    closed_sweep_timestamp: datetime

    def __post_init__(self) -> None:
        if not self.symbol or not self.direction or not self.poi_identity:
            raise ValueError("symbol, direction, and poi_identity are required")

    @property
    def value(self) -> str:
        return "|".join((
            self.symbol,
            self.direction,
            self.source_timeframe.name,
            self.poi_identity,
            self.closed_sweep_timestamp.isoformat(),
        ))


@dataclass(frozen=True, slots=True)
class ClosedSweep:
    """A sweep event already proven to originate from a completed source bar."""

    key: SweepEpisodeKey
    expires_at: datetime
    source_payload: Any = None

    def __post_init__(self) -> None:
        if self.expires_at <= self.key.closed_sweep_timestamp:
            raise ValueError("episode expiry must be after the closed sweep timestamp")


@dataclass(frozen=True, slots=True)
class Confirmation:
    """A route produced by the existing trigger engine on a completed LTF bar."""

    episode_id: str
    timeframe: Timeframe
    completed_at: datetime
    route_id: str
    payload: Any = None


class EpisodeStatus(str, Enum):
    ACTIVE = "active"
    WON = "won"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    RISK_CANCELLED = "risk_cancelled"
    EXECUTION_CANCELLED = "execution_cancelled"


@dataclass(slots=True)
class SweepEpisode:
    """Mutable lifecycle envelope; identity and source evidence stay immutable."""

    key: SweepEpisodeKey
    policy: SweepConfirmationPolicy
    expires_at: datetime
    source_payload: Any = None
    status: EpisodeStatus = EpisodeStatus.ACTIVE
    winner: Confirmation | None = None
    decisions: list[str] = field(default_factory=list)

    @property
    def episode_id(self) -> str:
        return self.key.value


class SweepEpisodeCoordinator:
    """Owns per-sweep identity, expiry, and cross-timeframe arbitration.

    Callers must provide only completed source/confirmation bars.  A caller
    should submit all confirmations discovered on one execution-clock tick as
    one batch through :meth:`resolve_confirmations`; that makes same-timestamp
    tie-breaks independent of feed arrival order.
    """

    def __init__(
        self,
        policies: Iterable[SweepConfirmationPolicy] = DEFAULT_SWEEP_CONFIRMATION_POLICIES,
    ) -> None:
        policy_list = tuple(policies)
        self._policies = {policy.source_timeframe: policy for policy in policy_list}
        if len(self._policies) != len(policy_list):
            raise ValueError("there may be only one policy per source timeframe")
        self._episodes: dict[str, SweepEpisode] = {}

    def create_episode(self, sweep: ClosedSweep) -> tuple[SweepEpisode, bool]:
        """Create an independent episode, or return its exact duplicate."""
        policy = self._policies.get(sweep.key.source_timeframe)
        if policy is None:
            raise ValueError(f"no sweep policy for {sweep.key.source_timeframe.name}")
        existing = self._episodes.get(sweep.key.value)
        if existing is not None:
            existing.decisions.append("duplicate_source_sweep")
            return existing, False
        episode = SweepEpisode(
            key=sweep.key,
            policy=policy,
            expires_at=sweep.expires_at,
            source_payload=sweep.source_payload,
        )
        episode.decisions.append("created")
        self._episodes[episode.episode_id] = episode
        return episode, True

    def resolve_confirmations(
        self, confirmations: Iterable[Confirmation]
    ) -> list[Confirmation]:
        """Resolve a batch of completed confirmation candidates.

        Winners are ordered by their completed timestamp.  Exact timestamp
        ties choose the lower timeframe, then the stable route id.  This is a
        deterministic batch rule and avoids allowing feed-arrival order to
        choose between M5 and M15.
        """
        ordered = sorted(
            confirmations,
            key=lambda item: (item.completed_at, item.timeframe.minutes, item.route_id),
        )
        winners: list[Confirmation] = []
        for confirmation in ordered:
            episode = self._episodes.get(confirmation.episode_id)
            if episode is None:
                continue
            if episode.status is not EpisodeStatus.ACTIVE:
                episode.decisions.append(f"ignored_{episode.status.value}")
                continue
            if confirmation.timeframe not in episode.policy.confirmation_timeframes:
                episode.decisions.append("ignored_ineligible_confirmation_tf")
                continue
            if confirmation.completed_at > episode.expires_at:
                episode.status = EpisodeStatus.EXPIRED
                episode.decisions.append("expired_before_confirmation")
                continue
            episode.winner = confirmation
            episode.status = EpisodeStatus.WON
            episode.decisions.append(
                f"won_{confirmation.timeframe.name}_{confirmation.route_id}"
            )
            winners.append(confirmation)
        return winners

    def expire(self, now: datetime) -> list[SweepEpisode]:
        """Close active episodes whose configured elapsed-time window ended."""
        expired: list[SweepEpisode] = []
        for episode in self._episodes.values():
            if episode.status is EpisodeStatus.ACTIVE and now > episode.expires_at:
                episode.status = EpisodeStatus.EXPIRED
                episode.decisions.append("expired")
                expired.append(episode)
        return expired

    def invalidate(self, episode_id: str, reason: str) -> SweepEpisode | None:
        """Close an active episode when its source thesis is no longer valid."""
        episode = self._episodes.get(episode_id)
        if episode is None or episode.status is not EpisodeStatus.ACTIVE:
            return episode
        episode.status = EpisodeStatus.INVALIDATED
        episode.decisions.append(f"invalidated_{reason}")
        return episode

    def get(self, episode_id: str) -> SweepEpisode | None:
        return self._episodes.get(episode_id)

    def episodes(self) -> tuple[SweepEpisode, ...]:
        return tuple(self._episodes.values())
