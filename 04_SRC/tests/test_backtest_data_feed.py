"""Phase 6 M1 — data feed: series validation, index lookup, multi-TF shape."""

from datetime import timedelta

import pytest

from smc.backtest.data_feed import CandleSeries, MultiTimeframeFeed
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle

ROWS = [
    (100.0, 100.4, 99.8, 100.2),
    (100.2, 100.7, 100.0, 100.5),
    (100.5, 101.1, 100.4, 100.9),
]


def _series(candle_factory, rows=ROWS, timeframe=Timeframe.M5):
    return CandleSeries(
        candle_factory(rows, timeframe=timeframe), timeframe=timeframe
    )


# ---------------------------------------------------------------------- #
# CandleSeries validation
# ---------------------------------------------------------------------- #
def test_empty_series_rejected():
    with pytest.raises(ValueError, match="at least one candle"):
        CandleSeries([], timeframe=Timeframe.M5)


def test_wrong_timeframe_candle_rejected(candle_factory):
    candles = candle_factory(ROWS, timeframe=Timeframe.M1)
    with pytest.raises(ValueError, match="timeframe"):
        CandleSeries(candles, timeframe=Timeframe.M5)


def test_out_of_order_bars_rejected(candle_factory):
    candles = candle_factory(ROWS, timeframe=Timeframe.M5)
    candles[0], candles[1] = candles[1], candles[0]  # break chronology
    with pytest.raises(ValueError, match="strictly ascending"):
        CandleSeries(candles, timeframe=Timeframe.M5)


def test_duplicate_timestamp_rejected(candle_factory):
    candles = candle_factory(ROWS, timeframe=Timeframe.M5)
    original = candles[1]
    duplicate = Candle(
        timestamp=original.timestamp,  # same timestamp → not strictly ascending
        open=original.open,
        high=original.high,
        low=original.low,
        close=original.close,
        timeframe=original.timeframe,
    )
    candles.append(duplicate)
    with pytest.raises(ValueError, match="strictly ascending"):
        CandleSeries(candles, timeframe=Timeframe.M5)


# ---------------------------------------------------------------------- #
# CandleSeries access
# ---------------------------------------------------------------------- #
def test_iteration_order_and_count(candle_factory):
    series = _series(candle_factory)
    assert len(series) == 3
    stamps = [c.timestamp for c in series]
    assert stamps == sorted(stamps)  # ascending iteration
    assert series[2].close == pytest.approx(100.9)


def test_first_last_timestamps(candle_factory):
    series = _series(candle_factory)
    assert series.first_timestamp < series.last_timestamp
    assert series.last_timestamp - series.first_timestamp == timedelta(minutes=10)


def test_index_at_exact_match(candle_factory):
    series = _series(candle_factory)
    assert series.index_at(series.candles[1].timestamp) == 1


def test_index_at_missing_timestamp_raises(candle_factory):
    series = _series(candle_factory)
    between = series.candles[0].timestamp + timedelta(minutes=1)
    with pytest.raises(KeyError):
        series.index_at(between)  # no silent snapping


def test_index_at_or_before_and_up_to(candle_factory):
    series = _series(candle_factory)
    t1 = series.candles[1].timestamp
    assert series.index_at_or_before(t1) == 1
    assert series.index_at_or_before(t1 + timedelta(minutes=1)) == 1
    before_all = series.first_timestamp - timedelta(minutes=5)
    assert series.index_at_or_before(before_all) is None
    assert series.up_to(t1) == series.candles[:2]
    assert series.up_to(before_all) == []


# ---------------------------------------------------------------------- #
# MultiTimeframeFeed
# ---------------------------------------------------------------------- #
def test_feed_primary_only(candle_factory):
    feed = MultiTimeframeFeed(_series(candle_factory))
    assert feed.primary_timeframe is Timeframe.M5
    assert feed.timeframes == [Timeframe.M5]
    assert not feed.has_series(Timeframe.H4)


def test_feed_with_htf_series(candle_factory):
    primary = _series(candle_factory)
    htf_candles = candle_factory(
        [(2000.0, 2010.0, 1990.0, 2005.0)] * 3,
        timeframe=Timeframe.H4,
        start=primary.first_timestamp - timedelta(days=2),
    )
    feed = MultiTimeframeFeed(
        primary, {Timeframe.H4: CandleSeries(htf_candles, Timeframe.H4)}
    )
    assert feed.has_series(Timeframe.H4)
    assert feed.series(Timeframe.H4).timeframe is Timeframe.H4
    assert feed.timeframes == [Timeframe.M5, Timeframe.H4]


def test_feed_rejects_duplicate_primary_in_htf(candle_factory):
    primary = _series(candle_factory)
    with pytest.raises(ValueError, match="duplicate"):
        MultiTimeframeFeed(primary, {Timeframe.M5: primary})


def test_feed_rejects_ltf_key_in_htf_map(candle_factory):
    primary = _series(candle_factory)
    m1 = CandleSeries(
        candle_factory(ROWS, timeframe=Timeframe.M1), timeframe=Timeframe.M1
    )
    with pytest.raises(ValueError, match="HTF timeframe"):
        MultiTimeframeFeed(primary, {Timeframe.M1: m1})


def test_feed_rejects_mismatched_htf_candles(candle_factory):
    primary = _series(candle_factory)
    m1 = CandleSeries(
        candle_factory(ROWS, timeframe=Timeframe.M1), timeframe=Timeframe.M1
    )
    with pytest.raises(ValueError, match="carries"):
        MultiTimeframeFeed(primary, {Timeframe.H4: m1})


def test_feed_rejects_htf_starting_after_primary(candle_factory):
    primary = _series(candle_factory)
    late_htf = candle_factory(
        [(2000.0, 2010.0, 1990.0, 2005.0)],
        timeframe=Timeframe.H4,
        start=primary.last_timestamp + timedelta(minutes=5),
    )
    with pytest.raises(ValueError, match="after the primary series start"):
        MultiTimeframeFeed(
            primary, {Timeframe.H4: CandleSeries(late_htf, Timeframe.H4)}
        )


def test_feed_htf_history_may_precede_primary(candle_factory):
    # HTF series starting EARLIER than the primary is fine (warm-up history).
    primary = _series(candle_factory)
    early_htf = candle_factory(
        [(2000.0, 2010.0, 1990.0, 2005.0)],
        timeframe=Timeframe.H4,
        start=primary.first_timestamp - timedelta(days=3),
    )
    feed = MultiTimeframeFeed(
        primary, {Timeframe.H4: CandleSeries(early_htf, Timeframe.H4)}
    )
    assert feed.series(Timeframe.H4).first_timestamp < primary.first_timestamp


def test_feed_index_at_or_before_across_timeframes(candle_factory):
    # Basic alignment hook: at a primary timestamp, the HTF index is the
    # last HTF bar that has CLOSED at or before that moment.
    primary = _series(candle_factory)
    htf_candles = candle_factory(
        [(2000.0, 2010.0, 1990.0, 2005.0)] * 2,
        timeframe=Timeframe.H4,
        start=primary.first_timestamp - timedelta(hours=4),
    )
    feed = MultiTimeframeFeed(
        primary, {Timeframe.H4: CandleSeries(htf_candles, Timeframe.H4)}
    )
    mid = primary.candles[1].timestamp
    htf_index = feed.series(Timeframe.H4).index_at_or_before(mid)
    assert htf_index == 1  # second H4 bar (first + 4h) covers the M5 timeline
