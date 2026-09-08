"""Phase 5 — FVG structural invalidation (v25_DIAG v22 "Step 3 — FVG
Structural Invalidation", ported to Python).

Hard exit when a CLOSED candle closes beyond the OPPOSITE side of the entry
FVG — the gap that "should have held" has been fully reclaimed, so the
structural premise of the setup is broken (v25: LONG exits when a close
prints below the bull FVG's low; SHORT exits when a close prints above the
bear FVG's high). Early exit beats waiting for price to crawl to the
physical SL.

FVG context contract (:class:`FvgContext`): snapshot the anchoring FVG at
trade open (v25 ``g_activeFVGCtx``) with its boundaries, direction and a
``valid`` flag. ``valid`` is True only while a trade is open against that
FVG; the context is cleared when the position closes.

Pure decision logic only: :func:`is_invalidated` returns True (exit) or
False (hold). The module never calls the broker — the caller (risk engine)
executes the exit. Fully unit-testable with synthetic candles + context.
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.core.enums import Direction

__all__ = ["FvgContext", "is_invalidated", "INVALIDATION_REASON_*"]

# Machine-readable invalidation reasons (for the risk engine's exit log).
INVALIDATION_REASON_BULL_BREACHED = "bull_fvg_low_breached"   # LONG premise dead
INVALIDATION_REASON_BEAR_BREACHED = "bear_fvg_high_breached"  # SHORT premise dead


@dataclass(frozen=True, slots=True)
class FvgContext:
    """Entry-FVG snapshot (v25 ``FVGContext``), captured at trade open."""

    valid: bool = False
    low: float = 0.0
    high: float = 0.0
    direction: Direction | None = None  # direction this FVG belongs to


def is_invalidated(
    ctx: FvgContext,
    *,
    direction: Direction,
    closed_close: float,
) -> tuple[bool, str | None]:
    """(exit?, reason) for a closed candle against the entry FVG.

    v25 semantics: only a closed candle (bar index 1 in v25) counts — the
    caller supplies the close of the just-closed bar. ``valid`` must be True
    (no context → hold). A LONG position is structurally invalidated when
    ``closed_close < ctx.low``; a SHORT when ``closed_close > ctx.high``.
    ``ctx.direction`` (when set) must match the position direction —
    otherwise the snapshot is stale and the caller should not be consulting
    it (raises ``ValueError`` to surface the misuse).
    """
    if not ctx.valid:
        return False, None
    if ctx.direction is not None and ctx.direction is not direction:
        raise ValueError("FVG context direction does not match position direction")
    if direction is Direction.LONG:
        if closed_close < ctx.low:
            return True, INVALIDATION_REASON_BULL_BREACHED
        return False, None
    if direction is Direction.SHORT:
        if closed_close > ctx.high:
            return True, INVALIDATION_REASON_BEAR_BREACHED
        return False, None
    raise ValueError(f"unsupported direction: {direction}")