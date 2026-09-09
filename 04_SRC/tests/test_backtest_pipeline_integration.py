"""Phase 6 M4 — full PipelineEngine integration tests (real detection → risk).

These tests drive the REAL pipeline (PipelineEngine + TriggerRouter +
Trigger D) through the M4 PipelineAdapter into the M3 BacktestRunner, over
the M1 BarLoop. No injected candidates on the pipeline path — entries come
from actual trigger detection on synthetic candles. The bridge helpers and
the adapter's workflow lifecycle get their own focused tests.

Geometry conventions (all UTC, M5 bars, zone [100.0, 100.2], LONG POI):

* CALM rows sit strictly ABOVE the zone (low 100.3 > top 100.2) — no §5
  touch, no violation: the POI stays FRESH;
* ENGULFED is the prior candle of the Trigger D two-bar reversal (bearish,
  volume 500) and also stays clear of the zone;
* ENGULFER is the bullish engulfing candle (volume 300 < 500 — the frozen
  confirmation) whose wick ENTERS the zone: the §5 first touch and the
  trigger pattern share this bar (scan-before-feed keeps both alive);
* CALM_SIGNAL is the bar immediately after the engulfing — Trigger D's
  frozen entry bar (§24 TRIGGER_D_EXPIRY = 1): the adapter routes there;
* FILL rows dip to low ≤ 100.45 (the 50%-body limit) without reaching the
  99.9 stop, so the pending limit fills and the position stays open;
* displacement is pre-computed exactly like test_pipeline_engine.py does
  (Pillar 2 is an injected input, not a per-bar recomputation);
* the §15 matrix makes Trigger D structural-eligible for the M1 tag.
"""

from datetime import datetime, timedelta, timezone

import pytest

from smc.backtest.bar_loop import BarLoop
from smc.backtest.data_feed import CandleSeries
from smc.backtest.orders import PendingOrderBook
from smc.backtest.pipeline_adapter import PipelineAdapter
from smc.backtest.pipeline_bridge import candidate_from_route, fvg_context_for_route
from smc.backtest.positions import PositionStore
from smc.backtest.runner import BacktestRunner, CandidateEntry, RunnerConfig
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, LiquidityType, POIState, PoolType, TriggerType
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.detection.displacement_checker import check_displacement
from smc.orchestration.engine import PipelineEngine
from smc.risk.risk_engine import RiskEngine
from smc.triggers.base_trigger import TriggerContext, TriggerSignal
from smc.triggers.trigger_d_two_bar import TwoBarReversalTrigger
from smc.triggers.trigger_router import TriggerRoute
from smc.utils.timestamps import Session

TF = Timeframe.M5
START = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)  # Thursday, London
SESSIONS = (Session.LONDON, Session.NEW_YORK)

CALM = (100.4, 100.6, 100.3, 100.5)          # above the zone — no touch
ENGULFED = (100.5, 100.55, 100.3, 100.4, 500.0)  # prior candle, vol 500
ENGULFER = (100.4, 100.6, 99.9, 100.5, 300.0)    # bullish engulf, vol 300, in zone
CALM_SIGNAL = (100.4, 100.6, 100.3, 100.5)   # Trigger D entry bar
NOFILL = (100.55, 100.7, 100.5, 100.6)       # low above the 100.45 limit — no fill
FILL = (100.3, 100.5, 100.35, 100.45)        # dips to the 100.45 limit only
FILL_LOW = (100.3, 100.5, 99.5, 100.2)       # dips through the 100.0 limit

PATTERN_ROWS = [CALM, ENGULFED, ENGULFER, CALM_SIGNAL]
D_ENTRY = (100.4 + 100.5) / 2.0  # 50% of the engulfing body (frozen §10)
D_STOP = 99.9                    # beyond the two-bar pattern extreme

DISPLACEMENT_PRE = [(100.5, 101.5, 99.5, 100.5)] * 15


def _rows(row, n):
    return [row] * n


def _series(candle_factory, rows, start=START):
    return CandleSeries(
        candle_factory(rows, timeframe=TF, start=start), timeframe=TF
    )


def _candle(ts, row):
    o, h, l, c = row[0], row[1], row[2], row[3]
    volume = float(row[4]) if len(row) > 4 else 0.0
    return Candle(
        timestamp=ts, open=o, high=h, low=l, close=c, volume=volume, timeframe=TF
    )


