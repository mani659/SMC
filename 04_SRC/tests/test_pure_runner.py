"""Phase 5 — PureRunner tests (BE at 1.0×ATR + 0.10 buffer, one-shot)."""

import pytest

from smc.config.locked_constants import (
    PURE_RUNNER_BE_ATR,
    PURE_RUNNER_BE_BUFFER_ATR,
)
from smc.core.enums import Direction
from smc.risk.pure_runner import PureRunner, PureRunnerState

ATR = 10.0
ENTRY = 100.0


def test_no_move_before_threshold():
    runner = PureRunner()
    sl = runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=ATR,
        current_price=ENTRY + 0.9 * PURE_RUNNER_BE_ATR * ATR,
        current_sl=95.0,
    )
    assert sl is None
    assert runner.state.be_moved is False


def test_long_be_price_at_threshold():
    runner = PureRunner()
    sl = runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=ATR,
        current_price=ENTRY + PURE_RUNNER_BE_ATR * ATR,  # exactly 1.0×ATR
        current_sl=95.0,
    )
    expected = ENTRY + PURE_RUNNER_BE_BUFFER_ATR * ATR
    assert sl == pytest.approx(expected)
    # Pure query: the decision does NOT latch — only mark_be_applied does.
    assert runner.state.be_moved is False
    runner.mark_be_applied()
    assert runner.state.be_moved is True


def test_short_be_price_at_threshold():
    runner = PureRunner()
    sl = runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.SHORT, atr=ATR,
        current_price=ENTRY - PURE_RUNNER_BE_ATR * ATR,
        current_sl=105.0,
    )
    expected = ENTRY - PURE_RUNNER_BE_BUFFER_ATR * ATR
    assert sl == pytest.approx(expected)
    # Pure query: the decision does NOT latch — only mark_be_applied does.
    assert runner.state.be_moved is False
    runner.mark_be_applied()
    assert runner.state.be_moved is True


def test_be_only_improves_sl_for_long():
    runner = PureRunner()
    # Current SL already above the BE price → no move (v25 shouldMove).
    sl = runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=ATR,
        current_price=ENTRY + PURE_RUNNER_BE_ATR * ATR,
        current_sl=ENTRY + PURE_RUNNER_BE_BUFFER_ATR * ATR + 0.5,
    )
    assert sl is None
    assert runner.state.be_moved is False


def test_be_only_improves_sl_for_short():
    runner = PureRunner()
    sl = runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.SHORT, atr=ATR,
        current_price=ENTRY - PURE_RUNNER_BE_ATR * ATR,
        current_sl=ENTRY - PURE_RUNNER_BE_BUFFER_ATR * ATR - 0.5,
    )
    assert sl is None
    assert runner.state.be_moved is False


def test_query_is_pure_until_applied_then_latches():
    runner = PureRunner()
    first = runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=ATR,
        current_price=ENTRY + PURE_RUNNER_BE_ATR * ATR,
        current_sl=95.0,
    )
    assert first is not None
    # Pure decision: repeated queries before the broker apply are idempotent
    # and do NOT latch (v25 sets g_beMoved only on successful PositionModify).
    assert runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=ATR,
        current_price=ENTRY + 3 * ATR, current_sl=95.0,
    ) == first
    assert runner.state.be_moved is False
    # Runner applies the modify at the broker, then confirms:
    runner.mark_be_applied()
    assert runner.state.be_moved is True
    assert runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=ATR,
        current_price=ENTRY + 3 * ATR, current_sl=95.0,
    ) is None  # never moves twice for the same trade


def test_reset_trade_rearms_for_next_trade():
    runner = PureRunner()
    assert runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=ATR,
        current_price=ENTRY + PURE_RUNNER_BE_ATR * ATR, current_sl=95.0,
    ) is not None
    runner.mark_be_applied()
    assert runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=ATR,
        current_price=ENTRY + 3 * ATR, current_sl=95.0,
    ) is None
    # New trade → latch re-armed → trade 2 gets its own BE opportunity:
    runner.reset_trade()
    assert runner.state.be_moved is False
    assert runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=ATR,
        current_price=ENTRY + PURE_RUNNER_BE_ATR * ATR, current_sl=95.0,
    ) is not None


def test_negative_profit_no_move():
    runner = PureRunner()
    sl = runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=ATR,
        current_price=ENTRY - 1.0,
        current_sl=95.0,
    )
    assert sl is None


def test_zero_atr_no_move():
    runner = PureRunner()
    sl = runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=0.0,
        current_price=ENTRY + 5.0, current_sl=95.0,
    )
    assert sl is None


def test_replayable_with_injected_state():
    state = PureRunnerState(be_moved=True)
    runner = PureRunner(state=state)
    sl = runner.be_moved_sl(
        entry_price=ENTRY, direction=Direction.LONG, atr=ATR,
        current_price=ENTRY + 5 * ATR, current_sl=95.0,
    )
    assert sl is None  # latch already set