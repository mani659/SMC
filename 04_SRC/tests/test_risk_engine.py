"""Phase 5 — risk engine orchestrator composition tests (entry gates + exits
+ state updates, synthetic state only)."""

from datetime import datetime, timedelta, timezone

import pytest

from smc.config.locked_constants import (
    CIRCUIT_BREAKER_LOSS_COUNT,
    FRIDAY_EOD_CLOSE_HOUR_UTC,
    RISK_PCT_MAX,
)
from smc.core.enums import Direction
from smc.execution.news_guard import NewsEvent
from smc.execution.session_filter import Session
from smc.risk.circuit_breaker import CircuitBreaker
from smc.risk.friday_eod import FridayEod
from smc.risk.fvg_invalidation import (
    FvgContext,
    INVALIDATION_REASON_BEAR_BREACHED,
    INVALIDATION_REASON_BULL_BREACHED,
)
from smc.risk.pure_runner import PureRunner
from smc.risk.spread_grading import effective_max_spread
from smc.risk.risk_engine import (
    BLOCK_CIRCUIT_BREAKER,
    BLOCK_MIN_LOTS,
    BLOCK_NEWS,
    BLOCK_SAME_LEVEL,
    BLOCK_SESSION,
    BLOCK_SPREAD,
    BLOCK_SWEEP,
    EntryRequest,
    PositionState,
    RiskAction,
    RiskEngine,
)
from smc.risk.same_level_guard import SameLevelGuard
from smc.risk.sweep_guard import SweepGuard

T0 = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)  # Monday, London session
ATR = 10.0
ZONE = 0.15 * ATR


def _entry(**overrides) -> EntryRequest:
    base = dict(
        direction=Direction.LONG,
        entry_price=100.0,
        sl_price=95.0,
        atr=ATR,
        current_bar=100,
        now=T0,
        equity=10_000,
        risk_fraction=0.01,
        pip_value_per_lot=10.0,
        min_lots=0.01,
        lot_step=0.01,
        score=8,
        current_spread_price=0.5,  # PRICE units (v25 works in points — convert at the boundary)
    )
    base.update(overrides)
    return EntryRequest(**base)


def _pos(**overrides) -> PositionState:
    base = dict(
        direction=Direction.LONG,
        entry_price=100.0,
        current_sl=95.0,
        atr=ATR,
        current_price=112.0,  # > 1.0×ATR in favour → BE eligible
    )
    base.update(overrides)
    return PositionState(**base)


# --------------------------------------------------------------------------- #
# Entry gates
# --------------------------------------------------------------------------- #
def test_all_gates_pass_returns_enter_with_sized_lots():
    engine = RiskEngine()
    # equity=400 × 1% / (5 × 10) = 0.08 lots — under LOT_MAX_SAFETY so uncapped.
    decision = engine.evaluate_entry(_entry(equity=400))
    assert decision.action is RiskAction.ENTER
    assert decision.lots == pytest.approx(0.08)
    assert decision.blocked_by is None


def test_news_gate_blocks():
    engine = RiskEngine()
    event = NewsEvent(kind="CPI", at=T0 + timedelta(minutes=5))
    decision = engine.evaluate_entry(_entry(news_events=[event]))
    assert decision.action is RiskAction.HOLD
    assert decision.blocked_by == BLOCK_NEWS


def test_session_gate_blocks():
    engine = RiskEngine()
    decision = engine.evaluate_entry(_entry(allowed_sessions=(Session.NEW_YORK,)))
    # T0 is 12:00 UTC = London; NY-only must block.
    assert decision.action is RiskAction.HOLD
    assert decision.blocked_by == BLOCK_SESSION


def test_no_session_gate_when_none():
    engine = RiskEngine()
    decision = engine.evaluate_entry(_entry(allowed_sessions=None))
    assert decision.action is RiskAction.ENTER


def test_circuit_breaker_gate_blocks():
    cb = CircuitBreaker()
    for _ in range(CIRCUIT_BREAKER_LOSS_COUNT):
        cb.record_result(win=False, at=T0)
    engine = RiskEngine(circuit_breaker=cb)
    decision = engine.evaluate_entry(_entry())
    assert decision.action is RiskAction.HOLD
    assert decision.blocked_by == BLOCK_CIRCUIT_BREAKER


def test_same_level_gate_blocks():
    guard = SameLevelGuard()
    guard.record_close(sl_level=100.0, bar_index=99)
    engine = RiskEngine(same_level_guard=guard)
    decision = engine.evaluate_entry(_entry(sl_price=100.0, current_bar=100))
    assert decision.action is RiskAction.HOLD
    assert decision.blocked_by == BLOCK_SAME_LEVEL