def _explicit_series(stamps_and_rows):
    """CandleSeries from explicit (timestamp, row) pairs — for tests that
    need non-uniform session timing (e.g. the 20:00+ no-session gap)."""
    return CandleSeries(
        [_candle(ts, row) for ts, row in stamps_and_rows], timeframe=TF
    )


def _fvg_poi(models=None):
    return POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
        models=models or [ModelType.M1],
    )


def _ssl(price):
    return LiquidityLevel(
        type=LiquidityType.EQUAL_HIGHS_LOWS,
        level=price,
        pool=PoolType.SSL,
        timeframe=TF,
    )


def _displacement(candle_factory):
    candles = candle_factory(
        DISPLACEMENT_PRE
        + [
            (99.8, 100.5, 98.2, 99.6),
            (100.0, 102.5, 100.3, 100.8),
            (101.0, 103.5, 102.0, 103.2),
        ]
    )
    return check_displacement(candles, Direction.LONG, sweep_index=15, bos_level=101.2)


def _validated_poi(engine, candle_factory, swing_factory):
    """Run a POI through the REAL merge → validate path (Pillar-2 injected)."""
    candles = candle_factory(
        [(99.5, 99.7, 99.3, 99.6)] * 15
        + [
            (99.9, 100.0, 99.7, 99.9),
            (100.0, 100.1, 99.6, 100.0),
            (100.15, 100.35, 100.2, 100.3),
            (100.3, 100.4, 100.1, 100.35),
        ],
        timeframe=TF,
    )
    swings = [
        swing_factory(candles, 3, True, level=105.0),
        swing_factory(candles, 4, False, level=99.0),
    ]
    poi = _fvg_poi()
    displacement = _displacement(candle_factory)
    passed, _ = engine.validate(
        [poi],
        candles,
        swings,
        [_ssl(100.3)],
        displacement_map={poi.id: displacement},
        merge_first=False,
    )
    assert len(passed) == 1
    return passed[0]


def _trigger_d_route(candle_factory, poi, arm_bar=2):
    """A real Trigger D signal via the trigger's evaluate path.

    The pattern sits INSIDE the [100.0, 100.2] zone: the engulfing candle's
    range overlaps it (the trigger's own requirement) and the signal
    completes on the bar immediately after (frozen §24 D expiry).
    """
    candles = candle_factory(PATTERN_ROWS, timeframe=TF)
    ctx = TriggerContext(poi=poi, candles=candles, swings=[], bar_index=3, from_bar=2)
    signal = TwoBarReversalTrigger().evaluate(ctx)
    assert signal is not None and signal.trigger is TriggerType.D_TWO_BAR_REVERSAL
    return TriggerRoute(poi=poi, bar=3, signal=signal)


def _make_runner(candle_factory, rows, *, config=None):
    return _make_runner_from_series(_series(candle_factory, rows), config=config)


def _make_runner_from_series(series, *, config=None):
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=config or RunnerConfig(allowed_sessions=SESSIONS),
    )
    loop = BarLoop(series, runner)
    return loop, runner


def _attach_pipeline(candle_factory, swing_factory, runner, *, arm_bar=0):
    """Build a REAL engine + validated POI + adapter wired to ``runner``."""
    engine = PipelineEngine()
    poi = _validated_poi(engine, candle_factory, swing_factory)
    engine.arm_at(poi, arm_bar=arm_bar)
    adapter = PipelineAdapter(engine)
    adapter.set_candles(
        candle_factory(PATTERN_ROWS, timeframe=TF, start=START)
    )  # scan universe; per-bar prefix caps keep it honest
    adapter.attach(runner)
    return engine, poi, adapter


# ---------------------------------------------------------------------- #
# Bridge helpers (pure mapping)
# ---------------------------------------------------------------------- #
def test_candidate_from_route_preserves_identity_and_prices(candle_factory):
    poi = _fvg_poi()
    poi.score = 3.0
    route = _trigger_d_route(candle_factory, poi)
    candidate = candidate_from_route(route)
    assert candidate.poi_id == poi.id
    assert candidate.trigger is TriggerType.D_TWO_BAR_REVERSAL
    assert candidate.direction is Direction.LONG
    assert candidate.entry_price == pytest.approx(D_ENTRY)
    assert candidate.sl_price == pytest.approx(D_STOP)
    assert candidate.tp_price is None  # no invented TP
    assert candidate.score == pytest.approx(3.0)
    # §11 event identity string: POI : trigger @ completion bar.
    assert candidate.route_id == (
        f"{poi.id}:{TriggerType.D_TWO_BAR_REVERSAL.value}@3"
    )
    # Trigger D supplies no signal FVG → the bound provider returns None
    # (absent context — never invented geometry).
    assert candidate.fvg_context() is None


