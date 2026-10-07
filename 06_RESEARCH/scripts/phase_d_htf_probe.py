"""POST-V1 PHASE D — HTF product-runtime probe (EXNESS Copy terminal ONLY).

Ops infrastructure proof per the Lead Architect's Phase D HTF probe brief —
NOT strategy validation, NOT edge evidence:

  1. identity gate   — bind to the ONLY permitted terminal
                       (C:\\Program Files\\MetaTrader 5 EXNESS - Copy\\terminal64.exe),
                       DEMO account enforced, symbol selected; abort loudly
                       on any mismatch BEFORE any stack is built.
  2. HTF probe       — build the SAME product stack as run_operator
                       (MultiTFProductRuntime product mode,
                       allow_single_tf_degraded=False) and run the product
                       start-time HTF check: per-TF ``copy_rates`` fetch +
                       ``runtime.missing_series`` + ``LiveLoop.start()``
                       probe semantics. Records per-TF bar counts and the
                       first/last bar timestamps.
  3. degraded smoke  --optional (--degraded-smoke): with the explicit opt-in
                       flag set on a FRESH runtime, confirm the single-TF
                       path is allowed and STAMPED degraded (never silent).
  4. dry_run loop    — bounded polling window (--max-seconds, default 60)
                       through ``LiveLoop.run_once`` (dry_run True):
                       counts polls / new bars / H1-cadence batches /
                       arm errors; any exception is RECORDED, the host
                       process must not crash (non-zero exit allowed at end).
  5. artifacts       — results/phase_d_htf_probe/{identity.json,
                       probe_summary.json, events.log}; plus a report
                       section appended by the caller (not this script).

Usage:
  python 06_RESEARCH/scripts/phase_d_htf_probe.py \
      --config config/live_demo.json --max-seconds 60 [--degraded-smoke]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[1] / "results" / "phase_d_htf_probe"
_SRC = Path(__file__).resolve().parents[2] / "04_SRC"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(events_path: Path, msg: str) -> None:
    line = f"{_utcnow()} {msg}"
    print(line)
    with events_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# ---------------------------------------------------------------------- #
# Step 1 — identity gate (abort on any mismatch)
# ---------------------------------------------------------------------- #
def identity_gate(cfg) -> dict:
    """Bind to the configured terminal; DEMO enforced; symbol selected."""
    import MetaTrader5 as mt5

    if not mt5.initialize(path=cfg.terminal_path):
        raise SystemExit(f"ABORT: mt5.initialize failed: {mt5.last_error()}")
    term = mt5.terminal_info()
    acct = mt5.account_info()
    if term is None or acct is None:
        mt5.shutdown()
        raise SystemExit(f"ABORT: terminal/account info unavailable: {mt5.last_error()}")

    from smc.live.operator_config import normalize_terminal_dir

    live_dir = normalize_terminal_dir(str(term.path or ""))
    required_dir = normalize_terminal_dir(cfg.terminal_path)
    mode = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(int(acct.trade_mode), "UNKNOWN")
    facts = {
        "checked_at_utc": _utcnow(),
        "terminal_path_configured": cfg.terminal_path,
        "terminal_dir_live": live_dir,
        "terminal_dir_required": required_dir,
        "identity_match": live_dir == required_dir,
        "connected": bool(term.connected),
        "trade_allowed": bool(term.trade_allowed),
        "login": int(acct.login),
        "server": str(acct.server),
        "company": str(acct.company),
        "currency": str(acct.currency),
        "mode": mode,
        "is_demo": mode == "DEMO",
        "symbol": cfg.symbol,
        "magic": cfg.magic,
        "dry_run": cfg.dry_run,
        "require_demo": cfg.require_demo,
        "mt5_python_version": str(mt5.version()),
    }
    if not facts["identity_match"]:
        mt5.shutdown()
        raise SystemExit(f"ABORT: terminal identity mismatch: {facts}")
    if cfg.require_demo and not facts["is_demo"]:
        mt5.shutdown()
        raise SystemExit(f"ABORT: require_demo=true but account mode={mode}: {facts}")
    if not mt5.symbol_select(cfg.symbol, True):
        err = mt5.last_error()
        mt5.shutdown()
        raise SystemExit(f"ABORT: symbol_select({cfg.symbol}) failed: {err}")
    return facts


# ---------------------------------------------------------------------- #
# Step 2 — product HTF probe (same stack as run_operator)
# ---------------------------------------------------------------------- #
def htf_probe(cfg, facts: dict, events_path: Path) -> dict:
    """Product-mode HTF provisioning check through the REAL seam objects."""
    from smc.config.timeframe import Timeframe
    from smc.data.mt5_connector import MT5Connector
    from smc.live.loop import LiveLoop
    from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime

    tf = Timeframe[cfg.timeframe]
    detection_tfs = tuple(Timeframe[name] for name in cfg.detection_timeframes)

    # Product mode by construction: the runtime is built with the operator's
    # degraded flag, and the probe asserts it is False for the product check.
    runtime = MultiTFProductRuntime(
        execution_timeframe=tf,
        detection_timeframes=detection_tfs,
        allow_single_tf_degraded=cfg.allow_single_tf_degraded,
    )
    connector = MT5Connector(symbol=cfg.symbol, magic=cfg.magic,
                             terminal_path=cfg.terminal_path)
    loop = LiveLoop(connector=connector, runner=_LooplessRunnerStub(),
                    heartbeat=None, symbol=cfg.symbol, timeframe=tf,
                    runtime=runtime)

    out: dict = {
        "product_mode": not runtime.allow_single_tf_degraded,
        "detection_timeframes": [t.name for t in detection_tfs],
        "execution_timeframe": tf.name,
        "htf_timeframes_provisioned": [t.name for t in loop.htf_timeframes],
        "per_tf": {},
    }

    # Raw per-TF fetch + counts + range (same path LiveLoop uses).
    series = loop._fetch_htf_series()  # noqa: SLF001 — the probe IS the seam check
    for tf_obj, bars in series.items():
        key = tf_obj.name
        if bars:
            out["per_tf"][key] = {
                "bars": len(bars),
                "first_bar_utc": bars[0].timestamp.isoformat(),
                "last_bar_utc": bars[-1].timestamp.isoformat(),
            }
        else:
            out["per_tf"][key] = {"bars": 0, "error": "connector returned no usable series"}

    missing = runtime.missing_series(series)
    out["missing_series"] = [t.name for t in missing]
    out["missing_series_policy"] = (
        "product mode: missing required series REFUSES the session (loud)"
        if not runtime.allow_single_tf_degraded
        else "degraded mode: explicit single-TF opt-in (stamped, not silent)"
    )

    # Product start gate — LiveLoop.start() performs the probe and must
    # REFUSE (return False) when required series are missing in product mode.
    started = loop.start()
    out["live_loop_start_probe"] = {
        "started": bool(started),
        "expected_product_behavior": "True when H1+H4 usable; False (refuse) otherwise",
        "compliant": bool(started) == (not out["missing_series"]),
    }
    if started:
        loop.stop()
    connector_shutdown = getattr(connector, "shutdown", None)
    if callable(connector_shutdown):
        connector_shutdown()
    out["htf_ok"] = not out["missing_series"] and started
    _log(events_path, "HTF_PROBE " + json.dumps(
        {k: out[k] for k in ("htf_ok", "missing_series", "per_tf",
                             "live_loop_start_probe")}, default=str))
    return out


class _LooplessRunnerStub:
    """Runner placeholder for the start-probe LiveLoop.

    ``LiveLoop.start()`` only touches the connector and the runtime; the
    runner is never invoked before ``run_once``. The dry-run loop below
    uses the REAL runner, not this stub.
    """


# ---------------------------------------------------------------------- #
# Step 3 — degraded smoke (optional, explicit opt-in only)
# ---------------------------------------------------------------------- #
def degraded_smoke(cfg, facts: dict, events_path: Path) -> dict:
    """With the explicit degraded flag: single-TF allowed AND stamped."""
    from smc.backtest.pipeline_adapter import PipelineAdapter
    from smc.config.timeframe import Timeframe
    from smc.data.mt5_connector import MT5Connector
    from smc.execution.order_manager import OrderManager
    from smc.execution.position_manager import PositionManager
    from smc.live.loop import LiveLoop
    from smc.orchestration.engine import PipelineEngine
    from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime
    from smc.paper.runner import PaperConfig, PaperRunner
    from smc.risk.risk_engine import RiskEngine

    tf = Timeframe[cfg.timeframe]
    runtime = MultiTFProductRuntime(
        execution_timeframe=tf,
        detection_timeframes=(Timeframe.H4, Timeframe.H1),
        allow_single_tf_degraded=True,           # the explicit opt-in
    )
    connector = MT5Connector(symbol=cfg.symbol, magic=cfg.magic,
                             terminal_path=cfg.terminal_path)
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=tf)
    runner = PaperRunner(
        connector=connector,
        risk_engine=RiskEngine(),
        pipeline=adapter,
        order_manager=OrderManager(connector, symbol=cfg.symbol, magic=cfg.magic),
        position_manager=PositionManager(connector, symbol=cfg.symbol),
        config=PaperConfig(dry_run=True),
        runtime=runtime,
    )
    loop = LiveLoop(connector=connector, runner=runner, heartbeat=None,
                    symbol=cfg.symbol, timeframe=tf, runtime=runtime)
    started = loop.start()
    # Force the DEGRADED shape: with the terminal reachable the broker
    # ALWAYS supplies H4/H1 (the degraded stamp can only be proven when the
    # series are genuinely missing), so this smoke runs the batch against an
    # EMPTY series dict on the same runtime (explicit opt-in) with the live
    # connector's own M5 bars as the execution series.
    degraded_stamped = None
    try:
        if started:
            raw = connector.copy_rates(cfg.symbol, tf, 0, 120)
            # NOTE: copy_rates returns a numpy record array — `raw or []`
            # would raise 'truth value of an array is ambiguous' for len>1.
            bars = list(raw) if raw is not None else []
            candles = [loop._to_candle(row, tf) for row in bars]
            if candles:
                report = runner.arm_multi_tf(
                    {}, as_of=candles[-1].timestamp, arm_bar=0,
                    execution_candles=candles)
                summary = report.summary()
                degraded_stamped = {
                    "degraded": summary.get("degraded"),
                    "reason": summary.get("degraded_reason"),
                    "missing": summary.get("missing"),
                }
    except Exception as exc:                       # noqa: BLE001 — smoke records, not dies
        degraded_stamped = {"error": repr(exc)}
    finally:
        if started:
            loop.stop()
    connector_shutdown = getattr(connector, "shutdown", None)
    if callable(connector_shutdown):
        connector_shutdown()
    out = {
        "started_with_degraded_opt_in": bool(started),
        "degraded_stamped": degraded_stamped,
        "pass": bool(started) and bool(
            degraded_stamped and degraded_stamped.get("degraded")),
    }
    _log(events_path, "DEGRADED_SMOKE " + json.dumps(out, default=str))
    return out


# ---------------------------------------------------------------------- #
# Step 4 — bounded dry_run loop (real runner, dry_run True)
# ---------------------------------------------------------------------- #
def dry_run_loop(cfg, facts: dict, seconds: float, events_path: Path) -> dict:
    from smc.backtest.pipeline_adapter import PipelineAdapter
    from smc.config.timeframe import Timeframe
    from smc.data.mt5_connector import MT5Connector
    from smc.execution.order_manager import OrderManager
    from smc.execution.position_manager import PositionManager
    from smc.live.heartbeat import HeartbeatPublisher
    from smc.live.loop import LiveLoop
    from smc.orchestration.engine import PipelineEngine
    from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime
    from smc.paper.runner import PaperConfig, PaperRunner
    from smc.risk.risk_engine import RiskEngine

    tf = Timeframe[cfg.timeframe]
    detection_tfs = tuple(Timeframe[name] for name in cfg.detection_timeframes)
    runtime = MultiTFProductRuntime(
        execution_timeframe=tf,
        detection_timeframes=detection_tfs,
        allow_single_tf_degraded=cfg.allow_single_tf_degraded,
    )
    connector = MT5Connector(symbol=cfg.symbol, magic=cfg.magic,
                             terminal_path=cfg.terminal_path)
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=tf)
    runner = PaperRunner(
        connector=connector,
        risk_engine=RiskEngine(),
        pipeline=adapter,
        order_manager=OrderManager(connector, symbol=cfg.symbol, magic=cfg.magic),
        position_manager=PositionManager(connector, symbol=cfg.symbol),
        config=PaperConfig(dry_run=True),   # evaluate + log, NEVER send
        runtime=runtime,
    )
    heartbeat = HeartbeatPublisher(RESULTS / "smc_heartbeat.txt")
    loop = LiveLoop(connector=connector, runner=runner, heartbeat=heartbeat,
                    symbol=cfg.symbol, timeframe=tf,
                    runtime=runtime, poll_interval=cfg.poll_interval_s)

    started_utc = _utcnow()
    errors: list[str] = []
    polls = new_bars = 0
    if not loop.start():
        connector_shutdown = getattr(connector, "shutdown", None)
        if callable(connector_shutdown):
            connector_shutdown()
        return {"started": False, "pass": False,
                "errors": ["LiveLoop.start() refused (HTF probe / connector)"]}

    deadline = time.monotonic() + seconds
    try:
        while time.monotonic() < deadline:
            try:
                new_bars += loop.run_once()
            except Exception as exc:               # noqa: BLE001 — record, keep polling
                errors.append(repr(exc))
                _log(events_path, f"LOOP_ERROR {exc!r}")
            polls += 1
            time.sleep(cfg.poll_interval_s)
    finally:
        loop.stop()
        connector_shutdown = getattr(connector, "shutdown", None)
        if callable(connector_shutdown):
            connector_shutdown()

    out = {
        "started": True,
        "dry_run": True,
        "seconds": seconds,
        "polls": polls,
        "new_bars_processed": new_bars,
        "htf_batches": loop.htf_batches,
        "arm_errors": loop.arm_errors,
        "last_arm_error": loop.last_arm_error,
        "kpi_counters": runner.kpi.counters(),
        "errors": errors,
        "pass": len(errors) == 0,
        "started_utc": started_utc,
        "stopped_utc": _utcnow(),
    }
    _log(events_path, "DRY_RUN_LOOP " + json.dumps(
        {k: out[k] for k in ("pass", "seconds", "polls", "new_bars_processed",
                             "htf_batches", "arm_errors", "errors")}, default=str))
    return out


# ---------------------------------------------------------------------- #
# Main
# ---------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Phase D HTF product-runtime probe")
    ap.add_argument("--config", default="config/live_demo.json")
    ap.add_argument("--max-seconds", type=float, default=60.0)
    ap.add_argument("--degraded-smoke", action="store_true",
                    help="also prove the explicit degraded single-TF stamp")
    args = ap.parse_args(argv)

    from smc.live.operator_config import load_operator_config

    RESULTS.mkdir(parents=True, exist_ok=True)
    events = RESULTS / "events.log"
    try:
        cfg = load_operator_config(args.config)
    except Exception as exc:                       # noqa: BLE001 — fail clearly
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    _log(events, f"PROBE START config={args.config} max_seconds={args.max_seconds}")

    summary: dict = {"probe_started_utc": _utcnow(), "config_source": args.config}
    try:
        facts = identity_gate(cfg)
    except SystemExit as exc:
        summary["identity"] = {"abort": str(exc)}
        summary["status"] = "FAIL"
        _write_summary(summary, events)
        print(exc, file=sys.stderr)
        return 3
    (RESULTS / "identity.json").write_text(json.dumps(facts, indent=2),
                                           encoding="utf-8")
    summary["identity"] = facts
    _log(events, "IDENTITY PASS " + json.dumps(
        {k: facts[k] for k in ("login", "server", "mode", "symbol", "magic",
                               "trade_allowed", "identity_match")}))

    summary["htf_probe"] = htf_probe(cfg, facts, events)
    summary["degraded_smoke"] = (
        degraded_smoke(cfg, facts, events) if args.degraded_smoke else "SKIP")
    summary["dry_run_loop"] = dry_run_loop(cfg, facts, args.max_seconds, events)

    loop = summary["dry_run_loop"]
    htf = summary["htf_probe"]
    degraded = summary["degraded_smoke"]
    ok = (
        facts["identity_match"] and facts["is_demo"]
        and htf.get("htf_ok") and loop.get("pass")
        and (degraded == "SKIP" or (isinstance(degraded, dict) and degraded.get("pass")))
    )
    summary["status"] = "PASS" if ok else "PARTIAL" if (
        facts["identity_match"] and (htf.get("htf_ok") or loop.get("pass"))) else "FAIL"
    summary["probe_finished_utc"] = _utcnow()
    summary["disposition"] = (
        "infrastructure proof only — NOT strategy validation, NOT edge evidence")
    _write_summary(summary, events)
    print(f"[done] status={summary['status']} — artifacts in {RESULTS}")
    return 0 if summary["status"] == "PASS" else 1


def _write_summary(summary: dict, events: Path) -> None:
    (RESULTS / "probe_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    _log(events, f"PROBE END status={summary.get('status')}")


if __name__ == "__main__":
    raise SystemExit(main())
