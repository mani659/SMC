#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Seek/scan contract redesign (Option B) — implementation measurement.

Lead Architect implementation directive (2026-10-05). Runs the accepted
design's new seek/scan contract (design §3 R1–R5, implemented in
``smc/orchestration/engine.py`` + ``smc/backtest/pipeline_adapter.py``)
over the SAME frozen window and inputs as the Stage 3 visibility /
lifecycle packs (exec 2025-06-01 → 2025-11-30 UTC, warm-up 2025-03-01),
and reports success metrics M1–M5 against the accepted baselines in
``06_RESEARCH/STAGE3_LIFECYCLE_TIMING_REPORT.md``.

Method (identification only — NO expectancy / PnL / edge claims):
  - Pass OLD: the accepted instrumented §5 replay
    (``stage3_trigger_visibility.observe_routes_instrumented``) — the
    before-facts + the M4a armed-count invariant baseline.
  - Pass NEW: ``observe_seek_scan_contract`` — per-bar mirror of the
    production ``PipelineAdapter`` with the redesign (posture
    classification at arm, arm-bar §5 skip, REVALIDATION re-entry gate
    via ``market_reentered_zone``, touch no longer terminates the seek,
    give-up retirement for every posture, one-shot route retirement).
  - Both replays share the same structures, series, arm anchors and
    give-up horizon (``poi_give_up_bars()`` = 20, locked).

Buckets (NEW contract, exactly one per completion):
  OPEN_SCAN     completion at or before the last bar the seek was open
                (visible + routable under the new contract)
  HIDDEN_*      completions the new contract still does not surface,
                each with an explicit machine-checked reason
  NEVER_ARMED / DATA_GAP / UNCLASSIFIED (defects — expected 0)
