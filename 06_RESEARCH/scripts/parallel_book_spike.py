"""PARALLEL BOOK SPIKE — frozen-window measurement (research only).

Runs the production menu and/or dedicated confirmation books through the REAL
menu → adapter → runner seam on the product_1y armed universe (the same replay
seam R1 used), and reports:

* **default parity** — the shipped single menu vs ``books=["PROD"]`` replay in
  the SAME process over the same bars: winner identity and fill identity must
  match exactly (no unexplained regression), and the product-fill anchor counts
  must be equal;
* **per-book flow** — wins / emitted routes / fills per book, trigger mix,
  detection-TF mix (no edge claim);
* **cross-book safety** — ``cross_book_duplicates`` (identical executable plan
  from two books → one ticket), opposite-direction coexistence count, and
  cross-tag purity (fail loud).

Nothing here changes a production default: the books layer is constructed only
when a selection is passed, and the research artifacts are gitignored.

Usage
-----
    python parallel_book_spike.py --segment feb25 --mode parity --hyp LONG
    python parallel_book_spike.py --segment feb25 --mode books --selection F,B --hyp SHORT
    python parallel_book_spike.py --segment feb25 --all
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "04_SRC"))
sys.path.insert(0, str(REPO / "06_RESEARCH" / "scripts"))

from r1_pure_tag_books import (  # noqa: E402
    MENU_WARMUP_BARS,
    SRC,
    TF,
    CountingOrderBook,
    _s,
    fail_loud,
    fill_key,
    load_truth_directions,
    parse_models,
    segment_series,
    trade_row,
)

from smc.backtest.bar_loop import BarLoop  # noqa: E402
from smc.backtest.cost_model import CostConfig  # noqa: E402
from smc.backtest.data_feed import CandleSeries  # noqa: E402
from smc.backtest.export import to_csv  # noqa: E402
from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.backtest.positions import PositionStore  # noqa: E402
from smc.backtest.reports import build_report  # noqa: E402
from smc.backtest.runner import BacktestRunner, RunnerConfig  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.enums import Direction  # noqa: E402
from smc.core.poi import POI  # noqa: E402
from smc.core.zone import Zone  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.parallel_books import (  # noqa: E402
    ParallelBookMenu,
    resolve_book_selection,
)
from smc.orchestration.product_menu_mtf import ProductMenuEngine  # noqa: E402
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

OUT = REPO / "06_RESEARCH" / "results" / "parallel_book_spike"
HYPOTHESES = ("LONG", "SHORT")

_SRC = {
    Timeframe.D1: "d1", Timeframe.H4: "h4", Timeframe.H1: "h1",
    Timeframe.M15: "m15", Timeframe.M5: "m5", Timeframe.M1: "m1",
}


def _menu_streams(menu) -> dict:
    tfs = tuple(dict.fromkeys(
        (*menu.detection_timeframes, *menu.confirmation_timeframes)))
    return {tf: _SRC[tf] for tf in tfs}


def _load_armed(seg: str) -> list[dict]:
    armed = json.loads((SRC / seg / "armed_records.json").read_text(
        encoding="utf-8"))
    return [dict(rec, poi_id=pid) for pid, rec in armed.items()]


def _reconstruct(armed, m5, truth, hyp_dir, covered_tfs):
    """POI universe for the books under test (TRUE direction when known)."""
    pois: list[POI] = []
    by_arm: dict[int, list[POI]] = defaultdict(list)
    for rec in armed:
        det_tf = Timeframe[str(rec["detection_tf"]).upper()]
        if det_tf not in covered_tfs:
            continue
        idx = int(rec["armed_bar"])
        if not (0 <= idx < len(m5)):
            fail_loud(f"armed_bar {idx} out of range")
        direction = (
            Direction[truth[rec["poi_id"]].upper()]
            if rec["poi_id"] in truth else hyp_dir
        )
        poi = POI(
            zone=Zone(bottom=float(rec["zone_low"]), top=float(rec["zone_high"]),
                      direction=direction, timeframe=det_tf),
            models=parse_models(rec["model_tags"]), m8_kind=None,
            created_at=m5[idx].timestamp, id=rec["poi_id"],
        )
        pois.append(poi)
        by_arm[idx].append(poi)
    return pois, by_arm


def _trim(series: dict, armed: list[dict], days: int) -> tuple[dict, list[dict], str]:
    """Trim the END of the window (bar indexes stay valid for armed POIs)."""
    m5 = series["m5"]
    cut = min(len(m5), int(days) * 288)      # M5 bars per UTC day
    if cut >= len(m5):
        return series, armed, m5[-1].timestamp.isoformat()
    last = m5[cut - 1].timestamp
    trimmed = {"m5": m5[:cut]}
    for key, bars in series.items():
        if key == "m5":
            continue
        trimmed[key] = [c for c in bars if c.timestamp <= last]
    kept = [r for r in armed if int(r["armed_bar"]) < cut]
    return trimmed, kept, last.isoformat()


def _run(seg: str, series: dict, armed: list[dict], truth: dict,
         *, hyp: str, selection, run_dir: Path, label: str,
         anchor_until: str | None = None) -> dict:
    """One replay: the shipped single menu (selection None) or N books."""
    t0 = time.perf_counter()
    m5 = series["m5"]
    hyp_dir = Direction[hyp]
    books = resolve_book_selection(selection)
    if books:
        menu = ParallelBookMenu(books, symbol="XAUUSD", same_bar_asof=False)
        mode = "books"
    else:
        menu = ProductMenuEngine(symbol="XAUUSD", same_bar_asof=False)
        mode = "plain"

    covered = set(menu.detection_timeframes)
    pois, by_arm = _reconstruct(armed, m5, truth, hyp_dir, covered)
    if not pois:
        fail_loud(f"{seg}/{label}: no armed POIs for {sorted(t.name for t in covered)}")

    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=TF)
    adapter.set_candles(m5)
    adapter.set_menu_confirmation(menu)     # production §5 wiring (F6)

    menu_tfs = tuple(_menu_streams(menu))
    menu_series = {tf: series[_SRC[tf]] for tf in menu_tfs}
    menu_closes = {
        tf: [c.timestamp + timedelta(minutes=tf.minutes)
             for c in menu_series[tf]] for tf in menu_tfs
    }

    order_book = CountingOrderBook()
    runner = BacktestRunner(
        risk_engine=RiskEngine(), order_book=order_book,
        position_store=PositionStore(),
        config=RunnerConfig(
            equity=10_000.0, risk_fraction=0.01, pip_value_per_lot=10.0,
            min_lots=0.01, lot_step=0.01, spread_price=0.0, news_events=[],
            allowed_sessions=(Session.ASIA, Session.LONDON, Session.NEW_YORK),
            timeframe=TF, cost=CostConfig()),
    )
    adapter.attach(runner)

    winner_rows: list[dict] = []

    class Cycle:
        """phase3 Cycle minus the detection branch (menu-first law)."""

        def __init__(self, inner) -> None:
            self.inner = inner
            self.bars = 0
            self._menu_cursor: dict = {}

        def on_bar(self, bar, bar_index, clock) -> None:
            for poi in by_arm.get(bar_index, ()):
                engine.arm_at(poi, arm_bar=bar_index)
                menu.register_armed(poi, poi.zone.timeframe,
                                    armed_ts=bar.timestamp)
            as_of = bar.timestamp + timedelta(minutes=TF.minutes)
            closed: dict = {}
            for tf in menu_tfs:
                stamps = menu_closes[tf]
                end = bisect_right(stamps, as_of)
                start = self._menu_cursor.get(tf)
                if start is None:
                    start = max(0, end - MENU_WARMUP_BARS)
                self._menu_cursor[tf] = max(start, end)
                closed[tf] = menu_series[tf][start:end]
            winners = menu.on_execution_bar(closed, as_of=as_of)
            for winner in winners:
                adapter.queue_menu_candidate(winner.candidate)
                try:
                    stamp = json.loads(
                        winner.candidate.signal_data_json or "{}").get(
                        "product_menu", {})
                except (TypeError, ValueError):
                    stamp = {}
                winner_rows.append({
                    "poi_id": _s(winner.poi_id),
                    "trigger": _s(winner.trigger),
                    "sweep_ts": str(stamp.get("sweep_ts", "")),
                    "window_end_ts": str(stamp.get("window_end_ts", "")),
                    "book_id": stamp.get("book_id"),
                    "book_tag": stamp.get("book_tag"),
                })
            self.inner.on_bar(bar, bar_index, clock)
            self.bars += 1

    loop = BarLoop(CandleSeries(m5, TF), Cycle(runner))
    loop.run()

    result = runner.result()
    report = build_report(result)
    run_dir.mkdir(parents=True, exist_ok=True)
    to_csv(report, run_dir / "trades.csv")
    rows = [trade_row(t) for t in report.trades]

    # --- cross-tag purity (fail loud, per book) ---------------------------
    if hasattr(menu, "assert_tag_purity"):
        menu.assert_tag_purity()

    # --- book attribution -------------------------------------------------
    tag_to_book = {
        b.tag_letter: b.book_id for b in books if b.tag_letter is not None
    } if books else {}
    prod_book = any(b.book_id == "PROD" for b in books) if books else False

    def book_of(trigger: str) -> str:
        if trigger in tag_to_book:
            return tag_to_book[trigger]
        return "PROD" if (prod_book or mode == "plain") else "UNATTRIBUTED"

    fills_by_book = Counter(book_of(r["trigger"]) for r in rows)
    leak = [
        r for r in rows
        if book_of(r["trigger"]) == "UNATTRIBUTED"
    ]
    if leak:
        fail_loud(f"{seg}/{label}: unexplained fills {leak[:3]}")

    # --- product anchor (same rule as R1, single hypothesis) --------------
    anchors = {}
    with (SRC / seg / "trades.csv").open(newline="", encoding="utf-8") as fh:
        prod = [dict(r) for r in csv.DictReader(fh)]
    if anchor_until is not None:
        # Short parity slice: only product fills inside the slice are anchors.
        prod = [r for r in prod if str(r["entry_at"]) <= anchor_until]
    replay_keys = {fill_key(r) for r in rows}
    prod_keys = {fill_key(r) for r in prod}
    anchors = {
        "product_fills": len(prod),
        "replayed": len(rows),
        "missing_product_fills": len(prod_keys - replay_keys),
        "extra_fills": len(replay_keys - prod_keys),
    }

    summary = {
        "label": label,
        "mode": mode,
        "segment": seg,
        "direction_hypothesis": hyp,
        "selection": [b.book_id for b in books] if books else None,
        "books": [
            {"book_id": b.book_id, "tag": b.tag_letter,
             "tiers": list(b.detection_tiers),
             "confirm_tf_map": {tf.name: [c.name for c in ctfs]
                                for tf, ctfs in b.confirm_tf_map.items()}}
            for b in books
        ] if books else [{"book_id": "PROD", "tag": None, "tiers": "shipped"}],
        "diagnostic_only": True,
        "armed_pois": len(pois),
        "menu_episodes": (
            sum(len(menu.engine(b.book_id).episodes()) for b in books)
            if books else len(menu.episodes())
        ),
        "winners_total": len(winner_rows),
        "winners_by_book": dict(Counter(
            str(w["book_id"] or "PROD") for w in winner_rows)),
        "winners_by_trigger": dict(Counter(w["trigger"] for w in winner_rows)),
        "placed": order_book.placed,
        "placed_with_tp": order_book.placed_with_tp,
        "fills": len(rows),
        "fills_by_book": dict(fills_by_book),
        "trades_by_trigger": dict(Counter(r["trigger"] for r in rows)),
        "direction_mix": dict(Counter(r["direction"] for r in rows)),
        "detection_tf_mix": dict(Counter(r["detection_tf"] or "?" for r in rows)),
        "pnl_net_sum": round(sum(float(r["pnl_net"]) for r in rows), 6),
        "blocked_by_reason": getattr(report, "blocked_by_reason", {}) or {},
        # M-4: per-book attribution (book_id → reason → count); {} on legacy.
        "blocked_by_book": getattr(report, "blocked_by_book", {}) or {},
        "story_counters": adapter.story_counters(),
        "menu_counters": adapter.menu_counters(),
        "cross_book": (
            {
                "duplicates": menu.counters()["cross_book_duplicates"],
                "opposite_direction": menu.counters()["cross_opposite_direction"],
                "events": list(menu.cross_book_events()),
                "per_book": menu.book_stats(),
            } if books else None
        ),
        "anchor": anchors,
        "menu_bar_count": len(m5),
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    if rows:
        cols = list(rows[0].keys()) + ["book_id"]
        with (run_dir / "fills.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=cols)
            writer.writeheader()
            for row in rows:
                writer.writerow({**row, "book_id": book_of(row["trigger"])})
    winner_keys = {(w["poi_id"], w["trigger"], w["sweep_ts"])
                   for w in winner_rows}
    (run_dir / "winners.json").write_text(json.dumps({
        "winners": winner_rows,
        "winner_keys": sorted(winner_keys),
    }, indent=2, default=str), encoding="utf-8")
    print(f"[parallel-spike] {seg} {label} ({hyp}): armed {len(pois)} "
          f"winners {len(winner_rows)} fills {len(rows)} "
          f"({summary['runtime_seconds']}s)", flush=True)
    return summary


def _parity(seg: str, series: dict, armed, truth, hyp: str,
            anchor_until: str | None = None) -> dict:
    """Shipped single menu vs books=["PROD"], same process, same bars."""
    plain = _run(seg, series, armed, truth, hyp=hyp, selection=None,
                 run_dir=OUT / seg / f"parity_plain_{hyp}", label=f"plain_{hyp}",
                 anchor_until=anchor_until)
    prod = _run(seg, series, armed, truth, hyp=hyp, selection=["PROD"],
                run_dir=OUT / seg / f"parity_prod_book_{hyp}",
                label=f"prod_book_{hyp}", anchor_until=anchor_until)

    def keys(run_dir_name: str, kind: str) -> set:
        if kind == "winners":
            payload = json.loads(
                (OUT / seg / run_dir_name / "winners.json").read_text(
                    encoding="utf-8"))
            return {tuple(k) for k in payload["winner_keys"]}
        with (OUT / seg / run_dir_name / "fills.csv").open(
                newline="", encoding="utf-8") as fh:
            # book_id is an added column; identity columns are unchanged.
            return {fill_key(row) for row in csv.DictReader(fh)}

    plain_w = keys(f"parity_plain_{hyp}", "winners")
    prod_w = keys(f"parity_prod_book_{hyp}", "winners")
    plain_f = keys(f"parity_plain_{hyp}", "fills")
    prod_f = keys(f"parity_prod_book_{hyp}", "fills")
    diff = {
        "winners_only_plain": sorted(plain_w - prod_w)[:5],
        "winners_only_prod_book": sorted(prod_w - plain_w)[:5],
        "fills_only_plain": sorted(plain_f - prod_f)[:5],
        "fills_only_prod_book": sorted(prod_f - plain_f)[:5],
    }
    parity = {
        "segment": seg,
        "direction_hypothesis": hyp,
        "anchor_until": anchor_until,
        "winners_plain": len(plain_w),
        "winners_prod_book": len(prod_w),
        "fills_plain": len(plain_f),
        "fills_prod_book": len(prod_f),
        "winners_identical": plain_w == prod_w,
        "fills_identical": plain_f == prod_f,
        "anchor_plain": plain["anchor"],
        "anchor_prod_book": prod["anchor"],
        "anchor_identical": plain["anchor"] == prod["anchor"],
        "differences": diff,
        "pass": plain_w == prod_w and plain_f == prod_f
        and plain["anchor"] == prod["anchor"],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"parity_{seg}_{hyp}.json").write_text(
        json.dumps(parity, indent=2, default=str), encoding="utf-8")
    print(f"[parallel-spike] parity {seg} {hyp}: "
          f"{'PASS' if parity['pass'] else 'FAIL'} "
          f"(winners {len(plain_w)}/{len(prod_w)}, fills "
          f"{len(plain_f)}/{len(prod_f)})", flush=True)
    return parity


def aggregate(seg: str, selection: str) -> dict:
    """Union fills/winners across hypotheses; per-book totals."""
    OUT.mkdir(parents=True, exist_ok=True)
    runs = {}
    fills: list[dict] = []
    winners: list[dict] = []
    for hyp in HYPOTHESES:
        run_dir = OUT / seg / f"books_{selection}_{hyp}"
        path = run_dir / "summary.json"
        if not path.exists():
            fail_loud(f"missing run artifact: {path}")
        runs[hyp] = json.loads(path.read_text(encoding="utf-8"))
        with (run_dir / "fills.csv").open(newline="", encoding="utf-8") as fh:
            fills.extend(dict(r) for r in csv.DictReader(fh))
        winners.extend(
            json.loads((run_dir / "winners.json").read_text(
                encoding="utf-8"))["winners"])

    uniq: dict[tuple, dict] = {}
    for row in fills:
        uniq.setdefault(fill_key(row), row)
    uniq_w: dict[tuple, dict] = {}
    for row in winners:
        uniq_w.setdefault(
            (row["poi_id"], row["trigger"], row["sweep_ts"]), row)

    summary = {
        "spike": "parallel_dedicated_books",
        "diagnostic_only": True,
        "window": {"segment": seg,
                   "definition": "product_1y segment (exec month, UTC)"},
        "selection": selection,
        "method": (
            "product_1y armed universe replayed through the real menu -> "
            "adapter -> runner seam; each book is a MenuTier set with "
            "trigger_types=(tag,); one shared broker/runner/RiskEngine"),
        "runs": runs,
        "winners_by_book": dict(Counter(
            str(w.get("book_id") or "PROD") for w in uniq_w.values())),
        "fills_unique": len(uniq),
        "fills_by_book": dict(Counter(r["book_id"] for r in uniq.values())),
        "trades_by_trigger": dict(Counter(r["trigger"] for r in uniq.values())),
        "detection_tf_mix": dict(Counter(
            r["detection_tf"] or "?" for r in uniq.values())),
        "cross_book_duplicates": sum(
            (r["cross_book"] or {}).get("duplicates", 0)
            for r in runs.values()),
        "cross_opposite_direction": sum(
            (r["cross_book"] or {}).get("opposite_direction", 0)
            for r in runs.values()),
        "skip_reasons": {
            hyp: r["blocked_by_reason"] for hyp, r in runs.items()
        },
        "story_counters": {hyp: r["story_counters"] for hyp, r in runs.items()},
        "tag_purity": "PASS (each book's filled trigger mix is its own tag)",
        "runtime_seconds": round(
            sum(r["runtime_seconds"] for r in runs.values()), 1),
    }
    (OUT / f"summary_{seg}_{selection}.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"[parallel-spike] aggregate {seg} {selection}: "
          f"fills {summary['fills_unique']} by book {summary['fills_by_book']} "
          f"dupes {summary['cross_book_duplicates']}", flush=True)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", default="feb25")
    ap.add_argument("--mode", choices=("parity", "books", "all"), default="all")
    ap.add_argument("--selection", default="F,B")
    ap.add_argument("--hyp", choices=HYPOTHESES, default=None)
    ap.add_argument("--parity-days", type=int, default=None,
                    help="trim the parity window to N trading days (smoke)")
    ap.add_argument("--aggregate-only", action="store_true")
    args = ap.parse_args()

    if args.aggregate_only:
        aggregate(args.segment, args.selection)
        return 0

    from r1_pure_tag_books import SEGMENTS

    if args.segment not in SEGMENTS:
        fail_loud(f"unknown segment {args.segment!r}")
    lo, hi = SEGMENTS[args.segment]
    t0 = time.perf_counter()
    series = segment_series(lo, hi)
    armed = _load_armed(args.segment)
    truth = load_truth_directions(args.segment)
    hyps = (args.hyp,) if args.hyp else HYPOTHESES

    if args.mode in ("parity", "all"):
        p_series, p_armed, anchor_until = (
            _trim(series, armed, args.parity_days)
            if args.parity_days else (series, armed, None)
        )
        for hyp in hyps:
            _parity(args.segment, p_series, p_armed, truth, hyp,
                    anchor_until=anchor_until)
    if args.mode in ("books", "all"):
        for hyp in hyps:
            _run(args.segment, series, armed, truth, hyp=hyp,
                 selection=args.selection.split(","),
                 run_dir=OUT / args.segment / f"books_{args.selection}_{hyp}",
                 label=f"books_{args.selection}_{hyp}")
        if len(hyps) == len(HYPOTHESES):
            aggregate(args.segment, args.selection)
    print(f"[parallel-spike] total {round(time.perf_counter() - t0, 1)}s",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
