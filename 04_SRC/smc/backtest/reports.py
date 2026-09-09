"""Phase 6 M5 — core reports: a pure projection over completed run data.

Reporting CONSUMES results, it never owns the loop: :func:`build_report`
turns a completed run's artifacts — the position store's
:class:`~smc.backtest.positions.ClosedPosition` history, the runner's
blocked-entry log, and the runner's ticket → ``route_id`` map — into one
deterministic :class:`BacktestReport`. No MT5, no wall clock, no trading
logic: identical inputs always produce an identical report object (and an
identical JSON export, see :mod:`smc.backtest.export`).

Metrics definitions (V1, frozen for this milestone):

* **win** — the close record's own flag (SL → loss, TP → win; runner-driven
  closes derive it price-symmetrically in the store).
* **P/L** — ``ClosedPosition.realized_pnl`` verbatim (price units × volume
  × direction sign; raw V1 units, no contract-size conversion).
* **win_rate** — wins / trades; 0.0 on an empty run (defined zero).
* **gross_profit / gross_loss** — sum of winning / losing P/L, the loss
  side reported as a POSITIVE magnitude.
* **profit_factor** — gross_profit / gross_loss. Zero-loss case (explicit,
  documented): ``None`` — an infinite PF is not representable in V1 JSON;
  an empty or all-flat run also yields ``None``.
* **net_pnl** — sum of all P/L.
* **max_drawdown** — peak-to-trough on the closed-trade equity curve
  (cumulative P/L in close order); ≥ 0, 0.0 on an empty/never-losing run.
  Intrabar MAE/MFE is explicitly out of V1 scope.
* **avg_win / avg_loss** — gross_profit / wins and gross_loss / losses;
  ``None`` when the side has no trades.

Breakdowns (identity fields already preserved by M4):

* per trigger — the trade's normalized ``trigger`` string (the §11 trigger
  type; ``None`` → the ``"unattributed"`` bucket);
* per POI — the trade's ``poi_id`` (``None`` → ``"unattributed"``).
* Model tags are NOT carried on closed positions (they live on the POI
  object, which reporting must not reach into) — per-POI grouping is the
  best honest mapping available; tags are not invented.

Blocked-entry visibility: counts by ``blocked_by`` reason, straight from
the runner's log. Cancelled/expired pendings are NOT counted — the M2
stores do not track cancellation events (nothing fabricated).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from smc.backtest.positions import ClosedPosition
from smc.backtest.runner import RunnerResult

__all__ = [
    "TradeRecord",
    "GroupMetrics",
    "CoreMetrics",
    "BacktestReport",
    "build_report",
]

UNATTRIBUTED = "unattributed"


@dataclass(frozen=True, slots=True)
class TradeRecord:
    """One normalized closed trade (the trade list row)."""

    ticket: int
    direction: object                 # Direction enum (raw — serialization normalizes)
    symbol: str
    volume: float
    entry_price: float
    exit_price: float
    sl: float | None
    tp: float | None
    entry_bar: int
    exit_bar: int
    entry_at: object                  # injected UTC datetime
    exit_at: object                   # injected UTC datetime
    close_kind: str                   # CloseKind / runner reason string
    win: bool
    pnl: float                        # realized_pnl verbatim (V1 raw units)
    poi_id: str | None
    trigger: str | None               # normalized trigger type value
    route_id: str | None              # §11 event identity (None when absent)

    @classmethod
    def from_closed(
        cls, record: ClosedPosition, route_id: str | None = None
    ) -> "TradeRecord":
        """Normalize one store close record (trigger → value string)."""
        trigger = record.position.trigger
        trigger_str: str | None
        if trigger is None:
            trigger_str = None
        elif hasattr(trigger, "value"):
            trigger_str = str(trigger.value)
        else:
            trigger_str = str(trigger)
        return cls(
            ticket=record.position.ticket,
            direction=record.position.direction,
            symbol=record.position.symbol,
            volume=record.position.volume,
            entry_price=record.position.entry_price,
            exit_price=record.exit_price,
            sl=record.position.sl,
            tp=record.position.tp,
            entry_bar=record.position.entry_bar,
            exit_bar=record.exit_bar,
            entry_at=record.position.entry_at,
            exit_at=record.exit_at,
            close_kind=record.kind,
            win=bool(record.win),
            pnl=record.realized_pnl,
            poi_id=record.position.poi_id,
            trigger=trigger_str,
            route_id=route_id,
        )


@dataclass(frozen=True, slots=True)
class CoreMetrics:
    """Core run metrics (V1 mandatory set — see module docstring)."""

    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float                    # 0.0 on an empty run
    gross_profit: float
    gross_loss: float                  # positive magnitude
    profit_factor: float | None        # None when gross_loss == 0 (documented)
    net_pnl: float
    max_drawdown: float                # ≥ 0, closed-trade equity curve
    avg_win: float | None              # None when no winners
    avg_loss: float | None             # None when no losers


@dataclass(frozen=True, slots=True)
class GroupMetrics:
    """Aggregate metrics for one breakdown group (same semantics as CoreMetrics)."""

    key: str
    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    net_pnl: float
    avg_win: float | None
    avg_loss: float | None


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """The completed-run report (pure data — export/sort freely)."""

    trades: tuple[TradeRecord, ...]
    metrics: CoreMetrics
    by_trigger: dict[str, GroupMetrics]   # sorted keys — deterministic
    by_poi: dict[str, GroupMetrics]       # sorted keys — deterministic
    blocked_by_reason: dict[str, int]     # reason → count (sorted keys)


# ---------------------------------------------------------------------- #
# Pure metric helpers
# ---------------------------------------------------------------------- #
def _profit_factor(gross_profit: float, gross_loss: float) -> float | None:
    """GP/GL with the zero-loss case explicit: None (never a fabricated inf)."""
    if gross_loss > 0.0:
        return gross_profit / gross_loss
    return None


def _aggregate(key: str, pnls: list[float]) -> GroupMetrics:
    """GroupMetrics over one group's P/L list (close order preserved)."""
    wins = [p for p in pnls if p > 0.0]
    losses = [p for p in pnls if p <= 0.0]
    gross_profit = sum(wins)
    gross_loss = sum(-p for p in losses)  # positive magnitude
    return GroupMetrics(
        key=key,
        n_trades=len(pnls),
        n_wins=len(wins),
        n_losses=len(losses),
        win_rate=(len(wins) / len(pnls)) if pnls else 0.0,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=_profit_factor(gross_profit, gross_loss),
        net_pnl=sum(pnls),
        avg_win=(gross_profit / len(wins)) if wins else None,
        avg_loss=(gross_loss / len(losses)) if losses else None,
    )


