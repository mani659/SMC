"""PermissionError(13) hardening tests — fakes only (no MT5, no strategy)."""

from __future__ import annotations

import json
import logging
import os
import time
import types
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from smc.data.mt5_connector import MT5CallError, MT5Connector
from smc.live.heartbeat import (
    HeartbeatWriteError,
    read_heartbeat,
    write_heartbeat,
)
from smc.live.operator_config import OperatorConfig
from smc.live.run_operator import OperatorSession


class _FakeKPI:
    records: list = []

    def counters(self):
        return {}

    def write_jsonl(self, path):
        Path(path).write_text("[]", encoding="utf-8")


class _FakeRunner:
    def __init__(self):
        self.kpi = _FakeKPI()


def _session(tmp_path, *, tick_side_effect=None):
    session = OperatorSession(OperatorConfig(
        terminal_path=r"C:\MT5\terminal64.exe",
        log_dir=str(tmp_path / "logs"),
        magic=7,
        console_mode="event",
        alive_interval_s=0.0,
        console_refresh_s=5.0,
    ))
    session._runner = _FakeRunner()
    session._adapter = types.SimpleNamespace(_candles=None)
    session._mt5 = types.SimpleNamespace(
        symbol_info_tick=Mock(return_value=None),
        positions_get=Mock(return_value=()),
        last_error=Mock(return_value=(5, "Access is denied")),
    )
    if tick_side_effect is not None:
        session._mt5.symbol_info_tick.side_effect = tick_side_effect
    return session


def test_mt5_copy_rates_permission_error_has_operation_path_and_recovery(caplog):
    mt5 = types.SimpleNamespace(
        last_error=Mock(return_value=(5, "Access is denied")),
        copy_rates_from_pos=Mock(
            side_effect=[PermissionError(13, "Access is denied"), "rates"]
        ),
    )
    connector = MT5Connector(terminal_path=r"C:\MT5\terminal64.exe")
    with patch.object(MT5Connector, "_mt5", staticmethod(lambda: mt5)):
        with caplog.at_level(logging.DEBUG, logger="smc.data.mt5_connector"):
            with pytest.raises(MT5CallError) as caught:
                connector.copy_rates("XAUUSDm", 5, 0, 10)
            assert caught.value.operation == "copy_rates_from_pos"
            assert caught.value.terminal_path == r"C:\MT5\terminal64.exe"
            assert isinstance(caught.value.__cause__, PermissionError)
            assert connector.copy_rates("XAUUSDm", 5, 0, 10) == "rates"

    assert "operation=copy_rates_from_pos" in caplog.text
    assert repr(r"C:\MT5\terminal64.exe") in caplog.text
    assert "last_error=(5, 'Access is denied')" in caplog.text
    assert "MT5 call recovered operation=copy_rates_from_pos" in caplog.text


def test_operator_poll_deduplicates_permission_and_continues(tmp_path):
    tick = types.SimpleNamespace(bid=100.0, ask=100.2)
    session = _session(
        tmp_path,
        tick_side_effect=[
            PermissionError(13, "Access is denied"),
            PermissionError(13, "Access is denied"),
            tick,
        ],
    )
    session._loop = types.SimpleNamespace(htf_batches=0)

    session._on_poll(0, connector=None)
    session._on_poll(0, connector=None)
    session._on_poll(0, connector=None)

    assert session.state["polls"] == 3
    assert len(session.state["errors"]) == 1
    assert session.state["spread"] == pytest.approx(0.2)
    assert session._mt5.symbol_info_tick.call_count == 3
    events = (tmp_path / "logs" / "events.log").read_text(encoding="utf-8")
    assert "operation=mt5.symbol_info_tick" in events
    assert repr(r"C:\MT5\terminal64.exe") in events
    assert "MT5 CALL RECOVERED operation=mt5.symbol_info_tick" in events


def test_operator_positions_read_is_called_once_and_unknown_on_error(tmp_path):
    session = _session(tmp_path)
    session._loop = types.SimpleNamespace(htf_batches=0)
    session._mt5.positions_get.side_effect = PermissionError(
        13, "Access is denied"
    )

    session._on_poll(0, connector=object())

    assert session._mt5.positions_get.call_count == 1
    assert session.state["open_positions"] is None
    assert len(session.state["errors"]) == 1


