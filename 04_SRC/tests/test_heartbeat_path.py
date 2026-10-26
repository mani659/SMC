"""Heartbeat path resolution tests (EA-readable default under terminal MQL5/Files).

Operational plumbing only — no strategy, no threshold, no locked-constant logic.
"""

from __future__ import annotations

import logging
from pathlib import Path

from smc.live.heartbeat_path import (
    EA_READABLE_DEFAULT_FILENAME,
    HEARTBEAT_FILENAME,
    data_folder_heartbeat_path,
    ea_readable_heartbeat_dir,
    ea_readable_heartbeat_path,
    heartbeat_path_candidates,
    probe_writable,
    resolve_heartbeat_path,
    terminal_dir,
)


# --------------------------------------------------------------------------- #
# terminal_dir
# --------------------------------------------------------------------------- #
def test_terminal_dir_accepts_terminal64_exe_paths():
    cases = {
        r"C:\Program Files\MetaTrader 5\terminal64.exe": Path(
            r"C:\Program Files\MetaTrader 5"
        ),
        r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe": Path(
            r"C:\Program Files\MetaTrader 5 EXNESS - Copy"
        ),
        r"D:\MT5\terminal64.exe": Path(r"D:\MT5"),
    }
    for raw, expected in cases.items():
        assert terminal_dir(raw) == expected


def test_terminal_dir_falls_back_to_path_when_not_terminal_exe():
    assert terminal_dir(r"C:\some\dir\container") == Path(r"C:\some\dir\container")


def test_terminal_dir_returns_none_for_empty():
    assert terminal_dir("") is None


# --------------------------------------------------------------------------- #
# ea_readable_heartbeat_dir / ea_readable_heartbeat_path
# --------------------------------------------------------------------------- #
def test_ea_readable_heartbeat_path_under_terminal():
    assert ea_readable_heartbeat_path(
        r"C:\Program Files\MetaTrader 5\terminal64.exe"
    ) == Path(r"C:\Program Files\MetaTrader 5\MQL5\Files\smc_heartbeat.txt")


def test_ea_readable_heartbeat_path_exness_copy_variant():
    assert ea_readable_heartbeat_path(
        r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe"
    ) == Path(
        r"C:\Program Files\MetaTrader 5 EXNESS - Copy\MQL5\Files\smc_heartbeat.txt")


def test_ea_readable_heartbeat_path_returns_none_for_unparseable_terminal():
    assert ea_readable_heartbeat_path("") is None
    assert ea_readable_heartbeat_path(None) is None


def test_ea_readable_heartbeat_dir_matches_path_parent_logic():
    assert ea_readable_heartbeat_dir(
        r"C:\Program Files\MetaTrader 5\terminal64.exe"
    ) == Path(r"C:\Program Files\MetaTrader 5\MQL5\Files")


# --------------------------------------------------------------------------- #
# resolve_heartbeat_path policy
# --------------------------------------------------------------------------- #
def test_terminal_path_wins_over_explicit_and_default():
    got = resolve_heartbeat_path(
        terminal_path=r"C:\Program Files\MetaTrader 5\terminal64.exe",
        explicit_heartbeat_path=r"C:\explicit\heartbeat.txt",
    )
    assert got == Path(
        r"C:\Program Files\MetaTrader 5\MQL5\Files\smc_heartbeat.txt")


def test_explicit_heartbeat_path_when_no_terminal_path():
    got = resolve_heartbeat_path(
        terminal_path="", explicit_heartbeat_path=r"C:\explicit\heartbeat.txt",
    )
    assert got == Path(r"C:\explicit\heartbeat.txt")


def test_default_fallback_when_no_terminal_and_no_explicit():
    got = resolve_heartbeat_path(terminal_path=None, explicit_heartbeat_path=None)
    assert got == Path("logs/phase_d/heartbeat.txt")


def test_default_fallback_is_project_log_local():
    got = resolve_heartbeat_path(terminal_path="", explicit_heartbeat_path="")
    assert got.name == "heartbeat.txt"
    assert got.parts[-2:] == ("phase_d", "heartbeat.txt")


def test_default_filename_matches_ea_input():
    assert HEARTBEAT_FILENAME == "smc_heartbeat.txt"
    assert EA_READABLE_DEFAULT_FILENAME == HEARTBEAT_FILENAME


# --------------------------------------------------------------------------- #
# data-folder derivation (installed / non-portable terminals — authoritative)
# --------------------------------------------------------------------------- #
def test_data_folder_heartbeat_path_under_appdata():
    got = data_folder_heartbeat_path(
        r"C:\Users\User10\AppData\Roaming\MetaQuotes\Terminal"
        r"\6FE846653CB9AC4D5ACECF98EF447F40")
    assert got == Path(
        r"C:\Users\User10\AppData\Roaming\MetaQuotes\Terminal"
        r"\6FE846653CB9AC4D5ACECF98EF447F40\MQL5\Files\smc_heartbeat.txt")


