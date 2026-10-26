#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HTF sweep census, H4 + H1 (read-only — count only).

Lead Architect directive: produce a first-class inventory of HTF sweeps
on H4 and H1 for the frozen 6m window, using the REAL sweep/liquidity
detector path the product uses. No POI arm, no pillars, no LTF triggers
required. No threshold changes (detectors run with frozen params).

Method (one line): liquidity_scanner.scan() builds levels on each TF
series, then sweep_detector.detect_sweep() enumerates every sweep per
level (first + re-fires by advancing start_index — same predicate the
product evaluates); formed_at bounds respected automatically, so a
level can never sweep itself at its formation bar.

Frozen conventions (stated before running):
  * Window: exec 2025-06-01 -> 2025-11-30 (sweep candle inside);
    M1 warm-up from 2025-05-01 (level/swing formation history).
  * Direction bias is a REPORTING convention only (the detector is
    pool-based): BSL -> SHORT (fade the swept highs), SSL -> LONG
    (fade the swept lows); other pools recorded as-is ("pool-side").
  * Unique levels = distinct (pool, level) pairs with >=1 in-window
    sweep (exact float equality — vendor data is 3-decimal, resample
    preserves it; no rounding invented). re-fires = total - unique.
  * Zone link = sweep level inside accepted zone bounds (exact
    containment, no tolerance invented). Accepted set = H4 pack raw +
    D1 subset (same loader rules as the Stage-3 pack).
  * Touch proximity = |sweep M5 index - zone FIRST-touch M5 index| <=
    20 bars (first-touch only, from the decomposed ledger — later
    touches uncounted, conservative undercount, documented).
  * A zone exists from its anchor bar on; touches before anchor are
    impossible by construction (touch list derives from anchored
    zones only).

