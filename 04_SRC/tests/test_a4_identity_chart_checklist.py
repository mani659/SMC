"""A4 identity chart checklist — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/a4_identity_chart_checklist.py``: checklist
selection (all contained + earliest-N partials, deduped, ordered) and
panel-window clamping. Rendering itself is eyeballed (two panels read
in the build session); no threshold, no gate, no expectancy assertion.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "a4_identity_chart_checklist.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "a4_identity_chart_checklist", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["a4_identity_chart_checklist"] = module
    spec.loader.exec_module(module)
    return module


def _row(eid, kind, ts):
    return {"episode_id": eid, "match_kind": kind, "first_sweep_ts": ts}


# --------------------------------------------------------------------------- #
# 1. Selection: all contained + earliest-N partials, deduped, ordered
# --------------------------------------------------------------------------- #
def test_select_checklist_priorities():
    pack = _load_pack()
    rows = ([_row(f"c{i:02d}", "contained", f"2025-08-{i + 1:02d}T00:00:00+00:00")
             for i in range(3)] +
            [_row(f"p{i:02d}", "partial", f"2025-06-{i + 1:02d}T00:00:00+00:00")
             for i in range(5)] +
            [_row("x1", "exact", "2025-06-01T00:00:00+00:00")])
    picked = pack.select_checklist(rows, n_partial=2)
    kinds = [r["match_kind"] for r in picked]
    assert kinds.count("contained") == 3    # all contained, any date
    assert kinds.count("partial") == 2      # earliest two partials only
    assert [r["episode_id"] for r in picked if r["match_kind"] == "partial"] == ["p00", "p01"]
    assert "x1" not in [r["episode_id"] for r in picked]  # other kinds out
    # Deterministic review order (sweep ts, then id).
    keys = [(r["first_sweep_ts"], r["episode_id"]) for r in picked]
    assert keys == sorted(keys)


def test_select_checklist_dedupes_and_defaults():
    pack = _load_pack()
    rows = [_row("c1", "contained", "2025-07-01T00:00:00+00:00"),
            _row("c1", "contained", "2025-07-01T00:00:00+00:00")]
    assert len(pack.select_checklist(rows)) == 1
    assert pack.select_checklist([]) == []


# --------------------------------------------------------------------------- #
# 2. Panel window clamps (house convention)
# --------------------------------------------------------------------------- #
def test_panel_window_clamps():
    pack = _load_pack()
    assert pack.panel_window(1000, 500, 90) == (410, 590, 90)
    assert pack.panel_window(1000, 10, 90) == (0, 100, 10)     # left edge
    assert pack.panel_window(1000, 990, 90) == (900, 1000, 90)  # right edge
    s, e, o = pack.panel_window(50, 25, 90)
    assert (s, e, o) == (0, 50, 25) and e - s == 50
