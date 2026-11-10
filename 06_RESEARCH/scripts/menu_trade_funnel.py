#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MENU TRADE FUNNEL — plan -> place -> fill -> close (measurement only).

Lead Architect directive (2026-11-10): the stage metric is COUNTABLE
PRODUCT-PATH TRADES (armed -> sweep -> confirm -> plan -> place -> fill ->
close), not another abstract PASS rate and not edge. This harness answers one
question: on the product menu path, how many confirmations become a closed
trade, and for every plan that does not, what stopped it.

Composition (imported, NOT forked — no production logic is patched):

    MultiTFProductRuntime.run_batch      detection batch -> armed POIs
      -> ProductMenuEngine.register_armed (F5 arm instant = batch as_of)
      -> ProductMenuEngine.on_execution_bar  post-arm zone sweeps ->
                                             confirm -> plan (MenuWinner)
      -> PipelineAdapter.queue_menu_candidate
      -> BacktestRunner                     risk (evaluate_entry) -> pending
                                            LIMIT -> M2 touch fill -> SL/TP/
                                            BE/Friday close

The M5 execution series is walked by the production ``BarLoop``. The handler
is a thin wrapper that, on every closed M5 bar and BEFORE the runner's step:

  1. runs the due detection batch (same 48-M15-bar cadence as the frozen
     plan-complement harness, so arm instants line up with post_f5f7);
  2. feeds the menu the newly closed bars of every menu timeframe at
     ``as_of`` = the M5 bar's close instant;
  3. hands the bar to ``BacktestRunner.on_bar`` (which drains the queued
     winners through the risk-gated entry step on the SAME bar).

Window: 2024-04-01 -> 2024-05-01, warm-up from 2023-12-01 — the frozen window
of post_f1f2 / post_f5f7, so the funnel ties to those runs. Missing data
raises (fail loud); a batch exception is counted and reported, never hidden.

Measurement only: no threshold/tier/trigger/TP edits, no OPT-B, no OPT-2, no
expectancy or edge claim. ``NET_PL_DIAGNOSTIC`` is a raw sum of realized
price*volume, labelled NOT performance.

Artifacts (gitignored): ``06_RESEARCH/results/menu_trade_funnel_1m/``
``funnel_summary.json``, ``trades.csv``, ``drops.csv``, ``run.log``.
Report (committed): ``06_RESEARCH/MENU_TRADE_FUNNEL_1M_NOTE.md``.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
import traceback
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_SRC"))
sys.path.insert(0, str(ROOT / "06_RESEARCH" / "scripts"))

from smc.backtest.bar_loop import BarHandler, BarLoop  # noqa: E402
from smc.backtest.cost_model import CostConfig  # noqa: E402
from smc.backtest.data_feed import CandleSeries  # noqa: E402
from smc.backtest.orders import PendingOrderBook  # noqa: E402
from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.backtest.positions import PositionStore  # noqa: E402
from smc.backtest.runner import BacktestRunner, RunnerConfig  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.candle import Candle  # noqa: E402
from smc.data.resample import resample_ohlcv  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.multi_tf_runtime import (  # noqa: E402
    MultiTFProductRuntime,
    build_htf_prefixes,
)
from smc.orchestration.product_menu_mtf import (  # noqa: E402
    PRODUCT_MENU_CONFIRMATION_TIMEFRAMES,
    PRODUCT_MENU_DETECTION_TIMEFRAMES,
    ProductMenuEngine,
)
from smc.risk.fill_regime_policy import SKIP_PLACE_FAR_FROM_ZONE  # noqa: E402
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

# The SAME data loader as the frozen plan-complement ledger: reusing it (not
# re-implementing) keeps the M1 spine byte-identical to post_f1f2/post_f5f7.
from plan_complement_ledger import load_m1  # noqa: E402

DETECTION_TFS = [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15]
EXEC_TF = Timeframe.M5
DATA_PATH = ROOT / "07_DATA" / "XAUUSD_M1.parquet"

WARMUP_START = datetime(2023, 12, 1, tzinfo=timezone.utc)
WINDOW_START = datetime(2024, 4, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2024, 5, 1, tzinfo=timezone.utc)
#: Detection batches every 48 M15 bars = every 12 h (frozen plan-complement
#: cadence — the arm instants of post_f5f7 are reproduced exactly).
BATCH_EVERY_M15_BARS = 48


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    if not raw:
        return default
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


