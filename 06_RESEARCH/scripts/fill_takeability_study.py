"""Fill / takeability study — MEASUREMENT ONLY (post R-HOLD P2 FVG).

Authority: ``00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md``.

Question: LEG 1 showed the FVG gate is not cutting a better class of paths and
LEG 2 held it. Scarcity is then a *frequency* problem somewhere in
ARM -> ROUTE -> PLACE -> FILL. This leg measures the last two links: when a
limit is actually placed under the frozen rules, does the market ever come to
it inside the window the product grants, and if not, why?

What the script does
--------------------
1. Drives the frozen product composition by importing
   ``phase3_structure_funnel.run`` unmodified and installing four
   **logging-only** wrappers, restored in ``finally``:
     * ``PendingOrderBook.place`` — every accepted placement, verbatim;
     * ``BacktestRunner._apply_fills`` — every fill (and any disappearance
       that is not a fill, which would be an anomaly);
     * ``BacktestRunner._expire_orders`` — every §23/R8/give-up expiry,
       with the mechanism and ``bars_open`` at cancel;
     * ``BacktestRunner.cancel_pending_for_poi`` — every cancellation from a
       POI dying (§5 violation);
     * ``BacktestRunner._cancel_all_pending`` + ``RiskEngine`` portfolio
       triggers — Friday-EOD and §11-news cancellations, attributed by which
       caller just returned True;
     * ``BacktestRunner.set_atr`` — the per-bar ATR the runner itself fed to
       its gates (used only as a scale for the distance columns).
   No decision, threshold, ordering or output changes.
2. Reconstructs each placed order's fill-eligible window from the frozen
   semantics (placement at runner step 6 -> the placement bar is never
   eligible; expiry runs at step 3 of a later bar, before fills), then walks
   the M5 series to classify the order's fate.
3. Runs the pre-registered counterfactual sensitivity (+12 / +24 / +48 bars
   of extra rest) — a sensitivity table, NOT a proposal.
4. Ranks the causes of non-fill and applies ONE pre-registered label.

Usage:
  python 06_RESEARCH/scripts/fill_takeability_study.py --capture
  python 06_RESEARCH/scripts/fill_takeability_study.py --capture \
      --load-from 2023-11-01 --exec-from 2023-12-01 --exec-to 2025-05-31 \
      --out-dir 06_RESEARCH/results/fill_takeability/secondary_18m
  python 06_RESEARCH/scripts/fill_takeability_study.py --analyze-only

Diagnostic only — NOT edge.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import json
import math
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "fill_takeability"
EVENTS_PATH = OUT_DIR / "events.jsonl.gz"
SUMMARY_PATH = OUT_DIR / "summary.json"
ORDERS_PATH = OUT_DIR / "orders_fate.csv"
BANNER = "DIAGNOSTIC — NOT EDGE"

# Primary window: the frozen 6m product window used by Phase 3 / FR-4 / LEG 1.
# Secondary window (CLI, not defaulted here): 2023-12-01 -> 2025-05-31, pinned
# before any secondary result existed after the 24-month run proved
# unaffordable (per-bar cost grows with accumulated POI history).
DEFAULT_LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)
DEFAULT_EXEC_FROM = datetime(2025, 6, 1, tzinfo=timezone.utc)
DEFAULT_EXEC_TO = datetime(2025, 11, 30, 23, 59, tzinfo=timezone.utc)
LOAD_FROM = DEFAULT_LOAD_FROM
EXEC_FROM = DEFAULT_EXEC_FROM
EXEC_TO = DEFAULT_EXEC_TO

# Pre-registered counterfactual rest extensions (bars beyond the product
# lifetime). Sensitivity only — never a proposal.
CF_EXTENSIONS = (12, 24, 48)
# Descriptive "did it ever come back" horizon, measured from placement.
RUNAWAY_HORIZON = 400
# A placement that ends within this many ATRs of its limit is a near miss.
NEAR_MISS_ATR = 0.5
MIN_PLACED_FOR_LABEL = 10

FATE_FILLED = "FILLED"
FATE_TOUCH_LIVE_UNFILLED = "TOUCHED_WHILE_LIVE_UNFILLED"
FATE_TOUCH_AFTER_EXPIRY = "TOUCHED_ONLY_AFTER_EXPIRY"
FATE_NEVER_TOUCHED = "NEVER_TOUCHED_IN_LIFE"
FATE_CANCELLED = "CANCELLED_OTHER"
FATE_DATA_GAP = "DATA_GAP"
FATES = (FATE_FILLED, FATE_TOUCH_LIVE_UNFILLED, FATE_TOUCH_AFTER_EXPIRY,
         FATE_NEVER_TOUCHED, FATE_CANCELLED, FATE_DATA_GAP)

# ---------------------------------------------------------------------- #
# Capture
# ---------------------------------------------------------------------- #

_EV = {
    "placements": [],
    "fills": [],
    "expiries": [],
    "poi_cancels": [],
    "portfolio_cancels": [],
}
_STATE = {"atr": None, "bar": None, "friday": False, "news": False,
          "runner": None}


def _reset_capture() -> None:
    for key in _EV:
        _EV[key].clear()
    _STATE.update(atr=None, cancel_reason=None, runner=None, friday=False,
                  news=False)


def _dir(value) -> str:
    return str(getattr(value, "value", value))


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _ticket_map(book) -> dict:
    return {order.ticket: order for order in book.active()}


def install_capture() -> tuple:
    """Install the logging-only wrappers; return the originals to restore."""
    from smc.backtest.orders import PendingOrderBook
    from smc.backtest.runner import BacktestRunner
    from smc.risk.risk_engine import RiskEngine

    orig = {
        "init": BacktestRunner.__init__,
        "place": PendingOrderBook.place,
        "on_bar": BacktestRunner.on_bar,
        "fills": BacktestRunner._apply_fills,
        "expire": BacktestRunner._expire_orders,
        "poi_cancel": BacktestRunner.cancel_pending_for_poi,
        "cancel_all": BacktestRunner._cancel_all_pending,
        "set_atr": BacktestRunner.set_atr,
        "friday": RiskEngine.evaluate_friday_close,
        "news": RiskEngine.hard_cancel_pending,
    }

    def init(self, *args, **kwargs):
        orig["init"](self, *args, **kwargs)
        _STATE["runner"] = self

    def place(self, **kwargs):
        order = orig["place"](self, **kwargs)
        _EV["placements"].append({
            "ticket": order.ticket,
            "poi_id": order.poi_id,
            "route_id": order.comment or None,
            "trigger": str(getattr(order.trigger, "value", order.trigger)),
            "direction": _dir(order.direction),
            "entry": float(order.entry_price),
            "sl": None if order.sl is None else float(order.sl),
            "tp": None if order.tp is None else float(order.tp),
            "original_sl": (None if order.original_sl is None
                            else float(order.original_sl)),
            "zone_low": order.zone_low,
            "zone_high": order.zone_high,
            "volume": float(order.volume),
            "placed_bar": int(order.placed_bar),
            "placed_at": _iso(order.placed_at),
            "rest_bars": order.rest_bars,
            "detection_tf": getattr(order.detection_tf, "name",
                                    str(order.detection_tf)),
            "model_tags": list(order.model_tags or []),
            "entry_anchor": order.entry_anchor,
            "tp_source": order.tp_source,
            "atr_at_place": _STATE["atr"],
        })
        return order

    def on_bar(self, bar, bar_index, clock):
        _STATE["bar"] = int(bar_index)
        _STATE["friday"] = False
        _STATE["news"] = False
        orig["on_bar"](self, bar, bar_index, clock)

    def fills(self, bar, bar_index):
        before = _ticket_map(self.orders)
        orig["fills"](self, bar, bar_index)
        after = _ticket_map(self.orders)
        for ticket, order in before.items():
            if ticket in after:
                continue
            from smc.backtest.fill_model import limit_filled
            touched = limit_filled(order.direction, order.entry_price, bar)
            _EV["fills"].append({
                "ticket": ticket,
                "bar": int(bar_index),
                "timestamp": _iso(bar.timestamp),
                "touched_at_fill_bar": bool(touched),
                "direction": _dir(order.direction),
                "entry": float(order.entry_price),
                "sl": None if order.sl is None else float(order.sl),
                "tp": None if order.tp is None else float(order.tp),
                "placed_bar": int(order.placed_bar),
                "rest_bars": order.rest_bars,
            })
            if not touched:  # would be a real anomaly — surfaced, never hidden
                _EV["fills"][-1]["anomaly"] = "fill_without_touch"

    def expire(self, bar_index):
        before = _ticket_map(self.orders)
        orig["expire"](self, bar_index)
        after = _ticket_map(self.orders)
        for ticket, order in before.items():
            if ticket in after:
                continue
            from smc.triggers.trigger_expiry import poi_give_up_bars
            from smc.validation.state_machine import expiry_bars_for
            from smc.config.timeframe import Timeframe
            bars_open = int(bar_index) - order.placed_bar + 1
            section23 = order.rest_bars
            if section23 is None:
                section23 = expiry_bars_for(Timeframe.M5)
            backstop = (max(poi_give_up_bars(), order.rest_bars)
                        if order.rest_bars is not None else poi_give_up_bars())
            if section23 is not None and bars_open >= section23:
                mechanism = "section23"
                limit = section23
            else:
                mechanism = "give_up"
                limit = backstop
            _EV["expiries"].append({
                "ticket": ticket,
                "bar": int(bar_index),
                "bars_open": bars_open,
                "limit": int(limit),
                "mechanism": mechanism,
                "placed_bar": int(order.placed_bar),
            })

    def poi_cancel(self, poi_id, bar_index=None):
        before = _ticket_map(self.orders)
        count = orig["poi_cancel"](self, poi_id, bar_index)
        after = _ticket_map(self.orders)
        for ticket, order in before.items():
            if ticket in after:
                continue
            _EV["poi_cancels"].append({
                "ticket": ticket,
                "bar": None if bar_index is None else int(bar_index),
                "poi_id": poi_id,
                "placed_bar": int(order.placed_bar),
            })
        return count

    def cancel_all(self):
        before = _ticket_map(self.orders)
        orig["cancel_all"](self)
        after = _ticket_map(self.orders)
        reason = ("friday_eod" if _STATE["friday"]
                  else "news" if _STATE["news"] else "cancel_all_other")
        for ticket, order in before.items():
            if ticket in after:
                continue
            _EV["portfolio_cancels"].append({
                "ticket": ticket,
                "bar": _STATE["bar"],
                "reason": reason,
                "placed_bar": int(order.placed_bar),
            })

    def set_atr(self, atr):
        _STATE["atr"] = None if atr is None else float(atr)
        return orig["set_atr"](self, atr)

    def friday(self, now):
        result = orig["friday"](self, now)
        if result:
            _STATE["friday"] = True
        return result

    def news(self, now, events):
        result = orig["news"](self, now, events)
        if result:
            _STATE["news"] = True
        return result

    BacktestRunner.__init__ = init
    PendingOrderBook.place = place
    BacktestRunner.on_bar = on_bar
    BacktestRunner._apply_fills = fills
    BacktestRunner._expire_orders = expire
    BacktestRunner.cancel_pending_for_poi = poi_cancel
    BacktestRunner._cancel_all_pending = cancel_all
    BacktestRunner.set_atr = set_atr
    RiskEngine.evaluate_friday_close = friday
    RiskEngine.hard_cancel_pending = news

    def restore() -> None:
        BacktestRunner.__init__ = orig["init"]
        PendingOrderBook.place = orig["place"]
        BacktestRunner.on_bar = orig["on_bar"]
        BacktestRunner._apply_fills = orig["fills"]
        BacktestRunner._expire_orders = orig["expire"]
        BacktestRunner.cancel_pending_for_poi = orig["poi_cancel"]
        BacktestRunner._cancel_all_pending = orig["cancel_all"]
        BacktestRunner.set_atr = orig["set_atr"]
        RiskEngine.evaluate_friday_close = orig["friday"]
        RiskEngine.hard_cancel_pending = orig["news"]

    return restore


def run_capture() -> dict:
    """Drive the frozen composition and persist the lifecycle capture."""
    import phase3_structure_funnel as funnel

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _reset_capture()
    restore = install_capture()
    args = argparse.Namespace(
        tag="fill_takeability",
        out_root=str(OUT_DIR.relative_to(REPO_ROOT) / "_funnel_capture"),
        load_from=LOAD_FROM.date().isoformat(),
        exec_from=EXEC_FROM.date().isoformat(),
        exec_to=EXEC_TO.date().isoformat(),
        cost_config=None,
        episode_store=None,
    )
    t0 = time.perf_counter()
    try:
        funnel_summary = funnel.run(args)
        event_rows = int(funnel_summary.get("merged_pois") or 0)
        runner = _STATE.get("runner")
        if runner is not None:
            _capture_blocks_and_intents(runner)
    finally:
        restore()
    elapsed = round(time.perf_counter() - t0, 1)

    with gzip.open(EVENTS_PATH, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "funnel", "data": funnel_summary},
                            default=str) + "\n")
        for key, rows in _EV.items():
            for row in rows:
                fh.write(json.dumps({"kind": key, "data": row},
                                    default=str) + "\n")
    meta = {
        "events": sum(len(v) for v in _EV.values()),
        "validation_events": event_rows,
        "runtime_seconds": elapsed,
        "funnel_summary": funnel_summary,
    }
    (OUT_DIR / "capture_meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )
    print(f"[fill] captured {meta['events']} lifecycle events in {elapsed}s",
          flush=True)
    return meta


def _capture_blocks_and_intents(runner) -> None:
    """Read the runner's own block log + R9 intent lifecycle after the run.

    ``BlockedEntry`` already carries poi/trigger/route identity (the logging
    patch landed before this study). Intent events are read from the book's
    own machine-readable list — this is how the published funnel's
    ``intents_expired = 0`` counter defect is avoided here (the real event is
    named ``intent_expired_no_reentry``).
    """
    for entry in getattr(runner, "blocked_log", []) or []:
        _EV.setdefault("blocks", []).append({
            "bar": int(entry.bar_index),
            "blocked_by": entry.blocked_by,
            "poi_id": entry.poi_id,
            "route_id": entry.route_id,
            "trigger": str(getattr(entry.trigger, "value", entry.trigger)),
        })
    book = getattr(runner, "intents", None)
    events = getattr(book, "events", None) if book is not None else None
    for ev in events or []:
        _EV.setdefault("intents", []).append({
            "event": ev.get("event"),
            "bar": ev.get("bar"),
            "intent_id": ev.get("intent_id"),
            "route_id": ev.get("route_id"),
            "poi_id": ev.get("poi_id"),
            "rest_bars": ev.get("rest_bars"),
        })


def load_events() -> dict:
    if not EVENTS_PATH.exists():
        raise SystemExit(f"capture missing: {EVENTS_PATH} — run --capture first")
    out: dict = defaultdict(list)
    with gzip.open(EVENTS_PATH, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["kind"] == "funnel":
                out["funnel"].append(rec["data"])
            else:
                out[rec["kind"]].append(rec["data"])
    return out


# ---------------------------------------------------------------------- #
# Pure helpers (unit-tested, no product import at module scope)
# ---------------------------------------------------------------------- #

def limit_touch(direction: str, limit: float, low: float, high: float) -> bool:
    """Mirror of ``smc.backtest.fill_model.limit_filled`` (inclusive touch)."""
    return low <= limit if direction == "long" else high >= limit


def live_window(placed_bar: int, rest_bars: int, cancel_bar: int | None,
                series_len: int) -> tuple[int, int]:
    """Fill-eligible bars of one resting order, inclusive.

    Frozen semantics: placement happens at runner step 6 (after that bar's
    fills), and expiry runs at step 3 of a later bar (before that bar's
    fills). With the §23/R8 convention ``bars_open = bar - placed + 1`` and
    cancellation at ``bars_open >= rest``, the order is eligible on
    ``placed+1 .. placed+rest-2``. A portfolio/POI cancellation on bar C
    removes it before C's fills, so the live window ends at ``C-1``.
    Returns ``(first, last)`` with ``first > last`` when nothing is eligible.
    """
    first = placed_bar + 1
    last = placed_bar + rest_bars - 2
    if cancel_bar is not None:
        last = min(last, cancel_bar - 1)
    last = min(last, series_len - 1)
    return first, last


def closest_approach(direction: str, limit: float, bars, first: int,
                     last: int) -> tuple[float | None, int | None]:
    """Min distance to the limit while live, and the bar it happened on.

    Distance is 0.0 whenever the bar's range reaches the limit (touch).
    Returns ``(None, None)`` for an empty window.
    """
    if last < first:
        return None, None
    best = math.inf
    best_bar = None
    for index in range(first, last + 1):
        low, high = bars[index]["low"], bars[index]["high"]
        if limit_touch(direction, limit, low, high):
            return 0.0, index
        distance = (low - limit) if direction == "long" else (limit - high)
        if distance < best:
            best = distance
            best_bar = index
    if best is math.inf:
        return None, None
    return max(best, 0.0), best_bar


def first_touch(direction: str, limit: float, bars, first: int,
                last: int) -> int | None:
    """First bar in ``[first, last]`` whose range touches the limit."""
    if last < first:
        return None
    for index in range(first, last + 1):
        if limit_touch(direction, limit, bars[index]["low"],
                       bars[index]["high"]):
            return index
    return None


def is_portfolio_cancel(cancel_reason: str | None) -> bool:
    """True only for portfolio/POI cancellations (never for expiry).

    ``expired_section23`` / ``expired_give_up`` are the *normal* end of the
    resting window — the market had its chance and did not take it. Only a
    Friday-EOD, §11-news or POI-violation cancel ends an order for a reason
    outside the fill geometry, and only those count as ``CANCELLED_OTHER``.
    """
    if cancel_reason is None:
        return False
    return not str(cancel_reason).startswith("expired_")


def classify_fate(*, filled_bar: int | None, live_first: int, live_last: int,
                  touch_live: int | None, touch_any: int | None,
                  cancel_reason: str | None) -> str:
    """One mutally-exclusive fate label per placed order (pre-registered)."""
    if filled_bar is not None:
        return FATE_FILLED
    if touch_live is not None and live_last >= live_first:
        # The market reached the limit while the order was resting and no
        # fill exists — a genuine inconsistency worth flagging loudly.
        return FATE_TOUCH_LIVE_UNFILLED
    if is_portfolio_cancel(cancel_reason):
        return FATE_CANCELLED
    if touch_any is not None:
        return FATE_TOUCH_AFTER_EXPIRY
    return FATE_NEVER_TOUCHED


def counterfactual_touch(direction: str, limit: float, bars, *,
                         placed_bar: int, rest_bars: int, extension: int,
                         series_len: int) -> int | None:
    """First touch if the same order had rested ``extension`` extra bars.

    Sensitivity only: the window is the product lifetime plus ``extension``
    eligible bars, i.e. ``placed+1 .. placed+rest-2+extension`` (clamped to
    the series). Intervening portfolio events are ignored (pure geometry).
    """
    first = placed_bar + 1
    last = min(placed_bar + rest_bars - 2 + extension, series_len - 1)
    return first_touch(direction, limit, bars, first, last)


def counterfactual_resolve(direction: str, entry: float, sl: float | None,
                           tp: float | None, bars, *, touch_bar: int,
                           horizon_end: int) -> dict:
    """Frozen stop-first resolution of a counterfactual fill at ``touch_bar``.

    The fill is at the limit price (locked fill model). From ``touch_bar``
    (inclusive — an entry+SL on the same bar is a stop, the frozen
    conservative rule) to ``horizon_end``: SL touching wins over TP on the
    same bar. ``DATA_GAP`` when SL or TP is missing; ``OPEN_AT_HORIZON``
    when neither is tagged inside the window.
    """
    if sl is None or tp is None:
        return {"result": "DATA_GAP", "bar": None, "r": None}
    risk = abs(entry - float(sl))
    if risk <= 0:
        return {"result": "DATA_GAP", "bar": None, "r": None}
    for index in range(touch_bar, horizon_end + 1):
        low, high = bars[index]["low"], bars[index]["high"]
        if direction == "long":
            stop = low <= float(sl)
            target = high >= float(tp)
        else:
            stop = high >= float(sl)
            target = low <= float(tp)
        if stop:
            return {"result": "STOPPED", "bar": index,
                    "r": (float(sl) - entry) / risk
                    if direction == "long" else (entry - float(sl)) / risk}
        if target:
            return {"result": "TARGET", "bar": index,
                    "r": (float(tp) - entry) / risk
                    if direction == "long" else (entry - float(tp)) / risk}
    return {"result": "OPEN_AT_HORIZON", "bar": None, "r": None}


def _median(values):
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return None
    mid = len(clean) // 2
    return (clean[mid - 1] + clean[mid]) / 2.0 if len(clean) % 2 == 0 else float(clean[mid])


def _pct(numerator: int, denominator: int) -> float | None:
    return 100.0 * numerator / denominator if denominator else None


def rank_causes(orders: list[dict], *, atr_scale: bool = True) -> dict:
    """Ranked causes of non-fill over the placed population.

    Buckets are exclusive and ordered by the mechanism that ended the order:
    never-touched (runaway), touched-after-end (clock), cancelled (portfolio/
    POI), anomaly, data gap. The proximity split inside never-touched shows
    whether the market merely stalled short of the limit or left entirely.
    """
    placed = [o for o in orders if o.get("fate") != FATE_DATA_GAP]
    never = [o for o in placed if o["fate"] == FATE_NEVER_TOUCHED]
    after = [o for o in placed if o["fate"] == FATE_TOUCH_AFTER_EXPIRY]
    cancelled = [o for o in placed if o["fate"] == FATE_CANCELLED]
    anomaly = [o for o in placed if o["fate"] == FATE_TOUCH_LIVE_UNFILLED]

    def near(row) -> bool:
        dist = row.get("closest_approach_price")
        atr = row.get("atr_at_place")
        if dist is None:
            return False
        if atr_scale and atr:
            return dist <= NEAR_MISS_ATR * float(atr)
        return False

    near_never = [o for o in never if near(o)]
    return {
        "n_placed": len(placed),
        "n_filled": sum(1 for o in placed if o["fate"] == FATE_FILLED),
        "never_touched": len(never),
        "never_touched_near_miss_le_0_5atr": len(near_never),
        "touched_only_after_end": len(after),
        "cancelled_other": len(cancelled),
        "touched_while_live_unfilled_anomaly": len(anomaly),
        "pct_never_touched": _pct(len(never), len(placed)),
        "pct_touched_after_end": _pct(len(after), len(placed)),
        "pct_cancelled": _pct(len(cancelled), len(placed)),
        "pct_filled": _pct(sum(1 for o in placed
                               if o["fate"] == FATE_FILLED), len(placed)),
        "cancel_reasons": dict(Counter(o.get("cancel_reason") for o in cancelled)),
        "expiry_mechanisms": dict(Counter(
            o.get("cancel_reason") for o in placed
            if str(o.get("cancel_reason") or "").startswith("expired_"))),
    }


def interpret(causes: dict) -> tuple[str, str]:
    """Pre-registered label rule (see the report §6, written before the run).

    ``F`` = filled / placed; ``X`` = share of placed orders that either
    touched only after the product lifetime ended or ended within
    ``NEAR_MISS_ATR`` ATR of their limit at that moment (market came back,
    the clock/geometry did not).
    """
    n = causes.get("n_placed") or 0
    if n < MIN_PLACED_FOR_LABEL:
        return ("INCONCLUSIVE_LOW_N",
                f"n_placed={n} < {MIN_PLACED_FOR_LABEL}: the pre-registered "
                "minimum for a directional label is not met in this window.")
    f = (causes.get("pct_filled") or 0.0) / 100.0
    x = ((causes.get("touched_only_after_end") or 0)
         + (causes.get("never_touched_near_miss_le_0_5atr") or 0)) / n
    if f >= 0.5 and x < 0.25:
        return ("FILL_PATH_HEALTHY",
                f"F={f:.2f} placed orders fill and only X={x:.2f} die of the "
                "clock/proximity; the fill path consumes what it places.")
    if f < 0.5 and x >= 0.5:
        return ("FILL_PATH_IS_BOTTLENECK",
                f"only F={f:.2f} of placed orders fill while X={x:.2f} come "
                "back to the limit only after their window ended or end within "
                f"{NEAR_MISS_ATR}x ATR of it — the lifetime/geometry, not the "
                "signal, ends most placements.")
    return ("MIXED",
            f"F={f:.2f} filled, X={x:.2f} near-miss-after-window, "
            f"{causes.get('pct_never_touched')}% never touched: the evidence "
            "is split between a real clock cost and genuine runaway.")


# ---------------------------------------------------------------------- #
# Analysis
# ---------------------------------------------------------------------- #

def load_exec_bars() -> dict:
    """Execution M5 bars (exec window only) as plain dicts + arrays."""
    import numpy as np

    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi
    from smc.utils.atr import atr_series

    path = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not path.exists():
        raise SystemExit(f"canonical dataset missing: {path}")
    m1 = load_ohlcv_parquet(path)
    m1 = [c for c in m1 if LOAD_FROM <= c.timestamp <= EXEC_TO + timedelta(days=1)]
    if not m1:
        raise SystemExit("no M1 bars in the requested window")
    m5 = [c for c in resample_multi(m1, [Timeframe.M5])[Timeframe.M5]
          if EXEC_FROM <= c.timestamp <= EXEC_TO]
    if not m5:
        raise SystemExit("no execution bars in the requested window")
    atr = atr_series(m5, 14)
    return {
        "bars": [{"timestamp": c.timestamp, "low": float(c.low),
                  "high": float(c.high), "close": float(c.close)} for c in m5],
        "highs": np.array([c.high for c in m5], dtype=float),
        "lows": np.array([c.low for c in m5], dtype=float),
        "closes": np.array([c.close for c in m5], dtype=float),
        "atr": atr,
        "n": len(m5),
        "start": m5[0].timestamp,
        "end": m5[-1].timestamp,
    }


def build_orders(events: dict, series: dict) -> list[dict]:
    """Reconstruct each placed order's fate from the capture + the series."""
    bars = series["bars"]
    n = series["n"]
    fills = {f["ticket"]: f for f in events.get("fills", [])}
    expiry = {e["ticket"]: e for e in events.get("expiries", [])}
    poi_cancel = {c["ticket"]: c for c in events.get("poi_cancels", [])}
    port_cancel = {}
    for c in events.get("portfolio_cancels", []):
        port_cancel.setdefault(c["ticket"], c)

    rows: list[dict] = []
    for order in events.get("placements", []):
        ticket = order["ticket"]
        placed_bar = int(order["placed_bar"])
        rest = order.get("rest_bars")
        cancel_reason = None
        cancel_bar = None
        if ticket in poi_cancel:
            cancel_reason = "poi_violated"
            cancel_bar = poi_cancel[ticket].get("bar")
        elif ticket in port_cancel:
            cancel_reason = port_cancel[ticket].get("reason")
            cancel_bar = port_cancel[ticket].get("bar")
        elif ticket in expiry:
            cancel_reason = f"expired_{expiry[ticket]['mechanism']}"
            cancel_bar = expiry[ticket]["bar"]

        fill = fills.get(ticket)
        filled_bar = None if fill is None else int(fill["bar"])
        if rest is None:
            from smc.validation.state_machine import expiry_bars_for
            from smc.config.timeframe import Timeframe
            rest = expiry_bars_for(Timeframe.M5)
        rest = int(rest)

        first, last = live_window(placed_bar, rest, cancel_bar, n)
        touch_live = first_touch(order["direction"], float(order["entry"]),
                                 bars, first, last)
        # Any touch after placement (descriptive runaway horizon), including
        # the post-lifetime stretch.
        touch_any = first_touch(order["direction"], float(order["entry"]),
                                bars, placed_bar + 1,
                                min(placed_bar + RUNAWAY_HORIZON, n - 1))
        approach, approach_bar = closest_approach(
            order["direction"], float(order["entry"]), bars, first, last)
        atr_place = order.get("atr_at_place")

        if filled_bar is not None and fill.get("anomaly"):
            fate = FATE_DATA_GAP
        else:
            fate = classify_fate(
                filled_bar=filled_bar, live_first=first, live_last=last,
                touch_live=touch_live, touch_any=touch_any,
                cancel_reason=cancel_reason)

        row = {
            "ticket": ticket,
            "poi_id": order.get("poi_id"),
            "route_id": order.get("route_id"),
            "trigger": order.get("trigger"),
            "direction": order["direction"],
            "detection_tf": order.get("detection_tf"),
            "models": "|".join(order.get("model_tags") or []),
            "entry_anchor": order.get("entry_anchor"),
            "tp_source": order.get("tp_source"),
            "limit": float(order["entry"]),
            "sl": order.get("sl"),
            "tp": order.get("tp"),
            "rest_bars": rest,
            "placed_bar": placed_bar,
            "placed_at": order.get("placed_at"),
            "eligible_first_bar": first,
            "eligible_last_bar": last,
            "eligible_bars": max(last - first + 1, 0),
            "cancel_bar": cancel_bar,
            "cancel_reason": cancel_reason,
            "filled_bar": filled_bar,
            "fill_ts": None if fill is None else fill.get("timestamp"),
            "bars_to_fill": (None if filled_bar is None
                             else filled_bar - placed_bar),
            "fate": fate,
            "touch_live_bar": touch_live,
            "bars_to_touch_live": (None if touch_live is None
                                   else touch_live - placed_bar),
            "touch_any_bar": touch_any,
            "touch_after_end_bars": (None if touch_any is None
                                     else touch_any - last),
            "closest_approach_price": approach,
            "closest_approach_atr": (None if approach is None or not atr_place
                                     else approach / float(atr_place)),
            "closest_approach_bar": approach_bar,
            "bars_live": max(last - first + 1, 0),
            "atr_at_place": atr_place,
            "tp_r": (None if order.get("sl") is None or order.get("tp") is None
                     else abs(float(order["tp"]) - float(order["entry"]))
                     / abs(float(order["entry"]) - float(order["sl"]))
                     if float(order["entry"]) != float(order["sl"]) else None),
        }

        # Counterfactual sensitivity (+N bars beyond the product lifetime).
        for ext in CF_EXTENSIONS:
            hit = counterfactual_touch(
                order["direction"], float(order["entry"]), bars,
                placed_bar=placed_bar, rest_bars=rest, extension=ext,
                series_len=n)
            row[f"cf_{ext}_touch_bar"] = hit
            row[f"cf_{ext}_touch_bars_after_end"] = (
                None if hit is None else hit - last)
            resolved = None
            if hit is not None:
                resolved = counterfactual_resolve(
                    order["direction"], float(order["entry"]),
                    order.get("sl"), order.get("tp"), bars,
                    touch_bar=hit,
                    horizon_end=min(hit + RUNAWAY_HORIZON, n - 1))
            row[f"cf_{ext}_result"] = None if resolved is None else resolved["result"]
            row[f"cf_{ext}_r"] = None if resolved is None else resolved["r"]
        rows.append(row)
    rows.sort(key=lambda r: (r["placed_bar"], r["ticket"]))
    return rows


