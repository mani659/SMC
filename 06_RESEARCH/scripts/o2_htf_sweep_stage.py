"""O2 — HTF sweep as a hard stage vs upstream-only (read-only measurement).

Question (``OPEN_DECISIONS_RESEARCH_AGENDA.md`` §O2): must the SAME POI show a
clear HTF sweep before the LTF seek, or is displacement / pillar context
enough?

WHAT THIS DOES
  Runs the frozen product composition (October 2025, full D1/H4/H1/M15
  detection set via ``lib/product_htf_series``) and joins, per **armed POI**:

    * its identity (id, direction, detection TF, zone band, arm time, models),
    * whether the frozen Stage-0 sweep detector fired a sweep of a liquidity
      level **inside that zone band**, in the same direction, at or before arm
      time (J1 — the pre-registered join),
    * a deliberately LOOSE secondary join (J2) reported separately,
    * displacement context (the product's own L1 sweep-link stamp),
    * outcome flags: routed → passed C3 → filled.

WHAT THIS DOES NOT DO
  No product change of any kind: no sweep pillar, no trigger field, no gate.
  ``LOGIC_CHANGED: NO``.

--------------------------------------------------------------------------
PRE-REGISTERED (frozen before any outcome table was inspected)
--------------------------------------------------------------------------
WINDOW (identical to O1)
  load 2025-05-01 UTC · exec 2025-10-01 → 2025-10-31 UTC

SWEEP SOURCE (existing frozen code, nothing invented)
  levels: ``smc.detection.liquidity_scanner.scan(candles, tf, include=ALL_FAMILIES)``
  sweeps: ``smc.detection.sweep_detector.detect_sweeps(candles, levels)``
  (the same pair ``DetectionDriver._stage0`` composes)

J1 (PRIMARY — the only join used for a HARD_STAGE reading)
  A POI is S+ when there exists a sweep result S on the POI's own detection-TF
  series with ALL of:
    (a) S.level.level inside [zone_low, zone_high] inclusive,
    (b) same direction: BSL sweep → SHORT zone, SSL sweep → LONG zone,
    (c) S candle timestamp <= arm time (no lookahead).
  Sweeps are computed once on the maximal closed-bar series per TF and then
  time-filtered per arm; a sweep candle never reads a later bar.

J2 (SECONDARY — reported, never a lock input)
  Any sweep in the same direction whose level lies within 0.25 × ATR of a zone
  edge (ATR = the detection-TF ATR at the sweep bar). Labeled LOOSE.

LOCK READING (agenda O2, words only)
  HARD_STAGE_WARRANTED requires S− to be *consistently* worse on route AND
  path with enough n; otherwise KEEP_UPSTREAM_ONLY (the current code has no
  sweep pillar, so ambiguity defaults to upstream-only).
--------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

# --- pre-registered constants (do not retune after results) ----------------
J2_EDGE_ATR = 0.25          # LOOSE secondary band, in detection-TF ATR
LOAD_FROM = "2025-05-01"
EXEC_FROM = "2025-10-01"
EXEC_TO = "2025-10-31"

CSV_FIELDS = [
    "poi_id", "direction", "detection_tf", "zone_low", "zone_high",
    "arm_time", "models", "has_displacement_context",
    "sweep_j1", "j1_sweep_time", "j1_sweep_level", "j1_pool",
    "sweep_j2_loose", "j2_sweep_time", "j2_sweep_level",
    "routed", "passed_c3", "filled",
]


def install_probes(state: dict) -> list:
    """Capture arm reports, the detection series and C3 outcomes (read-only)."""
    from smc.backtest import pipeline_adapter as pa
    from smc.backtest import pipeline_bridge as pb
    from smc.orchestration import multi_tf_runtime as rt

    restores = []
    ctx = {"site": "unknown"}

    original_run_batch = rt.MultiTFProductRuntime.run_batch

    def run_batch(self, **kwargs):
        report = original_run_batch(self, **kwargs)
        try:
            series = kwargs.get("series_by_tf") or {}
            kept = state["series"]
            for tf, bars in series.items():
                if bars and len(bars) > len(kept.get(tf, [])):
                    kept[tf] = list(bars)
            as_of = getattr(report, "as_of", None)
            disp = dict(getattr(report, "displacements", {}) or {})
            for poi in getattr(report, "armed", []) or []:
                state["armed"].append({
                    "poi": poi,
                    "arm_time": as_of,
                    "has_disp": poi.id in disp,
                })
        except Exception as exc:  # measurement never breaks the run
            state["errors"].append(f"run_batch probe: {exc!r}")
        return report

    rt.MultiTFProductRuntime.run_batch = run_batch
    restores.append(lambda: setattr(rt.MultiTFProductRuntime, "run_batch",
                                    original_run_batch))

    original_candidate = pb.candidate_from_route

    def candidate(route, **kwargs):
        result = original_candidate(route, **kwargs)
        if kwargs.get("completion_price") is not None:
            try:
                poi_id = route.poi.id
                state["routes"].setdefault(poi_id, 0)
                state["routes"][poi_id] += 1
                if result is not None:
                    state["passed"].setdefault(poi_id, 0)
                    state["passed"][poi_id] += 1
            except Exception as exc:  # noqa: BLE001
                state["errors"].append(f"candidate probe: {exc!r}")
        return result

    pb.candidate_from_route = candidate
    restores.append(lambda: setattr(pb, "candidate_from_route", original_candidate))

    for mod in (pa, rt):
        if not hasattr(mod, "candidate_from_route"):
            continue
        prev = mod.candidate_from_route
        mod.candidate_from_route = candidate
        restores.append(
            lambda mod=mod, prev=prev: setattr(mod, "candidate_from_route", prev)
        )
    return restores


def _sweeps_by_tf(series_by_tf: dict, errors: list) -> dict:
    """Stage-0 levels + sweeps per detection TF (frozen detector pair)."""
    from smc.detection.liquidity_scanner import ALL_FAMILIES
    from smc.detection.liquidity_scanner import scan as scan_liquidity
    from smc.detection.sweep_detector import detect_sweeps

    sweeps: dict = {}
    for tf, candles in series_by_tf.items():
        try:
            levels = scan_liquidity(candles, tf, include=ALL_FAMILIES)
            found = detect_sweeps(candles, levels)
            sweeps[tf] = sorted(found, key=lambda s: s.candle.timestamp)
        except Exception as exc:  # noqa: BLE001
            sweeps[tf] = []
            errors.append(f"stage0 {getattr(tf, 'name', tf)}: {exc!r}")
    return sweeps


def _atr_at(candles, index: int, period: int = 14) -> float | None:
    """Wilder ATR ending at ``index`` using only closed bars up to it."""
    if index < period:
        return None
    window = candles[: index + 1]
    trs = []
    for prev, cur in zip(window[:-1], window[1:]):
        tr = max(cur.high - cur.low,
                 abs(cur.high - prev.close),
                 abs(cur.low - prev.close))
        trs.append(tr)
    if len(trs) < period:
        return None
    seed = sum(trs[:period]) / period
    atr = seed
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def _j1_match(sweeps, tf, zone_low, zone_high, direction, arm_time):
    from smc.core.enums import PoolType

    want = PoolType.BSL if direction == "short" else PoolType.SSL
    for sweep in sweeps:
        if sweep.candle.timestamp > arm_time:
            continue
        if sweep.pool is not want:
            continue
        level = float(sweep.level.level)
        if zone_low <= level <= zone_high:
            return sweep
    return None


def _j2_match(sweeps, candles, zone_low, zone_high, direction, arm_time,
              atr_cache):
    from smc.core.enums import PoolType

    want = PoolType.BSL if direction == "short" else PoolType.SSL
    for sweep in sweeps:
        if sweep.candle.timestamp > arm_time:
            continue
        if sweep.pool is not want:
            continue
        atr = atr_cache.get(sweep.candle_index)
        if atr is None:
            atr = _atr_at(candles, sweep.candle_index)
            atr_cache[sweep.candle_index] = atr
        if not atr:
            continue
        level = float(sweep.level.level)
        if (zone_low - J2_EDGE_ATR * atr) <= level <= (zone_high + J2_EDGE_ATR * atr):
            return sweep
    return None


def _rate(n: int, d: int):
    return None if not d else n / d


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="O2 sweep stage measurement")
    parser.add_argument("--tag", default="o2_htf_sweep_stage")
    args = parser.parse_args(argv)

    out_dir = REPO_ROOT / "06_RESEARCH" / "results" / "open_decisions" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    state = {"armed": [], "series": {}, "routes": {}, "passed": {},
             "errors": []}
    restores = install_probes(state)
    try:
        import frozen_funnel_6m_new_contract as f6
        f6.LOCKED_LOAD, f6.LOCKED_FROM, f6.LOCKED_TO = LOAD_FROM, EXEC_FROM, EXEC_TO
        funnel = f6.run_frozen(args.tag, REPO_ROOT / "06_RESEARCH" / "results"
                               / "open_decisions" / f"{args.tag}_funnel")
    finally:
        for restore in reversed(restores):
            restore()

    sweeps_by_tf = _sweeps_by_tf(state["series"], state["errors"])

    fills = set()
    trades_path = (REPO_ROOT / "06_RESEARCH" / "results" / "open_decisions"
                   / f"{args.tag}_funnel" / "trades.csv")
    if trades_path.exists():
        import csv as _csv
        with trades_path.open(encoding="utf-8", newline="") as handle:
            for row in _csv.DictReader(handle):
                if row.get("poi_id"):
                    fills.add(row["poi_id"])

    rows = []
    atr_caches: dict = {}
    for entry in state["armed"]:
        poi = entry["poi"]
        zone = poi.zone
        tf = getattr(zone, "timeframe", None)
        tf_name = getattr(tf, "name", str(tf))
        direction = str(getattr(getattr(zone, "direction", None), "value",
                                getattr(zone, "direction", "")))
        low, high = float(zone.bottom), float(zone.top)
        arm_time = entry["arm_time"]
        candles = state["series"].get(tf, [])
        sweeps = sweeps_by_tf.get(tf, [])
        j1 = _j1_match(sweeps, tf, low, high, direction, arm_time) if candles else None
        cache = atr_caches.setdefault(tf_name, {})
        j2 = _j2_match(sweeps, candles, low, high, direction, arm_time, cache) if candles else None
        models = tuple(getattr(m, "name", str(m)) for m in (poi.models or []))
        rows.append({
            "poi_id": poi.id,
            "direction": direction,
            "detection_tf": tf_name,
            "zone_low": low,
            "zone_high": high,
            "arm_time": arm_time.isoformat() if hasattr(arm_time, "isoformat") else str(arm_time),
            "models": "+".join(models),
            "has_displacement_context": entry["has_disp"],
            "sweep_j1": j1 is not None,
            "j1_sweep_time": (j1.candle.timestamp.isoformat() if j1 else ""),
            "j1_sweep_level": (float(j1.level.level) if j1 else ""),
            "j1_pool": (getattr(j1.pool, "name", str(j1.pool)) if j1 else ""),
            "sweep_j2_loose": j2 is not None,
            "j2_sweep_time": (j2.candle.timestamp.isoformat() if j2 else ""),
            "j2_sweep_level": (float(j2.level.level) if j2 else ""),
            "routed": poi.id in state["routes"],
            "passed_c3": poi.id in state["passed"],
            "filled": poi.id in fills,
            "series_present": bool(candles),
        })

    rows.sort(key=lambda r: (r["arm_time"], r["poi_id"]))
    header = ",".join(CSV_FIELDS)
    lines = [header]
    for row in rows:
        cells = []
        for field in CSV_FIELDS:
            value = row.get(field, "")
            if isinstance(value, bool):
                value = "true" if value else "false"
            text = str(value)
            if "," in text:
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        lines.append(",".join(cells))
    payload = "\n".join(lines) + "\n"
    (out_dir / "armed_sweep_join.csv").write_text(payload, encoding="utf-8")
    checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    nodes = {True: "S_plus", False: "S_minus"}
    metrics = {}
    for flag in (True, False):
        subset = [r for r in rows if r["sweep_j1"] is flag]
        n = len(subset)
        metrics[nodes[flag]] = {
            "n": n,
            "routed": sum(1 for r in subset if r["routed"]),
            "passed_c3": sum(1 for r in subset if r["passed_c3"]),
            "filled": sum(1 for r in subset if r["filled"]),
            "route_rate": _rate(sum(1 for r in subset if r["routed"]), n),
            "fill_rate_of_routed": _rate(sum(1 for r in subset if r["filled"]),
                                         sum(1 for r in subset if r["routed"])),
            "fill_rate_of_armed": _rate(sum(1 for r in subset if r["filled"]), n),
        }
    # pass_C3 denominator is routed, so recompute honestly per cohort
    for flag in (True, False):
        subset = [r for r in rows if r["sweep_j1"] is flag]
        routed = [r for r in subset if r["routed"]]
        metrics[nodes[flag]]["pass_c3_rate"] = _rate(
            sum(1 for r in routed if r["passed_c3"]), len(routed))

    loose = {}
    for flag in (True, False):
        subset = [r for r in rows if r["sweep_j2_loose"] is flag]
        routed = [r for r in subset if r["routed"]]
        loose[nodes[flag]] = {
            "n": len(subset),
            "routed": len(routed),
            "route_rate": _rate(len(routed), len(subset)),
            "passed_c3": sum(1 for r in routed if r["passed_c3"]),
            "fill_rate_of_routed": _rate(sum(1 for r in subset if r["filled"]),
                                         len(routed)),
        }

    by_tf = {}
    for tf_name in sorted({r["detection_tf"] for r in rows}):
        subset = [r for r in rows if r["detection_tf"] == tf_name]
        by_tf[tf_name] = {
            "n": len(subset),
            "s_plus": sum(1 for r in subset if r["sweep_j1"]),
            "routed": sum(1 for r in subset if r["routed"]),
            "passed_c3": sum(1 for r in subset if r["passed_c3"]),
            "filled": sum(1 for r in subset if r["filled"]),
        }

    rejects = [r for r in rows if r["routed"] and not r["passed_c3"]]
    summary = {
        "window": {"load_from": LOAD_FROM, "exec_from": EXEC_FROM, "exec_to": EXEC_TO},
        "preregistered": {"join": "J1", "J2_EDGE_ATR": J2_EDGE_ATR,
                          "sweep_source": "liquidity_scanner.scan + sweep_detector.detect_sweeps",
                          "direction_map": "BSL->short, SSL->long",
                          "no_lookahead": "sweep candle timestamp <= arm time"},
        "counts": {
            "N_armed": len(rows),
            "N_s_plus": metrics["S_plus"]["n"],
            "share_s_plus": _rate(metrics["S_plus"]["n"], len(rows)),
            "N_routed": sum(1 for r in rows if r["routed"]),
            "N_passed_c3": sum(1 for r in rows if r["passed_c3"]),
            "N_filled": sum(1 for r in rows if r["filled"]),
            "N_displacement_context": sum(1 for r in rows if r["has_displacement_context"]),
        },
        "cohorts_j1": metrics,
        "cohorts_j2_loose": loose,
        "by_detection_tf": by_tf,
        "c3_rejects": {
            "n": len(rejects),
            "s_plus": sum(1 for r in rejects if r["sweep_j1"]),
            "s_plus_share": _rate(sum(1 for r in rejects if r["sweep_j1"]), len(rejects)),
        },
        "data_gap": {
            "armed_without_detection_series": sum(
                1 for r in rows if not r.get("series_present")),
            "sweeps_computed_by_tf": {getattr(tf, "name", str(tf)): len(v)
                                      for tf, v in sweeps_by_tf.items()},
            "error_count": len(state["errors"]),
            "errors": state["errors"][:5],
        },
        "funnel": {k: funnel.get(k) for k in
                   ("armed", "routes", "candidates", "fills", "armed_by_tf",
                    "detected_raw_by_tf", "htf_batches", "batch_errors")
                   if k in funnel},
        "checksum_armed_csv": checksum,
        "reconciliation": {"csv_rows": len(rows),
                           "armed_from_funnel": funnel.get("armed"),
                           "routes_from_funnel": funnel.get("routes")},
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), "checksum": checksum,
                      "counts": summary["counts"],
                      "cohorts_j1": metrics,
                      "by_detection_tf": by_tf,
                      "c3_rejects": summary["c3_rejects"],
                      "reconciliation": summary["reconciliation"]},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
