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

from smc.config.locked_constants import (
    LOT_MAX_SAFETY,
    RISK_PCT_MAX,
    RISK_PCT_MIN,
)
from smc.execution.lot_sizing import risk_lots

__all__ = ["risk_lots", "clamp_risk_fraction", "sized_lots"]


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
        return 0.0
    return min(lots, LOT_MAX_SAFETY)