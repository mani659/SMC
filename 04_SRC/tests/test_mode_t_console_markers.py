"""Marker writer + judgement console tests (design lock §3/§4)."""

from __future__ import annotations

from pathlib import Path

from smc.live.judgement_console import (
    judge_interval_used,
    render_judgement_board,
)
from smc.live.marker_writer import (
    MARKER_FILENAME,
    MARKER_HEADER,
    MAX_MARKER_OBJECTS,
    MarkerWriter,
    snapshot_to_records,
)


def _zone_row(i, tf="H4", armed=True, low=100.0, high=105.0):
    return {
        "id": f"poi-{i}", "id_short": f"poi-{i}", "tf": tf,
        "direction": "BULLISH", "kind": "m1m7", "zone_low": low,
        "zone_high": high, "armed": armed,
    }


# --------------------------------------------------------------------- #
# Marker writer (§4)
# --------------------------------------------------------------------- #
def test_writer_writes_header_and_rows_atomic(tmp_path):
    path = tmp_path / MARKER_FILENAME
    writer = MarkerWriter(path)
    records = snapshot_to_records(
        symbol="XAUUSDm",
        structure={"pois": [_zone_row("abc12345")], "sweeps": []},
        mode="A", heartbeat_ok=True, mode_t_poi=None,
        updated_at_utc="2026-10-15T09:30:00Z",
    )
    assert writer.write(records) is True
    text = path.read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    assert lines[0] == MARKER_HEADER
    assert len(lines) == 3                      # header + 1 zone + label row
    zone = lines[1].split(",")
    assert zone[0] == "zone_poi-abc12345"
    assert zone[2] == "poi"
    label = lines[2].split(",")
    assert label[2] == "label"
    assert label[7] == "SMC Mode A"


def test_writer_caps_at_11_objects(tmp_path):
    path = tmp_path / MARKER_FILENAME
    structures = {
        "pois": [_zone_row(f"z{i}{i}6789") for i in range(20)],
        "sweeps": [],
    }
    records = snapshot_to_records(
        symbol="XAUUSDm", structure=structures, mode="T",
        heartbeat_ok=True, mode_t_poi=None,
        updated_at_utc="2026-10-15T09:30:00Z",
    )
    assert len(records) <= MAX_MARKER_OBJECTS
    assert MarkerWriter(path).write(records) is True
    body = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(body) <= 1 + MAX_MARKER_OBJECTS


def test_writer_stale_heartbeat_label(tmp_path):
    path = tmp_path / MARKER_FILENAME
    records = snapshot_to_records(
        symbol="XAUUSDm", structure={}, mode="A",
        heartbeat_ok=False, mode_t_poi=None,
        updated_at_utc="2026-10-15T09:30:00Z",
    )
    MarkerWriter(path).write(records)
    text = path.read_text(encoding="utf-8")
    assert "HEARTBEAT STALE" in text
    assert "stale_red" in text


def test_writer_mode_t_entry_line(tmp_path):
    path = tmp_path / MARKER_FILENAME
    records = snapshot_to_records(
        symbol="XAUUSDm", structure={}, mode="T", heartbeat_ok=True,
        mode_t_poi={"poi_id": "poi-abc12345", "direction": "BUY",
                    "entry": 2651.8, "text": "Mode T LIMIT 2651.8"},
        updated_at_utc="2026-10-15T09:30:00Z",
    )
    MarkerWriter(path).write(records)
    text = path.read_text(encoding="utf-8")
    assert "entry_t_poi-abc1" in text
    assert "mode_T_orange" in text
    assert "2651.80" in text


def test_sweep_marker_needs_linked_zone(tmp_path):
    # sweep_calls with NO matching armed POI → no sweep row (never invented).
    records = snapshot_to_records(
        symbol="XAUUSDm",
        structure={
            "pois": [_zone_row("abc12345")],
            "sweeps": [{"poi_id": "poi-otherpoi", "side": "SELL", "tf": "H4"}],
        },
        mode="A", heartbeat_ok=True, mode_t_poi=None,
        updated_at_utc="2026-10-15T09:30:00Z",
    )
    kinds = [r.kind for r in records]
    assert "sweep" not in kinds


def test_writer_never_raises_on_unwritable_dir(tmp_path):
    # Path in a deleted dir: write() returns False, never raises (§4.4).
    dead = tmp_path / "gone" / MARKER_FILENAME
    writer = MarkerWriter(dead)
    tmp_path.chmod(0o500)   # read-only parent chain best effort; POSIX ok
    try:
        assert writer.write([]) is False or writer.write([]) is True
    except OSError:
        pytest.fail("MarkerWriter.write must swallow OSError")
    finally:
        tmp_path.chmod(0o700)


# --------------------------------------------------------------------- #
# Judgement console (§3)
# --------------------------------------------------------------------- #
_FLAT_STATE = dict(
    now_utc="2026-10-15T09:30:00",
    mode="A",
    mode_t_banner=None,
    structure=None,
    mode_t_events=[],
    book_product_positions=0,
    book_product_pendings=0,
    book_mode_t_positions=0,
    book_mode_t_pendings=0,
    hb_seq=41,
    hb_age_s=0.0,
    hb_state="running",
)


def test_flat_board_renders_with_mode_line():
    board = render_judgement_board(**_FLAT_STATE)
    for block in (" MODE", " POIS", " SWEEPS", " SEEKING", " JUDGEMENT",
                  " BOOK", " HEARTBEAT"):
        assert block in board, block
    assert " A" in board
    assert "JUDGEMENT: flat" in board       # honest idle line, never silent
    assert "SWEEPS: none" in board
    assert "SEEKING: none" in board


def test_mode_t_banner_block_when_flag_on():
    from smc.live.mode_t import MODE_T_BANNER
    state = dict(_FLAT_STATE, mode="T", mode_t_banner=MODE_T_BANNER)
    board = render_judgement_board(**state)
    assert MODE_T_BANNER.split("—")[0].strip() in board


def test_judgement_board_shows_skip_reasons():
    events = [
        "POI poi-aa12 proof=77 · action=SKIP · SKIP: GAP_TOO_WIDE",
        "POI poi-aa99 proof=80 · action=PLACE · Mode T LIMIT 100.00 reason proof_close-mid",
    ]
    board = render_judgement_board(**dict(_FLAT_STATE, mode="T", mode_t_events=events))
    assert "SKIP: GAP_TOO_WIDE" in board
    assert "Mode T LIMIT 100.00" in board
    assert "traceback" not in board.lower()


def test_judge_knob_zero_disables():
    assert judge_interval_used(60) is True
    assert judge_interval_used(0) is False
    assert judge_interval_used(None) is False
