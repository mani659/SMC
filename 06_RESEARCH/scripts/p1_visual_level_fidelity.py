#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P1 Visual Fidelity Pack — Liquidity LEVEL labeling only (research).

Authority: Lead Architect. READ-ONLY detectors + research artifacts only.
LOGIC_CHANGED: NO. No 04_SRC/smc edits, no locked_constants changes, no P2.

Goal: emit chartable evidence for Stage 0A level construction labels:
  1) Session H/L (Asia/London/NY UTC)  -> session_levels.detect_session_levels
  2) PDH/PDL                            -> periodic_levels.detect_periodic_levels
  3) PWH/PWL                            -> periodic_levels.detect_periodic_levels
  4) EQH/EQL (EQH_EQL_TOLERANCE=4.5 pips) -> eqh_eql_detector.detect_equal_levels
  5) Structural swings (is_valid only)  -> structural_swing_detector.detect_swings

Constructors are the SAME production functions used by liquidity_scanner/DetectionDriver
(no reimplementation). See CONSTRUCTORS_USED in summary.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from collections import defaultdict
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
from smc.core.enums import LiquidityType
from smc.data.resample import resample_ohlcv
from smc.detection.eqh_eql_detector import detect_equal_levels
from smc.detection.periodic_levels import detect_periodic_levels
from smc.detection.session_levels import detect_session_levels
from smc.detection.structural_swing_detector import detect_swings
from smc.utils.timestamps import detect_session

DATA_PATH = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "p1_visual_levels"

WARMUP_START = datetime(2025, 3, 1, tzinfo=timezone.utc)
EXEC_START = datetime(2025, 6, 1, tzinfo=timezone.utc)
EXEC_END = datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc)

SEED = 20261110
MAX_PER_FAMILY = 15

FAMILIES = ["session", "pdh_pdl", "pwh_pwl", "eqh_eql", "structural_swing"]


