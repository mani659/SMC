"""POST-V1 PHASE D — connection identity check (read-only, no orders).

Lead Architect constraint: bind to EXACTLY this terminal:
    C:\\Program Files\\MetaTrader 5 EXNESS - Copy\\terminal64.exe

The script:
  1. initializes MetaTrader5 with the explicit terminal path (the package
     attaches to the running terminal at that path, or launches it),
  2. prints terminal / version / account / server / company / trade-mode,
  3. resolves the exact XAUUSD symbol variant this broker actually serves
     (bid/ask visibility, digits, point, filling modes, trade mode),
  4. exits NONZERO on any identity mismatch (abort rule).

No orders are placed. This is the gate for everything else in Phase D.

Usage:  python 06_RESEARCH/scripts/phase_d_identity_check.py
"""

from __future__ import annotations

import sys

REQUIRED_TERMINAL = (
    r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe"
)

def main() -> int:
    import MetaTrader5 as mt5

    print("=" * 72)
    print("PHASE D — CONNECTION IDENTITY CHECK (read-only)")
    print("=" * 72)
    print(f"required terminal path : {REQUIRED_TERMINAL}")

    ok = mt5.initialize(path=REQUIRED_TERMINAL)
    if not ok:
        print(f"FATAL: mt5.initialize(path=...) failed: {mt5.last_error()}")
        return 2
    print("mt5.initialize(path=<required path>) -> OK (bound)")

    term = mt5.terminal_info()
    if term is None:
        print(f"FATAL: terminal_info() failed: {mt5.last_error()}")
        mt5.shutdown()
        return 2

    tpath = str(term.path or "")
    print("-" * 72)
    print(f"terminal path (live)   : {tpath}")
    print(f"terminal name          : {term.name}")
    print(f"terminal data path     : {term.data_path}")
    print(f"connected to broker    : {term.connected}")
    print(f"algo trading allowed   : {term.trade_allowed}")
    print(f"MT5 python pkg version : {mt5.version()}")

    identity_ok = True
    # terminal_info().path is the terminal DIRECTORY (no exe suffix);
    # compare it against the required exe's parent directory.
    norm = lambda p: p.replace("/", "\\").strip().lower().rstrip("\\")
    required_dir = norm(REQUIRED_TERMINAL.rsplit("\\", 1)[0])
    live_dir = norm(tpath)
    print(f"required dir  : {required_dir}")
    print(f"live dir      : {live_dir}")
    if live_dir != required_dir:
        print("IDENTITY MISMATCH: live terminal dir != required dir — ABORT")
        identity_ok = False
    else:
        print("terminal-path identity : MATCH")

    acct = mt5.account_info()
    if acct is None:
        print(f"FATAL: account_info() failed: {mt5.last_error()}")
        mt5.shutdown()
        return 2
    modes = {0: "DEMO", 1: "CONTEST", 2: "REAL"}
    mode = modes.get(int(acct.trade_mode), f"UNKNOWN({acct.trade_mode})")
    print("-" * 72)
    print(f"account login          : {acct.login}")
    print(f"account server         : {acct.server}")
    print(f"account company        : {acct.company}")
    print(f"account currency       : {acct.currency}")
    print(f"account leverage       : {acct.leverage}")
    print(f"account mode           : {mode}")
    print(f"account equity         : {acct.equity} {acct.currency}")

    if mode == "REAL":
        print("SAFETY: account is REAL — order-path tests must NOT proceed")
        identity_ok = False

    print("-" * 72)
    print("XAUUSD symbol variants visible on this broker:")
    variants = mt5.symbols_get("*XAUUSD*") or ()
    chosen = None
    for s in variants:
        print(
            f"  - {s.name:<16} visible={s.visible:<5} "
            f"digits={s.digits} point={s.point}"
        )
        if chosen is None and not s.visible:
            chosen = s.name  # remember first hidden variant as fallback
    # Prefer a VISIBLE symbol whose name starts with XAUUSD.
    for s in variants:
        if s.visible and s.name.upper().startswith("XAUUSD"):
            chosen = s.name
            break

    if chosen is None:
        print("FATAL: no XAUUSD variant found on this terminal")
        mt5.shutdown()
        return 2

    print(f"selected symbol        : {chosen}")
    if not mt5.symbol_select(chosen, True):
        print(f"FATAL: symbol_select({chosen}) failed: {mt5.last_error()}")
        mt5.shutdown()
        return 2
    si = mt5.symbol_info(chosen)
    tick = mt5.symbol_info_tick(chosen)
    if si is None or tick is None:
        print(f"FATAL: symbol_info/tick failed: {mt5.last_error()}")
        mt5.shutdown()
        return 2
    spread = tick.ask - tick.bid if tick.ask and tick.bid else float("nan")
    print(f"  digits={si.digits} point={si.point} "
          f"trade_mode={si.trade_mode} filling_flags={si.filling_mode}")
    print(f"  bid={tick.bid} ask={tick.ask} spread={spread:.5f} "
          f"(price units) time={tick.time}")
    print(f"  volume_min={si.volume_min} volume_max={si.volume_max} "
          f"volume_step={si.volume_step}")

    mt5.shutdown()
    print("-" * 72)
    print("PHASE_D_IDENTITY:", "PASS" if identity_ok else "FAIL")
    return 0 if identity_ok else 3


if __name__ == "__main__":
    sys.exit(main())
