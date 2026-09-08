"""Phase 5 — FVG structural invalidation tests (closed-candle breach)."""

import pytest

from smc.core.enums import Direction
from smc.risk.fvg_invalidation import (
    FvgContext,
    INVALIDATION_REASON_BEAR_BREACHED,
    INVALIDATION_REASON_BULL_BREACHED,
    is_invalidated,
)

BULL_FVG = FvgContext(valid=True, low=100.0, high=101.0, direction=Direction.LONG)
BEAR_FVG = FvgContext(valid=True, low=101.0, high=102.0, direction=Direction.SHORT)


def test_long_invalidated_when_close_below_fvg_low():
    exit_, reason = is_invalidated(BULL_FVG, direction=Direction.LONG, closed_close=99.5)
    assert exit_ is True
    assert reason == INVALIDATION_REASON_BULL_BREACHED


def test_long_not_invalidated_at_or_above_low():
    assert is_invalidated(BULL_FVG, direction=Direction.LONG, closed_close=100.0)[0] is False
    assert is_invalidated(BULL_FVG, direction=Direction.LONG, closed_close=100.5)[0] is False


def test_short_invalidated_when_close_above_fvg_high():
    exit_, reason = is_invalidated(BEAR_FVG, direction=Direction.SHORT, closed_close=102.5)
    assert exit_ is True
    assert reason == INVALIDATION_REASON_BEAR_BREACHED


def test_short_not_invalidated_at_or_below_high():
    assert is_invalidated(BEAR_FVG, direction=Direction.SHORT, closed_close=102.0)[0] is False
    assert is_invalidated(BEAR_FVG, direction=Direction.SHORT, closed_close=101.5)[0] is False


def test_invalid_context_never_exits():
    empty = FvgContext()
    assert is_invalidated(empty, direction=Direction.LONG, closed_close=0.5)[0] is False
    assert is_invalidated(empty, direction=Direction.SHORT, closed_close=150.0)[0] is False


def test_direction_mismatch_raises():
    # Context belongs to the other side → stale snapshot misuse.
    with pytest.raises(ValueError):
        is_invalidated(BULL_FVG, direction=Direction.SHORT, closed_close=99.0)
    with pytest.raises(ValueError):
        is_invalidated(BEAR_FVG, direction=Direction.LONG, closed_close=103.0)


def test_context_without_direction_is_accepted():
    # Contract allows direction=None when the caller keys boundaries itself.
    ctx = FvgContext(valid=True, low=100.0, high=101.0)
    assert is_invalidated(ctx, direction=Direction.LONG, closed_close=99.5)[0] is True
    # SHORT invalidation is close ABOVE high; 100.5 ≤ 101.0 → hold.
    assert is_invalidated(ctx, direction=Direction.SHORT, closed_close=100.5)[0] is False