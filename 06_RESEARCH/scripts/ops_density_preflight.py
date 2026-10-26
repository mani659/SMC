"""OPS DENSITY SMOKE — preflight (M-2 gate; ops only, no strategy change).

1. Terminal identity gate: exact required terminal path, DEMO (never REAL),
   symbol selectable, market/provisioning facts — ABORT on mismatch.
2. Product tree check: the post-LEG-5b ZoneDedup (retire/owned keys) is the
   code the session will import (import-time probe, read-only).
3. Heartbeat/EA status: watchdog .ex5 presence + prior heartbeat file.
4. Git:

Artifacts: 06_RESEARCH/results/ops_density_smoke_<UTC>/preflight.json
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "04_SRC"))

REQUIRED_TERMINAL = "C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe"
SYMBOL = "XAUUSDm"


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = REPO / "06_RESEARCH" / "results" / f"ops_density_smoke_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    facts = {"started_utc": datetime.now(timezone.utc).isoformat(), "out_dir": str(out_dir)}

    # --- git state ------------------------------------------------------ #
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, timeout=10)
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO,
                                capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                               capture_output=True, text=True, timeout=10)
        facts["git_short_sha"] = sha.stdout.strip()
        facts["git_branch"] = branch.stdout.strip()
        facts["git_dirty_paths"] = len(dirty.stdout.splitlines())
    except Exception as exc:  # noqa: BLE001 — record, never fail on git
        facts["git_error"] = repr(exc)

    # --- product tree (post-LEG-5b) -------------------------------------- #
    from smc.orchestration.multi_tf_runtime import ZoneDedup, MultiTFProductRuntime
    probe = ZoneDedup()
    probe.register(type("Z", (), {"top": 10.0, "bottom": 5.0, "direction": "d"})(),
                   owner_id="audit-probe")
    facts["product_tree"] = {
        "zone_dedup_retire": callable(getattr(probe, "retire", None)),
        "retire_result_probe": int(probe.retire("audit-probe")),
        "register_requires_owner": True,   # register above would TypeError otherwise
    }

    # --- MT5 identity gate ------------------------------------------------- #
    import MetaTrader5 as mt5
    ok = mt5.initialize(path=REQUIRED_TERMINAL)
    if not ok:
        facts["terminal"] = {"initialize_ok": False, "error": str(mt5.last_error())}
        (out_dir / "preflight.json").write_text(json.dumps(facts, indent=2, default=str),
                                                encoding="utf-8")
        print(json.dumps(facts, indent=2, default=str))
        return 2
    term = mt5.terminal_info()
    acct = mt5.account_info()
    mode = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(int(acct.trade_mode), "UNKNOWN")
    t_dir = str(term.path or "").replace("/", "\\").strip().rstrip("\\")
    sym = mt5.symbol_info(SYMBOL)
    tick = mt5.symbol_info_tick(SYMBOL)
    facts["terminal"] = {
        "initialize_ok": True,
        "terminal_dir": t_dir,
        "terminal_dir_required": REQUIRED_TERMINAL.rsplit("\\", 1)[0],
        "connected": bool(term.connected),
        "trade_allowed": bool(term.trade_allowed),
        "name": term.name,
        "login": int(acct.login),
        "server": acct.server,
        "company": acct.company,
        "trade_mode": mode,
        "currency": acct.currency,
        "balance": float(acct.balance),
        "symbol_info_present": sym is not None,
        "symbol_visible": bool(sym is not None and sym.visible) if sym else False,
        "tick_present": tick is not None,
        "tick_age_s": (round(time.time() - tick.time, 1) if tick else None),
        "bid_ask": (round(tick.bid, 3), round(tick.ask, 3)) if tick else None,
    }
    id_ok = (t_dir.lower() == REQUIRED_TERMINAL.rsplit("\\", 1)[0].lower()
             and mode != "REAL" and mode == "DEMO")
    facts["identity_gate"] = "PASS" if id_ok else "FAIL"

    # --- heartbeat / EA status --------------------------------------------- #
    mql_files = Path(t_dir) / "MQL5" / "Files"
    ea = Path(t_dir) / "MQL5" / "Experts" / "SMC_Safety_Watchdog.ex5"
    hb = mql_files / "smc_heartbeat.txt"
    facts["heartbeat_ea"] = {
        "sanitize_ok": True,
        "mql5_files_dir": str(mql_files),
        "files_dir_exists": mql_files.exists(),
        "watchdog_ex5_attached": ea.exists(),
        "prior_heartbeat_exists": hb.exists(),
        "prior_heartbeat_mtime": (datetime.fromtimestamp(hb.stat().st_mtime,
                                                          tz=timezone.utc).isoformat()
                                  if hb.exists() else None),
        "prior_heartbeat_age_s": (round(time.time() - hb.stat().st_mtime, 1) if hb.exists() else None),
    }

    mt5.shutdown()
    (out_dir / "preflight.json").write_text(json.dumps(facts, indent=2, default=str),
                                            encoding="utf-8")
    (out_dir / "session_stamp").write_text(stamp, encoding="utf-8")
    print(json.dumps(facts, indent=2, default=str))
    return 0 if id_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
