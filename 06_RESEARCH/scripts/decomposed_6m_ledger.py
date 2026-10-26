#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Decomposed 6M event ledger + combination tests (read-only research).

Lead Architect Tier-1 directive (accepted audit
INDEPENDENT_FUNNEL_IDEA_AUDIT_2026-10-11.md, Part C). Measurement only:
inventory each flowchart concept on the frozen 6m window WITHOUT
requiring the full HTF->LTF->entry chain, then measure post-event price
behavior with frozen horizons. NO production threshold changes, NO
gates, NO expectancy claims.

Frozen design (stated before running — nothing iterated):
  * Window: exec 2025-06-01 -> 2025-11-30 M5; M1 warm-up from 2025-05-01
    (ATR seed + trailing history; entries start a month inside).
  * Concepts (independence = no arm/route/fill required):
      1. htf-zone : accepted H4 pack raw rows + D1 subset (same loader
         rules as the Stage-3 pack) — zone fate over H_ZONE.
      2. sweep / 3. displacement / 4. trigger : accepted LTF ledger rows
         (non-trigger detector rows) + accepted Stage-3 ledger rows
         (trigger completions, ungated inventory). Concept 5 (real
         fills, n=3) is listed from the product book, never invented.
  * htf_context (frozen, zero new parameters): relation inside->inside,
    retest->near, above/below->far (uses only recorded fields; a
    diagnostic dist_to_zone_atr column is reported alongside).
  * Reference price (frozen): single level as-is; lo..hi range midpoint;
    trigger entry_price_ref. Direction as recorded (no reinterpretation).
  * Horizons frozen: H_ZONE=20 M5 (the product's give-up scale, zone
    fate); H_PATH=100 M5 (Track-B post-exit horizon, excursion/path).
  * Numeraires frozen: ATR(14) Wilder SMA-seeded on M5 at the event bar
    (no hypothetical stop may be invented, so ATR units — never R — for
    non-trade events). atr<=0 -> metrics empty, never zero-filled.
  * Zone fate (frozen): VIOLATED if any adverse close in window
    (LONG close<low / SHORT close>high), elif touched -> TOUCHED,
    else UNTOUCHED.
  * Invalidation (frozen, uniform): adverse excursion >= 1.0xATR inside
    the horizon. +1/+2 ATR hits on favorable excursion.
  * Truncation (frozen, strict): fewer than H bars after the event
    in-series -> metrics empty + note (never extrapolated).
  * Combination verdict (frozen rule): per concept, inside-vs-far +1ATR
    Wilson-95% CIs with both cells n>=30: disjoint -> separates;
    overlapping -> does_not_separate; either cell n<30 ->
    insufficient_n. Overall: separates if ANY concept separates;
    elif every decisive concept overlaps -> does_not_separate;
    else insufficient_n.
  * No-look-ahead: prefix-only inputs (accepted packs/ledgers are all
    timestamped decisions); forward scans read-only; indices resolved
    by timestamp (run-relative bar numbers never cross books).

Reuse (import, not fork): canonical parquet loader + resample_multi +
CandleSeries from smc; wilder_atr_14 from f_selectivity_post_exit.
NO 04_SRC/smc decision-logic change; locked_constants diff empty.

Outputs: results/decomposed_6m_ledger/decomposed_events.csv +
summary.json. Report: DECOMPOSED_6M_LEDGER_REPORT.md (separate step).
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
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

import ltf_confirmation_pack as ltf
from f_selectivity_post_exit import wilder_atr_14

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "decomposed_6m_ledger"
EVENTS_CSV = OUT_DIR / "decomposed_events.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — NOT EDGE"

# ---- Frozen params -------------------------------------------------------- #
H_ZONE = 20            # M5 bars (product give-up scale)
H_PATH = 100           # M5 bars (Track-B post-exit horizon)
ATR_PERIOD = 14
Z = 1.96               # Wilson 95%
MIN_CELL_N = 30        # combination verdict cell minimum
M1_LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)

LTF_LEDGER_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                  "ltf_confirmation" / "events_ltf_confirmation.csv")
STAGE3_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
              "stage3_trigger_visibility" / "events_stage3_triggers.csv")
