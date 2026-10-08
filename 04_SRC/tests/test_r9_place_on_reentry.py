"""R9 place-on-reentry intent tests — Lead Architect ruling (2026-09-22).

Covers the ruling's acceptance list plus the design-locked semantics
(00_LOCKED/R9_PLACE_ON_REENTRY_DESIGN.md):

* immediate place when the market is in band (R9 changes nothing);
* far market → intent armed, NOT placed (one-shot unburned);
* later-bar band re-entry → place with the CORRECT limit + inherited
  remaining rest_bars (§23 bars_open convention);
* limit-touch-only re-entry → place (geometry cross-checked against
  ``fill_model.limit_filled`` so the two can never drift);
* no re-entry → natural expiry, no order ever, one-shot still unburned;
* DOA boundary — remaining < 3 bars is never fabricated (design §2b);
* dedupe + clock immutability (first intent wins);
* REPLACED on immediate placement; POI-violation and portfolio drops;
* R8 table unchanged; ``ZONE_REFINEMENT_ATR`` unchanged (GATE_WIDENED=NO).

Paper path mirrored over the fake connector (test_paper_runner
conventions). No live terminal, no wall clock — fully deterministic.
"""

from datetime import datetime, timedelta, timezone

import pytest

from smc.backtest.fill_model import limit_filled
from smc.backtest.intents import (
    INTENT_ARMED,
    INTENT_EXPIRED,
    INTENT_PLACED,
    INTENT_REPLACED,
    IntentBook,
)
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
from smc.paper.runner import PaperConfig, PaperRunner
from smc.risk.fill_regime_policy import (
    INTENT_EXPIRED_NO_REENTRY,
    R8_REST_BARS_H1,
    R8_REST_BARS_HTF,
    SKIP_PLACE_FAR_FROM_ZONE,
    market_reentered_zone,
    rest_bars_for,
)
from smc.risk.risk_engine import RiskEngine
from smc.utils.timestamps import Session

TF = Timeframe.M5
START = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)  # Thursday, London

# CALM: close 100.3 — inside the [99, 101] zone band, above the 100.0
# limit (a resting buy-limit at 100.0 is never touched by low 100.1).
CALM = (100.25, 100.45, 100.1, 100.3)
# FAR: a runaway close far above the zone (the September 2025 class).
FAR = (104.0, 104.5, 103.5, 104.2)
# REENTRY: range touches the 100.0 limit but the close (100.6) stays
# ABOVE the zone top + band = 102.0 → touch-only re-entry path.
REENTRY = (100.8, 101.2, 99.9, 100.6)
# DIP: close back inside the band → band re-entry.
DIP = (100.4, 100.6, 100.1, 100.2)

SESSIONS = (Session.LONDON, Session.NEW_YORK)


def test_r9_uses_the_frozen_zone_refinement_constant():
    assert ZONE_REFINEMENT_ATR == 0.5


# ---------------------------------------------------------------------- #
# Re-entry geometry unit tests
# ---------------------------------------------------------------------- #
def test_reentry_band_path_uses_existing_r7_geometry():
    # Zone [99, 101], ATR 2 → band [98, 102]: close inside → True.
    assert market_reentered_zone(Direction.LONG, 99.0, 101.0, 100.0,
                                 100.6, 2.0) is True
    # Close exactly on the band edge (inclusive) → True.
    assert market_reentered_zone(Direction.LONG, 99.0, 101.0, 100.0,
                                 102.0, 2.0) is True
    # One tick beyond the band and no touch → False.
    assert market_reentered_zone(Direction.LONG, 99.0, 101.0, 100.0,
                                 102.01, 2.0) is False


