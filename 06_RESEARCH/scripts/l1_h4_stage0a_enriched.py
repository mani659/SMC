#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L1 — H4 Stage 0A enriched row (sweep × displacement × POI link).

Measurement-only research script (docs/research artifacts). LOGIC_CHANGED: NO.
No 04_SRC edits, no LTF wiring, no orders, no PnL, no expectancy.

Reads as-is (no new detection rules invented):
- plan_complement_ledger.load_m1 (M1 loader)
- smc.data.resample.resample_ohlcv (M1 -> H4)
- smc.detection.structural_swing_detector.detect_swings (for BOS prior swing context)
- smc.detection.liquidity_scanner.scan (Phase 1 H4 levels, ALL_FAMILIES)
- smc.detection.sweep_detector.detect_sweeps (wick-pierce + body-close-back)
- smc.detection.displacement_checker.check_displacement (per-sweep, V1 as-coded)
- smc.detection.fvg_detector.detect_fvgs + smc.utils.atr.atr_series (hoisted, value-equivalent)
- smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply (H4 M8 POI emission, ob/ds/fvg)

Join rules (explicit, deterministic):
- Sweep rows: one row per detected sweep event (SweepResult) in exec window.
  event_id = stable sweep id (H4 candle index + pool + level_type + level).
- Displacement: evaluated for the SAME sweep (same candle/sweep_index, same direction
  SSL->LONG/BSL->SHORT) using most recent prior structural swing extreme of move
  direction before sweep as BOS level (mirrors DetectionDriver._displacement_for_sweep).
  If no prior swing extreme or magnitude/ATR not evaluable -> DISPLACEMENT=UNKNOWN with reason.
- POI link (M8 H4 zones, emitted as-is): LINKED if any H4 M8 POI zone contains the swept
  liquidity level price (inclusive, Zone.contains) AND direction is compatible:
    SSL/BULLISH_SWEEP_SSL row links only to LONG (demand-side) POI zones;
    BSL/BEARISH_SWEEP_BSL row links only to SHORT (supply-side) POI zones.
  No new ATR bands for joining; no price tolerance beyond point containment.
  If multiple POIs qualify, pick deterministically: smallest zone.height, then m8_kind
  priority ob>demand_supply>fvg, then zone bounds, then poi id (stable tie-break).
- Bar equality: sweep and displacement share the same sweep candle/bar (candle_index_h4).
  POI is zone-level (not bar-stamped in join) so join is geometric (zone containment of level).

Chain classes (derived, documented):
  SWEEP_ONLY                sweep Y, displacement N/UNKNOWN, POI NONE
  SWEEP_PLUS_DISPLACEMENT   sweep Y, displacement Y (passed as-coded), POI NONE
  SWEEP_PLUS_POI            sweep Y, displacement N/UNKNOWN, POI LINKED
  FULL_0A                   sweep Y, displacement Y, POI LINKED (all known-true)
  DISPLACEMENT_WITHOUT_SWEEP  (reported only if observed as a standalone row; none
    emitted by this sweep-led pipeline because displacement is evaluated per sweep)
  ORPHAN_POI                POI with no sweep row linking to it in exec window

Window frozen (same convention as L1 H4 pack): exec 2025-06-01T00:00:00Z..2025-11-30T23:59:59Z,
warm-up from 2025-03-01T00:00:00Z. Fail-loud if data missing.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from plan_complement_ledger import load_m1
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, PoolType
from smc.data.resample import resample_ohlcv
from smc.detection.fvg_detector import detect_fvgs
from smc.detection.liquidity_scanner import scan as scan_liquidity, ALL_FAMILIES
from smc.detection.structural_swing_detector import detect_swings
from smc.detection.sweep_detector import detect_sweeps
from smc.detection.displacement_checker import check_displacement
from smc.poi.base_model import most_recent_swing
from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply
from smc.utils.atr import atr_series

DATA_PATH = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "l1_h4_stage0a_enriched"
CHARTS_DIR = OUT_DIR / "charts"

WARMUP_START = datetime(2025, 3, 1, tzinfo=timezone.utc)
EXEC_START = datetime(2025, 6, 1, tzinfo=timezone.utc)
EXEC_END = datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc)

SEED = 20261110
SAMPLE_N = 40
ATR_PERIOD = 14

