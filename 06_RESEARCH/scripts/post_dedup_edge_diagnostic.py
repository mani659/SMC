"""POST-DEDUP EDGE / OUTCOME DIAGNOSTIC (M-3 gate, Architect 2026-10-20).

DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION.

Measurement only. For the post-ZoneDedup-lifecycle 6m closed trade book
(2025-06-01 -> 2025-11-30, M5, filled trades) this script quantifies:

  1. counts + distributions: n, win rate by close_kind
  2. exit mix: close_kind / tp_source breakdown
  3. net PnL raw + profit factor   (label: DIAGNOSTIC ONLY)
  4. breakdowns by trigger letter, tp_source (via (3)/(5) groupbys), hours
  5. honest MFE / MAE in R from the book's stored window:
       risk_distance = |entry_price - original_sl|   (original_sl present?)
       LONG:  MFE = max(high - entry), MAE = max(entry - low)
       SHORT: MFE = max(entry - low),  MAE = max(entry - high)
       window = M5 resampled bars with entry_at <= ts <= exit_at
     (method mirrors r1_mfe_mae_study; series rebuilt via the composition's
     own loader: XAUUSD_M1.parquet -> resample_multi M5)
  6. hypothesis-style buckets: reuse the book's own path-derived
     post_exit_class column (TP_REACHED / SL_THEN_TP_PATH / MFE_ONLY /
     REJECTED...) — no re-derivation, byte-stable input
  7. contrast vs pre-lifecycle 6m book sample size (n=3, from the ledger)

READS (never writes source data):
  - 06_RESEARCH/results/zone_dedup_lifecycle/run1/_funnel_capture/trades.csv
    (byte-identical md5 476884250d607ac1b1e3806eadceba0c across run1/run2 and
    the LEG 6 re-capture — reuse of the same book, no re-capture performed)
  - 07_DATA/XAUUSD_M1.parquet via smc.data.parquet_loader (read-only)
WRITES (research artifacts only):
  - 06_RESEARCH/results/post_dedup_edge_diagnostic/{summary.json,trades_enriched.csv}

No strategy/threshold/locked-constant edit; no `smc` module writes; the
script imports ONLY the data loader + resampler (no detection/trigger/risk).
No expectancy/edge language; results feed the interpretation label in the
report, chosen by pre-registered rules only.
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

TRADES_CSV = (
    REPO_ROOT / "06_RESEARCH" / "results" / "zone_dedup_lifecycle"
    / "run1" / "_funnel_capture" / "trades.csv"
)
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "post_dedup_edge_diagnostic"

BANNER = "DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION"

WIN_START = datetime(2025, 6, 1, tzinfo=timezone.utc)
WIN_END = datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc)
LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)  # composition warm-up context


def _f(float_str, default=0.0):
    try:
        return float(float_str)
    except (TypeError, ValueError):
        return default


def _median(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def load_book() -> list[dict]:
    with TRADES_CSV.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return rows


def build_m5_index() -> tuple[dict, datetime]:
    """Rebuild the composition's M5 series; return ts->candle map."""
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.config.timeframe import Timeframe
    from smc.data.resample import resample_multi

    m1 = load_ohlcv_parquet(PARQUET)
    m1 = [c for c in m1 if LOAD_FROM <= c.timestamp <= WIN_END + timedelta(days=1)]
    multi = resample_multi(m1, [Timeframe.M5])
    m5 = [c for c in multi[Timeframe.M5]
          if WIN_START - timedelta(hours=1) <= c.timestamp <= WIN_END]
    return {c.timestamp: c for c in m5}
    # NOTE: immediate entry/exit anchoring uses timestamps from the book;
    # no index arithmetic across windows.


