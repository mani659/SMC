"""Step-4 entry path — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/poi_confirm_entry_path.py``: episode join tiers
(exact / smallest-container / none) and the gap taxonomy. Replay
fidelity and time-qualification use suite-level artifacts (covered by
the script's own gate); no threshold, no gate, no expectancy assertion.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "poi_confirm_entry_path.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "poi_confirm_entry_path", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["poi_confirm_entry_path"] = module
    spec.loader.exec_module(module)
    return module


def _poi(pid, direction, low, high):
    return {"poi_id": pid, "direction": direction, "low": low, "high": high}


# --------------------------------------------------------------------------- #
# 1. Join tiers (exact key, then smallest container, else none)
# --------------------------------------------------------------------------- #
def test_match_exact_beats_containment():
    pack = _load_pack()
    engine = [_poi("p1", "LONG", 90.0, 110.0),
              _poi("p2", "LONG", 80.0, 120.0)]
    tier, poi = pack.match_episode(("LONG", 90.0, 110.0), engine)
    assert tier == "exact" and poi["poi_id"] == "p1"


def test_match_containment_picks_smallest():
    pack = _load_pack()
    engine = [_poi("wide", "LONG", 80.0, 120.0),
              _poi("tight", "LONG", 88.0, 112.0)]
    tier, poi = pack.match_episode(("LONG", 90.0, 110.0), engine)
    assert tier == "containment" and poi["poi_id"] == "tight"
    # Opposite direction never contains (same bounds, wrong side).
    tier, poi = pack.match_episode(("SHORT", 90.0, 110.0), engine)
    assert (tier, poi) == ("none", None)
    # Partial overlap without containment is not a join.
    tier2, _ = pack.match_episode(("LONG", 105.0, 115.0),
                                  [_poi("p", "LONG", 100.0, 110.0)])
    assert tier2 == "none"  # overhangs the edge: no containment, no exact


def test_match_none_when_no_geometry():
    pack = _load_pack()
    assert pack.match_episode(("LONG", 90.0, 110.0), []) == ("none", None)


# --------------------------------------------------------------------------- #
# 2. Gap taxonomy (frozen; scans find nothing silently)
# --------------------------------------------------------------------------- #
def test_classify_gap_branches():
    pack = _load_pack()
    G = pack.classify_gap
    assert G(False, False, False, False) == "no-product-POI"
    assert G(True, False, False, False) == "never-scanned"
    assert G(True, True, False, True) == "routed-before-sweep"
    assert G(True, True, False, False) == "scanned-no-route"
    assert G(True, True, True, False) == ""     # routed: no gap
    # Pre-check precedes post-check (a both-ways row reports the
    # pre-sweep consumption; in the pipeline such rows never reach the
    # gap classifier because they have post-sweep routes).
    assert G(True, True, True, True) == "routed-before-sweep"
    # Join beats everything: an unjoined row is gap even if "scanned".
    assert G(False, True, False, False) == "no-product-POI"
