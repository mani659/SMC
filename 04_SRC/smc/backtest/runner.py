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
from smc.config.timeframe import Timeframe
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

__all__ = [
    "CandidateEntry",
    "RunnerConfig",
    "BacktestRunner",
    "BLOCKED_BY_NEWS",
    "BLOCKED_BY_SESSION",
]

# M4 sweep-level plumbing: the adapter records a candidate's sweep level
# on the pending order → fill ticket → losing close so the §28.6 sweep
# guard is fed (record_failed_sweep). No trigger in the frozen Phase 4 set
# exposes a sweep level on its signal yet, so the plumbing is complete but
# usually dormant — no sweep level is ever fabricated.

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
    route_id: str | None = None  # §11 event identity string (POI:trigger@bar)
    # M4: zero-arg callable → FvgContext | None, bound by the pipeline bridge
    # at construction (frozen dataclass — never mutated after creation).
    fvg_provider: object | None = None

    def fvg_context(self):
        """FVG context for this candidate (None when the signal supplies none).

        The M4 bridge binds ``fvg_provider`` (honest derivation only — see
        ``pipeline_bridge.fvg_context_for_route``); the M3 seam leaves it
        None so FVG invalidation is skipped for such trades.
        """
        provider = self.fvg_provider
        return None if provider is None else provider()


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
    # M4/I1: the runner's execution timeframe (drives the frozen §23
    # unfilled-order expiry: M5 = 12 / M1 = 30 bars) and the per-bar
    # spread input for the §28.5 spread gate (PRICE units; 0.0 leaves the
    # gate off — a caller enabling spread grading must configure it here).
    timeframe: Timeframe = Timeframe.M5
    spread_price: float = 0.0


@dataclass(slots=True)
class BlockedEntry:
    """Log record for a gated-out candidate (KPI/report data)."""

    bar_index: int
    now: datetime
    blocked_by: str


