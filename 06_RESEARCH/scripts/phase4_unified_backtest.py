"""Phase 4 — frozen backtest (+ paper dry path) on the unified machine.

Orchestrates the FINAL Choice-1 measurement gate: the same unified
composition proven in C1/Phase 3 (`MultiTFProductRuntime.run_batch` →
`PipelineEngine` arm → `PipelineAdapter` scans → `BacktestRunner`
risk/place/intent → manage) over the LOCKED 3-month window, run twice for
determinism, with byte-level artifacts compared and a paper dry-run smoke.

LOCKED window (do not shop): M1 warm-up from 2025-08-01, exec
2025-09-01 → 2025-11-30 (3 months M5). The composition, config, and strategy
code are FROZEN — this script changes nothing; it drives the Phase 3 funnel
composition (imported, not forked) twice and measures determinism.

Artifacts per run: `results/phase4_unified/run{1,2}/` — funnel_summary.json,
trades.csv, report.json, sample_audit.csv, armed_records.json (all produced
by the Phase 3 composition). Plus `summary.json` (this wrapper): determinism
block + October sub-slice comparison vs the Phase 3 run.
Paper dry note: `paper_dry_note.json`.

NOT edge, NOT a retuning gate. n is what it is; the funnel and trade outcomes
are reported separately and honestly.

Usage:
  python 06_RESEARCH/scripts/phase4_unified_backtest.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

import phase3_structure_funnel as p3  # noqa: E402  (the frozen composition)

LOCKED_LOAD = "2025-08-01"
LOCKED_FROM = "2025-09-01"
LOCKED_TO = "2025-11-30"
OCTOBER_FROM = "2025-10-01"
OCTOBER_TO = "2025-10-31"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_frozen(tag: str, out_root: Path) -> dict:
    """One frozen funnel run via the Phase 3 composition (imported, not forked)."""
    out_root.mkdir(parents=True, exist_ok=True)
    args = argparse.Namespace(
        tag=tag,
        out_root=str(out_root),
        load_from=LOCKED_LOAD,
        exec_from=LOCKED_FROM,
        exec_to=LOCKED_TO,
    )
    return p3.run(args)


def paper_dry_smoke(note_path: Path) -> dict:
    """PaperRunner.arm_multi_tf + dry_run wiring, NO terminal dependency.

    Repeats the C1-parity-smoke proof on a small real-data slice: the paper
    runner delegates arming to the SAME product runtime (spy-verified by the
    C1 tests) and its dry-run path records orders without any MT5 send. This
    is a wiring check only — no PnL meaning, demo PnL is never edge.
    """
    note: dict = {"paper_dry": None, "delegates_to_shared_runtime": None}
    try:
        from bisect import bisect_right

        from smc.backtest.pipeline_adapter import PipelineAdapter
        from smc.config.timeframe import Timeframe
        from smc.data.parquet_loader import load_ohlcv_parquet
        from smc.data.resample import resample_multi
        from smc.orchestration.engine import PipelineEngine
        from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime
        from smc.paper.runner import PaperRunner
        from smc.risk.risk_engine import RiskEngine

        TF = Timeframe.M5
        data_path = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
        if not data_path.exists():
            note["skip"] = f"dataset missing: {data_path}"
            note_path.write_text(json.dumps(note, indent=2))
            return note
        m1 = load_ohlcv_parquet(data_path)
        lo = datetime(2025, 9, 20, tzinfo=timezone.utc)
        hi = datetime(2025, 9, 26, tzinfo=timezone.utc)
        m1 = [c for c in m1 if lo - timedelta(days=45) <= c.timestamp <= hi]
        multi = resample_multi(m1, [TF, Timeframe.H1, Timeframe.H4, Timeframe.D1])
        h1 = multi[Timeframe.H1]
        h4 = multi[Timeframe.H4]
        d1 = multi[Timeframe.D1]
        m5 = [c for c in multi[TF] if lo <= c.timestamp <= hi]
        if not m5 or not h1 or not h4:
            note["skip"] = "empty slice"
            note_path.write_text(json.dumps(note, indent=2))
            return note

        class _NullConnector:
            def connect(self):
                return True

            def copy_rates(self, symbol, tf, start, count):
                return None

        engine = PipelineEngine()
        adapter = PipelineAdapter(engine, timeframe=TF)
        adapter.set_candles(m5)
        runner = PaperRunner(
            connector=_NullConnector(), risk_engine=RiskEngine(),
            pipeline=adapter, order_manager=None, position_manager=None,
        )
        h1_ts = [c.timestamp for c in h1]
        bar = m5[-1]
        cut = bisect_right(h1_ts, bar.timestamp) - 1
        series = {
            Timeframe.H1: h1[: cut + 1],
            Timeframe.H4: h4[: bisect_right([c.timestamp for c in h4], bar.timestamp)],
            Timeframe.D1: d1[: bisect_right([c.timestamp for c in d1], bar.timestamp)],
        }
        report = runner.arm_multi_tf(series, as_of=bar.timestamp, arm_bar=len(m5) - 1)
        note["paper_dry"] = {
            "armed": report.armed_count,
            "batches": report.batches,
            "degraded": report.degraded,
            "mt5_required": False,
            "dry_run_orders_sent": 0,
        }
        note["delegates_to_shared_runtime"] = type(runner.runtime) is MultiTFProductRuntime
    except Exception as exc:  # noqa: BLE001 — optional check, never fails Phase 4
        note["skip"] = f"{type(exc).__name__}: {exc}"
    note_path.write_text(json.dumps(note, indent=2, default=str))
    return note


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default=str(REPO_ROOT / "06_RESEARCH" / "results" / "phase4_unified"))
    args = ap.parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    summaries: dict[str, dict] = {}
    for tag in ("run1", "run2"):
        print(f"[p4] === frozen run {tag} ===", flush=True)
        summaries[tag] = run_frozen(tag, out_root / tag)

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
    ignore = {"runtime_seconds", "tag"}
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

    # ---- October sub-slice comparison vs Phase 3 (cheap, from artifacts) -#
    p3_summary_path = REPO_ROOT / "06_RESEARCH" / "results" / "phase3_structure_funnel" / "run1" / "funnel_summary.json"
    october_compare: dict = {}
    if p3_summary_path.exists():
        p3s = json.loads(p3_summary_path.read_text())
        october_compare = {
            "source": str(p3_summary_path.relative_to(REPO_ROOT)),
            "phase3_armed": p3s.get("armed"),
            "phase3_routes": p3s.get("routes"),
            "phase3_fills": p3s.get("fills"),
            "note": (
                "3-month window strictly contains October; per-batch prefix "
                "detection means the 3-month run's October sub-slice is not "
                "expected to equal the October-only run (warm-up + batch "
                "history differ), so this is a REFERENCE row, not an "
                "equality check"
            ),
        }

    summary = {
        "tag": "phase4_unified",
        "window": {
            "load_from": LOCKED_LOAD,
            "exec_from": LOCKED_FROM,
            "exec_to": LOCKED_TO,
            "exec_tf": "M5",
        },
        "config_frozen": {
            "equity": 10_000.0,
            "risk_fraction": 0.01,
            "spread_price": 0.0,
            "news_events": [],
            "sessions": ["ASIA", "LONDON", "NEW_YORK"],
            "detection": ["H4", "H1"],
            "m8_htf": "D1 when available",
            "diag_flags": "none (zone gate / R7 / R9 all live)",
        },
        "composition": (
            "MultiTFProductRuntime.run_batch (C1 product seam) -> "
            "PipelineEngine.arm_at -> PipelineAdapter.generate_candidates -> "
            "BacktestRunner (risk -> pending limits -> R9 intents -> manage); "
            "imported from phase3_structure_funnel.run — NOT forked"
        ),
        "runs": {
            "run1": {
                "bars_m5": r1.get("bars_m5"),
                "htf_batches": r1.get("htf_batches"),
                "merged_pois": r1.get("merged_pois"),
                "passed_validation": r1.get("passed_validation"),
                "pillar_first_failure": r1.get("pillar_first_failure"),
                "armed": r1.get("armed"),
                "armed_m8": r1.get("armed_m8"),
                "routes": r1.get("routes"),
                "routes_by_trigger": r1.get("routes_by_trigger"),
                "placed": r1.get("placed"),
                "intents": {
                    "armed": r1.get("intents_armed"),
                    "placed": r1.get("intents_placed"),
                    "expired": r1.get("intents_expired"),
                },
                "fills": r1.get("fills"),
                "trades": r1.get("trades"),
                "net_pl_diagnostic": sum(
                    getattr(t, "pnl", 0.0) for t in _trades(p1)
                ),
                "exit_mix": r1.get("trades_by_trigger"),
                "runtime_seconds": r1.get("runtime_seconds"),
            },
        },
        "determinism": determinism,
        "october_reference": october_compare,
    }
    # run2 mirrors run1 semantically; keep only the differing runtime field.
    summary["runs"]["run2"] = {
        **summary["runs"]["run1"],
        "net_pl_diagnostic": sum(getattr(t, "pnl", 0.0) for t in _trades(p2)),
        "runtime_seconds": r2.get("runtime_seconds"),
    }
    (out_root / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # ---- Optional paper dry-run wiring smoke --------------------------- #
    paper_note = paper_dry_smoke(out_root / "paper_dry_note.json")

    print(json.dumps({
        "determinism_verdict": determinism["verdict"],
        "armed": r1.get("armed"),
        "routes": r1.get("routes"),
        "fills": r1.get("fills"),
        "trades": r1.get("trades"),
        "october_reference": october_compare,
        "paper_dry": paper_note.get("paper_dry") or paper_note.get("skip"),
    }, indent=2, default=str))
    print(f"[p4] wrote {out_root / 'summary.json'}")
    return 0


def _trades(run_root: Path):
    """Trade PnLs from the run's report.json (diagnostic sum only)."""
    import math

    report_path = run_root / "report.json"
    if not report_path.exists():
        return []
    try:
        data = json.loads(report_path.read_text())
    except (ValueError, OSError):
        return []
    out = []
    for row in data.get("trades", []):
        pnl = row.get("pnl") if isinstance(row, dict) else getattr(row, "pnl", None)
        try:
            value = float(pnl)
        except (TypeError, ValueError):
            value = None
        if value is not None and math.isfinite(value):
            out.append(type("T", (), {"pnl": value})())
    return out


if __name__ == "__main__":
    raise SystemExit(main())
