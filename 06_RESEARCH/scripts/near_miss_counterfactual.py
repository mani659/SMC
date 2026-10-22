"""Near-miss / counterfactual study — did placement gates kill good paths?

Read-only measurement (Architect plan 2026-10-13 primary next; proof
register PRIMARY_NEXT).  ``LOGIC_CHANGED: NO`` — no ``04_SRC/smc``
decision path is edited, ``locked_constants.py`` untouched.

Question
--------
The product 6m book is thin (~30 armed -> 10 routes -> 4 placed -> 3
fills).  For every routed candidate that did NOT become a fill
(R7-skipped / session-blocked / placed-but-unfilled) paper-trade the
RECORDED entry/SL/TP under the frozen fill semantics, and compare the
outcome mix against the filled control arm.  If the untaken paths are
as bad or worse, placement gates are not the binding constraint; if
they systematically win, placement is a bottleneck *candidate* for a
later dated ruling.  Nothing is loosened, tuned, or gated here.

Method (frozen before running)
------------------------------
1. **Capture (logging-only seam).** The frozen composition
   ``phase3_structure_funnel.run`` (imported, not forked) is re-run on
   the frozen 6m window with the pilot's explicit CostConfig, under two
   class-level logging wrappers restored in ``finally``:

   * ``BacktestRunner.__init__`` -> keeps the run's runner instance so
     the post-run read can use its own ``blocked_log`` + ``intents``
     lifecycle events (never re-derived);
   * ``BacktestRunner._process_entries`` -> snapshots
     ``self._pending_entries`` (candidate geometry) before the frozen
     body runs and pairs each candidate with the ``blocked_log`` delta
     the body appended (order-preserving), giving every candidate a
     machine-readable fate;
   * ``PendingOrderBook.place`` -> records every accepted placement
     (limit/SL/TP/rest_bars/provenance) verbatim.

   The run must reproduce ``results/product_6m_refresh_track_b/run1``
   ``trades.csv`` + ``report.json`` **byte-identically**; a mismatch
   means the seam changed behavior and the study FAILS LOUD.

2. **Route table.** Candidates deduped by ``route_id`` (one route =
   one §11 identity ``poi:trigger@signal_bar``; blocks are retryable so
   one route can be presented on many bars).  First presentation bar is
   frozen as the counterfactual placement bar.  Arms:
   ``filled_control`` | ``placed_unfilled`` | ``blocked_session`` |
   ``blocked_r7_far`` | ``blocked_other`` (first blocking reason wins;
   a route that ever placed is never in a blocked arm).

3. **Counterfactual fill engine** (product-conservative, mirrored from
   ``smc.backtest.fill_model`` — never re-implemented differently,
   cross-checked by test):

   * touch = fill at the limit price (LONG ``low <= limit`` / SHORT
     ``high >= limit``, inclusive);
   * placement runs at runner step 6 (after fills) so the placement bar
     is NEVER fill-eligible: eligible bars are
     ``present_bar + 1 .. present_bar + rest_bars - 2`` where
     ``rest_bars`` is the route's own frozen R8/§23 lifetime
     (``rest_bars_for(detection_tf, is_m8, M5)``) — one rule, all rows;
   * once filled, the position resolves over the series with the frozen
     same-bar rule (SL before TP) and no holding cap;
   * no cost model in the primary pass (gross path labels only;
     disclosed); no BE stop (disclosed — quantified against the
     control arm's real exits instead of invented).

4. **Outcome labels** (exclusive): ``TP_HIT`` / ``SL_HIT`` /
   ``EXPIRED_NO_FILL`` / ``DATA_GAP``, plus ``OPEN_UNRESOLVED`` (a
   documented extension: a filled path still live at series end is
   never folded into a win or a loss).  Path diagnostics per filled
   row: ``MFE_R`` / ``MAE_R`` (R = |entry - original_sl|, falling back
   to ``|entry - sl|``), ``SL_THEN_TP``, bars to outcome.

5. **Secondary (disclosed, frozen):** an extended 100-M5-bar horizon
   pass, answering FR-4b's near-miss class ("touched, but not inside
   the lifetime the product would have granted").  Separate column,
   never the primary table.

6. **Kill criteria** (pre-registered in ``evaluate_kill_criteria``):
   gates can only be destructive if the untaken path would have filled
   AND won.  No resolved untaken paths -> PLACEMENT_NOT_PRIMARY; a
   resolved contrast needs n >= 5 and compares the TP-hit rate against
   control; otherwise INCONCLUSIVE.

Bans honoured: no threshold/pillar/trigger/risk/R7/session change, no
live or paper trading, no Mode B/ML, no expectancy claim, no
significance theater (counts only).  Every artifact is banner-stamped
``DIAGNOSTIC — NOT EDGE``.

Usage
-----
  python 06_RESEARCH/scripts/near_miss_counterfactual.py            # capture + analyze
  python 06_RESEARCH/scripts/near_miss_counterfactual.py --analyze-only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

import phase3_structure_funnel as p3  # noqa: E402  (frozen composition)
from product_baseline_pilot import PILOT_COSTS  # noqa: E402  (reused config)

BANNER = "DIAGNOSTIC — NOT EDGE"
LOGIC_CHANGED = "NO"

RESULTS_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "near_miss_counterfactual"
CAPTURE_DIR = RESULTS_ROOT / "capture"
EVENTS_PATH = RESULTS_ROOT / "events.json"

LOAD_FROM = "2025-05-01"
EXEC_FROM = "2025-06-01"
EXEC_TO = "2025-11-30"
CAPTURE_TAG = "near_miss_capture"

# Frozen secondary horizon (Track-B's H_PATH), disclosed only.
EXTENDED_HORIZON_BARS = 100

# Baseline artifacts the capture must reproduce byte-for-byte.
BASELINE_RUN1 = (REPO_ROOT / "06_RESEARCH" / "results"
                 / "product_6m_refresh_track_b" / "run1")

ARMS = ("filled_control", "placed_unfilled", "blocked_session",
        "blocked_r7_far", "blocked_other")


# ---------------------------------------------------------------------- #
# Pure helpers (test-locked; no I/O, no clock, no engine state)
# ---------------------------------------------------------------------- #
def limit_touch(direction: str, limit: float, low: float, high: float) -> bool:
    """Locked fill semantics: touch = fill (inclusive), mirrored exactly.

    LONG buy-limit fills when ``low <= limit``; SHORT sell-limit when
    ``high >= limit`` (``smc.backtest.fill_model.limit_filled``).
    """
    if direction == "long":
        return float(low) <= float(limit)
    return float(high) >= float(limit)


def sl_tag(direction: str, sl: float, low: float, high: float) -> bool:
    """Stop tagged this bar (LONG ``low <= sl`` / SHORT ``high >= sl``)."""
    if direction == "long":
        return float(low) <= float(sl)
    return float(high) >= float(sl)


def tp_tag(direction: str, tp: float, low: float, high: float) -> bool:
    """Target tagged this bar (LONG ``high >= tp`` / SHORT ``low <= tp``)."""
    if direction == "long":
        return float(high) >= float(tp)
    return float(low) <= float(tp)


def eligible_window(present_bar: int, rest_bars: int, series_len: int) -> tuple:
    """Frozen order lifetime as fill-eligible bar bounds (inclusive).

    Placement runs at runner step 6 (after that bar's fills) and §23
    expiry removes a resting order at step 3 (before fills) once
    ``bars_open >= rest_bars``: an order placed on N is fill-eligible on
    ``N+1 .. N+rest_bars-2``.  ``(first, last)`` is empty-detectable
    (``last < first``).
    """
    first = int(present_bar) + 1
    last = min(int(present_bar) + int(rest_bars) - 2, int(series_len) - 1)
    return first, last


def first_touch(direction: str, limit: float, bars, first: int, last: int):
    """First bar index in ``[first, last]`` whose range touches ``limit``."""
    if last < first:
        return None
    for index in range(max(0, first), min(last, len(bars) - 1) + 1):
        bar = bars[index]
        if limit_touch(direction, limit, bar["low"], bar["high"]):
            return index
    return None


def closest_approach(direction: str, limit: float, bars, first: int,
                     last: int):
    """Smallest price distance to the limit over ``[first, last]``.

    Positive when never touched (LONG: ``low - limit`` — price must fall
    to a buy limit; SHORT: ``limit - high`` — price must rise to a sell
    limit), 0.0 when touched — the FR-4b closest-approach read, mirrored
    rather than re-invented.
    """
    if last < first:
        return None
    best = None
    for index in range(max(0, first), min(last, len(bars) - 1) + 1):
        bar = bars[index]
        if direction == "long":
            value = float(bar["low"]) - float(limit)
        else:
            value = float(limit) - float(bar["high"])
        value = max(value, 0.0)
        best = value if best is None else min(best, value)
    return best


def _excursions(direction: str, entry: float, bars, start: int, end: int) -> tuple:
    """Favourable / adverse excursion (positive magnitudes) over a window."""
    mfe = 0.0
    mae = 0.0
    for index in range(max(0, start), min(end, len(bars) - 1) + 1):
        bar = bars[index]
        if direction == "long":
            mfe = max(mfe, float(bar["high"]) - entry)
            mae = max(mae, entry - float(bar["low"]))
        else:
            mfe = max(mfe, entry - float(bar["low"]))
            mae = max(mae, float(bar["high"]) - entry)
    return mfe, mae


def simulate_route(route: dict, bars, *, horizon_bars: int | None = None) -> dict:
    """Paper-trade one route under the frozen fill semantics.

    ``horizon_bars`` overrides the route's own R8 lifetime (secondary
    disclosed pass only).  Returns the exclusive outcome label plus path
    diagnostics; nothing is invented when geometry or series is missing
    (``DATA_GAP``).
    """
    direction = route.get("direction")
    entry = route.get("entry")
    sl = route.get("sl")
    tp = route.get("tp")
    present_bar = route.get("present_bar")
    risk_ref = route.get("original_sl")
    if risk_ref in (None, ""):
        risk_ref = sl
    base = {
        "route_id": route.get("route_id"),
        "arm": route.get("arm"),
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "original_sl": route.get("original_sl"),
        "anchor_kind": route.get("anchor_kind"),
        "present_bar": present_bar,
        "rest_bars_used": (horizon_bars if horizon_bars is not None
                           else route.get("rest_bars")),
        "fill_index": None,
        "exit_index": None,
        "bars_to_fill": None,
        "bars_to_outcome": None,
        "mfe_r": None,
        "mae_r": None,
        "sl_then_tp": None,
        "touched_inside_lifetime": None,
        "touched_at_any_horizon": None,
        "note": "",
    }
    if direction not in ("long", "short"):
        return {**base, "outcome": "DATA_GAP", "note": "missing/unknown direction"}
    if entry in (None, "") or sl in (None, "") or tp in (None, ""):
        return {**base, "outcome": "DATA_GAP",
                "note": "missing entry/sl/tp (never invented)"}
    if present_bar is None or not isinstance(present_bar, int):
        return {**base, "outcome": "DATA_GAP", "note": "missing presentation bar"}
    entry, sl, tp = float(entry), float(sl), float(tp)
    rest = int(horizon_bars if horizon_bars is not None else route.get("rest_bars"))
    first, last = eligible_window(present_bar, rest, len(bars))
    if last < first:
        return {**base, "outcome": "DATA_GAP",
                "note": "empty eligible window (series truncation)"}

    fill_index = first_touch(direction, entry, bars, first, last)
    touched_any = first_touch(direction, entry, bars, first,
                              min(present_bar + EXTENDED_HORIZON_BARS - 1,
                                  len(bars) - 1))
    if fill_index is None:
        return {**base, "outcome": "EXPIRED_NO_FILL",
                "touched_inside_lifetime": False,
                "touched_at_any_horizon": touched_any is not None,
                "late_touch_index": touched_any,
                "bars_after_lifetime": (touched_any - last
                                        if touched_any is not None else None),
                "min_distance_live": closest_approach(direction, entry, bars,
                                                      first, last),
                "note": ("limit never touched inside the order lifetime"
                         + ("; touched later at the disclosed 100-bar horizon"
                            if touched_any is not None else "")),
                "bars_to_fill": None}

    # Filled: resolve the frozen same-bar SL-before-TP path, uncapped.
    exit_index = None
    kind = None
    for index in range(fill_index, len(bars)):
        bar = bars[index]
        if sl_tag(direction, sl, bar["low"], bar["high"]):
            exit_index, kind = index, "SL_HIT"
            break
        if tp_tag(direction, tp, bar["low"], bar["high"]):
            exit_index, kind = index, "TP_HIT"
            break
    risk = abs(entry - float(risk_ref)) if risk_ref not in (None, "") else None
    if kind is None:
        end = len(bars) - 1
        mfe, mae = _excursions(direction, entry, bars, fill_index, end)
        return {**base, "outcome": "OPEN_UNRESOLVED",
                "fill_index": fill_index,
                "bars_to_fill": fill_index - present_bar,
                "mfe_r": (round(mfe / risk, 6) if risk else None),
                "mae_r": (round(mae / risk, 6) if risk else None),
                "touched_inside_lifetime": True,
                "touched_at_any_horizon": True,
                "note": "filled; neither SL nor TP tagged before series end"}

    mfe, mae = _excursions(direction, entry, bars, fill_index, exit_index)
    sl_then_tp = None
    if kind == "SL_HIT":
        sl_then_tp = first_touch(direction, tp, bars, exit_index + 1,
                                 len(bars) - 1) is not None
    return {**base, "outcome": kind,
            "fill_index": fill_index,
            "exit_index": exit_index,
            "bars_to_fill": fill_index - present_bar,
            "bars_to_outcome": exit_index - fill_index,
            "mfe_r": (round(mfe / risk, 6) if risk else None),
            "mae_r": (round(mae / risk, 6) if risk else None),
            "sl_then_tp": sl_then_tp,
            "touched_inside_lifetime": True,
            "touched_at_any_horizon": True,
            "note": ""}


def classify_arm(*, placed: bool, filled: bool, first_block: str | None) -> str:
    """Exclusive arm for one route (filled > placed > first block reason)."""
    if filled:
        return "filled_control"
    if placed:
        return "placed_unfilled"
    if first_block == "skip_place_far_from_zone":
        return "blocked_r7_far"
    if first_block == "session":
        return "blocked_session"
    return "blocked_other"


def outcome_mix(rows) -> dict:
    """Exclusive-label histogram (sorted, zero-free)."""
    mix: dict[str, int] = {}
    for row in rows:
        label = row.get("outcome") or "DATA_GAP"
        mix[label] = mix.get(label, 0) + 1
    return dict(sorted(mix.items()))


def evaluate_kill_criteria(control_rows, untaken_rows) -> dict:
    """Pre-registered verdict: protective vs destructive placement gates.

    Frozen rule (stated before running, no post-hoc adjustment):

    * no untaken rows -> INCONCLUSIVE;
    * unresolved untaken population (0 resolved paths) -> the gates cut
      off nothing that could be taken -> PLACEMENT_NOT_PRIMARY;
    * resolved contrast needs n >= 5 resolved untaken rows, then the
      TP-hit rate is compared against the control arm's;
    * anything else -> INCONCLUSIVE (n too small to read).
    """
    def _resolved(rows):
        return [r for r in rows if r["outcome"] in ("TP_HIT", "SL_HIT")]

    control_resolved = _resolved(control_rows)
    untaken_resolved = _resolved(untaken_rows)
    control_tp = sum(1 for r in control_resolved if r["outcome"] == "TP_HIT")
    untaken_tp = sum(1 for r in untaken_resolved if r["outcome"] == "TP_HIT")
    control_rate = (control_tp / len(control_resolved)) if control_resolved else None
    untaken_rate = (untaken_tp / len(untaken_resolved)) if untaken_resolved else None
    expired_no_fill = sum(1 for r in untaken_rows
                          if r["outcome"] == "EXPIRED_NO_FILL")

    result = {
        "n_control": len(control_rows),
        "n_untaken": len(untaken_rows),
        "n_resolved_control": len(control_resolved),
        "n_resolved_untaken": len(untaken_resolved),
        "control_tp_hit_rate": control_rate,
        "untaken_tp_hit_rate": untaken_rate,
        "tp_hit_rate_diff": (None if untaken_rate is None or control_rate is None
                             else round(untaken_rate - control_rate, 6)),
        "untaken_expired_no_fill": expired_no_fill,
        "untaken_expired_no_fill_rate": (round(expired_no_fill / len(untaken_rows), 6)
                                         if untaken_rows else None),
        "rule": ("no untaken -> INCONCLUSIVE; 0 resolved untaken -> "
                 "PLACEMENT_NOT_PRIMARY; resolved n >= 5 -> TP-rate contrast; "
                 "else INCONCLUSIVE"),
    }
    if not untaken_rows:
        result["verdict"] = "INCONCLUSIVE"
        result["reason"] = "no unplaced/blocked routes to paper-trade"
    elif not untaken_resolved:
        result["verdict"] = "PLACEMENT_NOT_PRIMARY"
        result["reason"] = ("every untaken route never touched its own limit "
                            "inside the product lifetime it would have been "
                            "granted — the gates cut off no takeable path")
    elif len(untaken_resolved) < 5:
        result["verdict"] = "INCONCLUSIVE"
        result["reason"] = (f"resolved untaken n={len(untaken_resolved)} < 5 — "
                            "contrast cannot be read")
    elif untaken_rate is not None and control_rate is not None \
            and untaken_rate > control_rate:
        result["verdict"] = "PLACEMENT_BOTTLENECK_CANDIDATE"
        result["reason"] = ("untaken routes' TP-hit rate exceeds control — "
                            "placement gates are a bottleneck candidate for a "
                            "later dated ruling (no change made here)")
    else:
        result["verdict"] = "PLACEMENT_NOT_PRIMARY"
        result["reason"] = ("untaken TP-hit rate <= control — scarcity is not "
                            "attributable to placement gates")
    return result


# ---------------------------------------------------------------------- #
# Capture (logging-only seam over the frozen composition)
# ---------------------------------------------------------------------- #
CAPTURE: dict = {"init": [], "candidates": [], "placements": []}


def _trigger_value(trigger) -> str:
    return str(getattr(trigger, "value", trigger))


def _direction_value(direction) -> str:
    return str(getattr(direction, "value", direction))


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _install_seams():
    """Wrap three frozen seams (class-level); returns restore callables."""
    from smc.backtest.orders import PendingOrderBook
    from smc.backtest.runner import BacktestRunner

    from smc.risk.fill_regime_policy import rest_bars_for
    from smc.config.timeframe import Timeframe

    original_init = BacktestRunner.__init__
    original_entries = BacktestRunner._process_entries
    original_place = PendingOrderBook.place

    def capturing_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        CAPTURE["init"].append(self)

    def capturing_entries(self, bar, bar_index, now):
        candidates = list(self._pending_entries)
        before = len(self.blocked_log)
        original_entries(self, bar, bar_index, now)
        new_blocks = self.blocked_log[before:]
        cursor = 0
        for candidate in candidates:
            blocked_by = None
            if cursor < len(new_blocks) and \
                    new_blocks[cursor].poi_id == candidate.poi_id:
                blocked_by = new_blocks[cursor].blocked_by
                cursor += 1
            detection_tf = getattr(candidate, "detection_tf", None)
            is_m8 = bool(getattr(candidate, "is_m8", False))
            CAPTURE["candidates"].append({
                "bar_index": bar_index,
                "timestamp": _iso(bar.timestamp),
                "bar_close": getattr(bar, "close", None),
                "blocked_by": blocked_by,
                "route_id": getattr(candidate, "route_id", None),
                "poi_id": getattr(candidate, "poi_id", None),
                "trigger": _trigger_value(getattr(candidate, "trigger", None)),
                "direction": _direction_value(getattr(candidate, "direction", None)),
                "entry": getattr(candidate, "entry_price", None),
                "sl": getattr(candidate, "sl_price", None),
                "tp": getattr(candidate, "tp_price", None),
                "original_sl": getattr(candidate, "original_sl", None),
                "zone_low": getattr(candidate, "zone_low", None),
                "zone_high": getattr(candidate, "zone_high", None),
                "tp_source": getattr(candidate, "tp_source", None),
                "model_tags": list(getattr(candidate, "model_tags", None) or []),
                "detection_tf": getattr(detection_tf, "name", str(detection_tf)),
                "is_m8": is_m8,
                "rest_bars": rest_bars_for(detection_tf, is_m8,
                                           execution_tf=Timeframe.M5),
                "score": getattr(candidate, "score", None),
            })
        if cursor != len(new_blocks):
            raise RuntimeError(
                "capture: blocked-log delta did not align with presented "
                f"candidates at bar {bar_index} "
                f"({cursor} consumed of {len(new_blocks)})")

    def capturing_place(self, **kwargs):
        order = original_place(self, **kwargs)
        CAPTURE["placements"].append({
            "ticket": order.ticket,
            "placed_bar": order.placed_bar,
            "placed_at": _iso(order.placed_at),
            "direction": _direction_value(order.direction),
            "entry": order.entry_price,
            "sl": order.sl,
            "tp": order.tp,
            "volume": order.volume,
            "poi_id": order.poi_id,
            "route_id": order.comment or None,
            "trigger": _trigger_value(order.trigger),
            "model_tags": list(order.model_tags or []),
            "zone_low": order.zone_low,
            "zone_high": order.zone_high,
            "original_sl": order.original_sl,
            "tp_source": order.tp_source,
            "rest_bars": order.rest_bars,
            "detection_tf": getattr(order.detection_tf, "name",
                                    str(order.detection_tf)),
        })
        return order

    BacktestRunner.__init__ = capturing_init
    BacktestRunner._process_entries = capturing_entries
    PendingOrderBook.place = capturing_place

    def restore():
        BacktestRunner.__init__ = original_init
        BacktestRunner._process_entries = original_entries
        PendingOrderBook.place = original_place

    return restore


def run_capture(*, window: dict | None = None, out_dir: Path | None = None,
                tag: str = CAPTURE_TAG) -> dict:
    """Run the frozen composition under the logging seam; return events."""
    window = window or {"load_from": LOAD_FROM, "exec_from": EXEC_FROM,
                        "exec_to": EXEC_TO}
    out_dir = Path(out_dir or CAPTURE_DIR).resolve()
    CAPTURE["init"].clear()
    CAPTURE["candidates"].clear()
    CAPTURE["placements"].clear()
    out_dir.mkdir(parents=True, exist_ok=True)
    args = argparse.Namespace(
        tag=tag,
        out_root=str(out_dir.relative_to(REPO_ROOT)),
        load_from=window["load_from"],
        exec_from=window["exec_from"],
        exec_to=window["exec_to"],
        cost_config=PILOT_COSTS,
    )
    t0 = time.perf_counter()
    restore = _install_seams()
    try:
        summary = p3.run(args)
    finally:
        restore()
    runners = CAPTURE["init"]
    if not runners:
        raise SystemExit("capture: runner instance was never constructed")
    runner = runners[-1]
    is_baseline_window = (window["load_from"] == LOAD_FROM
                          and window["exec_from"] == EXEC_FROM
                          and window["exec_to"] == EXEC_TO)
    events = {
        "banner": BANNER,
        "window": window,
        "is_baseline_window": is_baseline_window,
        "candidates": CAPTURE["candidates"],
        "placements": CAPTURE["placements"],
        "blocked_log": [
            {"bar_index": b.bar_index, "now": _iso(b.now),
             "blocked_by": b.blocked_by, "poi_id": b.poi_id,
             "trigger": _trigger_value(b.trigger), "route_id": b.route_id}
            for b in runner.blocked_log
        ],
        "intent_events": [dict(ev) for ev in runner.intents.events],
        "funnel": summary,
        "integrity": (
            {
                "trades_csv_matches_run1": _sha(out_dir / "trades.csv")
                == _sha(BASELINE_RUN1 / "trades.csv"),
                "report_json_matches_run1": _sha(out_dir / "report.json")
                == _sha(BASELINE_RUN1 / "report.json"),
                "sha256_capture_trades": _sha(out_dir / "trades.csv"),
                "sha256_run1_trades": _sha(BASELINE_RUN1 / "trades.csv"),
            }
            if is_baseline_window else {"baseline_check": "skipped (non-baseline window)"}
        ),
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }
    if out_dir == CAPTURE_DIR:
        EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVENTS_PATH.write_text(json.dumps(events, indent=2, default=str),
                               encoding="utf-8")
    return events


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------- #
# Series + route table
# ---------------------------------------------------------------------- #
def load_exec_bars(window: dict | None = None):
    """The composition's own M5 execution series (same filters/loader)."""
    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    window = window or {"load_from": LOAD_FROM, "exec_from": EXEC_FROM,
                        "exec_to": EXEC_TO}
    exec_from = datetime.strptime(window["exec_from"], "%Y-%m-%d").replace(
        tzinfo=timezone.utc)
    exec_to = (datetime.strptime(window["exec_to"], "%Y-%m-%d")
               .replace(tzinfo=timezone.utc)
               + timedelta(days=1) - timedelta(minutes=1))
    load_from = datetime.strptime(window["load_from"], "%Y-%m-%d").replace(
        tzinfo=timezone.utc)
    m1 = load_ohlcv_parquet(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet")
    m1 = [c for c in m1 if load_from <= c.timestamp <= exec_to + timedelta(days=1)]
    if not m1:
        raise SystemExit("near-miss: empty M1 load — check 07_DATA")
    multi = resample_multi(m1, [Timeframe.M5])
    m5 = [c for c in multi[Timeframe.M5] if exec_from <= c.timestamp <= exec_to]
    if len(m5) < 50:
        raise SystemExit("near-miss: execution window too small")
    return [{"timestamp": c.timestamp, "low": c.low, "high": c.high,
             "close": c.close} for c in m5]


def build_routes(events: dict, *, out_dir: Path | None = None) -> list[dict]:
    """Dedupe candidates by route_id into the route table (frozen rules)."""
    out_dir = Path(out_dir or CAPTURE_DIR).resolve()
    routes: dict[str, dict] = {}
    for cand in events["candidates"]:
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
                "model_tags": "|".join(cand.get("model_tags") or []),
                "tp_source": cand.get("tp_source"),
                "entry": cand.get("entry"),
                "sl": cand.get("sl"),
                "tp": cand.get("tp"),
                "original_sl": cand.get("original_sl"),
                "zone_low": cand.get("zone_low"),
                "zone_high": cand.get("zone_high"),
                "rest_bars": cand.get("rest_bars"),
                "first_present_bar": cand.get("bar_index"),
                "present_bar": cand.get("bar_index"),
                "anchor_kind": "first_presentation_bar",
                "first_present_ts": cand.get("timestamp"),
                "n_presentations": 0,
                "block_reasons": {},
                "placed": False,
                "placed_bar": None,
                "ticket": None,
                "filled": False,
            }
            routes[rid] = rec
        rec["n_presentations"] += 1
        reason = cand.get("blocked_by")
        if reason:
            rec["block_reasons"][reason] = rec["block_reasons"].get(reason, 0) + 1
            rec["first_block_reason"] = rec.get("first_block_reason", reason)

    # Placements come from the run's own order book (verbatim geometry).
    for order in events["placements"]:
        rid = order.get("route_id")
        if rid and rid in routes:
            rec = routes[rid]
            rec["placed"] = True
            rec["placed_bar"] = order["placed_bar"]
            # Placed rows anchor the counterfactual on the ACTUAL placement
            # bar (the event being reproduced) with the order's own R8
            # lifetime; unplaced/blocked rows anchor on their first
            # presentation bar.  Both are "the lifetime the product would
            # have granted this route" — disclosed, one rule each.
            rec["present_bar"] = order["placed_bar"]
            rec["anchor_kind"] = "placed_bar"
            rec["ticket"] = order["ticket"]
            rec["entry"] = order["entry"]
            rec["sl"] = order["sl"]
            rec["tp"] = order["tp"]
            rec["original_sl"] = order["original_sl"]
            rec["rest_bars"] = order["rest_bars"]
            rec["entry_anchor"] = order.get("entry_anchor")

    # Fills: the run's own closed trades (byte-checked against run1).
    with (out_dir / "trades.csv").open(newline="", encoding="utf-8") as fh:
        for trade in csv.DictReader(fh):
            rid = trade.get("route_id") or ""
            rec = routes.get(rid)
            if rec is None:
                continue
            rec["filled"] = True
            rec["actual_exit_kind"] = trade.get("close_kind")
            rec["actual_pnl"] = float(trade.get("pnl") or 0.0)
            rec["actual_bars_held"] = trade.get("bars_held")
            rec["actual_f_timing_label"] = trade.get("f_timing_label")
            if rec["present_bar"] is None:
                rec["present_bar"] = int(trade.get("entry_bar") or 0)

    rows: list[dict] = []
    for rec in routes.values():
        rec["arm"] = classify_arm(placed=rec["placed"], filled=rec["filled"],
                                  first_block=rec.get("first_block_reason"))
        rows.append(rec)
    rows.sort(key=lambda r: (ARM_ORDER.get(r["arm"], 99),
                             r["present_bar"] if r["present_bar"] is not None else -1))
    return rows