@dataclass(frozen=True, slots=True)
class RunnerResult:
    """Immutable snapshot of a completed run's reporting artifacts (M5).

    A pure projection over the stores — the runner stays usable without
    reports; :func:`smc.backtest.reports.build_report` consumes this.
    ``route_ids`` maps a CLOSED trade's ticket to its §11 event identity
    (``None``-free dict: identity-absent trades are simply not keyed).
    """

    closed: list  # list[ClosedPosition] — close order
    blocked: list  # list[BlockedEntry] — occurrence order
    route_ids: dict  # closed ticket → route_id string


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
        # I2 (coherence patch): RUNNING equity — starts at the configured
        # value and moves with realized P/L (see _record_close). Sizing
        # reads this, never the static config, after the first close.
        self._equity: float = self.config.equity
        self.blocked_log: list[BlockedEntry] = []
        self._fvg_by_ticket: dict[int, object] = {}   # ticket → FvgContext
        self._sweep_level_by_ticket: dict[int, float | None] = {}
        self._last_date: object | None = None
        # M3 seams (per-instance — never class-level mutable state):
        self._pending_entries: list[CandidateEntry] = []
        self._atr: float = 0.0  # current ATR for entries AND exits (M4 feeds)
        self._spread_price: float = 0.0
        # M4: optional pipeline adapter — when attached, the entry step
        # pulls candidate entries from real detection instead of the M3
        # submit_entry() test seam (see set_pipeline_adapter()).
        self._pipeline_adapter = None
        # M4: per-order context captured at placement, consumed at fill.
        self._sweep_by_order: dict[int, float | None] = {}
        self._fvg_by_order: dict[int, object] = {}
        # M5: §11 event identity captured at placement, moved to the fill
        # ticket at fill, and to the closed-tickets map on close —
        # ``result()`` projects it onto the closed-trade list.
        self._route_by_order: dict[int, str] = {}
        self._route_by_position: dict[int, str] = {}
        self._route_ids_closed: dict[int, str] = {}

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

        # 3b. I1: feed ATR + spread per bar so the ATR-dependent gates
        # (PureRunner BE, §28.5 spread, same-level) are never silently
        # disabled in the integrated path. ATR comes from the pipeline
        # adapter's honest candle prefix (capped at this bar — no
        # lookahead); the M3 test seam keeps its explicit set_atr().
        if self._pipeline_adapter is not None:
            self.set_atr(self._pipeline_adapter.current_atr(bar_index))
        self.set_spread_price(self.config.spread_price)

        # 3c. C1: §23/§24 unfilled-order expiry — resting limits past the
        # frozen bars (M5 = 12 / M1 = 30; give-up backstop elsewhere) are
        # cancelled BEFORE this bar's fills are evaluated, so an expired
        # order can never fill. Affected POIs go TESTED through the
        # state machine (engine authority).
        self._expire_orders(bar_index)

        # 4. Per-position risk exits (FVG invalidation + PureRunner BE).
        self._manage_open_positions(bar, bar_index, now)

        # 5. M2 fills: pending limits, then physical SL/TP (SL first).
        self._apply_fills(bar, bar_index)
        self._apply_physical_closes(bar, bar_index)        # 6. Entry path: the M4 pipeline adapter (real detection) when
        #    attached, else the M3 candidate seam. Both end in the same
        #    risk-gated pending-limit placement.
        if self._pipeline_adapter is not None:
            # I4: retire terminal POIs (workflow-live + order/position-
            # tied ids retained by the adapter) before this bar's scan.
            self._prune_engine_state(bar_index)
            self._pipeline_adapter.generate_candidates(bar, bar_index, now)
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

    def _expire_orders(self, bar_index: int) -> None:
        """C1: apply the frozen §23/§24 unfilled-order expiry (audit fix).

        ``PendingOrderBook.expired_by_section23`` / ``expired_by_give_up``
        cancel resting limits past their window (M5 = 12 / M1 = 30 bars;
        the 20-bar §24 give-up backstop for timeframes without a §23
        rule). Each affected POI is driven to TESTED through the engine's
        state machine (the sole §5 authority) via the adapter seam, and
        the runner's per-order context maps are cleaned up. Runs BEFORE
        fills each bar so an order reaching expiry on this bar can never
        fill on it.
        """
        expired = self.orders.expired_by_section23(bar_index, self.config.timeframe)
        expired += self.orders.expired_by_give_up(bar_index)
        for order in expired:
            self._sweep_by_order.pop(order.ticket, None)
            self._fvg_by_order.pop(order.ticket, None)
            self._route_by_order.pop(order.ticket, None)
            if self._pipeline_adapter is not None and order.poi_id is not None:
                bars_open = bar_index - order.placed_bar + 1
                self._pipeline_adapter.notify_order_expired(order.poi_id, bars_open)
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
            # M4 identity/context capture at trade open: the pending order
            # carries the sweep level + FVG context its candidate was built
            # with; both attach to the fill's ticket here.
            # FVG mapping (design note §FVG): the context is the trigger
            # signal's OWN signal FVG when the signal can supply one
            # (Trigger F emits its origin FVG); otherwise it stays ABSENT
            # and FVG invalidation is skipped for this trade — geometry is
            # never invented (M4 constraint).
            self._sweep_level_by_ticket[position.ticket] = self._sweep_by_order.pop(
                order.ticket, None
            )
            route_id = self._route_by_order.pop(order.ticket, None)
            if route_id is not None:
                self._route_by_position[position.ticket] = route_id
            fvg_context = self._fvg_by_order.pop(order.ticket, None)
            if fvg_context is not None:
                self._fvg_by_ticket[position.ticket] = fvg_context
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
                equity=self._equity,  # I2: running equity, not the static config
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
                # M4: a BLOCKED entry consumes nothing — the candidate's POI
                # one-shot stays armed and may fire on a later bar (see
                # PipelineAdapter.on_candidates: the episode is marked fired
                # ONLY on an accepted placement).
                self.blocked_log.append(
                    BlockedEntry(bar_index=bar_index, now=now, blocked_by=decision.blocked_by or "unknown")
                )
                continue
            order = self.orders.place(
                direction=candidate.direction,
                entry_price=candidate.entry_price,
                sl=candidate.sl_price,
                tp=candidate.tp_price,
                volume=decision.lots,  # policy-sized (sized_lots) — no second path
                placed_bar=bar_index,
                placed_at=now,
                poi_id=candidate.poi_id,
                trigger=candidate.trigger,
                comment=candidate.route_id or "",
            )
            # Identity/context ride along the order so the fill can attach
            # them to the trade (see _apply_fills).
            if candidate.sweep_level is not None:
                self._sweep_by_order[order.ticket] = candidate.sweep_level
            if candidate.route_id is not None:
                self._route_by_order[order.ticket] = candidate.route_id
            fvg_context = self._fvg_of_candidate(candidate)
            if fvg_context is not None:
                self._fvg_by_order[order.ticket] = fvg_context
            self._notify_candidate_accepted(candidate)
        self._pending_entries = []

    # ------------------------------------------------------------------ #
    # M3 seams (replaced by real integration in M4+)
    # ------------------------------------------------------------------ #
    def submit_entry(self, candidate: CandidateEntry) -> None:
        """Queue a candidate entry for the NEXT bar's entry step (M3 seam)."""
        self._pending_entries.append(candidate)

    # ------------------------------------------------------------------ #
    # M4 — pipeline integration (real detection → validation → triggers)
    # ------------------------------------------------------------------ #
    def set_pipeline_adapter(self, adapter) -> None:
        """Attach the M4 pipeline adapter (real detection each bar).

        The adapter is invoked as ``generate_candidates(bar, bar_index, now)``
        at the entry step of every bar; candidates it queues through
        :meth:`submit_entry` run the SAME risk-gated path as M3's seam.
        ``None`` detaches (falls back to the M3 seam only).
        """
        self._pipeline_adapter = adapter

    def _prune_engine_state(self, bar_index: int) -> None:
        """I4: drop terminal engine POIs whose state fully resolved.

        Retained ids: any POI with a resting pending limit or an open
        position in this runner's stores (its trade may still resolve).
        Workflow-live ids and POIs still inside the first-touch routing
        window are retained inside the adapter itself. Safe when no
        adapter is attached (backtest-only runs keep every POI the caller
        armed — there is no engine bookkeeping to prune).
        """
        adapter = self._pipeline_adapter
        prune = getattr(adapter, "prune_terminal_pois", None)
        if prune is None:
            return
        retain = {o.poi_id for o in self.orders.active() if o.poi_id}
        retain |= {p.poi_id for p in self.positions.open_positions() if p.poi_id}
        prune(retain, bar_index)

    def current_equity(self) -> float:
        """I2: running account equity (config start + realized P/L).

        Unit note: ``realized_pnl`` is raw price×volume; it is converted
        to the account-currency units of ``equity`` via
        ``pip_value_per_lot`` — the exact inverse of the sizing formula's
        divisor (``sl_distance × pip_value_per_lot``), so a winning close
        of +1.0 raw P/L on a 10.0 pip-value symbol adds 10.0 to equity.
        """
        return self._equity

    def _fvg_of_candidate(self, candidate: CandidateEntry):
        """FVG context attached to a candidate (None when not supplied).

        The adapter (not the runner) owns the honest-derivation rule: it
        attaches a context ONLY when the trigger signal can supply a real
        FVG. The runner never invents geometry here.
        """
        getter = getattr(candidate, "fvg_context", None)
        if getter is None:
            return None
        try:
            return getter()
        except Exception:  # noqa: BLE001 — a broken adapter must not kill the bar
            return None

    def _notify_candidate_accepted(self, candidate: CandidateEntry) -> None:
        """Tell the adapter its candidate was ACCEPTED (one-shot consumption)."""
        callback = getattr(self._pipeline_adapter, "on_candidate_accepted", None)
        if callback is not None:
            callback(candidate)

    def result(self) -> RunnerResult:
        """Snapshot the run's reporting artifacts (M5 seam — pure read).

        Collects the position store's closed-trade history, the blocked
        log, and the closed tickets' §11 route identities. No mutation,
        no clock, no MT5 — callable at any time; consume it with
        :func:`smc.backtest.reports.build_report`.
        """
        return RunnerResult(
            closed=self.positions.closed_positions(),
            blocked=list(self.blocked_log),
            route_ids=dict(self._route_ids_closed),
        )

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

    def cancel_pending_for_poi(self, poi_id: str) -> int:
        """M4: cancel every resting limit minted from ``poi_id``.

        The pipeline adapter calls this when the POI's §5 state dies
        (VIOLATED): a violated zone is a dead thesis, so its unfilled
        limit must not linger and fill later. Returns the count cancelled.
        """
        cancelled = 0
        for order in self.orders.active():
            if order.poi_id == poi_id:
                self.orders.cancel(order.ticket)
                cancelled += 1
        return cancelled

    def set_fvg_context(self, ticket: int, fvg_context) -> None:
        """Attach an FvgContext to an open position (design §8.7 seam)."""
        self._fvg_by_ticket[ticket] = fvg_context

    # ------------------------------------------------------------------ #
    # State updates on closed trades
    # ------------------------------------------------------------------ #
    def _record_close(self, record: ClosedPosition, *, bar_index: int) -> None:
        self.risk.record_result(win=record.win, at=record.exit_at)
        # I2: running equity moves with realized P/L (currency conversion:
        # raw price×volume × pip value per lot — see current_equity).
        self._equity += record.realized_pnl * self.config.pip_value_per_lot
        if record.kind == CloseKind.STOP_LOSS:
            self.risk.record_sl_close(sl_level=record.exit_price, bar_index=bar_index)
        # M4 sweep plumbing: a losing close on a trade whose candidate
        # carried a sweep level feeds the sweep guard. No level → nothing
        # recorded (never fabricated).
        sweep_level = self._sweep_level_by_ticket.pop(record.position.ticket, None)
        # M5: keep the §11 route identity reachable for the report snapshot.
        route_id = self._route_by_position.pop(record.position.ticket, None)
        if route_id is not None:
            self._route_ids_closed[record.position.ticket] = route_id
        if (
            not record.win
            and sweep_level is not None
            and sweep_level != 0.0
        ):
            self.risk.record_failed_sweep(
                sweep_level=sweep_level,
                bar_index=bar_index,
                is_long=record.position.direction is Direction.LONG,
            )
        self._fvg_by_ticket.pop(record.position.ticket, None)
