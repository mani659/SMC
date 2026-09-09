"""Phase 6 M6 — paper runner tests (fake broker, fake clock, real stack).

These tests drive the REAL PaperRunner over REAL ``OrderManager`` /
``PositionManager`` instances wrapped around a scriptable fake connector
(the same mock conventions as ``test_mt5_connector.py`` /
``test_position_manager.py`` — real MT5 is never required). The pipeline
side uses a protocol-conformant stub adapter (the same
``generate_candidates`` / ``on_candidate_accepted`` seam the M4 adapter
implements — its real-pipeline behaviour is proven in
``test_backtest_pipeline_integration.py``).

Geometry conventions (all UTC, M5 bars, START = Thursday 09:00 London):

* SEED bars (high-low 2.0, flat closes) give a stable ATR = 2.0 after the
  14-bar warm-up — the PureRunner BE gate is exactly 1.0 × ATR from entry;
* CALM closes at 100.3 (no BE, no trigger), RUN_UP closes at 102.5
  (> 1 × ATR in favour → BE proposes entry + 0.10 × ATR);
* the fake connector applies SLTP modifies to its position dicts and
  FIFO-pops one position per successful close DEAL, so observation tests
  see realistic broker truth.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from smc.backtest.runner import CandidateEntry
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.execution.order_manager import (
    ORDER_TYPE_BUY_LIMIT,
    OrderManager,
    TRADE_ACTION_DEAL,
    TRADE_ACTION_PENDING,
    TRADE_ACTION_REMOVE,
    TRADE_ACTION_SLTP,
)
from smc.execution.news_guard import NewsEvent
from smc.execution.position_manager import PositionManager
from smc.paper.kpi_logger import KPILogger
from smc.paper.runner import PaperConfig, PaperRunner, _TrackedPending, _TrackedPosition
from smc.risk.risk_engine import RiskEngine

TF = Timeframe.M5
START = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)  # Thursday, London

SEED_ROW = (100.0, 101.0, 99.0, 100.0)   # TR 2.0 → ATR 2.0 after warm-up
CALM = (100.2, 100.6, 100.1, 100.3)      # close 100.3 — below the BE gate
RUN_UP = (102.3, 102.7, 102.2, 102.5)    # close 102.5 — > 1 × ATR over entry


class FakePerf:
    """Deterministic monotonic source: each call advances by exactly 1.0."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return float(self.calls)


class FakeConnector:
    """Scriptable MT5-shaped connector (order_send routed by action)."""

    def __init__(self, *, init_ok: bool = True) -> None:
        self.init_ok = init_ok
        self.initialized = False
        self.shutdowns = 0
        self.account = SimpleNamespace(equity=10_000.0)
        self.positions: list[dict] = []
        self.requests: list[dict] = []
        self.order_seq = 1000
        self.place_success = True
        self.modify_success = True
        self.close_success = True

    def initialize(self) -> bool:
        self.initialized = self.init_ok
        return self.init_ok

    def shutdown(self) -> None:
        self.shutdowns += 1
        self.initialized = False

    def account_info(self):
        return self.account

    def positions_get(self, symbol=None):
        return tuple(self.positions)

    def order_send(self, request: dict) -> dict:
        self.requests.append(request)
        action = request.get("action")
        if action == TRADE_ACTION_PENDING:
            if not self.place_success:
                return {"retcode": 10030, "comment": "invalid price"}
            self.order_seq += 1
            return {"retcode": 10008, "order": self.order_seq, "comment": "placed"}
        if action == TRADE_ACTION_REMOVE:
            return (
                {"retcode": 10009, "comment": "ok"}
                if self.modify_success
                else {"retcode": 10030, "comment": "reject"}
            )
        if action == TRADE_ACTION_SLTP:
            if not self.modify_success:
                return {"retcode": 10030, "comment": "reject"}
            for position in self.positions:
                if position["ticket"] == request.get("position"):
                    position["sl"] = request["sl"]
            return {"retcode": 10009, "comment": "ok"}
        if action == TRADE_ACTION_DEAL:
            if not self.close_success:
                return {"retcode": 10030, "comment": "reject"}
            if self.positions:
                self.positions.pop(0)  # FIFO close (volume-agnostic fake)
            return {"retcode": 10009, "comment": "ok"}
        return {"retcode": 10030, "comment": "unsupported"}


