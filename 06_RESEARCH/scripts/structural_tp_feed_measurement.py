#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Structural TP feed — measurement on the frozen 3-month funnel window.

Lead Architect directive (2026-10-05): diagnostic-only measurement of the
implemented structural TP feed (design lock
`06_RESEARCH/STRUCTURAL_TP_FEED_DESIGN.md`, Architect-accepted). Dual run
on the same frozen Phase 4 / 3-month funnel window (M1 load 2025-08-01,
exec 2025-09-01→11-30) via the imported Phase 3 composition. NO
optimization, NO threshold tuning, NO expectancy claims — PnL stays
diagnostic.

Measured (placed-order level + trade level):
  * tp_non_null_rate on PLACED orders;
  * share of placed orders with tp_source structural_swing vs
    atr_fallback (harness wraps ``PendingOrderBook.place`` — wrap
    pattern, restored in ``finally``; the tag rides on the order);
  * determinism: trades.csv byte-identity across run1/run2 (the selector
    is a pure function — byte identity must hold);
  * exit mix delta vs the pre-feed funnel (both runs carry the feed).

Artifacts: ``06_RESEARCH/results/structural_tp_feed/run{1,2}/`` (the
composition's own artifacts + the harness-local placed_audit.json) and
``summary.json``. Report:
``06_RESEARCH/STRUCTURAL_TP_FEED_IMPLEMENTATION_NOTE.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

LOCKED_LOAD = "2025-08-01"
LOCKED_FROM = "2025-09-01"
LOCKED_TO = "2025-11-30"

OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "structural_tp_feed"
SUMMARY_JSON = OUT_ROOT / "summary.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instrument_placements(out_root: Path):
    """Wrap PendingOrderBook.place to audit each placed order's TP source.

    Harness-local instrumentation (FR-4 wrap pattern): the original place
    runs unchanged; the wrapper records (tp is not None, tp_source) per
    placed order; restored in ``finally`` by the caller.
    """
    from smc.backtest import orders as orders_module

    audit = {"placed": 0, "tp_non_null": 0,
             "structural_swing": 0, "atr_fallback": 0, "tp_source_none": 0}
    original_place = orders_module.PendingOrderBook.place

    def auditing_place(self, **kw):
        order = original_place(self, **kw)
        audit["placed"] += 1
        if order.tp is not None:
            audit["tp_non_null"] += 1
        src = getattr(order, "tp_source", None)
        if src == "structural_swing":
            audit["structural_swing"] += 1
        elif src == "atr_fallback":
            audit["atr_fallback"] += 1
        else:
            audit["tp_source_none"] += 1
        return order

    orders_module.PendingOrderBook.place = auditing_place
    return type("PlacementInstrument", (), {
        "audit": audit,
        "restore": staticmethod(
            lambda: setattr(orders_module.PendingOrderBook, "place",
                            original_place)),
    })()


def run_frozen(tag: str, out_root: Path) -> dict:
    out_root.mkdir(parents=True, exist_ok=True)
    import phase3_structure_funnel as p3
    args = argparse.Namespace(
        tag=tag, out_root=str(out_root),
        load_from=LOCKED_LOAD, exec_from=LOCKED_FROM, exec_to=LOCKED_TO,
    )
    return p3.run(args)


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    summaries: dict[str, dict] = {}
    audits: dict[str, dict] = {}
    for tag in ("run1", "run2"):
        print(f"[tpf] === structural-TP feed run {tag} ===", flush=True)
        instr = instrument_placements(OUT_ROOT / tag)
        try:
            summaries[tag] = run_frozen(tag, OUT_ROOT / tag)
        finally:
            audits[tag] = dict(instr.audit)
            instr.restore()
            (OUT_ROOT / tag / "placed_audit.json").write_text(
                json.dumps(audits[tag], indent=1), encoding="utf-8")

    r1, r2 = summaries["run1"], summaries["run2"]
    p1, p2 = OUT_ROOT / "run1", OUT_ROOT / "run2"

    byte_check = {}
    for name in ("trades.csv", "report.json"):
        f1, f2 = p1 / name, p2 / name
        if f1.exists() and f2.exists():
            byte_check[name] = {
                "byte_identical": f1.read_bytes() == f2.read_bytes(),
                "sha256": _sha256(f1),
            }
        else:
            byte_check[name] = {"byte_identical": None, "reason": "absent"}
    determinism = "PASS" if all(
        v.get("byte_identical") for v in byte_check.values()) else "FAIL"

    audit1 = audits["run1"]
    placed = audit1["placed"]
    tp_rate = (round(100.0 * audit1["tp_non_null"] / placed, 1)
               if placed else None)
    struct_share = (round(100.0 * audit1["structural_swing"] / placed, 1)
                    if placed else None)
    fallback_share = (round(100.0 * audit1["atr_fallback"] / placed, 1)
                      if placed else None)

    exit1 = Counter()
    tp_src_trades = Counter()
    net = 0.0
    report_path = p1 / "report.json"
    if report_path.exists():
        data = json.loads(report_path.read_text())
        for row in data.get("trades", []):
            exit1[str(row.get("close_kind") or "other")] += 1
            tp_src_trades[str(row.get("tp_source") or "none")] += 1
            try:
                net += float(row.get("pnl"))
            except (TypeError, ValueError):
                pass

    summary = {
        "directive": ("structural TP feed measurement — frozen 3m window, "
                      "diagnostic only, NOT performance"),
        "design": "06_RESEARCH/STRUCTURAL_TP_FEED_DESIGN.md (accepted 2026-10-05)",
        "window": {"load_from": LOCKED_LOAD, "exec_from": LOCKED_FROM,
                   "exec_to": LOCKED_TO, "exec_tf": "M5", "frozen": True},
        "placed_audit_run1": audit1,
        "metrics_run1": {
            "placed": placed,
            "tp_non_null_rate_pct": tp_rate,
            "structural_share_pct": struct_share,
            "atr_fallback_share_pct": fallback_share,
        },
        "trades_run1": {
            "trades": r1.get("trades"), "fills": r1.get("fills"),
            "routes": r1.get("routes"),
            "routes_by_trigger": r1.get("routes_by_trigger"),
            "exit_mix": dict(exit1),
            "tp_source_by_trade": dict(tp_src_trades),
            "net_pl_diagnostic": round(net, 4),
        },
        "determinism": {"byte_check": byte_check, "verdict": determinism},
        "run2_mirror": {"placed_audit": audits["run2"],
                        "routes": r2.get("routes"),
                        "fills": r2.get("fills"),
                        "trades": r2.get("trades")},
        "pre_feed_baseline_3m": {
            "routes": 9, "placed": 2, "fills": 2, "trades": 2,
            "exit_mix": {"stop_loss": 2, "be_scratch_subset": 1},
            "net_pl_diagnostic": -0.3013,
            "note": "identical frozen window BEFORE the feed "
                    "(FROZEN_FUNNEL_NEW_CONTRACT_REPORT.md) — direct "
                    "before/after anchor",
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=1, default=str),
                            encoding="utf-8")

    print(json.dumps(summary["metrics_run1"], indent=1))
    print(json.dumps(summary["trades_run1"], indent=1, default=str))
    print("determinism:", determinism)
    print(f"[tpf] wrote {SUMMARY_JSON}")
    return 0 if determinism == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