def test_sweep_gate_blocks():
    guard = SweepGuard()
    guard.record_failed_sweep(sweep_level=99.5, bar_index=99, is_long=True)
    engine = RiskEngine(sweep_guard=guard)
    decision = engine.evaluate_entry(_entry(sweep_level=99.5, current_bar=100))
    assert decision.action is RiskAction.HOLD
    assert decision.blocked_by == BLOCK_SWEEP


def test_spread_gate_blocks_and_disabled_passes():
    engine_on = RiskEngine()
    decision = engine_on.evaluate_entry(_entry(current_spread_price=10.0))
    assert decision.action is RiskAction.HOLD
    assert decision.blocked_by == BLOCK_SPREAD

    engine_off = RiskEngine(spread_gate_enabled=False)
    decision_off = engine_off.evaluate_entry(_entry(current_spread_price=10.0))
    assert decision_off.action is RiskAction.ENTER


def test_spread_units_are_price_units_with_exact_boundary():
    # ATR=10, score=8 (A+) → allowed = 0.15 × 10 × 1.5 = 2.25 PRICE units.
    # Exactly at the limit passes (v25 blocks only when spread > allowed);
    # one tick above blocks. Proves the field is price units, not points.
    engine = RiskEngine()
    allowed = effective_max_spread(8, ATR)
    assert allowed == pytest.approx(2.25)
    at_limit = engine.evaluate_entry(_entry(score=8, current_spread_price=allowed))
    assert at_limit.action is RiskAction.ENTER
    above = engine.evaluate_entry(_entry(score=8, current_spread_price=allowed + 0.01))
    assert above.blocked_by == BLOCK_SPREAD


def test_zero_atr_skips_spread_gate_and_never_raises():
    # v25 skips the float-spread gate when g_atr <= 0 — a degenerate ATR
    # must produce a decision, not an exception.
    engine = RiskEngine()
    decision = engine.evaluate_entry(
        _entry(atr=0.0, current_spread_price=999.0)
    )
    assert decision.action is RiskAction.ENTER
    assert decision.blocked_by is None


def test_min_lots_blocks_undersized():
    engine = RiskEngine()
    # equity=400 × 1% = $4 risk / ($50 per lot at SL5×pip10) = 0.08 < min_lots 0.1
    decision = engine.evaluate_entry(_entry(equity=400, min_lots=0.1))
    assert decision.action is RiskAction.HOLD
    assert decision.blocked_by == BLOCK_MIN_LOTS


def test_risk_fraction_clamped_into_band():
    engine = RiskEngine()
    # 50% requested → clamped to RISK_PCT_MAX (1%); equity=400 → 0.08 lots.
    decision = engine.evaluate_entry(_entry(equity=400, risk_fraction=0.50))
    assert decision.lots == pytest.approx(0.08)
    assert engine.clamp_risk_fraction(0.50) == pytest.approx(RISK_PCT_MAX / 100.0)


# --------------------------------------------------------------------------- #
# Exits
# --------------------------------------------------------------------------- #
def test_exit_hold_when_nothing_fires():
    engine = RiskEngine()
    decision = engine.evaluate_exit(_pos(current_price=101.0), now=T0)
    assert decision.action is RiskAction.HOLD
    assert decision.reason is None


def test_evaluate_friday_close_fires_once_per_friday():
    engine = RiskEngine()
    friday = datetime(2026, 9, 4, FRIDAY_EOD_CLOSE_HOUR_UTC, 0, tzinfo=timezone.utc)
    assert engine.evaluate_friday_close(friday) is True
    assert engine.evaluate_friday_close(friday) is False  # latch held for the day


def test_evaluate_friday_close_rearms_next_week():
    engine = RiskEngine()
    friday = datetime(2026, 9, 4, FRIDAY_EOD_CLOSE_HOUR_UTC, 0, tzinfo=timezone.utc)
    assert engine.evaluate_friday_close(friday) is True
    # Midweek checks reset the latch (the runner evaluates every bar, so a
    # non-Friday bar always precedes the next Friday):
    assert engine.evaluate_friday_close(friday + timedelta(days=4)) is False
    # Next week's Friday fires again:
    assert engine.evaluate_friday_close(friday + timedelta(days=7)) is True


