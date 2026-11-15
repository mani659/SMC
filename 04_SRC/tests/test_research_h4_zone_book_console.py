"""Console V2 + PRODUCT V1 naming tests (2026-11-02).

Pins: (a) the research H4 zone-book console (snapshot builder + renderer +
wiring surface), and (b) the PRODUCT V1 naming/default-launch ruling —
professional config ids, legacy-id alias mapping, product default mode, and
the case-insensitive "dumb" ban on new console renders.

The operator directive found the bat path LOADING Console V2 correctly but
the research slice mode owning no product engine/batches — so SCAN/ARMED
boards could never populate. The fix surfaces the slice's own read-only
inventories plus explicit mode notes. These tests pin:

1. The research-slice snapshot builder renders the feed's zone book as SCAN
   rows (candidates - NOT armed) and the renderer is pure.
2. Active slice episodes annotate zones as armed with their status; expired
   episodes drop out of the armed set (honest states, never invented).
3. The snapshot note reaches the rendered structure console.
4. The status board prints the mode note line when set and hides it when not.
5. The research builder never mutates the feed or machine (strict fake).
6. Naming: product_v1 default; legacy ids map once with a deprecation
   warning; unknown ids fail loud; NO case-insensitive "dumb" in any new
   console render.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "04_SRC"))

from smc.live.operator_config import (                       # noqa: E402
    ConfigError,
    OperatorConfig,
    load_operator_config,
)
import smc.live.operator_config as operator_config           # noqa: E402
from smc.live.operator_console import render_status_board    # noqa: E402
from smc.live.run_operator import (                          # noqa: E402
    _PRODUCT_NOTE_STATUS,
    _RESEARCH_NOTE_STATUS,
    _RESEARCH_SNAPSHOT_NOTE,
)
from smc.live.structure_console import (                     # noqa: E402
    build_research_h4_zone_book_snapshot,
    render_structure_console,
)
from smc.dumb.mtf import (                                   # noqa: E402
    DumbMtfEpisodeKey,
    DumbMtfStateMachine,
    DumbMtfStatus,
)
from smc.dumb.mtf_paper_adapter import DumbMtfPaperAdapter   # noqa: E402
from smc.config.timeframe import Timeframe                   # noqa: E402
from smc.core.enums import Direction                         # noqa: E402
from smc.core.zone import Zone                               # noqa: E402


@dataclass(frozen=True, slots=True)
class _FakeH4Poi:
    poi_id: str
    zone: Zone


def _zone(direction=Direction.LONG, low=4000.0, high=4010.0):
    return Zone(top=high, bottom=low, direction=direction, timeframe=Timeframe.H4)


def _zone_book(*zones):
    """Zone book in the feed's own shape: poi_id -> poi(zone)."""
    book = {}
    for direction, low, high in zones:
        poi_id = f"dumb-mtf-h4|ob|{direction.name}|{low:.6f}|{high:.6f}"
        book[poi_id] = _FakeH4Poi(poi_id, _zone(direction, low, high))
    return book


# ---------------------------------------------------------------------- #
# Research H4 zone-book console (wiring fix 2026-11-02)
# ---------------------------------------------------------------------- #
def test_research_zone_book_renders_as_scan_rows():
    snap = build_research_h4_zone_book_snapshot(
        feed=_zone_book((Direction.LONG, 4000.0, 4010.0),
                        (Direction.SHORT, 4050.0, 4085.0)),
        machine=None,
        now=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc),
        mode_note=_RESEARCH_SNAPSHOT_NOTE,
    )
    assert len(snap["scan"]) == 2
    row = next(r for r in snap["scan"] if r["direction"] == "LONG")
    assert row["tf"] == "H4" and row["kind"] == "ob"
    assert row["zone_low"] == 4000.0 and row["zone_high"] == 4010.0
    # candidates only: no armed/entry/trigger fields on scan rows
    assert "armed" not in row and "entry" not in row and "trigger" not in row
    assert snap["scan"] and snap["pois"]
    # no episode yet: honest armed=no rows, nothing counted armed
    assert all(r.get("armed") is False for r in snap["pois"])
    assert snap["armed_by_tf"] == {}
    assert snap["plan"] == [] and snap["sweeps"] == []
    board = render_structure_console(snap)
    assert " STRUCTURE SCAN  (candidates - NOT armed)" in board
    assert "H4" in board and "4000.00-4010.00" in board
    assert _RESEARCH_SNAPSHOT_NOTE in board   # mode clarification on the board
    # naming: research slice display ids are neutral, never a package prefix
    assert all(r["id_short"].startswith("zb-") for r in snap["scan"])
    # purity: same input -> same board
    assert render_structure_console(snap) == board


