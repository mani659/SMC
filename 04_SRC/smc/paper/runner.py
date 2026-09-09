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
the broker reports a position whose (symbol, magic, comment) matches
the pending's order identity (MT5 ``POSITION_MAGIC`` /
``POSITION_COMMENT`` carry from the order to the position record; the
position's own ticket is a DIFFERENT identifier from the order ticket,
so ticket equality is never used as a fill key — audit C2); a position
is CLOSED when it disappears from ``positions_get``. Close outcomes are
determined HONESTLY from tracked state (coherence patch CR2): runner-
issued closes (Friday EOD / risk exit) exit at the bar close price, so
win/loss is exact; broker closes are matched to THIS bar's range — an
SL-piercing bar means the stop-loss closed (loss → circuit breaker +
same-level guard), a TP-reaching bar means take-profit closed (win),
and a bar reaching neither (or both levels ambiguously) stays UNKNOWN
and feeds no guard (documented V1 limitation; the closing deal's exact
price/kind/P/L is not reconstructed from MT5 history in V1).

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
from smc.triggers.trigger_expiry import poi_give_up_bars
from smc.validation.state_machine import expiry_bars_for
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
    """A pending we placed at the broker (identity kept client-side).

    ``symbol`` / ``magic`` / ``comment`` are the order-identity linkage
    used to match a broker fill back to THIS pending (M6 audit fix): in
    MT5 the filled position's ticket differs from the order ticket, so
    fills are matched on (symbol, magic, comment) — the fields that carry
    through from the order to the position record.
    """

    ticket: int
    poi_id: str | None
    trigger: object
    route_id: str | None
    fvg_context: object | None
    sweep_level: float | None
    placed_at: datetime
    symbol: str = ""
    magic: int | None = None
    comment: str = ""


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
    tp: float | None = None


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
        # I2: wire the REAL M4 adapter in directly (its ``attach`` sets
        # ``adapter._runner`` and calls ``set_pipeline_adapter``), so the
        # identical adapter object drives backtest AND paper without a
        # manual wiring step. Protocol-conformant stubs without ``attach``
        # (tests) bind themselves as before.
        attach = getattr(self.adapter, "attach", None)
        if callable(attach):
            attach(self)

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
            self._friday_close(now, bar)
            self._last_bar_at = now
            return

        # 3. §11 news hard-cancel of pending limits.
        if self.config.news_events and self.risk.hard_cancel_pending(
            now, self.config.news_events
        ):
            self._hard_cancel_all(now)

        # 3b. C1: §23/§24 unfilled-order age expiry. The broker places GTC
        # orders (no MT5-side expiry), so the runner cancels by age:
        # M5 = 12 / M1 = 30 bars; the §24 give-up backstop elsewhere.
        self._expire_pendings(now)

        # 4. Observe the broker: fills + closes (broker truth).
        self._observe_fills(now)
        self._observe_closes(now, bar)

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

    def _friday_close(self, now: datetime, bar: Candle) -> None:
        """§28.4: close ALL positions + cancel ALL pendings (portfolio).

        The forced close exits at the bar close price (the same convention
        as the backtest runner's risk exits), so win/loss is exact and the
        circuit breaker / sweep guard are fed honestly (CR2).
        """
        bar_index = self._bar_index(bar)
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
                win = self._derive_close_win(tracked, bar.close)
                if tracked is not None and win is not None:
                    self._feed_risk_close(
                        tracked, win=win, sl_level=None,
                        now=now, bar_index=bar_index,
                    )
                self.kpi.record_trade_closed(
                    at=now, ticket=snapshot.ticket, kind="friday_eod",
                    win=win,
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

    def _expire_pendings(self, now: datetime) -> None:
        """C1: §23/§24 unfilled-order age expiry (runner-side, audit fix).

        The broker places GTC pendings (``ORDER_TIME_GTC`` — no MT5-side
        expiry), so the runner cancels by AGE: M5 = 12 / M1 = 30 bars
        (§23); timeframes without a frozen rule fall back to the §24
        give-up backstop (20 bars). Cancelled pendings emit a
        ``management`` KPI record; the POI one-shot was already consumed
        at placement, so no engine state is touched here.
        """
        limit = expiry_bars_for(self.timeframe)
        if limit is None:
            limit = poi_give_up_bars()
        bar_seconds = self.timeframe.minutes * 60
        for ticket in sorted(self._pendings):  # deterministic order
            tracked = self._pendings[ticket]
            age_bars = int((now - tracked.placed_at).total_seconds() // bar_seconds)
            if age_bars < limit:
                continue
            outcome = self.broker.cancel_pending(ticket)
            self.kpi.record_management(
                at=now, op="cancel", ticket=ticket,
                success=outcome.success, latency_ms=outcome.latency_ms,
            )
            if outcome.success:
                self._pendings.pop(ticket, None)

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

        Fill matching is by ORDER IDENTITY LINKAGE, not ticket equality
        (M6 audit fix): in MT5 a filled pending's position ticket is a
        DIFFERENT identifier from the order ticket, so a pending is
        matched to a position on (symbol, magic, comment) — the fields
        that carry from the order record to the position record
        (POSITION_SYMBOL / POSITION_MAGIC / POSITION_COMMENT). The
        pending's tracked identity transfers to the position keyed by the
        POSITION's ticket.
        """
        by_linkage: dict[tuple, list[int]] = {}
        for ticket, tracked in self._pendings.items():
            key = (tracked.symbol, tracked.magic, tracked.comment)
            by_linkage.setdefault(key, []).append(ticket)
        for snapshot in self._broker_positions():
            key = (snapshot.symbol, snapshot.magic, snapshot.comment)
            candidates = by_linkage.get(key) or []
            ticket = candidates.pop(0) if candidates else None
            if ticket is None:
                continue  # not a pending we placed (identity never guessed)
            tracked = self._pendings.pop(ticket, None)
            if tracked is None:
                continue
            self._positions[snapshot.ticket] = _TrackedPosition(
                ticket=snapshot.ticket,
                direction=snapshot.direction,
                volume=snapshot.volume,
                entry_price=snapshot.open_price,
                sl=snapshot.sl,
                tp=snapshot.tp,
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

    def _observe_closes(self, now: datetime, bar: Candle) -> None:
        """Position disappearance = closed (SL/TP or manual — broker truth).

        Honest local determination (CR2): when THIS closed bar's range can
        only have triggered one protective level, the outcome is KNOWN —
        an SL-piercing bar means a stop-loss close (loss → circuit breaker
        + same-level guard + sweep guard when a sweep level is tracked), a
        TP-reaching bar means a take-profit close (win → circuit breaker).
        SL-first is the same-bar tie-break (mirrors the backtest fill
        model). A bar reaching neither level leaves the outcome UNKNOWN
        and no guard is fed — the V1 limitation stays honest (the closing
        deal's exact price/kind/P/L is not reconstructed from MT5
        history).
        """
        bar_index = self._bar_index(bar)
        known = set(self._positions)
        seen = {snapshot.ticket for snapshot in self._broker_positions()}
        for ticket in sorted(known - seen):  # deterministic order
            tracked = self._positions.pop(ticket)
            win: bool | None = None
            kind = "broker_close"
            sl_level: float | None = None
            if tracked.direction is Direction.LONG:
                if tracked.sl is not None and bar.low <= tracked.sl:
                    win, kind, sl_level = False, "stop_loss", tracked.sl
                elif tracked.tp is not None and bar.high >= tracked.tp:
                    win, kind = True, "take_profit"
            else:
                if tracked.sl is not None and bar.high >= tracked.sl:
                    win, kind, sl_level = False, "stop_loss", tracked.sl
                elif tracked.tp is not None and bar.low <= tracked.tp:
                    win, kind = True, "take_profit"
            if win is not None:
                self._feed_risk_close(
                    tracked, win=win, sl_level=sl_level,
                    now=now, bar_index=bar_index,
                )
            self.kpi.record_trade_closed(
                at=now, ticket=ticket, kind=kind, win=win,
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
                    # Risk exit at the bar close price → exact P/L (CR2).
                    win = self._derive_close_win(tracked, bar.close)
                    if win is not None:
                        self._feed_risk_close(
                            tracked, win=win, sl_level=None,
                            now=now, bar_index=self._bar_index(bar),
                        )
                    self.kpi.record_trade_closed(
                        at=now, ticket=ticket, kind=decision.reason or "risk_exit",
                        win=win,
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
        # I4: retire terminal engine POIs (ids with resting pendings or
        # open positions retained; workflow-live + touch-window ids are
        # retained inside the adapter) before this bar's scan.
        self._prune_engine_state(bar_index)
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
                # dry-run: the decision was evaluated and logged, but no
                # order reached the broker and the §11 one-shot is not
                # consumed. ``placed`` counts "would have placed" accepted
                # verdicts, not broker acks.
                placed += 1
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
                    # Fill-linkage identity (M6 audit fix): the broker
                    # matches a fill to this pending on these fields — the
                    # order's symbol/magic/comment carry to the position.
                    symbol=self.broker.orders.symbol,
                    magic=getattr(self.broker.orders, "magic", None),
                    comment=candidate.route_id or "",
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
    def _derive_close_win(self, tracked, exit_price: float) -> bool | None:
        """Win/loss for a runner-issued close at a KNOWN price (exact)."""
        if tracked is None:
            return None
        if tracked.direction is Direction.LONG:
            return exit_price > tracked.entry_price
        return exit_price < tracked.entry_price

    def _feed_risk_close(
        self, tracked, *, win: bool, sl_level: float | None,
        now: datetime, bar_index: int,
    ) -> None:
        """CR2: feed a closed trade's outcome into the risk guards.

        Circuit breaker (win/loss) always; same-level guard when the close
        was a stop-loss (``sl_level`` known); sweep guard when the trade
        carried a sweep level and the close was a loss — the exact same
        feeding rule the backtest runner uses (never fabricated).
        """
        self.risk.record_result(win=win, at=now)
        if sl_level is not None:
            self.risk.record_sl_close(sl_level=sl_level, bar_index=bar_index)
        if not win and tracked.sweep_level not in (None, 0.0):
            self.risk.record_failed_sweep(
                sweep_level=tracked.sweep_level,
                bar_index=bar_index,
                is_long=tracked.direction is Direction.LONG,
            )

    def _prune_engine_state(self, bar_index: int) -> None:
        """I4: retire terminal engine POIs (workflow-live ids kept)."""
        engine = getattr(self.adapter, "engine", None)
        if engine is None:
            return  # protocol stubs without an engine keep everything
        prune = getattr(self.adapter, "prune_terminal_pois", None)
        retain = {t.poi_id for t in self._pendings.values() if t.poi_id}
        retain |= {p.poi_id for p in self._positions.values() if p.poi_id}
        if callable(prune):
            prune(retain, bar_index)
        else:
            engine.prune_terminal(retain)

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
