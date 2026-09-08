"""Phase 2 — M1–M8 model acceptance fixtures + decoys (R1 §5 canonical patterns).

Each model gets:
* an ACCEPTANCE fixture reproducing its canonical R1 §5 geometry with
  synthetic OHLCV, asserting the emitted POI (direction, zone, tag), and
* a DECOY fixture (same geometry minus the one decisive element) asserting
  the model stays silent.
"""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.poi.models.m1_origin_base import M1OriginBase
from smc.poi.models.m2_rbs_sbr_breaker import M2RbsSbrBreaker
from smc.poi.models.m3_choch_retest import M3ChochRetest
from smc.poi.models.m4_quasimodo import M4Quasimodo
from smc.poi.models.m5_extreme_equal_highs import M5ExtremeEqualHighs
from smc.poi.models.m6_neckline_retest import M6NecklineRetest
from smc.poi.models.m7_equal_resistance import M7EqualResistance
from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply

TF = Timeframe.M5


def _swings(candles, swing_factory, entries):
    return [
        swing_factory(candles, idx, is_high, level=level, is_valid=is_valid)
        for idx, is_high, level, is_valid in entries
    ]


def _only(pois):
    assert len(pois) == 1, f"expected exactly one POI, got {pois}"
    return pois[0]


def _assert_poi(poi, direction, model, top, bottom):
    assert poi.zone.direction is direction
    assert poi.models == [model]
    assert poi.zone.top == top
    assert poi.zone.bottom == bottom


# ========================================================================== #
# Model 1 — Origin Demand/Supply Base
# ========================================================================== #
def _m1_rows(with_fvg: bool = True):
    rows = []
    price = 100.0
    for _ in range(15):  # calm drift down: small ATR before the origin
        open_ = price
        close = open_ - 0.02
        rows.append((open_, open_ + 0.075, open_ - 0.075, close))
        price = close
    open_ = rows[10][3] - 0.05  # small local top, swing high H level = 100.0
    rows[10] = (open_, 100.0, open_ - 0.15, open_)
    rows[14] = (99.0, 99.2, 98.6, 99.0)  # origin swing low level 98.6
    if with_fvg:
        rows.append((99.2, 100.3, 99.1, 100.1))    # impulse candles 15-17
        rows.append((100.05, 100.9, 99.95, 100.7))
        rows.append((100.6, 101.3, 100.55, 101.1))  # bullish FVG + BOS close
    else:
        rows.append((99.2, 101.2, 99.1, 100.2))     # wide candle: no gap forms
        rows.append((100.0, 100.9, 99.1, 100.6))
        rows.append((100.6, 101.3, 100.55, 101.1))
    return rows


def test_m1_origin_base_acceptance(candle_factory, swing_factory):
    candles = candle_factory(_m1_rows(with_fvg=True))
    swings = _swings(
        candles,
        swing_factory,
        [(10, True, 100.0, True), (14, False, 98.6, True)],
    )
    poi = _only(M1OriginBase(TF).detect(candles, swings, []))
    _assert_poi(poi, Direction.LONG, ModelType.M1, 99.2, 98.6)


def test_m1_origin_base_decoy_without_fvg(candle_factory, swing_factory):
    candles = candle_factory(_m1_rows(with_fvg=False))
    swings = _swings(
        candles,
        swing_factory,
        [(10, True, 100.0, True), (14, False, 98.6, True)],
    )
    assert M1OriginBase(TF).detect(candles, swings, []) == []


# ========================================================================== #
# Model 2 — RBS / SBR Breaker Flip
# ========================================================================== #
def _m2_rows(break_above: bool = True):
    rows = [
        (99.4, 99.6, 99.2, 99.3),
        (99.3, 99.5, 99.1, 99.2),
        (99.2, 99.4, 99.0, 99.1),
        (99.1, 99.3, 99.0, 99.2),   # 3 swing low 99.0
        (99.2, 99.5, 99.1, 99.4),
        (99.4, 99.8, 99.3, 99.7),
        (99.7, 100.0, 99.6, 99.8),  # 6 swing high 100.0
        (99.8, 100.3, 99.7, 100.2) if break_above else (99.8, 99.9, 99.7, 99.85),
    ]
    return rows


