"""Stage 3 lifecycle timing audit — focused tests (identification only).

Locks the invariants demanded by the Lead Architect directive for
``06_RESEARCH/scripts/stage3_lifecycle_timing.py``:

  - join produces non-null structure_close for every completion whose
    ``related_htf_event_id`` is present in the accepted HTF packs,
  - the 2 ``route_would_form=yes`` rows classify as OPEN_SCAN,
  - bucket counts sum to 263,
  - no negative bar deltas that violate causal order (completion before
    structure close is a hard fail),
plus the pure helpers (bucket assignment, percentiles) and the locked
window constants (no section 5 / 23 / 24 widening in this audit).
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PACK_PATH = (_ROOT / "06_RESEARCH" / "scripts" /
              "stage3_lifecycle_timing.py")
_LIFECYCLE_DIR = (_ROOT / "06_RESEARCH" / "results" /
                  "stage3_lifecycle_timing")
_STAGE3_LEDGER = (_ROOT / "06_RESEARCH" / "results" /
                  "stage3_trigger_visibility" / "events_stage3_triggers.csv")
_H4_PACK = (_ROOT / "06_RESEARCH" / "results" /
            "h4_poi_confirmation" / "events_h4_poi.csv")
_D1_PACK = (_ROOT / "06_RESEARCH" / "results" /
            "d1_f1f2_resample" / "events_d1_poi_post_f1f2.csv")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "stage3_lifecycle_timing", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage3_lifecycle_timing"] = module
    spec.loader.exec_module(module)
    return module


def _lifecycle_rows() -> list[dict]:
    path = _LIFECYCLE_DIR / "events_lifecycle.csv"
    if not path.exists() or not _STAGE3_LEDGER.exists():
        pytest.skip("lifecycle audit artifacts not generated yet "
                    "(run 06_RESEARCH/scripts/stage3_lifecycle_timing.py)")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _summary() -> dict:
    path = _LIFECYCLE_DIR / "summary.json"
    if not path.exists():
        pytest.skip("lifecycle audit artifacts not generated yet "
                    "(run 06_RESEARCH/scripts/stage3_lifecycle_timing.py)")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pack_event_ids() -> set[str]:
    ids: set[str] = set()
    for path in (_H4_PACK, _D1_PACK):
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["event_type"] == "poi_raw":
                    ids.add(r["event_id"])
    return ids


# --------------------------------------------------------------------------- #
# 1. Pure helper — bucket assignment (exactly one bucket per completion)
# --------------------------------------------------------------------------- #
def test_assign_bucket_covers_every_case():
    pack = _load_pack()
    A = pack.assign_bucket
    assert A(join_ok=False, completion_bar=5, arm_bar=1,
             last_scanned=3, pop_reason=None, route_bar=None) == "DATA_GAP"
    assert A(join_ok=True, completion_bar=None, arm_bar=1,
             last_scanned=3, pop_reason=None, route_bar=None) == "DATA_GAP"
    assert A(join_ok=True, completion_bar=5, arm_bar=None, last_scanned=None,
             pop_reason=None, route_bar=None) == "NEVER_ARMED"
    # Visible: at or before the last bar the scan was open (inclusive).
    assert A(join_ok=True, completion_bar=3, arm_bar=1, last_scanned=3,
             pop_reason="tested", route_bar=None) == "OPEN_SCAN"
    assert A(join_ok=True, completion_bar=2, arm_bar=1, last_scanned=3,
             pop_reason="violated", route_bar=None) == "OPEN_SCAN"
    # Closed by the gate that actually ended the scan.
    assert A(join_ok=True, completion_bar=4, arm_bar=1, last_scanned=3,
             pop_reason="tested", route_bar=None) == "CLOSED_TOUCH"
    assert A(join_ok=True, completion_bar=9, arm_bar=1, last_scanned=3,
             pop_reason="violated", route_bar=None) == "CLOSED_VIOL"
    # Route retire: completion on the route bar itself stays visible.
    assert A(join_ok=True, completion_bar=7, arm_bar=1, last_scanned=7,
             pop_reason=None, route_bar=7) == "OPEN_SCAN"
    # Residual never silently absorbed (expected count 0 in the audit).
    assert A(join_ok=True, completion_bar=9, arm_bar=1, last_scanned=7,
             pop_reason=None, route_bar=7) == "UNCLASSIFIED"
    assert A(join_ok=True, completion_bar=9, arm_bar=1, last_scanned=7,
             pop_reason="fresh", route_bar=None) == "UNCLASSIFIED"


def test_assign_bucket_never_scanned_touch_gate():
    # Touch gate fired before the scan ever opened (pop at arm bar):
    # not visible -> reason bucket, not OPEN_SCAN.
    pack = _load_pack()
    assert pack.assign_bucket(join_ok=True, completion_bar=5, arm_bar=2,
                              last_scanned=None, pop_reason="tested",
                              route_bar=None) == "CLOSED_TOUCH"


# --------------------------------------------------------------------------- #
# 2. Pure helper — percentiles / distributions (null-safe)
# --------------------------------------------------------------------------- #
def test_pctl_and_distribution_deterministic():
    pack = _load_pack()
    assert pack.pctl([], 0.5) is None
    assert pack.pctl([7.0], 0.25) == 7.0
    data = [1.0, 2.0, 3.0, 4.0]
    assert pack.pctl(data, 0.5) == 2.5
    assert pack.pctl(data, 0.0) == 1.0
    assert pack.pctl(data, 1.0) == 4.0
    assert pack.pctl(data, 0.25) == pytest.approx(1.75)
    d = pack.distribution([3.0, None, 1.0, None, 5.0])
    assert d["n_used"] == 3 and d["n_null"] == 2
    assert d["p25"] == pytest.approx(2.0)
    assert d["median"] == 3.0
    assert d["p75"] == pytest.approx(4.0)


# --------------------------------------------------------------------------- #
# 3. Artifact invariant — join completeness (structure_close never null)
# --------------------------------------------------------------------------- #
def test_join_produces_non_null_structure_close():
    rows = _lifecycle_rows()
    pack_ids = _pack_event_ids()
    assert pack_ids, "accepted HTF packs missing"
    joined = [r for r in rows if r["related_htf_event_id"] in pack_ids]
    assert len(joined) == len(rows), "row joined to an id outside the packs"
    for r in joined:
        assert r["structure_close_ts"], (
            f"missing structure_close for {r['trigger_id']}")
        assert r["arm_ts"], f"missing arm_ts for {r['trigger_id']}"
        assert r["stage3_completion_ts"]
    with open(_STAGE3_LEDGER, encoding="utf-8") as f:
        stage3_rows = list(csv.DictReader(f))
    assert len(rows) == len(stage3_rows)


# --------------------------------------------------------------------------- #
# 4. Artifact invariant — the 2 routed rows classify as OPEN_SCAN
# --------------------------------------------------------------------------- #
def test_routed_rows_classify_open_scan():
    rows = _lifecycle_rows()
    summary = _summary()
    routed = [r for r in rows if r["route_would_form"] == "yes"]
    assert len(routed) == 2
    assert all(r["bucket"] == "OPEN_SCAN" for r in routed)
    assert summary["routed_rows_sanity"]["pass"] is True
    assert summary["routed_rows_sanity"]["found_routed_rows"] == 2


# --------------------------------------------------------------------------- #
# 5. Artifact invariant — bucket counts sum to 263
# --------------------------------------------------------------------------- #
def test_bucket_counts_sum_to_total():
    rows = _lifecycle_rows()
    summary = _summary()
    assert len(rows) == 263
    counts = summary["bucket_counts"]
    assert set(counts) == {"OPEN_SCAN", "CLOSED_TOUCH", "CLOSED_VIOL",
                           "NEVER_ARMED", "DATA_GAP"}
    assert sum(counts.values()) == 263
    assert summary["total_completions"] == 263
    assert summary["unclassified_count"] == 0
    for r in rows:
        assert r["bucket"] in counts


# --------------------------------------------------------------------------- #
# 6. Artifact invariant — causal order (completion before close = hard fail)
# --------------------------------------------------------------------------- #
def test_no_causal_order_violations():
    rows = _lifecycle_rows()
    summary = _summary()
    assert summary["causal_order_violations"] == []
    for r in rows:
        assert int(r["d_completion_minus_close_bars"]) >= 0, (
            f"completion before structure close: {r['trigger_id']}")
        # Timestamps are ISO-8601 with a fixed offset: lexicographic order
        # is chronological order for identical formats.
        assert r["stage3_completion_ts"] >= r["structure_close_ts"], (
            f"completion before structure close: {r['trigger_id']}")
        if r["arm_ts"]:
            assert int(r["d_completion_minus_arm_bars"]) >= 0


# --------------------------------------------------------------------------- #
# 7. Locked windows — no section 5 / 23 / 24 widening in this audit
# --------------------------------------------------------------------------- #
def test_locked_windows_unchanged():
    from smc.config import locked_constants as lc
    from smc.triggers.trigger_expiry import poi_give_up_bars
    pack = _load_pack()
    assert pack.ltf.LA_M5_BARS == poi_give_up_bars() == lc.TRIGGER_A_EXPIRY == 20
    assert lc.TRIGGER_B_EXPIRY == 30
    assert lc.TRIGGER_F_EXPIRY == 1
    assert lc.M5_EXPIRY_BARS == 12
