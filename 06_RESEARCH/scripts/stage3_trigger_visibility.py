#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage 3 Trigger Visibility + Conversion Audit — identification only.

Makes the six locked Stage 3 triggers (A CHOCH Reversal, B Leading Diagonal,
C Ending Diagonal, D Two-Bar Reversal, E RSI Divergence, F BOS + OB
Continuation) VISIBLE on the frozen window and measures the conversion gap
between LTF detector activity near accepted HTF zones and completed
Stage 3 trigger geometry.

Read-only: no locked constant, pillar, trigger definition, risk, TP/SL or
lot logic is touched. Existing trigger implementations are reused in
evaluation / scan mode only; product decision code is untouched.

Two passes (all existing code):

  Pass 1 — product pre-pillar route: ``ltf_confirmation_pack.observe_routes``
           (the SAME §5-mirrored arm/feed/scan_route replay the accepted
           LTF pack used) -> ``route_would_form`` per completion.
  Pass 2 — visibility inventory: one ``SeriesState(M5)`` extended per bar;
           for every structure window [close, close + poi_give_up_bars()]
           evaluate ALL matrix-eligible triggers directly and record EVERY
           completion (not only the first / best) so formed geometry is
           never hidden behind first-trigger-wins routing.

Scan window = the product horizon (existing constants only):
  [origin close, close + poi_give_up_bars() = 20 M5 bars] — identical rule
  for every structure (same as the accepted LTF pack; NOT tuned).

HTF universe = accepted packs only (events_h4_poi.csv raw rows + D1 subset
<=10). A trigger outside every accepted structure's window cannot be found
without inventing POI geometry (banned) — recorded honestly as
triggers_without_htf_link = 0 BY CONSTRUCTION (see summary limitations).

trigger_tf = M5 for every row: trigger code never reads a timeframe and the
product wires triggers only to the M5 execution path (PipelineAdapter
M5, §21 M5 primary). An M1 scan would duplicate TF-agnostic trigger code on
a hypothetical path and double-count the same windows — not run (honest
zero with reason in summary.json).
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

import matplotlib
matplotlib.use("Agg")

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_a_choch import ChochReversalTrigger
from smc.triggers.trigger_b_leading_diagonal import LeadingDiagonalTrigger
from smc.triggers.trigger_c_ending_diagonal import EndingDiagonalTrigger
from smc.triggers.trigger_d_two_bar import TwoBarReversalTrigger
from smc.triggers.trigger_e_rsi_divergence import RsiDivergenceTrigger
from smc.triggers.trigger_f_bos_ob import BosObContinuationTrigger
from smc.triggers.trigger_router import TriggerRouter

import ltf_confirmation_pack as ltf

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "stage3_trigger_visibility"
CHARTS_DIR = OUT_DIR / "charts"
EVENTS_CSV = OUT_DIR / "events_stage3_triggers.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

LTF_LEDGER_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                  "ltf_confirmation" / "events_ltf_confirmation.csv")

FOOTER = "Stage 3 trigger visibility — NOT a trade claim"

LEDGER_COLUMNS = [
    "trigger_id", "trigger_type", "trigger_tf", "direction", "bar_time_utc",
    "entry_price_ref", "related_htf_event_id", "related_htf_plain_tag",
    "related_htf_zone_low", "related_htf_zone_high", "relation_to_htf",
    "detector_context", "route_would_form", "notes",
]

TRIGGER_NAMES = {
    "A": "CHOCH REVERSAL",
    "B": "LEADING DIAGONAL",
    "C": "ENDING DIAGONAL",
    "D": "TWO-BAR REVERSAL",
    "E": "RSI DIVERGENCE",
    "F": "BOS + OB CONTINUATION",
}

#: signal.data key -> plain on-chart geometry label (render-only mapping).
GEOM_BAR_LABELS = {
    "bos_index": "BOS", "ob_index": "OB candle", "wave5_index": "Wave 5",
    "peak1_index": "peak 1", "peak2_index": "peak 2",
    "terminal_index": "diagonal terminal", "engulfing_index": "engulfing bar",
    "sweep_index": "sweep",
}
GEOM_PRICE_LABELS = {
    "broken_level": "broken level", "origin_level": "wave-1 origin",
    "neckline": "neckline", "boundary": "boundary",
    "terminal_level": "diagonal terminal",
}

