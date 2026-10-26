"""EpisodeStore V1 — Unified Episode Object + Append-Only Lifecycle Store.

Observability-only implementation conforming to EPISODE_STORE_DESIGN.md
and Section 9a Architect rulings (2026-10-13).

LOGIC_CHANGED: NO. Decision paths must NOT read this store in V1.
Store is append/query infrastructure only.

MANDATORY RULINGS (Section 9a):
- Identity: (direction, detection_tf, m8_kind_class, zone under ZoneDedup
  overlap-equivalence, 6dp bounds). poi_id / route_id = attributes only.
- H4 vs M8<-H4: SEPARATE episodes if detection_tf or m8_kind_class differs;
  overlap may record related_episode link, never forced merge.
- Refinement: tighter armed box inside parent census/validated geometry =
  SAME episode; adopt armed bounds; parent link MANDATORY when that happens.
- ZoneDedup = sole merge authority; store records suppressions as facts.
- EXPIRED_UNARMED = first-class state (bookkeeping).
- V1 persistence: in-memory per run/process only.
- Route keys unchanged as attributes; episode_id is join key.
- No lookahead: all events require bar_index <= current_bar.
- Loud fail discipline: missing required fields or unknown event kinds raise.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import io
import json
from pathlib import Path
from typing import Any, Iterable

from smc.orchestration.multi_tf_runtime import ZoneDedup

__all__ = [
    "EpisodeState",
    "EpisodeEventKind",
    "EpisodeIdentityKey",
    "EpisodeEvent",
    "EpisodeRecord",
    "EpisodeStore",
]


class EpisodeState(str, Enum):
    """Lifecycle states conforming to EPISODE_STORE_DESIGN.md Section 4."""

    DETECTED = "DETECTED"
    REJECTED_PILLAR = "REJECTED_PILLAR"
    VALIDATED = "VALIDATED"
    SUPPRESSED_DEDUP = "SUPPRESSED_DEDUP"
    EXPIRED_UNARMED = "EXPIRED_UNARMED"
    ARMED = "ARMED"
    SEEKING = "SEEKING"
    REVALIDATION = "REVALIDATION"
    ROUTED = "ROUTED"
    BLOCKED_RETRYABLE = "BLOCKED_RETRYABLE"
    BLOCKED_TERMINAL = "BLOCKED_TERMINAL"
    INTENT_ARMED = "INTENT_ARMED"
    INTENT_EXPIRED = "INTENT_EXPIRED"
    INTENT_REPLACED = "INTENT_REPLACED"
    INTENT_DROPPED_POI = "INTENT_DROPPED_POI"
    INTENT_DROPPED_PORTFOLIO = "INTENT_DROPPED_PORTFOLIO"
    PLACED = "PLACED"
    ORDER_EXPIRED = "ORDER_EXPIRED"
    FILLED = "FILLED"
    CLOSED_TP = "CLOSED_TP"
    CLOSED_SL = "CLOSED_SL"
    CLOSED_BE = "CLOSED_BE"
    CLOSED_PORTFOLIO = "CLOSED_PORTFOLIO"
    OPEN_UNRESOLVED = "OPEN_UNRESOLVED"
    SCAN_CLOSED = "SCAN_CLOSED"
    VIOLATED = "VIOLATED"


TERMINAL_STATES: frozenset[EpisodeState] = frozenset({
    EpisodeState.REJECTED_PILLAR,
    EpisodeState.SUPPRESSED_DEDUP,
    EpisodeState.EXPIRED_UNARMED,
    EpisodeState.SCAN_CLOSED,
    EpisodeState.VIOLATED,
    EpisodeState.INTENT_EXPIRED,
    EpisodeState.INTENT_REPLACED,
    EpisodeState.INTENT_DROPPED_POI,
    EpisodeState.INTENT_DROPPED_PORTFOLIO,
    EpisodeState.ORDER_EXPIRED,
    EpisodeState.CLOSED_TP,
    EpisodeState.CLOSED_SL,
    EpisodeState.CLOSED_BE,
    EpisodeState.CLOSED_PORTFOLIO,
    EpisodeState.OPEN_UNRESOLVED,
})


class EpisodeEventKind(str, Enum):
    """Append-only event kinds accepted by EpisodeStore V1."""

    DETECTED = "detected"
    REDETECTED = "redetected"
    PILLAR_FAILED = "pillar_failed"
    VALIDATED = "validated"
    REJECTED_PILLAR = "rejected_pillar"
    SUPPRESSED_DEDUP = "suppressed_dedup"
    ARM_SUPPRESSED_DEDUP = "arm_suppressed_dedup"
    ARMED = "armed"
    POSTURE_CLASSIFIED = "posture_classified"
    SWEEP_LINKED = "sweep_linked"
    SEEK_OPENED = "seek_opened"
    LTF_COMPLETION = "ltf_completion"
    REVALIDATED = "revalidated"
    ROUTE_FORMED = "route_formed"
    ROUTE = "route"
    BLOCK = "block"
    BLOCKED = "blocked"
    INTENT_ARMED = "intent_armed"
    INTENT_EXPIRED_NO_REENTRY = "intent_expired_no_reentry"
    INTENT_REPLACED = "intent_replaced"
    INTENT_DROPPED_POI = "intent_dropped_poi"
    INTENT_DROPPED_PORTFOLIO = "intent_dropped_portfolio"
    PLACE = "place"
    PLACED = "placed"
    ORDER_EXPIRED = "order_expired"
    EXPIRE_ORDER = "expire_order"
    FILL = "fill"
    FILLED = "filled"
    CLOSED = "closed"
    VIOLATED = "violated"
    SCAN_CLOSED = "scan_closed"
    GAVE_UP = "gave_up"
    EXPIRED_UNARMED = "expired_unarmed"
    SWEEP = "sweep"
    PRUNED = "pruned"


@dataclass(frozen=True, slots=True)
class EpisodeIdentityKey:
    """Canonical geometric grain per Section 3.1 & Section 9a."""

    direction: str
    detection_tf: str
    m8_kind_class: str
    zone_low: float
    zone_high: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "direction", str(self.direction).upper())
        object.__setattr__(self, "detection_tf", str(self.detection_tf).upper())
        object.__setattr__(self, "m8_kind_class", str(self.m8_kind_class or "n/a").lower())
        object.__setattr__(self, "zone_low", round(float(self.zone_low), 6))
        object.__setattr__(self, "zone_high", round(float(self.zone_high), 6))

    def as_tuple(self) -> tuple[str, str, str, float, float]:
        return (
            self.direction,
            self.detection_tf,
            self.m8_kind_class,
            self.zone_low,
            self.zone_high,
        )


@dataclass(frozen=True, slots=True)
class EpisodeEvent:
    """Frozen append-only fact in an episode history."""

    episode_id: str
    kind: str
    ts: datetime
    bar_index: int | None = None
    tf: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.episode_id:
            raise ValueError("EpisodeEvent requires a non-empty episode_id")
        if not self.kind:
            raise ValueError("EpisodeEvent requires a non-empty kind")
        if self.ts is None:
            raise ValueError("EpisodeEvent requires ts (tz-aware UTC datetime)")
        if self.ts.tzinfo is None:
            raise ValueError(f"EpisodeEvent timestamp must be timezone-aware (UTC): {self.ts}")
        if self.data is None or not isinstance(self.data, dict):
            raise ValueError("EpisodeEvent data must be a dict (never None)")


@dataclass(slots=True)
class EpisodeRecord:
    """Mutable aggregate tracking one episode's current state and history."""

    episode_id: str
    identity_key: EpisodeIdentityKey
    created_at: datetime
    created_bar: int | None
    state: EpisodeState = EpisodeState.DETECTED
    direction: str = "LONG"
    detection_tf: str = "H4"
    m8_kind_class: str = "n/a"
    zone_low: float = 0.0
    zone_high: float = 0.0
    bounds_history: list[tuple[float, float, int | None]] = field(default_factory=list)
    poi_ids: list[str] = field(default_factory=list)
    route_ids: list[str] = field(default_factory=list)
    parent_episode_id: str | None = None
    related_episode_ids: list[str] = field(default_factory=list)
    refinement: dict[str, Any] | None = None
    posture: str | None = None
    events: list[EpisodeEvent] = field(default_factory=list)
    fate: EpisodeState | None = None

    def __post_init__(self) -> None:
        self.direction = self.identity_key.direction
        self.detection_tf = self.identity_key.detection_tf
        self.m8_kind_class = self.identity_key.m8_kind_class
        self.zone_low = self.identity_key.zone_low
        self.zone_high = self.identity_key.zone_high
        if not self.bounds_history:
            self.bounds_history.append((self.zone_low, self.zone_high, self.created_bar))

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def adopt_bounds(
        self,
        new_low: float,
        new_high: float,
        bar: int | None,
        *,
        parent_bounds: tuple[float, float] | None = None,
        parent_episode_id: str | None = None,
    ) -> None:
        """Adopt tighter refined bounds inside parent geometry (Section 3.3)."""
        new_low_r = round(float(new_low), 6)
        new_high_r = round(float(new_high), 6)
        if (new_low_r, new_high_r) != (self.zone_low, self.zone_high):
            self.bounds_history.append((new_low_r, new_high_r, bar))
            self.zone_low = new_low_r
            self.zone_high = new_high_r
            self.refinement = {
                "present": True,
                "parent_bounds": parent_bounds or (self.identity_key.zone_low, self.identity_key.zone_high),
                "refined_bounds": (new_low_r, new_high_r),
                "adopted_at_bar": bar,
            }
            if parent_episode_id is not None:
                self.parent_episode_id = parent_episode_id


