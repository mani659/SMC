"""OPT-1 confirm-vs-zone smoke harness — LOST to the 2026-11-08 corruption event, not reconstructed.

**Recovery notice.** The original body was destroyed and only a fragment
survives (lines 58-137 (replay/episode plumbing)); the file is archived verbatim at
``ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/corrupt_originals/06_RESEARCH/scripts/confirm_vs_zone_opt1_smoke.py``.

It provided ``replay_episode`` — the engine replay the OPT-1 measurement and the wider OPT-4 join imported — plus the arming/replay glue. The frozen OPT-1 stamp and label semantics live on in ``smc/orchestration/product_menu_mtf.py`` (production) and in ``poi_timing_early_late_study.timing_label`` (verified against all 60 labelled OPT-4 rows).

Consequence: the published OPT-1 artifact tree ``06_RESEARCH/results/confirm_vs_zone_opt1/`` remains valid and citable, but the measurement CANNOT be re-run from this tree until the harness is rebuilt.

Any import raises :class:`ScriptLost` so nothing silently re-runs a harness
that no longer exists. Rebuilding it is NEW work with fresh pre-registration —
do not treat this placeholder as a restored harness.
"""

from __future__ import annotations

_MSG = (
    "06_RESEARCH/scripts/confirm_vs_zone_opt1_smoke.py was lost to the 2026-11-08 file-corruption "
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
