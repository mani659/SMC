"""POST-V1 PHASE C — segmented 5-year baseline over the frozen full stack.

The Phase B machinery (instrumentation, invariants, funnel, exports) is
imported from ``phase_b_fidelity_backtest`` UNCHANGED; this script only
adds the Phase C execution design mandated by the plan:

1. SEGMENTS — calendar years (2021 partial → 2026 partial) over the full
   canonical ``07_DATA/XAUUSD_M1.parquet`` range. Each segment runs the
   IDENTICAL frozen Phase B config family (only spread is parameterized
   for the §28.5 sensitivity runs) and writes its own
   ``summary.json`` / ``trades.csv`` / ``report.json``.
2. CHECKPOINT / RESUME — a segment with complete artifacts + matching
   manifest fingerprint (spread, window bars, run tag) is skipped, so an
   interrupted run resumes at segment granularity.
3. DETERMINISTIC MERGE — segment trades are concatenated in segment
   order with ABSOLUTE bar indices (segment entry_bar + segment start
   offset) and unique POI ids (segment-prefixed), then one merged
   report/summary is produced. No cross-segment state exists in the
   stack by construction (fresh engine/runner per segment), so the
   concatenation IS the serial semantics.
4. DETERMINISM — POI ids are injected deterministically with a segment
   prefix; two identical invocations (dual-run pair) produce
   byte-identical per-segment and merged artifacts.

Run from the repo root (one process per run tag):

    python 06_RESEARCH/scripts/phase_c_baseline_backtest.py --tag run1 \
        --out-root 06_RESEARCH/results/phase_c_baseline_run1

Smoke (cap bars per segment):

    python 06_RESEARCH/scripts/phase_c_baseline_backtest.py --tag smoke \
        --out-root 06_RESEARCH/results/phase_c_smoke --max-bars 800
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

import phase_b_fidelity_backtest as phase_b  # noqa: E402

from smc.backtest.bar_loop import BarLoop  # noqa: E402
from smc.backtest.data_feed import CandleSeries  # noqa: E402
from smc.backtest.export import to_csv, to_json  # noqa: E402
from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.backtest.reports import build_report  # noqa: E402
from smc.backtest.runner import BacktestRunner, RunnerConfig  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
import smc.backtest.pipeline_adapter as pipeline_adapter_module  # noqa: E402
from smc.backtest.reports import (  # noqa: E402
    UNATTRIBUTED,
    BacktestReport,
    CoreMetrics,
    GroupMetrics,
    TradeRecord,
    _group,
    _max_drawdown,
)
from smc.orchestration.detection_driver import DetectionDriver  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
TF = Timeframe.M1

# Frozen Phase C config family = the Phase B frozen config, verbatim
# (spread parameterized ONLY for the documented sensitivity runs).
CONFIG = dict(phase_b.CONFIG)

MANIFEST_NAME = "manifest.json"
ARTIFACT_NAMES = ("summary.json", "trades.csv", "report.json")


def parse_args() -> argparse.Namespace:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="run tag (run1/run2/...)")
    parser.add_argument("--out-root", required=True,
                        help="output root; segments under <root>/segments/, merge at <root>/merged")
    parser.add_argument("--from", dest="from_ts", default=None,
                        help="override window start (UTC YYYY-MM-DD; default = full canonical range)")
    parser.add_argument("--to", dest="to_ts", default=None,
                        help="override window end (UTC YYYY-MM-DD inclusive)")
    parser.add_argument("--spread", type=float, default=0.0,
                        help="constant spread in price units (main baseline = 0.0)")
    parser.add_argument("--window-bars", type=int, default=2880)
    parser.add_argument("--max-bars", type=int, default=None,
                        help="smoke cap on bars PER SEGMENT")
    parser.add_argument("--force", action="store_true",
                        help="re-run even when complete segment artifacts exist")
    return parser.parse_args()


# ---------------------------------------------------------------------- #
# Calendar-year segmentation of the canonical frame.
# ---------------------------------------------------------------------- #
def canonical_bounds() -> tuple[pd.Timestamp, pd.Timestamp]:
    frame = pd.read_parquet(PARQUET, columns=["timestamp"])
    stamps = pd.to_datetime(frame["timestamp"])
    if stamps.dt.tz is None:
        stamps = stamps.dt.tz_localize("UTC")
    return stamps.min(), stamps.max()


def plan_segments(first: pd.Timestamp, last: pd.Timestamp,
                  frame_stamps: pd.Series | None = None) -> list[dict]:
    """Calendar-year segments covering [first, last] (inclusive, UTC).

    ``start_bar`` — the canonical bar index of the segment's first bar
    (0-based over the FULL canonical frame; loaded once here so segment
    trades can be re-based to absolute bar indices in the merge).
    """
    if frame_stamps is None:
        frame = pd.read_parquet(PARQUET, columns=["timestamp"])
        frame_stamps = pd.to_datetime(frame["timestamp"])
        if frame_stamps.dt.tz is None:
            frame_stamps = frame_stamps.dt.tz_localize("UTC")
    segments: list[dict] = []
    year = first.year
    while year <= last.year:
        seg_start = max(pd.Timestamp(year, 1, 1, tz="UTC"), first)
        seg_end = min(pd.Timestamp(year, 12, 31, 23, 59, tz="UTC"), last)
        offset = int((frame_stamps < seg_start).sum())
        segments.append({
            "index": len(segments),
            "label": str(year),
            "from": seg_start,
            "to": seg_end,
            "start_bar": offset,
        })
        year += 1
    return segments


WARMUP_BARS = 2880          # detection window — the context an interior
                            # segment must inherit from the preceding bars
WARMUP_LOAD_DAYS = 7        # calendar margin covering 2,880 M1 bars
                            # across weekends/holidays


def load_segment(seg: dict) -> tuple[list, int]:
    """Load [segment + warm-up context] via the ACCEPTED loader.

    An interior segment loads ``seg.from − WARMUP_LOAD_DAYS`` so the last
    WARMUP_BARS bars before the segment exist as detection context; the
    returned ``own_start`` is the index of the segment's first own bar in
    the loaded list (0 for the FIRST segment — the continuous run also
    starts cold at the canonical first bar).
    """
    load_from = seg["from"]
    if seg["index"] > 0:
        load_from = seg["from"] - pd.Timedelta(days=WARMUP_LOAD_DAYS)
    candles = phase_b.load_window(load_from.to_pydatetime(), seg["to"].to_pydatetime())
    own_start = 0
    if seg["index"] > 0:
        own_start = next(
            i for i, c in enumerate(candles) if c.timestamp >= seg["from"].to_pydatetime()
        )
        warm = own_start - WARMUP_BARS
        if warm > 0:
            candles = candles[warm:]
            own_start -= warm
    return candles, own_start


# ---------------------------------------------------------------------- #
# Deterministic POI ids with a segment prefix (unique across the merge).
# ---------------------------------------------------------------------- #
def install_segment_poi_ids(prefix: str) -> None:
    import smc.core.poi as poi_module

    counter = count(1)

    def _deterministic_id() -> str:
        return f"{prefix}-{next(counter):06d}"

    poi_module.uuid4 = _deterministic_id  # type: ignore[assignment]


# ---------------------------------------------------------------------- #
# One segment = the Phase B run() body, with segment-scoped identity.
# ---------------------------------------------------------------------- #
def run_segment(seg: dict, candles: list, own_start: int,
                args: argparse.Namespace) -> dict:
    install_segment_poi_ids(f"y{seg['label']}")

    if args.max_bars:
        # Cap on OWN bars processed (warm-up context is never truncated
        # away — the interior-segment contract depends on it).
        candles = candles[: own_start + args.max_bars]
    if len(candles) - own_start < 50:
        raise SystemExit(f"segment {seg['label']} too small for the stack warm-up")

    config = dict(CONFIG)
    config["spread_price"] = args.spread

    series = CandleSeries(candles, TF)
    counters = phase_b.Counters()
    registry = phase_b.ZoneRegistry()

    engine = PipelineEngine()
    driver = DetectionDriver(TF)
    adapter = PipelineAdapter(engine, timeframe=TF)
    adapter.set_candles(candles)

    order_book = phase_b.CountingOrderBook().bind(counters)
    position_store = phase_b.CountingPositionStore().bind(counters)
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=order_book,
        position_store=position_store,
        config=RunnerConfig(
            equity=config["equity"],
            risk_fraction=config["risk_fraction"],
            pip_value_per_lot=config["pip_value_per_lot"],
            min_lots=config["min_lots"],
            lot_step=config["lot_step"],
            spread_price=config["spread_price"],
            news_events=list(config["news_events"]),
            allowed_sessions=tuple(Session(s) for s in config["allowed_sessions"]),
            timeframe=TF,
        ),
    )
    phase_b.instrument(runner, counters)
    adapter.attach(runner)

    original_bridge = pipeline_adapter_module.candidate_from_route

    def counting_bridge(route):
        counters.routes_created += 1
        return original_bridge(route)

    pipeline_adapter_module.candidate_from_route = counting_bridge

    window_bars = args.window_bars
    started = time.perf_counter()
    progress_every = 2000

    class DetectionCycle:
        """Phase B's rolling-window detection cycle, verbatim."""

        def __init__(self, inner) -> None:
            self.inner = inner
            self.bars = 0

        def on_bar(self, bar, bar_index, clock) -> None:
            window = candles[max(0, bar_index - window_bars + 1): bar_index + 1]
            try:
                passed, results, _run, skipped, detected = driver.validate_window(
                    window, engine=engine, merge_first=True
                )
            except Exception as exc:  # noqa: BLE001 — loud, then abort
                print(f"[detect] EXCEPTION {seg['label']} bar {bar_index}: "
                      f"{type(exc).__name__}: {exc}", flush=True)
                raise
            counters.detected_raw += len(detected)
            counters.validation_events += len(results)
            counters.validation_pass_events += len(passed)
            for reason, n in skipped.items():
                counters.skipped_models[reason] = counters.skipped_models.get(reason, 0) + n
            for result in results:
                failure = result.first_failure
                if failure is not None:
                    key = f"pillar_{failure.pillar}_{failure.status.value}"
                    counters.first_failure[key] = counters.first_failure.get(key, 0) + 1
            for poi in passed:
                if registry.seen(poi.zone):
                    continue
                engine.arm_at(poi, arm_bar=bar_index)
                registry.register(poi.zone)
                counters.zones_armed += 1
                for tag in poi.models:
                    name = str(getattr(tag, "name", tag))
                    counters.model_tags_on_armed[name] = counters.model_tags_on_armed.get(name, 0) + 1
            self.inner.on_bar(bar, bar_index, clock)
            self.bars += 1
            if self.bars % progress_every == 0:
                elapsed = time.perf_counter() - started
                rate = self.bars / elapsed if elapsed else 0.0
                eta = (len(candles) - self.bars) / rate if rate else 0.0
                print(
                    f"[progress] {seg['label']} bar {self.bars}/{len(candles)}  "
                    f"{rate:.1f} bars/s  eta {eta / 3600:.1f} h  "
                    f"armed={counters.zones_armed} placed={counters.placements} "
                    f"closed={len(runner.positions.closed_positions())}",
                    flush=True,
                )

    loop = BarLoop(series, DetectionCycle(runner))
    # Interior segments start at their own first bar — the WARMUP_BARS
    # bars before it are context only (detection windows + SeriesState
    # prefix), exactly what a continuous run inherits at that point.
    stats = loop.run(
        start_timestamp=None if own_start == 0 else candles[own_start].timestamp
    )

    elapsed = time.perf_counter() - started
    result = runner.result()
    report = build_report(result)

    funnel = {
        "segment": seg["label"],
        "absolute_start_bar": seg["start_bar"] - own_start,
        "warmup_bars": own_start,
        "bars_processed": stats.bars_processed,
        "window_from": candles[own_start].timestamp.isoformat(),
        "window_to": candles[-1].timestamp.isoformat(),
        "detection_window_bars": window_bars,
        "spread_price": config["spread_price"],
        "pois_detected_raw": counters.detected_raw,
        "validation_events": counters.validation_events,
        "validation_pass_events": counters.validation_pass_events,
        "first_failure_histogram": dict(sorted(counters.first_failure.items())),
        "skipped_models": dict(sorted(counters.skipped_models.items())),
        "pois_armed_unique": counters.zones_armed,
        "model_tags_on_armed": dict(sorted(counters.model_tags_on_armed.items())),
        "routes_produced": counters.routes_created,
        "entries_placed": counters.placements,
        "placed_by_trigger": dict(sorted(counters.placed_by_trigger.items())),
        "blocked_by_reason": dict(report.blocked_by_reason),
        "expired_section23": counters.expired_section23,
        "expired_give_up": counters.expired_give_up,
        "violated_pulls": counters.violated_pulls,
        "hard_cancelled_news": 0,
        "positions_opened": len(result.closed) + len(runner.positions.open_positions()),
        "positions_still_open": len(runner.positions.open_positions()),
        "closed_by_kind": phase_b._count_kinds(result),
        "be_modifies_applied": counters.be_applied,
        "friday_closes": sum(
            1 for c in result.closed if phase_b._kind_str(c.kind) == "friday_eod"
        ),
        "runtime_seconds": round(elapsed, 1),
        "bars_per_second": round(stats.bars_processed / elapsed, 2) if elapsed else 0.0,
    }
    metrics = {
        "n_trades": report.metrics.n_trades,
        "n_wins": report.metrics.n_wins,
        "n_losses": report.metrics.n_losses,
        "win_rate": report.metrics.win_rate,
        "profit_factor": report.metrics.profit_factor,
        "net_pnl": report.metrics.net_pnl,
        "max_drawdown": report.metrics.max_drawdown,
        "equity_end": config["equity"] + report.metrics.net_pnl * config["pip_value_per_lot"],
    }
    by_trigger = {k: v.n_trades for k, v in report.by_trigger.items()}
    invariants = phase_b.check_invariants(runner, counters, report, stats, funnel)

    summary = {
        "config": config,
        "window": {k: funnel[k] for k in ("window_from", "window_to", "bars_processed")},
        "funnel": funnel,
        "metrics": metrics,
        "by_trigger_trades": by_trigger,
        "invariants": invariants,
        "pass": all(v == "OK" for v in invariants.values()),
    }
    return {"summary": summary, "report": report, "funnel": funnel,
            "bars": stats.bars_processed}