def test_reentry_touch_path_mirrors_fill_model_both_directions():
    import math

    zone = (99.0, 101.0)
    long_bar = Candle(timestamp=START, open=100.8, high=101.2, low=99.9,
                      close=100.6, timeframe=TF)
    short_bar = Candle(timestamp=START, open=99.2, high=100.1, low=98.8,
                       close=99.4, timeframe=TF)
    # LONG: low 99.9 touches the 100.0 limit even though the close is
    # outside the band; the predicate agrees with the locked fill model.
    assert market_reentered_zone(Direction.LONG, *zone, 100.0, 100.6, 2.0,
                                 bar=long_bar) is True
    assert limit_filled(Direction.LONG, 100.0, long_bar) is True
    # SHORT mirror: high 100.1 touches the 100.0 sell-limit.
    assert market_reentered_zone(Direction.SHORT, *zone, 100.0, 99.4, 2.0,
                                 bar=short_bar) is True
    assert limit_filled(Direction.SHORT, 100.0, short_bar) is True
    # No touch + close outside band → False for both. Band for zone
    # [99, 101] with ATR 2 is [98, 102], so use a close beyond it and a
    # limit the bar's range never reaches.
    calm = Candle(timestamp=START, open=FAR[0], high=FAR[1], low=FAR[2],
                  close=FAR[3], timeframe=TF)
    assert market_reentered_zone(Direction.LONG, *zone, 99.5, 104.2, 2.0,
                                 bar=calm) is False
    assert limit_filled(Direction.LONG, 99.5, calm) is False
    # Non-finite limit never triggers: close far OUTSIDE the band so the
    # band path cannot mask the touch path, bar range touching nothing.
    far_bar = Candle(timestamp=START, open=FAR[0], high=FAR[1], low=FAR[2],
                     close=FAR[3], timeframe=TF)
    assert market_reentered_zone(Direction.LONG, *zone, float("nan"), 104.2,
                                 2.0, bar=far_bar) is False
    assert market_reentered_zone(Direction.LONG, *zone, None, 104.2, 2.0,
                                 bar=far_bar) is False


def test_reentry_band_dormancy_matches_r7():
    # ATR <= 0 → the band cannot be computed; R7 is dormant, so the
    # re-entry predicate defers to it (True) even outside any zone.
    assert market_reentered_zone(Direction.LONG, 99.0, 101.0, 100.0,
                                 130.0, 0.0) is True


# ---------------------------------------------------------------------- #
# Backtest integration — the four blueprint scenarios
# ---------------------------------------------------------------------- #
def _series(rows, start=START):
    return CandleSeries([
        Candle(timestamp=start + timedelta(minutes=5 * i), open=o, high=h,
               low=l, close=c, timeframe=TF)
        for i, (o, h, l, c) in enumerate(rows)
    ], timeframe=TF)


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
        zone_low=99.0,
        zone_high=101.0,
        route_id="poi-1:F@5",
        poi_id="poi-1",
    )
    kwargs.update(overrides)
    return CandidateEntry(**kwargs)


def test_backtest_immediate_place_when_market_in_band_arms_nothing(
        candle_factory):
    loop, runner = _backtest_runner([CALM] * 3)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    assert len(runner.orders) == 1
    assert len(runner.intents) == 0  # no intent needed, none armed
    assert runner.intents.counters()["armed"] == 0


def test_backtest_far_market_arms_intent_and_places_nothing(candle_factory):
    loop, runner = _backtest_runner([FAR] * 3)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    assert len(runner.orders) == 0
    assert len(runner.intents) == 1
    intent = runner.intents.alive_intents()[0]
    assert intent.status == INTENT_ARMED
    assert intent.signal_bar == 0 and intent.rest_bars == 12  # R8 default
    assert intent.expire_bar == 12
    # One-shot unburned: the M3 seam has no adapter; prove via the
    # blocked log (skip recorded) and the untouched pending book.
    assert [b.blocked_by for b in runner.blocked_log] == \
        [SKIP_PLACE_FAR_FROM_ZONE]


def test_backtest_reentry_places_with_correct_limit_and_inherited_life(
        candle_factory):
    # Bar 0: FAR close → intent armed (expire bar 12, R8 default 12).
    # Bar 1: DIP close 100.2 re-enters the band → place with the SAME
    # on-zone limit 100.0 and rest_bars = remaining = 11.
    loop, runner = _backtest_runner([FAR, DIP, CALM, CALM])
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    assert len(runner.orders) == 1
    order = runner.orders.active()[0]
    assert order.entry_price == 100.0          # the FR-3.1 on-zone limit
    assert order.volume == pytest.approx(_candidate_lots())
    assert order.placed_bar == 1
    assert order.rest_bars == 11               # remaining = 12 - 1
    assert order.detection_tf is None
    intent = runner.intents.alive_intents()
    assert intent == []                        # none alive…
    placed = [e for e in runner.intents.events if e["event"] == "placed"]
    assert len(placed) == 1 and placed[0]["rest_bars"] == 11
    # One-shot consumed exactly once at the intent place (M3 seam: the
    # sweep/context maps stay empty; the order exists = accepted path ran).
    # No duplicate order when the candidate re-proposes later bars:
    assert len(runner.orders) == 1


