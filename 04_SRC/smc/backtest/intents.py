"""R9 place-on-reentry intents (Lead Architect ruling, 2026-09-22).

An intent is THE risk-accepted placement R7 deferred — never a new
evaluation. R7 skips a far-from-zone candidate; instead of dropping it
silently, the runner arms a :class:`PlaceIntent` that places the SAME
pending limit (frozen direction / FR-3.1 zone-anchored limit / FR-2
SL+TP / policy-sized lots) when the market re-enters the zone band or
touches the limit — within an R8-sized clock from signal time.

Determinism contract (mirrors ``PendingOrderBook``):

* insertion-ordered list — same-bar intent processing is deterministic
  (the FIRST armed intent is evaluated FIRST on every bar);
* one intent per route identity PER RUN: the dedupe key is ``route_id``
  (fallback ``poi_id|trigger``); a terminal intent blocks re-arming (a
  second intent would extend life beyond R8; any later in-band proposal
  is covered by the immediate-place path);
* arm consumes NOTHING (the §11 one-shot burns only on accepted
  placement — the runner calls ``on_candidate_accepted`` when the intent
  actually places);
* lifecycle states: ``ARMED`` → ``PLACED`` | ``EXPIRED`` | ``REPLACED``
  | ``DROPPED_POI`` | ``DROPPED_PORTFOLIO``. Terminal records stay
  queryable for reports/CSV export (never fabricated, never deleted).

Pure Python — no MT5, no wall clock. The runner/paper own the bar loop;
this book stores state and answers identity/lifecycle queries only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # runtime duck-typed — no import cycle with runner.py
    from smc.backtest.runner import CandidateEntry

__all__ = ["PlaceIntent", "IntentBook", "INTENT_ARMED", "INTENT_PLACED",
           "INTENT_EXPIRED", "INTENT_REPLACED", "INTENT_DROPPED_POI",
           "INTENT_DROPPED_PORTFOLIO"]

# Lifecycle statuses (strings — CSV/JSON-exportable, machine-readable).
INTENT_ARMED = "ARMED"
INTENT_PLACED = "PLACED"
INTENT_EXPIRED = "EXPIRED"          # clock ran out, no re-entry
INTENT_REPLACED = "REPLACED"        # the candidate placed immediately
INTENT_DROPPED_POI = "DROPPED_POI"  # POI violated — dead thesis
INTENT_DROPPED_PORTFOLIO = "DROPPED_PORTFOLIO"  # Friday EOD / news cancel


@dataclass(slots=True)
class PlaceIntent:
    """One deferred placement (R9). Frozen at arm; lifecycle filled later.

    ``candidate`` is the FULL accepted candidate (identity, geometry,
    FR-3.1 limit, FR-2 stop/target) — the intent re-places it verbatim,
    it never re-derives anything. ``lots`` is the policy-sized volume
    from the risk decision at signal acceptance (single sizing path).
    ``signal_bar`` is the arming bar; ``rest_bars`` the R8 clock from
    signal; ``expire_bar = signal_bar + rest_bars`` is the first dead
    bar (design §2a).
    """

    intent_id: int
    candidate: "CandidateEntry"
    lots: float
    signal_bar: int
    rest_bars: int
    status: str = INTENT_ARMED
    expire_bar: int = 0
    placed_bar: int | None = None
    placed_ticket: int | None = None
    end_bar: int | None = None

    def __post_init__(self) -> None:
        if not self.expire_bar:
            self.expire_bar = self.signal_bar + self.rest_bars

    @property
    def route_key(self) -> tuple:
        """Dedupe identity: route_id, fallback poi_id|trigger (design §3)."""
        route_id = getattr(self.candidate, "route_id", None)
        if route_id:
            return ("route", route_id)
        poi_id = getattr(self.candidate, "poi_id", None)
        trigger = getattr(self.candidate, "trigger", None)
        return ("poi", poi_id, str(trigger))

    def remaining_bars(self, current_bar: int) -> int:
        """Inheritable order lifetime if placed on ``current_bar``."""
        return self.expire_bar - current_bar

    def alive(self) -> bool:
        return self.status == INTENT_ARMED


@dataclass(slots=True)
class IntentBook:
    """Insertion-ordered intent store with lifecycle + counters.

    ``events`` accumulates one machine-readable dict per lifecycle
    transition (armed/placed/expired/replaced/dropped) for reports and
    CSV export — occurrence order, never fabricated.
    """

    _intents: list[PlaceIntent] = field(default_factory=list)
    _by_key: dict[tuple, PlaceIntent] = field(default_factory=dict)
    _next_id: int = 1
    events: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Arming / queries
    # ------------------------------------------------------------------ #
    def arm(self, candidate, lots: float, signal_bar: int,
            rest_bars: int) -> PlaceIntent | None:
        """Arm one intent; None when the route already has one (any state).

        First intent wins — the clock is NEVER refreshed by re-proposals
        (design §3). ``lots``/``signal_bar``/``rest_bars`` frozen here.
        """
        probe = PlaceIntent(intent_id=0, candidate=candidate, lots=lots,
                            signal_bar=signal_bar, rest_bars=rest_bars)
        key = probe.route_key
        existing = self._by_key.get(key)
        if existing is not None:
            return None  # dedupe: one intent per route identity per run
        intent = PlaceIntent(intent_id=self._next_id, candidate=candidate,
                             lots=lots, signal_bar=signal_bar,
                             rest_bars=rest_bars)
        self._next_id += 1
        self._intents.append(intent)
        self._by_key[key] = intent
        self.events.append({
            "event": "armed", "bar": signal_bar, "intent_id": intent.intent_id,
            "route_id": getattr(candidate, "route_id", None),
            "poi_id": getattr(candidate, "poi_id", None),
            "expire_bar": intent.expire_bar, "rest_bars": rest_bars,
        })
        return intent

    def alive_intents(self) -> list[PlaceIntent]:
        """ARMED intents in arm order (deterministic iteration)."""
        return [i for i in self._intents if i.alive()]

    def find_alive(self, candidate) -> PlaceIntent | None:
        """The alive intent for ``candidate``'s route key, if any."""
        probe = PlaceIntent(intent_id=0, candidate=candidate, lots=0.0,
                            signal_bar=0, rest_bars=0)
        intent = self._by_key.get(probe.route_key)
        return intent if intent is not None and intent.alive() else None

    # ------------------------------------------------------------------ #
    # Lifecycle transitions
    # ------------------------------------------------------------------ #
    def mark_placed(self, intent: PlaceIntent, placed_bar: int,
                    ticket: int) -> None:
        intent.status = INTENT_PLACED
        intent.placed_bar = placed_bar
        intent.placed_ticket = ticket
        intent.end_bar = placed_bar
        self.events.append({
            "event": "placed", "bar": placed_bar,
            "intent_id": intent.intent_id, "ticket": ticket,
            "route_id": getattr(intent.candidate, "route_id", None),
            "poi_id": getattr(intent.candidate, "poi_id", None),
            "rest_bars": intent.remaining_bars(placed_bar),
        })

    def mark_expired(self, intent: PlaceIntent, bar: int) -> None:
        """Clock ran out with no re-entry (design §2 rule 4)."""
        intent.status = INTENT_EXPIRED
        intent.end_bar = bar
        self.events.append({
            "event": "intent_expired_no_reentry", "bar": bar,
            "intent_id": intent.intent_id,
            "route_id": getattr(intent.candidate, "route_id", None),
            "poi_id": getattr(intent.candidate, "poi_id", None),
        })

    def mark_replaced(self, intent: PlaceIntent, bar: int) -> None:
        """The candidate placed immediately — drop its alive intent."""
        intent.status = INTENT_REPLACED
        intent.end_bar = bar
        self.events.append({
            "event": "replaced", "bar": bar,
            "intent_id": intent.intent_id,
            "route_id": getattr(intent.candidate, "route_id", None),
            "poi_id": getattr(intent.candidate, "poi_id", None),
        })

    def drop_for_poi(self, poi_id: str, bar: int) -> int:
        """Dead thesis: drop the alive intent(s) of a violated POI."""
        dropped = 0
        for intent in self._intents:
            if intent.alive() and getattr(intent.candidate, "poi_id", None) == poi_id:
                intent.status = INTENT_DROPPED_POI
                intent.end_bar = bar
                dropped += 1
                self.events.append({
                    "event": "dropped_poi", "bar": bar,
                    "intent_id": intent.intent_id, "poi_id": poi_id,
                    "route_id": getattr(intent.candidate, "route_id", None),
                })
        return dropped

    def drop_all(self, bar: int, reason: str) -> int:
        """Portfolio events (Friday EOD, §11 news): drop everything alive."""
        dropped = 0
        for intent in self._intents:
            if intent.alive():
                intent.status = INTENT_DROPPED_PORTFOLIO
                intent.end_bar = bar
                dropped += 1
                self.events.append({
                    "event": reason, "bar": bar,
                    "intent_id": intent.intent_id,
                    "route_id": getattr(intent.candidate, "route_id", None),
                    "poi_id": getattr(intent.candidate, "poi_id", None),
                })
        return dropped

    # ------------------------------------------------------------------ #
    # Expiry scan (runner calls once per bar, before the re-entry step)
    # ------------------------------------------------------------------ #
    def expire_due(self, current_bar: int) -> list[PlaceIntent]:
        """Expire intents whose clock ended (``bar >= expire_bar``).

        Runs BEFORE the bar's re-entry step, so an intent whose clock
        ends on this bar can never place on it (design §4).
        """
        expired: list[PlaceIntent] = []
        for intent in self._intents:
            if intent.alive() and current_bar >= intent.expire_bar:
                self.mark_expired(intent, current_bar)
                expired.append(intent)
        return expired

    # ------------------------------------------------------------------ #
    # Counters / export
    # ------------------------------------------------------------------ #
    def counters(self) -> dict:
        """Run summary counts (machine-readable, deterministic)."""
        counts: dict[str, int] = {"armed": 0, "placed": 0,
                                  "expired_no_reentry": 0, "replaced": 0,
                                  "dropped_poi": 0, "dropped_portfolio": 0,
                                  "alive_at_end": 0}
        for intent in self._intents:
            counts["armed"] += 1
            if intent.status == INTENT_PLACED:
                counts["placed"] += 1
            elif intent.status == INTENT_EXPIRED:
                counts["expired_no_reentry"] += 1
            elif intent.status == INTENT_REPLACED:
                counts["replaced"] += 1
            elif intent.status == INTENT_DROPPED_POI:
                counts["dropped_poi"] += 1
            elif intent.status == INTENT_DROPPED_PORTFOLIO:
                counts["dropped_portfolio"] += 1
            elif intent.status == INTENT_ARMED:
                counts["alive_at_end"] += 1
        return counts

    def __len__(self) -> int:
        return len(self._intents)