class StubAdapter:
    """Protocol-conformant adapter stub (the M4 adapter's exact seam)."""

    def __init__(self) -> None:
        self._runner = None
        self._candles: list[Candle] = []   # PaperRunner extends this series
        self._queued: list = []
        self.accepted: list = []
        self.scanned: list[tuple[int, datetime]] = []

    def bind(self, runner) -> None:
        self._runner = runner

    def generate_candidates(self, bar: Candle, bar_index: int, now) -> None:
        self.scanned.append((bar_index, now))
        for candidate in self._queued:
            self._runner.submit_entry(candidate)
        self._queued = []

    def queue(self, candidate) -> None:
        self._queued.append(candidate)

    def on_candidate_accepted(self, candidate) -> None:
        self.accepted.append(candidate)


def _bar(ts, row):
    o, h, l, c = row
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, timeframe=TF)


def _seed(n: int = 14):
    """ATR warm-up series ending one bar before START."""
    return [
        _bar(START - timedelta(minutes=5 * (n - i)), SEED_ROW) for i in range(n)
    ]


def _pos(ticket, *, direction=Direction.LONG, price=100.0, sl=99.0, volume=0.10):
    return {
        "ticket": ticket,
        "symbol": "XAUUSD.x",
        "type": 0 if direction is Direction.LONG else 1,
        "volume": volume,
        "price_open": price,
        "sl": sl,
        "tp": 0.0,
    }


def _candidate(**overrides):
    kwargs = dict(
        direction=Direction.LONG,
        entry_price=100.0,
        sl_price=99.0,
        tp_price=None,
        score=10.0,
        poi_id="poi-1",
        trigger=TriggerType.D_TWO_BAR_REVERSAL,
        route_id="poi-1:D@3",
    )
    kwargs.update(overrides)
    return CandidateEntry(**kwargs)


def _make_runner(*, config=None, adapter=None, connector=None):
    connector = connector if connector is not None else FakeConnector()
    adapter = adapter if adapter is not None else StubAdapter()
    runner = PaperRunner(
        connector=connector,
        risk_engine=RiskEngine(),
        pipeline=adapter,
        order_manager=OrderManager(connector, symbol="XAUUSD.x", magic=999),
        position_manager=PositionManager(connector, symbol="XAUUSD.x"),
        config=config or PaperConfig(),
        perf=FakePerf(),
    )
    adapter.bind(runner)
    return runner, adapter, connector


def _requests_of(connector, action):
    return [r for r in connector.requests if r.get("action") == action]


# ---------------------------------------------------------------------- #
# Lifecycle + safety posture
# ---------------------------------------------------------------------- #
def test_start_refuses_when_connector_cannot_initialize():
    runner, _, connector = _make_runner(connector=FakeConnector(init_ok=False))
    assert runner.start() is False
    assert connector.initialized is False


def test_start_initializes_and_stop_releases():
    runner, _, connector = _make_runner()
    assert runner.start() is True
    runner.stop()
    assert connector.shutdowns == 1


def test_one_cycle_logs_a_decision_record():
    runner, adapter, _ = _make_runner()
    adapter._candles = _seed()
    runner.run_one_cycle(_bar(START, CALM))
    counters = runner.kpi.counters()
    assert counters["decisions"] == 1
    assert runner.kpi.records[0].event == "decision"


# ---------------------------------------------------------------------- #
# Entry path
# ---------------------------------------------------------------------- #
def test_successful_entry_places_real_limit_and_consumes_one_shot():
    runner, adapter, connector = _make_runner()
    adapter._candles = _seed()
    adapter.queue(_candidate())
    runner.run_one_cycle(_bar(START, CALM))

    placed = _requests_of(connector, TRADE_ACTION_PENDING)
    assert len(placed) == 1
    request = placed[0]
    assert request["type"] == ORDER_TYPE_BUY_LIMIT
    assert request["price"] == pytest.approx(100.0)
    assert request["sl"] == pytest.approx(99.0)
    assert request["tp"] == 0.0            # no invented TP
    assert request["volume"] == pytest.approx(0.10)  # §28.7 policy sizing cap
    assert request["magic"] == 999
    assert request["comment"] == "poi-1:D@3"         # §11 identity on the order

    assert list(runner._pendings) == [1001]          # broker ticket tracked
    pending = runner._pendings[1001]
    assert pending.poi_id == "poi-1"
    assert pending.trigger is TriggerType.D_TWO_BAR_REVERSAL
    assert len(adapter.accepted) == 1 and adapter.accepted[0].poi_id == "poi-1"

    counters = runner.kpi.counters()
    assert counters["orders_placed"] == 1 and counters["orders_rejected"] == 0
    decision = [r for r in runner.kpi.records if r.event == "decision"][0]
    assert decision.fields["placed"] == 1 and decision.fields["candidates"] == 1


