#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F entry selectivity + post-exit path (research / logging only).

Lead Architect directive (Track B): understand Trigger F entries —
(1) classify entry character with FROZEN Rule v1 timing labels,
(2) track where price goes AFTER the trade ends on a FROZEN M5 horizon
so "thesis dead" separates from "stopped early / path continued".
NO live gates. NO threshold fishing. NO strategy logic changes.

Frozen inputs (documented, never iterated):
  * Timing labels = Rule v1 from F_TIMING_DISCRIMINATOR_NOTES.md,
    computed on trailing-30-M1-bar geometry (PRE_BARS=30,
    CHOP_ATR_MULT=1.5, CHASE_HI=0.80, CHASE_LO=0.45, Wilder ATR(14)
    SMA-seeded — identical math to f_timing_labels.py, reimplemented
    dependency-free; fidelity-checked against its 37-row artifact).
  * Post-exit taxonomy = hypothesis_outcome_study.classify, reused
    VERBATIM via import for TP-bearing rows (same 5 labels, same 0.25
    analytics divider, same BE-scratch rule). Rows WITHOUT a TP level
    cannot reach the TP-path branches (never defaulted): they run the
    same MFE-only restriction of the taxonomy (documented below).
  * Forward horizon H=100 M5 bars (~one trading day; covers the
    product's 20-bar give-up scale 5x). Fewer than 100 bars after exit
    in-series -> DATA_GAP (strict; never extrapolated).
  * Honest R denominator = |entry - original_sl| STRICT (never a
    BE-modified working stop, never an sl fallback).

Samples (unique-trade identity = entry_at+exit_at+direction+entry_price):
  * product-6m : product_baseline_6m run1 (3 trades; pilot + posttp runs
    re-find the same rows -> 0 unique additions, documented).
  * verify-union: export_patch_verify w0 (115) + w1 (216) deduped on
    identity (39 overlap) -> 292 unique trades. original_sl present on
    all rows; tp null on all rows (TP-path branches unreachable).
  * phase-c-5y : side counts + field-gap statement ONLY (761 rows: no
    original_sl, no tp -> nothing computable beyond published mixes;
    faking columns is banned, so no per-trade rows are emitted).
Per-label pooled stats use the verify pool (F only); product-era rows
are labeled + listed individually (n=2 pools nothing). Non-F triggers
are side counts only.

Outputs: results/f_selectivity_post_exit/trades_f_selectivity.csv +
summary.json. Report: F_SELECTIVITY_POST_EXIT_REPORT.md (separate step).
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
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from smc.config.timeframe import Timeframe
from smc.backtest.data_feed import CandleSeries
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi

import hypothesis_outcome_study as hypo

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "f_selectivity_post_exit"
TRADES_CSV = OUT_DIR / "trades_f_selectivity.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC ONLY — NOT PERFORMANCE / NOT EDGE"

# ---- Frozen Rule v1 (F_TIMING_DISCRIMINATOR_NOTES.md) ------------------ #
PRE_BARS = 30
CHOP_ATR_MULT = 1.5
CHASE_HI = 0.80
CHASE_LO = 0.45
ATR_PERIOD = 14

# ---- Frozen post-exit params (this directive) --------------------------- #
HORIZON_BARS = 100          # M5 bars after exit; strict DATA_GAP if cut
MFE_R_THRESH = hypo.MFE_R_THRESH  # 0.25, analytics divider only (inherited)

# ---- Sample books -------------------------------------------------------- #
BOOKS = {
    "product-6m": (REPO_ROOT / "06_RESEARCH" / "results" /
                   "product_baseline_6m" / "run1" / "report.json", "report"),
    # Duplicates-by-construction (re-find product rows; dedupe evidence):
    "pilot": (REPO_ROOT / "06_RESEARCH" / "results" /
              "product_baseline_pilot" / "run1" / "report.json", "report"),
    "posttp-6m-r1": (REPO_ROOT / "06_RESEARCH" / "results" /
                     "frozen_funnel_6m_post_tp" / "run1" / "trades.csv",
                     "trades"),
    "posttp-6m-r2": (REPO_ROOT / "06_RESEARCH" / "results" /
                     "frozen_funnel_6m_post_tp" / "run2" / "trades.csv",
                     "trades"),
    "verify-w0": (REPO_ROOT / "06_RESEARCH" / "results" /
                  "export_patch_verify" / "verify_w0" / "trades.csv", "trades"),
    "verify-w1": (REPO_ROOT / "06_RESEARCH" / "results" /
                  "export_patch_verify" / "verify_w1" / "trades.csv", "trades"),
    "phase-c-5y": (REPO_ROOT / "06_RESEARCH" / "results" /
                   "phase_c_baseline_run1" / "merged" / "trades.csv", "trades"),
}
M1_LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)