def _candidate_lots():
    """Policy-sized lots for the default candidate (sl_distance 1.0)."""
    from smc.risk.lot_sizing import sized_lots
    return sized_lots(equity=10_000.0, risk_fraction=0.01, sl_distance=1.0,
                      pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01)


def test_backtest_touch_only_reentry_places(candle_factory):
    # Zone [90, 92], ATR 2 → band [89, 93]. Bar 0: FAR close 104.2 → arm.
    # Bar 1: a spike-down bar — low 89.9 crosses the 90.0 limit while its
    # close 104.1 stays OUTSIDE the band → TOUCH-ONLY re-entry (the band
    # path never fires on this bar).
    TOUCH = (104.0, 104.3, 89.9, 104.1)
    loop, runner = _backtest_runner([FAR, TOUCH, CALM, CALM])
    runner.set_atr(2.0)
    runner.submit_entry(_candidate(entry_price=90.0, sl_price=88.5,
                                   tp_price=94.0,
                                   zone_low=90.0, zone_high=92.0))
    loop.run()
    assert len(runner.orders) == 1
    order = runner.orders.active()[0]
    assert order.entry_price == 90.0
    assert order.placed_bar == 1
    assert order.rest_bars == 11


def test_backtest_no_reentry_expires_with_no_order(candle_factory):
    loop, runner = _backtest_runner([FAR] * 3)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate(detection_tf=Timeframe.H1))  # R8: 36 bars
    loop.run()
    assert len(runner.orders) == 0
    # Drive the clock by hand: expire_due is called inside on_bar, so
    # walk the remaining bars through the loop itself.
    rows = [CALM] * 40  # re-entry never happens (close in band? NO: CALM
    # close 100.3 IS in the [98,102] band for the [99,101] zone — so use
    # FAR rows to keep the intent alive until natural expiry.
    loop2, runner2 = _backtest_runner([FAR] * 40)
    runner2.set_atr(2.0)
    runner2.submit_entry(_candidate(detection_tf=Timeframe.H1))  # expire 36
    loop2.run()
    assert len(runner2.orders) == 0
    counters = runner2.intents.counters()
    assert counters["expired_no_reentry"] == 1
    assert counters["placed"] == 0
    expired = [e for e in runner2.intents.events
               if e["event"] == INTENT_EXPIRED_NO_REENTRY]
    assert len(expired) == 1 and expired[0]["bar"] == 36  # first dead bar


def test_backtest_intent_clock_uses_r8_not_default(candle_factory):
    # M8-detected candidate → R8 clock 48 from signal (design §2 rule 2).
    loop, runner = _backtest_runner([FAR] * 3)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate(detection_tf=Timeframe.H1, is_m8=True))
    loop.run()
    intent = runner.intents.alive_intents()[0]
    assert intent.rest_bars == 48 == R8_REST_BARS_HTF
    assert intent.expire_bar == 48


def test_backtest_doa_boundary_never_fabricates_a_born_expired_order(
        candle_factory):
    # An H1 intent armed on bar 0 (expire 36) is driven to bar 34 by the
    # loop; remaining = 2 < 3 → the re-entry on bar 34 must NOT place.
    # We construct it directly: arm, then place_due on the boundary bar.
    loop, runner = _backtest_runner([FAR] * 3)
    runner.set_atr(2.0)
    candidate = _candidate(detection_tf=Timeframe.H1)
    runner.submit_entry(candidate)
    loop.run()
    intent = runner.intents.alive_intents()[0]
    # Simulate the loop reaching bar 34 (remaining 2): expire_due ran for
    # bars <= 34 in-loop only up to bar 2; call the placement step by hand.
    from smc.core.candle import Candle as C
    bar34 = C(timestamp=START + timedelta(minutes=5 * 34), open=FAR[0],
              high=FAR[1], low=FAR[2], close=FAR[3], timeframe=TF)
    runner._place_due_intents(bar34, 34, bar34.timestamp)
    assert len(runner.orders) == 0  # remaining 2 → DOA, never placed
    # remaining 3 (bar 33) WOULD place: one fill-eligible bar.
    bar33 = C(timestamp=START + timedelta(minutes=5 * 33), open=FAR[0],
              high=FAR[1], low=FAR[2], close=FAR[3], timeframe=TF)
    # expire_due(33) hasn't run in-loop; the intent is still ARMED.
    runner._place_due_intents(bar33, 33, bar33.timestamp)
    # Wait: remaining at bar 33 = 36 - 33 = 3 → but the touch/band test
    # on FAR (close 104.2) fails → still no order. Force the band check
    # with a DIP bar instead.
    runner2_loop, runner2 = _backtest_runner([FAR] * 3)
    runner2.set_atr(2.0)
    runner2.submit_entry(_candidate(detection_tf=Timeframe.H1))
    runner2_loop.run()
    intent2 = runner2.intents.alive_intents()[0]
    dip33 = C(timestamp=START + timedelta(minutes=5 * 33), open=DIP[0],
              high=DIP[1], low=DIP[2], close=DIP[3], timeframe=TF)
    runner2._place_due_intents(dip33, 33, dip33.timestamp)
    assert len(runner2.orders) == 1  # remaining 3 → exactly one eligible bar
    assert runner2.orders.active()[0].rest_bars == 3
    dip34 = C(timestamp=START + timedelta(minutes=5 * 34), open=DIP[0],
              high=DIP[1], low=DIP[2], close=DIP[3], timeframe=TF)
    runner2._place_due_intents(dip34, 34, dip34.timestamp)
    assert len(runner2.orders) == 1  # no second placement (intent PLACED)


