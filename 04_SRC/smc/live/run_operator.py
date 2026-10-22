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

Operational hardening (2026-10-08, PERMISSION ERROR(13) INVESTIGATION):
    * Startup diagnostics include the configured terminal path and Python PID.
      One active Python owner per terminal is operational guidance; MetaQuotes'
      initialize documentation does not state a formal process exclusivity rule.
    * MT5 failures include operation, terminal path, PID, and last_error where
      available. Repeated transient poll errors are deduplicated and recovery
      is logged; identity failures remain fatal.
    * Heartbeat writes target the terminal data-folder MQL5/Files path first.
      Unwritable candidates are logged, no writable target aborts startup, and
      a runtime write failure stops the session instead of claiming freshness.

Usage:
    python 04_SRC/smc/live/run_operator.py --config config/live_demo.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
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
    render_alive_line,
    render_startup_banner,
    render_status_board,
)
from smc.live.judgement_console import (                     # noqa: E402
    judge_interval_used,
    render_judgement_board,
)
from smc.live.marker_writer import (                         # noqa: E402
    MARKER_FILENAME,
    MarkerWriter,
    snapshot_to_records,
)
from smc.live.mode_t import (                                # noqa: E402
    MODE_T_BANNER,
    MODE_T_MARK,
    ModeTDirector,
    ModeTLedger,
    is_skip_reason,
)
from smc.live.structure_console import (                     # noqa: E402
    build_structure_snapshot,
    render_structure_console,
)
from smc.live.structure_publish import (                     # noqa: E402
    STRUCTURE_DRAW_FILENAME,
    StructureDrawPublisher,
)

__all__ = ["OperatorSession", "main"]