def test_fvg_context_absent_for_non_f_trigger(candle_factory):
    # Trigger D carries no signal FVG → context must be ABSENT (never invented).
    route = _trigger_d_route(candle_factory, _fvg_poi())
    assert fvg_context_for_route(route) is None


def test_fvg_context_from_trigger_f_signal_data():
    poi = POI(
        zone=Zone(top=101.0, bottom=100.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M2],
    )
    signal = TriggerSignal(
        trigger=TriggerType.F_BOS_OB,
        direction=Direction.LONG,
        entry_price=100.0,
        stop_reference=99.0,
        completion_index=5,
        expiry_bars=1,
        data={"bos_index": 3, "ob_index": 2, "fvg": {"low": 100.4, "high": 100.9}},
    )
    ctx = fvg_context_for_route(TriggerRoute(poi=poi, bar=5, signal=signal))
    assert ctx is not None and ctx.valid is True
    assert ctx.low == pytest.approx(100.4)
    assert ctx.high == pytest.approx(100.9)
    assert ctx.direction is Direction.LONG


# ---------------------------------------------------------------------- #
# Pipeline path: real detection → risk gate → pending limit
# ---------------------------------------------------------------------- #
def test_synthetic_route_becomes_risk_checked_pending_limit(
    candle_factory, swing_factory
):
    # FULL integrated path: the adapter's own trigger scan finds the real
    # Trigger D pattern; the runner risk-gates it and places the limit.
    # The trailing NOFILL bar keeps the limit resting (low 100.5 > 100.45).
    loop, runner = _make_runner(
        candle_factory, PATTERN_ROWS + [NOFILL]
    )
    engine, poi, adapter = _attach_pipeline(candle_factory, swing_factory, runner)
    runner.set_atr(2.0)
    loop.run()
    assert len(runner.orders) == 1
    order = runner.orders.active()[0]
    assert order.poi_id == poi.id
    assert order.trigger is TriggerType.D_TWO_BAR_REVERSAL
    assert order.volume == pytest.approx(0.10)  # §28.7 policy sizing (capped)
    assert order.entry_price == pytest.approx(D_ENTRY)
    assert order.sl == pytest.approx(D_STOP)
    assert order.comment.endswith(f":{TriggerType.D_TWO_BAR_REVERSAL.value}@3")
    # One-shot consumed by the accepted placement.
    assert poi.id not in adapter._workflows


def test_blocked_risk_decision_places_nothing_and_keeps_one_shot(
    candle_factory, swing_factory
):
    # Bars 0–3 sit in the 20:00–24:00 UTC no-session gap → the risk engine's
    # session gate blocks the entry; the workflow must SURVIVE (one-shot NOT
    # consumed) and fire on the next London bar (next day 09:00 UTC).
    t = lambda day, hour, minute: datetime(  # noqa: E731
        2026, 3, day, hour, minute, tzinfo=timezone.utc
    )
    series = _explicit_series(
        [
            (t(12, 20, 0), CALM),
            (t(12, 20, 5), ENGULFED),
            (t(12, 20, 10), ENGULFER),
            (t(12, 20, 15), CALM_SIGNAL),  # signal bar — blocked (no session)
            (t(13, 9, 0), CALM_SIGNAL),    # Friday London — retry bar
        ]
    )
    loop, runner = _make_runner_from_series(series)
    engine, poi, adapter = _attach_pipeline(candle_factory, swing_factory, runner)
    runner.set_atr(2.0)

    loop.run(end_timestamp=t(12, 20, 15))
    assert len(runner.orders) == 0  # blocked → nothing placed
    assert [b.blocked_by for b in runner.blocked_log] == ["session"]
    assert poi.id in adapter._workflows  # one-shot NOT consumed
    blocked_candidate = adapter._workflows[poi.id].candidate

    # Same workflow retries on the next bar and is accepted in-session.
    # A submit spy proves the SAME candidate object was re-submitted (no
    # re-scan minted a second candidate — §11 one-shot held).
    submitted = []
    original_submit = runner.submit_entry
    runner.submit_entry = lambda c: (submitted.append(c), original_submit(c))
    loop.run(start_timestamp=t(13, 9, 0))
    assert len(runner.orders) == 1
    order = runner.orders.active()[0]
    assert order.poi_id == poi.id
    assert order.entry_price == pytest.approx(D_ENTRY)
    assert submitted and submitted[0] is blocked_candidate  # SAME candidate
    assert poi.id not in adapter._workflows  # consumed by the acceptance
    # Only the original block is logged — the retry entered cleanly.
    assert [b.blocked_by for b in runner.blocked_log] == ["session"]