def test_backtest_dedupe_first_intent_wins_clock_never_refreshed(
        candle_factory):
    loop, runner = _backtest_runner([FAR, FAR, FAR])
    runner.set_atr(2.0)
    runner.submit_entry(_candidate(detection_tf=Timeframe.H1))
    # Simulate re-proposals on bars 1 and 2 (adapter re-proposes each bar
    # while the one-shot is unburned) — each runs the entry step again.
    class ReProposer:
        def __init__(self, runner, candidate):
            self.runner, self.candidate = runner, candidate
            self.bar_n = 0

        def on_bar(self, bar, bar_index, clock):
            self.runner.submit_entry(self.candidate)
            self.runner.on_bar(bar, bar_index, clock)

    loop2, runner2 = _backtest_runner([FAR] * 3)
    runner2.set_atr(2.0)
    proposer = ReProposer(runner2, _candidate(detection_tf=Timeframe.H1))
    loop3 = BarLoop(_series([FAR] * 3), proposer)
    loop3.run()
    assert len(runner2.intents) == 1  # dedupe: first intent wins
    intent = runner2.intents.alive_intents()[0]
    assert intent.signal_bar == 0     # clock NEVER refreshed
    assert intent.expire_bar == 36
    assert len(runner2.orders) == 0


def test_backtest_immediate_place_supersedes_alive_intent_replaced(
        candle_factory):
    # Bar 0: FAR → intent armed (R8 36). Bars 1-3: DIP in-band re-proposals
    # → the immediate placement wins; the intent is marked REPLACED and
    # the one-shot stops further proposals (exactly one order).
    candidate = _candidate(detection_tf=Timeframe.H1)
    proposer = _StubAdapter()
    runner2 = BacktestRunner(
        risk_engine=RiskEngine(), order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=RunnerConfig(allowed_sessions=SESSIONS))
    runner2.set_pipeline_adapter(proposer)
    proposer._runner = runner2  # stubs bind themselves (no attach())
    proposer._atr = 2.0  # the adapter feeds the per-bar ATR (band = 1.0)

    class Driver:
        def __init__(self, inner, adapter):
            self.inner, self.adapter = inner, adapter
            self.n = 0

        def on_bar(self, bar, bar_index, clock):
            if self.n == 0 or not self.adapter.accepted:
                self.adapter.queue(candidate)  # §11: re-propose until burned
            self.n += 1
            self.inner.on_bar(bar, bar_index, clock)

    BarLoop(_series([FAR, DIP, DIP, DIP]), Driver(runner2, proposer)).run()
    assert len(runner2.orders) == 1
    order = runner2.orders.active()[0]
    assert order.placed_bar == 1
    assert order.rest_bars == 36          # immediate place keeps FULL R8
    counters = runner2.intents.counters()
    assert counters["placed"] == 0 and counters["replaced"] == 1
    assert len(proposer.accepted) == 1    # one-shot burned exactly once


def test_backtest_cancel_pending_for_poi_drops_intent(candle_factory):
    loop, runner = _backtest_runner([FAR] * 2)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    assert len(runner.intents.alive_intents()) == 1
    runner.cancel_pending_for_poi("poi-1", bar_index=5)
    assert runner.intents.alive_intents() == []
    counters = runner.intents.counters()
    assert counters["dropped_poi"] == 1


