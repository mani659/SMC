"""FR fill-regime policy tests — Lead Architect rulings R7 + R8 (2026-09-22).

Coverage per the ruling's instruction:

* **R7 place guard** — a risk-accepted candidate whose limit sits outside
  the routed POI zone beyond the EXISTING FR-3 band (``ZONE_REFINEMENT_ATR
  × ATR``) is NOT placed; an on-zone limit places normally. Unit tests pin
  the exact band geometry (inclusive bounds, ATR-dormancy, fail-closed on
  unlocatable zones) against ``entry_within_zone``'s semantics; integration
  tests prove the runner/paper paths skip with a machine-readable reason.
* **R8 HTF resting** — per-order pending lifetimes in runner bars
  (§23 ``bars_open`` convention): H1-detected 36, H4/M8/D1-detected 48,
  everything else the execution timeframe's frozen §23 default (12 on M5).
  Unit tests pin the table (incl. MT5-int timeframes, M8-wins-over-tf,
  default-never-shortens); integration tests prove an H1/M8 order
  outlives a default order and expires exactly on ``placed + rest_bars``
  under the project's INCLUSIVE convention (expiry when
  ``bars_open = limit``).
* **GATE_WIDENED = NO** — the frozen ``ZONE_REFINEMENT_ATR`` is asserted
  unchanged; R7 re-uses it and nothing else.

No live terminal is required: the paper tests drive the REAL PaperRunner
over the scriptable fake connector (test_paper_runner.py conventions).
"""

from datetime import datetime, timedelta, timezone

import pytest

from smc.backtest.runner import BacktestRunner, CandidateEntry, RunnerConfig
from smc.backtest.bar_loop import BarLoop
from smc.backtest.data_feed import CandleSeries
from smc.backtest.orders import PendingOrderBook
from smc.backtest.positions import PositionStore
from smc.config.locked_constants import ZONE_REFINEMENT_ATR
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.execution.order_manager import OrderManager
from smc.execution.position_manager import PositionManager
from smc.paper.kpi_logger import KPILogger
from smc.paper.runner import PaperConfig, PaperRunner, _TrackedPending
from smc.risk.fill_regime_policy import (
    R8_REST_BARS_H1,
    R8_REST_BARS_HTF,
    SKIP_PLACE_FAR_FROM_ZONE,
    give_up_backstop_bars,
    rest_bars_for,
    zone_place_allowed,
)
from smc.risk.risk_engine import RiskEngine
from smc.utils.timestamps import Session

TF = Timeframe.M5
START = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)  # Thursday, London

CALM = (100.25, 100.45, 100.1, 100.3)  # low 100.1 — never touches a 100.0 limit
SEED_ROW = (100.0, 101.0, 99.0, 100.0)  # TR 2.0 → ATR 2.0 after warm-up

SESSIONS = (Session.LONDON, Session.NEW_YORK)


# ---------------------------------------------------------------------- #
# Locked-constant guard (GATE_WIDENED = NO)
# ---------------------------------------------------------------------- #
def test_r7_uses_the_frozen_zone_refinement_constant():
    # R7 must re-use the existing FR-3 band multiplier — a changed value
    # here means the gate was widened and the ruling is violated.
    assert ZONE_REFINEMENT_ATR == 0.5


# ---------------------------------------------------------------------- #
# R7 unit tests — zone_place_allowed
# ---------------------------------------------------------------------- #
def test_r7_market_inside_zone_allowed():
    assert zone_place_allowed(Direction.LONG, 99.0, 101.0, 100.0, 2.0) is True


def test_r7_market_within_band_of_zone_edge_allowed():
    # Band = 0.5 × ATR = 1.0 → [98.0, 102.0] inclusive on both edges.
    assert zone_place_allowed(Direction.LONG, 99.0, 101.0, 102.0, 2.0) is True
    assert zone_place_allowed(Direction.LONG, 99.0, 101.0, 98.0, 2.0) is True
    # Same geometry as entry_within_zone for the identical inputs.
    assert zone_place_allowed(Direction.SHORT, 99.0, 101.0, 101.0, 2.0) is True


def test_r7_market_beyond_band_rejected_both_directions():
    assert zone_place_allowed(Direction.LONG, 99.0, 101.0, 102.01, 2.0) is False
    assert zone_place_allowed(Direction.SHORT, 99.0, 101.0, 97.99, 2.0) is False


