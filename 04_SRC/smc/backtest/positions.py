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
from smc.backtest.cost_model import (
    CostBreakdown,
    CostModel,
    normalize_spread,
)
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
    # Identity enrichment (logging only — copied verbatim on SL modifies).
    model_tags: tuple | None = None
    pillar_path: str | None = None
    disp_magnitude_atr: float | None = None
    # Placement-time geometry (logging only — modify_sl MUST copy these
    # unchanged while moving sl; enforced by test).
    original_sl: float | None = None
    zone_low: float | None = None
    zone_high: float | None = None
    signal_data_json: str | None = None
    # E1: trigger entry-anchor provenance (see CandidateEntry.entry_anchor);
    # copied verbatim on SL modifies (same invariant as original_sl).
    entry_anchor: str | None = None
    # Structural TP provenance (see CandidateEntry.tp_source). Logging/audit
    # only — never read by risk/fill/BE logic; copied verbatim on SL
    # modifies (same invariant as entry_anchor).
    tp_source: str | None = None
    # Entry-leg spread (PRICE units) known at fill time — cost input only
    # (never read by risk/fill logic). Normalized: None = unknown (the
    # legacy spread_price=0.0 means "gate off", never "zero spread"), so a
    # non-positive value is stored as None and falls back per CostConfig.
    # Copied verbatim on SL modifies (same invariant as entry_anchor).
    entry_spread_price: float | None = None


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
    # V1 cost ledger (Tier-1, 2026-10-11): additive per-close attribution.
    # Gross ``realized_pnl`` is NEVER rewritten — consumers net it as
    # ``realized_pnl - cost_ledger`` (see cost_model.net_ledger). All USD
    # legs default 0.0 (legacy zero-cost path reproduces exactly).
    commission_usd: float = 0.0
    spread_cost_usd: float = 0.0
    slippage_usd: float = 0.0
    swap_usd: float = 0.0    # always 0.0 in V1 (deferred by ruling)
    cost_usd: float = 0.0    # sum of the four legs above
    cost_ledger: float = 0.0  # cost_usd / pip_value_per_lot
    # Holding duration in execution bars (exit_bar - entry_bar). None =
    # unknown/legacy (never invented) — recorded so deferred swap stays
    # backfillable without a re-run.
    bars_held: int | None = None