Outputs: results/htf_sweep_census/sweeps_h4.csv + sweeps_h1.csv +
summary.json. Note: HTF_SWEEP_CENSUS_NOTE.md (separate step).
LOGIC_CHANGED: NO (04_SRC untouched — detectors only CALLED).
"""

from __future__ import annotations

import bisect as _bisect
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
from smc.backtest.data_feed import CandleSeries
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.detection.liquidity_scanner import scan as scan_liquidity
from smc.detection.sweep_detector import detect_sweep

import ltf_confirmation_pack as ltf

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "htf_sweep_census"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — NOT EDGE"

EXEC_FROM = datetime(2025, 6, 1, tzinfo=timezone.utc)
EXEC_TO = datetime(2025, 11, 30, 23, 59, tzinfo=timezone.utc)
LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)
PROXIMITY_BARS = 20

DECOMP_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "decomposed_6m_ledger" /
              "decomposed_events.csv")

CSV_COLUMNS = [
    "event_id", "tf", "bar_ts", "pool", "direction_bias", "level_family",
    "level", "formed_at", "sweep_n_for_level", "is_first_touch",
    "linked_zone_ids", "linked_zone_count",
    "nearest_touch_offset_bars", "within_20_of_zone_touch", "note",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def bias_for_pool(pool_value: str | None) -> str:
    """Reporting-only direction bias for a liquidity pool (frozen map)."""
    pool = (pool_value or "").strip().lower()
    if pool == "bsl":
        return "SHORT"
    if pool == "ssl":
        return "LONG"
    return "pool-side"


def sweep_key(pool_value: str | None, level: float) -> tuple:
    """Unique-level identity: exact (pool, level) — 3-decimal vendor data."""
    return ((pool_value or "").strip().lower(), float(level))


def nearest_touch_offset(sorted_touch_idx: list[int],
                         sweep_idx: int) -> int | None:
    """Signed offset to the nearest zone-touch bar (bisect; None if none)."""
    if not sorted_touch_idx:
        return None
    pos = _bisect.bisect_left(sorted_touch_idx, sweep_idx)
    best = None
    for cand in (pos - 1, pos):
        if 0 <= cand < len(sorted_touch_idx):
            off = sorted_touch_idx[cand] - sweep_idx
            if best is None or abs(off) < abs(best):
                best = off
    return best


def zone_link(zones: list[dict], level: float) -> list[str]:
    """Accepted zones whose bounds contain the level (exact, no tolerance)."""
    return [z["event_id"] for z in zones
            if z["zone_low"] <= level <= z["zone_high"]]


def content_hash(*parts) -> str:
    h = hashlib.sha1("|".join("" if p is None else str(p)
                              for p in parts).encode("utf-8"))
    return h.hexdigest()[:8]


def all_sweeps_for_level(candles, level) -> list:
    """Every sweep of one level in candle order (first + re-fires).

    Pure reuse of sweep_detector.detect_sweep with an advancing
    start_index — the identical wick-pierce + close-back predicate the
    product evaluates (formed_at bounds respected automatically).
    """
    out = []
    start = 0
    while True:
        res = detect_sweep(candles, level, start_index=start)
        if res is None:
            return out
        out.append(res)
        start = res.candle_index + 1


# --------------------------------------------------------------------------- #
# Loading (reuse canonical data + accepted packs — never regenerated)
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_accepted_zones() -> list[dict]:
    """H4 pack raw + D1 subset (same loader rules as the Stage-3 pack)."""
    zones: list[dict] = []
    with open(ltf.H4_EVENTS_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["event_type"] != "poi_raw":
                continue
            ts = datetime.fromisoformat(r["ts_utc"])
            if not (ltf.EXEC_START <= ts <= ltf.EXEC_END):
                continue
            zones.append({"event_id": r["event_id"],
                          "zone_low": float(r["zone_low"]),
                          "zone_high": float(r["zone_high"])})
    if ltf.D1_EVENTS_CSV.exists():
        with open(ltf.D1_EVENTS_CSV, encoding="utf-8") as f:
            d1 = [r for r in csv.DictReader(f)
                  if r["event_type"] == "poi_raw"]
        for r in ltf._spread(sorted(d1, key=lambda r: r["ts_utc"]),
                             ltf.MAX_D1_SUBSET):
            ts = datetime.fromisoformat(r["ts_utc"])
            if not (ltf.EXEC_START <= ts <= ltf.EXEC_END):
                continue
            zones.append({"event_id": r["event_id"],
                          "zone_low": float(r["zone_low"]),
                          "zone_high": float(r["zone_high"])})
    return zones


def load_zone_touch_m5(m5_keys: dict[str, int]) -> list[int]:
    """First-touch M5 indices of accepted zones (decomposed ledger, read)."""
    touches: list[int] = []
    with open(DECOMP_CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("concept") != "htf-zone":
                continue
            off = r.get("first_touch_offset")
            ts = r.get("ts_utc")
            if not off or not ts:
                continue
            try:
                anchor = m5_keys.get(
                    datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M"))
                if anchor is None:
                    continue
                touches.append(anchor + int(off))
            except (ValueError, TypeError):
                continue
    return sorted(touches)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def census_one_tf(tf: Timeframe, tf_bars: list, zones: list[dict],
                  touch_idx: list[int], m5_keys: dict[str, int]) -> tuple[list[dict], dict]:
    """Full sweep census on one TF series (levels + every re-fire)."""
    levels = scan_liquidity(tf_bars, tf)
    rows: list[dict] = []
    per_level_n: Counter = Counter()
    for lv in levels:
        pool = getattr(lv.pool, "value", lv.pool)
        key = sweep_key(pool, lv.level)
        nth = 0
        for res in all_sweeps_for_level(tf_bars, lv):
            nth += 1
            ts = res.candle.timestamp
            if not (EXEC_FROM <= ts <= EXEC_TO):
                continue
            per_level_n[key] += 1
            fam = getattr(lv.type, "value", lv.type)
            formed = lv.formed_at.isoformat() if lv.formed_at is not None \
                else ""
            linked = zone_link(zones, lv.level)
            sweep_m5 = m5_keys.get(ts.strftime("%Y-%m-%d %H:%M"))
            off = (nearest_touch_offset(touch_idx, sweep_m5)
                   if sweep_m5 is not None else None)
            rows.append({
                "event_id": f"sw-{tf.name.lower()}-{content_hash(ts.isoformat(), pool, lv.level, fam)}",
                "tf": tf.name,
                "bar_ts": ts.isoformat(),
                "pool": pool,
                "direction_bias": bias_for_pool(pool),
                "level_family": fam,
                "level": lv.level,
                "formed_at": formed,
                "sweep_n_for_level": nth,
                "is_first_touch": nth == 1,
                "linked_zone_ids": ";".join(linked),
                "linked_zone_count": len(linked),
                "nearest_touch_offset_bars": off,
                "within_20_of_zone_touch": (
                    off is not None and abs(off) <= PROXIMITY_BARS),
                "note": "",
            })
    # is_first_touch is per-LEVEL globally (incl. pre-window sweeps): fix up
    # rows whose level also swept before the exec window.
    seen: set = set()
    for r in sorted(rows, key=lambda r: (r["bar_ts"], r["event_id"])):
        k = sweep_key(r["pool"], r["level"])
        r["is_first_touch"] = k not in seen
        seen.add(k)
    unique_levels = {sweep_key(r["pool"], r["level"]) for r in rows}
    return rows, {
        "n_sweeps": len(rows),
        "n_levels_formed": len(levels),
        "unique_levels_swept": len(unique_levels),
        "refires": len(rows) - len(unique_levels),
        "by_pool": dict(Counter(r["pool"] for r in rows)),
        "by_bias": dict(Counter(r["direction_bias"] for r in rows)),
        "by_family": dict(Counter(r["level_family"] for r in rows)),
        "linked_sweeps": sum(1 for r in rows if r["linked_zone_count"] > 0),
        "within20_sweeps": sum(1 for r in rows
                                if r["within_20_of_zone_touch"] is True),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    parquet = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not parquet.exists():
        raise SystemExit(f"canonical dataset missing: {parquet}")
    m1_all = load_ohlcv_parquet(str(parquet), Timeframe.M1)
    m1 = [c for c in m1_all
          if LOAD_FROM <= c.timestamp <= EXEC_TO + timedelta(days=1)]
    if not m1:
        raise SystemExit("no M1 bars in the load window")
    multi = resample_multi(m1, [Timeframe.H4, Timeframe.H1, Timeframe.M5])
    h4, h1, m5_list = (multi[Timeframe.H4], multi[Timeframe.H1],
                       multi[Timeframe.M5])
    m5_keys: dict[str, int] = {}
    for i, c in enumerate(m5_list):
        m5_keys.setdefault(c.timestamp.strftime("%Y-%m-%d %H:%M"), i)
    print(f"[census] H4={len(h4)} H1={len(h1)} M5={len(m5_list)}", flush=True)

    zones = load_accepted_zones()
    print(f"[census] accepted zones={len(zones)}", flush=True)
    touch_idx = load_zone_touch_m5(m5_keys)
    print(f"[census] zone first-touch bars={len(touch_idx)}", flush=True)

    all_rows: list[dict] = []
    per_tf: dict[str, dict] = {}
    for tf, bars in (("H4", h4), ("H1", h1)):
        rows, stats = census_one_tf(Timeframe[tf], bars, zones, touch_idx,
                                    m5_keys)
        all_rows.extend(rows)
        per_tf[tf] = stats
        out_csv = OUT_DIR / f"sweeps_{tf.lower()}.csv"
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for r in rows:
                writer.writerow({c: ("" if r.get(c) is None else r.get(c))
                                 for c in CSV_COLUMNS})
        print(f"[census] {tf}: sweeps={stats['n_sweeps']} "
              f"unique={stats['unique_levels_swept']} "
              f"pools={stats['by_pool']}", flush=True)

    summary = {
        "banner": BANNER,
        "window": {"exec_from": EXEC_FROM.isoformat(),
                   "exec_to": EXEC_TO.isoformat(),
                   "m1_warm_up_from": LOAD_FROM.isoformat()},
        "method": ("liquidity_scanner.scan() levels per TF + "
                   "sweep_detector.detect_sweep() every sweep per level "
                   "(first + re-fires); formed_at bounds respected; "
                   "frozen params throughout"),
        "frozen_conventions": {
            "direction_bias": "BSL->SHORT, SSL->LONG (reporting only)",
            "unique_level": "exact (pool, level); 3-decimal vendor data",
            "zone_link": "level inside accepted zone bounds (exact)",
            "touch_proximity": (f"|sweep-touch| <= {PROXIMITY_BARS} M5 bars; "
                                "zone FIRST-touch list only (later touches "
                                "uncounted — conservative undercount)"),
        },
        "inputs": {
            "parquet": "07_DATA/XAUUSD_M1.parquet",
            "h4_pack": str(ltf.H4_EVENTS_CSV.relative_to(REPO_ROOT)),
            "d1_pack": (str(ltf.D1_EVENTS_CSV.relative_to(REPO_ROOT))
                        if ltf.D1_EVENTS_CSV.exists() else "absent"),
            "touch_source": ("results/decomposed_6m_ledger/"
                             "decomposed_events.csv (zone first-touch)"),
        },
        "accepted_zones": len(zones),
        "zone_touch_bars": len(touch_idx),
        "per_tf": per_tf,
        "clarification": ("These counts are a pure H4/H1 sweep-detector "
                          "census — NOT the decomposed ledger's 5,553 "
                          "structure-linked LTF sweep rows, NOT the 658 H4 "
                          "POI structures, NOT product fills."),
        "limitations": [
            "Per-bar enumeration counts re-fires of the same level as "
            "separate events (unique-level counts alongside for the "
            "setup-level read).",
            "Direction bias is a reporting convention on pools, not a "
            "trade signal.",
            "Touch proximity uses FIRST touches only (later touches "
            "uncounted).",
            "No gate, no threshold, no live rule follows (see note).",
        ],
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[census] wrote {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