def test_m2_rbs_break_and_flip_acceptance(candle_factory, swing_factory):
    candles = candle_factory(_m2_rows())
    swings = _swings(
        candles,
        swing_factory,
        [(3, False, 99.0, True), (6, True, 100.0, True)],
    )
    poi = _only(M2RbsSbrBreaker(TF).detect(candles, swings, []))
    _assert_poi(poi, Direction.LONG, ModelType.M2, 100.0, 99.6)


def test_m2_rbs_decoy_no_close_beyond(candle_factory, swing_factory):
    candles = candle_factory(_m2_rows(break_above=False))
    swings = _swings(
        candles,
        swing_factory,
        [(3, False, 99.0, True), (6, True, 100.0, True)],
    )
    assert M2RbsSbrBreaker(TF).detect(candles, swings, []) == []


# ========================================================================== #
# Model 3 — CHOCH Baseline Retest
# ========================================================================== #
def _m3_rows(sweep: bool = True, break_close: bool = True):
    rows = [
        (100.0, 100.2, 99.8, 99.9),
        (99.9, 100.1, 99.6, 99.7),
        (99.7, 99.9, 99.4, 99.5),
        (99.5, 99.7, 99.2, 99.3),
        (99.3, 99.6, 99.0, 99.4),   # 4 valid low 99.0
        (99.4, 99.8, 99.3, 99.7),
        (99.7, 100.2, 99.6, 100.1),
        (100.1, 100.6, 100.0, 100.5),
        (100.5, 100.8, 100.3, 100.6),  # 8 valid high 100.8
        (100.6, 101.0, 100.5, 100.9),
        (100.9, 101.3, 100.5, 100.6) if sweep else (100.9, 101.1, 100.6, 101.0),
        (100.4, 100.7, 100.1, 100.2),
        (100.0, 100.3, 99.4, 99.6),
        (99.4, 99.6, 98.5, 98.7) if break_close else (99.6, 99.9, 99.3, 99.7),
    ]
    return rows


def test_m3_choch_retest_acceptance(candle_factory, swing_factory):
    candles = candle_factory(_m3_rows())
    swings = _swings(
        candles,
        swing_factory,
        [(4, False, 99.0, True), (8, True, 100.8, True)],
    )
    poi = _only(M3ChochRetest(TF).detect(candles, swings, []))
    _assert_poi(poi, Direction.SHORT, ModelType.M3, 99.6, 99.0)


def test_m3_choch_retest_decoy_no_sweep(candle_factory, swing_factory):
    candles = candle_factory(_m3_rows(sweep=False))
    swings = _swings(
        candles,
        swing_factory,
        [(4, False, 99.0, True), (8, True, 100.8, True)],
    )
    assert M3ChochRetest(TF).detect(candles, swings, []) == []


# ========================================================================== #
# Model 4 — Quasimodo Level
# ========================================================================== #
def _m4_rows(close_below_neck: bool = True):
    rows = [
        (100.0, 100.5, 99.9, 100.3),
        (100.3, 100.6, 100.1, 100.4),
        (100.4, 101.0, 100.2, 100.8),
        (100.8, 101.2, 100.6, 101.0),
        (101.0, 101.6, 100.8, 101.4),  # 4 left shoulder high 101.6
        (101.4, 101.7, 101.1, 101.2),
        (101.2, 101.4, 100.8, 100.9),
        (100.9, 101.1, 100.3, 100.4),
        (100.3, 100.5, 99.8, 99.9),    # 8 neck low 99.8
        (99.9, 100.2, 99.7, 100.0),
        (100.0, 100.5, 99.9, 100.4),
        (100.4, 101.0, 100.3, 100.9),
        (100.9, 102.0, 100.7, 101.8),  # 12 head high 102.0 > LS
        (101.6, 101.9, 99.0, 99.2) if close_below_neck else (101.0, 101.4, 99.9, 100.2),
    ]
    return rows


def test_m4_quasimodo_acceptance(candle_factory, swing_factory):
    candles = candle_factory(_m4_rows())
    swings = _swings(
        candles,
        swing_factory,
        [(4, True, 101.6, True), (8, False, 99.8, True), (12, True, 102.0, True)],
    )
    poi = _only(M4Quasimodo(TF).detect(candles, swings, []))
    _assert_poi(poi, Direction.SHORT, ModelType.M4, 101.6, 100.8)


def test_m4_quasimodo_decoy_no_neckline_break(candle_factory, swing_factory):
    candles = candle_factory(_m4_rows(close_below_neck=False))
    swings = _swings(
        candles,
        swing_factory,
        [(4, True, 101.6, True), (8, False, 99.8, True), (12, True, 102.0, True)],
    )
    assert M4Quasimodo(TF).detect(candles, swings, []) == []