def build_route_level(capture_path: Path, series: dict) -> dict:
    """Route-level takeability for routes that never became orders.

    Source: the logging capture of the SAME frozen composition/window used by
    the near-miss study (``results/near_miss_counterfactual/events.json``) —
    byte-identical to this run's ``trades.csv``/``report.json`` (checked in
    that study). One route = one ``route_id``; the anchor is its FIRST
    presentation bar, the lifetime its own R8 ``rest_bars`` — the single rule
    the prior study used for unplaced rows. These rows are labelled
    ``ROUTE_UNPLACED`` and are NEVER pooled into the placed-order fates.
    """
    if not capture_path.exists():
        return {"available": False, "reason": f"missing {capture_path}"}
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    routes: dict[str, dict] = {}
    for cand in capture.get("candidates", []):
        rid = cand.get("route_id") or ""
        if not rid:
            continue
        rec = routes.get(rid)
        if rec is None:
            rec = {
                "route_id": rid,
                "poi_id": cand.get("poi_id"),
                "trigger": cand.get("trigger"),
                "direction": cand.get("direction"),
                "detection_tf": cand.get("detection_tf"),
                "is_m8": cand.get("is_m8"),
                "entry": cand.get("entry"),
                "sl": cand.get("sl"),
                "tp": cand.get("tp"),
                "rest_bars": cand.get("rest_bars"),
                "first_present_bar": cand.get("bar_index"),
                "presentations": 0,
                "block_reasons": {},
                "placed": False,
            }
            routes[rid] = rec
        rec["presentations"] += 1
        reason = cand.get("blocked_by")
        if reason:
            rec["block_reasons"][reason] = rec["block_reasons"].get(reason, 0) + 1
    for order in capture.get("placements", []):
        rec = routes.get(order.get("route_id") or "")
        if rec is not None:
            rec["placed"] = True
            rec["placed_bar"] = order.get("placed_bar")

    rows: list[dict] = []
    for rec in routes.values():
        if rec["placed"]:
            continue
        anchor = int(rec["first_present_bar"])
        rest = int(rec["rest_bars"] or 12)
        first, last = live_window(anchor, rest, None, series["n"])
        touch = first_touch(rec["direction"], float(rec["entry"]),
                            series["bars"], first, last)
        approach, approach_bar = closest_approach(
            rec["direction"], float(rec["entry"]), series["bars"], first, last)
        atr = series["atr"][anchor] if anchor < len(series["atr"]) else None
        cf = {}
        for ext in CF_EXTENSIONS:
            hit = counterfactual_touch(
                rec["direction"], float(rec["entry"]), series["bars"],
                placed_bar=anchor, rest_bars=rest, extension=ext,
                series_len=series["n"])
            cf[f"+{ext}"] = None if hit is None else hit - last
        rows.append({
            **rec,
            "population": "ROUTE_UNPLACED",
            "anchor_bar": anchor,
            "eligible_first_bar": first,
            "eligible_last_bar": last,
            "touched_in_life": touch is not None,
            "bars_to_touch": None if touch is None else touch - anchor,
            "closest_approach_price": approach,
            "closest_approach_atr": (None if approach is None or not atr
                                     else approach / float(atr)),
            "closest_approach_bar": approach_bar,
            "cf_touch_bars_after_end": cf,
        })
    touched = [r for r in rows if r["touched_in_life"]]
    after = [r for r in rows if any(v is not None for v in
                                    r["cf_touch_bars_after_end"].values())]
    return {
        "available": True,
        "source": str(capture_path.relative_to(REPO_ROOT)),
        "n_routes": len(routes),
        "n_placed": sum(1 for r in routes.values() if r["placed"]),
        "n_unplaced": len(rows),
        "unplaced_touched_in_life": len(touched),
        "unplaced_never_touched": len(rows) - len(touched),
        "unplaced_median_closest_price": _median(
            [r["closest_approach_price"] for r in rows]),
        "unplaced_median_closest_atr": _median(
            [r["closest_approach_atr"] for r in rows]),
        "unplaced_touched_within_plus12": sum(
            1 for r in rows
            if r["cf_touch_bars_after_end"].get("+12") is not None),
        "unplaced_touched_within_plus24": sum(
            1 for r in rows if r["cf_touch_bars_after_end"].get("+24") is not None),
        "unplaced_touched_within_plus48": sum(
            1 for r in rows if r["cf_touch_bars_after_end"].get("+48") is not None),
        "rows": rows,
        "note": ("anchor = first presentation bar + the route's own R8 "
                 "lifetime (prior study's rule for unplaced rows); these "
                 "rows are a separate population and never enter the "
                 "placed-order fates or the label rule"),
    }


