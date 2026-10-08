"""Event-driven operator console tests (display-only; 2026-10-07 directive).

Pins the event-mode behavior of the operator console:

* ``console_mode="event"`` (the DEFAULT) prints the full board ONLY when a
  major event queued a reason — never on a pure timer with no state change;
* board mode keeps the legacy timed full refresh;
* the alive ping is ONE short line per ``alive_interval_s`` (0 disables),
  never a full board.

Fakes only — no MetaTrader5, no detection, no strategy logic.
"""

from __future__ import annotations

import time as _time
from types import SimpleNamespace

from smc.live.operator_config import OperatorConfig
from smc.live.run_operator import OperatorSession


class _FakeKPI:
    """Minimal KPI surface used by _fold_flow_counters / _publish_console."""

    def __init__(self, counters=None):
        self.records = []
        self._counters = counters or {}

    def counters(self):
        return dict(self._counters)

    def write_jsonl(self, path):
        path.write_text("[]", encoding="utf-8")


class _FakeRunner:
    def __init__(self, counters=None):
        self.kpi = _FakeKPI(counters)


class _FakeHeartbeat:
    sequence = 42
    state = "running"
    _last_unix = None


def _session(tmp_path, mode="event", alive_interval_s=300.0, counters=None):
    cfg = OperatorConfig(
        log_dir=str(tmp_path / "logs"), magic=7,
        console_mode=mode, alive_interval_s=alive_interval_s,
        console_refresh_s=5.0,
    )
    session = OperatorSession(cfg)
    session._runner = _FakeRunner(counters)
    session._heartbeat = _FakeHeartbeat()
    session._mt5 = SimpleNamespace(symbol_info_tick=lambda s: None)
    session._loop = SimpleNamespace(htf_batches=0, last_report=None,
                                    arm_errors=0, sweep_links={})
    session._adapter = _FakeAdapter()
    return session


class _FakeAdapter:
    """Minimal adapter stub for event-mode tests (no real engine)."""

    _candles = None
    engine = None  # so structure-snapshot failures stay bounded in these tests

    def current_atr(self, idx):
        raise NotImplementedError("event-mode tests must not exercise real ATR")


# --------------------------------------------------------------------------- #
# Event mode: no print on a pure timer with no state change
# --------------------------------------------------------------------------- #
def test_event_mode_no_print_on_pure_timer(tmp_path, capsys):
    session = _session(tmp_path, alive_interval_s=0.0)   # ping off: isolate boards
    t0 = _time.monotonic()
    for step in range(20):                      # 20 idle polls, far apart in time
        session._on_poll(0, connector=None)  # connector None → _mt5_call short-circuits
        assert session._maybe_print_console(t0 + step * 60) is False
    assert capsys.readouterr().out == ""        # NO full board on a pure timer
    assert session._event_reason is None


def test_event_mode_alive_ping_covers_liveness_on_idle_polls(tmp_path, capsys):
    session = _session(tmp_path, alive_interval_s=300.0)
    t0 = _time.monotonic()
    for step in range(12):                      # 12 idle polls x 60 s
        session._on_poll(0, connector=None)
        session._maybe_alive(t0 + step * 60)
    out = capsys.readouterr().out
    assert out.count("[alive]") == 2            # anchored at start: +300s, +600s
    assert "SMC OPERATOR" not in out            # still NO full board


def test_event_mode_first_poll_is_silent_until_run_queues_start(tmp_path):
    session = _session(tmp_path)
    session._on_poll(0, connector=None)
    assert session._maybe_print_console(_time.monotonic()) is False