def test_poll_error_is_counted_once_and_successful_poll_resumes(
    tmp_path, monkeypatch
):
    session = _session(tmp_path)
    session._identity = {}
    session._heartbeat = types.SimpleNamespace(
        sequence=1, state="running", _last_unix=1_000_000
    )
    connector = types.SimpleNamespace(shutdown=Mock())
    session.identity_check = lambda: {}
    session._build_stack = lambda: connector
    session._loop = types.SimpleNamespace(
        start=lambda: True,
        run_once=Mock(side_effect=[
            MT5CallError(
                "copy_rates_from_pos",
                session.config.terminal_path,
                PermissionError(13, "Access is denied"),
            ),
            0,
            KeyboardInterrupt,
        ]),
        stop=lambda: None,
    )
    monkeypatch.setattr("smc.live.run_operator.time.sleep", lambda _seconds: None)

    session.run(max_seconds=10)

    assert session._loop.run_once.call_count == 3
    assert session.state["polls"] == 1
    assert len(session.state["errors"]) == 1
    events = (tmp_path / "logs" / "events.log").read_text(encoding="utf-8")
    assert "POLL RECOVERED" in events
    assert "copy_rates_from_pos" in events
    assert "Access is denied" in events


def test_identity_connect_logs_terminal_and_pid_and_initializes_once(
    tmp_path,
):
    terminal_path = r"C:\MT5\terminal64.exe"
    mt5 = types.SimpleNamespace(
        initialize=Mock(return_value=True),
        terminal_info=Mock(return_value=types.SimpleNamespace(
            path=r"C:\MT5",
            data_path=str(tmp_path / "terminal-data"),
            connected=True,
            trade_allowed=True,
        )),
        account_info=Mock(return_value=types.SimpleNamespace(
            trade_mode=0,
            login=12345,
            server="Broker-Demo",
            company="Broker",
            currency="USD",
            leverage=100,
        )),
        version=Mock(return_value=(5, 0, 0)),
        symbol_select=Mock(return_value=True),
        last_error=Mock(return_value=(0, "ok")),
        shutdown=Mock(),
    )
    session = OperatorSession(OperatorConfig(
        terminal_path=terminal_path,
        log_dir=str(tmp_path / "logs"),
        magic=7,
    ))
    with patch.object(MT5Connector, "_mt5", staticmethod(lambda: mt5)):
        facts = session.identity_check()
        assert session._connector.connect() is True

    mt5.initialize.assert_called_once_with(path=terminal_path)
    assert facts["mt5_python_pid"] > 0
    assert json.loads(
        (tmp_path / "logs" / "identity.json").read_text(encoding="utf-8")
    )["mt5_python_pid"] == facts["mt5_python_pid"]
    events = (tmp_path / "logs" / "events.log").read_text(encoding="utf-8")
    assert repr(terminal_path) in events
    assert f"python_pid={facts['mt5_python_pid']}" in events


def test_identity_initialize_permission_error_aborts_with_context(tmp_path):
    terminal_path = r"C:\MT5\terminal64.exe"
    mt5 = types.SimpleNamespace(
        initialize=Mock(side_effect=PermissionError(13, "Access is denied")),
        last_error=Mock(return_value=(5, "Access is denied")),
    )
    session = OperatorSession(OperatorConfig(
        terminal_path=terminal_path,
        log_dir=str(tmp_path / "logs"),
        magic=7,
    ))

    with patch.object(MT5Connector, "_mt5", staticmethod(lambda: mt5)):
        with pytest.raises(SystemExit, match="terminal identity call failed"):
            session.identity_check()

    events = (tmp_path / "logs" / "events.log").read_text(encoding="utf-8")
    assert "initialize" in events
    assert repr(terminal_path) in events
    assert "Access is denied" in events


def test_heartbeat_write_error_includes_target_and_operation(
    tmp_path, monkeypatch
):
    target = tmp_path / "MQL5" / "Files" / "smc_heartbeat.txt"

    def denied(self, *args, **kwargs):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(Path, "write_text", denied)
    with pytest.raises(HeartbeatWriteError) as caught:
        write_heartbeat(target, 1_000_000, 1)
    assert "write temporary file" in str(caught.value)
    assert str(target) in str(caught.value)


