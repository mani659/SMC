#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POI KPI + review pack — frozen-window structure spine (measurement only).

Builds the machine ledger + stratified human-review chart pack for the
PRODUCT path (detection → merged POI → pillars → arm → route → fill), over
the frozen 2025-06-01 → 2025-11-30 UTC window.

Composition (imported, never forked): ``phase3_structure_funnel.run`` —
``MultiTFProductRuntime.run_batch`` (H4+H1 detection, D1→M8 context) at the
new-H1-close cadence → ``PipelineEngine.arm_at`` → ``PipelineAdapter`` route
seam → ``BacktestRunner`` risk/placement. Extra instrumentation is a wrapper
around ``MultiTFDetectionDriver.validate_multi`` (+ ``run_batch`` for the
decision instant) that records each merged POI's identity and pillar path;
both are restored in ``finally``. No strategy code is edited.

Optional P2a/P2b pool link is a DESCRIPTIVE JOIN ONLY (never a gate, never a
ranking); lookback = ``poi_give_up_bars()`` M5 bars (imported constant).

Bans honoured: no threshold edits, no detector/trigger/pillar formula edits,
no expectancy/PF claims, no EQH-in-pool, no live terminal.

Usage:
  python 06_RESEARCH/scripts/poi_kpi_pack.py --tag run1 \
      --out-root 06_RESEARCH/results/poi_kpi_pack/run1
  python 06_RESEARCH/scripts/poi_kpi_pack.py --finalize
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
for _p in (SRC_DIR, SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DATA_PATH = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "poi_kpi_pack"
REPORT_PATH = REPO_ROOT / "06_RESEARCH" / "POI_KPI_REPORT.md"

LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)
EXEC_FROM = datetime(2025, 6, 1, tzinfo=timezone.utc)
EXEC_TO = datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc)

CHART_CAP = 48
POOL_LINK_LOOKBACK_BARS = None   # resolved from poi_give_up_bars() at runtime


# ---------------------------------------------------------------------- #
# Pure formatting / classification helpers (unit-tested)
# ---------------------------------------------------------------------- #
_KIND_LABEL = {
    "ob": "ORDER BLOCK",
    "fvg": "FVG",
    "demand_supply": "DEMAND/SUPPLY ZONE",
    "demand": "DEMAND ZONE",
    "supply": "SUPPLY ZONE",
}
_PILLAR_NAME = {
    1: "ZONE REFINEMENT",
    2: "DISPLACEMENT",
    3: "PREMIUM/DISCOUNT",
    4: "FRESHNESS",
    5: "INDUCEMENT",
}


def kind_label(row: dict) -> str:
    """Flowchart vocabulary for a POI row (never invents a kind)."""
    m8 = str(row.get("m8_kind") or "").strip().lower()
    if m8 in _KIND_LABEL:
        return _KIND_LABEL[m8]
    tags = str(row.get("model_tags") or "")
    if "M8" in tags.split("|"):
        return "M8 MODEL ZONE"
    if tags:
        return "DETECTOR " + tags.replace("|", "+")
    return "UNLABELED"


def pillar_label(first_fail: str | None) -> str:
    """Human pillar label: PASS or 'PILLAR 2 FAIL - DISPLACEMENT'."""
    text = str(first_fail or "PASS")
    if text == "PASS":
        return "PASS"
    parts = text.split(":", 1)
    number = parts[0].lstrip("Pp")
    try:
        name = _PILLAR_NAME.get(int(number), "?")
    except ValueError:
        name = "?"
    status = parts[1] if len(parts) > 1 else ""
    return f"PILLAR {number} FAIL - {name}" + (f" ({status})" if status else "")


