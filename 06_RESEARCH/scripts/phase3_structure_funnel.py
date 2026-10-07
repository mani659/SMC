"""Phase 3 — structure funnel + information-flow audit on the unified machine.

Drives the PRODUCT multi-TF path — the C1 seam ``MultiTFProductRuntime``
driving batches at the new-H1-close cadence into a real ``PipelineEngine``,
with the same arm/scan/risk wiring the FR-4 fidelity baseline uses — over a
LOCKED short window, and records:

1. **Funnel** (machine-readable JSON): detected_raw per TF → merged →
   pillar first-failure histogram → passed → armed (per TF + M8) → scans →
   routes (by trigger) → placed / intents (armed/placed/expired) → fills →
   trades. Counters come from the stack's own instruments; nothing invented
   (unavailable counters are ``null`` with a note).
2. **Sample audit** (CSV): first-N armed by arm order + all M8 armed + all
   routed (deduped), one row per POI — identity fields (tags, pillar_path,
   displacement magnitude, zone bounds, arm bar) and, when routed, the
   entry/SL/TP/anchor provenance — with an explicit ``flow_ok``/``flow_gap``
   verdict per row.

NOT edge, NOT paper trading, NOT F-timing. No strategy code is changed; the
only instrumentation is the FR-4 pattern of wrapping ``engine.scan_route``
and the adapter-module ``candidate_from_route`` (both restored in ``finally``).

Usage:
  python 06_RESEARCH/scripts/phase3_structure_funnel.py --tag run1 \
      --out-root 06_RESEARCH/results/phase3_structure_funnel/run1
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.backtest.bar_loop import BarLoop  # noqa: E402
from smc.backtest.data_feed import CandleSeries  # noqa: E402
from smc.backtest.export import to_csv, to_json  # noqa: E402
from smc.backtest.orders import PendingOrderBook  # noqa: E402
from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
import smc.backtest.pipeline_adapter as pipeline_adapter_module  # noqa: E402
from smc.backtest.pipeline_bridge import pillar_path_summary  # noqa: E402
from smc.backtest.positions import PositionStore  # noqa: E402
from smc.backtest.reports import build_report  # noqa: E402
from smc.backtest.runner import BacktestRunner, RunnerConfig  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.multi_tf_runtime import (  # noqa: E402
    MissingHtfSeriesError,
    MultiTFProductRuntime,
)
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

TF = Timeframe.M5
LOAD_FROM = datetime(2025, 9, 1, tzinfo=timezone.utc)   # warm-up context
EXEC_FROM = datetime(2025, 10, 1, tzinfo=timezone.utc)  # LOCKED primary window
EXEC_TO = datetime(2025, 11, 1, tzinfo=timezone.utc) - timedelta(minutes=1)
SAMPLE_TARGET = 12


def _parse_day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def install_deterministic_poi_ids() -> None:
    """FR-4 pattern: deterministic POI ids so run1/run2 rows are comparable."""
    import smc.core.poi as poi_module

    counter = count(1)

    def _deterministic_id() -> str:
        return f"poi-{next(counter):06d}"

    poi_module.uuid4 = _deterministic_id  # type: ignore[assignment]


class CountingOrderBook(PendingOrderBook):
    """Order book that counts placements + TP presence (read-only counters)."""

    def __init__(self) -> None:
        super().__init__()
        self.placed = 0
        self.placed_with_tp = 0

    def place(self, **kwargs):
        order = super().place(**kwargs)
        self.placed += 1
        if order.tp is not None:
            self.placed_with_tp += 1
        return order


# Notes accumulated during the run (module-level so both the cycle wrapper
# and the summary builder can append without threading a parameter).
summary_notes: list[str] = []


def run(args) -> dict:
    summary_notes.clear()
    install_deterministic_poi_ids()
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    load_from = _parse_day(args.load_from) if args.load_from else LOAD_FROM
    exec_from = _parse_day(args.exec_from) if args.exec_from else EXEC_FROM
    exec_to = (
        _parse_day(args.exec_to) + timedelta(days=1) - timedelta(minutes=1)
        if args.exec_to else EXEC_TO
    )
    t0 = time.perf_counter()

    data_path = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not data_path.exists():
        raise SystemExit(f"canonical dataset missing: {data_path}")
    m1 = load_ohlcv_parquet(data_path)
    m1 = [c for c in m1 if load_from <= c.timestamp <= exec_to + timedelta(days=1)]
    if not m1:
        raise SystemExit("no M1 bars in the requested window")
    multi = resample_multi(m1, [TF, Timeframe.H1, Timeframe.H4, Timeframe.D1])
    m5 = [c for c in multi[TF] if exec_from <= c.timestamp <= exec_to]
    if len(m5) < 50:
        raise SystemExit("execution window too small for the stack warm-up")
    h1, h4, d1 = (multi[Timeframe.H1], multi[Timeframe.H4], multi[Timeframe.D1])
    print(f"[p3] exec M5 {len(m5)} bars; H1 {len(h1)} H4 {len(h4)} D1 {len(d1)}",
          flush=True)

    # ---- Stack: engine + PRODUCT seam + FR-4 arm/scan/risk wiring ------ #
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=TF)
    adapter.set_candles(m5)
    runtime = MultiTFProductRuntime()  # product seam (C1): H4+H1 detect, D1→M8
    order_book = CountingOrderBook()
    position_store = PositionStore()
    runner = BacktestRunner(
        risk_engine=RiskEngine(), order_book=order_book,
        position_store=position_store,
        config=RunnerConfig(
            equity=10_000.0, risk_fraction=0.01, pip_value_per_lot=10.0,
            min_lots=0.01, lot_step=0.01, spread_price=0.0, news_events=[],
            allowed_sessions=(Session.ASIA, Session.LONDON, Session.NEW_YORK),
            timeframe=TF),
    )
    adapter.attach(runner)

    # Per-armed-POI capture (the seam's report carries POI objects in
    # report.armed — we snapshot identity at arm time).
    armed_records: dict[str, dict] = {}
    funnel: dict = {
        "htf_batches": 0,
        "batch_errors": 0,
        "detected_raw": {"H4": 0, "H1": 0},
        "merged": {"H4": 0, "H1": 0},
        "passed": {"H4": 0, "H1": 0},
        "armed": {"H4": 0, "H1": 0},
        "armed_m8": 0,
        "duplicates_suppressed": 0,
        "skipped_tracked": 0,
        "first_failure": {},
        "scan_calls": 0,
        "scan_routes": 0,
        "routes_by_trigger": {},
        "routes_m8": 0,
    }
    pillar_path_by_poi: dict[str, str] = {}
    disp_by_poi: dict[str, float] = {}
    armed_order: list[str] = []

    original_scan = engine.scan_route
    original_bridge = pipeline_adapter_module.candidate_from_route

    def counting_scan(poi, *a, **kw):
        funnel["scan_calls"] += 1
        route = original_scan(poi, *a, **kw)
        if route is not None:
            funnel["scan_routes"] += 1
        return route

    def counting_bridge(route, *a, **kw):
        trig = getattr(route.signal.trigger, "value", str(route.signal.trigger))
        funnel["routes_by_trigger"][trig] = \
            funnel["routes_by_trigger"].get(trig, 0) + 1
        tags = [getattr(m, "name", str(m)) for m in route.poi.models]
        if "M8" in tags:
            funnel["routes_m8"] += 1
        return original_bridge(route, *a, **kw)

    engine.scan_route = counting_scan
    pipeline_adapter_module.candidate_from_route = counting_bridge

    # Pillar first-failure histogram needs the per-POI ValidationResult list.
    # The seam's batch report carries machine-readable COUNTS only by design
    # (contract §2), so we wrap MultiTFDetectionDriver.validate_multi the same
    # way the runtime itself does (Phase-2-snapshot composition) and collect
    # first-failure keys per validated POI. No behavior change: the wrapper
    # calls the original and reads the returned details.
    from smc.orchestration.multi_tf import MultiTFDetectionDriver

    original_validate_multi = MultiTFDetectionDriver.validate_multi

    def histogramming_validate_multi(self, series_by_tf, engine=None,
                                     arm_bars=None, return_details=False):
        result = original_validate_multi(
            self, series_by_tf, engine=engine, arm_bars=arm_bars,
            return_details=True)
        for _tf, info in (getattr(result, "details", {}) or {}).items():
            if not info:
                continue
            for r in info.get("results", []):
                if r.first_failure is not None:
                    key = f"P{r.first_failure.pillar}:{r.first_failure.status.value}"
                else:
                    key = "PASS"
                funnel["first_failure"][key] = \
                    funnel["first_failure"].get(key, 0) + 1
        return result

    MultiTFDetectionDriver.validate_multi = histogramming_validate_multi

    h1_ts = [c.timestamp for c in h1]
    h4_ts = [c.timestamp for c in h4]
    d1_ts = [c.timestamp for c in d1]
    last_h1: datetime | None = None

    class Cycle:
        def __init__(self, inner):
            self.inner = inner
            self.bars = 0

        def on_bar(self, bar, bar_index, clock) -> None:
            nonlocal last_h1
            cut = bisect.bisect_right(h1_ts, bar.timestamp) - 1
            if cut < 0:
                return
            current_h1 = h1[cut].timestamp
            if current_h1 != last_h1:
                last_h1 = current_h1
                series = {
                    Timeframe.H1: h1[: cut + 1],
                    Timeframe.H4: h4[: bisect.bisect_right(h4_ts, bar.timestamp)],
                    Timeframe.D1: d1[: bisect.bisect_right(d1_ts, bar.timestamp)],
                }
                try:
                    report = runtime.run_batch(
                        engine=engine, series_by_tf=series,
                        as_of=bar.timestamp, arm_bar=bar_index, adapter=adapter,
                    )
                except MissingHtfSeriesError:
                    funnel["batch_errors"] += 1
                    return
                funnel["htf_batches"] += 1
                for name, counts in report.per_tf.items():
                    funnel["detected_raw"][name] = \
                        funnel["detected_raw"].get(name, 0) + counts["detected_raw"]
                    funnel["merged"][name] = \
                        funnel["merged"].get(name, 0) + counts["merged"]
                    funnel["passed"][name] = \
                        funnel["passed"].get(name, 0) + counts["passed"]
                funnel["duplicates_suppressed"] += len(report.duplicates)
                funnel["skipped_tracked"] += len(report.skipped_tracked)
                for poi in report.armed:
                    tags = sorted(getattr(m, "name", str(m)) for m in poi.models)
                    # Which TF produced this POI: the batch processed both
                    # detection TFs; attribute by zone timeframe.
                    tf_name = getattr(poi.zone.timeframe, "name", "?")
                    funnel["armed"][tf_name] = funnel["armed"].get(tf_name, 0) + 1
                    if "M8" in tags:
                        funnel["armed_m8"] += 1
                    armed_order.append(poi.id)
                    ctx = adapter._route_context.get(poi.id, (None, None))
                    if ctx[1] is not None:
                        pillar_path_by_poi[poi.id] = ctx[1]
                    if ctx[0] is not None and getattr(ctx[0], "magnitude_atr", None) is not None:
                        disp_by_poi[poi.id] = float(ctx[0].magnitude_atr)
                    armed_records[poi.id] = {
                        "poi_id": poi.id,
                        "detection_tf": tf_name,
                        "model_tags": "|".join(tags),
                        "pillar_path": pillar_path_by_poi.get(poi.id, ""),
                        "disp_magnitude_atr": disp_by_poi.get(poi.id, ""),
                        "zone_low": poi.zone.bottom,
                        "zone_high": poi.zone.top,
                        "armed_bar": bar_index,
                        "routed": "",
                        "trigger": "",
                        "entry": "",
                        "original_sl": "",
                        "tp": "",
                        "entry_anchor": "",
                    }
            self.inner.on_bar(bar, bar_index, clock)
            self.bars += 1
            if self.bars % 2000 == 0:
                el = max(time.perf_counter() - t0, 1e-9)
                print(f"[p3] bar {self.bars}/{len(m5)} "
                      f"{self.bars / el:.1f} bars/s "
                      f"armed={len(armed_records)} "
                      f"routes={funnel['scan_routes']}", flush=True)

    loop = BarLoop(CandleSeries(m5, TF), Cycle(runner))
    try:
        stats = loop.run()
    finally:
        engine.scan_route = original_scan
        pipeline_adapter_module.candidate_from_route = original_bridge
        MultiTFDetectionDriver.validate_multi = original_validate_multi

    # ---- Post-run: routes/placements from the adapter + runner --------- #
    result = runner.result()
    report = build_report(result)
    routes_by_poi: dict[str, dict] = {}
    for trade in report.trades:
        routes_by_poi[trade.poi_id] = {
            "trigger": trade.trigger,
            "entry": trade.entry_price,
            "sl": trade.sl,
            "tp": trade.tp,
        }
    # Routed-but-possibly-unfilled identity: read the adapter's workflow log
    # indirectly through the runner's order book (placed orders carry poi_id).
    placed_by_poi: dict[str, dict] = {}
    for order in getattr(order_book, "_orders", []):
        pid = getattr(order, "poi_id", None)
        if pid is None:
            continue
        placed_by_poi[pid] = {
            "entry": getattr(order, "price", None),
            "sl": getattr(order, "sl", None),
            "tp": getattr(order, "tp", None),
        }

    # Fill the routed/entry columns for sampled armed rows below.
    for pid, rec in armed_records.items():
        info = routes_by_poi.get(pid) or placed_by_poi.get(pid)
        if info is not None:
            rec["routed"] = "true"
            rec["trigger"] = str(info.get("trigger") or "")
            rec["entry"] = info.get("entry")
            rec["original_sl"] = info.get("sl")
            rec["tp"] = info.get("tp")

    # Intent telemetry (R9): count the runner's IntentBook lifecycle events
    # (the book records one machine-readable dict per transition; never
    # fabricated — an absent book stays null with a note).
    intent_book = getattr(runner, "intents", None)
    if intent_book is not None and hasattr(intent_book, "events"):
        events = intent_book.events or []
        by_kind: dict[str, int] = {}
        for ev in events:
            kind = str(ev.get("kind", ev.get("event", "?")))
            by_kind[kind] = by_kind.get(kind, 0) + 1
        intents = {
            "intents_armed": by_kind.get("armed", 0),
            "intents_placed": by_kind.get("placed", 0),
            "intents_expired": by_kind.get("expired", 0),
            "intents_replaced": by_kind.get("replaced", 0),
            "intents_dropped": by_kind.get("dropped", 0)
            + by_kind.get("dropped_poi", 0) + by_kind.get("dropped_portfolio", 0),
        }
    else:
        intents = {"intents_armed": None, "intents_placed": None,
                   "intents_expired": None}
        summary_notes.append(
            "intent counters unavailable: runner exposes no IntentBook "
            "attribute from this composition")

    # ---- Sample audit selection ---------------------------------------- #
    routed_ids = [pid for pid, rec in armed_records.items() if rec["routed"] == "true"]
    m8_ids = [pid for pid, rec in armed_records.items()
              if "M8" in rec["model_tags"].split("|")]
    selection: list[str] = []
    for pid in armed_order:
        if len(selection) >= SAMPLE_TARGET:
            break
        selection.append(pid)
    for pid in m8_ids + routed_ids:
        if pid not in selection:
            selection.append(pid)

    rows = []
    flow_gaps: list[str] = []
    for pid in selection:
        rec = armed_records[pid]
        gaps: list[str] = []
        zone_ok = rec["zone_low"] != "" and rec["zone_high"] != ""
        tags_ok = bool(rec["model_tags"])
        path_ok = bool(rec["pillar_path"])
        disp_ok = rec["disp_magnitude_atr"] != ""
        if not zone_ok:
            gaps.append("missing_zone_bounds")
        if not tags_ok:
            gaps.append("missing_model_tags")
        if not path_ok:
            gaps.append("missing_pillar_path")
        if not disp_ok:
            gaps.append("missing_disp_on_armed")
        if rec["routed"] == "true":
            if rec["entry"] in (None, ""):
                gaps.append("missing_entry")
            if rec["original_sl"] in (None, ""):
                gaps.append("missing_sl")
        rec["flow_ok"] = "false" if gaps else "true"
        rec["flow_gap"] = ";".join(gaps)
        for gap in gaps:
            if gap not in flow_gaps:
                flow_gaps.append(gap)
        rows.append(rec)

    out = REPO_ROOT / args.out_root
    out.mkdir(parents=True, exist_ok=True)

    fields = ["poi_id", "detection_tf", "model_tags", "pillar_path",
              "disp_magnitude_atr", "zone_low", "zone_high", "armed_bar",
              "routed", "trigger", "entry", "original_sl", "tp",
              "entry_anchor", "flow_ok", "flow_gap"]
    with (out / "sample_audit.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for rec in rows:
            row = {k: rec.get(k, "") for k in fields}
            row["disp_magnitude_atr"] = (
                "" if rec.get("disp_magnitude_atr") == ""
                else f"{float(rec['disp_magnitude_atr']):.6f}")
            for price_key in ("zone_low", "zone_high", "entry", "original_sl", "tp"):
                value = row.get(price_key)
                row[price_key] = "" if value in (None, "") else f"{float(value):.6f}"
            # entry_anchor: not exported by the current runner path — honest N/A.
            row["entry_anchor"] = "n/a:not_exported"
            writer.writerow(row)

    trades_by_trigger: dict = {}
    for trade in report.trades:
        trades_by_trigger[trade.trigger] = \
            trades_by_trigger.get(trade.trigger, 0) + 1

    notes: list[str] = list(summary_notes) + [
        "composition: MultiTFProductRuntime.run_batch (product seam, C1) at "
        "new-H1-close cadence → PipelineEngine arm → PipelineAdapter scans → "
        "BacktestRunner risk/placement — the FR-4 arm/scan/risk wiring",
        "detection window composition identical to C1 parity smoke: honest "
        "prefixes (bars <= as_of) per TF; D1 forwarded to M8 per contract §1",
        "spread 0.0 / news dormant / all sessions — machine-completeness "
        "config identical to FR-4, NOT cost realism",
    ]
    if args.exec_to:
        notes.append(f"exec_to overridden: {args.exec_to} (locked primary is "
                     f"{EXEC_TO.date().isoformat()})")

    summary = {
        "tag": args.tag,
        "window": {
            "start": m5[0].timestamp.isoformat(),
            "end": m5[-1].timestamp.isoformat(),
            "exec_tf": TF.name,
            "load_from": load_from.isoformat(),
        },
        "bars_m5": stats.bars_processed,
        "htf_batches": funnel["htf_batches"],
        "batch_errors": funnel["batch_errors"],
        "detected_raw_by_tf": funnel["detected_raw"],
        "merged_by_tf": funnel["merged"],
        "merged_pois": sum(funnel["merged"].values()),
        "passed_validation_by_tf": funnel["passed"],
        "passed_validation": sum(funnel["passed"].values()),
        "pillar_first_failure": funnel["first_failure"],
        "armed": sum(funnel["armed"].values()),
        "armed_by_tf": funnel["armed"],
        "armed_m8": funnel["armed_m8"],
        "duplicates_suppressed": funnel["duplicates_suppressed"],
        "skipped_tracked": funnel["skipped_tracked"],
        "scanned_pois": funnel["scan_calls"],
        "routes": funnel["scan_routes"],
        "routes_by_trigger": funnel["routes_by_trigger"],
        "routes_m8": funnel["routes_m8"],
        "placed": order_book.placed,
        "placed_with_tp": order_book.placed_with_tp,
        "intents_armed": intents["intents_armed"],
        "intents_placed": intents["intents_placed"],
        "intents_expired": intents["intents_expired"],
        "fills": len(report.trades),
        "trades": len(report.trades),
        "trades_by_trigger": trades_by_trigger,
        "sample_audit_rows": len(rows),
        "sample_flow_gaps": flow_gaps,
        "notes": notes,
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }
    (out / "funnel_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # Optional by-day CSV (armed/routes/fills by UTC date).
    by_day: dict[str, dict] = {}
    for rec in armed_records.values():
        day = m5[rec["armed_bar"]].timestamp.date().isoformat()
        by_day.setdefault(day, {"armed": 0, "routes": 0, "fills": 0})
        by_day[day]["armed"] += 1
    for pid, info in placed_by_poi.items():
        # placements are attributed to the POI's arm day when known
        rec = armed_records.get(pid)
        if rec is not None:
            day = m5[rec["armed_bar"]].timestamp.date().isoformat()
            by_day.setdefault(day, {"armed": 0, "routes": 0, "fills": 0})
            by_day[day]["routes"] += 1
    for trade in report.trades:
        day = trade.exit_at.date().isoformat() if trade.exit_at else ""
        by_day.setdefault(day, {"armed": 0, "routes": 0, "fills": 0})
        by_day[day]["fills"] += 1
    with (out / "funnel_by_day.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "armed", "routes", "fills"])
        for day in sorted(by_day):
            writer.writerow([day, by_day[day]["armed"], by_day[day]["routes"],
                             by_day[day]["fills"]])

    # persist armed records for the chart helper
    (out / "armed_records.json").write_text(
        json.dumps({pid: {k: (str(v) if not isinstance(v, (int, float, str)) else v)
                          for k, v in rec.items()}
                    for pid, rec in armed_records.items()},
                   indent=2, default=str),
        encoding="utf-8")
    to_csv(report, out / "trades.csv")
    to_json(report, out / "report.json")

    print(json.dumps({k: v for k, v in summary.items() if k != "notes"},
                     indent=2, default=str))
    print(f"[p3] wrote {out} in {summary['runtime_seconds']}s", flush=True)
    return summary


funnel_notes: list[str] = []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--load-from", default=None)
    ap.add_argument("--exec-from", default=None)
    ap.add_argument("--exec-to", default=None)
    args = ap.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