def test_heartbeat_read_permission_error_is_logged_and_fail_closed(
    tmp_path, monkeypatch, caplog
):
    target = tmp_path / "MQL5" / "Files" / "smc_heartbeat.txt"

    def denied(self, *args, **kwargs):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(Path, "read_text", denied)
    with caplog.at_level(logging.ERROR, logger="smc.live.heartbeat"):
        assert read_heartbeat(target) is None
        assert read_heartbeat(target) is None

    assert caplog.text.count("heartbeat read failed operation=open") == 1
    assert str(target) in caplog.text


def test_fallback_heartbeat_is_not_shown_as_watchdog_healthy(tmp_path, capsys):
    session = _session(tmp_path)
    session._heartbeat = types.SimpleNamespace(
        sequence=2, state="running", _last_unix=1_000_000
    )
    session._heartbeat_ea_readable = False

    session._publish_console()

    assert "running (EA path unconfirmed)" in capsys.readouterr().out


def test_heartbeat_runtime_write_failure_stops_operator(tmp_path):
    session = _session(tmp_path)
    session._console_mode = "board"
    session._identity = {}
    session._heartbeat = types.SimpleNamespace(
        sequence=1, state="running", _last_unix=1_000_000
    )
    session._loop = types.SimpleNamespace(
        start=lambda: True,
        run_once=lambda: (_ for _ in ()).throw(
            HeartbeatWriteError(
                "heartbeat write temporary file failed "
                "target=C:/data/MQL5/Files/smc_heartbeat.txt"
            )
        ),
        stop=lambda: None,
    )
    connector = types.SimpleNamespace(shutdown=Mock())
    session.identity_check = lambda: {}
    session._build_stack = lambda: connector

    with pytest.raises(SystemExit, match="heartbeat publication failed"):
        session.run(max_seconds=1)

    assert any("C:/data/MQL5/Files/smc_heartbeat.txt" in error
               for error in session.state["errors"])
    assert connector.shutdown.call_count == 1


# --------------------------------------------------------------------------- #
# Windows EA coexistence: atomic replace vs an active EA read lock
# (live evidence 2026-10-08: [WinError 5] on smc_heartbeat.txt.tmp -> target)
# --------------------------------------------------------------------------- #
def test_heartbeat_transient_replace_lock_recovers_via_retry(
    tmp_path, monkeypatch, caplog
):
    target = tmp_path / "MQL5" / "Files" / "smc_heartbeat.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    real_replace = os.replace
    calls = {"n": 0}

    def flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError(13, "Access is denied")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    with caplog.at_level(logging.WARNING, logger="smc.live.heartbeat"):
        write_heartbeat(target, 1_000_000, 7)

    assert calls["n"] >= 2                    # retried, then succeeded
    assert "1000000 7" in target.read_text(encoding="ascii")
    assert "state=running" in target.read_text(encoding="ascii")
    assert "wrote in place" not in caplog.text  # rename won on retry


def test_heartbeat_persistent_replace_lock_falls_back_in_place(
    tmp_path, monkeypatch, caplog
):
    target = tmp_path / "MQL5" / "Files" / "smc_heartbeat.txt"
    target.parent.mkdir(parents=True, exist_ok=True)

    def always_denied(src, dst):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(os, "replace", always_denied)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    with caplog.at_level(logging.WARNING, logger="smc.live.heartbeat"):
        write_heartbeat(target, 1_000_111, 8)

    text = target.read_text(encoding="ascii")
    assert "1000111 8" in text
    assert "state=running" in text
    assert "wrote in place" in caplog.text
    assert str(target) in caplog.text
    assert not (target.parent / "smc_heartbeat.txt.tmp").exists()


def test_heartbeat_total_publish_failure_raises_after_all_strategies(
    tmp_path, monkeypatch
):
    target = tmp_path / "MQL5" / "Files" / "smc_heartbeat.txt"
    target.parent.mkdir(parents=True, exist_ok=True)

    def always_denied(src, dst):
        raise PermissionError(13, "Access is denied")

    def inplace_denied(_target, _payload):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(os, "replace", always_denied)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        "smc.live.heartbeat._write_in_place", inplace_denied
    )
    with pytest.raises(HeartbeatWriteError) as caught:
        write_heartbeat(target, 1_000_000, 1)

    message = str(caught.value)
    assert str(target) in message
    assert "replace_error" in message
    assert "inplace_error" in message
