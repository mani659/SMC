"""Phase 3 — POI freshness state machine: §5 atomic transitions + §23 expiry."""

from datetime import datetime, timezone

import pytest

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.validation.state_machine import (
    IllegalTransitionError,
    POIStateMachine,
    expiry_bars_for,
)

TF = Timeframe.M5


def _poi(timeframe: Timeframe = TF, state: POIState = POIState.CREATED) -> POI:
    return POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=timeframe),
        models=[],
        state=state,
    )


def test_arm_created_to_fresh_and_state_sync():
    poi = _poi()
    machine = POIStateMachine()
    assert machine.arm(poi) is POIState.FRESH
    assert machine.current(poi) is POIState.FRESH
    assert poi.state is POIState.FRESH  # store and attribute stay in sync


def test_first_touch_ok_then_no_second_touch():
    poi = _poi(state=POIState.FRESH)
    machine = POIStateMachine()
    assert machine.can_trade(poi)
    # First touch: FRESH -> TESTED (entry may fire on the first touch).
    assert machine.on_touch(poi) is POIState.TESTED
    assert not machine.can_trade(poi)
    # Second touch on a TESTED POI is rejected.
    with pytest.raises(IllegalTransitionError):
        machine.on_touch(poi)


def test_violation_when_closed_beyond_without_touch():
    poi = _poi(state=POIState.FRESH)
    machine = POIStateMachine()
    assert machine.on_violation(poi) is POIState.VIOLATED
    assert not machine.can_trade(poi)


def test_terminal_states_never_transition():
    machine = POIStateMachine()
    tested = _poi(state=POIState.TESTED)
    violated = _poi(state=POIState.VIOLATED)
    with pytest.raises(IllegalTransitionError):
        machine.arm(tested)
    with pytest.raises(IllegalTransitionError):
        machine.on_violation(tested)
    with pytest.raises(IllegalTransitionError):
        machine.arm(violated)


def test_arm_twice_raises():
    poi = _poi()
    machine = POIStateMachine()
    machine.arm(poi)
    with pytest.raises(IllegalTransitionError):
        machine.arm(poi)


def test_expiry_bars_mapping():
    assert expiry_bars_for(Timeframe.M5) == 12  # §23 frozen
    assert expiry_bars_for(Timeframe.M1) == 30  # §23 frozen
    assert expiry_bars_for(Timeframe.H1) is None
    assert expiry_bars_for(Timeframe.D1) is None


def test_expire_unfilled_marks_tested_after_frozen_bars():
    machine = POIStateMachine()
    poi = _poi(timeframe=Timeframe.M5, state=POIState.FRESH)
    assert machine.expire_unfilled(poi, bars_open=11) is POIState.FRESH  # not yet
    assert machine.expire_unfilled(poi, bars_open=12) is POIState.TESTED  # M5 = 12 bars
    # Expiry on an already-TESTED POI is a no-op (terminal state is guarded
    # by transition(); expiry itself is idempotent).
    assert machine.expire_unfilled(poi, bars_open=13) is POIState.TESTED


def test_no_expiry_rule_for_other_timeframes():
    machine = POIStateMachine()
    poi = _poi(timeframe=Timeframe.H1, state=POIState.FRESH)
    assert machine.expire_unfilled(poi, bars_open=100) is None  # no frozen rule
    assert poi.state is POIState.FRESH


def test_touches_zone_helper():
    poi = _poi()  # zone [100.0, 100.2]
    machine = POIStateMachine()

    def candle(high: float, low: float) -> Candle:
        return Candle(
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            open=high,
            high=high,
            low=low,
            close=high,
            timeframe=TF,
        )

    assert machine.touches_zone(poi, candle(100.5, 100.15))  # wick inside
    assert machine.touches_zone(poi, candle(100.0, 99.7))    # touches bottom edge
    assert not machine.touches_zone(poi, candle(100.5, 100.3))  # stays above
    assert not machine.touches_zone(poi, candle(99.5, 99.2))  # stays below