CSV_COLUMNS = [
    "sample", "sample_ticket", "trigger_type", "direction",
    "entry_at", "exit_at", "entry_price", "exit_price",
    "original_sl", "tp", "tp_source", "close_kind", "pnl",
    "timing_label", "chase_pos", "range_atr", "zone_relation",
    "mfe_r_honest", "mae_r_honest", "hold_bars_m5", "hold_bars_m1",
    "horizon_bars", "post_exit_outcome", "tp_touched_after_entry",
    "tp_first_touch_abs_bar", "outcome_note", "horizon_truncated",
]

#: Banner for run scripts that attach these annotations (research
#: measurement only — never a trading filter).
TRACK_B_BANNER = ("Track-B annotations are research measurements "
                  "(DIAGNOSTIC ONLY) — NOT trading filters")


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def minute_key(ts: str) -> str | None:
    """Normalize any timestamp spelling to 'YYYY-MM-DD HH:MM' (M1 key)."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return None


def wilder_atr_14(highs: list[float], lows: list[float],
                  closes: list[float]) -> list[float]:
    """Wilder ATR(14), SMA-seeded — identical math to f_timing_labels.py."""
    n = len(closes)
    atr = [0.0] * n
    if n < ATR_PERIOD:
        return atr
    trs = [highs[0] - lows[0]]
    for i in range(1, n):
        trs.append(max(highs[i] - lows[i],
                       abs(highs[i] - closes[i - 1]),
                       abs(lows[i] - closes[i - 1])))
    s = sum(trs[:ATR_PERIOD]) / ATR_PERIOD
    atr[ATR_PERIOD - 1] = s
    for i in range(ATR_PERIOD, n):
        s = (s * (ATR_PERIOD - 1.0) + trs[i]) / ATR_PERIOD
        atr[i] = s
    return atr


def timing_label(entry_price: float, is_long: bool, window_hi: float,
                 window_lo: float, atr_at_entry: float) -> tuple[str, float | None, float | None]:
    """Frozen Rule v1 label over a trailing-30-bar window (M1)."""
    rng = window_hi - window_lo
    if rng <= 0 or atr_at_entry <= 0:
        return "unclear", None, None
    chase = ((entry_price - window_lo) / rng) if is_long else \
        ((window_hi - entry_price) / rng)
    ratr = rng / atr_at_entry
    if ratr < CHOP_ATR_MULT:
        return "chop", chase, ratr
    if chase >= CHASE_HI:
        return "late_chase", chase, ratr
    if chase >= CHASE_LO:
        return "mid_move", chase, ratr
    return "structured_pullback", chase, ratr


def zone_relation(entry_price: float, zone_low: float | None,
                  zone_high: float | None) -> str:
    """Zone relation axis (same rule as f_timing_labels.py)."""
    if zone_low is None or zone_high is None or zone_high <= zone_low:
        return "unknown"
    if zone_low <= entry_price <= zone_high:
        return "INSIDE"
    off = entry_price - zone_high if entry_price > zone_high \
        else zone_low - entry_price
    side = "above" if entry_price > zone_high else "below"
    return f"{side} {100.0 * off / (zone_high - zone_low):.0f}%"


def honest_r(excursion_units: float | None, entry_price: float | None,
             original_sl: float | None) -> float | None:
    """Honest R multiple. STRICT: no original_sl -> None (never sl)."""
    if excursion_units is None or entry_price is None or original_sl is None:
        return None
    denom = abs(entry_price - original_sl)
    if denom <= 0:
        return None
    return excursion_units / denom


def m1_index_at_or_before(m1_keys: dict[str, int], sorted_keys: list[str],
                          key: str | None) -> int | None:
    """Bar index of the greatest M1 minute-key <= target (None if none)."""
    import bisect as _bisect
    if not key:
        return None
    pos = _bisect.bisect_right(sorted_keys, key) - 1
    if pos < 0:
        return None
    return m1_keys[sorted_keys[pos]]


def m1_excursion(m1: list, entry_idx: int | None, exit_idx: int | None,
                 is_long: bool, entry_price: float | None
                 ) -> tuple[float | None, float | None]:
    """In-trade max favorable/adverse excursion on M1 (price units).

    honest_r convention (matches the honest_r table bit-for-bit):
    reference = ENTRY FILL PRICE (not bar close), entry bar through
    exit bar inclusive, floored at 0 downstream by honest_r().
    """
    if entry_idx is None or exit_idx is None or entry_price is None:
        return None, None
    if not (0 <= entry_idx <= exit_idx < len(m1)):
        return None, None
    mfe, mae = 0.0, 0.0
    for c in m1[entry_idx:exit_idx + 1]:
        if is_long:
            mfe = max(mfe, c.high - entry_price)
            mae = max(mae, entry_price - c.low)
        else:
            mfe = max(mfe, entry_price - c.low)
            mae = max(mae, c.high - entry_price)
    return mfe, mae


def identity_of(row: dict) -> tuple:
    """Unique-trade identity (entry+exit minute + direction + price).

    Minute-normalized so spelling variants across books still collide;
    price float-normalized so CSV strings collide with JSON numbers;
    run-local tickets never participate.
    """
    try:
        price = float(row.get("entry_price"))
    except (TypeError, ValueError):
        price = None
    return (minute_key(row.get("entry_at") or ""),
            minute_key(row.get("exit_at") or ""),
            (row.get("direction") or "").lower(),
            price)


def classify_no_tp(direction: str, mfe_units: float, mae_units: float,
                   mfe_r: float | None, is_sl_exit: bool,
                   be_scratch: bool) -> tuple[str, str]:
    """TP-path-free restriction of the locked taxonomy (tp null rows).

    Same 5 labels, same 0.25 divider, same BE-scratch-first order as
    hypothesis_outcome_study.classify; the TP_REACHED / SL_THEN_TP_PATH
    branches are unreachable without a TP level (never defaulted, never
    invented). mfe_r MUST be the M1 fill-referenced honest R (same value
    as the label tables — bit-identical to the honest_r table), NOT the
    M5 bar-close excursion: the divider must operate on the R readers
    see in the tables.
    """
    if be_scratch:
        return ("MFE_ONLY",
                "BE-scratch close; no TP level so no after-exit TP check")
    if mfe_r is not None and mfe_r < MFE_R_THRESH:
        return ("REJECTED",
                f"MFE_R={mfe_r:.3f} < {MFE_R_THRESH} (analytics divider only)")
    if mfe_units > 0:
        return ("MFE_ONLY",
                "favorable excursion, no TP level to test a path against")
    if is_sl_exit:
        return ("REJECTED", "stop exit with no favorable excursion, no TP level")
    return ("REJECTED", "residual REJECTED (no TP level)")


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_books() -> tuple[dict, list[dict]]:
    """Load sample books + manifest (paths, SHAs, counts, field matrix)."""
    manifest: dict = {}
    samples: list[dict] = []
    for sample, (path, kind) in BOOKS.items():
        if not path.exists():
            manifest[sample] = {"path": str(path), "status": "MISSING"}
            continue
        if kind == "report":
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("trades", [])
        else:
            with open(path, encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
        cols = sorted(rows[0].keys()) if rows else []
        manifest[sample] = {
            "path": str(path.relative_to(REPO_ROOT)),
            "sha256": _sha256(path),
            "rows": len(rows),
            "columns": cols,
            "has_original_sl": "original_sl" in cols,
            "original_sl_non_null": sum(1 for r in rows
                                        if r.get("original_sl")),
            "has_tp": "tp" in cols,
            "tp_non_null": sum(1 for r in rows if r.get("tp")),
            "has_tp_source": "tp_source" in cols,
        }
        for r in rows:
            samples.append({"sample": sample, "row": r})
    return manifest, samples


def load_series() -> tuple[list, dict[str, int], CandleSeries, CandleSeries]:
    """Canonical M1 slice + M5 exec series over the same load window."""
    parquet = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not parquet.exists():
        raise SystemExit(f"canonical dataset missing: {parquet}")
    m1_all = load_ohlcv_parquet(str(parquet), Timeframe.M1)
    m1 = [c for c in m1_all if c.timestamp >= M1_LOAD_FROM]
    if not m1:
        raise SystemExit("no M1 bars in the load window")
    m1_keys = {}
    for i, c in enumerate(m1):
        m1_keys.setdefault(c.timestamp.strftime("%Y-%m-%d %H:%M"), i)
    m1_sorted = sorted(m1_keys)
    m5_list = resample_multi(m1, [Timeframe.M5])[Timeframe.M5]
    m5 = CandleSeries(m5_list, Timeframe.M5)
    m1hi = [c.high for c in m1]
    m1lo = [c.low for c in m1]
    m1cl = [c.close for c in m1]
    atr = wilder_atr_14(m1hi, m1lo, m1cl)
    print(f"[f-sel] M1={len(m1)} M5={len(m5)} "
          f"({m1[0].timestamp.date()} -> {m1[-1].timestamp.date()})", flush=True)
    return m1, m1_keys, m1_sorted, m5, atr


# --------------------------------------------------------------------------- #
# Per-trade pipeline
# --------------------------------------------------------------------------- #
def label_trade_f(row: dict, m1: list, m1_keys: dict[str, int],
                  atr: list[float]) -> dict:
    """Frozen Rule v1 label + zone relation + chase/range diagnostics."""
    entry = hypo.parse_price(row.get("entry_price"))
    key = minute_key(row.get("entry_at") or "")
    is_long = (row.get("direction") or "").lower().startswith("long")
    zone = zone_relation(
        entry, hypo.parse_price(row.get("zone_low")),
        hypo.parse_price(row.get("zone_high"))) if entry is not None \
        else "unknown"
    b0 = m1_keys.get(key) if key else None
    if entry is None or b0 is None:
        return {"timing_label": "unclear", "chase_pos": None,
                "range_atr": None, "zone_relation": zone,
                "entry_m1_index": None}
    a0 = max(0, b0 - PRE_BARS)
    window = m1[a0:b0]
    if not window:
        return {"timing_label": "unclear", "chase_pos": None,
                "range_atr": None,
                "zone_relation": zone_relation(
                    entry, hypo.parse_price(row.get("zone_low")),
                    hypo.parse_price(row.get("zone_high"))),
                "entry_m1_index": b0}
    w_hi = max(c.high for c in window)
    w_lo = min(c.low for c in window)
    label, chase, ratr = timing_label(entry, is_long, w_hi, w_lo, atr[b0])
    return {"timing_label": label,
            "chase_pos": round(chase, 3) if chase is not None else None,
            "range_atr": round(ratr, 3) if ratr is not None else None,
            "zone_relation": zone_relation(
                entry, hypo.parse_price(row.get("zone_low")),
                hypo.parse_price(row.get("zone_high"))),
            "entry_m1_index": b0}


def post_exit(row: dict, m5: CandleSeries,
              m1_r_override: float | None = "__unset__") -> dict:
    """Post-exit outcome on the frozen H=100 M5 horizon (strict truncation).

    m1_r_override: the M1 fill-referenced honest R for the no-TP branch
    (computed by the caller on the same convention as the label tables).
    "__unset__" (default) keeps the function standalone-testable, in
    which case the branch falls back to the M5-window R.
    """
    entry_ts = row.get("entry_at") or ""
    exit_ts = row.get("exit_at") or ""
    try:
        entry_idx = m5.index_at_or_before(datetime.fromisoformat(entry_ts))
    except (ValueError, TypeError):
        entry_idx = None
    try:
        exit_idx = m5.index_at_or_before(datetime.fromisoformat(exit_ts))
    except (ValueError, TypeError):
        exit_idx = None
    base = {"entry_m5_index": entry_idx, "exit_m5_index": exit_idx,
            "horizon_truncated": None}
    if entry_idx is None or exit_idx is None:
        return {**base, "post_exit_outcome": "DATA_GAP",
                "tp_touched_after_entry": None,
                "tp_first_touch_abs_bar": None,
                "outcome_note": "entry/exit timestamp not resolvable on M5",
                "mfe_units": None, "mae_units": None,
                "mfe_r_classify": None, "horizon_truncated": True}
    if len(m5) - 1 < exit_idx + HORIZON_BARS:
        return {**base, "post_exit_outcome": "DATA_GAP",
                "tp_touched_after_entry": None,
                "tp_first_touch_abs_bar": None,
                "outcome_note": (f"fewer than {HORIZON_BARS} M5 bars after "
                                 "exit in-series (strict truncation)"),
                "mfe_units": None, "mae_units": None,
                "mfe_r_classify": None, "horizon_truncated": True}
    lo = max(0, entry_idx - 1)
    hi = exit_idx + HORIZON_BARS
    window = CandleSeries(list(m5)[lo:hi + 1], Timeframe.M5)
    slim = dict(row)
    slim["entry_bar"] = ""  # run-relative indices are not portable
    slim["exit_bar"] = ""   # across books — timestamps resolve instead
    tp = hypo.parse_price(row.get("tp"))
    if tp is not None:
        c = hypo.classify(slim, window)
        touch = c.get("tp_first_touch_bar")
        return {
            **base, "post_exit_outcome": c.get("hypothesis_outcome"),
            "tp_touched_after_entry": c.get("tp_touched_after_entry"),
            "tp_first_touch_abs_bar": (touch + lo if isinstance(touch, int)
                                       else None),
            "outcome_note": c.get("note"),
            "mfe_units": c.get("mfe_units"),
            "mae_units": c.get("mae_units"),
            "mfe_r_classify": c.get("mfe_ratio_over_original_sl"),
            "horizon_truncated": False,
        }
    # No TP level: TP-path branches unreachable (never defaulted).
    direction = row.get("direction", "")
    mfe = hypo.max_favorable(window, entry_idx - lo, exit_idx - lo, direction)
    mae = hypo.max_adverse(window, entry_idx - lo, exit_idx - lo, direction)
    pnl = hypo.parse_price(row.get("pnl"))
    kind = (row.get("close_kind") or "").strip().lower()
    is_sl = kind == "stop_loss"
    be_scratch = is_sl and (pnl is not None and abs(pnl) < 0.15)
    if m1_r_override == "__unset__":
        mfe_r = honest_r(mfe, hypo.parse_price(row.get("entry_price")),
                         hypo.parse_price(row.get("original_sl")))
    else:
        mfe_r = m1_r_override
    outcome, note = classify_no_tp(direction, mfe, mae, mfe_r, is_sl,
                                   be_scratch)
    return {**base, "post_exit_outcome": outcome,
            "tp_touched_after_entry": None,
            "tp_first_touch_abs_bar": None,
            "outcome_note": note + " [no TP level on order]",
            "mfe_units": mfe, "mae_units": mae,
            "mfe_r_classify": mfe_r, "horizon_truncated": False}


# --------------------------------------------------------------------------- #
# Product-harness entry point (Tier-1 harness — reuse, not re-tuning)
# --------------------------------------------------------------------------- #
def _trigger_letter(trigger) -> str:
    """Trigger family letter, shared convention (cf. stage3 inventory)."""
    if trigger is None:
        return "?"
    return str(getattr(trigger, "value", trigger)).split("_")[0].upper()


def _iso(ts) -> str:
    if ts is None:
        return ""
    if isinstance(ts, str):
        return ts
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)


def _dir_name(direction) -> str:
    return str(getattr(direction, "value", direction) or "").lower()


def annotate_product_trades(closed_positions, *, m1, m5) -> dict:
    """Track-B annotations for product-run closes (research only).

    Reuses the frozen pieces of THIS module (Rule v1 timing labels,
    strict honest R, frozen H=100 post-exit taxonomy incl. the TP-absent
    restriction) — nothing re-tuned, no thresholds. Intended caller: the
    product backtest composition, which passes its loaded M1 slice and
    M5 exec series plus the runner's closed positions, then feeds the
    returned map into ``reports.build_report(annotations=...)``.

    Load discipline (documented — ATR seed + trailing windows need
    history): M1 must start well before the first entry (the composition
    loads a month of warm-up); entries inside the first ATR seed window
    label "unclear" by rule. M5 must cover entries/exits; exits within
    100 M5 bars of the series end classify DATA_GAP (strict).

    Returns ``{ticket: {"f_timing_label": str | None,
    "post_exit_class": str | None}}`` — labels for F rows only (None
    otherwise), outcomes for every row. Unresolvable geometry yields
    "unclear"/DATA_GAP — never invented, never a filter.
    """
    m1_keys: dict[str, int] = {}
    for i, c in enumerate(m1):
        m1_keys.setdefault(c.timestamp.strftime("%Y-%m-%d %H:%M"), i)
    m1_sorted = sorted(m1_keys)
    atr = wilder_atr_14([c.high for c in m1], [c.low for c in m1],
                        [c.close for c in m1]) if m1 else []
    out: dict = {}
    for rec in closed_positions:
        pos = rec.position
        direction = _dir_name(pos.direction)
        is_long = direction.startswith("long")
        row = {
            "direction": direction,
            "entry_price": str(pos.entry_price),
            "exit_price": str(rec.exit_price),
            "sl": "" if pos.sl is None else str(pos.sl),
            "tp": "" if pos.tp is None else str(pos.tp),
            "original_sl": ("" if pos.original_sl is None
                            else str(pos.original_sl)),
            "tp_source": "",
            "close_kind": rec.kind,
            "pnl": str(rec.realized_pnl),
            "entry_at": _iso(pos.entry_at),
            "exit_at": _iso(rec.exit_at),
            "zone_low": ("" if pos.zone_low is None else str(pos.zone_low)),
            "zone_high": ("" if pos.zone_high is None
                          else str(pos.zone_high)),
            "entry_bar": "",  # run-relative indices are not portable
            "exit_bar": "",   # timestamps resolve instead
        }
        letter = _trigger_letter(pos.trigger)
        label = None
        if letter == "F" and m1:
            lab = label_trade_f(row, m1, m1_keys, atr)
            label = lab["timing_label"]
        mfe_r = None
        if m1:
            e1 = m1_index_at_or_before(m1_keys, m1_sorted,
                                       minute_key(row["entry_at"]))
            x1 = m1_index_at_or_before(m1_keys, m1_sorted,
                                       minute_key(row["exit_at"]))
            entry_f = hypo.parse_price(row["entry_price"])
            mfe1, _mae1 = m1_excursion(m1, e1, x1, is_long, entry_f)
            mfe_r = honest_r(mfe1, entry_f,
                             hypo.parse_price(row["original_sl"]))
        if len(m5) == 0:
            outcome = {"post_exit_outcome": "DATA_GAP",
                       "outcome_note": "empty M5 series"}
        else:
            outcome = post_exit(row, m5, m1_r_override=mfe_r)
        out[pos.ticket] = {
            "f_timing_label": label,
            "post_exit_class": outcome["post_exit_outcome"],
        }
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest, samples = load_books()
    m1, m1_keys, m1_sorted, m5, atr = load_series()

    # ---- Dedupe (unique-trade identity; pilot/posttp re-find 6m rows) --- #
    seen: dict[tuple, str] = {}
    unique: list[dict] = []
    dupes: list[dict] = []
    for s in samples:
        if s["sample"] == "phase-c-5y":
            continue  # side counts + gap statement only (no per-trade rows)
        key = identity_of(s["row"])
        if key in seen:
            dupes.append({"sample": s["sample"],
                          "ticket": s["row"].get("ticket"),
                          "duplicate_of_sample": seen[key]})
            continue
        seen[key] = s["sample"]
        unique.append(s)
    print(f"[f-sel] books={len(samples)} unique={len(unique)} "
          f"dupes={len(dupes)}", flush=True)

    rows_out: list[dict] = []
    for s in unique:
        sample, row = s["sample"], s["row"]
        trig = (row.get("trigger") or "").upper()
        # Trigger letter normalization across books (F_BOS_OB value vs "F").
        letter = trig.split("_")[0] if trig else "?"
        is_f = letter == "F"
        if is_f:
            lab = label_trade_f(row, m1, m1_keys, atr)
        else:
            lab = {"timing_label": "", "chase_pos": None, "range_atr": None,
                   "zone_relation": "", "entry_m1_index": None}
        post = None
        entry_price = hypo.parse_price(row.get("entry_price"))
        original_sl = hypo.parse_price(row.get("original_sl"))
        # In-trade excursion for label tables AND the no-TP outcome
        # divider: M1 resolution, fill-referenced (honest_r convention —
        # bit-identical to the honest_r table; the TP-row outcome divider
        # inherits the M5-window excursion of the prior classifier —
        # both documented, never mixed).
        mfe_r = mae_r = None
        if is_f:
            is_long = (row.get("direction") or "").lower().startswith("long")
            e1 = m1_index_at_or_before(
                m1_keys, m1_sorted, minute_key(row.get("entry_at") or ""))
            x1 = m1_index_at_or_before(
                m1_keys, m1_sorted, minute_key(row.get("exit_at") or ""))
            mfe1, mae1 = m1_excursion(m1, e1, x1, is_long, entry_price)
            mfe_r = honest_r(mfe1, entry_price, original_sl)
            mae_r = honest_r(mae1, entry_price, original_sl)
        post = post_exit(row, m5,
                         m1_r_override=mfe_r if is_f else "__unset__")
        hold = None
        hold_m1 = None
        if (post.get("entry_m5_index") is not None
                and post.get("exit_m5_index") is not None):
            hold = post["exit_m5_index"] - post["entry_m5_index"]
        if is_f and e1 is not None and x1 is not None and x1 >= e1:
            hold_m1 = x1 - e1
        rows_out.append({
            "sample": sample,
            "sample_ticket": row.get("ticket"),
            "trigger_type": letter,
            "direction": (row.get("direction") or "").lower(),
            "entry_at": row.get("entry_at"),
            "exit_at": row.get("exit_at"),
            "entry_price": entry_price,
            "exit_price": hypo.parse_price(row.get("exit_price")),
            "original_sl": original_sl,
            "tp": hypo.parse_price(row.get("tp")),
            "tp_source": (row.get("tp_source") or "").lower() or "unknown",
            "close_kind": (row.get("close_kind") or "").lower(),
            "pnl": hypo.parse_price(row.get("pnl")),
            "timing_label": lab["timing_label"],
            "chase_pos": lab["chase_pos"],
            "range_atr": lab["range_atr"],
            "zone_relation": lab["zone_relation"],
            "mfe_r_honest": round(mfe_r, 4) if mfe_r is not None else None,
            "mae_r_honest": round(mae_r, 4) if mae_r is not None else None,
            "hold_bars_m5": hold,
            "hold_bars_m1": hold_m1,
            "horizon_bars": HORIZON_BARS,
            "post_exit_outcome": post["post_exit_outcome"],
            "tp_touched_after_entry": post["tp_touched_after_entry"],
            "tp_first_touch_abs_bar": post["tp_first_touch_abs_bar"],
            "outcome_note": post["outcome_note"],
            "horizon_truncated": post["horizon_truncated"],
        })

    with open(TRADES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows_out:
            writer.writerow({c: ("" if r.get(c) is None else r.get(c))
                             for c in CSV_COLUMNS})

    # ---- Aggregates ------------------------------------------------------ #
    f_rows = [r for r in rows_out if r["trigger_type"] == "F"]
    side_counts: dict[str, int] = dict(Counter(
        r["trigger_type"] for r in rows_out if r["trigger_type"] != "F"))
    label_counts = dict(Counter(r["timing_label"] for r in f_rows))
    outcome_counts = dict(Counter(r["post_exit_outcome"] for r in rows_out))
    outcome_counts_f = dict(Counter(r["post_exit_outcome"] for r in f_rows))

    def _median(vals: list[float]) -> float | None:
        vals = sorted(vals)
        if not vals:
            return None
        mid = len(vals) // 2
        if len(vals) % 2:
            return vals[mid]
        return (vals[mid - 1] + vals[mid]) / 2.0

    per_label: dict[str, dict] = {}
    verify_f = [r for r in f_rows if r["sample"].startswith("verify-")]
    for label in ("late_chase", "mid_move", "structured_pullback", "chop",
                  "unclear"):
        sub = [r for r in verify_f if r["timing_label"] == label]
        mfe = [r["mfe_r_honest"] for r in sub
               if r["mfe_r_honest"] is not None]
        mae = [r["mae_r_honest"] for r in sub
               if r["mae_r_honest"] is not None]
        holds = [r["hold_bars_m5"] for r in sub
                 if r["hold_bars_m5"] is not None]
        holds_m1 = [r["hold_bars_m1"] for r in sub
                    if r.get("hold_bars_m1") is not None]
        per_label[label] = {
            "n": len(sub),
            "n_mfe_r": len(mfe),
            "median_mfe_r": _median(mfe),
            "median_mae_r": _median(mae),
            "pct_ge_1R": (100.0 * sum(1 for v in mfe if v >= 1.0) / len(mfe)
                          if mfe else None),
            "pct_ge_2R": (100.0 * sum(1 for v in mfe if v >= 2.0) / len(mfe)
                          if mfe else None),
            "exit_mix": dict(Counter(r["close_kind"] for r in sub)),
            "median_hold_bars_m5": _median([float(h) for h in holds]),
            "median_hold_bars_m1": _median([float(h) for h in holds_m1]),
        }

    # Cross-tab: outcome x label x tp_source x close_kind (counts).
    cross: dict[str, dict[str, dict[str, dict[str, int]]]] = {}
    for r in rows_out:
        oc, lab = r["post_exit_outcome"], r["timing_label"] or "(non-F)"
        cross.setdefault(oc, {}).setdefault(lab, {}).setdefault(
            r["tp_source"], {}).setdefault(r["close_kind"], 0)
        cross[oc][lab][r["tp_source"]][r["close_kind"]] += 1

    phasec = manifest.get("phase-c-5y", {})

    summary = {
        "banner": BANNER,
        "frozen": {
            "timing_rule": ("Rule v1 (F_TIMING_DISCRIMINATOR_NOTES.md): "
                            "trailing-30-M1-bar range, Wilder ATR(14) "
                            "SMA-seeded; chop<1.5xATR; late_chase>=0.80; "
                            "mid_move>=0.45; else structured_pullback; "
                            "degenerate->unclear"),
            "pre_bars": PRE_BARS, "chop_atr_mult": CHOP_ATR_MULT,
            "chase_hi": CHASE_HI, "chase_lo": CHASE_LO,
            "horizon_m5_bars": HORIZON_BARS,
            "horizon_rule": (f"strict: fewer than {HORIZON_BARS} M5 bars "
                             "after exit in-series -> DATA_GAP"),
            "honest_r": ("|entry-original_sl| strict; missing/degenerate "
                         "denominator -> R empty (never working-sl)"),
            "post_exit_taxonomy": ("hypothesis_outcome_study.classify "
                                   "verbatim for TP-bearing rows; TP-absent "
                                   "rows run the TP-path-free restriction "
                                   "(same labels/thresholds)"),
            "be_scratch": "|pnl|<0.15 + stop_loss -> MFE_ONLY default",
            "mfe_r_divider": MFE_R_THRESH,
            "pooling": ("per-label stats on the verify pool (F only); "
                        "product-era rows labeled + listed, never pooled; "
                        "non-F triggers side counts only"),
            "dedup_identity": "entry_at+exit_at+direction+entry_price",
        },
        "samples_manifest": manifest,
        "duplicates_dropped": dupes,
        "phase_c_5y_gap": {
            "rows": phasec.get("rows"),
            "trigger_mix": "F 659 / B 70 / A 29 / E 2 / C 1 (published book)",
            "close_mix": "stop_loss 754 + friday_eod 7 (published book)",
            "fields": "NO original_sl, NO tp on any row -> honest R and "
                      "TP-path outcomes uncomputable; side counts only, "
                      "no per-trade rows emitted, nothing faked",
        },
        "total_unique_trades": len(rows_out),
        "sample_n_f": sum(1 for r in rows_out if r["trigger_type"] == "F"),
        "label_counts_f": label_counts,
        "side_counts_non_f": side_counts,
        "post_exit_counts_all": outcome_counts,
        "post_exit_counts_f": outcome_counts_f,
        "per_label_verify_pool_note": ("verify-w0 + verify-w1 deduped; "
                                       "F only"),
        "per_label": per_label,
        "product_era_rows": [
            {k: r[k] for k in ("sample", "sample_ticket", "trigger_type",
                               "direction", "entry_at", "timing_label",
                               "chase_pos", "zone_relation", "mfe_r_honest",
                               "post_exit_outcome", "tp_source",
                               "close_kind")}
            for r in rows_out if r["sample"] == "product-6m"
        ],
        "cross_tab": cross,
        "limitations": [
            "Verify pool = one Oct-2025 regime (8-15 days, M1 book, "
            "pre-TP-feed, all exits stop_loss): any separation found is "
            "single-regime evidence, not a general filter.",
            "Product-era n=2F: labeled and listed, never pooled; no "
            "percentage is computed on n=2.",
            "TP-path outcomes exist only where TP levels exist (product "
            "rows); verify rows test the MFE/REJECTED restriction only.",
            "MFE_R uses M1 in-trade excursion referenced to the fill "
            "price (honest_r convention, bit-identical on overlap); the "
            "no-TP outcome divider operates on that same R; only "
            "TP-bearing rows inherit the prior classifier verbatim "
            "(M5-window excursion inside) — all documented.",
            "Hold bars are M5 exit-entry (coarse for M1-executed trades); "
            "M1 holds also reported.",
            "No gate, no threshold, no live rule follows from any table "
            "here (see separation verdict).",
        ],
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[f-sel] unique={len(rows_out)} F={summary['sample_n_f']} "
          f"labels={label_counts} outcomes={outcome_counts_f}", flush=True)
    print(f"[f-sel] wrote {TRADES_CSV} + {SUMMARY_JSON}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