# ---------------------------------------------------------------------- #
# Merge — concatenation IS the serial semantics (fresh stack per segment).
# ---------------------------------------------------------------------- #
def merge_summaries(seg_summaries: list[dict], args: argparse.Namespace,
                    total_bars: int) -> dict:
    """Deterministic merged summary (concatenation = serial semantics:
    every segment runs a fresh stack — no cross-segment state exists)."""
    funnel = {
        "segments": [s["funnel"]["segment"] for s in seg_summaries],
        "bars_processed": total_bars,
        "window_from": seg_summaries[0]["funnel"]["window_from"],
        "window_to": seg_summaries[-1]["funnel"]["window_to"],
        "detection_window_bars": args.window_bars,
        "spread_price": args.spread,
        "pois_detected_raw": sum(s["funnel"]["pois_detected_raw"] for s in seg_summaries),
        "validation_events": sum(s["funnel"]["validation_events"] for s in seg_summaries),
        "validation_pass_events": sum(s["funnel"]["validation_pass_events"] for s in seg_summaries),
        "pois_armed_unique": sum(s["funnel"]["pois_armed_unique"] for s in seg_summaries),
        "routes_produced": sum(s["funnel"]["routes_produced"] for s in seg_summaries),
        "entries_placed": sum(s["funnel"]["entries_placed"] for s in seg_summaries),
        "expired_section23": sum(s["funnel"]["expired_section23"] for s in seg_summaries),
        "expired_give_up": sum(s["funnel"]["expired_give_up"] for s in seg_summaries),
        "violated_pulls": sum(s["funnel"]["violated_pulls"] for s in seg_summaries),
        "hard_cancelled_news": 0,
        "positions_opened": sum(s["funnel"]["positions_opened"] for s in seg_summaries),
        "positions_still_open": sum(s["funnel"]["positions_still_open"] for s in seg_summaries),
        "be_modifies_applied": sum(s["funnel"]["be_modifies_applied"] for s in seg_summaries),
        "friday_closes": sum(s["funnel"]["friday_closes"] for s in seg_summaries),
    }
    # Histograms merge by key.
    def merge_hist(key: str) -> dict:
        merged: dict[str, int] = {}
        for s in seg_summaries:
            for k, v in s["funnel"][key].items():
                merged[k] = merged.get(k, 0) + v
        return dict(sorted(merged.items()))

    funnel["first_failure_histogram"] = merge_hist("first_failure_histogram")
    funnel["skipped_models"] = merge_hist("skipped_models")
    funnel["model_tags_on_armed"] = merge_hist("model_tags_on_armed")
    funnel["placed_by_trigger"] = merge_hist("placed_by_trigger")
    funnel["blocked_by_reason"] = merge_hist("blocked_by_reason")
    funnel["closed_by_kind"] = merge_hist("closed_by_kind")

    # Per-segment metric table + chained equity curve (V1 semantics:
    # closed-trade equity in close order; wins > 0, losses ≤ 0).
    per_segment = {}
    pnls_all: list[float] = []
    for s in seg_summaries:
        per_segment[s["funnel"]["segment"]] = s["metrics"]
        pnls_all.extend(s["pnls"])

    n_trades = sum(s["metrics"]["n_trades"] for s in seg_summaries)
    n_wins = sum(s["metrics"]["n_wins"] for s in seg_summaries)
    n_losses = sum(s["metrics"]["n_losses"] for s in seg_summaries)
    net_pnl = sum(s["metrics"]["net_pnl"] for s in seg_summaries)
    gross_profit = sum(s["gross_profit"] for s in seg_summaries)
    gross_loss = sum(s["gross_loss"] for s in seg_summaries)
    metrics = {
        "n_trades": n_trades,
        "n_wins": n_wins,
        "n_losses": n_losses,
        "win_rate": round(n_wins / n_trades, 6) if n_trades else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
        "net_pnl": net_pnl,
        "max_drawdown": _max_drawdown(pnls_all),
        "equity_end": CONFIG["equity"] + net_pnl * CONFIG["pip_value_per_lot"],
    }
    by_trigger = {}
    for s in seg_summaries:
        for k, v in s["by_trigger"].items():
            by_trigger[k] = by_trigger.get(k, 0) + v
    invariants_fail = {
        f"segment_{s['funnel']['segment']}": v
        for s in seg_summaries for k, v in s["invariants"].items() if v != "OK"
    }
    summary = {
        "config": {**CONFIG, "spread_price": args.spread},
        "window": {k: funnel[k] for k in ("window_from", "window_to", "bars_processed")},
        "funnel": funnel,
        "per_segment": per_segment,
        "metrics": metrics,
        "by_trigger_trades": dict(sorted(by_trigger.items())),
        "invariants": invariants_fail if invariants_fail else {"all_segments": "OK"},
        "pass": not invariants_fail,
    }
    return summary


