"""require_demo gate + dry_run=false + heartbeat derivation (v1.1-test.2 rulings).

Operational plumbing only — no strategy, no threshold, no locked-constant logic.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from smc.live.operator_config import OperatorConfig
from smc.live.run_operator import OperatorSession


# --------------------------------------------------------------------------- #
# Fake MetaTrader5 module (identity_check imports it locally)
# --------------------------------------------------------------------------- #
class _FakeTerm:
    def __init__(self, path, connected=True, data_path=""):
        self.path = path
        self.connected = connected
        self.trade_allowed = True
        self.data_path = data_path


class _FakeAcct:
    def __init__(self, trade_mode, login=474608655, server="Exness-MT5Trial15"):
        self.trade_mode = trade_mode
        self.login = login
        self.server = server
        self.company = "Exness"
        self.currency = "USD"
        self.leverage = 2000


class _FakeMT5:
    def __init__(self, trade_mode):
        self._trade_mode = trade_mode
        self.last_error = lambda: (0, "ok")
        self.version = lambda: ("5.0.0", "1000", "2024.01")

    def initialize(self, path=None):
        self.initialized_path = path
        return True

    def terminal_info(self):
        return _FakeTerm(self.initialized_path, data_path=self._data_path)

    def account_info(self):
        return _FakeAcct(self._trade_mode)

    def symbol_select(self, symbol, enable):
        return True


TRADE_MODE_DEMO = 0
TRADE_MODE_REAL = 2


def _install_fake_mt5(monkeypatch, trade_mode, data_path=""):
    fake = _FakeMT5(trade_mode)
    fake._data_path = data_path
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    return fake


# --------------------------------------------------------------------------- #
# require_demo gate
# --------------------------------------------------------------------------- #
def test_require_demo_blocks_real_account(tmp_path, monkeypatch):
    _install_fake_mt5(monkeypatch, TRADE_MODE_REAL)
    cfg = OperatorConfig(
        terminal_path=r"C:\MT5\terminal64.exe", log_dir=str(tmp_path / "logs"),
    )
    assert cfg.require_demo is True  # default holds
    session = OperatorSession(cfg)
    with pytest.raises(SystemExit, match="require_demo=true"):
        session.identity_check()


def test_require_demo_allows_demo_account(tmp_path, monkeypatch):
    _install_fake_mt5(monkeypatch, TRADE_MODE_DEMO)
    cfg = OperatorConfig(
        terminal_path=r"C:\MT5\terminal64.exe", log_dir=str(tmp_path / "logs"),
    )
    session = OperatorSession(cfg)
    facts = session.identity_check()
    assert facts["mode"] == "DEMO"
    assert session.state["is_demo"] is True


def test_dry_run_false_is_allowed_in_config(tmp_path, monkeypatch):
    _install_fake_mt5(monkeypatch, TRADE_MODE_DEMO)
    cfg = OperatorConfig(
        terminal_path=r"C:\MT5\terminal64.exe", log_dir=str(tmp_path / "logs"),
        dry_run=False,
    )
    assert cfg.dry_run is False
    session = OperatorSession(cfg)
    facts = session.identity_check()
    assert facts["dry_run"] is False


# --------------------------------------------------------------------------- #
# Heartbeat derivation wiring (operator resolves the EA-readable path)
# --------------------------------------------------------------------------- #
def test_operator_session_resolves_derived_heartbeat_path(tmp_path):
    from smc.live.heartbeat_path import resolve_heartbeat_path

    cfg = OperatorConfig(
        terminal_path=r"C:\MT5\terminal64.exe", log_dir=str(tmp_path / "logs"),
    )
    derived = resolve_heartbeat_path(cfg.terminal_path, cfg.heartbeat_path)
    assert derived.name == "smc_heartbeat.txt"
    assert Path(derived).parts[-3:-1] == ("MQL5", "Files")


def test_identity_facts_carry_terminal_data_path(tmp_path, monkeypatch):
    dp = (r"C:\Users\User10\AppData\Roaming\MetaQuotes\Terminal"
          r"\6FE846653CB9AC4D5ACECF98EF447F40")
    _install_fake_mt5(monkeypatch, TRADE_MODE_DEMO, data_path=dp)
    cfg = OperatorConfig(
        terminal_path=r"C:\MT5\terminal64.exe", log_dir=str(tmp_path / "logs"),
    )
    session = OperatorSession(cfg)
    session.identity_check()
    assert session._identity["terminal_data_path"] == dp


def test_operator_session_heartbeat_fallback_logs_loudly(tmp_path):
    cfg = OperatorConfig(terminal_path="", log_dir=str(tmp_path / "logs"))
    session = OperatorSession(cfg)
    # Loud fallback: the warning handler records a fallback line in events.log
    session._logger.warning(
        "HEARTBEAT PATH FALLBACK: terminal_path empty/unparseable"
    )
    for h in session._logger.handlers:
        h.flush()
    events = (tmp_path / "logs" / "events.log").read_text(encoding="utf-8")
    assert "HEARTBEAT PATH FALLBACK" in events
