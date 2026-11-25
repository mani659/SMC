#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Structural TP age-cap — Phase B measurement (probes only, no wiring).

Lead Architect ruling 2026-11-25: **OPTION C (separate constant), measure only.**
This script measures the *search window* of the structural TP branch on the
year Book F population. It never writes production code, never touches
`locked_constants.py`, and never changes a default.

Contract: `00_LOCKED/STRUCTURAL_TP_AGE_CAP_DESIGN.md` §4.

Probes (fixed before the run, no fitting — §4.4 K4):
  * ``age20``   — ``max_age_bars = 20`` (as coded; MUST reproduce P4 222/129)
  * ``age100``  — ``max_age_bars = 100``
  * ``none``    — ``max_age_bars = None``
  * ``b1``      — SENSITIVITY COLUMN ONLY: ``ceil(20 * 5 / tf_minutes)``
                  (M1 100 / M5 20 / M15 7 / H1 2 / H4 1 / D1 1)

Method (reuses the accepted P4 reconstruction, lookahead-safe):
  1. population = Book F year fills from the entry-quality universe export;
  2. confirmation series per segment via the frozen harness loader/resampler
     (`lib/menu_window.segment_series` -> `r1_pure_tag_books.segment_series`);
     processed ONE SEGMENT AT A TIME so peak memory stays flat;
  3. completion bar located by its CLOSE stamp (the export stores `_close_ts`);
  4. swings = `detect_swings(series)` once per (segment, TF). Equivalent to
     detecting on each row's place-time prefix because the selector keeps only
     swings with `confirmed_index < placement_bar`; asserted per group below;
  5. target = `structural_tp_target(..., placement_bar=idx, max_age_bars=cap)`
     with the probe's cap — the production selector, imported, never forked;
  6. a local mirror of the selector's ranking is used ONLY to report the
     winning swing's age, and MUST return the same level (asserted per row).