OUT_DIR = _env_path(
    "MENU_FUNNEL_OUT", ROOT / "06_RESEARCH" / "results" / "menu_trade_funnel_1m"
)
NOTE_PATH = _env_path(
    "MENU_FUNNEL_NOTE", ROOT / "06_RESEARCH" / "MENU_TRADE_FUNNEL_1M_NOTE.md"
)
RUN_LABEL = os.environ.get("MENU_FUNNEL_LABEL", "menu_trade_funnel_1m")
#: Plumbing smoke only (first N loop bars): never used for a reported funnel.
SMOKE_BARS = int(os.environ.get("MENU_FUNNEL_SMOKE_BARS", "0") or 0)

FEED_TFS = tuple(
    dict.fromkeys(
        tuple(PRODUCT_MENU_DETECTION_TIMEFRAMES)
        + tuple(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES)
    )
)


def _close_ts(bar: Candle) -> datetime:
    """Close instant of a closed bar (open timestamp + timeframe length)."""
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def _finite(value) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except Exception:  # noqa: BLE001 — non-numeric is simply "not finite"
        return False


def _dir_name(direction) -> str | None:
    if direction is None:
        return None
    return getattr(direction, "name", None) or str(direction)


def install_deterministic_poi_ids() -> None:
    """Deterministic POI ids (FR-4 pattern) so re-runs are comparable."""
    from itertools import count

    import smc.core.poi as poi_module

    counter = count(1)

    def _deterministic_id() -> str:
        return f"poi-{next(counter):06d}"

    poi_module.uuid4 = _deterministic_id  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# Instrumented stores (read-only counters — no behavior change)
# --------------------------------------------------------------------------- #
class CountingOrderBook(PendingOrderBook):
    """Pending-order book that records every placement/expiry/cancel.

    Subclassing the production book keeps the placement path byte-identical
    (same tickets, same order fields); the added surface is bookkeeping for
    the funnel only.
    """

    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict] = []
        self.by_ticket: dict[int, dict] = {}
        self.expired_section23: set[int] = set()
        self.expired_giveup: set[int] = set()
        self.cancelled_other: set[int] = set()

    def place(self, **kwargs):
        order = super().place(**kwargs)
        record = {
            "ticket": order.ticket,
            "poi_id": order.poi_id,
            "route_id": getattr(order, "route_id", None),
            "direction": _dir_name(order.direction),
            "entry_price": order.entry_price,
            "sl": order.sl,
            "tp": order.tp,
            "volume": order.volume,
            "placed_bar": order.placed_bar,
            "placed_at": order.placed_at,
            "rest_bars": order.rest_bars,
            "detection_tf": getattr(
                getattr(order, "detection_tf", None), "name", None
            ),
            "trigger": getattr(
                getattr(order, "trigger", None), "value", order.trigger
            ),
        }
        self.records.append(record)
        self.by_ticket[order.ticket] = record
        return order

    def expired_by_section23(self, current_bar: int, timeframe: Timeframe):
        out = super().expired_by_section23(current_bar, timeframe)
        for order in out:
            self.expired_section23.add(order.ticket)
        return out

    def expired_by_give_up(self, current_bar: int):
        out = super().expired_by_give_up(current_bar)
        for order in out:
            self.expired_giveup.add(order.ticket)
        return out

    def cancel(self, ticket: int):
        order = super().cancel(ticket)
        if order is not None:
            self.cancelled_other.add(order.ticket)
        return order

    def placed_with_tp(self) -> int:
        return sum(1 for r in self.records if r["tp"] is not None)


class CountingPositionStore(PositionStore):
    """Position store that records every fill (one row per opened position)."""

    def __init__(self) -> None:
        super().__init__()
        self.fills: list[dict] = []

    def open(self, **kwargs):
        position = super().open(**kwargs)
        self.fills.append(
            {
                "ticket": position.ticket,
                "poi_id": position.poi_id,
                "direction": _dir_name(position.direction),
                "entry_price": position.entry_price,
                "sl": position.sl,
                "tp": position.tp,
                "volume": position.volume,
                "entry_bar": position.entry_bar,
                "entry_at": position.entry_at,
            }
        )
        return position


