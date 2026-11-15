"""OPT-4 place-side join smoke harness — LOST to the 2026-11-08 corruption event, not reconstructed.

**Recovery notice.** The original body was destroyed and only a fragment
survives (lines 250-284 (submit-frame / CSV export tail)); the file is archived verbatim at
``ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/corrupt_originals/06_RESEARCH/scripts/confirm_vs_zone_opt4_smoke.py``.

It provided ``CSV_FIELDS`` and ``submit_frame`` — the submit-seam frame and export schema the wider join used. The runner-side fields it exported (``distance_at_place_atr``, ``r7_verdict``, join keys) are still produced by ``smc/paper/runner.py``, so the product logging path is intact; only the study harness is gone.

Consequence: ``06_RESEARCH/results/confirm_vs_zone_opt4_wider/`` (`join_primary.csv` 73 rows, `summary_primary.json`) remains the authoritative frozen measurement, but it cannot be regenerated from source.

Any import raises :class:`ScriptLost` so nothing silently re-runs a harness
that no longer exists. Rebuilding it is NEW work with fresh pre-registration —
do not treat this placeholder as a restored harness.
"""

from __future__ import annotations

_MSG = (
    "06_RESEARCH/scripts/confirm_vs_zone_opt4_smoke.py was lost to the 2026-11-08 file-corruption "
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