def test_backtest_friday_eod_drops_intents(candle_factory):
    # NOTE: the once-per-Friday latch fires on the FIRST Friday bar at/after
    # the frozen 20:00 UTC hour (FRIDAY_EOD_CLOSE_HOUR_UTC).
    # Intent armed far on Thursday (London session); on Friday the EOD
    # fires at the frozen 20:00 UTC hour BEFORE the entry step → the
    # intent dies with the portfolio event, no order. Ascending stamps.
    thursday = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)  # London
    stamps = [thursday,
              datetime(2026, 3, 13, 19, 55, tzinfo=timezone.utc),
              datetime(2026, 3, 13, 20, 0, tzinfo=timezone.utc),   # EOD fires
              datetime(2026, 3, 13, 20, 5, tzinfo=timezone.utc)]
    series = CandleSeries([
        Candle(timestamp=ts, open=FAR[0], high=FAR[1], low=FAR[2],
               close=FAR[3], timeframe=TF)
        for ts in stamps
    ], timeframe=TF)
    runner2 = BacktestRunner(
        risk_engine=RiskEngine(), order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=RunnerConfig(allowed_sessions=SESSIONS))
    runner2.set_atr(2.0)

    class ArmOnce:
        def __init__(self):
            self.submitted = False

        def on_bar(self, bar, bar_index, clock):
            if not self.submitted and bar.timestamp.date() == thursday.date():
                runner2.submit_entry(_candidate())
                self.submitted = True
            runner2.on_bar(bar, bar_index, clock)

    BarLoop(series, ArmOnce()).run()
    assert runner2.intents.counters()["dropped_portfolio"] == 1
    assert len(runner2.orders) == 0
    events = [e["event"] for e in runner2.intents.events]
    assert "dropped_portfolio_friday" in events


# ---------------------------------------------------------------------- #
# R8 table + gate constant (unchanged by R9)
# ---------------------------------------------------------------------- #
def test_r8_table_unchanged_by_r9():
    assert rest_bars_for(Timeframe.H1) == 36 == R8_REST_BARS_H1
    assert rest_bars_for(Timeframe.H4) == 48 == R8_REST_BARS_HTF
    assert rest_bars_for(Timeframe.D1) == 48
    assert rest_bars_for(None, is_m8=True) == 48
    assert rest_bars_for(Timeframe.M5) == 12


def test_intent_book_counters_and_deterministic_order():
    book = IntentBook()
    c1 = _candidate(route_id="r1", poi_id="p1")
    c2 = _candidate(route_id="r2", poi_id="p2")
    i1 = book.arm(c1, 0.1, 0, 12)
    i2 = book.arm(c2, 0.1, 3, 48)
    assert [i.intent_id for i in book.alive_intents()] == [1, 2]
    assert book.arm(_candidate(route_id="r1", poi_id="p1"), 0.1, 5, 12) is None
    book.mark_expired(i1, 12)
    book.mark_placed(i2, 5, 77)
    counters = book.counters()
    assert counters == {"armed": 2, "placed": 1, "expired_no_reentry": 1,
                        "replaced": 0, "dropped_poi": 0,
                        "dropped_portfolio": 0, "alive_at_end": 0}
    assert i2.status == INTENT_PLACED and i2.placed_ticket == 77
    assert i1.status == INTENT_EXPIRED and i1.end_bar == 12


# ---------------------------------------------------------------------- #
# Paper path — fake connector, real stack (test_paper_runner conventions)
# ---------------------------------------------------------------------- #
class _StubAdapter:
    def __init__(self) -> None:
        self._candles = []
        self._runner = None
        self._queued = []
        self.accepted = []

    def bind(self, runner) -> None:
        self._runner = runner

    def current_atr(self, bar_index):
        # Mirror the real adapter: the runner reads the per-bar ATR from
        # here when attached. None = "no honest value" → the runner keeps
        # whatever set_atr() injected (the M3 seam contract).
        return getattr(self, "_atr", None)

    def prune_terminal_pois(self, retain, bar_index) -> None:
        return None  # no engine bookkeeping in the stub

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


def _paper_bar(minutes_after_start, row=CALM):
    ts = START + timedelta(minutes=minutes_after_start)
    return Candle(timestamp=ts, open=row[0], high=row[1], low=row[2],
                  close=row[3], timeframe=TF)


def test_paper_far_market_arms_intent_not_place():
    runner, adapter = _paper_runner()
    adapter._candles = _seed()
    adapter.queue(_candidate(zone_low=90.0, zone_high=92.0))
    runner.run_one_cycle(_paper_bar(0, FAR))
    assert runner._pendings == {}
    assert adapter.accepted == []                      # one-shot unburned
    assert len(runner.intents.alive_intents()) == 1
    skips = [r for r in runner.kpi.records if r.event == "place_skip"]
    assert len(skips) == 1


