"""PARALLEL BOOKS — FULL RESEARCH BACKTEST (measurement only, detached-safe).

Runs the Architect's promote ruling (books ``F, B, C, E, A``, ``D`` excluded,
geometry = design/spike presets, shared risk envelope, cross-book dedupe ON,
one story PER BOOK) over the full product_1y window:

    exec  2024-11-01 .. 2025-10-31 UTC   (load warm-up 2024-09-01, as product_1y)

Window shape (sanctioned, not a shortcut)
-----------------------------------------
The continuous single-menu year replay is documented infeasible
(``PRODUCT_1Y_ONE_STORY_DIAGNOSTIC_REPORT.md`` §1.1: quadratic menu-bookkeeping
collapse, 26.1 -> 2.5 bars/s by bar 6,000, killed at the 45-min budget with
<10% covered). This harness therefore uses the SAME **12 adjacent calendar-
month segments** that tile the year exactly, through the SAME real
menu -> adapter -> runner seam the spike and smoke used, each segment loading
warm-up from 2024-09-01. Fills are unique-timestamp events, so segment fill
sums add; armed/episode counts do NOT (menu state restarts per segment) and are
reported per segment, never summed as a year total.

Controls (per segment, automatic)
---------------------------------
Every run writes its own product anchor versus that segment's product_1y
``trades.csv`` (``missing_product_fills`` must be 0: no product fill may be
lost by running dedicated books; extra fills are EXPECTED and are the books'
own flow).

Checks (fail loud, verdict-blocking)
------------------------------------
* ``CROSS_TAG_LEAK`` — each book's filled trigger mix must be its own tag.
* unattributed fills — every fill carries a selected book id.
* cross-book double-lot — no executable plan (direction/entry/SL/TP) filled by
  two books at the same instant (the union is deduped by fill identity).
* ``poi_outside_books`` — 0 expected (book F carries every tier).
* all selected books exercised (>= 1 fill over the year).

Nothing here flips a production default, edits a locked constant or places an
order: the replay goes through the research runner with a counting order book,
and every artifact lands under the gitignored results tree.

Detached use (never block the agent session)
--------------------------------------------
    powershell -ExecutionPolicy Bypass -File 06_RESEARCH/scripts/parallel_books_full_bt_launch.ps1
    python parallel_books_full_bt.py --days 3 --out 06_RESEARCH/results/parallel_books_full_bt/_preflight

Resume
------
Completed runs are marked with a ``.done`` file next to their ``summary.json``.
Re-running the same command resumes (skips them) — it never re-runs a finished
run. ``verdict.json`` and ``EXIT_CODE.txt`` are written by the process that
finishes the last run.
"""

from __future__ import annotations

import argparse
import atexit
import csv
import json
import os
import sys
import threading
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "04_SRC"))
sys.path.insert(0, str(REPO / "06_RESEARCH" / "scripts"))

import parallel_book_spike as spike  # noqa: E402
from r1_pure_tag_books import (  # noqa: E402
    SEGMENTS,
    SRC,
    fail_loud,
    fill_key,
    load_truth_directions,
    segment_series,
)

OUT = REPO / "06_RESEARCH" / "results" / "parallel_books_full_bt"
BOOKS = ("F", "B", "C", "E", "A")
SEG_ORDER = ("nov24", "dec24", "jan25", "feb25", "mar25", "apr25",
             "may25", "jun25", "jul25", "aug25", "sep25", "oct25")
HYPOTHESES = ("LONG", "SHORT")
WINDOW = {"exec_from": "2024-11-01", "exec_to": "2025-10-31",
          "load_from": "2024-09-01", "tz": "UTC"}

_CURRENT: dict = {"phase": "init", "run": None, "runs_done": 0,
                  "runs_total": 0, "started_utc": None}
_STATE_LOCK = threading.Lock()
_OUT_DIR: Path = OUT


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _read_fills(run_dir: Path) -> list[dict]:
    path = run_dir / "fills.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _plan_key(row: dict) -> tuple:
    """Executable identity (trigger EXCLUDED) — the double-lot test."""
    return (
        str(row.get("direction")),
        round(float(row.get("entry_price") or 0.0), 6),
        round(float(row.get("sl") or 0.0), 6),
        round(float(row.get("tp") or 0.0), 6),
        str(row.get("entry_at")),
    )


def _tag_letter(row: dict) -> str:
    return str(row.get("trigger") or "")[:1].upper()


