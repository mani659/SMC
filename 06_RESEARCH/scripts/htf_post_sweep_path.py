#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HTF post-sweep path analysis (read-only — measurement only).

Lead Architect directive: after a valid HTF sweep (H4 and/or H1),
measure what price does next — favorable continuation vs adverse
failure — WITHOUT requiring POI arm, pillars, LTF triggers, or fills.
NO production threshold/detector/pillar changes. No expectancy claims.

Frozen design (stated before running — nothing iterated):
  * Sample: UNIQUE level + FIRST sweep only in the exec window
    (census is_first_touch rows; re-fires counted as side counts only).
  * Stratify by TF (H4, H1) and level_family (structural_swing vs
    session vs equal_highs_lows as present).
  * Direction from census pool (reporting only): BSL -> downside
    continuation (SHORT bias), SSL -> upside (LONG bias).
  * Horizons (exact sets, no mining): {1,3,5,10} bars AFTER the sweep
    bar on the SAME TF (exclusive: window = sweep_idx+1 .. sweep_idx+H).
    Secondary M5-translated horizon only: H4->20 M5 bars, H1->5 M5 bars
    (~0.4 native bars — a shorter lens, clearly labeled secondary).
  * Reference (one rule, kept everywhere): the swept LEVEL extreme in
    the sweep direction (BSL: level minus subsequent lows; SSL:
    subsequent highs minus level) — NOT the sweep close.
  * Numeraires: ATR(14) Wilder SMA-seeded ON THE SERIES BEING READ at
    the sweep bar (TF ATR for native horizons, M5 ATR for secondary).
    No hypothetical SL anywhere (no R-multiples, no invented stops).
  * reclaim_fail (precise): the first bar in the window whose CLOSE is
    back beyond the level AGAINST the sweep close — BSL (close<level
    at sweep): a later close > level; SSL (close>level at sweep):
    a later close < level. Empty when never reclaimed in-window.
  * Truncation (frozen, strict): fewer than H bars after the sweep
    bar in-series -> metrics empty + note (never extrapolated).
    Series loaded with a forward buffer past exec end so Nov-30
    sweeps still read fully (buffer is look-forward DATA, not wider
    event selection — events counted only inside the exec window).

Reuse (import, not fork): census CSVs (no re-detection); canonical
loader + resample + CandleSeries from smc; wilder_atr_14 from
f_selectivity_post_exit; wilson from decomposed_6m_ledger.
LOGIC_CHANGED: NO (04_SRC untouched — series helpers only).