def funnel_rows(summary: dict) -> list[dict]:
    """Flatten a funnel summary into (stage, count) rows."""
    rows: list[dict] = []
    for tf_name, value in sorted((summary.get("detected_raw_by_tf") or {}).items()):
        rows.append({"stage": f"detected_raw_{tf_name}", "count": int(value)})
    for tf_name, value in sorted((summary.get("merged_by_tf") or {}).items()):
        rows.append({"stage": f"merged_{tf_name}", "count": int(value)})
    for tf_name, value in sorted((summary.get("passed_validation_by_tf") or {}).items()):
        rows.append({"stage": f"passed_{tf_name}", "count": int(value)})
    rows.append({"stage": "detected_raw_total",
                 "count": int(sum((summary.get("detected_raw_by_tf") or {}).values()))})
    rows.append({"stage": "merged_total", "count": int(summary.get("merged_pois") or 0)})
    rows.append({"stage": "passed_total", "count": int(summary.get("passed_validation") or 0)})
    rows.append({"stage": "armed", "count": int(summary.get("armed") or 0)})
    rows.append({"stage": "routes", "count": int(summary.get("routes") or 0)})
    rows.append({"stage": "placed", "count": int(summary.get("placed") or 0)})
    rows.append({"stage": "fills", "count": int(summary.get("fills") or 0)})
    return rows


