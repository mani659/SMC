"""Structure-console refresh policy + armed-visibility regression tests.

Pins the 2026-10-06 mismatch fix: an HTF batch change (the arming event)
ALWAYS rebuilds the structure snapshot immediately — the operator must see
an armed POI on the board without waiting out ``console_refresh_s`` —
while new-bar refreshes stay rate-limited. Also pins the board header
armed counter so ``detect: armed N`` vs POIS sections can never silently
diverge.
"""

from __future__ import annotations

import time as _time

from types import SimpleNamespace

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.live.operator_config import OperatorConfig
from smc.live.run_operator import OperatorSession
from smc.live.structure_console import render_structure_console
from smc.orchestration.engine import PipelineEngine


def _session(console_refresh_s: float = 900.0) -> OperatorSession:
    session = OperatorSession(OperatorConfig(
        log_dir="logs/_test_refresh", console_refresh_s=console_refresh_s))
    session._adapter = SimpleNamespace(
        engine=PipelineEngine(), active_workflows=lambda: {})
    session._loop = SimpleNamespace(sweep_links={})
    return session


def _arm_one(session: OperatorSession) -> POI:
    poi = POI(zone=Zone(top=2355.5, bottom=2340.1, direction=Direction.LONG,
                        timeframe=Timeframe.W1),
              models=[ModelType.M8], m8_kind="ob")
    session._adapter.engine.arm_at(poi, arm_bar=0)
    return poi


def test_batch_change_rebuilds_snapshot_immediately():
    session = _session(console_refresh_s=900.0)
    # Initial rebuild right before the batch (fresh anchor, empty engine).
    session._maybe_refresh_structure(new_bars=1, batch_changed=False)
    assert session.state["structure"] is not None
    assert session.state["structure"]["pois"] == []

    # A batch arms a POI seconds later — inside the 900 s rate-limit window.
    _arm_one(session)
    session._maybe_refresh_structure(new_bars=0, batch_changed=True)

    rows = session.state["structure"]["pois"]
    assert len(rows) == 1 and rows[0]["tf"] == "W1"
    assert rows[0]["armed"] is True


def test_bar_only_refresh_stays_rate_limited():
    session = _session(console_refresh_s=900.0)
    session._maybe_refresh_structure(new_bars=1, batch_changed=False)
    first = session.state["structure"]
    # A new bar inside the window refreshes nothing.
    session._maybe_refresh_structure(new_bars=1, batch_changed=False)
    assert session.state["structure"] is first


def test_idle_poll_still_noop():
    session = _session()
    session._maybe_refresh_structure(new_bars=0, batch_changed=False)
    assert session.state["structure"] is None


def test_board_header_carries_armed_count():
    engine = PipelineEngine()
    poi = POI(zone=Zone(top=101.0, bottom=99.0, direction=Direction.LONG,
                        timeframe=Timeframe.H4),
              models=[ModelType.M8], m8_kind="ob")
    engine.arm_at(poi, arm_bar=0)
    from smc.live.structure_console import build_structure_snapshot
    snapshot = build_structure_snapshot(engine=engine, now=None)
    board = render_structure_console(snapshot)
    assert "armed 1)" in board
    assert board.isascii()