Outputs: results/htf_post_sweep_path/{sweeps_path_h4.csv,
sweeps_path_h1.csv, summary.json}. Report: HTF_POST_SWEEP_PATH_REPORT.md
(separate step).
"""

from __future__ import annotations

import csv
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
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi

from f_selectivity_post_exit import wilder_atr_14
from decomposed_6m_ledger import wilson

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "htf_post_sweep_path"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — NOT EDGE"

EXEC_FROM = datetime(2025, 6, 1, tzinfo=timezone.utc)
EXEC_TO = datetime(2025, 11, 30, 23, 59, tzinfo=timezone.utc)
LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)
LOAD_TO = datetime(2026, 2, 1, tzinfo=timezone.utc)  # forward buffer only
HORIZONS = (1, 3, 5, 10)
M5_SECONDARY = {"H4": 20, "H1": 5}

CENSUS_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "htf_sweep_census"

H_COLS = ["mfe_atr", "mae_atr", "hit_plus1atr", "hit_plus2atr",
          "adverse_1atr", "reclaim_fail", "time_to_mfe_bars",
          "time_to_mae_bars"]
CSV_COLUMNS = (
    ["event_id", "tf", "bar_ts", "pool", "direction_bias", "level_family",
     "level", "atr_at_sweep"] +
    [f"h{h}_{c}" for h in list(HORIZONS) + ["m5sec"] for c in H_COLS] +
    ["truncated_horizons", "note"]
)


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def continuation_signs(pool_value: str | None) -> tuple[bool, int]:
    """(is_short_continuation, direction_sign_for_reference).

    BSL (swept highs, closed back below) -> downside continuation;
    SSL (swept lows, closed back above) -> upside continuation.
    Unknown pools raise (never silently mis-signed).
    """
    pool = (pool_value or "").strip().lower()
    if pool == "bsl":
        return True, -1
    if pool == "ssl":
        return False, 1
    raise ValueError(f"no continuation direction for pool {pool_value!r}")


def path_metrics(bars, start: int, end: int, *, level: float,
                 is_short_cont: bool, atr: float) -> dict:
    """Frozen H-bar path read over (sweep, sweep+H] (exclusive of sweep).

    Reference = swept level extreme in sweep direction. Returns Nones
    when the window is unmeasurable (empty/truncated handled by caller
    via end clamping — this function measures exactly what it is given).
    """
    fav, adv = 0.0, 0.0
    t_fav = t_mae = None
    reclaim = None
    for k, i in enumerate(range(start, end + 1)):
        c = bars[i]
        offset = k + 1  # 1-based bars after sweep
        if is_short_cont:
            f, a = level - c.low, c.high - level
            if c.close > level and reclaim is None:
                reclaim = offset
        else:
            f, a = c.high - level, level - c.low
            if c.close < level and reclaim is None:
                reclaim = offset
        if f > fav:
            fav, t_fav = f, offset
        if a > adv:
            adv, t_mae = a, offset
    if atr <= 0:
        return {"mfe_atr": None, "mae_atr": None, "hit_plus1atr": None,
                "hit_plus2atr": None, "adverse_1atr": None,
                "reclaim_fail": None, "time_to_mfe_bars": None,
                "time_to_mae_bars": None}
    mfe, mae = fav / atr, adv / atr
    return {"mfe_atr": mfe, "mae_atr": mae,
            "hit_plus1atr": mfe >= 1.0, "hit_plus2atr": mfe >= 2.0,
            "adverse_1atr": mae >= 1.0,
            "reclaim_fail": reclaim is not None,
            "time_to_mfe_bars": t_fav if fav > 0 else None,
            "time_to_mae_bars": t_mae if mae > 0 else None}


# --------------------------------------------------------------------------- #
# Loading (reuse census rows + canonical series — nothing regenerated)
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_series():
    """Canonical M1 slice + H4/H1/M5 series (forward buffer included)."""
    parquet = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not parquet.exists():
        raise SystemExit(f"canonical dataset missing: {parquet}")
    m1_all = load_ohlcv_parquet(str(parquet), Timeframe.M1)
    m1 = [c for c in m1_all if LOAD_FROM <= c.timestamp <= LOAD_TO]
    if not m1:
        raise SystemExit("no M1 bars in the load window")
    multi = resample_multi(m1, [Timeframe.H4, Timeframe.H1, Timeframe.M5])
    out = {}
    for tf in (Timeframe.H4, Timeframe.H1, Timeframe.M5):
        bars = multi[tf]
        keys = {}
        for i, c in enumerate(bars):
            keys.setdefault(c.timestamp.strftime("%Y-%m-%d %H:%M"), i)
        atr = wilder_atr_14([c.high for c in bars], [c.low for c in bars],
                            [c.close for c in bars])
        out[tf.name] = {"bars": bars, "keys": keys, "atr": atr}
    print(f"[path] H4={len(out['H4']['bars'])} H1={len(out['H1']['bars'])} "
          f"M5={len(out['M5']['bars'])}", flush=True)
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for tf in ("h4", "h1"):
        path = CENSUS_DIR / f"sweeps_{tf}.csv"
        if not path.exists():
            raise SystemExit(f"census rows missing: {path}")
    S = load_series()

    manifest = {}
    all_rows: list[dict] = []
    for tf_name in ("H4", "H1"):
        src = CENSUS_DIR / f"sweeps_{tf_name.lower()}.csv"
        with open(src, encoding="utf-8", newline="") as f:
            census_rows = list(csv.DictReader(f))
        manifest[tf_name] = {"path": str(src.relative_to(REPO_ROOT)),
                             "sha256": _sha256(src),
                             "rows": len(census_rows)}
        first_only = [r for r in census_rows if r.get("is_first_touch") == "True"]
        manifest[tf_name]["first_only"] = len(first_only)
        manifest[tf_name]["refires_side_count"] = (
            len(census_rows) - len(first_only))
        bars = S[tf_name]["bars"]
        keys = S[tf_name]["keys"]
        atr = S[tf_name]["atr"]
        m5bars = S["M5"]["bars"]
        m5keys = S["M5"]["keys"]
        m5atr = S["M5"]["atr"]
        trunc = 0
        for r in first_only:
            idx = keys.get((r.get("bar_ts") or "")[:16].replace("T", " "))
            if idx is None:
                continue  # bar outside loaded series (counted below)
            level = float(r["level"])
            short_cont, _ = continuation_signs(r["pool"])
            row = {"event_id": r["event_id"], "tf": tf_name,
                   "bar_ts": r["bar_ts"], "pool": r["pool"],
                   "direction_bias": r["direction_bias"],
                   "level_family": r["level_family"], "level": level,
                   "atr_at_sweep": atr[idx] if idx < len(atr) else None}
            truncated: list[str] = []
            for h in HORIZONS:
                col = f"h{h}_"
                if len(bars) - 1 < idx + h:
                    trunc += 1
                    for c in H_COLS:
                        row[col + c] = None
                    truncated.append(f"H{h}")
                    continue
                m = path_metrics(bars, idx + 1, idx + h, level=level,
                                 is_short_cont=short_cont, atr=atr[idx])
                for c in H_COLS:
                    row[col + c] = m[c]
            # Secondary M5-translated horizon (labeled secondary).
            mkey = (r.get("bar_ts") or "")[:16].replace("T", " ")
            midx = m5keys.get(mkey)
            mh = M5_SECONDARY[tf_name]
            if midx is None or len(m5bars) - 1 < midx + mh:
                trunc += 1
                for c in H_COLS:
                    row["m5sec_" + c] = None
                truncated.append("M5sec")
            else:
                m = path_metrics(m5bars, midx + 1, midx + mh, level=level,
                                 is_short_cont=short_cont, atr=m5atr[midx])
                for c in H_COLS:
                    row["m5sec_" + c] = m[c]
            row["truncated_horizons"] = ";".join(truncated)
            row["note"] = ""
            all_rows.append(row)
        manifest[tf_name]["unresolvable_bars"] = (
            len(first_only) - sum(1 for r in all_rows
                                  if r["tf"] == tf_name))
        print(f"[path] {tf_name}: first-only={len(first_only)} "
              f"truncated_reads={trunc}", flush=True)

    out_csv = OUT_DIR / "sweeps_path.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in all_rows:
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

    def cell(sub, col):
        n = len(sub)
        hits = sum(1 for r in sub if r[col + "hit_plus1atr"] is True)
        denom = sum(1 for r in sub if r[col + "hit_plus1atr"] is not None)
        lo, hi = wilson(hits, denom)
        return {
            "n": n,
            "hit_plus1atr_rate": (round(hits / denom, 4) if denom else None),
            "hit_plus1atr_ci95": ([round(lo, 4), round(hi, 4)]
                                  if lo is not None else None),
            "hit_plus2atr_rate": (round(sum(
                1 for r in sub if r[col + "hit_plus2atr"] is True) / denom, 4)
                if denom else None),
            "median_mfe_atr": _median([r[col + "mfe_atr"] for r in sub]),
            "median_mae_atr": _median([r[col + "mae_atr"] for r in sub]),
            "adverse_1atr_rate": (round(sum(
                1 for r in sub if r[col + "adverse_1atr"] is True) / denom, 4)
                if denom else None),
            "reclaim_fail_rate": (round(sum(
                1 for r in sub if r[col + "reclaim_fail"] is True) / denom, 4)
                if denom else None),
            "median_time_to_mfe": _median(
                [r[col + "time_to_mfe_bars"] for r in sub]),
            "median_time_to_mae": _median(
                [r[col + "time_to_mae_bars"] for r in sub]),
        }

    tables: dict[str, dict] = {}
    for tf_name in ("H4", "H1"):
        pool = [r for r in all_rows if r["tf"] == tf_name]
        tables[tf_name] = {}
        fams = sorted({r["level_family"] for r in pool})
        for fam in fams:
            tables[tf_name][fam] = {}
            sub = [r for r in pool if r["level_family"] == fam]
            for h in list(HORIZONS) + ["m5sec"]:
                prefix = "m5sec_" if h == "m5sec" else f"h{h}_"
                tables[tf_name][fam][f"h{h}"] = cell(sub, prefix)
        tables[tf_name]["_n_first"] = len(pool)

    struct = {}
    for tf_name in ("H4", "H1"):
        sub = [r for r in all_rows
               if r["tf"] == tf_name and r["level_family"] == "structural_swing"]
        struct[tf_name] = {"n": len(sub)}
        for h in list(HORIZONS) + ["m5sec"]:
            prefix = "m5sec_" if h == "m5sec" else f"h{h}_"
            struct[tf_name][f"h{h}"] = cell(sub, prefix)

    summary = {
        "banner": BANNER,
        "frozen": {
            "sample": ("unique level + first sweep only in exec window "
                       "(census is_first_touch); re-fires side counts only"),
            "horizons_tf_bars": list(HORIZONS),
            "horizon_rule": ("window = sweep_idx+1 .. sweep_idx+H "
                             "(exclusive of sweep bar); strict truncation"),
            "m5_secondary": (f"H4->{M5_SECONDARY['H4']} M5 bars, "
                             f"H1->{M5_SECONDARY['H1']} M5 bars "
                             "(~0.4 native bars — shorter lens)"),
            "reference": ("swept level extreme in sweep direction "
                          "(BSL: level-lows; SSL: highs-level)"),
            "numeraires": ("ATR(14) Wilder SMA-seeded on the series being "
                           "read, at the sweep bar; no R, no invented stops"),
            "reclaim_fail": ("first bar in window closing back beyond the "
                             "level against the sweep close "
                             "(BSL: close>level; SSL: close<level)"),
            "continuation": "BSL -> downside; SSL -> upside (reporting)",
        },
        "inputs_manifest": manifest,
        "side_counts": {
            tf: {"total_events": manifest[tf]["rows"],
                 "first_only": manifest[tf]["first_only"],
                 "refires": manifest[tf]["refires_side_count"]}
            for tf in ("H4", "H1")},
        "tables_by_tf_family": tables,
        "structural_only": struct,
        "limitations": [
            "Direction is pool-reported bias, not a trade signal.",
            "Reference is the swept extreme (not the sweep close); "
            "intrabar path inside the sweep bar itself is not measured.",
            "M5-secondary horizons are sub-native-bar lenses (~0.4 TF "
            "bars) — texture only.",
            "Single 6m window, single feed; no gate, no threshold, no "
            "live rule follows (see report).",
        ],
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[path] rows={len(all_rows)} wrote {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
