"""HTF POI census — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/htf_poi_census.py``: episode identity, window
membership, and content hashing. Detection itself is product code
(already tested); this file tests only the census bookkeeping. No
threshold, no gate, no expectancy assertion anywhere.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "htf_poi_census.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "htf_poi_census", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["htf_poi_census"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# 1. Episode identity (same side + same rounded geometry)
# --------------------------------------------------------------------------- #
def test_episode_key_groups_geometry_not_tags():
    pack = _load_pack()
    a = pack.episode_key("LONG", 100.1234, 110.5678)
    b = pack.episode_key("long", 100.12349, 110.56781)
    assert a == b  # case + sub-pip rounding tolerant
    assert pack.episode_key("SHORT", 100.1234, 110.5678) != a  # side matters
    c = pack.episode_key("LONG", 100.125, 110.5678)
    assert c != a  # 0.002 apart rounds apart at 3 decimals


# --------------------------------------------------------------------------- #
# 2. Window membership (frozen exec window, inclusive both ends)
# --------------------------------------------------------------------------- #
def test_in_window_boundaries():
    pack = _load_pack()
    assert pack.in_window(date(2025, 6, 1)) is True
    assert pack.in_window(date(2025, 11, 30)) is True
    assert pack.in_window(date(2025, 8, 15)) is True
    assert pack.in_window(date(2025, 5, 31)) is False
    assert pack.in_window(date(2025, 12, 1)) is False
    assert pack.in_window(date(2026, 1, 1)) is False


# --------------------------------------------------------------------------- #
# 3. Content hashing (deterministic episode ids)
# --------------------------------------------------------------------------- #
def test_content_hash_stable():
    pack = _load_pack()
    assert pack.content_hash("a", 1.5) == pack.content_hash("a", 1.5)
    assert pack.content_hash("a", 1.5) != pack.content_hash("a", 1.6)
    assert len(pack.content_hash("x")) == 8


# --------------------------------------------------------------------------- #
# 4. Frozen params present with directive values
# --------------------------------------------------------------------------- #
def test_frozen_window_and_prefix_floor():
    pack = _load_pack()
    assert (pack.EXEC_FROM.year, pack.EXEC_FROM.month) == (2025, 6)
    assert (pack.EXEC_TO.year, pack.EXEC_TO.month) == (2025, 11)
    assert pack.MIN_PREFIX_BARS == 60