def run(args: argparse.Namespace) -> dict:
    out_root = REPO_ROOT / args.out_root
    seg_root = out_root / "segments"
    merged_dir = out_root / "merged"
    seg_root.mkdir(parents=True, exist_ok=True)

    first, last = canonical_bounds()
    if args.from_ts:
        first = max(first, pd.Timestamp(args.from_ts, tz="UTC"))
    if args.to_ts:
        last = min(last, pd.Timestamp(args.to_ts, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(minutes=1))
    segments = plan_segments(first, last)
    print(f"[plan] {len(segments)} segments  {first} → {last}", flush=True)

    fingerprint = {
        "tag": args.tag, "spread": args.spread, "window_bars": args.window_bars,
        "max_bars": args.max_bars, "config": CONFIG,
        "from": str(first), "to": str(last),
    }

    seg_summaries: list[dict] = []
    total_bars = 0
    started = time.perf_counter()
    for seg in segments:
        seg_dir = seg_root / f"{seg['index']}_{seg['label']}"
        manifest_path = seg_dir / MANIFEST_NAME
        done = (all((seg_dir / name).exists() for name in ARTIFACT_NAMES)
                and manifest_path.exists()
                and json.loads(manifest_path.read_text(encoding="utf-8")) == fingerprint)
        if done and not args.force:
            print(f"[resume] {seg_dir.name} complete — loading artifacts", flush=True)
            summary = json.loads((seg_dir / "summary.json").read_text(encoding="utf-8"))
            pnls = [
                float(row["pnl"])
                for row in pd.read_csv(seg_dir / "trades.csv").to_dict("records")
            ]
            gross_profit = sum(p for p in pnls if p > 0)
            gross_loss = -sum(p for p in pnls if p < 0)
            seg_summaries.append({
                "funnel": summary["funnel"], "metrics": summary["metrics"],
                "by_trigger": summary["by_trigger_trades"],
                "invariants": summary["invariants"],
                "pnls": pnls,
                "gross_profit": gross_profit, "gross_loss": gross_loss,
            })
            total_bars += summary["funnel"]["bars_processed"]
            continue

        print(f"[segment] {seg['label']}  {seg['from']} → {seg['to']}", flush=True)
        t0 = time.perf_counter()
        candles, own_start = load_segment(seg)
        print(f"[segment] {seg['label']}: {len(candles)} bars loaded "
              f"(own {len(candles) - own_start}, warmup {own_start}; "
              f"{time.perf_counter() - t0:.1f} s)", flush=True)
        out = run_segment(seg, candles, own_start, args)
        seg_dir.mkdir(parents=True, exist_ok=True)
        phase_b.to_csv(out["report"], seg_dir / "trades.csv")
        phase_b.to_json(out["report"], seg_dir / "report.json")
        with open(seg_dir / "summary.json", "w", encoding="utf-8") as handle:
            json.dump(out["summary"], handle, sort_keys=True, indent=2)
            handle.write("\n")
        manifest_path.write_text(json.dumps(fingerprint, sort_keys=True), encoding="utf-8")
        pnls = [t.pnl for t in out["report"].trades]
        seg_summaries.append({
            "funnel": out["funnel"], "metrics": out["summary"]["metrics"],
            "by_trigger": out["summary"]["by_trigger_trades"],
            "invariants": out["summary"]["invariants"],
            "pnls": pnls,
            "gross_profit": sum(p for p in pnls if p > 0),
            "gross_loss": -sum(p for p in pnls if p < 0),
        })
        total_bars += out["bars"]
        elapsed_seg = time.perf_counter() - t0
        done_n = len(seg_summaries)
        eta_h = ((time.perf_counter() - started) / done_n
                 * (len(segments) - done_n) / 3600)
        print(f"[segment] {seg['label']} DONE  bars={out['bars']} "
              f"trades={out['summary']['metrics']['n_trades']} "
              f"pass={out['summary']['pass']}  {elapsed_seg / 3600:.2f} h  "
              f"eta {eta_h:.1f} h", flush=True)
        del candles

    merged_dir.mkdir(parents=True, exist_ok=True)
    merged_summary = merge_summaries(seg_summaries, args, total_bars)
    merged_report = build_merged_report(seg_summaries, segments, args)
    phase_b.to_csv(merged_report, merged_dir / "trades.csv")
    phase_b.to_json(merged_report, merged_dir / "report.json")
    with open(merged_dir / "summary.json", "w", encoding="utf-8") as handle:
        json.dump(merged_summary, handle, sort_keys=True, indent=2)
        handle.write("\n")
    print("[merge] artifacts written", flush=True)
    print(json.dumps(merged_summary, sort_keys=True, indent=2), flush=True)
    return merged_summary


def build_merged_report(seg_summaries: list[dict], segments: list[dict],
                        args: argparse.Namespace) -> BacktestReport:
    """Deterministic merged :class:`BacktestReport` (absolute bars).

    TradeRecords are rebuilt from the per-segment CSVs with the segment's
    absolute start-bar offset added (fields round-trip exactly — export
    normalizes enums/datetimes to strings); run-level aggregates are the
    frozen ``reports.py`` helpers over the concatenated close-ordered
    trade list. Segments are chronological and closes are bar-ordered
    within a segment, so the concatenation is close-ordered globally.
    """
    trades: list[TradeRecord] = []
    blocked_by_reason: dict[str, int] = {}
    for seg, s in zip(segments, seg_summaries):
        seg_dir = REPO_ROOT / args.out_root / "segments" / f"{seg['index']}_{seg['label']}"
        start_bar = int(s["funnel"]["absolute_start_bar"])
        rows = pd.read_csv(seg_dir / "trades.csv").to_dict("records")
        for row in rows:
            trades.append(TradeRecord(
                ticket=int(row["ticket"]),
                direction=row["direction"],
                symbol=row["symbol"],
                volume=float(row["volume"]),
                entry_price=float(row["entry_price"]),
                exit_price=float(row["exit_price"]),
                sl=float(row["sl"]) if pd.notna(row["sl"]) else None,
                tp=float(row["tp"]) if pd.notna(row["tp"]) else None,
                entry_bar=int(row["entry_bar"]) + start_bar,
                exit_bar=int(row["exit_bar"]) + start_bar,
                entry_at=row["entry_at"],
                exit_at=row["exit_at"],
                close_kind=row["close_kind"],
                win=bool(row["win"]),
                pnl=float(row["pnl"]),
                poi_id=row["poi_id"] if pd.notna(row["poi_id"]) else None,
                trigger=row["trigger"] if pd.notna(row["trigger"]) else None,
                route_id=row["route_id"] if pd.notna(row["route_id"]) else None,
            ))
        for key, n in s["funnel"].get("blocked_by_reason", {}).items():
            blocked_by_reason[key] = blocked_by_reason.get(key, 0) + n

    trade_tuple = tuple(trades)
    pnls = [t.pnl for t in trade_tuple]
    wins = [p for p in pnls if p > 0.0]
    losses = [p for p in pnls if p <= 0.0]
    gross_profit = sum(wins)
    gross_loss = sum(-p for p in losses)
    return BacktestReport(
        trades=trade_tuple,
        metrics=CoreMetrics(
            n_trades=len(trade_tuple),
            n_wins=len(wins),
            n_losses=len(losses),
            win_rate=(len(wins) / len(trade_tuple)) if trade_tuple else 0.0,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=(gross_profit / gross_loss) if gross_loss > 0.0 else None,
            net_pnl=sum(pnls),
            max_drawdown=_max_drawdown(pnls),
            avg_win=(gross_profit / len(wins)) if wins else None,
            avg_loss=(gross_loss / len(losses)) if losses else None,
        ),
        by_trigger=_group(trade_tuple, lambda t: t.trigger or UNATTRIBUTED),
        by_poi=_group(trade_tuple, lambda t: t.poi_id or UNATTRIBUTED),
        blocked_by_reason=dict(sorted(blocked_by_reason.items())),
    )



if __name__ == "__main__":
    merged = run(parse_args())
    raise SystemExit(0 if merged["pass"] else 2)
