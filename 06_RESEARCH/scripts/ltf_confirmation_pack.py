#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LTF Confirmation Pack — identification / information-flow only.

Read-only observation of what the CURRENT machine already produces on
M15 / M5 after an accepted H4 (or D1) structure exists. No strategy logic,
pillars, triggers, thresholds, risk, TP/SL or locked constants are changed;
every observation below drives existing product code in observation mode.

Layers (all existing code, no second detection stack):
  HTF   = accepted H4 pack raw rows (`events_h4_poi.csv`, post-F1F2, dual=0)
          + a deterministic D1 subset (`events_d1_poi_post_f1f2.csv`, <=10)
  M15   = DetectionDriver.stage0 on the resampled M15 series (sweep /
          displacement[+BOS] / FVG exactly as the detector emits them)
  M5    = DetectionDriver.stage0 on the exec M5 series (same vocabulary)
  Route = observation-mode replay of the adapter's scan path:
          PipelineEngine.arm_at at the structure's origin bar, then the
          §5 feed + PipelineEngine.scan_route per M5 bar with the SAME
          cursor/resume/`to_bar` semantics as PipelineAdapter.generate_candidates
          (pillars/execution NOT run; `route_would_form` is therefore the
          pre-pillar router signal — disclosed in the report).

Look-ahead (existing constants only — nothing invented):
  M5  = poi_give_up_bars() = TRIGGER_A_EXPIRY = 20 M5 bars (LOCKED 24)
  M15 = ceil(20 * 5 / 15) = 7 M15 bars (105 min >= 100 min; derived,
        disclosed in summary.json; identical for every structure)

