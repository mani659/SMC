from datetime import datetime, timedelta, timezone

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.live.loop import LiveLoop


START = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


def _bar(timeframe, minutes_ago):
    return Candle(
        timestamp=START - timedelta(minutes=minutes_ago),
        open=100.0, high=101.0, low=99.0, close=100.5, timeframe=timeframe,
    )


class _Feed:
    def __init__(self):
        self.calls = []

    def on_m5_closed(self, bar, *, h4_closed, m15_closed):
        self.calls.append((bar, h4_closed, m15_closed))


class _Runner:
    runtime = object()


class _Connector:
    def __init__(self, rows):
        self.rows = rows

    def copy_rates(self, *_args):
        return self.rows


def test_dumb_mtf_loop_passes_only_completed_h4_and_m15_bars():
    feed = _Feed()
    h4_closed = _bar(Timeframe.H4, 4 * 60)
    h4_forming = _bar(Timeframe.H4, 0)
    m15_closed = _bar(Timeframe.M15, 15)
    m15_forming = _bar(Timeframe.M15, 0)

    def fetch(tf, _count):
        return {
            Timeframe.H4: [h4_closed, h4_forming],
            Timeframe.M15: [m15_closed, m15_forming],
        }[tf]

    loop = LiveLoop(
        connector=object(), runner=_Runner(), heartbeat=None,
        symbol="XAUUSD", timeframe=Timeframe.M5,
        htf_fetch=fetch, dumb_mtf_feed=feed,
    )
    execution = _bar(Timeframe.M5, 0)
    loop._drive_dumb_mtf(execution)

    assert loop.runtime is None
    assert loop.htf_timeframes == (Timeframe.H4, Timeframe.M15)
    assert feed.calls == [(execution, [h4_closed], m15_closed)]


def test_dumb_mtf_loop_drops_the_current_forming_m5_bar():
    def row(minutes):
        return {
            "time": int((START + timedelta(minutes=minutes)).timestamp()),
            "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
        }

    connector = _Connector([row(-10), row(-5), row(0)])
    loop = LiveLoop(
        connector=connector, runner=_Runner(), heartbeat=None,
        symbol="XAUUSD", timeframe=Timeframe.M5,
        dumb_mtf_feed=_Feed(),
    )

    assert loop._fetch_new_bars() == []  # anchors at the last completed bar
    connector.rows = [row(-10), row(-5), row(0), row(5)]
    new = loop._fetch_new_bars()

    assert [bar.timestamp for bar in new] == [START]
