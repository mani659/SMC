"""P2b — sweep attribution over the pool, bounded by ``enter_at`` (R4)."""

from datetime import datetime, timedelta, timezone

import pytest

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import LiquidityType, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.liquidity import (
    LiquidityPool,
    PoolFamily,
    PoolLevel,
    PoolSide,
    attribute_sweeps,
    resolve_start_index,
    sweeps_on_bar,
)
from smc.liquidity.pool import from_pdh_pdl

START = datetime(2026, 3, 2, tzinfo=timezone.utc)  # Monday


def _series(override=None, count=12):
    """Flat M5 bars around 100; ``override`` maps index -> (high, low, close)."""
    bars = []
    for i in range(count):
        high, low, close = 101.0, 99.0, 100.0
        if override and i in override:
            high, low, close = override[i]
        open_ = 100.0
        bars.append(
            Candle(
                timestamp=START + timedelta(minutes=5 * i),
                open=open_,
                high=high,
                low=low,
                close=close,
                timeframe=Timeframe.M5,
            )
        )
    return bars


def _level(side, price, enter_at, *, formed_at=None, period_id="2026-03-02", family=PoolFamily.PREVIOUS_DAY,
           exit_at=None):
    return PoolLevel(
        family=family,
        side=side,
        price=price,
        period_id=period_id,
        source_tf=Timeframe.M5,
        formed_at=formed_at,
        enter_at=enter_at,
        exit_at=exit_at,
    )


def test_resolve_start_index_is_first_bar_at_or_after_enter_at():
    series = _series()
    assert resolve_start_index(series, series[5].timestamp) == 5
    # a time between bars resolves to the next bar
    assert resolve_start_index(series, series[5].timestamp + timedelta(seconds=1)) == 6
    # after the series end -> None (not applicable, never silently zero)
    assert resolve_start_index(series, series[-1].timestamp + timedelta(minutes=5)) is None


def test_resolve_start_index_fails_closed_on_unordered_series():
    series = _series()
    series[5], series[6] = series[6], series[5]
    with pytest.raises(ValueError, match="strictly ascending"):
        resolve_start_index(series, series[0].timestamp)


def test_pierce_before_enter_at_is_ignored():
    # bar 2 pierces 100 and closes back below -> would be a sweep if scanned from formed_at
    series = _series({2: (105.0, 99.0, 98.0)})
    enter_at = series[6].timestamp
    level = _level(PoolSide.BSL, 100.0, enter_at, formed_at=series[0].timestamp)
    pool = LiquidityPool()
    pool.add(level)

    report = attribute_sweeps(pool, series)
    assert report.hits == ()
    assert report.not_applicable == ()


def test_pierce_after_enter_at_is_a_hit():
    series = _series({8: (105.0, 99.0, 98.0)})
    enter_at = series[6].timestamp
    level = _level(PoolSide.BSL, 100.0, enter_at, formed_at=series[0].timestamp)
    pool = LiquidityPool()
    pool.add(level)

    report = attribute_sweeps(pool, series)
    assert len(report.hits) == 1
    hit = report.hits[0]
    assert hit.sweep_bar_index == 8
    assert hit.level_id == ("previous_day", "bsl", "2026-03-02")
    assert hit.direction == "short"
    assert hit.start_index_used == 6


def test_scan_starts_at_enter_at_not_formed_at():
    """The adapter never forwards formed_at; the bound is purely enter_at."""
    series = _series({3: (106.0, 99.0, 97.0), 9: (107.0, 99.0, 96.0)})
    level = _level(
        PoolSide.BSL, 100.0, series[7].timestamp, formed_at=series[0].timestamp
    )
    pool = LiquidityPool()
    pool.add(level)

    hit = attribute_sweeps(pool, series).hits[0]
    assert hit.start_index_used == 7
    assert hit.sweep_bar_index == 9


def test_exited_level_is_not_attributed():
    series = _series({8: (105.0, 99.0, 98.0)})
    level = _level(
        PoolSide.BSL,
        100.0,
        series[0].timestamp,
        exit_at=series[6].timestamp,  # superseded before the pierce
    )
    pool = LiquidityPool()
    pool.add(level)

    assert attribute_sweeps(pool, series).hits == ()


def test_two_active_levels_swept_by_one_bar_emit_two_hits():
    # high 110 / close 95 pierces and closes back below both 100 and 105
    series = _series({8: (110.0, 94.0, 95.0)})
    pool = LiquidityPool()
    pool.add(_level(PoolSide.BSL, 100.0, series[0].timestamp, period_id="2026-03-02"))
    pool.add(_level(PoolSide.BSL, 105.0, series[0].timestamp, period_id="2026-03-03"))

    report = attribute_sweeps(pool, series)
    assert len(report.hits) == 2
    assert {h.period_id for h in report.hits} == {"2026-03-02", "2026-03-03"}
    assert report.hits[0].sweep_bar_index == report.hits[1].sweep_bar_index == 8

    bar_hits = sweeps_on_bar(pool, series, 8)
    assert len(bar_hits) == 2


def test_ssl_sweep_maps_to_long_direction():
    series = _series({8: (101.0, 95.0, 103.0)})
    pool = LiquidityPool()
    pool.add(_level(PoolSide.SSL, 100.0, series[0].timestamp))

    hits = attribute_sweeps(pool, series).hits
    assert len(hits) == 1
    assert hits[0].direction == "long"
    assert hits[0].side == "ssl"


def test_level_entering_after_series_end_is_not_applicable():
    series = _series()
    pool = LiquidityPool()
    pool.add(_level(PoolSide.BSL, 100.0, series[-1].timestamp + timedelta(hours=1)))

    report = attribute_sweeps(pool, series)
    assert report.hits == ()
    assert report.not_applicable == (("previous_day", "bsl", "2026-03-02"),)


def test_eqh_cannot_reach_the_pool_or_attribution():
    pool = LiquidityPool()
    eqh = LiquidityLevel(
        type=LiquidityType.EQUAL_HIGHS_LOWS,
        level=100.0,
        pool=PoolType.BSL,
        timeframe=Timeframe.M5,
        formed_at=START,
    )
    with pytest.raises(ValueError, match="R-EQH-C"):
        pool.add_detected(eqh, source_tf=Timeframe.M5, period_id="x")
    assert attribute_sweeps(pool, _series()).hits == ()


def test_attribution_uses_pool_builder_enter_at():
    """End-to-end: a PDH built by the P2a builder is scanned from its enter_at."""
    formed = datetime(2026, 3, 2, 6, tzinfo=timezone.utc)  # Monday extreme bar
    level = from_pdh_pdl(
        LiquidityLevel(
            type=LiquidityType.PREVIOUS_DAY,
            level=100.0,
            pool=PoolType.BSL,
            timeframe=Timeframe.M5,
            formed_at=formed,
        ),
        Timeframe.M5,
    )
    # enter_at is the next UTC midnight, far after the extreme bar
    assert level.enter_at == datetime(2026, 3, 3, tzinfo=timezone.utc)

    series = _series(count=400)  # 400 x 5m spans past 2026-03-03 00:00
    pool = LiquidityPool()
    pool.add(level)
    index = resolve_start_index(series, level.enter_at)
    assert series[index].timestamp >= level.enter_at
    assert series[index - 1].timestamp < level.enter_at
    assert attribute_sweeps(pool, series).hits == ()
