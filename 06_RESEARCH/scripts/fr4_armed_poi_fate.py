"""FR-4 residual closeout — ARMED POI FATE ledger (logging-only instrumentation).

Closes the FR-4 residuals: for every POI that reached ARMED in the FR-4
compliant October window (2025-10-01 → 2025-10-31 multi-TF run), produce a
complete fate ledger — terminal §5 state, why no compliant route/trade
formed, and explicit gate-reject attribution — WITHOUT touching strategy
thresholds, gates, or any locked constant.

Method (read-only vs strategy code):
  * Replays the IDENTICAL frozen config/window as
    ``06_RESEARCH/scripts/fr4_fidelity_baseline.py`` (same wiring, same
    deterministic POI ids, same ZoneRegistry dedup).
  * Adds LOGGING-ONLY observation shims on public seams:
      - a pass-through recorder wrapped around each trigger's ``evaluate``
        (instance-level attribute shadow; the original method is called
        unchanged and its return value passed through verbatim);
      - a pass-through recorder wrapped around
        ``smc.triggers.trigger_f_bos_ob.entry_within_zone`` (module
        attribute — the same seam the sanctioned FR-4 diag ablation used)
        to capture FR-3 gate accept/reject events with geometry;
      - a counting wrapper on ``engine.scan_route`` (baseline pattern).
    No shim alters any decision: every wrapper returns the wrapped call's
    result unchanged. Determinism is PROVEN post-run by byte-comparing
    trades.csv/report.json against the compliant run1 artifacts.
  * Per-armed-POI observation is captured from run state (state machine
    polls each bar, signal/gate events, arm metadata) — no strategy file
    is modified.

Fate taxonomy (terminal §5 state machine: TESTED/VIOLATED are terminal):
  tested_same_bar_as_arm          zone armed inside current price; first
                                  touch flipped it terminal immediately.
  tested_after_arm                first touch at bar T > arm bar.
  violated_close_beyond_zone      closed beyond without touching.
  still_fresh_at_window_end       never touched, never violated; the §24
                                  give-up backstop retires the SCAN at
                                  arm+20 bars but does NOT transition the
                                  §5 state (V1 documented behavior); §23
                                  unfilled-order expiry is not defined for
                                  H1+/HTF zones and no order ever existed.
  other_<state>                   named code path (must never occur here).

Usage:
  python 06_RESEARCH/scripts/fr4_armed_poi_fate.py \
      [--out-root 06_RESEARCH/results/fr4_fidelity] \
      [--baseline-run1 06_RESEARCH/results/fr4_fidelity/run1]
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
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
from smc.core.enums import POIState  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.multi_tf import MultiTFDetectionDriver  # noqa: E402
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

TF = Timeframe.M5
LOAD_FROM = datetime(2025, 9, 1, tzinfo=timezone.utc)
EXEC_FROM = datetime(2025, 10, 1, tzinfo=timezone.utc)
EXEC_TO = datetime(2025, 11, 1, tzinfo=timezone.utc) - timedelta(minutes=1)

TRIGGER_MODULES = {
    "A_CHOCH": "smc.triggers.trigger_a_choch",
    "B_LEADING_DIAGONAL": "smc.triggers.trigger_b_leading_diagonal",
    "C_ENDING_DIAGONAL": "smc.triggers.trigger_c_ending_diagonal",
    "D_TWO_BAR_REVERSAL": "smc.triggers.trigger_d_two_bar",
    "E_RSI_DIVERGENCE": "smc.triggers.trigger_e_rsi_divergence",
    "F_BOS_OB": "smc.triggers.trigger_f_bos_ob",
}


def _parse_day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def install_deterministic_poi_ids() -> None:
    """Same deterministic id scheme as the FR-4 baseline (fresh process)."""
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


class TriggerObserver:
    """Logging-only pass-through wrapper around one trigger's evaluate().

    The wrapped method is called unchanged and its result returned verbatim;
    only completed-signal metadata is recorded. Instance-level attribute
    shadow — no class or module behavior changes.
    """

    def __init__(self, trigger, store: dict, name: str,
                 f_gate_ctx: "FGateObserver | None" = None) -> None:
        self._trigger = trigger
        self._store = store
        self._name = name
        self._f_gate_ctx = f_gate_ctx
        self._original = trigger.evaluate
        trigger.evaluate = self._evaluate  # instance-level shadow

    def _evaluate(self, context):
        poi_id = context.poi.id
        if self._f_gate_ctx is not None:
            self._f_gate_ctx.current_poi = poi_id
        try:
            signal = self._original(context)
        finally:
            if self._f_gate_ctx is not None:
                self._f_gate_ctx.current_poi = None
        if signal is not None:
            rec = self._store.setdefault(
                poi_id, {"signals": [], "gate_events": []})
            rec["signals"].append({
                "trigger": self._name,
                "bar": int(context.current_bar),
                "completion_index": int(signal.completion_index),
                "entry_price": float(signal.entry_price),
                "detail": str(signal.detail),
            })
        return signal

    def uninstall(self) -> None:
        self._trigger.evaluate = self._original


class FGateObserver:
    """Pass-through recorder for the FR-3 zone gate (logging only).

    Wraps the module-level ``entry_within_zone`` used by Trigger F exactly
    as the sanctioned FR-4 diag ablation did — but this wrapper CALLS the
    original and returns its verdict unchanged, recording geometry for the
    ledger. Attribution uses the POI id set by the F trigger observer
    (single-threaded, synchronous evaluation).
    """

    def __init__(self, store: dict) -> None:
        import smc.triggers.trigger_f_bos_ob as fmod

        self._fmod = fmod
        self._original = fmod.entry_within_zone
        self.current_poi: str | None = None
        self._store = store
        fmod.entry_within_zone = self._recording

    def _recording(self, entry_price, zone, atr, *args, **kwargs):
        allowed = self._original(entry_price, zone, atr, *args, **kwargs)
        if self.current_poi is not None:
            rec = self._store.setdefault(
                self.current_poi, {"signals": [], "gate_events": []})
            try:
                bottom = float(getattr(zone, "bottom", float("nan")))
                top = float(getattr(zone, "top", float("nan")))
            except (TypeError, ValueError):
                bottom = top = float("nan")
            rec["gate_events"].append({
                "allowed": bool(allowed),
                "entry_price": (float(entry_price)
                                if entry_price is not None else None),
                "zone_low": bottom,
                "zone_high": top,
                "atr": (float(atr) if atr is not None else None),
            })
        return allowed

    def uninstall(self) -> None:
        self._fmod.entry_within_zone = self._original


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args) -> dict:
    install_deterministic_poi_ids()
    run1_root = REPO_ROOT / args.baseline_run1
    for name in ("trades.csv", "report.json", "summary.json"):
        if not (run1_root / name).exists():
            raise FileNotFoundError(
                f"compliant baseline artifact missing: {run1_root / name} — "
                "run fr4_fidelity_baseline.py --tag run1 first")
    out_root = REPO_ROOT / args.out_root
    out_root.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    load_from = (_parse_day(args.load_from) if args.load_from else LOAD_FROM)
    exec_from = (_parse_day(args.exec_from) if args.exec_from else EXEC_FROM)
    exec_to = (_parse_day(args.exec_to) + timedelta(days=1)
               - timedelta(minutes=1) if args.exec_to else EXEC_TO)
    m1 = load_ohlcv_parquet(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet")
    m1 = [c for c in m1 if load_from <= c.timestamp <= exec_to + timedelta(days=1)]
    if not m1:
        raise RuntimeError("M1 parquet produced an empty series — check 07_DATA")
    print(f"[fate] M1 loaded: {len(m1)} bars "
          f"{m1[0].timestamp.isoformat()}..{m1[-1].timestamp.isoformat()}",
          flush=True)
    multi = resample_multi(m1, [Timeframe.M5, Timeframe.H1,
                                Timeframe.H4, Timeframe.D1])
    m5 = [c for c in multi[Timeframe.M5]
          if exec_from <= c.timestamp <= exec_to]
    if len(m5) < 50:
        raise SystemExit("execution window too small for the stack warm-up")
    h1, h4, d1 = (multi[Timeframe.H1], multi[Timeframe.H4], multi[Timeframe.D1])
    print(f"[fate] exec M5: {len(m5)} bars; H1/H4/D1: {len(h1)}/{len(h4)}/{len(d1)}",
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

    # --- logging-only observation shims -----------------------------------
    obs: dict[str, dict] = {}   # poi_id -> {"signals": [...], "gate_events": [...]}
    gate_ctx = FGateObserver(obs)
    observers: list[TriggerObserver] = []
    for name in TRIGGER_MODULES:
        trigger = next(t for t in engine.router.triggers
                       if t.name == name.lower() or t.type.name == name)
        observers.append(TriggerObserver(
            trigger, obs, name,
            f_gate_ctx=gate_ctx if name == "F_BOS_OB" else None))

    funnel = {"htf_batches": 0, "detected_raw": {tf.name: 0 for tf in
                                                 (Timeframe.H4, Timeframe.H1)},
              "passed": {tf.name: 0 for tf in (Timeframe.H4, Timeframe.H1)},
              "armed_unique": {tf.name: 0 for tf in (Timeframe.H4, Timeframe.H1)},
              "armed_m8": 0, "routes_created": 0, "scan_calls": 0,
              "scan_routes": 0, "first_failure": {}}
    original_bridge = pipeline_adapter_module.candidate_from_route
    original_scan = engine.scan_route

    def counting_scan(poi, *args, **kwargs):
        funnel["scan_calls"] += 1
        route = original_scan(poi, *args, **kwargs)
        if route is not None:
            funnel["scan_routes"] += 1
        return route

    engine.scan_route = counting_scan

    def counting_bridge(route, *args, **kwargs):
        funnel["routes_created"] += 1
        return original_bridge(route, *args, **kwargs)

    pipeline_adapter_module.candidate_from_route = counting_bridge

    # Armed-POI ledger state (run-state observation, no strategy change).
    armed: dict[str, dict] = {}
    tags_by_poi: dict[str, list[str]] = {}
    det_tf_by_poi: dict[str, str] = {}

    def bar_time(bar_index: int) -> str:
        if not 0 <= bar_index < len(m5):
            raise IndexError(
                f"bar index {bar_index} outside M5 series length {len(m5)}")
        return m5[bar_index].timestamp.isoformat()

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
                            tags = sorted(getattr(m, "name", str(m))
                                          for m in poi.models)
                            tags_by_poi[poi.id] = tags
                            det_tf_by_poi[poi.id] = tf.name
                            armed[poi.id] = {
                                "arm_bar": int(bar_index),
                                "arm_time": bar_time(bar_index),
                                "zone": [float(poi.zone.bottom),
                                         float(poi.zone.top)],
                                "first_transition_bar": None,
                                "first_transition_state": None,
                                "terminal_state": POIState.FRESH.value,
                                "terminal_state_bar": int(bar_index),
                            }
                            funnel["armed_unique"][tf.name] += 1
                            if "M8" in tags:
                                funnel["armed_m8"] += 1
                self.inner.on_bar(bar, bar_index, clock)
                # Per-bar §5 state observation (read-only polls).
                state_machine = engine.state_machine
                if armed:
                    tracked_by_id = {p.id: p for p in engine.tracked_pois()}
                    for pid, rec in armed.items():
                        tracked = tracked_by_id.get(pid)
                        if tracked is None:
                            continue  # pruned: terminal_state already captured
                        poi_state = state_machine.current(tracked)
                        if poi_state.value != rec["terminal_state"]:
                            if rec["first_transition_bar"] is None:
                                rec["first_transition_bar"] = int(bar_index)
                                rec["first_transition_state"] = poi_state.value
                            rec["terminal_state"] = poi_state.value
                            rec["terminal_state_bar"] = int(bar_index)
                self.bars += 1
                if self.bars % 1000 == 0:
                    el = time.perf_counter() - t0
                    print(f"[fate] bar {self.bars}/{len(m5)} "
                          f"{self.bars / el:.1f} bars/s "
                          f"armed={len(armed)} "
                          f"routes={funnel['routes_created']}", flush=True)

        loop = BarLoop(CandleSeries(m5, TF), Cycle(runner))
        stats = loop.run()
    finally:
        pipeline_adapter_module.candidate_from_route = original_bridge
        engine.scan_route = original_scan
        gate_ctx.uninstall()
        for observer in observers:
            observer.uninstall()

    # --- classify fates ----------------------------------------------------
    giveup_bars = 20  # §24 V1 POI-wide give-up window (TRIGGER_A_EXPIRY)
    rows: list[dict] = []
    for pid, rec in armed.items():
        events = obs.get(pid, {})
        signals = events.get("signals", [])
        gate_events = events.get("gate_events", [])
        gate_rejects = sum(1 for g in gate_events if not g["allowed"])
        gate_accepts = sum(1 for g in gate_events if g["allowed"])
        state = rec["terminal_state"]
        if state == POIState.TESTED.value:
            if rec["first_transition_bar"] == rec["arm_bar"]:
                fate_class = "tested_same_bar_as_arm"
            else:
                fate_class = "tested_after_arm"
        elif state == POIState.VIOLATED.value:
            fate_class = "violated_close_beyond_zone"
        elif state == POIState.FRESH.value:
            fate_class = "still_fresh_at_window_end_never_touched"
        else:
            fate_class = f"other_{state}"
        giveup_bar = rec["arm_bar"] + giveup_bars
        if fate_class.startswith("tested"):
            fb = rec["first_transition_bar"]
            detail = (f"first section-5 touch at bar {fb} "
                      f"(t+{fb - rec['arm_bar']} bars after arm); "
                      f"trigger signals completed pre-terminality: "
                      f"{len(signals)}; FR-3 gate events: "
                      f"{gate_accepts} pass / {gate_rejects} reject")
        elif fate_class == "violated_close_beyond_zone":
            fb = rec["first_transition_bar"]
            detail = (f"closed beyond zone without touch at bar {fb}; "
                      f"signals: {len(signals)}; gate rejects: {gate_rejects}")
        elif fate_class == "still_fresh_at_window_end_never_touched":
            detail = (
                "zone never touched and never violated through window end; "
                f"section-24 give-up retires the SCAN at bar {giveup_bar} "
                f"(arm+{giveup_bars}) without a state transition (V1 "
                "documented); section-23 unfilled-order expiry undefined for "
                "H1+/HTF zones and no order ever existed")
        else:
            detail = f"unclassified terminal state {state} — named code path"
        rows.append({
            "poi_id": pid,
            "detection_tf": det_tf_by_poi.get(pid, "unknown"),
            "model_tags": "+".join(tags_by_poi.get(pid, [])),
            "is_m8": ("M8" in tags_by_poi.get(pid, [])),
            "arm_bar": rec["arm_bar"],
            "arm_time": rec["arm_time"],
            "zone_low": rec["zone"][0],
            "zone_high": rec["zone"][1],
            "terminal_state": state,
            "fate_class": fate_class,
            "fate_bar": rec["first_transition_bar"],
            "first_signal_bar": (min((s["bar"] for s in signals), default=None)
                                 if signals else None),
            "signal_events_n": len(signals),
            "gate_accept_n": gate_accepts,
            "gate_reject_n": gate_rejects,
            "giveup_bar": giveup_bar,
            "detail": detail,
        })

    rows.sort(key=lambda r: r["arm_bar"])
    fate_counts: dict[str, int] = {}
    for row in rows:
        fate_counts[row["fate_class"]] = \
            fate_counts.get(row["fate_class"], 0) + 1
    m8_rows = [r for r in rows if r["is_m8"]]
    m8_counts: dict[str, int] = {}
    for row in m8_rows:
        m8_counts[row["fate_class"]] = \
            m8_counts.get(row["fate_class"], 0) + 1
    by_tf: dict[str, dict] = {}
    for row in rows:
        slot = by_tf.setdefault(row["detection_tf"],
                                {"armed": 0, "fate_counts": {}})
        slot["armed"] += 1
        slot["fate_counts"][row["fate_class"]] = \
            slot["fate_counts"].get(row["fate_class"], 0) + 1

    # --- artifacts ----------------------------------------------------------
    result = runner.result()
    report = build_report(result)
    to_csv(report, out_root / "trades.csv")
    to_json(report, out_root / "report.json")

    csv_path = out_root / "armed_poi_fate.csv"
    fieldnames = ["poi_id", "detection_tf", "model_tags", "is_m8", "arm_bar",
                  "arm_time", "zone_low", "zone_high", "terminal_state",
                  "fate_class", "fate_bar", "first_signal_bar",
                  "signal_events_n", "gate_accept_n", "gate_reject_n",
                  "giveup_bar", "detail"]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # --- determinism proof vs compliant run1 --------------------------------
    ident_trades = (_sha256(out_root / "trades.csv")
                    == _sha256(run1_root / "trades.csv"))
    ident_report = (_sha256(out_root / "report.json")
                    == _sha256(run1_root / "report.json"))
    baseline_summary = json.loads(
        (run1_root / "summary.json").read_text(encoding="utf-8"))

    def _comparable(summary: dict) -> dict:
        core = dict(summary)
        core.pop("tag", None)
        core.pop("runtime_seconds", None)
        return core

    summary = {
        "script": "fr4_armed_poi_fate.py",
        "purpose": "FR-4 residual closeout — armed-POI fate ledger "
                   "(logging-only instrumentation; no strategy change)",
        "window": [m5[0].timestamp.isoformat(), m5[-1].timestamp.isoformat()],
        "bars_processed": stats.bars_processed,
        "config": {"equity": 10_000.0, "risk_fraction": 0.01,
                   "spread_price": 0.0, "news_events": [],
                   "timeframe": "M5", "detection": ["H4", "H1"],
                   "fr2_tp": True, "fr2_sl_buffer": True,
                   "fr3_zone_gate": True},
        "determinism_check": {
            "trades_csv_byte_identical_vs_run1": ident_trades,
            "report_json_byte_identical_vs_run1": ident_report,
            "trades_csv_sha256": _sha256(out_root / "trades.csv"),
            "run1_trades_csv_sha256": _sha256(run1_root / "trades.csv"),
        },
        "funnel_parity_vs_run1": {
            "htf_batches": funnel["htf_batches"],
            "run1_htf_batches": baseline_summary["funnel"]["htf_batches"],
            "scan_calls": funnel["scan_calls"],
            "run1_scan_calls": baseline_summary["funnel"]["scan_calls"],
            "scan_routes": funnel["scan_routes"],
            "run1_scan_routes": baseline_summary["funnel"]["scan_routes"],
            "routes_created": funnel["routes_created"],
            "run1_routes_created": baseline_summary["funnel"]["routes_created"],
            "armed_unique": funnel["armed_unique"],
            "run1_armed_unique": baseline_summary["funnel"]["armed_unique"],
            "armed_m8": funnel["armed_m8"],
            "run1_armed_m8": baseline_summary["funnel"]["armed_m8"],
        },
        "armed_n": len(rows),
        "fate_counts": fate_counts,
        "by_detection_tf": by_tf,
        "m8": {"armed_n": len(m8_rows), "fate_counts": m8_counts,
               "poi_ids": [r["poi_id"] for r in m8_rows]},
        "gate_reject_events_total": sum(r["gate_reject_n"] for r in rows),
        "gate_accept_events_total": sum(r["gate_accept_n"] for r in rows),
        "signal_events_total": sum(r["signal_events_n"] for r in rows),
        "candidates_built_then_risk_rejected":
            (funnel["routes_created"] - order_book.placed)
            if funnel["routes_created"] else 0,
        "fate_class_definitions": {
            "tested_same_bar_as_arm":
                "first section-5 touch on the arm bar itself (zone armed "
                "inside current price); terminal immediately",
            "tested_after_arm":
                "first section-5 touch after the arm bar; POI terminal from "
                "that bar (1-touch rule)",
            "violated_close_beyond_zone":
                "closed beyond the zone without touching",
            "still_fresh_at_window_end_never_touched":
                "never touched/violated; give-up retires the scan at "
                "arm+20 bars without a state transition; section-23 expiry "
                "undefined for H1+/HTF zones; no order ever existed",
        },
        "armed_rows": rows,
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }
    summary_path = out_root / "armed_poi_fate_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[fate] done: {len(rows)} armed POIs, fates={fate_counts}, "
          f"gate_rejects={summary['gate_reject_events_total']}, "
          f"byte_identity trades={ident_trades} report={ident_report}",
          flush=True)

    if not (ident_trades and ident_report):
        raise SystemExit(
            "DETERMINISM FAILURE: replayed artifacts differ from compliant "
            "run1 — the logging-only shims must not change behavior; "
            "investigate before using this ledger")
    if funnel["armed_unique"] != baseline_summary["funnel"]["armed_unique"] \
            or funnel["scan_calls"] != baseline_summary["funnel"]["scan_calls"] \
            or funnel["routes_created"] != \
            baseline_summary["funnel"]["routes_created"]:
        raise SystemExit(
            "FUNNEL PARITY FAILURE: replay funnel differs from compliant "
            "run1 — replay is not equivalent; ledger unusable")
    if not rows:
        raise RuntimeError(
            "no armed POIs observed — window/config mismatch vs compliant "
            "baseline; refusing to emit an empty ledger silently")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default="06_RESEARCH/results/fr4_fidelity")
    ap.add_argument("--baseline-run1",
                    default="06_RESEARCH/results/fr4_fidelity/run1")
    ap.add_argument("--load-from", default=None)
    ap.add_argument("--exec-from", default=None)
    ap.add_argument("--exec-to", default=None)
    args = ap.parse_args()
    summary = run(args)
    print(json.dumps({k: v for k, v in summary.items()
                      if k != "armed_rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
