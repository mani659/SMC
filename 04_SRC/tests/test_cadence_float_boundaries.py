"""Float-boundary regression tests for the console cadence timers.

``time.monotonic()`` readings are large floats, so a delta that measures exactly
one interval can round a few ulps LOW (e.g. ``299.99999999999994`` for a 300 s
gap). Before the common ``MONO_CADENCE_EPS`` guard, such a delta suppressed a
due console action for one poll/bar — which is how CI caught it on a fresh
runner whose ``monotonic()`` magnitude was ~54 s.

These tests pin the boundary behaviour of the three cadence helpers
(judgement board, marker snapshot, structure refresh) plus the alive ping, and
keep a negative control so the tolerance can never quietly disable the timers.
Operational console timing only — no strategy, risk or threshold logic.
"""

from __future__ import annotations

from types import SimpleNamespace

import smc.live.run_operator as run_operator
from smc.live.operator_config import OperatorConfig
from smc.live.run_operator import OperatorSession

# A monotonic base (seen on a fresh CI runner) for which the exact 300 s
# boundary subtraction rounds low.
_T0 = 53.738963081
_ANCHOR = _T0 + 301.0
_DUE = _T0 + 601.0
_LOW_DELTA = _DUE - _ANCHOR
_INTERVAL = 300.0
_INSIDE_WINDOW = _ANCHOR + 100.0


def _session(tmp_path, **kwargs) -> OperatorSession:
    return OperatorSession(OperatorConfig(log_dir=str(tmp_path / "logs"), **kwargs))


def test_boundary_fixture_actually_rounds_low():
    """Guard the fixture: if this drifts, the boundary tests become mute."""
    assert _LOW_DELTA < _INTERVAL
    assert _INTERVAL - _LOW_DELTA <= run_operator.MONO_CADENCE_EPS


def test_alive_ping_fires_on_low_rounding_boundary(tmp_path):
    session = _session(tmp_path, alive_interval_s=_INTERVAL)
    session._last_alive_mono = _ANCHOR              # as if it fired at _ANCHOR
    assert session._maybe_alive(_INSIDE_WINDOW) is False   # still rate-limited
    assert session._maybe_alive(_DUE) is True              # ulp-low boundary fires


def test_judge_board_fires_on_low_rounding_boundary(tmp_path):
    session = _session(tmp_path, judge_interval_s=_INTERVAL)
    session._last_judge_mono = _ANCHOR
    assert session._maybe_judge(_INSIDE_WINDOW) is False
    assert session._maybe_judge(_DUE) is True


def test_marker_snapshot_rewrites_on_low_rounding_boundary(tmp_path):
    session = _session(tmp_path, console_refresh_s=_INTERVAL)
    writes: list[list] = []
    session._marker_writer = SimpleNamespace(
        write=lambda records: writes.append(records))
    session.state["htf_batches"] = 1                # signature differs from None
    session._last_marker_mono = _ANCHOR

    session._maybe_markers(_INSIDE_WINDOW)
    assert writes == []                             # inside the window: no write

    session._maybe_markers(_DUE)
    assert len(writes) == 1                         # boundary: written


def test_structure_refresh_rebuilds_on_low_rounding_boundary(tmp_path, monkeypatch):
    session = _session(tmp_path, console_refresh_s=_INTERVAL)
    session._adapter = SimpleNamespace(
        engine=_engine(), active_workflows=lambda: {})
    session._loop = SimpleNamespace(sweep_links={})

    ticks = iter([_ANCHOR, _INSIDE_WINDOW, _DUE])
    # Surgical patch: run_operator only reads time.monotonic() here.
    monkeypatch.setattr(
        run_operator, "time", SimpleNamespace(monotonic=lambda: next(ticks)))

    session._maybe_refresh_structure(new_bars=1, batch_changed=False)  # anchor
    first = session.state["structure"]
    assert first is not None

    session._maybe_refresh_structure(new_bars=1, batch_changed=False)  # in window
    assert session.state["structure"] is first

    session._maybe_refresh_structure(new_bars=1, batch_changed=False)  # boundary
    assert session.state["structure"] is not first


def _engine():
    from smc.orchestration.engine import PipelineEngine

    return PipelineEngine()
