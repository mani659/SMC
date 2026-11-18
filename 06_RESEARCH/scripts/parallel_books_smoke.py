"""PARALLEL BOOKS — INTEGRATED SMOKE (research only, dry-run only).

Three checks on a SHORT FROZEN SLICE (never a year backtest):

1. **PROD parity** — shipped single menu vs ``parallel_books=["PROD"]`` over the
   same bars in the same process: winner identity, fill identity and the
   product-fill anchor must match exactly (spike-note method, trimmed window).
2. **F+B multi-book (dry_run)** — ``["F","B"]`` over the same slice: per-book
   tag purity (CROSS_TAG_LEAK must be NO), at least one book path exercised,
   zero UNWANTED cross-book double-lots, ``poi_outside_books`` sane, and the
   shared risk envelope never crashing (skips reported).
3. **R-L guardrail** — ``parallel_books`` + ``dry_run=false`` without
   ``allow_parallel_books_live`` is refused loudly at BOTH the config-load
   seam and the code-built ``_build_stack`` seam; ``dry_run=true`` needs no
   flag; the shipped default still carries no books.

Nothing here flips a production default, edits a locked constant or places an
order: the replay goes through the research runner with a counting order book,
and every artifact is written under the gitignored results tree.

Usage
-----
    python parallel_books_smoke.py --days 5
    python parallel_books_smoke.py --days 10 --hyp LONG
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "04_SRC"))
sys.path.insert(0, str(REPO / "06_RESEARCH" / "scripts"))

import parallel_book_spike as spike  # noqa: E402
from r1_pure_tag_books import (  # noqa: E402
    SEGMENTS,
    fail_loud,
    load_truth_directions,
    segment_series,
)

SMOKE_OUT = REPO / "06_RESEARCH" / "results" / "parallel_books_smoke"
BOOKS = ["F", "B"]


def _read_fills(run_dir: Path) -> list[dict]:
    path = run_dir / "fills.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _plan_key(row: dict) -> tuple:
    """Executable identity (direction/entry/SL/TP) — trigger EXCLUDED."""
    return (
        str(row.get("direction")),
        round(float(row.get("entry_price") or 0.0), 6),
        round(float(row.get("sl") or 0.0), 6),
        round(float(row.get("tp") or 0.0), 6),
    )


def _tag_letter(row: dict) -> str:
    return str(row.get("trigger") or "")[:1].upper()


def _book_checks(summary: dict, fills: list[dict]) -> dict:
    """CROSS_TAG_LEAK / exercise / double-lot / outside-books checks."""
    books = summary["selection"] or []
    per_book_triggers: dict[str, set] = defaultdict(set)
    for row in fills:
        per_book_triggers[str(row.get("book_id"))].add(_tag_letter(row))
    leaks = {
        book: sorted(seen - {book})
        for book, seen in per_book_triggers.items()
        if book in books and seen - {book}
    }
    unattributed = [r for r in fills if str(r.get("book_id")) not in books]

    # UNWANTED double-lot: the SAME executable plan filled by TWO books.
    owners: dict[tuple, set] = defaultdict(set)
    for row in fills:
        owners[_plan_key(row)].add(str(row.get("book_id")))
    doubles = {
        "|".join(repr(k) for k in key): sorted(books_)
        for key, books_ in owners.items()
        if len(books_) > 1
    }

    menu_counters = summary["menu_counters"]
    story_counters = summary["story_counters"]
    exercised = bool(
        summary["winners_total"] or summary["fills"] or fills
        or menu_counters.get("poi_routed", 0)
    )
    return {
        "selection": books,
        "winners_by_book": summary["winners_by_book"],
        "fills_by_book": summary["fills_by_book"],
        "winners_total": summary["winners_total"],
        "fills": summary["fills"],
        "per_book_triggers": {
            k: sorted(v) for k, v in per_book_triggers.items()
        },
        "cross_tag_leak": leaks or "NO",
        "unattributed_fills": len(unattributed),
        "books_exercised": exercised,
        "cross_book_duplicates_suppressed": summary["cross_book"][
            "duplicates"
        ],
        "cross_book_duplicate_events": summary["cross_book"]["events"],
        "adapter_duplicate_story_cross_book": story_counters.get(
            "duplicate_story_cross_book", 0
        ),
        "unwanted_double_lots": doubles,
        "poi_outside_books": menu_counters.get("poi_outside_books", 0),
        "blocked_by_reason": summary["blocked_by_reason"],
        "cross_opposite_direction": summary["cross_book"][
            "opposite_direction"
        ],
        "runtime_seconds": summary["runtime_seconds"],
    }


def _guardrail_checks() -> dict:
    """R-L at both seams + safe defaults. No terminal, no MT5 connection."""
    from smc.live.operator_config import (
        ConfigError,
        OperatorConfig,
        load_operator_config,
    )
    from smc.live.run_operator import OperatorSession

    tmp = Path(tempfile.mkdtemp(prefix="pb_smoke_"))
    path = tmp / "operator.json"

    path.write_text(json.dumps({"parallel_books": BOOKS, "dry_run": False}),
                    encoding="utf-8")
    try:
        load_operator_config(path)
        load_refusal = "NO REFUSAL (FAIL)"
    except ConfigError as exc:
        load_refusal = str(exc)

    # Dry-run multi-book must NOT require the flag.
    path.write_text(json.dumps({"parallel_books": BOOKS, "dry_run": True}),
                    encoding="utf-8")
    cfg_dry = load_operator_config(path)

    # Code-built config (scripts/tests bypass the file): _build_stack refuses.
    class _FakeConnector:
        def __getattr__(self, name):
            def _refuse(*a, **k):
                raise AssertionError(f"connector.{name} called before guard")
            return _refuse

    cfg_code = OperatorConfig(parallel_books=tuple(BOOKS), dry_run=False,
                              log_dir=str(tmp / "logs"))
    session = OperatorSession(cfg_code)
    session._connector = _FakeConnector()
    try:
        session._build_stack()
        stack_refusal = "NO REFUSAL (FAIL)"
    except SystemExit as exc:
        stack_refusal = str(exc)
    except Exception as exc:  # pragma: no cover - harness diagnostic
        stack_refusal = f"UNEXPECTED {type(exc).__name__}: {exc}"

    # Shipped default: no books, no flag, single-menu path.
    from smc.orchestration.parallel_books import resolve_book_selection
    shipped = load_operator_config(REPO / "config" / "live_demo.json")
    return {
        "config_load_refusal": load_refusal,
        "config_load_refused": "R-L" in load_refusal,
        "build_stack_refusal": stack_refusal,
        "build_stack_refused": stack_refusal.startswith("ABORT"),
        "dry_run_multi_book_loads": bool(
            cfg_dry.parallel_books and cfg_dry.dry_run
        ),
        "dry_run_needs_no_flag": cfg_dry.allow_parallel_books_live is False,
        "shipped_default_books": list(shipped.parallel_books),
        "shipped_default_resolves_empty": resolve_book_selection(
            shipped.parallel_books
        ) == (),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", default="feb25")
    ap.add_argument("--days", type=int, default=5,
                    help="trading-day slice length (short frozen window)")
    ap.add_argument("--hyp", default=None, choices=spike.HYPOTHESES)
    args = ap.parse_args()

    if args.segment not in SEGMENTS:
        fail_loud(f"unknown segment {args.segment!r}")
    if args.days <= 0 or args.days > 20:
        fail_loud("--days must be 1..20 (this is a smoke, not a backtest)")

    spike.OUT = SMOKE_OUT          # keep all artifacts in the smoke tree
    SMOKE_OUT.mkdir(parents=True, exist_ok=True)
    lo, hi = SEGMENTS[args.segment]
    t0 = time.perf_counter()
    series = segment_series(lo, hi)
    armed = spike._load_armed(args.segment)
    truth = load_truth_directions(args.segment)
    p_series, p_armed, anchor_until = spike._trim(series, armed, args.days)
    hyps = (args.hyp,) if args.hyp else spike.HYPOTHESES

    parity: dict = {}
    for hyp in hyps:
        parity[hyp] = spike._parity(
            args.segment, p_series, p_armed, truth, hyp,
            anchor_until=anchor_until,
        )

    books_runs: dict = {}
    for hyp in hyps:
        name = f"books_{args.segment}_F,B_{hyp}"
        summary = spike._run(
            args.segment, p_series, p_armed, truth, hyp=hyp,
            selection=list(BOOKS), run_dir=SMOKE_OUT / args.segment / name,
            label=name,
        )
        books_runs[hyp] = {
            "summary": summary,
            "checks": _book_checks(
                summary, _read_fills(SMOKE_OUT / args.segment / name)
            ),
        }

    guard = _guardrail_checks()

    parity_pass = all(run["pass"] for run in parity.values())
    book_checks = [run["checks"] for run in books_runs.values()]
    books_pass = all(
        c["cross_tag_leak"] == "NO"
        and c["unattributed_fills"] == 0
        and c["books_exercised"]
        and not c["unwanted_double_lots"]
        and c["poi_outside_books"] == 0
        for c in book_checks
    )
    guard_pass = bool(
        guard["config_load_refused"]
        and guard["build_stack_refused"]
        and guard["dry_run_multi_book_loads"]
        and guard["dry_run_needs_no_flag"]
        and guard["shipped_default_resolves_empty"]
        and not guard["shipped_default_books"]
    )

    verdict = {
        "smoke": "parallel_books_integrated",
        "diagnostic_only": True,
        "dry_run_only": True,
        "window": {
            "segment": args.segment,
            "trading_days": args.days,
            "anchor_until": anchor_until,
            "bars": len(p_series["m5"]),
            "definition": "product_1y armed universe, END-trimmed slice",
        },
        "hypotheses": list(hyps),
        "prod_parity": {
            "runs": {
                hyp: {k: v for k, v in run.items()
                      if k in ("winners_plain", "winners_prod_book",
                               "fills_plain", "fills_prod_book",
                               "winners_identical", "fills_identical",
                               "anchor_identical", "pass")}
                for hyp, run in parity.items()
            },
            "pass": parity_pass,
        },
        "fb_multi_book": {
            "runs": {
                hyp: {
                    "winners_by_book": run["checks"]["winners_by_book"],
                    "fills_by_book": run["checks"]["fills_by_book"],
                    "cross_tag_leak": run["checks"]["cross_tag_leak"],
                    "cross_book_duplicates_suppressed": run["checks"][
                        "cross_book_duplicates_suppressed"],
                    "adapter_duplicate_story_cross_book": run["checks"][
                        "adapter_duplicate_story_cross_book"],
                    "unwanted_double_lots": run["checks"][
                        "unwanted_double_lots"],
                    "poi_outside_books": run["checks"]["poi_outside_books"],
                    "blocked_by_reason": run["checks"]["blocked_by_reason"],
                    "cross_opposite_direction": run["checks"][
                        "cross_opposite_direction"],
                    "runtime_seconds": run["checks"]["runtime_seconds"],
                }
                for hyp, run in books_runs.items()
            },
            "pass": books_pass,
        },
        "guardrail": {**guard, "pass": guard_pass},
        "pass": parity_pass and books_pass and guard_pass,
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }
    (SMOKE_OUT / "verdict.json").write_text(
        json.dumps(verdict, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "pass": verdict["pass"],
        "prod_parity": parity_pass,
        "fb_multi_book": books_pass,
        "guardrail": guard_pass,
        "window": verdict["window"],
        "fb": verdict["fb_multi_book"]["runs"],
        "guard": {k: guard[k] for k in (
            "config_load_refusal", "build_stack_refusal",
            "dry_run_multi_book_loads", "dry_run_needs_no_flag",
            "shipped_default_books")},
        "runtime_seconds": verdict["runtime_seconds"],
    }, indent=2, default=str), flush=True)
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
