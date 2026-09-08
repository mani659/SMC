"""Phase 5: Risk Layer — port of v25_DIAG defensive components.

Phase 5 complete (constant-locking milestone 2026-09-07 + coding milestones
1–4): ``lot_sizing`` (policy wrapper over the Phase 4 pure formula),
``circuit_breaker`` (§28.2), ``same_level_guard`` (§28.3), ``friday_eod``
(§28.4), ``spread_grading`` (§28.5), ``sweep_guard`` (§28.6), ``pure_runner``
(§28.1), ``fvg_invalidation`` and the ``risk_engine`` orchestrator. The
optional adx/atr gates remain locked-but-unported (only if still needed) —
see 00_LOCKED/TODO.md.
"""

from smc.risk.circuit_breaker import CircuitBreaker, CircuitBreakerState
from smc.risk.friday_eod import FridayEod, FridayEodState
from smc.risk.fvg_invalidation import (
    FvgContext,
    INVALIDATION_REASON_BEAR_BREACHED,
    INVALIDATION_REASON_BULL_BREACHED,
    is_invalidated,
)
from smc.risk.lot_sizing import (
    clamp_risk_fraction,
    risk_lots,
    sized_lots,
)
from smc.risk.pure_runner import PureRunner, PureRunnerState
from smc.risk.risk_engine import (
    BLOCK_CIRCUIT_BREAKER,
    BLOCK_MIN_LOTS,
    BLOCK_NEWS,
    BLOCK_SAME_LEVEL,
    BLOCK_SESSION,
    BLOCK_SPREAD,
    BLOCK_SWEEP,
    EntryDecision,
    EntryRequest,
    ExitDecision,
    PositionState,
    RiskAction,
    RiskEngine,
)
from smc.risk.same_level_guard import SameLevelGuard, SameLevelGuardState
from smc.risk.spread_grading import (
    SpreadGrade,
    effective_max_spread,
    grade_for_score,
)
from smc.risk.sweep_guard import SweepGuard, SweepGuardState

__all__ = [
    "BLOCK_CIRCUIT_BREAKER",
    "BLOCK_MIN_LOTS",
    "BLOCK_NEWS",
    "BLOCK_SAME_LEVEL",
    "BLOCK_SESSION",
    "BLOCK_SPREAD",
    "BLOCK_SWEEP",
    "CircuitBreaker",
    "CircuitBreakerState",
    "EntryDecision",
    "EntryRequest",
    "ExitDecision",
    "FridayEod",
    "FridayEodState",
    "FvgContext",
    "INVALIDATION_REASON_BEAR_BREACHED",
    "INVALIDATION_REASON_BULL_BREACHED",
    "PositionState",
    "PureRunner",
    "PureRunnerState",
    "RiskAction",
    "RiskEngine",
    "SameLevelGuard",
    "SameLevelGuardState",
    "SweepGuard",
    "SweepGuardState",
    "SpreadGrade",
    "clamp_risk_fraction",
    "effective_max_spread",
    "grade_for_score",
    "is_invalidated",
    "risk_lots",
    "sized_lots",
]