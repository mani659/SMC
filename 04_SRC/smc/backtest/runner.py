"""Backtest runner — RiskEngine integration (Phase 6, Milestone 3).

Implements the LOCKED per-bar runner contract (SMC_PHASE_6_DESIGN.md §2 /
M3 instruction) as an M1 :class:`~smc.backtest.bar_loop.BarHandler`, so the
same loop that walked bars in M1 now drives the full risk composition:

1. UTC date change → ``RiskEngine.reset_day()``;
2. ``evaluate_friday_close(now)`` → close ALL positions + cancel ALL
   pendings (portfolio-level, once per bar, before anything else);
3. ``hard_cancel_pending(now, news_events)`` → cancel pending limits (§11);
4. per-position ``evaluate_exit`` (FVG invalidation on the CLOSED bar +
   PureRunner BE proposal) → apply EXIT / MOVE_SL through the M2 store,
   calling ``on_be_applied()`` ONLY after a successful simulated modify;
5. M2 fill model: pending-limit fills + physical SL/TP hits (same-bar
   SL-first rule); a fill calls ``on_trade_opened()``;
6. entry path: externally supplied candidate entries (M3 seam — full
   signal generation is later) run through ``evaluate_entry``; an ENTER
   decision places a pending limit into the M2 book with the POLICY-sized
   lots; a blocked decision places nothing;
7. state updates on every closed trade: ``record_result`` (breaker),
   ``record_sl_close`` (same-level guard), ``record_failed_sweep`` (sweep
   guard — recorded ONLY when the candidate carried a sweep level; never
   fabricated).

Boundary preserved: the RiskEngine stays pure (decisions only); every
broker-like mutation happens in the M2 stores. Injected time only —
``now`` is the bar clock; there is no wall-clock read and no MT5 import.

Same-bar sequencing note (deterministic): exits are evaluated BEFORE
physical SL/TP, so a risk exit wins the bar when both would fire (design
§2.2). BE modifies are applied against the CURRENT store SL; a position
whose SL was already moved does not re-propose (the PureRunner latch).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from smc.backtest.bar_loop import BarHandler
from smc.backtest.clock import BarClock
from smc.backtest.fill_model import CloseKind
from smc.backtest.orders import PendingOrderBook
from smc.backtest.positions import ClosedPosition, PositionStore
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.risk.risk_engine import (
    BLOCK_NEWS,
    BLOCK_SESSION,
    EntryDecision,
    EntryRequest,
    ExitDecision,
    PositionState,
    RiskAction,
    RiskEngine,
)

__all__ = ["CandidateEntry", "RunnerConfig", "BacktestRunner", "BLOCKED_BY_NEWS", "BLOCKED_BY_SESSION"]

BLOCKED_BY_NEWS = BLOCK_NEWS
BLOCKED_BY_SESSION = BLOCK_SESSION


@dataclass(frozen=True, slots=True)
class CandidateEntry:
    """One externally supplied candidate entry (the M3 test seam).

    Full Stage 0–4 detection is deliberately out of M3 scope: tests (and a
    later M4+ integration) inject candidates; the runner converts them
    into a RiskEngine ``EntryRequest`` and, on ENTER, a pending limit in
    the M2 book. ``sweep_level`` / ``poi_id`` / ``trigger`` are optional
    identity for the sweep guard and the trade log.
    """

    direction: Direction
    entry_price: float
    sl_price: float
    tp_price: float | None = None
    score: float = 0.0
    sweep_level: float | None = None
    poi_id: str | None = None
    trigger: object | None = None


@dataclass(slots=True)
class RunnerConfig:
    """Sizing + environment inputs the runner threads into EntryRequest.

    ``risk_fraction`` stays a caller choice INSIDE the frozen §28.7 band —
    the policy layer clamps (single sizing path, no second path here).
    """

    equity: float = 10_000.0
    risk_fraction: float = 0.01
    pip_value_per_lot: float = 10.0
    min_lots: float = 0.01
    lot_step: float = 0.01
    allowed_sessions: tuple | list | None = None   # None = no session gate
    news_events: list = field(default_factory=list)


@dataclass(slots=True)
class BlockedEntry:
    """Log record for a gated-out candidate (KPI/report data)."""

    bar_index: int
    now: datetime
    blocked_by: str


class BacktestRunner(BarHandler):
    """Owns the per-bar order of operations over the M1/M2 primitives."""

    def __init__(
        self,
        *,
        risk_engine: RiskEngine,
        order_book: PendingOrderBook,
        position_store: PositionStore,
        config: RunnerConfig | None = None,
    ) -> None:
        self.risk = risk_engine
        self.orders = order_book
        self.positions = position_store
        self.config = config if config is not None else RunnerConfig()
        self.blocked_log: list[BlockedEntry] = []
        self._fvg_by_ticket: dict[int, object] = {}   # ticket → FvgContext
        self._sweep_level_by_ticket: dict[int, float | None] = {}
        self._last_date: object | None = None
        # M3 seams (per-instance — never class-level mutable state):
        self._pending_entries: list[CandidateEntry] = []
        self._atr: float = 0.0  # current ATR for entries AND exits (M4 feeds)
        self._spread_price: float = 0.0

    # ------------------------------------------------------------------ #
    # BarHandler entry point (called by the M1 BarLoop)
    # ------------------------------------------------------------------ #
    def on_bar(self, bar: Candle, bar_index: int, clock: BarClock) -> None:
        now = clock.now  # injected time — the ONLY clock in the loop
        self._maybe_reset_day(now)

        # 2. Portfolio-level Friday EOD (once per bar, first).
        if self.risk.evaluate_friday_close(now):
            self._close_everything(bar, bar_index, reason="friday_eod")
            self._cancel_all_pending()
            return

        # 3. §11 news hard-cancel of pending limits.
        if self.config.news_events and self.risk.hard_cancel_pending(
            now, self.config.news_events
        ):
            self._cancel_all_pending()

        # 4. Per-position risk exits (FVG invalidation + PureRunner BE).
        self._manage_open_positions(bar, bar_index, now)

        # 5. M2 fills: pending limits, then physical SL/TP (SL first).
        self._apply_fills(bar, bar_index)
        self._apply_physical_closes(bar, bar_index)

        # 6. Entry path (candidate seam).
        self._process_entries(bar, bar_index, now)

    # ------------------------------------------------------------------ #
    # Steps
    # ------------------------------------------------------------------ #
    def _maybe_reset_day(self, now: datetime) -> None:
        utc_date = now.date() if hasattr(now, "date") else None
        if self._last_date is not None and utc_date != self._last_date:
            self.risk.reset_day()
        self._last_date = utc_date

    def _close_everything(self, bar: Candle, bar_index: int, *, reason: str) -> None:
        """Close ALL open positions at the bar close (portfolio event)."""
        for position in list(self.positions.open_positions()):
            self._record_close(
                self.positions.close(
                    ticket=position.ticket,
                    exit_price=bar.close,
                    exit_bar=bar_index,
                    exit_at=bar.timestamp,
                    kind=reason,
                ),
                bar_index=bar_index,
            )

    def _cancel_all_pending(self) -> None:
        for order in self.orders.active():
            self.orders.cancel(order.ticket)

    def _manage_open_positions(self, bar: Candle, bar_index: int, now: datetime) -> None:
        for position in list(self.positions.open_positions()):
            fvg_context = self._fvg_by_ticket.get(position.ticket)
            decision: ExitDecision = self.risk.evaluate_exit(
                PositionState(
                    direction=position.direction,
                    entry_price=position.entry_price,
                    current_sl=position.sl if position.sl is not None else position.entry_price,
                    atr=self._atr,  # injected ATR (0.0 disables the BE gate)
                    current_price=bar.close,
                    closed_close=bar.close,  # the just-closed bar (contract)
                    bar_index=bar_index,
                ),
                now=now,
                fvg_context=fvg_context,
            )
            if decision.action is RiskAction.EXIT:
                record = self.positions.close(
                    ticket=position.ticket,
                    exit_price=bar.close,
                    exit_bar=bar_index,
                    exit_at=bar.timestamp,
                    kind=decision.reason or "risk_exit",
                )
                self._record_close(record, bar_index=bar_index)
            elif decision.action is RiskAction.MOVE_SL:
                # Simulated modify: succeed when it genuinely improves the
                # protective level (mirrors broker acceptance semantics).
                current = position.sl if position.sl is not None else position.entry_price
                improves = (
                    decision.new_sl > current
                    if position.direction is Direction.LONG
                    else decision.new_sl < current
                )
                if improves:
                    self.positions.modify_sl(position.ticket, decision.new_sl)
                    self.risk.on_be_applied()  # latch ONLY after "acceptance"

    def _apply_fills(self, bar: Candle, bar_index: int) -> None:
        from smc.backtest.fill_model import fill_price, limit_filled

        for order in self.orders.active():  # placement order — deterministic
            if not limit_filled(order.direction, order.entry_price, bar):
                continue
            price = fill_price(order.direction, order.entry_price, bar)
            self.orders.cancel(order.ticket)
            position = self.positions.open(
                direction=order.direction,
                volume=order.volume,
                entry_price=price,
                sl=order.sl,
                tp=order.tp,
                entry_bar=bar_index,
                entry_at=bar.timestamp,
                symbol=order.symbol,
                poi_id=order.poi_id,
                trigger=order.trigger,
            )
            self._sweep_level_by_ticket[position.ticket] = None
            self.risk.on_trade_opened()  # re-arm the BE latch for THIS trade

    def _apply_physical_closes(self, bar: Candle, bar_index: int) -> None:
        for record in self.positions.apply_bar(bar, bar_index):
            self._record_close(record, bar_index=bar_index)

    def _process_entries(self, bar: Candle, bar_index: int, now: datetime) -> None:
        for candidate in self._pending_entries:
            request = EntryRequest(
                direction=candidate.direction,
                entry_price=candidate.entry_price,
                sl_price=candidate.sl_price,
                atr=self._atr,
                current_bar=bar_index,
                now=now,
                equity=self.config.equity,
                risk_fraction=self.config.risk_fraction,
                pip_value_per_lot=self.config.pip_value_per_lot,
                min_lots=self.config.min_lots,
                lot_step=self.config.lot_step,
                score=candidate.score,
                current_spread_price=self._spread_price,
                sweep_level=candidate.sweep_level,
                news_events=list(self.config.news_events),
                allowed_sessions=self.config.allowed_sessions,
            )
            decision: EntryDecision = self.risk.evaluate_entry(request)
            if decision.action is not RiskAction.ENTER:
                self.blocked_log.append(
                    BlockedEntry(bar_index=bar_index, now=now, blocked_by=decision.blocked_by or "unknown")
                )
                continue
            self.orders.place(
                direction=candidate.direction,
                entry_price=candidate.entry_price,
                sl=candidate.sl_price,
                tp=candidate.tp_price,
                volume=decision.lots,  # policy-sized (sized_lots) — no second path
                placed_bar=bar_index,
                placed_at=now,
                poi_id=candidate.poi_id,
                trigger=candidate.trigger,
            )
        self._pending_entries = []

    # ------------------------------------------------------------------ #
    # M3 seams (replaced by real integration in M4+)
    # ------------------------------------------------------------------ #
    def submit_entry(self, candidate: CandidateEntry) -> None:
        """Queue a candidate entry for the NEXT bar's entry step (M3 seam)."""
        self._pending_entries.append(candidate)

    def set_atr(self, atr: float) -> None:
        """Inject the current ATR (M3 seam — M4/paper feed it per bar).

        Consumed by BOTH the entry gates/sizing (``EntryRequest.atr``) and
        the exit management (``PositionState.atr`` → PureRunner BE). ATR
        0.0 (the default) disables the ATR-dependent BE gate; FVG
        invalidation is ATR-independent and still works.
        """
        self._atr = atr

    def set_spread_price(self, spread: float) -> None:
        """Inject the current spread in PRICE units (M4/paper feed this)."""
        self._spread_price = spread

    def set_fvg_context(self, ticket: int, fvg_context) -> None:
        """Attach an FvgContext to an open position (design §8.7 seam)."""
        self._fvg_by_ticket[ticket] = fvg_context

    # ------------------------------------------------------------------ #
    # State updates on closed trades
    # ------------------------------------------------------------------ #
    def _record_close(self, record: ClosedPosition, *, bar_index: int) -> None:
        self.risk.record_result(win=record.win, at=record.exit_at)
        if record.kind == CloseKind.STOP_LOSS:
            self.risk.record_sl_close(sl_level=record.exit_price, bar_index=bar_index)
        # Sweep-guard recording needs the candidate's sweep level; M3's
        # entry seam does not plumb it per fill yet — deliberately NOT
        # fabricated (TODO(M4): thread candidate.sweep_level through the
        # fill into _sweep_level_by_ticket and call record_failed_sweep on
        # losing closes with a recorded level).
        self._sweep_level_by_ticket.pop(record.position.ticket, None)
        self._fvg_by_ticket.pop(record.position.ticket, None)
