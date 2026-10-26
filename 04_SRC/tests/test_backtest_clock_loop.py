"""Phase 6 M1 — deterministic clock + thin bar loop."""

from datetime import datetime, timedelta, timezone

import pytest

from smc.backtest.bar_loop import BarHandler, BarLoop, RecordingHandler
from smc.backtest.clock import BarClock, ClockNotSetError
from smc.backtest.data_feed import CandleSeries
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle

ROWS = [
    (100.0, 100.4, 99.8, 100.2),
    (100.2, 100.7, 100.0, 100.5),
    (100.5, 101.1, 100.4, 100.9),
    (100.9, 101.5, 100.7, 101.3),
]


def _series(candle_factory, rows=ROWS):
    return CandleSeries(
        candle_factory(rows, timeframe=Timeframe.M5), timeframe=Timeframe.M5
    )


# ---------------------------------------------------------------------- #
# BarClock
# ---------------------------------------------------------------------- #
def test_clock_unset_read_raises():
    clock = BarClock()
    assert not clock.is_set
    with pytest.raises(ClockNotSetError):
        clock.now  # noqa: B018 — property access must raise


def test_clock_advance_sets_and_returns_now():
    clock = BarClock()
    stamp = datetime(2026, 1, 1, 9, 5, tzinfo=timezone.utc)
    assert clock.advance(stamp) == stamp
    assert clock.now == stamp
    assert clock.is_set


def test_clock_normalizes_naive_to_utc():
    clock = BarClock()
    naive = datetime(2026, 1, 1, 9, 5)  # naive → UTC by convention
    clock.advance(naive)
    assert clock.now.tzinfo is not None
    assert clock.now == datetime(2026, 1, 1, 9, 5, tzinfo=timezone.utc)


def test_clock_rejects_non_advancing_step():
    clock = BarClock()
    t0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    clock.advance(t0)
    with pytest.raises(ValueError, match="strictly forward"):
        clock.advance(t0)  # same bar twice
    with pytest.raises(ValueError, match="strictly forward"):
        clock.advance(t0 - timedelta(minutes=5))  # backwards


def test_clock_reset_rearms():
    clock = BarClock()
    clock.advance(datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc))
    clock.reset()
    assert not clock.is_set
    with pytest.raises(ClockNotSetError):
        clock.now  # noqa: B018


def test_clock_never_reads_wall_time():
    # The module must not contain a wall-clock read (injected-now contract).
    import ast
    import inspect

    import smc.backtest.clock as clock_module

    # AST-based check: docstrings/comments are NOT executable code, so a
    # prose mention of ``datetime.now`` cannot false-positive here.
    tree = ast.parse(inspect.getsource(clock_module))
    wall_clock_reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in ("now", "utcnow")
    ]
    assert wall_clock_reads == []


# ---------------------------------------------------------------------- #
# BarLoop
# ---------------------------------------------------------------------- #
def test_loop_iterates_all_bars_in_order(candle_factory):
    series = _series(candle_factory)
    recorder = RecordingHandler()
    loop = BarLoop(series, recorder)
    stats = loop.run()
    assert stats.bars_processed == 4
    assert [index for index, _ in recorder.visited] == [0, 1, 2, 3]
    assert stats.start == series.first_timestamp
    assert stats.end == series.last_timestamp


def test_loop_now_equals_bar_timestamp(candle_factory):
    series = _series(candle_factory)
    recorder = RecordingHandler()
    loop = BarLoop(series, recorder)
    loop.run()
    for index, now in recorder.visited:
        assert now == series[index].timestamp  # deterministic injected now


def test_loop_window_bounds_are_exact_timestamps(candle_factory):
    series = _series(candle_factory)
    recorder = RecordingHandler()
    loop = BarLoop(series, recorder)
    stats = loop.run(
        start_timestamp=series.candles[1].timestamp,
        end_timestamp=series.candles[2].timestamp,
    )
    assert [index for index, _ in recorder.visited] == [1, 2]
    assert stats.bars_processed == 2


def test_loop_missing_window_bound_raises(candle_factory):
    series = _series(candle_factory)
    loop = BarLoop(series, RecordingHandler())
    between = series.candles[1].timestamp + timedelta(minutes=1)
    with pytest.raises(KeyError):
        loop.run(start_timestamp=between)


def test_loop_empty_window_raises(candle_factory):
    series = _series(candle_factory)
    loop = BarLoop(series, RecordingHandler())
    with pytest.raises(ValueError, match="empty run window"):
        loop.run(
            start_timestamp=series.candles[2].timestamp,
            end_timestamp=series.candles[1].timestamp,
        )


def test_loop_single_bar_run(candle_factory):
    series = _series(candle_factory)
    recorder = RecordingHandler()
    stats = BarLoop(series, recorder).run(
        start_timestamp=series.candles[0].timestamp,
        end_timestamp=series.candles[0].timestamp,
    )
    assert stats.bars_processed == 1
    assert stats.start == stats.end


def test_loop_rerun_fails_on_clock_regression(candle_factory):
    # Re-running the same loop from the start would run time backwards —
    # the strict clock must surface it (fresh loop per run is the contract).
    series = _series(candle_factory)
    loop = BarLoop(series, RecordingHandler())
    loop.run()
    with pytest.raises(ValueError, match="strictly forward"):
        loop.run()


def test_loop_handler_receives_candle_and_clock(candle_factory):
    series = _series(candle_factory)
    seen: list[tuple[int, datetime]] = []

    class Probe(BarHandler):
        def on_bar(self, bar, bar_index, clock):
            seen.append((bar_index, clock.now))
            assert bar is series[bar_index]

    BarLoop(series, Probe()).run()
    assert len(seen) == 4
    assert seen[2][1] == series[2].timestamp


def test_loop_handler_exception_aborts(candle_factory):
    series = _series(candle_factory)

    class Boom(BarHandler):
        def on_bar(self, bar, bar_index, clock):
            if bar_index == 2:
                raise RuntimeError("boom")

    loop = BarLoop(series, Boom())
    with pytest.raises(RuntimeError):
        loop.run()
    assert loop.stats.bars_processed == 2  # deterministic partial progress
