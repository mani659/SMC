"""O5 — TP: structural swing vs 4xATR fallback (read-only measurement).

Question (``OPEN_DECISIONS_RESEARCH_AGENDA.md`` §O5): how often is a structural
TP available, and do structural-TP fills show different path quality than the
ATR-fallback ones?

READ-ONLY. No ``resolve_take_profit``, feed or constant change; no 1:5 product
RR is proposed. ``tp_source`` is read from the product's own export — never
inferred.

--------------------------------------------------------------------------
PRE-REGISTERED (frozen before any result was inspected)
--------------------------------------------------------------------------
WINDOW
  product path, exec 2025-10-01 → 2025-10-31 UTC (the O1–O4 run). A 6-month
  slice is NOT mixed in: it would change the window after the fact.

TP_SOURCE LABELS (exactly as exported by ``trades.csv``)
  ``structural_swing`` | ``atr_fallback`` | ``none`` | ``unknown``
  A trade whose export carries an unknown label is reported as ``unknown``;
  nothing is inferred from prices.

PATH METRICS (per fill, M5 entry bar → exit bar inclusive; the O4 convention)
  mfe_price = best favourable excursion from entry
  mae_price = worst adverse excursion from entry
  tp_dist   = |tp − entry|
  r_dist    = |entry − original_sl|        (risk unit, for the R-multiple view)
  mfe_vs_tp = mfe_price / tp_dist;  mfe_vs_R = mfe_price / r_dist
  hit_tp    = ``take_profit`` close OR |exit − tp| <= 0.05 (fixed tolerance)

PLACEMENT LEVEL
  ``sample_audit.csv`` carries the routed/placed geometry but NOT the tp_source
  column, so the placement-level mix is taken from the trades export (11
  placements → 11 fills). The funnel's ``candidates`` counter (12) is reported
  beside it as a reconciliation note, never as an inferred source.
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
HIT_TOLERANCE = 0.05
LOAD_FROM = "2025-05-01"
EXEC_FROM = "2025-10-01"
EXEC_TO = "2025-10-31"
RUN = REPO_ROOT / "06_RESEARCH" / "results" / "open_decisions" / "o2_htf_sweep_stage_funnel"
TRADES = RUN / "trades.csv"
AUDIT = RUN / "sample_audit.csv"
FUNNEL = RUN / "funnel_summary.json"
DATA = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
SOURCES = ("structural_swing", "atr_fallback", "none", "unknown")

FIELDS = [
    "poi_id", "direction", "trigger", "detection_tf", "tp_source",
    "entry_price", "tp_price", "original_sl", "exit_price", "close_kind",
    "entry_bar", "exit_bar", "hold_bars",
    "tp_dist", "r_dist", "rr_tp_over_r", "mfe_price", "mae_price",
    "mfe_vs_tp", "mfe_vs_R", "hit_tp",
]


def _q(values, q):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _stats(values):
    return {"n": len(values),
            "median": _q(values, 0.5) if values else None,
            "p25": _q(values, 0.25) if values else None,
            "p75": _q(values, 0.75) if values else None}


def _m5_series():
    from datetime import datetime, timedelta, timezone

    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    exec_from = datetime.fromisoformat(EXEC_FROM).replace(tzinfo=timezone.utc)
    exec_to = (datetime.fromisoformat(EXEC_TO).replace(tzinfo=timezone.utc)
               + timedelta(days=1) - timedelta(minutes=1))
    load_from = datetime.fromisoformat(LOAD_FROM).replace(tzinfo=timezone.utc)
    bars = load_ohlcv_parquet(DATA)
    bars = [c for c in bars if load_from <= c.timestamp <= exec_to + timedelta(days=1)]
    multi = resample_multi(bars, [Timeframe.M5, Timeframe.H1, Timeframe.H4,
                                  Timeframe.D1])
    return [c for c in multi[Timeframe.M5] if exec_from <= c.timestamp <= exec_to]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="O5 TP source measurement")
    parser.add_argument("--tag", default="o5_tp_source")
    args = parser.parse_args(argv)
    out_dir = REPO_ROOT / "06_RESEARCH" / "results" / "open_decisions" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    trades = list(csv.DictReader(TRADES.read_text(encoding="utf-8").splitlines()))
    audit = list(csv.DictReader(AUDIT.read_text(encoding="utf-8").splitlines()))
    routed_audit = [r for r in audit if (r.get("tp") or "").strip()]
    funnel = json.loads(FUNNEL.read_text(encoding="utf-8"))
    tf_by_poi = {r["poi_id"]: r.get("detection_tf", "") for r in audit}

    m5 = _m5_series()

    rows = []
    for trade in trades:
        label = (trade.get("tp_source") or "").strip() or "none"
        if label not in SOURCES:
            label = "unknown"
        entry = float(trade["entry_price"])
        direction = trade["direction"]
        tp_raw = (trade.get("tp") or "").strip()
        tp = float(tp_raw) if tp_raw else None
        sl_raw = (trade.get("original_sl") or "").strip()
        sl = float(sl_raw) if sl_raw else None
        start, end = int(trade["entry_bar"]), int(trade["exit_bar"])
        path = m5[start: end + 1]
        lows = [float(c.low) for c in path]
        highs = [float(c.high) for c in path]
        if direction == "long":
            mfe = max(0.0, max(highs) - entry) if path else None
            mae = max(0.0, entry - min(lows)) if path else None
        else:
            mfe = max(0.0, entry - min(lows)) if path else None
            mae = max(0.0, max(highs) - entry) if path else None
        exit_price = float(trade["exit_price"])
        close_kind = trade.get("close_kind", "")
        tp_dist = abs(tp - entry) if tp is not None else None
        r_dist = abs(entry - sl) if sl is not None else None
        hit_tp = (("take" in close_kind.lower())
                  or (tp is not None and abs(exit_price - tp) <= HIT_TOLERANCE))
        rows.append({
            "poi_id": trade["poi_id"],
            "direction": direction,
            "trigger": trade.get("trigger", ""),
            "detection_tf": tf_by_poi.get(trade["poi_id"], ""),
            "tp_source": label,
            "entry_price": entry,
            "tp_price": tp if tp is not None else "",
            "original_sl": sl if sl is not None else "",
            "exit_price": exit_price,
            "close_kind": close_kind,
            "entry_bar": start,
            "exit_bar": end,
            "hold_bars": end - start,
            "tp_dist": tp_dist if tp_dist is not None else "",
            "r_dist": r_dist if r_dist is not None else "",
            "rr_tp_over_r": (tp_dist / r_dist) if (tp_dist and r_dist) else "",
            "mfe_price": mfe if mfe is not None else "",
            "mae_price": mae if mae is not None else "",
            "mfe_vs_tp": (mfe / tp_dist) if (tp_dist and mfe is not None) else "",
            "mfe_vs_R": (mfe / r_dist) if (r_dist and mfe is not None) else "",
            "hit_tp": hit_tp,
        })

    rows.sort(key=lambda r: r["entry_bar"])
    lines = [",".join(FIELDS)]
    for row in rows:
        cells = []
        for field in FIELDS:
            value = row.get(field, "")
            if isinstance(value, bool):
                value = "true" if value else "false"
            if isinstance(value, float):
                value = f"{value:.6f}"
            cells.append(str(value))
        lines.append(",".join(cells))
    payload = "\n".join(lines) + "\n"
    (out_dir / "trades_by_tp_source.csv").write_text(payload, encoding="utf-8")
    checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _vals(source, field):
        return [float(r[field]) for r in rows
                if r["tp_source"] == source and r[field] != ""]

    by_source = {}
    for source in SOURCES:
        subset = [r for r in rows if r["tp_source"] == source]
        if not subset:
            continue
        by_source[source] = {
            "n": len(subset),
            "hit_tp": sum(1 for r in subset if r["hit_tp"]),
            "hit_tp_share": sum(1 for r in subset if r["hit_tp"]) / len(subset),
            "tp_dist": _stats(_vals(source, "tp_dist")),
            "rr_tp_over_r": _stats(_vals(source, "rr_tp_over_r")),
            "mfe_vs_tp": _stats(_vals(source, "mfe_vs_tp")),
            "mfe_vs_R": _stats(_vals(source, "mfe_vs_R")),
            "hold_bars": _stats([float(r["hold_bars"]) for r in subset]),
            "pois": [r["poi_id"] for r in subset],
        }

    mix = {source: sum(1 for r in rows if r["tp_source"] == source)
           for source in SOURCES}
    summary = {
        "window": {"load_from": LOAD_FROM, "exec_from": EXEC_FROM, "exec_to": EXEC_TO},
        "preregistered": {
            "tp_source_labels": list(SOURCES),
            "hit_tolerance": HIT_TOLERANCE,
            "path": "M5, entry bar .. exit bar inclusive",
            "placement_mix_source": "trades.csv (sample_audit.csv has no tp_source column)",
        },
        "counts": {
            "N_trades": len(rows),
            "N_hit_tp": sum(1 for r in rows if r["hit_tp"]),
            "tp_source_mix": mix,
            "N_placements_audit_rows": len(routed_audit),
            "funnel_candidates": funnel.get("candidates"),
            "funnel_placed": funnel.get("placed"),
            "funnel_fills": funnel.get("fills"),
        },
        "by_source": by_source,
        "overall": {
            "tp_dist": _stats([r["tp_dist"] for r in rows if r["tp_dist"] != ""]),
            "rr_tp_over_r": _stats([r["rr_tp_over_r"] for r in rows
                                    if r["rr_tp_over_r"] != ""]),
            "mfe_vs_tp": _stats([r["mfe_vs_tp"] for r in rows if r["mfe_vs_tp"] != ""]),
            "hold_bars": _stats([float(r["hold_bars"]) for r in rows]),
        },
        "reconciliation": {
            "csv_rows": len(rows),
            "trades_in": len(trades),
            "mix_sum": sum(mix.values()),
            "audit_routed_rows": len(routed_audit),
        },
        "checksum_csv": checksum,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    print(json.dumps({"counts": summary["counts"], "by_source": by_source,
                      "overall": summary["overall"],
                      "reconciliation": summary["reconciliation"]},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
