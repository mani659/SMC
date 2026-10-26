#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POI-linked sweep rate — flowchart Step 2 (read-only).

Lead Architect directive (after HTF_POI_CENSUS_NOTE.md): for unique POI
episodes from Step 1, measure how often a valid sweep occurs on THAT
POI (zone high/low) — NOT how many sweeps exist in the universe.
No threshold changes, no gates, no production code touched.

Frozen design (stated before running):
  * Unit: unique census episode (poi_episodes.csv, 1,093 rows).
  * Sweep predicate: the product wick-pierce + close-back
    (sweep_detector.detect_sweep — the real function, not a copy) on
    the DIRECTIONAL edge only: LONG POI -> SSL predicate on zone_low
    (pierce below, close back above); SHORT POI -> BSL predicate on
    zone_high. Opposite-side sweeps are a different thesis (out of
    scope, stated). Level carrier: LiquidityType.POI_LEVEL (metadata
    only — detect_sweep reads pool/level/formed_at).
  * Primary scan: the POI's own TF bars (episode TF for m1m7; source
    TF for M8-*) — keeps the HTF sweep layer cleanly separated from
    Step-3 LTF confirmation. Secondary: M5 bars (same rule, labeled
    secondary). M8-W1 episodes scan W1 natively.
  * formed_at / first-seen respected: search starts strictly after
    first_seen_date 00:00 UTC (a sweep before the POI exists never
    counts); sweep candle must satisfy ts < 2025-12-01 (in-window).
  * Bars-to-first-sweep: TF bars from the first bar at/after
    first_seen_date to the sweep bar (secondary: M5 bars likewise).
  * Re-sweeps: every further sweep of the same edge in-window
    (advancing start_index, same predicate) — side count only.
  * No-look-ahead: packs/series are timestamped decisions; indices by
    timestamp; episode identity reused from Step 1.

