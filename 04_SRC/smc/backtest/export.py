"""Phase 6 M5 — CSV / JSON export helpers (pure serialization).

Deterministic: identical :class:`~smc.backtest.reports.BacktestReport`
inputs produce byte-identical output (fixed row/column order, ``sort_keys``
on the JSON path, full-repr floats in V1).
"""

from __future__ import annotations

import csv
import json

from smc.backtest.reports import BacktestReport

__all__ = ["to_csv", "to_json"]


def _direction_str(direction) -> str:
    return str(getattr(direction, "value", direction))


def _group_dict(group) -> dict:
    return {
        "n_trades": group.n_trades,
        "n_wins": group.n_wins,
        "n_losses": group.n_losses,
        "win_rate": group.win_rate,
        "gross_profit": group.gross_profit,
        "gross_loss": group.gross_loss,
        "profit_factor": group.profit_factor,
        "net_pnl": group.net_pnl,
        "avg_win": group.avg_win,
        "avg_loss": group.avg_loss,
        "net_pnl_after_cost": group.net_pnl_after_cost,
        "total_cost_usd": group.total_cost_usd,
    }


def to_csv(report: BacktestReport, path) -> None:
    """Write the report's trade list to CSV (fixed column order).

    Fixed header: ticket, direction, symbol, volume, entry_price,
    exit_price, sl, tp, entry_bar, exit_bar, entry_at, exit_at,
    close_kind, win, pnl, poi_id, trigger, route_id, then the appended
    identity columns model_tags, pillar_path, disp_magnitude_atr,
    original_sl, zone_low, zone_high, signal_data_json, entry_anchor,
    tp_source, then the appended V1 cost columns commission_usd,
    spread_cost_usd, slippage_usd, swap_usd, cost_usd, pnl_net, bars_held,
    then the appended Track-B annotation columns f_timing_label,
    post_exit_class (``None`` → empty cell)
    (backward compatible: old columns keep their order; new columns are
    appended; ``None`` → empty cell). Enums/datetimes are
    ``str()``-normalized. Metrics/breakdowns are
    not serialized here — the trade list is the M5 CSV contract.
    """
    header = [
        "ticket", "direction", "symbol", "volume", "entry_price",
        "exit_price", "sl", "tp", "entry_bar", "exit_bar", "entry_at",
        "exit_at", "close_kind", "win", "pnl", "poi_id", "trigger",
        "route_id", "model_tags", "pillar_path", "disp_magnitude_atr",
        "original_sl", "zone_low", "zone_high", "signal_data_json",
        "entry_anchor",
        "tp_source",
        "commission_usd", "spread_cost_usd", "slippage_usd", "swap_usd",
        "cost_usd", "pnl_net", "bars_held",
        "f_timing_label", "post_exit_class",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for trade in report.trades:
            writer.writerow([
                trade.ticket,
                _direction_str(trade.direction),
                trade.symbol,
                trade.volume,
                trade.entry_price,
                trade.exit_price,
                "" if trade.sl is None else trade.sl,
                "" if trade.tp is None else trade.tp,
                trade.entry_bar,
                trade.exit_bar,
                str(trade.entry_at),
                str(trade.exit_at),
                trade.close_kind,
                "1" if trade.win else "0",
                trade.pnl,
                "" if trade.poi_id is None else trade.poi_id,
                "" if trade.trigger is None else trade.trigger,
                "" if trade.route_id is None else trade.route_id,
                "" if trade.model_tags is None else "+".join(trade.model_tags),
                "" if trade.pillar_path is None else trade.pillar_path,
                "" if trade.disp_magnitude_atr is None else trade.disp_magnitude_atr,
                "" if trade.original_sl is None else trade.original_sl,
                "" if trade.zone_low is None else trade.zone_low,
                "" if trade.zone_high is None else trade.zone_high,
                "" if trade.signal_data_json is None else trade.signal_data_json,
                "" if trade.entry_anchor is None else trade.entry_anchor,
                "" if trade.tp_source is None else trade.tp_source,
                trade.commission_usd,
                trade.spread_cost_usd,
                trade.slippage_usd,
                trade.swap_usd,
                trade.cost_usd,
                "" if trade.pnl_net is None else trade.pnl_net,
                "" if trade.bars_held is None else trade.bars_held,
                "" if trade.f_timing_label is None else trade.f_timing_label,
                "" if trade.post_exit_class is None else trade.post_exit_class,
            ])


def to_json(report: BacktestReport, path) -> None:
    """Write the full report (metrics + breakdowns + trade list) to JSON.

    Deterministic: ``sort_keys=True``, enums/datetimes normalized to
    strings, ``None`` stays ``null``.
    """
    payload = {
        "metrics": {
            "n_trades": report.metrics.n_trades,
            "n_wins": report.metrics.n_wins,
            "n_losses": report.metrics.n_losses,
            "win_rate": report.metrics.win_rate,
            "gross_profit": report.metrics.gross_profit,
            "gross_loss": report.metrics.gross_loss,
            "profit_factor": report.metrics.profit_factor,
            "net_pnl": report.metrics.net_pnl,
            "max_drawdown": report.metrics.max_drawdown,
            "avg_win": report.metrics.avg_win,
            "avg_loss": report.metrics.avg_loss,
            "total_commission_usd": report.metrics.total_commission_usd,
            "total_spread_cost_usd": report.metrics.total_spread_cost_usd,
            "total_slippage_usd": report.metrics.total_slippage_usd,
            "total_swap_usd": report.metrics.total_swap_usd,
            "total_cost_usd": report.metrics.total_cost_usd,
            "net_pnl_after_cost": report.metrics.net_pnl_after_cost,
        },
        "by_trigger": {key: _group_dict(g) for key, g in report.by_trigger.items()},
        "by_poi": {key: _group_dict(g) for key, g in report.by_poi.items()},
        "by_timing_label": {key: _group_dict(g)
                            for key, g in report.by_timing_label.items()},
        "by_post_exit_class": {key: _group_dict(g)
                               for key, g in report.by_post_exit_class.items()},
        "blocked_by_reason": dict(report.blocked_by_reason),
        "trades": [
            {
                "ticket": trade.ticket,
                "direction": _direction_str(trade.direction),
                "symbol": trade.symbol,
                "volume": trade.volume,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "sl": trade.sl,
                "tp": trade.tp,
                "entry_bar": trade.entry_bar,
                "exit_bar": trade.exit_bar,
                "entry_at": str(trade.entry_at),
                "exit_at": str(trade.exit_at),
                "close_kind": trade.close_kind,
                "win": trade.win,
                "pnl": trade.pnl,
                "poi_id": trade.poi_id,
                "trigger": trade.trigger,
                "route_id": trade.route_id,
                "model_tags": list(trade.model_tags) if trade.model_tags is not None else None,
                "pillar_path": trade.pillar_path,
                "disp_magnitude_atr": trade.disp_magnitude_atr,
                "original_sl": trade.original_sl,
                "zone_low": trade.zone_low,
                "zone_high": trade.zone_high,
                "signal_data_json": trade.signal_data_json,
                "entry_anchor": trade.entry_anchor,
                "tp_source": trade.tp_source,
                "commission_usd": trade.commission_usd,
                "spread_cost_usd": trade.spread_cost_usd,
                "slippage_usd": trade.slippage_usd,
                "swap_usd": trade.swap_usd,
                "cost_usd": trade.cost_usd,
                "pnl_net": trade.pnl_net,
                "bars_held": trade.bars_held,
                "f_timing_label": trade.f_timing_label,
                "post_exit_class": trade.post_exit_class,
            }
            for trade in report.trades
        ],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")
