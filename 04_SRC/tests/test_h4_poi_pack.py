"""H4 POI confirmation pack smoke — identification-only assertions.

Covers: H4 synthetic M8 emission stays origin-tight with one row per
geometric episode (no duals/direction conflicts), the pack's plain-tag
contract has no D1 leakage, and pack event ids are geometry-derived
(POI.id is uuid4 → run-random; ids must never come from it).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from smc.config.timeframe import Timeframe
from smc.core.poi import POI
from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "h4_poi_confirmation.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location("h4_poi_confirmation", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["h4_poi_confirmation"] = module
    spec.loader.exec_module(module)
    return module


def test_h4_synthetic_emission_origin_tight_no_duals(candle_factory):
    rows = [(200.0 + 0.05 * i, 200.1 + 0.05 * i, 199.9 + 0.05 * i,
             200.05 + 0.05 * i) for i in range(14)]
    rows.append((200.7, 201.2, 200.6, 201.0))
    rows.append((201.0, 202.0, 199.4, 199.6))
    rows.append((199.6, 199.9, 199.0, 199.2))
    rows.append((199.2, 199.5, 198.8, 199.0))
    h4 = candle_factory(rows, timeframe=Timeframe.H4)
    model = M8HtfDemandSupply(Timeframe.H4, htf_candles={Timeframe.H4: h4})
    emitted = list(model._zones(h4, Timeframe.H4))
    assert emitted, "H4 emission produced no zones"
    seen: dict = {}
    for kind, direction, start, zone in emitted:
        if kind in ("ob", "demand_supply"):
            origin = h4[start]
            assert (zone.bottom, zone.top) == (origin.low, origin.high), kind
        key = (round(zone.bottom, 3), round(zone.top, 3))
        assert key not in seen, f"dual episode on H4: {key}"
        seen[key] = direction.name if hasattr(direction, "name") else str(direction)


def test_h4_plain_tags_have_no_d1_leakage():
    pack = _load_pack()
    assert set(pack.PLAIN_TAG) == {("ob", None), ("demand_supply", "LONG"),
                                  ("demand_supply", "SHORT"), ("fvg", None)}
    for tag in pack.PLAIN_TAG.values():
        assert tag.endswith("(H4)"), tag
        assert "(D1)" not in tag and "(M5)" not in tag, tag


def test_pack_event_ids_are_geometry_stable_not_uuid():
    pack = _load_pack()
    a = pack._eid("merged", "LONG", "4150.075", "4197.595", "2025-07-01T00:00:00+00:00")
    b = pack._eid("merged", "LONG", "4150.075", "4197.595", "2025-07-01T00:00:00+00:00")
    assert a == b  # same geometry → same id across runs
    c = pack._eid("merged", "SHORT", "4150.075", "4197.595", "2025-07-01T00:00:00+00:00")
    assert a != c  # direction participates in identity
    # Document why geometry-derived: POI ids are uuid4 and change every run.
    assert POI(zone=_dummy_zone()).id != POI(zone=_dummy_zone()).id


def _dummy_zone():
    from smc.core.enums import Direction
    from smc.core.zone import Zone
    return Zone(bottom=1.0, top=2.0, direction=Direction.LONG,
                timeframe=Timeframe.H4)


def test_h4_window_filter_keeps_only_exec_range_endpoints():
    pack = _load_pack()
    from datetime import datetime, timezone
    ends = [datetime(2025, 5, 1, tzinfo=timezone.utc),
            datetime(2025, 6, 1, tzinfo=timezone.utc),
            datetime(2025, 8, 1, tzinfo=timezone.utc)]
    kept = [e for e in ends if e >= pack.EXEC_START]
    assert kept == ends[1:]  # pre-exec endpoint windows are excluded
