"""O1 — C3 reject / boundary anatomy measurement (read-only).

Measures why Stage-3 routes die at the C3 in-between gate
(``not_in_between``) on the frozen product window, so the open decision in
``OPEN_DECISIONS_RESEARCH_AGENDA.md`` §O1 can be read against data instead of
chart taste.

WHAT THIS DOES
  * Runs the frozen product composition (Phase 3, which is the same code path
    post_c2_diagnostic used) with the full detection set supplied through
    ``lib/product_htf_series.ensure_product_detection_frames`` (D1/H4/H1/M15).
  * Wraps ``candidate_from_route`` — the ONE function that applies C3
    (``smc/triggers/in_between.py`` via ``pipeline_bridge``) for both call
    sites (adapter scan + product menu) — and records the geometry of every
    evaluation, whether it passed or was rejected.
  * Writes ``rejects.csv`` (every C3 evaluation, one row each) and
    ``summary.json`` (counts, bucket shares, percentiles, splits, checksum).

WHAT THIS DOES NOT DO
  No product code change, no gate change, no boundary-sweep emitter, no
  threshold tuning. Bucket edges are PRE-REGISTERED below and must not be
  edited after a result is inspected (that would fail the engagement).

WINDOW (frozen before any result was inspected)
  load 2025-05-01 UTC → exec 2025-10-01 → 2025-10-31 UTC (the directive's
  documented primary window; identical to POST_C2_DIAGNOSTIC_REPORT).

USAGE
  python 06_RESEARCH/scripts/o1_c3_boundary_anatomy.py [--tag o1_c3_boundary]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

# ---------------------------------------------------------------------------
# PRE-REGISTERED BUCKET EDGES (fixed before the run; do not edit post-hoc)
# ---------------------------------------------------------------------------
EDGE_NEAR_ATR = 0.25      # B1: outside but within 0.25 ATR of the edge
EDGE_WIDE_ATR = 1.0       # B2: 0.25 < dist <= 1.0 ATR; B3: > 1.0 ATR
# Fallback when ATR is unavailable (labeled DATA_GAP): same ratios applied to
# the zone height instead of ATR — the only quantity always available.
EDGE_NEAR_HEIGHT = 0.25
EDGE_WIDE_HEIGHT = 1.0

# Frozen window (identical to the post-C2 diagnostic primary).
LOAD_FROM = "2025-05-01"
EXEC_FROM = "2025-10-01"
EXEC_TO = "2025-10-31"

CSV_FIELDS = [
    "call_site", "timestamp", "direction", "trigger", "poi_id", "detection_tf",
    "model_tags", "zone_low", "zone_high", "zone_mid", "zone_height",
    "entry_ref", "bar_open", "bar_high", "bar_low", "bar_close",
    "close_inside", "signed_edge_dist", "dist_atr", "dist_height",
    "atr", "atr_missing", "bar_range_touches_zone", "limit_inside_zone",
    "bucket_primary", "b4_touch_close_out", "gate_result",
]


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _quantiles(values: list[float]) -> dict:
    return {
        "n": len(values),
        "median": _pct(values, 0.5),
        "p25": _pct(values, 0.25),
        "p75": _pct(values, 0.75),
        "max": max(values) if values else None,
    }


def install_probe(records: list[dict]) -> list:
    """Wrap candidate_from_route at every bound call site; return restores."""
    from smc.backtest import pipeline_adapter as pa
    from smc.backtest import pipeline_bridge as pb
    from smc.orchestration import product_menu_mtf as menu
    from smc.triggers.in_between import trigger_in_between

    restores = []
    ctx: dict = {"adapter": None}

    original = pb.candidate_from_route

    def probed(route, **kwargs):
        completion_price = kwargs.get("completion_price")
        result = original(route, **kwargs)
        if completion_price is None:
            records.append({"call_site": _current_site[0], "gate_result": "no_completion_price"})
            return result
        try:
            _record(records, route, completion_price, result, ctx,
                    _current_site[0], trigger_in_between)
        except Exception as exc:  # measurement must never break the product run
            records.append({"call_site": _current_site[0], "gate_result": f"probe_error:{exc!r}"})
        return result

    _current_site = ["unknown"]

    # 1) module attribute on pipeline_bridge itself
    pb.candidate_from_route = probed
    restores.append(lambda: setattr(pb, "candidate_from_route", original))

    # 2) names already bound by the two call sites (patch per module, tagging)
    for mod, label in ((pa, "scan"), (menu, "menu")):
        if not hasattr(mod, "candidate_from_route"):
            continue
        prev = mod.candidate_from_route

        def make(prev=prev, label=label):
            def call(route, **kwargs):
                _current_site[0] = label
                try:
                    return probed(route, **kwargs)
                finally:
                    _current_site[0] = "unknown"
            return call

        mod.candidate_from_route = make()
        restores.append(lambda mod=mod, prev=prev: setattr(mod, "candidate_from_route", prev))

    # 3) adapter context so the probe can read the completion bar and ATR
    original_gen = pa.PipelineAdapter.generate_candidates

    def gen(self, *args, **kwargs):
        ctx["adapter"] = self
        try:
            return original_gen(self, *args, **kwargs)
        finally:
            ctx["adapter"] = None

    pa.PipelineAdapter.generate_candidates = gen
    restores.append(lambda: setattr(pa.PipelineAdapter, "generate_candidates", original_gen))
    return restores


def _record(records, route, completion_price, result, ctx, call_site,
            trigger_in_between) -> None:
    signal = route.signal
    zone = route.poi.zone
    close = float(completion_price)
    try:
        low, high = float(zone.bottom), float(zone.top)
        locatable = True
    except (TypeError, ValueError):
        low, high = 0.0, 0.0
        locatable = False
    adapter = ctx.get("adapter")
    bar = None
    atr = None
    idx = getattr(signal, "completion_index", None)
    if adapter is not None and idx is not None:
        candles = getattr(adapter, "_candles", None) or []
        if 0 <= idx < len(candles):
            bar = candles[idx]
        try:
            atr = adapter.current_atr(idx)
        except Exception:
            atr = None

    # Mirrors the frozen predicate (``trigger_in_between`` is exactly this
    # comparison against the completion bar's CLOSE, §25; unlocatable bounds
    # fail closed → reject).
    inside = locatable and low <= close <= high
    height = (high - low) if locatable else 0.0
    if not locatable:
        dist = None
    elif inside:
        dist = 0.0
    elif close < low:
        dist = low - close
    else:
        dist = close - high

    atr_missing = not atr
    dist_atr = None if (atr_missing or dist is None) else dist / float(atr)
    dist_height = (None if (dist is None or height <= 0) else dist / height)

    if not locatable:
        bucket = "B_UNLOCATABLE"
    elif inside:
        bucket = "B0_CLOSE_INSIDE"
    else:
        if atr_missing:
            near, wide = EDGE_NEAR_HEIGHT, EDGE_WIDE_HEIGHT
            measure = dist_height
        else:
            near, wide = EDGE_NEAR_ATR, EDGE_WIDE_ATR
            measure = dist_atr
        if measure is None:
            bucket = "B3_FAR"
        elif measure <= near:
            bucket = "B1_EDGE_NEAR"
        elif measure <= wide:
            bucket = "B2_EDGE_WIDE"
        else:
            bucket = "B3_FAR"

    touches = False
    if bar is not None:
        touches = float(bar.low) <= high and float(bar.high) >= low
    b4 = bool(touches and not inside)

    entry = getattr(signal, "entry_price", None)
    limit_inside = None if entry is None else (low <= float(entry) <= high)

    models = getattr(route.poi, "models", None) or ()
    tags = tuple(getattr(m, "name", str(m)) for m in models)
    trigger = getattr(signal, "trigger", None)
    records.append({
        "call_site": call_site,
        "timestamp": (bar.timestamp.isoformat() if bar is not None
                      else (getattr(signal, "timestamp", None) or "")),
        "direction": str(getattr(getattr(signal, "direction", None), "value",
                                 getattr(signal, "direction", ""))),
        "trigger": str(getattr(trigger, "value", getattr(trigger, "name", trigger or ""))),
        "poi_id": getattr(route.poi, "id", ""),
        "detection_tf": str(getattr(getattr(zone, "timeframe", None), "name", "")),
        "model_tags": ",".join(tags),
        "zone_low": low if locatable else "", "zone_high": high if locatable else "",
        "zone_mid": ((low + high) / 2.0) if locatable else "",
        "zone_height": height if locatable else "",
        "entry_ref": "" if entry is None else float(entry),
        "bar_open": "" if bar is None else float(bar.open),
        "bar_high": "" if bar is None else float(bar.high),
        "bar_low": "" if bar is None else float(bar.low),
        "bar_close": close,
        "close_inside": inside,
        "signed_edge_dist": "" if dist is None else dist,
        "dist_atr": "" if dist_atr is None else dist_atr,
        "dist_height": "" if dist_height is None else dist_height,
        "atr": "" if atr_missing else float(atr),
        "atr_missing": atr_missing,
        "bar_range_touches_zone": touches,
        "limit_inside_zone": "" if limit_inside is None else limit_inside,
        "bucket_primary": bucket,
        "b4_touch_close_out": b4,
        "gate_result": "PASSED" if result is not None else "not_in_between",
    })


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarise(rows: list[dict]) -> dict:
    evals = [r for r in rows if r.get("gate_result") in ("PASSED", "not_in_between")]
    rejects = [r for r in evals if r["gate_result"] == "not_in_between"]
    passed = [r for r in evals if r["gate_result"] == "PASSED"]

    def shares(subset, field, keys):
        total = len(subset)
        counts = Counter(str(r[field]) for r in subset)
        return {
            k: {"n": counts.get(k, 0),
                "share": (counts.get(k, 0) / total) if total else None}
            for k in keys
        }

    distance_atr = [r["dist_atr"] for r in rejects if r["dist_atr"] != ""]
    distance_height = [r["dist_height"] for r in rejects if r["dist_height"] != ""]
    b4 = sum(1 for r in rejects if r["b4_touch_close_out"])

    by_trigger = {}
    for key, n in Counter(str(r["trigger"]) for r in rejects).most_common():
        subset = [r for r in rejects if str(r["trigger"]) == key]
        by_trigger[key] = {
            "n": n,
            "B1": sum(1 for r in subset if r["bucket_primary"] == "B1_EDGE_NEAR"),
            "B2": sum(1 for r in subset if r["bucket_primary"] == "B2_EDGE_WIDE"),
            "B3": sum(1 for r in subset if r["bucket_primary"] == "B3_FAR"),
            "B4": sum(1 for r in subset if r["b4_touch_close_out"]),
        }

    by_tf = {}
    for key, n in Counter(str(r["detection_tf"]) for r in rejects).most_common():
        subset = [r for r in rejects if str(r["detection_tf"]) == key]
        by_tf[key] = {
            "n": n,
            "B1": sum(1 for r in subset if r["bucket_primary"] == "B1_EDGE_NEAR"),
            "B2": sum(1 for r in subset if r["bucket_primary"] == "B2_EDGE_WIDE"),
            "B3": sum(1 for r in subset if r["bucket_primary"] == "B3_FAR"),
            "B4": sum(1 for r in subset if r["b4_touch_close_out"]),
        }

    return {
        "window": {"load_from": LOAD_FROM, "exec_from": EXEC_FROM, "exec_to": EXEC_TO},
        "preregistered_buckets": {
            "EDGE_NEAR_ATR": EDGE_NEAR_ATR, "EDGE_WIDE_ATR": EDGE_WIDE_ATR,
            "EDGE_NEAR_HEIGHT": EDGE_NEAR_HEIGHT, "EDGE_WIDE_HEIGHT": EDGE_WIDE_HEIGHT,
        },
        "counts": {
            "N_c3_evals": len(evals),
            "N_not_in_between": len(rejects),
            "N_passed_C3": len(passed),
            "N_no_completion_price": sum(1 for r in rows if r.get("gate_result") == "no_completion_price"),
            "N_probe_errors": sum(1 for r in rows if str(r.get("gate_result", "")).startswith("probe_error")),
            "N_by_call_site": dict(Counter(str(r.get("call_site")) for r in evals)),
        },
        "bucket_shares": shares(rejects, "bucket_primary",
                                ["B0_CLOSE_INSIDE", "B_UNLOCATABLE", "B1_EDGE_NEAR",
                                 "B2_EDGE_WIDE", "B3_FAR"]),
        "b4_touch_close_out": {
            "n": b4, "share_of_rejects": (b4 / len(rejects)) if rejects else None,
            "share_of_touch_rejects": (
                b4 / sum(1 for r in rejects if r["bar_range_touches_zone"])
                if any(r["bar_range_touches_zone"] for r in rejects) else None
            ),
        },
        "distance_atr": _quantiles(distance_atr),
        "distance_zone_height": _quantiles(distance_height),
        "atr_data_gap": {
            "n": sum(1 for r in rejects if r["atr_missing"]),
            "share_of_rejects": (
                sum(1 for r in rejects if r["atr_missing"]) / len(rejects) if rejects else None
            ),
        },
        "by_trigger": by_trigger,
        "by_detection_tf": by_tf,
        "limit_inside_zone": {
            "n_available": sum(1 for r in rejects if r["limit_inside_zone"] != ""),
            "n_inside": sum(1 for r in rejects if r["limit_inside_zone"] is True),
        },
        "sanity": {
            "rejects_with_close_inside": sum(1 for r in rejects if r["close_inside"]),
            "passed_with_close_outside": sum(1 for r in passed if not r["close_inside"]),
        },
        "reconciliation": {
            "csv_gate_rows": len(evals),
            "csv_not_in_between": len(rejects),
            "csv_passed": len(passed),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="O1 C3 reject / boundary anatomy")
    parser.add_argument("--tag", default="o1_c3_boundary")
    args = parser.parse_args(argv)

    out_dir = REPO_ROOT / "06_RESEARCH" / "results" / "open_decisions" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    restores = install_probe(records)

    import frozen_funnel_6m_new_contract as f6
    f6.LOCKED_LOAD, f6.LOCKED_FROM, f6.LOCKED_TO = LOAD_FROM, EXEC_FROM, EXEC_TO
    try:
        run_summary = f6.run_frozen(args.tag, REPO_ROOT / "06_RESEARCH" / "results"
                                    / "open_decisions" / f"{args.tag}_funnel")
    finally:
        for restore in reversed(restores):
            restore()

    gate_rows = [r for r in records if r.get("gate_result") in ("PASSED", "not_in_between")]
    gate_rows.sort(key=lambda r: (r["timestamp"], r["poi_id"], r["call_site"]))
    header = ",".join(CSV_FIELDS)
    lines = []
    for row in gate_rows:
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
    payload = "\n".join([header] + lines) + "\n"
    (out_dir / "rejects.csv").write_text(payload, encoding="utf-8")
    checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    summary = summarise(records)
    summary["checksum_rejects_csv"] = checksum
    summary["rows_written"] = len(gate_rows)
    summary["funnel"] = {
        key: run_summary.get(key) for key in
        ("armed", "routes", "candidates", "intents_placed", "fills", "htf_batches",
         "batch_errors", "detected_raw_by_tf", "duplicates_suppressed")
        if key in run_summary
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), "checksum": checksum,
                      "counts": summary["counts"],
                      "bucket_shares": summary["bucket_shares"],
                      "b4": summary["b4_touch_close_out"],
                      "funnel": summary["funnel"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
