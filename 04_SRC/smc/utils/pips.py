"""XAUUSD pip helpers.

Pip convention for gold: with a two-decimal quote (e.g. ``2650.55``),
**1 pip = 0.10 price units = 10 points**. This is the convention used by
LOCKED_DECISIONS §2 ("≤ 4.5 pips tolerance" ⇒ 0.45 price units).

The point/pip mapping is broker-dependent; ``XAUUSD_POINTS_PER_PIP`` is the
default for two-decimal quotes and should be verified against the broker's
``symbol_info().digits`` when the connector goes live.
"""

from __future__ import annotations

from smc.config.locked_constants import EQH_EQL_TOLERANCE

__all__ = [
    "XAUUSD_PIP_SIZE",
    "XAUUSD_POINTS_PER_PIP",
    "pips_to_price",
    "price_to_pips",
    "round_price",
    "within_pip_tolerance",
]

# ---------------------------------------------------------------------------
# ASSUMPTION — NOT FROZEN. VERIFY BEFORE PHASE 4 / PHASE 7.
# ---------------------------------------------------------------------------
# The 1 pip = 0.10 price-unit convention below (XAUUSD_PIP_SIZE) is an
# ASSUMPTION based on a two-decimal gold quote. It is NOT a value frozen in
# LOCKED_DECISIONS.md and it is broker-dependent. Before Phase 4 (Python
# execution) and Phase 7 (live), verify it against the live broker using
# mt5.symbol_info(symbol).digits and .point, and calibrate XAUUSD_PIP_SIZE
# (and XAUUSD_POINTS_PER_PIP) accordingly. A mismatch here silently scales
# every pip-based threshold, e.g. the frozen EQH/EQL 4.5-pip tolerance.
# ---------------------------------------------------------------------------
# 1 pip for XAUUSD at two-decimal precision (price units).
XAUUSD_PIP_SIZE = 0.1
# MT5 "points" per pip at two-decimal precision (point = 0.01).
XAUUSD_POINTS_PER_PIP = 10


def pips_to_price(pips: float) -> float:
    """Convert pips into XAUUSD price units."""
    return pips * XAUUSD_PIP_SIZE


def price_to_pips(price: float) -> float:
    """Convert an XAUUSD price distance into pips."""
    return price / XAUUSD_PIP_SIZE


def round_price(price: float, digits: int = 2) -> float:
    """Round a price to the quote precision (default: 2 decimals)."""
    return round(price, digits)


def within_pip_tolerance(
    price_a: float,
    price_b: float,
    tolerance_pips: float | None = None,
) -> bool:
    """True when two prices are within ``tolerance_pips`` of each other.

    Defaults to the frozen EQH/EQL tolerance (§2: ``EQH_EQL_TOLERANCE`` =
    4.5 pips on XAUUSD).
    """
    tolerance = EQH_EQL_TOLERANCE if tolerance_pips is None else tolerance_pips
    return abs(price_a - price_b) <= pips_to_price(tolerance)