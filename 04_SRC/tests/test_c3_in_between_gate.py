"""C3 — in-between containment gate (master card §3.4).

Entry validity = trigger fired AND completion close inside the routed POI
body. Completion price is the completion bar's CLOSE (frozen definition).
"""

from __future__ import annotations

from datetime import datetime, timezone

from smc.backtest.pipeline_bridge import candidate_from_route
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.orchestration.product_menu_mtf import (
    PRODUCT_MENU_TIERS,
    MenuEpisode,
    ProductMenuEngine,
)
from smc.poi.choch_classifier import LIVE_CHOCH_RULES, ChochRule
from smc.triggers.base_trigger import TriggerSignal
from smc.triggers.in_between import (
    NOT_IN_BETWEEN,
    price_inside_zone,
    trigger_in_between,
)
from smc.triggers.trigger_router import TriggerRoute

TF = Timeframe.M5


def _poi(low=99.8, high=101.0, direction=Direction.LONG):
    return POI(
        zone=Zone(top=high, bottom=low, direction=direction, timeframe=TF),
        models=[ModelType.M1],
    )


def _route(completion_index=5, poi=None):
    poi = poi if poi is not None else _poi()
    signal = TriggerSignal(
        trigger=TriggerType.A_CHOCH,
        direction=Direction.LONG,
        entry_price=100.0,
        stop_reference=98.5,
        completion_index=completion_index,
        expiry_bars=20,
    )
    return TriggerRoute(poi=poi, bar=completion_index, signal=signal)


def _series(candle_factory, close, n=20):
    return candle_factory(
        [(close - 0.4, close + 0.5, close - 0.6, close)] * n, timeframe=TF
    )


# ---------------------------------------------------------------------- #
# T1 — pure helper
# ---------------------------------------------------------------------- #
def test_t1_price_inside_zone():
    assert price_inside_zone(100.0, 99.0, 101.0) is True
    assert price_inside_zone(99.0, 99.0, 101.0) is True      # inclusive low
    assert price_inside_zone(101.0, 99.0, 101.0) is True     # inclusive high
    assert price_inside_zone(98.9, 99.0, 101.0) is False     # below
    assert price_inside_zone(101.1, 99.0, 101.0) is False    # above
    assert price_inside_zone(100.0, 101.0, 99.0) is False    # inverted
    assert price_inside_zone(None, 99.0, 101.0) is False     # unlocatable


def test_t1_trigger_in_between_matches_helper():
    assert trigger_in_between(zone_low=99.0, zone_high=101.0,
                              completion_price=100.0) is True
    assert trigger_in_between(zone_low=99.0, zone_high=101.0,
                              completion_price=97.0) is False
    assert NOT_IN_BETWEEN == "not_in_between"


# ---------------------------------------------------------------------- #
# T2/T3 — candidate path (the single choke point both products use)
# ---------------------------------------------------------------------- #
def test_t2_completion_inside_zone_produces_candidate(candle_factory):
    candles = _series(candle_factory, close=100.5)
    candidate = candidate_from_route(
        _route(), completion_price=float(candles[5].close)
    )
    assert candidate is not None
    assert candidate.zone_low == 99.8
    assert candidate.zone_high == 101.0


def test_t3_completion_outside_zone_is_rejected(candle_factory):
    candles = _series(candle_factory, close=102.5)   # above zone high
    assert candidate_from_route(
        _route(), completion_price=float(candles[5].close)
    ) is None


def test_t3_completion_below_zone_is_rejected(candle_factory):
    candles = _series(candle_factory, close=99.0)    # below zone low
    assert candidate_from_route(
        _route(), completion_price=float(candles[5].close)
    ) is None


# ---------------------------------------------------------------------- #
# T4 — menu candidate builder honours the same gate
# ---------------------------------------------------------------------- #
def _episode(poi):
    ts = datetime(2026, 11, 12, tzinfo=timezone.utc)
    return MenuEpisode(
        episode_id="ep-c3",
        poi=poi,
        tier=PRODUCT_MENU_TIERS[0],
        sweep_index=0,
        sweep_ts=ts,
        sweep_close_ts=ts,
    )


def test_t4_menu_candidate_outside_zone_not_built(candle_factory):
    menu = ProductMenuEngine()
    menu._confirm[TF] = _series(candle_factory, close=102.5)
    route = _route()
    assert menu._candidate(_episode(route.poi), route, TF) is None


def test_t4_menu_candidate_inside_zone_built(candle_factory):
    menu = ProductMenuEngine()
    menu._confirm[TF] = _series(candle_factory, close=100.5)
    route = _route()
    assert menu._candidate(_episode(route.poi), route, TF) is not None


# ---------------------------------------------------------------------- #
# T5 — C2a still holds (Rule 3 is not live)
# ---------------------------------------------------------------------- #
def test_t5_c2a_rule3_still_not_live():
    assert ChochRule.RULE_3_INSIDE_WICK not in LIVE_CHOCH_RULES
    assert ChochRule.RULE_1_STANDARD in LIVE_CHOCH_RULES
    assert ChochRule.RULE_2_INSIDE_BODY in LIVE_CHOCH_RULES
