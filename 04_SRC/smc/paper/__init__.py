"""Phase 6 M6 — Paper Trading: runner, broker adapter, KPI logging.

The paper stack runs the FROZEN shared components (``PipelineEngine``
through the M4 adapter, ``RiskEngine``) against the LIVE execution layer
(``OrderManager`` / ``PositionManager`` / ``MT5Connector``) on a demo
account, with the M4 bar-loop order applied bar-close driven:

* :class:`smc.paper.runner.PaperRunner` — one-cycle bar-close loop;
* :class:`smc.paper.broker_adapter.BrokerAdapter` — thin live boundary;
* :class:`smc.paper.kpi_logger.KPILogger` — operational KPI records.

The paper package shares NO mutable state with the backtest fill model:
backtest stores (``PendingOrderBook`` / ``PositionStore``) stay
backtest-pure; paper observes broker truth instead of simulating fills.
"""

from smc.paper.broker_adapter import BrokerAdapter, ModifyOutcome, PlaceOutcome
from smc.paper.kpi_logger import KPILogger, KpiRecord
from smc.paper.runner import PaperConfig, PaperRunner

__all__ = [
    "BrokerAdapter",
    "ModifyOutcome",
    "PlaceOutcome",
    "KPILogger",
    "KpiRecord",
    "PaperConfig",
    "PaperRunner",
]
