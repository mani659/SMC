"""Phase D operator pack — live operator entrypoint (demo/paper run surface).

Responsibilities (Lead Architect instruction, Phase D operator pack):

    load config → validate against locked bounds → initialize connector with
    terminal_path → prove terminal/account identity BEFORE the loop → start
    heartbeat → run the live loop → publish console status → write backend logs.

Ops tooling ONLY: the strategy stack is composed exactly as the Phase 7
tests wire it (PipelineEngine → PipelineAdapter → PaperRunner + RiskEngine
+ OrderManager/PositionManager, driven by LiveLoop). No strategy logic
lives here; no locked constant is readable, let alone overridable, from
the operator config (enforced in :mod:`smc.live.operator_config`).

Safety behavior:
    * abort on terminal-path family mismatch (normalized dir comparison);
    * abort when ``require_demo`` and the account is not DEMO;
    * default ``dry_run=true`` (evaluate + log, never send orders);
    * dedicated magic only (single terminal, single symbol per session);
    * Ctrl+C → clean stop → heartbeat ``shutdown`` marker (existing design).

Usage:
    python 04_SRC/smc/live/run_operator.py --config config/live_demo.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow ``python 04_SRC/smc/live/run_operator.py`` from the repo root.
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from smc.live.operator_config import (                      # noqa: E402
    OperatorConfig,
    normalize_terminal_dir,
    REQUIRED_TERMINAL_PATH,
    load_operator_config,
)
from smc.live.operator_console import (                      # noqa: E402
    render_startup_banner,
    render_status_board,
)
from smc.live.structure_console import (                     # noqa: E402
    build_structure_snapshot,
    render_structure_console,
)

__all__ = ["OperatorSession", "main"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OperatorSession:
    """One operator-controlled demo/paper session (single terminal)."""

    def __init__(self, config: OperatorConfig) -> None:
        self.config = config
        self.log_dir = Path(config.log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._logger = self._make_logger()
        self._mt5 = None                 # bound lazily in identity_check()
        self._identity: dict | None = None
        self._loop = None
        self._runner = None
        self._adapter = None
        self._heartbeat = None
        self._armed_total = 0            # C1: cumulative newly-armed POIs
        # Live board state (mutated by the poll hook, read by the renderer).
        self.state: dict = {
            "session_started_utc": None,
            "terminal_dir": None,
            "server": None,
            "account": None,
            "is_demo": None,
            "symbol": config.symbol,
            "magic": config.magic,
            "dry_run": config.dry_run,
            "bars_processed": 0,
            "polls": 0,
            "last_bar_utc": None,
            "spread": None,
            "atr": None,
            "gate_pass": None,
            "gate_detail": None,
            "open_positions": None,
            "errors": [],
            # C1 multi-TF status (filled by the poll hook; n/a until then).
            "htf_batches": 0,
            "htf_armed": 0,
            "arm_errors": 0,
            "htf_last": None,
            # L1 structure console (read-only snapshot; n/a until the
            # first structure refresh — never a hardcoded demo board).
            "structure": None,
        }
        # L1: rate-limit anchor for structure snapshot rebuilds.
        self._last_structure_mono = 0.0

    # ------------------------------------------------------------------ #
    # Backend logging (append-only, gitignored)
    # ------------------------------------------------------------------ #
    def _make_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"smc.operator.{id(self)}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not logger.handlers:
            fh = logging.FileHandler(self.log_dir / "events.log", encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)sZ %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
            ))
            logger.addHandler(fh)
        return logger

    def _log(self, msg: str) -> None:
        self._logger.info(msg)

    # ------------------------------------------------------------------ #
    # Identity gate (before anything else)
    # ------------------------------------------------------------------ #
    def identity_check(self) -> dict:
        """Bind to the configured terminal and prove identity; abort on mismatch."""
        import MetaTrader5 as mt5

        cfg = self.config
        if not mt5.initialize(path=cfg.terminal_path):
            raise SystemExit(
                f"ABORT: mt5.initialize(path={cfg.terminal_path!r}) failed: {mt5.last_error()}"
            )
        term = mt5.terminal_info()
        acct = mt5.account_info()
        if term is None or acct is None:
            raise SystemExit(f"ABORT: terminal/account info unavailable: {mt5.last_error()}")

        live_dir = normalize_terminal_dir(str(term.path or ""))
        required_dir = normalize_terminal_dir(cfg.terminal_path)
        mode = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(int(acct.trade_mode), "UNKNOWN")
        is_demo = mode == "DEMO"

        facts = {
            "checked_at_utc": _utcnow().isoformat(),
            "terminal_dir_configured": required_dir,
            "terminal_dir_live": live_dir,
            "connected": bool(term.connected),
            "trade_allowed": bool(term.trade_allowed),
            "login": int(acct.login),
            "server": str(acct.server),
            "company": str(acct.company),
            "currency": str(acct.currency),
            "leverage": int(acct.leverage),
            "mode": mode,
            "symbol": cfg.symbol,
            "magic": cfg.magic,
            "dry_run": cfg.dry_run,
            "require_demo": cfg.require_demo,
            "mt5_python_version": str(mt5.version()),
        }
        if live_dir != required_dir:
            self._mt5 = mt5
            self._log(f"IDENTITY MISMATCH: {facts}")
            raise SystemExit(
                f"ABORT: connected terminal dir {live_dir!r} != required {required_dir!r}"
            )
        if cfg.require_demo and not is_demo:
            raise SystemExit(
                f"ABORT: require_demo=true but account trade_mode={mode}"
            )
        if not mt5.symbol_select(cfg.symbol, True):
            raise SystemExit(
                f"ABORT: symbol_select({cfg.symbol}) failed: {mt5.last_error()}"
            )
        self._mt5 = mt5
        self._identity = facts
        self.state["terminal_dir"] = live_dir
        self.state["server"] = facts["server"]
        self.state["account"] = facts["login"]
        self.state["is_demo"] = is_demo
        (self.log_dir / "identity.json").write_text(
            json.dumps(facts, indent=2), encoding="utf-8"
        )
        self._log("IDENTITY OK: " + json.dumps(facts))
        # Console gets the one-line human summary; the full facts live in
        # identity.json + events.log (no need to scroll a JSON blob).
        print(
            f"[identity] PASS — {mode} {facts['login']} @ {facts['server']} | "
            f"{cfg.symbol} magic {cfg.magic} | dry_run={cfg.dry_run} | "
            f"trade_allowed={facts['trade_allowed']}"
        )
        return facts

    # ------------------------------------------------------------------ #
    # Stack wiring (exactly the Phase 7 test composition)
    # ------------------------------------------------------------------ #
    def _build_stack(self):
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
        from smc.utils.timestamps import Session

        cfg = self.config
        tf = Timeframe[cfg.timeframe]
        # C1: ONE product multi-TF runtime for this session (contract §2) —
        # the same seam the paper runner and research scripts call. Product
        # mode by default: missing HTF aborts the session loudly instead of
        # silently degrading to single-TF detection.
        detection_tfs = tuple(Timeframe[name] for name in cfg.detection_timeframes)
        runtime = MultiTFProductRuntime(
            execution_timeframe=tf,
            detection_timeframes=detection_tfs,
            allow_single_tf_degraded=cfg.allow_single_tf_degraded,
        )
        connector = MT5Connector(symbol=cfg.symbol, magic=cfg.magic,
                                 terminal_path=cfg.terminal_path)
        sessions = None
        if cfg.allowed_sessions:
            sessions = [Session[name] for name in cfg.allowed_sessions]
        engine = PipelineEngine()
        adapter = PipelineAdapter(engine, timeframe=tf)
        runner = PaperRunner(
            connector=connector,
            risk_engine=RiskEngine(),
            pipeline=adapter,
            order_manager=OrderManager(connector, symbol=cfg.symbol, magic=cfg.magic),
            position_manager=PositionManager(connector, symbol=cfg.symbol),
            config=PaperConfig(
                risk_fraction=cfg.risk_fraction,
                dry_run=cfg.dry_run,
                allowed_sessions=sessions,
            ),
            runtime=runtime,
        )
        heartbeat = HeartbeatPublisher(
            Path(cfg.heartbeat_path), interval_seconds=cfg.heartbeat_interval_s
        )
        self._loop = LiveLoop(
            connector=connector, runner=runner, heartbeat=heartbeat,
            symbol=cfg.symbol, timeframe=tf,
            window_bars=200, poll_interval=cfg.poll_interval_s,
            runtime=runtime,
        )
        self._runner = runner
        self._adapter = adapter
        self._heartbeat = heartbeat
        return connector

    # ------------------------------------------------------------------ #
    # Poll hook — board state + KPI folding
    # ------------------------------------------------------------------ #
    def _on_poll(self, new_bars: int, connector) -> None:
        cfg = self.config
        self.state["polls"] = self.state["polls"] + 1
        self.state["bars_processed"] = self.state["bars_processed"] + new_bars

        # C1: multi-TF batch status (info-level at H1 cadence — no spam).
        loop = self._loop
        batch_changed = False
        if loop is not None:
            batches = getattr(loop, "htf_batches", 0)
            if batches != self.state.get("htf_batches"):
                batch_changed = True
                self.state["htf_batches"] = batches
                report = getattr(loop, "last_report", None)
                if report is not None:
                    self._armed_total += int(getattr(report, "armed_count", 0))
                    self.state["htf_armed"] = self._armed_total
                    self.state["htf_last"] = "  ".join(
                        f"{name} {c.get('detected_raw', 0)}/"
                        f"{c.get('merged', 0)}/{c.get('passed', 0)}"
                        for name, c in (report.summary().get("per_tf") or {}).items()
                    ) or None
                    self._log("MULTI_TF " + json.dumps(
                        report.summary(), default=str))
            self.state["arm_errors"] = getattr(loop, "arm_errors", None)

        # L1 structure console: refresh on a new execution bar and/or HTF
        # batch, rate-limited so the console stays readable.
        self._maybe_refresh_structure(new_bars, batch_changed)

        tick = self._mt5.symbol_info_tick(cfg.symbol)
        if tick is not None and tick.bid and tick.ask:
            self.state["spread"] = float(tick.ask) - float(tick.bid)

        candles = getattr(self._adapter, "_candles", None)
        if candles:
            try:
                atr = self._adapter.current_atr(len(candles) - 1)
                self.state["atr"] = atr if atr > 0 else None
                self.state["last_bar_utc"] = candles[-1].timestamp.isoformat()
            except Exception:                     # noqa: BLE001 — board must not die
                pass

        spread, atr = self.state["spread"], self.state["atr"]
        if spread is not None and atr:
            # §28.5 gate ceilings per grade (display only — the RiskEngine
            # enforces the real gate; this mirrors it for the operator).
            ceilings = {g: 0.15 * atr * m for g, m in
                        (("A+", 1.5), ("A", 1.0), ("B", 0.7), ("C", 0.5))}
            self.state["gate_pass"] = bool(spread <= ceilings["A+"])
            self.state["gate_detail"] = (
                f"ceil A+<={ceilings['A+']:.3f} A<={ceilings['A']:.3f} "
                f"B<={ceilings['B']:.3f} C<={ceilings['C']:.3f}"
            )

        try:
            positions = connector.positions_get(cfg.symbol)
            self.state["open_positions"] = len(positions) if positions else 0
        except Exception:                          # noqa: BLE001
            pass

    def _maybe_refresh_structure(self, new_bars: int, batch_changed: bool) -> None:
        """L1: rebuild the read-only structure snapshot.

        Refresh policy (mismatch fix 2026-10-06): a batch change (arming
        event) ALWAYS rebuilds immediately — an armed POI must be visible
        on the board without waiting out the console cadence (with a 900 s
        cadence the pre-fix behaviour could show ``armed 1`` on the status
        board while POIS stayed ``(none)`` for up to 15 min). New-bar
        refreshes stay rate-limited to ``console_refresh_s`` so the board
        stays readable. Pure observability: the snapshot only READS
        engine/adapter state and can never influence a trading decision;
        any failure is recorded, never fatal.
        """
        if batch_changed:
            self._last_structure_mono = time.monotonic()   # rebuild NOW + anchor
        elif not new_bars:
            return
        else:
            now_mono = time.monotonic()
            min_gap = max(1.0, float(self.config.console_refresh_s))
            if now_mono - self._last_structure_mono < min_gap:
                return
            self._last_structure_mono = now_mono
        adapter = self._adapter
        loop = self._loop
        if adapter is None or loop is None:
            return
        try:
            self.state["structure"] = build_structure_snapshot(
                engine=adapter.engine,
                adapter=adapter,
                sweeps=getattr(loop, "sweep_links", None),
                now=_utcnow(),
            )
        except Exception as exc:               # noqa: BLE001 — board must not die
            self.state["errors"].append(f"structure snapshot: {exc!r}")
            self._logger.error("structure snapshot failed: %r", exc)

    def _fold_flow_counters(self) -> None:
        """Fold the KPI decision/management records into board flow fields."""
        counters = {"candidates": 0, "blocked": 0, "placed": 0, "cancelled": 0, "rejects": 0}
        for rec in self._runner.kpi.records:
            f = rec.fields
            if rec.event == "decision":
                counters["candidates"] += int(f.get("candidates", 0))
                counters["blocked"] += int(f.get("blocked", 0))
                counters["placed"] += int(f.get("placed", 0))
                counters["rejected"] = counters.get("rejected", 0) + int(f.get("rejected", 0))
            elif rec.event == "management" and f.get("op") == "cancel" and f.get("success"):
                counters["cancelled"] += 1
        self.state["candidates"] = counters["candidates"]
        self.state["blocked"] = counters["blocked"]
        self.state["placed"] = counters["placed"]
        self.state["cancelled"] = counters["cancelled"]
        self.state["rejects"] = counters.get("rejected", 0)

    # ------------------------------------------------------------------ #
    # Main run loop
    # ------------------------------------------------------------------ #
    def run(self, max_seconds: float | None = None) -> None:
        """Identity → stack → poll loop with console cadence → clean stop.

        ``max_seconds`` bounds the session for controlled ops windows and
        smoke tests (graceful stop + artifacts); None runs until Ctrl+C.
        """
        import MetaTrader5 as mt5  # noqa: F401 — bound by identity_check()

        cfg = self.config
        self.identity_check()
        connector = self._build_stack()

        if not self._loop.start():
            raise SystemExit("ABORT: connector failed to initialize")
        self.state["session_started_utc"] = _utcnow().isoformat()
        self._log(
            "SESSION START "
            + json.dumps({"symbol": cfg.symbol, "magic": cfg.magic,
                          "dry_run": cfg.dry_run, "tf": cfg.timeframe,
                          "detection_tfs": list(cfg.detection_timeframes),
                          "allow_single_tf_degraded":
                              cfg.allow_single_tf_degraded})
        )
        print(f"[session] running — Ctrl+C to stop (dry_run={cfg.dry_run})")
        # One-shot startup banner (first board still prints immediately —
        # last_console starts at 0.0 — then every console_refresh_s).
        banner = render_startup_banner(
            self._identity or {},
            timeframe=cfg.timeframe,
            console_refresh_s=cfg.console_refresh_s,
            log_dir=cfg.log_dir,
        )
        print(banner)
        with open(self.log_dir / "console_mirror.log", "a", encoding="utf-8") as fh:
            fh.write(banner + "\n")

        last_console = 0.0
        deadline = time.monotonic() + max_seconds if max_seconds else None
        try:
            while deadline is None or time.monotonic() < deadline:
                try:
                    new_bars = self._loop.run_once()
                except Exception as exc:           # noqa: BLE001 — log, keep polling
                    self.state["errors"].append(repr(exc))
                    self._logger.error("poll error: %r", exc)
                    time.sleep(1.0)
                    continue
                self._on_poll(new_bars, connector)

                now_mono = time.monotonic()
                if now_mono - last_console >= cfg.console_refresh_s:
                    last_console = now_mono
                    self._publish_console()
                time.sleep(cfg.poll_interval_s)
        except KeyboardInterrupt:
            print("\n[session] Ctrl+C — clean shutdown…")
        finally:
            if deadline is not None:
                print("\n[session] max-seconds reached — clean shutdown…")
            self._shutdown(connector)

    # ------------------------------------------------------------------ #
    # Console + artifacts
    # ------------------------------------------------------------------ #
    def _publish_console(self) -> None:
        self.state["now_utc"] = _utcnow().isoformat(timespec="seconds")
        hb = self._heartbeat
        self.state["hb_seq"] = hb.sequence
        self.state["hb_age_s"] = max(0.0, _utcnow().timestamp() - hb._last_unix) \
            if hb._last_unix is not None else None
        self.state["hb_state"] = hb.state
        self._fold_flow_counters()
        self.state["kpi"] = self._runner.kpi.counters()
        board = render_status_board(self.state)
        print(board)
        with open(self.log_dir / "console_mirror.log", "a", encoding="utf-8") as fh:
            fh.write(board + "\n")
        # L1 structure console (read-only): appended to the same board +
        # mirror so POIS/SWEEPS/SEEKING/PLAN share the refresh cadence.
        structure = self.state.get("structure")
        if structure is not None:
            structure_board = render_structure_console(structure)
            print(structure_board)
            with open(self.log_dir / "console_mirror.log", "a",
                      encoding="utf-8") as fh:
                fh.write(structure_board + "\n")
        # Periodic KPI JSONL rewrite (append-friendly snapshot of the session).
        self._runner.kpi.write_jsonl(self.log_dir / "kpi_records.jsonl")

    def _shutdown(self, connector) -> None:
        try:
            self._loop.stop()   # writes the heartbeat shutdown marker
        except Exception:       # noqa: BLE001
            pass
        self._runner.kpi.write_jsonl(self.log_dir / "kpi_records.jsonl")
        summary = {
            "stopped_utc": _utcnow().isoformat(),
            "session_started_utc": self.state.get("session_started_utc"),
            "polls": self.state.get("polls"),
            "bars_processed": self.state.get("bars_processed"),
            "errors": self.state.get("errors"),
            "kpi_counters": self._runner.kpi.counters(),
            "identity": self._identity,
        }
        (self.log_dir / "session_summary.json").write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8"
        )
        self._log("SESSION STOP " + json.dumps(
            {"polls": summary["polls"], "bars": summary["bars_processed"]}))
        shutdown = getattr(connector, "shutdown", None)
        if callable(shutdown):
            shutdown()
        print(f"[session] stopped — artifacts in {self.log_dir}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SMC Phase D operator session")
    ap.add_argument("--config", required=True, help="path to operator config JSON")
    ap.add_argument(
        "--max-seconds", type=float, default=None,
        help="bound the session (controlled ops window / smoke test); "
             "default: run until Ctrl+C",
    )
    args = ap.parse_args(argv)

    try:
        config = load_operator_config(args.config)
    except Exception as exc:                       # noqa: BLE001 — fail clearly
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    # Archive the raw config for auditability (no secrets are ever stored).
    log_dir = Path(config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "config_effective.json").write_text(
        json.dumps(config.raw, indent=2, sort_keys=True), encoding="utf-8"
    )

    session = OperatorSession(config)
    try:
        session.run(max_seconds=args.max_seconds)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