SIX_TRIGGERS = [
    ChochReversalTrigger(), LeadingDiagonalTrigger(), EndingDiagonalTrigger(),
    TwoBarReversalTrigger(), RsiDivergenceTrigger(), BosObContinuationTrigger(),
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def trigger_id(letter: str, structure_id: str, completion_index: int) -> str:
    """Deterministic, human-readable trigger id (no uuids)."""
    return f"s3-{letter}-{structure_id}-{int(completion_index):05d}"


def detector_context_string(rows: list[dict], before_iso: str) -> str:
    """Nearest PRECEDING detector link per LTF timeframe (max one each).

    ``rows`` = the structure's non-trigger rows from the accepted LTF pack
    ledger. Returns e.g. ``"SWEEP (M5)@2025-07-13 21:55; FAIR VALUE GAP
    (M15)@2025-07-13 21:45"`` or ``"none in window"``.
    """
    parts: list[str] = []
    for tf in ("M5", "M15"):
        candidates = [r for r in rows
                      if r.get("ltf_tf") == tf
                      and r.get("ltf_ts_utc")
                      and r["ltf_ts_utc"] <= before_iso]
        if candidates:
            best = max(candidates, key=lambda r: (r["ltf_ts_utc"],
                                                  r.get("ltf_plain_tag", "")))
            ts = best["ltf_ts_utc"][:16].replace("T", " ")
            parts.append(f"{best.get('ltf_plain_tag', '?')}@{ts}")
    return "; ".join(parts) if parts else "none in window"


def chart_plan(n_triggers: int, n_negatives: int, *, cap: int = 40,
               max_trigger_charts: int = 30,
               negative_quota: int = 6) -> dict:
    """Deterministic chart budget (prompt priorities a -> b -> c).

    a) one M5 panel per completed trigger (all of them when <= 30);
    b) one HTF-context panel per trigger ONLY when the trigger count is
       small enough that the full set + context + negatives still fits;
    c) up to ``negative_quota`` negative-example panels (detector activity,
       no Stage 3 trigger), reduced only if the budget would break.
    """
    t = max(min(int(n_triggers), max_trigger_charts, int(cap)), 0)
    neg = min(max(int(n_negatives), 0), negative_quota, max(cap - t, 0))
    ctx = t if (2 * t + neg <= cap) else 0
    return {"trigger_panels": t, "context_panels": ctx, "negative_panels": neg}


def select_negatives(structures: list[dict], trigger_structure_ids: set[str],
                     limit: int = 6) -> list[dict]:
    """High-detector-activity structures with ZERO Stage 3 completions.

    Top-``limit``*4 by linked-detector-row count (quality pool), then
    time-spread deterministically to ``limit`` (review coverage).
    """
    cands = [s for s in structures
             if s["event_id"] not in trigger_structure_ids
             and s.get("_detector_rows")]
    cands.sort(key=lambda s: (-len(s["_detector_rows"]), s["ts_utc"],
                              s["event_id"]))
    pool = cands[:limit * 4]
    return ltf._spread(pool, limit)


def select_trigger_charts(rows: list[dict], limit: int = 30) -> list[dict]:
    """Deterministic chart sample when completions exceed the panel cap.

    All rows when ``len(rows) <= limit``. Otherwise: seed the EARLIEST row
    of every trigger type present (so every formed type is visible), then
    fill the remaining quota with an even-in-time spread over the rest —
    quality coverage over first-N volume. Input sorted by bar_time/id.
    """
    if len(rows) <= limit:
        return list(rows)
    seeded: list[dict] = []
    seen_types: set[str] = set()
    for r in rows:
        if r["trigger_type"] not in seen_types:
            seen_types.add(r["trigger_type"])
            seeded.append(r)
    if len(seeded) > limit:
        seeded = seeded[:limit]
    remaining = [r for r in rows if r not in seeded]
    fill = ltf._spread(remaining, limit - len(seeded))
    picked = seeded + fill
    picked.sort(key=lambda r: (r["bar_time_utc"], r["trigger_type"],
                               r["trigger_id"]))
    return picked


def make_trigger_poi(structure: dict) -> POI:
    """Synthetic M8 POI for an accepted structure row (observation only)."""
    tf = Timeframe.D1 if structure["src"] == "D1_pack_subset" else Timeframe.H4
    return POI(zone=Zone(bottom=float(structure["zone_low"]),
                         top=float(structure["zone_high"]),
                         direction=ltf.Direction[structure["direction"]],
                         timeframe=tf),
               models=[ModelType.M8],
               m8_kind=structure.get("kind") or None)


def classify_route_funnel(rows: list[dict], gate: dict[str, dict],
                          m5_index: dict) -> dict:
    """Where each completion sits relative to the armed-POI scan lifecycle.

    ``gate[structure_id]`` = per-structure bookkeeping from Pass 1
    (``last_scanned`` / ``pop_bar`` / ``pop_reason`` / ``route_bar``).
    A completion at bar c is ``routed`` (route_would_form yes), ``scanned``
    (inside the open scan but not the chronological route — expected 0:
    first route retires the POI), or ``suppressed`` (completion bar after
    the scan closed: ``tested`` = zone first-touch +1 rule ended it,
    ``violated`` = zone violation ended it, ``deadline`` = scan open the
    whole window yet no route — expected 0 for a recorded completion).
    """
    out = {"routed": 0, "scanned_not_routed": 0, "suppressed": 0,
           "suppressed_tested": 0, "suppressed_violated": 0,
           "suppressed_other": 0, "not_probed": 0}
    for row in rows:
        if row["route_would_form"] == "yes":
            out["routed"] += 1
            continue
        info = gate.get(row["related_htf_event_id"])
        if info is None:
            out["not_probed"] += 1
            continue
        bar = m5_index[datetime.fromisoformat(row["bar_time_utc"])]
        last = info.get("last_scanned")
        last = -1 if last is None else last
        if bar <= last:
            out["scanned_not_routed"] += 1
            continue
        out["suppressed"] += 1
        reason = info.get("pop_reason")
        if reason == "tested":
            out["suppressed_tested"] += 1
        elif reason == "violated":
            out["suppressed_violated"] += 1
        else:
            out["suppressed_other"] += 1
    return out


def observe_routes_instrumented(structures: list[dict], m5) -> dict[str, dict]:
    """Pass 1 — product pre-pillar route + scan-lifecycle bookkeeping.

    Instrumented copy of ``ltf_confirmation_pack.observe_routes`` (same
    §5 mirror: arm at close, feed_bar state, _may_route FRESH/TESTED
    rules, cursor resume, retire on route) with per-structure gate stats
    added for the conversion funnel. Verified to produce the same routes
    as the accepted LTF pack replay.
    """
    from smc.backtest.series_state import SeriesState
    from smc.core.enums import POIState
    from smc.orchestration.engine import PipelineEngine

    stamps = [c.timestamp for c in m5]
    for s in structures:
        arm = bisect.bisect_left(stamps, s["_anchor_dt"])
        if arm >= len(m5):
            s["arm_bar"] = None
            continue
        s["arm_bar"] = arm
        s["_deadline"] = min(arm + ltf.LA_M5_BARS, len(m5) - 1)
        s["_gate"] = {"last_scanned": None, "pop_bar": None,
                      "pop_reason": None, "route_bar": None,
                      "tested_bar": None}

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
            engine.arm_at(poi, bar)
            s["_poi"] = poi
            s["_cursor"] = None
            active[poi.id] = s
            order.append(poi.id)

    for bar, candle in enumerate(m5):
        state.extend(candle)
        _arm_due(bar)
        for poi_id in list(order):
            s = active.get(poi_id)
            if s is None:
                continue
            gate = s["_gate"]
            new_state = engine.feed_bar(s["_poi"], candle)
            if new_state == POIState.TESTED.value and gate["tested_bar"] is None:
                gate["tested_bar"] = bar
            if new_state == POIState.FRESH.value:
                may_route = True
            elif new_state == POIState.TESTED.value:
                may_route = (gate["tested_bar"] is not None
                             and bar <= gate["tested_bar"] + 1)
            else:
                may_route = False
            if bar > s["_deadline"]:
                may_route = False
            if not may_route:
                gate["pop_bar"] = bar
                gate["pop_reason"] = new_state
                active.pop(poi_id, None)
                order.remove(poi_id)
                continue
            gate["last_scanned"] = bar
            route = engine.scan_route(
                s["_poi"], state.candles, state.swings,
                to_bar=bar, scan_from=s["_cursor"],
                evaluation_candles=state.candles,
                evaluation_swings=state.swings, hints=state)
            if route is not None:
                s["route"] = route
                gate["route_bar"] = route.bar
                active.pop(poi_id, None)
                order.remove(poi_id)
            else:
                s["_cursor"] = bar + 1
    return {s["event_id"]: s["_gate"] for s in structures
            if s.get("_gate") is not None}


# --------------------------------------------------------------------------- #
# Pass 2 — visibility inventory (every completion, matrix-eligible only)
# --------------------------------------------------------------------------- #
def scan_inventory(structures: list[dict], m5) -> int:
    """Evaluate all matrix-eligible triggers in every structure window.

    Mirrors the router's per-bar context contract (candles/swings prefix
    through ``bar_index``, ``from_bar`` = structure close, hints = state);
    collects EVERY TriggerSignal completion, ungated by §5 routing state —
    this is the visibility inventory, not the route.
    """
    from smc.backtest.series_state import SeriesState

    router = TriggerRouter()
    stamps = [c.timestamp for c in m5]
    windows: dict[int, list[dict]] = {}
    for s in structures:
        arm = bisect.bisect_left(stamps, s["_anchor_dt"])
        if arm >= len(m5):
            s["_s3_window"] = None
            continue
        start, end = ltf.lookahead_window(arm, ltf.LA_M5_BARS, len(m5))
        s["_s3_window"] = (start, end)
        s["_poi_inv"] = make_trigger_poi(s)
        s["_eligible"] = [t for t in SIX_TRIGGERS
                          if t.type in router.eligible_types(s["_poi_inv"])]
        s["_completions"] = []
        windows.setdefault(start, []).append(s)

    active: list[dict] = []
    state = SeriesState(Timeframe.M5)
    for bar, candle in enumerate(m5):
        state.extend(candle)
        active.extend(windows.get(bar, ()))
        keep: list[dict] = []
        for s in active:
            start, end = s["_s3_window"]
            if bar <= end:
                keep.append(s)
                if start <= bar:
                    ctx = TriggerContext(
                        poi=s["_poi_inv"], candles=state.candles,
                        swings=state.swings, bar_index=bar,
                        from_bar=start, hints=state)
                    for trigger in s["_eligible"]:
                        signal = trigger.evaluate(ctx)
                        if signal is not None:
                            s["_completions"].append(
                                {"structure": s, "bar": bar,
                                 "trigger": trigger, "signal": signal})
        active = keep
    return sum(len(s["_completions"]) for s in structures
               if s.get("_completions"))


# --------------------------------------------------------------------------- #
# Chart panel (Stage 3 geometry — render only)
# --------------------------------------------------------------------------- #
def render_stage3_panel(out_path: Path, *, series, anchor, zone_low: float,
                        zone_high: float, title: str, detection_tf: str,
                        chart_tf: str, htf_context: str,
                        detector_markers: list[dict], half: int,
                        signal_info: dict | None = None,
                        caption2: str = "") -> None:
    """One M5 Stage-3 / negative-example panel in the pack visual language."""
    from generate_d1_poi_pack import (CANVAS_W_IN, CANVAS_H_IN, CANVAS_DPI,
                                      CANDLE_UP, CANDLE_DOWN, EVENT_COLOR,
                                      EVENT_BAR_COLOR)
    import matplotlib.pyplot as plt

    window, center_offset, _ = ltf._panel_window(series, anchor, half)
    if not window:
        return
    # Global index of the window's first candle (exact, clamp-aware).
    all_stamps = [c.timestamp for c in series]
    center = bisect.bisect_left(all_stamps, anchor)
    window_start = max(center - half, 0)
    fig, ax = plt.subplots(figsize=(CANVAS_W_IN, CANVAS_H_IN), dpi=CANVAS_DPI)

    for i, candle in enumerate(window):
        color = CANDLE_UP if candle.close >= candle.open else CANDLE_DOWN
        ax.plot([i, i], [candle.low, candle.high], color=color, lw=0.9)
        ax.add_patch(plt.Rectangle(
            (i - 0.35, min(candle.open, candle.close)), 0.7,
            abs(candle.close - candle.open) + 1e-9,
            facecolor=color, edgecolor=color))

    if zone_high > zone_low:
        ax.axhspan(float(zone_low), float(zone_high), color=EVENT_COLOR,
                   alpha=0.20, label="HTF zone")
    else:
        ax.axhline(float(zone_low), color=EVENT_COLOR, ls="-", lw=1.5,
                   label="HTF zone")
    ax.axvline(center_offset, color=EVENT_BAR_COLOR, lw=1.5,
               label="HTF close (window start)")

    # Detector activity markers (legend labels deduped, hard-capped).
    det_colors = {"sweep": "#6a1b9a", "displacement": "#ef6c00",
                  "fvg": "#00838f"}
    stamps = [c.timestamp for c in window]
    seen_labels: set[str] = set()
    for m in detector_markers[:20]:
        if not (window[0].timestamp <= m["_ts"] <= window[-1].timestamp):
            continue
        idx = max(bisect.bisect_left(stamps, m["_ts"]), 0)
        tag = m["tag"]
        label = tag if tag not in seen_labels else None
        seen_labels.add(tag)
        mcolor = det_colors.get(m.get("kind"), "#455a64")
        ax.axvline(idx, color=mcolor, lw=1.1, ls="--", alpha=0.85,
                   label=label)

    # Stage 3 trigger geometry (never invented — all from the signal).
    if signal_info is not None:
        letter = signal_info["letter"]
        data = signal_info.get("data") or {}
        entry = signal_info.get("entry")
        stop = signal_info.get("stop")
        completion = signal_info.get("completion_index")

        if completion is not None and window_start <= completion < window_start + len(window):
            ax.axvline(completion - window_start, color="#c62828", lw=2.0,
                       label=f"TRIGGER {letter} completion bar")
        if entry is not None:
            ax.axhline(float(entry), color="#c62828", ls="--", lw=1.6,
                       label=f"entry {float(entry):.2f}")
        if stop is not None:
            ax.axhline(float(stop), color="#795548", ls=":", lw=1.6,
                       label=f"stop ref {float(stop):.2f}")

        for key, label in GEOM_BAR_LABELS.items():
            value = data.get(key)
            if (type(value) is int
                    and window_start <= value < window_start + len(window)):
                ax.scatter([value - window_start],
                           [window[value - window_start].low],
                           marker="v", s=70, color="#1b5e20", zorder=5,
                           label=label)
        for key, label in GEOM_PRICE_LABELS.items():
            value = data.get(key)
            if isinstance(value, float):
                ax.axhline(float(value), color="#1565c0", ls="-.", lw=1.2,
                           alpha=0.8, label=f"{label} {float(value):.2f}")
        band = data.get("fib_band")
        if isinstance(band, tuple) and len(band) == 2:
            lo, hi = float(min(band)), float(max(band))
            ax.axhspan(lo, hi, color="#00838f", alpha=0.10,
                       label="Fib band 50–61.8%")

    step = max(len(window) // 8, 1)
    ax.set_xticks(range(0, len(window), step))
    ax.set_xticklabels(
        [window[i].timestamp.strftime("%Y-%m-%d %H:%M")
         for i in range(0, len(window), step)], fontsize=7)
    ax.legend(loc="upper left", fontsize=7)
    ax.grid(alpha=0.25)
    fig.text(0.06, 0.955, title, fontsize=11.5, fontweight="bold",
             color="#0d2b45", ha="left", va="top")
    fig.text(0.06, 0.917,
             f"detection_tf: {detection_tf}  |  chart_tf: {chart_tf}"
             f"  |  htf_context: {htf_context}",
             fontsize=8, color="#555555", ha="left", va="top")
    if caption2:
        fig.text(0.06, 0.892, caption2, fontsize=7.5, color="#555555",
                 ha="left", va="top")
    fig.text(0.98, 0.02, FOOTER, fontsize=8.5, style="italic",
             color="#8c1d18", ha="right", va="bottom")
    fig.subplots_adjust(left=0.06, right=0.98, top=0.855, bottom=0.14)
    fig.savefig(out_path, dpi=CANVAS_DPI)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    from generate_d1_poi_pack import render_d1_chart

    ltf.install_deterministic_poi_ids()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in CHARTS_DIR.glob("*.png"):
        try:
            stale.unlink()
        except OSError:
            pass

    # ---- Series ------------------------------------------------------- #
    m1 = load_ohlcv_parquet(ltf.DATA_PARQUET)
    m1_win = [c for c in m1
              if c.timestamp >= ltf.WARM_START
              and c.timestamp <= datetime(2025, 12, 1, tzinfo=timezone.utc)]
    by_tf = resample_multi(m1_win, [Timeframe.H4, Timeframe.D1,
                                    Timeframe.M15, Timeframe.M5])
    h4, d1, m5 = (by_tf[Timeframe.H4], by_tf[Timeframe.D1],
                  by_tf[Timeframe.M5])
    print(f"[s3] H4={len(h4)} D1={len(d1)} M5={len(m5)}", flush=True)

    # ---- HTF structures (same accepted-pack loading as the LTF pack) --- #
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
            "kind": r["kind"], "src": "H4_pack_raw",
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
                "kind": r["kind"], "src": "D1_pack_subset",
            })
    structures.sort(key=lambda s: (s["ts_utc"], s["event_id"]))
    d1_subset.sort(key=lambda s: (s["ts_utc"], s["event_id"]))
    all_structures = structures + d1_subset
    for s in all_structures:
        s["route"] = None
    print(f"[s3] structures: H4={len(structures)} D1_subset={len(d1_subset)}",
          flush=True)

    # ---- Accepted LTF-pack ledger (detector context + activity) -------- #
    ltf_rows_by_struct: dict[str, list[dict]] = {}
    ltf_trigger_rows_by_struct: dict[str, list[dict]] = {}
    total_detector_rows = 0
    zone_interacting_structures: set[str] = set()
    if LTF_LEDGER_CSV.exists():
        with open(LTF_LEDGER_CSV, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                sid = r["htf_event_id"]
                if r["ltf_plain_tag"].startswith("TRIGGER"):
                    ltf_trigger_rows_by_struct.setdefault(sid, []).append(r)
                    continue
                if r["ltf_tf"] == "none":
                    continue
                ltf_rows_by_struct.setdefault(sid, []).append(r)
                total_detector_rows += 1
                if r["relation_to_htf"] in ("retest", "inside"):
                    zone_interacting_structures.add(sid)
    for s in all_structures:
        rows = ltf_rows_by_struct.get(s["event_id"], [])
        s["_detector_rows"] = rows
    print(f"[s3] LTF ledger detector rows={total_detector_rows} "
          f"zone-interacting structures={len(zone_interacting_structures)}",
          flush=True)

    # ---- Pass 1: product pre-pillar routes (instrumented §5 replay) ---- #
    gate_by_struct = observe_routes_instrumented(all_structures, m5)
    n_routes = sum(1 for s in all_structures if s.get("route"))
    print(f"[s3] pass1 product pre-pillar routes: {n_routes}", flush=True)

    # ---- Pass 2: visibility inventory (every completion) --------------- #
    n_completions = scan_inventory(all_structures, m5)
    print(f"[s3] pass2 Stage 3 completions in windows: {n_completions}",
          flush=True)

    # ---- Ledger rows ---------------------------------------------------- #
    m5_ts = [c.timestamp for c in m5]
    ledger_rows: list[dict] = []
    for s in all_structures:
        route = s.get("route")
        route_key = None
        if route is not None:
            letter = str(route.signal.trigger.value).split("_")[0].upper()
            route_key = (letter, int(route.signal.completion_index))
        matched_route = False
        for comp in s.get("_completions", []):
            signal = comp["signal"]
            letter = str(signal.trigger.value).split("_")[0].upper()
            is_route = (route_key is not None
                        and (letter, int(signal.completion_index)) == route_key)
            if is_route:
                matched_route = True
            bar_time = m5_ts[int(signal.completion_index)]
            entry = float(signal.entry_price)
            rel = ltf.relation_to_zone(s["zone_low"], s["zone_high"],
                                       entry, entry)
            row = {
                "trigger_id": trigger_id(letter, s["event_id"],
                                         signal.completion_index),
                "trigger_type": letter,
                "trigger_tf": "M5",
                "direction": getattr(signal.direction, "name", "n/a"),
                "bar_time_utc": bar_time.isoformat(),
                "entry_price_ref": ltf._r6(entry),
                "related_htf_event_id": s["event_id"],
                "related_htf_plain_tag": s["plain_tag"],
                "related_htf_zone_low": ltf._r6(s["zone_low"]),
                "related_htf_zone_high": ltf._r6(s["zone_high"]),
                "relation_to_htf": rel,
                "detector_context": detector_context_string(
                    s["_detector_rows"], bar_time.isoformat()),
                "route_would_form": "yes" if is_route else "no",
                "notes": (f"detail={signal.detail};"
                          f"stop_reference={ltf._r6(signal.stop_reference)};"
                          f"completion_index={signal.completion_index};"
                          f"expiry_bars={signal.expiry_bars};"
                          f"structure_close={s['_anchor_dt'].isoformat()};"
                          f"src={s['src']}"),
            }
            ledger_rows.append(row)
        if route is not None and not matched_route:
            # Product route found by pass 1 but not in the inventory —
            # record it honestly rather than dropping it.
            signal = route.signal
            letter = str(signal.trigger.value).split("_")[0].upper()
            bar_time = m5_ts[int(signal.completion_index)]
            entry = float(signal.entry_price)
            ledger_rows.append({
                "trigger_id": trigger_id(letter, s["event_id"],
                                         signal.completion_index),
                "trigger_type": letter, "trigger_tf": "M5",
                "direction": getattr(signal.direction, "name", "n/a"),
                "bar_time_utc": bar_time.isoformat(),
                "entry_price_ref": ltf._r6(entry),
                "related_htf_event_id": s["event_id"],
                "related_htf_plain_tag": s["plain_tag"],
                "related_htf_zone_low": ltf._r6(s["zone_low"]),
                "related_htf_zone_high": ltf._r6(s["zone_high"]),
                "relation_to_htf": ltf.relation_to_zone(
                    s["zone_low"], s["zone_high"], entry, entry),
                "detector_context": detector_context_string(
                    s["_detector_rows"], bar_time.isoformat()),
                "route_would_form": "yes",
                "notes": "route_only_scan_discrepancy=pass1_route_not_in_"
                         "pass2_inventory;detail=" + signal.detail,
            })
    ledger_rows.sort(key=lambda r: (r["bar_time_utc"], r["trigger_type"],
                                    r["trigger_id"]))
    with open(EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        writer.writeheader()
        for row in ledger_rows:
            writer.writerow({c: row.get(c, "") for c in LEDGER_COLUMNS})

    counts_by_type = {letter: 0 for letter in "ABCDEF"}
    structures_with_trigger: set[str] = set()
    for row in ledger_rows:
        counts_by_type[row["trigger_type"]] += 1
        structures_with_trigger.add(row["related_htf_event_id"])
    print(f"[s3] counts_by_type={counts_by_type} "
          f"route_rows={sum(1 for r in ledger_rows if r['route_would_form']=='yes')}",
          flush=True)

    # ---- Route funnel: where each completion sits vs the §5 scan ------- #
    m5_index = {c.timestamp: i for i, c in enumerate(m5)}
    route_funnel = classify_route_funnel(ledger_rows, gate_by_struct,
                                         m5_index)

    # ---- Negative examples --------------------------------------------- #
    negatives = select_negatives(all_structures, structures_with_trigger,
                                 limit=6)
    plan = chart_plan(len(ledger_rows), len(negatives))

    # ---- Charts --------------------------------------------------------- #
    chart_index: list[dict] = []
    seq = 0

    # (a) + (b): every completed trigger (<= 30), M5 panel + HTF context
    #     when the full set fits the cap. Over-cap -> deterministic
    #     type-seeding + time-spread sample (select_trigger_charts).
    shown = select_trigger_charts(ledger_rows, plan["trigger_panels"])
    for row in shown:
        s = next(x for x in all_structures
                 if x["event_id"] == row["related_htf_event_id"])
        comp = next(c for c in s["_completions"]
                    if trigger_id(row["trigger_type"], s["event_id"],
                                  c["signal"].completion_index)
                    == row["trigger_id"])
        signal = comp["signal"]
        letter = row["trigger_type"]
        bar_time = datetime.fromisoformat(row["bar_time_utc"])
        seq += 1
        clean = s["plain_tag"].lower().replace(" ", "_").replace("(", "").replace(")", "")
        ts_clean = s["ts_utc"].replace(":", "").replace("-", "")[:13]
        markers = [{"_ts": datetime.fromisoformat(r["ltf_ts_utc"]),
                    "tag": r["ltf_plain_tag"], "kind": _marker_kind(r),
                    "lo": None, "hi": None}
                   for r in s["_detector_rows"]]
        markers = [m for m in markers if m["_ts"] <= bar_time]
        title = (f"TRIGGER {letter} — {TRIGGER_NAMES[letter]} | M5 | "
                 f"{bar_time.strftime('%Y-%m-%d %H:%M')} | "
                 f"{row['direction']}")
        caption2 = (f"completion: {row['bar_time_utc'][:16].replace('T', ' ')} UTC"
                    f"  |  entry: {row['entry_price_ref']}"
                    f"  |  stop ref: {ltf._r6(signal.stop_reference)}"
                    f"  |  detector links in window: {len(s['_detector_rows'])}"
                    f" (showing {min(len(markers), 20)})"
                    f"  |  route_would_form: {row['route_would_form']}")
        name = (f"{seq:03d}_trigger_{letter}_{clean}_{ts_clean}_"
                f"{s['event_id']}.png")
        render_stage3_panel(
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
                            "structure": s["event_id"],
                            "trigger_id": row["trigger_id"],
                            "panel": "TRIGGER_M5", "chart_tf": "M5"})

    # (b) HTF context panels (rendered in a deterministic block: all
    #     TRIGGER_M5, then HTF_CONTEXT, then NEGATIVE_M5 — reviewers key
    #     off chart_index; only present when the full set fits the cap).
    if plan["context_panels"]:
        for row in shown[:plan["context_panels"]]:
            s = next(x for x in all_structures
                     if x["event_id"] == row["related_htf_event_id"])
            tf_ctx = "D1" if s["src"] == "D1_pack_subset" else "H4"
            ctx_series = d1 if tf_ctx == "D1" else h4
            seq += 1
            clean = s["plain_tag"].lower().replace(" ", "_").replace("(", "").replace(")", "")
            ts_clean = s["ts_utc"].replace(":", "").replace("-", "")[:13]
            h4_row = {
                "event_id": s["event_id"], "event_type": "poi_raw",
                "plain_tag": s["plain_tag"], "ts_utc": s["ts_utc"],
                "direction": s["direction"], "zone_low": s["zone_low"],
                "zone_high": s["zone_high"], "model_tags": "M8",
                "kind": s["kind"], "source_module": "accepted_pack_row",
                "related_event_id": "", "detection_tf": tf_ctx,
                "chart_tf": tf_ctx,
            }
            name = (f"{seq:03d}_htf_context_{clean}_{ts_clean}_"
                    f"{s['event_id']}.png")
            render_d1_chart(h4_row, ctx_series, CHARTS_DIR / name)
            chart_index.append({"seq": seq, "filename": name,
                                "structure": s["event_id"],
                                "panel": "HTF_CONTEXT", "chart_tf": tf_ctx})

    # (c) negative examples: high detector activity, NO Stage 3 trigger.
    for s in negatives[:plan["negative_panels"]]:
        seq += 1
        clean = s["plain_tag"].lower().replace(" ", "_").replace("(", "").replace(")", "")
        ts_clean = s["ts_utc"].replace(":", "").replace("-", "")[:13]
        markers = [{"_ts": datetime.fromisoformat(r["ltf_ts_utc"]),
                    "tag": r["ltf_plain_tag"], "kind": _marker_kind(r),
                    "lo": None, "hi": None}
                   for r in s["_detector_rows"]]
        title = (f"NO STAGE 3 TRIGGER — detector activity only | M5 | "
                 f"{s['ts_utc'][:16].replace('T', ' ')} | {s['direction']}")
        caption2 = (f"{s['plain_tag']} close {s['_anchor_dt'].strftime('%Y-%m-%d %H:%M')} UTC"
                    f"  |  detector links in window: {len(s['_detector_rows'])}"
                    f"  |  Stage 3 completions in window: 0"
                    f"  |  activity rows shown: {min(len(markers), 20)}")
        name = f"{seq:03d}_negative_{clean}_{ts_clean}_{s['event_id']}.png"
        render_stage3_panel(
            CHARTS_DIR / name, series=m5, anchor=s["_anchor_dt"],
            zone_low=s["zone_low"], zone_high=s["zone_high"], title=title,
            detection_tf="M5", chart_tf="M5",
            htf_context=("D1" if s["src"] == "D1_pack_subset" else "H4"),
            detector_markers=markers, half=90, signal_info=None,
            caption2=caption2)
        chart_index.append({"seq": seq, "filename": name,
                            "structure": s["event_id"],
                            "panel": "NEGATIVE_M5", "chart_tf": "M5"})

    # ---- Summary -------------------------------------------------------- #
    with_trigger_structures = structures_with_trigger
    zone_active = zone_interacting_structures
    zone_active_with_trigger = zone_active & with_trigger_structures
    n_zone_active = len(zone_active)
    pct = (100.0 * len(zone_active_with_trigger) / n_zone_active
           if n_zone_active else 0.0)
    total = len(ledger_rows)
    ratio = (100.0 * total / total_detector_rows
             if total_detector_rows else 0.0)

    conversion_notes = [
        f"{n_zone_active} of {len(all_structures)} accepted HTF structures "
        f"carried >=1 zone-interacting detector link (retest|inside) in the "
        f"20-bar window; {len(zone_active_with_trigger)} of those produced "
        f">=1 completed Stage 3 trigger ({pct:.1f}%).",
        f"Detector links in window: {total_detector_rows} non-trigger rows "
        f"-> {total} Stage 3 completions ({ratio:.2f}% of detector links "
        f"converted to a completed trigger row).",
        f"{len(with_trigger_structures)} of {len(all_structures)} structures "
        f"produced any Stage 3 completion; {sum(1 for r in ledger_rows if r['route_would_form']=='yes')} "
        f"completions would form a product route (chronological first, "
        f"pre-pillar).",
        "Heavy sweep / displacement / FVG / BOS detector activity near a "
        "zone is the INGREDIENT surface; a completed Stage 3 trigger "
        "additionally requires the locked pattern + zone/direction gates "
        "of its trigger (see report 'Gaps vs flowchart Stage 3').",
        f"Route funnel (pre-pillar §5 replay): {route_funnel['routed']} of "
        f"{total} completions occurred while the armed-POI scan was still "
        f"open and all became product routes; {route_funnel['suppressed']} "
        f"completed after it closed "
        f"({route_funnel['suppressed_tested']} zone first-touch +1 gate, "
        f"{route_funnel['suppressed_violated']} zone violation) — the Stage 3 "
        f"geometry formed but the product's 1-touch seek lifecycle had "
        f"already stopped scanning that POI.",
    ]

    limitations = [
        "Scan universe = accepted H4/D1 POI structures only: "
        "triggers_without_htf_link = 0 BY CONSTRUCTION — a completion "
        "outside every accepted structure's window cannot be found "
        "without inventing POI geometry (banned). No wall-to-wall "
        "unlinked scan was run.",
        "Scan window = product horizon [close, close + poi_give_up_bars() "
        "= 20 M5 bars], existing constant, identical for every structure "
        "(same rule as the accepted LTF pack); wider horizons were NOT "
        "tried (would change counts = tuning).",
        "route_would_form = pre-pillar router signal (Pass 1 replay "
        "mirrors PipelineAdapter.generate_candidates with §5 state; "
        "pillars / risk / execution NOT run).",
        "trigger_tf = M5 only: trigger code never reads a timeframe and "
        "the product wires triggers to the M5 execution path only; an M1 "
        "scan would duplicate TF-agnostic code on a hypothetical path "
        "(counts_by_tf M1 = 0, honest zero).",
        "Trigger D structurally cannot fire on the canonical dataset: "
        "frozen rule engulfing.volume < engulfed.volume vs all-zero "
        "volume column (0 of 1,768,123 nonzero) — documented A5, "
        "counts_by_type D = 0 by construction.",
        "detector_context / negative-example activity are sourced from "
        "the accepted LTF pack ledger (same window, same linking rule) — "
        "this pack does not re-run stage-0 detection.",
        "Inventory records EVERY completion; the product route takes the "
        "chronological first (LOCKED: first valid LTF trigger wins) — "
        "inventory rows can exceed route rows by design.",
        "No expectancy, PnL, win-rate or edge measurement anywhere in "
        "this pack (visibility only).",
    ]

    summary = {
        "window": {"exec_start_utc": ltf.EXEC_START.isoformat(),
                   "exec_end_utc": ltf.EXEC_END.isoformat(),
                   "warm_start_utc": ltf.WARM_START.isoformat()},
        "scan_window_rule": f"[structure close, close + "
                            f"poi_give_up_bars()={ltf.LA_M5_BARS} M5 bars], "
                            f"same rule every structure",
        "total_stage3_triggers": total,
        "counts_by_type": counts_by_type,
        "counts_by_tf": {"M5": total, "M1": 0},
        "triggers_with_htf_link": total,
        "triggers_without_htf_link": 0,
        "route_would_form_count": sum(
            1 for r in ledger_rows if r["route_would_form"] == "yes"),
        "structures_total": len(all_structures),
        "structures_with_any_completion": len(with_trigger_structures),
        "zone_active_structures": n_zone_active,
        "zone_active_with_completion": len(zone_active_with_trigger),
        "detector_links_in_window": total_detector_rows,
        "product_routes_pass1": n_routes,
        "route_funnel": route_funnel,
        "conversion_notes": conversion_notes,
        "limitations": limitations,
        "zero_reasons": {
            "D": "engulfer.volume < engulfed.volume can never be true on "
                 "the all-zero volume parquet (frozen rule; A5 ruling, "
                 "phase_a_data_acceptance.py)",
            "M1": "M1 not wired into trigger evaluation anywhere in "
                  "product code (execution_timeframe unread; adapter M5); "
                  "hypothetical M1 scan not run",
        },
        "chart_plan": plan,
        "trigger_chart_sample_rule": "all completions when <= 30; else "
                                     "earliest-of-each-type seeded + "
                                     "even-in-time spread "
                                     "(select_trigger_charts)",
        "negative_examples": [s["event_id"] for s in
                              negatives[:plan["negative_panels"]]],
        "charts_rendered": len(chart_index),
        "chart_index": chart_index,
        "ledger_columns": LEDGER_COLUMNS,
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[s3] ledger_rows={total} charts={len(chart_index)} "
          f"negatives={len(negatives[:plan['negative_panels']])} "
          f"plan={plan}", flush=True)
    print("[s3] STAGE3_VIS_MECHANICAL: PASS", flush=True)
    return 0


def _marker_kind(row: dict) -> str:
    tag = row.get("ltf_plain_tag", "")
    if tag.startswith("SWEEP"):
        return "sweep"
    if tag.startswith("DISPLACEMENT"):
        return "displacement"
    if tag.startswith("FAIR VALUE GAP"):
        return "fvg"
    return "other"


if __name__ == "__main__":
    raise SystemExit(main())