PRODUCT_SUMMARY = (REPO_ROOT / "06_RESEARCH" / "results" /
                   "product_6m_refresh_track_b" / "summary.json")
PRODUCT_FUNNEL = (REPO_ROOT / "06_RESEARCH" / "results" /
                  "product_6m_refresh_track_b" / "run1" /
                  "funnel_summary.json")
PRODUCT_REPORT = (REPO_ROOT / "06_RESEARCH" / "results" /
                  "product_6m_refresh_track_b" / "run1" / "report.json")

CSV_COLUMNS = [
    "event_id", "concept", "detection_tf", "direction", "ts_utc",
    "anchor_lo", "anchor_hi", "ref_price",
    "htf_event_id", "htf_context", "dist_to_zone_atr",
    "horizon_bars", "horizon_kind",
    "mfe_atr", "mae_atr", "hit_plus1atr", "hit_plus2atr",
    "inv_breach_1atr", "time_to_extreme_bars",
    "zone_fate", "zone_touched", "zone_violated", "first_touch_offset",
    "outcome_note",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def htf_context(relation: str | None) -> str:
    """Frozen trichotomy on the recorded relation only (no new params)."""
    rel = (relation or "").strip().lower()
    if rel == "inside":
        return "inside"
    if rel == "retest":
        return "near"
    if rel in ("above", "below"):
        return "far"
    return "unknown"


def parse_level(raw: str | None) -> tuple[float | None, float | None, float | None]:
    """Parse 'price' or 'lo..hi' into (lo, hi, ref); ref = level or mid."""
    if not raw:
        return None, None, None
    try:
        if ".." in raw:
            lo_s, hi_s = raw.split("..", 1)
            lo, hi = float(lo_s), float(hi_s)
            if hi < lo:
                return None, None, None
            return lo, hi, (lo + hi) / 2.0
        price = float(raw)
        return price, price, price
    except (TypeError, ValueError):
        return None, None, None


def wilson(k: int, n: int, z: float = Z) -> tuple[float | None, float | None]:
    """Wilson score interval for a rate (deterministic, dependency-free)."""
    if n <= 0:
        return None, None
    if k < 0 or k > n:
        return None, None
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def excursion_atr(m5: CandleSeries, start: int, end: int, is_long: bool,
                  ref: float, atr: float) -> tuple[float | None, float | None]:
    """Max favorable/adverse excursion in ATR units over [start, end]."""
    if atr <= 0 or start is None or end is None:
        return None, None
    if not (0 <= start <= end < len(m5)):
        return None, None
    mfe = mae = 0.0
    for i in range(start, end + 1):
        c = m5[i]
        if is_long:
            mfe = max(mfe, c.high - ref)
            mae = max(mae, ref - c.low)
        else:
            mfe = max(mfe, ref - c.low)
            mae = max(mae, c.high - ref)
    return mfe / atr, mae / atr


def zone_fate(m5: CandleSeries, anchor: int, zone_low: float,
              zone_high: float, is_long: bool,
              horizon: int = H_ZONE) -> dict:
    """Frozen zone-fate read over [anchor, anchor+horizon]."""
    end = anchor + horizon
    if not (0 <= anchor <= end < len(m5)):
        return {"fate": "DATA_GAP", "touched": None, "violated": None,
                "first_touch_offset": None,
                "note": "window truncated by series bounds"}
    touched, violated, first_touch = False, False, None
    for i in range(anchor, end + 1):
        c = m5[i]
        if c.low <= zone_high and c.high >= zone_low:
            touched = True
            if first_touch is None:
                first_touch = i - anchor
        adverse = c.close < zone_low if is_long else c.close > zone_high
        if adverse:
            violated = True
    if violated:
        fate = "VIOLATED"
    elif touched:
        fate = "TOUCHED"
    else:
        fate = "UNTOUCHED"
    return {"fate": fate, "touched": touched, "violated": violated,
            "first_touch_offset": first_touch, "note": ""}


def content_hash(*parts) -> str:
    h = hashlib.sha1("|".join("" if p is None else str(p)
                              for p in parts).encode("utf-8"))
    return h.hexdigest()[:8]


# --------------------------------------------------------------------------- #
# Loading (reuse accepted packs/ledgers — never regenerated)
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_structures() -> list[dict]:
    """Accepted HTF structures (same loader rules as the Stage-3 pack)."""
    structures: list[dict] = []
    with open(ltf.H4_EVENTS_CSV, encoding="utf-8") as f:
        h4_rows = list(csv.DictReader(f))
    for r in h4_rows:
        if r["event_type"] != "poi_raw":
            continue
        ts = datetime.fromisoformat(r["ts_utc"])
        if not (ltf.EXEC_START <= ts <= ltf.EXEC_END):
            continue
        structures.append({
            "event_id": r["event_id"], "direction": r["direction"],
            "zone_low": float(r["zone_low"]),
            "zone_high": float(r["zone_high"]), "ts_utc": r["ts_utc"],
            "_anchor_dt": ts + timedelta(hours=4), "src": "H4_pack_raw",
        })
    if ltf.D1_EVENTS_CSV.exists():
        with open(ltf.D1_EVENTS_CSV, encoding="utf-8") as f:
            d1_rows = [r for r in csv.DictReader(f)
                       if r["event_type"] == "poi_raw"]
        for r in ltf._spread(sorted(d1_rows, key=lambda r: r["ts_utc"]),
                             ltf.MAX_D1_SUBSET):
            ts = datetime.fromisoformat(r["ts_utc"])
            if not (ltf.EXEC_START <= ts <= ltf.EXEC_END):
                continue
            structures.append({
                "event_id": r["event_id"], "direction": r["direction"],
                "zone_low": float(r["zone_low"]),
                "zone_high": float(r["zone_high"]), "ts_utc": r["ts_utc"],
                "_anchor_dt": ts + timedelta(hours=24),
                "src": "D1_pack_subset",
            })
    return structures


def load_series():
    """Canonical M1 slice + M5 exec series (load discipline documented)."""
    parquet = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not parquet.exists():
        raise SystemExit(f"canonical dataset missing: {parquet}")
    m1_all = load_ohlcv_parquet(str(parquet), Timeframe.M1)
    m1 = [c for c in m1_all if c.timestamp >= M1_LOAD_FROM]
    if not m1:
        raise SystemExit("no M1 bars in the load window")
    m5_list = resample_multi(m1, [Timeframe.M5])[Timeframe.M5]
    m5 = CandleSeries(m5_list, Timeframe.M5)
    m5_keys: dict[str, int] = {}
    for i, c in enumerate(m5_list):
        m5_keys.setdefault(c.timestamp.strftime("%Y-%m-%d %H:%M"), i)
    atr = wilder_atr_14([c.high for c in m5_list],
                        [c.low for c in m5_list],
                        [c.close for c in m5_list])
    print(f"[decomp] M1={len(m1)} M5={len(m5_list)} "
          f"({m1[0].timestamp.date()} -> {m1[-1].timestamp.date()})",
          flush=True)
    return m5, m5_keys, atr


def minute_key(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (LTF_LEDGER_CSV, STAGE3_CSV):
        if not path.exists():
            raise SystemExit(f"required input ledger missing: {path}")
    m5, m5_keys, atr = load_series()
    last_idx = len(m5) - 1

    manifest = {
        "ltf_confirmation_ledger": {
            "path": str(LTF_LEDGER_CSV.relative_to(REPO_ROOT)),
            "sha256": _sha256(LTF_LEDGER_CSV)},
        "stage3_ledger": {
            "path": str(STAGE3_CSV.relative_to(REPO_ROOT)),
            "sha256": _sha256(STAGE3_CSV)},
    }

    rows_out: list[dict] = []

    def base_row(**kw) -> dict:
        row = {c: "" for c in CSV_COLUMNS}
        row.update(kw)
        return row

    # ---- Concept 1: HTF zones (fate over H_ZONE from structure close) --- #
    structures = load_structures()
    manifest["htf_structures"] = {
        "h4_pack": str(ltf.H4_EVENTS_CSV.relative_to(REPO_ROOT)),
        "d1_pack": (str(ltf.D1_EVENTS_CSV.relative_to(REPO_ROOT))
                    if ltf.D1_EVENTS_CSV.exists() else "absent"),
        "n": len(structures),
    }
    zone_gaps = 0
    import bisect as _bisect
    m5_stamps = [c.timestamp for c in m5]
    for s in structures:
        # Anchor = first M5 bar at/after structure close (the product arm
        # bar — same rule as the §5 replay, weekend closes included).
        anchor = _bisect.bisect_left(m5_stamps, s["_anchor_dt"])
        is_long = (s["direction"] or "").upper().startswith("LONG")
        if anchor >= len(m5):
            zone_gaps += 1
            rows_out.append(base_row(
                event_id=f"zone-{s['event_id']}", concept="htf-zone",
                detection_tf=("D1" if s["src"] == "D1_pack_subset" else "H4"),
                direction="LONG" if is_long else "SHORT",
                ts_utc=s["_anchor_dt"].isoformat(),
                anchor_lo=s["zone_low"], anchor_hi=s["zone_high"],
                htf_event_id=s["event_id"], htf_context="self",
                horizon_bars=H_ZONE, horizon_kind="ZONE20",
                zone_fate="DATA_GAP", outcome_note="anchor off M5 series"))
            continue
        fate = zone_fate(m5, anchor, s["zone_low"], s["zone_high"], is_long)
        rows_out.append(base_row(
            event_id=f"zone-{s['event_id']}", concept="htf-zone",
            detection_tf=("D1" if s["src"] == "D1_pack_subset" else "H4"),
            direction="LONG" if is_long else "SHORT",
            ts_utc=s["_anchor_dt"].isoformat(),
            anchor_lo=s["zone_low"], anchor_hi=s["zone_high"],
            htf_event_id=s["event_id"], htf_context="self",
            horizon_bars=H_ZONE, horizon_kind="ZONE20",
            zone_fate=fate["fate"], zone_touched=fate["touched"],
            zone_violated=fate["violated"],
            first_touch_offset=fate["first_touch_offset"],
            outcome_note=fate["note"]))

    # ---- Concepts 2-4: detector + trigger rows (path over H_PATH) ------- #
    with open(LTF_LEDGER_CSV, encoding="utf-8", newline="") as f:
        det_rows = list(csv.DictReader(f))
    manifest["ltf_detector_rows"] = len(det_rows)
    with open(STAGE3_CSV, encoding="utf-8", newline="") as f:
        trig_rows = list(csv.DictReader(f))
    manifest["stage3_rows"] = len(trig_rows)

    concept_of = {"SWEEP": "sweep", "DISPLACEMENT": "displacement",
                  "FAIR VALUE GAP": "fvg"}
    truncations = 0

    def scan_one(ts_utc: str, is_long: bool, ref: float | None,
                 atr_v: float | None) -> dict:
        """Frozen H_PATH excursion read (empty + note when unmeasurable)."""
        nonlocal truncations
        idx = m5_keys.get(minute_key(ts_utc) or "")
        if idx is None or ref is None or atr_v is None or atr_v <= 0:
            return {"mfe": None, "mae": None, "hit1": None, "hit2": None,
                    "inv": None, "t_ext": None,
                    "note": "unresolvable event bar/ref/atr"}
        if last_idx < idx + H_PATH:
            truncations += 1
            return {"mfe": None, "mae": None, "hit1": None, "hit2": None,
                    "inv": None, "t_ext": None,
                    "note": f"fewer than {H_PATH} M5 bars after event"}
        mfe, mae = excursion_atr(m5, idx, idx + H_PATH, is_long, ref,
                                 atr_v)
        t_ext = None
        if mfe is not None and mfe > 0:
            best, t_ext = -1.0, idx
            for i in range(idx, idx + H_PATH + 1):
                c = m5[i]
                fav = (c.high - ref) if is_long else (ref - c.low)
                if fav / atr_v > best:
                    best, t_ext = fav / atr_v, i
            t_ext = t_ext - idx
        return {"mfe": mfe, "mae": mae,
                "hit1": (mfe is not None and mfe >= 1.0),
                "hit2": (mfe is not None and mfe >= 2.0),
                "inv": (mae is not None and mae >= 1.0),
                "t_ext": t_ext, "note": ""}

    for r in det_rows:
        tag = (r.get("ltf_plain_tag") or "").split(" (")[0]
        if tag.startswith("TRIGGER"):
            # Product routes live in the Stage-3 ledger (concept trigger-*):
            # skipping here avoids double-counting the same completions.
            continue
        concept = concept_of.get(tag, "other-detector")
        is_long = (r.get("ltf_direction") or "").upper().startswith("LONG")
        lo, hi, ref = parse_level(r.get("ltf_zone_or_level"))
        idx = m5_keys.get(minute_key(r.get("ltf_ts_utc")) or "")
        atr_v = atr[idx] if idx is not None and idx < len(atr) else None
        ctx = htf_context(r.get("relation_to_htf"))
        dist = None
        if (ctx == "far" and ref is not None and atr_v is not None
                and atr_v > 0):
            zl = float(r["htf_zone_low"])
            zh = float(r["htf_zone_high"])
            edge = zh if ref > zh else zl
            dist = round(abs(ref - edge) / atr_v, 3)
        elif ctx == "inside":
            dist = 0.0
        scan = scan_one(r.get("ltf_ts_utc"), is_long, ref, atr_v)
        rows_out.append(base_row(
            event_id=f"det-{content_hash(r.get('htf_event_id'), r.get('ltf_tf'), r.get('ltf_ts_utc'), r.get('ltf_plain_tag'), r.get('ltf_zone_or_level'), r.get('relation_to_htf'))}",
            concept=concept, detection_tf=r.get("ltf_tf"),
            direction="LONG" if is_long else "SHORT",
            ts_utc=r.get("ltf_ts_utc"), anchor_lo=lo, anchor_hi=hi,
            ref_price=ref, htf_event_id=r.get("htf_event_id"),
            htf_context=ctx, dist_to_zone_atr=dist,
            horizon_bars=H_PATH, horizon_kind="PATH100",
            mfe_atr=scan["mfe"], mae_atr=scan["mae"],
            hit_plus1atr=scan["hit1"], hit_plus2atr=scan["hit2"],
            inv_breach_1atr=scan["inv"],
            time_to_extreme_bars=scan["t_ext"],
            outcome_note=scan["note"]))

    for r in trig_rows:
        letter = (r.get("trigger_type") or "?").split("_")[0].upper()
        is_long = (r.get("direction") or "").upper().startswith("LONG")
        try:
            ref = float(r["entry_price_ref"])
        except (TypeError, ValueError):
            ref = None
        idx = m5_keys.get(minute_key(r.get("bar_time_utc")) or "")
        atr_v = atr[idx] if idx is not None and idx < len(atr) else None
        ctx = htf_context(r.get("relation_to_htf"))
        scan = scan_one(r.get("bar_time_utc"), is_long, ref, atr_v)
        rows_out.append(base_row(
            event_id=r.get("trigger_id"), concept=f"trigger-{letter}",
            detection_tf=r.get("trigger_tf"),
            direction="LONG" if is_long else "SHORT",
            ts_utc=r.get("bar_time_utc"),
            anchor_lo=r.get("related_htf_zone_low"),
            anchor_hi=r.get("related_htf_zone_high"),
            ref_price=ref,
            htf_event_id=r.get("related_htf_event_id"),
            htf_context=ctx, dist_to_zone_atr=(0.0 if ctx == "inside" else None),
            horizon_bars=H_PATH, horizon_kind="PATH100",
            mfe_atr=scan["mfe"], mae_atr=scan["mae"],
            hit_plus1atr=scan["hit1"], hit_plus2atr=scan["hit2"],
            inv_breach_1atr=scan["inv"],
            time_to_extreme_bars=scan["t_ext"],
            outcome_note=(";".join(filter(None, [
                scan["note"],
                f"route_would_form={r.get('route_would_form')}"])))))
    # Concept 5: the 3 real fills, listed (never invented, never scanned).
    concept5 = "fills n=3 (product 6m refresh run1: F SL / C TP / F SL-BE); listed only"

    with open(EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows_out:
            writer.writerow({c: ("" if r.get(c) is None else r.get(c))
                             for c in CSV_COLUMNS})

    # ---- Aggregates ------------------------------------------------------ #
    def _median(vals):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return None
        mid = len(vals) // 2
        if len(vals) % 2:
            return vals[mid]
        return (vals[mid - 1] + vals[mid]) / 2.0

    def cell(sub):
        n = len(sub)
        hits = [r for r in sub if r["hit_plus1atr"] is True]
        k = len(hits)
        lo_ci, hi_ci = wilson(k, sum(1 for r in sub
                                     if r["hit_plus1atr"] is not None))
        return {"n": n,
                "hit_plus1atr_n": k,
                "hit_plus1atr_rate": (round(k / n, 4) if n else None),
                "hit_plus1atr_ci95": ([round(lo_ci, 4), round(hi_ci, 4)]
                                      if lo_ci is not None else None),
                "hit_plus2atr_rate": (round(sum(1 for r in sub
                                                if r["hit_plus2atr"] is True) / n, 4)
                                      if n else None),
                "median_mfe_atr": (_median([r["mfe_atr"] for r in sub])
                                   if n else None),
                "median_mae_atr": (_median([r["mae_atr"] for r in sub])
                                   if n else None),
                "inv_breach_rate": (round(sum(1 for r in sub
                                              if r["inv_breach_1atr"] is True) / n, 4)
                                    if n else None),
                "median_time_to_extreme_bars": (
                    _median([r["time_to_extreme_bars"] for r in sub])
                    if n else None)}

    det = [r for r in rows_out if r["concept"] in
           ("sweep", "displacement", "fvg")]
    trig = [r for r in rows_out if r["concept"].startswith("trigger-")]
    by_concept_context: dict[str, dict[str, dict]] = {}
    for concept in ("sweep", "displacement", "fvg", "trigger"):
        pool = trig if concept == "trigger" else [
            r for r in det if r["concept"] == concept]
        by_concept_context[concept] = {
            ctx: cell([r for r in pool if r["htf_context"] == ctx])
            for ctx in ("inside", "near", "far")}

    def verdict(table: dict[str, dict]) -> str:
        inside, far = table["inside"], table["far"]
        if inside["n"] < MIN_CELL_N or far["n"] < MIN_CELL_N:
            return "insufficient_n"
        ci_i, ci_f = inside["hit_plus1atr_ci95"], far["hit_plus1atr_ci95"]
        if ci_i is None or ci_f is None:
            return "insufficient_n"
        if ci_i[1] < ci_f[0] or ci_f[1] < ci_i[0]:
            return "separates"
        return "does_not_separate"

    verdicts = {c: verdict(t) for c, t in by_concept_context.items()}
    decisive = [v for v in verdicts.values() if v != "insufficient_n"]
    if any(v == "separates" for v in decisive):
        overall = "separates"
    elif decisive and all(v == "does_not_separate" for v in decisive):
        overall = "does_not_separate"
    else:
        overall = "insufficient_n"

    # Falsification (ii): routed (2) vs unrouted stage-3 completions.
    routed = [r for r in trig
              if "route_would_form=yes" in (r.get("outcome_note") or "")]
    unrouted = [r for r in trig if r not in routed]
    fals_ii = {
        "routed_n": len(routed),
        "routed": cell(routed),
        "unrouted_n": len(unrouted),
        "unrouted": cell(unrouted),
        "verdict": ("insufficient_n (routed n<30 by the frozen rule; "
                    "values published regardless)")}

    # Binding gates: requoted from product-6m logs (no recompute, ever).
    funnel = json.loads((REPO_ROOT / "06_RESEARCH" / "results" /
                         "product_6m_refresh_track_b" / "run1" /
                         "funnel_summary.json").read_text(encoding="utf-8"))
    binding = {
        "source": "product_6m_refresh_track_b/run1 (requoted, not recomputed)",
        "bars_m5": funnel.get("bars_m5"),
        "htf_batches": funnel.get("htf_batches"),
        "merged_pois": funnel.get("merged_pois"),
        "pillar_first_failure": funnel.get("pillar_first_failure"),
        "passed_validation": funnel.get("passed_validation"),
        "armed": funnel.get("armed"),
        "armed_m8": funnel.get("armed_m8"),
        "scanned_pois": funnel.get("scanned_pois"),
        "routes": funnel.get("routes"),
        "routes_by_trigger": funnel.get("routes_by_trigger"),
        "placed": funnel.get("placed"),
        "intents": {k: funnel.get(k) for k in
                    ("intents_armed", "intents_placed", "intents_expired")},
        "fills": funnel.get("fills"),
        "trades": funnel.get("trades"),
    }
    report = json.loads(PRODUCT_REPORT.read_text(encoding="utf-8"))
    binding["blocked_by_reason"] = report.get("blocked_by_reason", {})
    binding["cost_totals_usd"] = {
        k: report.get("metrics", {}).get(k) for k in
        ("total_commission_usd", "total_spread_cost_usd",
         "total_slippage_usd", "total_swap_usd", "total_cost_usd",
         "net_pnl_after_cost")}

    zone_fates = Counter(r["zone_fate"] for r in rows_out
                         if r["concept"] == "htf-zone")

    summary = {
        "banner": BANNER,
        "frozen": {
            "window": "exec 2025-06-01 -> 2025-11-30 M5; M1 warm-up 2025-05-01",
            "h_zone_m5": H_ZONE, "h_path_m5": H_PATH,
            "htf_context": ("relation inside->inside, retest->near, "
                            "above/below->far (recorded fields only)"),
            "ref_price": "single level as-is; lo..hi midpoint; trigger entry",
            "numeraires": ("ATR(14) Wilder SMA-seeded on M5 at event bar; "
                           "no hypothetical SL anywhere (ATR units, not R)"),
            "zone_fate": ("VIOLATED if any adverse close in window, elif "
                          "touched -> TOUCHED, else UNTOUCHED"),
            "invalidation": "adverse excursion >= 1.0xATR in horizon",
            "truncation": (f"strict: fewer than H bars after event -> "
                           "metrics empty + note"),
            "combination_rule": ("per concept, inside-vs-far +1ATR "
                                 "Wilson-95% CIs, both cells n>=30: disjoint "
                                 "-> separates; overlap -> does_not_separate; "
                                 "else insufficient_n; overall separates if "
                                 "ANY concept separates"),
        },
        "inputs_manifest": manifest,
        "events_by_concept": dict(Counter(r["concept"] for r in rows_out)),
        "zone_rows": len([r for r in rows_out
                          if r["concept"] == "htf-zone"]),
        "zone_anchor_gaps": zone_gaps,
        "path_truncations": truncations,
        "zone_fates": dict(zone_fates),
        "htf_context_mix": {
            concept: dict(Counter(
                r["htf_context"] for r in rows_out
                if r["concept"] == concept))
            for concept in ("sweep", "displacement", "fvg",
                            "trigger-A", "trigger-B", "trigger-C",
                            "trigger-E", "trigger-F")},
        "by_concept_context": by_concept_context,
        "combination_verdicts": verdicts,
        "combination_overall": overall,
        "falsification_ii_routed_vs_unrouted": fals_ii,
        "falsification_iii_fills": {
            "n": 3,
            "rows": "product 6m refresh run1 report.json trades "
                    "(pillar_path/model_tags/tp_source read in the report)",
            "verdict": "insufficient_n (n=3; published, not pooled)",
        },
        "binding_gates_requoted": binding,
        "concept5_note": concept5,
        "limitations": [
            "Detector rows are per-bar re-detections (same setup repeats "
            "across bars): n counts events, not setups — rates are "
            "event-weighted by construction.",
            "htf_context uses the LTF pack's recorded relation only; "
            "above/below distance is diagnostic (dist_to_zone_atr), not "
            "a bucket.",
            "Reference prices are midpoints for ranges (frozen); sweep "
            "singles are exact.",
            "M5 ATR seed starts 2025-05-01 (a month before first events); "
            "atr<=0 rows measured as empty, never zero-filled.",
            "No gate, no threshold, no live rule follows (see report).",
        ],
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[decomp] rows={len(rows_out)} "
          f"concepts={dict(Counter(r['concept'] for r in rows_out))}",
          flush=True)
    print(f"[decomp] combination={overall} "
          f"verdicts={verdicts} fates={dict(zone_fates)}", flush=True)
    print(f"[decomp] wrote {EVENTS_CSV} + {SUMMARY_JSON}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
