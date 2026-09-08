"""Phase 6 M3 — BacktestRunner composition tests (RiskEngine × M1/M2).

Each test drives a REAL RiskEngine over the M1 BarLoop + M2 stores and
asserts the composition behaviour (not RiskEngine internals — those are
Phase 5 unit-tested).

Row geometry conventions (all UTC, M5 bars, START = Thursday 09:00 London):

* CALM rows sit strictly ABOVE a 100.0 buy limit (low 100.1) and above the
  99.0 SL / below the 104.0 TP — nothing fills or closes on them;
* TOUCH rows dip to low 99.9 → fill a resting 100.0 limit at 100.0;
* RUN-UP rows close 1× ATR (ATR = 2.0) above entry with high < TP → the
  exit step proposes PureRunner BE; TP bars then close the trade.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from smc.backtest.bar_loop import BarHandler, BarLoop
from smc.backtest.data_feed import CandleSeries
from smc.backtest.orders import PendingOrderBook
from smc.backtest.positions import PositionStore
from smc.backtest.runner import BacktestRunner, CandidateEntry, RunnerConfig
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.execution.news_guard import NewsEvent
from smc.risk.fvg_invalidation import FvgContext
from smc.risk.risk_engine import RiskEngine
from smc.utils.timestamps import Session

TF = Timeframe.M5
START = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)  # Thursday, London

SESSIONS = (Session.LONDON, Session.NEW_YORK)
CALM = (100.25, 100.45, 100.1, 100.3)      # low 100.1 — never touches 100.0
TOUCH = (99.9, 100.1, 99.9, 100.0)         # low 99.9 — fills a 100.0 limit
RUN_UP = (103.0, 103.4, 102.9, 103.2)      # close 103.2 = 1.6× ATR over entry
TP_BAR = (104.1, 104.6, 103.9, 104.5)      # high 104.6 — hits a 104.0 TP


def _rows(row, n):
    return [row] * n


def _series(candle_factory, rows, start=START):
    return CandleSeries(candle_factory(rows, timeframe=TF, start=start), timeframe=TF)


def _candle(index, row, start=START):
    stamp = start + timedelta(minutes=5 * index)
    open_, high, low, close = row
    return Candle(timestamp=stamp, open=open_, high=high, low=low, close=close, timeframe=TF)


def _make_runner(candle_factory, rows, *, config=None, risk=None, start=START):
    series = _series(candle_factory, rows, start=start)
    runner = BacktestRunner(
        risk_engine=risk if risk is not None else RiskEngine(),
        order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=config or RunnerConfig(allowed_sessions=SESSIONS),
    )
    loop = BarLoop(series, runner)
    return loop, runner


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


# ---------------------------------------------------------------------- #
# Entry gating + sizing
# ---------------------------------------------------------------------- #
def test_blocked_entry_places_nothing(candle_factory):
    # 13:00 UTC = NY session; LONDON-only config → session block.
    ny_start = datetime(2026, 3, 12, 13, 0, tzinfo=timezone.utc)
    config = RunnerConfig(allowed_sessions=[Session.LONDON])
    loop, runner = _make_runner(
        candle_factory, _rows(CALM, 3), config=config, start=ny_start
    )
    runner.submit_entry(_candidate())
    loop.run()
    assert len(runner.orders) == 0
    assert [b.blocked_by for b in runner.blocked_log] == ["session"]


def test_news_blocked_entry_places_nothing(candle_factory):
    loop, runner = _make_runner(candle_factory, _rows(CALM, 3))
    runner.config.news_events = [NewsEvent(kind="CPI", at=START + timedelta(minutes=5))]
    runner.submit_entry(_candidate())
    loop.run()
    assert len(runner.orders) == 0
    assert [b.blocked_by for b in runner.blocked_log] == ["news"]


def test_allowed_entry_places_pending_limit_with_policy_lots(candle_factory):
    loop, runner = _make_runner(candle_factory, _rows(CALM, 3))
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    assert len(runner.orders) == 1
    order = runner.orders.active()[0]
    assert order.direction is Direction.LONG
    assert order.entry_price == pytest.approx(100.0)
    assert order.sl == pytest.approx(99.0)
    assert order.tp == pytest.approx(104.0)
    # Policy sizing: 10_000 × 1% / (2.0 × 10.0) = 1.0 lots → capped at
    # LOT_MAX_SAFETY (0.10) by the §28.7 policy path (single sizing path).
    assert order.volume == pytest.approx(0.10)


def test_blocked_entry_is_not_retried_within_same_run(candle_factory):
    ny_start = datetime(2026, 3, 12, 13, 0, tzinfo=timezone.utc)
    config = RunnerConfig(allowed_sessions=[Session.LONDON])
    loop, runner = _make_runner(
        candle_factory, _rows(CALM, 3), config=config, start=ny_start
    )
    runner.submit_entry(_candidate())
    loop.run()
    assert len(runner.orders) == 0
    assert len(runner.blocked_log) == 1  # evaluated exactly once


def test_same_sizing_path_used_for_entry_volume(candle_factory):
    # Sub-band risk fraction is clamped UP by the policy layer
    # (0.00001 → RISK_PCT_MIN 0.5%): 100 × 0.005 / (SL 1.0 × 10.0) = 0.05
    # lots (already on the 0.01 grid). The assert pins the CLAMPED
    # (policy) size — the raw 0.00001 fraction would size to ~0.0005 → 0.
    loop, runner = _make_runner(
        candle_factory,
        _rows(CALM, 3),
        config=RunnerConfig(allowed_sessions=SESSIONS, equity=100.0, risk_fraction=0.00001),
    )
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    assert runner.orders.active()[0].volume == pytest.approx(0.05)


# ---------------------------------------------------------------------- #
# Fill → on_trade_opened → BE available on that trade
# ---------------------------------------------------------------------- #
def test_fill_opens_position_at_limit_price(candle_factory):
    rows = _rows(CALM, 2) + [TOUCH]  # bar 2 dips to 99.9 → touch
    loop, runner = _make_runner(candle_factory, rows)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    assert len(runner.orders) == 0  # consumed by the fill
    assert len(runner.positions) == 1
    position = runner.positions.open_positions()[0]
    assert position.entry_price == pytest.approx(100.0)  # limit price, locked
    assert position.volume == pytest.approx(0.10)
    assert position.entry_bar == 2


def test_no_fill_when_bar_never_reaches_limit(candle_factory):
    loop, runner = _make_runner(candle_factory, _rows(CALM, 4))
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    assert len(runner.orders) == 1  # still resting
    assert len(runner.positions) == 0


def test_fill_rearms_be_latch(candle_factory):
    rows = _rows(CALM, 2) + [TOUCH]
    loop, runner = _make_runner(candle_factory, rows)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    position = runner.positions.open_positions()[0]
    # on_trade_opened re-armed the latch → BE opportunity exists NOW.
    new_sl = runner.risk.pure_runner.be_moved_sl(
        entry_price=position.entry_price,
        direction=position.direction,
        atr=2.0,
        current_price=position.entry_price + 2.0,  # 1× ATR in favour
        current_sl=position.sl,
    )
    assert new_sl is not None


def test_be_propose_apply_then_latch_confirmed(candle_factory):
    # Fill on bar 2; bar 3 closes 1.6× ATR in favour (high < TP) → the exit
    # step proposes BE, the runner "applies" it, the latch sets.
    rows = _rows(CALM, 2) + [TOUCH, RUN_UP]
    loop, runner = _make_runner(candle_factory, rows)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    position = runner.positions.open_positions()[0]
    assert position.sl == pytest.approx(100.2)  # entry + 0.10 × ATR buffer
    assert runner.risk.pure_runner.state.be_moved is True
    # Re-proposal returns None (latched) — no double BE.
    assert (
        runner.risk.pure_runner.be_moved_sl(
            entry_price=position.entry_price,
            direction=position.direction,
            atr=2.0,
            current_price=103.2,
            current_sl=position.sl,
        )
        is None
    )


def test_second_trade_gets_its_own_be_opportunity(candle_factory):
    # Trade #1: fill bar 2, BE bar 3, TP close bar 4. Trade #2: placed bar
    # 4 (entry step), fills bar 6 → on_trade_opened re-arms the latch.
    rows = (
        _rows(CALM, 2)
        + [TOUCH, RUN_UP, TP_BAR]      # bars 2–4
        + _rows(CALM, 1)               # bar 5 (rests trade #2's 99.8 limit)
        + [(99.9, 100.3, 99.6, 100.1)] # bar 6: low 99.6 → fills 99.8 limit
    )
    series = _series(candle_factory, rows)
    loop, runner = _make_runner(candle_factory, rows)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run(end_timestamp=series.candles[3].timestamp)  # bars 0–3: BE moved
    assert len(runner.positions.closed_positions()) == 0
    assert runner.risk.pure_runner.state.be_moved is True  # trade #1 latched
    runner.submit_entry(
        _candidate(entry_price=99.8, sl_price=98.8, tp_price=101.5)
    )
    loop.run(start_timestamp=series.candles[4].timestamp)  # bars 4–6
    assert len(runner.positions.closed_positions()) == 1  # trade #1 at TP
    assert len(runner.positions) == 1                     # trade #2 open
    assert runner.risk.pure_runner.state.be_moved is False  # re-armed on fill
    position2 = runner.positions.open_positions()[0]
    assert position2.entry_price == pytest.approx(99.8)  # limit price
    new_sl = runner.risk.pure_runner.be_moved_sl(
        entry_price=position2.entry_price,
        direction=position2.direction,
        atr=2.0,
        current_price=position2.entry_price + 2.0,
        current_sl=position2.sl,
    )
    assert new_sl is not None  # trade #2 has its own BE opportunity


# ---------------------------------------------------------------------- #
# FVG invalidation — closed bar only
# ---------------------------------------------------------------------- #
def test_fvg_invalidation_uses_closed_bar_close(candle_factory):
    # Bull FVG [100.0, 101.0] on a LONG: a bar that WICKS below the low but
    # closes above holds; a bar that CLOSES below exits (at the close).
    rows = (
        _rows(CALM, 1)
        + [TOUCH]                        # bar 1: fill at 100.0
        + [(100.2, 100.6, 99.7, 100.5)]  # bar 2: wick below, close 100.5 → HOLD
        + [(100.2, 100.6, 99.7, 99.8)]   # bar 3: close 99.8 < 100.0 → EXIT
    )
    series = _series(candle_factory, rows)
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=RunnerConfig(allowed_sessions=SESSIONS),
    )
    runner.set_fvg_context(1, FvgContext(valid=True, low=100.0, high=101.0, direction=Direction.LONG))
    loop = BarLoop(series, runner)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate(tp_price=None))
    loop.run()
    closed = runner.positions.closed_positions()
    assert len(closed) == 1
    assert closed[0].kind == "bull_fvg_low_breached"  # FVG reason, not SL/TP
    assert closed[0].exit_price == pytest.approx(99.8)  # the CLOSED close
    assert closed[0].win is False


def test_fvg_wick_only_bar_does_not_exit(candle_factory):
    rows = (
        _rows(CALM, 1)
        + [TOUCH]                        # bar 1: fill
        + [(100.2, 100.6, 99.7, 100.5)]  # bar 2: wick below low, close above
        + [(100.2, 100.6, 99.7, 100.5)]  # bar 3: same
    )
    series = _series(candle_factory, rows)
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=RunnerConfig(allowed_sessions=SESSIONS),
    )
    runner.set_fvg_context(1, FvgContext(valid=True, low=100.0, high=101.0, direction=Direction.LONG))
    loop = BarLoop(series, runner)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate(tp_price=None))
    loop.run()
    assert len(runner.positions) == 1  # held through both wick-only bars


def test_no_fvg_context_means_no_fvg_exit(candle_factory):
    rows = (
        _rows(CALM, 1)
        + [TOUCH]
        + [(100.2, 100.6, 99.7, 99.8)] * 3  # closes below any plausible FVG low
    )
    loop, runner = _make_runner(candle_factory, rows)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate(tp_price=None))
    loop.run()
    # No FvgContext → FVG check skipped → position still open (SL 99.0
    # never touched: bar lows 99.7 > 99.0).
    assert len(runner.positions) == 1


# ---------------------------------------------------------------------- #
# Friday EOD + news hard-cancel
# ---------------------------------------------------------------------- #
def test_friday_eod_closes_all_and_cancels_pending(candle_factory):
    rows = _rows(CALM, 1) + [TOUCH]  # bar 1: fill (Thursday)
    series = _series(candle_factory, rows)
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=RunnerConfig(allowed_sessions=SESSIONS),
    )
    loop = BarLoop(series, runner)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run(end_timestamp=series.candles[1].timestamp)  # bars 0–1
    assert len(runner.positions) == 1
    # One more resting pending, then the Friday 20:00 bar.
    runner.orders.place(
        direction=Direction.LONG, entry_price=98.0, sl=97.0, tp=None,
        volume=0.1, placed_bar=2, placed_at=series.candles[1].timestamp,
    )
    friday = datetime(2026, 3, 13, 20, 0, tzinfo=timezone.utc)
    friday_bar = replace(_candle(2, CALM), timestamp=friday)
    # The runner reads time from the CLOCK — advance it to the Friday bar
    # exactly as the M1 loop would before calling on_bar.
    loop.clock.advance(friday)
    runner.on_bar(friday_bar, 2, loop.clock)
    assert runner.positions.open_positions() == []  # position force-closed
    closed_kinds = [r.kind for r in runner.positions.closed_positions()]
    assert "friday_eod" in closed_kinds
    assert runner.orders.active() == []             # pending cancelled


def test_news_hard_cancel_clears_pending_only(candle_factory):
    series = _series(candle_factory, _rows(CALM, 4))
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=RunnerConfig(allowed_sessions=SESSIONS),
    )
    loop = BarLoop(series, runner)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run(end_timestamp=series.candles[2].timestamp)  # bars 0–2: resting
    assert len(runner.orders) == 1
    # NFP 10 minutes ahead of bar 3 → §11 hard-cancel window on bar 3.
    runner.config.news_events = [
        NewsEvent(kind="NFP", at=series.candles[3].timestamp + timedelta(minutes=10))
    ]
    loop.run(start_timestamp=series.candles[3].timestamp)
    assert runner.orders.active() == []  # hard-cancelled


# ---------------------------------------------------------------------- #
# State updates
# ---------------------------------------------------------------------- #
def test_trade_close_records_result_and_sl_level(candle_factory):
    rows = (
        _rows(CALM, 2)
        + [TOUCH]                        # bar 2: fill
        + [(98.8, 100.4, 98.7, 100.0)]   # bar 3: SL 99.0 hit
    )
    loop, runner = _make_runner(candle_factory, rows)
    runner.set_atr(2.0)
    runner.submit_entry(_candidate())
    loop.run()
    record = runner.positions.closed_positions()[0]
    assert record.win is False
    assert record.kind == "stop_loss"
    # Circuit breaker saw the loss; same-level guard saw the SL level.
    assert runner.risk.circuit_breaker.state.consecutive_losses == 1
    assert runner.risk.same_level_guard.state.last_sl_level == pytest.approx(99.0)


def test_date_change_triggers_reset_day(candle_factory):
    # Bar 0: Thursday 23:55 UTC; bar 1: Friday 00:00 UTC → reset_day fires.
    late = datetime(2026, 3, 12, 23, 55, tzinfo=timezone.utc)
    rows = [(100.0, 100.2, 99.8, 100.0), (100.0, 100.2, 99.8, 100.0)]
    loop, runner = _make_runner(
        candle_factory, rows, config=RunnerConfig(allowed_sessions=None), start=late
    )
    # Seed a 3-loss breaker state on "Thursday", then cross midnight.
    runner.risk.record_result(win=False, at=late)
    runner.risk.record_result(win=False, at=late)
    runner.risk.record_result(win=False, at=late)
    assert runner.risk.circuit_breaker.state.consecutive_losses == 3
    loop.run()
    assert runner.risk.circuit_breaker.state.consecutive_losses == 0  # reset


# ---------------------------------------------------------------------- #
# Determinism
# ---------------------------------------------------------------------- #
def test_identical_inputs_produce_identical_outcomes(candle_factory):
    rows = _rows(CALM, 2) + [TOUCH, RUN_UP, TP_BAR]

    def one_run():
        loop, runner = _make_runner(candle_factory, rows)
        runner.set_atr(2.0)
        runner.submit_entry(_candidate())
        loop.run()
        return (
            [
                (r.position.ticket, r.position.entry_price, r.exit_price, r.kind, r.win)
                for r in runner.positions.closed_positions()
            ],
            len(runner.orders),
            [b.blocked_by for b in runner.blocked_log],
        )

    assert one_run() == one_run()


def test_runner_is_a_bar_handler_and_loop_drives_it(candle_factory):
    loop, runner = _make_runner(candle_factory, _rows(CALM, 2))
    assert isinstance(runner, BarHandler)
    loop.run()
    assert loop.stats.bars_processed == 2
