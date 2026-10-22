"""Decomposed 6m ledger — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/decomposed_6m_ledger.py``: the htf_context
trichotomy, level parsing, Wilson intervals, ATR-unit excursion math,
zone-fate reads, and content hashing. No series loading, no books, no
threshold, no expectancy assertion anywhere.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "decomposed_6m_ledger.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "decomposed_6m_ledger", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["decomposed_6m_ledger"] = module
    spec.loader.exec_module(module)
    return module


def _m5_series(n, start=None, o=100.0, h=100.5, l=99.5, c=100.0):
    from smc.backtest.data_feed import CandleSeries
    from smc.config.timeframe import Timeframe
    from smc.core.candle import Candle
    t0 = start or datetime(2025, 6, 1, tzinfo=timezone.utc)
    bars = [Candle(timestamp=t0 + timedelta(minutes=5 * i), open=o, high=h,
                   low=l, close=c, timeframe=Timeframe.M5)
            for i in range(n)]
    return CandleSeries(bars, Timeframe.M5)


# --------------------------------------------------------------------------- #
# 1. htf_context trichotomy (recorded relation only, zero new params)
# --------------------------------------------------------------------------- #
def test_htf_context_mapping():
    pack = _load_pack()
    assert pack.htf_context("inside") == "inside"
    assert pack.htf_context("retest") == "near"
    assert pack.htf_context("above") == "far"
    assert pack.htf_context("below") == "far"
    assert pack.htf_context("  Inside ") == "inside"  # case/space tolerant
    assert pack.htf_context("") == "unknown"
    assert pack.htf_context(None) == "unknown"
    assert pack.htf_context("sideways") == "unknown"


# --------------------------------------------------------------------------- #
# 2. Level parsing (single price vs lo..hi range midpoint)
# --------------------------------------------------------------------------- #
def test_parse_level_shapes():
    pack = _load_pack()
    assert pack.parse_level("3309.335000") == (3309.335, 3309.335, 3309.335)
    lo, hi, ref = pack.parse_level("3306.115000..3311.248000")
    assert (lo, hi) == (3306.115, 3311.248)
    assert ref == (lo + hi) / 2.0
    assert pack.parse_level("") == (None, None, None)
    assert pack.parse_level(None) == (None, None, None)
    assert pack.parse_level("abc") == (None, None, None)
    assert pack.parse_level("5.0..1.0") == (None, None, None)  # inverted


# --------------------------------------------------------------------------- #
# 3. Wilson interval properties (no hardcoded oracle values)
# --------------------------------------------------------------------------- #
def test_wilson_properties():
    pack = _load_pack()
    assert pack.wilson(0, 0) == (None, None)
    assert pack.wilson(-1, 10) == (None, None)
    assert pack.wilson(11, 10) == (None, None)
    lo, hi = pack.wilson(5, 10)
    assert lo < 0.5 < hi                       # contains the sample rate
    lo0, hi0 = pack.wilson(0, 10)
    assert lo0 == 0.0 and hi0 > 0.0            # zero hits, nonzero upper
    lo1, hi1 = pack.wilson(10, 10)
    assert lo1 < 1.0 and hi1 == 1.0            # all hits, non-one lower
    a, b = pack.wilson(3, 10)                 # symmetry k <-> n-k
    c, d = pack.wilson(7, 10)
    assert abs(a - (1.0 - d)) < 1e-12 and abs(b - (1.0 - c)) < 1e-12
    narrow = pack.wilson(500, 1000)
    wide = pack.wilson(5, 10)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])  # shrinks with n


# --------------------------------------------------------------------------- #
# 4. ATR-unit excursion math
# --------------------------------------------------------------------------- #
def test_excursion_atr_long_short():
    pack = _load_pack()
    m5 = _m5_series(10)
    mfe, mae = pack.excursion_atr(m5, 2, 5, True, 100.0, 2.0)
    assert mfe == (100.5 - 100.0) / 2.0       # 0.25
    assert mae == (100.0 - 99.5) / 2.0        # 0.25
    mfe, mae = pack.excursion_atr(m5, 2, 5, False, 100.0, 2.0)
    assert mfe == (100.0 - 99.5) / 2.0
    assert mae == (100.5 - 100.0) / 2.0
    assert pack.excursion_atr(m5, 2, 5, True, 100.0, 0.0) == (None, None)
    assert pack.excursion_atr(m5, 5, 2, True, 100.0, 2.0) == (None, None)
    assert pack.excursion_atr(m5, 2, 500, True, 100.0, 2.0) == (None, None)


# --------------------------------------------------------------------------- #
# 5. Zone fate (VIOLATED dominates, touch recorded, strict bounds)
# --------------------------------------------------------------------------- #
def test_zone_fate_reads():
    pack = _load_pack()
    base = datetime(2025, 6, 1, tzinfo=timezone.utc)

    def series(closes, highs=None, lows=None):
        from smc.backtest.data_feed import CandleSeries
        from smc.config.timeframe import Timeframe
        from smc.core.candle import Candle
        bars = [Candle(timestamp=base + timedelta(minutes=5 * i), open=105.0,
                       high=(highs[i] if highs else 106.0),
                       low=(lows[i] if lows else 104.0), close=closes[i],
                       timeframe=Timeframe.M5)
                for i in range(len(closes))]
        return CandleSeries(bars, Timeframe.M5)

    touched = series([105.0] * 25)
    out = pack.zone_fate(touched, 0, 100.0, 110.0, True)
    assert out["fate"] == "TOUCHED" and out["touched"] is True
    assert out["violated"] is False and out["first_touch_offset"] == 0

    violated = series([105.0] * 10 + [99.0] + [105.0] * 14)
    out = pack.zone_fate(violated, 0, 100.0, 110.0, True)
    assert out["fate"] == "VIOLATED" and out["violated"] is True

    quiet = series([120.0] * 25, highs=[121.0] * 25, lows=[119.0] * 25)
    out = pack.zone_fate(quiet, 0, 100.0, 110.0, True)
    assert out["fate"] == "UNTOUCHED"

    short = series([99.0] * 25)
    out = pack.zone_fate(short, 0, 100.0, 110.0, False)
    assert out["fate"] == "TOUCHED"  # range intersects regardless of side

    tiny = series([105.0] * 5)
    out = pack.zone_fate(tiny, 0, 100.0, 110.0, True)
    assert out["fate"] == "DATA_GAP"  # window truncated by series bounds


# --------------------------------------------------------------------------- #
# 6. Content hashing (deterministic event ids)
# --------------------------------------------------------------------------- #
def test_content_hash_stable():
    pack = _load_pack()
    assert pack.content_hash("a", "b") == pack.content_hash("a", "b")
    assert pack.content_hash("a", "b") != pack.content_hash("a", "c")
    assert len(pack.content_hash("x")) == 8


# --------------------------------------------------------------------------- #
# 7. Frozen params present with audit values
# --------------------------------------------------------------------------- #
def test_frozen_params_match_audit():
    pack = _load_pack()
    assert pack.H_ZONE == 20
    assert pack.H_PATH == 100
    assert pack.MIN_CELL_N == 30