M8_KIND_PRIORITY = {"ob": 0, "demand_supply": 1, "fvg": 2}


def _iso(dt):
    if dt is None:
        return ""
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def event_row_key(r: dict) -> tuple:
    return (
        r.get("row_kind", ""),
        r.get("event_id", ""),
        r.get("timestamp", ""),
        r.get("pool_family", ""),
        f"{float(r.get('level_price') or 0):.6f}",
        r.get("poi_id", ""),
    )


def rows_hash(rows: list[dict]) -> str:
    blob = json.dumps([event_row_key(r) for r in rows], sort_keys=False).encode()
    return hashlib.sha256(blob).hexdigest()


def _direction_for_sweep(pool: PoolType):
    # mirrors DetectionDriver._displacement_for_sweep: SSL->LONG impulse, BSL->SHORT impulse
    return Direction.LONG if pool is PoolType.SSL else Direction.SHORT


def _compatible_poi_direction(pool: PoolType, poi_direction) -> bool:
    # SSL (bullish sweep of sell-side liquidity, upward rejection) -> LONG/demand zone context
    # BSL (bearish sweep of buy-side liquidity, downward rejection) -> SHORT/supply zone context
    if pool is PoolType.SSL:
        return getattr(poi_direction, "name", str(poi_direction)) == "LONG"
    return getattr(poi_direction, "name", str(poi_direction)) == "SHORT"


def stable_poi_key(poi):
    """Deterministic research key (no 04_SRC change): POI.id is UUID by core design,
    so for measurement stability we derive a stable key from emitted geometry/kind/dir."""
    z = poi.zone
    kind = getattr(poi, "m8_kind", None) or "unknown"
    d = getattr(z.direction, "name", str(z.direction))
    return f"m8h4_{kind}_{d}_{round(float(z.bottom),3)}_{round(float(z.top),3)}".replace(".", "p")


def pick_linked_poi(sweep_row, pois):
    level = float(sweep_row["level_price"])
    pool = sweep_row["_pool_enum"]
    candidates = []
    for p in pois:
        try:
            z = p.zone
            if not z.contains(level):
                continue
            if not _compatible_poi_direction(pool, z.direction):
                continue
            kind = getattr(p, "m8_kind", None) or "unknown"
            rid = stable_poi_key(p)
            candidates.append((z.height, M8_KIND_PRIORITY.get(kind, 99), float(z.bottom), float(z.top), rid, p))
        except Exception:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))
    return candidates[0][5]


def displacement_for_sweep(h4, swings, sweep, fvgs, atr_values):
    """Evaluate displacement as-coded for one sweep; return (flag, fields, reason)."""
    direction = _direction_for_sweep(sweep.pool)
    prior = most_recent_swing(swings, is_high=(direction is Direction.SHORT), before_index=sweep.candle_index)
    if prior is None:
        return "UNKNOWN", None, "no_prior_swing_extreme_for_bos_level"
    atr = atr_values[sweep.candle_index - 1] if (atr_values is not None and sweep.candle_index > 0) else None
    try:
        res = check_displacement(
            h4,
            direction,
            sweep.candle_index,
            prior.level,
            ATR_PERIOD,
            atr=atr,
            fvgs=fvgs,
        )
    except Exception as e:  # noqa: BLE001
        return "UNKNOWN", None, f"check_displacement_error:{type(e).__name__}"
    if res.magnitude_atr is None or res.atr is None:
        return "UNKNOWN", res, "magnitude_atr_or_atr_unavailable"
    return ("Y" if res.passed else "N"), res, ""


def chain_class_for(sweep_flag, disp_flag, poi_link):
    # sweep_flag expected Y for sweep rows
    if poi_link == "LINKED" and disp_flag == "Y":
        return "FULL_0A"
    if poi_link == "LINKED":
        return "SWEEP_PLUS_POI"
    if disp_flag == "Y":
        return "SWEEP_PLUS_DISPLACEMENT"
    return "SWEEP_ONLY"


