"""Wire-light — pool levels + enter_at-safe hits on the structure console.

Display-only contract: fake snapshots (no MT5), explicit ``(none)``,
no EQH/EQL render path, multi-hit bars list every level, and no hit can
precede its level's ``enter_at``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.live.pool_board import build_live_pool_board
from smc.live.structure_console import build_structure_snapshot, render_structure_console
from smc.orchestration.engine import PipelineEngine

NOW = datetime(2026, 3, 3, 12, 0, tzinfo=timezone.utc)
START = datetime(2026, 3, 2, tzinfo=timezone.utc)          # Monday 00:00 UTC


def _series(count=120, override=None):
    bars = []
    for i in range(count):
        high, low, close = 101.0, 99.0, 100.0
        if override and i in override:
            high, low, close = override[i]
        bars.append(Candle(
            timestamp=START + timedelta(minutes=5 * i),
            open=100.0, high=high, low=low, close=close,
            timeframe=Timeframe.M5,
        ))
    return bars


def _pool_snapshot(**overrides):
    pool = {
        "levels": [], "hits": [], "n_active": 0, "note": None,
    }
    pool.update(overrides)
    return build_structure_snapshot(engine=PipelineEngine(), now=NOW) | {"pool": pool}


def _level(family, side, price, period_id, enter_at):
    return {
        "family": family, "side": side, "price": price,
        "period_id": period_id, "source_tf": "M5", "enter_at": enter_at,
    }


# ---------------------------------------------------------------------- #
# Rendering — grouped, ordered, honest empties, header counter
# ---------------------------------------------------------------------- #
def test_active_pool_renders_grouped_in_soft_order():
    snapshot = _pool_snapshot(levels=[
        _level("session", "BSL", 2400.5, "ASIA-2026-03-02", NOW),
        _level("previous_day", "SSL", 2350.0, "2026-03-01", NOW),
    ], n_active=2)
    board = render_structure_console(snapshot)
    assert "pool active: 2" in board
    assert "ACTIVE POOL" in board
    # R3 display order: PDH/PDL before SESSION (readability only).
    assert board.index("PDH/PDL SSL") < board.index("SESSION BSL")
    assert "PWH/PWL: (none)" in board
    assert "2400.50" in board and "2350.00" in board
    assert "tf=M5" in board
    assert board.isascii()


def test_empty_pool_prints_explicit_none():
    board = render_structure_console(_pool_snapshot())
    assert "pool active: 0" in board
    assert "(none) - no active pool levels" in board
    assert "POOL SWEEPS: (none)" in board


def test_pool_absent_prints_none_not_blank():
    board = render_structure_console(build_structure_snapshot(engine=PipelineEngine(), now=NOW))
    assert "pool active: n/a" in board
    assert "(none) - pool snapshot unavailable" in board


def test_attribution_unavailable_prints_reason():
    board = render_structure_console(
        _pool_snapshot(note="n/a (attribution: ValueError)")
    )
    assert "POOL SWEEPS: n/a (attribution: ValueError)" in board


def test_multi_hit_bar_lists_every_level():
    group = {
        "ts": NOW, "ts_short": "03-03 12:00", "n": 2,
        "items": [
            {"family": "session", "side": "BSL", "price": 2400.0,
             "level_id": "session|bsl|ASIA-2026-03-02", "enter_at": NOW},
            {"family": "previous_day", "side": "BSL", "price": 2400.0,
             "level_id": "previous_day|bsl|2026-03-01", "enter_at": NOW},
        ],
    }
    board = render_structure_console(_pool_snapshot(hits=[group]))
    line = next(l for l in board.splitlines() if "03-03 12:00" in l)
    assert "n=2" in line
    assert "session/BSL" in line and "previous_day/BSL" in line


# ---------------------------------------------------------------------- #
# Real builder — families, no EQH, enter_at safety
# ---------------------------------------------------------------------- #
def test_live_board_never_builds_eqh_and_shows_session():
    # Equal highs inside Asia must not become an "equal highs" pool level.
    bars = _series(override={i: (101.0, 99.0, 100.0) for i in range(120)})
    bars = _series(override={
        10: (101.0, 99.0, 100.0), 11: (101.0, 99.0, 100.0),   # equal highs
        90: (106.0, 99.5, 105.5),                             # post-close sweep
    })
    board = build_live_pool_board(bars, timeframe=Timeframe.M5, now=NOW)
    families = {row["family"] for row in board["levels"]}
    assert families <= {"previous_week", "previous_day", "session", "structural_swing"}
    assert "equal" not in str(board).lower()
    assert "session" in families
    text = render_structure_console(_pool_snapshot(**board))
    assert "EQUAL" not in text.upper()


def test_hits_never_precede_enter_at():
    bars = _series(override={
        36: (105.0, 100.0, 100.5),   # spike INSIDE Asia (before the level exists)
        90: (106.0, 99.5, 105.5),    # first bar after Asia close
    })
    board = build_live_pool_board(bars, timeframe=Timeframe.M5, now=NOW)
    for group in board["hits"]:
        for item in group["items"]:
            assert group["ts"] >= item["enter_at"]
    # the honest board renders without crashing even with zero/one hit
    assert "POOL SWEEPS" in render_structure_console(_pool_snapshot(**board))


def test_empty_series_reports_reason():
    board = build_live_pool_board([], timeframe=Timeframe.M5, now=NOW)
    assert board["levels"] == [] and board["hits"] == []
    assert board["note"] == "n/a (no candles yet)"
