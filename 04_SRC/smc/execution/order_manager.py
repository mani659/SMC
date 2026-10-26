"""Order placement / cancel via the MT5 connector (Phase 4, Stage 4).

DEVELOPMENT_PLAN Phase 4: ``order_manager.py`` — PYTHON DIRECT, methods
``place_limit / place_market / cancel_order / modify_order`` using the thin
``smc.data.mt5_connector.MT5Connector`` (no HTTP bridge).

REQUEST MAPPING: the numeric action/order/time/filling values below are the
MetaTrader5 Python package constants (stable public API — the same parity
convention as ``smc.config.timeframe.Timeframe`` holding the MT5
``TIMEFRAME_*`` integers). Requests are built here so trading logic never
touches raw MT5 dicts.

ORDER TYPE POLICY (frozen): ALL six LTF triggers are LIMIT entries —
Trigger D is frozen at 50% of the engulfing body and is NEVER a market
order (§10); Model 8 entry is a limit inside the HTF zone (R1 §7). The
router/engine therefore only ever builds limit requests; ``place_market``
exists for the (Phase 5) risk-controlled exits and is NOT reachable from
trigger routing (defended in tests).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from smc.core.enums import Direction

__all__ = ["OrderManager", "OrderKind", "OrderRequest", "OrderResult"]

# --- MT5 API enum parity (MetaTrader5 Python package, stable public API) ---
TRADE_ACTION_DEAL = 1      # market order (immediate fill)
TRADE_ACTION_PENDING = 5   # pending order (limit/stop)
TRADE_ACTION_SLTP = 6      # modify SL/TP of a position
TRADE_ACTION_REMOVE = 7    # delete a pending order
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_LIMIT = 2
ORDER_TYPE_SELL_LIMIT = 3
ORDER_TIME_GTC = 0         # good-till-cancelled
ORDER_FILLING_RETURN = 2   # RETURN — partial fills OK (XAUUSD pending)
ORDER_FILLING_IOC = 1      # immediate-or-cancel (market closes)
TRADE_RETCODE_PLACED = 10008        # order placed (pending)
TRADE_RETCODE_DONE = 10009          # request executed (market)
TRADE_RETCODE_DONE_PARTIAL = 10010  # request executed partially


class OrderKind(Enum):
    """Order class: a resting LIMIT or an immediate MARKET execution."""

    LIMIT = "limit"
    MARKET = "market"


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """A semantic order request (independent of the MT5 dict shape)."""

    symbol: str
    kind: OrderKind
    direction: Direction
    volume: float
    price: float = 0.0          # limit price (0.0 for market)
    sl: float | None = None
    tp: float | None = None
    comment: str = ""


@dataclass(frozen=True, slots=True)
class OrderResult:
    """Outcome of one order_send call (parsed from the MT5 result object)."""

    success: bool
    retcode: int
    ticket: int | None = None
    message: str = ""

    @property
    def placed(self) -> bool:
        return self.success and self.ticket is not None


def _limit_type(direction: Direction) -> int:
    return ORDER_TYPE_BUY_LIMIT if direction is Direction.LONG else ORDER_TYPE_SELL_LIMIT


def _market_type(direction: Direction) -> int:
    return ORDER_TYPE_BUY if direction is Direction.LONG else ORDER_TYPE_SELL


class OrderManager:
    """Places/cancels orders through a connector implementing order_send."""

    def __init__(self, connector, symbol: str = "XAUUSD.x", magic: int = 0) -> None:
        self.connector = connector
        self.symbol = symbol
        self.magic = magic

    # ------------------------------------------------------------------ #
    def place_limit(self, request: OrderRequest) -> OrderResult:
        """Rest a limit order (Trigger D policy: limits only — see module doc)."""
        if request.kind is not OrderKind.LIMIT:
            raise ValueError("place_limit requires an OrderKind.LIMIT request")
        mt5_request = {
            "action": TRADE_ACTION_PENDING,
            "symbol": request.symbol or self.symbol,
            "volume": request.volume,
            "type": _limit_type(request.direction),
            "price": request.price,
            "sl": request.sl if request.sl is not None else 0.0,
            "tp": request.tp if request.tp is not None else 0.0,
            "type_time": ORDER_TIME_GTC,
            "type_filling": ORDER_FILLING_RETURN,
            "magic": self.magic,
            "comment": request.comment,
        }
        return self._send(mt5_request)

    def place_market(self, request: OrderRequest) -> OrderResult:
        """Immediate market execution (risk-controlled exits only — never a trigger entry)."""
        if request.kind is not OrderKind.MARKET:
            raise ValueError("place_market requires an OrderKind.MARKET request")
        mt5_request = {
            "action": TRADE_ACTION_DEAL,
            "symbol": request.symbol or self.symbol,
            "volume": request.volume,
            "type": _market_type(request.direction),
            "price": request.price if request.price else 0.0,
            "sl": request.sl if request.sl is not None else 0.0,
            "tp": request.tp if request.tp is not None else 0.0,
            "type_filling": ORDER_FILLING_RETURN,
            "magic": self.magic,
            "comment": request.comment,
        }
        return self._send(mt5_request)

    def cancel_order(self, ticket: int) -> OrderResult:
        """Delete a resting pending order by ticket (action REMOVE)."""
        return self._send(
            {"action": TRADE_ACTION_REMOVE, "order": ticket, "magic": self.magic}
        )

    def modify_order(self, ticket: int, request: OrderRequest) -> OrderResult:
        """V1 order modification = cancel + re-place with the new parameters.

        Documented V1: MT5 has no single-call 'modify pending' action in the
        Python package for arbitrary parameter changes; cancel + re-place is
        deterministic and testable. Position SL/TP moves live on
        ``smc.execution.position_manager`` (action SLTP).
        """
        if request.kind is not OrderKind.LIMIT:
            raise ValueError("modify_order only re-places LIMIT orders")
        cancel = self.cancel_order(ticket)
        if not cancel.success:
            return cancel
        return self.place_limit(request)

    # ------------------------------------------------------------------ #
    def _send(self, mt5_request: dict) -> OrderResult:
        try:
            raw = self.connector.order_send(mt5_request)
        except Exception as exc:  # connector/mock failures surface as rejects
            return OrderResult(success=False, retcode=-1, message=str(exc))
        return _parse_result(raw)


_SUCCESS_RETCODES = frozenset(
    {TRADE_RETCODE_PLACED, TRADE_RETCODE_DONE, TRADE_RETCODE_DONE_PARTIAL}
)


def _parse_result(raw) -> OrderResult:
    """Parse an MT5 order result object (or a plain mapping in tests)."""
    if isinstance(raw, dict):
        retcode = int(raw.get("retcode", -1))
        comment = str(raw.get("comment", ""))
        ticket_raw = raw.get("order")
    else:
        retcode = int(getattr(raw, "retcode", -1))
        comment = str(getattr(raw, "comment", ""))
        ticket_raw = getattr(raw, "order", None)
    ticket = int(ticket_raw) if ticket_raw not in (None, 0) else None
    return OrderResult(
        success=retcode in _SUCCESS_RETCODES,
        retcode=retcode,
        ticket=ticket,
        message=comment,
    )