# --------------------------------------------------------------------------- #
# Heartbeat (separate thread: proof of life while a long run is in memory)
# --------------------------------------------------------------------------- #
def _start_heartbeat(out: Path, interval: float = 20.0) -> threading.Event:
    stop = threading.Event()
    pid = os.getpid()

    def _beat() -> None:
        while not stop.wait(interval):
            with _STATE_LOCK:
                payload = dict(_CURRENT)
            payload.update({"pid": pid, "utc": _now(), "alive": True})
            try:
                _write_json(out / "heartbeat.json", payload)
            except OSError:
                pass  # never kill the run for a heartbeat write

    thread = threading.Thread(target=_beat, name="pb-heartbeat", daemon=True)
    thread.start()
    return stop


# --------------------------------------------------------------------------- #
# One segment / hypothesis → per-book + per-run metrics
# --------------------------------------------------------------------------- #
def _book_block(summary: dict, fills: list[dict]) -> dict:
    books = summary["selection"] or []
    per_book_engine = (summary.get("cross_book") or {}).get("per_book") or {}
    blocks: dict = {}
    for book in books:
        rows = [r for r in fills if str(r.get("book_id")) == book]
        engine = (per_book_engine.get(book) or {}).get("counters") or {}
        stats = per_book_engine.get(book) or {}
        blocks[book] = {
            # armed / scans (menu restarts per segment: never summed as a year)
            "armed_pois": engine.get("armed_pois", stats.get("armed_pois")),
            "detection_bars_seen": engine.get("detection_bars_seen"),
            "confirm_bars_evaluated": engine.get("confirm_bars_evaluated"),
            "sweeps_total": engine.get("sweeps_total"),
            "episodes_opened": engine.get("episodes_opened"),
            "episodes_expired": engine.get("episodes_expired"),
            # routes / fills
            "routes": stats.get("winners"),
            "emitted": stats.get("emitted"),
            "fills": len(rows),
            "trigger_mix": dict(Counter(_tag_letter(r) for r in rows)),
            "detection_tf_mix": dict(Counter(
                r.get("detection_tf") or "?" for r in rows)),
            "direction_mix": dict(Counter(r.get("direction") for r in rows)),
            "pnl_net_sum_diagnostic": round(
                sum(float(r.get("pnl_net") or 0.0) for r in rows), 6),
        }
    return blocks


def _run_checks(summary: dict, fills: list[dict]) -> dict:
    books = summary["selection"] or []
    leaks: dict = {}
    for book in books:
        seen = {_tag_letter(r) for r in fills if str(r.get("book_id")) == book}
        leak = sorted(seen - {book})
        if leak:
            leaks[book] = leak
    unattributed = [r for r in fills if str(r.get("book_id")) not in books]
    owners: dict[tuple, set] = defaultdict(set)
    for row in fills:
        owners[_plan_key(row)].add(str(row.get("book_id")))
    doubles = {
        "|".join(repr(k) for k in key): sorted(v)
        for key, v in owners.items() if len(v) > 1
    }
    menu_counters = summary.get("menu_counters") or {}
    story_counters = summary.get("story_counters") or {}
    cross = summary.get("cross_book") or {}
    return {
        "cross_tag_leak": leaks or "NO",
        "unattributed_fills": len(unattributed),
        "unwanted_double_lots": doubles,
        "cross_book_duplicates_suppressed": (cross.get("duplicates") or 0),
        "adapter_duplicate_story_cross_book": story_counters.get(
            "duplicate_story_cross_book", 0),
        "adapter_duplicate_story_menu": story_counters.get(
            "duplicate_story_menu", 0),
        "poi_outside_books": menu_counters.get("poi_outside_books", 0),
        "cross_opposite_direction": cross.get("opposite_direction") or 0,
        "shared_risk_skips": summary.get("blocked_by_reason") or {},
        # M-4: book_id → reason → count (empty on legacy/unstamped runs).
        "shared_risk_skips_by_book": summary.get("blocked_by_book") or {},
        "anchor": summary.get("anchor") or {},
    }