# --------------------------------------------------------------------------- #
# Event mode: prints on the major events
# --------------------------------------------------------------------------- #
def test_event_mode_prints_on_new_bar(tmp_path, capsys):
    session = _session(tmp_path)
    session._on_poll(1, connector=None)
    reason = session._event_reason
    assert reason is not None and "new bar" in reason
    assert session._maybe_print_console(_time.monotonic()) is True
    out = capsys.readouterr().out
    assert f">>> event: {reason}" in out
    assert "SMC OPERATOR" in out                 # full status board printed
    # Reason consumed — a repeat call prints nothing.
    assert session._event_reason is None
    assert session._maybe_print_console(_time.monotonic()) is False


def test_event_mode_prints_on_batch_change(tmp_path):
    from types import SimpleNamespace as NS

    session = _session(tmp_path)
    session._loop = NS(htf_batches=1, last_report=NS(
        armed_count=2,
        summary=lambda: {"per_tf": {"H4": {"detected_raw": 23, "merged": 7,
                                           "passed": 3}}},
    ), arm_errors=0, sweep_links={})
    # fresh session: error count starts at 0, so the first poll can queue a
    # "new error" reason only if something appended to state["errors"].
    session._on_poll(0, connector=None)
    assert session._event_reason == "HTF batch completed"
    assert session.state["htf_armed"] == 2       # armed delta folded
    assert session._maybe_print_console(_time.monotonic()) is True


def test_event_mode_prints_on_flow_counter_change(tmp_path, capsys):
    session = _session(tmp_path, counters={"fills": 0})
    session._on_poll(0, connector=None)          # anchor signature
    session._runner.kpi._counters = {"fills": 1}  # a fill happened
    session._on_poll(0, connector=None)
    assert session._event_reason is not None
    assert "flow/KPI" in session._event_reason
    assert session._maybe_print_console(_time.monotonic()) is True
    assert "SMC OPERATOR" in capsys.readouterr().out


def test_event_mode_prints_on_new_error(tmp_path, capsys):
    session = _session(tmp_path)
    session._on_poll(0, connector=None)          # anchor error count (0)
    session.state["errors"].append("PermissionError(13, 'Access is denied')")
    session._on_poll(0, connector=None)
    assert session._event_reason is not None
    assert "new error" in session._event_reason
    assert session._maybe_print_console(_time.monotonic()) is True
    assert "SMC OPERATOR" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Alive ping
# --------------------------------------------------------------------------- #
def test_alive_ping_one_short_line_per_interval(tmp_path, capsys):
    session = _session(tmp_path, alive_interval_s=300.0)
    t0 = _time.monotonic()
    assert session._maybe_alive(t0) is False        # anchored at session start
    assert session._maybe_alive(t0 + 200) is False  # inside the interval
    assert session._maybe_alive(t0 + 301) is True   # interval elapsed → fires
    out = capsys.readouterr().out
    assert out.strip().startswith("[alive]")
    assert "hb_seq=42" in out and "errors=0" in out
    assert "SMC OPERATOR" not in out             # NEVER a full board
    assert session._maybe_alive(t0 + 400) is False   # re-anchored at t0+301
    assert session._maybe_alive(t0 + 601) is True    # next interval fires
    assert "[alive]" in capsys.readouterr().out


def test_alive_ping_disabled_at_zero(tmp_path, capsys):
    session = _session(tmp_path, alive_interval_s=0.0)
    for step in range(10):
        assert session._maybe_alive(_time.monotonic() + step * 10_000) is False
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------- #
# Board mode: legacy timed refresh unchanged (regression guard)
# --------------------------------------------------------------------------- #
def test_board_mode_keeps_timed_refresh_semantics(tmp_path):
    session = _session(tmp_path, mode="board")
    # Board mode leaves the event reason machinery untouched; the run loop
    # branches on console_mode (see run()) — pin the mode wiring here.
    assert session._console_mode == "board"
    session._on_poll(0, connector=None)
    # ...and a batch change still forces the legacy immediate repaint flag.
    session._loop = SimpleNamespace(htf_batches=1, last_report=None,
                                    arm_errors=0, sweep_links={})
    session._on_poll(0, connector=None)
    assert session._console_force is True
