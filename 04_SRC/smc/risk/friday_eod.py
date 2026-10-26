"""Phase 5 — Friday EOD guard (v25_DIAG ``CheckFridayClose``, ported to
Python).

LOCKED_DECISIONS §28.4: force-close all positions (and cancel pending
orders) at ``FRIDAY_EOD_CLOSE_HOUR_UTC`` (20:00 UTC) on Friday, ONCE per
Friday — do not keep closing after the first trigger.

v25_DIAG semantics preserved verbatim:

* the decision is made from a UTC datetime only (``day_of_week == 5 &&
  hour >= FRIDAY_EOD_CLOSE_HOUR_UTC`` in MQL5 terms — Friday = weekday 4 in
  Python's ``datetime.weekday()``);
* the once-per-Friday flag resets on any bar that is NOT Friday-at/after-
  close (so it re-arms naturally for the next Friday);
* after a trigger the flag latches until the next reset.

The CORE only decides *whether* to force close (pure predicate + latch over
injected datetimes). Actually closing positions / cancelling orders is the
caller's job (the Phase 5 risk engine orchestrates the broker calls) — no
MT5 dependency here, fully unit-testable with synthetic datetimes
(:class:`FridayEodState` may be injected for replay).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from smc.config.locked_constants import FRIDAY_EOD_CLOSE_HOUR_UTC
from smc.utils.timestamps import to_utc

__all__ = ["FridayEod", "FridayEodState"]


@dataclass(slots=True)
class FridayEodState:
    """Synthetic state of one Friday-EOD guard (replayable / unit-testable)."""

    closed_this_friday: bool = False


class FridayEod:
    """Once-per-Friday force-close guard (LOCKED_DECISIONS §28.4).

    The threshold is imported from ``locked_constants`` — zero hardcoding.
    """

    def __init__(
        self,
        *,
        close_hour_utc: int = FRIDAY_EOD_CLOSE_HOUR_UTC,
        state: FridayEodState | None = None,
    ) -> None:
        self.close_hour_utc = close_hour_utc
        self._state = state if state is not None else FridayEodState()

    @property
    def state(self) -> FridayEodState:
        """Read-only handle on the guard's synthetic state."""
        return self._state

    def should_force_close(self, at: datetime) -> bool:
        """True exactly once on Friday at/after the close hour.

        Non-Friday bars (or Friday before the close hour) reset the latch;
        after a trigger the latch holds until the next reset — mirroring
        v25's ``g_fridayClosed`` flag.
        """
        at = to_utc(at)
        is_friday_close = at.weekday() == 4 and at.hour >= self.close_hour_utc
        if not is_friday_close:
            self._state.closed_this_friday = False
            return False
        if self._state.closed_this_friday:
            return False
        self._state.closed_this_friday = True
        return True

    def reset(self) -> None:
        """Explicitly re-arm the guard (equivalent to the non-Friday reset)."""
        self._state.closed_this_friday = False