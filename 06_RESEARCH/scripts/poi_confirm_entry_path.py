#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Entry path on confirmed swept POIs — flowchart Step 4 (read-only).

Lead Architect directive: of episodes with LTF confirmation after
first sweep, measure how the PRODUCT entry path treats them —
scan -> route -> place -> fill. Separate "confirmation exists" from
"product admits a trade." No loosening gates, no new entry rules.

Frozen design (stated before running):
  * Population primary: confirmed_within_48 (490 rows); secondary:
    confirmed_within_20 (282 rows). Unconfirmed never in denominators.
  * Instrumented replay (explicitly permitted): the FROZEN p3
    composition driven verbatim (same code path as the product runs)
    with call-through recording wrappers (FR-4 pattern: record-only,
    restored afterwards). Fidelity gate: replay funnel + trades.csv +
    report.json must equal the refresh run1 artifacts EXACTLY (byte
    identity on both files) — else FAIL, stop, report the defect.
    Recorded per engine-POI: scans (first to_bar), routes (bar +
    trigger + entry), placements (ticket, placed_at), fills/closes
    (entry_at, exit, kind), plus the stashed runner's blocked_log
    (poi_id, bar, reason) and intent events.
  * Join (frozen tiers): episode key (direction, round(bounds,3)) on
    both sides (Step-1 key reused by import). Tier A exact key match;
    Tier B same-direction containment (census zone inside exactly one
    engine zone -> join it; several -> smallest-area container,
    tie lowest low; documented); Tier C no-product-POI. Join tiers
    counted (transparency, not tuning).
  * Time qualification (frozen, sweep-anchored): ever_scanned = joined
    POI scanned at least once in-window; ever_routed = route with
    route_bar_ts >= first_sweep_ts; routed_before_sweep tracked
    separately (one-shot consumed — a mechanism, not a failure);
    ever_placed = order with placed_at >= sweep; ever_filled =
    position with entry_at >= sweep. Blocked reasons matched by
    poi_id with event ts >= sweep_ts.
  * Gap taxonomy for confirmed-never-routed-post-sweep (frozen):
    no-product-POI | never-scanned | routed-before-sweep |
    scanned-no-route (the scan finds nothing silently — no per-scan
    reason exists; stated, not filled in).
  * Aggregates: confirm->route over 490 (282 @20); route->place over
    post-sweep-routed; place->fill over post-sweep-placed.

Outputs: results/poi_confirm_entry_path/{lifecycle_per_episode.csv,
summary.json} (+ replay_run1/ artifacts for the fidelity check).
Note: POI_CONFIRM_ENTRY_PATH_NOTE.md (separate step).
LOGIC_CHANGED: NO (wrappers record and call through; restored after).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from smc.config.timeframe import Timeframe
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi

import phase3_structure_funnel as p3
from htf_poi_census import episode_key

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "poi_confirm_entry_path"
LIFECYCLE_CSV = OUT_DIR / "lifecycle_per_episode.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — NOT EDGE"

CONFIRM_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
               "poi_swept_ltf_confirm" / "confirm_per_episode.csv")
POI_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "htf_poi_census" /
           "poi_episodes.csv")
REFRESH_RUN1 = (REPO_ROOT / "06_RESEARCH" / "results" /
                "product_6m_refresh_track_b" / "run1")

CSV_COLUMNS = [
    "episode_id", "tf", "kind_tag", "direction",
    "first_sweep_ts", "confirmed_within_48", "confirmed_within_20",
    "first_confirm_trigger",
    "join_tier", "joined_poi_id",
    "ever_scanned", "first_scan_ts",
    "routed_before_sweep", "ever_routed", "route_ts", "route_trigger",
    "ever_placed", "place_ts_list", "n_orders",
    "ever_filled", "fill_entry_ts", "fill_close_kind",
            "blocked_reasons_post_sweep", "gap_reason",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def _iso(ts) -> str:
    if ts is None:
        return ""
    if isinstance(ts, str):
        return ts
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)


def match_episode(ep_bounds: tuple, engine_pois: list[dict]):
    """Frozen join tiers: exact episode key, else smallest container.

    ep_bounds = (direction_name, low, high); engine_pois = list of
    dicts with direction/low/high/poi_id. Returns (tier, poi_dict|None)
    with tier in {"exact", "containment", "none"}.
    """
    direction, lo, hi = ep_bounds
    key = (direction, round(lo, 3), round(hi, 3))
    for poi in engine_pois:
        if (poi["direction"], round(poi["low"], 3),
                round(poi["high"], 3)) == key:
            return "exact", poi
    containers = [p for p in engine_pois
                  if p["direction"] == direction
                  and p["low"] <= lo and hi <= p["high"]]
    if not containers:
        return "none", None
    best = sorted(containers,
                  key=lambda p: (p["high"] - p["low"], p["low"]))[0]
    return "containment", best


