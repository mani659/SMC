"""C2b — Demand/Supply identification is color-free (master card A2).

Pre-C2b the §22 scanner picked zones by candle color: a BEARISH candle became
demand (LONG) and a BULLISH candle became supply (SHORT). C2b selects the
origin by INDEX in the impulse spine and takes the direction from the impulse
leg itself, so an inverted origin body yields the SAME zone bounds and the
zone width stays the single origin candle's full high-low range.
"""

from __future__ import annotations

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.poi.choch_classifier import LIVE_CHOCH_RULES, ChochRule
from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply
from smc.triggers.in_between import price_inside_zone

TF = Timeframe.M5
HTF = Timeframe.H4


def _m8(rows, candle_factory, tf=HTF):
    return M8HtfDemandSupply(TF, htf_candles={tf: candle_factory(rows, timeframe=tf)})


def _warmup(n=16, price=100.0, half=0.05):
    """Calm overlapping bars — enough history for Wilder ATR, no gaps."""
    rows = []
    for _ in range(n):
        rows.append((price, price + half, price - half, price + 0.01))
    return rows


def _rising_horizon(price=100.4, step=1.0, n=3):
    rows = []
    for k in range(n):
        level = price + step * k
        rows.append((level, level + step, level - 0.05, level + step))
    return rows


def _falling_horizon(price=100.0, step=1.0, n=3):
    rows = []
    for k in range(n):
        level = price - step * k
        rows.append((level, level + 0.05, level - step, level - step))
    return rows


def _ds_zone(pois, direction, top, bottom):
    """The demand/supply POI at the given full-range bounds, if any."""
    return [
        p for p in pois
        if p.m8_kind in (None, "demand_supply")
        and p.zone.direction is direction
        and p.zone.top == top and p.zone.bottom == bottom
    ]


def _has_zone(pois, direction, top, bottom):
    return any(
        p.zone.direction is direction
        and p.zone.top == top and p.zone.bottom == bottom
        for p in pois
    )


# ---------------------------------------------------------------------- #
# T1 — LONG demand origin WITHOUT a bearish body
# ---------------------------------------------------------------------- #
def test_t1_long_origin_needs_no_bearish_body(candle_factory):
    # Origin is a BULLISH candle (pre-C2b: demand required a bearish body).
    origin = (99.95, 100.2, 99.85, 100.0)
    rows = _warmup() + [origin] + _rising_horizon()
    pois = _m8(rows, candle_factory).detect([], [], [])

    assert _has_zone(pois, Direction.LONG, 100.2, 99.85), (
        f"LONG demand zone at the origin range missing: "
        f"{[(p.zone.direction, p.zone.top, p.zone.bottom) for p in pois]}"
    )
    # Width = the single origin candle, full wick range.
    for poi in pois:
        assert poi.zone.top - poi.zone.bottom < 1.0


# ---------------------------------------------------------------------- #
# T2 — SHORT supply origin WITHOUT a bullish body (mirror)
# ---------------------------------------------------------------------- #
def test_t2_short_origin_needs_no_bullish_body(candle_factory):
    origin = (100.05, 100.2, 99.85, 100.0)   # BEARISH origin
    rows = _warmup() + [origin] + _falling_horizon()
    pois = _m8(rows, candle_factory).detect([], [], [])

    assert _has_zone(pois, Direction.SHORT, 100.2, 99.85), (
        f"SHORT supply zone at the origin range missing: "
        f"{[(p.zone.direction, p.zone.top, p.zone.bottom) for p in pois]}"
    )


# ---------------------------------------------------------------------- #
# T3 — color inversion of the origin leaves the zone bounds unchanged
# ---------------------------------------------------------------------- #
def test_t3_color_inversion_keeps_same_bounds(candle_factory):
    bullish_origin = (99.95, 100.2, 99.85, 100.0)
    bearish_origin = (100.05, 100.2, 99.85, 100.0)   # same high/low, inverted body
    rows_a = _warmup() + [bullish_origin] + _rising_horizon()
    rows_b = _warmup() + [bearish_origin] + _rising_horizon()

    pois_a = _m8(rows_a, candle_factory).detect([], [], [])
    pois_b = _m8(rows_b, candle_factory).detect([], [], [])

    assert _has_zone(pois_a, Direction.LONG, 100.2, 99.85)
    assert _has_zone(pois_b, Direction.LONG, 100.2, 99.85)


# ---------------------------------------------------------------------- #
# T4 — no impulse leg -> no zone (fail closed; no color guess)
# ---------------------------------------------------------------------- #
def test_t4_no_valid_origin_emits_no_zone(candle_factory):
    # No origin index exists (the series is shorter than the horizon window),
    # so the scanner fails closed instead of guessing an origin.
    rows = [(100.0, 100.1, 99.9, 100.05)] * 3
    assert _m8(rows, candle_factory).detect([], [], []) == []


def test_t4_origin_cannot_be_part_of_the_displacement(candle_factory):
    """The first candle of the dump is not the inventory candle."""
    dump_first = (101.0, 102.0, 99.4, 99.6)   # own body already displaced
    rows = _warmup() + [dump_first] + _falling_horizon(price=99.6)
    pois = _m8(rows, candle_factory).detect([], [], [])
    assert not any(
        p.m8_kind == "demand_supply"
        and p.zone.top == 102.0 and p.zone.bottom == 99.4
        for p in pois
    )


# ---------------------------------------------------------------------- #
# T5 — OB-from-FVG path is color-free and still emits (regression)
# ---------------------------------------------------------------------- #
def test_t5_ob_from_fvg_still_emits(candle_factory):
    rows = [
        (99.8, 99.9, 99.6, 99.8),      # 0 OB (full range 99.6..99.9)
        (99.8, 100.0, 99.6, 99.9),     # 1 FVG c1 (high 100.0)
        (100.5, 102.5, 100.2, 102.2),  # 2 impulse
        (102.2, 102.6, 101.0, 102.4),  # 3 low 101.0 > 100.0 -> bull FVG
    ]
    pois = _m8(rows, candle_factory).detect([], [], [])
    obs = [p for p in pois if p.m8_kind == "ob"]
    assert obs, f"OB zone missing: {[(p.m8_kind, p.zone.top, p.zone.bottom) for p in pois]}"
    assert any(
        p.zone.direction is Direction.LONG
        and p.zone.top == 99.9 and p.zone.bottom == 99.6
        for p in obs
    )


# ---------------------------------------------------------------------- #
# T6 — smoke: C3 gate and C2a Rule-3 policy still hold
# ---------------------------------------------------------------------- #
def test_t6_c3_and_c2a_still_hold():
    assert price_inside_zone(100.0, 99.0, 101.0) is True
    assert price_inside_zone(101.5, 99.0, 101.0) is False
    assert ChochRule.RULE_3_INSIDE_WICK not in LIVE_CHOCH_RULES
    assert ChochRule.RULE_1_STANDARD in LIVE_CHOCH_RULES