# ========================================================================== #
# Model 5 — Extreme Equal Highs (proactive)
# ========================================================================== #
def _m5_rows():
    return [
        (100.0, 100.3, 99.8, 100.1),
        (100.1, 100.4, 99.9, 100.2),
        (100.2, 100.7, 100.0, 100.5),
        (100.5, 101.0, 100.4, 100.8),
        (100.8, 101.4, 100.6, 101.2),  # 4 equal high A 101.4
        (101.2, 101.4, 100.9, 101.0),
        (101.0, 101.3, 100.6, 100.8),
        (100.8, 101.1, 100.3, 100.5),
        (100.5, 100.9, 99.9, 100.1),   # 8 pullback low
        (100.1, 100.5, 99.9, 100.3),
        (100.3, 101.5, 100.2, 101.3),  # 10 equal high B 101.5 (0.1 apart)
        (101.3, 101.6, 101.0, 101.2),
        (101.1, 101.4, 100.6, 100.8),
        (100.6, 100.9, 99.5, 99.6),    # 13 close below the cluster
    ]


def test_m5_equal_highs_acceptance(candle_factory, swing_factory):
    candles = candle_factory(_m5_rows())
    swings = _swings(
        candles,
        swing_factory,
        [(4, True, 101.4, True), (10, True, 101.5, True)],
    )
    poi = _only(M5ExtremeEqualHighs(TF).detect(candles, swings, []))
    _assert_poi(poi, Direction.SHORT, ModelType.M5, 101.5, 100.2)


def test_m5_equal_highs_decoy_out_of_tolerance(candle_factory, swing_factory):
    candles = candle_factory(_m5_rows())
    swings = _swings(
        candles,
        swing_factory,
        [(4, True, 101.4, True), (10, True, 103.0, True)],  # B far above A
    )
    assert M5ExtremeEqualHighs(TF).detect(candles, swings, []) == []


# ========================================================================== #
# Model 6 — Neckline / Double Top-Bottom
# ========================================================================== #
def _m6_rows():
    return [
        (100.0, 100.4, 99.8, 100.2),
        (100.2, 100.6, 100.0, 100.4),
        (100.4, 101.0, 100.3, 100.8),
        (100.8, 101.3, 100.6, 101.1),
        (101.1, 101.8, 100.9, 101.6),  # 4 top A 101.8
        (101.6, 101.9, 101.2, 101.4),
        (101.4, 101.6, 101.0, 101.1),
        (101.1, 101.3, 100.5, 100.6),
        (100.6, 100.8, 100.0, 100.1),  # 8 neck low 100.0
        (100.1, 100.5, 99.9, 100.3),
        (100.3, 100.9, 100.2, 100.8),
        (100.8, 101.4, 100.7, 101.2),
        (101.2, 101.9, 101.1, 101.7),  # 12 top B 101.9 ~ A
        (101.5, 101.8, 99.6, 99.7),    # 13 close below neck
    ]


def test_m6_neckline_acceptance(candle_factory, swing_factory):
    candles = candle_factory(_m6_rows())
    swings = _swings(
        candles,
        swing_factory,
        [(4, True, 101.8, True), (8, False, 100.0, True), (12, True, 101.9, True)],
    )
    poi = _only(M6NecklineRetest(TF).detect(candles, swings, []))
    _assert_poi(poi, Direction.SHORT, ModelType.M6, 100.8, 100.0)


def test_m6_neckline_decoy_unequal_tops(candle_factory, swing_factory):
    candles = candle_factory(_m6_rows())
    swings = _swings(
        candles,
        swing_factory,
        [(4, True, 101.8, True), (8, False, 100.0, True), (12, True, 102.8, True)],
    )
    assert M6NecklineRetest(TF).detect(candles, swings, []) == []