def classify_gap(joined: bool, scanned: bool, routed_post: bool,
                 routed_pre: bool) -> str:
    """Frozen gap taxonomy for confirmed-never-routed-post-sweep."""
    if not joined:
        return "no-product-POI"
    if routed_pre:
        return "routed-before-sweep"
    if not scanned:
        return "never-scanned"
    if not routed_post:
        return "scanned-no-route"
    return ""  # routed: no gap


# --------------------------------------------------------------------------- #
# Instrumented replay (frozen composition, record-only wrappers)
# --------------------------------------------------------------------------- #
def run_instrumented_replay(out_root: Path) -> tuple[dict, dict]:
    """Drive p3.run verbatim with call-through recorders; restore after.

    Returns (p3_summary, recording). Fidelity vs the refresh artifacts
    is checked by the caller (byte identity on trades.csv/report.json
    plus funnel equality) — mismatch means FAIL, not a gap table.
    """
    import smc.backtest.runner as runner_module
    import smc.backtest.orders as orders_module
    import smc.backtest.pipeline_adapter as adapter_module
    from smc.orchestration.engine import PipelineEngine

    recording: dict = {"scans": {}, "routes": [], "places": [],
                       "closes": [], "runners": []}
    saved = {}

    def _save_restore(obj, name):
        saved[(obj, name)] = getattr(obj, name)

    def _restore_all():
        for (obj, name), fn in saved.items():
            setattr(obj, name, fn)

    orig_init = runner_module.BacktestRunner.__init__

    def init_and_stash(self, *a, **k):
        orig_init(self, *a, **k)
        recording["runners"].append(self)

    _save_restore(PipelineEngine, "scan_route")
    _save_restore(adapter_module, "candidate_from_route")
    _save_restore(orders_module.PendingOrderBook, "place")
    _save_restore(runner_module.BacktestRunner, "_record_close")
    _save_restore(runner_module.BacktestRunner, "__init__")

    true_scan = saved[(PipelineEngine, "scan_route")]
    true_bridge = saved[(adapter_module, "candidate_from_route")]
    true_place = saved[(orders_module.PendingOrderBook, "place")]
    true_record = saved[(runner_module.BacktestRunner, "_record_close")]

    def scan_and_record(self, poi, candles, swings, from_bar=None,
                        to_bar=None, **kw):
        info = recording["scans"].setdefault(
            poi.id, {"low": poi.zone.bottom, "high": poi.zone.top,
                     "direction": poi.zone.direction.name,
                     "first_to_bar": to_bar, "n_scans": 0})
        info["n_scans"] += 1
        if to_bar is not None and (info["first_to_bar"] is None
                                   or to_bar < info["first_to_bar"]):
            info["first_to_bar"] = to_bar
        return true_scan(self, poi, candles, swings, from_bar=from_bar,
                         to_bar=to_bar, **kw)

    def bridge_and_record(route, *a, **kw):
        recording["routes"].append({
            "poi_id": route.poi.id,
            "bar": route.bar,
            "trigger": str(getattr(route.signal.trigger, "value",
                                   route.signal.trigger)),
            "entry": float(route.signal.entry_price),
        })
        return true_bridge(route, *a, **kw)

    def place_and_record(self, **kw):
        order = true_place(self, **kw)
        recording["places"].append({
            "ticket": order.ticket,
            "poi_id": kw.get("poi_id"),
            "placed_bar": kw.get("placed_bar"),
            "placed_at": _iso(kw.get("placed_at")),
        })
        return order

    def record_and_record(self, record, *, bar_index):
        recording["closes"].append({
            "ticket": record.position.ticket,
            "poi_id": record.position.poi_id,
            "entry_at": _iso(record.position.entry_at),
            "exit_at": _iso(record.exit_at),
            "kind": record.kind,
            "win": bool(record.win),
        })
        return true_record(self, record, bar_index=bar_index)

    PipelineEngine.scan_route = scan_and_record
    adapter_module.candidate_from_route = bridge_and_record
    orders_module.PendingOrderBook.place = place_and_record
    runner_module.BacktestRunner._record_close = record_and_record
    runner_module.BacktestRunner.__init__ = init_and_stash
    try:
        # SAME explicit CostConfig as the refresh runs (single source of
        # truth — a missing cost_config would silently price zero-cost
        # and trip the fidelity gate, as it did once during the build).
        from product_baseline_pilot import PILOT_COSTS
        args = argparse.Namespace(
            tag="replay_run1", out_root=str(out_root),
            load_from="2025-05-01", exec_from="2025-06-01",
            exec_to="2025-11-30", cost_config=PILOT_COSTS)
        summary = p3.run(args)
    finally:
        _restore_all()
    return summary, recording


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (CONFIRM_CSV, POI_CSV):
        if not path.exists():
            raise SystemExit(f"required input missing: {path}")

    replay_root = OUT_DIR / "replay_run1"
    print("[step4] instrumented replay (frozen composition) ...", flush=True)
    summary, rec = run_instrumented_replay(replay_root)

    # ---- Fidelity gate: replay MUST equal the refresh run1 artifacts --- #
    defects: list[str] = []
    byte_ok: dict = {}
    for name in ("trades.csv", "report.json"):
        f1, f2 = REFRESH_RUN1 / name, replay_root / name
        if f1.exists() and f2.exists():
            same = f1.read_bytes() == f2.read_bytes()
            byte_ok[name] = same
            if not same:
                defects.append(f"{name} bytes differ replay-vs-refresh")
        else:
            byte_ok[name] = None
            defects.append(f"{name} absent for fidelity check")
    for key in ("armed", "routes", "placed", "fills", "trades"):
        if summary.get(key) != json.loads(
                (REFRESH_RUN1 / "funnel_summary.json").read_text(
                    encoding="utf-8")).get(key):
            defects.append(f"funnel.{key} differs replay-vs-refresh: "
                           f"{summary.get(key)}")
    status = "PASS" if not defects else "FAIL"

    # ---- M5 series (IDENTICAL slice to the replay: load + exec filter) -- #
    # Bar indices recorded by the wrappers index the replay's EXEC m5
    # list, so this rebuild must match it bar-for-bar (same load slice,
    # same resample, same exec filter as phase3_structure_funnel.run).
    # Verified below against the replay's own window start/end.
    m1_all = load_ohlcv_parquet(
        str(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"), Timeframe.M1)
    _load_from = datetime(2025, 5, 1, tzinfo=timezone.utc)
    _exec_from = datetime(2025, 6, 1, tzinfo=timezone.utc)
    _exec_to = datetime(2025, 11, 30, tzinfo=timezone.utc)
    m1 = [c for c in m1_all
          if _load_from <= c.timestamp <= _exec_to + timedelta(days=1)]
    from smc.data.resample import resample_multi as _rs
    m5 = [c for c in _rs(m1, [Timeframe.M5])[Timeframe.M5]
          if _exec_from <= c.timestamp
          <= _exec_to + timedelta(days=1) - timedelta(minutes=1)]
    m5_ts = [c.timestamp.isoformat() for c in m5]
    # Mapping-validity proof: this list must equal the replay's own exec
    # series (same load slice + same exec filter as the composition).
    # NOTE: the window starts 2025-06-01T22:00, not 00:00 — June 1 2025
    # was a Sunday (market closed until the 22:00 UTC open).
    _replay_window = json.loads(
        (OUT_DIR / "replay_run1" / "funnel_summary.json").read_text(
            encoding="utf-8"))["window"]
    assert m5_ts[0] == _replay_window["start"], (m5_ts[0], _replay_window)
    assert m5_ts[-1] == _replay_window["end"], (m5_ts[-1], _replay_window)
    print(f"[step4] M5 mapping bars={len(m5)} "
          f"({m5_ts[0][:16]} -> {m5_ts[-1][:16]}) == replay series",
          flush=True)

    def ts_of_bar(bar_index) -> str:
        if bar_index is None or not (0 <= int(bar_index) < len(m5_ts)):
            return ""
        return m5_ts[int(bar_index)]

    # ---- Engine POIs (scan snapshots) ------------------------------------ #
    engine_pois = [{"poi_id": pid, "direction": info["direction"],
                    "low": info["low"], "high": info["high"]}
                   for pid, info in rec["scans"].items()]
    scans_by_poi = {pid: info for pid, info in rec["scans"].items()}
    routes_by_poi: dict[str, list[dict]] = {}
    for r in rec["routes"]:
        routes_by_poi.setdefault(r["poi_id"], []).append(r)
    places_by_poi: dict[str, list[dict]] = {}
    for p in rec["places"]:
        if p["poi_id"] is not None:
            places_by_poi.setdefault(p["poi_id"], []).append(p)
    closes_by_poi: dict[str, list[dict]] = {}
    for c in rec["closes"]:
        if c["poi_id"] is not None:
            closes_by_poi.setdefault(c["poi_id"], []).append(c)
    blocked: list[dict] = []
    intents_by_poi: dict[str, Counter] = {}
    for runner in rec["runners"]:
        for b in getattr(runner, "blocked_log", []):
            blocked.append({"poi_id": b.poi_id, "bar": b.bar_index,
                            "reason": b.blocked_by,
                            "ts": ts_of_bar(b.bar_index)})
        for ev in getattr(getattr(runner, "intents", None), "events", None) or []:
            if isinstance(ev, dict) and ev.get("poi_id"):
                intents_by_poi.setdefault(ev["poi_id"], Counter())[
                    str(ev.get("kind", ev.get("event", "?")))] += 1

    # ---- Confirm rows + episode bounds ------------------------------------ #
    with open(CONFIRM_CSV, encoding="utf-8", newline="") as f:
        confirm_all = list(csv.DictReader(f))
    # Population (frozen): confirmed_within_48 ONLY. Unconfirmed rows
    # never enter any denominator, join, or gap table — they are not
    # listed anywhere in the outputs (147 rows excluded, counted here).
    confirm_rows = {r["episode_id"]: r for r in confirm_all
                    if r.get("confirmed_within_48") == "True"}
    print(f"[step4] confirm book={len(confirm_all)} confirmed_48="
          f"{len(confirm_rows)} (unconfirmed excluded entirely)",
          flush=True)
    with open(POI_CSV, encoding="utf-8", newline="") as f:
        poi_rows = {r["episode_id"]: r for r in csv.DictReader(f)}

    rows_out: list[dict] = []
    for eid, crow in sorted(confirm_rows.items()):
        prow = poi_rows.get(eid, {})
        sweep_ts = crow.get("first_sweep_ts") or ""
        lo = float(prow.get("zone_low", "nan")) if prow.get("zone_low") \
            else None
        hi = float(prow.get("zone_high", "nan")) if prow.get("zone_high") \
            else None
        direction = (prow.get("direction") or crow.get("direction") or "")
        tier, joined = ("none", None)
        if lo is not None and hi is not None and direction:
            tier, joined = match_episode((direction, lo, hi), engine_pois)
        scan = scans_by_poi.get(joined["poi_id"]) if joined else None
        proutes = routes_by_poi.get(joined["poi_id"], []) if joined else []
        proutes_post = [r for r in proutes
                        if ts_of_bar(r["bar"]) >= sweep_ts] if sweep_ts else []
        routed_pre = any(ts_of_bar(r["bar"]) < sweep_ts for r in proutes) \
            if sweep_ts else False
        first_route = sorted(
            proutes_post,
            key=lambda r: (ts_of_bar(r["bar"]),
                           r["trigger"]))[0] if proutes_post else None
        porders = places_by_poi.get(joined["poi_id"], []) if joined else []
        porders_post = [p for p in porders
                        if p["placed_at"] and p["placed_at"] >= sweep_ts]
        closes = closes_by_poi.get(joined["poi_id"], []) if joined else []
        fills_post = [c for c in closes
                      if c["entry_at"] and c["entry_at"] >= sweep_ts]
        reasons = sorted({b["reason"] for b in blocked
                          if joined and b["poi_id"] == joined["poi_id"]
                          and b["ts"] and b["ts"] >= sweep_ts})
        gap = ""
        if not proutes_post:
            gap = classify_gap(
                joined is not None, scan is not None, False, routed_pre)
        rows_out.append({
            "episode_id": eid, "tf": crow.get("tf"),
            "kind_tag": crow.get("kind_tag"),
            "direction": crow.get("direction"),
            "first_sweep_ts": sweep_ts,
            "confirmed_within_48": crow.get("confirmed_within_48"),
            "confirmed_within_20": crow.get("confirmed_within_20"),
            "first_confirm_trigger": crow.get("first_confirm_trigger"),
            "join_tier": tier,
            "joined_poi_id": joined["poi_id"] if joined else "",
            "ever_scanned": scan is not None,
            "first_scan_ts": (ts_of_bar(scan["first_to_bar"])
                              if scan else ""),
            "routed_before_sweep": routed_pre,
            "ever_routed": bool(proutes_post),
            "route_ts": (ts_of_bar(first_route["bar"])
                         if first_route else ""),
            "route_trigger": (first_route["trigger"]
                              if first_route else ""),
            "ever_placed": bool(porders_post),
            "place_ts_list": ";".join(p["placed_at"] for p in porders_post),
            "n_orders": len(porders_post),
            "ever_filled": bool(fills_post),
            "fill_entry_ts": (fills_post[0]["entry_at"]
                              if fills_post else ""),
            "fill_close_kind": (fills_post[0]["kind"]
                                if fills_post else ""),
            "blocked_reasons_post_sweep": ";".join(reasons),
            "gap_reason": gap,
        })

    with open(LIFECYCLE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows_out:
            writer.writerow({c: ("" if r.get(c) is None else r.get(c))
                             for c in CSV_COLUMNS})

    # ---- Aggregates ------------------------------------------------------ #
    def _median(vals):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return None
        mid = len(vals) // 2
        if len(vals) % 2:
            return vals[mid]
        return (vals[mid - 1] + vals[mid]) / 2.0

    confirmed = [r for r in rows_out if r["confirmed_within_48"] == "True"]
    confirmed20 = [r for r in rows_out if r["confirmed_within_20"] == "True"]
    routed = [r for r in confirmed if r["ever_routed"]]
    placed = [r for r in routed if r["ever_placed"]]
    filled = [r for r in placed if r["ever_filled"]]

    def agg(sub):
        n = len(sub)
        rr = [r for r in sub if r["ever_routed"]]
        pp = [r for r in rr if r["ever_placed"]]
        ff = [r for r in pp if r["ever_filled"]]
        return {
            "n_confirmed": n,
            "join_tiers": dict(Counter(r["join_tier"] for r in sub)),
            "routed_n": len(rr),
            "confirm_to_route_rate": (round(len(rr) / n, 4) if n else None),
            "placed_n": len(pp),
            "route_to_place_rate": (round(len(pp) / len(rr), 4)
                                    if rr else None),
            "filled_n": len(ff),
            "place_to_fill_rate": (round(len(ff) / len(pp), 4)
                                   if pp else None),
            "gap_reasons": dict(Counter(r["gap_reason"] for r in sub
                                        if not r["ever_routed"])),
            "blocked_reasons": dict(Counter(
                reason for r in sub for reason in
                (r["blocked_reasons_post_sweep"].split(";")
                 if r["blocked_reasons_post_sweep"] else []))),
            "route_triggers": dict(Counter(r["route_trigger"] for r in rr
                                           if r["route_trigger"])),
        }

    summary = {
        "banner": BANNER,
        "frozen": {
            "population": ("confirmed_within_48 (490 primary) / "
                           "confirmed_within_20 (282 secondary); unconfirmed "
                           "never in denominators"),
            "replay": ("phase3_structure_funnel.run driven verbatim "
                       "(same window/config as the 6m refresh) with "
                       "call-through recorders (scans/routes/places/closes "
                       "+ stashed runner blocked_log); restored after"),
            "fidelity_gate": ("replay funnel + trades.csv + report.json "
                              "must equal refresh run1 EXACTLY "
                              "(byte identity) — else FAIL"),
            "join": ("episode key both sides; Tier A exact, Tier B "
                     "smallest-area same-direction container, Tier C none"),
            "time_rule": ("ever_routed/placed/filled qualified at/after "
                          "first_sweep_ts (route_bar/placed_at/entry_at); "
                          "routed-before-sweep tracked as one-shot "
                          "consumed; blocked reasons matched by poi_id "
                          "with event ts >= sweep"),
            "gap_taxonomy": ("no-product-POI | never-scanned | "
                             "routed-before-sweep | scanned-no-route "
                             "(scans find nothing silently — stated)"),
        },
        "fidelity": {"byte_check_trades_csv": byte_ok.get("trades.csv"),
                     "byte_check_report_json": byte_ok.get("report.json"),
                     "defects": defects, "status": status},
        "primary_48": agg(confirmed),
        "secondary_20": agg(confirmed20),
        "limitations": [
            "Containment joins (Tier B) match census geometry inside "
            "wider engine zones; direction-only, no tolerance invented.",
            "Blocked reasons come from the runner log (placement-time "
            "gates); scan-quiet has no reason by construction.",
            "Intent lifecycle contributes funnel counts (see binding "
            "report); per-POI intent linkage only where event payloads "
            "carry it.",
            "No gate, no threshold, no live rule follows (see note).",
        ],
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[step4] fidelity={status} "
          f"routed={summary['primary_48']['routed_n']}/"
          f"{summary['primary_48']['n_confirmed']} "
          f"placed={summary['primary_48']['placed_n']} "
          f"filled={summary['primary_48']['filled_n']}", flush=True)
    print(f"[step4] wrote {OUT_DIR}", flush=True)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
