"""POST-V1 PHASE D — ops validation session (EXNESS Copy terminal only).

Runs the runnable-now subset of the Lead Architect checklist:

  1. identity gate   — re-assert the exact terminal path / DEMO / symbol
                       before anything else (abort on mismatch);
  2. idle session    — LiveLoop.run_once() cadence over a controlled window:
                       bar poll (weekend ⇒ 0 new bars expected), heartbeat
                       publishing, no crashes; interleaved live spread
                       samples from symbol_info_tick;
  3. spread history  — mt5.copy_ticks_range over two representative Friday
                       windows (London/NY overlap, late NY) → spread
                       distribution vs the frozen §28.5 ATR-relative gate
                       (0.15 × ATR × grade multiplier, A+ 1.5 / A 1.0 /
                       B 0.7 / C 0.5);
  4. order paths     — order_check payload validation for a pending limit
                       (0.10 lots, dedicated Phase D magic) — NO sends.
                       place/cancel/SL-modify/close against the broker are
                       gated on a live session with Algo Trading enabled.

Artifacts land in 06_RESEARCH/results/phase_d_ops/.

Usage:
  python 06_RESEARCH/scripts/phase_d_ops_session.py --minutes 3
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REQUIRED_TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe"
PHASE_D_MAGIC = 20260919          # dedicated Phase D magic (not shared)
SYMBOL = "XAUUSDm"
RESULTS = Path(__file__).resolve().parents[1] / "results" / "phase_d_ops"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "04_SRC"))  # smc package

# Frozen §28.5 gate inputs (LOCKED_DECISIONS).
SPREAD_MAX_ATR = 0.15
GRADE_MULT = {"A+": 1.5, "A": 1.0, "B": 0.7, "C": 0.5}


def _identity_gate(mt5) -> dict:
    ok = mt5.initialize(path=REQUIRED_TERMINAL)
    if not ok:
        raise SystemExit(f"FATAL: initialize failed: {mt5.last_error()}")
    term = mt5.terminal_info()
    acct = mt5.account_info()
    live_dir = str(term.path or "").replace("/", "\\").strip().rstrip("\\").lower()
    required_dir = REQUIRED_TERMINAL.rsplit("\\", 1)[0].lower()
    mode = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(int(acct.trade_mode), "UNKNOWN")
    facts = {
        "terminal_dir": live_dir,
        "terminal_dir_required": required_dir,
        "connected": bool(term.connected),
        "trade_allowed": bool(term.trade_allowed),
        "login": int(acct.login),
        "server": acct.server,
        "company": acct.company,
        "mode": mode,
        "symbol": SYMBOL,
        "python_mt5_version": str(mt5.version()),
    }
    if live_dir != required_dir:
        raise SystemExit(f"FATAL: terminal identity mismatch: {facts}")
    if mode == "REAL":
        raise SystemExit("FATAL: REAL account — refusing to proceed")
    if not mt5.symbol_select(SYMBOL, True):
        raise SystemExit(f"FATAL: symbol_select({SYMBOL}) failed: {mt5.last_error()}")
    print("[identity] PASS:", json.dumps(facts, indent=2).encode("ascii", "backslashreplace").decode())
    return facts


def _idle_session(mt5, minutes: float, facts: dict) -> dict:
    """LiveLoop idle-session: poll cadence + heartbeat + spread samples."""
    from smc.backtest.pipeline_adapter import PipelineAdapter
    from smc.config.timeframe import Timeframe
    from smc.data.mt5_connector import MT5Connector
    from smc.execution.order_manager import OrderManager
    from smc.execution.position_manager import PositionManager
    from smc.live.heartbeat import HeartbeatPublisher, read_heartbeat
    from smc.live.loop import LiveLoop
    from smc.orchestration.detection_driver import DetectionDriver
    from smc.orchestration.engine import PipelineEngine
    from smc.paper.runner import PaperConfig, PaperRunner
    from smc.risk.risk_engine import RiskEngine

    connector = MT5Connector(symbol=SYMBOL, magic=PHASE_D_MAGIC,
                             terminal_path=REQUIRED_TERMINAL)
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=Timeframe.M5)
    runner = PaperRunner(
        connector=connector,
        risk_engine=RiskEngine(),
        pipeline=adapter,
        order_manager=OrderManager(connector, symbol=SYMBOL, magic=PHASE_D_MAGIC),
        position_manager=PositionManager(connector, symbol=SYMBOL),
        config=PaperConfig(dry_run=True),   # evaluate + log, never place
    )
    heartbeat = HeartbeatPublisher(RESULTS / "smc_heartbeat.txt")
    loop = LiveLoop(connector=connector, runner=runner, driver=DetectionDriver(Timeframe.M5),
                    heartbeat=heartbeat, symbol=SYMBOL, timeframe=Timeframe.M5,
                    window_bars=200, poll_interval=0.5)

    RESULTS.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    polls = new_bars = spread_samples = 0
    spreads = []
    errors = []

    assert loop.start(), "connector failed to initialize"
    print(f"[session] live for {minutes} min - polling (market-closed => 0 new bars expected)")
    deadline = time.monotonic() + minutes * 60.0
    while time.monotonic() < deadline:
        try:
            new_bars += loop.run_once()
            polls += 1
            tick = mt5.symbol_info_tick(SYMBOL)
            if tick is not None and tick.bid and tick.ask:
                spreads.append(round(tick.ask - tick.bid, 5))
                spread_samples += 1
        except Exception as exc:                      # noqa: BLE001 — session must record, not die
            errors.append(repr(exc))
            print(f"[session] ERROR: {exc!r}")
        time.sleep(2.0)

    hb_before_stop = read_heartbeat(heartbeat.path)
    loop.stop()
    time.sleep(0.2)
    hb_after_stop = read_heartbeat(heartbeat.path)
    stopped = datetime.now(timezone.utc)

    runner.kpi.write_jsonl(RESULTS / "kpi_records.jsonl")
    session = {
        "started_utc": started.isoformat(),
        "stopped_utc": stopped.isoformat(),
        "duration_min": round((stopped - started).total_seconds() / 60, 2),
        "polls": polls,
        "new_bars_processed": new_bars,
        "spread_samples": spread_samples,
        "errors": errors,
        "heartbeat_during_run": str(hb_before_stop),
        "heartbeat_after_stop": str(hb_after_stop),
        "heartbeat_interval_s": heartbeat.interval_seconds,
        "watchdog_timeout_s": 5.0,
        "ea_deployed": "MQL5\\Experts\\SMC_Safety_Watchdog.ex5 (compiled 0 err/0 warn; "
                       "attach via terminal GUI — InpHeartbeatFile=smc_heartbeat.txt, "
                       "InpSymbolFilter=XAUUSDm, InpMagicFilter=20260919)",
        "kpi_counters": runner.kpi.counters(),
    }
    (RESULTS / "spread_samples_live.csv").write_text(
        "seq,spread_price_units\n"
        + "\n".join(f"{i},{s}" for i, s in enumerate(spreads)) + "\n",
        encoding="utf-8",
    )
    print("[session]", json.dumps({k: v for k, v in session.items() if k != "ea_deployed"}, indent=2))
    return session


def _atr_from_bars(mt5, tf_const) -> float | None:
    """Approximate M5 ATR(14) over the most recent completed bars (Wilder)."""
    import numpy as np
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_const, 1, 60)  # skip forming bar
    if rates is None or len(rates) < 20:
        return None
    tr = np.maximum(
        rates["high"][: -1] - rates["low"][: -1],
        np.maximum(
            np.abs(rates["high"][1:] - rates["close"][:-1]),
            np.abs(rates["low"][1:] - rates["close"][:-1]),
        ),
    )
    atr = tr[:14].mean()
    for v in tr[14:]:
        atr = (atr * 13 + v) / 14.0
    return float(atr)


def _spread_distribution(mt5) -> dict:
    """Tick-history spread distribution vs the frozen ATR-relative gate."""
    import numpy as np
    import pandas as pd

    atr = _atr_from_bars(mt5, mt5.TIMEFRAME_M5)
    windows = {
        "friday_1400_1600_utc": ("2026-09-18T14:00:00+00:00", "2026-09-18T16:00:00+00:00"),
        "friday_2000_2057_utc": ("2026-09-18T20:00:00+00:00", "2026-09-18T20:57:00+00:00"),
    }
    out = {"atr_m5_approx_price_units": atr, "gate": {"SPREAD_MAX_ATR": SPREAD_MAX_ATR,
            "grade_multipliers": GRADE_MULT,
            "gate_max_per_grade_price_units": (
                {g: round(SPREAD_MAX_ATR * atr * m, 5) for g, m in GRADE_MULT.items()}
                if atr else None)}}
    for name, (a, b) in windows.items():
        t_from = datetime.fromisoformat(a)
        t_to = datetime.fromisoformat(b)
        ticks = mt5.copy_ticks_range(SYMBOL, t_from, t_to, mt5.COPY_TICKS_INFO)
        if ticks is None or len(ticks) == 0:
            out[name] = {"error": str(mt5.last_error())}
            continue
        df = pd.DataFrame(ticks)
        spr = (df["ask"] - df["bid"]).dropna()
        spr = spr[spr >= 0]
        dist = {
            "ticks": int(len(spr)),
            "p10": float(spr.quantile(0.10)),
            "p50": float(spr.quantile(0.50)),
            "p90": float(spr.quantile(0.90)),
            "p99": float(spr.quantile(0.99)),
            "max": float(spr.max()),
        }
        if atr:
            dist["pass_fraction_by_grade"] = {
                g: round(float((spr <= SPREAD_MAX_ATR * atr * m).mean()), 6)
                for g, m in GRADE_MULT.items()
            }
        out[name] = dist
    return out


def _order_path_checks(mt5) -> dict:
    """Payload validation via order_check — NO order is sent."""
    tick = mt5.symbol_info_tick(SYMBOL)
    si = mt5.symbol_info(SYMBOL)
    bid = tick.bid
    # Buy limit 5.0 below market; SL 3.0 below entry; TP 6.0 above entry.
    price = round(bid - 5.0, 3)
    sl = round(price - 3.0, 3)
    tp = round(price + 6.0, 3)
    base = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": SYMBOL,
        "volume": 0.10,                      # §28.7 lot cap — the value Phase C saw 100%
        "type": mt5.ORDER_TYPE_BUY_LIMIT,
        "price": price,
        "sl": sl,
        "tp": tp,
        "magic": PHASE_D_MAGIC,
        "comment": "PHASE_D_OPS",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    res_check = mt5.order_check(dict(base))
    check = {
        "request": {k: v for k, v in base.items()},
        "retcode": getattr(res_check, "retcode", None),
        "comment": getattr(res_check, "comment", None),
        "retcode_meaning": {
            0: "ok", 10018: "market closed (expected on weekend)",
            10030: "unsupported filling mode", 10015: "invalid price",
            10016: "invalid stops", 10019: "no money",
        }.get(getattr(res_check, "retcode", -1), "see MT5 docs"),
    }
    # Filling-mode fallback probe (IOC) when FOK unsupported.
    alt = dict(base)
    alt["type_filling"] = mt5.ORDER_FILLING_IOC
    res_alt = mt5.order_check(alt)
    check["ioc_fallback_retcode"] = getattr(res_alt, "retcode", None)

    out = {
        "symbol_spec": {"digits": si.digits, "point": si.point,
                        "volume_min": si.volume_min, "volume_max": si.volume_max,
                        "volume_step": si.volume_step,
                        "trade_mode": si.trade_mode, "filling_flags": si.filling_mode,
                        "stops_level_points": getattr(si, "trade_stops_level", None)},
        "limit_order_check": check,
        "note": "order_check ONLY — nothing sent. Live place/cancel/SL-modify/close "
                "require: (a) market open, (b) Algo Trading enabled in the terminal "
                "(trade_allowed=False at session time), (c) watchdog EA attached.",
    }
    (RESULTS / "order_check_results.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    print("[order-path]", json.dumps(check, indent=2, default=str).encode("ascii", "backslashreplace").decode())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=3.0)
    args = ap.parse_args()

    import MetaTrader5 as mt5
    RESULTS.mkdir(parents=True, exist_ok=True)

    facts = _identity_gate(mt5)
    session = _idle_session(mt5, args.minutes, facts)
    spread = _spread_distribution(mt5)
    orders = _order_path_checks(mt5)
    mt5.shutdown()

    report = {"identity": facts, "session": session,
              "spread_distribution": spread, "order_paths": orders}
    (RESULTS / "phase_d_ops_session.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(f"[done] artifacts in {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
