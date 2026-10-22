"""Staged product baseline PILOT — costs-on, product config (Tier-1).

Measurement only — no optimization. Runs the FROZEN Phase 3/4 product
composition (MultiTFProductRuntime H4+H1 detect + D1->M8, M5 execution,
PipelineEngine arm, PipelineAdapter scans incl. structural TP feed,
BacktestRunner risk/place/R9-intent/manage, current §5a seek contract)
over the LOCKED 3-month window with the V1 cost ledger explicitly ON,
twice for determinism.

Window (locked, do not shop): M1 warm-up load from 2025-08-01, exec
2025-09-01 → 2025-11-30 (M5) — the Phase 4 window, so the pilot is
directly comparable to the zero-cost frozen run except for costs and
post-September stack changes (structural TP feed, §5a seek, cost
ledger), all recorded in summary.json.

Costs ON explicit (Architect ruling 2026-10-11):
  commission_usd_per_lot_per_side=0.0 (no broker schedule on file —
  never invented), slippage_points=1.0, apply_half_spread=True,
  spread_fallback_price=0.26, swap=deferred(0.0, bars_held logged).

Artifacts per run: results/product_baseline_pilot/run{1,2}/ (the Phase 3
composition outputs: funnel_summary.json, trades.csv, report.json,
sample_audit.csv, funnel_by_day.csv, armed_records.json).
Plus root summary.json: banner + window + full config + determinism +
funnel + trade metrics + cost totals + mixes.

DIAGNOSTIC ONLY — NOT PERFORMANCE / NOT EDGE. n is what it is.

Usage:
  python 06_RESEARCH/scripts/product_baseline_pilot.py [--out-root ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

import phase3_structure_funnel as p3  # noqa: E402  (frozen composition)
from smc.backtest.cost_model import CostConfig  # noqa: E402

BANNER = "DIAGNOSTIC ONLY — NOT PERFORMANCE / NOT EDGE"

LOAD_FROM = "2025-08-01"
EXEC_FROM = "2025-09-01"
EXEC_TO = "2025-11-30"
DEFAULT_TAG = "product_baseline_pilot"

# Costs ON explicit — Architect ruling 2026-10-11. Every value below is
# recorded verbatim in summary.json; commission stays 0.0 because no
# broker schedule is on file (never invented).
PILOT_COSTS = CostConfig(
    apply_costs=True,
    commission_usd_per_lot_per_side=0.0,
    slippage_points=1.0,
    spread_fallback_price=0.26,
    apply_half_spread=True,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_once(tag: str, out_root: Path, *, load_from: str, exec_from: str,
             exec_to: str) -> dict:
    """One pilot run via the frozen composition (imported, not forked)."""
    out_root.mkdir(parents=True, exist_ok=True)
    args = argparse.Namespace(
        tag=tag,
        out_root=str(out_root),
        load_from=load_from,
        exec_from=exec_from,
        exec_to=exec_to,
        cost_config=PILOT_COSTS,
    )
    return p3.run(args)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default=str(
        REPO_ROOT / "06_RESEARCH" / "results" / "product_baseline_pilot"))
    # Window overrides (defaults reproduce the 3-month pilot exactly):
    # the 6M extension passes --load-from 2025-05-01 --exec-from 2025-06-01
    # --exec-to 2025-11-30 --tag product_baseline_6m --out-root .../product_baseline_6m.
    ap.add_argument("--load-from", default=LOAD_FROM)
    ap.add_argument("--exec-from", default=EXEC_FROM)
    ap.add_argument("--exec-to", default=EXEC_TO)
    ap.add_argument("--tag", default=DEFAULT_TAG)
    args = ap.parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    load_from, exec_from, exec_to = args.load_from, args.exec_from, args.exec_to

    summaries: dict[str, dict] = {}
    for tag in ("run1", "run2"):
        print(f"[pilot] === costs-on run {tag} "
              f"(exec {exec_from} -> {exec_to}) ===", flush=True)
        summaries[tag] = run_once(tag, out_root / tag, load_from=load_from,
                                  exec_from=exec_from, exec_to=exec_to)
    r1, r2 = summaries["run1"], summaries["run2"]
    p1, p2 = out_root / "run1", out_root / "run2"

    # ---- Determinism: byte-identical trades.csv + report.json ---------- #
    byte_check: dict = {}
    for name in ("trades.csv", "report.json"):
        f1, f2 = p1 / name, p2 / name
        if f1.exists() and f2.exists():
            same = f1.read_bytes() == f2.read_bytes()
            byte_check[name] = {
                "byte_identical": same,
                "sha256_run1": _sha256(f1),
                "sha256_run2": _sha256(f2),
            }
        else:
            byte_check[name] = {"byte_identical": None, "reason": "file absent"}

    # Semantic funnel equality (runtime seconds + tag excluded).
    ignore = {"runtime_seconds", "tag", "notes"}
    semantic_diffs = {
        key: [r1.get(key), r2.get(key)]
        for key in r1
        if key not in ignore and r1.get(key) != r2.get(key)
    }
    determinism = {
        "byte_check": byte_check,
        "semantic_diffs": semantic_diffs,
        "semantic_equal": not semantic_diffs,
        "verdict": (
            "PASS"
            if not semantic_diffs
            and all(v.get("byte_identical") for v in byte_check.values())
            else "FAIL"
        ),
    }

    # ---- Metrics + costs + mixes from run1's report.json ---------------- #
    report = _load_json(p1 / "report.json")
    metrics = report.get("metrics", {})
    trades = report.get("trades", [])
    tp_source_mix: dict[str, int] = {}
    tp_source_net: dict[str, float] = {}
    for t in trades:
        key = t.get("tp_source") or "unknown"
        tp_source_mix[key] = tp_source_mix.get(key, 0) + 1
        tp_source_net[key] = tp_source_net.get(key, 0.0) + float(
            t.get("pnl_net", t.get("pnl", 0.0)) or 0.0)
    by_trigger = report.get("by_trigger", {})
    trigger_net = {k: {"n": v.get("n_trades"),
                       "net_pnl_after_cost": v.get("net_pnl_after_cost"),
                       "total_cost_usd": v.get("total_cost_usd"),
                       "net_pnl_gross": v.get("net_pnl")}
                   for k, v in by_trigger.items()}

    summary = {
        "banner": BANNER,
        "tag": args.tag,
        "window": {
            "load_from": load_from,
            "exec_from": exec_from,
            "exec_to": exec_to,
            "exec_tf": "M5",
        },
        "config_frozen": {
            "equity": 10_000.0,
            "risk_fraction": 0.01,
            "pip_value_per_lot": 10.0,
            "min_lots": 0.01,
            "lot_step": 0.01,
            "spread_price": 0.0,
            "news_events": [],
            "sessions": ["ASIA", "LONDON", "NEW_YORK"],
            "timeframe": "M5",
            "detection": ["H4", "H1"],
            "detection_note": (
                "H4+H1 required via MultiTFProductRuntime (loud fail); "
                "D1 forwarded to M8 when available; W1 NOT in this "
                "composition (p3 resamples M5/H1/H4/D1 only)"
            ),
            "m8": "provisioned via the product runtime path",
            "structural_tp": (
                "feed as wired (structural_swing vs atr_fallback, "
                "tp_source audit-only)"
            ),
            "seek_contract": "current §5a (redesign accepted 2026-10-05)",
            "dry_run": "N/A (backtest; dry_run is a live/paper concept)",
            "trigger_d": "compiled, structurally unfireable (A5 ruling)",
        },
        "costs_on_explicit": {
            "apply_costs": PILOT_COSTS.apply_costs,
            "commission_usd_per_lot_per_side":
                PILOT_COSTS.commission_usd_per_lot_per_side,
            "commission_note": (
                "0.0 — no broker schedule on file; never invented"
            ),
            "slippage_points": PILOT_COSTS.slippage_points,
            "slippage_scope": "every exit except take_profit",
            "apply_half_spread": PILOT_COSTS.apply_half_spread,
            "spread_fallback_price": PILOT_COSTS.spread_fallback_price,
            "swap": "deferred (0.0; bars_held logged per trade)",
        },
        "composition": (
            "phase3_structure_funnel.run (imported, not forked): "
            "MultiTFProductRuntime.run_batch at new-H1-close cadence -> "
            "PipelineEngine arm -> PipelineAdapter scans -> BacktestRunner "
            "(risk -> pending limits -> R9 intents -> manage); only addition "
            "vs Phase 4 is the explicit CostConfig above (measurement-only)"
        ),
        "funnel_run1": {
            "bars_m5": r1.get("bars_m5"),
            "htf_batches": r1.get("htf_batches"),
            "batch_errors": r1.get("batch_errors"),
            "merged_pois": r1.get("merged_pois"),
            "passed_validation": r1.get("passed_validation"),
            "pillar_first_failure": r1.get("pillar_first_failure"),
            "armed": r1.get("armed"),
            "armed_by_tf": r1.get("armed_by_tf"),
            "armed_m8": r1.get("armed_m8"),
            "scanned_pois": r1.get("scanned_pois"),
            "routes": r1.get("routes"),
            "routes_by_trigger": r1.get("routes_by_trigger"),
            "routes_m8": r1.get("routes_m8"),
            "placed": r1.get("placed"),
            "intents_armed": r1.get("intents_armed"),
            "intents_placed": r1.get("intents_placed"),
            "intents_expired": r1.get("intents_expired"),
            "fills": r1.get("fills"),
            "trades": r1.get("trades"),
            "trades_by_trigger": r1.get("trades_by_trigger"),
            "blocked_by_reason": report.get("blocked_by_reason", {}),
            "runtime_seconds_run1": r1.get("runtime_seconds"),
            "runtime_seconds_run2": r2.get("runtime_seconds"),
        },
        "trade_metrics_run1": {
            "n_trades": metrics.get("n_trades"),
            "n_wins": metrics.get("n_wins"),
            "win_rate": metrics.get("win_rate"),
            "profit_factor_gross": metrics.get("profit_factor"),
            "net_pnl_gross_ledger": metrics.get("net_pnl"),
            "max_drawdown_gross_ledger": metrics.get("max_drawdown"),
            "avg_win_gross": metrics.get("avg_win"),
            "avg_loss_gross": metrics.get("avg_loss"),
        },
        "cost_totals_run1_usd": {
            "total_commission_usd": metrics.get("total_commission_usd"),
            "total_spread_cost_usd": metrics.get("total_spread_cost_usd"),
            "total_slippage_usd": metrics.get("total_slippage_usd"),
            "total_swap_usd": metrics.get("total_swap_usd"),
            "total_cost_usd": metrics.get("total_cost_usd"),
            "net_pnl_after_cost_ledger": metrics.get("net_pnl_after_cost"),
        },
        "per_trigger_net": trigger_net,
        "tp_source_mix": {"counts": tp_source_mix, "net_ledger": tp_source_net},
        "determinism": determinism,
        "notes": [
            BANNER,
            "Costs are an additive fill-only ledger; entry/SL/TP prices, "
            "gates, sizing, and locked constants are untouched by this run.",
            "Gross columns are byte-stable vs the zero-cost path; net "
            "columns are the costs-on headline.",
            "n is what it is — no parameter search, no WF/MC, no edge read.",
        ],
    }
    (out_root / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    m = summary["trade_metrics_run1"]
    c = summary["cost_totals_run1_usd"]
    print(json.dumps({
        "banner": BANNER,
        "determinism_verdict": determinism["verdict"],
        "window": f"{exec_from} -> {exec_to}",
        "bars_m5": r1.get("bars_m5"),
        "armed": r1.get("armed"),
        "routes": r1.get("routes"),
        "trades": m.get("n_trades"),
        "win_rate": m.get("win_rate"),
        "profit_factor_gross": m.get("profit_factor_gross"),
        "net_pnl_gross_ledger": m.get("net_pnl_gross_ledger"),
        "total_cost_usd": c.get("total_cost_usd"),
        "net_pnl_after_cost_ledger": c.get("net_pnl_after_cost_ledger"),
        "trades_by_trigger": r1.get("trades_by_trigger"),
        "tp_source_mix": tp_source_mix,
    }, indent=2, default=str))
    print(f"[pilot] wrote {out_root / 'summary.json'}")
    return 0 if determinism["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