def test_data_folder_heartbeat_path_none_for_empty():
    assert data_folder_heartbeat_path("") is None
    assert data_folder_heartbeat_path(None) is None


def test_data_path_wins_over_install_dir_and_config():
    got = resolve_heartbeat_path(
        terminal_path=r"C:\Program Files\MetaTrader 5\terminal64.exe",
        explicit_heartbeat_path=r"C:\explicit\heartbeat.txt",
        terminal_data_path=r"C:\Users\User10\AppData\Roaming\MetaQuotes"
                           r"\Terminal\ABC123",
    )
    assert got == Path(
        r"C:\Users\User10\AppData\Roaming\MetaQuotes\Terminal\ABC123"
        r"\MQL5\Files\smc_heartbeat.txt")


def test_install_dir_derivation_used_when_data_path_missing():
    got = resolve_heartbeat_path(
        terminal_path=r"C:\Program Files\MetaTrader 5\terminal64.exe",
        explicit_heartbeat_path=None,
        terminal_data_path="",
    )
    assert got == Path(
        r"C:\Program Files\MetaTrader 5\MQL5\Files\smc_heartbeat.txt")


def test_config_fallback_when_no_data_path_and_no_terminal():
    got = resolve_heartbeat_path(
        terminal_path="", explicit_heartbeat_path="logs/x.txt",
        terminal_data_path="",
    )
    assert got == Path("logs/x.txt")


# --------------------------------------------------------------------------- #
# candidates + write-probe (startup ACL hardening)
# --------------------------------------------------------------------------- #
def test_candidates_order_and_sources():
    cands = heartbeat_path_candidates(
        terminal_path=r"C:\MT5\terminal64.exe",
        explicit_heartbeat_path="logs/x.txt",
        terminal_data_path=r"C:\Users\User10\AppData\Roaming\MetaQuotes"
                           r"\Terminal\ABC123",
    )
    assert [src for src, _ in cands] == [
        "terminal_data_path", "terminal_path", "config", "default"]
    assert cands[-1] == ("default", Path("logs/phase_d/heartbeat.txt"))
    assert cands[0][1].name == "smc_heartbeat.txt"


def test_resolve_delegates_to_first_candidate():
    assert resolve_heartbeat_path(
        terminal_path=r"C:\MT5\terminal64.exe", explicit_heartbeat_path=None,
    ) == heartbeat_path_candidates(
        terminal_path=r"C:\MT5\terminal64.exe", explicit_heartbeat_path=None,
    )[0][1]


def test_probe_writable_true_on_tmp(tmp_path):
    p = tmp_path / "MQL5" / "Files" / "smc_heartbeat.txt"
    assert probe_writable(p) is True
    assert not list(p.parent.glob("*.probe"))  # probe cleaned up


def test_probe_writable_false_when_parent_is_a_file(tmp_path):
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("not a dir", encoding="ascii")
    p = blocker / "MQL5" / "Files" / "smc_heartbeat.txt"
    assert probe_writable(p) is False


def test_probe_permission_error_logs_operation_and_path(tmp_path, monkeypatch, caplog):
    p = tmp_path / "MQL5" / "Files" / "smc_heartbeat.txt"

    def denied(self, *args, **kwargs):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(Path, "write_text", denied)
    with caplog.at_level(logging.ERROR, logger="smc.live.heartbeat_path"):
        assert probe_writable(p) is False

    assert "heartbeat path probe failed operation=write heartbeat probe" in caplog.text
    assert str(p) in caplog.text


# --------------------------------------------------------------------------- #
# Publisher writes to the derived EA-readable path (Files dir created)
# --------------------------------------------------------------------------- #
def test_publisher_writes_to_derived_terminal_path(tmp_path):
    from smc.live.heartbeat import HeartbeatPublisher

    terminal = tmp_path / "MetaTrader 5" / "terminal64.exe"
    p = resolve_heartbeat_path(str(terminal), None)
    assert p.name == "smc_heartbeat.txt"
    assert p.parts[-3:] == ("MetaTrader 5", "MQL5", "Files")[-2:] or p.parts[-3:-1] == (
        "MQL5", "Files")
    # The operator creates the parent (MQL5/Files) before the session starts;
    # verify the publisher really lands the file there.
    p.parent.mkdir(parents=True, exist_ok=True)
    hb = HeartbeatPublisher(p, interval_seconds=0.0)
    hb.publish()
    assert p.exists()
    assert "state=running" in p.read_text(encoding="ascii")
