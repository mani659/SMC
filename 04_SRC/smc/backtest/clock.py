"""Deterministic backtest clock (Phase 6, Milestone 1).

The injected-clock contract (post-audit I5): trading decisions never read
the wall clock — the runner supplies ``now``. In backtest, ``now`` IS the
current bar's timestamp; :class:`BarClock` makes that explicit and
tamper-evident:

* the clock starts unset (reading it before the first bar is a loud error,
  not a silent zero time);
* it advances strictly bar-by-bar to strictly increasing timestamps
  (``advance`` raises on a non-advancing step — the loop can never run the
  same bar twice or run time backwards);
* :meth:`now` returns the CURRENT bar's timestamp only.

No wall-clock read anywhere: there is no ``datetime.now`` in this module.
"""

from __future__ import annotations

from datetime import datetime

from smc.utils.timestamps import to_utc

__all__ = ["BarClock", "ClockNotSetError"]


class ClockNotSetError(RuntimeError):
    """Raised when the clock is read before the first bar advanced it."""


class BarClock:
    """Deterministic bar clock — ``now`` is the current bar's timestamp.

    Timezone handling: datetimes are UTC-normalized via
    ``smc.utils.timestamps.to_utc`` (naive values are treated as UTC, the
    same convention as every Phase 0–5 component).
    """

    def __init__(self) -> None:
        self._now: datetime | None = None

    @property
    def now(self) -> datetime:
        """Current bar timestamp (UTC-normalized)."""
        if self._now is None:
            raise ClockNotSetError(
                "clock not set — read .now only after the loop advanced to a bar"
            )
        return self._now

    @property
    def is_set(self) -> bool:
        return self._now is not None

    def advance(self, timestamp: datetime) -> datetime:
        """Advance to ``timestamp`` (strictly forward) and return it.

        Raises ``ValueError`` on a non-advancing step (equal or earlier
        than the current timestamp) so a malformed feed cannot make the
        loop run the same bar twice.
        """
        stamp = to_utc(timestamp)
        if self._now is not None and stamp <= self._now:
            raise ValueError(
                f"clock must advance strictly forward: {stamp} <= {self._now}"
            )
        self._now = stamp
        return stamp

    def reset(self) -> None:
        """Return to the unset state (fresh run)."""
        self._now = None
