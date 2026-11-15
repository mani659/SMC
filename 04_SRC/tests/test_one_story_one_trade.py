"""ONE STORY → ONE PLAN → AT MOST ONE LIVE ORDER (locked 2026-11-15).

Locks the normative same-story definition and its single enforcement seam:
``PipelineAdapter`` intake (menu winner queue + seek route mint), before the
runner's risk gate. Measured motivation: PFE-2 menu windows produced 27 fills
across only 8 distinct plans (Oct 14 fills → 3 plans; Jun 11 → 4; Sep 2 → 1),
all same direction, same trigger F, byte-identical entry/SL/TP, overlapping
zones, different ``poi_id``.

Non-goals asserted here: different direction, different trigger, a
non-overlapping zone, or a different TP still allow two candidates.
"""

from smc.backtest.pipeline_adapter import PipelineAdapter
from smc.backtest.runner import CandidateEntry
from smc.core.enums import Direction, TriggerType
from smc.risk.story_guard import same_story, story_key, zones_overlap


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class _StubEngine:
    """Only the attributes the adapter touches at construction/binding."""

    state_machine = None


class _FakeRunner:
    def __init__(self) -> None:
        self.submitted: list = []
        self.live: list = []
        self.adapter = None

    def set_pipeline_adapter(self, adapter) -> None:
        self.adapter = adapter

    def submit_entry(self, candidate) -> None:
        self.submitted.append(candidate)

    def story_live_plans(self) -> list:
        return list(self.live)


def _candidate(*, poi_id="poi-1", direction=Direction.LONG, trigger=TriggerType.F_BOS_OB,
               entry=3341.605, sl=3340.738578590661, tp=3341.948,
               zone_low=3339.548, zone_high=3364.948):
    return CandidateEntry(
        direction=direction,
        entry_price=entry,
        sl_price=sl,
        tp_price=tp,
        poi_id=poi_id,
        trigger=trigger,
        zone_low=zone_low,
        zone_high=zone_high,
    )


def _adapter():
    runner = _FakeRunner()
    adapter = PipelineAdapter(engine=_StubEngine())
    adapter.attach(runner)
    return adapter, runner


# --------------------------------------------------------------------------- #
# The normative definition
# --------------------------------------------------------------------------- #
def test_identical_plan_inside_overlapping_zone_is_the_same_story():
    a = _candidate(poi_id="poi-a")
    b = _candidate(poi_id="poi-b", zone_low=3344.755, zone_high=3372.445)
    assert same_story(story_key(a), story_key(b)) is True


def test_same_plan_outside_the_zone_is_not_the_same_story():
    a = _candidate()
    b = _candidate(poi_id="poi-b", zone_low=3390.0, zone_high=3400.0)
    assert same_story(story_key(a), story_key(b)) is False


def test_different_trigger_is_not_the_same_story():
    a = _candidate()
    b = _candidate(poi_id="poi-b", trigger=TriggerType.A_CHOCH)
    assert same_story(story_key(a), story_key(b)) is False


def test_different_direction_is_not_the_same_story():
    a = _candidate()
    b = _candidate(poi_id="poi-b", direction=Direction.SHORT)
    assert same_story(story_key(a), story_key(b)) is False


def test_different_tp_is_not_the_same_story():
    a = _candidate()
    b = _candidate(poi_id="poi-b", tp=3342.5)
    assert same_story(story_key(a), story_key(b)) is False


def test_unknown_zone_is_never_collapsed():
    a = _candidate()
    b = _candidate(poi_id="poi-b", zone_low=None, zone_high=None)
    assert same_story(story_key(a), story_key(b)) is False


def test_overlap_helper_is_the_zone_dedup_rule():
    assert zones_overlap(10.0, 5.0, 7.0, 6.0) is True
    assert zones_overlap(10.0, 5.0, 12.0, 11.0) is False
    # touching edges count as overlap (inclusive), as ZoneDedup.seen does
    assert zones_overlap(10.0, 5.0, 11.0, 10.0) is True


# --------------------------------------------------------------------------- #
# The enforcement seam (adapter intake)
# --------------------------------------------------------------------------- #
def test_menu_spray_collapses_to_one_order():
    adapter, runner = _adapter()
    winners = [
        _candidate(poi_id=f"poi-{i}") for i in range(7)  # the Oct shape: 7 ids
    ]
    for candidate in winners:
        adapter.queue_menu_candidate(candidate)

    assert len(runner.submitted) == 1
    assert adapter.story_counters()["duplicate_story_menu"] == 6
    # the losing POIs are retired, so they can never re-propose the plan
    assert all(pid in adapter._menu_claimed_pois for pid in
               [f"poi-{i}" for i in range(1, 7)])


def test_different_zone_and_direction_still_allow_two_orders():
    adapter, runner = _adapter()
    adapter.queue_menu_candidate(_candidate(poi_id="poi-1"))
    adapter.queue_menu_candidate(_candidate(poi_id="poi-2",
                                            zone_low=3390.0, zone_high=3400.0))
    adapter.queue_menu_candidate(_candidate(poi_id="poi-3",
                                            direction=Direction.SHORT))
    assert len(runner.submitted) == 3
    assert adapter.story_counters()["duplicate_story_dropped"] == 0


def test_duplicate_is_dropped_while_the_plan_is_live_and_allowed_after_close():
    adapter, runner = _adapter()
    first = _candidate(poi_id="poi-1")
    adapter.queue_menu_candidate(first)
    adapter.on_candidate_accepted(first)  # a real placement seals the claim
    assert len(runner.submitted) == 1

    # the plan is live: the identical plan may not place
    runner.live = [first]
    adapter.queue_menu_candidate(_candidate(poi_id="poi-2"))
    assert len(runner.submitted) == 1

    # the trade resolved (no live obligation): the claim is pruned, so a new
    # story with the same geometry is allowed again — "wait for another story"
    runner.live = []
    adapter.queue_menu_candidate(_candidate(poi_id="poi-3"))
    assert len(runner.submitted) == 2
    assert adapter.story_counters()["stories_pruned"] >= 1


def test_seek_route_duplicate_burns_the_losing_poi_shot():
    adapter, runner = _adapter()
    adapter.queue_menu_candidate(_candidate(poi_id="poi-menu"))  # story claimed
    duplicate = _candidate(poi_id="poi-seek")

    assert adapter._duplicate_story(duplicate, source="seek") == "poi-menu"
    adapter._drop_duplicate_poi(duplicate)

    assert "poi-seek" in adapter._routed
    assert adapter.story_counters()["duplicate_story_seek"] == 1
    assert len(runner.submitted) == 1
