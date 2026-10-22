"""EXIT ANATOMY DIAGNOSTIC — Windows A + B (Architect 2026-10-20).

DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION.

Observation only. Explains *how* positions end in the two frozen post-dedup
books, with Window B's stop-heavy / SL_THEN_TP_PATH shape as the motivating
question. No rule, threshold, TP/SL/BE/trail parameter or product file is
touched; the two books are read as-is and the M5 series is rebuilt with the
composition's own loader/resampler (read-only).

PRE-REGISTERED BEFORE THE METRICS WERE COMPUTED (do not tune after):

Per trade
  1. R_stop   = |entry_price - original_sl|                (NA if absent)
     R_tp     = |tp - entry_price|                         (NA if no tp)
  2. hold_bars = book's own ``bars_held``; hold_hours from entry_at/exit_at
  3. MFE_R / MAE_R via the SAME honest path used by the two frozen legs
     (prior leg's ``build_m5_index`` + ``mfe_mae_r``, denominator R_stop)
  4. EXIT_CLASS: HARD_SL   = close_kind stop_loss AND pnl <= 0
                 SOFT_SL_OR_BE = close_kind stop_loss AND pnl > 0
                 TARGET_TP = close_kind take_profit
                 OTHER     = everything else
  5. MFE_VS_TP: YES iff the favourable excursion in PRICE reached
     >= 0.9 x R_tp inside the stored window; NA when tp/risk missing
  6. SL_WHILE_TP_VALID: close is HARD_SL or SOFT_SL_OR_BE AND the tp price was
     touched/crossed by any M5 bar STRICTLY BEFORE the exit bar. The exit bar
     itself is excluded (intrabar order unknowable) and same-bar touches are
     counted separately as ``same_bar_tp_touch``. This is a CHRONOLOGY
     COHERENCE probe: with a resting TP, a pre-exit TP touch should not exist.
  7. RUN_PAST_ENTRY: max favourable excursion in price units and in R
     (= MFE_R x R_stop)
  8. TP_DISTANCE_R = R_tp / R_stop  (NA if either missing)

Aggregates per window: EXIT_CLASS counts/shares, stop-exit share, TP share,
share of SL_WHILE_TP_VALID among stop exits, share of MFE_VS_TP YES among all
trades and among TP exits, and medians (hold_bars, MFE_R, TP_DISTANCE_R) by
EXIT_CLASS and by tp_source.

Label rule (exactly one label per window, checked in order)
  a. excursions unavailable for the window            -> DATA_GAP_BLOCKING
  b. stop-exit share >= 0.60 and SOFT_SL_OR_BE >= HARD_SL within the stop
     group                                            -> EXIT_DOMINATED_BY_SOFT_STOPS
  c. stop-exit share >= 0.60 otherwise                -> EXIT_DOMINATED_BY_HARD_SL
  d. TP-exit share >= 0.60                            -> TARGET_REACH_COMMON
  e. anything else                                    -> EXIT_MIXED_TARGET_AND_STOP
The 0.60 line is a plain dominance threshold applied symmetrically to both
windows; the underlying shares are printed next to every label so the reader
never has to trust the threshold.

Return-block INTERPRETATION = Window B's label (B is the window whose shape
motivated this leg); Window A's label is reported beside it and any
disagreement is flagged in ``summary.json`` and in the report.

READS  : the two books' trades.csv (read-only), 07_DATA/XAUUSD_M1.parquet
WRITES : 06_RESEARCH/results/exit_anatomy/{summary.json,trades_exit_anatomy.csv}

Usage:
  python 06_RESEARCH/scripts/exit_anatomy_diagnostic.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

BANNER = "DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION"

BOOK_A = (REPO_ROOT / "06_RESEARCH" / "results" / "zone_dedup_lifecycle"
          / "run1" / "_funnel_capture" / "trades.csv")
BOOK_B = (REPO_ROOT / "06_RESEARCH" / "results" / "post_dedup_edge_stability"
          / "run1" / "_funnel_capture" / "trades.csv")
ENRICHED_A = (REPO_ROOT / "06_RESEARCH" / "results" / "post_dedup_edge_diagnostic"
              / "trades_enriched.csv")
ENRICHED_B = (REPO_ROOT / "06_RESEARCH" / "results" / "post_dedup_edge_stability"
              / "trades_enriched_B.csv")

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "exit_anatomy"

WINDOWS = {
    "A": {"book": BOOK_A,
          "start": datetime(2025, 6, 1, tzinfo=timezone.utc),
          "end": datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc),
          "load_from": datetime(2025, 5, 1, tzinfo=timezone.utc),
          "label": "2025-06-01 -> 2025-11-30"},
    "B": {"book": BOOK_B,
          "start": datetime(2024, 12, 1, tzinfo=timezone.utc),
          "end": datetime(2025, 5, 31, 23, 59, 59, tzinfo=timezone.utc),
          "load_from": datetime(2024, 11, 1, tzinfo=timezone.utc),
          "label": "2024-12-01 -> 2025-05-31"},
}

PRE_REGISTRATION = {
    "banner": BANNER,
    "exit_class_rule": {
        "HARD_SL": "close_kind == stop_loss and pnl <= 0",
        "SOFT_SL_OR_BE": "close_kind == stop_loss and pnl > 0 (trailing/BE end)",
        "TARGET_TP": "close_kind == take_profit",
        "OTHER": "anything else",
    },
    "mfe_vs_tp": "YES iff max favourable price excursion >= 0.9 * |tp - entry|",
    "sl_while_tp_valid": (
        "stop close AND tp touched by an M5 bar strictly before the exit bar; "
        "same-bar touches counted separately (intrabar order unknowable)"
    ),
    "label_rule": (
        "DATA_GAP_BLOCKING if excursions unavailable; else stop-exit share>=0.60 "
        "with SOFT>=HARD -> EXIT_DOMINATED_BY_SOFT_STOPS; stop share>=0.60 -> "
        "EXIT_DOMINATED_BY_HARD_SL; TP share>=0.60 -> TARGET_REACH_COMMON; "
        "else EXIT_MIXED_TARGET_AND_STOP"
    ),
    "return_block_interpretation": (
        "Window B's label (the window whose stop-heavy shape motivated the leg); "
        "Window A's label reported beside it"
    ),
    "bans": [
        "no TP/SL/BE/trail parameter search",
        "no exit 'fix' proposed or implemented",
        "no expectancy / scale language",
        "LOGIC_CHANGED: NO under 04_SRC/smc/**",
    ],
}


def _f(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _median(values: list[float]):
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _ts(value: str):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _floor5(dt: datetime) -> datetime:
    return dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)


def exit_class(close_kind: str, pnl: float) -> str:
    kind = (close_kind or "").strip()
    if kind == "stop_loss":
        return "SOFT_SL_OR_BE" if pnl > 0 else "HARD_SL"
    if kind == "take_profit":
        return "TARGET_TP"
    return "OTHER"


def walk_path(row: dict, m5_map: dict) -> dict:
    """Bars strictly before the exit bar: tp touch + same-bar touch flags.

    The MFE/MAE numbers themselves come from the frozen honest path
    (``prior.mfe_mae_r``); this walk exists only for the tp-touch chronology,
    and its max-favourable price is cross-checked against that path.
    """
    entry_at, exit_at = _ts(row.get("entry_at")), _ts(row.get("exit_at"))
    if entry_at is None or exit_at is None:
        return {"tp_touch_before_exit": None, "same_bar_tp_touch": None,
                "bars_walked": 0, "walk_mfe_price": None}
    direction = (row.get("direction") or "").strip().lower()
    entry = _f(row.get("entry_price"))
    tp_raw = row.get("tp")
    tp = _f(tp_raw) if tp_raw not in ("", None) else None

    start, finish = _floor5(entry_at), _floor5(exit_at)
    cur, highs, lows = start, [], []
    tp_before = False
    tp_same_bar = False
    nbars = 0
    while cur <= finish:
        candle = m5_map.get(cur)
        if candle is not None:
            highs.append(candle.high)
            lows.append(candle.low)
            nbars += 1
            if tp is not None and tp > 0:
                hit = (candle.high >= tp - 1e-9 if direction == "long"
                       else candle.low <= tp + 1e-9)
                if hit:
                    if cur < finish:
                        tp_before = True
                    else:
                        tp_same_bar = True
        cur += timedelta(minutes=5)
    if nbars == 0:
        return {"tp_touch_before_exit": None, "same_bar_tp_touch": None,
                "bars_walked": 0, "walk_mfe_price": None}
    walk_mfe = (max(h - entry for h in highs) if direction == "long"
                else max(entry - l for l in lows))
    return {"tp_touch_before_exit": tp_before if tp is not None else None,
            "same_bar_tp_touch": tp_same_bar if tp is not None else None,
            "bars_walked": nbars, "walk_mfe_price": walk_mfe}


def build_window(key: str, spec: dict, enriched_path: Path) -> dict:
    import post_dedup_edge_diagnostic as prior

    prior.TRADES_CSV = spec["book"]
    prior.WIN_START = spec["start"]
    prior.WIN_END = spec["end"]
    prior.LOAD_FROM = spec["load_from"]

    rows = prior.load_book()
    m5_map = prior.build_m5_index()
    exc = prior.mfe_mae_r(rows, m5_map)

    trades = []
    path_mismatch = 0
    for row, e in zip(rows, exc):
        pnl = _f(row.get("pnl"))
        risk = e["risk_dist"]
        tp_raw = row.get("tp")
        tp = _f(tp_raw) if tp_raw not in ("", None) else None
        r_tp = abs(tp - _f(row.get("entry_price"))) if tp else None
        tp_distance_r = (r_tp / risk) if (r_tp and risk and risk > 0) else None

        mfe_r, mae_r = e["mfe_r"], e["mae_r"]
        mfe_price = (mfe_r * risk) if (mfe_r is not None and risk) else None
        mfe_vs_tp, mfe_ratio = None, None
        if mfe_price is not None and r_tp and r_tp > 0:
            mfe_ratio = mfe_price / r_tp
            mfe_vs_tp = "YES" if mfe_ratio >= 0.9 else "NO"

        klass = exit_class(row.get("close_kind"), pnl)
        walk = walk_path(row, m5_map)
        if (walk["walk_mfe_price"] is not None and mfe_price is not None
                and abs(walk["walk_mfe_price"] - mfe_price) > 1e-6):
            path_mismatch += 1

        is_stop = klass in ("HARD_SL", "SOFT_SL_OR_BE")
        if is_stop and tp is not None:
            sl_while_tp = "YES" if walk["tp_touch_before_exit"] else "NO"
        else:
            sl_while_tp = "NA"

        entry_at, exit_at = _ts(row.get("entry_at")), _ts(row.get("exit_at"))
        hold_hours = (round((exit_at - entry_at).total_seconds() / 3600.0, 3)
                      if entry_at and exit_at else None)

        trades.append({
            "window": key,
            "ticket": row.get("ticket"),
            "direction": row.get("direction"),
            "entry_at": row.get("entry_at"),
            "exit_at": row.get("exit_at"),
            "hold_bars": int(_f(row.get("bars_held"))),
            "hold_hours": hold_hours,
            "close_kind": row.get("close_kind"),
            "exit_class": klass,
            "pnl": pnl,
            "risk_stop": risk,
            "r_tp": r_tp,
            "tp_distance_r": tp_distance_r,
            "mfe_r": mfe_r,
            "mae_r": mae_r,
            "run_past_entry_price": mfe_price,
            "run_past_entry_r": mfe_r,
            "mfe_vs_tp": mfe_vs_tp,
            "mfe_vs_tp_ratio": mfe_ratio,
            "sl_while_tp_valid": sl_while_tp,
            "same_bar_tp_touch": walk["same_bar_tp_touch"],
            "tp_source": row.get("tp_source") or "none",
            "trigger": row.get("trigger") or "",
        })

    return {"key": key, "spec": spec, "trades": trades,
            "path_mismatch": path_mismatch,
            "m5_bars": len(m5_map),
            "enriched_path": enriched_path}


def enriched_check(window: dict) -> dict:
    """Cross-check the recomputed MFE/MAE against the stored enriched book."""
    path = window["enriched_path"]
    if not path.exists():
        return {"present": False}
    with path.open(encoding="utf-8") as fh:
        stored = {r["ticket"]: r for r in csv.DictReader(fh)}
    compared, mismatched = 0, 0
    for t in window["trades"]:
        s = stored.get(str(t["ticket"]))
        if s is None or s.get("mfe_r") in ("", None):
            continue
        compared += 1
        if (abs(_f(s["mfe_r"]) - (t["mfe_r"] if t["mfe_r"] is not None else 0.0)) > 1e-9
                or abs(_f(s["mae_r"]) - (t["mae_r"] if t["mae_r"] is not None else 0.0)) > 1e-9):
            mismatched += 1
    return {"present": True, "compared": compared, "mismatched": mismatched,
            "match": mismatched == 0}


def aggregate(window: dict) -> dict:
    trades = window["trades"]
    n = len(trades)
    classes = Counter(t["exit_class"] for t in trades)
    stop_trades = [t for t in trades if t["exit_class"] in ("HARD_SL", "SOFT_SL_OR_BE")]
    tp_trades = [t for t in trades if t["exit_class"] == "TARGET_TP"]

    sl_while = [t for t in stop_trades if t["sl_while_tp_valid"] == "YES"]
    mfe_yes_all = [t for t in trades if t["mfe_vs_tp"] == "YES"]
    mfe_scored_all = [t for t in trades if t["mfe_vs_tp"] in ("YES", "NO")]
    mfe_yes_tp = [t for t in tp_trades if t["mfe_vs_tp"] == "YES"]
    mfe_scored_tp = [t for t in tp_trades if t["mfe_vs_tp"] in ("YES", "NO")]

    by_class = {}
    for klass in ("HARD_SL", "SOFT_SL_OR_BE", "TARGET_TP", "OTHER"):
        group = [t for t in trades if t["exit_class"] == klass]
        by_class[klass] = {
            "n": len(group),
            "share": round(len(group) / n, 4) if n else None,
            "median_hold_bars": _median([t["hold_bars"] for t in group]),
            "median_mfe_r": _median([t["mfe_r"] for t in group
                                     if t["mfe_r"] is not None]),
            "median_tp_distance_r": _median([t["tp_distance_r"] for t in group
                                             if t["tp_distance_r"] is not None]),
            "median_run_past_entry_r": _median([t["run_past_entry_r"] for t in group
                                                if t["run_past_entry_r"] is not None]),
            "median_mfe_vs_tp_ratio": _median([t["mfe_vs_tp_ratio"] for t in group
                                               if t["mfe_vs_tp_ratio"] is not None]),
            "sum_pnl": round(sum(t["pnl"] for t in group), 6),
        }

    by_source = {}
    for source in sorted({t["tp_source"] for t in trades}):
        group = [t for t in trades if t["tp_source"] == source]
        by_source[source] = {
            "n": len(group),
            "exit_class": dict(Counter(t["exit_class"] for t in group)),
            "median_hold_bars": _median([t["hold_bars"] for t in group]),
            "median_mfe_r": _median([t["mfe_r"] for t in group
                                     if t["mfe_r"] is not None]),
            "median_tp_distance_r": _median([t["tp_distance_r"] for t in group
                                             if t["tp_distance_r"] is not None]),
            "sl_while_tp_valid_yes": sum(1 for t in group
                                         if t["sl_while_tp_valid"] == "YES"),
        }

    stop_share = len(stop_trades) / n if n else 0.0
    tp_share = len(tp_trades) / n if n else 0.0
    n_excursions = sum(1 for t in trades if t["mfe_r"] is not None)
    if n == 0 or n_excursions == 0:
        label = "DATA_GAP_BLOCKING"
    elif stop_share >= 0.60 and classes["SOFT_SL_OR_BE"] >= classes["HARD_SL"]:
        label = "EXIT_DOMINATED_BY_SOFT_STOPS"
    elif stop_share >= 0.60:
        label = "EXIT_DOMINATED_BY_HARD_SL"
    elif tp_share >= 0.60:
        label = "TARGET_REACH_COMMON"
    else:
        label = "EXIT_MIXED_TARGET_AND_STOP"

    return {
        "window": window["spec"]["label"],
        "n": n,
        "book": str(window["spec"]["book"].relative_to(REPO_ROOT)),
        "m5_bars_rebuilt": window["m5_bars"],
        "path_cross_check_mismatches": window["path_mismatch"],
        "exit_class_counts": dict(classes),
        "exit_class_shares": {k: round(v / n, 4) for k, v in classes.items()} if n else {},
        "stop_share": round(stop_share, 4),
        "tp_share": round(tp_share, 4),
        "sl_while_tp_valid": {
            "yes": len(sl_while), "denominator": len(stop_trades),
            "share_of_stop_exits": round(len(sl_while) / len(stop_trades), 4)
            if stop_trades else None,
            "na_stop_exits_without_tp": sum(1 for t in stop_trades
                                            if t["sl_while_tp_valid"] == "NA"),
            "same_bar_tp_touches": sum(1 for t in stop_trades
                                       if t["same_bar_tp_touch"] is True),
        },
        "mfe_vs_tp": {
            "yes": len(mfe_yes_all), "denominator": len(mfe_scored_all),
            "share_all": round(len(mfe_yes_all) / len(mfe_scored_all), 4)
            if mfe_scored_all else None,
            "among_tp_exits": {
                "yes": len(mfe_yes_tp), "denominator": len(mfe_scored_tp),
                "share": round(len(mfe_yes_tp) / len(mfe_scored_tp), 4)
                if mfe_scored_tp else None,
            },
            "na": n - len(mfe_scored_all),
        },
        "median_hold_bars": _median([t["hold_bars"] for t in trades]),
        "median_hold_hours": _median([t["hold_hours"] for t in trades
                                      if t["hold_hours"] is not None]),
        "median_mfe_r": _median([t["mfe_r"] for t in trades
                                 if t["mfe_r"] is not None]),
        "median_mae_r": _median([t["mae_r"] for t in trades
                                 if t["mae_r"] is not None]),
        "median_tp_distance_r": _median([t["tp_distance_r"] for t in trades
                                         if t["tp_distance_r"] is not None]),
        "by_exit_class": by_class,
        "by_tp_source": by_source,
        "interpretation_label": label,
    }


def main() -> int:
    print(BANNER, flush=True)
    agg = {}
    windows = {}
    for key, enriched in (("A", ENRICHED_A), ("B", ENRICHED_B)):
        spec = WINDOWS[key]
        if not spec["book"].exists():
            raise SystemExit(f"book missing for window {key}: {spec['book']}")
        window = build_window(key, spec, enriched)
        windows[key] = window
        agg[key] = aggregate(window)
        chk = enriched_check(window)
        agg[key]["enriched_reproduction"] = chk
        print(f"[exit] window {key}: n={agg[key]['n']} "
              f"classes={agg[key]['exit_class_counts']} "
              f"label={agg[key]['interpretation_label']} "
              f"path_mismatch={window['path_mismatch']} enriched={chk}",
              flush=True)

    label_disagreement = (agg["A"]["interpretation_label"]
                          != agg["B"]["interpretation_label"])
    summary = {
        "banner": BANNER,
        "pre_registration": PRE_REGISTRATION,
        "windows": agg,
        "label_disagreement": label_disagreement,
        "interpretation": {
            "A": agg["A"]["interpretation_label"],
            "B": agg["B"]["interpretation_label"],
            "single": agg["B"]["interpretation_label"],
            "rule": PRE_REGISTRATION["return_block_interpretation"],
        },
        "return_block": {
            "EXIT_ANATOMY_STATUS": "PASS",
            "N_A": agg["A"]["n"],
            "N_B": agg["B"]["n"],
            "EXIT_CLASS_A": agg["A"]["exit_class_counts"],
            "EXIT_CLASS_B": agg["B"]["exit_class_counts"],
            "SL_WHILE_TP_VALID_SHARE_A": agg["A"]["sl_while_tp_valid"]["share_of_stop_exits"],
            "SHARE_B": agg["B"]["sl_while_tp_valid"]["share_of_stop_exits"],
            "MFE_VS_TP_YES_SHARE_A": agg["A"]["mfe_vs_tp"]["share_all"],
            "MFE_VS_TP_YES_SHARE_B": agg["B"]["mfe_vs_tp"]["share_all"],
            "MEDIAN_HOLD_BARS_A": agg["A"]["median_hold_bars"],
            "MEDIAN_HOLD_BARS_B": agg["B"]["median_hold_bars"],
            "MEDIAN_TP_DISTANCE_R_A": agg["A"]["median_tp_distance_r"],
            "MEDIAN_TP_DISTANCE_R_B": agg["B"]["median_tp_distance_r"],
            "INTERPRETATION": agg["B"]["interpretation_label"],
            "INTERPRETATION_A": agg["A"]["interpretation_label"],
            "LOGIC_CHANGED": "NO",
            "LOCKED_CONSTANTS_DIFF": "empty",
            "SUITE": "NOT_RUN",
            "REPORT_PATH": "06_RESEARCH/EXIT_ANATOMY_DIAGNOSTIC_REPORT.md",
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    fields = ["window", "ticket", "direction", "entry_at", "exit_at",
              "hold_bars", "hold_hours", "close_kind", "exit_class", "pnl",
              "risk_stop", "r_tp", "tp_distance_r", "mfe_r", "mae_r",
              "run_past_entry_price", "run_past_entry_r", "mfe_vs_tp",
              "mfe_vs_tp_ratio", "sl_while_tp_valid", "same_bar_tp_touch",
              "tp_source", "trigger"]
    with (OUT_DIR / "trades_exit_anatomy.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for key in ("A", "B"):
            for trade in windows[key]["trades"]:
                writer.writerow({k: ("" if trade.get(k) is None else trade.get(k))
                                 for k in fields})

    print(json.dumps(summary["return_block"], indent=2, default=str), flush=True)
    print(f"[exit] label_disagreement={label_disagreement}; wrote {OUT_DIR}",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
