"""POI freshness state machine (LOCKED_DECISIONS §5, §23).

The §5 machine is strict 1-touch only::

    STATE_CREATED → STATE_FRESH → STATE_TESTED (terminal — no return)
    STATE_CREATED → STATE_FRESH → STATE_VIOLATED (close beyond, no touch)

Transitions are ATOMIC: every mutation goes through :meth:`transition`,
which checks the current state against an internal per-POI store and raises
:class:`IllegalTransitionError` on any disallowed move (e.g. a second touch
on an already-TESTED POI, or any move out of a terminal state). The POI's
own ``state`` attribute is kept in sync with the store.

Unfilled-order expiry (§23) is supported via :meth:`expire_unfilled` using
the FROZEN bar counts: M5 = 12 bars, M1 = 30 bars. Timeframes without a
frozen expiry rule (H1+) return ``None`` from :func:`expiry_bars_for` — no
automatic expiry is defined for them.

V1 NOTE (documented): the machine is in-memory and single-process. The
Redis-backed CAS (compare-and-set on the same state key) replaces this store
unchanged in live use — the transition table and validation order stay the
same.
"""

from __future__ import annotations

from smc.config.locked_constants import M1_EXPIRY_BARS, M5_EXPIRY_BARS
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import POIState
from smc.core.poi import POI

__all__ = [
    "IllegalTransitionError",
    "POIStateMachine",
    "expiry_bars_for",
]

# Allowed transitions per current state (§5 — TESTED/VIOLATED terminal).
_TRANSITIONS: dict[POIState, frozenset[POIState]] = {
    POIState.CREATED: frozenset({POIState.FRESH}),
    POIState.FRESH: frozenset({POIState.TESTED, POIState.VIOLATED}),
    POIState.TESTED: frozenset(),
    POIState.VIOLATED: frozenset(),
}


class IllegalTransitionError(Exception):
    """Raised when a state transition is not allowed by the §5 machine."""


def expiry_bars_for(timeframe: Timeframe) -> int | None:
    """Frozen unfilled-order expiry in bars (§23) for an order timeframe.

    Returns ``None`` for timeframes without a frozen expiry rule (only M5
    and M1 are defined in LOCKED_DECISIONS §5/§23).
    """
    if timeframe is Timeframe.M5:
        return M5_EXPIRY_BARS
    if timeframe is Timeframe.M1:
        return M1_EXPIRY_BARS
    return None


class POIStateMachine:
    """Atomic §5 freshness transitions, keyed by POI id.

    V1 in-memory store; ``poi.state`` is the source of truth for any POI the
    machine has not seen, and is written on every successful transition.
    """

    def __init__(self) -> None:
        self._states: dict[str, POIState] = {}

    # ------------------------------------------------------------------ #
    # State access
    # ------------------------------------------------------------------ #
    def current(self, poi: POI) -> POIState:
        """Current state of a POI (store first, POI attribute as fallback)."""
        return self._states.get(poi.id, poi.state)

    def transition(self, poi: POI, to: POIState) -> POIState:
        """Atomically move ``poi`` to ``to`` (raises if not allowed)."""
        current = self.current(poi)
        if to not in _TRANSITIONS[current]:
            raise IllegalTransitionError(
                f"Illegal §5 transition {current.name} -> {to.name} for POI {poi.id}"
            )
        self._states[poi.id] = to
        poi.state = to
        return to

    # ------------------------------------------------------------------ #
    # Named transitions
    # ------------------------------------------------------------------ #
    def arm(self, poi: POI) -> POIState:
        """CREATED → FRESH: make a newly validated POI tradeable."""
        return self.transition(poi, POIState.FRESH)

    def on_touch(self, poi: POI) -> POIState:
        """FRESH → TESTED: first touch deactivates forever (1-touch rule).

        A second touch on an already-TESTED POI raises (no new entries).
        """
        return self.transition(poi, POIState.TESTED)

    def on_violation(self, poi: POI) -> POIState:
        """FRESH → VIOLATED: price closed beyond the zone without touching."""
        return self.transition(poi, POIState.VIOLATED)

    def can_trade(self, poi: POI) -> bool:
        """True only while FRESH — the sole non-terminal tradeable state.

        "First touch OK": the entry may fire on the POI's FIRST touch; after
        the touch flips the POI to TESTED, ``can_trade`` returns False so a
        second touch is never traded.
        """
        return self.current(poi) is POIState.FRESH

    def expire_unfilled(self, poi: POI, bars_open: int) -> POIState | None:
        """§23 unfilled-order expiry: mark FRESH POIs TESTED after N bars.

        Returns the new state when an expiry fired, otherwise the current
        state; ``None`` only when no frozen expiry rule exists for the POI's
        timeframe (see :func:`expiry_bars_for`).
        """
        limit = expiry_bars_for(poi.zone.timeframe)
        if limit is None:
            return None
        if bars_open >= limit and self.current(poi) is POIState.FRESH:
            return self.transition(poi, POIState.TESTED)
        return self.current(poi)

    # ------------------------------------------------------------------ #
    # Geometry helper
    # ------------------------------------------------------------------ #
    @staticmethod
    def touches_zone(poi: POI, candle: Candle) -> bool:
        """True when a candle's wick (full range) enters the POI zone.

        Inclusive on both boundaries — matches the §5 touch definition
        ("price wick enters the zone boundary").
        """
        return (
            candle.low <= poi.zone.top and candle.high >= poi.zone.bottom
        )