def test_paper_reentry_places_and_consumes_one_shot_once():
    runner, adapter = _paper_runner()
    adapter._candles = _seed()
    adapter.queue(_candidate(zone_low=98.0, zone_high=100.5))
    runner.run_one_cycle(_paper_bar(0, FAR))    # close 104.2 → arm
    assert runner._pendings == {}
    runner.run_one_cycle(_paper_bar(5, CALM))   # close 100.3 → band re-entry
    assert list(runner._pendings) == [1001]
    assert len(adapter.accepted) == 1           # one-shot consumed at place
    assert runner.intents.counters()["placed"] == 1
    # The INTENT path (not a duplicate immediate place) did this: bar 5's
    # candidate queue was empty — only the intent could have placed.


def test_paper_no_reentry_expires_with_kpi_record():
    runner, adapter = _paper_runner()
    adapter._candles = _seed()
    adapter.queue(_candidate(zone_low=90.0, zone_high=92.0))
    runner.run_one_cycle(_paper_bar(0, FAR))    # arm (expire bar ≈ 0+12)
    # Walk 13 far bars → the intent expires naturally.
    for i in range(1, 15):
        runner.run_one_cycle(_paper_bar(5 * i, FAR))
    assert runner._pendings == {}
    assert runner.intents.counters()["expired_no_reentry"] == 1
    expired = [r for r in runner.kpi.records
               if r.event == INTENT_EXPIRED_NO_REENTRY]
    assert len(expired) == 1


def test_paper_intent_expiry_before_reentry_same_bar():
    # The clock ends on bar B; a band re-entry on bar B must NOT place
    # (expire_due runs before the re-entry step — design §4).
    runner, adapter = _paper_runner()
    adapter._candles = _seed()
    # Arm on bar 0 with default 12-bar clock; paper bar_index grows with
    # the adapter's series (seed 14 → bar indices 14, 15, ...). Arm at
    # index 14 → expire at 26; walk to bar index 26 and re-enter there.
    adapter.queue(_candidate(zone_low=98.0, zone_high=100.5))
    runner.run_one_cycle(_paper_bar(0, FAR))
    alive = runner.intents.alive_intents()[0]
    assert alive.expire_bar == 14 + 12 == 26
    for i in range(1, 13):  # bars 15..26 → 12 more cycles
        runner.run_one_cycle(_paper_bar(5 * i, FAR))
    # Bar index 26 = the expire bar: a DIP re-entry must be refused.
    runner.run_one_cycle(_paper_bar(60, DIP))
    assert runner._pendings == {}
    assert runner.intents.counters()["expired_no_reentry"] == 1


def test_paper_replaced_on_immediate_place():
    # Intent armed far; the adapter re-proposes (one-shot model) in-band
    # → the immediate path places and the intent is REPLACED. The stub
    # adapter then STOPS proposing (accepted non-empty) — exactly one order.
    runner, adapter = _paper_runner()
    adapter._candles = _seed()
    candidate = _candidate(zone_low=98.0, zone_high=100.5)
    adapter.queue(candidate)
    runner.run_one_cycle(_paper_bar(0, FAR))    # arm
    adapter.queue(candidate)                     # re-proposal, in-band
    runner.run_one_cycle(_paper_bar(5, CALM))    # immediate place
    assert list(runner._pendings) == [1001]
    counters = runner.intents.counters()
    assert counters["replaced"] == 1 and counters["placed"] == 0
    assert len(adapter.accepted) == 1            # one-shot burned once
    # No third proposal (one-shot consumed) — the book never doubles.


def test_paper_dry_run_never_sends_intent_order():
    runner, adapter = _paper_runner()
    runner.config.dry_run = True
    adapter._candles = _seed()
    adapter.queue(_candidate(zone_low=98.0, zone_high=100.5))
    runner.run_one_cycle(_paper_bar(0, FAR))    # arm
    runner.run_one_cycle(_paper_bar(5, CALM))   # re-entry → dry-run record
    assert runner._pendings == {}               # nothing sent
    assert adapter.accepted == []               # one-shot NOT consumed
    assert runner.intents.counters()["alive_at_end"] == 1
    dry = [r for r in runner.kpi.records if r.event == "intent_place_dry_run"]
    assert len(dry) == 1
