"""POST-V1 PHASE B — short fidelity backtest over the frozen full stack.

Load (accepted loader only) → rolling-window DetectionDriver (arm ONLY new
POIs, live-loop contract) → PipelineAdapter (real in-loop detection) →
BacktestRunner (locked per-bar order) → RiskEngine → fills/exits →
build_report + CSV/JSON exports.

NO optimization, NO parameter search, NO stack changes: this script only
WIRES the existing frozen pieces and COUNTS. Determinism: POI ids are
injected deterministically per run (the DetectionDriver-documented
evidence-run pattern) so two identical invocations produce byte-identical
CSV/JSON exports.

Run from the repo root:

    python 06_RESEARCH/scripts/phase_b_fidelity_backtest.py \
        --from 2025-10-01 --to 2025-10-14 \
        --out 06_RESEARCH/results/phase_b_run1

Checks against the plan (POST_V1_PLAN_OF_ACTION.md §4):
  funnel counters per stage; §23/§24 no-fill-after-expiry; §11 one-shot
  (≤1 placement per POI); fill price == limit price; Trigger D == 0 (A5);
  BE applied at most once per ticket; determinism via re-invocation.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.backtest.bar_loop import BarLoop  # noqa: E402
from smc.backtest.data_feed import CandleSeries  # noqa: E402
from smc.backtest.export import to_csv, to_json  # noqa: E402
from smc.backtest.orders import PendingOrderBook  # noqa: E402
from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.backtest.positions import PositionStore  # noqa: E402
from smc.backtest.reports import build_report  # noqa: E402
from smc.backtest.runner import BacktestRunner, RunnerConfig  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
import smc.backtest.pipeline_adapter as pipeline_adapter_module  # noqa: E402
from smc.orchestration.detection_driver import DetectionDriver  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
TF = Timeframe.M1

# Frozen §28.7 / §28 sizing environment (Phase C config, mid-band) + §2
# session gate (entries 00:00–20:00 UTC; 20:00–24:00 belongs to no session).
CONFIG = {
    "equity": 10_000.0,
    "risk_fraction": 0.01,
    "pip_value_per_lot": 10.0,
    "min_lots": 0.01,
    "lot_step": 0.01,
    "spread_price": 0.0,           # §28.5 gate OFF (Phase C adds sensitivity)
    "news_events": [],             # §11 dormant by default (documented)
    "allowed_sessions": ["asia", "london", "new_york"],
    "timeframe": "M1",
}


def parse_args() -> argparse.Namespace:
    if hasattr(sys.stdout, "reconfigure"):  # Windows cp1252 consoles
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="from_ts", required=True, help="UTC date YYYY-MM-DD (inclusive)")
    parser.add_argument("--to", dest="to_ts", required=True, help="UTC date YYYY-MM-DD (inclusive)")
    parser.add_argument("--out", required=True, help="output directory for artifacts")
    parser.add_argument("--window-bars", type=int, default=2880,
                        help="rolling detection window (M1 bars; 2880 ≈ 2 days so PDH/PDL exist)")
    parser.add_argument("--max-bars", type=int, default=None, help="smoke-test cap on bars processed")
    return parser.parse_args()


# ---------------------------------------------------------------------- #
# Deterministic POI identity (evidence-run pattern; ids would otherwise be
# per-run uuid4 values and exports could never be byte-identical).
# ---------------------------------------------------------------------- #
def install_deterministic_poi_ids() -> None:
    import smc.core.poi as poi_module

    counter = count(1)

    def _deterministic_id() -> str:
        return f"poi-{next(counter):06d}"

    poi_module.uuid4 = _deterministic_id  # type: ignore[assignment]


# ---------------------------------------------------------------------- #
# Window loading — the accepted loader stays the ONLY parquet→Candle path.
# The full 5-year series is sliced in pandas first (memory), the slice is
# materialized to a temp parquet, and load_ohlcv_parquet builds the Candles.
# ---------------------------------------------------------------------- #
def load_window(from_ts: datetime, to_ts: datetime) -> list:
    frame = pd.read_parquet(PARQUET)
    stamps = pd.to_datetime(frame["timestamp"])
    if stamps.dt.tz is None:
        stamps = stamps.dt.tz_localize("UTC")
    mask = (stamps >= pd.Timestamp(from_ts)) & (stamps <= pd.Timestamp(to_ts))
    window = frame.loc[mask].reset_index(drop=True)
    if window.empty:
        raise SystemExit(f"empty window {from_ts}..{to_ts}")
    with tempfile.TemporaryDirectory() as tmp:
        slice_path = Path(tmp) / "window.parquet"
        window.to_parquet(slice_path)
        from smc.data.parquet_loader import load_ohlcv_parquet

        candles = load_ohlcv_parquet(slice_path, timeframe=TF, symbol="XAUUSD")
    print(f"[load] {len(candles)} M1 bars  {candles[0].timestamp.isoformat()} → "
          f"{candles[-1].timestamp.isoformat()}", flush=True)
    return candles


# ---------------------------------------------------------------------- #
# Geometric POI dedupe: POI objects are re-created every detection cycle
# (fresh ids each re-detection); without geometric identity the same zone
# would be re-armed every cycle, resetting its §24 anchor and duplicating
# §11 one-shots. Same direction + overlapping zone = the same episode for
# the whole run (a TESTED/VIOLATED zone can never re-arm — §5 terminality).
# ---------------------------------------------------------------------- #
class ZoneRegistry:
    def __init__(self) -> None:
        self._zones: list[tuple[str, float, float]] = []

    @staticmethod
    def _key(zone) -> tuple[str, float, float]:
        return (str(zone.direction), round(float(zone.top), 6), round(float(zone.bottom), 6))

    def seen(self, zone) -> bool:
        for direction, top, bottom in self._zones:
            if direction != str(zone.direction):
                continue
            if top >= zone.bottom and zone.top >= bottom:  # overlap
                return True
        return False

    def register(self, zone) -> None:
        self._zones.append(self._key(zone))


# ---------------------------------------------------------------------- #
# Counting wrappers (script-side instrumentation — the stack is untouched;
# each wrapper delegates to the original bound method after recording).
# ---------------------------------------------------------------------- #
class Counters:
    def __init__(self) -> None:
        self.detected_raw = 0          # pre-merge model detections (cumulative)
        self.validation_events = 0     # per merged-POI pillar runs
        self.validation_pass_events = 0
        self.first_failure: dict[str, int] = {}
        self.skipped_models: dict[str, int] = {}
        self.zones_armed = 0
        self.model_tags_on_armed: dict[str, int] = {}
        self.placements = 0
        self.routes_created = 0
        self.placed_by_trigger: dict[str, int] = {}
        self.placed_by_poi: dict[str, int] = {}
        self.placed_limit_by_ticket: dict[int, float] = {}
        self.placed_bar_by_order: dict[int, int] = {}
        # fill linkage: fills cancel the order immediately before opening
        # the position at the SAME price — exact ticket→placement mapping.
        self._last_cancelled: tuple[int, float, int] | None = None  # ticket, price, placed_bar
        self.placed_bar_by_position: dict[int, int] = {}
        self.placed_limit_by_position: dict[int, float] = {}
        self.expired_section23 = 0
        self.expired_give_up = 0
        self.violated_pulls = 0
        self.be_applied = 0
        self.be_by_ticket: dict[int, int] = {}

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


def instrument(runner: BacktestRunner, counters: Counters) -> None:
    """Wrap the plain-class runner seams (the M2 stores are slots dataclasses
    and are instrumented via subclasses instead — see CountingOrderBook)."""
    original_pull = runner.cancel_pending_for_poi

    def counting_pull(poi_id):
        n = original_pull(poi_id)
        counters.violated_pulls += n
        return n

    runner.cancel_pending_for_poi = counting_pull  # type: ignore[method-assign]


class CountingOrderBook(PendingOrderBook):
    """Placement/expiry/cancel counters + exact cancel→open fill linkage.

    The M2 book is a slots dataclass, so instrumentation subclasses it
    (delegate to super, then record) — the stores' semantics are untouched.
    """

    counters: Counters

    def bind(self, counters: Counters) -> "CountingOrderBook":
        self.counters = counters
        return self

    def place(self, **kwargs):
        order = super().place(**kwargs)
        c = self.counters
        c.placements += 1
        trigger = kwargs.get("trigger")
        trigger_name = str(getattr(trigger, "value", trigger))
        c.placed_by_trigger[trigger_name] = c.placed_by_trigger.get(trigger_name, 0) + 1
        poi_id = kwargs.get("poi_id")
        c.placed_by_poi[poi_id] = c.placed_by_poi.get(poi_id, 0) + 1
        c.placed_limit_by_ticket[order.ticket] = order.entry_price
        c.placed_bar_by_order[order.ticket] = order.placed_bar
        return order

    def expired_by_section23(self, current_bar, timeframe):
        cancelled = super().expired_by_section23(current_bar, timeframe)
        self.counters.expired_section23 += len(cancelled)
        return cancelled

    def expired_by_give_up(self, current_bar):
        cancelled = super().expired_by_give_up(current_bar)
        self.counters.expired_give_up += len(cancelled)
        return cancelled

    def cancel(self, ticket):
        order = super().cancel(ticket)
        if order is not None:
            # Fill linkage: the runner cancels the order immediately before
            # opening the fill position at the SAME (limit) price.
            self.counters._last_cancelled = (
                order.ticket, order.entry_price, order.placed_bar
            )
        return order


class CountingPositionStore(PositionStore):
    """Fill-linkage + BE-modify counters over the slots-dataclass store."""

    counters: Counters

    def bind(self, counters: Counters) -> "CountingPositionStore":
        self.counters = counters
        return self

    def open(self, **kwargs):
        position = super().open(**kwargs)
        c = self.counters
        if c._last_cancelled is not None:
            _ticket, price, placed_bar = c._last_cancelled
            if price == kwargs.get("entry_price"):
                c.placed_bar_by_position[position.ticket] = placed_bar
                c.placed_limit_by_position[position.ticket] = price
            c._last_cancelled = None
        return position

    def modify_sl(self, ticket, new_sl):
        c = self.counters
        c.be_applied += 1
        c.be_by_ticket[ticket] = c.be_by_ticket.get(ticket, 0) + 1
        return super().modify_sl(ticket, new_sl)


def _kind_str(kind) -> str:
    return str(getattr(kind, "value", kind))


# ---------------------------------------------------------------------- #
# Main run
# ---------------------------------------------------------------------- #
def run(args: argparse.Namespace) -> dict:
    install_deterministic_poi_ids()
    from_ts = datetime.strptime(args.from_ts, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    to_ts = datetime.strptime(args.to_ts, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1) - timedelta(minutes=1)
    candles = load_window(from_ts, to_ts)
    if args.max_bars:
        candles = candles[: args.max_bars]
    if len(candles) < 50:
        raise SystemExit("window too small for the stack warm-up")

    series = CandleSeries(candles, TF)
    counters = Counters()
    registry = ZoneRegistry()

    engine = PipelineEngine()
    driver = DetectionDriver(TF)
    adapter = PipelineAdapter(engine, timeframe=TF)
    adapter.set_candles(candles)

    order_book = CountingOrderBook().bind(counters)
    position_store = CountingPositionStore().bind(counters)
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=order_book,
        position_store=position_store,
        config=RunnerConfig(
            equity=CONFIG["equity"],
            risk_fraction=CONFIG["risk_fraction"],
            pip_value_per_lot=CONFIG["pip_value_per_lot"],
            min_lots=CONFIG["min_lots"],
            lot_step=CONFIG["lot_step"],
            spread_price=CONFIG["spread_price"],
            news_events=list(CONFIG["news_events"]),
            allowed_sessions=tuple(Session(s) for s in CONFIG["allowed_sessions"]),
            timeframe=TF,
        ),
    )
    instrument(runner, counters)
    adapter.attach(runner)

    # Workflow-creation counter: candidate_from_route runs exactly once per
    # NEW §11 workflow (adapter._routed is discarded by pruning, so the
    # routed-set size is NOT a cumulative count).
    original_bridge = pipeline_adapter_module.candidate_from_route

    def counting_bridge(route):
        counters.routes_created += 1
        return original_bridge(route)

    pipeline_adapter_module.candidate_from_route = counting_bridge

    window_bars = args.window_bars
    started = time.perf_counter()
    progress_every = 500

    class DetectionCycle:
        """Rolling-window detection around the real handler (live-loop
        order: validate window → arm ONLY new POIs → bar cycle)."""

        def __init__(self, inner) -> None:
            self.inner = inner
            self.bars = 0

        def on_bar(self, bar, bar_index, clock) -> None:
            window = candles[max(0, bar_index - window_bars + 1): bar_index + 1]
            try:
                passed, results, _run, skipped, detected = driver.validate_window(
                    window, engine=engine, merge_first=True
                )
            except Exception as exc:  # noqa: BLE001 — loud, then abort (fail condition)
                print(f"[detect] EXCEPTION at bar {bar_index}: "
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
                    continue  # same episode (§5 terminality / §24 anchor preserved)
                engine.arm_at(poi, arm_bar=bar_index)  # series-relative §24 anchor
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
                    f"[progress] bar {self.bars}/{len(candles)}  {rate:.1f} bars/s  "
                    f"eta {eta / 60:.1f} min  armed={counters.zones_armed} "
                    f"placed={counters.placements} closed={len(runner.positions.closed_positions())}",
                    flush=True,
                )

    loop = BarLoop(series, DetectionCycle(runner))
    stats = loop.run()

    elapsed = time.perf_counter() - started
    result = runner.result()
    report = build_report(result)

    # ---------------- artifacts ---------------- #
    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    to_csv(report, out_dir / "trades.csv")
    to_json(report, out_dir / "report.json")

    funnel = {
        "bars_processed": stats.bars_processed,
        "window_from": candles[0].timestamp.isoformat(),
        "window_to": candles[-1].timestamp.isoformat(),
        "detection_window_bars": window_bars,
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
        "hard_cancelled_news": 0,  # news_events empty (§11 dormant — documented)
        "positions_opened": len(result.closed) + len(runner.positions.open_positions()),
        "positions_still_open": len(runner.positions.open_positions()),
        "closed_by_kind": _count_kinds(result),
        "be_modifies_applied": counters.be_applied,
        "friday_closes": sum(1 for c in result.closed if _kind_str(c.kind) == "friday_eod"),
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
        "equity_end": CONFIG["equity"] + report.metrics.net_pnl * CONFIG["pip_value_per_lot"],
    }
    by_trigger = {k: v.n_trades for k, v in report.by_trigger.items()}

    invariants = check_invariants(runner, counters, report, stats, funnel)

    summary = {
        "config": CONFIG,
        "window": {k: funnel[k] for k in ("window_from", "window_to", "bars_processed")},
        "funnel": funnel,
        "metrics": metrics,
        "by_trigger_trades": by_trigger,
        "invariants": invariants,
        "pass": all(v == "OK" for v in invariants.values()),
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, sort_keys=True, indent=2)
        handle.write("\n")
    print(json.dumps(summary, sort_keys=True, indent=2), flush=True)
    return summary


def _count_kinds(result) -> dict:
    kinds: dict[str, int] = {}
    for record in result.closed:
        key = _kind_str(record.kind)
        kinds[key] = kinds.get(key, 0) + 1
    return dict(sorted(kinds.items()))


def check_invariants(runner, counters, report, stats, funnel) -> dict:
    """Phase B exit-criteria checks (plan §4). Values are 'OK' or the failure."""
    checks: dict[str, str] = {}

    # 1. Bars processed.
    checks["bars_processed_nonzero"] = "OK" if stats.bars_processed > 0 else "FAIL: zero bars"

    # 2. §23/§24: no fill after expiry. The runner expires an order when
    #    bars_open >= limit BEFORE that bar's fills; the give-up backstop
    #    (20 bars) binds before §23 (M1 = 30), so the last fillable bar is
    #    placed_bar + 18 (bars_open 19; bar 20 cancels at its start).
    worst = -1
    unlinked = 0
    for record in runner.positions.closed_positions():
        placed_bar = counters.placed_bar_by_position.get(record.position.ticket)
        if placed_bar is None:
            unlinked += 1
            continue
        worst = max(worst, record.position.entry_bar - placed_bar)
    if unlinked:
        checks["no_fill_after_expiry"] = f"FAIL: {unlinked} fills without placement linkage"
    else:
        checks["no_fill_after_expiry"] = (
            "OK" if worst <= 18 else f"FAIL: fill {worst} bars after placement"
        )

    # 3. §11 one-shot: at most ONE placement per POI.
    max_per_poi = max(counters.placed_by_poi.values(), default=0)
    checks["one_shot_per_poi"] = "OK" if max_per_poi <= 1 else f"FAIL: {max_per_poi} placements for one POI"

    # 4. Fill price equals the resting limit price (touch semantics).
    bad_fills = [
        record.position.ticket
        for record in runner.positions.closed_positions()
        if record.position.ticket in counters.placed_limit_by_position
        and record.position.entry_price
        != counters.placed_limit_by_position[record.position.ticket]
    ]
    checks["fill_at_limit_price"] = "OK" if not bad_fills else f"FAIL: {len(bad_fills)} off-limit fills"

    # 5. Trigger D structurally unfireable on all-zero volume (A5 ruling).
    d_group = report.by_trigger.get("D_TWO_BAR_REVERSAL")
    d_count = d_group.n_trades if d_group else 0
    d_placed = counters.placed_by_trigger.get("D_TWO_BAR_REVERSAL", 0)
    checks["trigger_d_zero"] = (
        "OK" if d_count == 0 and d_placed == 0
        else f"FAIL: Trigger D placed={d_placed} trades={d_count}"
    )

    # 6. §5 one-touch: a POI never trades twice.
    trades_by_poi: dict[str, int] = {}
    for trade in report.trades:
        if trade.poi_id is not None:
            trades_by_poi[trade.poi_id] = trades_by_poi.get(trade.poi_id, 0) + 1
    double = {k: v for k, v in trades_by_poi.items() if v > 1}
    checks["no_poi_trades_twice"] = "OK" if not double else f"FAIL: {len(double)} POIs traded twice"

    # 7. BE modify applied at most once per ticket.
    double_be = {k: v for k, v in counters.be_by_ticket.items() if v > 1}
    checks["be_once_per_trade"] = "OK" if not double_be else f"FAIL: {len(double_be)} tickets modified twice"

    return checks


if __name__ == "__main__":
    summary = run(parse_args())
    raise SystemExit(0 if summary["pass"] else 2)
