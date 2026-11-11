"""P2a — liquidity pool registry: membership, identity, lifecycle (R1–R5)."""

from datetime import date, datetime, timedelta, timezone

import pytest

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import LiquidityType, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.core.swing import Swing
from smc.liquidity import (
    LiquidityPool,
    PoolFamily,
    PoolLevel,
    PoolSide,
    PoolStatus,
    from_pdh_pdl,
    from_pwh_pwl,
    from_session,
    from_structural,
    inventory_sort_key,
)


def _utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _detected(level_type, price, side, formed_at, timeframe=Timeframe.H4):
    return LiquidityLevel(
        type=level_type,
        level=price,
        pool=PoolType.BSL if side is PoolSide.BSL else PoolType.SSL,
        timeframe=timeframe,
        formed_at=formed_at,
    )


def _pdh(price, side, day):
    return from_pdh_pdl(_detected(LiquidityType.PREVIOUS_DAY, price, side, _utc(2026, 1, day, 6)), Timeframe.H4)


def _pwh(price, side, monday):
    formed = _utc(2026, 1, monday, 6)
    return from_pwh_pwl(_detected(LiquidityType.PREVIOUS_WEEK, price, side, formed), Timeframe.H4)


def test_level_id_excludes_price():
    a = _pdh(100.0, PoolSide.BSL, 5)
    b = _pdh(200.0, PoolSide.BSL, 5)
    assert a.level_id == b.level_id == ("previous_day", "bsl", "2026-01-05")


def test_duplicate_identity_rejected():
    pool = LiquidityPool()
    pool.add(_pdh(100.0, PoolSide.BSL, 5))
    with pytest.raises(ValueError, match="duplicate pool level_id"):
        pool.add(_pdh(101.0, PoolSide.BSL, 5))


def test_eqh_rejected_hard():
    pool = LiquidityPool()
    eqh = _detected(LiquidityType.EQUAL_HIGHS_LOWS, 100.0, PoolSide.BSL, _utc(2026, 1, 5, 6))
    with pytest.raises(ValueError, match="R-EQH-C"):
        pool.add_detected(eqh, source_tf=Timeframe.H4, period_id="2026-01-05")
    assert len(pool) == 0


def test_pool_level_rejects_non_member_family():
    with pytest.raises(ValueError, match="PoolFamily"):
        PoolLevel(
            family="equal_highs_lows",  # type: ignore[arg-type]
            side=PoolSide.BSL,
            price=1.0,
            period_id="x",
            source_tf=Timeframe.H4,
            formed_at=None,
            enter_at=_utc(2026, 1, 5),
        )


def test_pdh_enters_next_midnight_and_is_replaced():
    pool = LiquidityPool()
    first = pool.add(_pdh(100.0, PoolSide.BSL, 5))   # day 2026-01-05 -> enter 01-06 00:00
    second = pool.add(_pdh(110.0, PoolSide.BSL, 6))  # enter 01-07 00:00

    assert first.enter_at == _utc(2026, 1, 6)
    # before publication
    assert pool.active_asof(_utc(2026, 1, 6) - timedelta(seconds=1)) == []
    # first pair only while it is the newest
    active = pool.active_asof(_utc(2026, 1, 6, 12))
    assert [lv.period_id for lv in active] == ["2026-01-05"]
    # superseded exactly at the successor's enter_at
    active_after = pool.active_asof(_utc(2026, 1, 7))
    assert [lv.period_id for lv in active_after] == ["2026-01-06"]
    stored = {lv.level_id: lv for lv in pool.all_levels()}
    assert stored[first.level_id].exit_at == second.enter_at
    # status is time-derived, not set merely because a successor exists
    assert stored[first.level_id].status is PoolStatus.ACTIVE
    pool.apply_lifecycle(second.enter_at)
    stored = {lv.level_id: lv for lv in pool.all_levels()}
    assert stored[first.level_id].status is PoolStatus.EXITED


def test_pwh_enters_next_monday_and_is_replaced():
    pool = LiquidityPool()
    # 2026-01-05 and 2026-01-12 are Mondays
    first = pool.add(_pwh(300.0, PoolSide.SSL, 5))
    second = pool.add(_pwh(290.0, PoolSide.SSL, 12))

    assert first.enter_at == _utc(2026, 1, 12)
    assert pool.active_asof(_utc(2026, 1, 11, 23, 59)) == []
    assert [lv.period_id for lv in pool.active_asof(_utc(2026, 1, 13))] == ["2026-01-05"]
    assert [lv.period_id for lv in pool.active_asof(_utc(2026, 1, 19))] == ["2026-01-12"]
    assert first.level_id != second.level_id


def test_session_source_tf_is_m5_and_enters_at_session_close():
    lvl = _detected(LiquidityType.SESSION, 100.0, PoolSide.BSL, _utc(2026, 1, 5, 3))
    pool_level = from_session(lvl, session="ASIA", day=date(2026, 1, 5))
    assert pool_level.source_tf is Timeframe.M5
    assert pool_level.period_id == "2026-01-05_ASIA"
    assert pool_level.enter_at == _utc(2026, 1, 5, 7)


