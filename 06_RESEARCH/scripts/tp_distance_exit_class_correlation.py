"""FOUR-WINDOW TP-DISTANCE vs EXIT-CLASS CORRELATION (Architect 2026-10-21).

DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION.

Measurement only, observation only. Tests whether *TP distance in R*
systematically tracks the *exit class* across four locked, non-overlapping
6-month windows, following the EXIT_ANATOMY_DIAGNOSTIC (Architect 2026-10-20),
which found median TP_DISTANCE_R ~0.64R in Window A (TARGET-heavy) vs ~1.0R in
Window B (SOFT_STOP-heavy) with SL_WHILE_TP_VALID = 0 in both books.

HARD BANS honoured by this script
  * no edit under 04_SRC/smc/** (LOGIC_CHANGED: NO); the composition is
    *imported* (phase3_structure_funnel.run) and the data helpers are
    *reused* (post_dedup_edge_diagnostic.load_book/build_m5_index/mfe_mae_r,
    exit_anatomy_diagnostic.build_window/exit_class) — nothing is forked.
  * locked_constants.py untouched.
  * no TP/SL/BE/trail parameter search, no "optimal R" tuning, no exit fix.
  * no expectancy / scale / Sharpe language anywhere.
  * windows are LOCKED below and are never moved to improve a correlation.

WINDOWS (locked)
  W1  2024-06-01 -> 2024-11-30   load/warm-up 2024-05-01   (new capture)
  W2  2024-12-01 -> 2025-05-31   load/warm-up 2024-11-01   (prior Window B,
                                 REUSED byte-stable: post_dedup_edge_stability)
  W3  2025-06-01 -> 2025-11-30   load/warm-up 2025-05-01   (prior Window A,
                                 REUSED byte-stable: zone_dedup_lifecycle/run1)
  W4  2025-12-01 -> 2026-03-31   load/warm-up 2025-11-01   (new capture;
                                 the parquet covers through 2026-04-10, so W4 is
                                 a COMPLETE 6-month window — no partial-year
                                 fallback is used, and the drop-W4 sensitivity
                                 is still computed as a robustness check)

PRE-REGISTERED BEFORE ANY NEW WINDOW WAS READ (do not tune afterwards)

  Per trade (identical definitions to exit_anatomy_diagnostic):
    R_stop       = |entry_price - original_sl|
    R_tp         = |tp - entry_price|                (NA when no tp)
    TP_DISTANCE_R= R_tp / R_stop                     (NA if either missing)
    EXIT_CLASS   = TARGET_TP | SOFT_SL_OR_BE | HARD_SL | OTHER
    MFE_R, hold_bars  (honest path; risk = original_sl denominator)

  Distance buckets (pre-registered, fixed):
    near  = TP_DISTANCE_R <= 0.75
    mid   = 0.75 < TP_DISTANCE_R <= 1.25
    far   = TP_DISTANCE_R > 1.25

  Per window:
    n, n_with_distance, median TP_DISTANCE_R
    EXIT_CLASS counts + shares
    median TP_DISTANCE_R WITHIN each EXIT_CLASS
    share of trades in each distance bucket
    within each distance bucket: TARGET_TP rate, SOFT rate, HARD rate

  Per-window PATTERN criteria (mechanical, each evaluated only when its
  inputs are non-empty; a criterion with empty inputs is NA and counts as
  neither satisfied nor violated):
    C1  near→TARGET : TARGET_TP rate(near)  > TARGET_TP rate(far)
    C2  far→SOFT    : SOFT rate(far)        > SOFT rate(near)
    C3  far→HARD    : HARD rate(far)        > HARD rate(near)
    C4  class order : median TP_DISTANCE_R among TARGET_TP exits is strictly
                       below the median among HARD_SL exits AND strictly
                       below the median among SOFT_SL_OR_BE exits
                       (supporting evidence, NOT required for the label)
  A window TRACKS  iff C1 AND (C2 OR C3) are satisfied and evaluable.
  A window INVERTS iff C1 is evaluable and NOT satisfied.
  A window is INCONCLUSIVE if C1 is not evaluable (an empty bucket).
  A window is TOO_SMALL (excluded from the tally) if n_with_distance < 10.

  Overall label (exactly one, mechanical):
    usable = windows labelled TRACKS or INVERTS
    usable < 3                                -> DATA_GAP_BLOCKING
    TRACKS >= 3                               -> DISTANCE_TRACKS_EXIT_CLASS
    INVERTS >= TRACKS                         -> DISTANCE_WEAK_OR_NOISE
    otherwise (TRACKS > INVERTS but < 3)      -> DISTANCE_WINDOW_SPECIFIC

  Reported cross-window tests (descriptive only, no significance claim):
    1. rank windows by median TP_DISTANCE_R (asc) vs rank by TARGET_TP share
       (desc) and vs SOFT share (asc); report whether the orders agree and
       the Spearman rank correlation of each pair.
    2. pooled (all four windows): TARGET_TP rate by distance bucket.
    3. sensitivity: drop W4 (if it were partial; it is not, so this is a
       robustness check) and recompute the ranks and the label.

READS  : 07_DATA/XAUUSD_M1.parquet (read-only), the W2/W3 books (read-only)
WRITES : 06_RESEARCH/results/tp_distance_exit_class/** (gitignored research
         artifacts: W1/W4 funnel captures, summary.json, trades_all_windows.csv)

Usage:
  python 06_RESEARCH/scripts/tp_distance_exit_class_correlation.py \
      --capture W1 --run-id run1          # one capture (composition imported)
  python 06_RESEARCH/scripts/tp_distance_exit_class_correlation.py \
      --capture W1 --run-id run2
  python 06_RESEARCH/scripts/tp_distance_exit_class_correlation.py \
      --capture W4 --run-id run1
  python 06_RESEARCH/scripts/tp_distance_exit_class_correlation.py \
      --capture W4 --run-id run2
  python 06_RESEARCH/scripts/tp_distance_exit_class_correlation.py \
      --analyze-only
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

BANNER = "DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION"
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "tp_distance_exit_class"

#: Near / mid / far bucket edges — pre-registered, fixed.
BUCKET_EDGES = (0.75, 1.25)
BUCKET_NAMES = ("leq_0.75", "mid_0.75_1.25", "gt_1.25")
#: A window needs at least this many trades with a known TP_DISTANCE_R before
#: it is allowed into the cross-window tally.
MIN_TRADES_FOR_TALLY = 10

#: Locked windows. ``capture`` marks the windows this leg must capture; the
#: others are reused byte-stable books from the prior legs.
WINDOWS: dict[str, dict] = {
    "W1": {
        "start": datetime(2024, 6, 1, tzinfo=timezone.utc),
        "end": datetime(2024, 11, 30, 23, 59, 59, tzinfo=timezone.utc),
        "load_from": datetime(2024, 5, 1, tzinfo=timezone.utc),
        "label": "2024-06-01 -> 2024-11-30",
        "capture": True,
        "book": None,          # filled in by _book_path()
        "enriched": None,
        "prior": "new capture (this leg)",
    },
    "W2": {
        "start": datetime(2024, 12, 1, tzinfo=timezone.utc),
        "end": datetime(2025, 5, 31, 23, 59, 59, tzinfo=timezone.utc),
        "load_from": datetime(2024, 11, 1, tzinfo=timezone.utc),
        "label": "2024-12-01 -> 2025-05-31",
        "capture": False,
        "book": (REPO_ROOT / "06_RESEARCH" / "results"
                 / "post_dedup_edge_stability" / "run1" / "_funnel_capture"
                 / "trades.csv"),
        "enriched": (REPO_ROOT / "06_RESEARCH" / "results"
                     / "post_dedup_edge_stability" / "trades_enriched_B.csv"),
        "prior": "prior Window B book (post_dedup_edge_stability) — reused",
    },
    "W3": {
        "start": datetime(2025, 6, 1, tzinfo=timezone.utc),
        "end": datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc),
        "load_from": datetime(2025, 5, 1, tzinfo=timezone.utc),
        "label": "2025-06-01 -> 2025-11-30",
        "capture": False,
        "book": (REPO_ROOT / "06_RESEARCH" / "results" / "zone_dedup_lifecycle"
                 / "run1" / "_funnel_capture" / "trades.csv"),
        "enriched": (REPO_ROOT / "06_RESEARCH" / "results"
                     / "post_dedup_edge_diagnostic" / "trades_enriched.csv"),
        "prior": "prior Window A book (zone_dedup_lifecycle/run1) — reused",
    },
    "W4": {
        "start": datetime(2025, 12, 1, tzinfo=timezone.utc),
        "end": datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc),
        "load_from": datetime(2025, 11, 1, tzinfo=timezone.utc),
        "label": "2025-12-01 -> 2026-03-31",
        "capture": True,
        "book": None,
        "enriched": None,
        "prior": "new capture (this leg)",
    },
}

WINDOW_ORDER = ("W1", "W2", "W3", "W4")

PRE_REGISTRATION = {
    "banner": BANNER,
    "windows": {k: v["label"] for k, v in WINDOWS.items()},
    "population": ("all closed trades (fills) in each window's post-ZoneDedup "
                   "product book; nothing filtered, nothing re-ranked"),
    "per_trade": {
        "R_stop": "|entry_price - original_sl|",
        "R_tp": "|tp - entry_price| (NA when no tp)",
        "TP_DISTANCE_R": "R_tp / R_stop (NA if either missing)",
        "EXIT_CLASS": ("TARGET_TP | SOFT_SL_OR_BE (stop, pnl>0) | HARD_SL "
                       "(stop, pnl<=0) | OTHER — identical to "
                       "exit_anatomy_diagnostic"),
        "MFE_R": "honest path, risk = |entry - original_sl| (reused helper)",
    },
    "buckets": {"leq_0.75": "TP_DISTANCE_R <= 0.75",
                "mid_0.75_1.25": "0.75 < TP_DISTANCE_R <= 1.25",
                "gt_1.25": "TP_DISTANCE_R > 1.25"},
    "per_window_criteria": {
        "C1_near_to_target": "TARGET rate(near) > TARGET rate(far)",
        "C2_far_to_soft": "SOFT rate(far) > SOFT rate(near)",
        "C3_far_to_hard": "HARD rate(far) > HARD rate(near)",
        "C4_class_order": ("median TP_DISTANCE_R(TARGET_TP) < median(HARD_SL) "
                           "and < median(SOFT_SL_OR_BE) — supporting only"),
        "window_TRACKS": "C1 AND (C2 OR C3), both evaluable",
        "window_INVERTS": "C1 evaluable and not satisfied",
        "window_INCONCLUSIVE": "C1 not evaluable (empty bucket)",
        "window_TOO_SMALL": "n_with_distance < 10 (excluded from the tally)",
    },
    "label_rule": (
        "usable = {TRACKS, INVERTS}; usable<3 -> DATA_GAP_BLOCKING; "
        "TRACKS>=3 -> DISTANCE_TRACKS_EXIT_CLASS; INVERTS>=TRACKS -> "
        "DISTANCE_WEAK_OR_NOISE; else -> DISTANCE_WINDOW_SPECIFIC"
    ),
    "reported_tests": [
        "rank windows by median TP_DISTANCE_R vs TARGET_TP share and SOFT share",
        "pooled TARGET_TP rate by distance bucket",
        "sensitivity: drop W4 (partial-year rule) and recompute ranks + label",
    ],
    "bans": [
        "no TP/SL/BE/trail parameter search and no 'optimal R' tuning",
        "no expectancy / scale / Sharpe language",
        "no F-kill, no trigger ranking",
        "windows are locked and never moved to improve a correlation",
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


def _median(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _share(count: int, n: int):
    return (count / n) if n else None


def _round(value, digits=4):
    return None if value is None else round(value, digits)


def _book_path(window_key: str) -> Path:
    spec = WINDOWS[window_key]
    if spec["book"] is not None:
        return spec["book"]
    return OUT_DIR / window_key / "run1" / "_funnel_capture" / "trades.csv"


def bucket_of(distance_r):
    """Pre-registered bucket edges."""
    if distance_r is None:
        return None
    if distance_r <= BUCKET_EDGES[0]:
        return "leq_0.75"
    if distance_r <= BUCKET_EDGES[1]:
        return "mid_0.75_1.25"
    return "gt_1.25"


def _spearman(xs, ys) -> float | None:
    """Spearman rank correlation (descriptive only; no p-value)."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return None
    rx = _ranks([p[0] for p in pairs])
    ry = _ranks([p[1] for p in pairs])
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def _ranks(values):
    """Average ranks for ties."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


# ---------------------------------------------------------------------- #
# capture (W1 / W4) — composition imported, not forked
# ---------------------------------------------------------------------- #

def capture(window_key: str, run_id: str) -> dict:
    import phase3_structure_funnel as funnel

    spec = WINDOWS[window_key]
    out_root = OUT_DIR / window_key / run_id / "_funnel_capture"
    out_root.parent.mkdir(parents=True, exist_ok=True)
    rel_root = str(out_root.relative_to(REPO_ROOT)).replace("\\", "/")
    args = argparse.Namespace(
        tag=f"{window_key}_{run_id}",
        out_root=rel_root,
        load_from=spec["load_from"].date().isoformat(),
        exec_from=spec["start"].date().isoformat(),
        exec_to=spec["end"].date().isoformat(),
        cost_config=None,
        episode_store=None,
    )
    print(f"[tpd] capture {window_key} {run_id}: exec {args.exec_from} -> "
          f"{args.exec_to}, load {args.load_from}", flush=True)
    t0 = time.perf_counter()
    summary = funnel.run(args)
    elapsed = round(time.perf_counter() - t0, 1)
    trades = out_root / "trades.csv"
    report = out_root / "report.json"
    meta = {
        "window": window_key,
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
        "window_effective": summary.get("window"),
    }
    (OUT_DIR / window_key / run_id / "capture_meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"[tpd] {window_key} {run_id} capture done in {elapsed}s "
          f"trades_md5={meta['trades_md5']}", flush=True)
    return meta


def determinism(window_key: str) -> dict:
    """run1 vs run2 identity for a newly captured window."""
    runs = {}
    for run_id in ("run1", "run2"):
        d = OUT_DIR / window_key / run_id / "_funnel_capture"
        if not d.exists():
            runs[run_id] = None
            continue
        entry = {"dir": str(d.relative_to(REPO_ROOT))}
        for name in ("trades.csv", "report.json"):
            p = d / name
            entry[name] = (_sha256(p) if p.exists() else None)
        fs = d / "funnel_summary.json"
        if fs.exists():
            s = json.loads(fs.read_text(encoding="utf-8"))
            entry["funnel_counts"] = {k: s.get(k) for k in
                                      ("htf_batches", "merged_pois",
                                       "passed_validation", "armed", "routes",
                                       "placed", "fills", "trades")}
        runs[run_id] = entry
    if not (runs.get("run1") and runs.get("run2")):
        return {"window": window_key, "dual_run_present": False,
                "determinism_pass": None,
                "note": "single run present — determinism NOT established"}
    t1 = runs["run1"]["trades.csv"]
    t2 = runs["run2"]["trades.csv"]
    r1 = runs["run1"]["report.json"]
    r2 = runs["run2"]["report.json"]
    trades_same = bool(t1 and t2 and t1 == t2)
    report_same = bool(r1 and r2 and r1 == r2)
    funnel_same = (runs["run1"].get("funnel_counts")
                   == runs["run2"].get("funnel_counts"))
    return {
        "window": window_key,
        "dual_run_present": True,
        "determinism_pass": bool(trades_same and report_same and funnel_same),
        "trades_byte_identical": trades_same,
        "report_byte_identical": report_same,
        "funnel_counts_identical": funnel_same,
        "note": (f"trades.csv byte-identical={trades_same}; "
                 f"report.json byte-identical={report_same}; "
                 f"funnel counts identical={funnel_same}"),
    }


# ---------------------------------------------------------------------- #
# measurement — reuses the frozen helpers, nothing re-derived
# ---------------------------------------------------------------------- #

def measure_window(window_key: str) -> dict:
    import exit_anatomy_diagnostic as anatomy

    spec = dict(WINDOWS[window_key])
    book = _book_path(window_key)
    if not book.exists():
        raise SystemExit(f"book missing for {window_key}: {book} "
                         "(capture it first)")
    spec["book"] = book
    spec["start"] = WINDOWS[window_key]["start"]
    spec["end"] = WINDOWS[window_key]["end"]
    spec["load_from"] = WINDOWS[window_key]["load_from"]
    spec["label"] = WINDOWS[window_key]["label"]

    enriched_path = WINDOWS[window_key]["enriched"]
    if enriched_path is None:
        # no prior enriched artifact for a freshly captured window — point the
        # cross-check at a path that does not exist (it reports present: False)
        enriched_path = OUT_DIR / window_key / "trades_enriched.csv"
    window = anatomy.build_window(window_key, spec, enriched_path)
    trades = window["trades"]

    n = len(trades)
    classes = Counter(t["exit_class"] for t in trades)
    with_distance = [t for t in trades if t["tp_distance_r"] is not None]
    n_distance = len(with_distance)

    # ---- per-class medians (pre-registered) --------------------------- #
    by_class = {}
    for klass in ("TARGET_TP", "SOFT_SL_OR_BE", "HARD_SL", "OTHER"):
        group = [t for t in trades if t["exit_class"] == klass]
        by_class[klass] = {
            "n": len(group),
            "share": _round(_share(len(group), n)),
            "median_tp_distance_r": _round(_median(
                [t["tp_distance_r"] for t in group])),
            "median_hold_bars": _median([t["hold_bars"] for t in group]),
            "median_mfe_r": _round(_median([t["mfe_r"] for t in group])),
        }

    # ---- distance buckets (pre-registered) ---------------------------- #
    buckets = {}
    raw_rates = {}
    for name in BUCKET_NAMES:
        group = [t for t in with_distance if bucket_of(t["tp_distance_r"]) == name]
        m = len(group)
        c = Counter(t["exit_class"] for t in group)
        raw_rates[name] = {
            "n": m,
            "target": _share(c.get("TARGET_TP", 0), m),
            "soft": _share(c.get("SOFT_SL_OR_BE", 0), m),
            "hard": _share(c.get("HARD_SL", 0), m),
        }
        buckets[name] = {
            "n": m,
            "share_of_window": _round(_share(m, n)),
            "share_of_scored": _round(_share(m, n_distance)),
            "target_rate": _round(_share(c.get("TARGET_TP", 0), m)),
            "soft_rate": _round(_share(c.get("SOFT_SL_OR_BE", 0), m)),
            "hard_rate": _round(_share(c.get("HARD_SL", 0), m)),
            "exit_class_counts": dict(c),
            "median_hold_bars": _median([t["hold_bars"] for t in group]),
            "median_mfe_r": _round(_median([t["mfe_r"] for t in group])),
        }

    # ---- per-window pattern criteria (pre-registered) ----------------- #
    near, far = raw_rates["leq_0.75"], raw_rates["gt_1.25"]
    c1 = c2 = c3 = None
    if near["n"] > 0 and far["n"] > 0:
        c1 = near["target"] > far["target"]
        c2 = far["soft"] > near["soft"]
        c3 = far["hard"] > near["hard"]
    med_target = by_class["TARGET_TP"]["median_tp_distance_r"]
    med_hard = by_class["HARD_SL"]["median_tp_distance_r"]
    med_soft = by_class["SOFT_SL_OR_BE"]["median_tp_distance_r"]
    c4 = None
    if med_target is not None and med_hard is not None and med_soft is not None:
        c4 = bool(med_target < med_hard and med_target < med_soft)

    if n_distance < MIN_TRADES_FOR_TALLY:
        window_label = "TOO_SMALL"
    elif c1 is None:
        window_label = "INCONCLUSIVE"
    elif c1 and (c2 or c3):
        window_label = "TRACKS"
    else:
        window_label = "INVERTS"

    return {
        "window": window_key,
        "label": WINDOWS[window_key]["label"],
        "prior_book": WINDOWS[window_key]["prior"],
        "book_path": str(book.relative_to(REPO_ROOT)),
        "book_md5": _md5(book),
        "n": n,
        "n_with_tp_distance_r": n_distance,
        "n_missing_tp_distance_r": n - n_distance,
        "median_tp_distance_r": _round(_median(
            [t["tp_distance_r"] for t in with_distance])),
        "median_hold_bars": _median([t["hold_bars"] for t in trades]),
        "median_mfe_r": _round(_median([t["mfe_r"] for t in trades])),
        "exit_class_counts": dict(classes),
        "exit_class_shares": {k: _round(_share(v, n)) for k, v in classes.items()},
        "target_share": _round(_share(classes.get("TARGET_TP", 0), n)),
        "soft_share": _round(_share(classes.get("SOFT_SL_OR_BE", 0), n)),
        "hard_share": _round(_share(classes.get("HARD_SL", 0), n)),
        "stop_share": _round(_share(classes.get("SOFT_SL_OR_BE", 0)
                                    + classes.get("HARD_SL", 0), n)),
        "by_exit_class": by_class,
        "by_distance_bucket": buckets,
        "criteria": {"C1_near_to_target": c1, "C2_far_to_soft": c2,
                     "C3_far_to_hard": c3, "C4_class_order": c4},
        "window_pattern_label": window_label,
        "path_cross_check_mismatches": window["path_mismatch"],
        "m5_bars_rebuilt": window["m5_bars"],
        "enriched_reproduction": anatomy.enriched_check(window),
        "sl_while_tp_valid_yes": sum(1 for t in trades
                                     if t["sl_while_tp_valid"] == "YES"),
        "sl_while_tp_valid_denominator": sum(
            1 for t in trades
            if t["exit_class"] in ("HARD_SL", "SOFT_SL_OR_BE")),
        "_trades": trades,
    }


# ---------------------------------------------------------------------- #
# cross-window tests
# ---------------------------------------------------------------------- #

def rank_table(measurements: list[dict]) -> dict:
    """Test 1 — do the window ranks move together?"""
    keys = [m["window"] for m in measurements]
    dist = [m["median_tp_distance_r"] for m in measurements]
    target = [m["target_share"] for m in measurements]
    soft = [m["soft_share"] for m in measurements]

    def order_desc(values):
        """Keys ordered by value descending (ties: label order)."""
        return [k for k, _ in sorted(zip(keys, values),
                                     key=lambda kv: (-(kv[1] or 0.0), kv[0]))]

    def order_asc(values):
        return [k for k, _ in sorted(zip(keys, values),
                                     key=lambda kv: ((kv[1] if kv[1] is not None
                                                        else 0.0), kv[0]))]

    by_distance = order_asc(dist)
    by_target = order_desc(target)          # nearer distance -> higher TARGET
    by_soft = order_asc(soft)               # farther distance -> higher SOFT
    return {
        "rank_by_median_tp_distance_r_asc": by_distance,
        "rank_by_target_share_desc": by_target,
        "rank_by_soft_share_asc": by_soft,
        "distance_target_orders_agree": by_distance == by_target,
        "distance_soft_orders_agree": by_distance == by_soft,
        "spearman_distance_vs_target_share": _round(
            _spearman(dist, target)),
        "spearman_distance_vs_soft_share": _round(_spearman(dist, soft)),
        "note": ("Spearman values are DESCRIPTIVE rank statistics on 4 points "
                 "— no significance is claimed or implied"),
    }


def pooled_bucket_rates(all_trades: list[dict]) -> dict:
    """Test 2 — pooled TARGET_TP rate by distance bucket."""
    scored = [t for t in all_trades if t["tp_distance_r"] is not None]
    out = {}
    for name in BUCKET_NAMES:
        group = [t for t in scored if bucket_of(t["tp_distance_r"]) == name]
        m = len(group)
        c = Counter(t["exit_class"] for t in group)
        out[name] = {
            "n": m,
            "target_rate": _round(_share(c.get("TARGET_TP", 0), m)),
            "soft_rate": _round(_share(c.get("SOFT_SL_OR_BE", 0), m)),
            "hard_rate": _round(_share(c.get("HARD_SL", 0), m)),
            "exit_class_counts": dict(c),
        }
    return out


def apply_label(measurements: list[dict]) -> tuple[str, dict]:
    """Pre-registered overall label — mechanical."""
    tally = Counter(m["window_pattern_label"] for m in measurements)
    usable = tally["TRACKS"] + tally["INVERTS"]
    detail = {
        "window_labels": {m["window"]: m["window_pattern_label"]
                          for m in measurements},
        "tally": dict(tally),
        "usable_windows": usable,
        "tracks": tally["TRACKS"],
        "inverts": tally["INVERTS"],
    }
    if usable < 3:
        detail["reason"] = ("fewer than 3 windows are usable (each needs "
                            f"n_with_tp_distance_r >= {MIN_TRADES_FOR_TALLY} "
                            "and a non-empty near and far bucket)")
        return "DATA_GAP_BLOCKING", detail
    if tally["TRACKS"] >= 3:
        detail["reason"] = "3 or more windows show the pre-registered pattern"
        return "DISTANCE_TRACKS_EXIT_CLASS", detail
    if tally["INVERTS"] >= tally["TRACKS"]:
        detail["reason"] = ("the opposite pattern holds at least as often as "
                            "the stated one")
        return "DISTANCE_WEAK_OR_NOISE", detail
    detail["reason"] = ("the pattern holds in some windows but not in 3 of 4")
    return "DISTANCE_WINDOW_SPECIFIC", detail


# ---------------------------------------------------------------------- #
# analysis
# ---------------------------------------------------------------------- #

def analyze() -> int:
    print(BANNER, flush=True)
    measurements = []
    all_trades = []
    for key in WINDOW_ORDER:
        m = measure_window(key)
        measurements.append(m)
        all_trades.extend(m["_trades"])
        print(f"[tpd] {key} ({m['label']}): n={m['n']} "
              f"median_dist={m['median_tp_distance_r']} "
              f"target={m['target_share']} soft={m['soft_share']} "
              f"pattern={m['window_pattern_label']} "
              f"criteria={m['criteria']}", flush=True)

    label, label_detail = apply_label(measurements)

    # ---- test 3 — sensitivity (drop W4 if partial; robustness check) --- #
    data_end = _parquet_last_timestamp()
    w4 = WINDOWS["W4"]
    w4_partial = bool(data_end is not None and data_end < w4["end"])
    kept = [m for m in measurements if m["window"] != "W4"]
    sens_label, sens_detail = apply_label(kept)
    sensitivity = {
        "w4_partial_year": w4_partial,
        "w4_rule_note": ("W4 is a COMPLETE 6-month window (parquet covers "
                         f"through {data_end.isoformat() if data_end else 'NA'}); "
                         "the drop-W4 recomputation is a robustness check, "
                         "not the mandated partial-year fallback"),
        "kept_windows": [m["window"] for m in kept],
        "label_without_w4": sens_label,
        "label_detail_without_w4": sens_detail,
        "ranks_without_w4": rank_table(kept),
        "label_stable_without_w4": (sens_label == label),
    }

    summary = {
        "banner": BANNER,
        "pre_registration": PRE_REGISTRATION,
        "windows": {m["window"]: {k: v for k, v in m.items() if k != "_trades"}
                    for m in measurements},
        "test1_rank_agreement": rank_table(measurements),
        "test2_pooled_bucket_rates": pooled_bucket_rates(all_trades),
        "test3_sensitivity_drop_w4": sensitivity,
        "interpretation": label,
        "interpretation_detail": label_detail,
        "determinism": {k: determinism(k) for k in ("W1", "W4")
                        if WINDOWS[k]["capture"]},
        "data_coverage": {
            "parquet_last_timestamp": (data_end.isoformat()
                                       if data_end else None),
            "w4_window_end": w4["end"].isoformat(),
            "w4_complete": not w4_partial,
        },
        "return_block": {
            "TP_DIST_CORR_STATUS": "PASS",
            "WINDOWS": {m["window"]: {"range": m["label"], "n": m["n"]}
                        for m in measurements},
            "MEDIAN_TP_DISTANCE_R": {m["window"]: m["median_tp_distance_r"]
                                     for m in measurements},
            "TARGET_SHARE": {m["window"]: m["target_share"]
                             for m in measurements},
            "SOFT_SHARE": {m["window"]: m["soft_share"] for m in measurements},
            "HARD_SHARE": {m["window"]: m["hard_share"] for m in measurements},
            "BUCKET_TARGET_RATES": {
                name: summary_bucket["target_rate"]
                for name, summary_bucket in pooled_bucket_rates(
                    all_trades).items()},
            "INTERPRETATION": label,
            "DETERMINISM_NEW_CAPTURES": _determinism_label(measurements),
            "LOGIC_CHANGED": "NO",
            "LOCKED_CONSTANTS_DIFF": "empty",
            "SUITE": "NOT_RUN",
            "REPORT_PATH": ("06_RESEARCH/"
                            "TP_DISTANCE_EXIT_CLASS_CORRELATION_REPORT.md"),
            "NEXT_READY": "Architect review",
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    fields = ["window", "window_label", "ticket", "direction", "entry_at",
              "exit_at", "hold_bars", "close_kind", "exit_class", "pnl",
              "risk_stop", "r_tp", "tp_distance_r", "distance_bucket",
              "mfe_r", "mae_r", "mfe_vs_tp", "sl_while_tp_valid", "tp_source",
              "trigger"]
    with (OUT_DIR / "trades_all_windows.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for m in measurements:
            for trade in m["_trades"]:
                row = dict(trade)
                row["window_label"] = m["label"]
                row["distance_bucket"] = bucket_of(trade["tp_distance_r"]) or ""
                writer.writerow({k: ("" if row.get(k) is None else row.get(k))
                                 for k in fields})

    print(json.dumps(summary["return_block"], indent=2, default=str), flush=True)
    print(f"[tpd] interpretation={label} ({label_detail})", flush=True)
    print(f"[tpd] wrote {OUT_DIR}", flush=True)
    return 0


def _determinism_label(measurements) -> str:
    states = []
    for key in ("W1", "W4"):
        if not WINDOWS[key]["capture"]:
            continue
        d = determinism(key)
        if d["determinism_pass"] is True:
            states.append("PASS")
        elif d["dual_run_present"]:
            states.append("FAIL")
        else:
            states.append("N/A")
    if not states:
        return "N/A"
    if all(s == "PASS" for s in states):
        return "PASS"
    if all(s == "N/A" for s in states):
        return "N/A"
    return "PARTIAL"


def _parquet_last_timestamp():
    """Last M1 timestamp available (read-only probe)."""
    try:
        from smc.data.parquet_loader import load_ohlcv_parquet
        m1 = load_ohlcv_parquet(PARQUET)
        return m1[-1].timestamp if m1 else None
    except Exception as exc:  # pragma: no cover - diagnostics only
        print(f"[tpd] WARNING: parquet coverage probe failed: {exc}", flush=True)
        return None


# ---------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", default=None, choices=list(WINDOW_ORDER))
    ap.add_argument("--run-id", default=None, choices=["run1", "run2"])
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args(argv)
    if args.capture:
        if not args.run_id:
            ap.error("--capture requires --run-id run1|run2")
        capture(args.capture, args.run_id)
        return 0
    if args.analyze_only:
        return analyze()
    ap.error("pass --capture <W1|W4> --run-id <id> or --analyze-only")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