def test_evaluate_exit_never_consumes_the_friday_latch():
    engine = RiskEngine()
    friday = datetime(2026, 9, 4, FRIDAY_EOD_CLOSE_HOUR_UTC, 0, tzinfo=timezone.utc)
    ctx = FvgContext(valid=True, low=99.0, high=101.0, direction=Direction.LONG)
    # Per-position exit evaluation on Friday 20:00+ must keep producing
    # decisions for EVERY position (the runner closes the book via
    # evaluate_friday_close, not via per-position latching).
    d1 = engine.evaluate_exit(
        _pos(current_price=98.5, closed_close=98.5), now=friday, fvg_context=ctx
    )
    d2 = engine.evaluate_exit(
        _pos(current_price=98.5, closed_close=98.5), now=friday, fvg_context=ctx
    )
    assert d1.action is RiskAction.EXIT
    assert d2.action is RiskAction.EXIT
    assert d1.reason == INVALIDATION_REASON_BULL_BREACHED
    # The portfolio latch is untouched by per-position evaluations:
    assert engine.evaluate_friday_close(friday) is True


def test_fvg_invalidation_long_exits():
    engine = RiskEngine()
    ctx = FvgContext(valid=True, low=99.0, high=101.0, direction=Direction.LONG)
    decision = engine.evaluate_exit(
        _pos(current_price=98.5, closed_close=98.5), now=T0, fvg_context=ctx
    )
    assert decision.action is RiskAction.EXIT
    assert decision.reason == INVALIDATION_REASON_BULL_BREACHED


def test_fvg_invalidation_short_exits():
    engine = RiskEngine()
    ctx = FvgContext(valid=True, low=99.0, high=101.0, direction=Direction.SHORT)
    decision = engine.evaluate_exit(
        _pos(
            direction=Direction.SHORT,
            current_sl=105.0,
            current_price=102.0,
            closed_close=102.0,
        ),
        now=T0,
        fvg_context=ctx,
    )
    assert decision.action is RiskAction.EXIT
    assert decision.reason == INVALIDATION_REASON_BEAR_BREACHED


def test_fvg_uses_closed_bar_close_never_live_price():
    engine = RiskEngine()
    ctx = FvgContext(valid=True, low=99.0, high=101.0, direction=Direction.LONG)
    # Live/tick price pierced below the FVG low intrabar, but the CLOSED
    # bar held above it → hold (v25 iClose(..., 1) semantics).
    decision = engine.evaluate_exit(
        _pos(current_price=98.5, closed_close=100.5), now=T0, fvg_context=ctx
    )
    assert decision.action is RiskAction.HOLD


def test_fvg_check_skipped_without_closed_bar():
    # closed_close=None (no closed bar yet) → the structural test cannot
    # run; the engine must NOT fall back to the live/tick price.
    engine = RiskEngine()
    ctx = FvgContext(valid=True, low=99.0, high=101.0, direction=Direction.LONG)
    decision = engine.evaluate_exit(
        _pos(current_price=98.5), now=T0, fvg_context=ctx
    )
    assert decision.action is RiskAction.HOLD


def test_pure_runner_be_moves_sl():
    engine = RiskEngine()
    decision = engine.evaluate_exit(_pos(), now=T0)  # +12 vs entry, ATR 10 → 1.2×ATR
    assert decision.action is RiskAction.MOVE_SL
    assert decision.reason == "pure_runner_be"
    assert decision.new_sl == pytest.approx(100.0 + 0.10 * ATR)


def test_be_proposal_repeats_until_confirmed():
    engine = RiskEngine()
    first = engine.evaluate_exit(_pos(), now=T0)
    assert first.action is RiskAction.MOVE_SL
    assert first.reason == "pure_runner_be"
    # Pure query: before the runner confirms, the same BE price re-proposes
    # on every bar (retry-friendly after a failed broker modify).
    second = engine.evaluate_exit(_pos(), now=T0)
    assert second.action is RiskAction.MOVE_SL
    assert second.new_sl == pytest.approx(first.new_sl)
    # Runner applies the modify at the broker, then confirms:
    engine.on_be_applied()
    assert engine.evaluate_exit(_pos(), now=T0).action is RiskAction.HOLD


def test_successive_trades_each_get_own_be_opportunity():
    engine = RiskEngine()
    engine.on_trade_opened()  # trade 1 opened
    d1 = engine.evaluate_exit(_pos(), now=T0)
    assert d1.action is RiskAction.MOVE_SL
    engine.on_be_applied()  # trade 1: BE modify confirmed
    assert engine.evaluate_exit(_pos(), now=T0).action is RiskAction.HOLD
    # Trade 2 opens → latch re-armed → BE fires again for the new entry:
    engine.on_trade_opened()
    d2 = engine.evaluate_exit(
        _pos(entry_price=200.0, current_sl=195.0, current_price=212.0), now=T0
    )
    assert d2.action is RiskAction.MOVE_SL
    assert d2.new_sl == pytest.approx(200.0 + 0.10 * ATR)