ARM_ORDER = {arm: index for index, arm in enumerate(ARMS)}


def _fmt(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(row.get(k)) for k in fieldnames})


CANDIDATE_FIELDS = [    "route_id", "arm", "poi_id", "trigger", "direction", "detection_tf",
    "is_m8", "model_tags", "tp_source", "entry", "sl", "tp", "original_sl",
    "zone_low", "zone_high", "rest_bars", "anchor_kind", "present_bar",
    "first_present_bar", "first_present_ts",
    "n_presentations", "first_block_reason", "block_reasons", "placed",
    "placed_bar", "ticket", "filled", "actual_exit_kind", "actual_pnl",
    "actual_bars_held",
]

OUTCOME_FIELDS = [
    "route_id", "arm", "direction", "entry", "sl", "tp", "original_sl",
    "anchor_kind", "present_bar", "rest_bars_used", "outcome",
    "outcome_actual", "actual_exit_kind", "actual_pnl",
    "fill_index", "exit_index",
    "bars_to_fill", "bars_to_outcome", "mfe_r", "mae_r", "sl_then_tp",
    "touched_inside_lifetime", "touched_at_any_horizon", "late_touch_index",
    "bars_after_lifetime", "min_distance_live", "outcome_100bar",
    "fill_index_100bar", "note",
]