def test_rejected_order_increments_kpi_and_preserves_one_shot():
    connector = FakeConnector()
    connector.place_success = False
    runner, adapter, _ = _make_runner(connector=connector)
    adapter._candles = _seed()
    adapter.queue(_candidate())
    runner.run_one_cycle(_bar(START, CALM))

    assert runner._pendings == {}            # nothing tracked
    assert adapter.accepted == []            # one-shot NOT consumed (I2 parity)
    counters = runner.kpi.counters()
    assert counters["orders_rejected"] == 1 and counters["orders_placed"] == 0
    decision = [r for r in runner.kpi.records if r.event == "decision"][0]
    assert decision.fields["rejected"] == 1


def test_dry_run_logs_decisions_but_places_nothing():
    runner, adapter, connector = _make_runner(config=PaperConfig(dry_run=True))
    adapter._candles = _seed()
    adapter.queue(_candidate())
    runner.run_one_cycle(_bar(START, CALM))

    assert _requests_of(connector, TRADE_ACTION_PENDING) == []
    assert runner._pendings == {}
    decision = [r for r in runner.kpi.records if r.event == "decision"][0]
    assert decision.fields["placed"] == 1    # decision evaluated + logged
    assert adapter.accepted == []            # no broker state change → no consumption


def test_cancel_pending_for_poi_parity():
    runner, adapter, connector = _make_runner()
    adapter._candles = _seed()
    adapter.queue(_candidate())
    runner.run_one_cycle(_bar(START, CALM))

    assert runner.cancel_pending_for_poi("other-poi") == 0
    assert runner.cancel_pending_for_poi("poi-1") == 1
    assert len(_requests_of(connector, TRADE_ACTION_REMOVE)) == 1
    assert runner._pendings == {}


# ---------------------------------------------------------------------- #
# Fill observation → on_trade_opened → BE lifecycle
# ---------------------------------------------------------------------- #
def _filled_runner():
    """Runner with a filled LONG at 100.0 (sl 99.0) tracked from a placed
    pending — the full place → broker-fill → observe path."""
    runner, adapter, connector = _make_runner()
    adapter._candles = _seed()
    adapter.queue(_candidate())
    runner.run_one_cycle(_bar(START, CALM))          # place (ticket 1001)
    connector.positions.append(_pos(1001))
    runner.run_one_cycle(_bar(START + timedelta(minutes=5), CALM))  # fill observed
    return runner, adapter, connector


def test_fill_observed_from_broker_and_identity_transfers():
    runner, _, connector = _filled_runner()
    assert runner._pendings == {}                    # pending consumed
    tracked = runner._positions[1001]
    assert tracked.poi_id == "poi-1"
    assert tracked.trigger is TriggerType.D_TWO_BAR_REVERSAL
    assert tracked.route_id == "poi-1:D@3"
    assert tracked.entry_price == pytest.approx(100.0)
    fills = [r for r in runner.kpi.records if r.event == "fill"]
    assert len(fills) == 1 and fills[0].fields["ticket"] == 1001
    # on_trade_opened fired → the BE latch is re-armed for THIS trade.
    assert runner.risk.pure_runner.state.be_moved is False


def test_be_modify_success_confirms_latch():
    runner, _, connector = _filled_runner()
    # RUN_UP close 102.5 ≈ 1.38 × ATR(≈1.814 after two CALM bars) ≥ 1.0 → BE
    # proposal fires: entry + 0.10 × ATR buffer.
    runner.run_one_cycle(_bar(START + timedelta(minutes=10), RUN_UP))
    assert runner.risk.pure_runner.state.be_moved is True  # on_be_applied ran
    position = connector.positions[0]
    assert position["sl"] == pytest.approx(100.184, abs=0.01)  # entry + 0.1 × ATR
    counters = runner.kpi.counters()
    assert counters["sl_modify_success"] == 1 and counters["sl_modify_failures"] == 0


def test_be_modify_failure_does_not_call_on_be_applied():
    runner, _, connector = _filled_runner()
    connector.modify_success = False                 # broker rejects the modify
    runner.run_one_cycle(_bar(START + timedelta(minutes=10), RUN_UP))
    assert runner.risk.pure_runner.state.be_moved is False  # latch NOT set
    assert connector.positions[0]["sl"] == pytest.approx(99.0)  # SL unchanged
    counters = runner.kpi.counters()
    assert counters["sl_modify_failures"] == 1 and counters["sl_modify_success"] == 0