def test_fill_preserves_poi_trigger_identity_and_fires_on_trade_opened(
    candle_factory, swing_factory
):
    rows = PATTERN_ROWS + [FILL]
    loop, runner = _make_runner(candle_factory, rows)
    engine, poi, adapter = _attach_pipeline(candle_factory, swing_factory, runner)
    runner.set_atr(2.0)
    loop.run()
    assert len(runner.positions) == 1
    position = runner.positions.open_positions()[0]
    assert position.poi_id == poi.id            # identity survives the fill
    assert position.trigger is TriggerType.D_TWO_BAR_REVERSAL
    assert position.entry_price == pytest.approx(D_ENTRY)  # fill AT the limit
    # on_trade_opened re-armed the BE latch for THIS trade.
    assert runner.risk.pure_runner.state.be_moved is False


def test_fvg_context_attached_when_available_absent_when_not(
    candle_factory, swing_factory
):
    # (a) Trigger D through the REAL pipeline: no signal FVG → the fill's
    # context stays ABSENT and FVG invalidation is skipped for that trade.
    rows = PATTERN_ROWS + [FILL, FILL, FILL_LOW]
    loop, runner = _make_runner(candle_factory, rows)
    engine, poi, adapter = _attach_pipeline(candle_factory, swing_factory, runner)
    runner.set_atr(2.0)
    # Bars 0–4: the D workflow routes on bar 3 and fills on bar 4 — its FVG
    # context stays ABSENT (the honest "skip invalidation" state). Bar 5 is
    # the entry step for part (b), whose candidate is submitted BETWEEN runs.
    loop.run(end_timestamp=loop._series.candles[4].timestamp)
    positions_d = [
        p for p in runner.positions.open_positions() if p.poi_id == poi.id
    ]
    assert len(positions_d) == 1
    assert positions_d[0].ticket in runner._sweep_level_by_ticket  # map alive
    assert runner._fvg_by_ticket.get(positions_d[0].ticket) is None

    # (b) A Trigger-F candidate carrying its OWN FVG: the bridge binds the
    # provider, the runner attaches the context at fill time. Submitted
    # before bar 5 (its entry step), it fills on bar 6 (FILL_LOW low 99.5
    # reaches the 100.0 limit).
    poi_b = _fvg_poi([ModelType.M2])
    signal_f = TriggerSignal(
        trigger=TriggerType.F_BOS_OB,
        direction=Direction.LONG,
        entry_price=100.0,
        stop_reference=99.0,
        completion_index=1,
        expiry_bars=20,
        data={"fvg": {"low": 99.5, "high": 99.8}},
    )
    candidate_f = candidate_from_route(TriggerRoute(poi=poi_b, bar=1, signal=signal_f))
    runner.submit_entry(candidate_f)
    loop.run(start_timestamp=loop._series.candles[5].timestamp)  # bar 5 → 6
    positions_b = [
        p for p in runner.positions.open_positions() if p.poi_id == poi_b.id
    ]
    assert len(positions_b) == 1
    ctx = runner._fvg_by_ticket.get(positions_b[0].ticket)
    assert ctx is not None and ctx.valid is True
    assert ctx.low == pytest.approx(99.5) and ctx.high == pytest.approx(99.8)
    assert ctx.direction is Direction.LONG


def test_pipeline_adapter_queues_candidate_on_signal_bar(
    candle_factory, swing_factory
):
    loop, runner = _make_runner(candle_factory, [CALM])
    engine, poi, adapter = _attach_pipeline(candle_factory, swing_factory, runner)
    # Drive the adapter directly on the signal bar (bar 3): the real scan
    # must find the Trigger D pattern and queue exactly one candidate.
    candles = candle_factory(PATTERN_ROWS, timeframe=TF, start=START)
    adapter.set_candles(candles)
    adapter.generate_candidates(candles[3], 3, candles[3].timestamp)
    assert len(runner._pending_entries) == 1
    queued = runner._pending_entries[0]
    assert queued.poi_id == poi.id
    assert queued.trigger is TriggerType.D_TWO_BAR_REVERSAL
    assert queued.direction is Direction.LONG
    assert queued.entry_price == pytest.approx(D_ENTRY)
    # §11 one-shot: the workflow exists and is the SAME candidate object.
    assert adapter._workflows[poi.id].candidate is queued


