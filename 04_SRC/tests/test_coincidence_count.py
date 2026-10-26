"""Coincidence count — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/coincidence_count.py``: the coincidence window rule
(strict-greater start, inclusive end), completion de-duplication, the
conservative day-close PROXY anchor, direction-free zone containment, the
fate / state precedence orders, the pre-registered kill-criteria rule, and
the frozen horizon + exec-origin constants (a change to the measurement
rule must fail loudly, not silently re-label artifacts).

No threshold, no gate, no routing rule, no expectancy assertion — this
file tests measurement arithmetic only.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

_SCRIPT_PATH = (Path(__file__).resolve().parents[2]
                / "06_RESEARCH" / "scripts" / "coincidence_count.py")


def _load():
    spec = importlib.util.spec_from_file_location(
        "coincidence_count", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["coincidence_count"] = module
    spec.loader.exec_module(module)
    return module


def _comp(bar, letter):
    return {"bar": bar, "trigger": SimpleNamespace(value=f"{letter}_x")}


# --------------------------------------------------------------------------- #
# 1. Frozen constants (measurement rule pinned)
# --------------------------------------------------------------------------- #
def test_frozen_horizons_and_origin():
    m = _load()
    assert m.H_PRIMARY == 48
    assert m.H_SENS == (20, 38, 58)
    assert m.MAX_H == 58
    assert m.EXEC_ORIGIN.isoformat().startswith("2025-06-01T22:00")
    assert m.BANNER == "DIAGNOSTIC — NOT EDGE"


# --------------------------------------------------------------------------- #
# 2. Coincidence window: ref < bar <= ref + H (both edges pinned)
# --------------------------------------------------------------------------- #
def test_within_window_edges():
    m = _load()
    assert m.within(11, 10, 48) is True
    assert m.within(10, 10, 48) is False          # the reference bar itself
    assert m.within(58, 10, 48) is True           # ref + H inclusive
    assert m.within(59, 10, 48) is False
    assert m.within(10, 10, 0) is False
    assert m.within(11, 10, 0) is False   # H=0 -> empty window by design


def test_within_window_none_safe():
    m = _load()
    assert m.within(None, 10, 48) is False
    assert m.within(11, None, 48) is False


def test_nested_horizons_monotonic():
    m = _load()
    comps = [_comp(3, "F"), _comp(21, "A"), _comp(45, "B")]
    counts = [sum(1 for c in comps if m.within(c["bar"], 0, h))
              for h in (20, 38, 48, 58)]
    assert counts == [1, 2, 3, 3]


# --------------------------------------------------------------------------- #
# 3. De-duplication (a pair is never counted twice)
# --------------------------------------------------------------------------- #
def test_dedupe_collapses_repeats_keeps_order():
    m = _load()
    comps = [_comp(12, "F"), _comp(12, "F"), _comp(5, "A"), _comp(12, "A"),
             _comp(5, "A")]
    out = m.dedupe_completions(comps)
    assert [(c["bar"], m.step3.trigger_letter(c["trigger"])) for c in out] == \
        [(5, "A"), (12, "A"), (12, "F")]
    assert len(m.dedupe_completions([])) == 0


# --------------------------------------------------------------------------- #
# 4. PROXY anchor is the day CLOSE (conservative, no look-ahead)
# --------------------------------------------------------------------------- #
def test_day_close_index_picks_last_bar_of_date():
    m = _load()
    stamps = ["2025-06-02 23:50", "2025-06-02 23:55", "2025-06-03 00:00",
              "2025-06-03 00:05"]
    assert m.day_close_index(stamps, "2025-06-02") == 1
    assert m.day_close_index(stamps, "2025-06-03") == 3
    assert m.day_close_index(stamps, "2025-06-02 00:00") == 1
    assert m.day_close_index(stamps, "2025-06-04") is None
    assert m.day_close_index(stamps, "") is None
    assert m.day_close_index([], "2025-06-02") is None


# --------------------------------------------------------------------------- #
# 5. Direction-free containment (inclusive bounds, no invented tolerance)
# --------------------------------------------------------------------------- #
def test_zone_inside_boundaries():
    m = _load()
    assert m.zone_inside(10.0, 20.0, 10.0, 20.0) is True
    assert m.zone_inside(9.99, 20.0, 10.0, 20.0) is False
    assert m.zone_inside(10.0, 20.01, 10.0, 20.0) is False
    assert m.zone_inside(12.0, 18.0, 10.0, 20.0) is True


# --------------------------------------------------------------------------- #
# 5b. Join edges: smallest-area container, deterministic tie-break
# --------------------------------------------------------------------------- #
def test_pick_container_smallest_area():
    m = _load()
    assert m.pick_container([]) is None
    bands = [("poi-wide", 10.0, 100.0), ("poi-narrow", 40.0, 50.0),
             ("poi-mid", 30.0, 60.0)]
    assert m.pick_container(bands)[0] == "poi-narrow"
    assert m.pick_container(bands[:1])[0] == "poi-wide"
    # ties on area break by poi_id, never by list order
    tie = [("poi-b", 0.0, 10.0), ("poi-a", 5.0, 15.0)]
    assert m.pick_container(tie)[0] == "poi-a"
    assert m.pick_container(list(reversed(tie)))[0] == "poi-a"


# --------------------------------------------------------------------------- #
# 6. Fate precedence: filled > routed > joined > zone_only > never_armed
# --------------------------------------------------------------------------- #
def test_fate_precedence():
    m = _load()
    assert m.fate_for(ever_filled=True, ever_routed=True, joined=True,
                      zone_only=True) == "filled"
    assert m.fate_for(ever_filled=False, ever_routed=True, joined=True,
                      zone_only=True) == "routed"
    assert m.fate_for(ever_filled=False, ever_routed=False, joined=True,
                      zone_only=True) == "armed_never_routed"
    assert m.fate_for(ever_filled=False, ever_routed=False, joined=False,
                      zone_only=True) == "armed_never_routed_zone_only"
    assert m.fate_for(ever_filled=False, ever_routed=False, joined=False,
                      zone_only=False) == "never_armed"
    assert set(m.FATE_ORDER) == {
        "filled", "routed", "armed_never_routed",
        "armed_never_routed_zone_only", "never_armed"}


# --------------------------------------------------------------------------- #
# 7. State precedence: swept > armed_only > proxy_first_seen
# --------------------------------------------------------------------------- #
def test_state_precedence():
    m = _load()
    assert m.state_at(ref_is_sweep=True, armed_at=True) == "swept"
    assert m.state_at(ref_is_sweep=True, armed_at=False) == "swept"
    assert m.state_at(ref_is_sweep=False, armed_at=True) == "armed_only"
    assert m.state_at(ref_is_sweep=False, armed_at=False) == "proxy_first_seen"
    assert set(m.STATE_ORDER) == {"swept", "armed_only", "proxy_first_seen"}


# --------------------------------------------------------------------------- #
# 8. Pre-registered kill-criteria rule
# --------------------------------------------------------------------------- #
def test_kill_verdict_rule():
    m = _load()
    assert m.kill_verdict(9, 9, 9) == "SEQUENCE_REDESIGN_MOOT"
    assert m.kill_verdict(0, 0, 0) == "SEQUENCE_REDESIGN_MOOT"
    assert m.kill_verdict(10, 10, 10) == "COINCIDENCE_MASS_PRESENT"
    assert m.kill_verdict(585, 522, 642) == "COINCIDENCE_MASS_PRESENT"
    # 10 episodes but a window-unstable definition -> fragile, not mass
    assert m.kill_verdict(10, 4, 20) == "INCONCLUSIVE"
    # exactly on the 25% stability bound stays "stable" (<=)
    assert m.kill_verdict(100, 100, 125) == "COINCIDENCE_MASS_PRESENT"
    assert m.kill_verdict(100, 100, 126) == "INCONCLUSIVE"


# --------------------------------------------------------------------------- #
# 9. TF group classification
# --------------------------------------------------------------------------- #
def test_m8_group_classification():
    m = _load()
    assert m.is_m8_group("M8-H4") is True
    assert m.is_m8_group("M8-D1") is True
    assert m.is_m8_group("H4") is False
    assert m.is_m8_group("H1") is False
