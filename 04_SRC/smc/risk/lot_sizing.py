"""Phase 5 — risk lot sizing policy (v25_DIAG formula + frozen §28.7 band/cap).

Single sizing implementation, one path only:

* The pure v25 formula (``Lots = (Equity × Risk%) / (SL Distance × Tick
  Value)``) lives in ``smc.execution.lot_sizing.risk_lots`` — it is consumed
  by the Phase 4 ``PipelineEngine.compute_risk_lots`` and is re-exported
  here (NOT reimplemented; no parallel sizing path).
* This module adds the Phase-5 POLICY layer on top of that single formula:

  * the risk fraction is clamped into the frozen ``RISK_PCT_MIN``–``RISK_PCT_MAX``
    band (LOCKED_DECISIONS §28.7 — the caller/risk engine may pick any value
    within the band, the policy guarantees it stays inside);
  * the resulting size is capped at ``LOT_MAX_SAFETY`` (§28.7).

The Phase 5 risk engine consumes :func:`sized_lots`; broker lot-grid inputs
(``min_lots``/``lot_step``) and the tick-value per lot remain caller-supplied
(same UNFROZEN broker caveats as ``smc.execution.lot_sizing``).
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.config.locked_constants import (
    LOT_MAX_SAFETY,
    RISK_PCT_MAX,
    RISK_PCT_MIN,
)
from smc.execution.lot_sizing import risk_lots

__all__ = [
    "risk_lots",
    "clamp_risk_fraction",
    "sized_lots",
    "sized_lots_detail",
    "SizingDecision",
]


def clamp_risk_fraction(risk_fraction: float) -> float:
    """Clamp ``risk_fraction`` (as a fraction, e.g. 0.01 = 1%) into the
    frozen §28.7 band.

    ``RISK_PCT_MIN``/``RISK_PCT_MAX`` are expressed in percent, so the band
    is ``[RISK_PCT_MIN / 100, RISK_PCT_MAX / 100]``. Values inside the band
    pass through untouched; values below the floor raise to the floor and
    values above the ceiling lower to the ceiling (defensive enforcement of
    the locked decision: the caller/engine chooses within the band).
    """
    lo = RISK_PCT_MIN / 100.0
    hi = RISK_PCT_MAX / 100.0
    if risk_fraction < lo:
        return lo
    if risk_fraction > hi:
        return hi
    return risk_fraction


@dataclass(frozen=True, slots=True)
class SizingDecision:
    """One sizing verdict plus the §28.7 diagnostics the KPI needs.

    ``lots`` is the order volume actually used (band-clamped formula, on the
    lot grid, capped). ``uncapped_lots`` is the same size BEFORE the
    ``LOT_MAX_SAFETY`` cap, so a binding cap is visible instead of being
    silently absorbed; ``effective_risk_fraction`` is the risk the placed
    size really carries (``lots × sl_distance × unit_value / equity``),
    which differs from the requested fraction exactly when the cap binds.
    """

    lots: float
    uncapped_lots: float
    risk_fraction: float          # clamped band fraction actually used
    capped: bool                  # LOT_MAX_SAFETY bound the size
    effective_risk_fraction: float


def sized_lots_detail(
    equity: float,
    risk_fraction: float,
    sl_distance: float,
    pip_value_per_lot: float,
    min_lots: float,
    lot_step: float,
) -> SizingDecision:
    """The single sizing path WITH §28.7 diagnostics (F3).

    Same arithmetic as :func:`sized_lots` — that function now returns
    ``sized_lots_detail(...).lots``, so there is still exactly one formula
    and one cap, and the KPI cannot drift from the traded size.

    Returns ``lots == 0.0`` (and zero diagnostics) when the size is below
    ``min_lots`` or equity/risk/inputs are non-positive — the same skip
    contract as ``smc.execution.lot_sizing.risk_lots``.
    """
    fraction = clamp_risk_fraction(risk_fraction)
    lots = risk_lots(
        equity,
        fraction,
        sl_distance,
        pip_value_per_lot,
        min_lots,
        lot_step,
    )
    if lots <= 0.0:
        return SizingDecision(
            lots=0.0,
            uncapped_lots=0.0,
            risk_fraction=fraction,
            capped=False,
            effective_risk_fraction=0.0,
        )
    capped = lots > LOT_MAX_SAFETY
    placed = LOT_MAX_SAFETY if capped else lots
    # equity > 0 is guaranteed by risk_lots returning a positive size.
    effective = (placed * sl_distance * pip_value_per_lot) / equity
    return SizingDecision(
        lots=placed,
        uncapped_lots=lots,
        risk_fraction=fraction,
        capped=capped,
        effective_risk_fraction=effective,
    )


def sized_lots(
    equity: float,
    risk_fraction: float,
    sl_distance: float,
    pip_value_per_lot: float,
    min_lots: float,
    lot_step: float,
) -> float:
    """Phase-5 position size for one trade: clamp risk into the frozen §28.7
    band, run the single v25 formula, then cap at ``LOT_MAX_SAFETY``.

    Returns 0.0 when the computed size is below ``min_lots`` (skip the
    trade) or when equity/risk are non-positive — the same contract as
    ``smc.execution.lot_sizing.risk_lots``, which this wraps.

    F3 (2026-11-09): a thin reader of :func:`sized_lots_detail` — the KPI
    path and this path share one computation, never two.
    """
    return sized_lots_detail(
        equity,
        risk_fraction,
        sl_distance,
        pip_value_per_lot,
        min_lots,
        lot_step,
    ).lots