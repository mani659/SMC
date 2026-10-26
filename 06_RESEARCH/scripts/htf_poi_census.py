#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HTF POI census — flowchart Step 1 (read-only — count only).

Lead Architect directive (research re-anchor): count the HTF POIs the
engine actually emits — by TF and kind — BEFORE any sweep/LTF/entry
analysis. No POI arm, no pillars, no sweeps, no triggers required.

Reuse-or-redetect decision (documented): the H4/D1 review packs do NOT
use product emission (H4 raw rows come from M8HtfDemandSupply._zones,
an M8-only enumerator; merged rows via validate_window) — so this
census RE-DETECTS with the real product path and discloses the
difference. Pack CSVs are referenced for comparison, never as inputs.

Product path used (cited modules, frozen params throughout):
  * M1-M7 per TF (H4, H1 — the product's detection TFs): rolling daily
    prefixes -> DetectionDriver(TF).stage0 -> .detect_pois
    (registry M1-M8; constructed WITHOUT htf_candles so M8 emits
    nothing — exactly the product starved of HTF, and M1-M7 never read
    HTF anyway). detect_pois's own skip-recording honored.
  * M8 per HTF input (H4, D1, W1 — M8_HTF_TIMEFRAMES): M8HtfDemandSupply
    ._zones + collapse_episodes (the model's own episode collapse),
    timestamped by start_index (origin order preserved).
  * Merge per group: merge_overlapping (the product merge: same-direction
    overlapping zones, tag union) over first-seen POIs.

Frozen conventions (stated before running):
  * Prefixes step daily (first-seen dating at day granularity);
    prefixes shorter than MIN_PREFIX_BARS=60 bars are skipped (ATR14 +
    swing confirmation need history; counted, never silently dropped).
  * Episode key = (direction, round(bottom,3), round(top,3)) — same
    geometry + side re-detected across days is ONE episode (re-detects
    counted separately, never merged into n).
  * Window membership = first_seen_date inside exec 2025-06-01..11-30.
    n_raw = in-window prefix emissions; n_unique = episodes first-seen
    in-window; re_detects = n_raw - n_unique (approximate: includes
    re-emissions of pre-window episodes — stated, not hidden).
  * Kind language: M1-M7 rows carry MODEL TAGS (no tag->kind map exists
    in code — inventing one would be fabrication); M8 rows carry their
    m8_kind facet (ob | demand_supply | fvg).
  * M1 warm-up from 2025-03-01 (formation history; early-May thin
    prefixes behave like product cold-start — disclosed).

Outputs: results/htf_poi_census/poi_episodes.csv + summary.json.
Note: HTF_POI_CENSUS_NOTE.md (separate step).
LOGIC_CHANGED: NO (04_SRC untouched — detectors only CALLED).
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
sys.path.insert(0, str(SRC_DIR))

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.poi import POI
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.orchestration.detection_driver import DetectionDriver
from smc.poi.confluence_scorer import merge_overlapping
from smc.poi.models.m8_htf_demand_supply import (
    M8HtfDemandSupply,
    collapse_episodes,
)

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "htf_poi_census"
EPISODES_CSV = OUT_DIR / "poi_episodes.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — NOT EDGE"

EXEC_FROM = datetime(2025, 6, 1, tzinfo=timezone.utc).date()
EXEC_TO = datetime(2025, 11, 30, tzinfo=timezone.utc).date()
LOAD_FROM = datetime(2025, 3, 1, tzinfo=timezone.utc)
MIN_PREFIX_BARS = 60

CSV_COLUMNS = [
    "episode_id", "tf", "kind_tag", "all_tags", "m8_kind", "direction",
    "zone_low", "zone_high", "first_seen_date", "n_detections",
    "src",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def episode_key(direction_name: str | None, low: float,
                high: float) -> tuple:
    """Unique-episode identity: same side + same rounded geometry."""
    return ((direction_name or "").upper(), round(float(low), 3),
            round(float(high), 3))


def content_hash(*parts) -> str:
    h = hashlib.sha1("|".join("" if p is None else str(p)
                              for p in parts).encode("utf-8"))
    return h.hexdigest()[:8]


def in_window(day) -> bool:
    """First-seen day inside the frozen exec window (inclusive)."""
    return EXEC_FROM <= day <= EXEC_TO


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    parquet = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not parquet.exists():
        raise SystemExit(f"canonical dataset missing: {parquet}")
    m1_all = load_ohlcv_parquet(str(parquet), Timeframe.M1)
    m1 = [c for c in m1_all if c.timestamp >= LOAD_FROM]
    if not m1:
        raise SystemExit("no M1 bars in the load window")
    multi = resample_multi(m1, [Timeframe.H4, Timeframe.H1, Timeframe.D1,
                                Timeframe.W1])
    series = {tf: multi[tf] for tf in
              (Timeframe.H4, Timeframe.H1, Timeframe.D1, Timeframe.W1)}
    print("[census] " + " ".join(
        f"{tf.name}={len(series[tf])}" for tf in series), flush=True)

    episodes: dict[tuple, dict] = {}
    sightings = 0
    skipped_prefixes = 0
    skipped_models: Counter = Counter()
    m8_unexpected = 0
    raw_by_group: dict[str, Counter] = {}

    def record(tf_name: str, poi, day, src: str,
               kind_tag: str, m8_kind: str | None) -> None:
        """One detection sighting -> episode aggregation (first-seen kept)."""
        nonlocal sightings
        sightings += 1
        if in_window(day):
            raw_by_group.setdefault(src + ":" + tf_name,
                                    Counter())[kind_tag] += 1
        key = (tf_name,) + episode_key(poi.zone.direction.name,
                                       poi.zone.bottom, poi.zone.top)
        day_s = day.isoformat()
        if key not in episodes:
            episodes[key] = {
                "episode_id": f"poi-{tf_name.lower()}-{content_hash(*key)}",
                "tf": tf_name, "kind_tag": kind_tag, "all_tags": kind_tag,
                "m8_kind": m8_kind or "",
                "direction": poi.zone.direction.name,
                "zone_low": poi.zone.bottom, "zone_high": poi.zone.top,
                "first_seen_date": day_s, "n_detections": 0, "src": src,
                "_poi": poi,
            }
        ep = episodes[key]
        ep["n_detections"] += 1
        # Tag union across re-detections (first-seen kind_tag stands as the
        # attribution; all_tags shows every model that ever tagged it).
        tags = sorted(set(ep["all_tags"].split("+")) | {kind_tag})
        ep["all_tags"] = "+".join(tags)

    # ---- M1-M7 per TF (H4, H1): rolling daily prefixes ------------------ #
    for tf in (Timeframe.H4, Timeframe.H1):
        bars = series[tf]
        driver = DetectionDriver(tf)  # no htf_candles: M8 stays silent
        days = sorted({c.timestamp.date() for c in bars})
        for n, day in enumerate(days):
            prefix = [c for c in bars if c.timestamp.date() <= day]
            if len(prefix) < MIN_PREFIX_BARS:
                skipped_prefixes += 1
                continue
            try:
                run = driver.stage0(prefix)
                pois, skipped = driver.detect_pois(
                    prefix, run.swings, run.liquidity_levels)
            except Exception as exc:  # noqa: BLE001 — record, never stop
                skipped_models[f"stage0:{type(exc).__name__}"] += 1
                continue
            for tag, reason in skipped.items():
                skipped_models[f"{tag}:{reason}"] += 1
            for poi in pois:
                if ModelType.M8 in (poi.models or []):
                    m8_unexpected += 1
                    continue  # M8 measured separately (HTF-input census)
                tags = sorted((m.name if hasattr(m, "name") else str(m))
                              for m in (poi.models or [])) or ["untagged"]
                for tag in tags:
                    record(tf.name, poi, day, "m1m7-registry", tag, None)
            if (n + 1) % 60 == 0:
                print(f"[census] {tf.name} day {n + 1}/{len(days)} "
                      f"episodes={len(episodes)}", flush=True)
        print(f"[census] {tf.name} done: episodes={len(episodes)}",
              flush=True)

    # ---- M8 per HTF input (H4, D1, W1): _zones + episode collapse ------- #
    # W1 needs deep history (the product provisions W1 back to 2021; the
    # Mar-Nov census slice holds only ~59 W1 bars): resample W1 from the
    # full parquet for THIS leg only. Documented in the summary.
    print("[census] deep W1 resample for the M8-W1 leg ...", flush=True)
    m1_deep = [c for c in m1_all
               if c.timestamp >= datetime(2021, 1, 1, tzinfo=timezone.utc)]
    w1deep = resample_multi(m1_deep, [Timeframe.W1])[Timeframe.W1]
    print(f"[census] W1 deep bars={len(w1deep)}", flush=True)
    for tf in (Timeframe.H4, Timeframe.D1, Timeframe.W1):
        bars = w1deep if tf is Timeframe.W1 else series[tf]
        if len(bars) < MIN_PREFIX_BARS:
            skipped_prefixes += 1
            continue
        model = M8HtfDemandSupply(tf, htf_candles={tf: bars})
        try:
            raw = list(model._zones(bars, tf))
        except Exception as exc:  # noqa: BLE001 — record, never stop
            skipped_models[f"M8-{tf.name}:{type(exc).__name__}"] += 1
            continue
        for kind, direction, start, _zone in raw:
            if 0 <= start < len(bars):
                day = bars[start].timestamp.date()
                if in_window(day):
                    raw_by_group.setdefault(f"m8-htf:{tf.name}",
                                            Counter())[f"M8-{kind}"] += 1
        for kind, direction, start, zone in collapse_episodes(raw):
            ts = bars[start].timestamp if 0 <= start < len(bars) else None
            if ts is None:
                continue
            direction_name = getattr(direction, "name", str(direction))
            key = (f"M8-{tf.name}",) + episode_key(
                direction_name, zone.bottom, zone.top)
            if key not in episodes:
                episodes[key] = {
                    "episode_id": f"poi-m8-{tf.name.lower()}-{content_hash(*key)}",
                    "tf": f"M8-{tf.name}",
                    "kind_tag": f"M8-{kind}", "all_tags": f"M8-{kind}",
                    "m8_kind": kind,
                    "direction": direction_name,
                    "zone_low": zone.bottom, "zone_high": zone.top,
                    "first_seen_date": ts.date().isoformat(),
                    "n_detections": 0, "src": "m8-htf",
                    "_poi": POI(zone=zone, models=[ModelType.M8],
                                m8_kind=kind),
                }
            episodes[key]["n_detections"] += 1

    # ---- Window split + merge -------------------------------------------- #
    in_win = {k: e for k, e in episodes.items()
              if in_window(datetime.fromisoformat(e["first_seen_date"]).date())}
    groups: dict[str, list[dict]] = {}
    for ep in in_win.values():
        groups.setdefault(ep["src"] + ":" + ep["tf"], []).append(ep)
    merged_counts: dict[str, int] = {}
    for gname, eps in groups.items():
        merged_counts[gname] = len(merge_overlapping(
            [e["_poi"] for e in eps]))

    with open(EPISODES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for ep in sorted(in_win.values(),
                         key=lambda e: (e["first_seen_date"], e["episode_id"])):
            writer.writerow({c: ep[c] for c in CSV_COLUMNS})

    by_tf_kind: dict[str, dict[str, int]] = {}
    by_tf_dir: dict[str, dict[str, int]] = {}
    for ep in in_win.values():
        by_tf_kind.setdefault(ep["tf"], Counter())[ep["kind_tag"]] += 1
        by_tf_dir.setdefault(ep["tf"], Counter())[ep["direction"]] += 1

    summary = {
        "banner": BANNER,
        "frozen": {
            "window": "exec 2025-06-01..11-30 (first_seen_date); "
                      "M1 warm-up 2025-03-01",
            "prefix_step": "daily (first-seen dating at day granularity)",
            "min_prefix_bars": MIN_PREFIX_BARS,
            "m1m7_path": ("DetectionDriver(TF) [no htf_candles] .stage0 + "
                          ".detect_pois per daily prefix (registry M1-M8; "
                          "M8 silent without HTF feed)"),
            "m8_path": ("M8HtfDemandSupply(TF, htf_candles={TF}) ._zones + "
                        "collapse_episodes per HTF series (H4/D1/W1)"),
            "merge": ("merge_overlapping per group over first-seen POIs "
                      "(same-direction overlap, tag union)"),
            "w1_deep_load": ("M8-W1 leg resamples W1 from 2021-01-01 "
                             "(product provisions W1 deep history); all "
                             "other legs use the Mar-Nov slice"),
            "episode_key": "(direction, round(bottom,3), round(top,3))",
            "kind_language": ("M1-M7 rows carry MODEL TAGS (no tag->kind "
                              "map exists in code); M8 rows carry their "
                              "m8_kind facet"),
        },
        "sightings_total": sightings,
        "raw_in_window_by_group": {g: dict(c) for g, c in raw_by_group.items()},
        "re_detects_note": ("per group: raw_in_window minus unique "
                            "episodes (includes re-emissions of pre-window "
                            "episodes)"),
        "skipped_prefixes": skipped_prefixes,
        "skipped_models": dict(skipped_models),
        "m8_tagged_in_registry_runs": m8_unexpected,
        "unique_episodes_in_window": len(in_win),
        "by_tf_kind": {t: dict(c) for t, c in by_tf_kind.items()},
        "by_tf_direction": {t: dict(c) for t, c in by_tf_dir.items()},
        "merged_counts": merged_counts,
        "raw_vs_episodes_note": ("sightings counts every daily-prefix "
                                 "emission (re-detects included); episodes "
                                 "collapse same-geometry re-detections"),
        "pack_comparison": {
            "h4_pack_raw_658": ("different construction (M8-only _zones + "
                                "validate_window merged layer) — NOT reused; "
                                "this census re-detected with the product path"),
            "d1_pack": "same disclaimer (review-pack construction)",
        },
        "limitations": [
            "First-seen dating at day granularity (prefix step); "
            "formation inside a day is not timed.",
            "Thin-history early-May prefixes behave like product "
            "cold-start (out-of-window dates only).",
            "No tag->kind map exists in code: M1-M7 counted by model "
            "tag, M8 by facet - never conflated.",
            "Merge is computed on first-seen POIs (all_tags unions "
            "across re-detects ARE accumulated per episode).",
            "M1-M7 run on H4+H1 only (the product's detection TFs); "
            "D1/W1 emit via M8 only.",
            "No gate, no threshold, no live rule follows (see note).",
        ],
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[census] episodes_in_window={len(in_win)} "
          f"merged={merged_counts}", flush=True)
    print(f"[census] wrote {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
