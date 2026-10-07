"""Phase D order-path drill (demo ONLY, dedicated magic, market-open only).

Exercises the broker order paths the backtest assumes: limit place ->
cancel, market fill -> SL/TP bracket -> SL-modify preserves TP -> close.
Every step is logged JSONL; any failure force-flattens OUR magic scope
(cancel own pendings + close own positions) before exiting nonzero.

Safety: aborts unless terminal-dir identity MATCHES the required Copy
terminal AND the account is DEMO AND symbol is XAUUSDm. Dry-run default
(order_check payload validation only); --live performs real demo sends
(Lead Architect authorized for trade_allowed + open-market sessions).

Usage:
  python 06_RESEARCH/scripts/phase_d_order_drill.py [--live]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe"
SYMBOL, MAGIC = "XAUUSDm", 20260919
VOLUME = 0.01
DEVIATION = 20


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Drill:
    def __init__(self, dry_run: bool, log_path: Path) -> None:
        self.dry_run = dry_run
        self.log_path = log_path
        self._fh = open(log_path, "w", encoding="utf-8")
        self.steps: list[str] = []

    def log(self, event: str, **fields) -> None:
        rec = {"ts": utcnow(), "event": event, **fields}
        self._fh.write(json.dumps(rec) + "\n")
        self._fh.flush()
        self.steps.append(event)
        print(f"[drill] {event} " + " ".join(
            f"{k}={v}" for k, v in fields.items()), flush=True)

    def close(self) -> None:
        self._fh.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="perform real demo sends (default: order_check only)")
    args = ap.parse_args()
    import MetaTrader5 as mt5

    out = (REPO_ROOT / "06_RESEARCH" / "results" / "phase_d_ops"
           / f"order_drill_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    drill = Drill(dry_run=not args.live, log_path=out)
    try:
        if not mt5.initialize(path=TERMINAL):
            drill.log("abort", reason="initialize failed",
                      error=str(mt5.last_error()))
            return 3
        term, acct = mt5.terminal_info(), mt5.account_info()
        live_dir = str(term.path or "").replace("/", "\\").rstrip("\\").lower()
        mode = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(int(acct.trade_mode))
        drill.log("identity", live_dir=live_dir, mode=mode,
                  login=int(acct.login), trade_allowed=bool(term.trade_allowed))
        if "exness - copy" not in live_dir or mode != "DEMO":
            drill.log("abort", reason="identity gate")
            return 3
        if not mt5.symbol_select(SYMBOL, True):
            drill.log("abort", reason="symbol_select failed")
            return 3
        pre_pos = mt5.positions_get(symbol=SYMBOL) or []
        pre_ord = mt5.orders_get(symbol=SYMBOL) or []
        own_pre = [p for p in pre_pos if p.magic == MAGIC]
        own_pre_o = [o for o in pre_ord if o.magic == MAGIC]
        drill.log("precheck", open_positions=len(pre_pos),
                  own_magic_positions=len(own_pre),
                  pending=len(pre_ord), own_magic_pending=len(own_pre_o))
        if own_pre or own_pre_o:
            drill.log("abort", reason="own magic scope not flat")
            return 3

        tick = mt5.symbol_info_tick(SYMBOL)
        info = mt5.symbol_info(SYMBOL)
        digits = int(info.digits)
        limit_price = round(tick.bid - 5.0, digits)
        sl0 = round(limit_price - 3.0, digits)
        tp0 = round(limit_price + 6.0, digits)

        def send(request: dict, step: str):
            if drill.dry_run:
                check = mt5.order_check(request)
                drill.log(step + "_check", retcode=check.retcode,
                          comment=str(check.comment))
                return None, check
            result = mt5.order_send(request)
            drill.log(step + "_send", retcode=result.retcode,
                      ticket=result.order,
                      comment=str(result.comment))
            return result, None

        # STEP 1: limit place (far from market — must NOT fill immediately).
        req = {"action": mt5.TRADE_ACTION_PENDING, "symbol": SYMBOL,
               "volume": VOLUME, "type": mt5.ORDER_TYPE_BUY_LIMIT,
               "price": limit_price, "sl": sl0, "tp": tp0,
               "deviation": DEVIATION, "magic": MAGIC,
               "comment": "phased-drill-limit",
               "type_time": mt5.ORDER_TIME_GTC,
               "type_filling": mt5.ORDER_FILLING_IOC}
        res, check = send(req, "limit_place")
        if drill.dry_run:
            assert check.retcode == 0, f"order_check failed: {check.comment}"
            drill.log("done_dry_run")
            return 0
        assert res.retcode == 10009, f"place failed: {res.comment}"
        time.sleep(2)
        pend = [o for o in (mt5.orders_get(symbol=SYMBOL) or [])
                if o.magic == MAGIC]
        assert pend, "placed limit not visible"
        drill.log("limit_visible", tickets=[o.ticket for o in pend])

        # STEP 2: cancel it.
        cancel = {"action": mt5.TRADE_ACTION_REMOVE, "symbol": SYMBOL,
                  "order": pend[0].ticket, "magic": MAGIC,
                  "comment": "phased-drill-cancel"}
        res = mt5.order_send(cancel)
        drill.log("limit_cancel", retcode=res.retcode,
                  comment=str(res.comment))
        assert res.retcode == 10009, f"cancel failed: {res.comment}"
        time.sleep(1)
        assert not [o for o in (mt5.orders_get(symbol=SYMBOL) or [])
                    if o.magic == MAGIC], "pending survived cancel"

        # STEP 3: market fill 0.01 for the modify/close path.
        tick = mt5.symbol_info_tick(SYMBOL)
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL,
               "volume": VOLUME, "type": mt5.ORDER_TYPE_BUY,
               "price": tick.ask, "deviation": DEVIATION, "magic": MAGIC,
               "comment": "phased-drill-market",
               "type_time": mt5.ORDER_TIME_GTC,
               "type_filling": mt5.ORDER_FILLING_IOC}
        res = mt5.order_send(req)
        drill.log("market_fill", retcode=res.retcode,
                  deal=res.deal, price=res.price)
        assert res.retcode == 10009, f"market fill failed: {res.comment}"
        time.sleep(1)
        poss = [p for p in (mt5.positions_get(symbol=SYMBOL) or [])
                if p.magic == MAGIC]
        assert poss, "filled position not visible"
        pos, pt = poss[0], poss[0].ticket
        drill.log("position_open", ticket=pt, entry=pos.price_open)

        # STEP 4: bracket SL/TP, then SL-modify and verify TP preserved.
        sl1 = round(pos.price_open - 2.0, digits)
        tp1 = round(pos.price_open + 4.0, digits)
        mod = {"action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
               "position": pt, "sl": sl1, "tp": tp1, "magic": MAGIC,
               "comment": "phased-drill-bracket"}
        res = mt5.order_send(mod)
        drill.log("sltp_set", retcode=res.retcode, comment=str(res.comment))
        assert res.retcode == 10009, f"sltp failed: {res.comment}"
        sl2 = round(pos.price_open - 1.0, digits)
        mod2 = {"action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                "position": pt, "sl": sl2, "tp": tp1, "magic": MAGIC,
                "comment": "phased-drill-slmodify"}
        res = mt5.order_send(mod2)
        after = [p for p in mt5.positions_get(symbol=SYMBOL)
                 if p.ticket == pt][0]
        drill.log("sl_modify", retcode=res.retcode, sl=after.sl, tp=after.tp)
        assert res.retcode == 10009, f"sl modify failed: {res.comment}"
        assert abs(after.tp - tp1) < 1e-9, "TP NOT PRESERVED by SL modify"
        assert abs(after.sl - sl2) < 1e-9, "SL modify did not apply"
        drill.log("tp_preserved", tp=after.tp)

        # STEP 5: close at market, verify flat.
        tick = mt5.symbol_info_tick(SYMBOL)
        close = {"action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL,
                 "volume": VOLUME, "type": mt5.ORDER_TYPE_SELL,
                 "position": pt, "price": tick.bid, "deviation": DEVIATION,
                 "magic": MAGIC, "comment": "phased-drill-close",
                 "type_time": mt5.ORDER_TIME_GTC,
                 "type_filling": mt5.ORDER_FILLING_IOC}
        res = mt5.order_send(close)
        drill.log("close", retcode=res.retcode, comment=str(res.comment))
        assert res.retcode == 10009, f"close failed: {res.comment}"
        time.sleep(1)
        rest_p = [p for p in (mt5.positions_get(symbol=SYMBOL) or [])
                  if p.magic == MAGIC]
        rest_o = [o for o in (mt5.orders_get(symbol=SYMBOL) or [])
                  if o.magic == MAGIC]
        drill.log("flat_check", positions=len(rest_p), pending=len(rest_o))
        assert not rest_p and not rest_o, "scope not flat after drill"
        drill.log("done_live_flat")
        return 0
    except AssertionError as exc:
        drill.log("FAIL", error=str(exc))
        return 1
    finally:
        try:
            # Force-flatten OUR magic scope on any path (paranoia, demo-safe).
            for o in (mt5.orders_get(symbol=SYMBOL) or []):
                if o.magic == MAGIC:
                    mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE,
                                    "symbol": SYMBOL, "order": o.ticket})
            for p in (mt5.positions_get(symbol=SYMBOL) or []):
                if p.magic == MAGIC:
                    t = mt5.symbol_info_tick(SYMBOL)
                    mt5.order_send({
                        "action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL,
                        "volume": p.volume,
                        "type": (mt5.ORDER_TYPE_SELL
                                 if p.type == mt5.POSITION_TYPE_BUY
                                 else mt5.ORDER_TYPE_BUY),
                        "position": p.ticket, "price": t.bid,
                        "deviation": DEVIATION, "magic": MAGIC,
                        "comment": "phased-drill-cleanup",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC})
            drill.log("cleanup_scanned")
        except Exception as exc:  # noqa: BLE001 — shutdown must not mask results
            drill.log("cleanup_error", error=str(exc))
        finally:
            mt5.shutdown()
            drill.close()


if __name__ == "__main__":
    raise SystemExit(main())