def analyze(events: dict, *, out_dir: Path | None = None) -> dict:
    """Build the artifacts + verdict from captured events (pure compute)."""
    out_dir = Path(out_dir or CAPTURE_DIR).resolve()
    bars = load_exec_bars(events.get("window"))
    routes = build_routes(events, out_dir=out_dir)

    primary = [simulate_route(route, bars) for route in routes]
    extended = [simulate_route(route, bars,
                               horizon_bars=EXTENDED_HORIZON_BARS)
                for route in routes]
    for row, ext in zip(primary, extended):
        row["outcome_100bar"] = ext["outcome"]
        row["fill_index_100bar"] = ext["fill_index"]

    control = [r for r in primary if r["arm"] == "filled_control"]
    untaken = [r for r in primary if r["arm"] != "filled_control"]

    # Integrity: the control arm must reproduce the product's own fills.
    with (out_dir / "trades.csv").open(newline="", encoding="utf-8") as fh:
        trades_by_route = {t["route_id"]: t for t in csv.DictReader(fh)}
    fills = {rid: int(t["entry_bar"]) for rid, t in trades_by_route.items()}
    _ACTUAL = {"take_profit": "TP_HIT", "stop_loss": "SL_HIT"}
    for row in primary:
        trade = trades_by_route.get(row["route_id"])
        row["outcome_actual"] = None
        row["actual_exit_kind"] = None
        row["actual_pnl"] = None
        if trade is not None:
            kind = trade.get("close_kind") or ""
            row["outcome_actual"] = _ACTUAL.get(kind, "DATA_GAP")
            row["actual_exit_kind"] = kind
            row["actual_pnl"] = float(trade.get("pnl") or 0.0)

    control_checks = []
    for row in control:
        route = next(r for r in routes if r["route_id"] == row["route_id"])
        first, last = eligible_window(route["placed_bar"], route["rest_bars"],
                                      len(bars))
        control_checks.append({
            "route_id": row["route_id"],
            "placed_bar": route["placed_bar"],
            "fill_reproduced": (row["fill_index"] == fills.get(row["route_id"])),
            "eligible": [first, last],
            "actual_fill_bar": None,
            "engine_fill_bar": row["fill_index"],
            "engine_outcome": row["outcome"],
            "actual_exit_kind": route.get("actual_exit_kind"),
        })
    for check in control_checks:
        check["actual_fill_bar"] = fills.get(check["route_id"])
    fill_reproduction = {
        "reproduced": sum(1 for c in control_checks if c["fill_reproduced"]),
        "of": len(control_checks),
        "all_reproduced": all(c["fill_reproduced"] for c in control_checks),
    }

    blocked_by_reason: dict[str, int] = {}
    for event in events["blocked_log"]:
        key = event["blocked_by"]
        blocked_by_reason[key] = blocked_by_reason.get(key, 0) + 1

    summary = {
        "banner": BANNER,
        "logic_changed": LOGIC_CHANGED,
        "script": "near_miss_counterfactual.py",
        "window": events["window"],
        "series_bars_m5": len(bars),
        "method": {
            "fill_semantics": ("touch = fill at limit (inclusive); SL before TP "
                               "on the same bar; no fill on the placement bar "
                               "(placement at runner step 6)"),
            "eligible_window": ("present_bar+1 .. present_bar+rest_bars-2 with "
                                "rest_bars = rest_bars_for(detection_tf, is_m8, "
                                "M5) — the route's own R8/§23 lifetime"),
            "primary_present_bar": "first presentation bar per route_id",
            "costs": "gross path labels only (no cost model in this pass)",
            "be_stop": ("NOT modelled (PureRunner BE needs live risk state); "
                        "divergence quantified against the control arm's real "
                        "exits in the note, never invented"),
            "extended_horizon_bars": EXTENDED_HORIZON_BARS,
            "labels": ["TP_HIT", "SL_HIT", "EXPIRED_NO_FILL", "DATA_GAP",
                       "OPEN_UNRESOLVED (documented extension)"],
        },
        "counts": {
            "routes_captured": len(routes),
            "routes_funnel": events["funnel"].get("routes"),
            "placements_captured": len(events["placements"]),
            "placements_funnel": events["funnel"].get("placed"),
            "fills_funnel": events["funnel"].get("fills"),
            "blocked_log_events": len(events["blocked_log"]),
            "blocked_by_reason": dict(sorted(blocked_by_reason.items())),
        },
        "integrity": events["integrity"],
        "control_checks": control_checks,
        "control_fill_reproduction": fill_reproduction,
        "outcome_mix": {
            "control_raw_engine": outcome_mix(control),
            "control_actual": outcome_mix(
                [{"outcome": r["outcome_actual"]} for r in control
                 if r["outcome_actual"]]),
            "control_raw_vs_actual_divergence": sum(
                1 for r in control if r["outcome_actual"]
                and r["outcome_actual"] != r["outcome"]),
            "untaken": outcome_mix(untaken),
            "all": outcome_mix(primary),
            "by_arm": {arm: outcome_mix([r for r in primary if r["arm"] == arm])
                       for arm in ARMS},
            "extended_100bar_untaken": outcome_mix(
                [{"outcome": r["outcome_100bar"]} for r in untaken]),
        },
        "kill_criteria": evaluate_kill_criteria(control, untaken),
        "texture": {
            "untaken_never_touched_at_all": sum(
                1 for r in untaken
                if not r.get("touched_at_any_horizon")),
            "untaken_touched_only_after_lifetime": sum(
                1 for r in untaken
                if r.get("touched_at_any_horizon")
                and not r.get("touched_inside_lifetime")),
            "untaken_median_closest_approach_live": (
                round(statistics.median([
                    r["min_distance_live"] for r in untaken
                    if r.get("min_distance_live") is not None]), 6)
                if any(r.get("min_distance_live") is not None for r in untaken)
                else None),
            "untaken_extended_100bar_outcome": outcome_mix(
                [{"outcome": r["outcome_100bar"]} for r in untaken]),
        },
        "notes": [
            BANNER,
            "Diagnostic counts only — no expectancy, PF, or win-rate claim "
            "on n this small.",
            "No gate, threshold, pillar, trigger, risk, session, or locked "
            "constant was changed; nothing here authorizes a change.",
            events["funnel"].get("notes", []),
        ],
    }

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    results_root = RESULTS_ROOT if out_dir == CAPTURE_DIR else out_dir.parent
    results_root.mkdir(parents=True, exist_ok=True)
    candidates_rows = [dict(r, block_reasons=";".join(
        f"{k}={v}" for k, v in sorted((r.get("block_reasons") or {}).items())))
        for r in routes]
    _write_csv(results_root / "candidates.csv", candidates_rows,
               CANDIDATE_FIELDS)
    _write_csv(results_root / "outcomes.csv", primary, OUTCOME_FIELDS)
    (results_root / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analyze-only", action="store_true",
                    help="reuse results/near_miss_counterfactual/events.json")
    ap.add_argument("--load-from", default=LOAD_FROM)
    ap.add_argument("--exec-from", default=EXEC_FROM)
    ap.add_argument("--exec-to", default=EXEC_TO)
    ap.add_argument("--tag", default=CAPTURE_TAG)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    window = {"load_from": args.load_from, "exec_from": args.exec_from,
              "exec_to": args.exec_to}
    out_dir = Path(args.out_dir).resolve() if args.out_dir else CAPTURE_DIR
    if args.analyze_only:
        events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    else:
        events = run_capture(window=window, out_dir=out_dir, tag=args.tag)
    summary = analyze(events, out_dir=out_dir)
    print(json.dumps({
        "banner": BANNER,
        "integrity": summary["integrity"],
        "counts": summary["counts"],
        "outcome_mix": summary["outcome_mix"],
        "kill_criteria": summary["kill_criteria"],
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
