#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage 3 Lifecycle Timing Audit — arm / first-touch / scan-close vs completions.

Identification / measurement only (Lead Architect directive). For every
Stage 3 completion already recorded in the visibility pack ledger, measure
its position in the product lifecycle relative to the parent HTF
structure's arm / first-touch / scan-close events, using the SAME product
rules the runner uses (the accepted §5-mirrored replay — no invention).

Banned (enforced): no 04_SRC/smc/** edits, no §5/§23/§24 window widening,
no new thresholds/filters, no what-if expiry reruns, no PnL/edge claims.

Method (all existing code, no regeneration of inputs):
  - Inputs reused from disk: Stage 3 ledger (263 rows), accepted H4/D1
    packs, accepted LTF-pack ledger (detector markers for charts), the
    canonical M1 parquet.
  - Structures loaded with the SAME loader rules as
    ``stage3_trigger_visibility`` (H4 poi_raw + D1 subset <= 10).
  - Lifecycle recovered by ``stage3_trigger_visibility.
    observe_routes_instrumented`` — the instrumented §5 replay (arm at
    structure close, feed_bar state machine, first-touch +1 scan rule,
    violation/give-up/route retirement) that produced the accepted pack's
    route funnel (2 routed / 199 touch-gate / 62 violation).

Bucket taxonomy (exactly one per completion):
  OPEN_SCAN   completion at or before the last bar the §5 scan was open
              (scan_close_ts = timestamp of the last scanned bar — the
              window's inclusive close boundary; visible to product)
  CLOSED_TOUCH completed after the first-touch +1 gate closed the scan
  CLOSED_VIOL  completed after zone violation closed the scan
  NEVER_ARMED  parent structure never armed in the product path
  DATA_GAP     required timestamp / join key missing (counted, listed,
              never invented)
  UNCLASSIFIED residual (would be reported as a defect — expected 0)
"""

from __future__ import annotations

import bisect
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from smc.config.timeframe import Timeframe
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi

import ltf_confirmation_pack as ltf
import stage3_trigger_visibility as s3

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "stage3_lifecycle_timing"
CHARTS_DIR = OUT_DIR / "charts"
EVENTS_CSV = OUT_DIR / "events_lifecycle.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"
LIFECYCLE_LEDGER_CSV = OUT_DIR / "events_lifecycle.csv"

STAGE3_LEDGER_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                     "stage3_trigger_visibility" / "events_stage3_triggers.csv")

CSV_COLUMNS = [
    "trigger_id", "trigger_type", "direction", "relation_to_htf",
    "entry_price_ref", "route_would_form", "related_htf_event_id",
    "structure_close_ts", "arm_ts", "first_touch_ts", "scan_close_ts",
    "scan_close_event_ts", "scan_close_reason", "stage3_completion_ts",
    "d_completion_minus_close_bars", "d_completion_minus_arm_bars",
    "d_completion_minus_first_touch_bars",
    "d_completion_minus_scan_close_bars",
    "d_completion_minus_close_min", "d_completion_minus_arm_min",
    "d_completion_minus_first_touch_min",
    "d_completion_minus_scan_close_min", "bucket",
]

BUCKETS = ["OPEN_SCAN", "CLOSED_TOUCH", "CLOSED_VIOL", "NEVER_ARMED",
           "DATA_GAP"]

CLOSE_REASON_LABELS = {
    "tested": "first_touch_gate",
    "violated": "zone_violation",
    "fresh": "give_up",
}


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def scan_close_reason_label(pop_reason: str | None, route_bar: int | None,
                            last_scanned: int | None) -> str:
    """Why the §5 scan for a structure ended (product replay facts only)."""
    if route_bar is not None:
        return "route_retire"
    if pop_reason is not None:
        return CLOSE_REASON_LABELS.get(pop_reason, str(pop_reason))
    if last_scanned is not None:
        return "open_to_series_end"
    return "never_opened"


def assign_bucket(*, join_ok: bool, completion_bar: int | None,
                  arm_bar: int | None, last_scanned: int | None,
                  pop_reason: str | None, route_bar: int | None) -> str:
    """Exactly one lifecycle bucket per completion (see module docstring).

    Order: missing data -> never armed -> visible while scan open ->
    closed by the gate that actually ended the scan; anything else is
    UNCLASSIFIED (expected count 0; surfaced as a defect, never silently
    absorbed into another bucket).
    """
    if not join_ok or completion_bar is None:
        return "DATA_GAP"
    if arm_bar is None:
        return "NEVER_ARMED"
    if last_scanned is not None and completion_bar <= last_scanned:
        return "OPEN_SCAN"
    if pop_reason == "tested":
        return "CLOSED_TOUCH"
    if pop_reason == "violated":
        return "CLOSED_VIOL"
    if route_bar is not None and completion_bar <= route_bar:
        return "OPEN_SCAN"
    return "UNCLASSIFIED"


def pctl(values: list[float], q: float) -> float | None:
    """Linear-interpolation percentile (deterministic, q in [0, 1])."""
    if not values:
        return None
    data = sorted(float(v) for v in values)
    if len(data) == 1:
        return data[0]
    pos = q * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    frac = pos - lo
    return data[lo] * (1.0 - frac) + data[hi] * frac


def distribution(values: list[float | None]) -> dict:
    """p25 / median / p75 over the non-null values (null-safe)."""
    clean = [v for v in values if v is not None]
    return {
        "n_used": len(clean),
        "n_null": len(values) - len(clean),
        "p25": pctl(clean, 0.25),
        "median": pctl(clean, 0.50),
        "p75": pctl(clean, 0.75),
    }


def classify_scan_close(gate: dict | None) -> dict:
    """Recover close-boundary timestamps from one structure's gate stats."""
    if gate is None:
        return {"arm_bar": None, "tested_bar": None, "last_scanned": None,
                "pop_bar": None, "pop_reason": None, "route_bar": None}
    return {"tested_bar": gate.get("tested_bar"),
            "last_scanned": gate.get("last_scanned"),
            "pop_bar": gate.get("pop_bar"),
            "pop_reason": gate.get("pop_reason"),
            "route_bar": gate.get("route_bar")}


# --------------------------------------------------------------------------- #
# Inputs (reused from disk — never regenerated)
# --------------------------------------------------------------------------- #
def load_stage3_ledger() -> list[dict]:
    with open(STAGE3_LEDGER_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_structures() -> list[dict]:
    """Same accepted-pack loading rules as stage3_trigger_visibility.main."""
    structures: list[dict] = []
    with open(ltf.H4_EVENTS_CSV, encoding="utf-8") as f:
        h4_rows = list(csv.DictReader(f))
    for r in h4_rows:
        if r["event_type"] != "poi_raw":
            continue
        ts = datetime.fromisoformat(r["ts_utc"])
        if not (ltf.EXEC_START <= ts <= ltf.EXEC_END):
            continue
        structures.append({
            "event_id": r["event_id"], "plain_tag": r["plain_tag"].upper(),
            "direction": r["direction"], "zone_low": float(r["zone_low"]),
            "zone_high": float(r["zone_high"]), "ts_utc": r["ts_utc"],
            "_htf_dt": ts, "_anchor_dt": ts + timedelta(hours=4),
            "kind": r["kind"], "src": "H4_pack_raw", "route": None,
        })
    d1_subset: list[dict] = []
    if ltf.D1_EVENTS_CSV.exists():
        with open(ltf.D1_EVENTS_CSV, encoding="utf-8") as f:
            d1_rows = [r for r in csv.DictReader(f)
                       if r["event_type"] == "poi_raw"]
        for r in ltf._spread(sorted(d1_rows, key=lambda r: r["ts_utc"]),
                             ltf.MAX_D1_SUBSET):
            ts = datetime.fromisoformat(r["ts_utc"])
            if not (ltf.EXEC_START <= ts <= ltf.EXEC_END):
                continue
            d1_subset.append({
                "event_id": r["event_id"], "plain_tag": r["plain_tag"].upper(),
                "direction": r["direction"], "zone_low": float(r["zone_low"]),
                "zone_high": float(r["zone_high"]), "ts_utc": r["ts_utc"],
                "_htf_dt": ts, "_anchor_dt": ts + timedelta(hours=24),
                "kind": r["kind"], "src": "D1_pack_subset", "route": None,
            })
    structures.sort(key=lambda s: (s["ts_utc"], s["event_id"]))
    d1_subset.sort(key=lambda s: (s["ts_utc"], s["event_id"]))
    return structures + d1_subset


def load_detector_rows() -> dict[str, list[dict]]:
    """Accepted LTF-pack ledger detector rows (chart markers only)."""
    out: dict[str, list[dict]] = {}
    ltf_csv = (REPO_ROOT / "06_RESEARCH" / "results" / "ltf_confirmation" /
               "events_ltf_confirmation.csv")
    if not ltf_csv.exists():
        return out
    with open(ltf_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["ltf_plain_tag"].startswith("TRIGGER"):
                continue
            if r["ltf_tf"] == "none":
                continue
            out.setdefault(r["htf_event_id"], []).append(r)
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ltf.install_deterministic_poi_ids()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in CHARTS_DIR.glob("*.png"):
        try:
            stale.unlink()
        except OSError:
            pass

    # ---- Series (same window/rule as the Stage 3 pack) ------------------ #
    m1 = load_ohlcv_parquet(ltf.DATA_PARQUET)
    m1_win = [c for c in m1
              if c.timestamp >= ltf.WARM_START
              and c.timestamp <= datetime(2025, 12, 1, tzinfo=timezone.utc)]
    by_tf = resample_multi(m1_win, [Timeframe.M5])
    m5 = by_tf[Timeframe.M5]
    m5_ts = [c.timestamp for c in m5]
    m5_index = {ts: i for i, ts in enumerate(m5_ts)}
    print(f"[lifecycle] M5={len(m5)}", flush=True)

    # ---- Inputs --------------------------------------------------------- #
    ledger = load_stage3_ledger()
    structures = load_structures()
    by_id = {s["event_id"]: s for s in structures}
    print(f"[lifecycle] completions={len(ledger)} structures={len(structures)}",
          flush=True)

    # ---- Product lifecycle replay (accepted instrumented §5 mirror) ------ #
    gate_by_struct = s3.observe_routes_instrumented(structures, m5)
    print(f"[lifecycle] gate structures={len(gate_by_struct)}", flush=True)

    # ---- Pass 2 (charts + consistency cross-check only) ----------------- #
    inv_count = s3.scan_inventory(structures, m5)
    print(f"[lifecycle] inventory recomputed={inv_count}", flush=True)

    # ---- Per-completion lifecycle rows ---------------------------------- #
    rows: list[dict] = []
    data_gap: list[str] = []
    never_armed: list[str] = []
    causal_violations: list[dict] = []
    for r in ledger:
        sid = r["related_htf_event_id"]
        structure = by_id.get(sid)
        join_ok = structure is not None
        completion_dt = datetime.fromisoformat(r["bar_time_utc"])
        completion_bar = m5_index.get(completion_dt)

        if join_ok:
            close_dt = structure["_anchor_dt"]
            close_bar = bisect.bisect_left(m5_ts, close_dt)
        else:
            close_dt, close_bar = None, None
            data_gap.append(r["trigger_id"])

        gate = gate_by_struct.get(sid) if join_ok else None
        arm_bar = structure.get("arm_bar") if join_ok else None
        info = classify_scan_close(gate)
        tested_bar = info["tested_bar"]
        last_scanned = info["last_scanned"]
        pop_bar = info["pop_bar"]
        pop_reason = info["pop_reason"]
        route_bar = info["route_bar"]

        if join_ok and arm_bar is None and r["trigger_id"] not in never_armed:
            never_armed.append(r["trigger_id"])

        bucket = assign_bucket(
            join_ok=join_ok, completion_bar=completion_bar,
            arm_bar=arm_bar, last_scanned=last_scanned,
            pop_reason=pop_reason, route_bar=route_bar)

        # Causal order hard check (completion before structure close = defect).
        if (join_ok and close_bar is not None and completion_bar is not None
                and completion_bar < close_bar):
            causal_violations.append({
                "trigger_id": r["trigger_id"],
                "completion_bar": completion_bar,
                "structure_close_bar": close_bar})

        def _bar(idx: int | None) -> int | None:
            return None if idx is None else completion_bar - idx

        def _min(ts: datetime | None) -> float | None:
            return None if ts is None else round(
                (completion_dt - ts).total_seconds() / 60.0, 1)

        arm_dt = m5_ts[arm_bar] if arm_bar is not None else None
        touch_dt = m5_ts[tested_bar] if tested_bar is not None else None
        scan_close_dt = m5_ts[last_scanned] if last_scanned is not None else None
        event_bar = pop_bar if pop_bar is not None else route_bar
        event_dt = m5_ts[event_bar] if event_bar is not None else None

        rows.append({
            "trigger_id": r["trigger_id"],
            "trigger_type": r["trigger_type"],
            "direction": r["direction"],
            "relation_to_htf": r["relation_to_htf"],
            "entry_price_ref": r["entry_price_ref"],
            "route_would_form": r["route_would_form"],
            "related_htf_event_id": sid,
            "structure_close_ts": close_dt.isoformat() if close_dt else "",
            "arm_ts": arm_dt.isoformat() if arm_dt else "",
            "first_touch_ts": touch_dt.isoformat() if touch_dt else "",
            "scan_close_ts": scan_close_dt.isoformat() if scan_close_dt else "",
            "scan_close_event_ts": event_dt.isoformat() if event_dt else "",
            "scan_close_reason": (scan_close_reason_label(
                pop_reason, route_bar, last_scanned) if join_ok else "join_miss"),
            "stage3_completion_ts": completion_dt.isoformat(),
            "d_completion_minus_close_bars": (_bar(close_bar)
                                              if close_bar is not None else None),
            "d_completion_minus_arm_bars": _bar(arm_bar),
            "d_completion_minus_first_touch_bars": _bar(tested_bar),
            "d_completion_minus_scan_close_bars": _bar(last_scanned),
            "d_completion_minus_close_min": _min(close_dt),
            "d_completion_minus_arm_min": _min(arm_dt),
            "d_completion_minus_first_touch_min": _min(touch_dt),
            "d_completion_minus_scan_close_min": _min(scan_close_dt),
            "bucket": bucket,
        })

    # ---- Sanity gates ---------------------------------------------------- #
    unclassified = [r["trigger_id"] for r in rows
                    if r["bucket"] == "UNCLASSIFIED"]
    bucket_counts = {b: 0 for b in BUCKETS}
    for r in rows:
        if r["bucket"] in bucket_counts:
            bucket_counts[r["bucket"]] += 1
    routed = [r for r in rows if r["route_would_form"] == "yes"]
    routed_ids_ok = len(routed) == 2
    routed_open = routed_ids_ok and all(r["bucket"] == "OPEN_SCAN"
                                        for r in routed)
    sums_ok = (sum(bucket_counts.values()) + len(unclassified)) == len(rows)
    status = "PASS"
    defects: list[str] = []
    if causal_violations:
        status = "FAIL"
        defects.append(f"causal order violations: {causal_violations}")
    if data_gap:
        status = "FAIL"
        defects.append(f"DATA_GAP rows: {data_gap}")
    if unclassified:
        status = "FAIL"
        defects.append(f"UNCLASSIFIED rows: {unclassified}")
    if not routed_ids_ok:
        status = "FAIL"
        defects.append(f"expected exactly 2 routed rows, got {len(routed)}")
    if routed_ids_ok and not routed_open:
        status = "FAIL"
        defects.append("routed rows not OPEN_SCAN: "
                       f"{[(r['trigger_id'], r['bucket']) for r in routed]}")
    if not sums_ok:
        status = "FAIL"
        defects.append("bucket counts do not sum to completion total")

    # ---- Aggregates ------------------------------------------------------ #
    counts_by_type_bucket: dict[str, dict[str, int]] = {}
    for r in rows:
        t = counts_by_type_bucket.setdefault(r["trigger_type"],
                                             {b: 0 for b in BUCKETS})
        t[r["bucket"]] = t.get(r["bucket"], 0) + 1

    def group(bucket_set: set[str]) -> list[dict]:
        return [r for r in rows if r["bucket"] in bucket_set]

    open_rows = group({"OPEN_SCAN"})
    other_rows = [r for r in rows if r["bucket"] != "OPEN_SCAN"]

    def dist_block(subset: list[dict]) -> dict:
        return {
            "n": len(subset),
            "completion_minus_first_touch_bars": distribution(
                [r["d_completion_minus_first_touch_bars"] for r in subset]),
            "completion_minus_scan_close_bars": distribution(
                [r["d_completion_minus_scan_close_bars"] for r in subset]),
        }

    total = len(rows)
    n_open = bucket_counts["OPEN_SCAN"]
    pct_all = (100.0 * n_open / total) if total else 0.0
    f_rows = [r for r in rows if r["trigger_type"] == "F"]
    f_open = sum(1 for r in f_rows if r["bucket"] == "OPEN_SCAN")
    pct_f = (100.0 * f_open / len(f_rows)) if f_rows else 0.0

    all_scan_delts = [r["d_completion_minus_scan_close_bars"] for r in rows
                      if r["d_completion_minus_scan_close_bars"] is not None]
    f_scan_delts = [r["d_completion_minus_scan_close_bars"] for r in f_rows
                    if r["d_completion_minus_scan_close_bars"] is not None]

    summary = {
        "window": {"exec_start_utc": ltf.EXEC_START.isoformat(),
                   "exec_end_utc": ltf.EXEC_END.isoformat(),
                   "warm_start_utc": ltf.WARM_START.isoformat()},
        "source_ledger": str(STAGE3_LEDGER_CSV.relative_to(REPO_ROOT)),
        "total_completions": total,
        "bucket_counts": bucket_counts,
        "unclassified_count": len(unclassified),
        "counts_by_type_bucket": counts_by_type_bucket,
        "pct_open_scan_all": round(pct_all, 2),
        "pct_open_scan_f": round(pct_f, 2),
        "distributions": {
            "OPEN_SCAN": dist_block(open_rows),
            "OTHERS": dist_block(other_rows),
        },
        "median_completion_minus_scan_close_bars": {
            "all": pctl(all_scan_delts, 0.5),
            "f_only": pctl(f_scan_delts, 0.5),
            "n_used_all": len(all_scan_delts),
            "n_used_f_only": len(f_scan_delts),
        },
        "routed_rows_sanity": {
            "expected_routed_rows": 2,
            "found_routed_rows": len(routed),
            "routed_buckets": {r["trigger_id"]: r["bucket"] for r in routed},
            "pass": bool(routed_ids_ok and routed_open),
        },
        "join_rule": ("related_htf_event_id -> poi_raw event_id in accepted "
                      "H4 pack + D1 subset (same loader as the Stage 3 pack); "
                      "structure_close = HTF open ts + timeframe (H4 +4h / "
                      "D1 +24h), the product's arm anchor"),
        "lifecycle_rule": ("arm / first_touch / scan_close recovered by "
                           "stage3_trigger_visibility."
                           "observe_routes_instrumented — the accepted "
                           "§5-mirrored replay (arm at close, feed_bar state, "
                           "first-touch +1 scan gate, violation / give-up / "
                           "route retirement); scan_close_ts = timestamp of "
                           "the LAST bar the scan was open (inclusive close "
                           "boundary — the pop/retire bar is "
                           "scan_close_event_ts)"),
        "data_gap_rows": data_gap,
        "never_armed_rows": never_armed,
        "causal_order_violations": causal_violations,
        "inventory_recomputed": inv_count,
        "limitations": [
            "Lifecycle replay = the accepted instrumented §5 mirror "
            "(pre-pillar); pillars / risk / execution not run — arm_ts is "
            "when the product path arms, not when an order exists.",
            "scan_close_ts is the last OPEN bar of the §5 scan (inclusive "
            "boundary); scan_close_event_ts is the pop/retire bar itself. "
            "OPEN_SCAN uses the visibility rule (completion <= last open "
            "bar) so 'would be visible to product' never includes the bar "
            "on which the gate fired.",
            "first_touch_ts null = the zone was never reported TESTED in "
            "the replay (violation without prior touch is possible); "
            "first-touch distributions are null-safe and report n_null.",
            "No expiry/what-if variants were run; windows are the locked "
            "constants only (poi_give_up_bars / TRIGGER_*_EXPIRY).",
            "No expectancy, PnL, win-rate or edge claims anywhere in this "
            "audit (identification only).",
            "Buckets CLOSED_TOUCH / CLOSED_VIOL refer to the close reason "
            "of the structure that OWNED the completion's parent scan; a "
            "completion before that close is OPEN_SCAN regardless of the "
            "structure's eventual fate.",
        ],
        "status": status,
        "defects": defects,
        "charts": [],
    }

    # ---- Write ledger ----------------------------------------------------- #
    with open(EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: ("" if row.get(c) is None else row.get(c))
                             for c in CSV_COLUMNS})

    # ---- Charts: one illustrative example per populated bucket ------------ #
    det_by_struct = load_detector_rows()
    chart_index: list[dict] = []
    for bucket in ("OPEN_SCAN", "CLOSED_TOUCH", "CLOSED_VIOL"):
        examples = sorted([r for r in rows if r["bucket"] == bucket],
                          key=lambda r: (r["stage3_completion_ts"],
                                         r["trigger_id"]))
        if not examples:
            continue
        row = examples[0]
        s = by_id.get(row["related_htf_event_id"])
        if s is None:
            continue
        comp = next((c for c in s.get("_completions", [])
                     if s3.trigger_id(row["trigger_type"], s["event_id"],
                                      c["signal"].completion_index)
                     == row["trigger_id"]), None)
        if comp is None:
            continue
        signal = comp["signal"]
        seq = len(chart_index) + 1
        letter = row["trigger_type"]
        comp_dt = datetime.fromisoformat(row["stage3_completion_ts"])
        title = (f"TRIGGER {letter} — {s3.TRIGGER_NAMES[letter]} | M5 | "
                 f"{comp_dt.strftime('%Y-%m-%d %H:%M')} | "
                 f"{row['direction']}")
        caption2 = (f"bucket: {row['bucket']}"
                    f"  |  completion: {row['stage3_completion_ts'][:16].replace('T', ' ')} UTC"
                    f"  |  arm: {row['arm_ts'][:16].replace('T', ' ') or 'n/a'}"
                    f"  |  first touch: {row['first_touch_ts'][:16].replace('T', ' ') or 'n/a'}"
                    f"  |  scan open through: {row['scan_close_ts'][:16].replace('T', ' ') or 'n/a'}"
                    f"  |  closed by: {row['scan_close_reason']}"
                    f"  |  completion − scan_close: {row['d_completion_minus_scan_close_bars']} bars"
                    f"  |  route_would_form: {row['route_would_form']}")
        markers = [{"_ts": datetime.fromisoformat(d["ltf_ts_utc"]),
                    "tag": d["ltf_plain_tag"],
                    "kind": s3._marker_kind(d), "lo": None, "hi": None}
                   for d in det_by_struct.get(s["event_id"], [])
                   if d.get("ltf_ts_utc")
                   and datetime.fromisoformat(d["ltf_ts_utc"]) <= comp_dt]
        name = f"{seq:03d}_lifecycle_{bucket.lower()}_{row['trigger_id']}.png"
        s3.render_stage3_panel(
            CHARTS_DIR / name, series=m5, anchor=s["_anchor_dt"],
            zone_low=s["zone_low"], zone_high=s["zone_high"], title=title,
            detection_tf="M5", chart_tf="M5",
            htf_context=("D1" if s["src"] == "D1_pack_subset" else "H4"),
            detector_markers=markers, half=60,
            signal_info={"letter": letter, "data": signal.data or {},
                         "entry": float(signal.entry_price),
                         "stop": float(signal.stop_reference),
                         "completion_index": int(signal.completion_index)},
            caption2=caption2)
        chart_index.append({"seq": seq, "filename": name,
                            "bucket": bucket,
                            "trigger_id": row["trigger_id"],
                            "related_htf_event_id": row["related_htf_event_id"],
                            "chart_tf": "M5"})
    summary["charts"] = chart_index

    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[lifecycle] buckets={bucket_counts} unclassified={len(unclassified)}",
          flush=True)
    print(f"[lifecycle] pct_open_scan_all={pct_all:.2f}% "
          f"pct_open_scan_f={pct_f:.2f}%", flush=True)
    print(f"[lifecycle] median completion-scan_close: "
          f"all={summary['median_completion_minus_scan_close_bars']['all']} "
          f"f_only={summary['median_completion_minus_scan_close_bars']['f_only']}",
          flush=True)
    print(f"[lifecycle] charts={len(chart_index)}", flush=True)
    for defect in defects:
        print(f"[lifecycle] DEFECT: {defect}", flush=True)
    print(f"[lifecycle] STAGE3_LIFECYCLE_TIMING: {status}", flush=True)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