def collect(h4, exec_start, exec_end):
    swings = detect_swings(h4, Timeframe.H4)
    levels = scan_liquidity(h4, Timeframe.H4, include=ALL_FAMILIES)
    sweeps = detect_sweeps(h4, levels)
    fvgs = detect_fvgs(h4, Timeframe.H4)
    atr_values = atr_series(h4, ATR_PERIOD)

    # H4 M8 POIs (as-is emission on H4 series)
    m8 = M8HtfDemandSupply(Timeframe.H4, htf_candles={Timeframe.H4: h4}, atr_period=ATR_PERIOD)
    try:
        h4_pois = m8.detect(h4, swings, levels)
    except Exception:
        h4_pois = []
    # keep only H4 timeframe POIs defensively
    h4_pois = [p for p in h4_pois if getattr(getattr(p, "zone", None), "timeframe", None) == Timeframe.H4]

    rows = []
    linked_poi_ids = set()
    sweeps_exec = [s for s in sweeps if exec_start <= s.candle.timestamp <= exec_end]
    for sw in sweeps_exec:
        c = sw.candle
        pool = sw.pool
        pool_name = getattr(pool, "name", str(pool))
        lvl = sw.level
        level_type = getattr(lvl.type, "name", str(lvl.type))
        level_price = round(float(lvl.level), 6)
        disp_flag, disp_res, disp_reason = displacement_for_sweep(h4, swings, sw, fvgs, atr_values)
        sweep_row = {
            "row_kind": "SWEEP_EVENT",
            "event_id": f"h4_sw_{sw.candle_index}_{pool_name}_{level_type}_{level_price:.3f}".replace(".", "p"),
            "timestamp": _iso(c.timestamp),
            "tf": "H4",
            "pool_family": level_type,
            "level_type": level_type,
            "level_price": level_price,
            "pool_side": pool_name,
            "sweep_flag": "Y",
            "sweep_id": f"sweep@{sw.candle_index}",
            "candle_index_h4": sw.candle_index,
            "_pool_enum": pool,
        }
        linked = pick_linked_poi(sweep_row, h4_pois)
        if linked is not None:
            poi_link = "LINKED"
            poi = linked
            rid = stable_poi_key(poi)
            linked_poi_ids.add(rid)
            poi_id = rid
            poi_kind = getattr(poi, "m8_kind", None) or "m8"
            poi_zone_low = round(float(poi.zone.bottom), 6)
            poi_zone_high = round(float(poi.zone.top), 6)
            poi_models = ",".join([getattr(m, "name", str(m)) for m in getattr(poi, "models", [])])
            poi_direction = getattr(poi.zone.direction, "name", str(poi.zone.direction))
        else:
            poi_link = "NONE"
            poi_id = poi_kind = poi_models = poi_direction = ""
            poi_zone_low = poi_zone_high = ""

        chain = chain_class_for("Y", disp_flag, poi_link)
        row = {
            "row_kind": "SWEEP_EVENT",
            "event_id": sweep_row["event_id"],
            "timestamp": sweep_row["timestamp"],
            "tf": "H4",
            "pool_family": level_type,
            "level_type": level_type,
            "level_price": level_price,
            "pool_side": pool_name,
            "sweep_flag": "Y",
            "sweep_id": sweep_row["sweep_id"],
            "candle_index_h4": sw.candle_index,
            "displacement_flag": disp_flag,
            "displacement_reason": disp_reason,
            "displacement_passed": "" if disp_res is None else str(bool(disp_res.passed)),
            "displacement_bos": "" if disp_res is None else str(bool(disp_res.bos)),
            "displacement_fvg": "" if disp_res is None else str(bool(disp_res.fvg)),
            "displacement_magnitude_atr": "" if (disp_res is None or disp_res.magnitude_atr is None) else round(float(disp_res.magnitude_atr), 6),
            "displacement_magnitude": "" if (disp_res is None or disp_res.magnitude is None) else round(float(disp_res.magnitude), 6),
            "displacement_atr_pre_sweep": "" if (disp_res is None or disp_res.atr is None) else round(float(disp_res.atr), 6),
            "poi_link": poi_link,
            "poi_id": poi_id,
            "poi_kind": poi_kind,
            "poi_zone_low": poi_zone_low,
            "poi_zone_high": poi_zone_high,
            "poi_models_tags": poi_models,
            "poi_direction": poi_direction,
            "chain_class": chain,
        }
        rows.append(row)

    # ORPHAN_POI rows (POIs with no sweep link in exec window)
    orphan_rows = []
    for p in h4_pois:
        pid = stable_poi_key(p)
        if pid in linked_poi_ids:
            continue
        kind = getattr(p, "m8_kind", None) or "m8"
        models = ",".join([getattr(m, "name", str(m)) for m in getattr(p, "models", [])])
        orphan_rows.append({
            "row_kind": "ORPHAN_POI",
            "event_id": f"h4_orphan_poi_{pid}",
            "timestamp": "",
            "tf": "H4",
            "pool_family": "",
            "level_type": "",
            "level_price": "",
            "pool_side": "",
            "sweep_flag": "N",
            "sweep_id": "",
            "candle_index_h4": "",
            "displacement_flag": "N",
            "displacement_reason": "no_linked_sweep_in_exec_window",
            "displacement_passed": "",
            "displacement_bos": "",
            "displacement_fvg": "",
            "displacement_magnitude_atr": "",
            "displacement_magnitude": "",
            "displacement_atr_pre_sweep": "",
            "poi_link": "NONE",
            "poi_id": pid,
            "poi_kind": kind,
            "poi_zone_low": round(float(p.zone.bottom), 6),
            "poi_zone_high": round(float(p.zone.top), 6),
            "poi_models_tags": models,
            "poi_direction": getattr(p.zone.direction, "name", str(p.zone.direction)),
            "chain_class": "ORPHAN_POI",
        })
    orphan_rows.sort(key=lambda r: (r["poi_kind"], float(r["poi_zone_low"] or 0), float(r["poi_zone_high"] or 0), r["poi_id"]))
    rows.extend(orphan_rows)

    # deterministic stable ordering
    kind_order = {"SWEEP_EVENT": 0, "ORPHAN_POI": 1, "DISPLACEMENT_WITHOUT_SWEEP": 2}
    rows.sort(key=lambda r: (kind_order.get(r["row_kind"], 9), r.get("timestamp", ""), r.get("event_id", "")))

    meta = {
        "swings_n": len(swings),
        "levels_n": len(levels),
        "sweeps_all_n": len(sweeps),
        "sweeps_exec_n": len(sweeps_exec),
        "m8_h4_pois_n": len(h4_pois),
        "fvgs_n": len(fvgs),
    }
    return rows, meta, h4_pois