def test_r7_limit_price_is_not_the_tested_quantity():
    # The MARKET is tested, not the limit: post-FR-3.1 the limit is always
    # zone-anchored, so an on-zone limit with a runaway MARKET must skip.
    assert zone_place_allowed(Direction.LONG, 99.0, 101.0, 160.0, 2.0) is False


def test_r7_zero_atr_is_dormant_not_inventive():
    # ATR <= 0 → the band cannot be computed and is never invented;
    # R7 stays dormant (matches the FR-3 gate's documented behavior).
    assert zone_place_allowed(Direction.LONG, 99.0, 101.0, 120.0, 0.0) is True
    assert zone_place_allowed(Direction.LONG, 99.0, 101.0, 120.0, None) is True


def test_r7_missing_zone_is_dormant_m3_seam_keeps_working():
    # Candidates without zone provenance (M3 test seam) are not blocked.
    assert zone_place_allowed(Direction.LONG, None, None, 100.0, 2.0) is True


def test_r7_unlocatable_zone_fails_closed():
    assert zone_place_allowed(Direction.LONG, 101.0, 99.0, 100.0, 2.0) is False
    assert zone_place_allowed(Direction.LONG, float("nan"), 101.0, 100.0, 2.0) is False
    assert zone_place_allowed(Direction.LONG, 99.0, 101.0, float("inf"), 2.0) is False


# ---------------------------------------------------------------------- #
# R8 unit tests — rest_bars_for / give_up_backstop_bars
# ---------------------------------------------------------------------- #
def test_r8_table_h1_is_36():
    assert rest_bars_for(Timeframe.H1) == 36 == R8_REST_BARS_H1


def test_r8_table_h4_m8_d1_are_48():
    assert rest_bars_for(Timeframe.H4) == 48 == R8_REST_BARS_HTF
    assert rest_bars_for(Timeframe.D1) == 48
    assert rest_bars_for(Timeframe.H1, is_m8=True) == 48   # M8 wins over tf
    assert rest_bars_for(None, is_m8=True) == 48           # even with no tf
    assert rest_bars_for(Timeframe.M5, is_m8=True) == 48


def test_r8_table_ltf_and_unknown_use_execution_default():
    assert rest_bars_for(Timeframe.M5) == 12   # frozen §23 M5 default
    assert rest_bars_for(Timeframe.M1) == 12
    assert rest_bars_for(Timeframe.M30) == 12
    assert rest_bars_for(None) == 12           # unknown provenance → default
    # An M1-execution run must not have its 30-bar default shortened.
    assert rest_bars_for(Timeframe.M1, execution_tf=Timeframe.M1) == 30
    assert rest_bars_for(None, execution_tf=Timeframe.M1) == 30


def test_r8_accepts_mt5_style_int_timeframes():
    assert rest_bars_for(int(Timeframe.H1)) == 36   # 16385
    assert rest_bars_for(int(Timeframe.H4)) == 48   # 16388
    assert rest_bars_for(999) == 12                 # unmapped int → default


def test_r8_give_up_backstop_never_below_rest_bars():
    assert give_up_backstop_bars(Timeframe.M5) == 20       # plain backstop
    assert give_up_backstop_bars(Timeframe.H1) == 36       # max(20, 36)
    assert give_up_backstop_bars(None, is_m8=True) == 48   # max(20, 48)


# ---------------------------------------------------------------------- #
# R7 integration — backtest runner skips far-from-zone placements
# ---------------------------------------------------------------------- #
def _series(rows, start=START):
    candles = [
        Candle(timestamp=start + timedelta(minutes=5 * i), open=o, high=h,
               low=l, close=c, timeframe=TF)
        for i, (o, h, l, c) in enumerate(rows)
    ]
    return CandleSeries(candles, timeframe=TF)


def _backtest_runner(rows):
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=RunnerConfig(allowed_sessions=SESSIONS),
    )
    return BarLoop(_series(rows), runner), runner


def _candidate(**overrides):
    kwargs = dict(
        direction=Direction.LONG,
        entry_price=100.0,
        sl_price=99.0,
        tp_price=104.0,
        score=10.0,  # A+ spread grade — the spread gate never blocks
    )
    kwargs.update(overrides)
    return CandidateEntry(**kwargs)