Artifacts: `06_RESEARCH/results/structural_tp_age_cap/`
  (`per_fill.csv`, `summary.json`).
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "04_SRC"
for path in (str(SRC), str(REPO / "06_RESEARCH" / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

from smc.backtest.pipeline_bridge import (  # noqa: E402
    STRUCTURAL_TP_MIN_ATR,
    structural_tp_target,
)
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.enums import Direction  # noqa: E402
from smc.detection.structural_swing_detector import detect_swings  # noqa: E402
from smc.utils.atr import latest_atr  # noqa: E402

import lib.menu_window as menu_window  # noqa: E402
from lib.menu_window import segment_series  # noqa: E402

UNIVERSE = REPO / "06_RESEARCH/results/entry_quality_f_b/universe_features.csv"
P4_INVENTORY = REPO / "06_RESEARCH/results/f_tp_representation/fallback_inventory.csv"
OUT = REPO / "06_RESEARCH/results/structural_tp_age_cap"
SHARDS = OUT / "shards"  # one JSON per segment: the run is resumable

ATR_PERIOD = 14  # menu engine indicator parameter (`product_menu_mtf.atr_period`)
TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240, "D1": 1440}
SERIES_KEY = {"M1": "m1", "M5": "m5", "M15": "m15", "H1": "h1", "H4": "h4", "D1": "d1"}

PROBES = ("age20", "age100", "none", "b1")

P4_STRUCTURAL = 222
P4_FALLBACK = 129


def fail_loud(msg: str) -> None:
    raise SystemExit(f"[age-cap] FAIL LOUD: {msg}")


def b1_bars(tf: str) -> int:
    """B1 sensitivity: keep the 100-minute wall time of the M5 rule."""
    return int(math.ceil(20 * 5 / TF_MINUTES[tf]))


def cap_for(probe: str, tf: str) -> int | None:
    if probe == "age20":
        return 20
    if probe == "age100":
        return 100
    if probe == "none":
        return None
    if probe == "b1":
        return b1_bars(tf)
    raise ValueError(probe)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def winning_swing(swings, entry: float, direction: Direction, atr: float,
                  placement_bar: int, max_age_bars: int | None):
    """Mirror of `structural_tp_target`'s ranking, returning the swing.

    Used ONLY for the reported age; the returned level is asserted equal to
    the production selector's on every row (see `main`).
    """
    min_dist = STRUCTURAL_TP_MIN_ATR * atr
    is_long = direction is Direction.LONG
    best = None
    for swing in swings:
        level = float(swing.level)
        ci = swing.confirmed_index
        if not swing.is_valid or ci is None:
            continue
        if ci >= placement_bar:
            continue
        if (max_age_bars is not None
                and swing.candle_index < placement_bar - max_age_bars):
            continue
        if is_long:
            if not level > entry + min_dist:
                continue
            dist = level - entry
        else:
            if not level < entry - min_dist:
                continue
            dist = entry - level
        key = (dist, -swing.candle_index)
        if best is None or key < best[0]:
            best = (key, swing)
    return None if best is None else best[1]


def quantile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    pos = p * (len(vals) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def probe_row(row: dict, swings: list, atr: float, idx: int,
              direction: Direction) -> dict:
    entry = float(row["entry_price"])
    tf = row["confirmation_tf"]
    rec = {"id": row["id"], "segment": row["segment"], "confirmation_tf": tf,
           "direction": direction.name.lower(), "entry": entry, "atr": atr,
           "completion_index": idx}
    for probe in PROBES:
        cap = cap_for(probe, tf)
        level = structural_tp_target(swings, entry, direction, atr,
                                     placement_bar=idx, max_age_bars=cap)
        swing = winning_swing(swings, entry, direction, atr, idx, cap)
        mirror = None if swing is None else float(swing.level)
        if (level is None) != (mirror is None) or (
                level is not None and abs(level - mirror) > 1e-12):
            fail_loud(f"mirror diverged on {row['id']}/{probe}: {level} vs {mirror}")
        age = None if swing is None else idx - swing.candle_index
        rec[f"{probe}_target"] = level
        rec[f"{probe}_age_bars"] = age
        rec[f"{probe}_age_min"] = None if age is None else age * TF_MINUTES[tf]
        rec[f"{probe}_cap"] = cap
    return rec


def main() -> int:
    if STRUCTURAL_TP_MIN_ATR != 0.25:
        fail_loud(f"selector noise guard changed ({STRUCTURAL_TP_MIN_ATR})")

    fills = [r for r in read_csv(UNIVERSE) if r["book"] == "F"]
    if not fills:
        fail_loud("no Book F rows in the universe export")
    p4 = {r["id"]: r for r in read_csv(P4_INVENTORY)}
    p4_ids = set(p4)
    print(f"[age-cap] Book F fills: {len(fills)}; P4 fallback inventory: "
          f"{len(p4_ids)}", flush=True)

    segments: list[str] = []
    for row in fills:
        if row["segment"] not in segments:
            segments.append(row["segment"])

    per_fill: dict[str, dict] = {}
    comp_idx_checked = comp_idx_mismatched = 0
    equivalence_groups = 0

    comp_idx_deltas: dict[int, int] = defaultdict(int)

    for n_seg, seg in enumerate(segments, 1):
        shard = SHARDS / f"{seg}.json"
        if shard.exists():
            data = json.loads(shard.read_text(encoding="utf-8"))
            per_fill.update(data["rows"])
            comp_idx_checked += data["comp_idx_checked"]
            comp_idx_mismatched += data["comp_idx_mismatched"]
            for k, v in data["comp_idx_deltas"].items():
                comp_idx_deltas[int(k)] += v
            equivalence_groups += data["prefix_rows"]
            print(f"[age-cap] segment {seg} resumed from shard "
                  f"({len(data['rows'])} rows)", flush=True)
            continue
        rows = [r for r in fills if r["segment"] == seg]
        print(f"[age-cap] segment {seg} ({n_seg}/{len(segments)}, "
              f"{len(rows)} rows)", flush=True)
        series_by_tf: dict[str, list] = {}
        close_index: dict[str, dict] = {}
        seg_checked = seg_mismatched = 0
        seg_deltas: dict[int, int] = defaultdict(int)

        for n_row, row in enumerate(rows, 1):
            tf = row["confirmation_tf"]
            if tf not in SERIES_KEY:
                fail_loud(f"unmapped confirmation TF {tf!r} for {row['id']}")
            if tf not in series_by_tf:
                series_by_tf[tf] = segment_series(seg)[SERIES_KEY[tf]]
                minutes = TF_MINUTES[tf]
                series = series_by_tf[tf]
                close_index[tf] = {
                    bar.timestamp + timedelta(minutes=minutes): i
                    for i, bar in enumerate(series)}
            series = series_by_tf[tf]
            ts = row["completion_ts"]
            try:
                target_ts = datetime.fromisoformat(ts)
            except ValueError:
                fail_loud(f"unparseable completion_ts {ts!r} for {row['id']}")
            idx = close_index[tf].get(target_ts, -1)
            if idx < 0:
                fail_loud(f"completion bar (close {ts}) not on {tf} series of {seg}")

            atr = latest_atr(series[: idx + 1], ATR_PERIOD)
            if not atr or atr <= 0:
                fail_loud(f"no honest ATR at {row['id']}")
            direction = (Direction.LONG if row["direction"] == "long"
                         else Direction.SHORT)

            # PLACE-TIME PREFIX ONLY. Full-series detection is NOT equivalent:
            # a swing whose extreme sits 1-2 bars before the placement bar can
            # be confirmed before it, yet is invisible at place time because
            # its right-hand confirmation window is not complete (measured:
            # 2953.348 full-series vs 2944.648 prefix on feb25). The engine has
            # the same blind spot, so prefix detection is the faithful method.
            swings = detect_swings(series[: idx + 1], getattr(Timeframe, tf))
            equivalence_groups += 1

            per_fill[row["id"]] = probe_row(
                row, swings, float(atr), idx, direction)

            p4_comp = p4.get(row["id"], {}).get("comp_idx", "")
            if p4_comp not in ("", None):
                seg_checked += 1
                if int(p4_comp) != idx:
                    seg_mismatched += 1
                seg_deltas[idx - int(p4_comp)] += 1
            if n_row % 25 == 0:
                print(f"[age-cap] {seg} {n_row}/{len(rows)} rows", flush=True)

        # persist this segment, then free it (peak memory stays flat and a
        # killed run resumes instead of restarting from zero)
        SHARDS.mkdir(parents=True, exist_ok=True)
        seg_rows = {r["id"]: per_fill[r["id"]] for r in rows}
        shard.write_text(json.dumps({
            "rows": seg_rows,
            "prefix_rows": len(rows),
            "comp_idx_checked": seg_checked,
            "comp_idx_mismatched": seg_mismatched,
            "comp_idx_deltas": {str(k): v for k, v in seg_deltas.items()},
        }), encoding="utf-8")
        comp_idx_checked += seg_checked
        comp_idx_mismatched += seg_mismatched
        for k, v in seg_deltas.items():
            comp_idx_deltas[k] += v
        series_by_tf.clear()
        close_index.clear()
        menu_window._SEGMENT_CACHE.pop(seg, None)

    missing = [s for s in segments if not (SHARDS / f"{s}.json").exists()]
    if missing:
        print(f"[age-cap] INCOMPLETE: {len(missing)} segment(s) missing "
              f"{missing}; rerun to resume", flush=True)
        return 3

    print(f"[age-cap] prefix-bounded reconstructions: {equivalence_groups}"
          f" rows (no full-series detection anywhere)", flush=True)
    print(f"[age-cap] comp_idx vs P4: {comp_idx_checked - comp_idx_mismatched}"
          f"/{comp_idx_checked} match", flush=True)
    if comp_idx_mismatched:
        print(f"[age-cap] WARNING: {comp_idx_mismatched} comp_idx mismatches; "
              f"delta histogram (mine - P4): "
              f"{dict(sorted(comp_idx_deltas.items(), key=lambda kv: -kv[1])[:6])}",
              flush=True)

    # ---- validation: probe 20 must reproduce P4's split ----
    base_struct = [f for f, r in per_fill.items() if r["age20_target"] is not None]
    base_fallback = [f for f, r in per_fill.items() if r["age20_target"] is None]
    print(f"[age-cap] baseline(20): structural {len(base_struct)} / "
          f"fallback {len(base_fallback)} (P4 predicts {P4_STRUCTURAL} / "
          f"{P4_FALLBACK})", flush=True)
    baseline_matches_p4 = (len(base_struct) == P4_STRUCTURAL
                           and set(base_fallback) == p4_ids)
    disagreement = sorted(set(base_fallback) ^ p4_ids)
    if len(disagreement) > 8:
        fail_loud(f"baseline disagrees with P4 on {len(disagreement)} rows "
                  f"— reconstruction method differs, not an one-bar offset")
    if disagreement:
        print(f"[age-cap] baseline/P4 disagreement: {len(disagreement)} rows "
              f"{disagreement}", flush=True)
        for fid in disagreement:
            rec = per_fill[fid]
            print(f"[age-cap]   {fid} tf={rec['confirmation_tf']} "
                  f"idx={rec['completion_index']} atr={rec['atr']:.4f} "
                  f"mine={rec['age20_target']} "
                  f"p4_comp_idx={p4.get(fid, {}).get('comp_idx')} "
                  f"p4_min_age={p4.get(fid, {}).get('min_age_fav_swing_bars')}",
                  flush=True)

    # ---- metrics ----
    summary: dict = {
        "population": {
            "book": "F", "fills": len(per_fill),
            "baseline_structural": len(base_struct),
            "baseline_fallback": len(base_fallback),
            "p4_split_reproduced": baseline_matches_p4,
            "p4_fallback_id_set_matched": set(base_fallback) == p4_ids,
            "p4_disagreement_ids": disagreement,
            "p4_comp_idx_matched": comp_idx_checked - comp_idx_mismatched,
            "p4_comp_idx_checked": comp_idx_checked,
            "prefix_bounded_rows": equivalence_groups,
            "comp_idx_delta_histogram": {str(k): v for k, v in
                                         sorted(comp_idx_deltas.items())},
            "prefix_only_note": (
                "detect_swings is applied to series[:idx+1] only; full-series "
                "detection would leak bars after the placement bar into swing "
                "formation (measured divergence on feb25: 2953.348 vs 2944.648)."),
        },
        "probes": {},
        "contract": {
            "source": "00_LOCKED/STRUCTURAL_TP_AGE_CAP_DESIGN.md §4",
            "diagnostic_only": True, "no_expectancy": True, "book_scoped": True,
            "probe_cap_bars_by_tf": {p: {tf: cap_for(p, tf) for tf in TF_MINUTES}
                                     for p in PROBES},
        },
    }

    for probe in PROBES:
        structural = [f for f, r in per_fill.items()
                      if r[f"{probe}_target"] is not None]
        recovered = [f for f in base_fallback
                     if per_fill[f][f"{probe}_target"] is not None]
        ages = [per_fill[f][f"{probe}_age_bars"] for f in structural]
        ages_min = [per_fill[f][f"{probe}_age_min"] for f in structural]
        dists = [abs(per_fill[f][f"{probe}_target"] - per_fill[f]["entry"])
                 / per_fill[f]["atr"] for f in structural]
        churned = [f for f in base_struct
                   if per_fill[f][f"{probe}_target"] is not None
                   and abs(per_fill[f][f"{probe}_target"]
                           - per_fill[f]["age20_target"]) > 1e-12]
        stale_24h = [f for f in recovered
                     if (per_fill[f][f"{probe}_age_min"] or 0) > 1440]
        over_7d = [f for f in recovered
                   if (per_fill[f][f"{probe}_age_min"] or 0) > 10080]
        by_tf: dict[str, dict] = defaultdict(lambda: {"fallback": 0, "recovered": 0})
        for f in base_fallback:
            by_tf[per_fill[f]["confirmation_tf"]]["fallback"] += 1
            if per_fill[f][f"{probe}_target"] is not None:
                by_tf[per_fill[f]["confirmation_tf"]]["recovered"] += 1

        recovered_p4 = [f for f in p4_ids
                        if per_fill[f][f"{probe}_target"] is not None]
        recovery_pct = 100.0 * len(recovered) / len(base_fallback)
        churn_pct = 100.0 * len(churned) / len(base_struct)
        stale_pct = 100.0 * len(stale_24h) / len(recovered) if recovered else 0.0

        flags = []
        if probe != "age20" and recovery_pct < 25.0:
            flags.append("K1_NULL_RECOVERY")
        if stale_pct > 20.0 or over_7d:
            flags.append("K2_STALE_CAUTION")
        if churn_pct > 10.0:
            flags.append("K3_SELECTION_CHANGE")
        if probe == "none" and len(recovered) == len(base_fallback):
            flags.append("NOTE_RECOVERY_SATURATED_BY_CONSTRUCTION")

        summary["probes"][probe] = {
            "structural_share": {
                "n": len(structural), "of": len(per_fill),
                "pct": round(100.0 * len(structural) / len(per_fill), 2)},
            "recovery": {
                "n": len(recovered), "of": len(base_fallback),
                "pct": round(recovery_pct, 2),
                "on_p4_129": {"n": len(recovered_p4), "of": len(p4_ids),
                              "pct": round(100.0 * len(recovered_p4) / len(p4_ids), 2)},
                "by_confirmation_tf": {
                    tf: {**v, "pct": round(100.0 * v["recovered"] / v["fallback"], 1)
                         if v["fallback"] else None}
                    for tf, v in sorted(by_tf.items())}},
            "selected_age_bars": {
                "n": len(ages), "p50": quantile(ages, 0.50),
                "p90": quantile(ages, 0.90), "max": max(ages) if ages else None},
            "selected_age_wall_min": {
                "p50": quantile(ages_min, 0.50), "p90": quantile(ages_min, 0.90),
                "max": max(ages_min) if ages_min else None},
            "tp_distance_atr": {
                "n": len(dists), "p50": quantile(dists, 0.50),
                "p90": quantile(dists, 0.90)},
            "churn_vs_baseline": {
                "n_changed": len(churned), "of": len(base_struct),
                "pct": round(churn_pct, 2)},
            "staleness": {
                "newly_selected": len(recovered),
                "older_than_24h": len(stale_24h),
                "older_than_24h_pct": round(stale_pct, 2),
                "older_than_7d": len(over_7d),
                "oldest_new_selection_days": round(
                    max([per_fill[f][f"{probe}_age_min"] or 0
                         for f in recovered], default=0) / 1440, 2)},
            "flags": flags,
        }

    OUT.mkdir(parents=True, exist_ok=True)
    fields = ["id", "segment", "confirmation_tf", "direction", "entry", "atr",
              "completion_index"]
    for probe in PROBES:
        fields += [f"{probe}_target", f"{probe}_age_bars", f"{probe}_age_min",
                   f"{probe}_cap"]
    with (OUT / "per_fill.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for fid in sorted(per_fill):
            writer.writerow(per_fill[fid])
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    for probe in PROBES:
        p = summary["probes"][probe]
        print(f"[age-cap] {probe:7s} structural {p['structural_share']['n']}"
              f"/{p['structural_share']['of']}"
              f"  recovery {p['recovery']['n']}/{p['recovery']['of']}"
              f" ({p['recovery']['pct']}%)"
              f"  age p50/p90 {p['selected_age_bars']['p50']}/"
              f"{p['selected_age_bars']['p90']} bars"
              f"  churn {p['churn_vs_baseline']['pct']}%"
              f"  flags {p['flags']}", flush=True)
    print(f"[age-cap] artifacts: {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