def _max_drawdown(pnls: list[float]) -> float:
    """Peak-to-trough on the closed-trade equity curve (close order)."""
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        if equity > peak:
            peak = equity
        drawdown = peak - equity
        if drawdown > max_dd:
            max_dd = drawdown
    return max_dd


def _group(
    trades: tuple[TradeRecord, ...], key_of
) -> dict[str, GroupMetrics]:
    """Aggregate trades into sorted-key groups (deterministic order)."""
    buckets: dict[str, list[float]] = {}
    for trade in trades:
        buckets.setdefault(key_of(trade), []).append(trade.pnl)
    return {
        key: _aggregate(key, pnls)
        for key, pnls in sorted(buckets.items())
    }


# ---------------------------------------------------------------------- #
# Entry point
# ---------------------------------------------------------------------- #
def build_report(
    result: RunnerResult,
) -> BacktestReport:
    """Project a completed run's :class:`~smc.backtest.runner.RunnerResult`
    into a :class:`BacktestReport`.

    Pure and total: an empty run yields defined zeros (win_rate 0.0,
    max_drawdown 0.0, ``None`` for the undefined ratios) and empty
    breakdowns — never a crash, never fabricated values.
    """
    trades = tuple(
        TradeRecord.from_closed(record, route_id=result.route_ids.get(record.position.ticket))
        for record in result.closed
    )
    pnls = [trade.pnl for trade in trades]
    wins = [p for p in pnls if p > 0.0]
    losses = [p for p in pnls if p <= 0.0]
    gross_profit = sum(wins)
    gross_loss = sum(-p for p in losses)
    metrics = CoreMetrics(
        n_trades=len(trades),
        n_wins=len(wins),
        n_losses=len(losses),
        win_rate=(len(wins) / len(trades)) if trades else 0.0,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=_profit_factor(gross_profit, gross_loss),
        net_pnl=sum(pnls),
        max_drawdown=_max_drawdown(pnls),
        avg_win=(gross_profit / len(wins)) if wins else None,
        avg_loss=(gross_loss / len(losses)) if losses else None,
    )
    blocked_counts = Counter(entry.blocked_by for entry in result.blocked)
    return BacktestReport(
        trades=trades,
        metrics=metrics,
        by_trigger=_group(trades, lambda t: t.trigger or UNATTRIBUTED),
        by_poi=_group(trades, lambda t: t.poi_id or UNATTRIBUTED),
        blocked_by_reason=dict(sorted(blocked_counts.items())),
    )
