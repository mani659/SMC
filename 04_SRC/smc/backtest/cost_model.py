"""V1 trade cost model — fill-only additive ledger (Tier-1, 2026-10-11).

Design: ``06_RESEARCH/COST_MODEL_DESIGN.md`` (accepted 2026-10-11 with
Architect rulings: fill-only costs; entry/SL/TP prices unchanged; fixed
points slippage; half-spread per leg + config fallback; swap deferred;
commission config-driven default 0.0; no locked-constant edits).

What this module is: PURE arithmetic (no bars, no clock, no MT5, no
strategy decisions). It turns a close's facts (lots, per-leg spreads,
exit kind) plus a :class:`CostConfig` into a :class:`CostBreakdown`.
Identical inputs always produce an identical breakdown — the costed
dual-run pair stays byte-identical.

Unit convention (defined once, locked by test):
  * ``realized_pnl`` is denominated in price x volume ledger units.
  * Spread/slippage are natively price-unit charges:
    ``ledger charge = price_points x lots``.
  * Commission is quoted in USD:
    ``ledger charge = usd / pip_value_per_lot``.
  * ``cost_ledger`` = sum of ledger charges;
    ``cost_usd`` = ``cost_ledger x pip_value_per_lot``.
  * Net (ledger) = ``realized_pnl - cost_ledger``; equity moves by
    ``net x pip_value_per_lot`` (see ``BacktestRunner._record_close``).

Scope rules (rulings):
  * Commission: every close pays both legs (entry + exit — V1 has no
    partials, so a round trip is always exactly two legs).
  * Half-spread: charged per leg from the spread known at that leg's bar;
    unknown (None or <= 0 — the legacy ``spread_price=0.0`` means "gate
    off / unknown", never "zero spread") falls back to the configured
    fallback price. No half-spread leg is ever charged when
    ``apply_half_spread`` is off.
  * Slippage: charged on every exit EXCEPT take-profit. Rationale: TP
    exits rest at the limit price and cannot slip adversely (the fill
    model already fills them at limit — the conservative side); every
    other exit (stop-loss, risk exits, Friday EOD, breaker closes) exits
    at a market-ish price and can slip.
  * Swap: always 0.0 in V1 (deferred by ruling; ``bars_held`` is recorded
    on the close record so swap stays backfillable without a re-run).

Defaults preserve legacy numerics exactly: a default-constructed
``CostConfig`` prices every close at zero cost, so frozen tests and the
zero-cost "upper bound" baseline reproduce byte-identically. Research
runs set nonzero values explicitly (recommended research values are
documented on each field; adopting them as constructor defaults would
rewrite frozen test economics and is NOT done here — flagged for review
in ``06_RESEARCH/COST_MODEL_IMPLEMENTATION_NOTE.md``).
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.backtest.fill_model import CloseKind

__all__ = [
    "CostConfig",
    "CostBreakdown",
    "CostModel",
    "net_ledger",
    "normalize_spread",
    "resolve_leg_spread",
    "slippage_in_scope",
]


@dataclass(slots=True)
class CostConfig:
    """Cost-model measurement configuration (NOT strategy law).

    Lives on the runner/research config — deliberately NOT in
    ``locked_constants.py``. Every monetary default below preserves the
    legacy zero-cost behavior; see the module docstring for why the
    research values are set explicitly per run instead of by default.
    """

    apply_costs: bool = True
    # USD per 1.0 lot per side (entry leg + exit leg = 2 sides per close).
    # Ruled default 0.0 until the operator pins a real broker schedule —
    # a missing schedule is never silently priced as zero commission AND
    # never invented (see the design note's blocking rule).
    commission_usd_per_lot_per_side: float = 0.0
    # Fixed price-point charge on slippage-scoped exits (see
    # :func:`slippage_in_scope`). Recommended research value 1.0 (R6
    # experiment precedent) — set explicitly in new run configs.
    slippage_points: float = 0.0
    # Half-spread fallback (price units) per leg when the leg's spread is
    # unknown. Candidate value 0.26 (sampled live windows) — inert unless
    # ``apply_half_spread`` is enabled.
    spread_fallback_price: float = 0.26
    # Master switch for the half-spread legs. Off by default so a
    # default-constructed config reproduces legacy numerics; new research
    # runs enable it explicitly.
    apply_half_spread: bool = False

    def __post_init__(self) -> None:
        if self.commission_usd_per_lot_per_side < 0.0:
            raise ValueError(
                "commission_usd_per_lot_per_side must be >= 0.0 "
                f"(got {self.commission_usd_per_lot_per_side})"
            )
        if self.slippage_points < 0.0:
            raise ValueError(
                f"slippage_points must be >= 0.0 (got {self.slippage_points})"
            )
        if self.spread_fallback_price < 0.0:
            raise ValueError(
                "spread_fallback_price must be >= 0.0 "
                f"(got {self.spread_fallback_price})"
            )

    @classmethod
    def zero(cls) -> "CostConfig":
        """Explicit all-zero config (old behavior, by construction)."""
        return cls(
            apply_costs=False,
            commission_usd_per_lot_per_side=0.0,
            slippage_points=0.0,
            spread_fallback_price=0.0,
            apply_half_spread=False,
        )


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Per-close cost attribution (USD legs + ledger total)."""

    commission_usd: float = 0.0
    spread_cost_usd: float = 0.0
    slippage_usd: float = 0.0
    swap_usd: float = 0.0          # always 0.0 in V1 (deferred by ruling)
    cost_usd: float = 0.0         # sum of the four legs above
    cost_ledger: float = 0.0      # cost_usd / pip_value_per_lot

    @classmethod
    def zero(cls) -> "CostBreakdown":
        """Zero breakdown (costs off / unbound store path)."""
        return cls()


