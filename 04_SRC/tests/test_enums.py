"""Phase 0 validation — enums carry the correct members and values."""

import pytest

from smc.config.locked_constants import N_BAR_HTF, N_BAR_LTF
from smc.config.model_type import MODEL_DESCRIPTIONS, ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import (
    Direction,
    LiquidityType,
    POIState,
    PoolType,
    TriggerType,
)


def test_timeframe_members_and_mt5_values():
    # Values must equal MetaTrader5 TIMEFRAME_* constants (mapping by int).
    assert list(Timeframe) == [
        Timeframe.M1,
        Timeframe.M5,
        Timeframe.M15,
        Timeframe.M30,
        Timeframe.H1,
        Timeframe.H4,
        Timeframe.D1,
    ]
    assert int(Timeframe.M1) == 1
    assert int(Timeframe.M5) == 5
    assert int(Timeframe.M15) == 15
    assert int(Timeframe.M30) == 30
    assert int(Timeframe.H1) == 16385
    assert int(Timeframe.H4) == 16388
    assert int(Timeframe.D1) == 16408


def test_timeframe_minutes_and_lookup():
    assert Timeframe.M1.minutes == 1
    assert Timeframe.M5.minutes == 5
    assert Timeframe.H1.minutes == 60
    assert Timeframe.H4.minutes == 240
    assert Timeframe.D1.minutes == 1440
    assert Timeframe.from_minutes(30) is Timeframe.M30
    assert Timeframe.from_minutes(60) is Timeframe.H1
    with pytest.raises(ValueError):
        Timeframe.from_minutes(7)


def test_timeframe_htf_ltf_per_section_27():
    # §27: HTF class = D1/H4/H1 (N=5); LTF class = M30/M15/M5/M1 (N=3).
    for tf in (Timeframe.D1, Timeframe.H4, Timeframe.H1):
        assert tf.is_htf() and not tf.is_ltf()
        assert Timeframe.n_bar_confirmation(tf) == N_BAR_HTF == 5
    for tf in (Timeframe.M30, Timeframe.M15, Timeframe.M5, Timeframe.M1):
        assert tf.is_ltf() and not tf.is_htf()
        assert Timeframe.n_bar_confirmation(tf) == N_BAR_LTF == 3


def test_model_type_has_m1_through_m8():
    assert [m.name for m in ModelType] == [
        "M1",
        "M2",
        "M3",
        "M4",
        "M5",
        "M6",
        "M7",
        "M8",
    ]
    assert [m.value for m in ModelType] == [1, 2, 3, 4, 5, 6, 7, 8]
    # Every model must have a description (LOCKED_DECISIONS §1 table).
    assert set(MODEL_DESCRIPTIONS) == set(ModelType)


def test_trigger_type_a_through_f():
    assert [t.value for t in TriggerType] == ["A", "B", "C", "D", "E", "F"]
    assert TriggerType.A_CHOCH.value == "A"
    assert TriggerType.F_BOS_OB.value == "F"


def test_liquidity_type_has_eight_section_2_types():
    assert len(LiquidityType) == 8
    names = {t.name for t in LiquidityType}
    assert names == {
        "SESSION",
        "PREVIOUS_DAY",
        "PREVIOUS_WEEK",
        "EQUAL_HIGHS_LOWS",
        "STRUCTURAL_SWING",
        "POI_LEVEL",
        "DEMAND_SUPPLY_BOUNDARY",
        "ORDER_BLOCK_BOUNDARY",
    }


def test_poi_state_matches_section_5_machine():
    assert [s.name for s in POIState] == ["CREATED", "FRESH", "TESTED", "VIOLATED"]


def test_direction_and_pool_type():
    assert Direction.LONG.value == "long"
    assert Direction.SHORT.value == "short"
    assert PoolType.BSL.value == "bsl"
    assert PoolType.SSL.value == "ssl"
    assert {p.name for p in PoolType} == {
        "BSL",
        "SSL",
        "MAJOR_STRUCTURAL",
        "POI",
        "EXTREME_ZONE",
        "OB_EXTREME",
    }