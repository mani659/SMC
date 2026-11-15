"""COUPLED_MTF full-menu diagnostic driver — LOST to the 2026-11-08 corruption event, not reconstructed.

**Recovery notice.** The original body was destroyed and only a fragment
survives (lines 524-545 (summary tail)); the file is archived verbatim at
``ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/corrupt_originals/06_RESEARCH/scripts/coupled_mtf_full_menu_diagnostic.py``.

It drove the COUPLED_MTF research path, whose runtime module ``smc/orchestration/coupled_mtf.py`` is itself lost (fail-loud placeholder). Its downstream consumer ``coupled_mtf_fill_leg_capture.py`` therefore cannot run.

Consequence: the frozen COUPLED_MTF diagnostic results (`06_RESEARCH/results/coupled_mtf_full_menu_diag/`, cited in SESSION_HANDOFF 2026-10-31) stand as history only and cannot be reproduced.

Any import raises :class:`ScriptLost` so nothing silently re-runs a harness
that no longer exists. Rebuilding it is NEW work with fresh pre-registration —
do not treat this placeholder as a restored harness.
"""

from __future__ import annotations

_MSG = (
    "06_RESEARCH/scripts/coupled_mtf_full_menu_diagnostic.py was lost to the 2026-11-08 file-corruption "
    "event and was deliberately not reconstructed. See "
    "00_LOCKED/SESSION_HANDOFF.md 2026-11-08 (5) and "
    "ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/."
)


class ScriptLost(RuntimeError):
    """Raised on any use of this lost research harness."""


def __getattr__(name: str):
    if name.startswith("__"):
        raise AttributeError(name)
    raise ScriptLost(_MSG)