def pillar_rows(poi_rows: list[dict]) -> list[dict]:
    """First-failure histogram from captured POI rows (PASS included)."""
    counts = Counter(str(r.get("first_fail") or "PASS") for r in poi_rows)
    total = sum(counts.values()) or 1
    return [
        {"pillar": key, "label": pillar_label(key), "count": n,
         "pct": round(100.0 * n / total, 4)}
        for key, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def best_level(side: str, zone_low: float, zone_high: float, levels):
    """Nearest same-side active pool level by distance to the POI zone.

    Returns ``(level, distance)`` or ``(None, None)``. Distance is 0 when the
    level price sits inside the zone; otherwise the gap to the nearest bound.
    """
    best = None
    best_distance = None
    for level in levels:
        if str(getattr(level.side, "value", level.side)).lower() != side.lower():
            continue
        price = float(level.price)
        if zone_low <= price <= zone_high:
            distance = 0.0
        else:
            distance = min(abs(price - zone_low), abs(price - zone_high))
        if best_distance is None or distance < best_distance:
            best, best_distance = level, distance
    return best, best_distance


def link_status(best, distance, hit_ts_list) -> str:
    """YES / NO / UNKNOWN for the descriptive pool join (never forced)."""
    if best is None:
        return "UNKNOWN"
    if hit_ts_list:
        return "YES"
    return "NO"


# ---------------------------------------------------------------------- #
# Run stage — capture the product spine via the phase3 harness
# ---------------------------------------------------------------------- #
_CAPTURE = {"as_of": None, "rows": []}


def _install_capture():
    from smc.orchestration.multi_tf import MultiTFDetectionDriver
    from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime
    from smc.backtest.pipeline_bridge import pillar_path_summary

    original_validate = MultiTFDetectionDriver.validate_multi
    original_batch = MultiTFProductRuntime.run_batch
    original_init = MultiTFProductRuntime.__init__

    def init_phase34(self, *a, **kw):
        """Pin the Phase 3/4 composition: H4+H1 detection (D1 → M8 context).

        The March-2026 (M2) runtime default widened to D1/H4/H1/M15; this pack
        measures the Phase 3/4/C1 product composition, so the detection set is
        stated explicitly here — the same set the cited harness uses, not a
        second pipeline.
        """
        from smc.config.timeframe import Timeframe
        kw.setdefault("detection_timeframes", (Timeframe.H4, Timeframe.H1))
        return original_init(self, *a, **kw)

    def capture_batch(self, **kwargs):
        previous = _CAPTURE["as_of"]
        _CAPTURE["as_of"] = kwargs.get("as_of")
        try:
            return original_batch(self, **kwargs)
        finally:
            _CAPTURE["as_of"] = previous

    def capture_validate(self, series_by_tf, engine=None, arm_bars=None,
                         return_details=False):
        result = original_validate(
            self, series_by_tf, engine=engine, arm_bars=arm_bars,
            return_details=True)
        seen = {r["poi_id"] for r in _CAPTURE["rows"]}
        as_of = _CAPTURE["as_of"]
        for tf, info in (getattr(result, "details", {}) or {}).items():
            for res in (info or {}).get("results", []):
                poi = getattr(res, "poi", None)
                if poi is None:
                    continue
                poi_id = getattr(poi, "id", None)
                if poi_id in seen:
                    continue
                seen.add(poi_id)
                zone = getattr(poi, "zone", None)
                first = getattr(res, "first_failure", None)
                first_fail = (
                    "PASS" if first is None
                    else f"P{getattr(first, 'pillar', '?')}:"
                         f"{getattr(getattr(first, 'status', None), 'value', '?')}"
                )
                tags = sorted(getattr(m, "name", str(m)) for m in (getattr(poi, "models", None) or []))
                _CAPTURE["rows"].append({
                    "poi_id": poi_id,
                    "detection_tf": getattr(tf, "name", str(tf)),
                    "direction": getattr(getattr(zone, "direction", None), "name", ""),
                    "model_tags": "|".join(tags),
                    "m8_kind": getattr(poi, "m8_kind", None) or "",
                    "zone_low": getattr(zone, "bottom", None),
                    "zone_high": getattr(zone, "top", None),
                    "pillar_path": pillar_path_summary(res) or "",
                    "first_fail": first_fail,
                    "passed": bool(getattr(res, "passed", False)),
                    "event_ts": as_of.isoformat() if as_of is not None else "",
                    "armed": False,
                    "armed_bar": "",
                    "arm_ts": "",
                    "routed": "",
                    "trigger": "",
                    "entry": "",
                    "sl": "",
                    "tp": "",
                    "filled": "",
                    "close_kind": "",
                })
        return result

    MultiTFDetectionDriver.validate_multi = capture_validate
    MultiTFProductRuntime.run_batch = capture_batch
    MultiTFProductRuntime.__init__ = init_phase34
    return original_validate, original_batch, original_init


def _restore_capture(state):
    from smc.orchestration.multi_tf import MultiTFDetectionDriver
    from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime

    (MultiTFDetectionDriver.validate_multi,
     MultiTFProductRuntime.run_batch,
     MultiTFProductRuntime.__init__) = state


def run_pack(tag: str, out_root: Path, exec_from: datetime, exec_to: datetime) -> dict:
    import phase3_structure_funnel as p3

    out_root.mkdir(parents=True, exist_ok=True)
    _CAPTURE["rows"] = []
    _CAPTURE["as_of"] = None
    state = _install_capture()
    t0 = time.perf_counter()
    try:
        summary = p3.run(SimpleNamespace(
            tag=tag,
            out_root=str(out_root),
            load_from=LOAD_FROM.date().isoformat(),
            exec_from=exec_from.date().isoformat(),
            exec_to=exec_to.date().isoformat(),
        ))
    finally:
        _restore_capture(state)

    rows = _CAPTURE["rows"]
    armed_records = {}
    armed_path = out_root / "armed_records.json"
    if armed_path.exists():
        armed_records = json.loads(armed_path.read_text(encoding="utf-8"))
    trades_by_poi = {}
    report_path = out_root / "report.json"
    if report_path.exists():
        for trade in json.loads(report_path.read_text(encoding="utf-8")).get("trades", []):
            trades_by_poi[str(trade.get("poi_id"))] = trade

    for row in rows:
        rec = armed_records.get(row["poi_id"])
        if rec is None:
            continue
        row["armed"] = True
        row["armed_bar"] = rec.get("armed_bar", "")
        row["routed"] = rec.get("routed", "")
        row["trigger"] = rec.get("trigger", "")
        row["entry"] = rec.get("entry", "")
        row["sl"] = rec.get("original_sl", "")
        row["tp"] = rec.get("tp", "")
        trade = trades_by_poi.get(row["poi_id"])
        if trade is not None:
            row["filled"] = "true"
            row["close_kind"] = str(trade.get("close_kind") or "")

    poi_path = out_root / "poi_rows.json"
    poi_path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    (out_root / "run_meta.json").write_text(json.dumps({
        "tag": tag,
        "runtime_seconds": round(time.perf_counter() - t0, 1),
        "rows": len(rows),
        "funnel_summary": summary,
    }, indent=2, default=str), encoding="utf-8")
    print(f"[poi-kpi] {tag}: rows={len(rows)} wrote {poi_path}", flush=True)
    return summary


# ---------------------------------------------------------------------- #
# Finalize — artifacts, pool link, charts, report
# ---------------------------------------------------------------------- #
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_series():
    from plan_complement_ledger import load_m1
    from smc.config.timeframe import Timeframe
    from smc.data.resample import resample_ohlcv

    m1_all = load_m1(DATA_PATH, LOAD_FROM, EXEC_TO + timedelta(days=1))
    if not m1_all:
        raise SystemExit(f"canonical dataset missing/empty: {DATA_PATH}")
    m1_exec = [c for c in m1_all if EXEC_FROM <= c.timestamp <= EXEC_TO]
    htf = {
        Timeframe.H1: resample_ohlcv(m1_all, Timeframe.H1),
        Timeframe.H4: resample_ohlcv(m1_all, Timeframe.H4),
        Timeframe.D1: resample_ohlcv(m1_all, Timeframe.D1),
    }
    m5 = resample_ohlcv(m1_exec, Timeframe.M5)
    return m1_all, m5, htf


def _build_pool(m1_all, m5_exec):
    from p2a_pool_inventory import (
        EXEC_END, PERIODIC_TF, SESSION_TF, STRUCTURAL_TF,
        periodic_pool_levels, session_pool_levels, structural_pool_levels,
    )
    from smc.data.resample import resample_ohlcv
    from smc.liquidity import LiquidityPool

    h4_all = resample_ohlcv(m1_all, PERIODIC_TF)
    h4_exec = [c for c in h4_all if EXEC_FROM - timedelta(days=1) <= c.timestamp <= EXEC_END]
    days = sorted({c.timestamp.date() for c in h4_exec})
    levels = []
    levels += periodic_pool_levels(h4_all, PERIODIC_TF, days)
    levels += session_pool_levels(
        resample_ohlcv([c for c in m1_all if EXEC_FROM <= c.timestamp <= EXEC_END], SESSION_TF))
    levels += structural_pool_levels(h4_all, STRUCTURAL_TF)
    pool = LiquidityPool()
    for level in sorted(levels, key=lambda lv: (lv.enter_at, lv.family.value, lv.side.value, lv.period_id)):
        try:
            pool.add(level)
        except ValueError:
            continue
    return pool


def _pool_link_rows(rows: list[dict], pool, m5, m1_all) -> list[dict]:
    from smc.liquidity import attribute_sweeps
    from smc.triggers.trigger_expiry import poi_give_up_bars

    lookback = poi_give_up_bars()
    m5_ts = [c.timestamp for c in m5]
    report = attribute_sweeps(pool, m5)
    hits_by_level: dict = defaultdict(list)
    for hit in report.hits:
        hits_by_level[hit.level_id].append(hit.sweep_bar_ts)

    out = []
    for row in rows:
        if not row.get("armed"):
            continue
        arm_ts = _poi_arm_ts(row, m5_ts)
        side = "ssl" if str(row.get("direction")) == "LONG" else "bsl"
        entry = {
            "poi_id": row["poi_id"],
            "detection_tf": row["detection_tf"],
            "direction": row["direction"],
            "arm_ts": arm_ts.isoformat() if arm_ts else "",
            "lookback_bars": lookback,
            "link_status": "UNKNOWN",
            "family": "",
            "side": side,
            "price": "",
            "period_id": "",
            "distance": "",
            "hit_ts": "",
        }
        if arm_ts is None:
            out.append(entry)
            continue
        active = pool.inventory(arm_ts)
        zone_low = float(row["zone_low"])
        zone_high = float(row["zone_high"])
        best, distance = best_level(side, zone_low, zone_high, active)
        if best is not None:
            index = bisect.bisect_right(m5_ts, arm_ts) - 1
            lo = max(index - lookback, 0)
            window_hits = [ts for ts in hits_by_level.get(best.level_id, ())
                           if lo <= bisect.bisect_right(m5_ts, ts) - 1 <= index]
            entry.update({
                "link_status": link_status(best, distance, window_hits),
                "family": best.family.value,
                "price": f"{best.price:.6f}",
                "period_id": best.period_id,
                "distance": f"{distance:.6f}" if distance is not None else "",
                "hit_ts": window_hits[-1].isoformat() if window_hits else "",
            })
        out.append(entry)
    return out


def _poi_arm_ts(row: dict, m5_ts):
    bar = row.get("armed_bar")
    try:
        index = int(bar)
    except (TypeError, ValueError):
        return None
    if 0 <= index < len(m5_ts):
        return m5_ts[index]
    return None


def _select_for_charts(rows: list[dict], cap: int) -> list[dict]:
    buckets: dict = defaultdict(list)
    for row in rows:
        if row.get("armed"):
            key = ("ARMED", kind_label(row))
        elif row.get("passed"):
            key = ("PASS_UNARMED", kind_label(row))
        else:
            key = (pillar_label(row.get("first_fail")), kind_label(row))
        buckets[key].append(row)
    ordered = sorted(buckets.items(), key=lambda kv: kv[0])
    picked: list[dict] = []
    depth = 0
    while len(picked) < cap:
        added = False
        for _key, bucket in ordered:
            if depth < len(bucket):
                picked.append(bucket[depth])
                added = True
                if len(picked) >= cap:
                    break
        if not added:
            break
        depth += 1
    return picked


def _render_charts(rows: list[dict], m5, htf, out_dir: Path) -> list[dict]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for number, row in enumerate(_select_for_charts(rows, CHART_CAP), start=1):
        event_ts = row.get("event_ts") or ""
        try:
            event = datetime.fromisoformat(event_ts)
        except ValueError:
            continue
        tf_name = row.get("detection_tf") or "H4"
        series = htf.get(getattr(__import__("smc.config.timeframe", fromlist=["Timeframe"]).Timeframe, tf_name))
        if not series:
            continue
        htf_ts = [c.timestamp for c in series]
        htf_cut = bisect.bisect_right(htf_ts, event)
        htf_win = series[max(htf_cut - 120, 0):htf_cut]
        m5_ts = [c.timestamp for c in m5]
        m5_cut = bisect.bisect_right(m5_ts, event)
        m5_win = m5[max(m5_cut - 120, 0):m5_cut + 40]
        if not htf_win or not m5_win:
            continue

        fig, (ax_top, ax_bottom) = plt.subplots(2, 1, figsize=(14, 8), sharex=False)
        for ax, win, label in ((ax_top, htf_win, tf_name), (ax_bottom, m5_win, "M5")):
            for i, candle in enumerate(win):
                color = "#2e7d32" if candle.close >= candle.open else "#c62828"
                ax.plot([i, i], [candle.low, candle.high], color=color, lw=0.7)
                ax.add_patch(plt.Rectangle(
                    (i - 0.3, min(candle.open, candle.close)), 0.6,
                    abs(candle.close - candle.open) + 1e-9, facecolor=color, edgecolor=color))
            ax.axhspan(float(row["zone_low"]), float(row["zone_high"]),
                       color="#1e88e5", alpha=0.18)
            step = max(len(win) // 8, 1)
            ax.set_xticks(range(0, len(win), step))
            ax.set_xticklabels([win[i].timestamp.strftime("%m-%d %H:%M")
                                for i in range(0, len(win), step)], fontsize=7)
            ax.set_ylabel(label)
            ax.grid(alpha=0.25)

        if row.get("armed"):
            try:
                arm_ts = m5[int(row["armed_bar"])].timestamp
                idx = bisect.bisect_left([c.timestamp for c in m5_win], arm_ts)
                if idx < len(m5_win):
                    ax_bottom.axvline(idx, color="#f9a825", lw=1.5, label="arm")
            except (KeyError, IndexError, ValueError):
                pass
        title = (
            f"{row['poi_id']} [{row['detection_tf']}] {kind_label(row)} | "
            f"{pillar_label(row.get('first_fail'))} | "
            f"{'ARMED' if row.get('armed') else 'NOT ARMED'} | "
            f"{event:%Y-%m-%d %H:%M} UTC"
        )
        ax_top.set_title(title + "  (identification panel - not a trade claim)", fontsize=10)
        if ax_bottom.get_legend_handles_labels()[0]:
            ax_bottom.legend(loc="best", fontsize=8)
        fig.tight_layout()
        name = f"{number:02d}_{str(row['poi_id']).replace('|', '_')}_{row['detection_tf']}.png"
        fig.savefig(out_dir / name, dpi=110)
        plt.close(fig)
        index.append({
            "chart": name,
            "poi_id": row["poi_id"],
            "detection_tf": row["detection_tf"],
            "kind": kind_label(row),
            "pillar": pillar_label(row.get("first_fail")),
            "armed": bool(row.get("armed")),
            "routed": row.get("routed") == "true",
            "event_ts": event_ts,
        })
    return index


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def finalize(exec_from: datetime, exec_to: datetime) -> dict:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    run1 = OUT_ROOT / "run1"
    run2 = OUT_ROOT / "run2"
    if not (run1 / "poi_rows.json").exists():
        raise SystemExit("missing run1 artifacts; run --tag run1 first")

    summary = json.loads((run1 / "run_meta.json").read_text(encoding="utf-8"))["funnel_summary"]
    rows = json.loads((run1 / "poi_rows.json").read_text(encoding="utf-8"))

    m1_all, m5, htf = _load_series()
    m5_ts = [c.timestamp for c in m5]
    for row in rows:
        arm_ts = _poi_arm_ts(row, m5_ts)
        row["arm_ts"] = arm_ts.isoformat() if arm_ts else ""

    funnel = funnel_rows(summary)
    _write_csv(OUT_ROOT / "funnel.csv", funnel, ["stage", "count"])

    poi_fields = ["poi_id", "detection_tf", "direction", "model_tags", "m8_kind",
                  "zone_low", "zone_high", "pillar_path", "first_fail", "passed",
                  "event_ts", "armed", "arm_ts", "routed", "trigger", "entry",
                  "sl", "tp", "filled", "close_kind"]
    _write_csv(OUT_ROOT / "poi_emissions.csv", rows, poi_fields)

    pillars = pillar_rows(rows)
    _write_csv(OUT_ROOT / "pillar_first_fail.csv", pillars, ["pillar", "label", "count", "pct"])

    armed_rows = [r for r in rows if r.get("armed")]
    _write_csv(OUT_ROOT / "armed_routes_fills.csv", armed_rows,
               ["poi_id", "detection_tf", "model_tags", "pillar_path", "zone_low",
                "zone_high", "arm_ts", "routed", "trigger", "entry", "sl", "tp",
                "filled", "close_kind"])

    pool = _build_pool(m1_all, m5)
    links = _pool_link_rows(rows, pool, m5, m1_all)
    _write_csv(OUT_ROOT / "pool_link.csv", links,
               ["poi_id", "detection_tf", "direction", "arm_ts", "lookback_bars",
                "link_status", "family", "side", "price", "period_id", "distance",
                "hit_ts"])

    chart_index = _render_charts(rows, m5, htf, OUT_ROOT / "charts")
    _write_csv(OUT_ROOT / "charts" / "index.csv", chart_index,
               ["chart", "poi_id", "detection_tf", "kind", "pillar", "armed",
                "routed", "event_ts"])

    determinism = {"run2_present": (run2 / "poi_rows.json").exists()}
    if determinism["run2_present"]:
        s2 = json.loads((run2 / "run_meta.json").read_text(encoding="utf-8"))["funnel_summary"]
        strip = lambda d: {k: v for k, v in d.items()  # noqa: E731
                           if k not in ("runtime_seconds", "tag")}
        a, b = strip(summary), strip(s2)
        determinism.update({
            "summary_semantic_equal": a == b,
            "funnel_rows_equal": funnel_rows(a) == funnel_rows(b),
            "poi_rows_equal": json.loads((run1 / "poi_rows.json").read_text()) ==
                              json.loads((run2 / "poi_rows.json").read_text()),
            "excluded_fields": ["runtime_seconds", "tag"],
            "funnel_summary_sha_run1": _sha(run1 / "funnel_summary.json"),
            "funnel_summary_sha_run2": _sha(run2 / "funnel_summary.json"),
        })

    link_rates = Counter(r["link_status"] for r in links)
    final = {
        "window": summary.get("window"),
        "exec_range": {"start": exec_from.isoformat(), "end": exec_to.isoformat()},
        "pipeline": [
            "smc.orchestration.multi_tf_runtime.MultiTFProductRuntime.run_batch",
            "smc.orchestration.multi_tf.MultiTFDetectionDriver.validate_multi",
            "smc.orchestration.engine.PipelineEngine",
            "smc.backtest.pipeline_adapter.PipelineAdapter",
            "smc.backtest.runner.BacktestRunner",
        ],
        "funnel": {
            "raw": sum((summary.get("detected_raw_by_tf") or {}).values()),
            "merged": summary.get("merged_pois"),
            "pass": summary.get("passed_validation"),
            "armed": summary.get("armed"),
            "routes": summary.get("routes"),
            "fills": summary.get("fills"),
        },
        "funnel_by_tf": {
            "detected_raw": summary.get("detected_raw_by_tf"),
            "merged": summary.get("merged_by_tf"),
            "passed": summary.get("passed_validation_by_tf"),
        },
        "armed_by_tf": summary.get("armed_by_tf"),
        "routes_by_trigger": summary.get("routes_by_trigger"),
        "pillar_top_fail": pillars[0] if pillars else None,
        "pillars": pillars,
        "pool_link_rates": dict(link_rates),
        "charts_n": len(chart_index),
        "determinism": determinism,
        "runtime_seconds": summary.get("runtime_seconds"),
        "notes": summary.get("notes"),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")

    _write_report(final, rows, pots=pillars)
    print(json.dumps(final["funnel"], indent=2), flush=True)
    print(f"[poi-kpi] charts={len(chart_index)} report={REPORT_PATH}", flush=True)
    return final


def _write_report(final: dict, rows: list[dict], pots: list[dict]) -> None:
    funnel = final["funnel"]
    lines = [
        "# POI KPI REPORT — FROZEN-WINDOW STRUCTURE SPINE",
        "",
        "Status: **MEASUREMENT** (not performance, not go-live, no expectancy claim).",
        f"Window: **{final['exec_range']['start']} → {final['exec_range']['end']}** UTC "
        f"(exec M5; warm-up load 2025-05-01, matching the P2a/P2b/structure-ledger convention).",
        "",
        "## 1. Scope / pipeline",
        "",
        "Product spine, imported (never forked):",
        "",
    ]
    for module in final["pipeline"]:
        lines.append(f"- `{module}`")
    lines += [
        "",
        "Composition: new-H1-close batches → H4+H1 detection (D1→M8 context) → "
        "merged POI → 5 hard pillars → arm → scan/route → risk/placement → fills.",
        "Extra instrumentation: a wrapper around `MultiTFDetectionDriver.validate_multi` "
        "records each merged POI's identity + pillar path; restored in `finally`.",
        "",
        "Bans honoured: no threshold edits, no detector/trigger/pillar formula edits, "
        "no EQH-in-pool, no live terminal, no expectancy/PF language.",
        "",
        "## 2. Funnel",
        "",
        "| stage | count |",
        "| --- | ---: |",
    ]
    for row in funnel_rows({"detected_raw_by_tf": final["funnel_by_tf"]["detected_raw"],
                            "merged_by_tf": final["funnel_by_tf"]["merged"],
                            "passed_validation_by_tf": final["funnel_by_tf"]["passed"],
                            "merged_pois": funnel["merged"],
                            "passed_validation": funnel["pass"],
                            "armed": funnel["armed"], "routes": funnel["routes"],
                            "fills": funnel["fills"]}):
        lines.append(f"| {row['stage']} | {row['count']} |")
    lines += [
        "",
        f"Armed by TF: `{json.dumps(final['armed_by_tf'])}` · "
        f"routes by trigger: `{json.dumps(final['routes_by_trigger'])}`.",
        "",
        "## 3. Pillar first-fail breakdown (measurement, not a fix list)",
        "",
        "| pillar | label | count | pct |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in pots:
        lines.append(f"| {row['pillar']} | {row['label']} | {row['count']} | {row['pct']}% |")
    lines += [
        "",
        "## 4. Arm / route / fill chain",
        "",
        f"- merged POIs: {funnel['merged']} · passed: {funnel['pass']} · armed: {funnel['armed']}",
        f"- routes: {funnel['routes']} · placed: see `funnel.csv` · fills: {funnel['fills']}",
        "- Per-POI chain: `armed_routes_fills.csv` (routed/trigger/entry/SL/TP/filled/close_kind).",
    ]
    if funnel["fills"] == 0:
        lines.append("- **0 fills on this window** — reported honestly; not a success or failure claim.")
    lines += [
        "",
        "## 5. Pool link (descriptive join only — not a gate)",
        "",
        f"Rates: `{json.dumps(final['pool_link_rates'])}` (YES / NO / UNKNOWN).",
        "Lookback = `poi_give_up_bars()` M5 bars before the arm bar; nearest same-side "
        "active P2a level by distance to the POI zone; hit from P2b attribution. "
        "UNKNOWN means no same-side active level at the arm instant — never forced.",
        "",
        "## 6. Chart index + stratification",
        "",
        f"{final['charts_n']} charts under `06_RESEARCH/results/poi_kpi_pack/charts/` "
        "(index: `charts/index.csv`). Each figure has the HTF series panel plus the M5 "
        "window around the event, the POI zone rectangle and the arm marker.",
        "Stratification: armed POIs first, then PASS-unarmed, then first-fail rows, "
        "round-robin across (pillar, kind) buckets so F-routes do not dominate.",
        "Labels use flowchart vocabulary (ORDER BLOCK / DEMAND-SUPPLY ZONE / FVG / "
        "PILLAR n FAIL).",
        "",
        "### Scoring rubric (human / Architect)",
        "",
        "CORRECT | PARTIAL | WRONG | UNCLEAR — geometric zone, label kind, directional "
        "sense vs flowchart. The pack never auto-scores as expert truth.",
        "",
        "## 7. Determinism",
        "",
        f"`{json.dumps(final['determinism'])}`",
        "",
        "Dual run of the same composition (run1/run2); only `runtime_seconds` and the "
        "run `tag` are excluded from the comparison. `funnel_rows_equal` compares the "
        "funnel rows derived from each run, `poi_rows_equal` compares every captured "
        "POI row (identity, zone, pillar path, arm/route/fill chain).",
        "",
        "## 8. Residuals",
        "",
        "- `entry_anchor` is not exported by this composition (honest `n/a`).",
        "- Pool link covers armed POIs only; UNKNOWN rates are reported, not resolved.",
        "- Charts are identification panels; no trade is implied by an armed POI.",
        "- `06_RESEARCH/results/` is gitignored by repo policy (same as prior packs); "
        "the artifacts live locally under `06_RESEARCH/results/poi_kpi_pack/`.",
        "",
        "## 9. Explicit",
        "",
        "**Not performance. Not go-live. No expectancy, PF or win-rate claim.** "
        "No threshold was tuned in response to these numbers.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=None)
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--exec-from", default=None)
    ap.add_argument("--exec-to", default=None)
    ap.add_argument("--finalize", action="store_true")
    args = ap.parse_args()

    exec_from = (datetime.strptime(args.exec_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                 if args.exec_from else EXEC_FROM)
    exec_to = (datetime.strptime(args.exec_to, "%Y-%m-%d").replace(tzinfo=timezone.utc)
               if args.exec_to else EXEC_TO)

    if args.finalize:
        finalize(exec_from, exec_to)
        return 0
    if not args.tag or not args.out_root:
        ap.error("--tag and --out-root are required unless --finalize")
    run_pack(args.tag, Path(args.out_root), exec_from, exec_to)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
