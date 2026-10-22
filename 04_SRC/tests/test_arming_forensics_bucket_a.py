"""Arming forensics bucket A — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/arming_forensics_bucket_a.py``: the ZoneDedup-
equivalent overlap predicate, the A priority classifier, day-distance
parsing, and content hashing. Replay fidelity and batch recording are
covered by the script's own gate (byte identity + funnel equality);
no threshold, no gate, no expectancy assertion.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "arming_forensics_bucket_a.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "arming_forensics_bucket_a", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["arming_forensics_bucket_a"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# 1. Overlap predicate (same direction + ranges intersect, inclusive)
# --------------------------------------------------------------------------- #
def test_overlaps_same_side():
    pack = _load_pack()
    O = pack.overlaps_same_side
    assert O("LONG", 100.0, 110.0, "LONG", 105.0, 115.0) is True
    assert O("LONG", 100.0, 110.0, "LONG", 100.0, 110.0) is True
    assert O("LONG", 100.0, 110.0, "LONG", 110.0, 120.0) is True  # edge touch
    assert O("LONG", 100.0, 110.0, "LONG", 111.0, 120.0) is False
    assert O("LONG", 100.0, 110.0, "SHORT", 100.0, 110.0) is False
    assert O("long", 100.0, 110.0, "LONG", 105.0, 106.0) is True


# --------------------------------------------------------------------------- #
# 2. A priority (identity > pass > fail > absence > gaps)
# --------------------------------------------------------------------------- #
def test_classify_a_priority():
    pack = _load_pack()
    C = pack.classify_a
    assert C(armed_match=True, ever_validated=True, ever_passed=True,
             ever_raw=True, inputs_ok=True) == ("A4", "armed_other_identity")
    assert C(armed_match=False, ever_validated=True, ever_passed=True,
             ever_raw=True, inputs_ok=True) == ("A3", "passed_not_armed")
    assert C(armed_match=False, ever_validated=True, ever_passed=False,
             ever_raw=True, inputs_ok=True) == ("A2", "in_batch_failed_pillars")
    assert C(armed_match=False, ever_validated=False, ever_passed=False,
             ever_raw=True, inputs_ok=True) == (
                 "A1", "detected_but_never_validated")
    assert C(armed_match=False, ever_validated=False, ever_passed=False,
             ever_raw=False, inputs_ok=True) == ("A1", "never_detected")
    assert C(armed_match=True, ever_validated=True, ever_passed=True,
             ever_raw=True, inputs_ok=False) == ("A5", "data_gap")


# --------------------------------------------------------------------------- #
# 3. Day distance (None-safe, absolute)
# --------------------------------------------------------------------------- #
def test_day_diff():
    pack = _load_pack()
    assert pack.day_diff("2025-06-01", "2025-06-01") == 0
    assert pack.day_diff("2025-06-01", "2025-07-01") == 30
    assert pack.day_diff("2025-07-01", "2025-06-01") == 30
    assert pack.day_diff("", "2025-06-01") is None
    assert pack.day_diff(None, None) is None


# --------------------------------------------------------------------------- #
# 4. Content hashing (deterministic episode ids)
# --------------------------------------------------------------------------- #
def test_content_hash_stable():
    pack = _load_pack()
    assert pack.content_hash("a", 1.5) == pack.content_hash("a", 1.5)
    assert pack.content_hash("a", 1.5) != pack.content_hash("a", 1.6)
    assert len(pack.content_hash("x")) == 8


# --------------------------------------------------------------------------- #
# 5. Frozen params present with directive values
# --------------------------------------------------------------------------- #
def test_frozen_window_values():
    pack = _load_pack()
    assert (pack.EXEC_FROM.year, pack.EXEC_FROM.month) == (2025, 6)
    assert (pack.EXEC_TO.year, pack.EXEC_TO.month) == (2025, 11)