# --------------------------------------------------------------------------- #
# Per-bar composition: batch -> menu -> runner
# --------------------------------------------------------------------------- #
class MenuCycle(BarHandler):
    """Wrap the runner with the product-menu feed for every closed M5 bar."""

    def __init__(
        self,
        *,
        runner: BacktestRunner,
        adapter: PipelineAdapter,
        runtime: MultiTFProductRuntime,
        engine: PipelineEngine,
        menu: ProductMenuEngine,
        series: dict,
        exec_bars: list[Candle],
        batch_instants: set,
        total_bars: int,
        started_at: float,
    ) -> None:
        self.runner = runner
        self.adapter = adapter
        self.runtime = runtime
        self.engine = engine
        self.menu = menu
        self.series = series
        self.exec_bars = exec_bars
        self.batch_instants = batch_instants
        self.total_bars = total_bars
        self.started_at = started_at
        self.feed_idx = {tf: 0 for tf in FEED_TFS}
        self.bars_done = 0
        self.batches = 0
        self.batch_errors = 0
        self.menu_errors = 0
        self.armed_calls = 0
        self.winners: list[dict] = []

    # -- steps ---------------------------------------------------------- #
    def _run_batch(self, bar: Candle, bar_index: int, as_of: datetime) -> None:
        """One detection batch at ``as_of`` (the F5 arm instant)."""
        self.batches += 1
        prefixes = build_htf_prefixes(self.series, as_of)
        exec_prefix = self.exec_bars[: bar_index + 1]
        try:
            report = self.runtime.run_batch(
                engine=self.engine,
                series_by_tf=prefixes,
                as_of=as_of,
                arm_bar=bar_index,
                adapter=self.adapter,
                execution_candles=exec_prefix,
            )
        except Exception:  # noqa: BLE001 — counted, reported, never hidden
            self.batch_errors += 1
            print(
                f"  BATCH_ERROR at {as_of.isoformat()}:\n{traceback.format_exc()}",
                flush=True,
            )
            return
        for poi in report.armed or ():
            det_tf = getattr(getattr(poi, "zone", None), "timeframe", None)
            if det_tf is None:
                continue
            # F5: the batch decision instant IS the arm instant.
            if self.menu.register_armed(poi, det_tf, armed_ts=as_of):
                self.armed_calls += 1

    def _feed(self, as_of: datetime) -> dict:
        """Newly closed bars per menu timeframe, visible at ``as_of``."""
        feed: dict = {}
        for tf in FEED_TFS:
            series = self.series.get(tf) or []
            index = self.feed_idx.get(tf, 0)
            start = index
            while index < len(series) and _close_ts(series[index]) <= as_of:
                index += 1
            self.feed_idx[tf] = index
            if index > start:
                feed[tf] = series[start:index]
        return feed

    def on_bar(self, bar: Candle, bar_index: int, clock) -> None:
        as_of = _close_ts(bar)

        # 1. Detection batch (arms new POIs) when this close is due.
        if as_of in self.batch_instants:
            self._run_batch(bar, bar_index, as_of)

        # 2. Menu: closed bars -> sweeps -> confirmations -> plans.
        feed = self._feed(as_of)
        if feed:
            try:
                winners = self.menu.on_execution_bar(feed, as_of=as_of)
            except Exception:  # noqa: BLE001 — counted and reported
                self.menu_errors += 1
                print(
                    f"  MENU_ERROR at {as_of.isoformat()}:\n{traceback.format_exc()}",
                    flush=True,
                )
                winners = []
            for winner in winners or ():
                self.winners.append(
                    {
                        "poi_id": winner.poi_id,
                        "route_id": winner.route_id,
                        "tier": getattr(winner, "tier", None),
                        "detection_tf": getattr(
                            getattr(winner, "detection_tf", None), "name", None
                        ),
                        "confirmation_tf": getattr(
                            getattr(winner, "confirmation_tf", None), "name", None
                        ),
                        "sweep_ts": getattr(winner, "sweep_ts", None),
                        "window_end_ts": getattr(winner, "window_end_ts", None),
                        "confirm_bar": bar_index,
                        "confirm_at": as_of,
                        "candidate": winner.candidate,
                    }
                )
                # Third party of the funnel: the risk-gated entry path. The
                # backtest runner reports no per-candidate outcomes, so this
                # is the ONE submit for this winner (F7 retry is live-only;
                # see the note's limitations).
                self.adapter.queue_menu_candidate(winner.candidate)

        # 3. The production runner: expiry -> manage -> fills -> entries.
        self.runner.on_bar(bar, bar_index, clock)

        self.bars_done += 1
        if self.bars_done % 1000 == 0:
            elapsed = max(time.perf_counter() - self.started_at, 1e-9)
            rate = self.bars_done / elapsed
            remaining = max(self.total_bars - self.bars_done, 0)
            eta_min = (remaining / rate) / 60.0 if rate > 0 else float("nan")
            print(
                f"  bar {self.bars_done}/{self.total_bars} "
                f"elapsed={elapsed/60.0:.1f}min rate={rate:.1f} bars/s "
                f"eta={eta_min:.1f}min | batches={self.batches} "
                f"armed={self.armed_calls} sweeps={self.menu.sweeps_total} "
                f"winners={len(self.winners)} "
                f"placed={len(self.runner.orders.records)} "
                f"fills={len(self.runner.positions.fills)}",
                flush=True,
            )


