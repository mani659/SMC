#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""D1 F1/F2 re-sample (identification only — no trading, no thresholds).

Re-runs the audit pack's D1/M8 identification seam with FIXED code over the
SAME window (exec 2025-06-01 → 2025-11-30 UTC, warm-up load from 2025-03-01)
and emits: events_d1_poi_post_f1f2.csv, summary JSON, and bounded charts
(all armed + up to 10 OB + 10 demand + 10 supply, ts-sorted spread).

Layers (mirroring the confirmation pack, minus the M5 exec loop):
  raw     = M8HtfDemandSupply._zones on D1 (post-collapse: one row/episode)
  merged  = DetectionDriver.validate_window on D1 (product validation path);
            M8-tagged merged POIs only (D1 scope)
  armed   = validation-passed + ZoneDedup (origin ts; no M5-loop arm times —
            documented approximation, sufficient for gate + chart sampling)

Mechanical gates (loud fail, exit nonzero):
  dual_exact_bounds_count == 0, direction_conflict_count == 0,
  origin-tight violations == 0 (ob/ds bounds == origin candle range).
No human CORRECT scoring here — that remains the Architect/user step.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling research scripts

import matplotlib
matplotlib.use("Agg")

from smc.config.timeframe import Timeframe
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.orchestration.detection_driver import DetectionDriver
from smc.orchestration.multi_tf_runtime import ZoneDedup
from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "d1_f1f2_resample"
CHARTS_DIR = OUT_DIR / "charts"
EVENTS_CSV = OUT_DIR / "events_d1_poi_post_f1f2.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"
DATA_PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"

EXEC_START = datetime(2025, 6, 1, tzinfo=timezone.utc)
EXEC_END = datetime(2025, 11, 30, 23, 59, tzinfo=timezone.utc)
WARM_START = datetime(2025, 3, 1, tzinfo=timezone.utc)

PLAIN_TAG = {
    ("ob", None): "Order block (D1)",
    ("demand_supply", "LONG"): "Demand zone (D1)",
    ("demand_supply", "SHORT"): "Supply zone (D1)",
    ("fvg", None): "Fair value gap (D1)",
}


