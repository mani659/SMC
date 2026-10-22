"""DUMB FLOWCHART V1 capture — W3 (2025-06-01 → 2025-11-30), optionally W2.

DUMB IMPLEMENTATION — DIAGNOSTIC — NOT EDGE.

Runs `smc.dumb.runner.run_dumb_flowchart` over a frozen 6-month window with
the SAME composition data path COMPLEX used (parquet loader + resampler,
read-only), collects the locked rule metrics, and writes:

```
06_RESEARCH/results/dumb_flowchart_v1/<W>/run<id>/{trades.csv, run_meta.json}
06_RESEARCH/results/dumb_flowchart_v1/<W>/summary.json                  (run1)
06_RESEARCH/results/dumb_flowchart_v1/determinism.json                  (both)
```

Determinism: two captures (`run1`, `run2`) must be byte-identical on
``trades.csv`` (md5 + sha256) — recorded in `determinism.json`, PASS only
when both exist and match. NO edge claim anywhere; net PnL is book-internal
price units labelled DIAGNOSTIC ONLY. `compare_block` mirrors the design
§6 criteria (fill-count guidance only, never PnL).

Usage:
    python dumb_flowchart_v1_capture.py --window W3 --run-id run1
    python dumb_flowchart_v1_capture.py --window W3 --run-id run2
    python dumb_flowchart_v1_capture.py --window W2 --run-id run1   # optional
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.config.timeframe import Timeframe
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.dumb import DUMB_ATR_PERIOD, DUMB_CONFIRM_MAX_BARS, \
    DUMB_SL_BUFFER_ATR, DUMB_TP_R_MULTIPLE
from smc.dumb.runner import run_dumb_flowchart

BANNER = "DUMB IMPLEMENTATION — DIAGNOSTIC — NOT EDGE"
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "dumb_flowchart_v1"

WINDOWS = {
    "W3": {
        "exec_from": datetime(2025, 6, 1, tzinfo=timezone.utc),
        "exec_to": datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc),
        "load_from": datetime(2025, 5, 1, tzinfo=timezone.utc),
        "label": "2025-06-01 -> 2025-11-30",
        "complex_n": 58,
        "complex_report": "06_RESEARCH/POST_DEDUP_EDGE_DIAGNOSTIC_REPORT.md",
    },
    "W2": {
        "exec_from": datetime(2024, 12, 1, tzinfo=timezone.utc),
        "exec_to": datetime(2025, 5, 31, 23, 59, 59, tzinfo=timezone.utc),
        "load_from": datetime(2024, 11, 1, tzinfo=timezone.utc),
        "label": "2024-12-01 -> 2025-05-31",
        "complex_n": 44,
        "complex_report": "06_RESEARCH/POST_DEDUP_EDGE_STABILITY_REPORT.md",
    },
}

TRADE_FIELDS = [
    "ticket", "zone_poi_id", "detection_tf", "zone_kind", "direction",
    "zone_low", "zone_high", "sweep_ts", "confirm_ts", "entry_idx",
    "entry_ts", "entry_price", "sl", "tp", "r_stop", "atr_at_entry",
    "exit_idx", "exit_ts", "exit_price", "close_kind", "bars_held", "pnl",
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
    print(f"[dumb] {window_key} {run_id}: exec {spec['exec_from'].date()} -> "
          f"{spec['exec_to'].date()}, load {spec['load_from'].date()}", flush=True)

    t0 = time.perf_counter()
    m1 = load_ohlcv_parquet(PARQUET)
    m1 = [c for c in m1
          if spec["load_from"] <= c.timestamp <= spec["exec_to"] + timedelta(days=1)]
    if not m1:
        raise SystemExit(f"no M1 bars for {window_key}")
    multi = resample_multi(m1, [Timeframe.M5, Timeframe.H4, Timeframe.D1,
                                 Timeframe.W1])
    m5 = multi[Timeframe.M5]
    exec_from_idx = len(m5)
    for i, c in enumerate(m5):
        if c.timestamp >= spec["exec_from"]:
            exec_from_idx = i
            break
    m5_exec = m5[exec_from_idx:]
    series_by_tf = {Timeframe.M5: m5, Timeframe.H4: multi[Timeframe.H4],
                    Timeframe.D1: multi[Timeframe.D1],
                    Timeframe.W1: multi[Timeframe.W1]}
    trades, stats = run_dumb_flowchart(m5, series_by_tf,
                                       exec_from=spec["exec_from"],
                                       exec_to=spec["exec_to"])
    elapsed = round(time.perf_counter() - t0, 1)

    rows = []
    for t in trades:
        rows.append({
            "ticket": t.ticket,
            "zone_poi_id": t.zone_poi_id,
            "detection_tf": t.detection_tf.name,
            "zone_kind": t.zone_kind,
            "direction": t.direction.name,
            "zone_low": t.zone[0],
            "zone_high": t.zone[1],
            "sweep_ts": t.sweep_ts.isoformat(),
            "confirm_ts": t.confirm_ts.isoformat(),
            "entry_idx": t.entry_idx,
            "entry_ts": t.entry_ts.isoformat(),
            "entry_price": round(t.entry_price, 6),
            "sl": round(t.sl_price, 6),
            "tp": round(t.tp_price, 6),
            "r_stop": round(t.r_stop, 6),
            "atr_at_entry": round(t.atr_at_entry, 6),
            "exit_idx": t.exit_idx,
            "exit_ts": (t.exit_ts.isoformat() if t.exit_ts else ""),
            "exit_price": (round(t.exit_price, 6) if t.exit_price is not None else ""),
            "close_kind": t.close_kind,
            "bars_held": t.bars_held,
            "pnl": round(t.pnl, 6),
        })
    with (out_dir / "trades.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=TRADE_FIELDS)
        w.writeheader()
        w.writerows(rows)

    # ---- diagnostic aggregates (book-internal, NO edge claim) ---------- #
    pnl_vals = [r["pnl"] for r in rows]
    gross_win = sum(p for p in pnl_vals if p > 0)
    gross_loss = sum(-p for p in pnl_vals if p < 0)
    pf = (gross_win / gross_loss) if gross_loss > 0 else None
    kinds: dict[str, int] = {}
    for r in rows:
        kinds[r["close_kind"]] = kinds.get(r["close_kind"], 0) + 1
    tfs: dict[str, int] = {}
    dirs: dict[str, int] = {}
    for r in rows:
        tfs[r["detection_tf"]] = tfs.get(r["detection_tf"], 0) + 1
        dirs[r["direction"]] = dirs.get(r["direction"], 0) + 1

    meta = {
        "banner": BANNER,
        "window": window_key,
        "window_label": spec["label"],
        "run_id": run_id,
        "constants": {
            "DUMB_CONFIRM_MAX_BARS": DUMB_CONFIRM_MAX_BARS,
            "DUMB_SL_BUFFER_ATR": DUMB_SL_BUFFER_ATR,
            "DUMB_TP_R_MULTIPLE": DUMB_TP_R_MULTIPLE,
            "DUMB_ATR_PERIOD": DUMB_ATR_PERIOD,
        },
        "runtime_seconds": elapsed,
        "trades_md5": _md5(out_dir / "trades.csv"),
        "trades_sha256": _sha256(out_dir / "trades.csv"),
        "counters": {
            "n_m5_bars": stats.n_m5_bars,
            "n_m5_exec_bars": len(m5_exec),
            "n_zones_activated": stats.n_zones_activated,
            "n_zones_superseded": stats.n_zones_superseded,
            "n_htf_rescans": stats.n_htf_rescans,
            "n_setups_swept": stats.n_setups_swept,
            "n_setup_anchor_updates": stats.n_setup_anchor_updates,
            "n_entry_skipped_outside_zone": stats.n_entry_skipped_outside_zone,
            "n_confirmed": stats.n_confirmed,
            "n_expired": stats.n_expired,
            "n_sweeps_zone_busy": stats.n_sweeps_zone_busy,
            "n_trades": stats.n_trades,
        },
        "counters_by_tf": stats.counters_by_tf,
        "exit_mix": kinds,
        "trades_by_zone_tf": tfs,
        "trades_by_direction": dirs,
    }
    (out_dir / "run_meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"[dumb] {window_key} {run_id}: {len(rows)} trades in {elapsed}s "
          f"(zones {stats.n_zones_activated}, setups {stats.n_setups_swept}, "
          f"confirmed {stats.n_confirmed})", flush=True)

    if run_id == "run1":
        summary = {
            "banner": BANNER,
            "window": window_key,
            "window_label": spec["label"],
            "constants": meta["constants"],
            "n_trades": stats.n_trades,
            "n_setups_swept": stats.n_setups_swept,
            "n_confirmed": stats.n_confirmed,
            "n_entries": stats.n_trades,
            "exit_mix": kinds,
            "trades_by_zone_tf": tfs,
            "trades_by_direction": dirs,
            "net_pl_diagnostic": {
                "sum_pnl": round(sum(pnl_vals), 6),
                "gross_win": round(gross_win, 6),
                "gross_loss": round(gross_loss, 6),
                "profit_factor": (round(pf, 6) if pf is not None else None),
                "label": "DIAGNOSTIC ONLY — book-internal price units, NOT an expectancy or edge claim",
            },
            "compare_block": {
                f"complex_{window_key.lower()}_n": spec["complex_n"],
                f"dumb_{window_key.lower()}_n": stats.n_trades,
                "fill_ratio_vs_complex": (round(stats.n_trades / spec["complex_n"], 4)
                                          if spec["complex_n"] else None),
                "note": "count comparison only (design §6) — never a PnL comparison",
            },
            "counters": meta["counters"],
            "counters_by_tf": stats.counters_by_tf,
            "book": {
                "trades_csv": str((out_dir / "trades.csv").relative_to(REPO_ROOT)),
                "trades_md5": meta["trades_md5"],
                "trades_sha256": meta["trades_sha256"],
            },
        }
        (OUT_ROOT / window_key / "summary.json").write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return meta


def determinism(window_key: str) -> dict:
    runs = []
    for rid in ("run1", "run2"):
        p = OUT_ROOT / window_key / rid / "trades.csv"
        if p.exists():
            runs.append({"run_id": rid, "md5": _md5(p), "sha256": _sha256(p)})
    ok = (len(runs) == 2 and runs[0]["md5"] == runs[1]["md5"]
          and runs[0]["sha256"] == runs[1]["sha256"])
    return {
        "window": window_key,
        "runs": runs,
        "determinism_pass": ok if len(runs) == 2 else None,
        "note": ("trades.csv byte-identical run1 vs run2" if ok
                 else ("single run present — determinism NOT established"
                       if len(runs) < 2 else "runs DIFFER — capture not deterministic")),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="W3", choices=sorted(WINDOWS))
    ap.add_argument("--run-id", required=True, choices=["run1", "run2"])
    args = ap.parse_args(argv)
    print(BANNER, flush=True)
    capture(args.window, args.run_id)
    det = determinism(args.window)
    det_path = OUT_ROOT / "determinism.json"
    state = {}
    if det_path.exists():
        state = json.loads(det_path.read_text(encoding="utf-8"))
    state[det["window"]] = det
    det_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps(det, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