def test_backtest_r7_skips_when_market_left_the_zone(candle_factory):
    # Risk-accepted (no session/news blocks) but the MARKET (bar close
    # 100.3) sits outside the [90, 92] zone beyond the 1.0 band → R7
    # skips the placement even though the LIMIT (100.0, FR-3.1-anchored)
    # would be irrelevant here — the thesis zone is 8+ units away.
    loop, runner = _backtest_runner([CALM] * 3)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate(entry_price=91.0,
                                   zone_low=90.0, zone_high=92.0))
    loop.run()
    assert len(runner.orders) == 0
    assert [b.blocked_by for b in runner.blocked_log] == [SKIP_PLACE_FAR_FROM_ZONE]
    skip = runner.blocked_log[0]
    assert skip.poi_id is None and skip.route_id is None  # identity passthrough


def test_backtest_r7_allows_when_market_near_zone(candle_factory):
    # Market close 100.3 inside the [99, 101] zone band → placed (this is
    # the September 2025 runaway class inverted: market still at the zone).
    loop, runner = _backtest_runner([CALM] * 3)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate(zone_low=99.0, zone_high=101.0))
    loop.run()
    assert len(runner.orders) == 1
    assert [b.blocked_by for b in runner.blocked_log] == []


def test_backtest_r7_band_boundary_is_inclusive(candle_factory):
    # market = zone_high + band exactly → allowed (entry_within_zone parity).
    # Single bar: placement happens in bar 0's entry step and no later bar
    # can fill/market the resting limit — the book itself is the assertion.
    loop, runner = _backtest_runner([CALM] * 1)
    runner.set_atr(2.0)  # band = 1.0
    runner.submit_entry(_candidate(zone_low=99.0, zone_high=101.0))
    # CALM close is 100.3; rezone so close = top + band exactly.
    runner._pending_entries[0] = _candidate(zone_low=99.3, zone_high=99.3)
    loop.run()
    assert len(runner.orders) == 1
    assert [b.blocked_by for b in runner.blocked_log] == []


# ---------------------------------------------------------------------- #
# R8 integration — backtest pending lifetimes (§23 bars_open convention)
# ---------------------------------------------------------------------- #
def test_backtest_r8_htf_order_outlives_default_order_and_expires_exactly(
        candle_factory):
    # Both orders place on bar 0 (submitted before the loop; nothing fills
    # on CALM rows — low 100.1 never touches a 100.0 limit). The default
    # M5 order §23-expires when bars_open = 12 (bar 11); the M8-detected
    # order rests 48 bars and expires when bars_open = 48 (bar 47), NOT at
    # the §24 give-up 20 (the R8-aware backstop is max(20, 48)).
    rows = [CALM] * 8  # 8 bars: neither lifetime reached during the loop
    loop, runner = _backtest_runner(rows)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())                                      # default
    runner.submit_entry(_candidate(detection_tf=Timeframe.H1, is_m8=True))  # R8
    loop.run()
    default_order, m8_order = runner.orders.active()  # insertion order
    assert default_order.rest_bars == 12
    assert m8_order.rest_bars == 48

    # Drive the same book by hand through the inclusive boundaries.
    assert runner.orders.expired_by_section23(10, TF) == []   # bars_open 11
    assert runner.orders.expired_by_section23(11, TF) == [default_order]
    assert m8_order in runner.orders.active()
    # bars_open 20 at bar 19: the PLAIN §24 backstop would cancel here —
    # the R8-aware one (max(20, 48)) must not shorten the HTF rest.
    assert runner.orders.expired_by_give_up(19) == []
    assert m8_order in runner.orders.active()
    # bars_open 36 at bar 35: still inside the R8 window (36 inclusive).
    assert runner.orders.expired_by_section23(35, TF) == []
    assert m8_order in runner.orders.active()
    # bars_open 48 at bar 47 → expired (give-up path shown; §23 identical).
    assert runner.orders.expired_by_give_up(47) == [m8_order]


def test_backtest_r8_legacy_orders_keep_the_frozen_defaults(candle_factory):
    # Orders without R8 provenance (M3-era) expire exactly as before.
    loop, runner = _backtest_runner([CALM] * 3)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    order = runner.orders.active()[0]
    assert order.rest_bars == 12 and order.detection_tf is None
    assert runner.orders.expired_by_section23(10, TF) == []   # bars_open 11
    assert runner.orders.expired_by_section23(11, TF) == [order]  # bars_open 12


# ---------------------------------------------------------------------- #
# R7 + R8 integration — paper runner (fake broker, real stack)
# ---------------------------------------------------------------------- #
class _StubAdapter:
    """Minimal PipelineAdapter protocol stub (test_paper_runner conventions)."""

    def __init__(self) -> None:
        self._candles = []
        self._runner = None
        self._queued = []
        self.accepted = []

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