def summarize(rows: list[dict], series: dict, capture_meta: dict,
              route_level: dict | None = None) -> dict:
    causes = rank_causes(rows)
    label, why = interpret(causes)
    filled = [r for r in rows if r["fate"] == FATE_FILLED]
    never = [r for r in rows if r["fate"] == FATE_NEVER_TOUCHED]
    after = [r for r in rows if r["fate"] == FATE_TOUCH_AFTER_EXPIRY]

    def col(rows_, key):
        return _median([r.get(key) for r in rows_])

    # The counterfactual question applies to the orders the product did NOT
    # fill and that were not killed by a portfolio/POI cancel: would extra
    # rest have seen a touch? Filled rows are excluded (their touch is inside
    # the base window and adds nothing to the question).
    cf_base = [r for r in rows
               if r["fate"] in (FATE_NEVER_TOUCHED, FATE_TOUCH_AFTER_EXPIRY)]
    cf = {}
    for ext in CF_EXTENSIONS:
        hits = [r for r in cf_base
                if r.get(f"cf_{ext}_touch_bar") is not None]
        incremental = [r for r in hits
                       if int(r[f"cf_{ext}_touch_bar"]) > int(r["eligible_last_bar"])]
        results = Counter(r.get(f"cf_{ext}_result") for r in incremental
                          if r.get(f"cf_{ext}_result"))
        cf[f"+{ext}"] = {
            "n_base": len(cf_base),
            "n_touched_incremental": len(incremental),
            "pct_of_nonfilled_touched": _pct(len(incremental), len(cf_base)),
            "median_bars_after_end": col(incremental,
                                         f"cf_{ext}_touch_bars_after_end"),
            "resolution_mix": dict(results),
            "pct_target_of_touched": _pct(results.get("TARGET", 0),
                                          len(incremental)),
        }

    funnel = (capture_meta.get("funnel_summary") or {})
    strand = _route_strand(rows, funnel, capture_meta)
    integrity = _integrity(rows, capture_meta)
    return {
        "banner": BANNER,
        "authority": "00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md",
        "window": {
            "load_from": LOAD_FROM.isoformat(),
            "exec_from": EXEC_FROM.isoformat(),
            "exec_to": EXEC_TO.isoformat(),
            "exec_tf": "M5",
            "m5_exec_bars": series["n"],
            "first_bar": series["start"].isoformat(),
            "last_bar": series["end"].isoformat(),
        },
        "funnel": {
            k: funnel.get(k) for k in
            ("htf_batches", "merged_pois", "passed_validation", "armed",
             "routes", "placed", "fills", "trades")
        },
        "capture": {
            "runtime_seconds": capture_meta.get("runtime_seconds"),
            "events": capture_meta.get("events"),
            "placements": len(rows),
            "fills_seen": len([r for r in rows if r["filled_bar"] is not None]),
            "expiries": len(capture_meta.get("_expiry_rows") or []),
        },
        "fates": dict(Counter(r["fate"] for r in rows)),
        "causes": causes,
        "medians": {
            "closest_approach_price_live": col(rows, "closest_approach_price"),
            "closest_approach_atr_live": col(rows, "closest_approach_atr"),
            "bars_live": col(rows, "bars_live"),
            "bars_to_touch_live": col([r for r in rows
                                       if r["touch_live_bar"] is not None],
                                      "bars_to_touch_live"),
            "bars_to_fill": col(filled, "bars_to_fill"),
            "never_touched_closest_price": col(never, "closest_approach_price"),
            "never_touched_closest_atr": col(never, "closest_approach_atr"),
            "after_end_bars_to_touch": col(after, "touch_after_end_bars"),
            "after_end_closest_before_expiry": col(
                after, "closest_approach_price"),
            "tp_r_placed": col(rows, "tp_r"),
        },
        "counterfactual": cf,
        "route_strand": strand,
        "route_level_unplaced": route_level,
        "integrity": integrity,
        "interpretation": {"label": label, "why": why},
        "guards": {
            "logic_changed": "NO",
            "locked_constants_touched": "NO",
            "expiry_or_gate_widened": "NO",
            "edge_or_expectancy_claim": "NO",
            "multi_symbol": "NO",
        },
    }


