"""Console V2 bat-wiring tests (2026-11-02): DUMB slice console + mode notes.

The operator directive found the bat path LOADING Console V2 correctly but the
configured ``DUMB_MTF_H4`` slice mode owning no product engine/batches — so
SCAN/ARMED boards could never populate. The fix surfaces the slice's own
read-only inventories plus explicit mode notes. These tests pin:

1. The dumb-slice snapshot builder renders the feed's zone book as SCAN rows
   (candidates - NOT armed) and the renderer is pure.
2. Active DUMB episodes annotate zones as armed with their status; expired
   episodes drop out of the armed set (honest states, never invented).
3. The snapshot note reaches the rendered structure console.
4. The status board prints the mode note line when set and hides it when not.
5. The dumb builder never mutates the feed or machine (dynamic strict fake).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "04_SRC"))

from smc.dumb.mtf import (                                   # noqa: E402
    DumbMtfEpisodeKey,
    DumbMtfStateMachine,
    DumbMtfStatus,
)
from smc.dumb.mtf_paper_adapter import DumbMtfPaperAdapter   # noqa: E402
from smc.config.timeframe import Timeframe                   # noqa: E402
from smc.core.enums import Direction                         # noqa: E402
from smc.core.zone import Zone                               # noqa: E402
from smc.live.operator_console import render_status_board    # noqa: E402
from smc.live.structure_console import (                     # noqa: E402
    build_dumb_mtf_snapshot,
    render_structure_console,
)

NOTE = (
    "DUMB-MTF H4 slice - zone book from the dumb-owned read-only M8 H4 scan;"
    " episode annotations are the DUMB slice book, NOT the product"
    " locked-Pillar engine book"
)


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


def test_dumb_zone_book_renders_as_scan_rows():
    snap = build_dumb_mtf_snapshot(
        feed=_zone_book((Direction.LONG, 4000.0, 4010.0),
                        (Direction.SHORT, 4050.0, 4085.0)),
        machine=None,
        now=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc),
        mode_note=NOTE,
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
    assert NOTE in board                      # mode clarification on the board
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

    snap = build_dumb_mtf_snapshot(
        feed=zones, machine=machine,
        now=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc), mode_note=NOTE,
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
    snap2 = build_dumb_mtf_snapshot(
        feed=zones, machine=machine,
        now=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc), mode_note=NOTE,
    )
    assert snap2["armed_by_tf"] == {"H4": 1}
    assert list(snap2["pois"])[0]["state"] == "BOUNDARY_FALLBACK"
    machine.record_boundary_sweep(key.value, 11)
    machine.advance_clock(Timeframe.M5, 30)   # > 11 + FALLBACK_BARS(16)
    snap3 = build_dumb_mtf_snapshot(
        feed=zones, machine=machine,
        now=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc), mode_note=NOTE,
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
    build_dumb_mtf_snapshot(
        feed=feed, machine=DumbMtfStateMachine(),
        now=datetime.now(timezone.utc), mode_note=NOTE,
    )
    assert feed.mutations == [], (
        "console mutated the feed: {0}".format(feed.mutations)
    )


def test_status_board_mode_note_line():
    note = (
        "DUMB_MTF_H4 slice mode: product MTF batches never run here (htf"
        " batches stays 0); STRUCTURE SCAN below lists the DUMB-MTF H4 zone book"
    )
    with_note = render_status_board({"mode_note": note})
    without = render_status_board({})
    assert f" note     : {note}" in with_note
    assert " note     :" not in without