def _iso(dt):
    if dt is None:
        return ""
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _ensure_utc(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def level_key(row):
    return (
        row["family"], row["type"], row["pool"], row["timeframe"],
        f"{float(row['level_price']):.6f}", row.get("formed_at", ""), row.get("session_name", ""),
        row.get("constructor_source", ""),
    )


def csv_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def in_exec(ts) -> bool:
    if ts is None:
        return False
    ts = _ensure_utc(ts)
    return EXEC_START <= ts <= EXEC_END


# --- collection ---

def collect_session(m1_exec):
    # True session extremes on M1 (UTC windows per smc.utils.timestamps)
    levels = detect_session_levels(m1_exec, Timeframe.M1)
    rows = []
    for lv in levels:
        if not in_exec(lv.formed_at):
            continue
        sess = detect_session(_ensure_utc(lv.formed_at)) if lv.formed_at else None
        rows.append({
            "family": "session",
            "type": lv.type.name,
            "pool": lv.pool.name,
            "level_price": float(lv.level),
            "timeframe": lv.timeframe.value,
            "formed_at": _iso(lv.formed_at),
            "session_name": sess.name if sess else "",
            "constructor_source": "smc.detection.session_levels.detect_session_levels(m1_exec, Timeframe.M1)",
            "note": "Session H/L per (UTC day, session window) on M1 candles",
            "_formed_dt": _ensure_utc(lv.formed_at),
        })
    rows.sort(key=lambda r: (r["formed_at"], r["session_name"], r["pool"], r["level_price"]))
    return rows


def collect_periodic(m1_all):
    # PDH/PDL and PWH/PWL: prior completed day/week valid as_of each UTC day start in exec.
    # Deduped by formed extreme (stable level instance) across as_of evaluations.
    exec_days = sorted({c.timestamp.date() for c in m1_all if EXEC_START.date() <= c.timestamp.date() <= EXEC_END.date()})
    by_sig = {}
    for d in exec_days:
        as_of = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        lvls = detect_periodic_levels(m1_all, Timeframe.M1, as_of=as_of)
        for lv in lvls:
            fam = "pdh_pdl" if lv.type == LiquidityType.PREVIOUS_DAY else "pwh_pwl"
            sig = (fam, lv.type.name, lv.pool.name, round(float(lv.level), 8), _iso(lv.formed_at))
            if sig not in by_sig:
                by_sig[sig] = {
                    "family": fam,
                    "type": lv.type.name,
                    "pool": lv.pool.name,
                    "level_price": float(lv.level),
                    "timeframe": lv.timeframe.value,
                    "formed_at": _iso(lv.formed_at),
                    "session_name": "",
                    "constructor_source": "smc.detection.periodic_levels.detect_periodic_levels(m1_all, Timeframe.M1, as_of=UTC_day_start)",
                    "note": "Prior completed day/week extreme (deduped by formed extreme across as_of evals)",
                    "_formed_dt": _ensure_utc(lv.formed_at),
                }
    rows = list(by_sig.values())
    out = [r for r in rows if r["_formed_dt"] and r["_formed_dt"] >= WARMUP_START and r["_formed_dt"] <= EXEC_END]
    out.sort(key=lambda r: (r["family"], r["formed_at"], r["pool"], r["level_price"]))
    return out


def collect_structural_and_eqh(h4_all):
    swings = detect_swings(h4_all, Timeframe.H4)
    struct_rows = []
    for sw in swings:
        if not sw.is_valid:
            continue
        if not in_exec(sw.timestamp):
            continue
        struct_rows.append({
            "family": "structural_swing",
            "type": LiquidityType.STRUCTURAL_SWING.name,
            "pool": sw.pool.name,
            "level_price": float(sw.level),
            "timeframe": Timeframe.H4.value,
            "formed_at": _iso(sw.timestamp),
            "session_name": "",
            "constructor_source": "smc.detection.structural_swing_detector.detect_swings(h4_all, Timeframe.H4) [is_valid only]",
            "note": f"is_valid=True base_candle_idx={sw.candle_index} confirmed_index={sw.confirmed_index}",
            "_formed_dt": _ensure_utc(sw.timestamp),
        })
    struct_rows.sort(key=lambda r: (r["formed_at"], r["pool"], r["level_price"]))

    eq_levels = detect_equal_levels(swings, Timeframe.H4)
    eq_rows = []
    for lv in eq_levels:
        if not in_exec(lv.formed_at):
            continue
        eq_rows.append({
            "family": "eqh_eql",
            "type": lv.type.name,
            "pool": lv.pool.name,
            "level_price": float(lv.level),
            "timeframe": lv.timeframe.value,
            "formed_at": _iso(lv.formed_at),
            "session_name": "",
            "constructor_source": "smc.detection.eqh_eql_detector.detect_equal_levels(detect_swings(h4_all, Timeframe.H4), Timeframe.H4)",
            "note": "Cluster extreme within EQH_EQL_TOLERANCE=4.5 pips (XAUUSD), >=2 members",
            "_formed_dt": _ensure_utc(lv.formed_at),
        })
    eq_rows.sort(key=lambda r: (r["formed_at"], r["pool"], r["level_price"]))
    return struct_rows, eq_rows


# --- sampling ---

def stratified_sample(rows, n, seed=SEED):
    if len(rows) <= n:
        return list(rows), "all (<=n)"
    rng = random.Random(seed)
    buckets = defaultdict(list)
    for r in rows:
        dt = r.get("_formed_dt") or datetime.fromisoformat(r["formed_at"])
        buckets[(dt.strftime("%Y-%m"), r.get("pool", ""))].append(r)
    keys = sorted(buckets.keys())
    for k in keys:
        buckets[k].sort(key=lambda r: (r.get("formed_at", ""), r.get("level_price", 0)))
    chosen = []
    seen = set()
    idxs = {k: 0 for k in keys}
    while len(chosen) < n:
        progressed = False
        for k in keys:
            if len(chosen) >= n:
                break
            arr = buckets[k]
            if idxs[k] >= len(arr):
                continue
            r = arr[idxs[k]]
            idxs[k] += 1
            rk = (r["family"], r["formed_at"], r["pool"], r["level_price"], r.get("session_name", ""))
            if rk in seen:
                continue
            seen.add(rk)
            chosen.append(r)
            progressed = True
        if not progressed:
            break
    if len(chosen) < n:
        rest = [r for r in rows if (r["family"], r["formed_at"], r["pool"], r["level_price"], r.get("session_name", "")) not in seen]
        rng.shuffle(rest)
        chosen.extend(rest[: n - len(chosen)])
    chosen.sort(key=lambda r: (r.get("formed_at", ""), r.get("pool", ""), r.get("level_price", 0)))
    return chosen[:n], f"stratified round-robin by (month,pool), spread within bucket, seed={seed}"


# --- charting ---

def _slice_candles(candles, center_dt, before=40, after=40):
    if not candles or center_dt is None:
        return []
    idx = 0
    for i, c in enumerate(candles):
        if c.timestamp >= center_dt:
            idx = i
            break
    else:
        idx = len(candles) - 1
    lo = max(0, idx - before)
    hi = min(len(candles), idx + after + 1)
    return candles[lo:hi]


def render_level_chart(row, candles, out_path: Path, before=50, after=50):
    center = row.get("_formed_dt")
    window = _slice_candles(candles, center, before, after)
    if not window:
        return False
    times = [mdates.date2num(c.timestamp) for c in window]
    fig, ax = plt.subplots(figsize=(14, 5.5))
    width = max((times[-1] - times[0]) / max(len(times), 1) * 0.6, 0.0005)
    for t, c in zip(times, window):
        color = "#2ca02c" if c.close >= c.open else "#d62728"
        ax.vlines(t, c.low, c.high, color=color, linewidth=0.8)
        bottom = min(c.open, c.close)
        height = max(abs(c.close - c.open), 1e-9)
        ax.add_patch(Rectangle((t - width/2, bottom), width, height, facecolor=color, edgecolor=color, alpha=0.8))

    level = float(row["level_price"])
    ax.axhline(level, color="#1f77b4", linestyle="-", linewidth=1.4, alpha=0.95)
    ft = mdates.date2num(center)
    ax.axvline(ft, color="#9467bd", linestyle="--", linewidth=1.0, alpha=0.8)

    fam = row["family"].upper()
    sess = row.get("session_name") or ""
    extra = f" session={sess}" if sess else ""
    title = (f"[{fam}] {row['type']} pool={row['pool']} tf={row['timeframe']} level={level:.3f}\n"
             f"formed_at={row.get('formed_at')}{extra}\n"
             f"src={row.get('constructor_source','')}")
    ax.set_title(title, fontsize=8)
    ax.set_ylabel("Price")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M', tz=timezone.utc))
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return True


# --- io ---

def write_csv(rows, path: Path):
    cols = ["family", "type", "pool", "level_price", "timeframe", "formed_at", "session_name", "constructor_source", "note"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def run_once(m1_all, m1_exec, h4_all):
    session_rows = collect_session(m1_exec)
    periodic_rows = collect_periodic(m1_all)
    pdh_rows = [r for r in periodic_rows if r["family"] == "pdh_pdl"]
    pwh_rows = [r for r in periodic_rows if r["family"] == "pwh_pwl"]
    struct_rows, eq_rows = collect_structural_and_eqh(h4_all)
    by = {
        "session": session_rows,
        "pdh_pdl": pdh_rows,
        "pwh_pwl": pwh_rows,
        "eqh_eql": eq_rows,
        "structural_swing": struct_rows,
    }
    all_rows = []
    for fam in FAMILIES:
        all_rows.extend(by[fam])
    all_rows.sort(key=lambda r: (r["family"], r.get("formed_at", ""), r.get("type", ""), r.get("pool", ""), r.get("level_price", 0), r.get("session_name", "")))
    return by, all_rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for fam in FAMILIES:
        (OUT_DIR / fam).mkdir(parents=True, exist_ok=True)
    log = []

    def L(m):
        print(m, flush=True)
        log.append(m)

    L(f"[p1-visual] DATA={DATA_PATH}")
    if not DATA_PATH.exists():
        L("[p1-visual] FAIL: missing parquet")
        (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
        return 2

    warm_start, exec_start, exec_end = WARMUP_START, EXEC_START, EXEC_END
    L(f"[p1-visual] exec={exec_start.isoformat()}..{exec_end.isoformat()} warmup={warm_start.isoformat()}")
    m1_all = load_m1(DATA_PATH, warm_start, exec_end + timedelta(days=1))
    if not m1_all:
        L("[p1-visual] FAIL: no M1 bars")
        (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
        return 2
    m1_min, m1_max = m1_all[0].timestamp, m1_all[-1].timestamp
    L(f"[p1-visual] m1_all bars={len(m1_all)} range={m1_min.isoformat()}..{m1_max.isoformat()}")
    if m1_min > exec_start or m1_max < exec_start:
        L("[p1-visual] FAIL: data does not cover exec_start")
        (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
        return 2
    m1_exec = [c for c in m1_all if exec_start <= c.timestamp <= exec_end]
    L(f"[p1-visual] m1_exec bars={len(m1_exec)}")
    h4_all = resample_ohlcv(m1_all, Timeframe.H4)
    L(f"[p1-visual] h4_all bars={len(h4_all)} range={h4_all[0].timestamp.isoformat()}..{h4_all[-1].timestamp.isoformat()}")

    by1, rows1 = run_once(m1_all, m1_exec, h4_all)
    by2, rows2 = run_once(m1_all, m1_exec, h4_all)
    csv_path = OUT_DIR / "p1_levels.csv"
    write_csv(rows1, csv_path)
    sha1 = csv_sha(csv_path)
    tmp = OUT_DIR / "_p1_levels_pass2.csv"
    write_csv(rows2, tmp)
    sha2 = csv_sha(tmp)
    try:
        tmp.unlink()
    except Exception:
        pass
    deterministic = (sha1 == sha2 and len(rows1) == len(rows2) and [level_key(r) for r in rows1] == [level_key(r) for r in rows2])
    L(f"[p1-visual] pass1 rows={len(rows1)} sha={sha1}")
    L(f"[p1-visual] pass2 rows={len(rows2)} sha={sha2} deterministic={deterministic}")
    if not deterministic:
        summary = {"status": "FAIL", "reason": "non_deterministic", "sha1": sha1, "sha2": sha2}
        (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
        return 3

    counts = {fam: len(by1[fam]) for fam in FAMILIES}
    L(f"[p1-visual] counts={counts}")

    chart_counts = {}
    sample_info = {}
    candle_src = {
        "session": m1_exec,
        "pdh_pdl": m1_all,
        "pwh_pwl": m1_all,
        "eqh_eql": h4_all,
        "structural_swing": h4_all,
    }
    bar_ctx = {
        "session": (80, 30),
        "pdh_pdl": (300, 120),
        "pwh_pwl": (1200, 400),
        "eqh_eql": (50, 30),
        "structural_swing": (50, 30),
    }
    for fam in FAMILIES:
        sample, method = stratified_sample(by1[fam], MAX_PER_FAMILY, seed=SEED)
        sample_info[fam] = {"n": len(sample), "method": method}
        written = 0
        for r in sample:
            ts_clean = (r.get("formed_at", "") or "na").replace(":", "").replace("-", "").replace("+00:00", "Z")
            pool = r.get("pool", "NA")
            lvl = f"{float(r['level_price']):.2f}".replace(".", "p")
            sess = (r.get("session_name") or "").lower()
            extra = f"_{sess}" if sess else ""
            fname = f"{fam}_{ts_clean}_{pool}_{lvl}{extra}.png"
            fname = fname.replace("/", "_")[:180]
            outp = OUT_DIR / fam / fname
            try:
                before, after = bar_ctx[fam]
                if render_level_chart(r, candle_src[fam], outp, before=before, after=after):
                    written += 1
            except Exception as e:  # noqa: BLE001
                L(f"[p1-visual] chart error {fam} {r.get('formed_at')} {r.get('level_price')}: {e!r}")
        chart_counts[fam] = written
        L(f"[p1-visual] charts {fam}: {written} (sample {len(sample)})")

    constructors_used = [
        "smc.detection.session_levels.detect_session_levels",
        "smc.detection.periodic_levels.detect_periodic_levels",
        "smc.detection.structural_swing_detector.detect_swings",
        "smc.detection.eqh_eql_detector.detect_equal_levels",
        "smc.detection.liquidity_scanner.scan (reference canonical emitter; families called directly here for per-family evidence)",
    ]
    summary = {
        "status": "PASS",
        "pack": "P1_VISUAL_LEVEL_FIDELITY",
        "logic_changed": "NO",
        "window_exec_start": exec_start.isoformat(),
        "window_exec_end": exec_end.isoformat(),
        "warmup_start": warm_start.isoformat(),
        "data_path": str(DATA_PATH).replace("\\", "/"),
        "m1_all_bars": len(m1_all),
        "m1_exec_bars": len(m1_exec),
        "h4_all_bars": len(h4_all),
        "h4_range": [h4_all[0].timestamp.isoformat(), h4_all[-1].timestamp.isoformat()],
        "counts_per_family": counts,
        "sample_sizes": {f: sample_info[f]["n"] for f in FAMILIES},
        "chart_counts": chart_counts,
        "sample_methods": {f: sample_info[f]["method"] for f in FAMILIES},
        "level_csv": str(csv_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "level_csv_sha256": sha1,
        "determinism": {"dual_run_equal": deterministic, "sha1": sha1, "sha2": sha2, "rows": len(rows1)},
        "constructors_used": constructors_used,
        "constructor_calls": {
            "session": "detect_session_levels(m1_exec, Timeframe.M1) filtered to formed_at in exec window",
            "pdh_pdl": "detect_periodic_levels(m1_all, Timeframe.M1, as_of=each UTC day start in exec) -> PREVIOUS_DAY rows, deduped by (type,pool,level,formed_at)",
            "pwh_pwl": "detect_periodic_levels(m1_all, Timeframe.M1, as_of=each UTC day start in exec) -> PREVIOUS_WEEK rows, deduped by (type,pool,level,formed_at)",
            "eqh_eql": "detect_equal_levels(detect_swings(h4_all, Timeframe.H4), Timeframe.H4), formed_at in exec",
            "structural_swing": "detect_swings(h4_all, Timeframe.H4) where is_valid==True (base-candle/§19 gate), formed_at in exec",
        },
        "notes": [
            "Session/periodic detected on M1 for true extremes; structural/eqh detected on H4 (Timeframe.H4, N-bar per production swing detector) consistent with scanner-style usage.",
            "PDH/PDL/PWH/PWL are prior-completed-period references; rows deduped by formed extreme (stable level instance) across as_of evaluations.",
            "Charts per family capped at 15 with stratified (month,pool) sampling; detection/counts run on full window.",
            "No sweep overlay, no displacement, no OB/FVG trade-quality audit, no expectancy.",
        ],
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    L(f"[p1-visual] DONE status=PASS csv={csv_path} sha={sha1} charts={chart_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
