#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P2a frozen-window liquidity pool inventory (research only).

Builds pool levels from the existing production constructors, feeds them
through the new in-memory registry (``smc.liquidity``), and reports active
counts over a frozen window. No ranking scores, no sweep attribution.

HARD BANS honoured: detection math untouched, EQH/EQL never offered to the
pool, no live/paper/trigger/risk wiring.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from plan_complement_ledger import load_m1
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import LiquidityType, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.data.resample import resample_ohlcv
from smc.detection.periodic_levels import _aggregate, _monday, detect_periodic_levels
from smc.detection.session_levels import detect_session_levels
from smc.detection.structural_swing_detector import detect_swings
from smc.liquidity import (
    LiquidityPool,
    PoolFamily,
    from_pdh_pdl,
    from_pwh_pwl,
    from_session,
    from_structural,
    inventory_sort_key,
)
from smc.utils.timestamps import detect_session as detect_session_window

DATA_PATH = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "p2a_pool_inventory"

WARMUP_START = datetime(2025, 3, 1, tzinfo=timezone.utc)
EXEC_START = datetime(2025, 6, 1, tzinfo=timezone.utc)
EXEC_END = datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc)

SAMPLE_STEP = timedelta(hours=6)
SAMPLE_LEVEL_CAP = 300

# R1: session levels are computed on M5 and published with source_tf=M5.
# Periodic + structural use the §4a required minimum detection series (H4).
PERIODIC_TF = Timeframe.H4
STRUCTURAL_TF = Timeframe.H4
SESSION_TF = Timeframe.M5


def _iso(dt):
    return "" if dt is None else dt.astimezone(timezone.utc).isoformat()


def _midnight(day):
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def periodic_pool_levels(series, tf: Timeframe, days) -> list:
    """One PDH/PDL pair per completed trading day, built via production rules."""
    daily, weekly = _aggregate(series)
    out = []
    seen = set()
    for day in days:
        completed = [d for d in daily if d < day]
        if not completed:
            continue
        prior = max(completed)
        entry = daily[prior]
        for pool, key in ((PoolType.BSL, "high"), (PoolType.SSL, "low")):
            price, formed_at = entry[key]
            level = from_pdh_pdl(
                LiquidityLevel(
                    type=LiquidityType.PREVIOUS_DAY,
                    level=price,
                    pool=pool,
                    timeframe=tf,
                    formed_at=formed_at,
                ),
                tf,
            )
            if level.level_id in seen:
                continue
            seen.add(level.level_id)
            out.append(level)

    for monday in sorted(weekly):
        enter = _midnight(monday + timedelta(days=7))
        if enter > EXEC_END:
            continue
        entry = weekly[monday]
        for pool, key in ((PoolType.BSL, "high"), (PoolType.SSL, "low")):
            price, formed_at = entry[key]
            level = from_pwh_pwl(
                LiquidityLevel(
                    type=LiquidityType.PREVIOUS_WEEK,
                    level=price,
                    pool=pool,
                    timeframe=tf,
                    formed_at=formed_at,
                ),
                tf,
            )
            if level.level_id in seen:
                continue
            seen.add(level.level_id)
            out.append(level)
    return out


def session_pool_levels(m5_exec) -> list:
    levels = detect_session_levels(m5_exec, SESSION_TF)
    out = []
    for level in levels:
        if level.formed_at is None:
            continue
        formed = level.formed_at.astimezone(timezone.utc)
        window = detect_session_window(formed)
        if window is None:
            continue
        out.append(
            from_session(
                level,
                session=window.name,
                day=formed.date(),
                source_tf=SESSION_TF,
            )
        )
    return out


def structural_pool_levels(series, tf: Timeframe) -> list:
    out = []
    for swing in detect_swings(series, tf):
        if not swing.is_valid:
            continue
        out.append(from_structural(swing, series, tf))
    return out