def test_close_observation_records_unknown_win_without_breaker_update():
    runner, _, connector = _filled_runner()
    connector.positions.clear()                      # broker: position gone (SL/TP)
    runner.run_one_cycle(_bar(START + timedelta(minutes=10), CALM))
    closed = [r for r in runner.kpi.records if r.event == "trade_closed"]
    assert len(closed) == 1
    assert closed[0].fields["kind"] == "broker_close"
    assert closed[0].fields["win"] is None           # honest: P/L not reconstructed
    assert runner._positions == {}
    # Unknown-P/L closes never reach the circuit breaker.
    assert runner.risk.circuit_breaker.state.consecutive_losses == 0


# ---------------------------------------------------------------------- #
# Portfolio events: Friday EOD + §11 hard-cancel
# ---------------------------------------------------------------------- #
def test_friday_close_closes_all_and_cancels_pendings():
    runner, _, connector = _make_runner()
    connector.positions = [_pos(2001), _pos(2002, direction=Direction.SHORT, sl=101.0)]
    runner._positions = {
        2001: _TrackedPosition(
            ticket=2001, direction=Direction.LONG, volume=0.10,
            entry_price=100.0, sl=99.0, poi_id="poi-a", trigger=None,
            route_id=None, fvg_context=None, sweep_level=None,
        ),
        2002: _TrackedPosition(
            ticket=2002, direction=Direction.SHORT, volume=0.10,
            entry_price=100.0, sl=101.0, poi_id="poi-b", trigger=None,
            route_id=None, fvg_context=None, sweep_level=None,
        ),
    }
    runner._pendings = {
        2003: _TrackedPending(
            ticket=2003, poi_id="poi-c", trigger=None, route_id=None,
            fvg_context=None, sweep_level=None, placed_at=START,
        )
    }
    friday = datetime(2026, 3, 13, 20, 0, tzinfo=timezone.utc)
    runner.run_one_cycle(_bar(friday, CALM))

    assert len(_requests_of(connector, TRADE_ACTION_DEAL)) == 2   # both closed
    assert len(_requests_of(connector, TRADE_ACTION_REMOVE)) == 1  # pending gone
    assert runner._positions == {} and runner._pendings == {}
    episode = [r for r in runner.kpi.records if r.event == "friday_close"][0]
    assert episode.fields["closed"] == 2 and episode.fields["cancelled"] == 1
    counters = runner.kpi.counters()
    assert counters["friday_closes"] == 1
    assert counters["exit_close_success"] == 2 and counters["cancel_success"] == 1
    kinds = [r.fields["kind"] for r in runner.kpi.records if r.event == "trade_closed"]
    assert kinds == ["friday_eod", "friday_eod"]


def test_hard_cancel_cancels_pendings_only():
    runner, adapter, connector = _make_runner()
    adapter._candles = _seed()
    adapter.queue(_candidate())
    runner.run_one_cycle(_bar(START, CALM))          # pending 1001 resting
    assert runner._pendings
    # NFP 10 minutes ahead of the next bar → §11 hard-cancel window.
    runner.config.news_events = [
        NewsEvent(kind="NFP", at=START + timedelta(minutes=15))
    ]
    runner.run_one_cycle(_bar(START + timedelta(minutes=5), CALM))
    assert runner._pendings == {}
    assert len(_requests_of(connector, TRADE_ACTION_REMOVE)) == 1
    episode = [r for r in runner.kpi.records if r.event == "hard_cancel"][0]
    assert episode.fields["cancelled"] == 1
    # Open positions are untouched by a hard-cancel (none existed here).
    assert connector.positions == []


# ---------------------------------------------------------------------- #
# KPI records
# ---------------------------------------------------------------------- #
def test_missed_bar_gap_logged():
    runner, _, _ = _make_runner()
    runner.run_one_cycle(_bar(START, CALM))
    runner.run_one_cycle(_bar(START + timedelta(minutes=20), CALM))  # 4 bars late
    missed = [r for r in runner.kpi.records if r.event == "missed_bar"]
    assert len(missed) == 1
    assert missed[0].fields["gap_bars"] == 3         # 09:05 expected, 09:20 seen
    assert runner.kpi.counters()["bars_missed"] == 3


def test_kpi_records_deterministic_under_fake_clock_and_connector():
    def one_run():
        runner, adapter, _ = _make_runner()
        adapter._candles = _seed()
        adapter.queue(_candidate())
        runner.run_one_cycle(_bar(START, CALM))                     # place
        runner._wire_positions = None
        runner.broker.positions.connector.positions.append(_pos(1001))
        runner.run_one_cycle(_bar(START + timedelta(minutes=5), CALM))  # fill
        runner.run_one_cycle(_bar(START + timedelta(minutes=10), RUN_UP))  # BE
        return runner.kpi.to_json()

    assert one_run() == one_run()
