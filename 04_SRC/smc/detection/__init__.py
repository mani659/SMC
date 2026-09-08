"""Phase 1: Core Detection — Stage 0A/0b/0c detectors.

Implements liquidity level scanning (§2), Base Candle identification (§18),
the swing validity gate (§19), N-bar structural swings (§27), sweep
confirmation (§2), FVG and displacement checks (§3). No POI/trigger/risk
logic lives here.
"""

from smc.detection.base_candle import find_base_candle_index
from smc.detection.displacement_checker import DisplacementResult, check_displacement
from smc.detection.eqh_eql_detector import detect_equal_levels
from smc.detection.fvg_detector import FVG, detect_fvgs
from smc.detection.liquidity_scanner import ALL_FAMILIES, scan
from smc.detection.periodic_levels import detect_periodic_levels
from smc.detection.session_levels import detect_session_levels
from smc.detection.structural_swing_detector import detect_swings
from smc.detection.sweep_detector import SweepResult, detect_sweep, detect_sweeps
from smc.detection.swing_validator import SwingValidation, is_valid_swing, validate_swing

__all__ = [
    "ALL_FAMILIES",
    "DisplacementResult",
    "FVG",
    "SweepResult",
    "SwingValidation",
    "check_displacement",
    "detect_equal_levels",
    "detect_fvgs",
    "detect_periodic_levels",
    "detect_session_levels",
    "detect_sweep",
    "detect_sweeps",
    "detect_swings",
    "find_base_candle_index",
    "is_valid_swing",
    "scan",
    "validate_swing",
]