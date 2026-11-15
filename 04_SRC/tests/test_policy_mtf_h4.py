"""Legacy policy-mode tests (``DUMB_MTF_H4`` era) — LOST, superseded.

Only lines 411-421 of the original module survived, and they assert the retired
mode id ``DUMB_MTF_H4``, which no longer exists: strategy modes are now
``PRODUCT_V1`` (default) with ``RESEARCH_H4_ZONE_BOOK`` / ``RESEARCH_SNAPSHOT`` /
``RESEARCH_COUPLED_MTF`` and a one-time ``DEPRECATION:`` alias print. Rewriting
those assertions against today's contract would invent coverage the original
never had, so the suite is skipped at module level.

Current mode-contract coverage lives in ``test_operator_config_modes.py`` and
``test_mode_t_console_markers.py``. The surviving fragment is archived at
``ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/corrupt_originals/04_SRC/tests/test_policy_mtf_h4.py``.
"""

from __future__ import annotations

import pytest

pytest.skip(
    "test_policy_mtf_h4: original suite lost to the 2026-11-08 file corruption "
    "and its surviving assertions target the retired DUMB_MTF_H4 mode id.",
    allow_module_level=True,
)
