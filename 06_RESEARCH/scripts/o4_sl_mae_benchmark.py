"""O4 — SL / MAE vs the expert ~30-pip benchmark (read-only measurement).

Question (``OPEN_DECISIONS_RESEARCH_AGENDA.md`` §O4): does the shipped ATR-
buffer stop sit materially worse than the expert's ~30-pip reference on realised
paths, and would a pinned-distance stop reduce avoidable stop-outs without
changing entry validity?

READ-ONLY. No SL code, constant or gate is touched. This script reads the
**product trades already exported** by the frozen October composition
(``o2_htf_sweep_stage_funnel/trades.csv`` — same window/composition as O1–O3)
and measures post-entry path excursion on the execution series:

  MAE = worst adverse excursion from entry (price, then pips)
  MFE = best favourable excursion from entry

--------------------------------------------------------------------------
PRE-REGISTERED (frozen before any result was inspected)
--------------------------------------------------------------------------
WINDOW
  fills from exec 2025-10-01 → 2025-10-31 UTC (product path, full
  D1/H4/H1/M15 detection set). n is small (~11) and is labelled as such
  everywhere; no second slice is added mid-flight.

PIP DEFINITION (XAUUSD, 2-digit gold)
  1 pip = 0.10 price units  →  30 pips = 3.00 price units.
  Sanity-checked against the data: the instrument trades near 4,000 and the
  exported stops span 3–12 price units, i.e. 30–120 pips, which is only
  coherent under the 0.10 definition (an FX 0.0001 pip would put the whole
  book inside half a pip).

SL SOURCE
  ``original_sl`` (the placement stop) when present — never the BE-modified
  working ``sl`` column. When ``original_sl`` is empty the working ``sl`` is
  used and the row is flagged.

MAE / MFE path
  Execution series = M5, reconstructed from ``07_DATA/XAUUSD_M1.parquet`` and
  resampled exactly as the composition does. Path = entry bar through exit bar
  inclusive (the whole entry bar counts, which is conservative: it never
  understates MAE).

  LONG : MAE = max(0, entry - min(low));  MFE = max(0, max(high) - entry)
  SHORT: MAE = max(0, max(high) - entry); MFE = max(0, entry - min(low))

CLEAN-STOP TOLERANCE
  ``hit_product_sl`` = stop-like ``close_kind`` AND |exit - original_sl| <= 0.05
  price units (fixed; not tuned).
--------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

# --- pre-registered constants ---------------------------------------------
PIP_PRICE = 0.10          # XAUUSD: 1 pip = 0.10 price units
BENCH_PIPS = 30           # expert review benchmark
BENCH_PRICE = BENCH_PIPS * PIP_PRICE          # = 3.00 price units
STOP_TOLERANCE = 0.05     # clean-stop match tolerance (price units)
LOAD_FROM = "2025-05-01"
EXEC_FROM = "2025-10-01"
EXEC_TO = "2025-10-31"

TRADES = (REPO_ROOT / "06_RESEARCH" / "results" / "open_decisions"
          / "o2_htf_sweep_stage_funnel" / "trades.csv")
ARMED = (REPO_ROOT / "06_RESEARCH" / "results" / "open_decisions"
         / "o2_htf_sweep_stage" / "armed_sweep_join.csv")
DATA = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"

FIELDS = [
    "poi_id", "direction", "trigger", "detection_tf", "models", "tp_source",
    "entry_price", "original_sl", "working_sl", "sl_source", "exit_price",
    "close_kind", "entry_bar", "exit_bar", "hold_bars",
    "product_sl_dist", "product_sl_pips", "bench_price",
    "mae_price", "mae_pips", "mfe_price", "mfe_pips",
    "mae_vs_product", "mae_vs_30", "mfe_vs_product",
    "hit_product_sl", "mae_exceeds_30", "mae_exceeds_product_sl",
]


def _q(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _stats(values: list[float], scale: float = 1.0) -> dict:
    return {
        "n": len(values),
        "median": None if not values else _q(values, 0.5) / scale,
        "p25": None if not values else _q(values, 0.25) / scale,
        "p75": None if not values else _q(values, 0.75) / scale,
        "min": None if not values else min(values) / scale,
        "max": None if not values else max(values) / scale,
    }


def _m5_series() -> list:
    from datetime import datetime, timedelta, timezone

    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    # Mirror the composition exactly: trade bar indices are positions in the
    # EXEC-window M5 slice, so the reconstructed path series must be that same
    # slice (not the longer warm-up series used for HTF resampling).
    exec_to = (datetime.fromisoformat(EXEC_TO).replace(tzinfo=timezone.utc)
               + timedelta(days=1) - timedelta(minutes=1))
    exec_from = datetime.fromisoformat(EXEC_FROM).replace(tzinfo=timezone.utc)
    load_from = datetime.fromisoformat(LOAD_FROM).replace(tzinfo=timezone.utc)
    bars = load_ohlcv_parquet(DATA)
    bars = [c for c in bars if load_from <= c.timestamp <= exec_to + timedelta(days=1)]
    multi = resample_multi(bars, [Timeframe.M5, Timeframe.H1, Timeframe.H4,
                                  Timeframe.D1])
    return [c for c in multi[Timeframe.M5]
            if exec_from <= c.timestamp <= exec_to]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="O4 SL / MAE benchmark")
    parser.add_argument("--tag", default="o4_sl_mae")
    args = parser.parse_args(argv)
    out_dir = REPO_ROOT / "06_RESEARCH" / "results" / "open_decisions" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = TRADES.read_text(encoding="utf-8")
    trades = list(csv.DictReader(payload.splitlines()))
    tf_by_poi = {}
    for row in csv.DictReader(ARMED.read_text(encoding="utf-8").splitlines()):
        tf_by_poi[row["poi_id"]] = row["detection_tf"]

    m5 = _m5_series()

    rows = []
    for trade in trades:
        direction = trade["direction"]
        entry = float(trade["entry_price"])
        original = trade.get("original_sl") or ""
        working = trade.get("sl") or ""
        sl_source = "original_sl" if original else "working_sl"
        sl_value = float(original) if original else float(working)
        start, end = int(trade["entry_bar"]), int(trade["exit_bar"])
        path = m5[start: end + 1]
        if not path:
            continue
        lows = [float(c.low) for c in path]
        highs = [float(c.high) for c in path]
        if direction == "long":
            mae = max(0.0, entry - min(lows))
            mfe = max(0.0, max(highs) - entry)
        else:
            mae = max(0.0, max(highs) - entry)
            mfe = max(0.0, entry - min(lows))
        sl_dist = abs(entry - sl_value)
        exit_price = float(trade["exit_price"])
        close_kind = trade.get("close_kind", "")
        clean_stop = ("stop" in close_kind.lower()
                      and abs(exit_price - sl_value) <= STOP_TOLERANCE)
        rows.append({
            "poi_id": trade["poi_id"],
            "direction": direction,
            "trigger": trade.get("trigger", ""),
            "detection_tf": tf_by_poi.get(trade["poi_id"], ""),
            "models": trade.get("model_tags", ""),
            "tp_source": trade.get("tp_source", ""),
            "entry_price": entry,
            "original_sl": sl_value,
            "working_sl": float(working) if working else "",
            "sl_source": sl_source,
            "exit_price": exit_price,
            "close_kind": close_kind,
            "entry_bar": start,
            "exit_bar": end,
            "hold_bars": end - start,
            "product_sl_dist": sl_dist,
            "product_sl_pips": sl_dist / PIP_PRICE,
            "bench_price": BENCH_PRICE,
            "mae_price": mae,
            "mae_pips": mae / PIP_PRICE,
            "mfe_price": mfe,
            "mfe_pips": mfe / PIP_PRICE,
            "mae_vs_product": (mae / sl_dist) if sl_dist > 0 else None,
            "mae_vs_30": mae / BENCH_PRICE,
            "mfe_vs_product": (mfe / sl_dist) if sl_dist > 0 else None,
            "hit_product_sl": clean_stop,
            "mae_exceeds_30": mae > BENCH_PRICE,
            "mae_exceeds_product_sl": mae > sl_dist + 1e-9,
        })

    rows.sort(key=lambda r: r["entry_bar"])
    header = ",".join(FIELDS)
    lines = [header]
    for row in rows:
        cells = []
        for field in FIELDS:
            value = row.get(field, "")
            if isinstance(value, bool):
                value = "true" if value else "false"
            if isinstance(value, float):
                value = f"{value:.6f}"
            text = str(value)
            if "," in text:
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        lines.append(",".join(cells))
    out_payload = "\n".join(lines) + "\n"
    (out_dir / "trades_mae.csv").write_text(out_payload, encoding="utf-8")
    checksum = hashlib.sha256(out_payload.encode("utf-8")).hexdigest()

    sl_pips = [r["product_sl_pips"] for r in rows]
    mae_pips = [r["mae_pips"] for r in rows]
    mfe_pips = [r["mfe_pips"] for r in rows]
    winners = [r for r in rows if "take" in r["close_kind"].lower()]
    losers = [r for r in rows if "stop" in r["close_kind"].lower()]

    summary = {
        "window": {"load_from": LOAD_FROM, "exec_from": EXEC_FROM, "exec_to": EXEC_TO},
        "preregistered": {
            "pip_price": PIP_PRICE,
            "bench_pips": BENCH_PIPS,
            "bench_price": BENCH_PRICE,
            "stop_tolerance": STOP_TOLERANCE,
            "sl_source": "original_sl preferred (placement stop, not BE-modified)",
            "path": "M5, entry bar .. exit bar inclusive",
        },
        "counts": {
            "N_trades": len(rows),
            "N_winners": len(winners),
            "N_losers": len(losers),
            "N_hit_product_sl": sum(1 for r in rows if r["hit_product_sl"]),
            "N_mae_exceeds_30": sum(1 for r in rows if r["mae_exceeds_30"]),
            "N_mae_exceeds_product_sl": sum(1 for r in rows
                                            if r["mae_exceeds_product_sl"]),
            "N_sl_from_working": sum(1 for r in rows if r["sl_source"] != "original_sl"),
        },
        "product_sl": {"pips": _stats(sl_pips, 1.0),
                       "price": _stats([r["product_sl_dist"] for r in rows], 1.0)},
        "mae": {"pips": _stats(mae_pips, 1.0)},
        "mfe": {"pips": _stats(mfe_pips, 1.0)},
        "ratios": {
            "mae_vs_product": _stats([r["mae_vs_product"] for r in rows
                                      if r["mae_vs_product"] is not None], 1.0),
            "mae_vs_30": _stats([r["mae_vs_30"] for r in rows], 1.0),
            "mfe_vs_product": _stats([r["mfe_vs_product"] for r in rows
                                      if r["mfe_vs_product"] is not None], 1.0),
        },
        "shares": {
            "mae_le_30pip": sum(1 for r in rows if r["mae_pips"] <= BENCH_PIPS) / len(rows),
            "product_sl_le_30pip": sum(1 for r in rows if r["product_sl_pips"] <= BENCH_PIPS) / len(rows),
            "product_sl_gt_30pip": sum(1 for r in rows if r["product_sl_pips"] > BENCH_PIPS) / len(rows),
            "clean_stop": sum(1 for r in rows if r["hit_product_sl"]) / len(rows),
            "mae_le_30_on_winners": (sum(1 for r in winners if r["mae_pips"] <= BENCH_PIPS)
                                     / len(winners)) if winners else None,
            "mae_gt_30_on_losers": (sum(1 for r in losers if r["mae_pips"] > BENCH_PIPS)
                                    / len(losers)) if losers else None,
        },
        "by_trigger": {
            trig: {"n": sum(1 for r in rows if r["trigger"] == trig),
                   "median_sl_pips": _stats([r["product_sl_pips"] for r in rows
                                             if r["trigger"] == trig], 1.0)["median"],
                   "median_mae_pips": _stats([r["mae_pips"] for r in rows
                                              if r["trigger"] == trig], 1.0)["median"]}
            for trig in sorted({r["trigger"] for r in rows})
        },
        "by_detection_tf": {
            tf: {"n": sum(1 for r in rows if r["detection_tf"] == tf),
                 "median_sl_pips": _stats([r["product_sl_pips"] for r in rows
                                           if r["detection_tf"] == tf], 1.0)["median"]}
            for tf in sorted({r["detection_tf"] for r in rows})
        },
        "per_trade": [
            {k: r[k] for k in ("poi_id", "direction", "trigger", "detection_tf",
                               "tp_source", "product_sl_pips", "mae_pips",
                               "mfe_pips", "close_kind", "hold_bars",
                               "mae_vs_product", "hit_product_sl")}
            for r in rows
        ],
        "cs_source_trades": {"path": str(TRADES),
                             "rows_in": len(trades)},
        "reconciliation": {"exec_m5_bars": len(m5), "csv_rows": len(rows),
                           "trades_in": len(trades),
                           "dropped_missing_path": len(trades) - len(rows),
                           "winners_plus_losers": len(winners) + len(losers)},
        "checksum_trades_mae_csv": checksum,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    print(json.dumps({k: summary[k] for k in ("counts", "product_sl", "mae",
                                              "mfe", "ratios", "shares")},
                     indent=2, default=str))
    print("per trade:", json.dumps(summary["per_trade"], indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
