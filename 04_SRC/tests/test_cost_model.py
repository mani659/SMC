"""V1 cost model tests — arithmetic identities only (Tier-1, 2026-10-11).

Covers ``smc/backtest/cost_model.py`` (pure math), the position-store
seam (entry-spread capture, close pricing, bars_held), the runner seam
(net equity, spread threading), and the report/export contract (cost
columns + summary totals).

Every assertion below is arithmetic or determinism — no test asserts
profitability, expectancy, or any threshold on returns. No live MT5 is
required; all fills are synthetic. Monetary values use fixed example
rates (e.g. commission 7.0) that are NOT broker schedules.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from smc.backtest.bar_loop import BarLoop
from smc.backtest.cost_model import (
    CostBreakdown,
    CostConfig,
    CostModel,
    net_ledger,
    normalize_spread,
    resolve_leg_spread,
    slippage_in_scope,
)
from smc.backtest.data_feed import CandleSeries
from smc.backtest.export import to_csv, to_json
from smc.backtest.orders import PendingOrderBook
from smc.backtest.positions import ClosedPosition, PositionStore
from smc.backtest.reports import (
    BacktestReport,
    CoreMetrics,
    TradeRecord,
    build_report,
)
from smc.backtest.runner import BacktestRunner, CandidateEntry, RunnerConfig
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.risk.risk_engine import RiskEngine

TF = Timeframe.M5
START = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)  # Thursday
PIP = 10.0

CALM = (100.25, 100.45, 100.1, 100.3)
TOUCH = (99.9, 100.1, 99.9, 100.0)      # fills a resting 100.0 LONG limit
TP_BAR = (104.1, 104.6, 103.9, 104.5)   # hits a 104.0 TP
SL_BAR = (98.9, 99.2, 98.8, 99.0)       # hits a 99.0 SL


def _candle(index, row, start=START):
    stamp = start + timedelta(minutes=5 * index)
    open_, high, low, close = row
    return Candle(timestamp=stamp, open=open_, high=high, low=low,
                  close=close, timeframe=TF)


def _run(candle_factory, rows, *, config=None, candidate=None, start=START):
    series = CandleSeries(candle_factory(rows, timeframe=TF, start=start),
                          timeframe=TF)
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=config or RunnerConfig(),
    )
    runner.set_atr(2.0)
    runner.submit_entry(candidate or CandidateEntry(
        direction=Direction.LONG, entry_price=100.0, sl_price=99.0,
        tp_price=104.0, score=10.0,
    ))
    BarLoop(series, runner).run()
    return runner


def _cost_config(**overrides):
    kwargs = dict(commission_usd_per_lot_per_side=7.0,
                  slippage_points=1.0,
                  spread_fallback_price=0.26,
                  apply_half_spread=True)
    kwargs.update(overrides)
    return CostConfig(**kwargs)


# ---------------------------------------------------------------------- #
# 1. Pure arithmetic — commission both legs, both sides
# ---------------------------------------------------------------------- #
def test_commission_covers_both_legs():
    # Direction-agnostic: the same quote prices LONG and SHORT closes
    # (sign handling is asserted at the store seam below).
    model = CostModel(config=_cost_config(), pip_value_per_lot=PIP)
    quote = model.quote_close(lots=0.5, entry_spread=None,
                              exit_spread=None, exit_kind="stop_loss")
    # 7.0 USD/lot/side x 0.5 lots x 2 sides = 7.0 USD ...
    assert quote.commission_usd == pytest.approx(7.0)
    # ... converted with the run's own divisor (0.7 ledger units).
    assert quote.commission_usd / PIP == pytest.approx(0.7)


def test_half_spread_charged_per_leg_in_ledger_units():
    cfg = CostConfig(apply_half_spread=True)
    model = CostModel(config=cfg, pip_value_per_lot=PIP)
    quote = model.quote_close(lots=0.5, entry_spread=0.5, exit_spread=1.5,
                              exit_kind="take_profit")
    # (0.5/2 + 1.5/2) x 0.5 lots = 0.5 ledger units -> 5.0 USD.
    assert quote.spread_cost_usd == pytest.approx(5.0)
    # TP exit: no slippage; no commission configured.
    assert quote.slippage_usd == pytest.approx(0.0)
    assert quote.cost_usd == pytest.approx(5.0)
    assert quote.cost_ledger == pytest.approx(0.5)


def test_slippage_scope_matrix():
    assert slippage_in_scope("take_profit") is False   # resting limit: free
    assert slippage_in_scope("stop_loss") is True
    assert slippage_in_scope("risk_exit") is True
    assert slippage_in_scope("friday_eod") is True
    assert slippage_in_scope("breaker") is True
    assert slippage_in_scope(None) is True             # unknown = market
    cfg = _cost_config()
    model = CostModel(config=cfg, pip_value_per_lot=PIP)
    free = model.quote_close(lots=0.5, entry_spread=None, exit_spread=None,
                             exit_kind="take_profit")
    assert free.slippage_usd == pytest.approx(0.0)
    # 1.0 point x 0.5 lots = 0.5 ledger -> 5.0 USD on a market exit.
    stopped = model.quote_close(lots=0.5, entry_spread=None, exit_spread=None,
                                exit_kind="stop_loss")
    assert stopped.slippage_usd == pytest.approx(5.0)


def test_swap_always_zero():
    model = CostModel(config=_cost_config(), pip_value_per_lot=PIP)
    quote = model.quote_close(lots=1.0, entry_spread=1.0, exit_spread=1.0,
                              exit_kind="stop_loss")
    assert quote.swap_usd == 0.0  # deferred by ruling


def test_net_ledger_identity():
    assert net_ledger(0.4, 0.17) == pytest.approx(0.23)
    assert net_ledger(-0.1, 0.0) == pytest.approx(-0.1)


# ---------------------------------------------------------------------- #
# 2. Spread source: known vs fallback vs disabled
# ---------------------------------------------------------------------- #
def test_resolve_leg_spread_paths():
    cfg = _cost_config()  # fallback 0.26, half-spread on
    assert resolve_leg_spread(cfg, 0.30) == pytest.approx(0.30)  # known wins
    assert resolve_leg_spread(cfg, None) == pytest.approx(0.26)  # fallback
    assert resolve_leg_spread(cfg, 0.0) == pytest.approx(0.26)   # 0.0=unknown
    assert normalize_spread(0.0) is None
    assert normalize_spread(None) is None
    assert normalize_spread(0.30) == pytest.approx(0.30)
    off = _cost_config(apply_half_spread=False)
    assert resolve_leg_spread(off, 0.30) == 0.0
    assert resolve_leg_spread(off, None) == 0.0
    quiet = _cost_config(apply_costs=False)
    assert resolve_leg_spread(quiet, 0.30) == 0.0


def test_apply_costs_false_is_zero_despite_params():
    model = CostModel(config=_cost_config(apply_costs=False),
                      pip_value_per_lot=PIP)
    quote = model.quote_close(lots=1.0, entry_spread=1.0, exit_spread=1.0,
                              exit_kind="stop_loss")
    assert quote == CostBreakdown.zero()
    assert quote.cost_usd == 0.0 and quote.cost_ledger == 0.0


def test_default_config_is_zero_cost():
    model = CostModel(config=CostConfig(), pip_value_per_lot=PIP)
    quote = model.quote_close(lots=0.1, entry_spread=0.3, exit_spread=0.3,
                              exit_kind="stop_loss")
    assert quote == CostBreakdown.zero()
    assert CostConfig.zero().apply_costs is False


# ---------------------------------------------------------------------- #
# 3. Config loud-fail (misconfiguration never prices silently)
# ---------------------------------------------------------------------- #
def test_cost_config_rejects_negatives():
    with pytest.raises(ValueError):
        CostConfig(commission_usd_per_lot_per_side=-1.0)
    with pytest.raises(ValueError):
        CostConfig(slippage_points=-0.5)
    with pytest.raises(ValueError):
        CostConfig(spread_fallback_price=-0.1)


def test_cost_model_rejects_bad_inputs():
    model = CostModel(config=_cost_config(), pip_value_per_lot=PIP)
    with pytest.raises(ValueError):
        model.quote_close(lots=0.0, entry_spread=None, exit_spread=None,
                          exit_kind="stop_loss")
    with pytest.raises(ValueError):
        CostModel(config=_cost_config(), pip_value_per_lot=0.0)


# ---------------------------------------------------------------------- #
# 4. Store seam — entry-spread capture, close pricing, bars_held
# ---------------------------------------------------------------------- #
def test_unbound_store_prices_zero_cost():
    store = PositionStore()  # never bound: the legacy path
    pos = store.open(direction=Direction.LONG, volume=0.5, entry_price=100.0,
                     sl=99.0, tp=104.0, entry_bar=7, entry_at=START,
                     entry_spread_price=0.30)
    assert pos.entry_spread_price == pytest.approx(0.30)
    (closed,) = store.apply_bar(_candle(9, TP_BAR), 9,
                                exit_spread_price=0.30)
    assert closed.realized_pnl == pytest.approx(2.0)  # (104-100) x 0.5
    assert closed.cost_usd == 0.0 and closed.cost_ledger == 0.0
    assert closed.bars_held == 2  # exit_bar 9 - entry_bar 7


def test_zero_spread_normalizes_to_unknown():
    store = PositionStore()
    pos = store.open(direction=Direction.LONG, volume=0.5, entry_price=100.0,
                     sl=99.0, tp=104.0, entry_bar=7, entry_at=START,
                     entry_spread_price=0.0)
    assert pos.entry_spread_price is None  # 0.0 = gate off, never zero spread


def test_modify_sl_preserves_entry_spread():
    store = PositionStore()
    pos = store.open(direction=Direction.LONG, volume=0.5, entry_price=100.0,
                     sl=99.0, tp=104.0, entry_bar=7, entry_at=START,
                     entry_spread_price=0.30)
    updated = store.modify_sl(pos.ticket, 100.0)
    assert updated.entry_spread_price == pytest.approx(0.30)


def test_bound_store_short_side_signs():
    store = PositionStore()
    store.bind_cost_model(CostModel(config=_cost_config(),
                                    pip_value_per_lot=PIP))
    pos = store.open(direction=Direction.SHORT, volume=0.5, entry_price=100.0,
                     sl=101.0, tp=96.0, entry_bar=7, entry_at=START,
                     entry_spread_price=0.5)
    (closed,) = store.apply_bar(_candle(9, (95.0, 96.5, 95.8, 96.0)), 9,
                                exit_spread_price=1.5)
    assert closed.realized_pnl == pytest.approx(2.0)  # (96-100) x -1 x 0.5
    assert closed.win is True
    # Spread (0.5/2 + 1.5/2) x 0.5 = 0.5 ledger; commission 0.7 ledger.
    assert closed.cost_ledger == pytest.approx(1.2)
    assert closed.cost_usd == pytest.approx(12.0)
    assert closed.realized_pnl - closed.cost_ledger == pytest.approx(0.8)


# ---------------------------------------------------------------------- #
# 5. Runner seam — net equity + spread threading (real RiskEngine)
# ---------------------------------------------------------------------- #
def test_runner_zero_config_reproduces_legacy_equity(candle_factory):
    config = RunnerConfig()  # default cost config: zero-cost by construction
    runner = _run(candle_factory, [CALM, TOUCH, TP_BAR], config=config)
    assert len(runner.positions.closed_positions()) == 1
    (record,) = runner.positions.closed_positions()
    assert record.realized_pnl == pytest.approx(0.4)
    assert record.cost_usd == 0.0 and record.cost_ledger == 0.0
    assert record.bars_held == 1
    # Legacy identity: equity moves with gross x pip value, exactly.
    assert runner.current_equity() == pytest.approx(10000.0 + 0.4 * PIP)


def test_runner_costed_tp_close_exact_math(candle_factory):
    config = RunnerConfig(spread_price=0.30, cost=_cost_config())
    runner = _run(candle_factory, [CALM, TOUCH, TP_BAR], config=config)
    (record,) = runner.positions.closed_positions()
    assert record.kind == "take_profit"
    assert record.realized_pnl == pytest.approx(0.4)      # price untouched
    assert record.commission_usd == pytest.approx(1.40)   # 7 x 0.1 x 2
    assert record.spread_cost_usd == pytest.approx(0.30)  # (0.3/2)x2 x 0.1 x10
    assert record.slippage_usd == pytest.approx(0.0)      # TP rest = free
    assert record.swap_usd == 0.0
    assert record.cost_usd == pytest.approx(1.70)
    assert record.cost_ledger == pytest.approx(0.17)
    # Net equity: (0.4 - 0.17) x 10 -> 10002.30, not the gross 10004.00.
    assert runner.current_equity() == pytest.approx(10002.30)
    assert record.bars_held == 1


def test_runner_costed_sl_close_pays_slippage(candle_factory):
    config = RunnerConfig(spread_price=0.30, cost=_cost_config())
    runner = _run(candle_factory, [CALM, TOUCH, SL_BAR], config=config)
    (record,) = runner.positions.closed_positions()
    assert record.kind == "stop_loss"
    assert record.realized_pnl == pytest.approx(-0.1)
    assert record.slippage_usd == pytest.approx(1.00)     # 1.0pt x 0.1 x10
    assert record.cost_usd == pytest.approx(1.40 + 0.30 + 1.00)
    assert runner.current_equity() == pytest.approx(
        10000.0 + (-0.1 - 0.27) * PIP)


def test_runner_spread_fallback_used_when_spread_unknown(candle_factory):
    # spread_price=0.0 (gate off / unknown) + half-spread on -> fallback.
    config = RunnerConfig(cost=_cost_config())
    runner = _run(candle_factory, [CALM, TOUCH, TP_BAR], config=config)
    (record,) = runner.positions.closed_positions()
    # (0.26/2 + 0.26/2) x 0.1 lots x 10 = 0.26 USD.
    assert record.spread_cost_usd == pytest.approx(0.26)


# ---------------------------------------------------------------------- #
# 6. Report/export contract — cost columns + summary totals
# ---------------------------------------------------------------------- #
def _costed_report():
    store = PositionStore()
    store.bind_cost_model(CostModel(config=_cost_config(),
                                    pip_value_per_lot=PIP))
    pos = store.open(direction=Direction.LONG, volume=0.5, entry_price=100.0,
                     sl=99.0, tp=104.0, entry_bar=7, entry_at=START,
                     entry_spread_price=0.5)
    (closed,) = store.apply_bar(_candle(9, TP_BAR), 9, exit_spread_price=1.5)
    from smc.backtest.runner import RunnerResult
    return build_report(RunnerResult(closed=[closed], blocked=[],
                                     route_ids={}))


def test_report_carries_cost_totals():
    report = _costed_report()
    (trade,) = report.trades
    assert trade.cost_usd == pytest.approx(12.0)   # 7.0 commission + 5.0 spread
    assert trade.pnl_net == pytest.approx(2.0 - 1.2)
    assert trade.bars_held == 2
    assert trade.pnl == pytest.approx(2.0)         # gross verbatim
    assert report.metrics.net_pnl == pytest.approx(2.0)
    assert report.metrics.total_cost_usd == pytest.approx(12.0)
    assert report.metrics.total_commission_usd == pytest.approx(7.0)
    assert report.metrics.total_spread_cost_usd == pytest.approx(5.0)
    assert report.metrics.total_slippage_usd == pytest.approx(0.0)
    assert report.metrics.total_swap_usd == 0.0
    assert report.metrics.net_pnl_after_cost == pytest.approx(0.8)
    assert report.by_trigger["unattributed"].net_pnl_after_cost == pytest.approx(0.8)
    assert report.by_trigger["unattributed"].total_cost_usd == pytest.approx(12.0)


def test_export_csv_and_json_carry_cost_fields(tmp_path):
    report = _costed_report()
    csv_path = tmp_path / "trades.csv"
    json_path = tmp_path / "report.json"
    to_csv(report, csv_path)
    to_json(report, json_path)
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert header.endswith("commission_usd,spread_cost_usd,slippage_usd,"
                           "swap_usd,cost_usd,pnl_net,bars_held,"
                           "f_timing_label,post_exit_class")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    trade = payload["trades"][0]
    assert trade["cost_usd"] == pytest.approx(12.0)
    assert trade["pnl_net"] == pytest.approx(0.8)
    assert trade["bars_held"] == 2
    assert payload["metrics"]["total_cost_usd"] == pytest.approx(12.0)
    assert payload["metrics"]["net_pnl_after_cost"] == pytest.approx(0.8)


def test_zero_cost_report_matches_legacy_totals():
    store = PositionStore()  # unbound: legacy path
    store.open(direction=Direction.LONG, volume=0.5, entry_price=100.0,
               sl=99.0, tp=104.0, entry_bar=7, entry_at=START)
    (closed,) = store.apply_bar(_candle(9, TP_BAR), 9)
    from smc.backtest.runner import RunnerResult
    report = build_report(RunnerResult(closed=[closed], blocked=[],
                                       route_ids={}))
    assert report.metrics.net_pnl == pytest.approx(2.0)
    assert report.metrics.total_cost_usd == 0.0
    assert report.metrics.net_pnl_after_cost == pytest.approx(2.0)
    assert report.trades[0].pnl_net == pytest.approx(2.0)
