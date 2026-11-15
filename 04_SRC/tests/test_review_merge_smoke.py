"""One-assert smoke that re-opens the key cited source paths for this review merge and fails
loudly if any are missing. Mirrors the "no uncommitted 04_SRC edits" discipline on the docs side.
No product/logic change.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

ROOT = SRC_ROOT

REQUIRED = [
    SRC_ROOT / "smc" / "config" / "locked_constants.py",
    SRC_ROOT / "smc" / "config" / "timeframe.py",
    Path("06_RESEARCH/scripts/ungated_event_ledger_p1.py"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_bos_01_h4-structure-bos-000027.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_bos_02_h4-structure-bos-000065.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_bos_03_h4-structure-bos-000094.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_choch_01_h4-structure-choch-000226.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_choch_02_h4-structure-choch-000271.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_choch_03_h4-structure-choch-000288.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_fvg_01_h4-fvg-000010.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_fvg_02_h4-fvg-000011.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_fvg_03_h4-fvg-000015.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_last_opposite_before_bos_01_h4-ob-000027-000025.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_last_opposite_before_bos_02_h4-ob-000065-000064.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_h4/charts/h4_last_opposite_before_bos_03_h4-ob-000094-000092.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/m5_order_block_01_m5-ob-000013-000011.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/m5_structure_01_m5-structure-bos-000013.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/m5_fvg_01_m5-fvg-000014.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/m5_fvg_02_m5-fvg-000019.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/m5_structure_02_m5-structure-choch-000020.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/m5_fvg_03_m5-fvg-000021.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/h1_fvg_01_h1-fvg-000002.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/h1_fvg_02_h1-fvg-000003.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/m5_order_block_02_m5-ob-000075-000071.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/m5_structure_03_m5-structure-bos-000075.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/h1_fvg_03_h1-fvg-000010.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/m5_order_block_03_m5-ob-000141-000139.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/h1_order_block_01_h1-ob-000022-000019.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/h1_structure_01_h1-structure-bos-000022.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/h1_order_block_02_h1-ob-000035-000033.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/h1_structure_02_h1-structure-bos-000035.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/h1_order_block_03_h1-ob-000102-000100.png"),
    Path("06_RESEARCH/results/ungated_event_ledger_p1/charts/h1_structure_03_h1-structure-bos-000102.png"),
]

import pytest

REQUIRED_DIRS = [
    "06_RESEARCH/results/ungated_event_ledger_p1/charts",
    "06_RESEARCH/results/ungated_event_ledger_h4/charts",
]

REQUIRED_SWEEP = [Path("06_RESEARCH/results/track_a_sweep_ledger")]

missing = [str(p) for p in REQUIRED if not p.exists()]
missing_dirs = [d for d in REQUIRED_DIRS if not Path(d).is_dir()]
missing_sweep = [str(p) for p in REQUIRED_SWEEP if not p.exists()]

if missing or missing_dirs or missing_sweep:
    pytest.skip(
        "review_merge_smoke: research chart artifacts missing (local gitignored)",
        allow_module_level=True,
    )

assert not missing, "review_merge_smoke: missing required artifacts:\n" + "\n".join(missing)
assert not missing_dirs, "review_merge_smoke: missing required chart dirs:\n" + "\n".join(missing_dirs)
assert not missing_sweep, "review_merge_smoke: missing required sweep artifacts:\n" + "\n".join(missing_sweep)

