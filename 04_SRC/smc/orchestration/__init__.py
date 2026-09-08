"""Phase 4: orchestration glue — Detection → POI → Validation → Trigger → Execution.

The heavy lifting lives in ``smc.orchestration.engine`` (a single
:class:`PipelineEngine` that merges overlapping POIs, runs the Phase 3
5-pillar validation with injected displacement, arms the survivors, scans
triggers chronologically while FRESH, and routes the winning signal to the
execution layer as a LIMIT order through the news/session gates).

The detection and POI-classification stages (Phase 1/2) are per-stage
libraries consumed by the engine — the engine does NOT re-run them; it
consumes their outputs (POIs, swings, liquidity levels, displacement
results), which keeps it deterministic and unit-testable with synthetic
data. Full bar/event plumbing for backtest (Phase 6) and live (Phase 7)
runners composes this engine.
"""

from smc.orchestration.engine import (
    ExecutionOutcome,
    PipelineEngine,
    build_limit_request,
)

__all__ = ["ExecutionOutcome", "PipelineEngine", "build_limit_request"]
