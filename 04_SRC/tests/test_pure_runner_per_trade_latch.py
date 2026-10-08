"""Phase B fidelity regression — §28.1 BE latch must be PER TRADE.

Phase B smoke run (2025-10-01 M1, commit before the fix) observed a ticket
BE-modified TWICE: trade A's BE applied → trade B filled (``reset_trade``
cleared the SHARED v25 ``g_beMoved`` flag) → ATR grew → A re-proposed BE
and the runner modified A's SL again. The plan's Phase B invariant
"BE: ``on_be_applied()`` fires only on a successful (improving) modify;
never twice per trade" was violated by the shared-latch design (v25 was a
single-position EA; the Python runners are not).

The fix keys the one-shot latch by trade identity (the position ticket).
These tests pin the multi-position guarantee AND the legacy single-trade
semantics.
"""

from __future__ import annotations

from smc.core.enums import Direction
from smc.risk.pure_runner import PureRunner, PureRunnerState
from smc.risk.risk_engine import PositionState, RiskEngine


def _propose(runner: PureRunner, *, ticket, entry, current, atr, current_sl=None):
    return runner.be_moved_sl(
        entry_price=entry,
        direction=Direction.LONG,
        atr=atr,
        current_price=current,
        current_sl=current_sl if current_sl is not None else entry,
        trade_key=ticket,
    )


def test_concurrent_trade_fill_cannot_unlatch_applied_be():
    """The Phase B failure shape: A BE-moved; B fills; ATR grows; A must
    NOT re-propose BE (the SL would be modified twice)."""
    runner = PureRunner()

    # Trade A: BE eligible and applied (latch keyed by ticket 101).
    first = _propose(runner, ticket=101, entry=100.0, current=101.5, atr=1.0)
    assert first is not None
    runner.mark_be_applied(101)

    # Trade B opens → the legacy reset fires (shared flag cleared).
    runner.reset_trade()

    # ATR grew; A is still 1× ATR+ in favour. Per-key latch holds → no
    # second proposal for A.
    assert _propose(runner, ticket=101, entry=100.0, current=101.8, atr=1.4) is None

    # Trade B (ticket 102) still gets its OWN BE opportunity after the reset.
    second = _propose(runner, ticket=102, entry=200.0, current=201.5, atr=1.0)
    assert second is not None
    runner.mark_be_applied(102)
    # …and B is latched independently too.
    assert _propose(runner, ticket=102, entry=200.0, current=201.8, atr=1.4) is None


def test_forget_trade_releases_only_that_key():
    runner = PureRunner()
    assert _propose(runner, ticket=1, entry=100.0, current=101.5, atr=1.0) is not None
    runner.mark_be_applied(1)
    assert _propose(runner, ticket=2, entry=100.0, current=101.5, atr=1.0) is not None
    runner.mark_be_applied(2)

    runner.forget_trade(1)
    assert _propose(runner, ticket=1, entry=100.0, current=101.5, atr=1.0) is not None
    # Ticket 2 stays latched.
    assert _propose(runner, ticket=2, entry=100.0, current=101.5, atr=1.0) is None


def test_legacy_single_trade_flag_unchanged_without_key():
    """No trade_key → the v25 shared-flag semantics (existing tests/tests
    upstream of the fix keep their behaviour)."""
    runner = PureRunner()
    legacy = runner.be_moved_sl(
        entry_price=100.0,
        direction=Direction.LONG,
        atr=1.0,
        current_price=101.5,
        current_sl=100.0,
    )
    assert legacy is not None
    runner.mark_be_applied()
    assert (
        runner.be_moved_sl(
            entry_price=100.0,
            direction=Direction.LONG,
            atr=1.4,
            current_price=101.8,
            current_sl=100.1,
        )
        is None
    )
    runner.reset_trade()
    assert (
        runner.be_moved_sl(
            entry_price=100.0,
            direction=Direction.LONG,
            atr=1.4,
            current_price=101.8,
            current_sl=100.1,
        )
        is not None
    )
    # State defaults stay intact (serializable/injectable shape).
    assert PureRunnerState().be_moved is False
    assert PureRunnerState().latched == set()


def test_risk_engine_threads_trade_key_through_exit_hooks():
    """``evaluate_exit`` + ``on_be_applied`` keyed by the runner's ticket:
    a MOVE_SL confirm on trade B must not un-latch trade A."""
    engine = RiskEngine()
    state_a = PositionState(
        direction=Direction.LONG,
        entry_price=100.0,
        current_sl=100.0,
        atr=1.0,
        current_price=101.5,
        closed_close=101.5,
    )
    decision_a = engine.evaluate_exit(state_a, now=None, trade_key=201)
    assert decision_a.action.value == "move_sl"
    engine.on_be_applied(201)

    # Trade B opens (legacy reset fires) → A stays latched per key.
    engine.on_trade_opened()
    decision_again = engine.evaluate_exit(
        PositionState(
            direction=Direction.LONG,
            entry_price=100.0,
            current_sl=100.1,  # A's SL already sits at BE+buffer
            atr=1.4,
            current_price=101.8,
            closed_close=101.8,
        ),
        now=None,
        trade_key=201,
    )
    assert decision_again.action.value == "hold"

    # On close, the runner releases A's key (hygiene hook exists).
    engine.on_trade_closed(201)
    decision_after_close = engine.evaluate_exit(
        PositionState(
            direction=Direction.LONG,
            entry_price=100.0,
            current_sl=100.0,
            atr=1.0,
            current_price=101.5,
            closed_close=101.5,
        ),
        now=None,
        trade_key=201,
    )
    assert decision_after_close.action.value == "move_sl"