# --------------------------------------------------------------------------- #
# Accounting
# --------------------------------------------------------------------------- #
def _identity_key(route_id, poi_id) -> tuple:
    """Stable join key for a plan -> order -> fill -> close chain.

    POI id is the primary identity: ``PendingOrder`` carries no route id (the
    runner keeps ``_route_by_order`` privately and pops it at fill), while
    every order/fill/close carries the POI. A menu POI is one-shot, so one
    POI can never own two winners. Route id is only a fallback.
    """
    if poi_id:
        return ("poi", str(poi_id))
    return ("route", route_id)


def _outcome_maps(runner: BacktestRunner, book: CountingOrderBook):
    """Build the identity -> stage maps the drop classification reads."""
    blocked: dict = {}
    for entry in runner.blocked_log:
        key = _identity_key(getattr(entry, "route_id", None), entry.poi_id)
        blocked.setdefault(key, entry.blocked_by or "unknown")

    intent_events: dict = {}
    for event in runner.intents.events:
        key = _identity_key(event.get("route_id"), event.get("poi_id"))
        intent_events.setdefault(key, []).append(event)

    order_by_key: dict = {}
    for record in book.records:
        key = _identity_key(record.get("route_id"), record.get("poi_id"))
        order_by_key.setdefault(key, record)
    return blocked, intent_events, order_by_key


def classify_winners(
    runner: BacktestRunner, book: CountingOrderBook, winners: list[dict]
) -> list[dict]:
    """One row per plan: the furthest stage reached and the reason it stopped."""
    blocked, intent_events, order_by_key = _outcome_maps(runner, book)
    fills = {row["ticket"]: row for row in runner.positions.fills}
    closed = {rec.position.ticket: rec for rec in runner.result().closed}

    rows: list[dict] = []
    for index, winner in enumerate(winners, start=1):
        candidate = winner["candidate"]
        stamp: dict = {}
        raw = getattr(candidate, "signal_data_json", None)
        if raw:
            try:
                payload = json.loads(raw)
            except (TypeError, ValueError):
                payload = {}
            if isinstance(payload, dict):
                stamp = payload.get("product_menu") or {}
        route_id = winner.get("route_id")
        key = _identity_key(route_id, winner.get("poi_id"))

        stage, reason, ticket = "plan", "unaccounted", None
        order = order_by_key.get(key)
        block_reason = blocked.get(key)
        deferred = (
            block_reason == SKIP_PLACE_FAR_FROM_ZONE
        )  # R7: retryable, not a dead end

        if order is not None:
            ticket = order["ticket"]
            if ticket in closed:
                record = closed[ticket]
                stage, reason = "closed", record.kind
            elif ticket in fills:
                stage, reason = "filled_open_at_end", "position_open"
            elif ticket in book.expired_section23:
                stage, reason = "placed", "expired_section23_unfilled"
            elif ticket in book.expired_giveup:
                stage, reason = "placed", "expired_give_up_unfilled"
            elif ticket in book.cancelled_other:
                stage, reason = "placed", "withdrawn_before_fill"
            else:
                stage, reason = "placed", "resting_at_end"
            if deferred:
                reason = f"r7_reentry:{reason}"
        elif deferred:
            # R7 skip with no order yet: the R9 intent owns the placement.
            events = [e.get("event") for e in intent_events.get(key, [])]
            stage = "r7_deferred"
            reason = events[-1] if events else "intent_armed_no_event"
        elif block_reason is not None:
            stage, reason = "blocked", block_reason
        elif key in intent_events:
            events = [e.get("event") for e in intent_events[key]]
            stage = "r7_deferred"
            reason = events[-1] if events else "intent_no_event"
        else:
            stage, reason = "plan", "submitted_no_verdict"

        rows.append(
            {
                "winner_index": index,
                "poi_id": winner.get("poi_id"),
                "route_id": route_id,
                # The tier name rides the candidate's product_menu stamp (the
                # MenuWinner itself carries detection/confirmation TFs).
                "tier": stamp.get("tier") or winner.get("detection_tf"),
                "detection_tf": winner.get("detection_tf"),
                "confirmation_tf": winner.get("confirmation_tf"),
                "t_arm": stamp.get("armed_ts"),
                "t_sweep": stamp.get("sweep_ts"),
                "t_confirm": winner.get("confirm_at").isoformat()
                if winner.get("confirm_at")
                else None,
                "direction": _dir_name(getattr(candidate, "direction", None)),
                "entry_price": getattr(candidate, "entry_price", None),
                "sl_price": getattr(candidate, "sl_price", None),
                "tp_price": getattr(candidate, "tp_price", None),
                "tp_source": getattr(candidate, "tp_source", None),
                "entry_anchor": getattr(candidate, "entry_anchor", None),
                "stage": stage,
                "reason": reason,
                "ticket": ticket,
            }
        )
    return rows


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})


