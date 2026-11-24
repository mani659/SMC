"""O-block year re-read (P2) — read-only measurement over the year census.

Recomputes O4 (SL / MAE vs the 30-pip benchmark) and O5 (TP structural vs
4xATR fallback) with each decision's ORIGINAL pre-registered definition, on:

    PRIMARY    the post-R1 S3 multi-book census (24 runs, books F/B/C/E/A)
    SECONDARY  the product_1y product-path census (12 segments, 239 fills)

O1 / O2 / O3 are NOT recomputed here: their verbatim definitions need
per-reject geometry / per-arm direction + arm timestamp, none of which exists
at year scale on disk. They are reported as UNDERDETERMINED by the note, not
approximated by this script.

Reads only. Writes only 06_RESEARCH/results/o_block_year_read/ (gitignored).
No smc import that mutates anything; no 04_SRC edit; no PnL used.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
S3 = REPO / "06_RESEARCH" / "results" / "parallel_books_s3_rerun"
PRODUCT = REPO / "06_RESEARCH" / "results" / "product_1y_one_story"
OUT = REPO / "06_RESEARCH" / "results" / "o_block_year_read"
PARQUET = REPO / "07_DATA" / "XAUUSD_M1.parquet"

SEGMENTS = ("nov24", "dec24", "jan25", "feb25", "mar25", "apr25",
            "may25", "jun25", "jul25", "aug25", "sep25", "oct25")
HYPOTHESES = ("LONG", "SHORT")
BOOKS = ("F", "B", "C", "E", "A")
UNIVERSE = "-".join(BOOKS)

PIP = 0.10                 # O4: 1 pip = 0.10 price
BENCH_PIPS = 30.0          # O4: 30 pips = 3.00 price (review benchmark only)
BENCH_PRICE = BENCH_PIPS * PIP
CLEAN_TOL = 0.05           # O4/O5: clean-stop / hit_tp tolerance
STOP_KINDS = ("stop_loss", "sl", "original_sl", "stop")
EXEC_BAR_MIN = 5           # trade stamps are M5 bucket OPENS: a bar stamped t
                           # spans [t, t+5min). The O4 convention "entry bar ->
                           # exit bar inclusive" therefore ends at exit_at + 5min
                           # on M1 data; without this an intrabar stop (entry_at
                           # == exit_at) is measured over a single minute and its
                           # own MAE is lost.


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def fill_key(row: dict) -> tuple:
    return (str(row["poi_id"]), str(row["trigger"]), str(row["entry_at"]),
            round(float(row["entry_price"]), 6), str(row["direction"]))


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(str(value))


def load_s3_universe() -> list[dict]:
    """Unique union of every fill in the 24 post-R1 runs (deduped by identity)."""
    seen: dict = {}
    for seg in SEGMENTS:
        for hyp in HYPOTHESES:
            for row in _read_csv(S3 / seg / f"books_{UNIVERSE}_{hyp}" / "trades.csv"):
                row["segment"] = seg
                row["hypothesis"] = hyp
                row["population"] = "s3_books"
                seen.setdefault(fill_key(row), row)
    return list(seen.values())


def load_product_universe() -> list[dict]:
    """The product-path year census (one row per product fill)."""
    rows: list[dict] = []
    for seg in SEGMENTS:
        for row in _read_csv(PRODUCT / "run1" / seg / "trades.csv"):
            row["segment"] = seg
            row["hypothesis"] = ""
            row["population"] = "product_1y"
            rows.append(row)
    return rows


def atr_of(row: dict) -> float | None:
    raw = row.get("signal_data_json") or ""
    if not raw:
        return None
    try:
        pm = json.loads(raw).get("product_menu") or {}
    except json.JSONDecodeError:
        return None
    atr = pm.get("atr_at_confirm")
    try:
        return float(atr) if atr not in (None, "") else None
    except (TypeError, ValueError):
        return None


class Path:
    """M1 path extremes over [entry, exit] inclusive (O4 convention)."""

    def __init__(self) -> None:
        frame = pd.read_parquet(PARQUET, columns=["timestamp", "high", "low"])
        self.ts = frame["timestamp"].to_numpy()
        self.high = frame["high"].to_numpy(dtype=float)
        self.low = frame["low"].to_numpy(dtype=float)

    def extremes(self, entry_at: str, exit_at: str) -> tuple[float, float] | None:
        start = np.datetime64(_dt(entry_at).replace(tzinfo=None), "us")
        end = np.datetime64(
            _dt(exit_at).replace(tzinfo=None) + timedelta(minutes=EXEC_BAR_MIN), "us")
        lo_i = int(np.searchsorted(self.ts, start, side="left"))
        hi_i = int(np.searchsorted(self.ts, end, side="right"))
        lo_i = max(0, min(lo_i, len(self.ts) - 1))
        hi_i = max(lo_i + 1, min(hi_i, len(self.ts)))
        if hi_i <= lo_i:
            return None
        return float(np.min(self.low[lo_i:hi_i])), float(np.max(self.high[lo_i:hi_i]))


def enrich(rows: list[dict], path: Path) -> list[dict]:
    """O4 / O5 per-fill facts, using each pack's own convention."""
    out: list[dict] = []
    for row in rows:
        entry = float(row["entry_price"])
        sl = float(row.get("original_sl") or row["sl"])
        tp = float(row["tp"]) if row.get("tp") not in (None, "") else None
        ex = float(row["exit_price"]) if row.get("exit_price") not in (None, "") else None
        long = str(row["direction"]).lower() == "long"
        ext = path.extremes(row["entry_at"], row["exit_at"])
        if ext is None:
            continue
        low, high = ext
        mae = max(0.0, entry - low) if long else max(0.0, high - entry)
        mfe = max(0.0, high - entry) if long else max(0.0, entry - low)
        risk = abs(entry - sl)
        tp_dist = abs(tp - entry) if tp is not None else None
        close_kind = str(row.get("close_kind") or "")
        hit_tp = bool(
            (ex is not None and tp is not None and abs(ex - tp) <= CLEAN_TOL)
            or close_kind == "take_profit")
        clean_stop = bool(close_kind in STOP_KINDS and ex is not None
                          and abs(ex - sl) <= CLEAN_TOL)
        out.append({
            "population": row["population"],
            "book": row.get("trigger") or "",
            "segment": row["segment"],
            "hypothesis": row.get("hypothesis") or "",
            "poi_id": row["poi_id"],
            "direction": row["direction"],
            "entry_at": row["entry_at"],
            "exit_at": row["exit_at"],
            "close_kind": close_kind,
            "entry_price": entry,
            "original_sl": sl,
            "tp": tp,
            "tp_source": row.get("tp_source") or "",
            "atr": atr_of(row),
            "sl_price": risk,
            "sl_pips": risk / PIP,
            "sl_atr": (risk / atr_of(row)) if atr_of(row) else None,
            "mae_price": mae,
            "mae_pips": mae / PIP,
            "mfe_price": mfe,
            "mfe_pips": mfe / PIP,
            "tp_dist": tp_dist,
            "tp_R": (tp_dist / risk) if (tp_dist is not None and risk) else None,
            "mfe_over_tp": (mfe / tp_dist) if (tp_dist and mfe is not None) else None,
            "hit_tp": hit_tp,
            "clean_stop": clean_stop,
        })
    return out


