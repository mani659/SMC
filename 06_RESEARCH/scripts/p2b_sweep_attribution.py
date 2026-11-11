#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P2b — sweep attribution over the pool + co-location census (research).

Reuses the P2a pool generation and ``smc.liquidity.attribute_sweeps`` (which
in turn reuses ``detect_sweep``). No ranking, no winner selection, no wiring.

HARD BANS honoured: detection math untouched, EQH/EQL never pooled, no
live/paper/trigger/risk changes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from plan_complement_ledger import load_m1
from smc.config.timeframe import Timeframe
from smc.data.resample import resample_ohlcv
from smc.liquidity import LiquidityPool, attribute_sweeps

from p2a_pool_inventory import (
    DATA_PATH,
    EXEC_END,
    EXEC_START,
    PERIODIC_TF,
    SESSION_TF,
    STRUCTURAL_TF,
    WARMUP_START,
    periodic_pool_levels,
    session_pool_levels,
    structural_pool_levels,
)

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "p2b_sweep_attribution"
SAMPLE_CAP = 300


def _iso(ts):
    return "" if ts is None else ts.isoformat()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log = []

    def L(message):
        print(message, flush=True)
        log.append(message)

    if not DATA_PATH.exists():
        L(f"[p2b] FAIL missing data: {DATA_PATH}")
        return 2

    m1_all = load_m1(DATA_PATH, WARMUP_START, EXEC_END + timedelta(days=1))
    if not m1_all:
        L("[p2b] FAIL no M1 bars")
        return 2
    m1_exec = [c for c in m1_all if EXEC_START <= c.timestamp <= EXEC_END]
    h4_all = resample_ohlcv(m1_all, PERIODIC_TF)
    h4_exec = [c for c in h4_all if EXEC_START - timedelta(days=1) <= c.timestamp <= EXEC_END]
    m5_exec = resample_ohlcv(m1_exec, SESSION_TF)
    L(f"[p2b] m1={len(m1_all)} h4={len(h4_all)} m5_exec={len(m5_exec)}")

    days = sorted({c.timestamp.date() for c in h4_exec})
    levels = []
    levels += periodic_pool_levels(h4_all, PERIODIC_TF, days)
    levels += session_pool_levels(m5_exec)
    levels += structural_pool_levels(h4_all, STRUCTURAL_TF)

    pool = LiquidityPool()
    for level in sorted(
        levels, key=lambda lv: (lv.enter_at, lv.family.value, lv.side.value, lv.period_id)
    ):
        try:
            pool.add(level)
        except ValueError as exc:
            L(f"[p2b] skip {level.level_id}: {exc}")
    L(f"[p2b] levels registered={len(pool)}")

    # ---- attribution, grouped by the series each level's source_tf refers to
    by_tf = defaultdict(list)
    for level in pool.all_levels():
        by_tf[level.source_tf].append(level)

    series_for = {PERIODIC_TF: h4_all, SESSION_TF: m5_exec}
    hits = []
    not_applicable = []
    for tf, tf_levels in sorted(by_tf.items(), key=lambda kv: kv[0].name):
        series = series_for.get(tf)
        if series is None:
            L(f"[p2b] FAIL no series for source_tf={tf.name}")
            return 3
        report = attribute_sweeps(pool, series, levels=tf_levels)
        hits.extend(report.hits)
        not_applicable.extend(report.not_applicable)
        L(f"[p2b] tf={tf.name} levels={len(tf_levels)} hits={len(report.hits)} n/a={len(report.not_applicable)}")

    hits.sort(key=lambda h: (h.sweep_bar_index, h.sweep_bar_ts, h.family, h.side, h.period_id))

    # ---- artifacts
    per_family = defaultdict(list)
    for hit in hits:
        per_family[(hit.family, hit.side)].append(hit)

    hits_by_family_path = OUT_DIR / "hits_by_family.csv"
    with hits_by_family_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["family", "side", "n_hits", "first_hit_ts", "last_hit_ts"]
        )
        writer.writeheader()
        for (family, side), group in sorted(per_family.items()):
            stamps = sorted(h.sweep_bar_ts for h in group)
            writer.writerow({
                "family": family,
                "side": side,
                "n_hits": len(group),
                "first_hit_ts": _iso(stamps[0]),
                "last_hit_ts": _iso(stamps[-1]),
            })

    bars = defaultdict(list)
    for hit in hits:
        bars[hit.sweep_bar_ts].append(hit)

    multi = {ts: group for ts, group in bars.items() if len(group) >= 2}
    colocation_path = OUT_DIR / "colocation_by_bar.csv"
    with colocation_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["bar_ts", "bar_index", "n_hits", "level_ids"]
        )
        writer.writeheader()
        for ts in sorted(multi):
            group = multi[ts]
            writer.writerow({
                "bar_ts": _iso(ts),
                "bar_index": group[0].sweep_bar_index,
                "n_hits": len(group),
                "level_ids": ";".join(
                    f"{h.family}|{h.side}|{h.period_id}" for h in group
                ),
            })

    sample_path = OUT_DIR / "sample_hits.csv"
    with sample_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["family", "side", "period_id", "price", "sweep_bar_ts",
                        "sweep_bar_index", "direction", "enter_at", "start_index_used"],
        )
        writer.writeheader()
        for hit in hits[:SAMPLE_CAP]:
            writer.writerow({
                "family": hit.family,
                "side": hit.side,
                "period_id": hit.period_id,
                "price": hit.price,
                "sweep_bar_ts": _iso(hit.sweep_bar_ts),
                "sweep_bar_index": hit.sweep_bar_index,
                "direction": hit.direction,
                "enter_at": _iso(hit.enter_at),
                "start_index_used": hit.start_index_used,
            })

    swept_ids = {h.level_id for h in hits}
    never_swept = Counter()
    for level in pool.all_levels():
        if level.level_id not in swept_ids:
            never_swept[f"{level.family.value}__{level.side.value}"] += 1

    hits_by_family_side = {
        f"{family}__{side}": len(group) for (family, side), group in sorted(per_family.items())
    }
    summary = {
        "pack": "P2B_SWEEP_ATTRIBUTION",
        "window": {
            "start": _iso(EXEC_START),
            "end": _iso(EXEC_END),
            "warmup_start": _iso(WARMUP_START),
        },
        "start_index_rule": "enter_at",
        "cadence": "event-driven: one first-sweep scan per registered pool level",
        "n_levels_registered": len(pool),
        "n_sweep_events_checked": len(pool),
        "n_hits": len(hits),
        "hits_by_family_side": hits_by_family_side,
        "n_bars_with_hits": len(bars),
        "n_bars_multi_hit": len(multi),
        "max_hits_one_bar": max((len(g) for g in bars.values()), default=0),
        "eqh_hits": 0,
        "not_applicable_levels": len(not_applicable),
        "never_swept_by_family_side": dict(sorted(never_swept.items())),
        "series": {
            "periodic_structural": PERIODIC_TF.name,
            "session": SESSION_TF.name,
        },
        "notes": [
            "Scan bound is the first bar with timestamp >= level.enter_at; formed_at is never passed to the detector.",
            "detect_sweep returns the first sweep per level, so a level contributes at most one hit.",
            "Multi-hit bars are emitted in full; no winner is selected (ranking is not frozen).",
            "EQH/EQL is not a pool family, so eqh_hits is structurally zero.",
            "Structural 'broken' exit and ranking remain out of scope for P2b.",
        ],
    }

    summary_path = OUT_DIR / "summary.json"
    summary_text = json.dumps(summary, indent=2)
    summary_path.write_text(summary_text, encoding="utf-8")

    # dual-run determinism (semantic: summary text + hits_by_family bytes)
    hits_sha = hashlib.sha256(hits_by_family_path.read_bytes()).hexdigest()
    summary_sha = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    tmp = OUT_DIR / "_determinism_summary.json"
    tmp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    same = hashlib.sha256(tmp.read_bytes()).hexdigest() == summary_sha
    tmp.unlink()

    L(f"[p2b] hits={len(hits)} by_family={hits_by_family_side}")
    L(f"[p2b] multi_hit_bars={len(multi)} max_per_bar={summary['max_hits_one_bar']} n/a={len(not_applicable)}")
    L(f"[p2b] determinism={same} summary_sha={summary_sha} hits_csv_sha={hits_sha}")

    (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    return 0 if same else 3


if __name__ == "__main__":
    raise SystemExit(main())