def test_hard_cancel_pending_fires_inside_pre_news_window():
    engine = RiskEngine()
    event = NewsEvent(kind="CPI", at=T0 + timedelta(minutes=10))
    assert engine.hard_cancel_pending(T0 + timedelta(minutes=10), [event]) is True
    assert engine.hard_cancel_pending(T0 + timedelta(minutes=10), [event]) is True


def test_hard_cancel_pending_quiet_outside_window():
    engine = RiskEngine()
    event = NewsEvent(kind="CPI", at=T0 + timedelta(hours=3))
    assert engine.hard_cancel_pending(T0 + timedelta(hours=1), [event]) is False


def test_hard_cancel_boundary_at_window_edge():
    engine = RiskEngine()
    event = NewsEvent(kind="FOMC", at=T0 + timedelta(minutes=15))
    assert engine.hard_cancel_pending(T0, [event]) is True   # exactly 15 min before
    # One minute closer (14 min before) is still INSIDE the pre-window —
    # the blackout runs from 15 min before until 30 min after the release.
    assert engine.hard_cancel_pending(T0 + timedelta(minutes=1), [event]) is True
    # Only after the re-evaluate horizon (release + 30 min) does it lift:
    assert engine.hard_cancel_pending(event.at + timedelta(minutes=31), [event]) is False


def test_hard_cancel_ignores_low_impact_events():
    engine = RiskEngine()
    event = NewsEvent(kind="PMI", at=T0 + timedelta(minutes=10))
    assert engine.hard_cancel_pending(T0 + timedelta(minutes=10), [event]) is False


# --------------------------------------------------------------------------- #
# State updates → composition across calls
# --------------------------------------------------------------------------- #
def test_record_result_feeds_circuit_breaker():
    engine = RiskEngine()
    for _ in range(CIRCUIT_BREAKER_LOSS_COUNT - 1):
        engine.record_result(win=False, at=T0)
        assert engine.evaluate_entry(_entry()).action is RiskAction.ENTER
    engine.record_result(win=False, at=T0)
    assert engine.evaluate_entry(_entry()).blocked_by == BLOCK_CIRCUIT_BREAKER


def test_record_sl_close_feeds_same_level_guard():
    engine = RiskEngine()
    engine.record_sl_close(sl_level=100.0, bar_index=99)
    decision = engine.evaluate_entry(_entry(sl_price=100.0, current_bar=100))
    assert decision.blocked_by == BLOCK_SAME_LEVEL


def test_record_failed_sweep_feeds_sweep_guard():
    engine = RiskEngine()
    engine.record_failed_sweep(sweep_level=99.5, bar_index=99, is_long=True)
    decision = engine.evaluate_entry(_entry(sweep_level=99.5, current_bar=100))
    assert decision.blocked_by == BLOCK_SWEEP


def test_reset_day_clears_state():
    engine = RiskEngine()
    for _ in range(CIRCUIT_BREAKER_LOSS_COUNT):
        engine.record_result(win=False, at=T0)
    engine.record_sl_close(sl_level=100.0, bar_index=99)
    engine.record_failed_sweep(sweep_level=99.5, bar_index=99, is_long=True)
    # Before the rollover both re-entry guards genuinely block (circuit
    # breaker fires first in gate order, so assert the same-level/sweep
    # guards directly via fresh engines):
    sl_engine = RiskEngine(same_level_guard=engine.same_level_guard)
    assert sl_engine.evaluate_entry(
        _entry(sl_price=100.5, current_bar=100)  # 0.5 ≤ 0.15×ATR zone
    ).blocked_by == BLOCK_SAME_LEVEL
    sweep_engine = RiskEngine(sweep_guard=engine.sweep_guard)
    assert sweep_engine.evaluate_entry(
        _entry(sweep_level=99.5, current_bar=100)
    ).blocked_by == BLOCK_SWEEP
    engine.reset_day()
    assert engine.evaluate_entry(_entry()).action is RiskAction.ENTER
    # Same-level reference MUST be cleared by the rollover (v25 resets
    # g_lastSLLevel): same SL, inside zone + cooldown, passes after reset.
    decision = engine.evaluate_entry(_entry(sl_price=100.5, current_bar=100))
    assert decision.action is RiskAction.ENTER
    assert decision.blocked_by is None
    # Sweep guard MUST be cleared too: the same failed level inside the
    # cooldown would still block if the failure survived the rollover.
    sweep = engine.evaluate_entry(_entry(sweep_level=99.5, current_bar=100))
    assert sweep.action is RiskAction.ENTER
    assert sweep.blocked_by is None