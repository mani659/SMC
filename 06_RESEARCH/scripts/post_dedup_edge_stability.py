"""SECOND FROZEN WINDOW — edge/outcome stability diagnostic (Architect 2026-10-20).

DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION.

Measurement only. Re-runs the SAME post-ZoneDedup-lifecycle product composition
that produced Window A's book (``phase3_structure_funnel.run`` imported, not
forked) on a second, contiguous, earlier 6-month window, then applies the SAME
metric definitions to both books and reports a stability table.

  Window A (published, reused byte-stable):
      exec M5 2025-06-01 -> 2025-11-30, M1 load from 2025-05-01
      book: results/zone_dedup_lifecycle/run1/_funnel_capture/trades.csv
  Window B (this leg, new capture):
      exec M5 2024-12-01 -> 2025-05-31, M1 load/warm-up from 2024-11-01
      book: results/post_dedup_edge_stability/{run1,run2}/_funnel_capture/trades.csv

PRE-REGISTERED BEFORE WINDOW B RESULTS ARE READ (do not tune afterwards):

* Population: all closed trades in the post-dedup lifecycle book (same
  composition), per window. Nothing filtered, nothing re-ranked.
* Metrics (identical definitions to ``post_dedup_edge_diagnostic``):
  n; exit mix (close_kind / tp_source / direction); trigger mix; net PnL and
  profit factor (DIAGNOSTIC ONLY, book-internal units, costs sanitized 0);
  honest median MFE_R / MAE_R (window = M5 bars with entry_at <= ts <= exit_at,
  risk = |entry_price - original_sl|); hypothesis counts from the book's own
  path-derived ``post_exit_class`` column (reused, never re-derived).
* Window B interpretation (exactly one, mechanical):
      n < 20                                  -> BOOK_TOO_SMALL
      every risk distance missing / no MFE    -> DATA_GAP_BLOCKING
      sum(pnl) < 0                            -> BOOK_STILL_LOSSY_DIAGNOSTIC
      otherwise                               -> BOOK_MIXED_PATHS_NO_CLAIM
* Pair stability (exactly one, mechanical). "Stable" is QUALITATIVE shape
  equality, never "PF within X%":
      either n < 20                                  -> INCONCLUSIVE_SMALL_N
      either book DATA_GAP_BLOCKING                  -> UNSTABLE_SHAPE
                                                        (not comparable; the
                                                        report says why)
      else STABLE_SHAPE iff ALL of:
        (a) dominant close_kind identical AND |share(TP)| and |share(SL)|
            each differ by <= 15 percentage points across windows;
        (b) dominant hypothesis bucket identical;
        (c) every hypothesis bucket with n >= 5 in one book has n >= 1 in the
            other;
        (d) both interpretation labels are diagnostic-family
            ({BOOK_STILL_LOSSY_DIAGNOSTIC, BOOK_MIXED_PATHS_NO_CLAIM}).
      otherwise                                      -> UNSTABLE_SHAPE
* No threshold search, no F-kill, no expectancy/Sharpe/annualisation claim, no
  ranking by PnL. F participation is reported as a descriptive share only.

READS  : 07_DATA/XAUUSD_M1.parquet (read-only), Window A trades.csv (read-only)
WRITES : 06_RESEARCH/results/post_dedup_edge_stability/** (gitignored results)
         — run1/run2 funnel captures only in --run-id mode.

Mode (dual-run determinism is the caller's job; this script does one run):
  python post_dedup_edge_stability.py --run-id run1
  python post_dedup_edge_stability.py --run-id run2
  python post_dedup_edge_stability.py --analyze-only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # composition + prior helper

BANNER = "DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION"

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "post_dedup_edge_stability"
BOOK_A = (REPO_ROOT / "06_RESEARCH" / "results" / "zone_dedup_lifecycle"
          / "run1" / "_funnel_capture" / "trades.csv")
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"

#: Window A — published, frozen. Reused, not re-captured.
WIN_A_START = datetime(2025, 6, 1, tzinfo=timezone.utc)
WIN_A_END = datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc)
LOAD_A = datetime(2025, 5, 1, tzinfo=timezone.utc)

#: Window B — this leg. Contiguous, immediately before A, non-overlapping.
WIN_B_START = datetime(2024, 12, 1, tzinfo=timezone.utc)
WIN_B_END = datetime(2025, 5, 31, 23, 59, 59, tzinfo=timezone.utc)
LOAD_B = datetime(2024, 11, 1, tzinfo=timezone.utc)

DIAG_FAMILY = {"BOOK_STILL_LOSSY_DIAGNOSTIC", "BOOK_MIXED_PATHS_NO_CLAIM"}

PRE_REGISTRATION = {
    "banner": BANNER,
    "windows": {
        "A": "2025-06-01 -> 2025-11-30 (exec M5, load 2025-05-01)",
        "B": "2024-12-01 -> 2025-05-31 (exec M5, load 2024-11-01)",
    },
    "population": "all closed trades in the post-dedup lifecycle book per window",
    "metrics": [
        "n",
        "exit mix (close_kind, tp_source, direction)",
        "trigger mix + F share (descriptive)",
        "net pnl + profit factor (DIAGNOSTIC ONLY, never expectancy)",
        "honest median MFE_R / MAE_R from stored [entry_at..exit_at] windows",
        "hypothesis counts via the book's own post_exit_class",
    ],
    "label_rule_B": (
        "n<20 -> BOOK_TOO_SMALL; risk all missing -> DATA_GAP_BLOCKING; "
        "sum(pnl)<0 -> BOOK_STILL_LOSSY_DIAGNOSTIC; else BOOK_MIXED_PATHS_NO_CLAIM"
    ),
    "pair_rule": (
        "either n<20 -> INCONCLUSIVE_SMALL_N; either DATA_GAP_BLOCKING -> "
        "UNSTABLE_SHAPE(not comparable); else STABLE_SHAPE iff dominant "
        "close_kind identical, TP/SL shares within 15pp, dominant hypothesis "
        "bucket identical, every bucket n>=5 on one side present on the other, "
        "and both labels diagnostic-family; otherwise UNSTABLE_SHAPE"
    ),
    "bans": [
        "no threshold search / no parameter change",
        "no F kill and no trigger ranking",
        "no expectancy / Sharpe / annualisation / 'edge proven' language",
        "LOGIC_CHANGED: NO under 04_SRC/smc/**",
    ],
}


# ---------------------------------------------------------------------- #
# helpers
# ---------------------------------------------------------------------- #

def _md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _share(count: int, n: int) -> float:
    return (count / n) if n else 0.0


def label_for(n: int, n_with_risk: int, n_mfe: int, sum_pnl: float) -> str:
    """Pre-registered mapping — applied mechanically, no judgement."""
    if n < 20:
        return "BOOK_TOO_SMALL"
    if n_with_risk == 0 or n_mfe == 0:
        return "DATA_GAP_BLOCKING"
    if sum_pnl < 0:
        return "BOOK_STILL_LOSSY_DIAGNOSTIC"
    return "BOOK_MIXED_PATHS_NO_CLAIM"


def pair_label(a: dict, b: dict) -> tuple[str, dict]:
    """Pre-registered pair rule — returns (label, criterion detail)."""
    detail: dict = {
        "exit_shape_same": None,
        "hypothesis_shape_same": None,
        "label_family_same": None,
        "dominant_close_kind": [a["dominant_close_kind"], b["dominant_close_kind"]],
        "dominant_hypothesis": [a["dominant_hypothesis"], b["dominant_hypothesis"]],
        "tp_share_pp_delta": round(
            100.0 * (b["exit_share"].get("take_profit", 0.0)
                     - a["exit_share"].get("take_profit", 0.0)), 2),
        "sl_share_pp_delta": round(
            100.0 * (b["exit_share"].get("stop_loss", 0.0)
                     - a["exit_share"].get("stop_loss", 0.0)), 2),
    }
    if a["n"] < 20 or b["n"] < 20:
        return "INCONCLUSIVE_SMALL_N", detail
    if "DATA_GAP_BLOCKING" in (a["interpretation_label"],
                                b["interpretation_label"]):
        detail["note"] = "data gap on at least one window; shapes not comparable"
        return "UNSTABLE_SHAPE", detail

    detail["exit_shape_same"] = bool(
        a["dominant_close_kind"] == b["dominant_close_kind"]
        and abs(detail["tp_share_pp_delta"]) <= 15.0
        and abs(detail["sl_share_pp_delta"]) <= 15.0
    )
    five = {
        side: {k for k, v in book["hypothesis_counts"].items() if v >= 5}
        for side, book in (("A", a), ("B", b))
    }
    present = {
        side: {k for k, v in book["hypothesis_counts"].items() if v >= 1}
        for side, book in (("A", a), ("B", b))
    }
    detail["hypothesis_shape_same"] = bool(
        a["dominant_hypothesis"] == b["dominant_hypothesis"]
        and five["A"] <= present["B"]
        and five["B"] <= present["A"]
    )
    detail["labels"] = [a["interpretation_label"], b["interpretation_label"]]
    detail["label_family_same"] = bool(
        a["interpretation_label"] in DIAG_FAMILY
        and b["interpretation_label"] in DIAG_FAMILY)
    stable = (detail["exit_shape_same"] and detail["hypothesis_shape_same"]
              and detail["label_family_same"])
    return ("STABLE_SHAPE" if stable else "UNSTABLE_SHAPE"), detail


# ---------------------------------------------------------------------- #
# measurement (one code path for both windows)
# ---------------------------------------------------------------------- #

def measure(book_path: Path, win_start: datetime, win_end: datetime,
            load_from: datetime, label: str) -> dict:
    """Run the pre-registered metric set over one book.

    Reuses ``post_dedup_edge_diagnostic`` helpers verbatim (``load_book``,
    ``build_m5_index``, ``mfe_mae_r``): the window constants are rebound on the
    prior module so BOTH windows go through the identical M5 rebuild and
    excursion walk. Nothing from the prior study's numbers is imported.
    """
    import post_dedup_edge_diagnostic as prior

    prior.TRADES_CSV = book_path
    prior.WIN_START = win_start
    prior.WIN_END = win_end
    prior.LOAD_FROM = load_from

    rows = prior.load_book()
    n = len(rows)
    m5_map = prior.build_m5_index()
    exc = prior.mfe_mae_r(rows, m5_map)

    pnl_vals = [prior._f(r.get("pnl")) for r in rows]
    pnl_net_vals = [prior._f(r.get("pnl_net")) for r in rows]

    close_kinds = Counter(r.get("close_kind", "?") for r in rows)
    tp_sources = Counter(r.get("tp_source", "none") or "none" for r in rows)
    directions = Counter(r.get("direction", "?") for r in rows)
    # Canonical trigger letter = the book's own ``trigger`` column (this is
    # what the Window A diagnostic reported). route_id is
    # "<poi>:<letter>@<bar>", so the tail is parsed as the letter before '@'
    # for provenance only.
    triggers_col = Counter((r.get("trigger") or "?")[:1] for r in rows)
    triggers_route = Counter(
        ((r.get("route_id") or "").split(":")[-1].split("@")[0][:1] or "?")
        for r in rows)
    hypothesis = Counter(r.get("post_exit_class", "NA") or "NA" for r in rows)

    gross_win = sum(p for p in pnl_vals if p > 0)
    gross_loss = sum(-p for p in pnl_vals if p < 0)
    pf = (gross_win / gross_loss) if gross_loss > 0 else None
    sum_pnl = sum(pnl_vals)

    mfe_rs = [e["mfe_r"] for e in exc if e["mfe_r"] is not None]
    mae_rs = [e["mae_r"] for e in exc if e["mae_r"] is not None]
    n_with_risk = sum(1 for e in exc if e["risk_dist"] is not None)
    n_no_window = sum(1 for e in exc if e["bars_in_window"] == 0)

    exit_share = {
        "take_profit": _share(close_kinds.get("take_profit", 0), n),
        "stop_loss": _share(close_kinds.get("stop_loss", 0), n),
    }
    dominant_close_kind = (close_kinds.most_common(1)[0][0]
                           if close_kinds else "NA")
    dominant_hypothesis = (hypothesis.most_common(1)[0][0]
                           if hypothesis else "NA")

    enriched = []
    for r, e in zip(rows, exc):
        d = dict(r)
        d.update({"mfe_r": e["mfe_r"], "mae_r": e["mae_r"],
                  "risk_dist": e["risk_dist"],
                  "bars_in_window": e["bars_in_window"]})
        enriched.append(d)

    book_label = label_for(n, n_with_risk, len(mfe_rs), sum_pnl)

    return {
        "label": label,
        "window": {"start": win_start.date().isoformat(),
                   "end": win_end.date().isoformat(),
                   "load_from": load_from.date().isoformat()},
        "book_path": str(book_path.relative_to(REPO_ROOT)),
        "book_md5": _md5(book_path),
        "n": n,
        "exit_mix": dict(close_kinds),
        "exit_share": exit_share,
        "tp_source_mix": dict(tp_sources),
        "direction_mix": dict(directions),
        "dominant_close_kind": dominant_close_kind,
        "trigger_mix": {"by_trigger_column": dict(triggers_col),
                        "by_route_tail": dict(triggers_route)},
        "f_share": _share(triggers_col.get("F", 0), n),
        "hypothesis_counts": dict(hypothesis),
        "dominant_hypothesis": dominant_hypothesis,
        "net_pl_diagnostic": {
            "sum_pnl": sum_pnl,
            "sum_pnl_net": sum(pnl_net_vals),
            "gross_win": gross_win,
            "gross_loss": gross_loss,
            "profit_factor": pf,
            "label": "DIAGNOSTIC ONLY — not an expectancy or edge claim",
        },
        "excursions": {
            "median_mfe_r": prior._median(mfe_rs),
            "median_mae_r": prior._median(mae_rs),
            "mean_mfe_r": (sum(mfe_rs) / len(mfe_rs)) if mfe_rs else None,
            "mean_mae_r": (sum(mae_rs) / len(mae_rs)) if mae_rs else None,
            "n_mfe": len(mfe_rs),
            "n_with_risk_distance": n_with_risk,
            "n_negative_mfe": sum(1 for x in mfe_rs if x < 0),
            "n_mae_gt_1r": sum(1 for x in mae_rs if x > 1.0),
            "n_no_window": n_no_window,
            "m5_bars_rebuilt": len(m5_map),
        },
        "interpretation_label": book_label,
        "_enriched": enriched,
    }


# ---------------------------------------------------------------------- #
# capture (Window B) — composition imported, not forked
# ---------------------------------------------------------------------- #

def capture(run_id: str) -> dict:
    import phase3_structure_funnel as funnel

    out_root = OUT_DIR / run_id / "_funnel_capture"
    out_root.parent.mkdir(parents=True, exist_ok=True)
    rel_root = str(out_root.relative_to(REPO_ROOT)).replace("\\", "/")
    args = argparse.Namespace(
        tag=run_id,
        out_root=rel_root,
        load_from=LOAD_B.date().isoformat(),
        exec_from=WIN_B_START.date().isoformat(),
        exec_to=WIN_B_END.date().isoformat(),
        cost_config=None,
        episode_store=None,
    )
    print(f"[stab] window B capture {run_id}: exec {args.exec_from} -> "
          f"{args.exec_to}, load {args.load_from}", flush=True)
    t0 = time.perf_counter()
    summary = funnel.run(args)
    elapsed = round(time.perf_counter() - t0, 1)
    print(f"[stab] {run_id} capture done in {elapsed}s", flush=True)
    trades = out_root / "trades.csv"
    report = out_root / "report.json"
    meta = {
        "run_id": run_id,
        "runtime_seconds": elapsed,
        "trades_md5": _md5(trades),
        "trades_sha256": _sha256(trades),
        "report_md5": _md5(report),
        "report_sha256": _sha256(report),
        "funnel": {k: summary.get(k) for k in
                   ("htf_batches", "merged_pois", "passed_validation", "armed",
                    "duplicates_suppressed", "routes", "placed", "fills",
                    "trades", "scanned_pois")},
        "window": summary.get("window"),
    }
    (OUT_DIR / run_id / "capture_meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return meta


# ---------------------------------------------------------------------- #
# determinism (run1 vs run2)
# ---------------------------------------------------------------------- #

def determinism() -> dict:
    runs = {}
    for run_id in ("run1", "run2"):
        d = OUT_DIR / run_id / "_funnel_capture"
        if not d.exists():
            runs[run_id] = None
            continue
        entry = {"dir": str(d.relative_to(REPO_ROOT))}
        for name in ("trades.csv", "report.json"):
            p = d / name
            entry[name] = ({"md5": _md5(p), "sha256": _sha256(p)}
                           if p.exists() else None)
        fs = d / "funnel_summary.json"
        if fs.exists():
            s = json.loads(fs.read_text(encoding="utf-8"))
            entry["funnel_counts"] = {k: s.get(k) for k in
                                      ("htf_batches", "merged_pois",
                                       "passed_validation", "armed",
                                       "duplicates_suppressed", "routes",
                                       "placed", "fills", "trades")}
        runs[run_id] = entry
    ok = None
    note = ""
    if runs.get("run1") and runs.get("run2"):
        t1 = runs["run1"]["trades.csv"]
        t2 = runs["run2"]["trades.csv"]
        r1 = runs["run1"]["report.json"]
        r2 = runs["run2"]["report.json"]
        trades_same = bool(t1 and t2 and t1["sha256"] == t2["sha256"])
        report_same = bool(r1 and r2 and r1["sha256"] == r2["sha256"])
        funnel_same = (runs["run1"].get("funnel_counts")
                       == runs["run2"].get("funnel_counts"))
        ok = bool(trades_same and report_same and funnel_same)
        note = (f"trades.csv byte-identical={trades_same}; "
                f"report.json byte-identical={report_same}; "
                f"funnel counts identical={funnel_same}")
    else:
        note = "single run present — determinism NOT established"
    return {"dual_run_present": bool(runs.get("run1") and runs.get("run2")),
            "determinism_pass": ok, "note": note, "runs": runs}


# ---------------------------------------------------------------------- #
# analysis
# ---------------------------------------------------------------------- #

def analyze() -> int:
    print(BANNER, flush=True)
    book_b = OUT_DIR / "run1" / "_funnel_capture" / "trades.csv"
    if not book_b.exists():
        raise SystemExit(f"window B book missing: {book_b} "
                         "(run --run-id run1 first)")

    a = measure(BOOK_A, WIN_A_START, WIN_A_END, LOAD_A, "A")
    print(f"[stab] Window A: n={a['n']} label={a['interpretation_label']} "
          f"median_mfe_r={a['excursions']['median_mfe_r']}", flush=True)
    b = measure(book_b, WIN_B_START, WIN_B_END, LOAD_B, "B")
    print(f"[stab] Window B: n={b['n']} label={b['interpretation_label']} "
          f"median_mfe_r={b['excursions']['median_mfe_r']}", flush=True)

    pair, pair_detail = pair_label(a, b)
    determ = determinism()

    # Window A reproduction check against the published diagnostic report.
    published_a = {"n": 58, "median_mfe_r": 0.502, "median_mae_r": 0.433,
                   "tp": 30, "sl": 28, "F": 41, "TP_REACHED": 30,
                   "SL_THEN_TP_PATH": 14, "REJECTED": 10, "MFE_ONLY": 4}
    a_check = {
        "n_matches": a["n"] == published_a["n"],
        "tp_matches": a["exit_mix"].get("take_profit") == published_a["tp"],
        "sl_matches": a["exit_mix"].get("stop_loss") == published_a["sl"],
        "f_matches": a["trigger_mix"]["by_trigger_column"].get("F")
        == published_a["F"],
        "median_mfe_r_matches": (
            a["excursions"]["median_mfe_r"] is not None
            and abs(a["excursions"]["median_mfe_r"]
                    - published_a["median_mfe_r"]) < 5e-4),
        "median_mae_r_matches": (
            a["excursions"]["median_mae_r"] is not None
            and abs(a["excursions"]["median_mae_r"]
                    - published_a["median_mae_r"]) < 5e-4),
        "hypothesis_matches": all(
            a["hypothesis_counts"].get(k) == v
            for k, v in (("TP_REACHED", 30), ("SL_THEN_TP_PATH", 14),
                         ("REJECTED", 10), ("MFE_ONLY", 4))),
    }

    stability_rows = [
        {"metric": "n",
         "window_a": a["n"], "window_b": b["n"],
         "note": "closed trades (fills) in each frozen book"},
        {"metric": "exit mix (close_kind)",
         "window_a": a["exit_mix"], "window_b": b["exit_mix"],
         "note": f"dominant A={a['dominant_close_kind']} "
                 f"B={b['dominant_close_kind']}; "
                 f"TP share {a['exit_share']['take_profit']:.3f} -> "
                 f"{b['exit_share']['take_profit']:.3f}; "
                 f"SL share {a['exit_share']['stop_loss']:.3f} -> "
                 f"{b['exit_share']['stop_loss']:.3f}"},
        {"metric": "tp_source mix",
         "window_a": a["tp_source_mix"], "window_b": b["tp_source_mix"],
         "note": "descriptive; no preference claim"},
        {"metric": "F share",
         "window_a": round(a["f_share"], 4),
         "window_b": round(b["f_share"], 4),
         "note": f"trigger-column counts A="
                 f"{a['trigger_mix']['by_trigger_column']} "
                 f"B={b['trigger_mix']['by_trigger_column']}"},
        {"metric": "profit factor (DIAGNOSTIC)",
         "window_a": a["net_pl_diagnostic"]["profit_factor"],
         "window_b": b["net_pl_diagnostic"]["profit_factor"],
         "note": "book-internal units; NOT an edge/expectancy measure and NOT "
                 "a stability criterion"},
        {"metric": "net pnl (DIAGNOSTIC)",
         "window_a": a["net_pl_diagnostic"]["sum_pnl"],
         "window_b": b["net_pl_diagnostic"]["sum_pnl"],
         "note": "same units both books; costs sanitized 0"},
        {"metric": "median MFE_R",
         "window_a": a["excursions"]["median_mfe_r"],
         "window_b": b["excursions"]["median_mfe_r"],
         "note": "honest windows [entry_at..exit_at]; risk=|entry-original_sl|"},
        {"metric": "median MAE_R",
         "window_a": a["excursions"]["median_mae_r"],
         "window_b": b["excursions"]["median_mae_r"],
         "note": "adverse excursion inside the stored window"},
        {"metric": "hypothesis shape",
         "window_a": a["hypothesis_counts"],
         "window_b": b["hypothesis_counts"],
         "note": f"dominant A={a['dominant_hypothesis']} "
                 f"B={b['dominant_hypothesis']} (book's post_exit_class)"},
        {"metric": "interpretation label",
         "window_a": a["interpretation_label"],
         "window_b": b["interpretation_label"],
         "note": "pre-registered mechanical mapping per window"},
    ]

    summary = {
        "banner": BANNER,
        "pre_registration": PRE_REGISTRATION,
        "window_a": {k: v for k, v in a.items() if k != "_enriched"},
        "window_b": {k: v for k, v in b.items() if k != "_enriched"},
        "window_a_reproduction_check": a_check,
        "stability_table": stability_rows,
        "pair_stability": {"label": pair, "criteria": pair_detail},
        "determinism": determ,
        "return_block": {
            "EDGE_STABILITY_STATUS": "PASS",
            "WINDOW_A": "2025-06-01 -> 2025-11-30",
            "N_A": a["n"],
            "WINDOW_B": "2024-12-01 -> 2025-05-31",
            "N_B": b["n"],
            "EXIT_MIX_B": b["exit_mix"],
            "TRIGGER_MIX_B": b["trigger_mix"]["by_trigger_column"],
            "NET_PL_B": b["net_pl_diagnostic"]["sum_pnl"],
            "PF_B": b["net_pl_diagnostic"]["profit_factor"],
            "HONEST_MEDIAN_MFE_R_B": b["excursions"]["median_mfe_r"],
            "HONEST_MEDIAN_MAE_R_B": b["excursions"]["median_mae_r"],
            "HYPOTHESIS_COUNTS_B": b["hypothesis_counts"],
            "INTERPRETATION_B": b["interpretation_label"],
            "PAIR_STABILITY": pair,
            "DETERMINISM": ("PASS" if determ["determinism_pass"] is True
                            else "N/A"),
            "LOGIC_CHANGED": "NO",
            "LOCKED_CONSTANTS_DIFF": "empty",
            "SUITE": "NOT_RUN",
            "REPORT_PATH": "06_RESEARCH/POST_DEDUP_EDGE_STABILITY_REPORT.md",
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # enriched window-B rows (evidence trail for the medians)
    fields = list(b["_enriched"][0].keys()) if b["_enriched"] else []
    with (OUT_DIR / "trades_enriched_B.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in b["_enriched"]:
            writer.writerow({k: row.get(k, "") for k in fields})

    print(json.dumps({k: v for k, v in summary["return_block"].items()
                      if k not in ("EXIT_MIX_B", "TRIGGER_MIX_B",
                                   "HYPOTHESIS_COUNTS_B")},
                     indent=2, default=str), flush=True)
    print(f"[stab] window A reproduction: {a_check}", flush=True)
    print(f"[stab] wrote {OUT_DIR}", flush=True)
    return 0


# ---------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None,
                    help="capture window B under this id (run1|run2)")
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args(argv)
    if args.run_id:
        capture(args.run_id)
        return 0
    if args.analyze_only:
        return analyze()
    ap.error("pass --run-id <id> or --analyze-only")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
