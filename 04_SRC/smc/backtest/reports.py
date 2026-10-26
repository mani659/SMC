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
* **V1 costs (Tier-1, 2026-10-11)** — every existing metric above stays
  GROSS (frozen semantics, byte-stable). Costs ride alongside: each trade
  carries ``commission_usd / spread_cost_usd / slippage_usd / swap_usd``
  (always 0.0 swap in V1), ``cost_usd`` (their sum), ``pnl_net``
  (``pnl - cost_ledger``), and ``bars_held``; aggregates carry
  ``total_cost_usd`` (+ per-component totals) and ``net_pnl_after_cost``.
  A ``pnl_net`` of ``None`` on a hand-built record means "derive as
  gross" (never invented per-trade economics).
* **Track-B research annotations (harness, 2026-10-11)** — carried data
  ONLY, never read by any decision logic: ``f_timing_label`` (frozen
  Rule v1 timing character, F rows; ``None`` = not annotated) and
  ``post_exit_class`` (frozen post-exit taxonomy; ``None`` = not
  annotated). Groups expose ``by_timing_label`` (``None`` folds into
  the ``"unknown"`` bucket) and ``by_post_exit_class`` (``None`` folds
  into ``"DATA_GAP"``). Annotation is a research post-step over
  exported timestamps + canonical series; unresolvable geometry stays
  ``"unknown"`` / ``DATA_GAP`` — never invented, never a filter.

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
from dataclasses import dataclass, field

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
    model_tags: tuple | None = None   # POI model tag names (None = unknown)
    pillar_path: str | None = None    # validation path summary (None = unknown)
    disp_magnitude_atr: float | None = None  # displacement ATR multiple (None = unknown)
    original_sl: float | None = None  # placement stop (NEVER BE-modified)
    zone_low: float | None = None     # POI zone bottom at route time
    zone_high: float | None = None    # POI zone top at route time
    signal_data_json: str | None = None  # trigger signal data (JSON, or None)
    entry_anchor: str | None = None   # E1: trigger entry-anchor provenance
                                      # (None = unknown — never invented)
    tp_source: str | None = None      # structural TP provenance: "structural_swing"
                                      # | "atr_fallback" (None = unknown/legacy)
    # V1 cost ledger (Tier-1, 2026-10-11) — appended, backward compatible.
    # ``pnl`` above stays gross-verbatim; ``pnl_net`` is the after-cost
    # ledger (None on hand-built records = derive as gross, see _net_of).
    commission_usd: float = 0.0
    spread_cost_usd: float = 0.0
    slippage_usd: float = 0.0
    swap_usd: float = 0.0             # always 0.0 in V1 (deferred by ruling)
    cost_usd: float = 0.0             # sum of the four legs above
    pnl_net: float | None = None      # after-cost ledger units
    bars_held: int | None = None      # exit_bar - entry_bar (None = unknown)
    # Track-B research annotations (harness — carried data only, NEVER
    # read by risk/fill/trigger logic; see module docstring). None = not
    # annotated (no series supplied at report time).
    f_timing_label: str | None = None  # frozen Rule v1 (F rows; None else)
    post_exit_class: str | None = None  # frozen post-exit taxonomy

    @classmethod
    def from_closed(
        cls, record: ClosedPosition, route_id: str | None = None,
        *, f_timing_label: str | None = None,
        post_exit_class: str | None = None,
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
        tags = record.position.model_tags
        tags = tuple(tags) if tags is not None else None
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
            model_tags=tags,
            pillar_path=record.position.pillar_path,
            disp_magnitude_atr=record.position.disp_magnitude_atr,
            original_sl=record.position.original_sl,
            zone_low=record.position.zone_low,
            zone_high=record.position.zone_high,
            signal_data_json=record.position.signal_data_json,
            entry_anchor=record.position.entry_anchor,
            tp_source=record.position.tp_source,
            commission_usd=record.commission_usd,
            spread_cost_usd=record.spread_cost_usd,
            slippage_usd=record.slippage_usd,
            swap_usd=record.swap_usd,
            cost_usd=record.cost_usd,
            pnl_net=record.realized_pnl - record.cost_ledger,
            bars_held=record.bars_held,
            f_timing_label=f_timing_label,
            post_exit_class=post_exit_class,
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
    # V1 cost totals (Tier-1) — appended; existing fields stay gross.
    total_commission_usd: float = 0.0
    total_spread_cost_usd: float = 0.0
    total_slippage_usd: float = 0.0
    total_swap_usd: float = 0.0        # always 0.0 in V1
    total_cost_usd: float = 0.0        # sum of the four totals above
    net_pnl_after_cost: float = 0.0    # ledger net (same units as net_pnl)


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
    # V1 cost totals (Tier-1) — appended; existing fields stay gross.
    net_pnl_after_cost: float = 0.0    # ledger net (same units as net_pnl)
    total_cost_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """The completed-run report (pure data — export/sort freely)."""

    trades: tuple[TradeRecord, ...]
    metrics: CoreMetrics
    by_trigger: dict[str, GroupMetrics]   # sorted keys — deterministic
    by_poi: dict[str, GroupMetrics]       # sorted keys — deterministic
    blocked_by_reason: dict[str, int]     # reason → count (sorted keys)
    # Track-B research breakdowns (harness — always present; unannotated
    # runs fold into the "unknown" / "DATA_GAP" single buckets).
    by_timing_label: dict[str, GroupMetrics] = field(default_factory=dict)
    by_post_exit_class: dict[str, GroupMetrics] = field(default_factory=dict)


# ---------------------------------------------------------------------- #
# Pure metric helpers
# ---------------------------------------------------------------------- #
def _profit_factor(gross_profit: float, gross_loss: float) -> float | None:
    """GP/GL with the zero-loss case explicit: None (never a fabricated inf)."""
    if gross_loss > 0.0:
        return gross_profit / gross_loss
    return None


def _net_of(trade: TradeRecord) -> float:
    """After-cost ledger for one trade (None = derive as gross)."""
    if trade.pnl_net is None:
        return trade.pnl
    return trade.pnl_net


def _aggregate(key: str, pnls: list[float], *,
               nets: list[float] | None = None,
               cost_usds: list[float] | None = None) -> GroupMetrics:
    """GroupMetrics over one group's P/L list (close order preserved).

    ``nets``/``cost_usds`` default to gross/zero so direct callers keep
    legacy semantics; :func:`_group` always passes the trade-led fields.
    """
    if nets is None:
        nets = list(pnls)
    if cost_usds is None:
        cost_usds = [0.0] * len(pnls)
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
        net_pnl_after_cost=sum(nets),
        total_cost_usd=sum(cost_usds),
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
    buckets: dict[str, list[tuple[float, float, float]]] = {}
    for trade in trades:
        buckets.setdefault(key_of(trade), []).append(
            (trade.pnl, _net_of(trade), trade.cost_usd)
        )
    return {
        key: _aggregate(key, [p for p, _, _ in rows],
                        nets=[n for _, n, _ in rows],
                        cost_usds=[c for _, _, c in rows])
        for key, rows in sorted(buckets.items())
    }


# ---------------------------------------------------------------------- #
# Entry point
# ---------------------------------------------------------------------- #
def build_report(
    result: RunnerResult,
    *,
    annotations: dict[int, dict] | None = None,
) -> BacktestReport:
    """Project a completed run's :class:`~smc.backtest.runner.RunnerResult`
    into a :class:`BacktestReport`.

    Pure and total: an empty run yields defined zeros (win_rate 0.0,
    max_drawdown 0.0, ``None`` for the undefined ratios) and empty
    breakdowns — never a crash, never fabricated values.

    ``annotations`` (Track-B harness, optional): ticket →
    ``{"f_timing_label": ..., "post_exit_class": ...}``, computed by
    research code over exported timestamps + canonical series and passed
    in here. Absent (or a ticket missing from the map) leaves the
    fields ``None`` — unannotated, never invented.
    """
    def _ann(ticket: int, key: str):
        if not annotations:
            return None
        return (annotations.get(ticket) or {}).get(key)

    trades = tuple(
        TradeRecord.from_closed(
            record, route_id=result.route_ids.get(record.position.ticket),
            f_timing_label=_ann(record.position.ticket, "f_timing_label"),
            post_exit_class=_ann(record.position.ticket, "post_exit_class"),
        )
        for record in result.closed
    )
    pnls = [trade.pnl for trade in trades]
    nets = [_net_of(trade) for trade in trades]
    wins = [p for p in pnls if p > 0.0]
    losses = [p for p in pnls if p <= 0.0]
    gross_profit = sum(wins)
    gross_loss = sum(-p for p in losses)
    total_commission_usd = sum(trade.commission_usd for trade in trades)
    total_spread_cost_usd = sum(trade.spread_cost_usd for trade in trades)
    total_slippage_usd = sum(trade.slippage_usd for trade in trades)
    total_swap_usd = sum(trade.swap_usd for trade in trades)
    total_cost_usd = sum(trade.cost_usd for trade in trades)
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
        total_commission_usd=total_commission_usd,
        total_spread_cost_usd=total_spread_cost_usd,
        total_slippage_usd=total_slippage_usd,
        total_swap_usd=total_swap_usd,
        total_cost_usd=total_cost_usd,
        net_pnl_after_cost=sum(nets),
    )
    blocked_counts = Counter(entry.blocked_by for entry in result.blocked)
    return BacktestReport(
        trades=trades,
        metrics=metrics,
        by_trigger=_group(trades, lambda t: t.trigger or UNATTRIBUTED),
        by_poi=_group(trades, lambda t: t.poi_id or UNATTRIBUTED),
        blocked_by_reason=dict(sorted(blocked_counts.items())),
        by_timing_label=_group(trades, lambda t: t.f_timing_label or "unknown"),
        by_post_exit_class=_group(
            trades, lambda t: t.post_exit_class or "DATA_GAP"),
    )
