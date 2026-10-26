"""474 never-routed decomposition — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/confirm_never_routed_474.py``: C sub-reason
priority (expired > late > matrix > rest), fix-class mapping, and
trigger-letter normalization. Aggregation I/O is covered by the run
itself (reconciliation asserted in-script); no threshold, no gate, no
expectancy assertion.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "confirm_never_routed_474.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "confirm_never_routed_474", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["confirm_never_routed_474"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# 1. C priority: expired-give-up > scan-late > matrix > rest (first wins)
# --------------------------------------------------------------------------- #
def test_subreason_c_priority():
    pack = _load_pack()
    C = pack.subreason_c
    assert C(True, False, True) == "C1-expired-give-up"
    assert C(False, True, True) == "C2-scan-late"
    assert C(False, False, False) == "C3-matrix-ineligible"
    assert C(False, False, True) == "C4-scanned-no-route-unspecified"
    # Priority is total: first true flag decides, later flags ignored.
    assert C(True, True, False) == "C1-expired-give-up"
    assert C(False, True, False) == "C2-scan-late"


# --------------------------------------------------------------------------- #
# 2. Fix classes (stated, never implemented here)
# --------------------------------------------------------------------------- #
def test_fix_class_for_mapping():
    pack = _load_pack()
    F = pack.fix_class_for
    assert F("B", "B-one-shot-consumed").startswith("none (")
    assert F("D", "D-never-scanned").startswith("instrumentation")
    assert F("C", "C2-scan-late") == "arm timing"
    assert "instrumentation" in F("C", "C4-scanned-no-route-unspecified")
    assert F("C", "C1-expired-give-up").startswith("real rule change")
    assert F("C", "C3-matrix-ineligible").startswith("real rule change")
    assert F("A", "A-validated-elsewhere").startswith("arm timing")
    assert F("A", "A-never-validated").startswith("real rule change")
    assert F("A", "anything-else") == "instrumentation"


# --------------------------------------------------------------------------- #
# 3. Letter normalization across shapes
# --------------------------------------------------------------------------- #
def test_letter_of_shapes():
    pack = _load_pack()
    assert pack.letter_of(SimpleNamespace(value="f_bos_ob")) == "F"
    assert pack.letter_of("A") == "A"
    assert pack.letter_of("ending_diagonal") == "ENDING"
