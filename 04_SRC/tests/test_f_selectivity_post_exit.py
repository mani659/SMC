"""F selectivity + post-exit path — focused tests (research only).

Locks the frozen definitions of
``06_RESEARCH/scripts/f_selectivity_post_exit.py`` without re-running
any book: Rule v1 label boundaries, zone relation, honest-R strictness,
the fill-referenced excursion convention, the no-TP outcome branch,
the strict horizon-truncation rule, and trade-identity normalization.

No strategy code is exercised; no threshold, gate, or expectancy
assertion appears anywhere here.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "f_selectivity_post_exit.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "f_selectivity_post_exit", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["f_selectivity_post_exit"] = module
    spec.loader.exec_module(module)
    return module


def _candle(ts, o, h, l, c, tf=None):
    from smc.config.timeframe import Timeframe
    from smc.core.candle import Candle
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c,
                  timeframe=tf or Timeframe.M1)


def _m5(ts, o, h, l, c):
    from smc.config.timeframe import Timeframe
    return _candle(ts, o, h, l, c, Timeframe.M5)


# --------------------------------------------------------------------------- #
# 1. Frozen Rule v1 boundaries (no iteration to maximize separation)
# --------------------------------------------------------------------------- #
def test_timing_label_frozen_boundaries():
    pack = _load_pack()
    A = pack.timing_label
    # chop dominates regardless of chase position.
    assert A(100.0, True, 101.0, 100.0, 10.0)[0] == "chop"  # range 1 < 15
    # chase cut lines (range 10, atr 10 -> ratr 1.0? no: need ratr >= 1.5).
    # window 0..20 (range 20), atr 10 -> ratr 2.0: position decides.
    assert A(16.0, True, 20.0, 0.0, 10.0)[0] == "late_chase"   # 0.80 exactly
    assert A(15.998, True, 20.0, 0.0, 10.0)[0] == "mid_move"   # just under
    assert A(9.0, True, 20.0, 0.0, 10.0)[0] == "mid_move"      # 0.45 exactly
    assert A(8.998, True, 20.0, 0.0, 10.0)[0] == "structured_pullback"
    # short side mirrors (1 = extreme in trade direction).
    assert A(4.0, False, 20.0, 0.0, 10.0)[0] == "late_chase"   # (20-4)/20
    assert A(16.0, False, 20.0, 0.0, 10.0)[0] == "structured_pullback"
    # degenerate geometry -> unclear, never invented.
    assert A(100.0, True, 100.0, 100.0, 10.0)[0] == "unclear"
    assert A(100.0, True, 110.0, 100.0, 0.0)[0] == "unclear"


def test_zone_relation_cases():
    pack = _load_pack()
    Z = pack.zone_relation
    assert Z(105.0, 100.0, 110.0) == "INSIDE"
    assert Z(100.0, 100.0, 110.0) == "INSIDE"   # boundary inclusive
    assert Z(95.0, 100.0, 110.0) == "below 50%"
    assert Z(115.0, 100.0, 110.0) == "above 50%"
    assert Z(105.0, None, 110.0) == "unknown"
    assert Z(105.0, 110.0, 100.0) == "unknown"  # inverted zone


# --------------------------------------------------------------------------- #
# 2. Honest R strictness + fill-referenced excursion
# --------------------------------------------------------------------------- #
def test_honest_r_strict_denominator():
    pack = _load_pack()
    assert pack.honest_r(2.0, 100.0, 98.0) == 1.0
    assert pack.honest_r(2.0, 100.0, None) is None      # never working-sl
    assert pack.honest_r(None, 100.0, 98.0) is None
    assert pack.honest_r(2.0, 100.0, 100.0) is None     # degenerate denom


def test_m1_excursion_uses_fill_reference():
    pack = _load_pack()
    t0 = datetime(2025, 10, 1, tzinfo=timezone.utc)
    # SHORT filled at 100; bar dips to 99 then closes 101 (adverse).
    bars = [_candle(t0, 100.5, 101.0, 99.0, 101.0)]
    mfe, mae = pack.m1_excursion(bars, 0, 0, False, 100.0)
    assert mfe == 1.0   # 100 - 99 (fill-referenced ...
    assert mae == 1.0   # ... NOT close-referenced (101-99 = 2 would differ)
    # LONG mirror.
    mfe, mae = pack.m1_excursion(bars, 0, 0, True, 100.0)
    assert mfe == 1.0 and mae == 1.0
    # Unresolvable / inverted windows -> (None, None), never invented.
    assert pack.m1_excursion(bars, None, 0, True, 100.0) == (None, None)
    assert pack.m1_excursion(bars, 1, 0, True, 100.0) == (None, None)
    assert pack.m1_excursion(bars, 0, 0, True, None) == (None, None)


# --------------------------------------------------------------------------- #
# 3. No-TP outcome branch (same labels/order, TP paths unreachable)
# --------------------------------------------------------------------------- #
def test_classify_no_tp_buckets():
    pack = _load_pack()
    C = pack.classify_no_tp
    # BE-scratch defaults before any R evaluation (frozen order).
    assert C("long", 0.5, 0.4, 0.05, True, True)[0] == "MFE_ONLY"
    # Sub-divider rejects (strict, M1 fill-referenced R supplied).
    assert C("long", 0.1, 1.2, 0.10, True, False)[0] == "REJECTED"
    # Favorable excursion without a TP level to test -> MFE_ONLY.
    assert C("short", 1.5, 0.4, 1.50, True, False)[0] == "MFE_ONLY"
    # Stop with no favorable excursion at all -> REJECTED.
    assert C("short", 0.0, 2.0, 0.0, True, False)[0] == "REJECTED"
    # TP-path labels are unreachable here by construction.
    for args in [("long", 5.0, 0.1, 9.0, True, False),
                 ("long", 0.0, 0.0, 0.0, False, False)]:
        assert C(*args)[0] in ("MFE_ONLY", "REJECTED")


def test_post_exit_strict_truncation_and_unresolvable():
    from smc.backtest.data_feed import CandleSeries
    from smc.config.timeframe import Timeframe
    pack = _load_pack()
    t0 = datetime(2025, 10, 1, tzinfo=timezone.utc)
    bars = [_m5(t0 + timedelta(minutes=5 * i), 100.0, 100.5, 99.5, 100.0)
            for i in range(30)]
    m5 = CandleSeries(bars, Timeframe.M5)
    base = {"direction": "long", "entry_price": "100.0",
            "original_sl": "90.0", "tp": "", "close_kind": "stop_loss",
            "pnl": "-5.0"}
    # Exit on the last bar: fewer than 100 M5 bars follow -> DATA_GAP.
    row = dict(base, entry_at=bars[10].timestamp.isoformat(),
               exit_at=bars[29].timestamp.isoformat())
    out = pack.post_exit(row, m5)
    assert out["post_exit_outcome"] == "DATA_GAP"
    assert out["horizon_truncated"] is True
    # Ungarbage timestamps -> DATA_GAP, never invented.
    row = dict(base, entry_at="not-a-time", exit_at=bars[5].timestamp.isoformat())
    out = pack.post_exit(row, m5)
    assert out["post_exit_outcome"] == "DATA_GAP"


def test_post_exit_no_tp_full_horizon_rejects():
    from smc.backtest.data_feed import CandleSeries
    from smc.config.timeframe import Timeframe
    pack = _load_pack()
    t0 = datetime(2025, 10, 1, tzinfo=timezone.utc)
    # Flat-then-down: LONG from 100, SL 90 (denom 10), never favorable.
    bars = [_m5(t0 + timedelta(minutes=5 * i),
                100.0 - 0.01 * i, 100.1 - 0.01 * i,
                99.9 - 0.01 * i, 100.0 - 0.01 * i)
            for i in range(150)]
    m5 = CandleSeries(bars, Timeframe.M5)
    row = {"direction": "long", "entry_price": "100.0",
           "original_sl": "90.0", "tp": "", "close_kind": "stop_loss",
           "pnl": "-5.0",
           "entry_at": bars[10].timestamp.isoformat(),
           "exit_at": bars[20].timestamp.isoformat()}
    out = pack.post_exit(row, m5, m1_r_override=0.05)
    assert out["post_exit_outcome"] == "REJECTED"
    assert out["horizon_truncated"] is False
    # Same geometry but BE-scratch pnl -> MFE_ONLY default wins.
    row2 = dict(row, pnl="-0.05")
    out2 = pack.post_exit(row2, m5, m1_r_override=0.05)
    assert out2["post_exit_outcome"] == "MFE_ONLY"


# --------------------------------------------------------------------------- #
# 4. Identity + timestamp normalization across books
# --------------------------------------------------------------------------- #
def test_identity_normalizes_price_and_time_spellings():
    pack = _load_pack()
    a = {"entry_at": "2025-10-01 02:41:00+00:00",
         "exit_at": "2025-10-01 02:43:00+00:00",
         "direction": "LONG", "entry_price": "3865.325"}
    b = {"entry_at": "2025-10-01T02:41:00+00:00",
         "exit_at": "2025-10-01T02:43:00+00:00",
         "direction": "long", "entry_price": 3865.325}
    assert pack.identity_of(a) == pack.identity_of(b)  # str/float + T/space
    c = dict(b, entry_price=3865.326)
    assert pack.identity_of(a) != pack.identity_of(c)
    assert pack.minute_key("2025-10-01T02:41:00+00:00") == "2025-10-01 02:41"
    assert pack.minute_key("") is None
