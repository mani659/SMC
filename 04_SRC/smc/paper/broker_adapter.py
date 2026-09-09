"""Phase 6 M6 — broker adapter: the thin live/paper boundary.

Maps the RiskEngine's pure decisions onto the frozen Phase 4 execution
layer (:class:`~smc.execution.order_manager.OrderManager`,
:class:`~smc.execution.position_manager.PositionManager`). The adapter is
the ONLY place the paper runner touches broker-shaped calls — it holds no
strategy state and makes no decisions:

* accepted entry  → ``OrderManager.place_limit`` (§10: limits only — the
  same frozen ``OrderRequest`` shape the engine's
  ``build_limit_request`` produces);
* BE / SL modify  → ``PositionManager.modify_sl`` — the manager itself
  re-sends the position's untouched TP alongside the new SL, so the
  post-audit rule (an SL move must never clear the TP) is enforced at
  the execution layer, not here;
* exits / Friday EOD → ``PositionManager.close_position`` (opposite-side
  DEAL);
* pendings cancel → ``OrderManager.cancel_order`` (§11 hard-cancel and
  Friday EOD).

Failure policy (M6 constraint: never call ``on_be_applied()`` unless the
modify actually succeeded): every method returns a plain success flag /
``OrderResult`` and RAISES NOTHING on broker failure — the caller checks
the return and only then confirms to the risk engine. Exceptions from the
connector are caught at the OrderManager/PositionManager boundary and
surface as failed results (``OrderManager._send``); the adapter propagates
exactly that verdict.

Call latency: every broker call's wall-clock cost is measured with the
injected ``perf`` source and reported back in the result, so the KPI
logger records decision→ack and management delays without a second
clock read in the runner.
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.core.enums import Direction
from smc.execution.order_manager import OrderManager, OrderRequest, OrderResult
from smc.execution.position_manager import PositionManager

__all__ = ["BrokerAdapter", "PlaceOutcome", "ModifyOutcome"]


@dataclass(frozen=True, slots=True)
class PlaceOutcome:
    """Result of one limit placement attempt."""

    success: bool
    retcode: int
    ticket: int | None = None
    message: str = ""
    latency_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class ModifyOutcome:
    """Result of one broker management op (SL modify / close / cancel)."""

    success: bool
    latency_ms: float = 0.0


class BrokerAdapter:
    """Thin broker boundary — execution calls only, zero decisions."""

    def __init__(self, *, order_manager: OrderManager, position_manager: PositionManager, perf=None) -> None:
        self.orders = order_manager
        self.positions = position_manager
        self._perf = perf  # injected monotonic () -> float (test fake)

    # ------------------------------------------------------------------ #
    # Entries
    # ------------------------------------------------------------------ #
    def place_limit(self, request: OrderRequest) -> PlaceOutcome:
        """Place one pending limit (the only entry path — §10)."""
        start = self._perf() if self._perf else None
        result: OrderResult = self.orders.place_limit(request)
        latency = (self._perf() - start) * 1000.0 if self._perf else 0.0
        return PlaceOutcome(
            success=result.success,
            retcode=result.retcode,
            ticket=result.ticket,
            message=result.message,
            latency_ms=latency,
        )

    def cancel_pending(self, ticket: int) -> ModifyOutcome:
        """Delete a resting pending order."""
        start = self._perf() if self._perf else None
        result: OrderResult = self.orders.cancel_order(ticket)
        latency = (self._perf() - start) * 1000.0 if self._perf else 0.0
        return ModifyOutcome(success=result.success, latency_ms=latency)

    # ------------------------------------------------------------------ #
    # Position management
    # ------------------------------------------------------------------ #
    def modify_sl(self, ticket: int, new_sl: float) -> ModifyOutcome:
        """Move a position's stop (TP preserved by the manager — post-audit)."""
        start = self._perf() if self._perf else None
        try:
            ok = self.positions.modify_sl(ticket, new_sl)
        except ValueError:
            ok = False  # ticket vanished between decision and modify
        latency = (self._perf() - start) * 1000.0 if self._perf else 0.0
        return ModifyOutcome(success=bool(ok), latency_ms=latency)

    def close_position(
        self, ticket: int, direction: Direction, volume: float
    ) -> ModifyOutcome:
        """Close one position by opposite-side market DEAL (exits / EOD)."""
        start = self._perf() if self._perf else None
        try:
            ok = self.positions.close_position(ticket, direction, volume)
        except Exception:  # noqa: BLE001 — broker failure is a verdict, not a crash
            ok = False
        latency = (self._perf() - start) * 1000.0 if self._perf else 0.0
        return ModifyOutcome(success=bool(ok), latency_ms=latency)
