"""Phase 7 — live readiness tests (heartbeat + watchdog contract + live loop).

The MQL5 EA cannot run in pytest, so the watchdog DECISION is specified and
tested in Python (``smc.live.heartbeat.evaluate_watchdog``) and the EA is a
thin implementation of exactly that decision; the loop tests drive the REAL
stack (PipelineEngine + PipelineAdapter + PaperRunner + DetectionDriver)
over a scriptable fake connector.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from smc.backtest.pipeline_adapter import PipelineAdapter
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.execution.order_manager import OrderManager
from smc.execution.position_manager import PositionManager
from smc.execution.session_filter import Session
from smc.live.config import LiveConfig, live_config_from_dict
from smc.live.heartbeat import (
    HeartbeatPublisher,
    evaluate_watchdog,
    is_stale,
    read_heartbeat,
)
from smc.live.loop import LiveLoop
from smc.orchestration.detection_driver import DetectionDriver
from smc.orchestration.engine import PipelineEngine
from smc.paper.runner import PaperConfig, PaperRunner
from smc.risk.risk_engine import RiskEngine

TF = Timeframe.M5
START = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)  # Thursday, London
SESSIONS = (Session.LONDON, Session.NEW_YORK)
CALM = (100.4, 100.6, 100.3, 100.5)


class FakeClock:
    """Deterministic datetime source for the heartbeat publisher."""

    def __init__(self, start: datetime) -> None:
        self.t = start

    def __call__(self) -> datetime:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += timedelta(seconds=seconds)


def _bars(rows, start=START, step_minutes=5):
    step = timedelta(minutes=step_minutes)
    return [
        Candle(
            timestamp=start + i * step,
            open=o, high=h, low=l, close=c, timeframe=TF,
        )
        for i, (o, h, l, c) in enumerate(rows)
    ]


# ---------------------------------------------------------------------- #
# Heartbeat file format + freshness (fail-closed)
# ---------------------------------------------------------------------- #
def test_heartbeat_roundtrip_and_freshness(tmp_path):
    clock = FakeClock(START)
    path = tmp_path / "hb.txt"
    pub = HeartbeatPublisher(path, now=clock)
    pub.publish()

    record = read_heartbeat(path)
    assert record is not None and record.sequence == 1
    assert record.state == "running"
    assert record.unix_ts == int(START.timestamp())

    # Fresh within the timeout; stale past it.
    assert is_stale(record, clock().timestamp() + 1.0, 5.0) is False
    assert is_stale(record, clock().timestamp() + 6.0, 5.0) is True


def test_heartbeat_missing_or_garbage_is_stale_fail_closed(tmp_path):
    # Missing file → unreadable → stale (a dead Python cannot write).
    assert read_heartbeat(tmp_path / "nope.txt") is None
    assert is_stale(None, 1000.0, 5.0) is True

    # Garbage / truncated content → unreadable → stale.
    garbage = tmp_path / "garbage.txt"
    garbage.write_text("not a heartbeat at all\n", encoding="ascii")
    assert read_heartbeat(garbage) is None
    assert is_stale(read_heartbeat(garbage), 1000.0, 5.0) is True

    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="ascii")
    assert read_heartbeat(empty) is None


def test_heartbeat_sequence_and_clean_shutdown_marker(tmp_path):
    clock = FakeClock(START)
    pub = HeartbeatPublisher(tmp_path / "hb.txt", now=clock)
    pub.publish()
    pub.publish()
    assert read_heartbeat(tmp_path / "hb.txt").sequence == 2

    pub.publish_shutdown()
    record = read_heartbeat(tmp_path / "hb.txt")
    assert record.state == "shutdown"
    assert record.sequence == 3


def test_heartbeat_publisher_respects_interval(tmp_path):
    clock = FakeClock(START)
    pub = HeartbeatPublisher(tmp_path / "hb.txt", interval_seconds=1.0, now=clock)
    assert pub.maybe_publish() is True        # first write
    clock.advance(0.5)
    assert pub.maybe_publish() is False       # interval not elapsed
    clock.advance(0.6)
    assert pub.maybe_publish() is True        # 1.1s since last write
    assert pub.sequence == 2


# ---------------------------------------------------------------------- #
# Watchdog decision — the spec the MQL5 EA implements
# ---------------------------------------------------------------------- #
def test_watchdog_decision_healthy_no_action_stale_emergency(tmp_path):
    clock = FakeClock(START)
    path = tmp_path / "hb.txt"
    HeartbeatPublisher(path, now=clock).publish()
    now = clock().timestamp()

    assert evaluate_watchdog(path, now + 1.0, 5.0).action == "no_action"
    stale = evaluate_watchdog(path, now + 6.0, 5.0)
    assert stale.action == "emergency" and stale.reason == "stale"
    # Fail-closed: a missing file requests the SAME emergency action.
    missing = evaluate_watchdog(tmp_path / "missing.txt", now, 5.0)
    assert missing.action == "emergency" and missing.reason == "unreadable"


# ---------------------------------------------------------------------- #
# Live config
# ---------------------------------------------------------------------- #
def test_live_config_from_dict_and_timeframe_coercion():
    cfg = live_config_from_dict(
        {"symbol": "EURUSD", "timeframe": "H1", "heartbeat_interval": 2.0}
    )
    assert cfg.symbol == "EURUSD"
    assert cfg.timeframe is Timeframe.H1
    assert cfg.heartbeat_interval == pytest.approx(2.0)
    assert cfg.demo is True                        # demo-first default
    cfg2 = live_config_from_dict({"timeframe": 16385})
    assert cfg2.timeframe is Timeframe.H1
    cfg3 = live_config_from_dict({"timeframe": "m5"})
    assert cfg3.timeframe is Timeframe.M5
    with pytest.raises(ValueError):
        live_config_from_dict({"timeframe": "NONSENSE_TF_XYZ"})


# ---------------------------------------------------------------------- #
# Live loop over the real stack (fake connector)
# ---------------------------------------------------------------------- #
class LiveFakeConnector:
    """MT5-shaped connector for the loop: bars, account, order surface."""

    def __init__(self, bars=None, *, connect_ok=True) -> None:
        self.bars = list(bars or [])
        self.connect_ok = connect_ok
        self.connected = False
        self.requests: list[dict] = []

    def connect(self) -> bool:
        self.connected = self.connect_ok
        return self.connect_ok

    def append_bar(self, bar: Candle) -> None:
        self.bars.append(bar)

    def copy_rates(self, symbol, tf, start, count):
        return [
            dict(
                time=int(b.timestamp.timestamp()),
                open=b.open, high=b.high, low=b.low, close=b.close,
            )
            for b in self.bars
        ]

    def positions_get(self, symbol=None):
        return ()

    def account_info(self):
        return SimpleNamespace(equity=10_000.0)

    def order_send(self, request: dict) -> dict:
        self.requests.append(request)
        return {"retcode": 10008, "comment": "ok"}


def _make_loop(tmp_path, connector, *, clock=None):
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=TF)
    runner = PaperRunner(
        connector=connector,
        risk_engine=RiskEngine(),
        pipeline=adapter,                       # REAL adapter, REAL engine
        order_manager=OrderManager(connector, symbol="XAUUSD.x", magic=999),
        position_manager=PositionManager(connector, symbol="XAUUSD.x"),
        config=PaperConfig(allowed_sessions=SESSIONS),
    )
    driver = DetectionDriver(TF)
    heartbeat = HeartbeatPublisher(
        tmp_path / "smc_heartbeat.txt",
        now=clock if clock is not None else FakeClock(START),
    )
    loop = LiveLoop(
        connector=connector, runner=runner, driver=driver, heartbeat=heartbeat,
        symbol="XAUUSD.x", timeframe=TF, window_bars=200,
    )
    return loop, runner, heartbeat


def test_live_loop_anchors_history_then_processes_new_bars(tmp_path):
    clock = FakeClock(START)
    connector = LiveFakeConnector(bars=_bars([CALM, CALM, CALM]))
    loop, runner, heartbeat = _make_loop(tmp_path, connector, clock=clock)

    assert loop.start() is True
    # Cold start: existing history is anchored, never replayed.
    assert loop.run_once() == 0
    assert runner.kpi.records == []             # no cycle ran
    assert heartbeat.sequence >= 1              # heartbeat published anyway
    assert is_stale(read_heartbeat(heartbeat.path), clock().timestamp(), 5.0) is False

    # A genuinely NEW closed bar arrives → exactly one live cycle runs
    # through the real adapter/engine/risk stack.
    connector.append_bar(_bars([CALM], start=START + timedelta(minutes=15))[0])
    clock.advance(60)
    assert loop.run_once() == 1
    assert runner.kpi.counters()["decisions"] == 1
    # The adapter series received the bar (scan universe stays in sync).
    assert len(loop.runner.adapter._candles) == 1
    # Heartbeat stays fresh after the poll.
    assert is_stale(read_heartbeat(heartbeat.path), clock().timestamp(), 5.0) is False

    # Clean stop marks shutdown; the watchdog contract is unchanged.
    loop.stop()
    assert read_heartbeat(heartbeat.path).state == "shutdown"


def test_live_loop_refuses_to_start_when_connector_fails():
    connector = LiveFakeConnector(connect_ok=False)
    loop = LiveLoop(
        connector=connector, runner=None, driver=None, heartbeat=None
    )
    assert loop.start() is False
    assert connector.connected is False
    with pytest.raises(RuntimeError):
        loop.run_once()                          # never started


def test_live_loop_never_rearms_an_existing_poi(tmp_path):
    """A POI already armed through the engine keeps its §24 anchor: the
    rolling validate_window arms only NEW passes (no episode reset)."""
    clock = FakeClock(START)
    connector = LiveFakeConnector(bars=_bars([CALM]))
    loop, runner, _ = _make_loop(tmp_path, connector, clock=clock)
    engine = runner.adapter.engine

    poi = POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M1],
    )
    engine.arm_at(poi, arm_bar=0)
    loop.start()
    loop.run_once()                               # history anchored (0 bars)
    connector.append_bar(_bars([CALM], start=START + timedelta(minutes=5))[0])
    loop.run_once()                               # one real cycle

    assert [p.id for p in engine.tracked_pois()] == [poi.id]   # no duplicates
    assert engine.episode(poi) is not None
    assert engine.episode(poi).arm_bar == 0       # §24 anchor NOT reset