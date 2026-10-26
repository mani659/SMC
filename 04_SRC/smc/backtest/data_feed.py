"""Backtest data feed — historical candle access (Phase 6, Milestone 1).

M1 scope: a clean, deterministic, MT5-free feed over already-loaded
``list[Candle]`` series. Loading itself stays where it is today —
``smc.data.csv_loader.load_ohlcv`` (single-TF CSV) builds the lists; this
module CONTAINS and indexes them.

Multi-TF shape (approved design §8.10): the primary execution timeframe
plus optional HTF series (e.g. M5 execution + D1/H4 for M8, §21/§26) in one
container keyed by :class:`~smc.config.timeframe.Timeframe`. M1 only
validates the container and its alignment preconditions — consumers (M2+
triggers, M8 detection) decide how to read the HTF series.

Determinism contract: every series is validated to be strictly ascending in
timestamp, single-timeframe, and timezone-aware; access is by integer bar
index or exact timestamp lookup. Nothing here reads wall-clock time.
"""

from __future__ import annotations

from bisect import bisect_left
from datetime import datetime

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle

__all__ = ["CandleSeries", "MultiTimeframeFeed"]


class CandleSeries:
    """One validated, indexable OHLCV series (single timeframe).

    Wraps a chronological ``list[Candle]`` and adds O(log n) timestamp
    lookup plus index-range slicing. The list is NOT copied — the caller
    keeps ownership; this module only reads.
    """

    def __init__(self, candles: list[Candle], timeframe: Timeframe) -> None:
        if not candles:
            raise ValueError("CandleSeries requires at least one candle")
        for index, candle in enumerate(candles):
            if candle.timeframe is not timeframe:
                raise ValueError(
                    f"candle {index} has timeframe {candle.timeframe.name}, "
                    f"expected {timeframe.name}"
                )
            if index > 0 and not candles[index - 1].timestamp < candle.timestamp:
                raise ValueError(
                    f"candles not strictly ascending at index {index} "
                    f"({candles[index - 1].timestamp} !< {candle.timestamp})"
                )
        self._candles = candles
        self._timeframe = timeframe
        self._timestamps = [c.timestamp for c in candles]

    # ------------------------------------------------------------------ #
    # Access
    # ------------------------------------------------------------------ #
    @property
    def timeframe(self) -> Timeframe:
        return self._timeframe

    @property
    def candles(self) -> list[Candle]:
        """The underlying candle list (read-only by convention)."""
        return self._candles

    def __len__(self) -> int:
        return len(self._candles)

    def __getitem__(self, index: int) -> Candle:
        return self._candles[index]

    def __iter__(self):
        return iter(self._candles)

    @property
    def first_timestamp(self) -> datetime:
        return self._candles[0].timestamp

    @property
    def last_timestamp(self) -> datetime:
        return self._candles[-1].timestamp

    def index_at(self, timestamp: datetime) -> int:
        """Bar index whose timestamp is exactly ``timestamp``.

        Raises ``KeyError`` when no bar carries that timestamp (no silent
        nearest-bar snapping — misalignment must be loud).
        """
        position = bisect_left(self._timestamps, timestamp)
        if position < len(self._timestamps) and self._timestamps[position] == timestamp:
            return position
        raise KeyError(f"no bar at timestamp {timestamp!r} in {self._timeframe.name} series")

    def index_at_or_before(self, timestamp: datetime) -> int | None:
        """Index of the last bar with ``bar.timestamp <= timestamp``.

        ``None`` when ``timestamp`` precedes the first bar (nothing has
        happened yet on this timeframe).
        """
        position = bisect_left(self._timestamps, timestamp)
        if position < len(self._timestamps) and self._timestamps[position] == timestamp:
            return position
        return position - 1 if position > 0 else None

    def up_to(self, timestamp: datetime) -> list[Candle]:
        """Candles with ``timestamp <=`` the given time (closed bars only)."""
        index = self.index_at_or_before(timestamp)
        return self._candles[: index + 1] if index is not None else []


class MultiTimeframeFeed:
    """Primary execution-TF series + optional HTF series in one container.

    Shape contract (design §8.10): ``primary`` is the execution timeframe
    the loop walks; every other key is a higher timeframe aligned to the
    same absolute UTC timeline (each series independently validated by
    :class:`CandleSeries`). M1 enforces: no duplicate timeframes, HTF keys
    must be HTF-class per §27, and the primary series must not START before
    any HTF series' first bar (an HTF gap at the head would silently starve
    M8 detection — fail loudly instead).
    """

    def __init__(
        self,
        primary: CandleSeries,
        htf: dict[Timeframe, CandleSeries] | None = None,
    ) -> None:
        self._primary = primary
        self._series: dict[Timeframe, CandleSeries] = {primary.timeframe: primary}
        for timeframe, series in (htf or {}).items():
            if timeframe is primary.timeframe:
                raise ValueError("HTF series cannot duplicate the primary timeframe")
            if timeframe in self._series:
                raise ValueError(f"duplicate timeframe in feed: {timeframe.name}")
            if not timeframe.is_htf():
                raise ValueError(
                    f"HTF map key must be an HTF timeframe (D1/H4/H1), "
                    f"got {timeframe.name}"
                )
            if series.timeframe is not timeframe:
                raise ValueError(
                    f"HTF series declared {timeframe.name} but carries "
                    f"{series.timeframe.name} candles"
                )
            self._series[timeframe] = series
        primary_start = primary.first_timestamp
        for timeframe, series in self._series.items():
            if timeframe is primary.timeframe:
                continue
            if series.first_timestamp > primary_start:
                raise ValueError(
                    f"{timeframe.name} series starts at {series.first_timestamp}, "
                    f"after the primary series start {primary_start} — the HTF "
                    f"history must cover the whole primary timeline"
                )

    # ------------------------------------------------------------------ #
    # Access
    # ------------------------------------------------------------------ #
    @property
    def primary(self) -> CandleSeries:
        """The execution-timeframe series the bar loop walks."""
        return self._primary

    @property
    def primary_timeframe(self) -> Timeframe:
        return self._primary.timeframe

    def series(self, timeframe: Timeframe) -> CandleSeries:
        """The series for ``timeframe`` (KeyError when absent — loud)."""
        return self._series[timeframe]

    def has_series(self, timeframe: Timeframe) -> bool:
        return timeframe in self._series

    @property
    def timeframes(self) -> list[Timeframe]:
        return sorted(self._series, key=lambda tf: tf.minutes)
