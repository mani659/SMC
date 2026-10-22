"""POI-linked sweep rate — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/poi_linked_sweep_rate.py``: directional-edge
mapping, sweep enumeration with formed_at + window bounds, and
re-sweep counting. Detection itself is product code (already tested).
No threshold, no gate, no expectancy assertion anywhere.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "poi_linked_sweep_rate.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "poi_linked_sweep_rate", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["poi_linked_sweep_rate"] = module
    spec.loader.exec_module(module)
    return module


def _bars(n, start=None):
    from smc.config.timeframe import Timeframe
    from smc.core.candle import Candle
    t0 = start or datetime(2025, 6, 1, tzinfo=timezone.utc)
    return [Candle(timestamp=t0 + timedelta(hours=i), open=100.0, high=101.0,
                   low=99.0, close=100.0, timeframe=Timeframe.H1)
            for i in range(n)]


# --------------------------------------------------------------------------- #
# 1. Directional edge (LONG->SSL-on-low, SHORT->BSL-on-high, else loud)
# --------------------------------------------------------------------------- #
def test_directional_edge_mapping():
    pack = _load_pack()
    edge, pool = pack.directional_edge("LONG", 90.0, 110.0)
    assert edge == 90.0 and pool.value == "ssl"
    edge, pool = pack.directional_edge("SHORT", 90.0, 110.0)
    assert edge == 110.0 and pool.value == "bsl"
    assert pack.directional_edge("long", 90.0, 110.0)[0] == 90.0
    try:
        pack.directional_edge("SIDEWAYS", 90.0, 110.0)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown direction must raise, never mis-side")
    try:
        pack.directional_edge(None, 90.0, 110.0)
    except ValueError:
        pass
    else:
        raise AssertionError("missing direction must raise")


# --------------------------------------------------------------------------- #
# 2. Sweep enumeration respects formed_at, window end, and re-fires
# --------------------------------------------------------------------------- #
def _sweep_bars_long():
    # LONG zone low=100: bar 2 pierces to 99, closes back 101 (sweep);
    # bar 4 re-fires; bar 1 pierces but closes through (breakout, no).
    t0 = datetime(2025, 6, 1, tzinfo=timezone.utc)
    specs = [(100.0, 101.0, 99.5, 100.5),   # 0 calm
             (100.0, 100.5, 98.0, 99.0),    # 1 pierce + close-through
             (101.0, 101.5, 99.0, 101.0),   # 2 SWEEP
             (101.0, 101.5, 100.5, 101.0),  # 3 calm
             (101.0, 101.5, 98.5, 101.0)]   # 4 SWEEP (re-fire)
    from smc.config.timeframe import Timeframe
    from smc.core.candle import Candle
    return [Candle(timestamp=t0 + timedelta(hours=i), open=o, high=h,
                   low=l, close=c, timeframe=Timeframe.H1)
            for i, (o, h, l, c) in enumerate(specs)]


def test_all_sweeps_first_and_refires():
    pack = _load_pack()
    bars = _sweep_bars_long()
    out = pack.all_sweeps_of_edge(
        bars, 100.0, "ssl", formed_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        window_end_exclusive=datetime(2025, 7, 1, tzinfo=timezone.utc))
    assert [r.candle_index for r in out] == [2, 4]


def test_formed_at_bound_excludes_early_sweep():
    pack = _load_pack()
    bars = _sweep_bars_long()
    out = pack.all_sweeps_of_edge(
        bars, 100.0, "ssl",
        formed_at=datetime(2025, 6, 1, 2, tzinfo=timezone.utc),
        window_end_exclusive=datetime(2025, 7, 1, tzinfo=timezone.utc))
    assert [r.candle_index for r in out] == [4]  # bar-2 sweep predates zone


def test_window_end_excludes_late_sweep():
    pack = _load_pack()
    bars = _sweep_bars_long()
    out = pack.all_sweeps_of_edge(
        bars, 100.0, "ssl", formed_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        window_end_exclusive=datetime(2025, 6, 1, 4, tzinfo=timezone.utc))
    assert [r.candle_index for r in out] == [2]  # bar-4 sweep out of window


def test_short_side_mirror():
    pack = _load_pack()
    t0 = datetime(2025, 6, 1, tzinfo=timezone.utc)
    from smc.config.timeframe import Timeframe
    from smc.core.candle import Candle
    bars = [Candle(timestamp=t0, open=100.0, high=100.5, low=99.5,
                   close=100.0, timeframe=Timeframe.H1),
            Candle(timestamp=t0 + timedelta(hours=1), open=99.0, high=101.0,
                   low=98.0, close=99.0, timeframe=Timeframe.H1)]
    out = pack.all_sweeps_of_edge(
        bars, 100.0, "bsl", formed_at=t0,
        window_end_exclusive=datetime(2025, 7, 1, tzinfo=timezone.utc))
    assert [r.candle_index for r in out] == [1]  # pierce high, close back
    # String pools normalize to the same enum predicate (no silent branch).
    from smc.core.enums import PoolType
    out2 = pack.all_sweeps_of_edge(
        bars, 100.0, PoolType.BSL, formed_at=t0,
        window_end_exclusive=datetime(2025, 7, 1, tzinfo=timezone.utc))
    assert [r.candle_index for r in out2] == [1]


# --------------------------------------------------------------------------- #
# 3. Frozen params present with directive values
# --------------------------------------------------------------------------- #
def test_frozen_window_end():
    pack = _load_pack()
    assert (pack.EXEC_END_EXCLUSIVE.year, pack.EXEC_END_EXCLUSIVE.month,
            pack.EXEC_END_EXCLUSIVE.day) == (2025, 12, 1)
