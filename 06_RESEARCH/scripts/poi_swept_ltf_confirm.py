#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LTF confirmation on swept POIs — flowchart Step 3 (read-only).

Lead Architect directive (after POI_LINKED_SWEEP_RATE_NOTE.md): of POIs
swept at least once, measure how often LTF confirmation (Stage-3
trigger completion A-F) appears after the first sweep. Do NOT require
product arm/route/fill. No threshold/pillar/seek changes.

Frozen design (stated before running):
  * Population: unique Step-1 episodes with n_swept >= 1 from
    sweeps_per_episode.csv (946); primary anchor = first_sweep_ts.
    Unswept episodes (147) reported as n only (never in any
    denominator).
  * Confirmation = product Stage-3 completion evaluated EXACTLY like
    the visibility pack (stage3_trigger_visibility.scan_inventory):
    one SeriesState(M5) extended per bar, TriggerRouter
    matrix-eligible triggers evaluated directly with TriggerContext
    (poi=<episode zone+bounds+direction>, from_bar=<first-sweep bar>),
    EVERY completion recorded ungated. Only the window moves: structure
    close -> first sweep; horizon -> +48 M5 bars max.
  * POI models mirror product compatibility: m1m7 episodes carry their
    recorded tag union (M1..M7); M8 episodes carry [M8] + m8_kind
    facet (exactly make_trigger_poi). Trigger code never reads
    timeframes; zone/direction gates live inside trigger.evaluate.
  * Link rule (frozen, no new magic numbers): a completion links iff
    its bar satisfies sweep_bar < completion_bar <= sweep_bar + H, for
    H in {5, 12, 20, 48}. H=20 reuses the locked give-up scale
    (TRIGGER_A_EXPIRY = poi_give_up_bars()); strict-greater excludes
    same-timestamp ambiguity (unknowable intrabar order).
  * One inventory pass over (sweep, sweep+48]; nested horizons derived
    ({5,12,20}amination subsets of the 48-pass — no separate runs).
  * M15 parallel skipped by design (product evaluates triggers on M5
    only; an M15 scan would be a hypothetical path — stated, not run).