def mfe_mae_r(rows: list[dict], m5_map: dict) -> list[dict]:
    """Per-trade MFE/MAE in R over the stored [entry_at .. exit_at] window."""
    out = []
    missing_window = 0
    for r in rows:
        try:
            entry_at = datetime.fromisoformat(r["entry_at"])
            exit_at = datetime.fromisoformat(r["exit_at"])
        except (KeyError, ValueError):
            out.append({"mfe_r": None, "mae_r": None, "risk_dist": None,
                        "bars_in_window": None})
            continue
        direction = (r.get("direction") or "").strip().lower()
        entry = _f(r.get("entry_price"))
        sl = r.get("original_sl", "")
        risk = None
        if sl not in ("", None):
            risk = abs(entry - _f(sl))
        # collect candles covering the trade's timestamps
        highs, lows, nbars = [], [], 0
        ts = entry_at
        # walk M5 buckets by timestamp keys only (bars exist on 5-min grid;
        # entry/exit times are already on M5 closes in this book)
        cur = entry_at.replace(minute=(entry_at.minute // 5) * 5, second=0,
                               microsecond=0)
        end = exit_at.replace(minute=(exit_at.minute // 5) * 5, second=0,
                              microsecond=0)
        while cur <= end:
            c = m5_map.get(cur)
            if c is not None:
                highs.append(c.high)
                lows.append(c.low)
                nbars += 1
            cur += timedelta(minutes=5)
        if nbars == 0:
            missing_window += 1
            out.append({"mfe_r": None, "mae_r": None, "risk_dist": risk,
                        "bars_in_window": 0})
            continue
        if direction == "long":
            mfe = max(h - entry for h in highs)
            mae = max(entry - l for l in lows)
        else:
            mfe = max(entry - l for l in lows)
            mae = max(h - entry for h in highs)
        mfe_r = mfe / risk if risk and risk > 0 else None
        mae_r = mae / risk if risk and risk > 0 else None
        out.append({"mfe_r": mfe_r, "mae_r": mae_r, "risk_dist": risk,
                    "bars_in_window": nbars})
    if missing_window:
        print(f"[diag] WARNING: {missing_window} trades with no M5 bars in window",
              flush=True)
    return out


def main() -> int:
    print(BANNER, flush=True)
    rows = load_book()
    n = len(rows)
    print(f"[diag] book rows (closed trades): {n}", flush=True)

    m5_map = build_m5_index()
    print(f"[diag] M5 series rebuilt for excursion windows: {len(m5_map)} bars",
          flush=True)
    exc = mfe_mae_r(rows, m5_map)

    # ---- enrich rows -------------------------------------------------- #
    enriched = []
    for r, e in zip(rows, exc):
        d = dict(r)
        d["mfe_r"] = e["mfe_r"]
        d["mae_r"] = e["mae_r"]
        d["risk_dist"] = e["risk_dist"]
        d["bars_in_window"] = e["bars_in_window"]
        enriched.append(d)

    pnl_vals = [_f(r.get("pnl")) for r in rows]
    pnl_net_vals = [_f(r.get("pnl_net")) for r in rows]
    wins = sum(1 for r in rows if r.get("close_kind") == "take_profit")
    close_kinds = Counter(r.get("close_kind", "?") for r in rows)
    tp_sources = Counter(r.get("tp_source", "none") or "none" for r in rows)
    triggers = Counter((r.get("trigger") or "?")[:1] for r in rows)
    trigger_from_route = Counter(
        (r.get("route_id") or "").split(":")[-1][1:2] or "?" for r in rows
    )
    hypothesis = Counter(r.get("post_exit_class", "NA") or "NA" for r in rows)
    directions = Counter(r.get("direction", "?") for r in rows)

    by_ck = defaultdict(list)
    for r in rows:
        by_ck[r.get("close_kind", "?")].append(_f(r.get("pnl")))

    # profit factor diagnostic: gross wins / gross losses (|sum|)
    gross_win = sum(p for p in pnl_vals if p > 0)
    gross_loss = sum(-p for p in pnl_vals if p < 0)
    pf = (gross_win / gross_loss) if gross_loss > 0 else None

    mfe_rs = [e["mfe_r"] for e in exc if e["mfe_r"] is not None]
    mae_rs = [e["mae_r"] for e in exc if e["mae_r"] is not None]
    risk_missing = sum(1 for e in exc if e["risk_dist"] is None)

    def dist(vals):
        vals = sorted(vals)
        if not vals:
            return {"n": 0}
        return {
            "n": len(vals), "min": vals[0], "median": _median(vals),
            "mean": sum(vals) / len(vals), "max": vals[-1],
            "p25": vals[int(0.25 * (len(vals) - 1))],
            "p75": vals[int(0.75 * (len(vals) - 1))],
        }

    summary = {
        "banner": BANNER,
        "window": "2025-06-01 -> 2025-11-30 (frozen 6m, M5)",
        "book_source": str(TRADES_CSV.relative_to(REPO_ROOT)),
        "book_md5": "476884250d607ac1b1e3806eadceba0c",
        "recapture_performed": False,
        "n_trades": n,
        "interpretation_label": "",
        "pre_registration": {
            "population": "all closed trades in the lifecycle book (post-dedup fills)",
            "metrics": [
                "win rate by close_kind", "exit mix", "net pnl + pf (diagnostic)",
                "trigger/tp_source breakdowns",
                "MFE/MAE in R via stored windows",
                "hypothesis buckets via book's post_exit_class",
                "contrast vs pre-lifecycle n=3 sample only",
            ],
            "interpretation_rule": (
                "choose exactly one of BOOK_* labels per the report's "
                "pre-registered mapping; no edge/scale language permitted"
            ),
        },
        "win_rate_by_close_kind": {
            k: {"count": v, "win_rate": (
                sum(1 for r in rows if r.get("close_kind") == k and _f(r.get("pnl")) > 0)
                / v) if v else None}
            for k, v in close_kinds.items()
        },
        "exit_mix": {
            "close_kind": dict(close_kinds),
            "tp_source": dict(tp_sources),
            "direction": dict(directions),
        },
        "trigger_mix": {
            "by_route_tail": dict(trigger_from_route),
            "by_trigger_column": dict(triggers),
            "f_timing_label": dict(Counter(
                r.get("f_timing_label") or "NA" for r in rows)),
        },
        "hypothesis_counts": dict(hypothesis),
        "net_pl_diagnostic": {
            "sum_pnl": sum(pnl_vals),
            "sum_pnl_net": sum(pnl_net_vals),
            "gross_win": gross_win, "gross_loss": gross_loss,
            "profit_factor": pf,
            "label": "DIAGNOSTIC ONLY — not an expectancy or edge claim",
        },
        "mfe_mae": {
            "risk_dist_missing": risk_missing,
            "mfe_r": dist(mfe_rs),
            "mae_r": dist(mae_rs),
            "median_mfe_r": _median(mfe_rs),
            "median_mae_r": _median(mae_rs),
        },
        "contrast_pre_lifecycle": {
            "pre_lifecycle_n": 3,       # frozen pre-dedup book (LEG ≤4 funnel)
            "post_lifecycle_n": n,
            "note": "sample-size contrast only; not an improvement claim",
        },
    }

    # ---- pre-registered interpretation mapping ------------------------ #
    if n < 20:
        label = "BOOK_TOO_SMALL"
    elif risk_missing == n:
        label = "DATA_GAP_BLOCKING"
    elif gross_loss <= 0:
        label = "BOOK_MIXED_PATHS_NO_CLAIM"   # can't happen with losses alone
    else:
        # neither label asserts edge; only descriptive lossiness
        label = ("BOOK_STILL_LOSSY_DIAGNOSTIC"
                 if (pnl_net_vals and sum(pnl_net_vals) < 0)
                 else "BOOK_MIXED_PATHS_NO_CLAIM")
    summary["interpretation_label"] = label

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "trades_enriched.csv").open("w", newline="", encoding="utf-8") as fh:
        if enriched:
            keys = list(enriched[0].keys())
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(enriched)
    with (OUT_DIR / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    print(json.dumps({k: summary[k] for k in
                      ("n_trades", "exit_mix", "trigger_mix",
                       "hypothesis_counts", "net_pl_diagnostic",
                       "mfe_mae", "interpretation_label")},
                     indent=2, ensure_ascii=False), flush=True)
    print(BANNER, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
