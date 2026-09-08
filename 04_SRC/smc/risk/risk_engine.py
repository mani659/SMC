"""Phase 5 — risk engine orchestrator (v25_DIAG entry gates + exit management
composed into one decision surface).

The engine composes the individually-tested risk components into a single
typed API for the future live / backtest loop (Phase 6/7 runners):

* **Pre-entry gates** — news (existing §11 guard), session (existing §2
  filter), circuit breaker (§28.2), same-level guard (§28.3), sweep guard
  (§28.6) and spread grading (§28.5, optional hard gate) — then risk % band
  clamping + lot sizing (§28.7).
* **Open-position management** — portfolio-level Friday EOD force-close
  (§28.4, consumed ONCE per bar via :meth:`RiskEngine.evaluate_friday_close`
  — never per position), then per-position FVG structural invalidation
  (closed-bar close only) and PureRunner break-even move (§28.1, pure query
  confirmed by :meth:`RiskEngine.on_be_applied`).
* **News hard-cancel (§11)** — :meth:`RiskEngine.hard_cancel_pending` returns
  when ALL pending limit orders must be cancelled (pre-news blackout window).
* **Trade lifecycle** — :meth:`RiskEngine.on_trade_opened` re-arms the
  per-trade PureRunner BE latch; :meth:`RiskEngine.on_be_applied` confirms
  the broker applied the proposed BE modify (v25 sets ``g_beMoved`` only
  inside the successful ``PositionModify`` branch).
* **State updates** — circuit-breaker win/loss, same-level SL close,
  failed-sweep recording, daily rollover (breaker + sweep guard + same-level
  reference — v25 resets all three on a new day).

Deferred (recorded, NOT ported — pending a Lead Architect decision): the
remaining v25 ``TradeAllowed`` gates (daily-loss limit, max daily losses,
max trades/day, MaxDD cooldown, ``InpMaxConsecLoss`` backstop) and the
drawdown-scaled risk multiplier (``GetDDRiskMultiplier``).

Design: every component is dependency-injected (defaults built from
``locked_constants``), all thresholds come only from ``locked_constants``,
and the engine NEVER calls the broker — it returns pure, typed decisions
(:class:`EntryDecision` / :class:`ExitDecision`). Fully unit-testable with
synthetic state; the caller (runner) applies the decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from smc.core.enums import Direction
from smc.execution.news_guard import NewsEvent, should_block_entry, should_hard_cancel
from smc.execution.session_filter import (
    ALL_SESSIONS,
    Session,
    is_allowed_session,
)
from smc.risk.circuit_breaker import CircuitBreaker
from smc.risk.friday_eod import FridayEod
from smc.risk.fvg_invalidation import (
    FvgContext,
    INVALIDATION_REASON_BEAR_BREACHED,
    INVALIDATION_REASON_BULL_BREACHED,
    is_invalidated,
)
from smc.risk.lot_sizing import clamp_risk_fraction, sized_lots
from smc.risk.pure_runner import PureRunner
from smc.risk.same_level_guard import SameLevelGuard
from smc.risk.spread_grading import SpreadGrade, effective_max_spread, grade_for_score
from smc.risk.sweep_guard import SweepGuard

__all__ = [
    "RiskEngine",
    "EntryDecision",
    "ExitDecision",
    "RiskAction",
    "EntryRequest",
    "PositionState",
    "BLOCK_NEWS",
    "BLOCK_SESSION",
    "BLOCK_CIRCUIT_BREAKER",
    "BLOCK_SAME_LEVEL",
    "BLOCK_SWEEP",
    "BLOCK_SPREAD",
    "BLOCK_MIN_LOTS",
]

# --- Entry block reasons (machine-readable, for the runner's log) ----------
BLOCK_NEWS = "news"
BLOCK_SESSION = "session"
BLOCK_CIRCUIT_BREAKER = "circuit_breaker"
BLOCK_SAME_LEVEL = "same_level"
BLOCK_SWEEP = "sweep"
BLOCK_SPREAD = "spread"
BLOCK_MIN_LOTS = "min_lots"


class RiskAction(Enum):
    """What the runner must do with a position / candidate entry."""

    HOLD = "hold"        # no action
    ENTER = "enter"      # place the sized order
    MOVE_SL = "move_sl"  # modify SL to new_sl
    EXIT = "exit"        # close the position now


@dataclass(frozen=True, slots=True)
class EntryRequest:
    """One candidate entry for the pre-entry gates + sizing."""

    direction: Direction
    entry_price: float
    sl_price: float
    atr: float
    current_bar: int
    now: datetime
    # Sizing inputs (broker lot grid + account).
    equity: float
    risk_fraction: float
    pip_value_per_lot: float
    min_lots: float
    lot_step: float
    # Spread grading inputs.
    score: float = 0.0
    # Spread in PRICE units (e.g. 0.35 on gold), NOT MT5 points. It is
    # compared against SPREAD_MAX_ATR × ATR × grade multiplier, which is
    # also in price units (v25 works in SYMBOL_SPREAD points and divides
    # ATR by pointSize — convert at the data boundary, price units here).
    current_spread_price: float = 0.0
    # Optional gates.
    sweep_level: float | None = None   # sweep-guard candidate level
    news_events: list[NewsEvent] = field(default_factory=list)
    allowed_sessions: tuple[Session, ...] | None = ALL_SESSIONS


@dataclass(frozen=True, slots=True)
class EntryDecision:
    """Pre-entry verdict + sized lots (when allowed)."""

    action: RiskAction
    lots: float = 0.0
    blocked_by: str | None = None
    spread_grade: SpreadGrade | None = None


@dataclass(frozen=True, slots=True)
class PositionState:
    """Per-bar open-position snapshot for exit management.

    ``closed_close`` is the CLOSE of the just-closed bar (v25
    ``iClose(_Symbol, PERIOD_CURRENT, 1)``) — FVG structural invalidation
    must never be evaluated on the live/tick price, so the engine consumes
    ONLY this field for the closed-candle test; ``None`` skips the check
    (no closed bar yet). ``bar_index`` identifies that closed bar for the
    runner's logging / cadence bookkeeping (not consumed by the engine).
    """

    direction: Direction
    entry_price: float
    current_sl: float
    atr: float
    current_price: float
    closed_close: float | None = None
    bar_index: int | None = None


@dataclass(frozen=True, slots=True)
class ExitDecision:
    """Per-bar exit-management verdict."""

    action: RiskAction
    reason: str | None = None
    new_sl: float | None = None


class RiskEngine:
    """Composes all risk components into entry/exit/state APIs.

    Every component is injectable (defaults built from ``locked_constants``)
    so the whole engine stays unit-testable with synthetic state. No broker
    calls — pure decisions only.
    """

    def __init__(
        self,
        *,
        circuit_breaker: CircuitBreaker | None = None,
        same_level_guard: SameLevelGuard | None = None,
        sweep_guard: SweepGuard | None = None,
        friday_eod: FridayEod | None = None,
        pure_runner: PureRunner | None = None,
        spread_gate_enabled: bool = True,
    ) -> None:
        self.circuit_breaker = circuit_breaker if circuit_breaker is not None else CircuitBreaker()
        self.same_level_guard = same_level_guard if same_level_guard is not None else SameLevelGuard()
        self.sweep_guard = sweep_guard if sweep_guard is not None else SweepGuard()
        self.friday_eod = friday_eod if friday_eod is not None else FridayEod()
        self.pure_runner = pure_runner if pure_runner is not None else PureRunner()
        self.spread_gate_enabled = spread_gate_enabled

    # ------------------------------------------------------------------ #
    # Pre-entry gates + sizing
    # ------------------------------------------------------------------ #
    def evaluate_entry(self, request: EntryRequest) -> EntryDecision:
        """Run every pre-entry gate in order; first block wins.

        Order follows the v25 entry pipeline (news/session environment →
        safety breaker → re-entry guards → spread quality): news, session,
        circuit breaker, same-level guard, sweep guard, spread grading
        (optional), then risk-band clamping + lot sizing. An undersized lot
        (below ``min_lots``) also blocks the entry.
        """
        if request.news_events and should_block_entry(request.now, request.news_events):
            return EntryDecision(action=RiskAction.HOLD, blocked_by=BLOCK_NEWS)

        if request.allowed_sessions is not None and not is_allowed_session(
            request.now, request.allowed_sessions
        ):
            return EntryDecision(action=RiskAction.HOLD, blocked_by=BLOCK_SESSION)

        if self.circuit_breaker.is_blocked(request.now):
            return EntryDecision(action=RiskAction.HOLD, blocked_by=BLOCK_CIRCUIT_BREAKER)

        if self.same_level_guard.is_blocked(
            new_sl=request.sl_price,
            atr=request.atr,
            current_bar=request.current_bar,
        ):
            return EntryDecision(action=RiskAction.HOLD, blocked_by=BLOCK_SAME_LEVEL)

        if request.sweep_level is not None and self.sweep_guard.is_blocked(
            sweep_level=request.sweep_level,
            atr=request.atr,
            current_bar=request.current_bar,
            is_long=request.direction is Direction.LONG,
        ):
            return EntryDecision(action=RiskAction.HOLD, blocked_by=BLOCK_SWEEP)

        grade = grade_for_score(request.score)
        # v25 skips the float-spread gate when ATR is unavailable
        # (``InpUseFloatSpread && g_atr > 0.0``) — a degenerate ATR must
        # produce a decision here, never an exception.
        if self.spread_gate_enabled and request.atr > 0.0:
            allowed = effective_max_spread(request.score, request.atr)
            if request.current_spread_price > allowed:
                return EntryDecision(
                    action=RiskAction.HOLD,
                    blocked_by=BLOCK_SPREAD,
                    spread_grade=grade,
                )

        sl_distance = abs(request.entry_price - request.sl_price)
        lots = sized_lots(
            equity=request.equity,
            risk_fraction=request.risk_fraction,
            sl_distance=sl_distance,
            pip_value_per_lot=request.pip_value_per_lot,
            min_lots=request.min_lots,
            lot_step=request.lot_step,
        )
        if lots <= 0.0:
            return EntryDecision(
                action=RiskAction.HOLD,
                blocked_by=BLOCK_MIN_LOTS,
                spread_grade=grade,
            )
        return EntryDecision(
            action=RiskAction.ENTER,
            lots=lots,
            spread_grade=grade,
        )

    # ------------------------------------------------------------------ #
    # Open-position management (per bar)
    # ------------------------------------------------------------------ #
    def evaluate_exit(
        self,
        position: PositionState,
        *,
        now: datetime,
        fvg_context: FvgContext | None = None,
    ) -> ExitDecision:
        """Exit verdict for ONE open position (per bar).

        Runner protocol (v25 order of operations — the runner owns the
        loop, the engine only decides):

          1. call :meth:`evaluate_friday_close` ONCE per bar; when True,
             close ALL positions + cancel pending orders and skip
             per-position management for that bar (v25 ``CheckFridayClose``
             clears the whole book in one pass);
          2. otherwise call this method per open position — FVG structural
             invalidation (closes) then PureRunner BE (modifies SL);
          3. on ``MOVE_SL``, apply the modify at the broker and then call
             :meth:`on_be_applied` (the BE decision is a pure query and
             never latches by itself);
          4. call :meth:`on_trade_opened` when a new trade is opened.

        The FVG check consumes ONLY ``position.closed_close`` (the
        just-closed bar's close, v25 ``iClose(..., 1)``) — never the live
        price; with ``closed_close=None`` the check is skipped. ``now`` is
        retained for the runner's logging/cadence contract.
        """
        if fvg_context is not None and position.closed_close is not None:
            invalidated, reason = is_invalidated(
                fvg_context,
                direction=position.direction,
                closed_close=position.closed_close,
            )
            if invalidated:
                return ExitDecision(action=RiskAction.EXIT, reason=reason)

        new_sl = self.pure_runner.be_moved_sl(
            entry_price=position.entry_price,
            direction=position.direction,
            atr=position.atr,
            current_price=position.current_price,
            current_sl=position.current_sl,
        )
        if new_sl is not None:
            return ExitDecision(
                action=RiskAction.MOVE_SL,
                reason="pure_runner_be",
                new_sl=new_sl,
            )
        return ExitDecision(action=RiskAction.HOLD)

    # ------------------------------------------------------------------ #
    # Portfolio-level + lifecycle hooks (runner applies the actions)
    # ------------------------------------------------------------------ #
    def evaluate_friday_close(self, now: datetime) -> bool:
        """Portfolio-level Friday EOD check — call ONCE per bar BEFORE any
        per-position :meth:`evaluate_exit`.

        True exactly once on Friday at/after ``FRIDAY_EOD_CLOSE_HOUR_UTC``;
        the runner then closes ALL positions and cancels pending orders.
        The once-per-Friday latch is owned here so a multi-position book
        cannot have it consumed by a single position's evaluation.
        """
        return self.friday_eod.should_force_close(now)

    def hard_cancel_pending(
        self, now: datetime, news_events: list[NewsEvent]
    ) -> bool:
        """§11 hard-cancel: True when ALL pending limit orders must be
        cancelled right now (high-impact event inside
        ``NEWS_HARD_CANCEL_MINUTES``). The runner performs the
        cancellations via ``OrderManager``."""
        return should_hard_cancel(now, news_events)

    def on_trade_opened(self) -> None:
        """Runner hook: a new trade was opened — re-arms per-trade exit
        state (resets the PureRunner BE latch so THIS trade gets its own
        BE opportunity; v25 resets ``g_beMoved`` on every new position)."""
        self.pure_runner.reset_trade()

    def on_be_applied(self) -> None:
        """Runner hook: the BE modify proposed by :meth:`evaluate_exit` was
        applied at the broker — sets the one-shot PureRunner latch so BE
        never moves twice for this trade (v25 sets ``g_beMoved`` only on a
        successful ``PositionModify``)."""
        self.pure_runner.mark_be_applied()

    # ------------------------------------------------------------------ #
    # State updates
    # ------------------------------------------------------------------ #
    def record_result(self, win: bool, at: datetime) -> None:
        """Record a closed trade's win/loss (circuit breaker)."""
        self.circuit_breaker.record_result(win=win, at=at)

    def record_sl_close(self, sl_level: float, bar_index: int) -> None:
        """Record a closed trade's SL level (same-level guard)."""
        self.same_level_guard.record_close(sl_level=sl_level, bar_index=bar_index)

    def record_failed_sweep(
        self, *, sweep_level: float, bar_index: int, is_long: bool
    ) -> None:
        """Record a failed sweep on a losing close (sweep guard)."""
        self.sweep_guard.record_failed_sweep(
            sweep_level=sweep_level, bar_index=bar_index, is_long=is_long
        )

    def reset_day(self) -> None:
        """Daily rollover: clear circuit breaker, sweep guard AND same-level
        guard state (v25's daily block resets ``consecLosses``, the
        failed-sweep guards and ``g_lastSLLevel`` on a new day)."""
        self.circuit_breaker.reset_day()
        self.sweep_guard.reset_day()
        self.same_level_guard.reset()

    # ------------------------------------------------------------------ #
    @staticmethod
    def clamp_risk_fraction(risk_fraction: float) -> float:
        """Delegate to the single §28.7 band clamp (no parallel sizing path)."""
        return clamp_risk_fraction(risk_fraction)