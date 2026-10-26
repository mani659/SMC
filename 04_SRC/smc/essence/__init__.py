"""ESSENCE contract v1 — the parallel signed-contract product path slice.

ESSENCE V1 SLICE — NOT FULL COMPLEX REWRITE.

``smc.essence`` implements `00_LOCKED/ESSENCE_CONTRACT_V1.md` (SIGNED
2026-10-21) as a parallel product path authorized by the 2026-10-21
runtime-contract amendment (M1 execution for essence only). COMPLEX is
untouched; see `06_RESEARCH/ESSENCE_V1_SLICE_NOTE.md`.
"""

from smc.essence.constants import (
    ESSENCE_ATR_PERIOD,
    ESSENCE_BE_ATR,
    ESSENCE_BE_BUFFER_ATR,
    ESSENCE_CONFIRM_KIND_ED,
    ESSENCE_CONFIRM_KINDS,
    ESSENCE_ED_TERMINAL_EXPIRY,
    ESSENCE_LIMIT_EXPIRY_BARS,
    ESSENCE_MIN_RR,
    ESSENCE_SL_MAX_PIPS,
    ESSENCE_SL_MIN_PIPS,
    ESSENCE_ZONE_BAND_ATR,
)

__all__ = [
    "ESSENCE_ATR_PERIOD",
    "ESSENCE_BE_ATR",
    "ESSENCE_BE_BUFFER_ATR",
    "ESSENCE_CONFIRM_KIND_ED",
    "ESSENCE_CONFIRM_KINDS",
    "ESSENCE_ED_TERMINAL_EXPIRY",
    "ESSENCE_LIMIT_EXPIRY_BARS",
    "ESSENCE_MIN_RR",
    "ESSENCE_SL_MAX_PIPS",
    "ESSENCE_SL_MIN_PIPS",
    "ESSENCE_ZONE_BAND_ATR",
]
