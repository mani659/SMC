"""Phase 3 chart helper — armed POI geometry (zone + arm-bar context).

Renders up to N armed-POI charts from the funnel run's captured records:
zone rectangle + surrounding M5 candles around the arm bar. A routed POI's
entry/SL/TP are drawn when present. Charts are labeled honestly: this is
armed-POI geometry, and if the POI never filled, the title says "no fill".

Usage:
  python 06_RESEARCH/scripts/phase3_funnel_charts.py \
      --run-root 06_RESEARCH/results/phase3_structure_funnel/run1 --max 6
"""

from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_left, bisect_right
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

OUT_DEFAULT = REPO_ROOT / "06_RESEARCH" / "results" / "phase3_structure_funnel" / "charts"


def main() -> int:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    ap = argparse.ArgumentParser()
    ap.add_argument("--run-root", default=str(REPO_ROOT / "06_RESEARCH" / "results" / "phase3_structure_funnel" / "run1"))
    ap.add_argument("--max", type=int, default=6)
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    args = ap.parse_args()

    run_root = Path(args.run_root)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = json.loads((run_root / "armed_records.json").read_text())
    if not records:
        print("[p3-charts] no armed records — nothing to render")
        return 0
    summary = json.loads((run_root / "funnel_summary.json").read_text())
    m5_start = summary["window"]["start"]

    data_path = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not data_path.exists():
        print(f"[p3-charts] SKIP: dataset missing at {data_path}")
        return 0
    m1 = load_ohlcv_parquet(data_path)
    from datetime import datetime, timedelta

    start_dt = datetime.fromisoformat(m5_start) - timedelta(days=2)
    end_dt = datetime.fromisoformat(summary["window"]["end"]) + timedelta(days=1)
    m1 = [c for c in m1 if start_dt <= c.timestamp <= end_dt]
    m5 = resample_multi(m1, [Timeframe.M5])[Timeframe.M5]
    ts = [c.timestamp for c in m5]

    # Prefer routed POIs first (they carry entry/SL/TP context), then arm order.
    ordered = sorted(
        records.values(),
        key=lambda r: (r.get("routed") != "true", int(r.get("armed_bar", 0))),
    )
    rendered = 0
    for rec in ordered:
        if rendered >= args.max:
            break
        arm_bar = int(rec.get("armed_bar", 0) or 0)
        if arm_bar >= len(m5):
            continue
        lo = max(arm_bar - 120, 0)
        hi = min(arm_bar + 120, len(m5) - 1)
        window = m5[lo:hi + 1]
        if not window:
            continue
        zone_low = float(rec["zone_low"])
        zone_high = float(rec["zone_high"])
        routed = rec.get("routed") == "true"
        title = (
            f"{rec['poi_id']} [{rec['detection_tf']}] tags={rec['model_tags']} "
            + ("ROUTED (F)" if routed else "NO FILL")
        )
        fig, ax = plt.subplots(figsize=(14, 7))
        for i, candle in enumerate(window):
            color = "#2e7d32" if candle.close >= candle.open else "#c62828"
            ax.plot([i, i], [candle.low, candle.high], color=color, lw=0.7)
            ax.add_patch(plt.Rectangle(
                (i - 0.3, min(candle.open, candle.close)), 0.6,
                abs(candle.close - candle.open) + 1e-9,
                facecolor=color, edgecolor=color))
        ax.axhspan(zone_low, zone_high, color="#1e88e5", alpha=0.18, label="POI zone")
        arm_idx = arm_bar - lo
        ax.axvline(arm_idx, color="#f9a825", lw=1.5, label="arm bar")
        if routed:
            for key, color, label in (
                ("entry", "#6a1b9a", "entry (limit)"),
                ("original_sl", "#c62828", "original SL"),
                ("tp", "#2e7d32", "TP"),
            ):
                value = rec.get(key)
                if value not in (None, ""):
                    ax.axhline(float(value), color=color, ls="--", lw=1.2, label=label)
        step = max(len(window) // 8, 1)
        ax.set_xticks(range(0, len(window), step))
        ax.set_xticklabels(
            [window[i].timestamp.strftime("%m-%d %H:%M") for i in range(0, len(window), step)],
            fontsize=7)
        ax.set_title(title + " — armed-POI geometry (identification, not a trade claim)")
        ax.legend(loc="best", fontsize=8)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        path = out_dir / f"{rec['poi_id']}_{'routed' if routed else 'nofill'}.png"
        fig.savefig(path, dpi=130)
        plt.close(fig)
        rendered += 1
        print(f"[p3-charts] {path.name}")
    print(f"[p3-charts] rendered {rendered} chart(s) -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