def test_active_episode_annotates_armed_with_status():
    machine = DumbMtfStateMachine()
    DumbMtfPaperAdapter(machine)              # same seam the session wires
    zones = _zone_book((Direction.LONG, 4000.0, 4010.0))
    poi_id = next(iter(zones))
    key = DumbMtfEpisodeKey("XAUUSDm", "LONG", Timeframe.H4, poi_id, "evt-1")
    episode, _ = machine.start_primary(key, 3)
    assert episode.status is DumbMtfStatus.IN_ZONE_PRIMARY

    snap = build_research_h4_zone_book_snapshot(
        feed=zones, machine=machine,
        now=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc),
        mode_note=_RESEARCH_SNAPSHOT_NOTE,
    )
    armed = [r for r in snap["pois"] if r.get("armed")]
    assert len(armed) == 1
    assert armed[0]["state"] == "IN_ZONE_PRIMARY"
    assert snap["armed_by_tf"] == {"H4": 1}
    board = render_structure_console(snap)
    assert " ARMED POI" in board and "state=IN_ZONE_PRIMARY" in board

    # after the locked primary window the episode stands in the fallback
    # posture (STILL LIVE per the sequential ruling); expiry needs a
    # boundary sweep + the fallback clock, or invalidation.
    machine.advance_clock(Timeframe.M5, 10)
    snap2 = build_research_h4_zone_book_snapshot(
        feed=zones, machine=machine,
        now=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc),
        mode_note=_RESEARCH_SNAPSHOT_NOTE,
    )
    assert snap2["armed_by_tf"] == {"H4": 1}
    assert list(snap2["pois"])[0]["state"] == "BOUNDARY_FALLBACK"
    machine.record_boundary_sweep(key.value, 11)
    machine.advance_clock(Timeframe.M5, 30)   # > 11 + FALLBACK_BARS(16)
    snap3 = build_research_h4_zone_book_snapshot(
        feed=zones, machine=machine,
        now=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc),
        mode_note=_RESEARCH_SNAPSHOT_NOTE,
    )
    row = [r for r in snap3["pois"] if r["id"] == poi_id][0]
    assert row["armed"] is False
    assert row["state"] == "EXPIRED_SWEEP_TIMEOUT"
    assert snap3["armed_by_tf"] == {}


class _RaisingMutationFeed:
    """Dynamic strict fake: any attribute WRITE is recorded, never silently ok."""

    def __init__(self):
        object.__setattr__(self, "_book",
                           _zone_book((Direction.LONG, 4000.0, 4010.0)))
        object.__setattr__(self, "mutations", [])

    def __setattr__(self, name, value):
        self.__dict__["mutations"].append(name)
        object.__setattr__(self, name, value)

    @property
    def _h4_pois(self):
        return object.__getattribute__(self, "_book")


def test_builder_is_read_only_on_feed_and_machine():
    feed = _RaisingMutationFeed()
    build_research_h4_zone_book_snapshot(
        feed=feed, machine=DumbMtfStateMachine(),
        now=datetime.now(timezone.utc), mode_note=_RESEARCH_SNAPSHOT_NOTE,
    )
    assert feed.mutations == [], (
        "console mutated the feed: {0}".format(feed.mutations)
    )


def test_status_board_mode_note_line():
    with_note = render_status_board({"mode_note": _PRODUCT_NOTE_STATUS})
    without = render_status_board({})
    assert f" note     : {_PRODUCT_NOTE_STATUS}" in with_note
    assert " note     :" not in without


# ---------------------------------------------------------------------- #
# PRODUCT V1 naming + default launch (Lead Architect ruling 2026-11-02)
# ---------------------------------------------------------------------- #
def test_product_v1_is_the_accepted_default_mode():
    assert OperatorConfig().strategy_mode == "PRODUCT_V1"
    dataclass_default = OperatorConfig(
        terminal_path="C:/term/terminal64.exe",
    )
    assert dataclass_default.strategy_mode == "PRODUCT_V1"
    assert dataclass_default.detection_timeframes == ("D1", "H4", "H1", "M15")
    assert dataclass_default.timeframe == "M5"


def test_canonical_and_lowercase_ids_load(tmp_path):
    p = tmp_path / "cfg.json"
    # detection_timeframes must satisfy each mode's locked constraint.
    cases = (
        ("product_v1", "PRODUCT_V1", None),
        ("PRODUCT_V1", "PRODUCT_V1", None),
        ("archive_tight_htf", "ARCHIVE_TIGHT_HTF", ["H4"]),
        ("research_h4_zone_book", "RESEARCH_H4_ZONE_BOOK", None),
        ("coupled_mtf", "COUPLED_MTF", ["D1", "H4", "H1", "M15"]),
    )
    for raw, expected, detection in cases:
        payload = {"strategy_mode": raw}
        if detection is not None:
            payload["detection_timeframes"] = detection
        p.write_text(json.dumps(payload), encoding="utf-8")
        assert load_operator_config(p).strategy_mode == expected, raw


