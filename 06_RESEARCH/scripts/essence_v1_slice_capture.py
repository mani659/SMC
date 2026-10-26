"""ESSENCE contract v1 — diagnostic capture over the frozen 6m window (W3).

ESSENCE V1 SLICE — NOT FULL COMPLEX REWRITE.

Runs `smc.essence.runner.run_essence_v1` on native M1 over the frozen
window (load 2025-05-01, exec 2025-06-01 → 2025-11-30 — the same window the
COMPLEX baseline reports use) and writes:

```
06_RESEARCH/results/essence_v1_slice/<W>/run<id>/{trades.csv, run_meta.json}
06_RESEARCH/results/essence_v1_slice/<W>/summary.json        (run1)
06_RESEARCH/results/essence_v1_slice/determinism.json        (both)
```

Determinism: `run1` vs `run2` byte-identical on `trades.csv` (md5+sha256),
recorded in `determinism.json`, PASS only when both exist and match. NO
edge claim anywhere; PnL is book-internal price units per unit of XAU,
DIAGNOSTIC ONLY (costs 0 — NOT a trading result).

Usage:
    python essence_v1_slice_capture.py --window W3 --run-id run1
    python essence_v1_slice_capture.py --window W3 --run-id run2
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.config.timeframe import Timeframe
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.essence import (
    ESSENCE_ATR_PERIOD,
    ESSENCE_BE_BUFFER_ATR,
    ESSENCE_LIMIT_EXPIRY_BARS,
    ESSENCE_MIN_RR,
    ESSENCE_SL_MIN_PIPS,
)
from smc.essence.runner import run_essence_v1

BANNER = "ESSENCE V1 SLICE — NOT FULL COMPLEX REWRITE"
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "essence_v1_slice"

WINDOWS = {
    "W3": {
        "exec_from": datetime(2025, 6, 1, tzinfo=timezone.utc),
        "exec_to": datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc),
        "load_from": datetime(2025, 5, 1, tzinfo=timezone.utc),
        "label": "2025-06-01 -> 2025-11-30",
        "complex_n": 58,
        "complex_report": "06_RESEARCH/POST_DEDUP_EDGE_DIAGNOSTIC_REPORT.md",
    },
}

TRADE_FIELDS = [
    "ticket", "zone_poi_id", "detection_tf", "zone_kind", "direction",
    "zone_low", "zone_high", "sweep_ts", "sweep_extreme", "confirm_kind",
    "confirm_ts", "terminal_idx", "entry_level", "entry_ts", "entry_price",
    "sl_price", "sl_pips_buffer", "tp_price", "target_ref", "rr_planned",
    "r_stop", "atr_at_entry", "limit_placed_idx", "limit_expiry_bars",
    "be_applied", "exit_idx", "exit_ts", "exit_price", "close_kind",
    "bars_held", "pnl",
]


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def capture(window_key: str, run_id: str) -> dict:
    spec = WINDOWS[window_key]
    out_dir = OUT_ROOT / window_key / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[essence] {window_key} {run_id}: exec {spec['exec_from'].date()} -> "
          f"{spec['exec_to'].date()}, load {spec['load_from'].date()}", flush=True)

    t0 = time.perf_counter()
    m1 = load_ohlcv_parquet(PARQUET)
    m1 = [c for c in m1
          if spec["load_from"] <= c.timestamp <= spec["exec_to"] + timedelta(days=1)]
    if not m1:
        raise SystemExit(f"no M1 bars for {window_key}")
    print(f"[essence] {len(m1):,} M1 bars loaded", flush=True)

    multi = resample_multi(m1, [Timeframe.H4, Timeframe.D1, Timeframe.W1])
    series_by_tf = {Timeframe.H4: multi[Timeframe.H4],
                    Timeframe.D1: multi[Timeframe.D1],
                    Timeframe.W1: multi[Timeframe.W1]}

    trades, stats = run_essence_v1(m1, series_by_tf,
                                   exec_from=spec["exec_from"],
                                   exec_to=spec["exec_to"],
                                   on_progress=lambda i, n, _p0=t0: print(
                                       f"[essence] bar {i:,}/{n:,} "
                                       f"({time.perf_counter() - _p0:.0f}s)", flush=True))
    elapsed = time.perf_counter() - t0

    trades_csv = out_dir / "trades.csv"
    with trades_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TRADE_FIELDS)
        writer.writeheader()
        for t in trades:
            row = {k: getattr(t, k) for k in TRADE_FIELDS if hasattr(t, k)}
            row["zone_low"], row["zone_high"] = t.zone
            row["detection_tf"] = t.detection_tf.name
            row["direction"] = t.direction.name
            row["target_ref"] = f"{t.target_ref[0]}@{t.target_ref[1]:.2f}"
            for ts_key in ("sweep_ts", "confirm_ts", "entry_ts", "exit_ts"):
                v = row.get(ts_key)
                row[ts_key] = v.isoformat() if isinstance(v, datetime) else (v or "")
            for k in TRADE_FIELDS:
                row.setdefault(k, "")
            writer.writerow(row)

    run_meta = {
        "banner": BANNER,
        "window": window_key,
        "run_id": run_id,
        "label": spec["label"],
        "load_from": spec["load_from"].isoformat(),
        "exec_from": spec["exec_from"].isoformat(),
        "exec_to": spec["exec_to"].isoformat(),
        "n_m1_bars": stats.n_m1_bars,
        "elapsed_s": round(elapsed, 1),
        "no_edge_claim": True,
        "pnl_units": "book-internal price units per 1 XAU; DIAGNOSTIC ONLY; costs 0",
        "essence_constants": {
            "sl_pips_buffer": ESSENCE_SL_MIN_PIPS,
            "min_rr": ESSENCE_MIN_RR,
            "limit_expiry_bars": ESSENCE_LIMIT_EXPIRY_BARS,
            "be_buffer_atr": ESSENCE_BE_BUFFER_ATR,
            "atr_period_m1": ESSENCE_ATR_PERIOD,
        },
        "stats": {k: v for k, v in asdict(stats).items()},
        "signed_picks": {
            "entry_tf": "A (M1 sniper)",
            "sl": "B (2-5 pips beyond M1 structure)",
            "tp": "D (M8 profile, min 1:5 RR)",
            "pure_runner_be": "ON (1.0x ATR to BE, 100% runner)",
            "confirm_set": "C (M8 preferred set: ending diagonal wired)",
            "fallback_sweep": "OUT of v1 build (include later)",
        },
    }
    (out_dir / "run_meta.json").write_text(
        json.dumps(run_meta, indent=2, default=str), encoding="utf-8")

    # deterministic summary id output
    print(f"[essence] trades={len(trades)} elapsed={elapsed:.1f}s", flush=True)
    print(f"[essence] funnel={json.dumps({k: v for k, v in asdict(stats).items()})}",
          flush=True)
    return {
        "trades_csv": str(trades_csv),
        "n_trades": len(trades),
        "md5": _md5(trades_csv),
        "sha256": _sha256(trades_csv),
        "stats": {k: v for k, v in asdict(stats).items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", choices=list(WINDOWS), default="W3")
    ap.add_argument("--run-id", choices=["run1", "run2"], default="run1")
    args = ap.parse_args()

    result = capture(args.window, args.run_id)

    summary_path = OUT_ROOT / args.window / "summary.json"
    summary = {}
    if args.run_id == "run1":
        summary = {
            "banner": BANNER,
            "window": args.window,
            "run1": result,
            "complex_n": WINDOWS[args.window]["complex_n"],
            "complex_report": WINDOWS[args.window]["complex_report"],
            "note": ("DIAGNOSTIC ONLY — no edge claim. The COMPLEX n is the "
                     "frozen baseline count for scale comparison only; the "
                     "essence rule set is a different trade definition."),
        }
        summary_path.write_text(json.dumps(summary, indent=2, default=str),
                                encoding="utf-8")

    # determinism record for the pair
    det_path = OUT_ROOT / "determinism.json"
    det = {}
    if det_path.exists():
        det = json.loads(det_path.read_text(encoding="utf-8"))
    det.setdefault(args.window, {})
    det[args.window][args.run_id] = {"md5": result["md5"],
                                     "sha256": result["sha256"]}
    runs = det[args.window]
    if "run1" in runs and "run2" in runs:
        runs["byte_identical"] = runs["run1"]["md5"] == runs["run2"]["md5"]
    det_path.write_text(json.dumps(det, indent=2), encoding="utf-8")
    print(f"[essence] written {summary_path} (run1 only) + {det_path}", flush=True)


if __name__ == "__main__":
    main()