"""

from __future__ import annotations

import bisect
import csv
import hashlib
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

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "seek_scan_implementation"
EVENTS_CSV = OUT_DIR / "events_seek_scan.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

STAGE3_LEDGER_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                     "stage3_trigger_visibility" / "events_stage3_triggers.csv")
OLD_LIFECYCLE_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                     "stage3_lifecycle_timing" / "events_lifecycle.csv")

CSV_COLUMNS = [
    "trigger_id", "trigger_type", "direction", "related_htf_event_id",
    "structure_close_ts", "arm_ts", "completion_ts",
    "posture", "revalidated_ts", "last_scanned_ts",
    "pop_reason_new", "route_new", "route_bar_new",
    "d_completion_minus_last_scanned_bars",
    "bucket_new", "hidden_reason_new",
    "bucket_old", "route_would_form_old",
]

HIDDEN_REASONS = [
    "violation_after_live_seek",     # post-arm adverse close before completion
    "never_reentered_arm_violation",  # VIOLATION_AT_ARM, no re-entry, gave up
    "give_up_before_completion",
    "awaiting_zone_reentry",          # completion before the re-entry bar
    "routed_earlier",                 # one-shot consumed by an earlier route
    "open_to_series_end",
]


# --------------------------------------------------------------------------- #
# NEW-contract replay (per-bar mirror of the redesigned PipelineAdapter)
# --------------------------------------------------------------------------- #
def observe_seek_scan_contract(structures: list[dict], m5) -> dict[str, dict]:
    """Per-bar replay of the production adapter under the NEW contract.

    Mirrors ``PipelineAdapter.generate_candidates`` exactly: give-up
    retirement for every posture → seek gate (posture + re-entry latch +
    §5 state + deadline) → scan (cursor resume) → §5 feed AFTER the scan
    (arm candle skipped by the engine for non-CLEAN postures).
    """
    from smc.backtest.series_state import SeriesState
    from smc.core.enums import POIState
    from smc.orchestration.engine import PipelineEngine, SeekPosture
    from smc.core.poi import POI
    from smc.core.zone import Zone
    from smc.config.model_type import ModelType
    from smc.risk.fill_regime_policy import market_reentered_zone

    stamps = [c.timestamp for c in m5]
    for s in structures:
        arm = bisect.bisect_left(stamps, s["_anchor_dt"])
        if arm >= len(m5):
            s["arm_bar"] = None
            continue
        s["arm_bar"] = arm
        s["_deadline"] = min(arm + ltf.LA_M5_BARS, len(m5) - 1)
        s["_gate"] = {"posture": None, "revalidated_bar": None,
                      "last_scanned": None, "pop_bar": None,
                      "pop_reason": None, "route_bar": None,
                      "tested_bar": None, "routes": 0}

    by_arm: dict[int, list[dict]] = {}
    for s in structures:
        if s.get("arm_bar") is not None:
            by_arm.setdefault(s["arm_bar"], []).append(s)

    engine = PipelineEngine()
    state = SeriesState(Timeframe.M5)
    active: dict[str, dict] = {}
    order: list[str] = []

    def _arm_due(bar: int) -> None:
        for s in by_arm.get(bar, ()):
            poi = POI(zone=Zone(bottom=float(s["zone_low"]),
                                top=float(s["zone_high"]),
                                direction=ltf.Direction[s["direction"]],
                                timeframe=Timeframe.H4),
                      models=[ModelType.M8], m8_kind=s.get("kind") or None)
            engine.arm_at(poi, bar, arm_candle=m5[bar])
            s["_gate"]["posture"] = engine.episode(poi).posture.value
            s["_poi"] = poi
            s["_cursor"] = None
            active[poi.id] = s
            order.append(poi.id)

    for bar, candle in enumerate(m5):
        state.extend(candle)
        _arm_due(bar)
        atr_values = state.atr_values
        for poi_id in list(order):
            s = active.get(poi_id)
            if s is None:
                continue
            gate = s["_gate"]
            poi = s["_poi"]
            episode = engine.episode(poi)

            # Give-up retirement (R4.1a — every posture; scan bookkeeping).
            if bar > s["_deadline"]:
                if gate["pop_reason"] is None and gate["route_bar"] is None:
                    gate["pop_bar"] = bar
                    gate["pop_reason"] = "give_up"
                active.pop(poi_id, None)
                order.remove(poi_id)
                continue

            # Seek gate — mirror of adapter._may_route(poi, state, bar, bar).
            cur = engine.state_machine.current(poi)
            may = False
            if cur.value in (POIState.FRESH.value, POIState.TESTED.value):
                if (episode.posture is SeekPosture.VIOLATION_AT_ARM
                        and episode.revalidated_bar is None):
                    atr = (atr_values[bar]
                           if bar < len(atr_values) else None)
                    if atr is not None and atr > 0:
                        zone = poi.zone
                        if market_reentered_zone(
                                zone.direction, float(zone.bottom),
                                float(zone.top), None,
                                float(candle.close), atr):
                            episode.revalidated_bar = bar
                            gate["revalidated_bar"] = bar
                            s["_cursor"] = bar  # scan starts at re-entry
                            may = True
                elif cur.value == POIState.FRESH.value:
                    may = True
                else:
                    may = bar <= episode.arm_bar + ltf.LA_M5_BARS

            if may:
                gate["last_scanned"] = bar
                route = engine.scan_route(
                    poi, state.candles, state.swings,
                    to_bar=bar, scan_from=s["_cursor"],
                    evaluation_candles=state.candles,
                    evaluation_swings=state.swings, hints=state)
                if route is not None:
                    gate["route_bar"] = route.bar
                    gate["routes"] += 1
                    s["route"] = route
                    active.pop(poi_id, None)
                    order.remove(poi_id)
                    continue
                s["_cursor"] = bar + 1

            # §5 feed AFTER the scan (adapter order; engine skips the arm
            # candle for non-CLEAN postures).
            result = engine.feed_bar(poi, candle)
            if result == POIState.VIOLATED.value:
                if gate["pop_reason"] is None and gate["route_bar"] is None:
                    gate["pop_bar"] = bar
                    gate["pop_reason"] = "violated"
                active.pop(poi_id, None)
                order.remove(poi_id)
            elif (result == POIState.TESTED.value
                    and gate["tested_bar"] is None):
                gate["tested_bar"] = bar

    return {s["event_id"]: s["_gate"] for s in structures
            if s.get("_gate") is not None}


# --------------------------------------------------------------------------- #
# Bucketing (NEW contract)
# --------------------------------------------------------------------------- #
def assign_bucket_new(*, join_ok: bool, completion_bar: int | None,
                      arm_bar: int | None, gate: dict | None,
                      route_bar: int | None, completion_is_route: bool
                      ) -> tuple[str, str | None]:
    from smc.orchestration.engine import SeekPosture  # local: enum compare
    """(bucket, hidden_reason) — exactly one per completion."""
    if not join_ok or completion_bar is None:
        return "DATA_GAP", "join_or_bar_missing"
    if arm_bar is None or gate is None:
        return "NEVER_ARMED", "never_armed"
    last = gate.get("last_scanned")
    if last is not None and completion_bar <= last:
        return "OPEN_SCAN", None
    # Hidden: the seek was closed (or gated) before the completion bar.
    if gate.get("route_bar") is not None:
        # R4.1c/R5: the one-shot consumed this episode on an earlier route —
        # the seek ended in SUCCESS; a later completion cannot route again.
        return "HIDDEN", "routed_earlier"
    pop_reason = gate.get("pop_reason")
    posture = gate.get("posture")
    revalidated = gate.get("revalidated_bar")
    if completion_is_route:
        return "UNCLASSIFIED", "route_completion_not_scanned"
    if pop_reason == "violated":
        return "HIDDEN", "violation_after_live_seek"
    if pop_reason == "give_up":
        if posture == SeekPosture.VIOLATION_AT_ARM.value and revalidated is None:
            return "HIDDEN", "never_reentered_arm_violation"
        return "HIDDEN", "give_up_before_completion"
    if pop_reason is None:
        if posture == SeekPosture.VIOLATION_AT_ARM.value and revalidated is None:
            return "HIDDEN", "awaiting_zone_reentry"
        return "HIDDEN", "open_to_series_end"
    return "UNCLASSIFIED", f"unknown_pop_{pop_reason}"


def pctl(values: list, q: float) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    data = sorted(float(v) for v in clean)
    if len(data) == 1:
        return data[0]
    pos = q * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    frac = pos - lo
    return data[lo] * (1.0 - frac) + data[hi] * frac


def distribution(values: list[float | None]) -> dict:
    clean = [v for v in values if v is not None]
    return {"n_used": len(clean), "n_null": len(values) - len(clean),
            "p25": pctl(clean, 0.25), "median": pctl(clean, 0.50),
            "p75": pctl(clean, 0.75)}


# --------------------------------------------------------------------------- #
# Inputs (reused from disk — same loaders as the accepted packs)
# --------------------------------------------------------------------------- #
def load_structures() -> list[dict]:
    structures: list[dict] = []
    with open(ltf.H4_EVENTS_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
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
    if ltf.D1_EVENTS_CSV.exists():
        with open(ltf.D1_EVENTS_CSV, encoding="utf-8") as f:
            d1_rows = [r for r in csv.DictReader(f)
                       if r["event_type"] == "poi_raw"]
        for r in ltf._spread(sorted(d1_rows, key=lambda r: r["ts_utc"]),
                             ltf.MAX_D1_SUBSET):
            ts = datetime.fromisoformat(r["ts_utc"])
            if not (ltf.EXEC_START <= ts <= ltf.EXEC_END):
                continue
            structures.append({
                "event_id": r["event_id"], "plain_tag": r["plain_tag"].upper(),
                "direction": r["direction"], "zone_low": float(r["zone_low"]),
                "zone_high": float(r["zone_high"]), "ts_utc": r["ts_utc"],
                "_htf_dt": ts, "_anchor_dt": ts + timedelta(hours=24),
                "kind": r["kind"], "src": "D1_pack_subset", "route": None,
            })
    structures.sort(key=lambda s: (s["ts_utc"], s["event_id"]))
    return structures


def load_stage3_ledger() -> list[dict]:
    with open(STAGE3_LEDGER_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_old_lifecycle() -> dict[str, dict]:
    with open(OLD_LIFECYCLE_CSV, encoding="utf-8") as f:
        return {r["trigger_id"]: r for r in csv.DictReader(f)}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ltf.install_deterministic_poi_ids()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Series (same window/rule as the Stage 3 pack) ------------------ #
    m1 = load_ohlcv_parquet(ltf.DATA_PARQUET)
    m1_win = [c for c in m1
              if c.timestamp >= ltf.WARM_START
              and c.timestamp <= datetime(2025, 12, 1, tzinfo=timezone.utc)]
    by_tf = resample_multi(m1_win, [Timeframe.M5])
    m5 = by_tf[Timeframe.M5]
    m5_ts = [c.timestamp for c in m5]
    m5_index = {ts: i for i, ts in enumerate(m5_ts)}
    print(f"[impl] M5={len(m5)}", flush=True)

    # ---- OLD replay (before-facts + armed invariant baseline) ----------- #
    structures_old = load_structures()
    old_gate = s3.observe_routes_instrumented(structures_old, m5)
    armed_old = {sid for sid, g in old_gate.items()
                 if structures_old and True}
    armed_old_bars = {s["event_id"]: s["arm_bar"] for s in structures_old}
    n_armed_old = sum(1 for v in armed_old_bars.values() if v is not None)
    print(f"[impl] OLD replay: structures={len(structures_old)} "
          f"armed={n_armed_old}", flush=True)

    # ---- NEW replay ------------------------------------------------------ #
    structures_new = load_structures()
    new_gate = observe_seek_scan_contract(structures_new, m5)
    new_bars = {s["event_id"]: s["arm_bar"] for s in structures_new}
    new_by_id = {s["event_id"]: s for s in structures_new}
    n_armed_new = sum(1 for v in new_bars.values() if v is not None)
    print(f"[impl] NEW replay: structures={len(structures_new)} "
          f"armed={n_armed_new}", flush=True)

    # ---- Per-completion rows -------------------------------------------- #
    ledger = load_stage3_ledger()
    old_rows = load_old_lifecycle()
    rows: list[dict] = []
    for r in ledger:
        sid = r["related_htf_event_id"]
        structure = new_by_id.get(sid)
        join_ok = structure is not None
        completion_dt = datetime.fromisoformat(r["bar_time_utc"])
        completion_bar = m5_index.get(completion_dt)
        gate = new_gate.get(sid) if join_ok else None
        arm_bar = new_bars.get(sid) if join_ok else None

        # One-shot cross-check: the old ledger's routed rows are exactly the
        # completions whose completion bar equals the old route bar.
        old_row = old_rows.get(r["trigger_id"], {})
        route_would_form_old = old_row.get("route_would_form", "")

        is_old_routed = route_would_form_old == "yes"
        new_route_bar = gate.get("route_bar") if gate else None
        routed_this_completion = (
            new_route_bar is not None and completion_bar == new_route_bar)

        bucket_new, hidden_reason = assign_bucket_new(
            join_ok=join_ok, completion_bar=completion_bar,
            arm_bar=arm_bar, gate=gate, route_bar=new_route_bar,
            completion_is_route=False)

        arm_ts = (m5_ts[arm_bar].isoformat()
                  if arm_bar is not None else "")
        reval_bar = gate.get("revalidated_bar") if gate else None
        last_bar = gate.get("last_scanned") if gate else None
        close_dt = structure["_anchor_dt"] if join_ok else None

        rows.append({
            "trigger_id": r["trigger_id"],
            "trigger_type": r["trigger_type"],
            "direction": r["direction"],
            "related_htf_event_id": sid,
            "structure_close_ts": close_dt.isoformat() if close_dt else "",
            "arm_ts": arm_ts,
            "completion_ts": completion_dt.isoformat(),
            "posture": (gate.get("posture") or "") if gate else "",
            "revalidated_ts": (m5_ts[reval_bar].isoformat()
                               if reval_bar is not None else ""),
            "last_scanned_ts": (m5_ts[last_bar].isoformat()
                                if last_bar is not None else ""),
            "pop_reason_new": (gate.get("pop_reason") or "") if gate else "",
            "route_new": ("yes" if new_route_bar is not None else "no"),
            "_routed_this_completion": routed_this_completion,
            "route_bar_new": (m5_ts[new_route_bar].isoformat()
                              if new_route_bar is not None else ""),
            "d_completion_minus_last_scanned_bars": (
                completion_bar - last_bar
                if completion_bar is not None and last_bar is not None else None),
            "bucket_new": bucket_new,
            "hidden_reason_new": hidden_reason or "",
            "bucket_old": old_row.get("bucket", ""),
            "route_would_form_old": route_would_form_old,
            "_completion_bar": completion_bar,
            "_old_routed": is_old_routed,
            "_old_route_bar": (old_row.get("scan_close_event_ts") or ""),
        })

    # ---- Sanity + metrics ------------------------------------------------ #
    defects: list[str] = []
    data_gap = [r["trigger_id"] for r in rows if r["bucket_new"] == "DATA_GAP"]
    never_armed = [r["trigger_id"] for r in rows
                   if r["bucket_new"] == "NEVER_ARMED"]
    unclassified = [r["trigger_id"] for r in rows
                    if r["bucket_new"] == "UNCLASSIFIED"]

    total = len(rows)
    open_rows = [r for r in rows if r["bucket_new"] == "OPEN_SCAN"]
    hidden = [r for r in rows if r["bucket_new"] == "HIDDEN"]
    pct_open_all = 100.0 * len(open_rows) / total if total else 0.0
    f_rows = [r for r in rows if r["trigger_type"] == "F"]
    f_open = [r for r in open_rows if r["trigger_type"] == "F"]
    pct_open_f = 100.0 * len(f_open) / len(f_rows) if f_rows else 0.0

    hidden_reason_counts: dict[str, int] = {}
    for r in hidden:
        hidden_reason_counts[r["hidden_reason_new"]] = \
            hidden_reason_counts.get(r["hidden_reason_new"], 0) + 1

    # M2 — the two previously routed rows remain routable, same bars.
    old_routed_rows = [r for r in rows if r["_old_routed"]]
    m2_pass = (len(old_routed_rows) == 2
               and all(r["route_new"] == "yes" for r in old_routed_rows)
               and all(r["bucket_new"] == "OPEN_SCAN"
                       for r in old_routed_rows))
    m2_detail = {
        "expected": 2, "found": len(old_routed_rows),
        "rows": {r["trigger_id"]: {
            "route_new": r["route_new"],
            "route_bar_new": r["route_bar_new"],
            "bucket_new": r["bucket_new"],
            "completion_ts": r["completion_ts"]} for r in old_routed_rows},
        "pass": m2_pass,
    }

    # M3 — median(completion − last_scanned) for previously CLOSED rows.
    prev_closed = [r for r in rows
                   if r["bucket_old"] in ("CLOSED_TOUCH", "CLOSED_VIOL")]
    m3_deltas = [r["d_completion_minus_last_scanned_bars"]
                 for r in prev_closed]
    m3_visible = [r for r in prev_closed if r["bucket_new"] == "OPEN_SCAN"]
    m3 = {
        "n_previously_closed": len(prev_closed),
        "now_open_scan": len(m3_visible),
        "distribution_completion_minus_last_scanned_bars":
            distribution(m3_deltas),
        "median": pctl(m3_deltas, 0.50),
        "pass_le_2": (pctl(m3_deltas, 0.50) is not None
                      and pctl(m3_deltas, 0.50) <= 2.0),
    }

    # M4 — armed-count invariant (arming rule untouched).
    arm_mismatch = [sid for sid in armed_old_bars
                    if armed_old_bars.get(sid) != new_bars.get(sid)]
    m4a_pass = (n_armed_old == n_armed_new and not arm_mismatch)
    routes_new = sum(g.get("routes", 0) for g in new_gate.values())
    routes_old = sum(1 for g in old_gate.values()
                     if g.get("route_bar") is not None)
    m4 = {
        "armed_count_old": n_armed_old,
        "armed_count_new": n_armed_new,
        "arm_bar_mismatches": arm_mismatch[:10],
        "pass": m4a_pass,
        "routes_old_replay": routes_old,
        "routes_new_replay": routes_new,
        "routes_per_armed_share_new": round(routes_new / n_armed_new, 4)
        if n_armed_new else None,
        "selectivity_alarm_over_50pct": bool(
            n_armed_new and routes_new / n_armed_new > 0.5),
    }

    # M5 — one-shot invariant: at most one route per episode (the replay
    # retires on route, so gate['routes'] <= 1 must hold everywhere).
    multi_route_gates = [sid for sid, g in new_gate.items()
                         if g.get("routes", 0) > 1]
    m5_pass = not multi_route_gates
    m5 = {
        "multi_route_episodes": multi_route_gates[:10],
        "n_multi_route": len(multi_route_gates),
        "pass": m5_pass,
    }

    if data_gap:
        defects.append(f"DATA_GAP rows: {data_gap}")
    if never_armed:
        defects.append(f"NEVER_ARMED rows: {never_armed}")
    if unclassified:
        defects.append(f"UNCLASSIFIED rows: {unclassified}")
    if not m2_pass:
        defects.append(f"M2 regression: {m2_detail}")
    if not m4a_pass:
        defects.append("M4a armed-count invariant FAIL")
    if not m5_pass:
        defects.append("M5 one-shot invariant FAIL")
    status = "PASS" if not defects else "FAIL"

    funnel_old = {
        "open_scan": sum(1 for r in rows if r["bucket_old"] == "OPEN_SCAN"),
        "closed_touch": sum(1 for r in rows
                            if r["bucket_old"] == "CLOSED_TOUCH"),
        "closed_viol": sum(1 for r in rows
                           if r["bucket_old"] == "CLOSED_VIOL"),
    }
    posture_counts: dict[str, int] = {}
    for g in new_gate.values():
        posture_counts[g.get("posture") or "none"] = \
            posture_counts.get(g.get("posture") or "none", 0) + 1

    summary = {
        "window": {"exec_start_utc": ltf.EXEC_START.isoformat(),
                   "exec_end_utc": ltf.EXEC_END.isoformat(),
                   "warm_start_utc": ltf.WARM_START.isoformat()},
        "design_note": "06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md",
        "total_completions": total,
        "bucket_counts_new": {
            "OPEN_SCAN": len(open_rows),
            "HIDDEN": len(hidden),
            "DATA_GAP": len(data_gap),
            "NEVER_ARMED": len(never_armed),
            "UNCLASSIFIED": len(unclassified),
        },
        "m1_open_scan_share": {
            "all_pct": round(pct_open_all, 2),
            "f_only_pct": round(pct_open_f, 2),
            "baseline_pct": 0.76,
            "target_min_pct": 80.0,
            "pass_ge_80": pct_open_all >= 80.0,
        },
        "hidden_reason_counts": hidden_reason_counts,
        "m2_prev_routes_preserved": m2_detail,
        "m3_timing": m3,
        "m4_armed_invariant_and_routes": m4,
        "m5_oneshot_invariant": m5,
        "before_after_funnel": {
            "old": funnel_old,
            "new": {"open_scan": len(open_rows), "hidden": len(hidden)},
        },
        "posture_counts_all_armed": posture_counts,
        "route_type_mix_new": _route_type_mix(rows, open_rows),
        "status": status,
        "defects": defects,
        "non_claims": [
            "Identification / visibility only — pre-pillar router replay; "
            "pillars / risk / execution / fills not run.",
            "No expectancy, PnL, win-rate or edge claims anywhere.",
            "Locked constants untouched; horizon poi_give_up_bars()=20.",
        ],
    }

    with open(EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS,
                                extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: ("" if row.get(c) is None else row.get(c))
                             for c in CSV_COLUMNS})

    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[impl] buckets_new={summary['bucket_counts_new']}", flush=True)
    print(f"[impl] M1 open_scan share: all={pct_open_all:.2f}% "
          f"f_only={pct_open_f:.2f}% (baseline 0.76%)", flush=True)
    print(f"[impl] hidden reasons={hidden_reason_counts}", flush=True)
    print(f"[impl] M2 prev-routed preserved: {m2_pass}", flush=True)
    print(f"[impl] M3 median(completion−last_scanned) over prev-CLOSED: "
          f"{m3['median']} (n={len(m3_deltas)}, now_open={len(m3_visible)})",
          flush=True)
    print(f"[impl] M4 armed old={n_armed_old} new={n_armed_new} "
          f"routes old={routes_old} new={routes_new}", flush=True)
    print(f"[impl] M5 one-shot multi-route episodes: {len(multi_route_gates)}",
          flush=True)
    for d in defects:
        print(f"[impl] DEFECT: {d}", flush=True)
    print(f"[impl] SEEK_SCAN_IMPL_MEASUREMENT: {status}", flush=True)
    return 0 if status == "PASS" else 1


def _route_type_mix(rows: list[dict], open_rows: list[dict]) -> dict:
    """Trigger-type mix of completions that WERE the episode's route."""
    mix: dict[str, int] = {}
    for r in rows:
        if r.get("_routed_this_completion"):
            mix[r["trigger_type"]] = mix.get(r["trigger_type"], 0) + 1
    return mix


if __name__ == "__main__":
    raise SystemExit(main())
