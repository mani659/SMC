"""Phase 5 — failed-sweep re-entry guard (v25_DIAG ``IsFailedSweepBlocked``,
ported to Python).

LOCKED_DECISIONS §28.6: block a new entry on the SAME failed-sweep level
within ``SWEEP_GUARD_ZONE_ATR`` (0.5) × ATR and ``SWEEP_GUARD_COOLDOWN_BARS``
(4) bars of the failed sweep.

v25_DIAG semantics preserved verbatim:

* state is PER DIRECTION (v25 tracks ``g_lastFailedSweepBull`` /
  ``g_lastFailedSweepBear`` separately with their failure times);
* a failed sweep is recorded when a trade on that side closes as a LOSS
  (``g_lastFailedSweep{side} = g_lastSweepLevel{side}`` in v25);
* :meth:`SweepGuard.is_blocked` passes when no failed level is recorded
  (``failedLevel == 0``), when the candidate sweep is NOT within the zone
  (``abs(candidate - failed) > zone``), or when the cooldown has elapsed;
* v25 measures the cooldown in bars since the failure time
  (``(TimeCurrent() - failedTime) / PeriodSeconds``) — here the caller
  supplies ``current_bar`` and the failure bar directly, keeping the core
  MT5-free and synthetic-state-testable;
* ``reset_day`` mirrors v25's daily rollover ("reset failed sweep guard
  daily so yesterday's failures don't block today").

The guard is PURE state over injected scalars — no MT5 dependency, fully
unit-testable (:class:`SweepGuardState` may be injected for replay).
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.config.locked_constants import (
    SWEEP_GUARD_COOLDOWN_BARS,
    SWEEP_GUARD_ZONE_ATR,
)

__all__ = ["SweepGuard", "SweepGuardState"]


@dataclass(slots=True)
class SweepGuardState:
    """Synthetic per-direction state (replayable / unit-testable)."""

    failed_sweep_level_long: float = 0.0   # level of the last failed LONG sweep (0 = none)
    failed_sweep_bar_long: int = 0         # bar index of that failure
    failed_sweep_level_short: float = 0.0  # level of the last failed SHORT sweep (0 = none)
    failed_sweep_bar_short: int = 0        # bar index of that failure


class SweepGuard:
    """Failed-sweep re-entry guard (LOCKED_DECISIONS §28.6).

    Thresholds are imported from ``locked_constants`` — zero hardcoding.
    """

    def __init__(
        self,
        *,
        zone_atr: float = SWEEP_GUARD_ZONE_ATR,
        cooldown_bars: int = SWEEP_GUARD_COOLDOWN_BARS,
        state: SweepGuardState | None = None,
    ) -> None:
        self.zone_atr = zone_atr
        self.cooldown_bars = cooldown_bars
        self._state = state if state is not None else SweepGuardState()

    @property
    def state(self) -> SweepGuardState:
        """Read-only handle on the guard's synthetic state."""
        return self._state

    # ------------------------------------------------------------------ #
    # Failure recording (on a losing trade close, per v25)
    # ------------------------------------------------------------------ #
    def record_failed_sweep(
        self, *, sweep_level: float, bar_index: int, is_long: bool
    ) -> None:
        """Record a failed sweep level + bar for one direction."""
        if is_long:
            self._state.failed_sweep_level_long = sweep_level
            self._state.failed_sweep_bar_long = bar_index
        else:
            self._state.failed_sweep_level_short = sweep_level
            self._state.failed_sweep_bar_short = bar_index

    # ------------------------------------------------------------------ #
    # Entry gate
    # ------------------------------------------------------------------ #
    def is_blocked(
        self, *, sweep_level: float, atr: float, current_bar: int, is_long: bool
    ) -> bool:
        """True when a new sweep at ``sweep_level`` is blocked for a side.

        Mirrors v25's ``IsFailedSweepBlocked(is_long)``: no recorded failure
        → pass; candidate outside ``zone_atr × atr`` of the failed level →
        pass; cooldown elapsed → pass; otherwise blocked.
        """
        if is_long:
            failed_level = self._state.failed_sweep_level_long
            failed_bar = self._state.failed_sweep_bar_long
        else:
            failed_level = self._state.failed_sweep_level_short
            failed_bar = self._state.failed_sweep_bar_short
        if failed_level <= 0.0 or atr <= 0.0:
            return False
        zone = self.zone_atr * atr
        same_level = abs(sweep_level - failed_level) <= zone
        if not same_level:
            return False
        bars_since_failure = current_bar - failed_bar
        return bars_since_failure < self.cooldown_bars

    # ------------------------------------------------------------------ #
    # Daily rollover
    # ------------------------------------------------------------------ #
    def reset_day(self) -> None:
        """Clear both directions' failed-sweep state on a new day (v25)."""
        self._state.failed_sweep_level_long = 0.0
        self._state.failed_sweep_bar_long = 0
        self._state.failed_sweep_level_short = 0.0
        self._state.failed_sweep_bar_short = 0