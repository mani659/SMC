"""LEG 5b — ZoneDedup ↔ episode lifecycle (design R1–R8, Architect ACCEPT 2026-10-20).

Every test here pins a rule of ``06_RESEARCH/ZONE_DEDUP_LIFECYCLE_DESIGN.md``:

* **R1** ``register`` stores the owner ``poi.id`` beside the unchanged
  ``(direction, round(top,6), round(bottom,6))`` geometry; owner required.
* **R2** ``seen`` is owner-blind and byte-compatible with the pre-LEG-5
  inclusive-overlap rule; retired keys are removed, not flagged.
* **R3.1** death = no live obligation AND (VIOLATED OR past
  ``arm_bar + poi_give_up_bars()``).
* **R3.2** retirement happens in ``PipelineAdapter.prune_terminal_pois``
  (engine first, registry second); the engine's own retention is untouched.
* **R3.4** the adapter's retire handle IS the runtime's registry.
* **R6** retire is idempotent, misses counted, arm path never breaks.
* **Invariant (Gate C)** ≤ 1 concurrent arm per live key: arm → kill → re-arm.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from smc.backtest.pipeline_adapter import PipelineAdapter
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.orchestration.engine import PipelineEngine
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime, ZoneDedup
from smc.triggers.trigger_expiry import poi_give_up_bars

TF = Timeframe.M5
START = datetime(2025, 6, 2, 9, 0, tzinfo=timezone.utc)
ZONE_BOTTOM = 99.0
ZONE_TOP = 101.0


def _give_up() -> int:
    return poi_give_up_bars()


# ---------------------------------------------------------------------- #
# R1 — owner-attributed registration
# ---------------------------------------------------------------------- #
def test_register_requires_owner_id():
    dedup = ZoneDedup()
    zone = _zone()
    with pytest.raises(TypeError):
        dedup.register(zone)  # ownerless key could never be retired
    assert len(dedup) == 0 and dedup.retired_total == 0


def test_register_geometry_unchanged_and_owner_stored():
    dedup = ZoneDedup()
    zone = _zone()
    dedup.register(zone, owner_id="poi-000001")
    assert dedup.seen(zone) is True
    assert dedup.live_keys == 1
    # The stored geometry tuple keeps the pre-LEG-5 shape (owner is the 4th
    # element); rounding stays 6 dp.
    assert dedup._zones[0][:3] == ("Direction.LONG", ZONE_TOP, ZONE_BOTTOM)
    assert dedup._zones[0][3] == "poi-000001"


# ---------------------------------------------------------------------- #
# R2 — seen: owner-blind, retired keys removed (not flagged)
# ---------------------------------------------------------------------- #
def test_seen_is_owner_blind_and_overlap_rule_unchanged():
    dedup = ZoneDedup()
    dedup.register(_zone(), owner_id="poi-000001")
    for top, bottom, direction, expected in (
        (ZONE_TOP, ZONE_BOTTOM, Direction.LONG, True),    # identical
        (100.0, 95.0, Direction.LONG, True),              # overlap
        (ZONE_TOP, ZONE_BOTTOM, Direction.SHORT, False),  # other side
        (98.9, 95.0, Direction.LONG, False),              # disjoint
    ):
        assert dedup.seen(_zone(top, bottom, direction)) is expected


def test_retire_removes_key_so_seen_frees_the_zone():
    dedup = ZoneDedup()
    zone = _zone()
    dedup.register(zone, owner_id="poi-000001")
    assert dedup.retire("poi-000001") == 1
    assert dedup.seen(zone) is False          # removed, never flagged
    assert dedup.retired_total == 1
    # A NEW owner may claim the same geometry after retirement (re-arm).
    dedup.register(zone, owner_id="poi-000002")
    assert dedup.seen(zone) is True


# ---------------------------------------------------------------------- #
# R6 — idempotent retire, misses counted
# ---------------------------------------------------------------------- #
def test_retire_idempotent_and_misses_counted():
    dedup = ZoneDedup()
    dedup.register(_zone(), owner_id="poi-000001")
    assert dedup.retire("poi-000002") == 0
    assert dedup.retire_misses == 1           # unknown id: counted, not raised
    assert dedup.retire("poi-000001") == 1
    assert dedup.retire("poi-000001") == 0    # idempotent
    assert dedup.retire_misses == 2
    assert dedup.retired_total == 1


# ---------------------------------------------------------------------- #
# R3.4 — handle identity: adapter retires from the runtime's registry
# ---------------------------------------------------------------------- #
def test_runtime_binds_its_registry_onto_the_adapter():
    runtime = MultiTFProductRuntime()
    adapter = PipelineAdapter(PipelineEngine())
    series = {Timeframe.H4: [], Timeframe.H1: []}
    # Product mode without required HTF series raises loudly — but the
    # registry bind happens BEFORE that policy decision (design R3.4).
    from smc.orchestration.multi_tf_runtime import MissingHtfSeriesError

    with pytest.raises(MissingHtfSeriesError):
        runtime.run_batch(engine=adapter.engine, series_by_tf=series,
                          as_of=START, arm_bar=0, adapter=adapter)
    assert adapter._dedup_registry is runtime.dedup
    with pytest.raises(MissingHtfSeriesError):  # idempotent for the same handle
        runtime.run_batch(engine=adapter.engine, series_by_tf=series,
                          as_of=START, arm_bar=1, adapter=adapter)
    assert adapter._dedup_registry is runtime.dedup


def test_rebinding_a_different_handle_refused():
    adapter = PipelineAdapter(PipelineEngine())
    adapter.bind_dedup_registry(ZoneDedup())
    with pytest.raises(ValueError):
        adapter.bind_dedup_registry(ZoneDedup())


def test_unbound_adapter_retirement_is_a_noop():
    """R6: no handle → retirement no-ops; the bar loop is never broken."""
    engine = PipelineEngine()
    poi = _armed(engine, arm_bar=0)
    _violate(engine, poi)
    adapter = PipelineAdapter(engine)
    pruned = adapter.prune_terminal_pois(set(), bar_index=_give_up() + 1)
    assert pruned == [poi.id]                 # I4 engine release unchanged
    assert adapter._dedup_registry is None    # never raised, never crashed


# ---------------------------------------------------------------------- #
# R3.1/R3.2 — the death predicate at the per-bar prune step
# ---------------------------------------------------------------------- #
def test_violated_without_obligation_releases_key():
    engine = PipelineEngine()
    dedup = ZoneDedup()
    poi = _armed(engine, arm_bar=0)
    dedup.register(poi.zone, owner_id=poi.id)
    adapter = PipelineAdapter(engine)
    adapter.bind_dedup_registry(dedup)
    _violate(engine, poi)
    pruned = adapter.prune_terminal_pois(set(), bar_index=_give_up() + 5)
    assert pruned == [poi.id]                 # engine released it
    assert dedup.seen(poi.zone) is False      # registry followed same step
    assert dedup.retired_total == 1


def test_violated_with_open_position_keeps_key():
    """P1: a live obligation outranks death — the key must NOT retire."""
    engine = PipelineEngine()
    dedup = ZoneDedup()
    poi = _armed(engine, arm_bar=0)
    dedup.register(poi.zone, owner_id=poi.id)
    adapter = PipelineAdapter(engine)
    adapter.bind_dedup_registry(dedup)
    _violate(engine, poi)
    pruned = adapter.prune_terminal_pois({poi.id}, bar_index=_give_up() + 5)
    assert pruned == []                       # retained in the engine too
    assert dedup.seen(poi.zone) is True       # key stays while obligated


def test_inside_give_up_window_never_retires_while_fresh():
    """FRESH/TESTED inside the seek window stay live even with no obligation."""
    engine = PipelineEngine()
    dedup = ZoneDedup()
    poi = _armed(engine, arm_bar=0)
    dedup.register(poi.zone, owner_id=poi.id)
    adapter = PipelineAdapter(engine)
    adapter.bind_dedup_registry(dedup)
    adapter.prune_terminal_pois(set(), bar_index=_give_up() // 2)
    adapter.prune_terminal_pois(set(), bar_index=_give_up())  # boundary: not past
    assert dedup.seen(poi.zone) is True
    assert dedup.retired_total == 0


def test_fresh_past_give_up_releases_key():
    """A give-up-closed FRESH episode is product-dead (scan closed, no route)."""
    engine = PipelineEngine()
    dedup = ZoneDedup()
    poi = _armed(engine, arm_bar=0)
    dedup.register(poi.zone, owner_id=poi.id)
    adapter = PipelineAdapter(engine)
    adapter.bind_dedup_registry(dedup)
    adapter.prune_terminal_pois(set(), bar_index=_give_up() + 1)
    assert dedup.seen(poi.zone) is False
    assert poi in engine.tracked_pois()       # engine retention untouched (§1.1)
    assert dedup.retired_total == 1


def test_workflow_live_tested_episode_keeps_key():
    """An in-flight workflow is a live obligation even past the window."""
    engine = PipelineEngine()
    dedup = ZoneDedup()
    poi = _armed(engine, arm_bar=0)
    dedup.register(poi.zone, owner_id=poi.id)
    adapter = PipelineAdapter(engine)
    adapter.bind_dedup_registry(dedup)
    engine.state_machine.transition(poi, POIState.TESTED)
    adapter._workflows[poi.id] = object()
    adapter.prune_terminal_pois(set(), bar_index=_give_up() * 10)
    assert dedup.seen(poi.zone) is True       # obligation held


def test_retire_sent_bookkeeping_prevents_miss_spam():
    """R3.2: the two sources may touch one id; the re-send never re-counts."""
    engine = PipelineEngine()
    dedup = ZoneDedup()
    poi = _armed(engine, arm_bar=0)
    dedup.register(poi.zone, owner_id=poi.id)
    adapter = PipelineAdapter(engine)
    adapter.bind_dedup_registry(dedup)
    _violate(engine, poi)
    adapter.prune_terminal_pois(set(), bar_index=_give_up() + 5)
    # A later sweep over still-tracked POIs finds nothing new for this id
    # (it left tracking with the prune); misses stay at 0.
    adapter._retire_dead_keys([], set(), _give_up() + 6)
    assert dedup.retired_total == 1
    assert dedup.retire_misses == 0
    assert dedup.seen(poi.zone) is False


# ---------------------------------------------------------------------- #
# Gate C invariant — arm → kill → re-arm
# ---------------------------------------------------------------------- #
def test_arm_kill_re_arm_same_geometry_no_live_double_arm():
    """≤ 1 concurrent arm per live key: a second PASS on a LIVE episode is
    suppressed; after the key dies the SAME geometry may arm again."""
    engine = PipelineEngine()
    dedup = ZoneDedup()
    adapter = PipelineAdapter(engine)
    adapter.bind_dedup_registry(dedup)

    first = _armed(engine, arm_bar=0)
    dedup.register(first.zone, owner_id=first.id)
    assert dedup.seen(first.zone) is True     # overlapping PASS suppressed

    # Inside the window the key is live even with no obligation.
    adapter.prune_terminal_pois(set(), bar_index=_give_up() // 2)
    assert dedup.seen(first.zone) is True

    # The episode dies (VIOLATED, no obligation) → key released same step.
    _violate(engine, first)
    adapter.prune_terminal_pois(set(), bar_index=_give_up() + 1)
    assert dedup.seen(first.zone) is False

    second = _armed(engine, arm_bar=_give_up() + 2)   # same geometry, new POI
    dedup.register(second.zone, owner_id=second.id)
    assert dedup.seen(second.zone) is True
    assert len(dedup) == 1                    # one live key, one live episode


def test_register_after_retire_keeps_order_deterministic():
    dedup = ZoneDedup()
    dedup.register(_zone(10.0, 5.0), owner_id="poi-a")
    dedup.register(_zone(20.0, 15.0), owner_id="poi-b")
    assert dedup.retire("poi-a") == 1
    assert dedup._zones == [("Direction.LONG", 20.0, 15.0, "poi-b")]


# ---------------------------------------------------------------------- #
# helpers
# ---------------------------------------------------------------------- #
def _zone(top: float = ZONE_TOP, bottom: float = ZONE_BOTTOM,
          direction: Direction = Direction.LONG) -> Zone:
    return Zone(top=top, bottom=bottom, direction=direction, timeframe=Timeframe.H4)


def _armed(engine: PipelineEngine, arm_bar: int) -> POI:
    poi = POI(zone=_zone(), models=[ModelType.M1])
    poi.state = POIState.FRESH
    engine.arm_at(poi, arm_bar=arm_bar)
    return poi


def _violate(engine: PipelineEngine, poi: POI) -> None:
    """Drive the POI to §5 VIOLATED the way the state machine requires:
    a candle trading entirely BELOW the LONG zone without touching it."""
    bottom = poi.zone.bottom
    candle = Candle(
        timestamp=START,
        open=bottom - 3.0, high=bottom - 2.5, low=bottom - 4.0,
        close=bottom - 3.0, timeframe=TF,
    )
    assert engine.feed_bar(poi, candle) == POIState.VIOLATED.value
