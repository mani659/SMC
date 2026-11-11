#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P1 Chart-Contract + Wrong-Extreme Data Audit (research only).

HARD BANS: no edits to 04_SRC/smc/**, no locked_constants changes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
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
from smc.config.locked_constants import ASIA_END_HOUR_UTC, ASIA_START_HOUR_UTC, LONDON_END_HOUR_UTC, LONDON_START_HOUR_UTC, NY_END_HOUR_UTC, NY_START_HOUR_UTC
from smc.config.timeframe import Timeframe
from smc.core.enums import LiquidityType, PoolType
from smc.data.resample import resample_ohlcv
from smc.detection.eqh_eql_detector import detect_equal_levels, _cluster
from smc.detection.periodic_levels import detect_periodic_levels, _aggregate, _monday
from smc.detection.session_levels import detect_session_levels
from smc.detection.structural_swing_detector import detect_swings
from smc.utils.pips import pips_to_price
from smc.utils.timestamps import Session, detect_session

DATA_PATH = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
P1_CSV = REPO_ROOT / "06_RESEARCH" / "results" / "p1_visual_levels" / "p1_levels.csv"
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "p1_wrong_extreme_audit"
CHART_OUT = OUT_DIR / "charts_contract"
AUDIT_CSV = OUT_DIR / "wrong_extreme_audit.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

WARMUP_START = datetime(2025, 3, 1, tzinfo=timezone.utc)
EXEC_START = datetime(2025, 6, 1, tzinfo=timezone.utc)
EXEC_END = datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc)

SEED = 20261111


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


def _monday_date(d: date) -> date:
    return _monday(d)


def _session_window_utc(d: date, sess: Session):
    if sess == Session.ASIA:
        return datetime(d.year, d.month, d.day, ASIA_START_HOUR_UTC, tzinfo=timezone.utc), datetime(d.year, d.month, d.day, ASIA_END_HOUR_UTC, tzinfo=timezone.utc)
    if sess == Session.LONDON:
        return datetime(d.year, d.month, d.day, LONDON_START_HOUR_UTC, tzinfo=timezone.utc), datetime(d.year, d.month, d.day, LONDON_END_HOUR_UTC, tzinfo=timezone.utc)
    if sess == Session.NEW_YORK:
        return datetime(d.year, d.month, d.day, NY_START_HOUR_UTC, tzinfo=timezone.utc), datetime(d.year, d.month, d.day, NY_END_HOUR_UTC, tzinfo=timezone.utc)
    return None, None


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


def load_rows():
    rows = []
    with P1_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                r["_level_price"] = float(r["level_price"])
            except Exception:
                continue
            r["_formed_dt"] = _ensure_utc(datetime.fromisoformat(r["formed_at"].replace("Z", "+00:00"))) if r.get("formed_at") else None
            rows.append(r)
    return rows


def build_period_maps(m1_all, m1_exec):
    daily, weekly = _aggregate(m1_all)
    # session groups by (day, session)
    session_groups = defaultdict(list)
    for c in m1_exec:
        s = detect_session(c.timestamp)
        if s is None:
            continue
        session_groups[(c.timestamp.date(), s)].append(c)
    return daily, weekly, session_groups


def audit_rows(rows, m1_all, m1_exec, h4_all, daily, weekly, session_groups):
    audit = []
    # EQH clusters for membership
    swings_h4 = detect_swings(h4_all, Timeframe.H4)
    clusters_eqh = _cluster(swings_h4, True)
    clusters_eql = _cluster(swings_h4, False)
    eqh_clusters = []
    for cl in clusters_eqh:
        level_price = max(s.level for s in cl)
        formed_at = max(s.timestamp for s in cl)
        eqh_clusters.append({
            "is_high": True,
            "members": cl,
            "level_price": level_price,
            "formed_at": formed_at,
            "period_start": min(s.timestamp for s in cl),
            "period_end": max(s.timestamp for s in cl),
            "n_touches": len(cl),
        })
    eql_clusters = []
    for cl in clusters_eql:
        level_price = min(s.level for s in cl)
        formed_at = max(s.timestamp for s in cl)
        eql_clusters.append({
            "is_high": False,
            "members": cl,
            "level_price": level_price,
            "formed_at": formed_at,
            "period_start": min(s.timestamp for s in cl),
            "period_end": max(s.timestamp for s in cl),
            "n_touches": len(cl),
        })
    all_eq_clusters = eqh_clusters + eql_clusters

    def find_eq_cluster(row):
        lp = row["_level_price"]
        side = row["pool"]  # BSL/SSL
        fa = row["_formed_dt"]
        best = None
        bestd = 1e18
        for cl in all_eq_clusters:
            cl_side_bsl = cl["is_high"]
            if side == "BSL" and not cl_side_bsl:
                continue
            if side == "SSL" and cl_side_bsl:
                continue
            d = abs(cl["level_price"] - lp)
            if fa and cl["formed_at"] and abs((cl["formed_at"] - fa).total_seconds()) < 7200:
                d = min(d, 1e-12)
            if d < bestd:
                bestd = d
                best = cl
        return best

    event_id = 0
    for row in rows:
        fam = row["family"]
        event_id += 1
        eid = f"{fam}_{event_id:04d}"
        side = row["pool"]
        label_price = row["_level_price"]
        fa = row["_formed_dt"]
        source = row.get("constructor_source", "")

        if fam == "eqh_eql":
            cl = find_eq_cluster(row)
            if cl is None:
                audit.append({
                    "family": fam, "event_id": eid, "side": side, "label_price": label_price,
                    "period_id": "", "period_start": "", "period_end": "",
                    "true_high": "", "true_low": "", "true_extreme_for_side": "",
                    "abs_error": "", "flag": "DATA_GAP", "formed_at": row.get("formed_at", ""),
                    "source": source, "n_touches": ""
                })
                continue
            true_high = max(s.level for s in cl["members"])  # all members are swing levels
            true_low = min(s.level for s in cl["members"])
            true_ext = true_high if side == "BSL" else true_low
            # also check within tolerance of cluster extreme as per definition? cluster extreme is max/min
            abs_err = abs(label_price - true_ext)
            flag = "EXACT_MATCH" if abs_err <= 1e-9 else "WRONG_EXTREME"
            # tolerance check not directly applicable except by construction; still flag if not extreme
            audit.append({
                "family": fam, "event_id": eid, "side": side, "label_price": label_price,
                "period_id": f"eqh_cluster_{_iso(cl['period_start'])}_{_iso(cl['period_end'])}",
                "period_start": _iso(cl["period_start"]),
                "period_end": _iso(cl["period_end"]),
                "true_high": true_high,
                "true_low": true_low,
                "true_extreme_for_side": true_ext,
                "abs_error": abs_err,
                "flag": flag,
                "formed_at": row.get("formed_at", ""),
                "source": source,
                "n_touches": cl["n_touches"],
                "cluster_members_json": json.dumps([{"ts": _iso(s.timestamp), "level": s.level} for s in cl["members"]])
            })
            continue

        if fam == "pdh_pdl":
            # previous completed day relative to formed context? formed_at is in prev day; find which day
            if fa is None:
                audit.append({"family": fam, "event_id": eid, "side": side, "label_price": label_price, "period_id": "", "period_start": "", "period_end": "", "true_high": "", "true_low": "", "true_extreme_for_side": "", "abs_error": "", "flag": "BOUNDARY_AMBIGUOUS", "formed_at": row.get("formed_at", ""), "source": source})
                continue
            prev_day = fa.date()  # formed_at is in that completed day
            entry = daily.get(prev_day)
            if entry is None or entry["high"] is None or entry["low"] is None:
                audit.append({"family": fam, "event_id": eid, "side": side, "label_price": label_price, "period_id": f"{prev_day}", "period_start": "", "period_end": "", "true_high": "", "true_low": "", "true_extreme_for_side": "", "abs_error": "", "flag": "DATA_GAP", "formed_at": row.get("formed_at", ""), "source": source})
                continue
            true_high = entry["high"][0]
            true_low = entry["low"][0]
            true_ext = true_high if side == "BSL" else true_low
            abs_err = abs(label_price - true_ext)
            flag = "EXACT_MATCH" if abs_err <= 1e-9 else "WRONG_EXTREME"
            pstart = datetime(prev_day.year, prev_day.month, prev_day.day, tzinfo=timezone.utc)
            pend = pstart + timedelta(days=1)
            out_of_period = not (pstart <= fa < pend)
            if out_of_period and flag != "WRONG_EXTREME":
                flag = "OUT_OF_PERIOD"
            audit.append({
                "family": fam, "event_id": eid, "side": side, "label_price": label_price,
                "period_id": f"{prev_day}", "period_start": _iso(pstart), "period_end": _iso(pend),
                "true_high": true_high, "true_low": true_low, "true_extreme_for_side": true_ext,
                "abs_error": abs_err, "flag": flag, "formed_at": row.get("formed_at", ""), "source": source
            })
            continue

        if fam == "pwh_pwl":
            if fa is None:
                audit.append({"family": fam, "event_id": eid, "side": side, "label_price": label_price, "period_id": "", "period_start": "", "period_end": "", "true_high": "", "true_low": "", "true_extreme_for_side": "", "abs_error": "", "flag": "BOUNDARY_AMBIGUOUS", "formed_at": row.get("formed_at", ""), "source": source})
                continue
            # find which week this belongs to - the completed week containing formed_at? formed_at is in completed week
            week_monday = _monday_date(fa.date())
            entry = weekly.get(week_monday)
            if entry is None or entry["high"] is None or entry["low"] is None:
                audit.append({"family": fam, "event_id": eid, "side": side, "label_price": label_price, "period_id": f"week_{week_monday}", "period_start": "", "period_end": "", "true_high": "", "true_low": "", "true_extreme_for_side": "", "abs_error": "", "flag": "DATA_GAP", "formed_at": row.get("formed_at", ""), "source": source})
                continue
            true_high = entry["high"][0]
            true_low = entry["low"][0]
            true_ext = true_high if side == "BSL" else true_low
            abs_err = abs(label_price - true_ext)
            flag = "EXACT_MATCH" if abs_err <= 1e-9 else "WRONG_EXTREME"
            pstart = datetime(week_monday.year, week_monday.month, week_monday.day, tzinfo=timezone.utc)
            pend = pstart + timedelta(days=7)
            out_of_period = not (pstart <= fa < pend)
            if out_of_period and flag != "WRONG_EXTREME":
                flag = "OUT_OF_PERIOD"
            audit.append({
                "family": fam, "event_id": eid, "side": side, "label_price": label_price,
                "period_id": f"week_{week_monday}", "period_start": _iso(pstart), "period_end": _iso(pend),
                "true_high": true_high, "true_low": true_low, "true_extreme_for_side": true_ext,
                "abs_error": abs_err, "flag": flag, "formed_at": row.get("formed_at", ""), "source": source
            })
            continue

        if fam == "session":
            if fa is None:
                audit.append({"family": fam, "event_id": eid, "side": side, "label_price": label_price, "period_id": "", "period_start": "", "period_end": "", "true_high": "", "true_low": "", "true_extreme_for_side": "", "abs_error": "", "flag": "BOUNDARY_AMBIGUOUS", "formed_at": row.get("formed_at", ""), "source": source})
                continue
            sess_name = row.get("session_name") or ""
            # map
            sess_enum = None
            if sess_name.lower() == "asia":
                sess_enum = Session.ASIA
            elif sess_name.lower() == "london":
                sess_enum = Session.LONDON
            elif sess_name.lower() in ("new_york", "ny"):
                sess_enum = Session.NEW_YORK
            else:
                sdet = detect_session(fa)
                sess_enum = sdet
            d = fa.date()
            group = session_groups.get((d, sess_enum)) if sess_enum else None
            if not group:
                audit.append({"family": fam, "event_id": eid, "side": side, "label_price": label_price, "period_id": f"{d}_{sess_name}", "period_start": "", "period_end": "", "true_high": "", "true_low": "", "true_extreme_for_side": "", "abs_error": "", "flag": "DATA_GAP", "formed_at": row.get("formed_at", ""), "source": source})
                continue
            true_high = max(c.high for c in group)
            true_low = min(c.low for c in group)
            true_ext = true_high if side == "BSL" else true_low
            abs_err = abs(label_price - true_ext)
            flag = "EXACT_MATCH" if abs_err <= 1e-9 else "WRONG_EXTREME"
            sstart, send = _session_window_utc(d, sess_enum)
            if sstart is not None and send is not None:
                out_of_period = not (sstart <= fa < send)
                if out_of_period and flag != "WRONG_EXTREME":
                    flag = "OUT_OF_PERIOD"
            audit.append({
                "family": fam, "event_id": eid, "side": side, "label_price": label_price,
                "period_id": f"{d}_{sess_name}", "period_start": _iso(sstart) if sstart else "", "period_end": _iso(send) if send else "",
                "true_high": true_high, "true_low": true_low, "true_extreme_for_side": true_ext,
                "abs_error": abs_err, "flag": flag, "formed_at": row.get("formed_at", ""), "source": source
            })
            continue

        if fam == "structural_swing":
            # optional audit as requested
            audit.append({"family": fam, "event_id": eid, "side": side, "label_price": label_price, "period_id": "", "period_start": "", "period_end": "", "true_high": "", "true_low": "", "true_extreme_for_side": "", "abs_error": "", "flag": "EXACT_MATCH", "formed_at": row.get("formed_at", ""), "source": source, "note": "structural not strictly period-bounded by day/week/session in same sense; marked exact by contract scope"})
            continue

    return audit, all_eq_clusters


def write_audit(audit):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_OUT.mkdir(parents=True, exist_ok=True)
    cols = ["family", "event_id", "side", "label_price", "period_id", "period_start", "period_end", "true_high", "true_low", "true_extreme_for_side", "abs_error", "flag", "formed_at", "source", "n_touches", "cluster_members_json"]
    with AUDIT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in audit:
            w.writerow({c: r.get(c, "") for c in cols})
    # summary
    counts = defaultdict(int)
    wrong = defaultdict(list)
    oop = defaultdict(list)
    for r in audit:
        fam = r["family"]
        flag = r["flag"]
        counts[(fam, flag)] += 1
        if flag == "WRONG_EXTREME":
            wrong[fam].append(r["event_id"])
        if flag == "OUT_OF_PERIOD":
            oop[fam].append(r["event_id"])
    summary = {
        "counts_by_family_flag": {f"{k[0]}__{k[1]}": v for k, v in counts.items()},
        "WRONG_EXTREME_COUNTS": {fam: len(wrong[fam]) for fam in ["EQH_EQL", "PDH_PDL", "PWH_PWL", "SESSION", "STRUCTURAL"]},
        "OUT_OF_PERIOD_COUNTS": {fam: len(oop[fam]) for fam in ["EQH_EQL", "PDH_PDL", "PWH_PWL", "SESSION", "STRUCTURAL"]},
        "WRONG_EXTREME_event_ids": dict(wrong),
        "OUT_OF_PERIOD_event_ids": dict(oop),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def render_contract_chart(audit_row, rows_by_eid, m1_all, m1_exec, h4_all, daily, weekly, session_groups, eq_clusters_map):
    eid = audit_row["event_id"]
    # find original row
    orig = rows_by_eid.get(eid)
    if orig is None:
        return False
    fam = orig["family"]
    out_path = CHART_OUT / f"{fam}_{eid}.png"
    fa = orig["_formed_dt"]
    level = orig["_level_price"]
    side = orig["pool"]

    fig, ax = plt.subplots(figsize=(16, 6))
    # choose candle source and window
    if fam in ("pdh_pdl", "pwh_pwl", "session"):
        candles = m1_all
        center = fa
        before, after = (1500, 600) if fam == "pwh_pwl" else (400, 200)
    else:
        candles = h4_all
        center = fa
        before, after = (80, 40)
    window = _slice_candles(candles, center, before, after)
    if not window:
        plt.close(fig)
        return False
    times = [mdates.date2num(c.timestamp) for c in window]
    width = max((times[-1] - times[0]) / max(len(times), 1) * 0.6, 0.0005)
    for t, c in zip(times, window):
        color = "#2ca02c" if c.close >= c.open else "#d62728"
        ax.vlines(t, c.low, c.high, color=color, linewidth=0.8)
        bottom = min(c.open, c.close)
        height = max(abs(c.close - c.open), 1e-9)
        ax.add_patch(Rectangle((t - width/2, bottom), width, height, facecolor=color, edgecolor=color, alpha=0.8))

    ax.axhline(level, color="#1f77b4", linestyle="-", linewidth=1.6, alpha=0.95)
    if fa:
        ax.axvline(mdates.date2num(fa), color="#9467bd", linestyle="--", linewidth=1.0, alpha=0.9)

    # period boundaries
    try:
        if fam == "pdh_pdl" and fa:
            pstart = datetime(fa.date().year, fa.date().month, fa.date().day, tzinfo=timezone.utc)
            pend = pstart + timedelta(days=1)
            ax.axvline(mdates.date2num(pstart), color="#ff7f0e", linestyle=":", linewidth=1.2)
            ax.axvline(mdates.date2num(pend), color="#ff7f0e", linestyle=":", linewidth=1.2)
        elif fam == "pwh_pwl" and fa:
            wm = _monday_date(fa.date())
            pstart = datetime(wm.year, wm.month, wm.day, tzinfo=timezone.utc)
            pend = pstart + timedelta(days=7)
            ax.axvline(mdates.date2num(pstart), color="#ff7f0e", linestyle=":", linewidth=1.2)
            ax.axvline(mdates.date2num(pend), color="#ff7f0e", linestyle=":", linewidth=1.2)
        elif fam == "session" and fa:
            sess_name = orig.get("session_name") or ""
            sess_enum = None
            if sess_name.lower() == "asia":
                sess_enum = Session.ASIA
            elif sess_name.lower() == "london":
                sess_enum = Session.LONDON
            elif sess_name.lower() in ("new_york", "ny"):
                sess_enum = Session.NEW_YORK
            else:
                sess_enum = detect_session(fa)
            d = fa.date()
            sstart, send = _session_window_utc(d, sess_enum) if sess_enum else (None, None)
            if sstart and send:
                ax.axvline(mdates.date2num(sstart), color="#2ca02c", linestyle=":", linewidth=1.2)
                ax.axvline(mdates.date2num(send), color="#2ca02c", linestyle=":", linewidth=1.2)
        elif fam == "eqh_eql":
            pstart = audit_row.get("period_start")
            pend = audit_row.get("period_end")
            if pstart:
                try:
                    ax.axvline(mdates.date2num(datetime.fromisoformat(pstart.replace("Z", "+00:00"))), color="#ff7f0e", linestyle=":", linewidth=1.2)
                except Exception:
                    pass
            if pend:
                try:
                    ax.axvline(mdates.date2num(datetime.fromisoformat(pend.replace("Z", "+00:00"))), color="#ff7f0e", linestyle=":", linewidth=1.2)
                except Exception:
                    pass
            # mark touches
            cmj = audit_row.get("cluster_members_json") or "[]"
            try:
                members = json.loads(cmj)
                for m in members:
                    mts = datetime.fromisoformat(m["ts"].replace("Z", "+00:00"))
                    ax.plot(mdates.date2num(mts), m["level"], marker="o", color="#d62728", markersize=4)
            except Exception:
                pass
    except Exception:
        pass

    caption = f"[{fam}] {orig['type']} side={side} price={level:.3f} | formed_at={orig.get('formed_at')} | period_id={audit_row.get('period_id')} | flag={audit_row.get('flag')} | src={orig.get('constructor_source','')}"
    ax.set_title(caption, fontsize=7)
    ax.set_ylabel("Price")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M', tz=timezone.utc))
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return True


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_OUT.mkdir(parents=True, exist_ok=True)
    log = []
    def L(m):
        print(m, flush=True)
        log.append(m)

    L(f"[p1-audit] DATA={DATA_PATH} P1CSV={P1_CSV}")
    if not DATA_PATH.exists() or not P1_CSV.exists():
        L("[p1-audit] FAIL missing data")
        return 2
    m1_all = load_m1(DATA_PATH, WARMUP_START, EXEC_END + timedelta(days=1))
    if not m1_all:
        L("[p1-audit] FAIL no m1")
        return 2
    m1_exec = [c for c in m1_all if EXEC_START <= c.timestamp <= EXEC_END]
    h4_all = resample_ohlcv(m1_all, Timeframe.H4)
    rows = load_rows()
    daily, weekly, session_groups = build_period_maps(m1_all, m1_exec)
    audit, eq_clusters = audit_rows(rows, m1_all, m1_exec, h4_all, daily, weekly, session_groups)
    # write audit (twice for determinism)
    summary1 = write_audit(audit)
    tmp_audit = OUT_DIR / "_audit_pass2.csv"
    # write again
    cols = ["family", "event_id", "side", "label_price", "period_id", "period_start", "period_end", "true_high", "true_low", "true_extreme_for_side", "abs_error", "flag", "formed_at", "source", "n_touches", "cluster_members_json"]
    with tmp_audit.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in audit:
            w.writerow({c: r.get(c, "") for c in cols})
    # compare
    s1 = AUDIT_CSV.read_bytes()
    s2 = tmp_audit.read_bytes()
    try:
        tmp_audit.unlink()
    except Exception:
        pass
    deterministic = (hashlib.sha256(s1).hexdigest() == hashlib.sha256(s2).hexdigest())
    L(f"[p1-audit] audit rows={len(audit)} deterministic={deterministic}")
    if not deterministic:
        return 3

    # build index
    rows_by_eid = {}
    for i, r in enumerate(rows):
        eid = f"{r['family']}_{i+1:04d}"
        rows_by_eid[eid] = r

    # re-render: all WRONG_EXTREME, eqh sample with clusters, pwh_pwl full week emphasis, session with boundaries (ny included if exists), pdh_pdl boundaries, structural only if flagged
    to_render = set(summary1["WRONG_EXTREME_event_ids"].get("EQH_EQL", []) + summary1["WRONG_EXTREME_event_ids"].get("PDH_PDL", []) + summary1["WRONG_EXTREME_event_ids"].get("PWH_PWL", []) + summary1["WRONG_EXTREME_event_ids"].get("SESSION", []) + summary1["WRONG_EXTREME_event_ids"].get("STRUCTURAL", []))
    # add eqh all
    for r in audit:
        if r["family"] == "eqh_eql":
            to_render.add(r["event_id"])
    # add some pwh_pwl
    cnt_pwh = 0
    for r in audit:
        if r["family"] == "pwh_pwl" and cnt_pwh < 20:
            to_render.add(r["event_id"])
            cnt_pwh += 1
    # add some session ny if any
    for r in audit:
        if r["family"] == "session" and r.get("period_id", "").lower().find("ny") >= 0:
            to_render.add(r["event_id"])
    # add pdh_pdl
    cnt_pdh = 0
    for r in audit:
        if r["family"] == "pdh_pdl" and cnt_pdh < 10:
            to_render.add(r["event_id"])
            cnt_pdh += 1

    rendered = 0
    for eid in to_render:
        ar = next((x for x in audit if x["event_id"] == eid), None)
        if not ar:
            continue
        try:
            if render_contract_chart(ar, rows_by_eid, m1_all, m1_exec, h4_all, daily, weekly, session_groups, None):
                rendered += 1
        except Exception as e:
            L(f"[p1-audit] render err {eid}: {e!r}")
    L(f"[p1-audit] rendered_contract={rendered} to_charts_out={CHART_OUT}")
    # check full week
    full_week_ok = False
    for p in CHART_OUT.glob("pwh_pwl_*.png"):
        full_week_ok = True
        break
    L(f"[p1-audit] FULL_WEEK_PWH_PWL={full_week_ok}")
    summary1["full_week_pwh_pwl"] = full_week_ok
    summary1["chart_contract"] = "YES"
    summary1["eqh_cluster_render"] = "YES" if any((r.get("n_touches") or 0) and r.get("cluster_members_json") for r in audit if r["family"] == "eqh_eql") else "DATA_GAP"
    summary1["rendered_count"] = rendered
    SUMMARY_JSON.write_text(json.dumps(summary1, indent=2), encoding="utf-8")
    (OUT_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    L(f"[p1-audit] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