def _paper_runner():
    from tests.test_paper_runner import FakeConnector

    connector = FakeConnector()
    adapter = _StubAdapter()
    runner = PaperRunner(
        connector=connector,
        risk_engine=RiskEngine(),
        pipeline=adapter,
        order_manager=OrderManager(connector, symbol="XAUUSD.x", magic=999),
        position_manager=PositionManager(connector, symbol="XAUUSD.x"),
        config=PaperConfig(),
        perf=lambda: 0.0,
    )
    adapter.bind(runner)
    return runner, adapter


def _seed(n=14):
    return [
        Candle(timestamp=START - timedelta(minutes=5 * (n - i)), open=100.0,
               high=101.0, low=99.0, close=100.0, timeframe=TF)
        for i in range(n)
    ]


def _paper_bar(minutes_after_start):
    ts = START + timedelta(minutes=minutes_after_start)
    return Candle(timestamp=ts, open=CALM[0], high=CALM[1], low=CALM[2],
                  close=CALM[3], timeframe=TF)


def test_paper_r7_skips_far_from_zone_candidate_and_keeps_one_shot():
    runner, adapter = _paper_runner()
    adapter._candles = _seed()
    # Market (close 100.3) outside the [90, 92] zone beyond the band →
    # skip; the on-zone limit (91.0) is irrelevant to the guard.
    adapter.queue(_candidate(entry_price=91.0,
                             zone_low=90.0, zone_high=92.0))
    runner.run_one_cycle(_paper_bar(0))

    assert runner._pendings == {}                       # nothing placed
    assert adapter.accepted == []                       # one-shot NOT consumed
    skips = [r for r in runner.kpi.records if r.event == "place_skip"]
    assert len(skips) == 1
    assert skips[0].fields["reason"] == SKIP_PLACE_FAR_FROM_ZONE
    decision = [r for r in runner.kpi.records if r.event == "decision"][0]
    assert decision.fields["placed"] == 0 and decision.fields["blocked"] == 1


def test_paper_r7_allows_on_zone_candidate():
    runner, adapter = _paper_runner()
    adapter._candles = _seed()
    adapter.queue(_candidate(zone_low=99.0, zone_high=101.0))
    runner.run_one_cycle(_paper_bar(0))

    assert list(runner._pendings) == [1001]
    assert [r for r in runner.kpi.records if r.event == "place_skip"] == []


def test_paper_r8_pending_expires_on_its_own_rest_bars():
    runner, _ = _paper_runner()
    h1_pending = _TrackedPending(
        ticket=2001, poi_id="poi-h1", trigger=None, route_id=None,
        fvg_context=None, sweep_level=None, placed_at=START,
        symbol="XAUUSD.x", magic=999, comment="poi-h1",
        rest_bars=rest_bars_for(Timeframe.H1),   # 36
    )
    m5_pending = _TrackedPending(
        ticket=2002, poi_id="poi-m5", trigger=None, route_id=None,
        fvg_context=None, sweep_level=None, placed_at=START,
        symbol="XAUUSD.x", magic=999, comment="poi-m5",
        rest_bars=None,                          # runner default (12)
    )
    runner._pendings = {2001: h1_pending, 2002: m5_pending}

    # age 11 → both resting (M5's inclusive boundary not yet reached).
    runner._expire_pendings(START + timedelta(minutes=55))
    assert sorted(runner._pendings) == [2001, 2002]
    # age 12 → the default order expires; the H1 order rests on.
    runner._expire_pendings(START + timedelta(minutes=60))
    assert sorted(runner._pendings) == [2001]
    # age 35 → the H1 order is still inside its R8 window (36 inclusive).
    runner._expire_pendings(START + timedelta(minutes=175))
    assert sorted(runner._pendings) == [2001]
    # age 36 → expired exactly on placed + rest_bars.
    runner._expire_pendings(START + timedelta(minutes=180))
    assert runner._pendings == {}


def test_paper_r8_rest_bars_recorded_on_placed_pending():
    runner, adapter = _paper_runner()
    adapter._candles = _seed()
    adapter.queue(_candidate(detection_tf=Timeframe.H1))
    runner.run_one_cycle(_paper_bar(0))

    pending = runner._pendings[1001]
    assert pending.rest_bars == 36
