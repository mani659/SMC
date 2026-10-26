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

from dataclasses import dataclass, field

from smc.config.locked_constants import (
    PURE_RUNNER_BE_ATR,
    PURE_RUNNER_BE_BUFFER_ATR,
)
from smc.core.enums import Direction

__all__ = ["PureRunner", "PureRunnerState"]


@dataclass(slots=True)
class PureRunnerState:
    """Synthetic per-trade state (replayable / unit-testable).

    ``be_moved`` is the v25 single-trade latch (``g_beMoved``). ``latched``
    extends the same one-shot guarantee to CONCURRENT trades (Phase B
    fidelity finding 2026-09-12): v25 was single-position, so the shared
    flag was safe there — a multi-position book must key the latch per
    trade (the runner supplies the position ticket as ``trade_key``) or a
    later fill's ``reset_trade()`` would un-latch an already-moved trade
    and its SL could be BE-modified twice. Keys persist for the trade's
    life; ``forget_trade`` releases them on close (hygiene, not safety).
    """

    be_moved: bool = False  # v25 g_beMoved latch — BE moved once per trade
    latched: set = field(default_factory=set)  # trade_key per BE-moved trade


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
        trade_key=None,
    ) -> float | None:
        """New SL price when the BE move fires, else ``None`` (pure query).

        Price must be ≥ ``be_atr`` × ATR in the trade's direction from
        entry, and the computed BE price must genuinely improve
        ``current_sl`` (longs move SL up, shorts down). Returns ``None``
        when the confirmed latch is set, ATR is non-positive, the move
        threshold is unmet, or the BE price does not improve the SL.

        ``trade_key`` (Phase B fix): the caller's per-trade identity (e.g.
        the position ticket). When supplied, the one-shot latch is checked
        per key so concurrent trades never un-latch each other; without it
        the legacy v25 single-trade flag applies (unchanged behaviour for
        existing callers/tests).

        This call does NOT latch — repeated calls before the broker applies
        return the same price (idempotent). After a successful modify the
        runner must invoke :meth:`mark_be_applied`.
        """
        if trade_key is None:
            if self._state.be_moved:
                return None
        elif trade_key in self._state.latched:
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
    def mark_be_applied(self, trade_key=None) -> None:
        """Confirm the BE modify was applied at the broker — sets the
        one-shot latch (v25 sets ``g_beMoved`` only after a successful
        ``PositionModify``). Until then, :meth:`be_moved_sl` re-proposes
        the same BE price on every evaluation (retry-friendly).

        With ``trade_key`` the latch is recorded per trade so a concurrent
        book keeps every trade's one-shot intact (Phase B fix).
        """
        self._state.be_moved = True
        if trade_key is not None:
            self._state.latched.add(trade_key)

    def reset_trade(self) -> None:
        """Re-arm the BE latch for a NEW trade (v25 resets ``g_beMoved`` on
        every new position) — otherwise trade 2+ would never receive a BE
        move.

        Deliberately does NOT touch ``latched``: a new fill must never
        un-latch another open trade's already-applied BE move (Phase B
        fix — the v25 single-position assumption does not hold for a
        portfolio of concurrent trades).
        """
        self._state.be_moved = False

    def forget_trade(self, trade_key) -> None:
        """Release a closed trade's latch key (hygiene on close; keys are
        never reused within a run, so this is bookkeeping, not safety)."""
        self._state.latched.discard(trade_key)