def _integrity(rows: list[dict], capture_meta: dict) -> dict:
    """Every placement must resolve to exactly one terminal record."""
    terminals = Counter()
    for row in rows:
        if row["filled_bar"] is not None:
            terminals[row["ticket"]] += 1
        elif row["cancel_reason"]:
            terminals[row["ticket"]] += 1
    gaps = [r["ticket"] for r in rows if terminals[r["ticket"]] == 0]
    double = [t for t, n in terminals.items() if n > 1]
    return {
        "placements": len(rows),
        "terminal_records": sum(terminals.values()),
        "unaccounted_placements": gaps,
        "double_terminal": double,
        "fill_without_touch": sum(
            1 for f in capture_meta.get("_fills") or [] if f.get("anomaly")),
        "note": ("unaccounted/double terminal rows are capture defects, not "
                 "fates; they are surfaced rather than silently classified"),
    }


def _route_strand(rows: list[dict], funnel: dict, capture_meta: dict) -> dict:
    """SCOPE C: routes -> placements -> fills and who blocked the rest."""
    routes = funnel.get("routes")
    placed = funnel.get("placed")
    fills = funnel.get("fills")
    blocked_events = funnel.get("_blocked_by_reason") or {}
    blocks = capture_meta.get("_blocks") or []
    intents = capture_meta.get("_intents") or []

    placed_routes = {r["route_id"] for r in rows if r.get("route_id")}
    blocked_routes: dict[str, Counter] = defaultdict(Counter)
    for b in blocks:
        rid = b.get("route_id")
        if rid:
            blocked_routes[rid][b.get("blocked_by") or "unknown"] += 1
    never_placed = sorted(set(blocked_routes) - placed_routes)
    first_reason = {rid: next(iter(blocked_routes[rid])) for rid in never_placed}
    ranked = Counter(first_reason.values())
    intent_events = Counter(e.get("event") for e in intents
                            if e.get("event"))
    return {
        "routes": routes,
        "placed": placed,
        "fills": fills,
        "routes_without_place": (None if routes is None or placed is None
                                 else routes - placed),
        "blocked_by_reason_events": blocked_events,
        "blocked_routes_observed": len(blocked_routes),
        "routes_never_placed_observed": len(never_placed),
        "never_placed_first_reason_ranked": dict(ranked.most_common()),
        "never_placed_detail": [
            {"route_id": rid, "first_reason": first_reason[rid],
             "all_reasons": dict(blocked_routes[rid].most_common())}
            for rid in never_placed
        ],
        "intent_lifecycle": dict(intent_events),
        "note": ("event counts come from the composition's report.json; "
                 "route-level reasons from the runner's own blocked_log; "
                 "intent counts from IntentBook.events (the published "
                 "funnel's intents_expired counter is known to read 0 — the "
                 "real event is intent_expired_no_reentry)."),
    }