# ========================================================================== #
# Model 7 — Equal Resistance Shelf (reactive)
# ========================================================================== #
def _m7_rows():
    return [
        (109.0, 109.5, 108.8, 109.2),
        (109.2, 109.8, 109.0, 109.6),
        (109.6, 110.4, 109.5, 110.2),
        (110.2, 110.9, 110.0, 110.7),  # 3 prior high X 110.9
        (110.7, 110.9, 110.2, 110.4),
        (110.3, 110.5, 109.7, 109.9),
        (109.8, 110.1, 109.2, 109.4),
        (109.3, 109.6, 108.8, 109.0),
        (108.9, 109.2, 108.4, 108.6),  # 8 bounce-origin low a 108.4
        (108.6, 109.1, 108.4, 108.9),
        (108.9, 109.6, 108.8, 109.4),
        (109.4, 110.2, 109.3, 110.0),
        (110.0, 110.6, 109.8, 110.4),  # 12 shelf high b 110.6
        (110.2, 110.5, 108.0, 108.2),  # 13 close below the origin low
    ]


def test_m7_equal_resistance_acceptance(candle_factory, swing_factory):
    candles = candle_factory(_m7_rows())
    swings = _swings(
        candles,
        swing_factory,
        [(3, True, 110.9, True), (8, False, 108.4, True), (12, True, 110.6, True)],
    )
    poi = _only(M7EqualResistance(TF).detect(candles, swings, []))
    _assert_poi(poi, Direction.SHORT, ModelType.M7, 110.6, 109.8)


def test_m7_equal_resistance_decoy_no_prior_high(candle_factory, swing_factory):
    candles = candle_factory(_m7_rows())
    swings = _swings(
        candles,
        swing_factory,
        [(8, False, 108.4, True), (12, True, 110.6, True)],
    )
    assert M7EqualResistance(TF).detect(candles, swings, []) == []


# ========================================================================== #
# Model 8 — HTF Demand/Supply zones (D1/H4)
# ========================================================================== #
def _htf_rows():
    """19 calm up-bars, one last-up candle (idx19), then a 4-bar dump."""
    rows = []
    price = 200.0
    for _ in range(19):
        open_ = price
        close = open_ + 0.05
        rows.append((open_, close + 0.05, open_ - 0.05, close))
        price = close
    rows.append((200.7, 201.2, 200.6, 201.0))   # 19 last up candle
    rows.append((201.0, 202.0, 199.4, 199.6))   # 20 dump
    rows.append((199.6, 199.9, 199.0, 199.2))   # 21
    rows.append((199.2, 199.5, 198.8, 199.0))   # 22
    rows.append((199.0, 199.4, 198.9, 199.2))   # 23
    return rows


def _m8(htf_candles):
    return M8HtfDemandSupply(TF, htf_candles=htf_candles)


def test_m8_htf_zones_acceptance_single_timeframe(candle_factory):
    h4 = candle_factory(_htf_rows(), timeframe=Timeframe.H4)
    pois = _m8({Timeframe.H4: h4}).detect([], [], [])
    assert pois
    for poi in pois:
        assert poi.models == [ModelType.M8]
        assert poi.zone.timeframe is Timeframe.H4
        assert not poi.htf_overlap  # single timeframe: no D1/H4 overlap
    assert any(p.zone.direction is Direction.SHORT for p in pois)
    # §22: supply zone = FULL high-low range of the SINGLE last bullish
    # candle (idx19: high 201.2, low 200.6) before the bearish impulse.
    assert any(
        p.zone.direction is Direction.SHORT
        and p.zone.top == 201.2
        and p.zone.bottom == 200.6
        for p in pois
    )


def test_m8_ignores_non_d1_h4_series(candle_factory):
    """§21/§22: detection is D1/H4 only — H1 (or any other TF) is ignored."""
    h1 = candle_factory(_htf_rows(), timeframe=Timeframe.H1)
    assert _m8({Timeframe.H1: h1}).detect([], [], []) == []


def test_m8_htf_overlap_flag_when_d1_and_h4_overlap(candle_factory):
    h4 = candle_factory(_htf_rows(), timeframe=Timeframe.H4)
    d1 = candle_factory(_htf_rows(), timeframe=Timeframe.D1)  # identical price levels
    pois = _m8({Timeframe.H4: h4, Timeframe.D1: d1}).detect([], [], [])
    shorts = [p for p in pois if p.zone.direction is Direction.SHORT]
    assert shorts
    for poi in shorts:
        assert poi.htf_overlap
    d1_short = [p for p in shorts if p.zone.timeframe is Timeframe.D1]
    h4_short = [p for p in shorts if p.zone.timeframe is Timeframe.H4]
    assert d1_short and h4_short


def test_m8_no_htf_candles_emits_nothing():
    assert _m8({}).detect([], [], []) == []
    assert _m8({Timeframe.H4: []}).detect([], [], []) == []
