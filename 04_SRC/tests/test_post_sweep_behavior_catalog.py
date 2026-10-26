"""Post-sweep behavior catalog — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/post_sweep_behavior_catalog.py``: thesis
alignment, linkage overlap, touch runs, first violation, mitigation
touch, and level parsing. Series loading and detector calls are
covered by the run itself (cross-check gate); no threshold, no gate,
no expectancy assertion.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "post_sweep_behavior_catalog.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "post_sweep_behavior_catalog", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["post_sweep_behavior_catalog"] = module
    spec.loader.exec_module(module)
    return module


def _bars(spec):
    """(high, low, close) tuples from compact rows."""
    return [(h, l, c) for (_o, h, l, c) in spec]


# --------------------------------------------------------------------------- #
# 1. Thesis alignment + linkage overlap (frozen rules)
# --------------------------------------------------------------------------- #
def test_thesis_aligned():
    pack = _load_pack()
    assert pack.thesis_aligned("LONG", "long") is True
    assert pack.thesis_aligned("SHORT", "LONG") is False
    assert pack.thesis_aligned("LONG", "") is False
    assert pack.thesis_aligned(None, "long") is False


def test_ranges_overlap():
    pack = _load_pack()
    assert pack.ranges_overlap(100.0, 110.0, 105.0, 115.0) is True
    assert pack.ranges_overlap(100.0, 110.0, 100.0, 110.0) is True
    assert pack.ranges_overlap(100.0, 110.0, 110.0, 120.0) is True
    assert pack.ranges_overlap(100.0, 110.0, 111.0, 120.0) is False


# --------------------------------------------------------------------------- #
# 2. Touch bars/runs/first (inclusive intersection)
# --------------------------------------------------------------------------- #
def test_touch_stats_bars_runs_first():
    pack = _load_pack()
    # bars: touch, touch (run), gap, touch (new run), gap.
    bars = _bars([(0, 106, 104, 105), (0, 107, 103, 104),
                  (0, 95, 90, 92), (0, 106, 104, 105),
                  (0, 95, 90, 92)])
    n_bars, n_runs, first = pack.touch_stats(bars, 100.0, 110.0, 0, 4)
    assert (n_bars, n_runs, first) == (3, 2, 0)
    n_bars, n_runs, first = pack.touch_stats(bars, 100.0, 110.0, 2, 4)
    assert (n_bars, n_runs, first) == (1, 1, 1)  # offsets relative to start
    n_bars, n_runs, first = pack.touch_stats(bars, 200.0, 210.0, 0, 4)
    assert (n_bars, n_runs, first) == (0, 0, None)


# --------------------------------------------------------------------------- #
# 3. Violation first-offset (adverse close only, both sides)
# --------------------------------------------------------------------------- #
def test_first_violation():
    pack = _load_pack()
    bars = _bars([(0, 102, 100, 101), (0, 101, 99, 98), (0, 100, 97, 98)])
    assert pack.first_violation(bars, 100.0, 110.0, True, 0, 2) == 1
    assert pack.first_violation(bars, 100.0, 110.0, False, 0, 2) is None
    bars2 = _bars([(0, 102, 100, 101), (0, 112, 100, 111)])
    assert pack.first_violation(bars2, 100.0, 110.0, False, 0, 1) == 1
    # Close exactly on the edge is not beyond (strict).
    bars3 = _bars([(0, 102, 100, 100.0)])
    assert pack.first_violation(bars3, 100.0, 110.0, True, 0, 0) is None


# --------------------------------------------------------------------------- #
# 4. Mitigation touch + level parsing (singles and ranges)
# --------------------------------------------------------------------------- #
def test_first_mitigation_and_parse_bounds():
    pack = _load_pack()
    assert pack.parse_bounds("3306.115000..3311.248000") == (3306.115, 3311.248)
    assert pack.parse_bounds("100.5") == (100.5, 100.5)
    assert pack.parse_bounds("") == (None, None)
    assert pack.parse_bounds(None) == (None, None)
    assert pack.parse_bounds("5.0..1.0") == (None, None)
    bars = _bars([(0, 95, 90, 92), (0, 101, 99, 100), (0, 108, 106, 107)])
    assert pack.first_mitigation(bars, 100.0, 102.0, 0, 2) == 1
    assert pack.first_mitigation(bars, 200.0, 210.0, 0, 2) is None


# --------------------------------------------------------------------------- #
# 5. Frozen params present with directive values
# --------------------------------------------------------------------------- #
def test_frozen_horizons():
    pack = _load_pack()
    assert pack.H_TRIG == 48
    assert pack.H_PATH == 100