def analyze(routes_capture: Path | None = None) -> dict:
    events = load_events()
    series = load_exec_bars()
    meta_path = OUT_DIR / "capture_meta.json"
    capture_meta = (json.loads(meta_path.read_text(encoding="utf-8"))
                    if meta_path.exists() else {})
    # The composition's report.json carries the blocked-by histogram.
    report_path = OUT_DIR / "_funnel_capture" / "report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = {}
        capture_meta.setdefault("funnel_summary", {})["_blocked_by_reason"] = (
            report.get("blocked_by_reason") or report.get("blocked_reasons")
            or {})
    capture_meta["_expiry_rows"] = events.get("expiries", [])
    capture_meta["_fills"] = events.get("fills", [])
    capture_meta["_blocks"] = events.get("blocks", [])
    capture_meta["_intents"] = events.get("intents", [])

    rows = build_orders(events, series)
    route_level = (build_route_level(routes_capture, series)
                   if routes_capture is not None else None)
    summary = summarize(rows, series, capture_meta, route_level)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str),
                            encoding="utf-8")
    fields = list(rows[0].keys()) if rows else ["ticket"]
    with ORDERS_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({
        "placed": summary["causes"]["n_placed"],
        "filled": summary["causes"]["n_filled"],
        "fates": summary["fates"],
        "label": summary["interpretation"]["label"],
    }, indent=2))
    return summary


