"""POI KPI pack — pure helper tests (no MT5, no data load)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

import poi_kpi_pack as pack  # noqa: E402


def test_funnel_rows_flattens_stages():
    rows = pack.funnel_rows({
        "detected_raw_by_tf": {"H4": 10, "H1": 5},
        "merged_by_tf": {"H4": 7, "H1": 4},
        "passed_validation_by_tf": {"H4": 2, "H1": 1},
        "merged_pois": 11, "passed_validation": 3,
        "armed": 3, "routes": 2, "fills": 0,
    })
    by_stage = {r["stage"]: r["count"] for r in rows}
    assert by_stage["detected_raw_total"] == 15
    assert by_stage["merged_total"] == 11
    assert by_stage["passed_total"] == 3
    assert by_stage["armed"] == 3 and by_stage["routes"] == 2 and by_stage["fills"] == 0


def test_kind_label_uses_flowchart_vocabulary_and_invents_nothing():
    assert pack.kind_label({"m8_kind": "ob"}) == "ORDER BLOCK"
    assert pack.kind_label({"m8_kind": "fvg"}) == "FVG"
    assert pack.kind_label({"model_tags": "M8"}) == "M8 MODEL ZONE"
    assert pack.kind_label({"model_tags": "M1"}) == "DETECTOR M1"
    assert pack.kind_label({}) == "UNLABELED"
    # an unknown m8_kind must not be silently relabelled as a known kind
    assert pack.kind_label({"m8_kind": "mystery"}) == "UNLABELED"


def test_pillar_label_reads_like_the_flowchart():
    assert pack.pillar_label("PASS") == "PASS"
    assert pack.pillar_label("P2:FAIL") == "PILLAR 2 FAIL - DISPLACEMENT (FAIL)"
    assert pack.pillar_label("P5:SOFT").startswith("PILLAR 5")


def test_pillar_rows_histogram_never_invents_counts():
    rows = pack.pillar_rows([
        {"first_fail": "PASS"}, {"first_fail": "PASS"}, {"first_fail": "P2:FAIL"},
    ])
    assert rows[0]["pillar"] == "PASS" and rows[0]["count"] == 2
    assert rows[0]["pct"] == round(200 / 3, 4)
    assert {r["pillar"] for r in rows} == {"PASS", "P2:FAIL"}


def _level(side, price, family="session", period_id="ASIA"):
    return SimpleNamespace(side=SimpleNamespace(value=side), price=price,
                           family=SimpleNamespace(value=family), period_id=period_id)


def test_best_level_prefers_zone_overlap_then_distance():
    levels = [_level("bsl", 2400.0), _level("bsl", 2405.0), _level("ssl", 2390.0)]
    best, distance = pack.best_level("bsl", 2395.0, 2400.5, levels)
    assert best.price == 2400.0 and distance == 0.0
    best, distance = pack.best_level("bsl", 2401.0, 2402.0, levels)
    assert best.price == 2400.0 and distance == 1.0
    best, distance = pack.best_level("ssl", 2401.0, 2402.0, levels)
    assert best.price == 2390.0 and distance == 11.0
    assert pack.best_level("ssl", 2401.0, 2402.0, [_level("bsl", 2400.0)]) == (None, None)


def test_link_status_is_never_forced():
    assert pack.link_status(None, None, []) == "UNKNOWN"
    assert pack.link_status(_level("bsl", 2400.0), 0.0, []) == "NO"
    assert pack.link_status(_level("bsl", 2400.0), 0.0, ["2026-03-02T12:00Z"]) == "YES"
