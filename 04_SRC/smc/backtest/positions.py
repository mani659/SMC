"""Backtest open-position store (Phase 6, Milestone 2).

Tracks open positions produced by pending-limit fills and applies the
:mod:`smc.backtest.fill_model` close decisions (SL/TP, SL-first rule).
Pure in-memory bookkeeping — no MT5, no risk decisions (the later runner
decides WHEN to consult the fill model; this store applies the outcome).

Determinism contract: positions are keyed by a monotonically increasing
ticket sequence (same generator style as :class:`PendingOrderBook`);
iteration order is fill order. ``BacktestPosition`` mirrors the live
``PositionSnapshot`` shape (``smc.execution.position_manager``) plus
backtest bookkeeping (entry bar/time, originating POI/trigger).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from smc.backtest.fill_model import BarClose, evaluate_position_bar
from smc.core.candle import Candle
from smc.core.enums import Direction

__all__ = ["BacktestPosition", "ClosedPosition", "PositionStore"]


@dataclass(frozen=True, slots=True)
class BacktestPosition:
    """One open backtest position (mirrors the live snapshot shape)."""

    ticket: int
    direction: Direction
    volume: float
    entry_price: float       # the limit fill price
    sl: float | None
    tp: float | None
    entry_bar: int
    entry_at: object         # injected UTC datetime (fill bar timestamp)
    symbol: str = ""
    poi_id: str | None = None
    trigger: object | None = None


@dataclass(frozen=True, slots=True)
class ClosedPosition:
    """A closed position + its close metadata (trade-log entry)."""

    position: BacktestPosition
    exit_price: float
    exit_bar: int
    exit_at: object
    kind: str                # CloseKind.STOP_LOSS / TAKE_PROFIT
    win: bool
    realized_pnl: float      # price units × volume × direction sign (V1 raw)


@dataclass(slots=True)
class PositionStore:
    """In-memory open-position store for the backtest."""

    first_ticket: int = 1
    _open: list[BacktestPosition] = field(default_factory=list)
    _closed: list[ClosedPosition] = field(default_factory=list)
    _next_ticket: int | None = None

    def __post_init__(self) -> None:
        if self._next_ticket is None:
            self._next_ticket = self.first_ticket

    # ------------------------------------------------------------------ #
    # Opening
    # ------------------------------------------------------------------ #
    def open(
        self,
        *,
        direction: Direction,
        volume: float,
        entry_price: float,
        sl: float | None,
        tp: float | None,
        entry_bar: int,
        entry_at,
        symbol: str = "",
        poi_id: str | None = None,
        trigger=None,
    ) -> BacktestPosition:
        """Open one position on a fill; returns it (ticket pre-assigned)."""
        if volume <= 0.0:
            raise ValueError("position volume must be positive")
        position = BacktestPosition(
            ticket=self._next_ticket,
            direction=direction,
            volume=volume,
            entry_price=entry_price,
            sl=sl,
            tp=tp,
            entry_bar=entry_bar,
            entry_at=entry_at,
            symbol=symbol,
            poi_id=poi_id,
            trigger=trigger,
        )
        self._next_ticket += 1
        self._open.append(position)
        return position

    # ------------------------------------------------------------------ #
    # Per-bar management
    # ------------------------------------------------------------------ #
    def apply_bar(self, bar: Candle, bar_index: int) -> list[ClosedPosition]:
        """Evaluate SL/TP for every open position over ``bar``.

        Uses :func:`fill_model.evaluate_position_bar` (SL-first on same-bar
        conflicts). Closes are applied in fill order — deterministic.
        Returns the closed positions for this bar (possibly empty).
        """
        closed: list[ClosedPosition] = []
        for position in list(self._open):  # copy — closes mutate the list
            decision: BarClose = evaluate_position_bar(
                position.direction, position.sl, position.tp, bar
            )
            if not decision.closed:
                continue
            closed.append(self._close(position, decision, bar, bar_index))
        return closed

    def close(
        self,
        ticket: int,
        *,
        exit_price: float,
        exit_bar: int,
        exit_at,
        kind: str,
        win: bool | None = None,
    ) -> ClosedPosition:
        """Explicitly close one position (runner-driven close, e.g. a risk
        exit). ``win`` may be omitted for price-symmetric kinds — it is
        then derived from the exit direction relative to entry (LONG:
        ``exit_price > entry_price``). Raises ``KeyError`` for an unknown
        ticket."""
        for index, position in enumerate(self._open):
            if position.ticket == ticket:
                if win is None:
                    win = self._derive_win(position, exit_price)
                decision = BarClose(closed=True, kind=kind, price=exit_price, win=win)
                return self._close(position, decision, None, exit_bar, exit_at=exit_at)
        raise KeyError(f"no open position with ticket {ticket}")

    @staticmethod
    def _derive_win(position: BacktestPosition, exit_price: float) -> bool:
        """Price-symmetric win derivation for runner-driven closes."""
        if position.direction is Direction.LONG:
            return exit_price > position.entry_price
        return exit_price < position.entry_price

    def modify_sl(self, ticket: int, new_sl: float) -> BacktestPosition:
        """Apply an SL modify to an open position (M3: PureRunner BE and
        later risk-driven SL moves). Returns the updated position; raises
        ``KeyError`` for an unknown ticket. The BACKTEST store has no
        stops-level/spread broker guards — the caller (risk layer) owns
        the validity of the new level (mirrors the live split where the
        broker validates and ``PositionManager`` only sends)."""
        for index, position in enumerate(self._open):
            if position.ticket == ticket:
                updated = BacktestPosition(
                    ticket=position.ticket,
                    direction=position.direction,
                    volume=position.volume,
                    entry_price=position.entry_price,
                    sl=new_sl,
                    tp=position.tp,
                    entry_bar=position.entry_bar,
                    entry_at=position.entry_at,
                    symbol=position.symbol,
                    poi_id=position.poi_id,
                    trigger=position.trigger,
                )
                self._open[index] = updated
                return updated
        raise KeyError(f"no open position with ticket {ticket}")

    def sl_of(self, ticket: int) -> float | None:
        """Current SL of an open position (None when unknown ticket)."""
        for position in self._open:
            if position.ticket == ticket:
                return position.sl
        return None

    # ------------------------------------------------------------------ #
    # Access
    # ------------------------------------------------------------------ #
    def open_positions(self) -> list[BacktestPosition]:
        """Open positions in fill order (deterministic iteration)."""
        return list(self._open)

    def closed_positions(self) -> list[ClosedPosition]:
        """All closed positions in close order."""
        return list(self._closed)

    def __len__(self) -> int:
        return len(self._open)

    # ------------------------------------------------------------------ #
    def _close(
        self,
        position: BacktestPosition,
        decision: BarClose,
        bar: Candle | None,
        exit_bar: int,
        exit_at=None,
    ) -> ClosedPosition:
        self._open.remove(position)
        if exit_at is None:
            exit_at = bar.timestamp if bar is not None else position.entry_at
        direction_sign = 1.0 if position.direction is Direction.LONG else -1.0
        realized = (decision.price - position.entry_price) * direction_sign * position.volume
        record = ClosedPosition(
            position=position,
            exit_price=decision.price,
            exit_bar=exit_bar,
            exit_at=exit_at,
            kind=decision.kind,
            win=bool(decision.win),
            realized_pnl=realized,
        )
        self._closed.append(record)
        return record
