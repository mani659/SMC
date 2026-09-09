"""Phase 6 M6 — paper runner: the shared stack against a demo broker.

Composes the FROZEN pieces exactly as the backtest does —
``PipelineEngine`` (driven through the M4 ``PipelineAdapter``)
finds/validates/routes, ``RiskEngine`` gates/sizes/manages (pure
decisions), and the broker boundary applies them — but the broker side
is the LIVE execution layer (``OrderManager`` / ``PositionManager`` over
an ``MT5Connector``) instead of the M2 simulated stores. Composition,
not a copy of ``BacktestRunner``: the runner holds NO detection /
validation / sizing logic of its own.

Per-bar order (the locked backtest order, applied live — the loop calls
``run_one_cycle(bar)`` when a bar closes):

1. UTC date change → ``RiskEngine.reset_day()``;
2. ``evaluate_friday_close(now)`` → close ALL positions + cancel ALL
   pendings through the adapter, KPI-logged, and skip everything else;
3. ``hard_cancel_pending(now, news_events)`` → cancel all pendings (§11);
4. observe broker state → fills (pending → position) and closes
   (position gone) → risk lifecycle hooks + KPI records;
5. per-position ``evaluate_exit`` → EXIT (close) / MOVE_SL (modify) —
   ``on_be_applied()`` ONLY after a successful modify (M6 constraint);
6. entry step LAST: drive the pipeline (scan + feed through the M4
   adapter), run queued routes through ``RiskEngine.evaluate_entry``,
   place ENTER verdicts as real pending limits via the adapter. A
   blocked verdict places nothing and consumes nothing (engine I2
   semantics — the route may be re-attempted later).

Fill/close observation is broker-truth-based: a pending is FILLED when
the broker reports a position whose ticket equals the pending's order
ticket (MT5's position-id convention); a position is CLOSED when it
disappears from ``positions_get``. Documented V1 limitations (honest,
not faked): the closing deal's exact price/kind/P/L is not
reconstructed from MT5 history, so closes of unknown P/L are NOT fed
into the circuit breaker (``record_result`` requires a known win/loss).

Determinism: the ONLY clock inputs are the injected ``now`` (bar
timestamp) and the injected ``perf`` monotonic source; KPI records are
therefore reproducible under fakes. No wall-clock read, no sleep.

Safety posture (demo): :meth:`start` refuses to run when
``connector.initialize()`` fails; symbol/magic live on the injected
managers; ``dry_run`` evaluates and logs decisions but never sends an
order. The paper package shares nothing mutable with the backtest fill
model — backtest stores stay backtest-pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from smc.backtest.pipeline_adapter import PipelineAdapter
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.execution.order_manager import OrderKind, OrderRequest
from smc.paper.broker_adapter import BrokerAdapter
from smc.paper.kpi_logger import KPILogger
from smc.risk.risk_engine import (
    EntryDecision,
    EntryRequest,
    ExitDecision,
    PositionState,
    RiskAction,
    RiskEngine,
)

__all__ = ["PaperConfig", "PaperRunner"]


@dataclass(slots=True)
class PaperConfig:
    """Demo-safety + sizing configuration (single sizing path — §28.7)."""

    risk_fraction: float = 0.01
    pip_value_per_lot: float = 10.0
    min_lots: float = 0.01
    lot_step: float = 0.01
    allowed_sessions: tuple | list | None = None   # None = no session gate
    news_events: list = field(default_factory=list)
    dry_run: bool = False          # True → evaluate + log, never place
    atr_period: int = 14           # indicator parameter (matches smc.utils.atr)
    spread_price: float = 0.0      # current spread in PRICE units


@dataclass(slots=True)
class _TrackedPending:
    """A pending we placed at the broker (identity kept client-side)."""

    ticket: int
    poi_id: str | None
    trigger: object
    route_id: str | None
    fvg_context: object | None
    sweep_level: float | None
    placed_at: datetime


@dataclass(slots=True)
class _TrackedPosition:
    """An open position we know about (identity + risk context)."""

    ticket: int
    direction: Direction
    volume: float
    entry_price: float
    sl: float | None
    poi_id: str | None
    trigger: object
    route_id: str | None
    fvg_context: object | None
    sweep_level: float | None


class PaperRunner:
    """One-cycle bar-close paper loop over the frozen shared stack.

    The M4 ``PipelineAdapter`` protocol is honoured directly: this class
    IS the adapter's runner (``submit_entry`` / ``set_pipeline_adapter``
    / ``cancel_pending_for_poi``), so the exact same adapter drives the
    backtest and the paper path.
    """

    def __init__(
        self,
        *,
        connector,
        risk_engine: RiskEngine,
        pipeline: PipelineAdapter,
        order_manager,
        position_manager,
        config: PaperConfig | None = None,
        kpi: KPILogger | None = None,
        perf=None,
        timeframe: Timeframe = Timeframe.M5,
    ) -> None:
        self.connector = connector
        self.risk = risk_engine
        self.adapter = pipeline          # the M4 adapter drives the engine
        self.broker = BrokerAdapter(
            order_manager=order_manager, position_manager=position_manager, perf=perf
        )
        self.config = config if config is not None else PaperConfig()
        self.kpi = kpi if kpi is not None else KPILogger()
        self._perf = perf                # injected monotonic () -> float
        self.timeframe = timeframe
        self._last_date: object | None = None
        self._last_bar_at: datetime | None = None
        self._pendings: dict[int, _TrackedPending] = {}
        self._positions: dict[int, _TrackedPosition] = {}
        self._entry_queue: list = []     # candidates the adapter queued this bar
        self._bar_count = 0              # monotonically increasing bar anchor

    # ------------------------------------------------------------------ #
    # M4 adapter-runner protocol (same seam the backtest runner exposes)
    # ------------------------------------------------------------------ #
    def set_pipeline_adapter(self, adapter) -> None:
        """Called by ``PipelineAdapter.attach`` — wiring parity with backtest."""
        self._entry_queue = []

    def submit_entry(self, candidate) -> None:
        """Adapter seam: queue a candidate for THIS bar's entry step."""
        self._entry_queue.append(candidate)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> bool:
        """Initialize the connector (refuse to run when it fails)."""
        return bool(self.connector.initialize())

    def stop(self) -> None:
        """Release the connector (idempotent for fakes without shutdown)."""
        shutdown = getattr(self.connector, "shutdown", None)
        if callable(shutdown):
            shutdown()

    def run_one_cycle(self, bar: Candle) -> None:
        """Process ONE closed bar (bar-close driven V1 loop step)."""
        now = bar.timestamp  # injected time — the ONLY clock in the loop
        self._log_missed_bars(now)
        self._maybe_reset_day(now)
        self._remember_bar(bar)
        self._bar_count += 1

        # 2. Portfolio-level Friday EOD (once per bar, first).
        if self.risk.evaluate_friday_close(now):
            self._friday_close(now)
            self._last_bar_at = now
            return

        # 3. §11 news hard-cancel of pending limits.
        if self.config.news_events and self.risk.hard_cancel_pending(
            now, self.config.news_events
        ):
            self._hard_cancel_all(now)

        # 4. Observe the broker: fills + closes (broker truth).
        self._observe_fills(now)
        self._observe_closes(now)

        # 5. Per-position risk exits (FVG invalidation + PureRunner BE).
        self._manage_open_positions(bar, now)

        # 6. Entry step LAST — pipeline scan → risk gate → broker limit.
        self._entry_step(bar, now)
        self._last_bar_at = now

    # ------------------------------------------------------------------ #
    # Step helpers
    # ------------------------------------------------------------------ #
    def _maybe_reset_day(self, now: datetime) -> None:
        utc_date = now.date() if hasattr(now, "date") else None
        if self._last_date is not None and utc_date != self._last_date:
            self.risk.reset_day()
        self._last_date = utc_date

    def _remember_bar(self, bar: Candle) -> None:
        """Append the closed bar to the adapter's scan series (no dupes).

        The adapter's ``_candles`` is the scan universe; live bars extend
        it so per-bar prefixes ``[: bar_index + 1]`` stay the honest
        known-at-that-time history (same causal contract as backtest).
        """
        candles = self.adapter._candles
        if not candles or candles[-1].timestamp != bar.timestamp:
            candles.append(bar)

    def _bar_index(self, bar: Candle) -> int:
        """Index of ``bar`` inside the adapter's scan series (the anchor).

        The adapter uses it as the no-lookahead scan cap, the §24 expiry
        anchor, and the first-touch window bound — all relative to the
        same growing series, so the last known bar is the honest index.
        """
        return max(len(self.adapter._candles) - 1, 0)

    def _log_missed_bars(self, now: datetime) -> None:
        """Detect feed gaps against the expected next bar timestamp."""
        if self._last_bar_at is None:
            return
        expected = self._last_bar_at + timedelta(minutes=self.timeframe.minutes)
        if now > expected:
            gap_minutes = int((now - expected).total_seconds() // 60)
            gap_bars = max(gap_minutes // self.timeframe.minutes, 1)
            self.kpi.record_missed_bar(at=now, expected_at=expected, gap_bars=gap_bars)

    def _friday_close(self, now: datetime) -> None:
        """§28.4: close ALL positions + cancel ALL pendings (portfolio)."""
        closed = 0
        for snapshot in list(self._broker_positions()):
            outcome = self.broker.close_position(
                snapshot.ticket, snapshot.direction, snapshot.volume
            )
            self.kpi.record_management(
                at=now, op="close", ticket=snapshot.ticket,
                success=outcome.success, latency_ms=outcome.latency_ms,
            )
            if outcome.success:
                closed += 1
                tracked = self._positions.pop(snapshot.ticket, None)
                self.kpi.record_trade_closed(
                    at=now, ticket=snapshot.ticket, kind="friday_eod",
                    win=None,  # honest: live P/L not reconstructed in V1
                    poi_id=tracked.poi_id if tracked else None,
                )
        cancelled = self._cancel_all_pendings(now)
        self.kpi.record_friday_close(at=now, closed=closed, cancelled=cancelled)

    def _hard_cancel_all(self, now: datetime) -> None:
        """§11: cancel every resting pending (open positions stay)."""
        cancelled = self._cancel_all_pendings(now)
        self.kpi.record_hard_cancel(at=now, cancelled=cancelled)

    def _cancel_all_pendings(self, now: datetime) -> int:
        """Cancel every tracked pending through the adapter; count successes."""
        cancelled = 0
        for ticket in sorted(self._pendings):  # deterministic order
            tracked = self._pendings[ticket]
            outcome = self.broker.cancel_pending(ticket)
            self.kpi.record_management(
                at=now, op="cancel", ticket=ticket,
                success=outcome.success, latency_ms=outcome.latency_ms,
            )
            if outcome.success:
                cancelled += 1
                self._pendings.pop(ticket, None)
            _ = tracked  # identity retained only while the order rests
        return cancelled

    def cancel_pending_for_poi(self, poi_id: str) -> int:
        """M4 parity: cancel a violated POI's resting limits (dead thesis)."""
        cancelled = 0
        for ticket in sorted(self._pendings):
            if self._pendings[ticket].poi_id == poi_id:
                outcome = self.broker.cancel_pending(ticket)
                if outcome.success:
                    cancelled += 1
                    self._pendings.pop(ticket, None)
        return cancelled

    # ------------------------------------------------------------------ #
    # Broker observation (fills + closes — broker truth, not simulation)
    # ------------------------------------------------------------------ #
    def _broker_positions(self) -> list:
        return self.broker.positions.list_positions()

    def _observe_fills(self, now: datetime) -> None:
        """Pending → position transitions reported by the broker.

        MT5 convention: a filled pending's position id equals the order
        ticket, so the pending's tracked identity transfers to the
        position keyed by the SAME ticket.
        """
        for snapshot in self._broker_positions():
            tracked = self._pendings.pop(snapshot.ticket, None)
            if tracked is None:
                continue  # not a pending we placed
            self._positions[snapshot.ticket] = _TrackedPosition(
                ticket=snapshot.ticket,
                direction=snapshot.direction,
                volume=snapshot.volume,
                entry_price=snapshot.open_price,
                sl=snapshot.sl,
                poi_id=tracked.poi_id,
                trigger=tracked.trigger,
                route_id=tracked.route_id,
                fvg_context=tracked.fvg_context,
                sweep_level=tracked.sweep_level,
            )
            self.kpi.record_fill(
                at=now, ticket=snapshot.ticket, poi_id=tracked.poi_id,
                trigger=tracked.trigger, volume=snapshot.volume,
            )
            self.risk.on_trade_opened()  # re-arm the BE latch for THIS trade

    def _observe_closes(self, now: datetime) -> None:
        """Position disappearance = closed (SL/TP or manual — broker truth).

        V1 limitation (documented, not faked): the closing deal's exact
        price/kind is not reconstructed from MT5 history, so the win/loss
        is UNKNOWN here — unknown-P/L closes are NOT fed to the circuit
        breaker (``record_result`` must never guess).
        """
        known = set(self._positions)
        seen = {snapshot.ticket for snapshot in self._broker_positions()}
        for ticket in sorted(known - seen):  # deterministic order
            tracked = self._positions.pop(ticket)
            self.kpi.record_trade_closed(
                at=now, ticket=ticket, kind="broker_close", win=None,
                poi_id=tracked.poi_id,
            )

    # ------------------------------------------------------------------ #
    # Exit management (decisions pure, application through the adapter)
    # ------------------------------------------------------------------ #
    def _manage_open_positions(self, bar: Candle, now: datetime) -> None:
        snapshots = {s.ticket: s for s in self._broker_positions()}
        atr = self._current_atr()
        for ticket in sorted(self._positions):  # deterministic order
            tracked = self._positions[ticket]
            snapshot = snapshots.get(ticket)
            if snapshot is None:
                continue  # closed mid-cycle (observed next cycle)
            decision: ExitDecision = self.risk.evaluate_exit(
                PositionState(
                    direction=tracked.direction,
                    entry_price=tracked.entry_price,
                    current_sl=snapshot.sl if snapshot.sl is not None else tracked.entry_price,
                    atr=atr,  # 0.0 disables the ATR-dependent BE gate
                    current_price=bar.close,
                    closed_close=bar.close,  # the just-closed bar (contract)
                    bar_index=self._bar_index(bar),
                ),
                now=now,
                fvg_context=tracked.fvg_context,
            )
            if decision.action is RiskAction.EXIT:
                outcome = self.broker.close_position(
                    ticket, tracked.direction, tracked.volume
                )
                self.kpi.record_management(
                    at=now, op="close", ticket=ticket,
                    success=outcome.success, latency_ms=outcome.latency_ms,
                )
                if outcome.success:
                    self._positions.pop(ticket, None)
                    self.kpi.record_trade_closed(
                        at=now, ticket=ticket, kind=decision.reason or "risk_exit",
                        win=None,  # honest: exit P/L unknown until history
                        poi_id=tracked.poi_id,
                    )
            elif decision.action is RiskAction.MOVE_SL:
                outcome = self.broker.modify_sl(ticket, decision.new_sl)
                self.kpi.record_management(
                    at=now, op="modify_sl", ticket=ticket,
                    success=outcome.success, latency_ms=outcome.latency_ms,
                )
                if outcome.success:
                    self.risk.on_be_applied()  # latch ONLY on real success
                    tracked.sl = decision.new_sl

    # ------------------------------------------------------------------ #
    # Entry step (pipeline → risk gate → broker limit)
    # ------------------------------------------------------------------ #
    def _entry_step(self, bar: Candle, now: datetime) -> None:
        start = self._perf() if self._perf else None
        bar_index = self._bar_index(bar)
        # Drive the REAL pipeline (M4 adapter protocol — scan + feed);
        # candidates arrive through submit_entry().
        self.adapter.generate_candidates(bar, bar_index, now)
        queued = list(self._entry_queue)
        self._entry_queue = []

        placed = blocked = rejected = 0
        for candidate in queued:
            request = EntryRequest(
                direction=candidate.direction,
                entry_price=candidate.entry_price,
                sl_price=candidate.sl_price,
                atr=self._current_atr(),
                current_bar=bar_index,
                now=now,
                equity=self._equity(),
                risk_fraction=self.config.risk_fraction,
                pip_value_per_lot=self.config.pip_value_per_lot,
                min_lots=self.config.min_lots,
                lot_step=self.config.lot_step,
                score=candidate.score,
                current_spread_price=self.config.spread_price,
                sweep_level=candidate.sweep_level,
                news_events=list(self.config.news_events),
                allowed_sessions=self.config.allowed_sessions,
            )
            decision: EntryDecision = self.risk.evaluate_entry(request)
            if decision.action is not RiskAction.ENTER:
                blocked += 1
                continue  # nothing placed, nothing consumed (I2 parity)
            if self.config.dry_run:
                placed += 1  # decision logged; the broker sees nothing
                continue
            outcome = self.broker.place_limit(
                OrderRequest(
                    symbol=self.broker.orders.symbol,
                    kind=OrderKind.LIMIT,
                    direction=candidate.direction,
                    volume=decision.lots,  # policy-sized (§28.7, single path)
                    price=candidate.entry_price,
                    sl=candidate.sl_price,
                    tp=candidate.tp_price,
                    comment=candidate.route_id or "",
                )
            )
            self.kpi.record_order_ack(
                at=now, latency_ms=outcome.latency_ms,
                success=outcome.success, retcode=outcome.retcode,
                ticket=outcome.ticket,
            )
            if outcome.success:
                placed += 1
                self._pendings[outcome.ticket] = _TrackedPending(
                    ticket=outcome.ticket,
                    poi_id=candidate.poi_id,
                    trigger=candidate.trigger,
                    route_id=candidate.route_id,
                    fvg_context=candidate.fvg_context(),
                    sweep_level=candidate.sweep_level,
                    placed_at=now,
                )
                accepted = getattr(self.adapter, "on_candidate_accepted", None)
                if accepted is not None:
                    accepted(candidate)  # consume the §11 one-shot
            else:
                rejected += 1
        latency = (self._perf() - start) * 1000.0 if self._perf else 0.0
        self.kpi.record_decision(
            at=now, latency_ms=latency, candidates=len(queued),
            placed=placed, blocked=blocked, rejected=rejected,
            bar_index=bar_index,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _current_atr(self) -> float:
        """ATR over the adapter's known series (0.0 until enough bars)."""
        from smc.utils.atr import latest_atr

        atr = latest_atr(list(self.adapter._candles), self.config.atr_period)
        return float(atr) if atr is not None else 0.0

    def _equity(self) -> float:
        """Account equity from the connector (broker truth for sizing)."""
        try:
            info = self.connector.account_info()
            if isinstance(info, dict):
                return float(info.get("equity", 0.0) or 0.0)
            return float(getattr(info, "equity", 0.0) or 0.0)
        except Exception:  # noqa: BLE001 — sizing needs a number, not a crash
            return 0.0