def quantiles(values: list[float]) -> dict:
    vals = sorted(values)
    if not vals:
        return {}
    def q(p: float) -> float:
        if len(vals) == 1:
            return vals[0]
        pos = p * (len(vals) - 1)
        lo = int(np.floor(pos))
        hi = min(lo + 1, len(vals) - 1)
        return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)
    return {"n": len(vals), "p25": round(q(0.25), 2), "median": round(median(vals), 2),
            "p75": round(q(0.75), 2), "min": round(vals[0], 2),
            "max": round(vals[-1], 2)}


def o4_block(fills: list[dict]) -> dict:
    sl = [f["sl_pips"] for f in fills]
    mae = [f["mae_pips"] for f in fills]
    mfe = [f["mfe_pips"] for f in fills]
    ratios = [f["mae_pips"] / f["sl_pips"] for f in fills if f["sl_pips"]]
    atr_multiples = [f["sl_atr"] for f in fills if f["sl_atr"] is not None]
    n = len(fills)
    return {
        "n": n,
        "sl_pips": quantiles(sl),
        "mae_pips": quantiles(mae),
        "mfe_pips": quantiles(mfe),
        "shares": {
            "mae_le_30": f"{sum(1 for v in mae if v <= BENCH_PIPS)}/{n}",
            "mae_le_30_pct": round(100.0 * sum(1 for v in mae if v <= BENCH_PIPS) / n, 1),
            "sl_le_30": f"{sum(1 for v in sl if v <= BENCH_PIPS)}/{n}",
            "sl_le_30_pct": round(100.0 * sum(1 for v in sl if v <= BENCH_PIPS) / n, 1),
            "sl_gt_30_pct": round(100.0 * sum(1 for v in sl if v > BENCH_PIPS) / n, 1),
            "clean_stop": f"{sum(1 for f in fills if f['clean_stop'])}/{n}",
            "clean_stop_pct": round(100.0 * sum(1 for f in fills if f["clean_stop"]) / n, 1),
        },
        "median_mae_over_sl": round(median(ratios), 2) if ratios else None,
        "median_mae_over_bench": round(median(mae) / BENCH_PIPS, 2) if mae else None,
        "sl_atr": quantiles(atr_multiples),
        "shares_by_source_close": dict(Counter(f["close_kind"] for f in fills)),
    }


