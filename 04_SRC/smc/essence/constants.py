"""ESSENCE contract v1 constants — essence-owned wiring of the SIGNED numbers.

ESSENCE V1 SLICE — NOT FULL COMPLEX REWRITE.

Authority: `00_LOCKED/ESSENCE_CONTRACT_V1.md` (SIGNED 2026-10-21, Owner
Salman + Architect) with the M1-entry F1 amendment recorded in
`00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` (2026-10-21) and the follow-up list
in `06_RESEARCH/ESSENCE_V1_CODE_MAPPING.md`.

Every trading number below is IMPORTED from `smc.config.locked_constants`
(wired, not re-declared): the mapping verified they already match the signed
picks, so no value is created here. The only essence-owned values are the
ATR period (the codebase-standard 14, same as DUMB/COMPLEX) and the confirm
SET allow-list (which patterns may complete an essence entry). `locked_constants.py`
is untouched; no COMPLEX threshold is aliased or repurposed.
"""

from __future__ import annotations

from smc.config.locked_constants import (
    M1_EXPIRY_BARS,
    M8_MIN_RR,
    M8_SL_MAX_PIPS,
    M8_SL_MIN_PIPS,
    PURE_RUNNER_BE_ATR,
    PURE_RUNNER_BE_BUFFER_ATR,
    TRIGGER_C_EXPIRY_EXTRA,
    ZONE_REFINEMENT_ATR,
)

__all__ = [
    "ESSENCE_SL_MIN_PIPS",
    "ESSENCE_SL_MAX_PIPS",
    "ESSENCE_MIN_RR",
    "ESSENCE_LIMIT_EXPIRY_BARS",
    "ESSENCE_BE_ATR",
    "ESSENCE_BE_BUFFER_ATR",
    "ESSENCE_ED_TERMINAL_EXPIRY",
    "ESSENCE_ZONE_BAND_ATR",
    "ESSENCE_ATR_PERIOD",
    "ESSENCE_CONFIRM_KINDS",
    "ESSENCE_CONFIRM_KIND_ED",
]

# §5 signed SL band B — 2–5 pips beyond the M1 structure. Values = the frozen
# §21/§26 pair; the slice places the stop at the band floor (2.0 pips).
ESSENCE_SL_MIN_PIPS = M8_SL_MIN_PIPS   # 2.0 — signed band floor (no new number)
ESSENCE_SL_MAX_PIPS = M8_SL_MAX_PIPS   # 5.0 — signed band ceiling (no new number)

# §6 signed TP profile D — minimum 1:5 risk:reward, hard gate.
ESSENCE_MIN_RR = M8_MIN_RR             # 5.0 (no new number)

# §4 — the LIMIT resting window on the M1 execution timeframe: the frozen §23
# per-TF value (M1 = 30 bars), exactly as the contract's implementation note
# states. Not a new number.
ESSENCE_LIMIT_EXPIRY_BARS = M1_EXPIRY_BARS   # 30

# §6 — PureRunner break-even, ON: threshold + buffer = the frozen §28.1 pair.
ESSENCE_BE_ATR = PURE_RUNNER_BE_ATR          # 1.0
ESSENCE_BE_BUFFER_ATR = PURE_RUNNER_BE_BUFFER_ATR  # 0.10

# §3 — Trigger C's terminal-recency window (sweep candle + extra) re-used for
# the ending-diagonal confirm: the most recent 5-wave terminal throw only.
ESSENCE_ED_TERMINAL_EXPIRY = TRIGGER_C_EXPIRY_EXTRA   # 3

# §13 zone-context band half-width multiplier (0.5 × ATR) — the same frozen
# multiplier Trigger C re-uses for the "terminal extreme reaches the POI zone"
# check. No new number.
ESSENCE_ZONE_BAND_ATR = ZONE_REFINEMENT_ATR   # 0.5

# ATR period (Wilder, `smc.utils.atr`) on the M1 execution series — the
# codebase's standard period (also DUMB's); not a trading threshold.
ESSENCE_ATR_PERIOD = 14

# Signed confirm set C as IMPLEMENTED in the v1 slice: the §15-preferred
# ending diagonal is wired; the set-C alternates (F/D/A) remain in the signed
# set on the page but are NOT wired in this slice (residual, listed in the
# slice note). B (leading diagonal) and E (RSI divergence) are explicitly
# OUT of the signed set and can never complete an essence entry.
ESSENCE_CONFIRM_KIND_ED = "c_ending_diagonal"
ESSENCE_CONFIRM_KINDS: tuple[str, ...] = (ESSENCE_CONFIRM_KIND_ED,)
