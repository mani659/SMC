"""FR-4 fidelity re-baseline (post-reset machine) — one-month multi-TF run.

Measures cascade compliance + composition on the FR-1/2/3 stack. NOT edge,
promotion, or capital advice. Phase C is archived as pre-reset and
incomparable (different machine: buffered stops, TP routing, zone gate,
multi-TF detection) — any side-by-side table must be labeled
INCOMPARABLE REGIMES.

Design (mirrors phase_b wiring; library path does the multi-TF work):
  M1 parquet (accepted loader) → resample M5/H1/H4/D1 → M5 bar loop;
  on every newly-closed H1 bar, MultiTFDetectionDriver.validate_multi
  over honest prefixes (H4+H1 detection, D1/H4 map into M8) → geometric
  ZoneRegistry dedup → arm new POIs at the M5 bar index + feed
  note_route_context (displacement + pillar summary) → adapter trigger
  scans on M5 → risk → fills → closes. Deterministic POI ids injected
  (phase_b pattern) so run1/run2 are byte-comparable.

 frozen intent: equity 10_000, risk 0.01, spread 0.0 (gates off — machine
 completeness, not cost realism), news dormant, all sessions, Friday EOD
 on, M5 execution, H4+H1 detection, FR-2 TP/SL + FR-3 zone gate live,
 Trigger D absent on volume-less data (explained, not fixed).

Usage:
  python 06_RESEARCH/scripts/fr4_fidelity_baseline.py --tag run1 --out-root 06_RESEARCH/results/fr4_fidelity/run1
"""

from __future__ import annotations

import argparse
import bisect
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
from smc.backtest.pipeline_bridge import (  # noqa: E402
    candidate_from_route,
    pillar_path_summary,
)
import smc.backtest.pipeline_adapter as pipeline_adapter_module  # noqa: E402
from smc.backtest.positions import PositionStore  # noqa: E402
from smc.backtest.reports import build_report  # noqa: E402
from smc.backtest.runner import BacktestRunner, RunnerConfig  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.multi_tf import MultiTFDetectionDriver  # noqa: E402
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

TF = Timeframe.M5
LOAD_FROM = datetime(2025, 9, 1, tzinfo=timezone.utc)
EXEC_FROM = datetime(2025, 10, 1, tzinfo=timezone.utc)
EXEC_TO = datetime(2025, 11, 1, tzinfo=timezone.utc) - timedelta(minutes=1)


def _parse_day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def install_deterministic_poi_ids() -> None:
    import smc.core.poi as poi_module

    counter = count(1)

    def _deterministic_id() -> str:
        return f"poi-{next(counter):06d}"

    poi_module.uuid4 = _deterministic_id  # type: ignore[assignment]


class ZoneRegistry:
    """Geometric POI dedup: same direction + overlapping zone = one episode."""

    def __init__(self) -> None:
        self._zones: list[tuple[str, float, float]] = []

    def seen(self, zone) -> bool:
        for direction, top, bottom in self._zones:
            if direction != str(zone.direction):
                continue
            if top >= zone.bottom and zone.top >= bottom:
                return True
        return False

    def register(self, zone) -> None:
        self._zones.append(
            (str(zone.direction), round(float(zone.top), 6),
             round(float(zone.bottom), 6)))


class CountingOrderBook(PendingOrderBook):
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


