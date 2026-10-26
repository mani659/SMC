"""Phase 4: LTF Triggers A–F + chronological routing + §24 expiry.

Stage 3 per LOCKED_DECISIONS §9/§10/§12/§15/§22–§24 and R1 §7. The six
triggers (A CHOCH Reversal, B Leading Diagonal, C Ending Diagonal, D
Two-Bar Reversal, E RSI Divergence, F BOS+OB Continuation) all emit LIMIT
entries on a FRESH POI; ``TriggerRouter`` scans chronologically (first-valid
wins, §12) over the §15 compatibility matrix, and ``trigger_expiry`` maps
the frozen §24 windows. ``wave_structure`` pins down the deterministic V1
wave rules the two diagonal triggers consume.
"""

from smc.triggers.base_trigger import (
    Trigger,
    TriggerContext,
    TriggerSignal,
    atr_band_half_width,
)
from smc.triggers.compatibility_matrix import (
    DEFAULT_MATRIX,
    CompatibilityGrade,
    CompatibilityMatrix,
)
from smc.triggers.trigger_a_choch import ChochReversalTrigger
from smc.triggers.trigger_b_leading_diagonal import LeadingDiagonalTrigger
from smc.triggers.trigger_c_ending_diagonal import EndingDiagonalTrigger
from smc.triggers.trigger_d_two_bar import TwoBarReversalTrigger
from smc.triggers.trigger_e_rsi_divergence import RsiDivergenceTrigger
from smc.triggers.trigger_expiry import (
    poi_give_up_bars,
    signal_expired,
    window_bars_for,
)
from smc.triggers.trigger_f_bos_ob import BosObContinuationTrigger
from smc.triggers.trigger_router import (
    DEFAULT_TRIGGERS,
    TriggerRoute,
    TriggerRouter,
    default_triggers,
)

__all__ = [
    "BosObContinuationTrigger",
    "ChochReversalTrigger",
    "CompatibilityGrade",
    "CompatibilityMatrix",
    "DEFAULT_MATRIX",
    "DEFAULT_TRIGGERS",
    "EndingDiagonalTrigger",
    "LeadingDiagonalTrigger",
    "RsiDivergenceTrigger",
    "Trigger",
    "TriggerContext",
    "TriggerRoute",
    "TriggerRouter",
    "TriggerSignal",
    "TwoBarReversalTrigger",
    "atr_band_half_width",
    "default_triggers",
    "poi_give_up_bars",
    "signal_expired",
    "window_bars_for",
]