# MT5 auto-reconnect (2026-10-17 Lead Architect ruling): a transient terminal
# drop (terminal restarted, IPC lost, broker weekend reconnect) must self-heal
# with capped backoff instead of killing the session; a terminal that never
# comes back must stop the operator loudly (non-zero exit) rather than spin
# silently. Operational timing only — NOT a trading constant.
RECONNECT_BACKOFF_SECONDS = (1.0, 2.0, 5.0)
RECONNECT_MAX_ATTEMPTS = 10
RECONNECT_LOG_INTERVAL_SECONDS = 30.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OperatorSession:
    """One operator-controlled demo/paper session (single terminal)."""

    def __init__(self, config: OperatorConfig) -> None:
        self.config = config
        self.log_dir = Path(config.log_dir)
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PermissionError(
                f"operator log directory create failed path={self.log_dir}: {exc}"
            ) from exc
        self._logger = self._make_logger()
        self._mt5 = None                 # bound lazily in identity_check()
        self._connector = None
        self._identity: dict | None = None
        self._loop = None
        self._runner = None
        self._adapter = None
        self._heartbeat = None
        self._heartbeat_ea_readable: bool | None = None
        # 2026-10-17 (B1): heartbeat runs on its own daemon thread so a main
        # poll-thread hang cannot freeze the watchdog sequence.
        self._hb_runner = None
        # 2026-10-17 (B2/B3): MT5 reconnect bookkeeping + console rate-limit.
        self._reconnect_attempts = 0
        self._last_reconnect_log_mono = 0.0
        self._last_reconnect_signature: tuple | None = None
        self._armed_total = 0            # C1: cumulative newly-armed POIs
        self._console_force = False      # batch change → repaint board NOW
        # Event-driven console (2026-10-07): "event" mode stays mostly silent
        # and prints the full board only on major events; "board" keeps the
        # legacy timed full refresh. See _maybe_print_console / _maybe_alive.
        self._console_mode = getattr(config, "console_mode", "event")
        self._event_reason: str | None = None   # set by _on_poll when an event fired
        self._last_flow_sig: tuple | None = None  # flow/KPI signature for event detection
        self._last_err_count = 0
        self._last_alive_mono = time.monotonic()
        # PermissionError(13) hardening (2026-10-08): de-duplicate identical
        # MT5-call failures across polls so a persistent IPC blip does not
        # inflate state["errors"] every tick, and surface it loudly when new.
        self._active_mt5_err_signatures: dict[str, tuple] = {}
        self._last_poll_error_signature: tuple | None = None
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
        # Mode T + judgement + markers (design lock §2/§3/§4; built in
        # _build_stack only when the config opts in — default posture A).
        self._mode_t_director: ModeTDirector | None = None
        self._marker_writer: MarkerWriter | None = None
        self._last_judge_mono = 0.0
        self._last_marker_mono = 0.0
        self._last_marker_sig = None

    # ------------------------------------------------------------------ #
    # Backend logging (append-only, gitignored)
    # ------------------------------------------------------------------ #
    def _make_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"smc.operator.{id(self)}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not logger.handlers:
            path = self.log_dir / "events.log"
            try:
                fh = logging.FileHandler(path, encoding="utf-8")
            except OSError as exc:
                raise PermissionError(
                    f"operator events log open failed path={path}: {exc}"
                ) from exc
            fh.setFormatter(logging.Formatter(
                "%(asctime)sZ %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
            ))
            logger.addHandler(fh)
        return logger

    def _log(self, msg: str) -> None:
        self._logger.info(msg)

    def _write_text(self, path: Path, text: str, operation: str) -> None:
        try:
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            self._logger.error(
                "FILE WRITE FAILED operation=%s path=%s python_pid=%s error=%r",
                operation,
                path,
                os.getpid(),
                exc,
                exc_info=True,
            )
            raise

    def _append_console_mirror(self, text: str) -> None:
        path = self.log_dir / "console_mirror.log"
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError as exc:
            self._logger.error(
                "FILE WRITE FAILED operation=append_console_mirror "
                "path=%s python_pid=%s error=%r",
                path,
                os.getpid(),
                exc,
                exc_info=True,
            )
            raise

    # ------------------------------------------------------------------ #
    # Identity gate (before anything else)
    # ------------------------------------------------------------------ #
    def identity_check(self) -> dict:
        """Bind to the configured terminal and prove identity; abort on mismatch."""
        from smc.data.mt5_connector import MT5CallError, MT5Connector

        cfg = self.config
        self._log(
            f"MT5 STARTUP terminal_path={cfg.terminal_path!r} "
            f"python_pid={os.getpid()}; use one active Python owner per terminal"
        )
        connector = MT5Connector(
            symbol=cfg.symbol,
            magic=cfg.magic,
            terminal_path=cfg.terminal_path,
        )
        try:
            if not connector.connect():
                raise SystemExit(
                    f"ABORT: mt5.initialize(path={cfg.terminal_path!r}) failed: "
                    f"{connector.last_error()}"
                )
            term = connector.terminal_info()
            acct = connector.account_info()
            mt5_version = connector.version()
        except MT5CallError as exc:
            self._log(f"IDENTITY FAILED: {exc}")
            raise SystemExit(f"ABORT: terminal identity call failed: {exc}") from exc
        if term is None or acct is None:
            raise SystemExit(
                "ABORT: terminal/account info unavailable: "
                f"{connector.last_error()}"
            )

        live_dir = normalize_terminal_dir(str(term.path or ""))
        required_dir = normalize_terminal_dir(cfg.terminal_path)
        mode = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(int(acct.trade_mode), "UNKNOWN")
        is_demo = mode == "DEMO"

        facts = {
            "checked_at_utc": _utcnow().isoformat(),
            "terminal_dir_configured": required_dir,
            "terminal_dir_live": live_dir,
            # EA FileOpen sandbox for installed terminals — the authoritative
            # heartbeat target (see heartbeat_path.data_folder_heartbeat_path).
            "terminal_data_path": str(getattr(term, "data_path", "") or ""),
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
            "mt5_python_version": str(mt5_version),
            "mt5_python_pid": os.getpid(),
        }
        self._connector = connector
        self._mt5 = connector._mt5()
        if live_dir != required_dir:
            self._log(f"IDENTITY MISMATCH: {facts}")
            raise SystemExit(
                f"ABORT: connected terminal dir {live_dir!r} != required {required_dir!r}"
            )
        if cfg.require_demo and not is_demo:
            raise SystemExit(
                f"ABORT: require_demo=true but account trade_mode={mode}"
            )
        try:
            selected = connector.symbol_select(cfg.symbol, True)
        except MT5CallError as exc:
            self._log(f"IDENTITY FAILED: {exc}")
            raise SystemExit(f"ABORT: symbol_select({cfg.symbol}) failed: {exc}") from exc
        if not selected:
            raise SystemExit(
                f"ABORT: symbol_select({cfg.symbol}) failed: "
                f"{connector.last_error()}"
            )
        self._identity = facts
        self.state["terminal_dir"] = live_dir
        self.state["server"] = facts["server"]
        self.state["account"] = facts["login"]
        self.state["is_demo"] = is_demo
        self._write_text(
            self.log_dir / "identity.json",
            json.dumps(facts, indent=2),
            "write_identity",
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
        from smc.live.heartbeat import HeartbeatPublisher, HeartbeatRunner
        from smc.live.heartbeat_path import (
            heartbeat_path_candidates,
            probe_writable,
        )
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
        connector = self._connector or MT5Connector(
            symbol=cfg.symbol, magic=cfg.magic, terminal_path=cfg.terminal_path
        )
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
        # The watchdog EA reads MQL5/Files/smc_heartbeat.txt in its FileOpen
        # sandbox. For an INSTALLED (non-portable) terminal that sandbox is the
        # terminal DATA folder (mt5.terminal_info().data_path — captured at
        # identity check), not the install dir. Policy: live data_path >
        # install-dir derivation > config path > logs. Each candidate is
        # write-probed at startup so a Program-Files ACL degrades gracefully
        # (loud) instead of crashing or silently never updating the file.
        data_path = (self._identity or {}).get("terminal_data_path") or ""
        candidates = heartbeat_path_candidates(
            cfg.terminal_path, cfg.heartbeat_path,
            terminal_data_path=data_path,
        )
        heartbeat_source, heartbeat_path = candidates[0]
        for source, cand in candidates:
            if probe_writable(cand):
                heartbeat_source, heartbeat_path = source, cand
                break
            self._logger.warning(
                "HEARTBEAT PATH UNWRITABLE: %s (%s) - trying next candidate "
                "(Program Files ACL or missing permissions?)", cand, source,
            )
        else:
            self._logger.error(
                "HEARTBEAT PATH ALL CANDIDATES UNWRITABLE - refusing to start; "
                "the watchdog would treat the session as stale."
            )
            raise SystemExit(
                "ABORT: no writable heartbeat target; see events.log for "
                "candidate paths and probe failures"
            )
        if heartbeat_source != "terminal_data_path":
            self._heartbeat_ea_readable = False
            self._logger.warning(
                "HEARTBEAT PATH FALLBACK IS NOT CONFIRMED EA-READABLE: "
                f"heartbeat writes to {heartbeat_path}; the watchdog EA reads "
                "MQL5/Files/smc_heartbeat.txt under its terminal data folder "
                "and may NOT see it."
            )
        else:
            self._heartbeat_ea_readable = True
        self._log(
            f"HEARTBEAT PATH RESOLVED: {heartbeat_path} "
            f"(source: {heartbeat_source})"
        )
        try:
            heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._logger.critical(
                "HEARTBEAT PATH CREATE FAILED operation=mkdir path=%s "
                "python_pid=%s error=%r",
                heartbeat_path.parent,
                os.getpid(),
                exc,
                exc_info=True,
            )
            raise SystemExit(
                f"ABORT: cannot create heartbeat directory "
                f"{heartbeat_path.parent}: {exc}"
            ) from exc
        heartbeat = HeartbeatPublisher(
            heartbeat_path, interval_seconds=cfg.heartbeat_interval_s
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
        # B1 (2026-10-17): independent heartbeat ticker (started by run()).
        self._hb_runner = HeartbeatRunner(heartbeat)
        # --- Marker surface (design note §4.1): same Files-dir recipe as the
        # heartbeat — explicit config path wins, else the heartbeat's dir.
        if getattr(cfg, "marker_enabled", True):
            marker_dir = (
                Path(str(cfg.marker_path)).resolve(strict=False)
                if cfg.marker_path
                else heartbeat_path.parent
            )
            self._marker_writer = MarkerWriter(
                marker_dir / MARKER_FILENAME
            )
            self._log(
                "MARKER PATH RESOLVED: " + str(self._marker_writer.path)
            )
        # --- Structure-draw publisher (design lock 2026-10-22, §2): writes
        # smc_structure_draw.txt for the draw-only EA. Same EA-readable dir
        # recipe as the markers: the heartbeat's already-probed directory.
        # VISUALIZATION ONLY — never feeds a trading decision.
        self._structure_draw = None
        if getattr(cfg, "structure_draw_enabled", True):
            draw_dir = (
                Path(str(cfg.structure_draw_path)).resolve(strict=False)
                if cfg.structure_draw_path
                else heartbeat_path.parent
            )
            self._structure_draw = StructureDrawPublisher(
                draw_dir / STRUCTURE_DRAW_FILENAME
            )
            self._log(
                "STRUCTURE DRAW PATH RESOLVED: "
                + str(self._structure_draw.path)
            )
        # --- Mode T director (design note §2): diagnostics only; the product
        # path above is untouched. In dry_run NOTHING is sent (decisions are
        # still logged — prompt §1.4 / note dry-run parity).
        if cfg.diagnostic_entries:
            ledger = ModeTLedger(Path(cfg.log_dir) / "mode_t_events.jsonl")
            place_fn = None
            cancel_fn = None
            if not cfg.dry_run:
                from smc.execution.order_manager import (
                    OrderKind,
                    OrderRequest,
                )
                from smc.core.enums import Direction as _Direction

                broker = getattr(runner, "broker", None)
                if broker is not None:
                    def place_fn(decision, comment):
                        return broker.place_limit(OrderRequest(
                            symbol=cfg.symbol,
                            kind=OrderKind.LIMIT,
                            direction=decision.direction if isinstance(
                                decision.direction, _Direction) else _Direction.LONG,
                            volume=float(decision.volume),
                            price=float(decision.entry),
                            sl=float(decision.sl),
                            tp=float(decision.tp),
                            comment=comment,
                        ))

                    cancel_fn = (lambda ticket: bool(getattr(
                        broker.cancel_pending(int(ticket)), "success", False)
                    ))
            self._mode_t_director = ModeTDirector(
                ledger=ledger, place_fn=place_fn, cancel_fn=cancel_fn,
                clock=lambda: datetime.now(timezone.utc),
            )
            self._log(
                "MODE T enabled (diagnostic_entries=true, dry_run="
                + str(cfg.dry_run) + ")"
            )
        return connector

    # ------------------------------------------------------------------ #
    # Poll hook — board state + KPI folding
    # ------------------------------------------------------------------ #
    def _mt5_call(self, name: str, fn, *args, **kwargs):
        """Call one MT5 function; on PermissionError(13) or other IPC/OS blips,

        log the function + last_error loudly WITHOUT breaking the poll, and
        de-duplicate the same logical failure across polls so it does not inflate
        state["errors"] every tick. Returns the MT5 return value, or None on a
        non-fatal IPC blip so callers can continue.

        Any NEW failure is also appended to state["errors"] once (via the normal
        poll event path) — but identical repeated signatures are suppressed.
        """
        if fn is None or self._mt5 is None:
            return None
        try:
            result = fn(*args, **kwargs)
        except (OSError, ValueError) as exc:
            sig = (type(exc).__name__, str(exc))
            self._log_mt5_error(name, exc, sig)
            return None
        previous = self._active_mt5_err_signatures.pop(name, None)
        if previous is not None:
            self._logger.info(
                "MT5 CALL RECOVERED operation=mt5.%s terminal_path=%r "
                "python_pid=%s",
                name,
                self.config.terminal_path,
                os.getpid(),
            )
        return result

    def _log_mt5_error(self, name: str, exc: BaseException, sig: tuple) -> None:
        """Log one MT5-call failure per operation/signature until recovery."""
        try:
            err = self._mt5.last_error() if self._mt5 is not None else None
        except (OSError, ValueError) as last_error_exc:
            err = f"unavailable: {last_error_exc!r}"
        detail = (
            f"MT5 CALL FAILED operation=mt5.{name} "
            f"terminal_path={self.config.terminal_path!r} "
            f"python_pid={os.getpid()} error={exc!r} last_error={err!r}"
        )
        if self._active_mt5_err_signatures.get(name) == sig:
            self._logger.debug("%s (repeated; suppressed)", detail)
        else:
            self.state["errors"].append(detail)
            self._logger.error(
                "%s",
                detail,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            self._active_mt5_err_signatures[name] = sig

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
        # Display-only: an arming event must be VISIBLE on the prompt within
        # one poll, not at the next cadence tick (completes the 2026-10-06
        # console-mismatch fix — that fix rebuilt the snapshot immediately but
        # left printing bound to console_refresh_s, so with a 900 s cadence an
        # armed POI still stayed invisible for up to 15 min).
        if batch_changed:
            self._console_force = True

        # Event-driven console: decide WHY this poll should print (if at all).
        # Reasons, in directive order: new bar, HTF batch, flow/KPI change,
        # new error + new MT5-call permission/OS failure (loud once, deduped).
        # A pure-timer poll with no change sets NO reason, so event mode prints
        # nothing (the alive ping covers liveness).
        reasons: list[str] = []
        if batch_changed:
            reasons.append("HTF batch completed")
        if new_bars:
            reasons.append(f"new bar(s) processed: {new_bars}")
        if self._runner is not None:
            self._fold_flow_counters()
            kpi = self._runner.kpi.counters()
            sig = (
                self.state.get("candidates"), self.state.get("blocked"),
                self.state.get("placed"), self.state.get("cancelled"),
                self.state.get("rejects"),
                tuple(sorted(kpi.items())) if isinstance(kpi, dict) else (),
            )
            if self._last_flow_sig is not None and sig != self._last_flow_sig:
                reasons.append("flow/KPI counters changed")
            self._last_flow_sig = sig
        err_count = len(self.state["errors"])
        if err_count != self._last_err_count:
            reasons.append(f"new error (total {err_count})")
            self._last_err_count = err_count
        if reasons:
            self._event_reason = "; ".join(reasons) if len(reasons) > 1 else reasons[0]

        # MT5 market-state reads wrapped for IPC/permission resilience
        # (2026-10-08): on PermissionError(13) the poll continues and the
        # failure is loud once + de-duplicated (see _mt5_call).
        tick = self._mt5_call(
            "symbol_info_tick", self._mt5.symbol_info_tick, cfg.symbol
        )
        if tick is not None and tick.bid and tick.ask:
            self.state["spread"] = float(tick.ask) - float(tick.bid)
        elif tick is None:
            self.state["spread"] = None

        candles = getattr(self._adapter, "_candles", None)
        if candles:
            try:
                atr = self._adapter.current_atr(len(candles) - 1)
                self.state["atr"] = atr if atr > 0 else None
                self.state["last_bar_utc"] = candles[-1].timestamp.isoformat()
            except Exception as exc:              # noqa: BLE001 — board must not die
                self._logger.warning(
                    "BOARD READ FAILED operation=current_atr error=%r",
                    exc,
                    exc_info=True,
                )

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
        else:
            self.state["gate_pass"] = False
            self.state["gate_detail"] = "n/a (atr/spread unavailable)"

        if connector is not None:
            positions = self._mt5_call(
                "positions_get",
                self._mt5.positions_get,
                symbol=cfg.symbol,
            )
        else:
            positions = None
        self.state["open_positions"] = (
            None if positions is None else len(positions)
        )
        # Mode T poll hook (design note §2.2/§2.4): evaluate proof events
        # + manage the diagnostic book AFTER the §28.5 mirror artifacts
        # (spread/atr/positions are either valid or untouched); never
        # breaks the product poll itself.
        try:
            self._mode_t_on_poll()
        except Exception as exc:          # noqa: BLE001 — never breaks the poll
            self.state["errors"].append(f"mode T poll: {exc!r}")
            self._logger.error(
                "MODE T POLL FAILED error=%r", exc, exc_info=True,
            )

    def _mode_t_on_poll(self) -> None:
        """Mode T seam (candidate/limit seam, design note §2 — diagnostics only).

        Per poll, for each routed-but-not-accepted workflow in the adapter's
        own book (the ONLY Stage-3 proof events visible without forking
        detection/§5), evaluate rule T2 once per (poi, proof) event and
        manage the director's ticket book (12-bar rest / §5 invalidation /
        Friday EOD §28.4). Product ties win via ``product_ticket_active``
        (a live product pending/position for the same POI). dry_run: the
        director records every decision and sends nothing (§1.4 parity).
        Observability-only: any failure is recorded, never fatal to the
        product loop.
        """
        director = self._mode_t_director
        if director is None:
            return
        from smc.config.locked_constants import (
            FRIDAY_EOD_CLOSE_HOUR_UTC,
            SPREAD_GRADE_MULTIPLIERS,
            SPREAD_MAX_ATR,
        )
        from smc.core.enums import POIState
        from smc.risk.spread_grading import grade_for_score
        from smc.utils.timestamps import in_session
        from smc.utils.timestamps import Session as _Session
        from smc.live.mode_t import ACTION_PLACE

        cfg = self.config
        adapter = self._adapter
        engine = getattr(adapter, "engine", None)
        candles = getattr(adapter, "_candles", None)
        if engine is None or not candles:
            return
        bar_index = len(candles) - 1
        now_bar = candles[-1].timestamp
        atr = adapter.current_atr(bar_index)
        spread = self.state.get("spread")

        from smc.live.mode_t import ACTION_PLACE, MIN_LOT_FLOOR

        def to_utc_hour(ts):
            from smc.utils.timestamps import to_utc
            return to_utc(ts).hour

        def session_gate(ts) -> bool:
            if not cfg.allowed_sessions:
                return True
            return any(
                in_session(ts, _Session[name]) for name in cfg.allowed_sessions
            )

        def spread_gate(score, bar_ts) -> bool:
            if spread is None or not atr > 0:
                return True          # unknowable → not a Mode T verdict input
            grade = grade_for_score(float(score or 0.0))
            ceiling = SPREAD_MAX_ATR * atr * SPREAD_GRADE_MULTIPLIERS[str(grade)]
            return bool(spread <= ceiling)

        # Deferred (separate dict) because consider() must run AFTER the
        # product-ticket scan of the SAME poll — built below, then applied.
        for poi_id, candidate in list(adapter.active_workflows().items()):
            route_id = str(getattr(candidate, "route_id", "") or "")
            if "@" not in route_id:
                continue
            try:
                proof_bar = int(route_id.rsplit("@", 1)[1])
            except ValueError:
                continue
            if proof_bar < 0 or proof_bar >= len(candles):
                continue
            proof = candles[proof_bar]
            trigger_enum = getattr(candidate, "trigger", None)
            letter = str(
                getattr(trigger_enum, "value", None) or "T2"
            )
            tf_enum = getattr(candidate, "detection_tf", None)
            detection_tf = (
                getattr(tf_enum, "name", None)
                if tf_enum is not None else None
            )
            decision = director.consider(
                poi_id=str(poi_id),
                detection_tf=detection_tf,
                trigger_letter=letter,
                direction=candidate.direction,
                proof_bar=proof_bar,
                proof_high=float(proof.high),
                proof_low=float(proof.low),
                proof_close=float(proof.close),
                atr=atr if atr > 0 else None,
                session_ok=session_gate(now_bar),
                spread_gate_ok=spread_gate(
                    getattr(candidate, "score", None), now_bar
                ),
                product_ticket_active=self._product_ticket_active(
                    str(poi_id)
                ),
                concurrent_open=(
                    len(director.open_pois)
                ),
                volume_min=MIN_LOT_FLOOR,
                bar_index=bar_index,
            )
            if (decision.action == ACTION_PLACE
                    or decision.skip_reason is not None):
                self._event_reason = self._event_reason or (
                    "Mode T " + decision.action
                    + (""
                       if decision.skip_reason is None
                       else ": " + decision.skip_reason)
                )

        # §28.4 Friday EOD + §5 invalidation cancel the book (§2.4).
        invalidated = []
        for poi in engine.tracked_pois():
            try:
                if engine.state_machine.current(poi) == POIState.VIOLATED:
                    invalidated.append(poi.id)
            except Exception:          # noqa: BLE001 — display-only safety
                continue
        friday_eod = (
            now_bar.weekday() == 4
            and to_utc_hour(now_bar) >= int(FRIDAY_EOD_CLOSE_HOUR_UTC)
        )
        for cancel in director.manage(
            bar_index=bar_index,
            friday_eod=friday_eod,
            invalidated_pois=invalidated,
        ):
            self._log("MODE T MANAGE " + str(cancel))

    def _product_ticket_active(self, poi_id: str) -> bool:
        """True when a PRODUCT pending/position exists for ``poi_id`` (broker
        truth; product comments start with ``poi.id[:8]`` and never with the
        Mode T mark). Conservative: a MT5-call failure reads False (ties are
        then product-lost only if the book is empty — demo caps still bound)."""
        if self._mt5 is None:
            return False
        prefix = str(poi_id)[:8]
        orders = self._mt5_call(
            "orders_get", self._mt5.orders_get, symbol=self.config.symbol
        ) or []
        for order in orders:
            comment = str(getattr(order, "comment", "") or "")
            if comment.startswith(MODE_T_MARK):
                continue
            if prefix and comment.startswith(prefix):
                return True
        positions = self._mt5_call(
            "positions_get", self._mt5.positions_get, symbol=self.config.symbol
        ) or []
        for position in positions:
            comment = str(getattr(position, "comment", "") or "")
            if comment.startswith(MODE_T_MARK):
                continue
            if prefix and comment.startswith(prefix):
                return True
        return False

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
            self._logger.error(
                "STRUCTURE SNAPSHOT FAILED operation=build_structure_snapshot "
                "error=%r",
                exc,
                exc_info=True,
            )
        # Structure-draw file (design lock §2): publish on EVERY refresh —
        # a batch change (arming) forces both the board AND the draw file.
        # Fail-safe: a broken draw publish is logged, never fatal.
        self._publish_structure_draw()

    def _publish_structure_draw(self) -> None:
        """Rewrite smc_structure_draw.txt from the current snapshot.

        No snapshot yet (early loop) → publishes a header-only payload so
        the EA clears rather than showing stale geometry. Never raises.
        """
        writer = getattr(self, "_structure_draw", None)
        if writer is None:
            return
        try:
            if not writer.publish(
                self.state.get("structure"),
                symbol=self.config.symbol,
            ):
                self.state["errors"].append("structure draw publish failed")
        except Exception as exc:               # noqa: BLE001 — never fatal
            self.state["errors"].append(f"structure draw: {exc!r}")
            self._logger.error(
                "STRUCTURE DRAW PUBLISH FAILED path=%s error=%r",
                getattr(writer, "path", "?"),
                exc,
                exc_info=True,
            )

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
    def _session_start_payload(self) -> dict:
        """Structured session-start record (§2.1: mode discriminable —
        "T" when diagnostic_entries is true, else "A").

        The ``mode`` key reads the CONFIG FLAG, not ``_mode_t_director``:
        the director is only built later inside ``_build_stack()`` (which
        constructs it IFF the flag is true), so the flag is the posture's
        source of truth at logging time and the two can never disagree.
        """
        return {"symbol": self.config.symbol,
                "magic": self.config.magic,
                "dry_run": self.config.dry_run,
                "tf": self.config.timeframe,
                "terminal_path": self.config.terminal_path,
                "python_pid": os.getpid(),
                "detection_tfs": list(self.config.detection_timeframes),
                "allow_single_tf_degraded":
                    self.config.allow_single_tf_degraded,
                "mode":
                    "T" if getattr(self.config, "diagnostic_entries", False)
                    else "A"}

    def run(self, max_seconds: float | None = None) -> None:
        """Identity → stack → poll loop with console cadence → clean stop.

        ``max_seconds`` bounds the session for controlled ops windows and
        smoke tests (graceful stop + artifacts); None runs until Ctrl+C.
        """
        from smc.live.heartbeat import HeartbeatWriteError
        cfg = self.config
        self.identity_check()
        connector = self._build_stack()

        if not self._loop.start():
            raise SystemExit("ABORT: connector failed to initialize")
        # B1 (2026-10-17): start the independent heartbeat ticker. A failure
        # here means the watchdog would fail-close immediately → abort loudly.
        if self._hb_runner is not None:
            try:
                self._hb_runner.start()
            except HeartbeatWriteError as exc:
                raise SystemExit(
                    f"ABORT: heartbeat publication failed: {exc}"
                ) from exc
        self.state["session_started_utc"] = _utcnow().isoformat()
        self._log("SESSION START " + json.dumps(self._session_start_payload()))
        print(f"[session] running — Ctrl+C to stop (dry_run={cfg.dry_run})")
        # One-shot startup banner (identity/terminal/symbol/dry_run/paths).
        banner = render_startup_banner(
            self._identity or {},
            timeframe=cfg.timeframe,
            console_refresh_s=cfg.console_refresh_s,
            log_dir=cfg.log_dir,
            console_mode=self._console_mode,
            alive_interval_s=cfg.alive_interval_s,
            heartbeat_path=getattr(self._heartbeat, "path", None),
            hb_independent=self._hb_runner is not None,
            auto_reconnect=bool(
                callable(getattr(connector, "reconnect", None))
            ),
        )
        print(banner)
        self._append_console_mirror(banner)
        # Mode T posture banner (design note §2.1 — printed EXACTLY once,
        # exact string). Never printed when the flag is off.
        if self._mode_t_director is not None:
            print(MODE_T_BANNER)
            self._append_console_mirror(MODE_T_BANNER)
        # Event 1 (session start): the first full board prints immediately in
        # BOTH modes — event mode via a queued reason, board mode via the
        # legacy last_console=0.0 anchor.
        if self._console_mode == "event":
            self._event_reason = self._event_reason or "session start"

        last_console = 0.0
        deadline = time.monotonic() + max_seconds if max_seconds else None
        try:
            while deadline is None or time.monotonic() < deadline:
                try:
                    probe = getattr(connector, "is_alive", None)
                    if callable(probe) and not probe():
                        raise ConnectionError(
                            "MT5 terminal not responding (liveness probe)"
                        )
                    new_bars = self._loop.run_once()
                except HeartbeatWriteError as exc:
                    detail = f"HEARTBEAT WRITE FAILED: {exc}"
                    if detail not in self.state["errors"]:
                        self.state["errors"].append(detail)
                    self._logger.critical(
                        "%s; terminating because watchdog liveness is "
                        "unavailable",
                        detail,
                        exc_info=True,
                    )
                    raise SystemExit(
                        f"ABORT: heartbeat publication failed: {exc}"
                    ) from exc
                except Exception as exc:           # noqa: BLE001 — log, keep polling
                    signature = (type(exc).__name__, str(exc))
                    if signature != self._last_poll_error_signature:
                        self.state["errors"].append(
                            f"{type(exc).__name__}: {exc}"
                        )
                        self._logger.error(
                            "POLL FAILED terminal_path=%r python_pid=%s "
                            "error=%r",
                            cfg.terminal_path,
                            os.getpid(),
                            exc,
                            exc_info=True,
                        )
                        self._print_console(
                            f"[poll-error] utc={_utcnow().isoformat()} "
                            f"{type(exc).__name__}: {exc}"
                        )
                        self._last_poll_error_signature = signature
                    else:
                        self._logger.debug(
                            "Repeated poll failure suppressed: %s", exc
                        )
                    self._attempt_reconnect(connector, exc)
                    continue
                if self._last_poll_error_signature is not None:
                    self._logger.info(
                        "POLL RECOVERED terminal_path=%r python_pid=%s",
                        cfg.terminal_path,
                        os.getpid(),
                    )
                    self._print_console(
                        f"[poll-recovered] utc={_utcnow().isoformat()} "
                        f"polls={self.state.get('polls')}"
                    )
                    self._last_poll_error_signature = None
                if self._reconnect_attempts:
                    self._reconnect_attempts = 0
                self._on_poll(new_bars, connector)

                now_mono = time.monotonic()
                if self._console_mode == "event":
                    self._maybe_print_console(now_mono)
                    self._maybe_alive(now_mono)
                    self._maybe_judge(now_mono)
                else:
                    if self._console_force or \
                            now_mono - last_console >= cfg.console_refresh_s:
                        self._console_force = False
                        last_console = now_mono
                        self._publish_console()
                    self._maybe_judge(now_mono)
                time.sleep(cfg.poll_interval_s)
        except KeyboardInterrupt:
            print("\n[session] Ctrl+C — clean shutdown…")
        finally:
            if deadline is not None:
                print("\n[session] max-seconds reached — clean shutdown…")
            self._shutdown(connector)

    # ------------------------------------------------------------------ #
    # MT5 reconnect (2026-10-17 ruling B2/B3)
    # ------------------------------------------------------------------ #
    def _print_console(self, line: str) -> None:
        """Print a structured one-liner to stdout and mirror it (best effort)."""
        print(line)
        try:
            self._append_console_mirror(line)
        except OSError:
            pass

    def _log_reconnect(self, line: str, signature: tuple) -> None:
        """Console one-liner for a reconnect event, rate-limited (B3).

        An identical (unchanged) signature prints at most once per
        ``RECONNECT_LOG_INTERVAL_SECONDS``; a changed state always prints.
        Every line is still recorded in events.log.
        """
        now_mono = time.monotonic()
        changed = signature != self._last_reconnect_signature
        if changed or (
            now_mono - self._last_reconnect_log_mono
            >= RECONNECT_LOG_INTERVAL_SECONDS
        ):
            self._print_console(line)
            self._last_reconnect_log_mono = now_mono
            self._last_reconnect_signature = signature
        self._log(line)

    def _verify_reconnect_gate(self, connector) -> None:
        """Re-assert the terminal-path + demo gate on the SAME connector.

        After a reconnect the SAME terminal and (when ``require_demo``) a DEMO
        account are required; a real mismatch aborts the session. A still-
        unresponsive terminal is left to the next liveness probe.
        """
        from smc.data.mt5_connector import MT5CallError

        try:
            term = connector.terminal_info()
            acct = connector.account_info()
        except MT5CallError as exc:
            self._logger.error(
                "RECONNECT GATE info unavailable error=%r", exc, exc_info=True
            )
            return
        except Exception as exc:  # noqa: BLE001 — never crash on the gate probe
            self._logger.error(
                "RECONNECT GATE call failed error=%r", exc, exc_info=True
            )
            return
        if term is None or acct is None:
            self._logger.error(
                "RECONNECT GATE: terminal/account info unavailable after "
                "reconnect terminal_path=%r",
                self.config.terminal_path,
            )
            return
        live_dir = normalize_terminal_dir(str(term.path or ""))
        required_dir = normalize_terminal_dir(self.config.terminal_path)
        if live_dir != required_dir:
            raise SystemExit(
                f"ABORT: reconnect terminal dir {live_dir!r} != required "
                f"{required_dir!r}"
            )
        mode = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(
            int(acct.trade_mode), "UNKNOWN"
        )
        if self.config.require_demo and mode != "DEMO":
            raise SystemExit(
                f"ABORT: require_demo=true after reconnect but mode={mode}"
            )

    def _attempt_reconnect(self, connector, exc) -> None:
        """Capped-backoff MT5 reconnect after a poll failure (2026-10-17 B2).

        Reuses THIS connector (no second process for the same magic/terminal).
        Gives up with a non-zero exit only after ``RECONNECT_MAX_ATTEMPTS``
        consecutive hard failures. Sleeps a short backoff between attempts;
        the caller continues the poll loop on return.
        """
        self._reconnect_attempts += 1
        attempt = self._reconnect_attempts
        delay = RECONNECT_BACKOFF_SECONDS[
            min(attempt - 1, len(RECONNECT_BACKOFF_SECONDS) - 1)
        ]
        if attempt >= RECONNECT_MAX_ATTEMPTS:
            message = (
                f"MAJOR: giving up reconnect after {attempt} consecutive "
                f"failures: {exc!r}"
            )
            self._log(message)
            print(f"[critical] {message}")
            raise SystemExit(message)
        self._log_reconnect(
            f"[reconnect] utc={_utcnow().isoformat()} "
            f"attempt={attempt}/{RECONNECT_MAX_ATTEMPTS} "
            f"terminal={self.config.terminal_path!r} error={exc!r} "
            f"retry_in={delay:g}s",
            (type(exc).__name__, str(exc)),
        )
        reconnect = getattr(connector, "reconnect", None)
        if callable(reconnect):
            try:
                if reconnect():
                    self._reconnect_attempts = 0
                    self._verify_reconnect_gate(connector)
                    self._log(
                        "MT5 RECONNECTED terminal_path=%r python_pid=%s"
                        % (self.config.terminal_path, os.getpid())
                    )
                    self._log_reconnect(
                        f"[reconnect] utc={_utcnow().isoformat()} RECONNECTED "
                        f"terminal={self.config.terminal_path!r}",
                        ("reconnected", ""),
                    )
                    return
            except SystemExit:
                raise
            except Exception as re_exc:  # noqa: BLE001 — keep retrying
                self._logger.error(
                    "MT5 RECONNECT CALL FAILED error=%r", re_exc, exc_info=True
                )
        time.sleep(delay)

    # ------------------------------------------------------------------ #
    # Console + artifacts
    # ------------------------------------------------------------------ #
    def _maybe_print_console(self, now_mono: float) -> bool:
        """Event mode: print the full board ONLY on a queued event reason.

        A poll with no state change queues no reason → no print, no matter
        how long since the last print (the alive ping covers liveness).
        Returns True when a board was printed.
        """
        reason = self._event_reason
        if not reason:
            return False
        self._event_reason = None
        self._publish_console(reason=reason)
        return True

    def _maybe_judge(self, now_mono: float) -> bool:
        """Judgement board (design note §3.1): guaranteed at least ONE full
        board per ``judge_interval_s`` EVEN WHEN FLAT (0 s disables). Pure
        observability; failures are recorded, never fatal."""
        interval = 0.0
        try:
            interval = float(getattr(self.config, "judge_interval_s", 60.0) or 0.0)
        except (TypeError, ValueError):
            interval = 0.0
        if interval <= 0:
            return False
        if now_mono - self._last_judge_mono < interval:
            return False
        self._last_judge_mono = now_mono
        try:
            self._publish_judgement()
        except Exception as exc:          # noqa: BLE001 — board must not die
            self.state["errors"].append(f"judgement board: {exc!r}")
            self._logger.error(
                "JUDGEMENT BOARD FAILED error=%r", exc, exc_info=True,
            )
        return True

    def _publish_judgement(self) -> None:
        """Render + mirror ONE judgement board (blocks per design §3.2)."""
        now_utc = _utcnow().isoformat(timespec="seconds")
        director = self._mode_t_director
        events: list[dict] = []
        if director is not None:
            tail = director.ledger.tail(5)
            for rec in tail:
                events.append(
                    f"POI {rec.get('poi_id', 'n/a')[:8]} proof={rec.get('proof_bar', 'n/a')}"
                    f" · action={rec.get('action', 'n/a')}"
                    + (f" · SKIP: {rec.get('skip_reason')}"
                       if rec.get("skip_reason") else "")
                    + (f" · Mode T LIMIT {rec.get('entry'):.2f} reason proof_close-mid"
                       if rec.get("action") == "PLACE" else "")
                )
        if not events and self.state.get("structure") is None and not self.state.get("errors"):
            events = []                     # flat session keeps the note's idle line
        hb = self._heartbeat
        board = render_judgement_board(
            now_utc=now_utc,
            mode="T" if director is not None else "A",
            mode_t_banner=MODE_T_BANNER if director is not None else None,
            structure=self.state.get("structure"),
            mode_t_events=events,
            book_product_positions=self.state.get("open_positions") or 0,
            book_product_pendings=None,
            book_mode_t_positions=None,
            book_mode_t_pendings=(len(director.resting) if director is not None else 0),
            hb_seq=getattr(hb, "sequence", None),
            hb_age_s=(max(0.0, _utcnow().timestamp() - hb._last_unix)
                      if hb is not None and getattr(hb, "_last_unix", None) is not None
                      else None),
            hb_state=(getattr(hb, "state", None)
                      if self._heartbeat_ea_readable is not False
                      else f"{getattr(hb, 'state', None)} (EA path unconfirmed)"),
        )
        print(board)
        self._append_console_mirror(board)

    def _maybe_markers(self, now_mono: float) -> None:
        """Marker snapshot rewrite (design note §4.1): refresh when the
        structure snapshot changes and on Mode T place/cancel (rate-limited
        by ``console_refresh_s`` otherwise). Marker failure logged + skipped
        — never fatal (§4.4)."""
        writer = self._marker_writer
        if writer is None:
            return
        director = self._mode_t_director
        entry_marker = (
            director.latest_entry_marker()
            if director is not None else None
        )
        marker_sig = (
            self.state.get("htf_batches"),
            tuple(sorted((director.resting or {}).items()))
            if director is not None else (),
            # R1: the entry_t line is part of the marker identity so a new
            # dry-run decision refreshes the snapshot (no book change to piggy
            # on) and a fill/cancel/expiry drops or updates it.
            (entry_marker or {}).get("poi_id"),
            (entry_marker or {}).get("entry"),
            (entry_marker or {}).get("text"),
        )
        sig = marker_sig
        if sig == self._last_marker_sig:
            return
        if now_mono - self._last_marker_mono < max(1.0, float(self.config.console_refresh_s)):
            return
        self._last_marker_mono = now_mono
        self._last_marker_sig = sig
        try:
            records = snapshot_to_records(
                symbol=self.config.symbol,
                structure=self.state.get("structure"),
                mode="T" if self._mode_t_director is not None else "A",
                heartbeat_ok=(self._heartbeat_ea_readable is not False),
                mode_t_poi=entry_marker,   # R1: live entry_t line (§4.3)
                updated_at_utc=_utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            writer.write(records)
        except Exception as exc:          # noqa: BLE001 — markers never fatal
            self.state["errors"].append(f"marker writer: {exc!r}")
            self._logger.error(
                "MARKER SNAPSHOT FAILED error=%r", exc, exc_info=True,
            )

    def _maybe_alive(self, now_mono: float) -> bool:
        """Event mode: at most ONE short alive line per ``alive_interval_s``.

        Never a full board. ``alive_interval_s=0`` disables the ping.
        Returns True when a ping was printed.
        """
        interval = float(getattr(self.config, "alive_interval_s", 300.0) or 0.0)
        if interval <= 0:
            return False
        if now_mono - self._last_alive_mono < interval:
            return False
        self._last_alive_mono = now_mono
        hb = self._heartbeat
        line = render_alive_line({
            "now_utc": _utcnow().isoformat(timespec="seconds"),
            "hb_seq": hb.sequence if hb is not None else None,
            "bars_processed": self.state.get("bars_processed"),
            "htf_armed": self.state.get("htf_armed"),
            "errors": self.state.get("errors"),
        })
        print(line)
        self._append_console_mirror(line)
        return True

    def _publish_console(self, reason: str | None = None) -> None:
        if reason:
            header = f">>> event: {reason}"
            print(header)
            self._append_console_mirror(header)
        self.state["now_utc"] = _utcnow().isoformat(timespec="seconds")
        hb = self._heartbeat
        self.state["hb_seq"] = hb.sequence
        self.state["hb_age_s"] = max(0.0, _utcnow().timestamp() - hb._last_unix) \
            if hb._last_unix is not None else None
        self.state["hb_state"] = (
            hb.state
            if self._heartbeat_ea_readable is not False
            else f"{hb.state} (EA path unconfirmed)"
        )
        self._fold_flow_counters()
        self.state["kpi"] = self._runner.kpi.counters()
        board = render_status_board(self.state)
        print(board)
        self._append_console_mirror(board)
        # L1 structure console (read-only): appended to the same board +
        # mirror so POIS/SWEEPS/SEEKING/PLAN share the refresh cadence.
        structure = self.state.get("structure")
        if structure is not None:
            structure_board = render_structure_console(structure)
            print(structure_board)
            self._append_console_mirror(structure_board)
        # Marker surface rides every console publish (design §4.1: refresh
        # on structure change + Mode T place/cancel; rate-limited).
        try:
            self._maybe_markers(time.monotonic())
        except Exception as exc:          # noqa: BLE001 — markers never fatal
            self.state["errors"].append(f"marker publish: {exc!r}")
        # Periodic KPI JSONL rewrite (append-friendly snapshot of the session).
        kpi_path = self.log_dir / "kpi_records.jsonl"
        try:
            self._runner.kpi.write_jsonl(kpi_path)
        except OSError as exc:
            self._logger.error(
                "FILE WRITE FAILED operation=write_kpi_jsonl path=%s "
                "python_pid=%s error=%r",
                kpi_path,
                os.getpid(),
                exc,
                exc_info=True,
            )
            raise

    def _shutdown(self, connector) -> None:
        from smc.live.heartbeat import HeartbeatWriteError

        # B1 (2026-10-17): stop the independent ticker FIRST so it cannot
        # overwrite the shutdown marker with a "running" record afterwards.
        if self._hb_runner is not None:
            try:
                self._hb_runner.stop()
            except Exception as exc:       # noqa: BLE001 — shutdown must finish
                self._logger.error(
                    "HEARTBEAT RUNNER STOP FAILED error=%r",
                    exc,
                    exc_info=True,
                )
        try:
            self._loop.stop()   # writes the heartbeat shutdown marker
        except HeartbeatWriteError as exc:
            self._logger.critical(
                "HEARTBEAT SHUTDOWN WRITE FAILED: %s",
                exc,
                exc_info=True,
            )
            print(f"[critical] heartbeat shutdown marker failed: {exc}")
        except Exception as exc:       # noqa: BLE001 — shutdown must finish
            self._logger.error(
                "SESSION SHUTDOWN FAILED operation=loop.stop error=%r",
                exc,
                exc_info=True,
            )
        kpi_path = self.log_dir / "kpi_records.jsonl"
        try:
            self._runner.kpi.write_jsonl(kpi_path)
        except OSError as exc:
            self._logger.error(
                "SHUTDOWN FILE WRITE FAILED operation=write_kpi_jsonl path=%s "
                "python_pid=%s error=%r",
                kpi_path,
                os.getpid(),
                exc,
                exc_info=True,
            )
        summary = {
            "stopped_utc": _utcnow().isoformat(),
            "session_started_utc": self.state.get("session_started_utc"),
            "polls": self.state.get("polls"),
            "bars_processed": self.state.get("bars_processed"),
            "errors": self.state.get("errors"),
            "kpi_counters": self._runner.kpi.counters(),
            "identity": self._identity,
        }
        summary_path = self.log_dir / "session_summary.json"
        try:
            summary_path.write_text(
                json.dumps(summary, indent=2, default=str), encoding="utf-8"
            )
        except OSError as exc:
            self._logger.error(
                "SHUTDOWN FILE WRITE FAILED operation=write_session_summary "
                "path=%s python_pid=%s error=%r",
                summary_path,
                os.getpid(),
                exc,
                exc_info=True,
            )
        self._log("SESSION STOP " + json.dumps(
            {"polls": summary["polls"], "bars": summary["bars_processed"]}))
        # Mode T clean stop (design note §2.4): resting diagnostic tickets
        # cancelled; open diagnostic positions left to the static watchdog.
        if self._mode_t_director is not None:
            for cancel in self._mode_t_director.shutdown():
                self._log("MODE T SHUTDOWN CANCEL " + str(cancel))
        shutdown = getattr(connector, "shutdown", None)
        if callable(shutdown):
            shutdown()
        # Event 8 (shutdown): the stop line always prints; in event mode the
        # final full board rides along so the operator sees the end state.
        if self._console_mode == "event" and self._runner is not None:
            try:
                self._publish_console(reason="session shutdown (clean stop)")
            except Exception as exc:            # noqa: BLE001 — shutdown must finish
                self._logger.error(
                    "SHUTDOWN CONSOLE PUBLISH FAILED path=%s error=%r",
                    self.log_dir / "console_mirror.log",
                    exc,
                    exc_info=True,
                )
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
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(
            f"FILE OPERATION FAILED: create log directory {log_dir}: {exc}",
            file=sys.stderr,
        )
        return 2
    config_path = log_dir / "config_effective.json"
    try:
        config_path.write_text(
            json.dumps(config.raw, indent=2, sort_keys=True), encoding="utf-8"
        )
    except OSError as exc:
        print(
            f"FILE OPERATION FAILED: write config snapshot {config_path}: {exc}",
            file=sys.stderr,
        )
        return 2

    try:
        session = OperatorSession(config)
    except OSError as exc:
        print(f"OPERATOR STARTUP FILE ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        session.run(max_seconds=args.max_seconds)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