def test_deterministic_results_on_repeated_runs(candle_factory, swing_factory):
    rows = PATTERN_ROWS + [FILL, FILL]
    results = []
    for _ in range(2):
        loop, runner = _make_runner(candle_factory, rows)
        _attach_pipeline(candle_factory, swing_factory, runner)
        runner.set_atr(2.0)
        loop.run()
        orders = [
            (o.ticket, o.entry_price, o.volume, o.placed_bar, o.sl)
            for o in runner.orders.active()
        ]
        positions = [
            (
                p.ticket,
                p.entry_price,
                p.volume,
                p.trigger,
                p.entry_bar,
                p.sl,
            )
            for p in runner.positions.open_positions()
        ]
        closed = [
            (c.position.ticket, c.exit_price, c.kind, c.win)
            for c in runner.positions.closed_positions()
        ]
        results.append((orders, positions, closed))
    # Mechanics are identical run to run (POI UUIDs are per-run values, so
    # identity STRINGS are deliberately excluded from the comparison).
    assert results[0] == results[1]


# ---------------------------------------------------------------------- #
# C1 audit fix: §23/§24 unfilled-order expiry in the integrated loop
# ---------------------------------------------------------------------- #
def test_resting_limit_expires_by_section23_and_cannot_fill_later(
    candle_factory
):
    """C1: a limit placed on bar 0 rests until bars_open = 12 (M5 §23),
    is cancelled at the START of the 12th bar, and can never fill after —
    even when later bars trade through the entry level."""
    rows = [NOFILL] * 14  # low 100.5 > D_ENTRY 100.45 → never fills
    loop, runner = _make_runner(candle_factory, rows)
    runner.submit_entry(
        CandidateEntry(
            direction=Direction.LONG, entry_price=D_ENTRY, sl_price=D_STOP,
        )
    )
    loop.run(end_timestamp=loop._series.candles[10].timestamp)  # bars 0..10
    assert len(runner.orders) == 1  # bars_open 11 < 12 — still resting
    # Bar 11 only: bars_open 12 → §23 expiry fires at the START of the bar.
    loop.run(
        start_timestamp=loop._series.candles[11].timestamp,
        end_timestamp=loop._series.candles[11].timestamp,
    )
    assert len(runner.orders) == 0  # cancelled before this bar's fills
    assert len(runner.positions) == 0
    # Later bars trading through the limit must NOT fill the cancelled order.
    loop.run(start_timestamp=loop._series.candles[12].timestamp)  # bars 12..13
    assert len(runner.positions) == 0


def test_expired_resting_limit_marks_poi_tested(candle_factory):
    """C1: the POI behind an expired resting limit goes TESTED through the
    state machine (engine authority) — it can never route again."""
    engine = PipelineEngine()
    poi = POI(
        # Zone far below the bars: never touched, never violated → the only
        # way out of FRESH is the §23 expiry itself.
        zone=Zone(top=99.2, bottom=99.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M1],
    )
    engine.arm_at(poi, arm_bar=0)  # CREATED → FRESH, tracked
    rows = [NOFILL] * 14
    loop, runner = _make_runner(candle_factory, rows)
    adapter = PipelineAdapter(engine)
    adapter.set_candles(candle_factory(rows, timeframe=TF, start=START))
    adapter.attach(runner)
    runner.submit_entry(
        CandidateEntry(
            direction=Direction.LONG, entry_price=D_ENTRY, sl_price=D_STOP,
            poi_id=poi.id, trigger=TriggerType.D_TWO_BAR_REVERSAL,
        )
    )
    loop.run(end_timestamp=loop._series.candles[10].timestamp)
    assert len(runner.orders) == 1
    assert poi.state is POIState.FRESH
    loop.run(
        start_timestamp=loop._series.candles[11].timestamp,
        end_timestamp=loop._series.candles[11].timestamp,
    )
    assert len(runner.orders) == 0
    assert poi.state is POIState.TESTED  # §23 drove the POI TESTED
    loop.run(start_timestamp=loop._series.candles[12].timestamp)
    assert len(runner.positions) == 0  # nothing left to fill
