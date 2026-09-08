"""Thin bar-driven loop (Phase 6, Milestone 1).

M1 scope ONLY: walk the primary series bar-by-bar in deterministic order,
set the deterministic clock on every bar, and hand each bar to a pluggable
handler. No fills, no orders, no risk, no engine wiring — those land in
M2/M3 behind the same handler seam.

Design (approved SMC_PHASE_6_DESIGN.md §1/§2):

* ONE loop, two backends — this loop is the backtest/live shared skeleton.
  M5's paper runner reuses it with a broker-backed feed instead of
  duplicating the iteration order.
* The clock is THE injected ``now``: the handler receives the bar plus the
  clock, and everything downstream reads ``clock.now`` (never wall time).
* Handlers implement :class:`BarHandler` (a recording no-op is shipped for
  M1 tests); M2+ attaches fill/order logic as additional handlers.
* :class:`LoopStats` records bars processed and the start/end timestamps —
  the minimal observability M1 requires.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from smc.backtest.clock import BarClock
from smc.backtest.data_feed import CandleSeries
from smc.core.candle import Candle

__all__ = ["BarHandler", "RecordingHandler", "BarLoop", "LoopStats"]


class BarHandler(ABC):
    """Per-bar hook. M1 ships a recorder; M2+ attach trading logic here."""

    @abstractmethod
    def on_bar(self, bar: Candle, bar_index: int, clock: BarClock) -> None:
        """Handle one closed bar (``clock.now`` == the bar's timestamp)."""
        raise NotImplementedError


class RecordingHandler(BarHandler):
    """No-op handler that records the visit order (M1 tests + replay)."""

    def __init__(self) -> None:
        self.visited: list[tuple[int, datetime]] = []

    def on_bar(self, bar: Candle, bar_index: int, clock: BarClock) -> None:
        self.visited.append((bar_index, clock.now))


@dataclass(slots=True)
class LoopStats:
    """Basic loop bookkeeping (M1 minimum observability)."""

    bars_processed: int = 0
    start: datetime | None = None
    end: datetime | None = None


class BarLoop:
    """Walk a :class:`CandleSeries` bar-by-bar with a deterministic clock."""

    def __init__(self, series: CandleSeries, handler: BarHandler) -> None:
        self._series = series
        self._handler = handler
        self._clock = BarClock()
        self.stats = LoopStats()

    @property
    def clock(self) -> BarClock:
        """The loop's deterministic clock (``now`` = current bar timestamp)."""
        return self._clock

    def run(
        self,
        *,
        start_timestamp: datetime | None = None,
        end_timestamp: datetime | None = None,
    ) -> LoopStats:
        """Iterate the primary series from ``start_timestamp`` to the end.

        Bounds are INCLUSIVE timestamps (``KeyError`` when absent — the
        feed's exact-timestamp contract, no silent snapping). ``now`` is
        set BEFORE the handler runs; a handler that raises aborts the loop
        (deterministic partial state is the caller's to inspect).
        """
        first = (
            0
            if start_timestamp is None
            else self._series.index_at(start_timestamp)
        )
        last = (
            len(self._series) - 1
            if end_timestamp is None
            else self._series.index_at(end_timestamp)
        )
        if first > last:
            raise ValueError(
                f"empty run window: start {start_timestamp} is after end {end_timestamp}"
            )
        for index in range(first, last + 1):
            bar = self._series[index]
            self._clock.advance(bar.timestamp)
            self._handler.on_bar(bar, index, self._clock)
            if self.stats.start is None:
                self.stats.start = bar.timestamp
            self.stats.end = bar.timestamp
            self.stats.bars_processed += 1
        return self.stats
