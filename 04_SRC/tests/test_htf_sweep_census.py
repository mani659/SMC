"""HTF sweep census — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/htf_sweep_census.py``: pool→bias reporting map,
unique-level identity, touch-proximity bisect, exact zone containment,
content hashing, and the re-fire enumeration loop over the real
``detect_sweep`` predicate. No threshold, no gate, no expectancy
assertion anywhere.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "htf_sweep_census.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "htf_sweep_census", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["htf_sweep_census"] = module
    spec.loader.exec_module(module)
    return module


def _candle(ts, o, h, l, c):
    from smc.config.timeframe import Timeframe
    from smc.core.candle import Candle
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c,
                  timeframe=Timeframe.H1)


# --------------------------------------------------------------------------- #
# 1. Reporting maps (frozen conventions, not signals)
# --------------------------------------------------------------------------- #
def test_bias_for_pool():
    pack = _load_pack()
    assert pack.bias_for_pool("bsl") == "SHORT"   # fade the swept highs
    assert pack.bias_for_pool("ssl") == "LONG"    # fade the swept lows
    assert pack.bias_for_pool("BSL") == "SHORT"   # case tolerant
    assert pack.bias_for_pool("major_structural") == "pool-side"
    assert pack.bias_for_pool(None) == "pool-side"
    assert pack.bias_for_pool("") == "pool-side"


def test_sweep_key_exact_levels():
    pack = _load_pack()
    assert pack.sweep_key("bsl", 100.5) == pack.sweep_key("BSL", 100.5)
    assert pack.sweep_key("bsl", 100.5) != pack.sweep_key("ssl", 100.5)
    assert pack.sweep_key("bsl", 100.5) != pack.sweep_key("bsl", 100.6)


# --------------------------------------------------------------------------- #
# 2. Touch proximity (bisect, signed, strict radius applied by caller)
# --------------------------------------------------------------------------- #
def test_nearest_touch_offset():
    pack = _load_pack()
    touches = [10, 50, 100]
    assert pack.nearest_touch_offset(touches, 12) == -2   # touch at 10
    assert pack.nearest_touch_offset(touches, 8) == 2
    assert pack.nearest_touch_offset(touches, 50) == 0
    assert pack.nearest_touch_offset(touches, 200) == -100  # signed: lag
    assert pack.nearest_touch_offset([], 50) is None


# --------------------------------------------------------------------------- #
# 3. Zone link (exact containment, no tolerance invented)
# --------------------------------------------------------------------------- #
def test_zone_link_exact_containment():
    pack = _load_pack()
    zones = [{"event_id": "a", "zone_low": 100.0, "zone_high": 110.0},
             {"event_id": "b", "zone_low": 200.0, "zone_high": 210.0}]
    assert pack.zone_link(zones, 105.0) == ["a"]
    assert pack.zone_link(zones, 100.0) == ["a"]   # boundary inclusive
    assert pack.zone_link(zones, 110.0) == ["a"]
    assert pack.zone_link(zones, 99.999) == []
    assert pack.zone_link(zones, 150.0) == []
    assert pack.zone_link([], 105.0) == []


# --------------------------------------------------------------------------- #
# 4. Re-fire enumeration reuses the real predicate (first + repeats)
# --------------------------------------------------------------------------- #
def test_all_sweeps_for_level_finds_first_and_refires():
    from smc.core.enums import LiquidityType, PoolType
    from smc.core.liquidity_level import LiquidityLevel
    pack = _load_pack()
    t0 = datetime(2025, 6, 1, tzinfo=timezone.utc)
    # SSL level at 100: bar 1 sweeps (low 99, close back 101), bar 3 re-fires.
    bars = [_candle(t0, 102.0, 103.0, 101.0, 102.0),
            _candle(t0 + timedelta(hours=1), 101.0, 102.0, 99.0, 101.0),
            _candle(t0 + timedelta(hours=2), 101.0, 102.0, 100.5, 101.5),
            _candle(t0 + timedelta(hours=3), 101.0, 102.0, 98.0, 101.0)]
    level = LiquidityLevel(type=LiquidityType.STRUCTURAL_SWING, level=100.0,
                           pool=PoolType.SSL)
    out = pack.all_sweeps_for_level(bars, level)
    assert [r.candle_index for r in out] == [1, 3]
    # A level never swept yields nothing (no fabrication).
    calm = LiquidityLevel(type=LiquidityType.STRUCTURAL_SWING, level=50.0,
                          pool=PoolType.SSL)
    assert pack.all_sweeps_for_level(bars, calm) == []


# --------------------------------------------------------------------------- #
# 5. Content hashing (deterministic event ids)
# --------------------------------------------------------------------------- #
def test_content_hash_stable():
    pack = _load_pack()
    assert pack.content_hash("a", 1.5) == pack.content_hash("a", 1.5)
    assert pack.content_hash("a", 1.5) != pack.content_hash("a", 1.6)
    assert len(pack.content_hash("x")) == 8


# --------------------------------------------------------------------------- #
# 6. Frozen params present with directive values
# --------------------------------------------------------------------------- #
def test_frozen_window_and_proximity():
    pack = _load_pack()
    assert pack.EXEC_FROM == datetime(2025, 6, 1, tzinfo=timezone.utc)
    assert (pack.EXEC_TO.year, pack.EXEC_TO.month) == (2025, 11)
    assert pack.PROXIMITY_BARS == 20