def summarize(rows):
    sweep_rows = [r for r in rows if r["row_kind"] == "SWEEP_EVENT"]
    n_sweeps = len(sweep_rows)
    by_family = {}
    by_chain = {}
    for r in rows:
        fam = r.get("pool_family") or "(none)"
        cls = r.get("chain_class") or "UNKNOWN"
        by_family[fam] = by_family.get(fam, 0) + 1
        by_chain[cls] = by_chain.get(cls, 0) + 1
    # sweep-only denominators for rates (per task: % sweeps with displacement Y/N/UNKNOWN, % sweeps with POI link, % FULL_0A)
    disp_y = sum(1 for r in sweep_rows if r.get("displacement_flag") == "Y")
    disp_n = sum(1 for r in sweep_rows if r.get("displacement_flag") == "N")
    disp_u = sum(1 for r in sweep_rows if r.get("displacement_flag") == "UNKNOWN")
    poi_linked = sum(1 for r in sweep_rows if r.get("poi_link") == "LINKED")
    full_0a = sum(1 for r in sweep_rows if r.get("chain_class") == "FULL_0A")

    def pct(x, d):
        return round(100.0 * x / d, 4) if d else 0.0

    return {
        "n_rows": len(rows),
        "n_sweep_rows": n_sweeps,
        "counts_by_pool_family": dict(sorted(by_family.items())),
        "counts_by_chain_class": dict(sorted(by_chain.items())),
        "sweep_displacement": {
            "Y": disp_y, "N": disp_n, "UNKNOWN": disp_u,
            "pct_Y": pct(disp_y, n_sweeps),
            "pct_N": pct(disp_n, n_sweeps),
            "pct_UNKNOWN": pct(disp_u, n_sweeps),
        },
        "pct_sweep_with_displacement_Y": pct(disp_y, n_sweeps),
        "pct_sweep_with_poi_link": pct(poi_linked, n_sweeps),
        "pct_full_0a": pct(full_0a, n_sweeps),
        "n_sweep_with_poi_link": poi_linked,
        "n_full_0a": full_0a,
    }