Linking rule (same for every structure): an LTF event links to an HTF
structure when its timestamp lies in [htf_ts, htf_ts + look-ahead] AND its
price relation to the HTF zone is not `none` (retest / inside / above /
below). The structure's own router trigger row always links (it belongs to
that POI by construction).
"""

from __future__ import annotations

import bisect
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling scripts

import matplotlib
matplotlib.use("Agg")

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.orchestration.detection_driver import DetectionDriver
from smc.orchestration.engine import PipelineEngine
from smc.triggers.trigger_expiry import poi_give_up_bars

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "ltf_confirmation"
CHARTS_DIR = OUT_DIR / "charts"
EVENTS_CSV = OUT_DIR / "events_ltf_confirmation.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"
DATA_PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
H4_EVENTS_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                 "h4_poi_confirmation" / "events_h4_poi.csv")
D1_EVENTS_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                 "d1_f1f2_resample" / "events_d1_poi_post_f1f2.csv")
LEDGER_EVENTS_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                     "structure_ledger_6m" / "events.csv")

EXEC_START = datetime(2025, 6, 1, tzinfo=timezone.utc)
EXEC_END = datetime(2025, 11, 30, 23, 59, tzinfo=timezone.utc)
WARM_START = datetime(2025, 3, 1, tzinfo=timezone.utc)

#: Look-ahead — EXISTING constants only (see module docstring).
LA_M5_BARS = poi_give_up_bars()                       # 20 (TRIGGER_A_EXPIRY)
LA_M15_BARS = math.ceil(LA_M5_BARS * 5 / 15)          # 7 (derived, disclosed)

#: Deterministic sample caps (prompt-mandated — not strategy thresholds).
MAX_ACTIVE = 12
MAX_SILENT = 8
PANEL_CAP = 40
MAX_D1_SUBSET = 10

LEDGER_COLUMNS = [
    "htf_event_id", "htf_plain_tag", "htf_direction", "htf_zone_low",
    "htf_zone_high", "htf_ts_utc", "ltf_tf", "ltf_plain_tag", "ltf_direction",
    "ltf_ts_utc", "ltf_zone_or_level", "relation_to_htf", "trigger_type",
    "route_would_form", "notes",
]

FOOTER = "structure / confirmation identification — NOT a trade claim"


def install_deterministic_poi_ids() -> None:
    """Deterministic POI ids so run1/run2 rows are byte-comparable."""
    import smc.core.poi as poi_module

    counter = count(1)

    def _deterministic_id() -> str:
        return f"poi-{next(counter):07d}"

    poi_module.uuid4 = _deterministic_id  # type: ignore[assignment]


def _eid(*parts: str) -> str:
    return "evt-" + hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def _r6(value) -> float | str:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return ""


def _iso(value) -> str:
    if value is None:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _spread(rows: list, n: int) -> list:
    """Deterministic even-in-time sample of ``n`` rows (ts-sorted input)."""
    if n <= 0 or not rows:
        return []
    if len(rows) <= n:
        return list(rows)
    step = len(rows) / n
    return [rows[min(int(i * step), len(rows) - 1)] for i in range(n)]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def lookahead_window(arm_idx: int, la_bars: int, series_len: int) -> tuple[int, int]:
    """Inclusive [start, end] bar window — same rule for every structure.

    Clamped to the series end (identical clamping for all structures).
    """
    start = max(arm_idx, 0)
    end = min(start + la_bars, series_len - 1)
    return start, end


def relation_to_zone(zone_low: float, zone_high: float,
                     ev_lo: float | None, ev_hi: float | None) -> str:
    """Honest price relation of an LTF event to the HTF zone.

    Range events (FVG, sweep candle, displacement candle): overlap with the
    zone -> ``retest``; otherwise entirely above/below. Single-level events
    (sweep level, trigger entry): inside / above / below.
    """
    if ev_lo is None or ev_hi is None:
        return "none"
    ev_lo, ev_hi = float(ev_lo), float(ev_hi)
    if ev_lo == ev_hi:  # single level
        if zone_low <= ev_lo <= zone_high:
            return "inside"
        return "above" if ev_lo > zone_high else "below"
    if ev_hi >= zone_low and ev_lo <= zone_high:
        return "retest"
    if ev_lo > zone_high:
        return "above"
    if ev_hi < zone_low:
        return "below"
    return "none"


def select_structures(active: list[dict], silent: list[dict],
                      max_active: int = MAX_ACTIVE,
                      max_silent: int = MAX_SILENT,
                      panel_cap: int = PANEL_CAP) -> list[dict]:
    """Deterministic review sample.

    Caps (prompt): <= max_active actives, <= max_silent silents, total chart
    panels <= panel_cap. Actives and silents are interleaved (a, s, a, s...)
    so BOTH classes are represented under the panel cap ("prefer quality
    over volume"); within a pair the active is considered first; a structure
    is included only when its FULL panel set fits (never partial). Inputs
    are ts-sorted dicts with ``panels`` = chart files it needs.
    """
    a = _spread(active, max_active)
    s = _spread(silent, max_silent)
    picked: list[dict] = []
    used = 0
    for i in range(max(len(a), len(s))):
        for group in (a, s):
            if i >= len(group):
                continue
            cost = int(group[i].get("panels", 2))
            if used + cost <= panel_cap:
                picked.append(group[i])
                used += cost
    return picked


def build_structure_row(structure: dict, link_rows: list[dict]) -> list[dict]:
    """Ledger rows for one structure (linked events, or one NONE row)."""
    base = {
        "htf_event_id": structure["event_id"],
        "htf_plain_tag": structure["plain_tag"],
        "htf_direction": structure["direction"],
        "htf_zone_low": structure["zone_low"],
        "htf_zone_high": structure["zone_high"],
        "htf_ts_utc": structure["ts_utc"],
    }
    route_yes = "yes" if structure.get("route") else "no"
    if not link_rows:
        return [{**base, "ltf_tf": "none", "ltf_plain_tag": "NONE",
                 "ltf_direction": "n/a", "ltf_ts_utc": "",
                 "ltf_zone_or_level": "", "relation_to_htf": "none",
                 "trigger_type": "none", "route_would_form": route_yes,
                 "notes": structure["notes_base"]}]
    out = []
    for ev in sorted(link_rows, key=lambda e: (e["ts"], e["tf"], e["tag"])):
        out.append({**base,
                    "ltf_tf": ev["tf"],
                    "ltf_plain_tag": ev["tag"],
                    "ltf_direction": ev.get("direction", "n/a"),
                    "ltf_ts_utc": ev["ts"],
                    "ltf_zone_or_level": ev["level_text"],
                    "relation_to_htf": ev["relation"],
                    "trigger_type": ev.get("trigger", "none"),
                    "route_would_form": route_yes,
                    "notes": structure["notes_base"] + ";" + ev["notes"]})
    return out


def derive_gate_counts(structures: list[dict]) -> tuple[int, int]:
    """dual_exact_bounds_count / direction_conflict_count over structures.

    Counted PER SOURCE pack (H4 pack rows among themselves, D1 subset rows
    among themselves): an identical geometry appearing in two DIFFERENT
    accepted packs (cross-TF coincidence) is not a dual emission of either
    pack — each pack already proved dual=0 on its own rows.
    """
    dual = 0
    conflicts = 0
    for src in sorted({s["src"] for s in structures}):
        groups: dict[tuple, list] = {}
        for s in structures:
            if s["src"] != src:
                continue
            groups.setdefault((s["zone_low"], s["zone_high"]), []).append(s)
        dual += sum(1 for g in groups.values() if len(g) > 1)
        conflicts += sum(1 for g in groups.values()
                         if len({s["direction"] for s in g}) > 1)
    return dual, conflicts


# --------------------------------------------------------------------------- #
# Observation event extraction (stage0 outputs -> plain-tag rows)
# --------------------------------------------------------------------------- #
def extract_stage0_events(tf: Timeframe, run, series: list[Candle]) -> list[dict]:
    """Sweep / displacement(+BOS) / FVG rows exactly as stage0 emits them."""
    tf_name = tf.name
    events: list[dict] = []
    sweeps_by_index = {}
    for sweep in run.sweeps:
        sweeps_by_index[getattr(sweep, "candle_index", -1)] = sweep

    for sweep in run.sweeps:
        level = sweep.level
        candle = sweep.candle
        pool = getattr(level, "pool", None)
        direction = "SHORT" if getattr(pool, "name", str(pool)) == "BSL" else "LONG"
        ts = getattr(candle, "timestamp", None)
        if ts is None:
            continue
        price = float(level.level)
        events.append({
            "kind": "sweep", "tf": tf_name,
            "tag": f"SWEEP ({tf_name})", "direction": direction,
            "ts": _iso(ts), "_ts": ts,
            "lo": price, "hi": price,
            "level_text": f"{price:.6f}",
            "notes": f"kind=sweep;pool={getattr(pool, 'name', pool)};"
                     f"level_type={getattr(getattr(level, 'type', None), 'value', '')}",
        })

    for sweep_index, disp in run.displacements:
        sweep = sweeps_by_index.get(sweep_index)
        if sweep is None:
            continue
        candle = sweep.candle
        ts = getattr(candle, "timestamp", None)
        if ts is None:
            continue
        bos = bool(getattr(disp, "bos", False))
        tag = (f"DISPLACEMENT ({tf_name}) + BOS ({tf_name})" if bos
               else f"DISPLACEMENT ({tf_name})")
        direction = getattr(disp.direction, "name", str(disp.direction))
        events.append({
            "kind": "displacement", "tf": tf_name, "tag": tag,
            "direction": direction, "ts": _iso(ts), "_ts": ts,
            "lo": float(candle.low), "hi": float(candle.high),
            "level_text": f"{float(candle.low):.6f}..{float(candle.high):.6f}",
            "notes": f"kind=displacement;bos={bos};"
                     f"magnitude_atr={_r6(getattr(disp, 'magnitude_atr', None))}",
        })

    for fvg in (run.fvgs or []):
        zone = fvg.zone
        idx = getattr(fvg, "start_index", -1)
        if not (0 <= idx < len(series)):
            continue
        ts = series[idx].timestamp
        events.append({
            "kind": "fvg", "tf": tf_name,
            "tag": f"FAIR VALUE GAP ({tf_name})",
            "direction": getattr(zone.direction, "name", str(zone.direction)),
            "ts": _iso(ts), "_ts": ts,
            "lo": float(zone.bottom), "hi": float(zone.top),
            "level_text": f"{float(zone.bottom):.6f}..{float(zone.top):.6f}",
            "notes": f"kind=fvg;zone_tf={getattr(zone.timeframe, 'name', zone.timeframe)}",
        })
    return events


# --------------------------------------------------------------------------- #
# Router observation (adapter scan path, observation mode)
# --------------------------------------------------------------------------- #
def observe_routes(structures: list[dict], m5: list[Candle]) -> None:
    """Arm every structure at its origin bar and replay the adapter's scan.

    Mirrors ``PipelineAdapter.generate_candidates`` scan semantics: one
    ``SeriesState`` extended per M5 bar, §5 ``feed_bar`` per armed POI,
    ``scan_route(to_bar=bar, scan_from=cursor, evaluation_*=state, hints=state)``
    with the cursor resume rule and the 1-touch seek rule (_may_route).
    Pillars and execution are NOT run — this is the pre-pillar router signal.
    """
    from smc.backtest.series_state import SeriesState

    stamps = [c.timestamp for c in m5]
    for s in structures:
        arm_idx = bisect.bisect_left(stamps, s["_anchor_dt"])
        if arm_idx >= len(m5):
            s["arm_bar"] = None
            continue
        s["arm_bar"] = arm_idx
        s["_deadline"] = min(arm_idx + LA_M5_BARS, len(m5) - 1)

    by_arm: dict[int, list[dict]] = {}
    for s in structures:
        if s.get("arm_bar") is not None:
            by_arm.setdefault(s["arm_bar"], []).append(s)

    engine = PipelineEngine()
    state = SeriesState(Timeframe.M5)
    active: dict[str, dict] = {}   # poi.id -> structure (armed, seeking)
    order: list[str] = []          # stable per-bar iteration order

    def _arm_due(bar: int) -> None:
        for s in by_arm.get(bar, ()):
            poi = POI(zone=Zone(bottom=float(s["zone_low"]),
                                top=float(s["zone_high"]),
                                direction=Direction[s["direction"]],
                                timeframe=Timeframe.H4),
                      models=[ModelType.M8], m8_kind=s.get("kind") or None)
            engine.arm_at(poi, bar)
            s["_poi"] = poi
            s["_cursor"] = None
            s["_tested_bar"] = None
            active[poi.id] = s
            order.append(poi.id)

    for bar, candle in enumerate(m5):
        state.extend(candle)
        _arm_due(bar)
        for poi_id in list(order):
            s = active.get(poi_id)
            if s is None:
                continue
            poi = s["_poi"]
            new_state = engine.feed_bar(poi, candle)
            if new_state == POIState.TESTED.value and s["_tested_bar"] is None:
                s["_tested_bar"] = bar
            # _may_route mirror: FRESH -> yes; TESTED -> bar <= tested+1.
            if new_state == POIState.FRESH.value:
                may_route = True
            elif new_state == POIState.TESTED.value:
                may_route = (s["_tested_bar"] is not None
                             and bar <= s["_tested_bar"] + 1)
            else:
                may_route = False
            if bar > s["_deadline"]:
                may_route = False
            if not may_route:
                active.pop(poi_id, None)
                order.remove(poi_id)
                continue
            route = engine.scan_route(
                poi, state.candles, state.swings,
                to_bar=bar,
                scan_from=s["_cursor"],
                evaluation_candles=state.candles,
                evaluation_swings=state.swings,
                hints=state,
            )
            if route is not None:
                s["route"] = route
                active.pop(poi_id, None)
                order.remove(poi_id)
            else:
                s["_cursor"] = bar + 1
        if not active:
            # Nothing left to seek — still fold the remaining bars so the
            # M5 stage0 inputs and determinism stay identical per run.
            continue


# --------------------------------------------------------------------------- #
# Chart panels
# --------------------------------------------------------------------------- #
def _panel_window(series: list[Candle], anchor, half: int):
    stamps = [c.timestamp for c in series]
    center = max(bisect.bisect_left(stamps, anchor), 0)
    lo = max(center - half, 0)
    hi = min(center + half, len(series) - 1)
    return series[lo:hi + 1], center - lo, center


def render_ltf_panel(out_path: Path, *, series: list[Candle], anchor,
                     zone_low: float, zone_high: float, title: str,
                     detection_tf: str, chart_tf: str, htf_context: str,
                     markers: list[dict], half: int) -> None:
    """One LTF/HTF context panel in the D1-pack visual language."""
    from generate_d1_poi_pack import (CANVAS_W_IN, CANVAS_H_IN, CANVAS_DPI,
                                      CANDLE_UP, CANDLE_DOWN, EVENT_COLOR,
                                      EVENT_BAR_COLOR)
    import matplotlib.pyplot as plt

    window, center_offset, _ = _panel_window(series, anchor, half)
    if not window:
        return
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
               label="HTF event bar")

    stamps = [c.timestamp for c in window]
    colors = {"sweep": "#6a1b9a", "displacement": "#ef6c00", "fvg": "#00838f",
              "trigger": "#c62828"}
    for m in markers:
        if not (window[0].timestamp <= m["_ts"] <= window[-1].timestamp):
            continue
        idx = max(bisect.bisect_left(stamps, m["_ts"]), 0)
        mcolor = colors.get(m["kind"], "#455a64")
        ax.axvline(idx, color=mcolor, lw=1.1, ls="--", alpha=0.9,
                   label=f"{m['tag']}")
        if m.get("lo") is not None and m.get("hi") is not None:
            if m["lo"] == m["hi"]:
                ax.axhline(float(m["lo"]), color=mcolor, lw=1.0, ls=":", alpha=0.9)
            else:
                ax.axhspan(float(m["lo"]), float(m["hi"]), color=mcolor,
                           alpha=0.10)

    step = max(len(window) // 8, 1)
    ax.set_xticks(range(0, len(window), step))
    ax.set_xticklabels(
        [window[i].timestamp.strftime("%Y-%m-%d %H:%M")
         for i in range(0, len(window), step)], fontsize=7)
    ax.set_title(f"{title}\n{FOOTER}", fontsize=9)
    ax.legend(loc="upper left", fontsize=7)
    ax.grid(alpha=0.25)
    fig.text(0.06, 0.955, title, fontsize=12, fontweight="bold",
             color="#0d2b45", ha="left", va="top")
    fig.text(0.06, 0.915,
             f"detection_tf: {detection_tf}  |  chart_tf: {chart_tf}"
             f"  |  htf_context: {htf_context}",
             fontsize=8, color="#555555", ha="left", va="top")
    fig.text(0.98, 0.02, FOOTER, fontsize=8.5, style="italic",
             color="#8c1d18", ha="right", va="bottom")
    fig.subplots_adjust(left=0.06, right=0.98, top=0.86, bottom=0.14)
    fig.savefig(out_path, dpi=CANVAS_DPI)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    from generate_d1_poi_pack import render_d1_chart

    install_deterministic_poi_ids()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in CHARTS_DIR.glob("*.png"):
        try:
            stale.unlink()
        except OSError:
            pass

    # ---- Series ------------------------------------------------------- #
    m1 = load_ohlcv_parquet(DATA_PARQUET)
    m1_win = [c for c in m1
              if c.timestamp >= WARM_START
              and c.timestamp <= datetime(2025, 12, 1, tzinfo=timezone.utc)]
    by_tf = resample_multi(m1_win, [Timeframe.H4, Timeframe.D1,
                                    Timeframe.M15, Timeframe.M5])
    h4, d1, m15, m5 = (by_tf[Timeframe.H4], by_tf[Timeframe.D1],
                       by_tf[Timeframe.M15], by_tf[Timeframe.M5])
    print(f"[ltf] H4={len(h4)} D1={len(d1)} M15={len(m15)} M5={len(m5)}",
          flush=True)

    # ---- HTF structures (accepted packs) ------------------------------ #
    structures: list[dict] = []
    with open(H4_EVENTS_CSV, encoding="utf-8") as f:
        h4_rows = list(csv.DictReader(f))
    for r in h4_rows:
        if r["event_type"] != "poi_raw":
            continue
        ts = datetime.fromisoformat(r["ts_utc"])
        if not (EXEC_START <= ts <= EXEC_END):
            continue
        structures.append({
            "event_id": r["event_id"], "plain_tag": r["plain_tag"].upper(),
            "direction": r["direction"], "zone_low": float(r["zone_low"]),
            "zone_high": float(r["zone_high"]), "ts_utc": r["ts_utc"],
            "_htf_dt": ts, "_anchor_dt": ts + timedelta(hours=4),
            "kind": r["kind"], "src": "H4_pack_raw",
        })
    merged_geom = set()
    for r in h4_rows:
        if r["event_type"] == "poi_merged":
            merged_geom.add((r["direction"], round(float(r["zone_low"]), 3),
                             round(float(r["zone_high"]), 3)))
            for s in structures:
                if (s["direction"], round(s["zone_low"], 3),
                        round(s["zone_high"], 3)) == \
                        (r["direction"], round(float(r["zone_low"]), 3),
                         round(float(r["zone_high"]), 3)):
                    s["notes_base"] = "merged_in_accepted_run"
    d1_subset: list[dict] = []
    if D1_EVENTS_CSV.exists():
        with open(D1_EVENTS_CSV, encoding="utf-8") as f:
            d1_rows = [r for r in csv.DictReader(f)
                       if r["event_type"] == "poi_raw"]
        for r in _spread(sorted(d1_rows, key=lambda r: r["ts_utc"]),
                         MAX_D1_SUBSET):
            ts = datetime.fromisoformat(r["ts_utc"])
            if not (EXEC_START <= ts <= EXEC_END):
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
        s.setdefault("notes_base", "")
        s["route"] = None
    print(f"[ltf] structures: H4={len(structures)} D1_subset={len(d1_subset)}",
          flush=True)

    # ---- Stage0 observation on M15 + M5 ------------------------------- #
    m15_run = DetectionDriver(Timeframe.M15, htf_candles={Timeframe.M15: m15}
                               ).stage0(m15)
    m5_run = DetectionDriver(Timeframe.M5, htf_candles={Timeframe.M5: m5}
                             ).stage0(m5)
    events = (extract_stage0_events(Timeframe.M15, m15_run, m15)
              + extract_stage0_events(Timeframe.M5, m5_run, m5))
    events.sort(key=lambda e: (e["_ts"], e["tf"], e["tag"]))
    print(f"[ltf] stage0 events: M15={sum(1 for e in events if e['tf']=='M15')} "
          f"M5={sum(1 for e in events if e['tf']=='M5')}", flush=True)

    # ---- Router observation (per-bar replay) -------------------------- #
    observe_routes(all_structures, m5)
    n_routes = sum(1 for s in all_structures if s.get("route"))
    print(f"[ltf] router routes (pre-pillar observation): {n_routes}", flush=True)

    # ---- Actual product routes (accepted 6-month ledger, cross-ref) --- #
    actual_routes: dict[tuple, list[str]] = {}
    if LEDGER_EVENTS_CSV.exists():
        with open(LEDGER_EVENTS_CSV, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["event_type"] != "route_ltf":
                    continue
                key = (r["direction"], round(float(r["price_low"]), 3),
                       round(float(r["price_high"]), 3))
                actual_routes.setdefault(key, []).append(
                    f"{r['trigger']}@{r['ts_utc']}")

    # ---- Link events to structures ------------------------------------ #
    m15_stamps = [e["_ts"] for e in events if e["tf"] == "M15"]
    m5_stamps = [e["_ts"] for e in events if e["tf"] == "M5"]
    m15_events = [e for e in events if e["tf"] == "M15"]
    m5_events = [e for e in events if e["tf"] == "M5"]
    m15_ts_list = [c.timestamp for c in m15]
    m5_ts_list = [c.timestamp for c in m5]

    ledger_rows: list[dict] = []
    for s in all_structures:
        # Look-ahead starts at the structure's CLOSE (the bar that FORMS it
        # is not yet a present structure; its own sub-bars must not self-
        # link). Window = [close, close + LA] clamped to series AND exec end.
        anchor = s["_anchor_dt"]
        arm15 = bisect.bisect_left(m15_ts_list, anchor)
        _, end15 = lookahead_window(arm15, LA_M15_BARS, len(m15))
        end15_ts = min(m15_ts_list[end15], EXEC_END)
        arm5 = bisect.bisect_left(m5_ts_list, anchor)
        _, end5 = lookahead_window(arm5, LA_M5_BARS, len(m5))
        end5_ts = min(m5_ts_list[end5], EXEC_END)

        linked: list[dict] = []
        for pool, stamps, end_ts in ((m15_events, m15_stamps, end15_ts),
                                     (m5_events, m5_stamps, end5_ts)):
            lo_i = bisect.bisect_left(stamps, anchor)
            hi_i = bisect.bisect_right(stamps, end_ts)
            for ev in pool[lo_i:hi_i]:
                rel = relation_to_zone(s["zone_low"], s["zone_high"],
                                       ev["lo"], ev["hi"])
                if rel == "none":
                    continue
                linked.append({**ev, "relation": rel, "trigger": "none"})

        route = s.get("route")
        if route is not None:
            letter = str(route.signal.trigger.value).split("_")[0].upper()
            ts = m5[route.bar].timestamp
            entry = float(route.signal.entry_price)
            rel = relation_to_zone(s["zone_low"], s["zone_high"], entry, entry)
            linked.append({
                "kind": "trigger", "tf": "M5",
                "tag": f"TRIGGER {letter} (M5)",
                "direction": getattr(route.signal.direction, "name", "n/a"),
                "ts": _iso(ts), "_ts": ts, "lo": entry, "hi": entry,
                "level_text": f"{entry:.6f}", "relation": rel,
                "trigger": letter,
                "notes": f"kind=trigger;route_id={s['event_id']}:{letter}"
                         f"@{route.bar};completion_index="
                         f"{getattr(route.signal, 'completion_index', '')}"
                         f";detail={getattr(route.signal, 'detail', '')}",
            })
        s["linked"] = linked
        # Zone ACTIVITY (drives active/silent classification + summary):
        # >=1 in-window link that actually interacts with the zone
        # (retest / inside) or the structure's own router trigger. Links
        # merely NEAR the zone in time (above / below) are recorded honestly
        # but do NOT make a structure "active".
        s["active"] = (route is not None
                       or any(ev["relation"] in ("retest", "inside")
                              for ev in linked))
        key = (s["direction"], round(s["zone_low"], 3), round(s["zone_high"], 3))
        if key in actual_routes:
            extra = ";actual_product_route=" + "|".join(actual_routes[key])
            s["notes_base"] = (s["notes_base"] + extra) if s["notes_base"] else extra.lstrip(";")
        ledger_rows.extend(build_structure_row(s, linked))

    # ---- Gates -------------------------------------------------------- #
    dual, conflicts = derive_gate_counts(all_structures)
    ok_gates = dual == 0 and conflicts == 0
    print(f"[ltf] structures={len(all_structures)} dual={dual} "
          f"conflicts={conflicts}", flush=True)

    # ---- Sample + panels ---------------------------------------------- #
    def panel_count(s: dict) -> int:
        has_m5 = any(ev["tf"] == "M5" for ev in s.get("linked", []))
        return 2 + (1 if has_m5 else 0)

    active = [s for s in all_structures if s.get("active")]
    silent = [s for s in all_structures if not s.get("active")]
    active.sort(key=lambda s: (s["ts_utc"], s["event_id"]))
    silent.sort(key=lambda s: (s["ts_utc"], s["event_id"]))
    for s in active + silent:
        s["panels"] = panel_count(s)
    selected = select_structures(active, silent)

    chart_index: list[dict] = []
    seq = 0
    for s in selected:
        tf_ctx = "D1" if s["src"] == "D1_pack_subset" else "H4"
        ctx_series = d1 if tf_ctx == "D1" else h4
        seq += 1
        ts_clean = s["ts_utc"].replace(":", "").replace("-", "")[:13]
        clean = s["plain_tag"].lower().replace(" ", "_").replace("(", "").replace(")", "")
        # HTF context panel (shared renderer, correct subtitle via row fields)
        h4_row = {
            "event_id": s["event_id"], "event_type": "poi_raw",
            "plain_tag": s["plain_tag"], "ts_utc": s["ts_utc"],
            "direction": s["direction"], "zone_low": s["zone_low"],
            "zone_high": s["zone_high"], "model_tags": "M8",
            "kind": s["kind"], "source_module": "accepted_pack_row",
            "related_event_id": "", "detection_tf": tf_ctx,
            "chart_tf": tf_ctx,
        }
        h4_name = f"{seq:03d}_htf_context_{clean}_{ts_clean}_{s['event_id']}.png"
        render_d1_chart(h4_row, ctx_series, CHARTS_DIR / h4_name)
        chart_index.append({"seq": seq, "filename": h4_name,
                            "structure": s["event_id"],
                            "panel": "HTF_CONTEXT", "chart_tf": tf_ctx})

        # M15 panel (always)
        seq += 1
        markers15 = [ev for ev in s["linked"] if ev["tf"] == "M15"]
        tags15 = " + ".join(sorted({ev["tag"] for ev in markers15})) or "no linked M15 events"
        title15 = (f"{s['plain_tag']} + {tags15} | M15 | "
                   f"{s['ts_utc'][:16].replace('T', ' ')} UTC | {s['direction']}")
        m15_name = f"{seq:03d}_ltf_m15_{clean}_{ts_clean}_{s['event_id']}.png"
        render_ltf_panel(
            CHARTS_DIR / m15_name, series=m15, anchor=s["_anchor_dt"],
            zone_low=s["zone_low"], zone_high=s["zone_high"],
            title=title15, detection_tf="M15", chart_tf="M15",
            htf_context=tf_ctx, markers=markers15, half=24)
        chart_index.append({"seq": seq, "filename": m15_name,
                            "structure": s["event_id"],
                            "panel": "LTF_M15", "chart_tf": "M15"})

        # M5 panel (only when an M5-linked event exists)
        markers5 = [ev for ev in s["linked"] if ev["tf"] == "M5"]
        if markers5:
            seq += 1
            tags5 = " + ".join(sorted({ev["tag"] for ev in markers5}))
            title5 = (f"{s['plain_tag']} + {tags5} | M5 | "
                      f"{s['ts_utc'][:16].replace('T', ' ')} UTC | {s['direction']}")
            m5_name = f"{seq:03d}_ltf_m5_{clean}_{ts_clean}_{s['event_id']}.png"
            render_ltf_panel(
                CHARTS_DIR / m5_name, series=m5, anchor=s["_anchor_dt"],
                zone_low=s["zone_low"], zone_high=s["zone_high"],
                title=title5, detection_tf="M5", chart_tf="M5",
                htf_context=tf_ctx, markers=markers5, half=90)
            chart_index.append({"seq": seq, "filename": m5_name,
                                "structure": s["event_id"],
                                "panel": "LTF_M5", "chart_tf": "M5"})

    # ---- CSV + summary ------------------------------------------------ #
    ledger_rows.sort(key=lambda r: (r["htf_ts_utc"], r["htf_event_id"],
                                    r["ltf_ts_utc"], r["ltf_plain_tag"]))
    with open(EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        writer.writeheader()
        for row in ledger_rows:
            writer.writerow({c: row.get(c, "") for c in LEDGER_COLUMNS})

    trigger_mix: dict[str, int] = {}
    for row in ledger_rows:
        trig = row.get("trigger_type") or "none"
        if trig != "none":
            trigger_mix[trig] = trigger_mix.get(trig, 0) + 1
    active_count = sum(1 for s in all_structures if s.get("active"))
    summary = {
        "status": "PASS" if ok_gates else "FAIL",
        "window": {"exec_start_utc": EXEC_START.isoformat(),
                   "exec_end_utc": EXEC_END.isoformat()},
        "htf_source": {"H4_pack_raw": len(structures),
                       "D1_pack_subset": len(d1_subset)},
        "structures_total": len(all_structures),
        "counts_by_htf_kind": {
            k: sum(1 for s in all_structures if s["kind"] == k)
            for k in sorted({s["kind"] for s in all_structures})},
        "htf_with_ltf_activity": active_count,
        "htf_silent": len(all_structures) - active_count,
        "activity_definition": "zone-interacting link (relation retest|inside "
                               "within the look-ahead window) OR own router "
                               "trigger; time-nearby above/below links are "
                               "recorded but do NOT count as activity",
        "anchor_rule": "look-ahead + arm start at the HTF origin bar CLOSE "
                       "(H4 origin +4h, D1 origin +24h); window clamped to "
                       "series end and exec end",
        "trigger_mix": dict(sorted(trigger_mix.items())),
        "lookahead_bars": {"M5": LA_M5_BARS, "M15": LA_M15_BARS,
                           "source": "M5=poi_give_up_bars()=TRIGGER_A_EXPIRY "
                                     "(LOCKED 24); M15=ceil(20*5/15) derived"},
        "dual_exact_bounds_count": dual,
        "direction_conflict_count": conflicts,
        "router_routes_observed": n_routes,
        "ledger_rows": len(ledger_rows),
        "sampled_structures": len(selected),
        "charts_rendered": len(chart_index),
        "chart_index": chart_index,
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[ltf] rows={len(ledger_rows)} active={active_count} "
          f"silent={len(all_structures)-active_count} "
          f"triggers={dict(trigger_mix)} sampled={len(selected)} "
          f"charts={len(chart_index)}", flush=True)
    print(f"[ltf] GATE_MECHANICAL: {'PASS' if ok_gates else 'FAIL'}",
          flush=True)
    return 0 if ok_gates else 1


if __name__ == "__main__":
    raise SystemExit(main())