@dataclass(slots=True)
class PositionStore:
    """In-memory open-position store for the backtest."""

    first_ticket: int = 1
    _open: list[BacktestPosition] = field(default_factory=list)
    _closed: list[ClosedPosition] = field(default_factory=list)
    _next_ticket: int | None = None
    # Bound V1 cost pricer (None = unbound → every close prices at zero
    # cost, the legacy path). The runner binds this from RunnerConfig at
    # construction; store-level tests stay unbound by default. Excluded
    # from repr/compare — bookkeeping, not trade state.
    _cost_model: CostModel | None = field(default=None, init=False,
                                          repr=False, compare=False)

    def bind_cost_model(self, model: CostModel | None) -> None:
        """Bind (or unbind, with None) the V1 cost pricer for new closes."""
        self._cost_model = model

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
        model_tags: tuple | None = None,
        pillar_path: str | None = None,
        disp_magnitude_atr: float | None = None,
        original_sl: float | None = None,
        zone_low: float | None = None,
        zone_high: float | None = None,
        signal_data_json: str | None = None,
        entry_anchor: str | None = None,
        tp_source: str | None = None,
        entry_spread_price: float | None = None,
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
            model_tags=model_tags,
            pillar_path=pillar_path,
            disp_magnitude_atr=disp_magnitude_atr,
            original_sl=original_sl,
            zone_low=zone_low,
            zone_high=zone_high,
            signal_data_json=signal_data_json,
            entry_anchor=entry_anchor,
            tp_source=tp_source,
            entry_spread_price=normalize_spread(entry_spread_price),
        )
        self._next_ticket += 1
        self._open.append(position)
        return position

    # ------------------------------------------------------------------ #
    # Per-bar management
    # ------------------------------------------------------------------ #
    def apply_bar(self, bar: Candle, bar_index: int,
                  *, exit_spread_price: float | None = None
                  ) -> list[ClosedPosition]:
        """Evaluate SL/TP for every open position over ``bar``.

        Uses :func:`fill_model.evaluate_position_bar` (SL-first on same-bar
        conflicts). Closes are applied in fill order — deterministic.
        ``exit_spread_price`` is the spread known on this bar (cost input
        only; None = unknown → fallback per CostConfig).
        Returns the closed positions for this bar (possibly empty).
        """
        closed: list[ClosedPosition] = []
        for position in list(self._open):  # copy — closes mutate the list
            decision: BarClose = evaluate_position_bar(
                position.direction, position.sl, position.tp, bar
            )
            if not decision.closed:
                continue
            closed.append(self._close(position, decision, bar, bar_index,
                                      exit_spread_price=exit_spread_price))
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
        exit_spread_price: float | None = None,
    ) -> ClosedPosition:
        """Explicitly close one position (runner-driven close, e.g. a risk
        exit). ``win`` may be omitted for price-symmetric kinds — it is
        then derived from the exit direction relative to entry (LONG:
        ``exit_price > entry_price``). ``exit_spread_price`` is the spread
        known on the exit bar (cost input only). Raises ``KeyError`` for an
        unknown ticket."""
        for index, position in enumerate(self._open):
            if position.ticket == ticket:
                if win is None:
                    win = self._derive_win(position, exit_price)
                decision = BarClose(closed=True, kind=kind, price=exit_price, win=win)
                return self._close(position, decision, None, exit_bar,
                                   exit_at=exit_at,
                                   exit_spread_price=exit_spread_price)
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
                    model_tags=position.model_tags,
                    pillar_path=position.pillar_path,
                    disp_magnitude_atr=position.disp_magnitude_atr,
                    # Placement-time geometry rides along UNCHANGED while
                    # only sl moves (the BE-preservation invariant).
                    original_sl=position.original_sl,
                    zone_low=position.zone_low,
                    zone_high=position.zone_high,
                    signal_data_json=position.signal_data_json,
                    entry_anchor=position.entry_anchor,
                    tp_source=position.tp_source,
                    entry_spread_price=position.entry_spread_price,
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
        *,
        exit_spread_price: float | None = None,
    ) -> ClosedPosition:
        self._open.remove(position)
        if exit_at is None:
            exit_at = bar.timestamp if bar is not None else position.entry_at
        direction_sign = 1.0 if position.direction is Direction.LONG else -1.0
        realized = (decision.price - position.entry_price) * direction_sign * position.volume
        # V1 cost ledger: both legs priced here (entry leg from the spread
        # recorded at fill, exit leg from this bar). Unbound store (legacy
        # path, incl. store-level tests) prices at zero — gross untouched.
        model = self._cost_model
        if model is None:
            costs = CostBreakdown.zero()
        else:
            costs = model.quote_close(
                lots=position.volume,
                entry_spread=position.entry_spread_price,
                exit_spread=normalize_spread(exit_spread_price),
                exit_kind=decision.kind,
            )
        record = ClosedPosition(
            position=position,
            exit_price=decision.price,
            exit_bar=exit_bar,
            exit_at=exit_at,
            kind=decision.kind,
            win=bool(decision.win),
            realized_pnl=realized,
            commission_usd=costs.commission_usd,
            spread_cost_usd=costs.spread_cost_usd,
            slippage_usd=costs.slippage_usd,
            swap_usd=costs.swap_usd,
            cost_usd=costs.cost_usd,
            cost_ledger=costs.cost_ledger,
            bars_held=exit_bar - position.entry_bar,
        )
        self._closed.append(record)
        return record
