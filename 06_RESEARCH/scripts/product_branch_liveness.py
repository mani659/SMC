#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PRODUCT BRANCH LIVENESS — can each Stage-3 trigger A–F complete the funnel?

Local-implementer audit (2026-11-25). One question only: on the PRODUCT menu
path, which trigger types reach completion -> route -> placement -> fill in a
declared window? This is a functional milestone check ("all branches producing
trades"), NOT expectancy, NOT edge, NOT a retune.

Composition (imported from the frozen product harness, never forked):

    MultiTFProductRuntime.run_batch  -> armed POIs
      -> ProductMenuEngine.register_armed / on_execution_bar
         (per-tier trigger subsets: DAY = A..F, H4/H1/M15 = A,D,F)
      -> PipelineAdapter.queue_menu_candidate
      -> BacktestRunner (risk -> pending LIMIT -> M2 touch fill -> SL/TP/BE)
      -> BacktestRunner.on_bar

``menu_trade_funnel.MenuCycle`` is reused verbatim as the per-bar driver; this
script only supplies the window, the counters and the artifact writers.

Instrumentation is read-only and restored in ``finally``:

* each of the six trigger classes' ``evaluate`` is wrapped to count every
  non-None completion the router observes (letter, detection TF, confirm TF,
  POI) — the tap never alters a return value;
* ``ProductMenuEngine._candidate`` is wrapped to count C3 in-between gate
  rejections per trigger (the only place a completion fails to become a plan);
* ``ProductMenuEngine.register_armed`` is wrapped to count armed POIs by
  detection TF;
* the order book / position store subclasses record ``trigger`` per placement
  and per fill (the production fields, not a second derivation).

Window is declared BEFORE any count: exec 2025-09-01 -> 2025-11-30 (M5), the
LOCKED Phase-4 product calendar, warm-up from 2025-08-01. No window shopping.

Measurement only: no threshold/tier/trigger/TP/risk edits, no OPT-B, no
locked-constant change, no performance claim. ``NET_PL_DIAGNOSTIC`` (if
emitted by the runner) is a raw price*volume sum, labelled NOT performance.

Artifacts (gitignored): 06_RESEARCH/results/product_branch_liveness/
  summary.json, winners.csv, orders.csv, fills.csv, blocks.csv, run.log
Report (committed): 06_RESEARCH/PRODUCT_BRANCH_LIVENESS_REPORT.md
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_SRC"))
sys.path.insert(0, str(ROOT / "06_RESEARCH" / "scripts"))

from smc.backtest.bar_loop import BarLoop  # noqa: E402
from smc.backtest.cost_model import CostConfig  # noqa: E402
from smc.backtest.data_feed import CandleSeries  # noqa: E402
from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.backtest.runner import BacktestRunner, RunnerConfig  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.candle import Candle  # noqa: E402
from smc.data.resample import resample_ohlcv  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime  # noqa: E402
from smc.orchestration.product_menu_mtf import (  # noqa: E402
    PRODUCT_MENU_CONFIRMATION_TIMEFRAMES,
    PRODUCT_MENU_DETECTION_TIMEFRAMES,
    ProductMenuEngine,
)
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.triggers.trigger_a_choch import ChochReversalTrigger  # noqa: E402
from smc.triggers.trigger_b_leading_diagonal import LeadingDiagonalTrigger  # noqa: E402
from smc.triggers.trigger_c_ending_diagonal import EndingDiagonalTrigger  # noqa: E402
from smc.triggers.trigger_d_two_bar import TwoBarReversalTrigger  # noqa: E402
from smc.triggers.trigger_e_rsi_divergence import RsiDivergenceTrigger  # noqa: E402
from smc.triggers.trigger_f_bos_ob import BosObContinuationTrigger  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

# The frozen product composition (imported, never forked).
import menu_trade_funnel as mtf  # noqa: E402
from plan_complement_ledger import load_m1  # noqa: E402

DETECTION_TFS = [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15]
EXEC_TF = Timeframe.M5
DATA_PATH = ROOT / "07_DATA" / "XAUUSD_M1.parquet"

# ---- DECLARED WINDOW (fixed before any count is read) --------------------- #
WARMUP_START = datetime(2025, 8, 1, tzinfo=timezone.utc)
WINDOW_START = datetime(2025, 9, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2025, 12, 1, tzinfo=timezone.utc)  # exclusive
BATCH_EVERY_M15_BARS = 48  # frozen plan-complement cadence (12 h)

LETTERS = ("A", "B", "C", "D", "E", "F")
TAP_CLASSES = (
    ChochReversalTrigger,
    LeadingDiagonalTrigger,
    EndingDiagonalTrigger,
    TwoBarReversalTrigger,
    RsiDivergenceTrigger,
    BosObContinuationTrigger,
)

OUT_DIR = ROOT / "06_RESEARCH" / "results" / "product_branch_liveness"
_run_env = os.environ.get("BRANCH_LIVENESS_OUT")
if _run_env:
    OUT_DIR = Path(_run_env) if Path(_run_env).is_absolute() else ROOT / _run_env
SMOKE_BARS = int(os.environ.get("BRANCH_LIVENESS_SMOKE_BARS", "0") or 0)

FEED_TFS = tuple(
    dict.fromkeys(
        tuple(PRODUCT_MENU_DETECTION_TIMEFRAMES)
        + tuple(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES)
    )
)


def _close_ts(bar: Candle) -> datetime:
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def _letter(value) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", None) or str(value)


def _tf_name(tf) -> str | None:
    return getattr(tf, "name", None) or (str(tf) if tf is not None else None)


# --------------------------------------------------------------------------- #
# Recording stores (production fields only)
# --------------------------------------------------------------------------- #
class RecordingPositionStore(mtf.CountingPositionStore):
    """Position store that also records the originating trigger per fill."""

    def open(self, **kwargs):
        position = super().open(**kwargs)
        self.fills[-1]["trigger"] = _letter(getattr(position, "trigger", None))
        self.fills[-1]["detection_tf"] = _tf_name(
            getattr(position, "detection_tf", None)
        )
        return position


# --------------------------------------------------------------------------- #
# Read-only instrumentation
# --------------------------------------------------------------------------- #
class LivenessTap:
    """Counts completions / gate rejects / arms without changing behaviour."""

    def __init__(self, menu: ProductMenuEngine) -> None:
        self.menu = menu
        self.completions = Counter()          # (letter, det_tf, conf_tf)
        self.completion_pois = defaultdict(set)  # letter -> {poi_id}
        self.completion_rows: list[dict] = []
        self.gate_rejects = Counter()         # letter -> C3 rejects
        self.armed_by_det_tf = Counter()
        self.armed_pois: set[str] = set()
        self._orig = []

    def __enter__(self) -> "LivenessTap":
        for cls in TAP_CLASSES:
            original = cls.evaluate
            self._orig.append((cls, original))

            def make(bound_cls, orig):
                def tapped(trigger_self, context):
                    signal = orig(trigger_self, context)
                    if signal is not None:
                        poi = getattr(context, "poi", None)
                        zone = getattr(poi, "zone", None)
                        det = _tf_name(getattr(zone, "timeframe", None))
                        candles = getattr(context, "candles", None) or ()
                        idx = getattr(context, "bar_index", None)
                        conf = None
                        if isinstance(idx, int) and 0 <= idx < len(candles):
                            conf = _tf_name(getattr(candles[idx], "timeframe", None))
                        letter = _letter(bound_cls.type)
                        self.completions[(letter, det, conf)] += 1
                        poi_id = getattr(poi, "id", None)
                        if poi_id is not None:
                            self.completion_pois[letter].add(str(poi_id))
                        self.completion_rows.append(
                            {
                                "trigger": letter,
                                "poi_id": poi_id,
                                "detection_tf": det,
                                "confirmation_tf": conf,
                                "bar_index": idx,
                            }
                        )
                    return signal

                return tapped

            cls.evaluate = make(cls, original)  # type: ignore[assignment]

        menu = self.menu
        original_candidate = menu._candidate

        def tapped_candidate(episode, route, tf, *, window_end_ts=None):
            out = original_candidate(
                episode, route, tf, window_end_ts=window_end_ts
            )
            if out is None:
                self.gate_rejects[
                    _letter(getattr(route.signal, "trigger", None))
                ] += 1
            return out

        menu._candidate = tapped_candidate  # type: ignore[assignment]
        self._menu_candidate_installed = True

        original_register = menu.register_armed

        def tapped_register(poi, detection_tf, *, armed_ts=None):
            accepted = original_register(poi, detection_tf, armed_ts=armed_ts)
            if accepted:
                self.armed_by_det_tf[_tf_name(detection_tf)] += 1
                poi_id = getattr(poi, "id", None)
                if poi_id is not None:
                    self.armed_pois.add(str(poi_id))
            return accepted

        menu.register_armed = tapped_register  # type: ignore[assignment]
        return self

    def __exit__(self, *exc) -> None:
        for cls, original in self._orig:
            cls.evaluate = original  # type: ignore[assignment]
        try:
            del self.menu._candidate  # type: ignore[attr-defined]
        except AttributeError:
            pass
        try:
            del self.menu.register_armed  # type: ignore[attr-defined]
        except AttributeError:
            pass
        return False


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def run() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        raise SystemExit(f"DATA_GAP: missing {DATA_PATH}")
    started = time.perf_counter()

    print("=" * 78, flush=True)
    print("PRODUCT BRANCH LIVENESS — per-trigger funnel on the product menu path",
          flush=True)
    print(f"exec {WINDOW_START.date()}..{WINDOW_END.date()} (M5) "
          f"warmup {WARMUP_START.date()}", flush=True)
    print("Measurement only: no threshold/tier/trigger/TP/risk edits. "
          "No edge/PnL claim.", flush=True)
    print("=" * 78, flush=True)

    mtf.install_deterministic_poi_ids()

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

    # ---- production stack (identical wiring to menu_trade_funnel) ------ #
    engine = PipelineEngine()
    menu = ProductMenuEngine(symbol="XAUUSD")
    adapter = PipelineAdapter(engine, timeframe=EXEC_TF, menu_confirmation=menu)
    adapter.set_candles(exec_all)
    runtime = MultiTFProductRuntime(
        detection_timeframes=DETECTION_TFS, execution_timeframe=EXEC_TF
    )
    order_book = mtf.CountingOrderBook()
    positions = RecordingPositionStore()
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

    cycle = mtf.MenuCycle(
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

    end_timestamp = window_bars[-1].timestamp
    if SMOKE_BARS:
        end_timestamp = window_bars[min(SMOKE_BARS, len(window_bars)) - 1].timestamp
        print(f"  SMOKE MODE: loop stops at {end_timestamp.isoformat()}", flush=True)
    cycle.total_bars = sum(
        1 for c in exec_all if WINDOW_START <= c.timestamp <= end_timestamp
    )

    stats = None
    with LivenessTap(menu) as tap:
        loop = BarLoop(CandleSeries(exec_all, EXEC_TF), cycle)
        print("running…", flush=True)
        try:
            stats = loop.run(
                start_timestamp=WINDOW_START, end_timestamp=end_timestamp
            )
        finally:
            elapsed = max(time.perf_counter() - started, 1e-9)
            print(
                f"loop done: bars={getattr(stats, 'bars_processed', 'ERR')} "
                f"batches={cycle.batches} batch_errors={cycle.batch_errors} "
                f"menu_errors={cycle.menu_errors} "
                f"elapsed={elapsed/60.0:.1f}min",
                flush=True,
            )

    result = runner.result()
    menu_counters = menu.counters()
    adapter_counters = adapter.menu_counters()

    # ---- per-winner rows (route stage) --------------------------------- #
    stamp_by_poi: dict = {}
    winner_rows: list[dict] = []
    for index, winner in enumerate(cycle.winners, start=1):
        candidate = winner["candidate"]
        stamp = {}
        if candidate.signal_data_json:
            try:
                stamp = json.loads(candidate.signal_data_json).get(
                    "product_menu", {}
                )
            except (TypeError, ValueError):
                stamp = {}
        letter = _letter(getattr(candidate, "trigger", None))
        stamp_by_poi[str(winner.get("poi_id"))] = stamp
        winner_rows.append(
            {
                "winner_index": index,
                "poi_id": winner.get("poi_id"),
                "route_id": winner.get("route_id"),
                "trigger": letter,
                "tier": stamp.get("tier"),
                "detection_tf": stamp.get("detection_tf") or winner.get("detection_tf"),
                "confirmation_tf": stamp.get("confirmation_tf")
                or winner.get("confirmation_tf"),
                "direction": _dir_name(getattr(candidate, "direction", None)),
                "entry_price": getattr(candidate, "entry_price", None),
                "sl_price": getattr(candidate, "sl_price", None),
                "tp_price": getattr(candidate, "tp_price", None),
                "t_arm": stamp.get("armed_ts"),
                "t_sweep": stamp.get("sweep_ts"),
                "t_confirm": stamp.get("completion_ts"),
            }
        )

    # ---- per-order rows (placement stage) ------------------------------ #
    order_rows = []
    order_trigger_by_ticket: dict = {}
    for record in order_book.records:
        letter = _letter(record.get("trigger"))
        order_trigger_by_ticket[record["ticket"]] = letter
        order_rows.append(
            {
                "ticket": record["ticket"],
                "poi_id": record.get("poi_id"),
                "route_id": record.get("route_id"),
                "trigger": letter,
                "detection_tf": record.get("detection_tf"),
                "direction": record.get("direction"),
                "entry_price": record.get("entry_price"),
                "sl": record.get("sl"),
                "tp": record.get("tp"),
                "volume": record.get("volume"),
                "placed_at": record.get("placed_at"),
                "placed_bar": record.get("placed_bar"),
            }
        )

    closed_by_ticket = {rec.position.ticket: rec for rec in result.closed}
    fill_rows = []
    for row in positions.fills:
        ticket = row["ticket"]
        record = closed_by_ticket.get(ticket)
        fill_rows.append(
            {
                "ticket": ticket,
                "poi_id": row.get("poi_id"),
                "trigger": row.get("trigger")
                or order_trigger_by_ticket.get(ticket),
                "direction": row.get("direction"),
                "entry_price": row.get("entry_price"),
                "sl_at_entry": row.get("sl"),
                "tp_price": row.get("tp"),
                "volume": row.get("volume"),
                "entry_at": row.get("entry_at"),
                "entry_bar": row.get("entry_bar"),
                "exit_kind": getattr(record, "kind", None) if record else "open_at_end",
                "exit_at": getattr(record, "exit_at", None) if record else None,
            }
        )

    # ---- blocked (pre-place) by trigger + reason ----------------------- #
    block_rows = []
    blocked_by_trigger_reason = Counter()
    blocked_total_reasons = Counter()
    for entry in result.blocked:
        letter = _letter(getattr(entry, "trigger", None))
        if letter is None:
            letter = _letter(
                next(
                    (w["trigger"] for w in winner_rows
                     if w["poi_id"] == entry.poi_id),
                    None,
                )
            )
        reason = entry.blocked_by or "unknown"
        blocked_total_reasons[reason] += 1
        blocked_by_trigger_reason[(letter, reason)] += 1
        block_rows.append(
            {
                "poi_id": entry.poi_id,
                "trigger": letter,
                "reason": reason,
                "route_id": getattr(entry, "route_id", None),
                "bar_index": getattr(entry, "bar_index", None),
            }
        )

    # ---- expired / withdrawn unfilled ---------------------------------- #
    filled_tickets = {row["ticket"] for row in positions.fills}
    expired_section23 = order_book.expired_section23
    expired_giveup = order_book.expired_giveup
    withdrawn = order_book.cancelled_other - filled_tickets

    def _count_orders(tickets) -> Counter:
        out: Counter = Counter()
        for ticket in tickets:
            out[order_trigger_by_ticket.get(ticket)] += 1
        return out

    expired_s23_by_trigger = _count_orders(expired_section23)
    expired_giveup_by_trigger = _count_orders(expired_giveup)
    withdrawn_by_trigger = _count_orders(withdrawn)

    # ---- aggregates ----------------------------------------------------- #
    routes_by_trigger = Counter(w["trigger"] for w in winner_rows)
    placed_by_trigger = Counter(r["trigger"] for r in order_rows)
    fills_by_trigger = Counter(r["trigger"] for r in fill_rows)
    closed_by_trigger = Counter(
        r["trigger"] for r in fill_rows if r["exit_kind"] != "open_at_end"
    )
    blocked_by_trigger = Counter(
        letter for (letter, _reason), n in blocked_by_trigger_reason.items()
        for _ in range(n)
    )

    per_trigger = {}
    for letter in LETTERS:
        completions = sum(
            n for (lt, _det, _conf), n in tap.completions.items() if lt == letter
        )
        per_trigger[letter] = {
            "completed_signals": completions,
            "distinct_pois_with_completion": len(tap.completion_pois.get(letter, ())),
            "routes": routes_by_trigger.get(letter, 0),
            "gate_rejected_c3": tap.gate_rejects.get(letter, 0),
            "accepted_placed": placed_by_trigger.get(letter, 0),
            "fills": fills_by_trigger.get(letter, 0),
            "closed": closed_by_trigger.get(letter, 0),
            "blocked_pre_place": blocked_by_trigger.get(letter, 0),
            "expired_section23_unfilled": expired_s23_by_trigger.get(letter, 0),
            "expired_give_up_unfilled": expired_giveup_by_trigger.get(letter, 0),
            "withdrawn_before_fill": withdrawn_by_trigger.get(letter, 0),
            "block_reasons": {
                f"{reason}": n
                for (lt, reason), n in blocked_by_trigger_reason.items()
                if lt == letter
            },
        }

    tiers_by_trigger: dict = defaultdict(Counter)
    for row in winner_rows:
        tiers_by_trigger[row["trigger"]][
            f"{row['tier']}:{row['detection_tf']}/{row['confirmation_tf']}"
        ] += 1

    completions_by_tier = Counter()
    for (letter, det, conf), n in tap.completions.items():
        completions_by_tier[f"{letter}|{det}/{conf}"] += n

    total_fills = len(fill_rows)
    dominant = None
    if total_fills:
        letter, n = fills_by_trigger.most_common(1)[0]
        dominant = {"trigger": letter, "share_pct": round(100.0 * n / total_fills, 2)}

    summary = {
        "RUN": "product_branch_liveness",
        "LOGIC_CHANGED": "NO",
        "SMOKE_BARS": SMOKE_BARS or None,
        "WINDOW_START": WINDOW_START.isoformat(),
        "WINDOW_END_EXCLUSIVE": WINDOW_END.isoformat(),
        "WARMUP_START": WARMUP_START.isoformat(),
        "EXEC_TF": EXEC_TF.name,
        "DETECTION_TFS": [tf.name for tf in DETECTION_TFS],
        "BATCH_EVERY_M15_BARS": BATCH_EVERY_M15_BARS,
        "EXEC_BARS_RUN": getattr(stats, "bars_processed", None),
        "BATCHES": cycle.batches,
        "BATCH_ERRORS": cycle.batch_errors,
        "MENU_ERRORS": cycle.menu_errors,
        "ARMED": {
            "total": len(tap.armed_pois),
            "by_detection_tf": dict(tap.armed_by_det_tf),
            "register_calls_accepted": sum(tap.armed_by_det_tf.values()),
            "live_at_end": len(getattr(menu, "_armed", {})),
        },
        "TOTALS": {
            "routes": len(winner_rows),
            "accepted_placed": len(order_rows),
            "fills": total_fills,
            "closed": sum(1 for r in fill_rows if r["exit_kind"] != "open_at_end"),
            "open_at_end": len(positions.open_positions()),
            "blocked_pre_place": sum(blocked_total_reasons.values()),
            "expired_section23_unfilled": len(expired_section23),
            "expired_give_up_unfilled": len(expired_giveup),
            "withdrawn_before_fill": len(withdrawn),
        },
        "BY_TRIGGER": per_trigger,
        "COMPLETIONS_BY_LETTER_TIER": dict(completions_by_tier),
        "ROUTES_BY_TRIGGER_TIER": {
            letter: dict(counts) for letter, counts in tiers_by_trigger.items()
        },
        "BLOCKED_REASONS_TOTAL": dict(blocked_total_reasons),
        "MENU_COUNTERS": menu_counters,
        "MENU_RETRY": adapter_counters,
        "EXIT_MIX": dict(Counter(r["exit_kind"] for r in fill_rows)),
        "MULTI_BRANCH_FILLS": "YES"
        if sum(1 for n in fills_by_trigger.values() if n) >= 2 else "NO",
        "MULTI_BRANCH_ROUTES": "YES"
        if sum(1 for n in routes_by_trigger.values() if n) >= 2 else "NO",
        "DOMINANT_FILL_SHARE": dominant,
        "NET_PL_DIAGNOSTIC": {
            "n_closed": len(result.closed),
            "sum_realized_pnl_raw": round(
                sum(rec.realized_pnl for rec in result.closed), 6
            ),
            "LABEL": "raw price*volume sum — NOT performance, NOT edge",
        },
        "ELAPSED_SECONDS": round(max(time.perf_counter() - started, 1e-9), 1),
    }

    with (OUT_DIR / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)

    def write(path: Path, rows: list[dict]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    write(OUT_DIR / "winners.csv", winner_rows)
    write(OUT_DIR / "orders.csv", order_rows)
    write(OUT_DIR / "fills.csv", fill_rows)
    write(OUT_DIR / "blocks.csv", block_rows)
    write(OUT_DIR / "completions.csv", tap.completion_rows)

    print(json.dumps(
        {
            "ARMED": summary["ARMED"],
            "TOTALS": summary["TOTALS"],
            "BY_TRIGGER": {
                k: {kk: vv for kk, vv in v.items() if kk != "block_reasons"}
                for k, v in per_trigger.items()
            },
            "MULTI_BRANCH_FILLS": summary["MULTI_BRANCH_FILLS"],
            "MULTI_BRANCH_ROUTES": summary["MULTI_BRANCH_ROUTES"],
            "OUT": str(OUT_DIR),
        },
        indent=2, default=str,
    ), flush=True)
    print(f"artifacts: {OUT_DIR}", flush=True)
    return 0


def _dir_name(direction):
    if direction is None:
        return None
    return getattr(direction, "name", None) or str(direction)


if __name__ == "__main__":
    sys.exit(run())