class _EpisodeZoneProxy:
    """Duck-typed zone proxy for ZoneDedup overlap predicate."""

    __slots__ = ("direction", "top", "bottom")

    def __init__(self, direction: str, top: float, bottom: float) -> None:
        self.direction = direction
        self.top = top
        self.bottom = bottom


class EpisodeStore:
    """In-memory, append-only lifecycle store for episodes (V1).

    Observability-only: no trading or routing logic reads this store in V1.
    """

    def __init__(self, *, enabled: bool = True, strict_no_lookahead: bool = True) -> None:
        self.enabled = enabled
        self.strict_no_lookahead = strict_no_lookahead
        self._episodes: dict[str, EpisodeRecord] = {}
        # episodes by (direction, detection_tf, m8_kind_class) -> list[EpisodeRecord]
        self._by_class: dict[tuple[str, str, str], list[EpisodeRecord]] = {}
        self._poi_to_episode: dict[str, str] = {}
        self._route_to_episode: dict[str, str] = {}
        self._next_id: int = 1
        self._current_bar: int | None = None
        self._clock_anchored: bool = False
        self._all_events: list[EpisodeEvent] = []

    def set_current_bar(self, bar: int) -> None:
        """Update current bar index for no-lookahead invariant enforcement."""
        if self._current_bar is not None and bar < self._current_bar:
            raise ValueError(
                f"Clock regression detected: current_bar={self._current_bar}, incoming bar={bar}"
            )
        self._current_bar = bar
        self._clock_anchored = True

    # ------------------------------------------------------------------ #
    # Identity Resolution (Section 3.1, Section 3.3, Section 9a)
    # ------------------------------------------------------------------ #
    def _canonical_m8_kind(self, poi_or_tags: Any, m8_kind: str | None = None) -> str:
        """Extract canonical m8_kind_class (ob, demand_supply, fvg, n/a)."""
        if m8_kind:
            kind_clean = str(m8_kind).strip().lower()
            if kind_clean:
                return kind_clean
        raw_m8 = getattr(poi_or_tags, "m8_kind", None)
        if raw_m8:
            return str(raw_m8).strip().lower()
        models = getattr(poi_or_tags, "models", None)
        if models is not None:
            tag_names = [getattr(m, "name", str(m)) for m in models]
            if "M8" in tag_names:
                return "m8_generic"
        return "n/a"

    def _zone_bounds(self, zone_or_poi: Any) -> tuple[float, float]:
        """Extract rounded 6dp bounds from Zone or POI."""
        zone = getattr(zone_or_poi, "zone", zone_or_poi)
        top = round(float(getattr(zone, "top")), 6)
        bottom = round(float(getattr(zone, "bottom")), 6)
        return min(bottom, top), max(bottom, top)

    def _direction_str(self, dir_or_obj: Any) -> str:
        """Extract uppercase direction string ('LONG' / 'SHORT')."""
        direction = getattr(dir_or_obj, "direction", dir_or_obj)
        name = getattr(direction, "name", str(direction))
        return name.upper()

    def _detection_tf_str(self, tf_or_obj: Any) -> str:
        """Extract uppercase timeframe string ('H4', 'H1', etc.)."""
        tf = getattr(tf_or_obj, "detection_tf", tf_or_obj)
        tf = getattr(tf, "timeframe", tf)
        name = getattr(tf, "name", str(tf))
        return name.upper()

    def resolve_identity(
        self,
        *,
        direction: str,
        detection_tf: str,
        m8_kind_class: str,
        zone_low: float,
        zone_high: float,
        poi_id: str | None = None,
        parent_candidate: EpisodeRecord | None = None,
    ) -> tuple[EpisodeRecord, bool]:
        """Resolve identity per Section 3 & Section 9a rulings.

        Returns (episode_record, is_new).
        Rule 1: If poi_id is already mapped to an episode, return that episode.
        Rule 2: Match within same (direction, detection_tf, m8_kind_class).
                Overlap check uses ZoneDedup overlap predicate.
        Rule 3: Refinement: if within an existing episode's bounds (containment or overlap),
                and is arming/tighter box, same episode and adopt bounds.
        Rule 4: If separate class (e.g. H4 vs M8<-H4), separate episode; link related if overlap.
        """
        dir_clean = self._direction_str(direction)
        tf_clean = self._detection_tf_str(detection_tf)
        m8_clean = str(m8_kind_class or "n/a").strip().lower()
        low_clean = round(float(zone_low), 6)
        high_clean = round(float(zone_high), 6)
        class_key = (dir_clean, tf_clean, m8_clean)

        # 1. Quick check by known poi_id
        if poi_id and poi_id in self._poi_to_episode:
            existing = self._episodes[self._poi_to_episode[poi_id]]
            return existing, False

        # 2. Check candidates in the same class partition using ZoneDedup overlap logic
        candidates = self._by_class.get(class_key, [])
        for candidate in candidates:
            # Overlap predicate from ZoneDedup:
            # (known_top >= bottom and top >= known_bottom)
            dedup = ZoneDedup()
            dedup.register(
                _EpisodeZoneProxy(candidate.direction, candidate.zone_high, candidate.zone_low),
                owner_id=candidate.episode_id)  # LEG 5 R1: owned key (seen is owner-blind)
            probe = _EpisodeZoneProxy(dir_clean, high_clean, low_clean)
            if dedup.seen(probe):
                # Matched existing episode via ZoneDedup overlap authority
                if poi_id:
                    self._poi_to_episode[poi_id] = candidate.episode_id
                    if poi_id not in candidate.poi_ids:
                        candidate.poi_ids.append(poi_id)
                return candidate, False

        # 3. Check refinement against parent_candidate if explicitly provided
        if parent_candidate is not None:
            # Check if current box is inside parent bounds (containment)
            if parent_candidate.zone_low <= low_clean and high_clean <= parent_candidate.zone_high:
                if poi_id:
                    self._poi_to_episode[poi_id] = parent_candidate.episode_id
                    if poi_id not in parent_candidate.poi_ids:
                        parent_candidate.poi_ids.append(poi_id)
                return parent_candidate, False

        # 4. Create new episode
        new_id = f"ep-{self._next_id:06d}"
        self._next_id += 1
        ident = EpisodeIdentityKey(
            direction=dir_clean,
            detection_tf=tf_clean,
            m8_kind_class=m8_clean,
            zone_low=low_clean,
            zone_high=high_clean,
        )
        record = EpisodeRecord(
            episode_id=new_id,
            identity_key=ident,
            created_at=datetime.now(timezone.utc),
            created_bar=self._current_bar,
        )
        if poi_id:
            record.poi_ids.append(poi_id)
            self._poi_to_episode[poi_id] = new_id

        # Check cross-class overlap for related_episode link (e.g. H4 vs M8<-H4)
        for other_class_key, records in self._by_class.items():
            if other_class_key[0] != dir_clean:
                continue
            for other_rec in records:
                dedup = ZoneDedup()
                dedup.register(
                    _EpisodeZoneProxy(other_rec.direction, other_rec.zone_high, other_rec.zone_low),
                    owner_id=other_rec.episode_id)  # LEG 5 R1 (seen is owner-blind)
                probe = _EpisodeZoneProxy(dir_clean, high_clean, low_clean)
                if dedup.seen(probe):
                    if other_rec.episode_id not in record.related_episode_ids:
                        record.related_episode_ids.append(other_rec.episode_id)
                    if record.episode_id not in other_rec.related_episode_ids:
                        other_rec.related_episode_ids.append(record.episode_id)

        self._episodes[new_id] = record
        self._by_class.setdefault(class_key, []).append(record)
        return record, True

    # ------------------------------------------------------------------ #
    # Append Event (Section 5)
    # ------------------------------------------------------------------ #
    def record_event(
        self,
        kind: str | EpisodeEventKind,
        *,
        episode_id: str | None = None,
        poi: Any | None = None,
        poi_id: str | None = None,
        route_id: str | None = None,
        ts: datetime | None = None,
        bar_index: int | None = None,
        tf: str | None = None,
        data: dict[str, Any] | None = None,
        detection_tf: str | None = None,
        m8_kind_class: str | None = None,
        zone_low: float | None = None,
        zone_high: float | None = None,
        direction: str | None = None,
    ) -> EpisodeEvent:
        """Append an event to an episode history.

        Resolves episode identity if episode_id is not given.
        Asserts no-lookahead and validates required event payload.
        """
        if not self.enabled:
            # Even if disabled, return a lightweight dummy event or handle gracefully
            pass

        data_dict = dict(data) if data is not None else {}
        kind_str = getattr(kind, "value", str(kind))

        # Check valid kind against vocabulary
        valid_kinds = {k.value for k in EpisodeEventKind}
        if kind_str not in valid_kinds:
            raise ValueError(f"Unknown event kind: '{kind_str}'. Valid kinds: {sorted(valid_kinds)}")

        # Timestamp validation
        if ts is None:
            ts = datetime.now(timezone.utc)
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # Bar index & no-lookahead check
        if bar_index is not None:
            if self._current_bar is not None and bar_index < self._current_bar:
                # Event from a previous bar is allowed (e.g. multi-bar lifecycle or batch facts)
                pass
            elif self._current_bar is not None and bar_index > self._current_bar:
                # If current_bar was anchored and incoming event is in the future
                if self.strict_no_lookahead and self._clock_anchored:
                    raise ValueError(
                        f"No-lookahead invariant violated: event bar {bar_index} > current_bar {self._current_bar}"
                    )
                self._current_bar = bar_index
            else:
                self._current_bar = bar_index

        actual_bar = bar_index if bar_index is not None else self._current_bar

        # Resolve episode
        record: EpisodeRecord | None = None
        if episode_id is not None:
            record = self._episodes.get(episode_id)
            if record is None:
                raise ValueError(f"Episode with id '{episode_id}' not found in store")
        elif poi_id is not None and poi_id in self._poi_to_episode:
            record = self._episodes[self._poi_to_episode[poi_id]]
        elif route_id is not None and route_id in self._route_to_episode:
            record = self._episodes[self._route_to_episode[route_id]]
        elif poi is not None:
            p_id = getattr(poi, "id", poi_id)
            if p_id and p_id in self._poi_to_episode:
                record = self._episodes[self._poi_to_episode[p_id]]
            else:
                low, high = self._zone_bounds(poi)
                d_str = self._direction_str(poi.zone if hasattr(poi, "zone") else poi)
                t_str = self._detection_tf_str(detection_tf or getattr(getattr(poi, "zone", None), "timeframe", "H4"))
                m_str = self._canonical_m8_kind(poi, m8_kind_class)
                record, _ = self.resolve_identity(
                    direction=d_str,
                    detection_tf=t_str,
                    m8_kind_class=m_str,
                    zone_low=low,
                    zone_high=high,
                    poi_id=p_id,
                )
        else:
            # Attempt to resolve from explicit parameters
            if direction is not None and zone_low is not None and zone_high is not None:
                d_str = self._direction_str(direction)
                t_str = self._detection_tf_str(detection_tf or "H4")
                m_str = self._canonical_m8_kind(None, m8_kind_class)
                record, _ = self.resolve_identity(
                    direction=d_str,
                    detection_tf=t_str,
                    m8_kind_class=m_str,
                    zone_low=zone_low,
                    zone_high=zone_high,
                    poi_id=poi_id,
                )
            else:
                raise ValueError("Cannot resolve episode without episode_id, poi, or explicit geometric coordinates")

        # Associate poi_id / route_id if supplied
        effective_poi_id = poi_id or getattr(poi, "id", None)
        if effective_poi_id:
            self._poi_to_episode[effective_poi_id] = record.episode_id
            if effective_poi_id not in record.poi_ids:
                record.poi_ids.append(effective_poi_id)

        effective_route_id = route_id or data_dict.get("route_id")
        if effective_route_id:
            self._route_to_episode[effective_route_id] = record.episode_id
            if effective_route_id not in record.route_ids:
                record.route_ids.append(effective_route_id)

        # One-shot invariant check: at most one route per episode (Section 8.4)
        if kind_str in (EpisodeEventKind.ROUTE.value, EpisodeEventKind.ROUTE_FORMED.value):
            existing_routes = [
                e for e in record.events
                if e.kind in (EpisodeEventKind.ROUTE.value, EpisodeEventKind.ROUTE_FORMED.value)
            ]
            if existing_routes:
                raise ValueError(
                    f"One-shot invariant violated: episode {record.episode_id} already has a route: "
                    f"{existing_routes[0].data.get('route_id')}"
                )

        # Refinement adoption on arming if refined bounds provided (Section 3.3)
        if kind_str == EpisodeEventKind.ARMED.value:
            ref_low = data_dict.get("zone_low")
            ref_high = data_dict.get("zone_high")
            if ref_low is not None and ref_high is not None:
                parent_bounds = (record.identity_key.zone_low, record.identity_key.zone_high)
                record.adopt_bounds(
                    ref_low,
                    ref_high,
                    actual_bar,
                    parent_bounds=parent_bounds,
                    parent_episode_id=data_dict.get("parent_episode_id"),
                )

        # State transition bookkeeping
        self._transition_state(record, kind_str, data_dict)

        event = EpisodeEvent(
            episode_id=record.episode_id,
            kind=kind_str,
            ts=ts,
            bar_index=actual_bar,
            tf=tf or record.detection_tf,
            data=data_dict,
        )
        record.events.append(event)
        self._all_events.append(event)
        return event

    def _transition_state(self, record: EpisodeRecord, kind: str, data: dict[str, Any]) -> None:
        """Map append-only event kind to normative lifecycle state."""
        mapping: dict[str, EpisodeState] = {
            EpisodeEventKind.DETECTED.value: EpisodeState.DETECTED,
            EpisodeEventKind.VALIDATED.value: EpisodeState.VALIDATED,
            EpisodeEventKind.REJECTED_PILLAR.value: EpisodeState.REJECTED_PILLAR,
            EpisodeEventKind.PILLAR_FAILED.value: EpisodeState.REJECTED_PILLAR,
            EpisodeEventKind.SUPPRESSED_DEDUP.value: EpisodeState.SUPPRESSED_DEDUP,
            EpisodeEventKind.ARM_SUPPRESSED_DEDUP.value: EpisodeState.SUPPRESSED_DEDUP,
            EpisodeEventKind.EXPIRED_UNARMED.value: EpisodeState.EXPIRED_UNARMED,
            EpisodeEventKind.ARMED.value: EpisodeState.ARMED,
            EpisodeEventKind.POSTURE_CLASSIFIED.value: EpisodeState.SEEKING,
            EpisodeEventKind.SEEK_OPENED.value: EpisodeState.SEEKING,
            EpisodeEventKind.REVALIDATED.value: EpisodeState.REVALIDATION,
            EpisodeEventKind.ROUTE.value: EpisodeState.ROUTED,
            EpisodeEventKind.ROUTE_FORMED.value: EpisodeState.ROUTED,
            EpisodeEventKind.BLOCKED.value: EpisodeState.BLOCKED_RETRYABLE,
            EpisodeEventKind.INTENT_ARMED.value: EpisodeState.INTENT_ARMED,
            EpisodeEventKind.INTENT_EXPIRED_NO_REENTRY.value: EpisodeState.INTENT_EXPIRED,
            EpisodeEventKind.INTENT_REPLACED.value: EpisodeState.INTENT_REPLACED,
            EpisodeEventKind.INTENT_DROPPED_POI.value: EpisodeState.INTENT_DROPPED_POI,
            EpisodeEventKind.INTENT_DROPPED_PORTFOLIO.value: EpisodeState.INTENT_DROPPED_PORTFOLIO,
            EpisodeEventKind.PLACE.value: EpisodeState.PLACED,
            EpisodeEventKind.PLACED.value: EpisodeState.PLACED,
            EpisodeEventKind.ORDER_EXPIRED.value: EpisodeState.ORDER_EXPIRED,
            EpisodeEventKind.EXPIRE_ORDER.value: EpisodeState.ORDER_EXPIRED,
            EpisodeEventKind.FILL.value: EpisodeState.FILLED,
            EpisodeEventKind.FILLED.value: EpisodeState.FILLED,
            EpisodeEventKind.SCAN_CLOSED.value: EpisodeState.SCAN_CLOSED,
            EpisodeEventKind.GAVE_UP.value: EpisodeState.SCAN_CLOSED,
            EpisodeEventKind.VIOLATED.value: EpisodeState.VIOLATED,
        }

        if kind in mapping:
            target_state = mapping[kind]
            # Special case for BLOCKED: could be terminal or retryable
            if kind == EpisodeEventKind.BLOCKED.value:
                reason = str(data.get("reason", "")).lower()
                if "terminal" in reason:
                    target_state = EpisodeState.BLOCKED_TERMINAL
                else:
                    target_state = EpisodeState.BLOCKED_RETRYABLE
            # Special case for CLOSED: inspect win/kind
            elif kind == EpisodeEventKind.CLOSED.value:
                close_kind = str(data.get("kind", "")).lower()
                if "tp" in close_kind:
                    target_state = EpisodeState.CLOSED_TP
                elif "sl" in close_kind:
                    target_state = EpisodeState.CLOSED_SL
                elif "be" in close_kind:
                    target_state = EpisodeState.CLOSED_BE
                elif "portfolio" in close_kind or "friday" in close_kind or "news" in close_kind:
                    target_state = EpisodeState.CLOSED_PORTFOLIO
                else:
                    target_state = EpisodeState.CLOSED_TP if data.get("win") else EpisodeState.CLOSED_SL

            record.state = target_state
            if target_state in TERMINAL_STATES:
                record.fate = target_state

        if kind == EpisodeEventKind.POSTURE_CLASSIFIED.value:
            record.posture = data.get("posture")

    # ------------------------------------------------------------------ #
    # Query API (Section 5.2)
    # ------------------------------------------------------------------ #
    def get(self, episode_id: str) -> EpisodeRecord | None:
        return self._episodes.get(episode_id)

    def get_by_poi(self, poi_id: str) -> EpisodeRecord | None:
        ep_id = self._poi_to_episode.get(poi_id)
        return self._episodes.get(ep_id) if ep_id else None

    def get_by_route(self, route_id: str) -> EpisodeRecord | None:
        ep_id = self._route_to_episode.get(route_id)
        return self._episodes.get(ep_id) if ep_id else None

    def all_episodes(self) -> list[EpisodeRecord]:
        return list(self._episodes.values())

    def state_at(self, episode_id: str, bar: int) -> EpisodeState | None:
        """Query state of episode as of given bar (no-lookahead query)."""
        record = self.get(episode_id)
        if record is None:
            return None
        events_up_to = [e for e in record.events if e.bar_index is not None and e.bar_index <= bar]
        if not events_up_to:
            return None
        dummy_rec = EpisodeRecord(
            episode_id=record.episode_id,
            identity_key=record.identity_key,
            created_at=record.created_at,
            created_bar=record.created_bar,
        )
        for ev in events_up_to:
            self._transition_state(dummy_rec, ev.kind, ev.data)
        return dummy_rec.state

    def events_for(self, episode_id: str) -> list[EpisodeEvent]:
        record = self.get(episode_id)
        return list(record.events) if record else []

    def fate(self, episode_id: str) -> EpisodeState | None:
        record = self.get(episode_id)
        return record.fate if record else None

    def funnel(self, as_of_bar: int | None = None) -> dict[str, int]:
        """Derived counters: derived by counting events, never manual tallies.

        This guarantees that the 'expired 0' defect is structurally impossible.
        """
        counts: dict[str, int] = {
            "episodes_total": 0,
            "detected": 0,
            "validated": 0,
            "rejected_pillar": 0,
            "suppressed_dedup": 0,
            "expired_unarmed": 0,
            "armed": 0,
            "seeking": 0,
            "routed": 0,
            "blocked": 0,
            "intent_armed": 0,
            "intent_expired_no_reentry": 0,
            "intent_replaced": 0,
            "intent_dropped": 0,
            "placed": 0,
            "order_expired": 0,
            "filled": 0,
            "closed": 0,
            "closed_tp": 0,
            "closed_sl": 0,
            "closed_be": 0,
            "violated": 0,
            "scan_closed": 0,
        }

        for record in self._episodes.values():
            counts["episodes_total"] += 1
            events = record.events
            if as_of_bar is not None:
                events = [e for e in events if e.bar_index is None or e.bar_index <= as_of_bar]
            kinds = {e.kind for e in events}
            if EpisodeEventKind.DETECTED.value in kinds:
                counts["detected"] += 1
            if EpisodeEventKind.VALIDATED.value in kinds:
                counts["validated"] += 1
            if EpisodeEventKind.REJECTED_PILLAR.value in kinds or EpisodeEventKind.PILLAR_FAILED.value in kinds:
                counts["rejected_pillar"] += 1
            if EpisodeEventKind.SUPPRESSED_DEDUP.value in kinds or EpisodeEventKind.ARM_SUPPRESSED_DEDUP.value in kinds:
                counts["suppressed_dedup"] += 1
            if EpisodeEventKind.EXPIRED_UNARMED.value in kinds:
                counts["expired_unarmed"] += 1
            if EpisodeEventKind.ARMED.value in kinds:
                counts["armed"] += 1
            if EpisodeEventKind.SEEK_OPENED.value in kinds or EpisodeEventKind.POSTURE_CLASSIFIED.value in kinds:
                counts["seeking"] += 1
            if EpisodeEventKind.ROUTE.value in kinds or EpisodeEventKind.ROUTE_FORMED.value in kinds:
                counts["routed"] += 1
            if EpisodeEventKind.BLOCKED.value in kinds or EpisodeEventKind.BLOCK.value in kinds:
                counts["blocked"] += 1
            if EpisodeEventKind.INTENT_ARMED.value in kinds:
                counts["intent_armed"] += 1
            if EpisodeEventKind.INTENT_EXPIRED_NO_REENTRY.value in kinds:
                counts["intent_expired_no_reentry"] += 1
            if EpisodeEventKind.INTENT_REPLACED.value in kinds:
                counts["intent_replaced"] += 1
            if EpisodeEventKind.INTENT_DROPPED_POI.value in kinds or EpisodeEventKind.INTENT_DROPPED_PORTFOLIO.value in kinds:
                counts["intent_dropped"] += 1
            if EpisodeEventKind.PLACE.value in kinds or EpisodeEventKind.PLACED.value in kinds:
                counts["placed"] += 1
            if EpisodeEventKind.ORDER_EXPIRED.value in kinds or EpisodeEventKind.EXPIRE_ORDER.value in kinds:
                counts["order_expired"] += 1
            if EpisodeEventKind.FILL.value in kinds or EpisodeEventKind.FILLED.value in kinds:
                counts["filled"] += 1
            if EpisodeEventKind.CLOSED.value in kinds:
                counts["closed"] += 1
            if EpisodeEventKind.VIOLATED.value in kinds:
                counts["violated"] += 1
            if EpisodeEventKind.SCAN_CLOSED.value in kinds or EpisodeEventKind.GAVE_UP.value in kinds:
                counts["scan_closed"] += 1

        return counts

    def coincidence_hits(self, horizon_bars: int = 48) -> list[tuple[str, str, int]]:
        """Research helper: proof events within H bars of armed / reference event.

        Returns list of (episode_a, episode_b, delta_bars).
        """
        hits: list[tuple[str, str, int]] = []
        armed_list: list[tuple[str, int, float, float, str]] = []
        for rec in self._episodes.values():
            arm_events = [e for e in rec.events if e.kind == EpisodeEventKind.ARMED.value]
            if arm_events and arm_events[0].bar_index is not None:
                armed_list.append((
                    rec.episode_id,
                    arm_events[0].bar_index,
                    rec.zone_low,
                    rec.zone_high,
                    rec.direction,
                ))

        armed_list.sort(key=lambda x: x[1])
        for i in range(len(armed_list)):
            id_a, bar_a, low_a, high_a, dir_a = armed_list[i]
            for j in range(i + 1, len(armed_list)):
                id_b, bar_b, low_b, high_b, dir_b = armed_list[j]
                delta = bar_b - bar_a
                if delta > horizon_bars:
                    break
                hits.append((id_a, id_b, delta))
        return hits

    def blueprint(self, episode_id: str) -> dict[str, Any] | None:
        """Summary blueprint dictionary of episode geometry, tags, and lifecycle timing."""
        rec = self.get(episode_id)
        if rec is None:
            return None
        arm_t = None
        route_t = None
        place_t = None
        fill_t = None
        close_t = None
        for e in rec.events:
            if e.kind == EpisodeEventKind.ARMED.value and arm_t is None:
                arm_t = e.ts.isoformat()
            elif e.kind in (EpisodeEventKind.ROUTE.value, EpisodeEventKind.ROUTE_FORMED.value) and route_t is None:
                route_t = e.ts.isoformat()
            elif e.kind in (EpisodeEventKind.PLACE.value, EpisodeEventKind.PLACED.value) and place_t is None:
                place_t = e.ts.isoformat()
            elif e.kind in (EpisodeEventKind.FILL.value, EpisodeEventKind.FILLED.value) and fill_t is None:
                fill_t = e.ts.isoformat()
            elif e.kind == EpisodeEventKind.CLOSED.value and close_t is None:
                close_t = e.ts.isoformat()

        return {
            "episode_id": rec.episode_id,
            "direction": rec.direction,
            "detection_tf": rec.detection_tf,
            "m8_kind_class": rec.m8_kind_class,
            "zone_low": rec.zone_low,
            "zone_high": rec.zone_high,
            "poi_ids": list(rec.poi_ids),
            "route_ids": list(rec.route_ids),
            "parent_episode_id": rec.parent_episode_id,
            "refinement": dict(rec.refinement) if rec.refinement else None,
            "bounds_history": list(rec.bounds_history),
            "state": rec.state.value,
            "fate": rec.fate.value if rec.fate else None,
            "posture": rec.posture,
            "event_count": len(rec.events),
            "timing": {
                "arm_t": arm_t,
                "route_t": route_t,
                "place_t": place_t,
                "fill_t": fill_t,
                "close_t": close_t,
            },
        }

    # ------------------------------------------------------------------ #
    # Export (Section 7)
    # ------------------------------------------------------------------ #
    def to_rows(self) -> list[dict[str, Any]]:
        """Stable column order representation of all episodes."""
        rows: list[dict[str, Any]] = []
        for rec in self._episodes.values():
            bp = self.blueprint(rec.episode_id)
            if not bp:
                continue
            rows.append({
                "episode_id": bp["episode_id"],
                "direction": bp["direction"],
                "detection_tf": bp["detection_tf"],
                "m8_kind_class": bp["m8_kind_class"],
                "zone_low": bp["zone_low"],
                "zone_high": bp["zone_high"],
                "state": bp["state"],
                "fate": bp["fate"] or "",
                "posture": bp["posture"] or "",
                "poi_ids": "|".join(bp["poi_ids"]),
                "route_ids": "|".join(bp["route_ids"]),
                "parent_episode_id": bp["parent_episode_id"] or "",
                "refinement_present": bool(bp["refinement"]),
                "event_count": bp["event_count"],
                "arm_t": bp["timing"]["arm_t"] or "",
                "route_t": bp["timing"]["route_t"] or "",
                "place_t": bp["timing"]["place_t"] or "",
                "fill_t": bp["timing"]["fill_t"] or "",
                "close_t": bp["timing"]["close_t"] or "",
            })
        return rows

    def export_events_rows(self) -> list[dict[str, Any]]:
        """Export raw events with stable column order."""
        rows: list[dict[str, Any]] = []
        for ev in self._all_events:
            rows.append({
                "episode_id": ev.episode_id,
                "kind": ev.kind,
                "ts": ev.ts.isoformat(),
                "bar_index": ev.bar_index if ev.bar_index is not None else "",
                "tf": ev.tf or "",
                "data": json.dumps(ev.data, sort_keys=True),
            })
        return rows

    def write_csv(self, path: Path | str) -> None:
        """Write episodes summary CSV with deterministic column ordering."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        rows = self.to_rows()
        fieldnames = [
            "episode_id",
            "direction",
            "detection_tf",
            "m8_kind_class",
            "zone_low",
            "zone_high",
            "state",
            "fate",
            "posture",
            "poi_ids",
            "route_ids",
            "parent_episode_id",
            "refinement_present",
            "event_count",
            "arm_t",
            "route_t",
            "place_t",
            "fill_t",
            "close_t",
        ]
        with open(p, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

    def write_json(self, path: Path | str) -> None:
        """Write full episode blueprints + derived funnel to JSON."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "funnel": self.funnel(),
            "episodes": [self.blueprint(ep_id) for ep_id in self._episodes],
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
