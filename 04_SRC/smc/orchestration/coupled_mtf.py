"""COUPLED_MTF orchestration (research path) — LOST, not reconstructed.

**Recovery notice (2026-11-08).** The original module body was destroyed by the
file-corruption event; only its final 60 lines survived (the candidate
identity-stamp builder at the end of ``on_confirmation``). That fragment is
preserved verbatim in
``ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/coupled_mtf.py.fragment`` and in the
project's incident record.

Nothing in the shipped product path imports this module: ``PRODUCT_V1`` menu
confirmation lives in :mod:`smc.orchestration.product_menu_mtf`, and the
research scripts that consumed this module
(``coupled_mtf_full_menu_diagnostic.py``,
``coupled_mtf_fill_leg_capture.py``) are themselves lost or unverified.
Rather than ship invented logic that would look like a restored research path,
any attempt to use it fails loudly with :class:`CoupledMTFLost`.

If the coupled-MTF study is revived, treat it as NEW work with its own
pre-registration — do not treat this placeholder as a restored implementation.
"""

from __future__ import annotations

_MSG = (
    "smc.orchestration.coupled_mtf was lost to the 2026-11-08 file-corruption "
    "event and was deliberately NOT reconstructed. The RESEARCH_COUPLED_MTF path "
    "is unavailable; use smc.orchestration.product_menu_mtf (PRODUCT_V1 menu "
    "confirmation) for shipped behaviour. See "
    "00_LOCKED/SESSION_HANDOFF.md (4) for the incident record."
)


class CoupledMTFLost(RuntimeError):
    """Raised on any use of the lost COUPLED_MTF research module."""


def __getattr__(name: str):
    if name.startswith("__"):
        raise AttributeError(name)
    raise CoupledMTFLost(_MSG)