Outputs: results/poi_linked_sweep_rate/{sweeps_per_episode.csv,
summary.json}. Note: POI_LINKED_SWEEP_RATE_NOTE.md (separate step).
LOGIC_CHANGED: NO (04_SRC untouched — detector only CALLED).
"""

from __future__ import annotations

import bisect as _bisect
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
sys.path.insert(0, str(SRC_DIR))

from smc.config.timeframe import Timeframe
from smc.core.enums import PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.detection.sweep_detector import detect_sweep
from smc.core.enums import LiquidityType

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "poi_linked_sweep_rate"
ROWS_CSV = OUT_DIR / "sweeps_per_episode.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — NOT EDGE"

POI_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "htf_poi_census" /
           "poi_episodes.csv")
EXEC_END_EXCLUSIVE = datetime(2025, 12, 1, tzinfo=timezone.utc)
LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)

CSV_COLUMNS = [
    "episode_id", "tf", "kind_tag", "direction",
    "zone_low", "zone_high", "swept_edge", "pool", "first_seen_date",
    "swept", "first_sweep_ts", "bars_to_first_sweep",
    "n_sweeps_total",
    "m5_swept", "m5_first_sweep_ts", "m5_bars_to_first", "m5_n_sweeps",
    "note",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def directional_edge(direction_name: str | None, zone_low: float,
                     zone_high: float) -> tuple[float, object]:
    """(edge price, PoolType member) for a POI's directional edge.

    LONG (demand) -> SSL predicate on the LOW (sell stops below support
    swept, rejection back up); SHORT (supply) -> BSL on the HIGH.
    Returns the real enum (detect_sweep branches on identity) — callers
    serialize .value for rows. Unknown direction raises (never
    silently mis-sided).
    """
    side = (direction_name or "").strip().upper()
    if side == "LONG":
        return float(zone_low), PoolType.SSL
    if side == "SHORT":
        return float(zone_high), PoolType.BSL
    raise ValueError(f"no directional edge for direction {direction_name!r}")


def all_sweeps_of_edge(bars, edge: float, pool_value, formed_at,
                       window_end_exclusive) -> list:
    """Every sweep of one POI edge in-window (first + re-fires).

    Pure reuse of sweep_detector.detect_sweep with an advancing
    start_index — the identical predicate the product evaluates.
    formed_at bounds the search (zone must exist first); sweeps at or
    past the window end are excluded. Pool accepts the enum or its
    value string (normalized — a string never silently mis-branches).
    """
    pool = pool_value
    if not isinstance(pool, PoolType):
        pool = PoolType(str(pool_value).strip().lower())  # loud on garbage
    level = LiquidityLevel(type=LiquidityType.POI_LEVEL, level=edge,
                           pool=pool, formed_at=formed_at)
    out = []
    start = 0
    while True:
        res = detect_sweep(bars, level, start_index=start)
        if res is None:
            return out
        if res.candle.timestamp >= window_end_exclusive:
            return out
        out.append(res)
        start = res.candle_index + 1


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not POI_CSV.exists():
        raise SystemExit(f"Step-1 episodes missing: {POI_CSV}")
    parquet = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not parquet.exists():
        raise SystemExit(f"canonical dataset missing: {parquet}")
    m1_all = load_ohlcv_parquet(str(parquet), Timeframe.M1)
    m1 = [c for c in m1_all
          if LOAD_FROM <= c.timestamp <= EXEC_END_EXCLUSIVE + timedelta(days=1)]
    if not m1:
        raise SystemExit("no M1 bars in the load window")
    multi = resample_multi(m1, [Timeframe.H4, Timeframe.H1, Timeframe.D1,
                                Timeframe.W1, Timeframe.M5])
    series = {tf: multi[tf] for tf in
              (Timeframe.H4, Timeframe.H1, Timeframe.D1, Timeframe.W1,
               Timeframe.M5)}
    print("[step2] " + " ".join(f"{tf.name}={len(series[tf])}"
                                for tf in series), flush=True)

    native_tf = {"H4": Timeframe.H4, "H1": Timeframe.H1,
                 "M8-H4": Timeframe.H4, "M8-D1": Timeframe.D1,
                 "M8-W1": Timeframe.W1}

    with open(POI_CSV, encoding="utf-8", newline="") as f:
        episodes = list(csv.DictReader(f))
    print(f"[step2] episodes={len(episodes)}", flush=True)

    rows_out: list[dict] = []
    for ep in episodes:
        tf = native_tf[ep["tf"]]
        bars = series[tf]
        stamps = [c.timestamp for c in bars]
        edge, pool = directional_edge(ep["direction"],
                                      float(ep["zone_low"]),
                                      float(ep["zone_high"]))
        formed_at = datetime.fromisoformat(ep["first_seen_date"]).replace(
            tzinfo=timezone.utc)
        start_idx = _bisect.bisect_left(stamps, formed_at)
        sweeps = ([s for s in all_sweeps_of_edge(bars, edge, pool, formed_at,
                                                 EXEC_END_EXCLUSIVE)
                   if s.candle_index >= start_idx])
        m5bars = series[Timeframe.M5]
        m5stamps = [c.timestamp for c in m5bars]
        m5_start = _bisect.bisect_left(m5stamps, formed_at)
        m5sweeps = ([s for s in all_sweeps_of_edge(
            m5bars, edge, pool, formed_at, EXEC_END_EXCLUSIVE)
            if s.candle_index >= m5_start])
        row = {
            "episode_id": ep["episode_id"], "tf": ep["tf"],
            "kind_tag": ep["kind_tag"], "direction": ep["direction"],
            "zone_low": ep["zone_low"], "zone_high": ep["zone_high"],
            "swept_edge": edge, "pool": pool.value,
            "first_seen_date": ep["first_seen_date"],
            "swept": bool(sweeps),
            "first_sweep_ts": (sweeps[0].candle.timestamp.isoformat()
                               if sweeps else ""),
            "bars_to_first_sweep": (sweeps[0].candle_index - start_idx
                                    if sweeps else ""),
            "n_sweeps_total": len(sweeps),
            "m5_swept": bool(m5sweeps),
            "m5_first_sweep_ts": (m5sweeps[0].candle.timestamp.isoformat()
                                  if m5sweeps else ""),
            "m5_bars_to_first": (m5sweeps[0].candle_index - m5_start
                                 if m5sweeps else ""),
            "m5_n_sweeps": len(m5sweeps),
            "note": "",
        }
        rows_out.append(row)

    with open(ROWS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows_out:
            writer.writerow({c: ("" if r.get(c) is None else r.get(c))
                             for c in CSV_COLUMNS})

    # ---- Aggregates ------------------------------------------------------ #
    def _median(vals):
        vals = sorted(v for v in vals if v != "" and v is not None)
        vals = [float(v) for v in vals]
        if not vals:
            return None
        mid = len(vals) // 2
        if len(vals) % 2:
            return vals[mid]
        return (vals[mid - 1] + vals[mid]) / 2.0

    by_group: dict[str, dict] = {}
    for g in ("H4", "H1", "M8-H4", "M8-D1", "M8-W1"):
        sub = [r for r in rows_out if r["tf"] == g]
        n = len(sub)
        swept = [r for r in sub if r["swept"]]
        m5swept = [r for r in sub if r["m5_swept"]]
        by_group[g] = {
            "n_episodes": n,
            "n_swept": len(swept),
            "sweep_rate": (round(len(swept) / n, 4) if n else None),
            "median_bars_to_first_sweep": _median(
                [r["bars_to_first_sweep"] for r in swept]),
            "n_resweeps_total": sum(r["n_sweeps_total"] for r in sub),
            "m5_n_swept": len(m5swept),
            "m5_sweep_rate": (round(len(m5swept) / n, 4) if n else None),
            "m5_median_bars_to_first": _median(
                [r["m5_bars_to_first"] for r in m5swept]),
        }

    summary = {
        "banner": BANNER,
        "frozen": {
            "unit": "unique Step-1 episode (not raw re-detect rows)",
            "predicate": ("product wick-pierce + close-back "
                          "(sweep_detector.detect_sweep, same function)"),
            "edge": ("directional only: LONG->SSL on zone_low, "
                     "SHORT->BSL on zone_high; opposite side out of scope"),
            "primary_scan": "episode's own TF bars (HTF-scale rejection)",
            "secondary_scan": "M5 bars, same rule, labeled secondary",
            "formed_rule": ("search starts strictly after first_seen "
                            "00:00 UTC; sweep candle ts < 2025-12-01"),
            "bars_to_first": ("TF bars from first bar at/after first_seen "
                              "to sweep bar (M5 likewise for secondary)"),
        },
        "by_group": by_group,
        "overall": {
            "n_episodes": len(rows_out),
            "n_swept": sum(1 for r in rows_out if r["swept"]),
            "m5_n_swept": sum(1 for r in rows_out if r["m5_swept"]),
        },
        "limitations": [
            "First-seen dating is day-granular (Step-1 census rule); "
            "sweeps earlier the same day count from the day boundary.",
            "Opposite-side sweeps unmeasured (different thesis).",
            "M5 secondary will saturate on choppy zones (wick noise) — "
            "reported alongside, never averaged with primary.",
            "No gate, no threshold, no live rule follows (see note).",
        ],
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[step2] swept={summary['overall']['n_swept']}/"
          f"{len(rows_out)} m5_swept={summary['overall']['m5_n_swept']}",
          flush=True)
    print(f"[step2] wrote {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