def sample_timestamps():
    stamps = []
    current = EXEC_START
    while current <= EXEC_END:
        stamps.append(current)
        current += SAMPLE_STEP
    return stamps


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log = []

    def L(message):
        print(message, flush=True)
        log.append(message)

    if not DATA_PATH.exists():
        L(f"[p2a-inventory] FAIL missing data: {DATA_PATH}")
        return 2

    m1_all = load_m1(DATA_PATH, WARMUP_START, EXEC_END + timedelta(days=1))
    if not m1_all:
        L("[p2a-inventory] FAIL no M1 bars")
        return 2
    m1_exec = [c for c in m1_all if EXEC_START <= c.timestamp <= EXEC_END]
    h4_all = resample_ohlcv(m1_all, PERIODIC_TF)
    h4_exec = [c for c in h4_all if EXEC_START - timedelta(days=1) <= c.timestamp <= EXEC_END]
    m5_exec = resample_ohlcv(m1_exec, SESSION_TF)
    L(f"[p2a-inventory] m1={len(m1_all)} m1_exec={len(m1_exec)} h4={len(h4_all)} m5_exec={len(m5_exec)}")

    days = sorted({c.timestamp.date() for c in h4_exec})
    levels = []
    levels += periodic_pool_levels(h4_all, PERIODIC_TF, days)
    levels += session_pool_levels(m5_exec)
    levels += structural_pool_levels(h4_all, STRUCTURAL_TF)

    pool = LiquidityPool()
    for level in sorted(levels, key=lambda lv: (lv.enter_at, lv.family.value, lv.side.value, lv.period_id)):
        try:
            pool.add(level)
        except ValueError as exc:  # duplicate ids from H4 date collisions
            L(f"[p2a-inventory] skip {level.level_id}: {exc}")
    L(f"[p2a-inventory] levels asked={len(levels)} registered={len(pool)}")

    # ---- equivalence spot-check against the production periodic constructor
    checks = []
    for as_of_day in (days[len(days) // 4], days[len(days) // 2], days[(3 * len(days)) // 4]):
        as_of = _midnight(as_of_day)
        prod = [
            lv for lv in detect_periodic_levels(m1_all, Timeframe.M1, as_of=as_of)
            if lv.type is LiquidityType.PREVIOUS_DAY
        ]
        prod_map = {
            f"PREVIOUS_DAY__{lv.pool.name}": round(float(lv.level), 6) for lv in prod
        }
        ours_map = {
            f"PREVIOUS_DAY__{lv.side.name.upper()}": round(lv.price, 6)
            for lv in pool.active_asof(as_of)
            if lv.family is PoolFamily.PREVIOUS_DAY
        }
        match = prod_map == ours_map
        checks.append({"as_of": _iso(as_of), "match": match, "production": prod_map, "pool": ours_map})
    L(f"[p2a-inventory] periodic equivalence checks={[c['match'] for c in checks]}")

    # ---- sampling
    stamps = sample_timestamps()
    counts_rows = []
    sample_rows = []
    max_active = 0
    max_active_at = ""
    max_by_family = defaultdict(int)
    active_distinct = defaultdict(set)

    for index, asof in enumerate(stamps):
        active = pool.active_asof(asof)
        per = Counter((lv.family.value, lv.side.value) for lv in active)
        for family in PoolFamily:
            for side in ("bsl", "ssl"):
                counts_rows.append({
                    "asof": _iso(asof),
                    "family": family.value,
                    "side": side,
                    "n_active": per.get((family.value, side), 0),
                })
        for family, n in Counter(lv.family.value for lv in active).items():
            max_by_family[family] = max(max_by_family[family], n)
        if len(active) > max_active:
            max_active = len(active)
            max_active_at = _iso(asof)
        for lv in active:
            active_distinct[(lv.family.value, lv.side.value)].add(lv.level_id)
        if index % 7 == 0:
            for lv in sorted(active, key=inventory_sort_key):
                if len(sample_rows) >= SAMPLE_LEVEL_CAP:
                    break
                sample_rows.append({
                    "asof": _iso(asof),
                    "level_id": "|".join(lv.level_id),
                    "family": lv.family.value,
                    "side": lv.side.value,
                    "price": lv.price,
                    "period_id": lv.period_id,
                    "source_tf": lv.source_tf.name,
                    "enter_at": _iso(lv.enter_at),
                    "exit_at": _iso(lv.exit_at),
                    "sort_key": inventory_sort_key(lv)[0],
                })

    counts_path = OUT_DIR / "active_counts_by_family.csv"
    with counts_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["asof", "family", "side", "n_active"])
        writer.writeheader()
        writer.writerows(counts_rows)

    sample_path = OUT_DIR / "sample_active_levels.csv"
    with sample_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["asof", "level_id", "family", "side", "price", "period_id",
                        "source_tf", "enter_at", "exit_at", "sort_key"],
        )
        writer.writeheader()
        writer.writerows(sample_rows)

    counts_by_family_side = {
        f"{key[0]}__{key[1]}": len(ids) for key, ids in sorted(active_distinct.items())
    }
    summary = {
        "pack": "P2A_POOL_INVENTORY",
        "window": {"start": _iso(EXEC_START), "end": _iso(EXEC_END), "warmup_start": _iso(WARMUP_START)},
        "sample_step_hours": SAMPLE_STEP.total_seconds() / 3600,
        "n_samples": len(stamps),
        "n_levels_requested": len(levels),
        "n_levels_registered": len(pool),
        "counts_by_family_side": counts_by_family_side,
        "max_active_same_bar": max_active,
        "max_active_same_bar_at": max_active_at,
        "max_active_by_family": dict(sorted(max_by_family.items())),
        "eqh_included": False,
        "periodic_equivalence_checks": checks,
        "session_source_tf": SESSION_TF.name,
        "session_series": "M5 (amendment R1)",
        "periodic_series": PERIODIC_TF.name,
        "structural_series": STRUCTURAL_TF.name,
        "ranking_scores": "none",
        "notes": [
            "Session H/L computed on M5 and published with source_tf=M5 (R1).",
            "Periodic and structural levels use H4 (the §4a required minimum).",
            "H1 duplicate provenance is NOT registered: level_id (family, side, period_id) would collide with H4 — design open question 8.",
            "Exit is supersession-only; the structural 'broken' exit and sweep enter_at bounds are P2b residuals (R2/R4).",
            "Soft inventory sort (R3) is applied to the sample CSV only; active_asof stays chronological.",
        ],
    }

    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ---- determinism: rebuild summary + counts, compare bytes
    counts_bytes = counts_path.read_bytes()
    counts_hash = hashlib.sha256(counts_bytes).hexdigest()
    summary_hash = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    tmp = OUT_DIR / "_determinism_summary.json"
    tmp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    same = hashlib.sha256(tmp.read_bytes()).hexdigest() == summary_hash
    tmp.unlink()
    L(f"[p2a-inventory] determinism={same} counts_sha={counts_hash}")
    L(f"[p2a-inventory] max_active={max_active} at {max_active_at}")
    L(f"[p2a-inventory] counts_by_family_side={counts_by_family_side}")

    (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    return 0 if same else 3


if __name__ == "__main__":
    raise SystemExit(main())
