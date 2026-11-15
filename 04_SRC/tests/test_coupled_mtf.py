"""COUPLED_MTF orchestration tests — LOST to the 2026-11-08 corruption event.

Only lines 360-381 of the original module survived (assertions on the
``coupled_mtf`` identity stamp of the bridge candidate). The module under test
(:mod:`smc.orchestration.coupled_mtf`) is also lost and intentionally not
reconstructed, so this suite is skipped at module level rather than replaced
with tests that would merely pin invented behaviour.

The surviving fragment is archived at
``ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/corrupt_originals/04_SRC/tests/test_coupled_mtf.py``.
Reviving the coupled-MTF path is NEW research work (fresh pre-registration).
"""

from __future__ import annotations

import pytest

pytest.skip(
    "test_coupled_mtf: original module + suite lost to the 2026-11-08 file "
    "corruption; COUPLED_MTF research path unavailable (see "
    "ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/).",
    allow_module_level=True,
)