def o5_block(fills: list[dict]) -> dict:
    n = len(fills)
    out: dict = {"n": n, "mix": dict(Counter(f["tp_source"] for f in fills))}
    for source in ("structural_swing", "atr_fallback"):
        group = [f for f in fills if f["tp_source"] == source]
        if not group:
            out[source] = {"n": 0}
            continue
        hits = sum(1 for f in group if f["hit_tp"])
        out[source] = {
            "n": len(group),
            "share_pct": round(100.0 * len(group) / n, 1),
            "hit_tp": f"{hits}/{len(group)}",
            "hit_tp_pct": round(100.0 * hits / len(group), 1),
            "tp_dist": quantiles([f["tp_dist"] for f in group if f["tp_dist"] is not None]),
            "tp_R": quantiles([f["tp_R"] for f in group if f["tp_R"] is not None]),
            "mfe_over_tp": quantiles([f["mfe_over_tp"] for f in group
                                      if f["mfe_over_tp"] is not None]),
        }
    other = n - sum(1 for f in fills if f["tp_source"] in
                    ("structural_swing", "atr_fallback"))
    out["none_or_unknown"] = other
    fallback_pct = 100.0 * sum(1 for f in fills if f["tp_source"] == "atr_fallback") / n
    out["fallback_share_pct"] = round(fallback_pct, 1)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    path = Path()

    s3_rows = load_s3_universe()
    product_rows = load_product_universe()
    print(f"[s3] union fills {len(s3_rows)} by book "
          f"{dict(sorted(Counter(r['trigger'] for r in s3_rows).items()))}")
    print(f"[product] fills {len(product_rows)}")

    s3 = enrich(s3_rows, path)
    product = enrich(product_rows, path)
    print(f"[path] enriched {len(s3)} S3 + {len(product)} product rows")

    summary: dict = {
        "study": "o_block_year_read",
        "diagnostic_only": True,
        "not_performance": "no expectancy, PF, edge or ranking; geometry and counts only",
        "populations": {
            "primary_s3_books": {
                "fills_union": len(s3),
                "books": dict(sorted(Counter(f["book"] for f in s3).items())),
                "source": "06_RESEARCH/results/parallel_books_s3_rerun/",
                "scope": "BOOK-SCOPED (P0 SUPERSET_OPEN_BOOK_SCOPE_ONLY)",
            },
            "secondary_product_1y": {
                "fills": len(product),
                "source": "06_RESEARCH/results/product_1y_one_story/run1/<seg>/trades.csv",
                "scope": "product path, 12 segments, one-story guard ON",
            },
        },
        "o4": {
            "rule": {
                "pip": PIP, "benchmark_pips": BENCH_PIPS,
                "sl_column": "original_sl",
                "path": ("entry bar -> exit bar inclusive (M1; min-low/max-high "
                         "invariant to resampling); the exit bar is the full M5 "
                         "bucket [exit_at, exit_at+5min) because trade stamps are "
                         "M5 bucket opens"),
                "mae": "LONG max(0, entry - min low), SHORT max(0, max high - entry)",
                "clean_stop": f"stop-like close_kind AND |exit - original_sl| <= {CLEAN_TOL}",
            },
            "primary_all_books": o4_block(s3),
            "primary_F_only": o4_block([f for f in s3 if f["book"] == "F"]),
            "primary_B_only": o4_block([f for f in s3 if f["book"] == "B"]),
            "secondary_product_1y": o4_block(product),
        },
        "o5": {
            "rule": {
                "tp_source": "read from export only",
                "hit_tp": f"close_kind == take_profit OR |exit - tp| <= {CLEAN_TOL}",
                "tp_R": "|tp - entry| / |entry - original_sl|",
            },
            "primary_all_books": o5_block(s3),
            "primary_F_only": o5_block([f for f in s3 if f["book"] == "F"]),
            "primary_B_only": o5_block([f for f in s3 if f["book"] == "B"]),
            "secondary_product_1y": o5_block(product),
            "by_book_mix": {
                book: dict(Counter(f["tp_source"] for f in s3 if f["book"] == book))
                for book in BOOKS},
        },
        "not_recomputed": {
            "O1": "no year-scale per-reject ledger (zone bounds + completion close + ATR)",
            "O2": "year armed ledger has no direction and no arm timestamp (J1 keys)",
            "O3": "year armed ledger has no direction; overlap relation branches on it",
        },
    }

    for name, rows in (("o4_o5_fills_s3.csv", s3), ("o4_o5_fills_product.csv", product)):
        with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                      encoding="utf-8")

    for label, block in (("S3 all books", summary["o4"]["primary_all_books"]),
                         ("S3 F only", summary["o4"]["primary_F_only"]),
                         ("product_1y", summary["o4"]["secondary_product_1y"])):
        print(f"[o4] {label}: n={block['n']} "
              f"SL med {block['sl_pips']['median']} pips | "
              f"MAE med {block['mae_pips']['median']} pips | "
              f"MAE<=30 {block['shares']['mae_le_30_pct']}% | "
              f"SL<=30 {block['shares']['sl_le_30_pct']}% | "
              f"clean {block['shares']['clean_stop_pct']}%")
    for label, block in (("S3 all books", summary["o5"]["primary_all_books"]),
                         ("S3 F only", summary["o5"]["primary_F_only"]),
                         ("product_1y", summary["o5"]["secondary_product_1y"])):
        st = block.get("structural_swing", {})
        fb = block.get("atr_fallback", {})
        print(f"[o5] {label}: n={block['n']} fallback {block['fallback_share_pct']}% "
              f"({fb.get('n', 0)}/{block['n']}) | "
              f"hit struct {st.get('hit_tp_pct')}% fallback {fb.get('hit_tp_pct')}% | "
              f"TP/R struct {st.get('tp_R', {}).get('median')} "
              f"fallback {fb.get('tp_R', {}).get('median')}")
    print(f"[out] {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
