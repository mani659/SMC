"""Phase 5 — PureRunner (v25_DIAG BE-at-ATR logic, ported to Python).

LOCKED_DECISIONS §28.1: move the stop-loss to break-even when price has
moved ``PURE_RUNNER_BE_ATR`` (1.0) × ATR in the trade's favour, with a
``PURE_RUNNER_BE_BUFFER_ATR`` (0.10) buffer so BE sits slightly better than
scratch. V1: NO early partials — the position runs to its TP; this module
only manages the BE move.

v25_DIAG semantics preserved verbatim (``ManageExits`` Phase 1 / v24 RC2
ATR-triggered BE):

* the ATR-multiple is measured from ENTRY: ``rr = (price - entry) × dir /
  atr`` and BE is eligible when ``rr >= PURE_RUNNER_BE_ATR``;
* the BE price is ``entry + dir × PURE_RUNNER_BE_BUFFER_ATR × atr``
  (v25: ``en + dir * g_atr * InpBEBuffer``);
* the move only fires when it actually improves the current SL
  (``bePrice > csl`` for longs, ``bePrice < csl`` for shorts);
* the latch is CONFIRMATION-based (v25 sets ``g_beMoved`` only inside the
  successful ``PositionModify`` branch): :meth:`PureRunner.be_moved_sl` is
  a pure, idempotent query and never sets the latch itself — the runner
  applies the modify at the broker and then confirms via
  :meth:`PureRunner.mark_be_applied`; :meth:`PureRunner.reset_trade`
  re-arms the latch for the next trade (v25 resets ``g_beMoved`` on every
  new position).

Pure decision logic: :meth:`PureRunner.be_moved_sl` returns the NEW SL price
or ``None`` (no move). The module never calls the broker — the caller (risk
engine) applies the returned SL. Fully unit-testable with synthetic
price/ATR/position state (:class:`PureRunnerState` may be injected).
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.config.locked_constants import (
    PURE_RUNNER_BE_ATR,
    PURE_RUNNER_BE_BUFFER_ATR,
)
from smc.core.enums import Direction

__all__ = ["PureRunner", "PureRunnerState"]


@dataclass(slots=True)
class PureRunnerState:
    """Synthetic per-trade state (replayable / unit-testable)."""

    be_moved: bool = False  # v25 g_beMoved latch — BE moved once per trade


class PureRunner:
    """Break-even-at-ATR exit manager (LOCKED_DECISIONS §28.1).

    Thresholds are imported from ``locked_constants`` — zero hardcoding.
    """

    def __init__(
        self,
        *,
        be_atr: float = PURE_RUNNER_BE_ATR,
        be_buffer_atr: float = PURE_RUNNER_BE_BUFFER_ATR,
        state: PureRunnerState | None = None,
    ) -> None:
        self.be_atr = be_atr
        self.be_buffer_atr = be_buffer_atr
        self._state = state if state is not None else PureRunnerState()

    @property
    def state(self) -> PureRunnerState:
        """Read-only handle on the runner's synthetic state."""
        return self._state

    def be_moved_sl(
        self,
        *,
        entry_price: float,
        direction: Direction,
        atr: float,
        current_price: float,
        current_sl: float,
    ) -> float | None:
        """New SL price when the BE move fires, else ``None`` (pure query).

        Price must be ≥ ``be_atr`` × ATR in the trade's direction from
        entry, and the computed BE price must genuinely improve
        ``current_sl`` (longs move SL up, shorts down). Returns ``None``
        when the confirmed latch is set, ATR is non-positive, the move
        threshold is unmet, or the BE price does not improve the SL.

        This call does NOT latch — repeated calls before the broker applies
        return the same price (idempotent). After a successful modify the
        runner must invoke :meth:`mark_be_applied`.
        """
        if self._state.be_moved:
            return None
        if atr <= 0.0:
            return None
        direction_sign = 1.0 if direction is Direction.LONG else -1.0
        rr = (current_price - entry_price) * direction_sign / atr
        if rr < self.be_atr:
            return None
        be_price = entry_price + direction_sign * self.be_buffer_atr * atr
        # Only move if it actually improves the current SL (v25 shouldMove).
        if direction is Direction.LONG and be_price <= current_sl:
            return None
        if direction is Direction.SHORT and be_price >= current_sl:
            return None
        return be_price

    # ------------------------------------------------------------------ #
    # Lifecycle (runner-confirmed handshake)
    # ------------------------------------------------------------------ #
    def mark_be_applied(self) -> None:
        """Confirm the BE modify was applied at the broker — sets the
        one-shot latch (v25 sets ``g_beMoved`` only after a successful
        ``PositionModify``). Until then, :meth:`be_moved_sl` re-proposes
        the same BE price on every evaluation (retry-friendly)."""
        self._state.be_moved = True

    def reset_trade(self) -> None:
        """Re-arm the BE latch for a NEW trade (v25 resets ``g_beMoved`` on
        every new position) — otherwise trade 2+ would never receive a BE
        move."""
        self._state.be_moved = False