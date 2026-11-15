"""Instrumented single-pass FILL-LEG CAPTURE (GO: Lead Architect 2026-11-01).

banner: DIAGNOSTIC ONLY - NOT PERFORMANCE / NOT EDGE.

Runs the SAME production diagnostic machinery (coupled_mtf_full_menu_diagnostic)
over the SAME frozen window / window / parquet with ONE augmentation: logging
only. The paper book/position-store subclasses record one JSON line per
placement, FILL and EXIT into ``fill_legs.jsonl``. Zero strategy, sizing,
trigger, risk or threshold changes; ``04_SRC`` untouched; the existing
``coupled_mtf_full_menu_diag/**`` DONE trees are never touched — the capture
writes its own tree at:

    06_RESEARCH/results/coupled_mtf_fill_leg_capture/
        run1/fill_legs.jsonl   run1/capture_meta.json   run1/DONE (+ standard
        checkpoint/progress/run.json artifacts of the reused harness)

Determinism: the dual-run harness is already PASS for the frozen window;
this single-pass capture consumes the same deterministic replay machinery, so
n_fills is expected to land on ≈443 (≈ placed 693 context). Material drift ⇒
STOP (composition mismatch), never tuning.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_SRC"))

OUT = ROOT / "06_RESEARCH" / "results" / "coupled_mtf_fill_leg_capture"
HEARTBEAT_FILE = OUT / "runner_heartbeat.json"
EXIT_REASON_FILE = OUT / "exit_reason.json"
ALERT_OK = OUT / "ALERT_CAPTURE_DONE.txt"
ALERT_FAIL = OUT / "ALERT_CAPTURE_FAILED.txt"

BANNER = "DIAGNOSTIC ONLY - NOT PERFORMANCE / NOT EDGE"

# ------------------------------------------------------------------ #
# heartbeat (alive-ness only; bars live in run1/progress.log)
# ------------------------------------------------------------------ #
def heartbeat_thread() -> None:
    def loop() -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        while True:
            payload = {
                "pid": os.getpid(),
                "run_name": "capture_run1",
                "alive": True,
                "note": BANNER,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            tmp = HEARTBEAT_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
            os.replace(tmp, HEARTBEAT_FILE)
            time.sleep(15)

    t = threading.Thread(target=loop, daemon=True)
    t.start()


def _write_exit_reason(reason: str, code: int, exc: str | None = None) -> None:
    payload = {
        "pid": os.getpid(),
        "exit_reason": reason,
        "exit_code": code,
        "exception": exc,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        tmp = EXIT_REASON_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        os.replace(tmp, EXIT_REASON_FILE)
    except Exception:
        pass


def _alert(path: Path, lines: list[str]) -> None:
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


# ------------------------------------------------------------------ #
# capture state (single-threaded harness; module-global is safe)
# ------------------------------------------------------------------ #
CAPTURE: dict = {
    "legs_path": None,       # run1/fill_legs.jsonl (bytes-appending handle)
    "n_place": 0,
    "n_fills": 0,
    "n_exits": 0,
    "last_cancelled": None,  # {ticket, comment(route identity), entry, sl, tp}
    "exc": {},               # position ticket -> [mfe_price, mae_price]
    "meta_extra": {},
}


def _iso(v) -> str | None:
    if v is None:
        return None
    try:
        return getattr(v, "isoformat", lambda v=v: str(v))()
    except Exception:
        return str(v)


def _line(rec: dict) -> None:
    """Append one durable JSON leg line (flush + fsync at each event)."""
    fh: "object | None" = CAPTURE["leg_fh"]
    fh.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


# ------------------------------------------------------------------ #
# patched store classes (subclass the diagnostic harness's own classes)
# ------------------------------------------------------------------ #
def build_capture_classes(diag):
    """Return patched (Book, Positions) for module-level use in run_once."""
    from smc.core.enums import Direction  # noqa: PLC0415 — capture-only import

    class LegCaptureBook(diag.CountingBook):
        """place(): route identity from ``comment`` (= candidate.route_id);
        cancel(): stash the just-cancelled order so the FILL that
        immediately follows the cancel in ``_apply_fills`` can join the
        route identity + placement geometry (production order flow:
        limit-check → cancel(ticket) → positions.open(...))."""

        def place(self, **kwargs):
            order = super().place(**kwargs)
            CAPTURE["n_place"] += 1
            _line({
                "leg_id": f"ord-{order.ticket}",
                "event": "placed",
                "bar_index": kwargs.get("placed_bar"),
                "time_utc": _iso(kwargs.get("placed_at")),
                "ticket": order.ticket,
                "route_id": kwargs.get("comment") or None,
                "direction": getattr(kwargs.get("direction"), "name", None),
                "volume": kwargs.get("volume"),
                "entry_price": kwargs.get("entry_price"),
                "sl_price": kwargs.get("sl"),
                "tp_price": kwargs.get("tp"),
                "sl_original": kwargs.get("original_sl"),
                "zone_low": kwargs.get("zone_low"),
                "zone_high": kwargs.get("zone_high"),
                "poi_id": kwargs.get("poi_id"),
                "pillar_path": kwargs.get("pillar_path"),
            })
            return order

        def cancel(self, ticket):
            order = super().cancel(ticket)
            if order is not None:
                CAPTURE["last_cancelled"] = {
                    "ticket": order.ticket,
                    "route_id": (order.comment or None),
                    "entry_price": order.entry_price,
                    "sl": order.sl,
                    "tp": order.tp,
                    "rest_bars": order.rest_bars,
                }
            return order

    class LegCapturePositions(diag.CountingPositions):
        """open(): one FILL leg. _close(): one EXIT leg (single choke point
        for both bar-driven SL/TP closes and runner-driven risk closes).
        apply_bar(): per-bar max favorable / adverse excursion update for
        still-open positions (MFE/MAE ride onto the EXIT leg)."""

        # -- excursion bookkeeping --------------------------------------
        def _note(self, position: object, high: float, low: float) -> None:
            entry = position.entry_price
            mfe, mae = CAPTURE["exc"].get(position.ticket, [entry, entry])
            if position.direction is Direction.LONG:
                # favorable extreme = highest price; adverse = lowest
                mfe, mae = max(mfe, high), min(mae, low)
            else:
                # SHORT: favorable extreme = lowest price; adverse = highest
                mfe, mae = min(mfe, low), max(mae, high)
            CAPTURE["exc"][position.ticket] = [mfe, mae]

        def apply_bar(self, bar, bar_index, *, exit_spread_price=None):
            for position in list(self._open):
                self._note(position, bar.high, bar.low)
            return super().apply_bar(
                bar, bar_index, exit_spread_price=exit_spread_price
            )

        # -- fill --------------------------------------------------------
        def open(self, **kwargs):
            cancelled = CAPTURE["last_cancelled"] or {}
            CAPTURE["last_cancelled"] = None
            position = super().open(**kwargs)
            CAPTURE["n_fills"] += 1
            payload = {}
            try:
                payload = json.loads(kwargs.get("signal_data_json") or "{}")
            except (TypeError, ValueError):
                payload = {}
            cmf = payload.get("coupled_mtf", {})
            entry_price = kwargs.get("entry_price")
            CAPTURE["exc"][position.ticket] = [entry_price, entry_price]
            _line({
                "leg_id": f"fill-{position.ticket}",
                "event": "fill",
                "ticket": position.ticket,
                "bar_index": kwargs.get("entry_bar"),
                "time_utc": _iso(kwargs.get("entry_at")),
                "direction": getattr(kwargs.get("direction"), "name", None),
                "volume": kwargs.get("volume"),
                "entry_price": kwargs.get("entry_price"),
                "sl_price": kwargs.get("sl"),
                "tp_price": kwargs.get("tp"),
                "sl_original": kwargs.get("original_sl"),
                "zone_low": kwargs.get("zone_low"),
                "zone_high": kwargs.get("zone_high"),
                "poi_id": kwargs.get("poi_id"),
                "pillar_path": kwargs.get("pillar_path"),
                "entry_anchor": kwargs.get("entry_anchor"),
                "tp_source": kwargs.get("tp_source"),
                "route_id": cancelled.get("route_id"),
                "placed_entry_price": cancelled.get("entry_price"),
                "placed_sl": cancelled.get("sl"),
                "placed_tp": cancelled.get("tp"),
                "detection_tier": cmf.get("source_tf"),
                "trigger": cmf.get("trigger"),
                "confirm_tf": cmf.get("confirm_tf"),
                "sweep_close_ts": _iso(cmf.get("sweep_close_ts")),
                "trigger_signal_data": payload.get("trigger_signal_data"),
            })
            return position

        # -- exit (single choke point) ------------------------------------
        def _close(self, position, decision, bar, exit_bar, exit_at=None, *,
                   exit_spread_price=None):
            # Fold the decisive exit price into the excursion window first:
            # SL/TP hits inside the closing bar must count in MFE/MAE.
            self._note(position, max(decision.price, position.entry_price),
                       min(decision.price, position.entry_price))
            closed = super()._close(
                position, decision, bar, exit_bar, exit_at=exit_at,
                exit_spread_price=exit_spread_price,
            )
            CAPTURE["n_exits"] += 1
            mfe, mae = CAPTURE["exc"].pop(closed.position.ticket, [None, None])
            _line({
                "leg_id": f"exit-{closed.position.ticket}",
                "event": "exit",
                "ticket": closed.position.ticket,
                "bar_index": closed.exit_bar,
                "time_utc": _iso(closed.exit_at),
                "direction": getattr(closed.position.direction, "name", None),
                "entry_price": closed.position.entry_price,
                "sl_price": closed.position.sl,
                "sl_original": closed.position.original_sl,
                "tp_price": closed.position.tp,
                "exit_price": closed.exit_price,
                # normalize enum → persisted value (take_profit/stop_loss);
                # close_kind_repr keeps the verbatim Python repr for audit.
                "close_kind": getattr(closed.kind, "value", closed.kind),
                "close_kind_repr": str(closed.kind),
                "win": closed.win,
                "pnl_raw": closed.realized_pnl,
                "cost_usd": closed.cost_usd,
                "cost_ledger": closed.cost_ledger,
                "hold_bars": closed.bars_held,
                "mfe_price": mfe,
                "mae_price": mae,
                "zone_low": closed.position.zone_low,
                "zone_high": closed.position.zone_high,
                "pillar_path": closed.position.pillar_path,
                "poi_id": closed.position.poi_id,
            })
            return closed

    return LegCaptureBook, LegCapturePositions


def run_capture(run_name: str = "run1", *, stop_after_bars: int | None = None) -> dict:
    """One instrumented pass over the frozen window (fresh in the new tree).

    ``stop_after_bars`` = harness self-test short pass (simulated crash; the
    tree stays deliberately unfinished, DONE never written). Smoke-only.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    legs_path = OUT / run_name / "fill_legs.jsonl"
    (OUT / run_name).mkdir(parents=True, exist_ok=True)
    CAPTURE["legs_path"] = legs_path
    CAPTURE["leg_fh"] = legs_path.open("a", encoding="utf-8")

    spec = importlib.util.spec_from_file_location(
        "coupled_mtf_full_menu_diagnostic_cfg",
        ROOT / "06_RESEARCH" / "scripts" / "coupled_mtf_full_menu_diagnostic.py",
    )
    diag = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = diag
    spec.loader.exec_module(diag)

    # Patch only LOGGING SEAMS — window/composition/strategy untouched:
    diag._run_dir = lambda run: OUT / run  # NEW out dir; DONE trees untouched

    book_cls, pos_cls = build_capture_classes(diag)
    diag.CountingBook = book_cls
    diag.CountingPositions = pos_cls

    started = time.perf_counter()
    summary = diag.run_once(
        run_name, stop_after_bars=stop_after_bars
    )  # fresh: no DONE, no checkpoint here (smoke passes end mid-window by design)
    elapsed = time.perf_counter() - started
    smoke = summary is None and stop_after_bars is not None
    if summary is None and not smoke:
        raise RuntimeError("run_once returned None (refused or unexpected stop)")
    if smoke:
        # Wind-up only: keep meta honest; nothing finalizes in a smoke pass.
        meta = {
            "banner": BANNER,
            "capture": "SMOKE short pass (stop_after_bars; simulated crash; "
                       "seam verification only)",
            "run_id": run_name,
            "smoke": True,
            "stop_after_bars": stop_after_bars,
            "n_placed_counter": CAPTURE["n_place"],
            "n_fills_counter": CAPTURE["n_fills"],
            "n_exits_written": CAPTURE["n_exits"],
            "fill_legs_path": str(legs_path),
            "runtime_seconds": round(elapsed, 3),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = OUT / run_name / "capture_meta_smoke.json"
        tmp = meta_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(meta, indent=1), encoding="utf-8")
        os.replace(tmp, meta_path)
        return meta

    meta = {
        "banner": BANNER,
        "capture": "single-pass instrumented fill-leg capture (logging only)",
        "run_id": run_name,
        "out_dir": str(OUT / run_name),
        "git_sha": summary.get("git_sha") or diag._git_sha(),
        "window": summary.get("window"),
        "execution_bars_total": (summary.get("run_completion") or {}).get(
            "execution_bars_total_frozen"),
        "execution_bars_processed": (summary.get("run_completion") or {}).get(
            "execution_bars_processed"),
        "n_placed_counter": CAPTURE["n_place"],
        "n_fills_counter": CAPTURE["n_fills"],
        "n_exits_written": CAPTURE["n_exits"],
        "n_legs_written": CAPTURE["n_place"] + CAPTURE["n_fills"] + CAPTURE["n_exits"],
        "expected_context": {
            "reference_dual_run": "coupled_mtf_full_menu_diag",
            "reference_fills": 443,
            "reference_placed": 693,
            "drift_rule": "STOP on material drift (composition mismatch) — no tuning",
        },
        "fill_legs_path": str(legs_path),
        "runtime_seconds": round(elapsed, 3),
        "strategy_changed": False,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = OUT / run_name / "capture_meta.json"
    tmp = meta_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    os.replace(tmp, meta_path)
    return meta


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="run1")
    parser.add_argument("--smoke", type=int, default=None, metavar="N_BARS",
                        help="short harness self-test pass (simulated crash; "
                        "never finalizes; bypasses alert/exit bookkeeping)")
    args = parser.parse_args()
    heartbeat_thread()
    try:
        meta = run_capture(args.run, stop_after_bars=args.smoke)
        if meta.get("smoke"):
            print(f"[{BANNER}] SMOKE PASS: placed={meta['n_placed_counter']} "
                  f"fills={meta['n_fills_counter']} exits="
                  f"{meta['n_exits_written']} (seam verification)")
            return 0
        _alert(ALERT_OK, [
            "COUPLED FULL-MENU FILL-LEG CAPTURE - DONE",
            f"fills_counter={meta['n_fills_counter']} "
            f"(reference 443) exits={meta['n_exits_written']} "
            f"runtime={meta['runtime_seconds']}s",
            "fill_legs=" + meta["fill_legs_path"],
        ])
        _write_exit_reason("CAPTURE_DONE_PASS", 0)
        print(f"[{BANNER}] CAPTURE PASS: {meta['n_fills_counter']} fills, "
              f"{meta['n_exits_written']} exits", flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001 — capture must ALWAYS report exit
        err = traceback.format_exc()
        _alert(ALERT_FAIL, [
            "COUPLED FULL-MENU FILL-LEG CAPTURE - FAILED",
            repr(exc)[:300],
            "See exit_reason.json + logs; existing DONE trees untouched.",
            str(err)[-800:],
        ])
        _write_exit_reason("CAPTURE_FAILED", 1, err[-2000:])
        print(f"[{BANNER}] CAPTURE FAILED", file=sys.stderr, flush=True)
        traceback.print_exc()
        return 1
    finally:
        try:
            fh = CAPTURE.get("leg_fh")
            if fh is not None and not fh.closed:
                fh.flush()
                os.fsync(fh.fileno())
                fh.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
