"""Phase 6: Backtesting — event-driven engine + walk-forward/Monte Carlo.

Milestone 1 (thin bar loop + data feed) public surface:

* :class:`~smc.backtest.data_feed.CandleSeries` — one validated OHLCV series
* :class:`~smc.backtest.data_feed.MultiTimeframeFeed` — primary TF + HTF map
* :class:`~smc.backtest.clock.BarClock` — deterministic bar clock (injected ``now``)
* :class:`~smc.backtest.bar_loop.BarLoop` / :class:`~smc.backtest.bar_loop.BarHandler`
  — the thin bar-driven loop skeleton

Milestone 2 (pending orders + fill model) adds the execution primitives:

* :class:`~smc.backtest.orders.PendingOrder` / ``PendingOrderBook`` — resting
  limit book (deterministic tickets, §23/give-up expiry)
* :mod:`smc.backtest.fill_model` — pure limit-fill / SL / TP decisions
  (touch = fill at the limit price; same-bar SL+TP → SL wins)
* :class:`~smc.backtest.positions.PositionStore` — open-position tracking
  that applies the fill-model close decisions

Milestone 3 (RiskEngine integration) adds the runner:

* :class:`~smc.backtest.runner.BacktestRunner` — the locked per-bar order
  of operations (Friday EOD → hard-cancel → exits → fills → entries) as an
  M1 ``BarHandler``, with the candidate-entry test seam

Later milestones add core reports (M5) and the paper runner (M6)
behind the same seams — see ``01_ARCHITECTURE/SMC_PHASE_6_DESIGN.md``.
"""

from smc.backtest.bar_loop import BarHandler, BarLoop, LoopStats, RecordingHandler
from smc.backtest.clock import BarClock, ClockNotSetError
from smc.backtest.data_feed import CandleSeries, MultiTimeframeFeed
from smc.backtest.fill_model import (
    BarClose,
    CloseKind,
    evaluate_position_bar,
    fill_price,
    limit_filled,
    sl_hit,
    tp_hit,
)
from smc.backtest.orders import PendingOrder, PendingOrderBook
from smc.backtest.positions import BacktestPosition, ClosedPosition, PositionStore
from smc.backtest.runner import (
    BacktestRunner,
    BlockedEntry,
    CandidateEntry,
    RunnerConfig,
)

__all__ = [
    "BacktestPosition",
    "BacktestRunner",
    "BlockedEntry",
    "CandidateEntry",
    "BarClock",
    "BarClose",
    "BarHandler",
    "BarLoop",
    "CandleSeries",
    "CloseKind",
    "ClockNotSetError",
    "ClosedPosition",
    "LoopStats",
    "MultiTimeframeFeed",
    "PendingOrder",
    "PendingOrderBook",
    "PositionStore",
    "RecordingHandler",
    "RunnerConfig",
    "evaluate_position_bar",
    "fill_price",
    "limit_filled",
    "sl_hit",
    "tp_hit",
]