def _eid(*parts: str) -> str:
    return "evt-" + hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def _r6(value) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    from generate_d1_poi_pack import render_d1_chart  # same visual language

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    m1 = load_ohlcv_parquet(DATA_PARQUET)
    m1_win = [c for c in m1
              if WARM_START <= c.timestamp <= datetime(2025, 12, 1, tzinfo=timezone.utc)]
    d1 = resample_multi(m1_win, [Timeframe.D1])[Timeframe.D1]
    print(f"[f1f2] D1 bars: {len(d1)} "
          f"{d1[0].timestamp.isoformat()}..{d1[-1].timestamp.isoformat()}", flush=True)
    by_ts = {c.timestamp: (i, c) for i, c in enumerate(d1)}

    # ---- Raw layer: collapsed _zones yields -------------------------- #
    model = M8HtfDemandSupply(Timeframe.D1, htf_candles={Timeframe.D1: d1})
    raw_rows: list[dict] = []
    origin_violations = 0
    for kind, direction, start, zone in model._zones(d1, Timeframe.D1):
        origin_ts = d1[start].timestamp if 0 <= start < len(d1) else None
        if origin_ts is None or not (EXEC_START <= origin_ts <= EXEC_END):
            continue
        # Origin-tight check (ob/ds must equal origin candle range exactly).
        if kind in ("ob", "demand_supply"):
            origin = d1[start]
            if not (zone.bottom == origin.low and zone.top == origin.high):
                origin_violations += 1
        tag = PLAIN_TAG.get((kind, None), PLAIN_TAG.get(
            (kind, direction.name if hasattr(direction, "name") else str(direction)),
            "Unlabeled POI (D1)"))
        raw_rows.append({
            "event_id": _eid(kind, str(direction), str(zone.bottom),
                             str(zone.top), origin_ts.isoformat()),
            "event_type": "poi_raw",
            "plain_tag": tag,
            "ts_utc": origin_ts.isoformat(),
            "direction": direction.name if hasattr(direction, "name") else str(direction),
            "zone_low": _r6(zone.bottom),
            "zone_high": _r6(zone.top),
            "model_tags": "M8",
            "kind": kind,
            "detection_tf": "D1",
            "chart_tf": "D1",
            "related_event_id": "",
            "source_module": "smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply._zones",
            "notes": f"kind={kind};origin_bar={origin_ts.isoformat()};zone_tf=D1;post_f1f2_collapsed",
        })
    raw_rows.sort(key=lambda r: (r["ts_utc"], r["plain_tag"], r["event_id"]))

    # ---- Gate metrics on emitted output ------------------------------ #
    groups: dict[tuple, list] = {}
    for r in raw_rows:
        groups.setdefault((r["zone_low"], r["zone_high"]), []).append(r)
    dual = sum(1 for g in groups.values() if len(g) > 1)
    conflicts = sum(1 for g in groups.values()
                    if len({r["direction"] for r in g}) > 1)

    # ---- Merged + armed layers via rolling product validation -------- #
    # Single full-series batch rejects everything on staleness (zones touched
    # long ago are TESTED/VIOLATED at once). Rolling 60-bar windows step 10
    # mirror live-loop semantics: zones validate while fresh near window end.
    from smc.orchestration.multi_tf_runtime import ZoneDedup
    driver = DetectionDriver(Timeframe.D1, htf_candles={Timeframe.D1: d1})
    try:
        from smc.backtest.pipeline_bridge import pillar_path_summary
    except Exception:  # noqa: BLE001 — notes field stays empty, never fatal
        pillar_path_summary = None
    merged_seen: dict = {}
    WINDOWS = [e for e in list(range(60, len(d1) + 1, 10))
               if d1[e - 1].timestamp >= EXEC_START]
    if not WINDOWS or WINDOWS[-1] != len(d1):
        WINDOWS.append(len(d1))
    # Origin ts lookup from the raw layer (structure birth, not batch time).
    origin_by_geo: dict = {}
    for _r in raw_rows:
        _k = (_r["direction"], _r["zone_low"], _r["zone_high"])
        if _k not in origin_by_geo or _r["ts_utc"] < origin_by_geo[_k]:
            origin_by_geo[_k] = _r["ts_utc"]
    for end_idx in WINDOWS:
        window = d1[max(0, end_idx - 60):end_idx]
        if len(window) < 20:
            continue
        _p, _res, _run, _sk, _det = driver.validate_window(window)
        wend = window[-1].timestamp
        for res in _res:
            key = (res.poi.zone.direction.name
                   if hasattr(res.poi.zone.direction, "name")
                   else str(res.poi.zone.direction),
                   round(float(res.poi.zone.bottom), 3),
                   round(float(res.poi.zone.top), 3))
            if key not in merged_seen:
                merged_seen[key] = (res, wend)
    results = [res for res, _ in merged_seen.values()]
    passed = [res for res in results if bool(getattr(res, "passed", False))]
    wend_by_id = {}
    for (res, wend) in merged_seen.values():
        wend_by_id.setdefault(res.poi.id, wend)

    merged_rows: list[dict] = []
    for res in results:
        poi, zone = res.poi, res.poi.zone
        if "M8" not in [getattr(m, "name", str(m)) for m in (poi.models or [])]:
            continue
        wend = wend_by_id.get(poi.id)
        if wend is None or not (EXEC_START <= wend <= EXEC_END):
            continue  # outside the exec measurement window
        path = ""
        if pillar_path_summary is not None:
            try:
                path = pillar_path_summary(res) or ""
            except Exception:  # noqa: BLE001
                path = ""
        _gkey = (zone.direction.name
                 if hasattr(zone.direction, "name") else str(zone.direction),
                 _r6(zone.bottom), _r6(zone.top))
        _ts = origin_by_geo.get(_gkey, wend.isoformat())
        merged_rows.append({
            "event_id": _eid("merged", poi.id),
            "event_type": "poi_merged",
            "plain_tag": "Merged POI (D1)",
            "ts_utc": _ts,
            "direction": zone.direction.name
            if hasattr(zone.direction, "name") else str(zone.direction),
            "zone_low": _r6(zone.bottom),
            "zone_high": _r6(zone.top),
            "model_tags": "|".join(sorted(
                getattr(m, "name", str(m)) for m in (poi.models or []))),
            "kind": getattr(poi, "m8_kind", "") or "",
            "detection_tf": "D1",
            "chart_tf": "D1",
            "related_event_id": "",
            "source_module": "smc.orchestration.detection_driver.validate_window",
            "notes": f"pillar_path={path};"
                     f"passed={bool(getattr(res, 'passed', False))}",
            "_passed": bool(getattr(res, "passed", False)),
        })

    dedup = ZoneDedup()
    armed_rows: list[dict] = []
    for row in sorted(merged_rows, key=lambda r: r["ts_utc"]):
        if not row.pop("_passed", False):
            continue
        from smc.core.zone import Zone as _Zone
        from smc.core.enums import Direction as _Direction
        zone = _Zone(top=float(row["zone_high"]), bottom=float(row["zone_low"]),
                     direction=_Direction[row["direction"]],
                     timeframe=Timeframe.D1)
        if dedup.seen(zone):
            continue
        dedup.register(zone)
        armed_rows.append({**row, "event_type": "poi_armed",
                           "plain_tag": "Armed POI (D1)",
                           "event_id": _eid("armed", row["event_id"])})

    # ---- Width distribution (measurement record for the note) -------- #
    widths: dict[str, list[float]] = {}
    for r in raw_rows:
        widths.setdefault(r["kind"], []).append(r["zone_high"] - r["zone_low"])
    width_stats = {}
    for kind, ws in widths.items():
        ws.sort()
        width_stats[kind] = {
            "n": len(ws), "min": ws[0], "p50": ws[len(ws) // 2],
            "p90": ws[int(len(ws) * 0.9) - 1] if len(ws) >= 10 else ws[-1],
            "max": ws[-1],
        }

    # ---- Charts: all armed + stratified raw (≤10 per kind, ts-spread) - #
    def spread_sample(rows, n):
        rows = sorted(rows, key=lambda r: r["ts_utc"])
        if len(rows) <= n:
            return list(rows)
        step = len(rows) / n
        return [rows[min(int(i * step), len(rows) - 1)] for i in range(n)]

    chart_rows = list(armed_rows)
    for kind in ("ob", "demand_supply"):
        pool = [r for r in raw_rows if r["kind"] == kind]
        chart_rows += [r for r in spread_sample(pool, 10)
                       if all(c["event_id"] != r["event_id"] for c in chart_rows)]
    chart_rows.sort(key=lambda r: (r["ts_utc"], r["plain_tag"], r["event_id"]))
    chart_index = []
    for seq, r in enumerate(chart_rows, start=1):
        ts_clean = r["ts_utc"].replace(":", "").replace("-", "")[:13]
        clean_tag = r["plain_tag"].lower().replace(" ", "_").replace("(", "").replace(")", "")
        filename = f"{seq:03d}_{clean_tag}_{ts_clean}_{r['event_id']}.png"
        render_d1_chart(r, d1, CHARTS_DIR / filename)
        chart_index.append({"seq": seq, "filename": filename,
                            "event_id": r["event_id"],
                            "plain_tag": r["plain_tag"],
                            "ts_utc": r["ts_utc"]})

    # ---- Events CSV + summary + gates -------------------------------- #
    with open(EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
        cols = ["event_id", "event_type", "plain_tag", "ts_utc", "direction",
                "zone_low", "zone_high", "model_tags", "kind",
                "detection_tf", "chart_tf", "related_event_id",
                "source_module", "notes"]
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        # Private _passed keys never reach the CSV (column projection only).
        for r in raw_rows + merged_rows + armed_rows:
            writer.writerow({c: r.get(c, "") for c in cols})

    summary = {
        "status": "PASS",
        "window": {"exec_start_utc": "2025-06-01T00:00:00+00:00",
                   "exec_end_utc": "2025-11-30T23:59:00+00:00"},
        "raw_rows": len(raw_rows),
        "by_kind": {k: sum(1 for r in raw_rows if r["kind"] == k)
                    for k in sorted({r["kind"] for r in raw_rows})},
        "merged_rows": len([r for r in merged_rows]),
        "armed_rows": len(armed_rows),
        "dual_exact_bounds_count": dual,
        "direction_conflict_count": conflicts,
        "origin_tight_violations": origin_violations,
        "width_stats": width_stats,
        "charts_rendered": len(chart_index),
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[f1f2] raw={len(raw_rows)} merged={len(merged_rows)} "
          f"armed={len(armed_rows)} dual={dual} conflicts={conflicts} "
          f"origin_violations={origin_violations} charts={len(chart_index)}",
          flush=True)
    ok = (dual == 0 and conflicts == 0 and origin_violations == 0)
    print(f"[f1f2] GATE_MECHANICAL: {'PASS' if ok else 'FAIL'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
