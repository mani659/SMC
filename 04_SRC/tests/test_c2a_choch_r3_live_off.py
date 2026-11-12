"""C2a — CHOCH Rule 3 (wick-only) is never live-eligible.

Master card A1 / amendment A1: live CHOCH = Rule 1 + Rule 2 (body close).
Rule 3 stays classifiable for research but must not produce a Trigger A
signal or a tradeable M3 POI.
"""

from __future__ import annotations

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.poi.choch_classifier import (
    LIVE_CHOCH_RULES,
    ChochRule,
    classify_choch_at,
    is_live_choch,
)
from smc.poi.models.m3_choch_retest import M3ChochRetest
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_a_choch import ChochReversalTrigger

TF = Timeframe.M5


def _rule1_rows():
    """Uptrend, valid low 99.0 (idx4), valid high 100.8 (idx8), sweep idx10,
    body close below 99.0 at idx13."""
    return [
        (100.0, 100.2, 99.8, 99.9),
        (99.9, 100.1, 99.6, 99.7),
        (99.7, 99.9, 99.4, 99.5),
        (99.5, 99.7, 99.2, 99.3),
        (99.3, 99.6, 99.0, 99.4),      # valid low 99.0
        (99.4, 99.8, 99.3, 99.7),
        (99.7, 100.2, 99.6, 100.1),
        (100.1, 100.6, 100.0, 100.5),
        (100.5, 100.8, 100.3, 100.6),  # valid high 100.8
        (100.6, 101.0, 100.5, 100.9),
        (100.9, 101.3, 100.5, 100.6),  # sweep of 100.8
        (100.4, 100.7, 100.1, 100.2),
        (100.0, 100.3, 99.4, 99.6),
        (99.4, 99.6, 98.5, 98.7),      # body close below 99.0 (Rule 1)
    ]


def _rule2_rows():
    """Rule 2: body close below an intermediate low (99.6), last swing intact."""
    return [
        (100.0, 100.2, 99.6, 99.7),
        (99.7, 99.9, 99.4, 99.5),
        (99.5, 99.7, 99.2, 99.3),
        (99.3, 99.6, 99.0, 99.4),      # valid low 99.0
        (99.4, 99.8, 99.3, 99.7),
        (99.7, 100.2, 99.6, 100.1),
        (100.1, 100.6, 100.0, 100.5),
        (100.5, 100.9, 100.4, 100.8),
        (100.8, 101.2, 100.6, 101.0),  # valid high 101.2
        (101.0, 101.5, 100.7, 100.8),  # sweep of high
        (100.6, 100.9, 100.0, 100.2),
        (100.0, 100.3, 99.6, 99.8),    # intermediate low 99.6 (unconfirmed)
        (99.9, 100.2, 99.7, 99.95),
        (99.6, 99.8, 99.2, 99.45),     # close below 99.6, above 99.0
    ]


def _rule3_rows():
    """Rule 3: wick below 99.0, body closes back above it (no body break)."""
    rows = _rule1_rows()
    rows[13] = (99.2, 99.5, 98.4, 99.2)
    return rows


def _swings(candles, swing_factory, entries):
    return [
        swing_factory(candles, idx, is_high, level=level, is_valid=is_valid)
        for idx, is_high, level, is_valid in entries
    ]


def _ctx(candles, swings, direction=Direction.SHORT, bar=13, from_bar=8):
    poi = POI(
        zone=Zone(top=101.0, bottom=99.8, direction=direction, timeframe=TF),
        models=[ModelType.M1],
    )
    return TriggerContext(
        poi=poi, candles=candles, swings=swings, bar_index=bar, from_bar=from_bar
    )


# ---------------------------------------------------------------------- #
# Helper contract
# ---------------------------------------------------------------------- #
def test_live_rule_set_is_r1_and_r2_only():
    assert LIVE_CHOCH_RULES == (
        ChochRule.RULE_1_STANDARD,
        ChochRule.RULE_2_INSIDE_BODY,
    )


def test_is_live_choch_mapping():
    from types import SimpleNamespace

    def live(rule):
        return is_live_choch(SimpleNamespace(rule=rule))

    assert live(ChochRule.RULE_1_STANDARD) is True
    assert live(ChochRule.RULE_2_INSIDE_BODY) is True
    assert live(ChochRule.RULE_3_INSIDE_WICK) is False
    assert is_live_choch(None) is False


# ---------------------------------------------------------------------- #
# T1/T2 — body-close rules still produce a Trigger A signal
# ---------------------------------------------------------------------- #
def test_t1_rule1_still_fires_trigger_a(candle_factory, swing_factory):
    candles = candle_factory(_rule1_rows(), timeframe=TF)
    swings = _swings(candles, swing_factory,
                     [(4, False, 99.0, True), (8, True, 100.8, True)])
    signal = ChochReversalTrigger().evaluate(_ctx(candles, swings))
    assert signal is not None
    assert signal.data["rule"] == "rule_1"


def test_t2_rule2_still_fires_trigger_a(candle_factory, swing_factory):
    candles = candle_factory(_rule2_rows(), timeframe=TF)
    swings = _swings(candles, swing_factory, [
        (3, False, 99.0, True), (8, True, 101.2, True), (11, False, 99.6, False),
    ])
    signal = ChochReversalTrigger().evaluate(_ctx(candles, swings))
    assert signal is not None
    assert signal.data["rule"] == "rule_2"
    assert signal.entry_price == 99.6


# ---------------------------------------------------------------------- #
# T3 — Rule 3 produces no Trigger A signal
# ---------------------------------------------------------------------- #
def test_t3_rule3_only_does_not_fire_trigger_a(candle_factory, swing_factory):
    candles = candle_factory(_rule3_rows(), timeframe=TF)
    swings = _swings(candles, swing_factory,
                     [(4, False, 99.0, True), (8, True, 100.8, True)])
    assert ChochReversalTrigger().evaluate(_ctx(candles, swings)) is None


# ---------------------------------------------------------------------- #
# T4 — classifier keeps Rule 3 for research visibility
# ---------------------------------------------------------------------- #
def test_t4_classifier_still_reports_rule3(candle_factory, swing_factory):
    candles = candle_factory(_rule3_rows(), timeframe=TF)
    swings = _swings(candles, swing_factory,
                     [(4, False, 99.0, True), (8, True, 100.8, True)])
    result = classify_choch_at(candles, swings, bar_index=13)
    assert result is not None
    assert result.rule is ChochRule.RULE_3_INSIDE_WICK


# ---------------------------------------------------------------------- #
# T5 — no tradeable M3 POI from a wick-only CHOCH; Rule 1 still emits
# ---------------------------------------------------------------------- #
def test_t5_rule3_emits_no_m3_poi(candle_factory, swing_factory):
    candles = candle_factory(_rule3_rows(), timeframe=TF)
    swings = _swings(candles, swing_factory,
                     [(4, False, 99.0, True), (8, True, 100.8, True)])
    assert M3ChochRetest(TF).detect(candles, swings, []) == []


def test_t5_rule1_emits_m3_poi(candle_factory, swing_factory):
    candles = candle_factory(_rule1_rows(), timeframe=TF)
    swings = _swings(candles, swing_factory,
                     [(4, False, 99.0, True), (8, True, 100.8, True)])
    assert len(M3ChochRetest(TF).detect(candles, swings, [])) == 1
