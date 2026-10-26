"""F1 episode uniqueness — one geometric episode → one M8 POI.

Covers: same-bounds same-direction kind collapse (ob wins), same-bounds
opposite-direction collapse (deterministic winner), distinct zones
untouched, merge/arm path propagation without re-duplication.
"""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.poi.confluence_scorer import merge_overlapping
from smc.poi.models.m8_htf_demand_supply import collapse_episodes


def _z(bottom, top, direction=Direction.LONG, tf=Timeframe.D1):
    return Zone(bottom=bottom, top=top, direction=direction, timeframe=tf)


def test_same_bounds_same_direction_collapses_to_ob():
    out = collapse_episodes([
        ("ob", Direction.LONG, 10, _z(100.0, 101.0)),
        ("demand_supply", Direction.LONG, 10, _z(100.0, 101.0)),
    ])
    assert len(out) == 1
    kind, direction, start, zone = out[0]
    assert kind == "ob"  # kind priority ob > demand_supply
    assert direction is Direction.LONG
    assert (zone.bottom, zone.top) == (100.0, 101.0)


def test_same_bounds_opposite_directions_collapse_deterministically():
    out = collapse_episodes([
        ("demand_supply", Direction.SHORT, 12, _z(100.0, 101.0)),
        ("ob", Direction.LONG, 10, _z(100.0, 101.0)),
    ])
    assert len(out) == 1
    kind, direction, start, zone = out[0]
    # Kind priority first (ob beats demand_supply regardless of direction).
    assert (kind, direction) == ("ob", Direction.LONG)
    # Determinism: input order must not matter.
    out2 = collapse_episodes([
        ("ob", Direction.LONG, 10, _z(100.0, 101.0)),
        ("demand_supply", Direction.SHORT, 12, _z(100.0, 101.0)),
    ])
    assert [(k, d) for k, d, _, _ in out2] == [(k, d) for k, d, _, _ in out]


def test_same_kind_opposite_directions_long_wins_documented():
    # Arbitrary-but-deterministic final tiebreak (no strength signal exists
    # at emission): LONG before SHORT. Documented here, not tuned.
    out = collapse_episodes([
        ("demand_supply", Direction.SHORT, 9, _z(100.0, 101.0)),
        ("demand_supply", Direction.LONG, 11, _z(100.0, 101.0)),
    ])
    assert len(out) == 1
    assert out[0][0] == "demand_supply" and out[0][1] is Direction.LONG


def test_distinct_zones_all_survive_in_chronological_order():
    out = collapse_episodes([
        ("ob", Direction.SHORT, 20, _z(200.0, 201.0)),
        ("demand_supply", Direction.LONG, 5, _z(100.0, 101.0)),
        ("fvg", Direction.LONG, 12, _z(150.0, 150.5)),
    ])
    assert len(out) == 3
    assert [start for _, _, start, _ in out] == [5, 12, 20]


def test_fvg_loses_to_ob_and_ds_on_identical_bounds():
    out = collapse_episodes([
        ("fvg", Direction.LONG, 7, _z(100.0, 101.0)),
        ("demand_supply", Direction.LONG, 7, _z(100.0, 101.0)),
        ("ob", Direction.LONG, 7, _z(100.0, 101.0)),
    ])
    assert len(out) == 1 and out[0][0] == "ob"


def test_merge_does_not_reduplicate_collapsed_pois():
    a = POI(zone=_z(100.0, 101.0), models=[ModelType.M8], m8_kind="ob")
    b = POI(zone=_z(100.0, 101.0), models=[ModelType.M8],
            m8_kind="demand_supply")
    merged = merge_overlapping([a, b])
    assert len(merged) == 1
    assert "ob" in (merged[0].m8_kind or "")
    assert "demand_supply" in (merged[0].m8_kind or "")
    assert merged[0].models == [ModelType.M8]


def test_merge_preserves_m8_kind_with_other_models():
    a = POI(zone=_z(100.0, 101.0), models=[ModelType.M8], m8_kind="ob")
    b = POI(zone=_z(100.5, 101.5), models=[ModelType.M1])
    merged = merge_overlapping([a, b])
    assert len(merged) == 1
    assert merged[0].m8_kind == "ob"
    assert sorted(merged[0].models) == [ModelType.M1, ModelType.M8]


def test_merge_without_kind_stays_none():
    a = POI(zone=_z(100.0, 101.0), models=[ModelType.M1])
    b = POI(zone=_z(100.5, 101.5), models=[ModelType.M2])
    merged = merge_overlapping([a, b])
    assert len(merged) == 1
    assert merged[0].m8_kind is None
