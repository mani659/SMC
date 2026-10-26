from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.core.zone import Zone
from smc.dumb.mtf import DumbMtfEpisodeKey
from smc.dumb.mtf_paper_adapter import DumbMtfPaperAdapter, DumbMtfRoute


class _Runner:
    def __init__(self):
        self.adapter = None
        self.entries = []

    def set_pipeline_adapter(self, adapter):
        self.adapter = adapter

    def submit_entry(self, candidate):
        self.entries.append(candidate)


ZONE = Zone(101.0, 100.0, Direction.LONG, Timeframe.H4)


def _key():
    return DumbMtfEpisodeKey("XAUUSD", "LONG", Timeframe.H4, "zone-a", "touch-a")


def _route(episode_id, route_id="m5-a", timeframe=Timeframe.M5):
    return DumbMtfRoute(
        episode_id, timeframe, route_id, ZONE,
        entry_price=100.6, sweep_extreme=99.8, atr=1.0,
        completed_at=datetime(2026, 10, 25, 12, tzinfo=timezone.utc),
    )


def test_paper_adapter_submits_one_winner_through_existing_protocol():
    adapter = DumbMtfPaperAdapter()
    runner = _Runner()
    adapter.attach(runner)
    episode_id = adapter.start_primary(_key(), clock_bar=0)

    assert adapter.record_confirmation(_route(episode_id)) is True
    adapter.generate_candidates(None, 0, None)

    assert runner.adapter is adapter
    assert len(runner.entries) == 1
    candidate = runner.entries[0]
    assert candidate.route_id == "DUMB_MTF|m5-a"
    assert candidate.poi_id == episode_id
    assert candidate.entry_price == 100.6
    assert candidate.zone_low == 100.0
    assert candidate.zone_high == 101.0


def test_losing_second_confirmation_never_submits_a_second_candidate():
    adapter = DumbMtfPaperAdapter()
    runner = _Runner()
    adapter.attach(runner)
    episode_id = adapter.start_primary(_key(), clock_bar=0)

    assert adapter.record_confirmation(_route(episode_id, "first")) is True
    assert adapter.record_confirmation(_route(episode_id, "second")) is False
    adapter.generate_candidates(None, 0, None)

    assert [entry.route_id for entry in runner.entries] == ["DUMB_MTF|first"]


def test_fallback_route_requires_primary_expiry_and_boundary_sweep():
    adapter = DumbMtfPaperAdapter()
    episode_id = adapter.start_primary(_key(), clock_bar=0)
    adapter.advance_clock(Timeframe.M5, 7)

    assert adapter.record_confirmation(_route(episode_id)) is False
    adapter.record_boundary_sweep(episode_id, clock_bar=7)
    assert adapter.record_confirmation(_route(episode_id)) is True
from datetime import datetime, timezone



def test_same_instant_confirmation_tie_prefers_finer_timeframe():
    adapter = DumbMtfPaperAdapter()
    episode_id = adapter.start_primary(_key(), clock_bar=0)

    winners = adapter.record_confirmations(
        [
            _route(episode_id, "m15", Timeframe.M15),
            _route(episode_id, "m5", Timeframe.M5),
        ]
    )

    assert winners == ["m5"]
    assert adapter.machine.get(episode_id).winner_route_id == "m5"
