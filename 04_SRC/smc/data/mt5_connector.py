"""Thin wrapper around the MetaTrader5 Python package (direct, no HTTP).

Reference: ``03_REFERENCE_CODE/cab_watcher_v16_3-1.py`` — the reusable MT5
connection + order patterns extracted from it are:

  * lifecycle:  ``mt5.initialize(path=terminal)`` then optional
    ``mt5.login(login, password=password, server=server)``, with
    ``mt5.shutdown()`` on failure (see ``cab_watcher`` ``run_brain()``);
  * requests:   ``order_send()`` with dict keys ``action/position/symbol/
    volume/type/price/deviation/magic/comment/type_time/type_filling``
    (see ``cab_watcher`` ``_close_position()``) and SL/TP modify via
    ``TRADE_ACTION_SLTP`` (see ``_modify_sl()``);
  * guards:     spread checks from ``symbol_info_tick()`` and stops-level
    checks from ``symbol_info()`` before sending orders — to be enforced by
    the Phase 4/5 execution + risk layers, not this connector.

Design: MetaTrader5 is imported lazily so backtesting, CI, and unit tests
never require the package to be installed. **No connection is made at
import time** — call :meth:`MT5Connector.connect` explicitly.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

from smc.config.timeframe import Timeframe

__all__ = ["MT5CallError", "MT5Connector", "MT5NotAvailableError"]

logger = logging.getLogger(__name__)

_DEFAULT_DEVIATION = 20  # max slippage in points (cab_watcher default)


class MT5NotAvailableError(RuntimeError):
    """Raised when the MetaTrader5 package is not installed."""


class MT5CallError(PermissionError):
    """An MT5 operation failed with terminal and operation context."""

    def __init__(
        self,
        operation: str,
        terminal_path: str | None,
        cause: OSError,
    ) -> None:
        self.operation = operation
        self.terminal_path = terminal_path
        self.cause = cause
        super().__init__(
            getattr(cause, "errno", None) or 13,
            f"mt5.{operation} failed for terminal {terminal_path!r}: {cause}",
        )


class MT5Connector:
    """Thin facade over the MetaTrader5 module with connection/error state.

    Method names mirror the underlying MT5 API so the mapping stays obvious.
    ``Timeframe`` values are MT5 ``TIMEFRAME_*`` integers, so passing
    ``int(tf)`` is sufficient — no translation table required.
    """

    def __init__(
        self,
        symbol: str = "XAUUSD.x",
        magic: int = 0,
        deviation: int = _DEFAULT_DEVIATION,
        terminal_path: str | None = None,
    ) -> None:
        self.symbol = symbol
        self.magic = magic
        self.deviation = deviation
        self.terminal_path = terminal_path
        self._connected = False
        self._active_call_errors: dict[str, tuple[str, str]] = {}

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _mt5() -> Any:
        """Lazily import and return the MetaTrader5 module."""
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:  # pragma: no cover - env dependent
            raise MT5NotAvailableError(
                "The MetaTrader5 package is not installed. "
                "Install it with: pip install MetaTrader5"
            ) from exc
        return mt5

    # ------------------------------------------------------------------ #
    # Lifecycle (not called at import — explicit connect only)
    # ------------------------------------------------------------------ #
    def connect(
        self,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
    ) -> bool:
        """Initialize the MT5 terminal and optionally log in.

        Mirrors the cab_watcher pattern: initialize with the terminal path,
        then login when credentials are supplied (auto-login otherwise).
        """
        if self._connected:
            return True
        mt5 = self._mt5()
        logger.info(
            "MT5 initialize attempt terminal_path=%r python_pid=%s",
            self.terminal_path,
            os.getpid(),
        )
        if not self._call("initialize", mt5.initialize, path=self.terminal_path):
            logger.error(
                "MT5 initialize() returned false terminal_path=%r python_pid=%s "
                "last_error=%r",
                self.terminal_path,
                os.getpid(),
                mt5.last_error(),
            )
            return False
        if login is not None and password and server:
            if not self._call(
                "login", mt5.login, login, password=password, server=server
            ):
                logger.error("MT5 login() failed for account %s", login)
                self._call("shutdown", mt5.shutdown)
                return False
        self._connected = True
        return True

    def shutdown(self) -> None:
        """Disconnect from the MT5 terminal."""
        self._call("shutdown", self._mt5().shutdown)
        self._connected = False

    def last_error(self) -> tuple[int, str] | None:
        """Return ``(code, message)`` from the last MT5 call, if any."""
        return self._mt5().last_error()

    def terminal_info(self) -> Any:
        """Return terminal identity and data-folder information."""
        mt5 = self._mt5()
        return self._call("terminal_info", mt5.terminal_info)

    def version(self) -> Any:
        """Return the connected MT5 terminal version."""
        mt5 = self._mt5()
        return self._call("version", mt5.version)

    def symbol_select(self, symbol: str, enable: bool) -> Any:
        """Enable or disable a symbol in Market Watch."""
        mt5 = self._mt5()
        return self._call("symbol_select", mt5.symbol_select, symbol, enable)

    def _call(
        self,
        operation: str,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        try:
            result = fn(*args, **kwargs)
        except OSError as exc:
            signature = (type(exc).__name__, str(exc))
            if self._active_call_errors.get(operation) == signature:
                logger.debug(
                    "Repeated MT5 call failure operation=%s terminal_path=%r "
                    "python_pid=%s error=%r",
                    operation,
                    self.terminal_path,
                    os.getpid(),
                    exc,
                )
            else:
                try:
                    last_error = self._mt5().last_error()
                except OSError as last_error_exc:
                    last_error = f"unavailable: {last_error_exc!r}"
                logger.error(
                    "MT5 call failed operation=%s terminal_path=%r python_pid=%s "
                    "error=%r last_error=%r",
                    operation,
                    self.terminal_path,
                    os.getpid(),
                    exc,
                    last_error,
                    exc_info=True,
                )
            self._active_call_errors[operation] = signature
            if isinstance(exc, PermissionError):
                raise MT5CallError(operation, self.terminal_path, exc) from exc
            raise
        previous = self._active_call_errors.pop(operation, None)
        if previous is not None:
            logger.info(
                "MT5 call recovered operation=%s terminal_path=%r python_pid=%s",
                operation,
                self.terminal_path,
                os.getpid(),
            )
        return result

    # ------------------------------------------------------------------ #
    # Market data
    # ------------------------------------------------------------------ #
    def copy_rates(
        self,
        symbol: str,
        tf: Timeframe,
        start: int,
        count: int,
    ) -> Any:
        """Fetch ``count`` bars ending ``start`` bars before now.

        Wraps ``mt5.copy_rates_from_pos``. Returns a numpy record array
        (        or ``None`` when the MT5 API reports an error. Raised OS failures
        include operation and terminal context in :class:`MT5CallError`.
        """
        mt5 = self._mt5()
        return self._call(
            "copy_rates_from_pos",
            mt5.copy_rates_from_pos,
            symbol,
            int(tf),
            start,
            count,
        )

    def symbol_info(self, symbol: str) -> Any:
        """Return symbol specs (digits, stops level, tick size, ...)."""
        mt5 = self._mt5()
        return self._call("symbol_info", mt5.symbol_info, symbol)

    def symbol_info_tick(self, symbol: str) -> Any:
        """Return the last tick (bid/ask) for a symbol."""
        mt5 = self._mt5()
        return self._call("symbol_info_tick", mt5.symbol_info_tick, symbol)

    # ------------------------------------------------------------------ #
    # Account / positions
    # ------------------------------------------------------------------ #
    def account_info(self) -> Any:
        """Return account info (equity, balance, currency, leverage, ...)."""
        mt5 = self._mt5()
        return self._call("account_info", mt5.account_info)

    def positions_get(self, symbol: str | None = None) -> Any:
        """Return open positions, optionally filtered by symbol."""
        if symbol is None:
            return self._call("positions_get", self._mt5().positions_get)
        return self._call(
            "positions_get", self._mt5().positions_get, symbol=symbol
        )

    # ------------------------------------------------------------------ #
    # Trading (thin pass-through — guards live in execution/risk layers)
    # ------------------------------------------------------------------ #
    def order_send(self, request: dict) -> Any:
        """Send a trade request dict; returns an order result object."""
        request.setdefault("magic", self.magic)
        request.setdefault("deviation", self.deviation)
        return self._call("order_send", self._mt5().order_send, request)

    def order_check(self, request: dict) -> Any:
        """Validate a trade request without sending it."""
        request.setdefault("magic", self.magic)
        request.setdefault("deviation", self.deviation)
        return self._call("order_check", self._mt5().order_check, request)