def combine(primary_path: Path, secondary_path: Path) -> dict:
    """Choose the label basis: primary first, else secondary (both n>=10).

    The rule is fixed before the runs: the *frozen 6m window* is the primary
    basis; if it has fewer than ``MIN_PLACED_FOR_LABEL`` placements, the
    secondary window is the basis; if neither reaches the minimum the leg
    reports ``INCONCLUSIVE_LOW_N``. Windows are never pooled (they cover
    different regimes and pooling would not be a single population).
    """
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    secondary = json.loads(secondary_path.read_text(encoding="utf-8"))
    n_primary = primary["causes"]["n_placed"]
    n_secondary = secondary["causes"]["n_placed"]
    if n_primary >= MIN_PLACED_FOR_LABEL:
        basis, source = "primary", primary
    elif n_secondary >= MIN_PLACED_FOR_LABEL:
        basis, source = "secondary", secondary
    else:
        basis, source = None, None
    label = source["interpretation"]["label"] if source else "INCONCLUSIVE_LOW_N"
    why = (source["interpretation"]["why"] if source else
           f"n_placed primary={n_primary}, secondary={n_secondary}: both "
           f"below {MIN_PLACED_FOR_LABEL}.")
    out = {
        "banner": BANNER,
        "basis": basis,
        "n_placed_primary": n_primary,
        "n_placed_secondary": n_secondary,
        "windows": {"primary": primary["window"],
                    "secondary": secondary["window"]},
        "primary": {"funnel": primary["funnel"], "fates": primary["fates"],
                    "causes": primary["causes"], "medians": primary["medians"],
                    "counterfactual": primary["counterfactual"],
                    "route_strand": primary["route_strand"],
                    "integrity": primary["integrity"]},
        "secondary": {"funnel": secondary["funnel"],
                      "fates": secondary["fates"],
                      "causes": secondary["causes"],
                      "medians": secondary["medians"],
                      "counterfactual": secondary["counterfactual"],
                      "route_strand": secondary["route_strand"],
                      "integrity": secondary["integrity"]},
        "interpretation": {"label": label, "why": why, "basis": basis},
        "guards": primary["guards"],
    }
    path = primary_path.parent / "summary_all.json"
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"basis": basis, "n_primary": n_primary,
                      "n_secondary": n_secondary, "label": label},
                     indent=2))
    return out


