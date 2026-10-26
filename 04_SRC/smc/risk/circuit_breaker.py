"""Phase 5 — circuit breaker (v25_DIAG ``TradeAllowed`` / consecutive-loss
tracking, ported to Python).

LOCKED_DECISIONS §28.2: after ``CIRCUIT_BREAKER_LOSS_COUNT`` (3) consecutive
losses, block all new entries for ``CIRCUIT_BREAKER_PAUSE_HOURS`` (4) hours
(Z-score validated −2.27 — losses cluster in time).

v25_DIAG semantics preserved verbatim:

* consecutive losses are counted across closes; any WIN resets the counter
  to 0 and (if the breaker is active) releases it immediately;
* the breaker TRIGGERS at the close that pushes the counter to
  ``CIRCUIT_BREAKER_LOSS_COUNT`` — ``locked_at`` is that close time;
* :meth:`CircuitBreaker.is_blocked` returns True while the pause is active
  (``now - locked_at < CIRCUIT_BREAKER_PAUSE_HOURS``) and releases the
  breaker once the pause has fully elapsed;
* a NEW DAY resets the consecutive-loss counter (v25 resets it in the
  daily-rollover block) — :meth:`CircuitBreaker.reset_day` exists for that.

The breaker is PURE state over injected datetimes — no MT5 / account
dependency, so it is fully unit-testable with synthetic state
(:class:`CircuitBreakerState` may be injected for replay).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from smc.config.locked_constants import (
    CIRCUIT_BREAKER_LOSS_COUNT,
    CIRCUIT_BREAKER_PAUSE_HOURS,
)
from smc.utils.timestamps import to_utc

__all__ = ["CircuitBreaker", "CircuitBreakerState"]


@dataclass(slots=True)
class CircuitBreakerState:
    """Synthetic state of one circuit breaker (replayable / unit-testable)."""

    consecutive_losses: int = 0
    active: bool = False
    locked_at: datetime | None = None  # UTC; set when the breaker triggers

    def __post_init__(self) -> None:
        if self.locked_at is not None:
            self.locked_at = to_utc(self.locked_at)


class CircuitBreaker:
    """Consecutive-loss circuit breaker (LOCKED_DECISIONS §28.2).

    Thresholds are imported from ``locked_constants`` — zero hardcoding.
    """

    def __init__(
        self,
        *,
        loss_count: int = CIRCUIT_BREAKER_LOSS_COUNT,
        pause_hours: int = CIRCUIT_BREAKER_PAUSE_HOURS,
        state: CircuitBreakerState | None = None,
    ) -> None:
        self.loss_count = loss_count
        self.pause_hours = pause_hours
        self._state = state if state is not None else CircuitBreakerState()

    @property
    def state(self) -> CircuitBreakerState:
        """Read-only handle on the breaker's synthetic state."""
        return self._state

    # ------------------------------------------------------------------ #
    # Trade-close recording
    # ------------------------------------------------------------------ #
    def record_result(self, win: bool, at: datetime) -> None:
        """Record one closed trade outcome.

        ``win=True`` resets the consecutive-loss counter and releases an
        active breaker (v25: "any win resets circuit breaker"). ``win=False``
        increments the counter and triggers the pause once it reaches
        ``loss_count``.
        """
        at = to_utc(at)
        if win:
            self._state.consecutive_losses = 0
            if self._state.active:
                self._state.active = False
                self._state.locked_at = None
            return
        self._state.consecutive_losses += 1
        if (
            not self._state.active
            and self._state.consecutive_losses >= self.loss_count
        ):
            self._state.active = True
            self._state.locked_at = at

    # ------------------------------------------------------------------ #
    # Entry gate
    # ------------------------------------------------------------------ #
    def is_blocked(self, at: datetime) -> bool:
        """True while the pause is active (block all new entries).

        Mirrors v25's entry gate: once ``now - locked_at >= pause_hours``
        the breaker is RELEASED (active=False, locked_at=None) and trading
        resumes. Idempotent — calling with a later time keeps working.
        """
        at = to_utc(at)
        if not self._state.active or self._state.locked_at is None:
            return False
        elapsed = at - self._state.locked_at
        if elapsed < timedelta(hours=self.pause_hours):
            return True
        self._state.active = False
        self._state.locked_at = None
        return False

    # ------------------------------------------------------------------ #
    # Daily rollover
    # ------------------------------------------------------------------ #
    def reset_day(self) -> None:
        """Reset the consecutive-loss counter on a new day (v25 daily
        rollover also clears the circuit breaker)."""
        self._state.consecutive_losses = 0
        if self._state.active:
            self._state.active = False
            self._state.locked_at = None