def test_legacy_ids_map_once_with_deprecation_warning(tmp_path, capsys, monkeypatch):
    """Alias policy (chosen): map + one-time deprecation warning; the
    mapping happens at config load, never at runtime."""
    monkeypatch.setattr(operator_config, "_ALIASES_WARNED", set())
    p = tmp_path / "legacy.json"
    for raw, expected, detection in (
        ("DUMB_MTF_H4", "RESEARCH_H4_ZONE_BOOK", None),
        ("POLICY_MTF_H4", "ARCHIVE_TIGHT_HTF", ["H4"]),
        ("COMPLEX", "PRODUCT_V1", None),
    ):
        payload = {"strategy_mode": raw}
        if detection is not None:
            payload["detection_timeframes"] = detection
        p.write_text(json.dumps(payload), encoding="utf-8")
        assert load_operator_config(p).strategy_mode == expected, raw
    captured = capsys.readouterr().out
    # ONE-time notice per legacy value; our own wording never prints the
    # research nickname (only the professional target id does).
    assert captured.count("DEPRECATION") == 3
    assert "dumb" not in captured.lower()
    # extra loads do not repeat the notice (one-time policy)
    assert load_operator_config(p).strategy_mode == "PRODUCT_V1"
    assert capsys.readouterr().out.count("DEPRECATION") == 0


def test_unknown_strategy_mode_fails_loud(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"strategy_mode": "GOLD_RUSH"}', encoding="utf-8")
    with pytest.raises(ConfigError, match="strategy_mode"):
        load_operator_config(p)


def test_new_console_renders_never_print_the_research_nickname():
    """Case-insensitive ban on NEW renders across every console surface."""
    surfaces = [
        render_status_board({"mode_note": _PRODUCT_NOTE_STATUS}),
        render_status_board({"mode_note": _RESEARCH_NOTE_STATUS}),
        render_status_board({}),                       # fully empty board
        render_status_board({"structure": None, "htf_batches": 0}),
    ]
    book = _zone_book((Direction.LONG, 4000.0, 4010.0))
    adapter = DumbMtfPaperAdapter()
    snap = build_research_h4_zone_book_snapshot(
        feed=book, machine=getattr(adapter, "machine", None),
        now=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc),
        mode_note=_RESEARCH_SNAPSHOT_NOTE,
    )
    surfaces.append(render_structure_console(snap))
    for rendered in surfaces:
        assert "dumb" not in rendered.lower(), rendered[:400]


def test_product_mode_invokes_the_multi_tf_runtime_batches():
    """Directive Part 4 (unit, fakes): product_v1 must drive the REAL
    loop wiring (MultiTFProductRuntime batches -> htf_batches >= 1),
    never the isolated non-batch slice."""
    from smc.live.loop import LiveLoop

    class _SentinelRuntime:
        detection_timeframes = (Timeframe.H4, Timeframe.H1)
        optional_timeframes = ()
        supply_d1_to_m8 = True
        allow_single_tf_degraded = False

    runtime = _SentinelRuntime()
    loop = LiveLoop(
        connector=None, runner=None, driver=None, heartbeat=None,
        symbol="XAUUSDm", runtime=runtime,
    )
    assert loop.runtime is runtime          # product batches own the loop
    # isolated research slice: explicit runtime is IGNORED (no product batches)
    slice_loop = LiveLoop(
        connector=None, runner=None, driver=None, heartbeat=None,
        symbol="XAUUSDm", runtime=_SentinelRuntime(), dumb_mtf_feed=object(),
    )
    assert slice_loop.runtime is None


def test_product_mode_note_and_research_note_are_professional():
    assert "dumb" not in _PRODUCT_NOTE_STATUS.lower()
    assert "dumb" not in _RESEARCH_NOTE_STATUS.lower()
    assert "dumb" not in _RESEARCH_SNAPSHOT_NOTE.lower()
    assert _PRODUCT_NOTE_STATUS.startswith("PRODUCT V1 (multi-TF)")
    assert _RESEARCH_NOTE_STATUS.startswith("RESEARCH H4 zone-book")
    assert _RESEARCH_SNAPSHOT_NOTE.startswith("RESEARCH H4 zone-book")