def _run_one(seg: str, hyp: str, books: list[str], series: dict,
             armed: list[dict], truth: dict, out: Path,
             anchor_until: str | None = None) -> dict:
    name = f"books_{'-'.join(books)}_{hyp}"
    run_dir = out / seg / name
    done = run_dir / ".done"
    if done.exists() and not _CURRENT.get("force"):
        prev = json.loads(done.read_text(encoding="utf-8"))
        print(f"[pb-full] skip (done) {seg} {name}", flush=True)
        return prev
    with _STATE_LOCK:
        _CURRENT["phase"] = "replay"
        _CURRENT["run"] = f"{seg}/{name}"
    t0 = time.perf_counter()
    summary = spike._run(
        seg, series, armed, truth, hyp=hyp, selection=list(books),
        run_dir=run_dir, label=name, anchor_until=anchor_until,
    )
    fills = _read_fills(run_dir)
    payload = {
        "segment": seg,
        "hypothesis": hyp,
        "run": name,
        "finished_utc": _now(),
        "runtime_seconds": round(time.perf_counter() - t0, 1),
        "selection": summary["selection"],
        "armed_pois_covered": summary["armed_pois"],
        "winners_total": summary["winners_total"],
        "winners_by_book": summary["winners_by_book"],
        "winners_by_trigger": summary["winners_by_trigger"],
        "placed": summary["placed"],
        "placed_with_tp": summary["placed_with_tp"],
        "fills": summary["fills"],
        "fills_by_book": summary["fills_by_book"],
        "trades_by_trigger": summary["trades_by_trigger"],
        "detection_tf_mix": summary["detection_tf_mix"],
        "direction_mix": summary["direction_mix"],
        "pnl_net_sum_diagnostic": summary["pnl_net_sum"],
        "books": _book_block(summary, fills),
        "checks": _run_checks(summary, fills),
        "story_counters": summary["story_counters"],
        "menu_counters": summary["menu_counters"],
        "menu_bar_count": summary["menu_bar_count"],
    }
    if payload["checks"]["cross_tag_leak"] != "NO":
        fail_loud(f"{seg}/{name}: CROSS_TAG_LEAK {payload['checks']['cross_tag_leak']}")
    _write_json(run_dir / "run_metrics.json", payload)
    done.write_text(json.dumps(payload, default=str), encoding="utf-8")
    with _STATE_LOCK:
        _CURRENT["runs_done"] = int(_CURRENT.get("runs_done", 0)) + 1
    print(f"[pb-full] {seg} {name}: fills {payload['fills']} "
          f"by book {payload['fills_by_book']} "
          f"dupes {payload['checks']['cross_book_duplicates_suppressed']} "
          f"({payload['runtime_seconds']}s)", flush=True)
    return payload