def _parse_day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main() -> int:
    global LOAD_FROM, EXEC_FROM, EXEC_TO, OUT_DIR, EVENTS_PATH, \
        SUMMARY_PATH, ORDERS_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--analyze-only", action="store_true")
    ap.add_argument("--load-from", default=None)
    ap.add_argument("--exec-from", default=None)
    ap.add_argument("--exec-to", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--combine", action="store_true",
                    help="pick the label basis from primary + secondary")
    ap.add_argument("--secondary-dir", default=None)
    ap.add_argument("--routes-capture", default=None,
                    help="prior near-miss events.json for the route-level "
                         "unplaced table (same frozen window/composition)")
    args = ap.parse_args()
    if args.combine:
        secondary = (REPO_ROOT / (args.secondary_dir or
                     "06_RESEARCH/results/fill_takeability/secondary_18m"))
        combine(SUMMARY_PATH, secondary / "summary.json")
        return 0
    if not args.capture and not args.analyze_only:
        ap.error("choose --capture or --analyze-only")
    if args.load_from:
        LOAD_FROM = _parse_day(args.load_from)
    if args.exec_from:
        EXEC_FROM = _parse_day(args.exec_from)
    if args.exec_to:
        EXEC_TO = _parse_day(args.exec_to) + timedelta(days=1) - timedelta(minutes=1)
    if args.out_dir:
        OUT_DIR = REPO_ROOT / args.out_dir
        EVENTS_PATH = OUT_DIR / "events.jsonl.gz"
        SUMMARY_PATH = OUT_DIR / "summary.json"
        ORDERS_PATH = OUT_DIR / "orders_fate.csv"
    if args.routes_capture:
        args.routes_capture = REPO_ROOT / args.routes_capture
    if args.capture:
        run_capture()
    analyze(args.routes_capture)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
