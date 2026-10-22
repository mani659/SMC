"""DUMB FLOWCHART V1 — the parallel simple path (sweep → confirm → entry).

Banner: **DUMB IMPLEMENTATION — DIAGNOSTIC — NOT EDGE.**

Implemented exactly per the accepted design lock
(`06_RESEARCH/DUMB_FLOWCHART_V1_DESIGN.md`, Architect 2026-10-21). DUMB is a
PARALLEL measurement mode: the COMPLEX decision spine (pillars, triggers A–F,
seek/scan postures, ZoneDedup lifecycle, structural TP feed, risk hard
filters) is untouched — no `if dumb: ...` branch exists anywhere outside this
package, and `locked_constants.py` is not repurposed (all DUMB constants live
here).

Modules
-------
``constants``  DUMB-owned frozen constants (`DUMB_*` names; ATR period 14).
``rules``      Pure rule functions: sweep, confirm, expiry, SL/TP arithmetic.
``types``      `DumbSetup` / `DumbTrade` records.
``runner``     Bar loop: M5 series + HTF-zone feed → trades & counters.

The HTF zones are READ-ONLY library reuse of the product's own M8 scan
(`smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply`) over honest
prefixes (reuse of `smc.orchestration.multi_tf_runtime.build_htf_prefixes`).
The execution loop reuses the locked conservative fill semantics
(`smc.backtest.fill_model.evaluate_position_bar`: touch = fill, fill price =
level, same-bar SL+TP → SL wins) — no COMPLEX routing is invoked.
"""

from smc.dumb.constants import (
    DUMB_ATR_PERIOD,
    DUMB_CONFIRM_MAX_BARS,
    DUMB_SL_BUFFER_ATR,
    DUMB_TP_R_MULTIPLE,
)
from smc.dumb.rules import compute_sl_tp, is_confirm, is_expired, is_sweep

__all__ = [
    "DUMB_ATR_PERIOD",
    "DUMB_CONFIRM_MAX_BARS",
    "DUMB_SL_BUFFER_ATR",
    "DUMB_TP_R_MULTIPLE",
    "compute_sl_tp",
    "is_confirm",
    "is_expired",
    "is_sweep",
]