# --------------------------------------------------------------------------- #
# Aggregation / verdict
# --------------------------------------------------------------------------- #
def _aggregate(out: Path, books: list[str], segs: list[str],
               hyps: list[str]) -> dict:
    runs: dict = {}
    missing: list[str] = []
    fills_union: dict = {}
    winners_union: dict = {}
    for seg in segs:
        for hyp in hyps:
            name = f"books_{'-'.join(books)}_{hyp}"
            done = out / seg / name / ".done"
            if not done.exists():
                missing.append(f"{seg}/{name}")
                continue
            payload = json.loads(done.read_text(encoding="utf-8"))
            runs[f"{seg}/{hyp}"] = payload
            for row in _read_fills(out / seg / name):
                fills_union.setdefault(fill_key(row), row)
            wpath = out / seg / name / "winners.json"
            if wpath.exists():
                for w in json.loads(wpath.read_text(encoding="utf-8"))["winners"]:
                    winners_union.setdefault(
                        (seg, w["poi_id"], w["trigger"], w["sweep_ts"]), w)

    fills_by_book = Counter(str(r.get("book_id")) for r in fills_union.values())
    routes_by_book = Counter(
        str(w.get("book_id") or "PROD") for w in winners_union.values())
    trigger_mix = Counter(_tag_letter(r) for r in fills_union.values())
    per_book = {}
    for book in books:
        rows = [r for r in fills_union.values()
                if str(r.get("book_id")) == book]
        per_book[book] = {
            "fills": len(rows),
            "routes": routes_by_book.get(book, 0),
            "trigger_mix": dict(Counter(_tag_letter(r) for r in rows)),
            "detection_tf_mix": dict(Counter(
                r.get("detection_tf") or "?" for r in rows)),
            "direction_mix": dict(Counter(r.get("direction") for r in rows)),
            "pnl_net_sum_diagnostic": round(
                sum(float(r.get("pnl_net") or 0.0) for r in rows), 6),
        }
    duplicate_skips = sum(
        r["checks"]["cross_book_duplicates_suppressed"] for r in runs.values())
    adapter_dupes = sum(
        r["checks"]["adapter_duplicate_story_cross_book"] for r in runs.values())
    outside = sum(r["checks"]["poi_outside_books"] for r in runs.values())
    risk_skips: Counter = Counter()
    risk_skips_by_book: dict = {}
    anchors_lost: list = []
    for key, run in runs.items():
        risk_skips.update(run["checks"]["shared_risk_skips"] or {})
        for book, reasons in (run["checks"].get("shared_risk_skips_by_book") or {}).items():
            risk_skips_by_book.setdefault(book, Counter()).update(reasons or {})
        anchor = run["checks"]["anchor"] or {}
        if anchor.get("missing_product_fills"):
            anchors_lost.append({
                "run": key,
                "missing_product_fills": anchor.get("missing_product_fills"),
                "product_fills": anchor.get("product_fills"),
                "replayed": anchor.get("replayed"),
            })
    leaks = {k: r["checks"]["cross_tag_leak"] for k, r in runs.items()
             if r["checks"]["cross_tag_leak"] != "NO"}
    unattributed = sum(r["checks"]["unattributed_fills"] for r in runs.values())
    doubles: dict = {}
    for key, run in runs.items():
        for plan, owners in (run["checks"]["unwanted_double_lots"] or {}).items():
            doubles.setdefault(plan, set()).update(owners)
    doubles = {k: sorted(v) for k, v in doubles.items()}
    exercised = {b: per_book[b]["fills"] > 0 for b in books}
    checks = {
        "cross_tag_leak_no": not leaks,
        "unattributed_zero": unattributed == 0,
        "no_cross_book_double_lot": not doubles,
        "poi_outside_books_zero": outside == 0,
        "all_books_exercised": all(exercised.values()),
        "no_product_fill_lost": not anchors_lost,
        "all_runs_present": not missing,
    }
    return {
        "backtest": "parallel_books_full_year",
        "diagnostic_only": True,
        "not_performance": ("pnl_net_sum_diagnostic is an accounting residue, "
                            "NEVER a performance claim"),
        "window": {**WINDOW, "segments": segs,
                   "shape": "12 adjacent calendar-month segments tiling the "
                            "year (continuous year replay documented "
                            "infeasible: PRODUCT_1Y report §1.1)"},
        "books": books,
        "hypotheses": hyps,
        "runs_present": len(runs),
        "runs_expected": len(segs) * len(hyps),
        "runs_missing": missing,
        "fills_union": len(fills_union),
        "fills_by_book": dict(fills_by_book),
        "fills_by_trigger": dict(trigger_mix),
        "routes_union": len(winners_union),
        "routes_by_book": dict(routes_by_book),
        "per_book": per_book,
        "winners_by_book_raw_sum_not_year": dict(Counter(
            b for r in runs.values()
            for b, n in (r["winners_by_book"] or {}).items() for _ in range(n))),
        "cross_book_duplicate_skips": duplicate_skips,
        "adapter_duplicate_story_cross_book": adapter_dupes,
        "poi_outside_books": outside,
        "shared_risk_skips": dict(risk_skips),
        "shared_risk_skips_by_book": {
            b: dict(c) for b, c in sorted(risk_skips_by_book.items())},
        "cross_opposite_direction": sum(
            r["checks"]["cross_opposite_direction"] for r in runs.values()),
        "cross_tag_leak": leaks or "NO",
        "unattributed_fills": unattributed,
        "unwanted_double_lots": doubles,
        "product_anchor_losses": anchors_lost,
        "books_exercised": exercised,
        "checks": checks,
        "pass": all(checks.values()),
        "runtime_seconds_total": round(
            sum(r["runtime_seconds"] for r in runs.values()), 1),
        "generated_utc": _now(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", default=",".join(BOOKS))
    ap.add_argument("--segments", default=",".join(SEG_ORDER))
    ap.add_argument("--hyps", default=",".join(HYPOTHESES))
    ap.add_argument("--days", type=int, default=0,
                    help="preflight: trim every segment to N trading days")
    ap.add_argument("--out", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = Path(args.out) if args.out else OUT
    out = out if out.is_absolute() else REPO / out
    out.mkdir(parents=True, exist_ok=True)
    global _OUT_DIR
    _OUT_DIR = out
    books = [b.strip().upper() for b in args.books.split(",") if b.strip()]
    segs = [s.strip() for s in args.segments.split(",") if s.strip()]
    hyps = [h.strip().upper() for h in args.hyps.split(",") if h.strip()]
    if not books or not segs or not hyps:
        fail_loud("books/segments/hyps must be non-empty")
    if "D" in books:
        fail_loud("book D is excluded (R-K)")
    for seg in segs:
        if seg not in SEGMENTS:
            fail_loud(f"unknown segment {seg!r}")
        if not (SRC / seg / "armed_records.json").exists():
            fail_loud(f"missing product_1y armed universe: {SRC / seg}")

    with _STATE_LOCK:
        _CURRENT.update({"runs_total": len(segs) * len(hyps),
                         "runs_done": 0, "started_utc": _now(),
                         "phase": "start", "force": args.force})
    (out / "pid.txt").write_text(str(os.getpid()), encoding="utf-8")
    _write_json(out / "progress.json", {
        **_CURRENT, "pid": os.getpid(), "books": books,
        "segments": segs, "hypotheses": hyps, "window": WINDOW,
    })
    stop = _start_heartbeat(out)
    atexit.register(stop.set)

    # Shipped default must stay single-menu (no silent production change).
    from smc.live.operator_config import load_operator_config
    from smc.orchestration.parallel_books import resolve_book_selection
    shipped = load_operator_config(REPO / "config" / "live_demo.json")
    shipped_books = list(shipped.parallel_books)
    if shipped_books or resolve_book_selection(shipped.parallel_books) != ():
        fail_loud(f"shipped default carries books: {shipped_books}")
    print(f"[pb-full] books={books} segments={segs} hyps={hyps} "
          f"out={out} shipped_default_books={shipped_books}", flush=True)

    results: dict = {}
    for seg in segs:
        lo, hi = SEGMENTS[seg]
        with _STATE_LOCK:
            _CURRENT.update({"phase": "load", "run": f"{seg}/load"})
        series = segment_series(lo, hi)
        armed = spike._load_armed(seg)
        truth = load_truth_directions(seg)
        anchor_until = None
        if args.days:
            series, armed, anchor_until = spike._trim(series, armed, args.days)
            # ``_trim`` returns ISO with "T"; product_1y trades.csv writes
            # "YYYY-MM-DD HH:MM:SS+00:00". The anchor filter is a STRING
            # compare, and " " < "T" would let same-day later product fills
            # into a trimmed slice — normalise the separator.
            anchor_until = anchor_until.replace("T", " ", 1)
        with _STATE_LOCK:
            _CURRENT["phase"] = "replay"
        for hyp in hyps:
            results[f"{seg}/{hyp}"] = _run_one(
                seg, hyp, books, series, armed, truth, out,
                anchor_until=anchor_until)

    with _STATE_LOCK:
        _CURRENT["phase"] = "aggregate"
    verdict = _aggregate(out, books, segs, hyps)
    if args.days:
        verdict["preflight"] = {
            "days_per_segment": args.days,
            "note": ("slice preflight: the product anchor is restricted to "
                     "in-slice fills, and the per-book exercise gate is not "
                     "meaningful on a few days — this is a seam check, not "
                     "the year result"),
        }
    _write_json(out / "verdict.json", verdict)
    (out / "progress.json").write_text(json.dumps({
        **_CURRENT, "pid": os.getpid(), "books": books,
        "segments": segs, "hypotheses": hyps,
        "finished_utc": _now(),
    }, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "pass": verdict["pass"],
        "runs": f"{verdict['runs_present']}/{verdict['runs_expected']}",
        "fills_union": verdict["fills_union"],
        "fills_by_book": verdict["fills_by_book"],
        "routes_by_book": verdict["routes_by_book"],
        "cross_book_duplicate_skips": verdict["cross_book_duplicate_skips"],
        "poi_outside_books": verdict["poi_outside_books"],
        "shared_risk_skips": verdict["shared_risk_skips"],
        "checks": verdict["checks"],
        "runtime_seconds_total": verdict["runtime_seconds_total"],
    }, indent=2, default=str), flush=True)
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    code = 2
    try:
        code = main()
    except SystemExit as exc:  # fail_loud
        print(f"[pb-full] ABORT: {exc}", flush=True)
        code = 2
    except Exception:  # noqa: BLE001 - persist the traceback for the resume
        traceback.print_exc()
        try:
            (_OUT_DIR / "traceback.log").write_text(traceback.format_exc(),
                                                    encoding="utf-8")
        except OSError:
            pass
        code = 1
    finally:
        _CURRENT["phase"] = "exit"
        _CURRENT["exit_code"] = code
        _write_json(_OUT_DIR / "heartbeat.json", {**_CURRENT, "pid": os.getpid(),
                                                  "utc": _now(), "alive": False})
        try:
            (_OUT_DIR / "EXIT_CODE.txt").write_text(str(code), encoding="utf-8")
        except OSError:
            pass
    raise SystemExit(code)
