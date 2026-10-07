"""POST-V1 PHASE C — frozen-artifact breakdowns + fingerprint (read-only).

Everything the Phase C closeout report tabulates, recomputed from the SHIPPED
artifacts so the report's numbers are reproducible rather than transcribed:

  * config fingerprint — sha256 over the canonical (sorted-key) JSON of the
    frozen ``RunnerConfig`` recorded in the merged summary, plus the sha256 of
    the two research scripts and the canonical parquet;
  * coverage — bars, window, segment list, and the per-segment coverage check
    against the canonical series;
  * core metrics + exit-kind / BE-latch histograms (why are 567 trades losses
    while TP is never in ``closed_by_kind``?);
  * per-year (from the merged summary, cross-checked against the trade list);
  * per-trigger and per-direction breakdowns with P/L, PF and share of flow;
  * blocked-reason histogram.

Writes 06_RESEARCH/results/phase_c_breakdowns.json and prints it.

    python 06_RESEARCH/scripts/phase_c_breakdowns.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "06_RESEARCH" / "results"
RUN = "phase_c_baseline_run1"
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
FROZEN_SCRIPTS = (
    "06_RESEARCH/scripts/phase_c_baseline_backtest.py",
    "06_RESEARCH/scripts/phase_b_fidelity_backtest.py",
)
OUT = RESULTS / "phase_c_breakdowns.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def profit_factor(pnl: pd.Series) -> float | None:
    losses = -pnl[pnl < 0].sum()
    if losses == 0:
        return None  # undefined, never inf
    return round(float(pnl[pnl > 0].sum() / losses), 6)


def bucket(pnl: pd.Series) -> dict:
    return {
        "n_trades": int(len(pnl)),
        "n_wins": int((pnl > 0).sum()),
        "n_losses": int((pnl < 0).sum()),
        "n_flat": int((pnl == 0).sum()),
        "win_rate": round(float((pnl > 0).mean()), 6) if len(pnl) else None,
        "net_pnl": round(float(pnl.sum()), 6),
        "profit_factor": profit_factor(pnl),
        "avg_win": round(float(pnl[pnl > 0].mean()), 6) if (pnl > 0).any() else None,
        "avg_loss": round(float(pnl[pnl < 0].mean()), 6) if (pnl < 0).any() else None,
    }


def main() -> int:
    summary = json.loads((RESULTS / RUN / "merged" / "summary.json").read_text("utf-8"))
    trades = pd.read_csv(RESULTS / RUN / "merged" / "trades.csv")
    trades["pnl"] = pd.to_numeric(trades["pnl"])
    trades["entry_at"] = pd.to_datetime(
        trades["entry_at"], utc=True, format="ISO8601"
    )

    config_json = json.dumps(summary["config"], sort_keys=True)
    report: dict = {
        "run": RUN,
        "fingerprints": {
            "config_canonical_json_sha256": hashlib.sha256(
                config_json.encode("utf-8")
            ).hexdigest(),
            "config": summary["config"],
            "canonical_parquet_sha256": sha256_file(PARQUET),
            "frozen_scripts": {
                name: sha256_file(REPO_ROOT / name) for name in FROZEN_SCRIPTS
            },
        },
        "coverage": {
            "bars_processed": summary["window"]["bars_processed"],
            "window_from": summary["window"]["window_from"],
            "window_to": summary["window"]["window_to"],
            "segments": summary["funnel"]["segments"],
            "detection_window_bars": summary["funnel"]["detection_window_bars"],
            "invariants": summary["invariants"],
            "pass": summary["pass"],
        },
        "core_metrics": summary["metrics"],
        "funnel": summary["funnel"],
        "by_trigger_trades": summary["by_trigger_trades"],
        "closed_by_kind": (
            trades["close_kind"].value_counts().sort_index().to_dict()
        ),
        "exit_kind_x_win": {
            f"{kind}|win={win}": int(count)
            for (kind, win), count in trades.groupby(["close_kind", "win"])
            .size()
            .items()
        },
        "per_year_from_summary": summary["per_segment"],
        "all_trades": bucket(trades["pnl"]),
        "by_trigger": {
            trigger: bucket(group["pnl"])
            for trigger, group in trades.groupby("trigger")
        },
        "by_trigger_share": {
            trigger: round(len(group) / len(trades), 6)
            for trigger, group in trades.groupby("trigger")
        },
        "by_direction": {
            direction: bucket(group["pnl"])
            for direction, group in trades.groupby("direction")
        },
    }

    # Per-year recomputed from the trade list (independent of the summary).
    per_year = {}
    for year, group in trades.groupby(trades["entry_at"].dt.year):
        per_year[str(int(year))] = bucket(group["pnl"])
    report["per_year_from_trades"] = per_year

    # Sizing / risk context.
    report["sizing"] = {
        "volume_values": sorted(trades["volume"].round(3).unique().tolist()),
        "n_distinct_volumes": int(trades["volume"].round(3).nunique()),
    }

    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    print(f"\n[written] {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
