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
    # Identity enrichment (logging only — carried order → fill → position).
    model_tags: tuple | None = None
    pillar_path: str | None = None
    disp_magnitude_atr: float | None = None
    # Placement-time geometry (logging only — never modified after place).
    original_sl: float | None = None
    zone_low: float | None = None
    zone_high: float | None = None
    signal_data_json: str | None = None
    # E1: trigger entry-anchor provenance (see CandidateEntry.entry_anchor);
    # None = unknown (never invented).
    entry_anchor: str | None = None
    # Structural TP provenance (see CandidateEntry.tp_source). Logging/audit
    # only — never read by risk/fill logic. None = unknown/legacy.
    tp_source: str | None = None
    # FR fill-regime policy (R8): this order's pending lifetime in runner
    # bars (§23 bars_open convention) + its detection-timeframe provenance.
    # None = use the runner-timeframe §23 default (legacy orders, M3 seam).
    rest_bars: int | None = None
    detection_tf: object | None = None


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
        model_tags: tuple | None = None,
        pillar_path: str | None = None,
        disp_magnitude_atr: float | None = None,
        original_sl: float | None = None,
        zone_low: float | None = None,
        zone_high: float | None = None,
        signal_data_json: str | None = None,
        entry_anchor: str | None = None,
        tp_source: str | None = None,
        rest_bars: int | None = None,
        detection_tf: object | None = None,
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
            model_tags=model_tags,
            pillar_path=pillar_path,
            disp_magnitude_atr=disp_magnitude_atr,
            original_sl=original_sl,
            zone_low=zone_low,
            zone_high=zone_high,
            signal_data_json=signal_data_json,
            entry_anchor=entry_anchor,
            tp_source=tp_source,
            rest_bars=rest_bars,
            detection_tf=detection_tf,
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
        """Cancel orders past the frozen §23 unfilled-order expiry (R8-aware).

        Lifetime is PER ORDER: an R8-extended order carries its own
        ``rest_bars`` (H1-detected 36 / H4, M8 or D1-detected 48 runner
        bars); orders without one use the frozen execution-timeframe rule
        (M5 = 12 / M1 = 30 bars, ``expiry_bars_for``). Timeframes without
        a frozen rule (H1+) NEVER auto-expire by default — the runner
        decides (no invented rule), but an explicit R8 ``rest_bars`` still
        applies there (it is runner-bar units, not POI-timeframe units).
        ``bars_open`` uses the SAME convention as
        ``POIStateMachine.expire_unfilled`` (expiry when ``bars_open >=
        limit``): the placement bar counts as the first open bar, so an
        order placed on bar N has been open 1 bar on N and 12 bars on
        N+11 (M5) — it expires once the 12th bar closes unfilled.
        Returns the cancelled orders.
        """
        default_limit = expiry_bars_for(timeframe)
        cancelled: list[PendingOrder] = []
        for order in self._orders:
            limit = order.rest_bars if order.rest_bars is not None else default_limit
            if limit is None:
                continue
            bars_open = current_bar - order.placed_bar + 1
            if bars_open >= limit:
                cancelled.append(order)
        for order in cancelled:
            self._orders.remove(order)
        return cancelled

    def expired_by_give_up(self, current_bar: int) -> list[PendingOrder]:
        """Cancel orders resting past the POI-wide give-up window (§24 V1).

        Uses ``poi_give_up_bars()`` (Trigger A's frozen 20 M5 bars) as the
        default backstop — never below an order's R8 ``rest_bars`` (an
        R8-extended order is not silently shortened by the backstop; the
        effective backstop is ``max(20, rest_bars)``). Same ``bars_open``
        convention as :meth:`expired_by_section23` (placement bar counts
        as the first open bar; expiry when ``bars_open >= backstop``).
        """
        default_backstop = poi_give_up_bars()
        cancelled: list[PendingOrder] = []
        for order in self._orders:
            backstop = (max(default_backstop, order.rest_bars)
                        if order.rest_bars is not None else default_backstop)
            bars_open = current_bar - order.placed_bar + 1
            if bars_open >= backstop:
                cancelled.append(order)
        for order in cancelled:
            self._orders.remove(order)
        return cancelled
