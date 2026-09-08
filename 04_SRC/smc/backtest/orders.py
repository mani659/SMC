"""Backtest pending order book (Phase 6, Milestone 2).

In-memory pending LIMIT order store for the backtest broker adapter. Pure
Python — no MT5 anywhere in the backtest core (guarded by a test).

Determinism contract:

* tickets are a monotonically increasing integer sequence started at an
  injected ``first_ticket`` (no randomness, no wall clock);
* insertion order is preserved (list-backed) so same-bar processing is
  deterministic — the FIRST placed order is evaluated FIRST on every bar;
* expiry is caller-driven: :meth:`PendingOrderBook.expire` applies the §23
  unfilled-order rule (M5 = 12 / M1 = 30 bars, frozen) or an explicit
  bars-open count supplied by the runner.

Orders reuse the frozen execution-layer semantics: a pending limit is the
same semantic shape as ``OrderRequest(kind=LIMIT)`` from
``smc.execution.order_manager`` (direction, limit price, SL, TP, volume,
comment) plus backtest bookkeeping (placed bar, POI identity for the later
risk/pipeline integration).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.triggers.trigger_expiry import poi_give_up_bars
from smc.validation.state_machine import expiry_bars_for

__all__ = ["PendingOrder", "PendingOrderBook"]


@dataclass(frozen=True, slots=True)
class PendingOrder:
    """One resting LIMIT order in the backtest book.

    ``poi_id`` / ``trigger`` carry the R1 §11 event identity so the later
    runner can tie a fill back to the POI/trigger that produced it (the
    engine's one-shot stays engine-owned; this is bookkeeping only).
    """

    ticket: int
    direction: Direction
    entry_price: float        # resting limit price (fill price on touch)
    sl: float | None          # protective stop (None = none)
    tp: float | None          # take profit (None = none)
    volume: float
    placed_bar: int           # bar index the order was placed on
    placed_at: object         # injected UTC datetime (bookkeeping)
    symbol: str = ""
    comment: str = ""
    poi_id: str | None = None
    trigger: object | None = None  # TriggerType of the originating route


@dataclass(slots=True)
class PendingOrderBook:
    """Insertion-ordered in-memory pending LIMIT order book.

    Tickets are deterministic: ``first_ticket + n`` for the n-th order
    placed since construction.
    """

    first_ticket: int = 1
    _orders: list[PendingOrder] = field(default_factory=list)
    _next_ticket: int | None = None

    def __post_init__(self) -> None:
        if self._next_ticket is None:
            self._next_ticket = self.first_ticket

    # ------------------------------------------------------------------ #
    # Placement / cancellation
    # ------------------------------------------------------------------ #
    def place(
        self,
        *,
        direction: Direction,
        entry_price: float,
        sl: float | None,
        tp: float | None,
        volume: float,
        placed_bar: int,
        placed_at,
        symbol: str = "",
        comment: str = "",
        poi_id: str | None = None,
        trigger=None,
    ) -> PendingOrder:
        """Add one pending limit order; returns it (ticket pre-assigned)."""
        if volume <= 0.0:
            raise ValueError("pending order volume must be positive")
        if entry_price <= 0.0:
            raise ValueError("pending order entry_price must be positive")
        order = PendingOrder(
            ticket=self._next_ticket,
            direction=direction,
            entry_price=entry_price,
            sl=sl,
            tp=tp,
            volume=volume,
            placed_bar=placed_bar,
            placed_at=placed_at,
            symbol=symbol,
            comment=comment,
            poi_id=poi_id,
            trigger=trigger,
        )
        self._next_ticket += 1
        self._orders.append(order)
        return order

    def cancel(self, ticket: int) -> PendingOrder | None:
        """Remove the pending order ``ticket``; None when not resting."""
        for index, order in enumerate(self._orders):
            if order.ticket == ticket:
                return self._orders.pop(index)
        return None

    def remove(self, order: PendingOrder) -> None:
        """Remove a specific order instance (e.g. after a fill)."""
        try:
            self._orders.remove(order)
        except ValueError:
            pass  # already gone — idempotent

    # ------------------------------------------------------------------ #
    # Listing / expiry
    # ------------------------------------------------------------------ #
    def active(self) -> list[PendingOrder]:
        """Resting orders in placement order (deterministic iteration)."""
        return list(self._orders)

    def __len__(self) -> int:
        return len(self._orders)

    def expired_by_section23(self, current_bar: int, timeframe: Timeframe) -> list[PendingOrder]:
        """Cancel orders past the frozen §23 unfilled-order expiry.

        M5 = 12 / M1 = 30 bars (``expiry_bars_for``); timeframes without a
        frozen rule (H1+) NEVER auto-expire here — the runner decides (no
        invented rule). ``bars_open`` uses the SAME convention as
        ``POIStateMachine.expire_unfilled`` (expiry when ``bars_open >=
        limit``): the placement bar counts as the first open bar, so an
        order placed on bar N has been open 1 bar on N and 12 bars on
        N+11 (M5) — it expires once the 12th bar closes unfilled.
        Returns the cancelled orders.
        """
        limit = expiry_bars_for(timeframe)
        if limit is None:
            return []
        cancelled: list[PendingOrder] = []
        for order in self._orders:
            bars_open = current_bar - order.placed_bar + 1
            if bars_open >= limit:
                cancelled.append(order)
        for order in cancelled:
            self._orders.remove(order)
        return cancelled

    def expired_by_give_up(self, current_bar: int) -> list[PendingOrder]:
        """Cancel orders resting past the POI-wide give-up window (§24 V1).

        Uses ``poi_give_up_bars()`` (Trigger A's frozen 20 M5 bars) — a
        defensive backstop for orders on timeframes without a §23 rule.
        Same ``bars_open`` convention as :meth:`expired_by_section23`
        (placement bar counts as the first open bar; expiry when
        ``bars_open >= poi_give_up_bars()``).
        """
        limit = poi_give_up_bars()
        cancelled: list[PendingOrder] = []
        for order in self._orders:
            bars_open = current_bar - order.placed_bar + 1
            if bars_open >= limit:
                cancelled.append(order)
        for order in cancelled:
            self._orders.remove(order)
        return cancelled
