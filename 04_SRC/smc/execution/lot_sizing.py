"""Dynamic risk lot sizing (v25_DIAG formula, ported to Python).

v5 flowchart STAGE 4 (reference)::

    Lots = (Equity × Risk%) / (SL Distance × Tick Value)

This is a PURE sizing function — every input is supplied by the caller:

* ``equity`` — account equity in account currency;
* ``risk_fraction`` — the fraction of equity risked per trade. v25_DIAG used
  a 0.5%–1.0% band, but those percentages are NOT frozen (see the header of
  ``smc.config.locked_constants``: the v25 risk thresholds are deliberately
  excluded until Phase 5 when the risk layer is ported). The caller/Phase 5
  risk engine supplies the fraction; nothing is invented here;
* ``sl_distance`` — stop distance in PRICE units;
* ``pip_value_per_lot`` — value of one pip (price unit) per 1.0 lot in
  account currency. XAUUSD pip value is broker/tick-size dependent — the
  same UNFROZEN caveat as ``smc.utils.pips`` (verify against the live
  broker before Phase 7);
* ``min_lots`` / ``lot_step`` — broker lot grid.

Returns 0.0 when the computed size is below ``min_lots`` (skip the trade)
and rounds DOWN to ``lot_step`` so risk never exceeds the budget.
"""

from __future__ import annotations

import math

__all__ = ["risk_lots"]

_MIN_ACCOUNT_EQUITY = 0.0


def risk_lots(
    equity: float,
    risk_fraction: float,
    sl_distance: float,
    pip_value_per_lot: float,
    min_lots: float,
    lot_step: float,
) -> float:
    """Risk-based position size in lots for one trade.

    ``sl_distance`` and ``pip_value_per_lot`` must share units (price units
    per lot). The function never invents a risk fraction or a pip value —
    those are caller/Phase-5/broker inputs.
    """
    if equity <= _MIN_ACCOUNT_EQUITY or risk_fraction <= 0.0:
        return 0.0
    if sl_distance <= 0.0 or pip_value_per_lot <= 0.0:
        raise ValueError("sl_distance and pip_value_per_lot must be positive")
    raw = (equity * risk_fraction) / (sl_distance * pip_value_per_lot)
    if raw < min_lots:
        return 0.0
    steps = math.floor(raw / lot_step)
    lots = steps * lot_step
    # Guard against float grid drift (e.g. 0.30000000000000004).
    return round(lots, 10)
