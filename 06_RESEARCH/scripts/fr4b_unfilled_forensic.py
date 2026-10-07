"""FR-4b unfilled-order forensic — why did the 5 resting limits never fill?

Read-only vs strategy: the FR-4b window is re-run under the identical
frozen config with a LOGGING-ONLY recording order book swapped in on the
``fr4_fidelity_baseline.CountingOrderBook`` module-attribute seam (same
instrumentation pattern as the FR-4 diag/fate scripts; production modules
untouched, restoration guaranteed). Every placed order is then measured
against the M5 series:

* exact live window under the locked runner order (placement at step 6 —
  after fills; expiry at step 3 — before fills): an order placed on bar N
  is fill-eligible on bars N+1 .. N+10 (on N+11 ``bars_open`` reaches the
  frozen §23 limit of 12 and ``_expire_orders`` removes it pre-fill);
* touch semantics copied from ``smc.backtest.fill_model.limit_filled``
  (inclusive: LONG fills when ``bar.low <= limit``, SHORT when
  ``bar.high >= limit``) — the script never "fixes" fills, it measures;
* post-expiry horizon: expiry bar (N+11) through window end.

Fates: ``never_touched_in_life`` | ``touched_while_live_unfilled_ANOMALY``
| ``touched_only_after_expiry`` | ``data_gap`` (insufficient M5 data after
placement to evaluate any eligible bar).

No MT5 is used (backtest core is MT5-free by design); loader failures and
out-of-range indices are guarded with explicit errors. Diagnostic only —
no expiry/gate/timing/threshold conclusion is implemented here.

Usage:
  python 06_RESEARCH/scripts/fr4b_unfilled_forensic.py
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

import fr4_fidelity_baseline as fr4  # noqa: E402
import fr4b_wider_window as fr4b  # noqa: E402

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "fr4b_wider"
FORENSIC_OUT = OUT_DIR / "forensic_run"

# Locked §23 M5 unfilled-order expiry (expiry_bars_for) and the runner's
# operation-order consequences, stated once and reused below.
SECTION23_M5_BARS = 12           # bars_open >= 12 -> expired (placement bar counts)
FIRST_ELIGIBLE_OFFSET = 1        # placed bar N -> first fill-eligible bar N+1
LAST_ELIGIBLE_OFFSET = SECTION23_M5_BARS - 2  # N+10: N+11 expires pre-fill


class RecordingOrderBook(fr4.CountingOrderBook):
    """Logging-only book: records every place/cancel/expiry/fill event.

    Class-level registry because ``fr4.run`` constructs the book locally.
    All overrides delegate to the parent first, then record — behavior is
    byte-identical to the frozen run (verified against run1 artifacts).
    """

    INSTANCES: list["RecordingOrderBook"] = []

    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict] = []
        type(self).INSTANCES.append(self)

    def place(self, **kwargs):
        order = super().place(**kwargs)
        self.events.append({
            "event": "placed", "ticket": order.ticket,
            "placed_bar": order.placed_bar,
            "placed_at": order.placed_at,
            "direction": getattr(order.direction, "value", str(order.direction)),
            "limit": order.entry_price, "sl": order.sl, "tp": order.tp,
            "volume": order.volume, "poi_id": order.poi_id,
            "trigger": getattr(order.trigger, "value", str(order.trigger)),
            "model_tags": list(order.model_tags) if order.model_tags else [],
            "zone_low": order.zone_low, "zone_high": order.zone_high,
            "signal_data_json": order.signal_data_json,
        })
        return order

    def cancel(self, ticket: int):
        order = super().cancel(ticket)
        if order is not None:
            # The runner's fill path ALSO cancels (``_apply_fills``); the
            # caller context disambiguates via the run's trade count.
            self.events.append({"event": "cancelled", "ticket": ticket,
                                "reason": "cancel_or_fill"})
        return order

    def remove(self, order) -> None:
        self.events.append({"event": "filled", "ticket": order.ticket})
        super().remove(order)

    def expired_by_section23(self, current_bar: int, timeframe):
        cancelled = super().expired_by_section23(current_bar, timeframe)
        for order in cancelled:
            self.events.append({"event": "expired", "ticket": order.ticket,
                                "reason": "section23", "at_bar": current_bar})
        return cancelled

    def expired_by_give_up(self, current_bar: int):
        cancelled = super().expired_by_give_up(current_bar)
        for order in cancelled:
            self.events.append({"event": "expired", "ticket": order.ticket,
                                "reason": "give_up", "at_bar": current_bar})
        return cancelled


def load_m5_series(load_from: str, exec_from: str, exec_to: str):
    """Reload the FR-4b M5 execution series (identical filters to fr4.run)."""
    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    load_dt = datetime.strptime(load_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    exec_dt_from = datetime.strptime(exec_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    exec_dt_to = (datetime.strptime(exec_to, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                  + timedelta(days=1) - timedelta(minutes=1))
    m1 = load_ohlcv_parquet(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet")
    m1 = [c for c in m1 if load_dt <= c.timestamp <= exec_dt_to + timedelta(days=1)]
    if not m1:
        raise SystemExit("forensic: M1 load produced an empty series — check 07_DATA")
    multi = resample_multi(m1, [Timeframe.M5])
    m5 = [c for c in multi[Timeframe.M5]
          if exec_dt_from <= c.timestamp <= exec_dt_to]
    if len(m5) < 50:
        raise SystemExit("forensic: execution window too small for analysis")
    return m5


def analyze(m5, events: list[dict], trades_closed: int) -> tuple[list[dict], dict]:
    """Build one forensic row per placed order (index-guarded throughout)."""
    n_bars = len(m5)
    lows = [c.low for c in m5]
    highs = [c.high for c in m5]
    times = [c.timestamp for c in m5]
    placed = [e for e in events if e["event"] == "placed"]
    end_events = {e["ticket"]: e for e in events if e["event"] in
                  ("expired", "cancelled", "filled")}
    rows: list[dict] = []

    for order in placed:
        ticket = order["ticket"]
        n = order["placed_bar"]
        if not 0 <= n < n_bars:
            rows.append({**order, "fate_class": "data_gap",
                         "detail": f"placed_bar {n} outside M5 series (0..{n_bars - 1})"})
            continue
        is_long = order["direction"] == "long"
        limit = float(order["limit"])

        def _touch(bar_index: int) -> bool:
            # fill_model.limit_filled semantics, mirrored exactly.
            return (lows[bar_index] <= limit) if is_long else (highs[bar_index] >= limit)

        # Live (fill-eligible) bars: N+1 .. min(N+10, window end).
        live_first = n + FIRST_ELIGIBLE_OFFSET
        live_last = min(n + LAST_ELIGIBLE_OFFSET, n_bars - 1)
        eligible = max(0, live_last - live_first + 1)

        first_touch_live = next((i for i in range(live_first, live_last + 1)
                                 if _touch(i)), None)
        if first_touch_live is not None:
            min_dist_live = 0.0
        elif eligible > 0:
            # Closest approach of price to the limit while live (positive
            # when never touched): LONG buy-limit fills when low <= limit,
            # so distance at bar i is lows[i] - limit; SHORT is mirrored.
            if is_long:
                min_dist_live = min(lows[i] - limit for i in range(live_first, live_last + 1))
            else:
                min_dist_live = min(limit - highs[i] for i in range(live_first, live_last + 1))
        else:
            min_dist_live = None

        # Post-expiry horizon: expiry bar (N+11) .. window end.
        expire_bar = n + SECTION23_M5_BARS - 1
        first_touch_after = next((i for i in range(expire_bar, n_bars)
                                  if _touch(i)), None)

        end_event = end_events.get(ticket, {}).get("event")
        if end_event == "filled" or (end_event == "cancelled"
                                     and trades_closed > 0):
            # An actually-filled order is outside the unfilled taxonomy —
            # recorded factually and excluded from fate pivots (cannot occur
            # in the FR-4b window: trades_closed == 0, verified by the
            # byte-identity cross-check against run1).
            fate = "filled"
        elif eligible == 0:
            fate = "data_gap"
        elif first_touch_live is not None:
            fate = "touched_while_live_unfilled_ANOMALY"
        elif first_touch_after is not None:
            fate = "touched_only_after_expiry"
        else:
            fate = "never_touched_in_life"

        anchor = None
        if order.get("signal_data_json"):
            try:
                payload = json.loads(order["signal_data_json"])
                anchor = payload.get("entry_anchor") if isinstance(payload, dict) else None
            except (TypeError, ValueError):
                anchor = None

        rows.append({
            "ticket": ticket,
            "direction": order["direction"],
            "limit_price": limit,
            "volume": order["volume"],
            "poi_id": order["poi_id"],
            "model_tags": "+".join(order["model_tags"]) or "unknown",
            "is_m8": "M8" in (order["model_tags"] or []),
            "entry_anchor": anchor or "unknown",
            "placed_bar": n,
            "placed_time": order["placed_at"],
            "expire_bar": expire_bar,
            "expire_time": times[expire_bar] if expire_bar < n_bars else None,
            "end_event": end_events.get(ticket, {}).get("event", "still_resting"),
            "end_reason": end_events.get(ticket, {}).get("reason", ""),
            "bars_live_actual": eligible,
            "touch_while_live": first_touch_live is not None,
            "first_touch_bar_live": first_touch_live,
            "first_touch_time_live": times[first_touch_live] if first_touch_live is not None else None,
            "min_distance_to_limit_live": min_dist_live,
            "touch_after_expiry": first_touch_after is not None,
            "first_touch_bar_after": first_touch_after,
            "first_touch_time_after": times[first_touch_after] if first_touch_after is not None else None,
            "bars_after_to_touch": (first_touch_after - expire_bar
                                    if first_touch_after is not None else None),
            "bars_after_to_window_end": max(0, n_bars - expire_bar),
            "fate_class": fate,
        })
    return rows, {"m5_bars": n_bars}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--load-from", default=fr4b.DEFAULT_LOAD_FROM)
    ap.add_argument("--exec-from", default=fr4b.DEFAULT_EXEC_FROM)
    ap.add_argument("--exec-to", default=fr4b.DEFAULT_EXEC_TO)
    args = ap.parse_args()
    args.tag = "forensic"
    args.out_root = str(FORENSIC_OUT.relative_to(REPO_ROOT))
    args.diag_no_zone_gate = False

    RecordingOrderBook.INSTANCES.clear()
    original_book = fr4.CountingOrderBook
    fr4.CountingOrderBook = RecordingOrderBook  # logging-only seam
    t0 = time.perf_counter()
    try:
        summary = fr4b.run_with_gate_counter(args)
    finally:
        fr4.CountingOrderBook = original_book

    events = RecordingOrderBook.INSTANCES[-1].events if RecordingOrderBook.INSTANCES else []
    m5 = load_m5_series(args.load_from, args.exec_from, args.exec_to)
    rows, meta = analyze(m5, events, int(summary.get("trades_closed") or 0))

    FORENSIC_OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "unfilled_forensic.csv"
    json_path = OUT_DIR / "unfilled_forensic_summary.json"
    fieldnames = list(rows[0].keys()) if rows else ["fate_class"]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    def _median(values):
        values = [v for v in values if v is not None]
        return round(statistics.median(values), 6) if values else None

    fates = {}
    m8_fates = {}
    for row in rows:
        fates[row["fate_class"]] = fates.get(row["fate_class"], 0) + 1
        key = "M8" if row["is_m8"] else "non_M8"
        m8_fates.setdefault(key, {})
        m8_fates[key][row["fate_class"]] = m8_fates[key].get(row["fate_class"], 0) + 1

    # Determinism cross-check: the forensic run must reproduce run1 exactly.
    import hashlib
    def _sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    run1 = OUT_DIR / "run1"
    identity = {
        "trades_csv_matches_run1": _sha(FORENSIC_OUT / "trades.csv") == _sha(run1 / "trades.csv"),
        "report_json_matches_run1": _sha(FORENSIC_OUT / "report.json") == _sha(run1 / "report.json"),
    }

    out = {
        "script": "fr4b_unfilled_forensic.py",
        "window": [m5[0].timestamp.isoformat(), m5[-1].timestamp.isoformat()],
        "m5_bars": meta["m5_bars"],
        "orders_placed": summary.get("entries_placed"),
        "orders_recorded": len(rows),
        "fate_counts": fates,
        "m8_fate_counts": m8_fates,
        "median_min_distance_live": _median([r["min_distance_to_limit_live"] for r in rows]),
        "median_bars_live": _median([r["bars_live_actual"] for r in rows]),
        "median_bars_after_to_touch": _median([r["bars_after_to_touch"] for r in rows]),
        "section23_m5_bars": SECTION23_M5_BARS,
        "live_window_rule": "fill-eligible bars N+1..N+10 (placement at runner step 6 after fills; §23 expiry at step 3 before fills on N+11)",
        "forensic_run_matches_run1_bytes": identity,
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }
    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