def normalize_spread(spread: float | None) -> float | None:
    """Map a leg spread to known-price-or-unknown.

    ``None`` and ``<= 0.0`` both mean unknown: the legacy
    ``spread_price=0.0`` default means "gate off", never "zero spread",
    so a non-positive spread must fall back, not price at zero.
    """
    if spread is None or spread <= 0.0:
        return None
    return spread


def resolve_leg_spread(config: CostConfig, known_spread: float | None) -> float:
    """Spread price to charge for ONE leg (price units, full spread).

    Returns 0.0 unless costs are applied AND half-spread legs are enabled;
    otherwise the known spread, or the configured fallback when unknown.
    """
    if not config.apply_costs or not config.apply_half_spread:
        return 0.0
    if known_spread is not None and known_spread > 0.0:
        return known_spread
    return config.spread_fallback_price


def slippage_in_scope(exit_kind: str | None) -> bool:
    """Whether an exit kind pays the fixed-points slippage charge.

    Only take-profit exits rest at the limit price (provably slip-free);
    every other exit — stop-loss, risk exits, Friday EOD, breaker closes —
    exits at a market-ish price. ``None`` (unknown/legacy kind) is charged:
    an unknown exit is a market exit until proven a limit.
    """
    return exit_kind != CloseKind.TAKE_PROFIT


def net_ledger(realized_pnl: float, cost_ledger: float) -> float:
    """Net ledger units for one close (gross minus cost ledger)."""
    return realized_pnl - cost_ledger


@dataclass(frozen=True, slots=True)
class CostModel:
    """Bound cost pricer: config + the run's ledger divisor.

    ``pip_value_per_lot`` is the SAME divisor the equity path already uses
    (``RunnerConfig.pip_value_per_lot``) — the model introduces no new
    currency factor.
    """

    config: CostConfig
    pip_value_per_lot: float

    def __post_init__(self) -> None:
        if self.pip_value_per_lot <= 0.0:
            raise ValueError(
                "pip_value_per_lot must be > 0.0 "
                f"(got {self.pip_value_per_lot})"
            )

    def quote_close(
        self,
        *,
        lots: float,
        entry_spread: float | None,
        exit_spread: float | None,
        exit_kind: str | None,
    ) -> CostBreakdown:
        """Price one close (both legs) in ledger-native units, USD reported.

        Commission covers entry + exit (V1 has no partials: always 2 legs).
        Half-spread is charged per leg from each leg's own spread.
        Slippage is charged once, on the exit leg, when in scope.
        """
        if lots <= 0.0:
            raise ValueError(f"close lots must be > 0.0 (got {lots})")
        if not self.config.apply_costs:
            return CostBreakdown.zero()
        entry_leg = resolve_leg_spread(self.config, entry_spread)
        exit_leg = resolve_leg_spread(self.config, exit_spread)
        spread_ledger = (entry_leg / 2.0 + exit_leg / 2.0) * lots
        commission_ledger = (
            self.config.commission_usd_per_lot_per_side * lots * 2.0
            / self.pip_value_per_lot
        )
        slippage_ledger = (
            self.config.slippage_points * lots
            if slippage_in_scope(exit_kind)
            else 0.0
        )
        cost_ledger = spread_ledger + commission_ledger + slippage_ledger
        factor = self.pip_value_per_lot
        return CostBreakdown(
            commission_usd=commission_ledger * factor,
            spread_cost_usd=spread_ledger * factor,
            slippage_usd=slippage_ledger * factor,
            swap_usd=0.0,
            cost_usd=cost_ledger * factor,
            cost_ledger=cost_ledger,
        )
