"""Phase D operator pack — focused unit tests (no live terminal required).

Covers the four instructed areas:
    * config load + loud rejection (locked keys, unknown keys, out-of-band
      risk_fraction);
    * terminal-path identity normalization logic;
    * console renderer formatting with fake state (incl. n/a degradation);
    * backend logger writes the expected files.
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from smc.live.operator_config import (
    ConfigError,
    OperatorConfig,
    normalize_terminal_dir,
)
from smc.live.operator_config import load_operator_config
from smc.live.operator_console import render_startup_banner, render_status_board
from smc.live.run_operator import OperatorSession


# ---------------------------------------------------------------------- #
# Config loading
# ---------------------------------------------------------------------- #
def _write_config(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "op.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_defaults_when_file_is_empty_object(tmp_path):
    cfg = load_operator_config(_write_config(tmp_path, {}))
    assert isinstance(cfg, OperatorConfig)
    assert cfg.dry_run is True
    assert cfg.require_demo is True
    assert cfg.symbol == "XAUUSDm"
    assert cfg.magic == 20260919
    assert cfg.risk_fraction == 0.01


def test_load_valid_overrides(tmp_path):
    cfg = load_operator_config(_write_config(tmp_path, {
        "symbol": "XAUUSDm", "magic": 42, "dry_run": False,
        "risk_fraction": 0.005, "console_refresh_s": 2.5,
    }))
    assert cfg.magic == 42
    assert cfg.dry_run is False
    assert cfg.risk_fraction == 0.005
    assert cfg.console_refresh_s == 2.5


def test_rejects_locked_key_loudly(tmp_path):
    with pytest.raises(ConfigError, match="LOCKED"):
        load_operator_config(_write_config(tmp_path, {"spread_max_atr": 0.5}))
    with pytest.raises(ConfigError, match="LOCKED"):
        load_operator_config(_write_config(tmp_path, {"LOT_MAX_SAFETY": 5.0}))
    with pytest.raises(ConfigError, match="LOCKED"):
        load_operator_config(_write_config(tmp_path, {"be_atr": 1.0}))


def test_rejects_unknown_key(tmp_path):
    with pytest.raises(ConfigError, match="unknown config keys"):
        load_operator_config(_write_config(tmp_path, {"poll_intervall": 1.0}))


def test_rejects_risk_fraction_outside_locked_band(tmp_path):
    with pytest.raises(ConfigError, match="LOCKED band"):
        load_operator_config(_write_config(tmp_path, {"risk_fraction": 0.02}))
    with pytest.raises(ConfigError, match="LOCKED band"):
        load_operator_config(_write_config(tmp_path, {"risk_fraction": 0.001}))


def test_risk_fraction_band_edges_are_accepted(tmp_path):
    cfg = load_operator_config(_write_config(tmp_path, {"risk_fraction": 0.005}))
    assert cfg.risk_fraction == 0.005
    cfg = load_operator_config(_write_config(tmp_path, {"risk_fraction": 0.01}))
    assert cfg.risk_fraction == 0.01


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_operator_config(tmp_path / "nope.json")


def test_malformed_json_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_operator_config(p)


# ---------------------------------------------------------------------- #
# Terminal-dir normalization (identity logic)
# ---------------------------------------------------------------------- #
def test_normalize_terminal_dir_variants():
    base = r"c:\program files\metatrader 5 exness - copy"
    assert normalize_terminal_dir(
        r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe"
    ) == base
    assert normalize_terminal_dir(
        "C:/Program Files/MetaTrader 5 EXNESS - Copy/TERMINAL64.EXE"
    ) == base
    assert normalize_terminal_dir(
        r"C:\Program Files\MetaTrader 5 EXNESS - Copy"
    ) == base
    assert normalize_terminal_dir(
        "C:\\Program Files\\MetaTrader 5 EXNESS - Copy\\"
    ) == base


def test_normalize_keeps_other_exes_distinct():
    assert normalize_terminal_dir(
        r"C:\Program Files\MetaTrader 5 EXNESS - Copy\other.exe"
    ) != normalize_terminal_dir(
        r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe"
    )


# ---------------------------------------------------------------------- #
# Console renderer (fake state)
# ---------------------------------------------------------------------- #
def test_render_full_board_contains_fields():
    board = render_status_board({
        "now_utc": "2026-09-19T20:00:00",
        "terminal_dir": "c:\\program files\\metatrader 5 exness - copy",
        "server": "Exness-MT5Trial15", "account": 474608655, "is_demo": True,
        "symbol": "XAUUSDm", "magic": 20260919, "dry_run": True,
        "hb_seq": 61, "hb_age_s": 0.4, "hb_state": "running",
        "last_bar_utc": "2026-09-18T20:55:00+00:00", "bars_processed": 12,
        "spread": 0.26, "atr": 3.749, "gate_pass": True,
        "gate_detail": "ceil A+<=0.843", "candidates": 3, "blocked": 2,
        "placed": 1, "cancelled": 0, "rejects": 0, "open_positions": 1,
        "kpi": {"decisions": 12, "fills": 1, "trades_closed": 1,
                "missed_bar_episodes": 0, "hard_cancels": 0, "friday_closes": 0},
        "errors": [],
        "session_started_utc": "2026-09-19T19:37:24+00:00",
    })
    for needle in (
        "SMC OPERATOR", "Exness-MT5Trial15", "474608655", "XAUUSDm",
        "20260919", "demo: True", "seq 61", "0.260", "3.749",
        "ceil A+<=0.843", "candidates 3", "placed 1", "open positions 1",
        "decisions 12", "errors   : 0",
    ):
        assert needle in board


def test_render_empty_state_degrades_to_na():
    board = render_status_board({})
    assert board.count("n/a") >= 10
    assert "errors   : 0" in board
    assert "kpi" in board


def test_render_error_tail():
    board = render_status_board({"errors": ["E1", "E2", "E3", "E4"]})
    assert "4 total" in board and "E4" in board and "E1'" not in board


def test_render_startup_banner_contains_fields():
    banner = render_startup_banner(
        {
            "terminal_dir_live": "c:\\program files\\metatrader 5 exness - copy",
            "login": 474608655, "server": "Exness-MT5Trial15",
            "mode": "DEMO", "currency": "USD", "leverage": 2000,
            "trade_allowed": True, "symbol": "XAUUSDm", "magic": 20260919,
            "dry_run": True,
        },
        timeframe="M5", console_refresh_s=900.0, log_dir="logs/phase_d",
    )
    for needle in (
        "____", "PHASE D", "PAPER TRADING ON DEMO", "474608655",
        "Exness-MT5Trial15", "XAUUSDm",
        "20260919", "M5", "900s", "15 min", "dry_run: True", "logs/phase_d",
    ):
        assert needle in banner
    assert banner.isascii()


def test_render_startup_banner_empty_degrades():
    banner = render_startup_banner({})
    assert "n/a" in banner
    assert "PHASE D" in banner
    assert banner.isascii()


# ---------------------------------------------------------------------- #
# Backend logging artifacts (no terminal)
# ---------------------------------------------------------------------- #
def test_operator_session_logger_writes_files(tmp_path):
    cfg = OperatorConfig(log_dir=str(tmp_path / "logs" / "phase_d"))
    session = OperatorSession(cfg)
    session._log("hello operator")
    session._logger.handlers[0].flush()
    events = (tmp_path / "logs" / "phase_d" / "events.log").read_text(encoding="utf-8")
    assert "hello operator" in events


def test_session_state_initialized_from_config(tmp_path):
    cfg = OperatorConfig(log_dir=str(tmp_path / "l2"), magic=7, symbol="XAUUSDm")
    session = OperatorSession(cfg)
    assert session.state["magic"] == 7
    assert session.state["symbol"] == "XAUUSDm"
    assert session.state["dry_run"] is True
    assert session.state["errors"] == []


# ---------------------------------------------------------------------- #
# Console repaint on batch change (display-only; completes the 2026-10-06
# mismatch fix — armed POIs must be visible within one poll, not at the
# next console_refresh_s tick)
# ---------------------------------------------------------------------- #
class _FakeLoop:
    def __init__(self, batches, report):
        self.htf_batches = batches
        self.last_report = report
        self.arm_errors = 0


class _FakeReport:
    armed_count = 2

    def summary(self):
        return {"per_tf": {"H4": {"detected_raw": 23, "merged": 7, "passed": 3}}}


def test_batch_change_forces_console_repaint(tmp_path):
    cfg = OperatorConfig(log_dir=str(tmp_path / "l3"), magic=7)
    session = OperatorSession(cfg)
    session._mt5 = types.SimpleNamespace(symbol_info_tick=lambda s: None)
    session._adapter = types.SimpleNamespace(_candles=None)
    assert session._console_force is False
    session._loop = _FakeLoop(1, _FakeReport())
    session._on_poll(0, connector=None)
    assert session._console_force is True
    assert session.state["htf_batches"] == 1
    assert session.state["htf_armed"] == 2


def test_no_batch_change_leaves_cadence_alone(tmp_path):
    cfg = OperatorConfig(log_dir=str(tmp_path / "l4"), magic=7)
    session = OperatorSession(cfg)
    session._mt5 = types.SimpleNamespace(symbol_info_tick=lambda s: None)
    session._adapter = types.SimpleNamespace(_candles=None)
    session._loop = _FakeLoop(0, None)
    session._on_poll(0, connector=None)
    assert session._console_force is False
