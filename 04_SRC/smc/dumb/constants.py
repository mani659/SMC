"""DUMB FLOWCHART V1 frozen constants — DUMB-owned, never locked_constants.

DUMB IMPLEMENTATION — DIAGNOSTIC — NOT EDGE.

These values implement the accepted design lock
(`06_RESEARCH/DUMB_FLOWCHART_V1_DESIGN.md`, Architect 2026-10-21). They are
**deliberately not aliases of any COMPLEX threshold**: `locked_constants.py`
is untouched, and no COMPLEX module reads these names. Frozen at
implementation; changing any of them is a dated design amendment, not tuning.
"""

from __future__ import annotations

__all__ = [
    "DUMB_CONFIRM_MAX_BARS",
    "DUMB_SL_BUFFER_ATR",
    "DUMB_TP_R_MULTIPLE",
    "DUMB_ATR_PERIOD",
]

#: R3 — a swept setup must confirm within this many M5 bars of its sweep bar
#: (`sweep_idx < confirm_idx <= sweep_idx + 12`), else it expires.
DUMB_CONFIRM_MAX_BARS = 12

#: R5 — stop buffer beyond the sweep extreme, as a fraction of M5 ATR(14).
DUMB_SL_BUFFER_ATR = 0.10

#: R6 — fixed profit target as a multiple of the initial risk |entry - SL|.
DUMB_TP_R_MULTIPLE = 2.0

#: ATR period (Wilder, `smc.utils.atr`) — the codebase's standard period,
#: reused by design lock R5; not a new DUMB-invented number.
DUMB_ATR_PERIOD = 14