def test_sessions_of_the_same_day_coexist():
    pool = LiquidityPool()
    asia = from_session(_detected(LiquidityType.SESSION, 100.0, PoolSide.BSL, _utc(2026, 1, 5, 3)), session="ASIA", day=date(2026, 1, 5))
    london = from_session(_detected(LiquidityType.SESSION, 105.0, PoolSide.BSL, _utc(2026, 1, 5, 9)), session="LONDON", day=date(2026, 1, 5))
    pool.add(asia)
    pool.add(london)
    active = pool.active_asof(_utc(2026, 1, 5, 14))
    assert {lv.period_id for lv in active} == {"2026-01-05_ASIA", "2026-01-05_LONDON"}
    # next day's Asia print supersedes only the Asia series
    pool.add(from_session(_detected(LiquidityType.SESSION, 102.0, PoolSide.BSL, _utc(2026, 1, 6, 3)), session="ASIA", day=date(2026, 1, 6)))
    active = pool.active_asof(_utc(2026, 1, 6, 8))
    assert {lv.period_id for lv in active} == {"2026-01-06_ASIA", "2026-01-05_LONDON"}


def test_active_asof_excludes_expired_level():
    pool = LiquidityPool()
    first = pool.add(_pdh(100.0, PoolSide.SSL, 5))
    pool.add(_pdh(101.0, PoolSide.SSL, 6))
    stored = {lv.level_id: lv for lv in pool.all_levels()}[first.level_id]
    assert stored.exit_at is not None
    assert stored not in pool.active_asof(_utc(2026, 1, 8))


def _h4_bars(count=12, start=_utc(2026, 1, 5)):
    bars = []
    for i in range(count):
        ts = start + timedelta(hours=4 * i)
        price = 100.0 + i
        bars.append(Candle(timestamp=ts, open=price, high=price + 1, low=price - 1, close=price, timeframe=Timeframe.H4))
    return bars


def test_structural_enters_at_confirmation_close_and_is_superseded():
    bars = _h4_bars()
    older = Swing(
        is_high=False,
        level=90.0,
        candle_index=1,
        base_candle=bars[1],
        timeframe=Timeframe.H4,
        is_valid=True,
        confirmed_index=3,
    )
    newer = Swing(
        is_high=False,
        level=95.0,
        candle_index=5,
        base_candle=bars[5],
        timeframe=Timeframe.H4,
        is_valid=True,
        confirmed_index=7,
    )

    old_pool = from_structural(older, bars, Timeframe.H4)
    new_pool = from_structural(newer, bars, Timeframe.H4)
    # enter_at is the confirmation bar close, never the base candle
    assert old_pool.enter_at == bars[3].timestamp + timedelta(hours=4)
    assert old_pool.enter_at != older.timestamp

    pool = LiquidityPool()
    pool.add(old_pool)
    pool.add(new_pool)
    active = pool.active_asof(new_pool.enter_at)
    assert [lv.level_id for lv in active] == [new_pool.level_id]
    stored_old = {lv.level_id: lv for lv in pool.all_levels()}[old_pool.level_id]
    assert stored_old.exit_at == new_pool.enter_at


def test_structural_sides_are_independent_series():
    bars = _h4_bars()
    low = from_structural(
        Swing(False, 90.0, 1, bars[1], Timeframe.H4, True, 3), bars, Timeframe.H4
    )
    high = from_structural(
        Swing(True, 120.0, 5, bars[5], Timeframe.H4, True, 7), bars, Timeframe.H4
    )
    pool = LiquidityPool()
    pool.add(low)
    pool.add(high)
    assert len(pool.active_asof(high.enter_at)) == 2


def test_inventory_soft_sort_order():
    pool = LiquidityPool()
    pool.add(_pdh(100.0, PoolSide.BSL, 5))
    pool.add(_pwh(200.0, PoolSide.BSL, 5))
    pool.add(
        from_session(
            _detected(LiquidityType.SESSION, 50.0, PoolSide.SSL, _utc(2026, 1, 5, 3)),
            session="ASIA",
            day=date(2026, 1, 5),
        )
    )
    bars = _h4_bars()
    pool.add(
        from_structural(
            Swing(False, 10.0, 1, bars[1], Timeframe.H4, True, 3), bars, Timeframe.H4
        )
    )
    order = [lv.family for lv in pool.inventory(_utc(2026, 1, 13))]
    assert order == [
        PoolFamily.PREVIOUS_WEEK,
        PoolFamily.PREVIOUS_DAY,
        PoolFamily.SESSION,
        PoolFamily.STRUCTURAL_SWING,
    ]
    # soft sort is reports-only: active_asof stays chronological
    assert [lv.enter_at for lv in pool.active_asof(_utc(2026, 1, 13))] == sorted(
        lv.enter_at for lv in pool.active_asof(_utc(2026, 1, 13))
    )


def test_add_requires_chronological_series_order():
    pool = LiquidityPool()
    pool.add(_pdh(100.0, PoolSide.BSL, 6))  # enter 01-07
    with pytest.raises(ValueError, match="chronologically"):
        pool.add(_pdh(99.0, PoolSide.BSL, 5))  # enter 01-06


def test_apply_lifecycle_marks_exited():
    pool = LiquidityPool()
    pool.add(_pdh(100.0, PoolSide.BSL, 5))
    pool.add(_pdh(101.0, PoolSide.BSL, 6))
    changed = pool.apply_lifecycle(_utc(2026, 1, 7))
    assert [lv.status for lv in changed] == [PoolStatus.EXITED]
    assert pool.apply_lifecycle(_utc(2026, 1, 8)) == []


def test_structural_builder_rejects_invalid_swing():
    bars = _h4_bars()
    swing = Swing(False, 90.0, 1, bars[1], Timeframe.H4, False, None)
    with pytest.raises(ValueError, match="§19"):
        from_structural(swing, bars, Timeframe.H4)
