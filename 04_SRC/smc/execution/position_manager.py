"""Position monitoring + SL/TP management (Phase 4, Stage 4).

DEVELOPMENT_PLAN Phase 4: ``position_manager.py`` — PYTHON DIRECT over the
MT5 connector (``positions_get``), plus SL/TP moves (``TRADE_ACTION_SLTP``,
the cab_watcher ``_modify_sl()`` pattern) and closes (opposite-side DEAL).

Phase 5 owns the risk management that decides WHICH SL/TP/closes to make
(PureRunner, FVG invalidation, Friday EOD); this module executes them and
reports state. Tick/quote precision handling is delegated to the live
connector layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.core.enums import Direction
from smc.execution.order_manager import (
    ORDER_FILLING_IOC,
    ORDER_TYPE_BUY,
    ORDER_TYPE_SELL,
    TRADE_ACTION_DEAL,
    TRADE_ACTION_SLTP,
)

__all__ = ["PositionSnapshot", "PositionManager"]

# Close a LONG by selling (and vice versa).
_CLOSE_TYPE = {Direction.LONG: ORDER_TYPE_SELL, Direction.SHORT: ORDER_TYPE_BUY}


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    """A read-only view of one open position (decoupled from MT5 tuples)."""

    ticket: int
    symbol: str
    direction: Direction
    volume: float
    open_price: float
    sl: float | None = None
    tp: float | None = None


class PositionManager:
    """Monitors and manages positions through a connector."""

    def __init__(self, connector, symbol: str = "XAUUSD.x") -> None:
        self.connector = connector
        self.symbol = symbol

    # ------------------------------------------------------------------ #
    def list_positions(self) -> list[PositionSnapshot]:
        """Current open positions for the symbol, mapped to snapshots."""
        raw = self.connector.positions_get(self.symbol) or []
        snapshots: list[PositionSnapshot] = []
        for position in raw:
            snapshots.append(_snapshot(position))
        return snapshots

    def modify_sl(self, ticket: int, sl: float, symbol: str | None = None) -> bool:
        """Move a position's stop loss (TRADE_ACTION_SLTP).

        The current TP is fetched from the position and re-sent alongside the
        new SL (the cab_watcher ``_modify_sl`` pattern) — the untouched
        protective price is never sent as 0.0, so a TP is never cleared by an
        SL move (and vice versa). Raises ``ValueError`` when the ticket is
        not open (a clobbering request must never be sent blindly).
        """
        position = self._find_position(ticket)
        if position is None:
            raise ValueError(
                f"position ticket {ticket} not found — cannot preserve its TP"
            )
        request = {
            "action": TRADE_ACTION_SLTP,
            "symbol": symbol or self.symbol,
            "position": ticket,
            "sl": sl,
            "tp": position.tp or 0.0,
        }
        result = self.connector.order_send(request)
        return _ok(result)

    def modify_tp(self, ticket: int, tp: float, symbol: str | None = None) -> bool:
        """Move a position's take profit (TRADE_ACTION_SLTP).

        The current SL is fetched from the position and re-sent alongside the
        new TP (the cab_watcher ``_modify_sl`` pattern) — the untouched
        protective price is never sent as 0.0, so an SL is never cleared by a
        TP move (and vice versa). Raises ``ValueError`` when the ticket is
        not open (a clobbering request must never be sent blindly).
        """
        position = self._find_position(ticket)
        if position is None:
            raise ValueError(
                f"position ticket {ticket} not found — cannot preserve its SL"
            )
        request = {
            "action": TRADE_ACTION_SLTP,
            "symbol": symbol or self.symbol,
            "position": ticket,
            "sl": position.sl or 0.0,
            "tp": tp,
        }
        result = self.connector.order_send(request)
        return _ok(result)

    def _find_position(self, ticket: int) -> PositionSnapshot | None:
        """Current snapshot for ``ticket`` (None when the position is not open)."""
        for snapshot in self.list_positions():
            if snapshot.ticket == ticket:
                return snapshot
        return None

    def close_position(
        self, ticket: int, direction: Direction, volume: float, symbol: str | None = None
    ) -> bool:
        """Close a position by sending an opposite-side market DEAL."""
        request = {
            "action": TRADE_ACTION_DEAL,
            "symbol": symbol or self.symbol,
            "volume": volume,
            "type": _CLOSE_TYPE[direction],
            "price": 0.0,
            "type_filling": ORDER_FILLING_IOC,
        }
        result = self.connector.order_send(request)
        return _ok(result)


def _snapshot(position) -> PositionSnapshot:
    """Map an MT5 position object/dict to a :class:`PositionSnapshot`."""
    if isinstance(position, dict):
        get = position.get
    else:
        get = lambda name: getattr(position, name, None)  # noqa: E731
    ticket = int(get("ticket") or 0)
    volume = float(get("volume") or 0.0)
    raw_type = int(get("type") or 0)
    direction = Direction.LONG if raw_type == 0 else Direction.SHORT  # BUY=0
    return PositionSnapshot(
        ticket=ticket,
        symbol=str(get("symbol") or ""),
        direction=direction,
        volume=volume,
        open_price=float(get("price_open") or 0.0),
        sl=float(get("sl")) if get("sl") else None,
        tp=float(get("tp")) if get("tp") else None,
    )


def _ok(result) -> bool:
    retcode = result.retcode if hasattr(result, "retcode") else result.get("retcode", -1)
    return int(retcode) in (10009, 10010)  # TRADE_RETCODE_DONE(_PARTIAL)