def _trade_rows(runner: BacktestRunner) -> list[dict]:
    rows = []
    route_ids = runner.result().route_ids
    for record in runner.result().closed:
        position = record.position
        # A BE scratch is a stop-out at a stop that is NOT the placement stop:
        # the runner moved the SL (PureRunner BE) and the trade then closed at
        # the moved level. Exact test — no tolerance is invented.
        moved_stop = (
            record.kind == "stop_loss"
            and _finite(position.original_sl)
            and _finite(record.exit_price)
            and abs(record.exit_price - position.original_sl) > 1e-9
        )
        # Ledger arithmetic (exact, same price*volume units as realized_pnl):
        # the risk the PLACED size carried. LOT_MAX_SAFETY (0.10) caps the
        # sized lots, so a tight stop means the intended risk fraction is not
        # what the position actually carries — recorded, never adjusted here.
        price_at_risk = (
            abs(position.entry_price - position.original_sl) * position.volume
            if _finite(position.original_sl)
            else None
        )
        rows.append(
            {
                "ticket": position.ticket,
                "poi_id": position.poi_id,
                "route_id": route_ids.get(position.ticket),
                "direction": _dir_name(position.direction),
                "volume": position.volume,
                "entry_price": position.entry_price,
                "entry_at": position.entry_at,
                "entry_bar": position.entry_bar,
                "sl_at_entry": position.original_sl,
                "tp_price": position.tp,
                "exit_price": record.exit_price,
                "exit_at": record.exit_at,
                "exit_bar": record.exit_bar,
                "kind": record.kind,
                "be_scratch_derived": "YES" if moved_stop else "NO",
                "lots_at_cap": "YES" if position.volume >= 0.10 - 1e-9 else "NO",
                "price_at_risk_raw": price_at_risk,
                "win": "YES" if record.win else "NO",
                "realized_pnl_raw": record.realized_pnl,
                "bars_held": record.bars_held,
                "cost_usd": record.cost_usd,
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def run() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        raise SystemExit(f"DATA_GAP: missing {DATA_PATH}")
    started = time.perf_counter()

    print("=" * 74, flush=True)
    print("MENU TRADE FUNNEL — plan -> place -> fill -> close (measurement)", flush=True)
    print(f"window={WINDOW_START.date()}..{WINDOW_END.date()} "
          f"warmup={WARMUP_START.date()} label={RUN_LABEL}", flush=True)
    print("Product menu path only. No threshold/tier/trigger/TP edits. "
          "No edge/PnL claim.", flush=True)
    print("=" * 74, flush=True)

    install_deterministic_poi_ids()

    m1_all = load_m1(DATA_PATH, WARMUP_START, WINDOW_END)
    if not m1_all:
        raise SystemExit("DATA_GAP: no M1 bars in the requested window")
    print(f"loaded M1 bars={len(m1_all)}", flush=True)

    needed = set(DETECTION_TFS) | set(FEED_TFS) | {EXEC_TF}
    series: dict = {}
    for tf in sorted(needed, key=lambda t: t.minutes, reverse=True):
        series[tf] = resample_ohlcv(m1_all, tf)
        print(f"  resampled {tf.name}={len(series[tf])}", flush=True)

    exec_all = series[EXEC_TF]
    if not exec_all:
        raise SystemExit("DATA_GAP: no execution bars")
    window_bars = [c for c in exec_all if c.timestamp >= WINDOW_START]
    if not window_bars:
        raise SystemExit("DATA_GAP: no execution bars inside the window")
    print(f"  execution bars in window (M5)={len(window_bars)}", flush=True)

    # Detection batch instants: every 48th M15 close inside the window (the
    # frozen plan-complement cadence — same arm instants as post_f5f7).
    m15_window = [
        c for c in series[Timeframe.M15]
        if WINDOW_START <= c.timestamp < WINDOW_END
    ]
    batch_instants = {
        _close_ts(m15_window[i])
        for i in range(0, len(m15_window), BATCH_EVERY_M15_BARS)
    }
    print(f"  M15 window bars={len(m15_window)} -> "
          f"batch instants={len(batch_instants)}", flush=True)

    # ---- the production stack ---------------------------------------- #
    engine = PipelineEngine()
    menu = ProductMenuEngine(symbol="XAUUSD")
    adapter = PipelineAdapter(engine, timeframe=EXEC_TF, menu_confirmation=menu)
    adapter.set_candles(exec_all)
    runtime = MultiTFProductRuntime(
        detection_timeframes=DETECTION_TFS, execution_timeframe=EXEC_TF
    )
    order_book = CountingOrderBook()
    positions = CountingPositionStore()
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=order_book,
        position_store=positions,
        config=RunnerConfig(
            equity=10_000.0,
            risk_fraction=0.01,
            pip_value_per_lot=10.0,
            min_lots=0.01,
            lot_step=0.01,
            allowed_sessions=(Session.ASIA, Session.LONDON, Session.NEW_YORK),
            news_events=[],
            timeframe=EXEC_TF,
            spread_price=0.0,
            cost=CostConfig(),
        ),
    )
    adapter.attach(runner)

    cycle = MenuCycle(
        runner=runner,
        adapter=adapter,
        runtime=runtime,
        engine=engine,
        menu=menu,
        series=series,
        exec_bars=exec_all,
        batch_instants=batch_instants,
        total_bars=len(window_bars),
        started_at=started,
    )
    # The loop bound is a TIMESTAMP (inclusive), so the smoke bound is simply
    # the last bar of the first N window bars — the same production BarLoop.
    end_timestamp = window_bars[-1].timestamp
    if SMOKE_BARS:
        end_timestamp = window_bars[min(SMOKE_BARS, len(window_bars)) - 1].timestamp
        print(f"  SMOKE MODE: loop stops at {end_timestamp.isoformat()}", flush=True)
    cycle.total_bars = sum(
        1 for c in exec_all
        if WINDOW_START <= c.timestamp <= end_timestamp
    )

    loop = BarLoop(CandleSeries(exec_all, EXEC_TF), cycle)
    print("running…", flush=True)
    stats = loop.run(
        start_timestamp=WINDOW_START, end_timestamp=end_timestamp
    )
    elapsed = max(time.perf_counter() - started, 1e-9)
    print(
        f"loop done: bars={stats.bars_processed} batches={cycle.batches} "
        f"batch_errors={cycle.batch_errors} menu_errors={cycle.menu_errors} "
        f"elapsed={elapsed/60.0:.1f}min",
        flush=True,
    )

    # ---- funnel ------------------------------------------------------ #
    result = runner.result()
    counters = menu.counters()
    menu_retry = adapter.menu_counters()
    drops = classify_winners(runner, order_book, cycle.winners)
    trades = _trade_rows(runner)

    blocked_by = Counter(
        entry.blocked_by or "unknown" for entry in result.blocked
    )
    exit_mix = Counter(record.kind for record in result.closed)
    be_scratch = sum(1 for row in trades if row["be_scratch_derived"] == "YES")
    lots_at_cap = sum(1 for row in trades if row["lots_at_cap"] == "YES")
    stage_mix = Counter(row["stage"] for row in drops)
    # "Drops" are the plans that did NOT become a closed trade; a close kind
    # (stop_loss / take_profit) is an OUTCOME, counted by EXIT_MIX only.
    drop_reasons = Counter(
        row["reason"] for row in drops if row["stage"] != "closed"
    )

    armed_total = cycle.armed_calls
    filled = len(positions.fills)
    closed = len(result.closed)
    placed = len(order_book.records)
    accepted = placed  # every placement in this run is a menu-path placement

    funnel = {
        "armed_pois_total": armed_total,
        "armed_pois_live_at_end": len(getattr(menu, "_armed", {})),
        "sweeps": getattr(menu, "sweeps_total", None),
        "winners_plans": len(cycle.winners),
        "accepted_placed": accepted,
        "blocked": sum(blocked_by.values()),
        "placed_resting": placed,
        "filled": filled,
        "closed": closed,
        "open_at_end": len(positions.open_positions()),
        "resting_at_end": len(order_book.active()),
    }

    summary = {
        "RUN": RUN_LABEL,
        "SMOKE_BARS": SMOKE_BARS or None,
        "LOGIC_CHANGED": "NO",
        "WINDOW_START": WINDOW_START.isoformat(),
        "WINDOW_END": WINDOW_END.isoformat(),
        "WARMUP_START": WARMUP_START.isoformat(),
        "DATA": str(DATA_PATH),
        "M1_BARS": len(m1_all),
        "EXEC_BARS_RUN": stats.bars_processed,
        "BATCHES": cycle.batches,
        "BATCH_ERRORS": cycle.batch_errors,
        "MENU_ERRORS": cycle.menu_errors,
        "FUNNEL": funnel,
        "STAGE_MIX": dict(stage_mix),
        "BLOCKED_BY": dict(blocked_by),
        "EXIT_MIX": dict(exit_mix),
        "BE_SCRATCH_DERIVED": be_scratch,
        "LOTS_AT_SAFETY_CAP": lots_at_cap,
        "DROP_REASONS": dict(drop_reasons),
        "TOP_DROPS": [
            f"{reason}={count}" for reason, count in drop_reasons.most_common(8)
        ],
        "MENU_COUNTERS": counters,
        "MENU_RETRY": menu_retry,
        "ORDER_BOOK": {
            "placed": placed,
            "placed_with_tp": order_book.placed_with_tp(),
            "expired_section23": len(order_book.expired_section23),
            "expired_give_up": len(order_book.expired_giveup),
            # ``_apply_fills`` consumes a filled order through ``cancel``, so
            # the raw cancel count is not "withdrawn": subtract the fills.
            "cancel_calls_raw": len(order_book.cancelled_other),
            "withdrawn_before_fill": len(
                order_book.cancelled_other
                - {row["ticket"] for row in positions.fills}
            ),
        },
        "INTENTS_R9": dict(
            Counter(event.get("event") for event in runner.intents.events)
        ),
        "NET_PL_DIAGNOSTIC": {
            "n_closed": closed,
            "sum_realized_pnl_raw": round(
                sum(record.realized_pnl for record in result.closed), 6
            )
            if closed
            else 0.0,
            "LABEL": "raw price*volume sum — NOT performance, NOT edge",
        },
        "ELAPSED_SECONDS": round(elapsed, 1),
        "NOTE_PATH": str(NOTE_PATH),
    }

    # ---- artifacts --------------------------------------------------- #
    with (OUT_DIR / "funnel_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)

    drop_fields = [
        "winner_index", "poi_id", "route_id", "tier", "detection_tf",
        "confirmation_tf", "t_arm", "t_sweep", "t_confirm", "direction",
        "entry_price", "sl_price", "tp_price", "tp_source", "entry_anchor",
        "stage", "reason", "ticket",
    ]
    _write_csv(OUT_DIR / "drops.csv", drop_fields, drops)

    trade_fields = [
        "ticket", "poi_id", "route_id", "direction", "volume",
        "entry_price", "entry_at", "entry_bar", "sl_at_entry", "tp_price",
        "exit_price", "exit_at", "exit_bar", "kind", "be_scratch_derived",
        "lots_at_cap", "price_at_risk_raw", "win", "realized_pnl_raw",
        "bars_held", "cost_usd",
    ]
    _write_csv(OUT_DIR / "trades.csv", trade_fields, trades)

    print(json.dumps(
        {
            "FUNNEL": funnel,
            "STAGE_MIX": dict(stage_mix),
            "BLOCKED_BY": dict(blocked_by),
            "EXIT_MIX": dict(exit_mix),
            "TOP_DROPS": summary["TOP_DROPS"],
            "OUT": str(OUT_DIR),
        }, indent=2, default=str), flush=True)
    print(f"artifacts: {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(run())