Outputs: results/poi_swept_ltf_confirm/{confirm_per_episode.csv,
summary.json}. Note: POI_SWEPT_LTF_CONFIRM_NOTE.md (separate step).
LOGIC_CHANGED: NO (04_SRC untouched — triggers only EVALUATED).
"""

from __future__ import annotations

import bisect
import csv
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

from smc.backtest.series_state import SeriesState
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_router import TriggerRouter

import stage3_trigger_visibility as s3

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "poi_swept_ltf_confirm"
ROWS_CSV = OUT_DIR / "confirm_per_episode.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — NOT EDGE"

SWEEPS_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
              "poi_linked_sweep_rate" / "sweeps_per_episode.csv")
LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)
LOAD_END = datetime(2025, 12, 3, tzinfo=timezone.utc)
HORIZONS = (5, 12, 20, 48)
MAX_H = max(HORIZONS)

CSV_COLUMNS = [
    "episode_id", "tf", "kind_tag", "direction",
    "first_sweep_ts", "confirmed_within_5", "confirmed_within_12",
    "confirmed_within_20", "confirmed_within_48",
    "first_confirm_trigger", "bars_sweep_to_confirm",
    "n_completions_48",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def completions_in_window(completions: list[dict], sweep_bar: int,
                          horizon: int) -> list[dict]:
    """Completions with sweep_bar < bar <= sweep_bar + horizon.

    Strict-greater excludes same-timestamp ambiguity (unknowable
    intrabar order between the sweep bar and the completion bar).
    """
    return [c for c in completions
            if sweep_bar < int(c["bar"]) <= sweep_bar + horizon]


def trigger_letter(trigger) -> str:
    """Trigger family letter, shared convention (cf. stage-3 inventory).

    Accepts the TriggerType enum (has .value), a trigger object (has
    .type -> enum), or a plain "F..." string — never raises on shape.
    """
    value = getattr(trigger, "value", None)
    if value is None:
        value = getattr(getattr(trigger, "type", None), "value", trigger)
    return str(value).split("_")[0].upper()


def first_confirmation(completions: list[dict]) -> dict | None:
    """Earliest completion (bar, then letter — deterministic)."""
    if not completions:
        return None
    return sorted(completions,
                  key=lambda c: (int(c["bar"]),
                                 trigger_letter(c["trigger"])))[0]


def episode_poi(episode: dict):
    """Synthetic POI for an episode (bounds + direction + tags).

    m1m7 rows carry their recorded tag union; M8 rows carry [M8] with
    the m8_kind facet (exactly stage-3 make_trigger_poi for M8).
    """
    tf_name = episode["tf"]
    src_tf = {"H4": "H4", "H1": "H1", "M8-H4": "H4", "M8-D1": "D1",
              "M8-W1": "W1"}[tf_name]
    if tf_name.startswith("M8-"):
        models = [ModelType.M8]
        m8_kind = episode.get("m8_kind") or None
    else:
        models = [ModelType[t.strip()] for t in
                  (episode.get("all_tags") or episode.get("kind_tag") or "")
                  .split("+") if t.strip() in ModelType.__members__]
        m8_kind = None
    return POI(zone=Zone(bottom=float(episode["zone_low"]),
                         top=float(episode["zone_high"]),
                         direction=Direction[episode["direction"]],
                         timeframe=Timeframe[src_tf]),
               models=models or [ModelType.M1],
               m8_kind=m8_kind)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not SWEEPS_CSV.exists():
        raise SystemExit(f"Step-2 rows missing: {SWEEPS_CSV}")
    parquet = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not parquet.exists():
        raise SystemExit(f"canonical dataset missing: {parquet}")
    m1_all = load_ohlcv_parquet(str(parquet), Timeframe.M1)
    m1 = [c for c in m1_all if LOAD_FROM <= c.timestamp <= LOAD_END]
    if not m1:
        raise SystemExit("no M1 bars in the load window")
    m5 = resample_multi(m1, [Timeframe.M5])[Timeframe.M5]
    stamps = [c.timestamp for c in m5]
    print(f"[step3] M5={len(m5)} ({m5[0].timestamp.date()} -> "
          f"{m5[-1].timestamp.date()})", flush=True)

    with open(SWEEPS_CSV, encoding="utf-8", newline="") as f:
        sweep_rows = list(csv.DictReader(f))
    swept = [r for r in sweep_rows if r.get("swept") == "True"]
    unswept_n = sum(1 for r in sweep_rows if r.get("swept") != "True")
    print(f"[step3] swept episodes={len(swept)} "
          f"unswept_reported_n_only={unswept_n}", flush=True)

    router = TriggerRouter()
    windows: dict[int, list[dict]] = {}
    for ep in swept:
        sweep_ts = datetime.fromisoformat(ep["first_sweep_ts"])
        s = bisect.bisect_left(stamps, sweep_ts)
        if s >= len(m5):
            ep["_sweep"] = None
            continue
        ep["_sweep"] = s
        ep["_poi_inv"] = episode_poi(ep)
        ep["_eligible"] = [t for t in s3.SIX_TRIGGERS
                           if t.type in router.eligible_types(ep["_poi_inv"])]
        ep["_completions"] = []
        windows.setdefault(s, []).append(ep)

    active: list[dict] = []
    state = SeriesState(Timeframe.M5)
    for bar, candle in enumerate(m5):
        state.extend(candle)
        active.extend(windows.get(bar, ()))
        keep: list[dict] = []
        for ep in active:
            if bar <= ep["_sweep"] + MAX_H:
                keep.append(ep)
                if bar > ep["_sweep"]:
                    ctx = TriggerContext(
                        poi=ep["_poi_inv"], candles=state.candles,
                        swings=state.swings, bar_index=bar,
                        from_bar=ep["_sweep"], hints=state)
                    for trigger in ep["_eligible"]:
                        signal = trigger.evaluate(ctx)
                        if signal is not None:
                            ep["_completions"].append(
                                {"bar": int(signal.completion_index),
                                 "trigger": trigger.type})
        active = keep
    n_completions = sum(len(ep["_completions"]) for ep in swept
                        if ep.get("_sweep") is not None)
    print(f"[step3] completions in (sweep, sweep+{MAX_H}] sweeping: "
          f"{n_completions}", flush=True)

    rows_out: list[dict] = []
    for ep in swept:
        s = ep.get("_sweep")
        comps = ep.get("_completions", []) if s is not None else []
        flags = {}
        for h in HORIZONS:
            flags[h] = bool(completions_in_window(comps, s, h)) \
                if s is not None else False
        first = first_confirmation(
            completions_in_window(comps, s, MAX_H)) \
            if s is not None else None
        rows_out.append({
            "episode_id": ep["episode_id"], "tf": ep["tf"],
            "kind_tag": ep["kind_tag"], "direction": ep["direction"],
            "first_sweep_ts": ep["first_sweep_ts"],
            "confirmed_within_5": flags.get(5, False),
            "confirmed_within_12": flags.get(12, False),
            "confirmed_within_20": flags.get(20, False),
            "confirmed_within_48": flags.get(48, False),
            "first_confirm_trigger": (trigger_letter(first["trigger"])
                                      if first else ""),
            "bars_sweep_to_confirm": ((int(first["bar"]) - s)
                                      if first and s is not None else ""),
            "n_completions_48": len(completions_in_window(comps, s, MAX_H))
            if s is not None else 0,
        })

    with open(ROWS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows_out:
            writer.writerow({c: ("" if r.get(c) is None else r.get(c))
                             for c in CSV_COLUMNS})

    # ---- Aggregates ------------------------------------------------------ #
    def rate(key):
        sub = [r for r in rows_out if r[key] is True]
        return {"n": len(sub),
                "rate": round(len(sub) / len(rows_out), 4) if rows_out else None}

    by_trigger: dict[str, int] = dict(Counter(
        r["first_confirm_trigger"] for r in rows_out
        if r["first_confirm_trigger"]))
    by_group: dict[str, dict] = {}
    for g in ("H4", "H1", "M8-H4", "M8-D1", "M8-W1"):
        sub = [r for r in rows_out if r["tf"] == g]
        by_group[g] = {
            "n_swept": len(sub),
            "confirmed_48_n": sum(1 for r in sub if r["confirmed_within_48"]),
            "confirmed_48_rate": (round(sum(
                1 for r in sub if r["confirmed_within_48"]) / len(sub), 4)
                if sub else None),
        }

    summary = {
        "banner": BANNER,
        "frozen": {
            "population": ("unique Step-1 episodes with n_swept >= 1 "
                           "(first sweep anchor); unswept reported as n "
                           "only"),
            "evaluation": ("stage3_trigger_visibility.scan_inventory mode: "
                           "SeriesState(M5) per bar, TriggerRouter "
                           "matrix-eligible triggers, TriggerContext with "
                           "episode POI + from_bar=first-sweep bar, EVERY "
                           "completion recorded ungated"),
            "link_rule": ("sweep_bar < completion_bar <= sweep_bar + H, "
                          "H in {5,12,20,48}; H=20 reuses the locked "
                          "give-up scale (TRIGGER_A_EXPIRY); strict-greater "
                          "excludes same-timestamp ambiguity"),
            "one_pass": ("single (sweep, sweep+48] inventory; nested "
                         "horizons derived, never re-run"),
            "m15": ("skipped by design (product evaluates triggers on M5 "
                    "only)"),
            "unswept_n": unswept_n,
        },
        "swept_n": len(rows_out),
        "confirm_rate_by_h": {str(h): rate(f"confirmed_within_{h}")
                              for h in HORIZONS},
        "by_trigger_first": by_trigger,
        "by_group": by_group,
        "total_completions_48": sum(r["n_completions_48"] for r in rows_out),
        "limitations": [
            "Completion bars index this script's M5 series (canonical "
            "pipeline — same grid as the packs).",
            "Trigger-internal zone/direction gates run as coded (same as "
            "the visibility pack); no new linking tolerance.",
            "Episodes whose first sweep falls within 48 M5 bars of the "
            "series end read short windows honestly (flags reflect "
            "observed bars only).",
            "No gate, no threshold, no live rule follows (see note).",
        ],
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[step3] confirmed_48="
          f"{sum(1 for r in rows_out if r['confirmed_within_48'])}/"
          f"{len(rows_out)} wrote {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
