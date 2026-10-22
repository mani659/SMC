"""Passed -> armed attribution study — focused pure-helper tests (research).

Locks the frozen helpers of
``06_RESEARCH/scripts/passed_to_armed_study.py``:

* the overlap geometry used to decide whether a dedup match is the SAME
  episode (coverage of the PASS zone by its blocker, identical bounds,
  Jaccard);
* the mutual exclusivity + precedence of the disposition buckets (the arm
  loop's own order: armed -> arm error -> dedup -> tracked -> gap);
* the episode clustering partition, cross-checked against the product's own
  ``ZoneDedup`` predicate so the study can never drift from the gate it
  measures;
* the exact-geometry census (re-emission counts);
* the pre-registered interpretation branches, including the low-n guard, the
  wiring-hole guard, and the same-episode vs distinct-structure split.

No series loading, no runner, no MT5, no threshold, no expectancy assertion.
``LOGIC_CHANGED: NO``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "passed_to_armed_study.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "passed_to_armed_study", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["passed_to_armed_study"] = module
    spec.loader.exec_module(module)
    return module


pa = _load_pack()


def _event(seq: int, direction: str, low: float, high: float,
           *, disposition: str = pa.BUCKET_ARMED,
           detection_tf: str = "H1", blocker: dict | None = None) -> dict:
    return {
        "seq": seq,
        "batch_idx": seq + 1,
        "as_of": None,
        "arm_bar": seq,
        "detection_tf": detection_tf,
        "zone_tf": detection_tf,
        "poi_id": f"poi-{seq:06d}",
        "direction": direction,
        "zone_low": low,
        "zone_high": high,
        "models": ["M8"],
        "disposition": disposition,
        "blocker": blocker,
    }


# ------------------------------------------------------------------ #
# Overlap geometry
# ------------------------------------------------------------------ #
def test_overlap_metrics_full_coverage_is_same_episode():
    geo = pa.overlap_metrics(100.0, 110.0, 100.0, 110.0)
    assert geo["coverage"] == pytest.approx(1.0)
    assert geo["blocker_coverage"] == pytest.approx(1.0)
    assert geo["jaccard"] == pytest.approx(1.0)
    assert geo["identical_bounds"] is True


def test_overlap_metrics_nested_pass_zone_is_fully_covered():
    # PASS zone sits inside a wider already-armed zone -> 1.0 coverage
    geo = pa.overlap_metrics(104.0, 106.0, 100.0, 110.0)
    assert geo["coverage"] == pytest.approx(1.0)
    assert geo["blocker_coverage"] == pytest.approx(0.2)
    assert geo["identical_bounds"] is False


def test_overlap_metrics_shallow_touch_low_coverage():
    # 1% of the PASS zone overlaps the blocker: folded in, but barely
    geo = pa.overlap_metrics(100.0, 200.0, 199.0, 260.0)
    assert geo["coverage"] == pytest.approx(0.01)
    assert geo["identical_bounds"] is False


def test_overlap_metrics_no_overlap_never_negative():
    geo = pa.overlap_metrics(100.0, 110.0, 120.0, 130.0)
    assert geo["overlap_abs"] == 0.0
    assert geo["coverage"] == 0.0
    assert geo["jaccard"] == 0.0


def test_overlap_metrics_degenerate_zone_is_zero_not_crash():
    geo = pa.overlap_metrics(100.0, 100.0, 95.0, 105.0)
    assert geo["coverage"] == 0.0


# ------------------------------------------------------------------ #
# Disposition precedence / exclusivity
# ------------------------------------------------------------------ #
def test_classify_event_arm_wins():
    decision = {"armed": True, "dedup": True, "tracked": True,
                "episode_calls": 1, "dedup_calls": 0, "arm_error": None}
    assert pa.classify_event(_event(1, "LONG", 1.0, 2.0), decision)[0] == \
        pa.BUCKET_ARMED


def test_classify_event_arm_error_is_skip_other():
    decision = {"armed": False, "dedup": False, "tracked": False,
                "episode_calls": 1, "dedup_calls": 0,
                "arm_error": "ValueError: arm_at expects a CREATED or FRESH POI"}
    bucket, note = pa.classify_event(_event(1, "LONG", 1.0, 2.0), decision)
    assert bucket == pa.BUCKET_OTHER
    assert "ValueError" in note


def test_classify_event_dedup_and_tracked():
    dedup = {"armed": False, "dedup": True, "tracked": False,
             "episode_calls": 1, "dedup_calls": 1, "arm_error": None}
    assert pa.classify_event(_event(1, "LONG", 1.0, 2.0), dedup)[0] == \
        pa.BUCKET_DEDUP
    tracked = {"armed": False, "dedup": None, "tracked": True,
               "episode_calls": 1, "dedup_calls": 0, "arm_error": None}
    assert pa.classify_event(_event(1, "LONG", 1.0, 2.0), tracked)[0] == \
        pa.BUCKET_TRACKED


def test_classify_event_missing_decision_is_data_gap():
    assert pa.classify_event(_event(1, "LONG", 1.0, 2.0), None)[0] == \
        pa.BUCKET_GAP


def test_classify_event_reached_no_gate_is_data_gap():
    decision = {"armed": False, "dedup": None, "tracked": False,
                "episode_calls": 1, "dedup_calls": 0, "arm_error": None}
    bucket, note = pa.classify_event(_event(1, "LONG", 1.0, 2.0), decision)
    assert bucket == pa.BUCKET_GAP
    assert "no gate" in note


# ------------------------------------------------------------------ #
# Episode clustering vs the product's own dedup predicate
# ------------------------------------------------------------------ #
def test_cluster_events_matches_zonededup_partition():
    from smc.core.enums import Direction
    from smc.orchestration.multi_tf_runtime import ZoneDedup

    class _Zone:
        def __init__(self, direction, top, bottom):
            self.direction = direction
            self.top = top
            self.bottom = bottom

    zones = [
        (Direction.LONG, 110.0, 100.0),
        (Direction.LONG, 108.0, 102.0),    # nested -> same episode
        (Direction.SHORT, 110.0, 100.0),   # other direction -> new episode
        (Direction.LONG, 205.0, 200.0),    # disjoint -> new episode
        (Direction.LONG, 203.0, 201.0),    # overlaps the previous LONG
        (Direction.LONG, 100.5, 99.0),     # overlaps the FIRST long -> same
    ]
    events = [
        _event(i, zone[0].name, zone[2], zone[1], disposition=pa.BUCKET_DEDUP)
        for i, zone in enumerate(zones)
    ]
    clusters = pa.cluster_events(events)
    assert len(clusters) == 3

    seen = ZoneDedup()
    expected = []
    for _direction, top, bottom in zones:
        zone = _Zone(_direction, top, bottom)
        expected.append(1 if seen.seen(zone) else 0)
        if not expected[-1]:
            seen.register(zone, owner_id=f"poi-{len(expected):06d}")
    sizes = [len(c["events"]) for c in clusters]
    assert sizes[0] == 3                    # 100-110, 102-108, 99-100.5
    assert sizes[1] == 1                    # short
    assert sizes[2] == 2                    # 200-205, 201-203
    assert expected == [0, 1, 0, 0, 1, 1]


def test_cluster_events_counts_armed_members():
    events = [
        _event(0, "LONG", 100.0, 110.0),
        _event(1, "LONG", 101.0, 109.0, disposition=pa.BUCKET_DEDUP),
        _event(2, "LONG", 200.0, 210.0, disposition=pa.BUCKET_DEDUP),
    ]
    clusters = pa.cluster_events(events)
    assert len(clusters) == 2
    assert clusters[0]["armed"] == 1
    assert clusters[0]["deduped"] == 1
    assert clusters[1]["armed"] == 0


def test_cluster_events_records_detection_tfs():
    events = [
        _event(0, "LONG", 100.0, 110.0, detection_tf="H4"),
        _event(1, "LONG", 101.0, 109.0, detection_tf="H1",
               disposition=pa.BUCKET_DEDUP),
    ]
    clusters = pa.cluster_events(events)
    assert clusters[0]["detection_tfs"] == ["H4", "H1"]


# ------------------------------------------------------------------ #
# Geometry census + histogram
# ------------------------------------------------------------------ #
def test_geometry_census_counts_reemissions():
    events = [
        _event(0, "LONG", 100.0, 110.0),
        _event(1, "LONG", 100.0, 110.0, disposition=pa.BUCKET_DEDUP),
        _event(2, "SHORT", 100.0, 110.0, disposition=pa.BUCKET_DEDUP),
    ]
    census = pa.geometry_census(events)
    assert census["n_events"] == 3
    assert census["n_distinct_geometries"] == 2
    assert census["n_distinct_geometries_armed"] == 1
    assert census["n_distinct_geometries_never_armed"] == 1
    assert census["reemission_per_geometry_max"] == 2


def test_disposition_counts_keeps_every_bucket():
    events = [
        _event(0, "LONG", 100.0, 110.0),
        _event(1, "LONG", 100.0, 110.0, disposition=pa.BUCKET_DEDUP),
    ]
    counts = pa.disposition_counts(events)
    assert counts["_total"] == 2
    for bucket in pa.BUCKETS:
        assert bucket in counts
    assert counts[pa.BUCKET_ARMED]["count"] == 1
    assert counts[pa.BUCKET_DEDUP]["pct_of_passes"] == pytest.approx(50.0)
    assert counts[pa.BUCKET_FRESHNESS]["code_impossible_today"] is True
    assert counts[pa.BUCKET_DEDUP]["code_impossible_today"] is False


# ------------------------------------------------------------------ #
# Interpretation (pre-registered branches)
# ------------------------------------------------------------------ #
def _counts(**shares) -> dict:
    """Build a disposition blob from bucket -> percent (must sum to 100)."""
    counts = {b: {"count": 0, "pct_of_passes": 0.0,
                  "code_impossible_today": b in pa.CODE_IMPOSSIBLE_BUCKETS}
              for b in pa.BUCKETS}
    counts["_total"] = 1000
    for bucket, pct in shares.items():
        counts[bucket]["pct_of_passes"] = float(pct)
        counts[bucket]["count"] = int(round(pct * 10))
    return counts


def test_interpret_low_n_guard():
    label, _ = pa.interpret(_counts(**{pa.BUCKET_ARMED: 100.0}),
                            pa.MIN_PASSES_FOR_LABEL - 1, {})
    assert label == "INCONCLUSIVE_LOW_N"


def test_interpret_wiring_hole_is_mixed_not_hidden():
    counts = _counts(**{pa.BUCKET_DEDUP: 90.0, pa.BUCKET_GAP: 10.0})
    label, why = pa.interpret(counts, 1000, {"coverage_median": 1.0})
    assert label == "MIXED"
    assert "wiring" in why


def test_interpret_dedup_dominated_when_same_episode():
    counts = _counts(**{pa.BUCKET_DEDUP: 96.0, pa.BUCKET_ARMED: 4.0})
    label, why = pa.interpret(counts, 1000, {
        "coverage_median": 0.9, "pct_identical_bounds": 30.0})
    assert label == "DEDUP_DOMINATED"
    assert "SAME episode" in why


def test_interpret_dedup_loose_overlap_is_bottleneck():
    counts = _counts(**{pa.BUCKET_DEDUP: 96.0, pa.BUCKET_ARMED: 4.0})
    label, _ = pa.interpret(counts, 1000, {"coverage_median": 0.2})
    assert label == "ARM_FILTER_IS_BOTTLENECK"


def test_interpret_freshness_dominated():
    counts = _counts(**{pa.BUCKET_FRESHNESS: 80.0, pa.BUCKET_ARMED: 20.0})
    label, _ = pa.interpret(counts, 1000, {})
    assert label == "FRESHNESS_DOMINATED"


def test_interpret_healthy_when_no_bucket_dominates():
    counts = _counts(**{pa.BUCKET_ARMED: 40.0, pa.BUCKET_DEDUP: 30.0,
                        pa.BUCKET_TRACKED: 30.0})
    label, _ = pa.interpret(counts, 1000, {})
    assert label == "ARM_PATH_HEALTHY"


def test_interpret_labels_are_the_preregistered_set():
    text = _PACK_PATH.read_text(encoding="utf-8")
    for label in ("ARM_PATH_HEALTHY", "ARM_FILTER_IS_BOTTLENECK",
                  "DEDUP_DOMINATED", "FRESHNESS_DOMINATED", "MIXED",
                  "INCONCLUSIVE_LOW_N"):
        assert label in text


# ------------------------------------------------------------------ #
# Autopsy + time structure
# ------------------------------------------------------------------ #
def test_select_autopsy_is_deterministic_and_non_armed():
    events = [
        _event(i, "LONG", 100.0 + i, 110.0 + i,
               disposition=pa.BUCKET_DEDUP,
               blocker={"coverage": (i % 10) / 10.0})
        for i in range(40)
    ]
    events.append(_event(99, "LONG", 1.0, 2.0))
    first = pa.select_autopsy(events, target=20)
    second = pa.select_autopsy(events, target=20)
    assert [e["seq"] for e in first] == [e["seq"] for e in second]
    assert first
    assert all(e["disposition"] != pa.BUCKET_ARMED for e in first)
    assert len(first) <= 20


def test_select_autopsy_empty_when_all_armed():
    assert pa.select_autopsy([_event(0, "LONG", 1.0, 2.0)]) == []


def test_time_structure_buckets_by_month():
    from datetime import datetime, timezone

    events = [
        dict(_event(0, "LONG", 100.0, 110.0),
             as_of=datetime(2025, 6, 2, tzinfo=timezone.utc)),
        dict(_event(1, "LONG", 100.0, 110.0,
                    disposition=pa.BUCKET_DEDUP),
             as_of=datetime(2025, 6, 9, tzinfo=timezone.utc)),
        dict(_event(2, "LONG", 200.0, 210.0),
             as_of=datetime(2025, 7, 4, tzinfo=timezone.utc)),
    ]
    rows = pa.time_structure(events, pa.cluster_events(events))
    assert [r["month"] for r in rows] == ["2025-06", "2025-07"]
    assert rows[0]["passes"] == 2
    assert rows[0]["armed"] == 1
    assert rows[0]["dedup"] == 1
    assert rows[0]["clusters_first_seen"] == 1
    assert rows[1]["clusters_first_seen"] == 1
