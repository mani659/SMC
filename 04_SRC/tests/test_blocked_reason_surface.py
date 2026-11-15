"""Blocked-reason surface tests (entry-block vocabulary + bounded block log).

Pins that the paper runner names an entry block with the EXISTING
machine-readable code (no new vocabulary), that the ``decision`` record keeps
its counts unchanged, and that the display helpers are read-only and bounded.

.. note::
   Rebuilt 2026-11-08 after a file-corruption event destroyed the original
   module (only lines 140-209 survived). Assertions below are those the
   surviving fragment pins; the operator-board half of the original file is
   NOT reconstructed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from smc.backtest.runner import CandidateEntry
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.execution.order_manager import OrderManager
from smc.execution.position_manager import PositionManager
from smc.paper.kpi_logger import KPILogger
from smc.paper.runner import PaperConfig, PaperRunner
from smc.risk.risk_engine import BLOCK_MIN_LOTS, BLOCK_SESSION, RiskEngine

TF = Timeframe.M5
START = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)   # Thursday, London
CALM = (100.25, 100.45, 100.1, 100.3)


class _Perf:
    def __call__(self) -> float:
        return 0.0


class _Adapter:
    def __init__(self) -> None:
        self._candles: list[Candle] = []
        self._runner = None
        self._queued: list = []
        self.accepted: list = []

    def bind(self, runner) -> None:
        self._runner = runner

    def generate_candidates(self, bar, bar_index, now) -> None:
        for candidate in self._queued:
            self._runner.submit_entry(candidate)
        self._queued = []

    def queue(self, candidate) -> None:
        self._queued.append(candidate)

    def on_candidate_accepted(self, candidate) -> None:
        self.accepted.append(candidate)


def _seed(n=14):
    return [
        Candle(timestamp=START - timedelta(minutes=5 * (n - i)), open=100.0,
               high=101.0, low=99.0, close=100.0, timeframe=TF)
        for i in range(n)
    ]


def _bar(ts, row=CALM):
    o, h, l, c = row
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, timeframe=TF)


def _candidate(**overrides) -> CandidateEntry:
    kwargs = dict(
        direction=Direction.LONG,
        entry_price=100.0,
        sl_price=99.0,
        tp_price=104.0,
        score=10.0,
        zone_low=99.0,
        zone_high=101.0,
        route_id="poi-1:D@3",
        poi_id="poi-1",
        trigger=TriggerType.D_TWO_BAR_REVERSAL,
        detection_tf=Timeframe.H4,
    )
    kwargs.update(overrides)
    return CandidateEntry(**kwargs)


def _runner(config=None, *, kpi=None, equity: float = 10_000.0):
    from tests.test_paper_runner import FakeConnector

    connector = FakeConnector()
    connector.account = SimpleNamespace(equity=equity)
    adapter = _Adapter()
    runner = PaperRunner(
        connector=connector,
        risk_engine=RiskEngine(),
        pipeline=adapter,
        order_manager=OrderManager(connector, symbol="XAUUSD.x", magic=999),
        position_manager=PositionManager(connector, symbol="XAUUSD.x"),
        config=config if config is not None else PaperConfig(),
        kpi=kpi,
        perf=_Perf(),
    )
    adapter.bind(runner)
    adapter._candles = _seed()
    return runner, adapter


# --------------------------------------------------------------------- #
# 1. Machine-readable block surface
# --------------------------------------------------------------------- #
def test_blocked_entry_names_the_existing_code_and_keeps_counts():
    kpi = KPILogger()
    runner, adapter = _runner(PaperConfig(allowed_sessions=()), kpi=kpi)
    adapter.queue(_candidate(poi_id="poi-block-1", route_id="poi-block-1:D@3"))
    runner.run_one_cycle(_bar(START, CALM))

    assert runner.block_reasons() == {BLOCK_SESSION: 1}
    decision = [r for r in runner.kpi.records if r.event == "decision"][-1]
    assert decision.fields["blocked"] == 1        # count unchanged
    assert decision.fields["placed"] == 0

    events = [r for r in runner.kpi.records if r.event == "entry_blocked"]
    assert len(events) == 1
    assert events[0].fields["reason"] == BLOCK_SESSION
    assert events[0].fields["poi_id"] == "poi-block-1"
    assert events[0].fields["tier"] is None        # not invented
    assert events[0].fields["bar_index"] == decision.fields["bar_index"]


def test_unblocked_run_records_no_reason():
    runner, adapter = _runner()
    adapter.queue(_candidate())
    runner.run_one_cycle(_bar(START, CALM))
    assert runner.block_reasons() == {}
    assert runner.last_blocks() == []


def test_sizing_shortfall_is_reported_as_the_existing_min_lots_code():
    # Zero equity -> the EXISTING sizing gate returns BLOCK_MIN_LOTS. The
    # point is that the surface can name it without a new vocabulary.
    runner, adapter = _runner(equity=0.0)
    adapter.queue(_candidate())
    runner.run_one_cycle(_bar(START, CALM))
    assert runner.block_reasons() == {BLOCK_MIN_LOTS: 1}


def test_last_blocks_is_bounded_and_oldest_first():
    runner, adapter = _runner(PaperConfig(allowed_sessions=()))
    for index in range(4):
        adapter.queue(_candidate(poi_id=f"poi-block-{index}",
                                 route_id=f"poi-block-{index}:D@3"))
        runner.run_one_cycle(_bar(START + timedelta(minutes=5 * index), CALM))
    recent = runner.last_blocks(3)
    assert [row["poi_id"] for row in recent] == [
        "poi-block-1", "poi-block-2", "poi-block-3",
    ]
    assert runner.book_counts() == {"pendings": 0, "positions": 0}