def run(args) -> dict:
    install_deterministic_poi_ids()
    if getattr(args, "diag_no_zone_gate", False):
        # DIAGNOSTIC-ONLY ablation (never for evidence runs): bypass the FR-3
        # zone gate to attribute zero-route outcomes (gate vs general
        # strictness). Production code untouched; the flag is logged.
        import smc.triggers.trigger_f_bos_ob as fmod
        fmod.entry_within_zone = lambda *a, **k: True
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    load_from = _parse_day(args.load_from) if args.load_from else LOAD_FROM
    exec_from = _parse_day(args.exec_from) if args.exec_from else EXEC_FROM
    exec_to = (_parse_day(args.exec_to) + timedelta(days=1) - timedelta(minutes=1)
               if args.exec_to else EXEC_TO)
    t0 = time.perf_counter()
    m1 = load_ohlcv_parquet(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet")
    m1 = [c for c in m1 if load_from <= c.timestamp <= exec_to + timedelta(days=1)]
    print(f"[fr4] M1 loaded: {len(m1)} bars "
          f"{m1[0].timestamp.isoformat()}..{m1[-1].timestamp.isoformat()}",
          flush=True)
    multi = resample_multi(m1, [Timeframe.M5, Timeframe.H1,
                                Timeframe.H4, Timeframe.D1])
    m5 = [c for c in multi[Timeframe.M5]
          if exec_from <= c.timestamp <= exec_to]
    if len(m5) < 50:
        raise SystemExit("execution window too small for the stack warm-up")
    h1, h4, d1 = (multi[Timeframe.H1], multi[Timeframe.H4], multi[Timeframe.D1])
    print(f"[fr4] exec M5: {len(m5)} bars; H1/H4/D1: {len(h1)}/{len(h4)}/{len(d1)}",
          flush=True)

    engine = PipelineEngine()
    driver = MultiTFDetectionDriver(
        detection_timeframes=(Timeframe.H4, Timeframe.H1),
        execution_timeframe=Timeframe.M5,
    )
    adapter = PipelineAdapter(engine, timeframe=TF)
    adapter.set_candles(m5)
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
    registry = ZoneRegistry()
    tags_by_poi: dict[str, list[str]] = {}
    from smc.validation.state_machine import POIState
    armed: dict[str, dict] = {}
    funnel = {"htf_batches": 0, "detected_raw": {tf.name: 0 for tf in
                                                 (Timeframe.H4, Timeframe.H1)},
              "passed": {tf.name: 0 for tf in (Timeframe.H4, Timeframe.H1)},
              "armed_unique": {tf.name: 0 for tf in (Timeframe.H4, Timeframe.H1)},
              "armed_m8": 0, "routes_created": 0,
              "first_failure": {}}
    routes_m8 = 0

    original_bridge = pipeline_adapter_module.candidate_from_route
    original_scan = engine.scan_route
    funnel["scan_calls"] = 0
    funnel["scan_routes"] = 0

    def counting_scan(poi, *args, **kwargs):
        funnel["scan_calls"] += 1
        route = original_scan(poi, *args, **kwargs)
        if route is not None:
            funnel["scan_routes"] += 1
        return route

    engine.scan_route = counting_scan

    def counting_bridge(route, *args, **kwargs):
        nonlocal routes_m8
        funnel["routes_created"] += 1
        trig = getattr(route.signal.trigger, "value", str(route.signal.trigger))
        funnel.setdefault("routes_by_trigger", {})
        funnel["routes_by_trigger"][trig] = \
            funnel["routes_by_trigger"].get(trig, 0) + 1
        if "M8" in [getattr(m, "name", str(m)) for m in route.poi.models]:
            routes_m8 += 1
        return original_bridge(route, *args, **kwargs)

    pipeline_adapter_module.candidate_from_route = counting_bridge
    try:
        h1_ts = [c.timestamp for c in h1]
        h4_ts = [c.timestamp for c in h4]
        d1_ts = [c.timestamp for c in d1]
        last_h1_cut = -1

        class Cycle:
            def __init__(self, inner):
                self.inner = inner
                self.bars = 0

            def on_bar(self, bar, bar_index, clock) -> None:
                h1_cut = bisect.bisect_right(h1_ts, bar.timestamp) - 1
                nonlocal last_h1_cut
                if h1_cut != last_h1_cut:
                    # New H1 close: refresh HTF batch detection on honest
                    # prefixes (no future bars by construction).
                    last_h1_cut = h1_cut
                    prefixes = {
                        Timeframe.H1: h1[:h1_cut + 1],
                        Timeframe.H4: h4[:bisect.bisect_right(h4_ts, bar.timestamp)],
                        Timeframe.D1: d1[:bisect.bisect_right(d1_ts, bar.timestamp)],
                    }
                    res = driver.validate_multi(
                        {Timeframe.H4: prefixes[Timeframe.H4],
                         Timeframe.H1: prefixes[Timeframe.H1]},
                        engine=engine, return_details=True)
                    # M8 map rides the same prefixes (shared-map convention).
                    funnel["htf_batches"] += 1
                    for tf_key, counts in res.counts_by_tf().items():
                        funnel["detected_raw"][tf_key.name] += \
                            counts["detected_raw"]
                    det = res.details
                    for tf in (Timeframe.H4, Timeframe.H1):
                        info = det.get(tf)
                        if not info:
                            continue
                        res_by_id = {r.poi.id: r for r in info["results"]}
                        funnel["passed"][tf.name] += len(info["passed"])
                        for r in info["results"]:
                            key = (r.first_failure.name
                                   if r.first_failure is not None else "PASS")
                            funnel["first_failure"][key] = \
                                funnel["first_failure"].get(key, 0) + 1
                        for poi in info["passed"]:
                            if registry.seen(poi.zone):
                                continue
                            disp = info["disp_map"].get(poi.id)
                            vres = res_by_id.get(poi.id)
                            adapter.note_route_context(
                                poi.id, displacement=disp,
                                pillar_path=(pillar_path_summary(vres)
                                             if vres is not None else None))
                            engine.arm_at(poi, arm_bar=bar_index)
                            registry.register(poi.zone)
                            armed[poi.id] = {
                                "arm_bar": bar_index, "poi": poi,
                                "zone": (poi.zone.bottom, poi.zone.top),
                                "fate": None, "fate_bar": None,
                            }
                            funnel["armed_unique"][tf.name] += 1
                            tags = sorted(getattr(m, "name", str(m))
                                          for m in poi.models)
                            tags_by_poi[poi.id] = tags
                            if "M8" in tags:
                                funnel["armed_m8"] += 1
                self.inner.on_bar(bar, bar_index, clock)
                for pid, rec in armed.items():
                    if rec["fate"] is None:
                        state = engine.state_machine.current(rec["poi"])
                        if state is not POIState.FRESH:
                            rec["fate"] = state.value
                            rec["fate_bar"] = bar_index
                self.bars += 1
                if self.bars % 1000 == 0:
                    el = time.perf_counter() - t0
                    print(f"[fr4] bar {self.bars}/{len(m5)} "
                          f"{self.bars / el:.1f} bars/s "
                          f"armed={sum(funnel['armed_unique'].values())} "
                          f"routes={funnel['routes_created']}", flush=True)

        loop = BarLoop(CandleSeries(m5, TF), Cycle(runner))
        stats = loop.run()
    finally:
        pipeline_adapter_module.candidate_from_route = original_bridge
        engine.scan_route = original_scan

    for rec in armed.values():
        rec.pop("poi", None)
    funnel["armed_fate"] = armed
    result = runner.result()
    report = build_report(result)
    out = REPO_ROOT / args.out_root
    out.mkdir(parents=True, exist_ok=True)
    to_csv(report, out / "trades.csv")
    to_json(report, out / "report.json")
    by_trigger = {}
    for t in report.trades:
        by_trigger[t.trigger] = by_trigger.get(t.trigger, 0) + 1
    tp_placed = sum(1 for t in report.trades if t.tp is not None)
    tp_closed = sum(1 for t in report.trades if t.close_kind == "take_profit")
    m8_trades = sum(1 for t in report.trades
                    if "M8" in (tags_by_poi.get(t.poi_id) or []))
    summary = {
        "tag": args.tag, "bars_processed": stats.bars_processed,
        "window": [m5[0].timestamp.isoformat(), m5[-1].timestamp.isoformat()],
        "config": {"equity": 10_000.0, "risk_fraction": 0.01,
                   "spread_price": 0.0, "news_events": [],
                   "timeframe": "M5", "detection": ["H4", "H1"],
                   "fr2_tp": True, "fr2_sl_buffer": True, "fr3_zone_gate": True},
        "diag_no_zone_gate": bool(getattr(args, "diag_no_zone_gate", False)),
        "funnel": funnel,
        "routes_m8": routes_m8,
        "entries_placed": order_book.placed,
        "placed_with_tp": order_book.placed_with_tp,
        "trades_closed": len(report.trades),
        "by_trigger": by_trigger,
        "m8_trades": m8_trades,
        "tp_non_null": tp_placed,
        "tp_closed": tp_closed,
        "positions_still_open": sum(
            1 for _ in position_store._open) if hasattr(
                position_store, "_open") else "n/a",
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[fr4] done: {len(report.trades)} trades, "
          f"triggers={by_trigger}, tp_closed={tp_closed}", flush=True)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--load-from", default=None)
    ap.add_argument("--exec-from", default=None)
    ap.add_argument("--exec-to", default=None)
    ap.add_argument("--diag-no-zone-gate", action="store_true",
                    help="DIAGNOSTIC ONLY: bypass FR-3 zone gate to attribute "
                         "zero-route outcomes. Never for evidence runs.")
    args = ap.parse_args()
    summary = run(args)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