def stratified_sample(rows, n, seed=SEED):
    # Prefer mix of chain classes (FULL_0A, SWEEP_ONLY, SWEEP_PLUS_DISPLACEMENT, LINKED vs NONE)
    sweep_rows = [r for r in rows if r["row_kind"] == "SWEEP_EVENT"]
    pool = sweep_rows if sweep_rows else rows
    if len(pool) <= n:
        return list(pool), "all (<=n)"
    rng = random.Random(seed)
    groups = {
        "FULL_0A": [r for r in pool if r.get("chain_class") == "FULL_0A"],
        "SWEEP_PLUS_POI": [r for r in pool if r.get("chain_class") == "SWEEP_PLUS_POI"],
        "SWEEP_PLUS_DISPLACEMENT": [r for r in pool if r.get("chain_class") == "SWEEP_PLUS_DISPLACEMENT"],
        "SWEEP_ONLY": [r for r in pool if r.get("chain_class") == "SWEEP_ONLY"],
    }
    target_per = max(1, n // max(1, len([g for g in groups.values() if g])))
    chosen = []
    seen = set()
    def add(rs):
        for r in rs:
            k = event_row_key(r)
            if k in seen:
                continue
            seen.add(k); chosen.append(r)
    # round 1: take from each non-empty group
    for name in ["FULL_0A", "SWEEP_PLUS_POI", "SWEEP_PLUS_DISPLACEMENT", "SWEEP_ONLY"]:
        g = sorted(groups[name], key=lambda r: (r.get("timestamp",""), r.get("event_id","")))
        if not g:
            continue
        take = min(target_per, len(g), n - len(chosen))
        if take <= 0:
            continue
        # spread in time
        idxs = sorted(set(min(len(g)-1, int(i * len(g) / take)) for i in range(take)))
        pick = [g[i] for i in idxs][:take]
        if len(pick) < take:
            rest = [x for x in g if x not in pick]
            rng.shuffle(rest)
            pick += rest[: take-len(pick)]
        add(pick)
    # fill remainder preferring linked vs none mix
    if len(chosen) < n:
        rest = [r for r in sorted(pool, key=lambda r:(r.get("timestamp",""), r.get("event_id",""))) if event_row_key(r) not in seen]
        # alternate linked/none where possible
        linked = [r for r in rest if r.get("poi_link") == "LINKED"]
        none = [r for r in rest if r.get("poi_link") != "LINKED"]
        rng.shuffle(linked); rng.shuffle(none)
        i=j=0
        while len(chosen) < n and (i < len(linked) or j < len(none)):
            if i < len(linked):
                add([linked[i]]); i += 1
            if len(chosen) >= n: break
            if j < len(none):
                add([none[j]]); j += 1
    chosen.sort(key=lambda r: (r.get("timestamp",""), r.get("event_id","")))
    return chosen[:n], f"stratified by chain_class+poi_link (seed={seed})"


def render_chart(row, h4, h4_pois, out_path: Path, bars_each_side=40):
    if row.get("row_kind") != "SWEEP_EVENT" or row.get("candle_index_h4") == "":
        return False
    idx = int(row["candle_index_h4"])
    lo = max(0, idx - bars_each_side)
    hi = min(len(h4), idx + bars_each_side + 1)
    window = h4[lo:hi]
    if not window:
        return False
    times = [mdates.date2num(c.timestamp) for c in window]
    fig, ax = plt.subplots(figsize=(14, 5.5))
    width = 0.12
    for t, c in zip(times, window):
        color = "#2ca02c" if c.close >= c.open else "#d62728"
        ax.vlines(t, c.low, c.high, color=color, linewidth=1)
        bottom = min(c.open, c.close)
        height = max(abs(c.close - c.open), 1e-6)
        ax.add_patch(Rectangle((t - width/2, bottom), width, height, facecolor=color, edgecolor=color, alpha=0.8))

    st = mdates.date2num(h4[idx].timestamp)
    ax.axvline(st, color="#9467bd", linestyle="--", linewidth=1.1, alpha=0.8)
    level = float(row["level_price"])
    ax.axhline(level, color="#1f77b4", linestyle="-", linewidth=1.2, alpha=0.9)
    is_bsl = row.get("pool_side") == "BSL"
    ax.scatter([st], [h4[idx].high if is_bsl else h4[idx].low], marker="v" if is_bsl else "^", s=70, color="#9467bd", zorder=5)

    # displacement annotation (text)
    disp = row.get("displacement_flag", "UNKNOWN")
    disp_txt = f"DISPLACEMENT={disp}"
    if disp == "Y" and row.get("displacement_magnitude_atr"):
        disp_txt += f" (mag_atr={row['displacement_magnitude_atr']}, bos={row.get('displacement_bos')}, fvg={row.get('displacement_fvg')})"
    elif row.get("displacement_reason"):
        disp_txt += f" ({row['displacement_reason']})"

    # POI zone rectangle if linked (draw matching poi)
    poi_txt = "POI=NONE"
    if row.get("poi_link") == "LINKED" and row.get("poi_zone_low") != "" and row.get("poi_zone_high") != "":
        zlo = float(row["poi_zone_low"]); zhi = float(row["poi_zone_high"])
        # draw across visible window
        x0 = times[0] - 0.2; x1 = times[-1] + 0.2
        ax.add_patch(Rectangle((x0, zlo), x1-x0, max(zhi-zlo, 1e-6), facecolor="#ff7f0e", edgecolor="#ff7f0e", alpha=0.18, label="POI zone"))
        poi_txt = f"POI={row.get('poi_kind')} [{zlo},{zhi}] models={row.get('poi_models_tags')}"

    chain = row.get("chain_class", "")
    title = (f"SWEEP={row.get('pool_side')} {row.get('level_type')} @ {row.get('timestamp')} | level={level} | {chain}\n"
             f"{disp_txt}\n{poi_txt}")
    ax.set_title(title, fontsize=8.5)
    ax.set_ylabel("Price")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M', tz=timezone.utc))
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return True


def write_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "row_kind","event_id","timestamp","tf","pool_family","level_type","level_price","pool_side",
        "sweep_flag","sweep_id","candle_index_h4",
        "displacement_flag","displacement_reason","displacement_passed","displacement_bos","displacement_fvg",
        "displacement_magnitude_atr","displacement_magnitude","displacement_atr_pre_sweep",
        "poi_link","poi_id","poi_kind","poi_zone_low","poi_zone_high","poi_models_tags","poi_direction",
        "chain_class",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    log = []
    def L(msg):
        print(msg, flush=True); log.append(msg)

    L(f"[l1-h4-0a] DATA={DATA_PATH}")
    if not DATA_PATH.exists():
        L("[l1-h4-0a] FAIL: missing parquet")
        (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
        return 2

    warm_start, exec_start, exec_end = WARMUP_START, EXEC_START, EXEC_END
    L(f"[l1-h4-0a] exec={exec_start.isoformat()}..{exec_end.isoformat()} warmup={warm_start.isoformat()}")
    m1 = load_m1(DATA_PATH, warm_start, exec_end + timedelta(days=1))
    if not m1:
        L("[l1-h4-0a] FAIL: no M1 bars")
        (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
        return 2
    m1_min, m1_max = m1[0].timestamp, m1[-1].timestamp
    L(f"[l1-h4-0a] m1 bars={len(m1)} range={m1_min.isoformat()}..{m1_max.isoformat()}")
    if m1_min > exec_start or m1_max < exec_start:
        L("[l1-h4-0a] FAIL: data does not cover exec_start")
        (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
        return 2
    if m1_max < exec_end.replace(hour=0, minute=0, second=0, microsecond=0):
        L(f"[l1-h4-0a] NOTE: m1 ends before requested exec_end (ends {m1_max.isoformat()}); documented coverage")

    h4 = resample_ohlcv(m1, Timeframe.H4)
    L(f"[l1-h4-0a] h4 bars={len(h4)} range={h4[0].timestamp.isoformat()}..{h4[-1].timestamp.isoformat()}")

    rows1, meta1, h4_pois1 = collect(h4, exec_start, exec_end)
    h1 = rows_hash(rows1)
    rows2, meta2, _ = collect(h4, exec_start, exec_end)
    h2 = rows_hash(rows2)
    deterministic = (h1 == h2 and len(rows1) == len(rows2) and meta1 == meta2)
    L(f"[l1-h4-0a] pass1 rows={len(rows1)} hash={h1} meta={meta1}")
    L(f"[l1-h4-0a] pass2 rows={len(rows2)} hash={h2} deterministic={deterministic}")
    if not deterministic:
        (OUT_DIR / "summary.json").write_text(json.dumps({"status":"FAIL","reason":"non_deterministic","hash1":h1,"hash2":h2}, indent=2), encoding="utf-8")
        (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
        return 3

    rows = rows1
    stats = summarize(rows)
    sample, sample_method = stratified_sample(rows, SAMPLE_N, seed=SEED)
    L(f"[l1-h4-0a] sample_n={len(sample)} method={sample_method}")

    charts_written = 0
    for r in sample:
        if r.get("row_kind") != "SWEEP_EVENT":
            continue
        ts_clean = (r.get("timestamp","") or "na").replace(":", "").replace("-", "").replace("+00:00","Z")
        fname = f"stage0a_{r.get('event_id','x')}_{r.get('chain_class','x')}_{ts_clean}.png"
        # keep filename reasonably short/safe
        fname = fname.replace("/", "_")[:180]
        try:
            if render_chart(r, h4, h4_pois1, CHARTS_DIR / fname):
                charts_written += 1
        except Exception as e:  # noqa: BLE001
            L(f"[l1-h4-0a] chart error {r.get('event_id')}: {e!r}")

    write_csv(rows, OUT_DIR / "events_stage0a_h4.csv")
    summary = {
        "status": "PASS",
        "layer": "L1",
        "tf": "H4",
        "window_exec_start": exec_start.isoformat(),
        "window_exec_end": exec_end.isoformat(),
        "warmup_start": warm_start.isoformat(),
        "m1_bars": len(m1),
        "h4_bars": len(h4),
        "h4_range_start": h4[0].timestamp.isoformat(),
        "h4_range_end": h4[-1].timestamp.isoformat(),
        "determinism": {"dual_run_equal": deterministic, "hash1": h1, "hash2": h2},
        "pipeline_counts": meta1,
        **stats,
        "sample_n": len(sample),
        "sample_method": sample_method,
        "charts_n": charts_written,
        "join_rules": {
            "sweep_row": "one row per exec-window SweepResult (detect_sweeps) with stable event_id from candle_index/pool/level_type/level",
            "displacement": "check_displacement per sweep (SSL->LONG,BSL->SHORT), BOS=most recent prior structural swing extreme of move direction before sweep; pre-sweep ATR/fvgs hoisted; UNKNOWN if no prior swing or magnitude/atr unavailable or checker error",
            "poi_link": "LINKED if any H4 M8 POI zone contains swept level price (Zone.contains, inclusive) AND direction compatible (SSL->LONG/demand, BSL->SHORT/supply); no new ATR bands; deterministic tie-break (smallest height, m8_kind ob>ds>fvg, bounds, stable_poi_key)",
            "bar_equality": "sweep and displacement share same sweep candle_index_h4/bar; POI join is geometric (zone contains level)",
            "poi_source": "M8HtfDemandSupply on H4 series only (ob/demand_supply/fvg episodes as-emitted); ORPHAN_POI rows for H4 M8 POIs with no linked sweep in exec window",
            "poi_id_stability": "research uses stable_poi_key derived from zone geometry+kind+direction (core POI.id is UUID per emission; 04_SRC unchanged)",
        },
        "detector_apis": {
            "swings": "smc.detection.structural_swing_detector.detect_swings(h4, Timeframe.H4)",
            "levels": "smc.detection.liquidity_scanner.scan(h4, Timeframe.H4, include=ALL_FAMILIES)",
            "sweeps": "smc.detection.sweep_detector.detect_sweeps(h4, levels)",
            "displacement": "smc.detection.displacement_checker.check_displacement(h4, dir, sweep_index, prior_swing.level, atr_period, atr=pre_sweep, fvgs=hoisted)",
            "poi_m8_h4": "smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply(Timeframe.H4, htf_candles={H4:h4}).detect(h4, swings, levels)",
            "resample": "smc.data.resample.resample_ohlcv(m1, Timeframe.H4)",
            "loader": "06_RESEARCH.scripts.plan_complement_ledger.load_m1",
        },
        "logic_changed": "NO",
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    L(f"[l1-h4-0a] DONE status=PASS rows={len(rows)} charts={charts_written} out={OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
