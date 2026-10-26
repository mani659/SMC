from datetime import datetime, timedelta, timezone

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.zone import Zone
from smc.dumb.mtf_h4_feed import DumbMtfH4Feed, _H4Poi
from smc.dumb.mtf_paper_adapter import DumbMtfPaperAdapter


START = datetime(2026, 10, 25, tzinfo=timezone.utc)
ZONE = Zone(101.0, 100.0, Direction.LONG, Timeframe.H4)


class _Runner:
    def __init__(self):
        self.entries = []

    def set_pipeline_adapter(self, _adapter):
        pass

    def submit_entry(self, candidate):
        self.entries.append(candidate)


def _bar(index, *, low=101.5, high=102.0, close=101.5):
    return Candle(
        timestamp=START + timedelta(minutes=5 * index),
        open=101.5,
        high=high,
        low=low,
        close=close,
        timeframe=Timeframe.M5,
    )


def _feed():
    adapter = DumbMtfPaperAdapter()
    runner = _Runner()
    adapter.attach(runner)
    feed = DumbMtfH4Feed(adapter, symbol="XAUUSD")
    feed._h4_pois["h4-zone"] = _H4Poi("h4-zone", ZONE)
    return feed, adapter, runner


def test_primary_touch_without_sweep_never_queues_order():
    feed, adapter, runner = _feed()
    for index in range(15):  # provide ATR history and a plain touch at index 0
        feed.on_m5_closed(_bar(index), h4_closed=[])
        adapter.generate_candidates(None, index, None)

    assert runner.entries == []


def test_primary_uses_first_real_sweep_as_stop_anchor_then_confirms():
    feed, adapter, runner = _feed()
    for index in range(14):
        feed.on_m5_closed(_bar(index), h4_closed=[])
    # Wick below the demand-zone boundary and close back in: valid sweep.
    feed.on_m5_closed(_bar(14, low=99.8, high=100.7, close=100.4), h4_closed=[])
    feed.on_m5_closed(_bar(15, low=100.2, high=100.9, close=100.8), h4_closed=[])
    adapter.generate_candidates(None, 15, None)

    assert len(runner.entries) == 1
    assert runner.entries[0].sweep_level == 99.8
    assert runner.entries[0].trigger == "DUMB_MTF"


def test_sweep_bar_never_confirms_its_own_episode():
    feed, adapter, runner = _feed()
    for index in range(14):
        feed.on_m5_closed(_bar(index), h4_closed=[])
    # It is both an in-zone close above the midpoint and a valid sweep.
    feed.on_m5_closed(_bar(14, low=99.8, high=101.0, close=100.8), h4_closed=[])
    adapter.generate_candidates(None, 14, None)

    assert runner.entries == []
