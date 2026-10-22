"""Marker writer + judgement console tests (design lock §3/§4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from smc.core.enums import Direction
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
    # R3 (post-audit hardening): the old assertion was a tautology
    # ("is False or is True") — it checked the OSError escape guarantee but
    # never an actual failure outcome. A REAL grammar of the failure path:
    # make the parent a FILE so mkdir/replace genuinely fail (OSError
    # subclass), then require write() to swallow it and return exactly False.
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("x", encoding="utf-8")
    dead_path = blocker / "sub" / MARKER_FILENAME   # parent chain is a file
    writer = MarkerWriter(dead_path)
    try:
        assert writer.write([]) is False
    except OSError as exc:                    # pragma: no cover
        pytest.fail(f"MarkerWriter.write must swallow OSError, got {exc!r}")


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


# --------------------------------------------------------------------- #
# R1 — entry_t marker goes LIVE (was: wiring passed mode_t_poi=None)
# --------------------------------------------------------------------- #
def _clock(s="2026-10-15T09:30:00"):
    from datetime import datetime, timezone
    return lambda: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_entry_t_row_lives_while_ticket_is_booked(tmp_path):
    from smc.live.mode_t import ModeTDirector, ModeTLedger

    class FakeOutcome:
        def __init__(self):
            self.success = True
            self.retcode = 10008
            self.ticket = 77

    director = ModeTDirector(
        ledger=ModeTLedger(tmp_path / "ev.jsonl"),
        place_fn=lambda d, c: FakeOutcome(), cancel_fn=lambda t: True,
        clock=_clock(),
    )
    director.consider(
        poi_id="poi-abcdef12", detection_tf="H4", trigger_letter="F",
        direction=Direction.LONG,
        proof_bar=5, proof_high=100.4, proof_low=99.6, proof_close=100.0,
        atr=2.0, session_ok=True, spread_gate_ok=True,
        product_ticket_active=False, concurrent_open=0, volume_min=0.01,
        bar_index=10,
    )
    marker = director.latest_entry_marker()
    assert marker is not None
    assert marker["direction"] == "BUY"
    assert marker["entry"] == 100.0
    assert "Mode T LIMIT 100.00" in marker["text"]

    records = snapshot_to_records(
        symbol="XAUUSDm", structure={}, mode="T", heartbeat_ok=True,
        mode_t_poi=marker,
        updated_at_utc="2026-10-15T09:30:00Z",
    )
    entry_rows = [r for r in records if r.kind == "entry_t"]
    assert len(entry_rows) == 1
    assert entry_rows[0].price_high == 100.0
    assert entry_rows[0].id.startswith("entry_t_")


def test_entry_t_row_clears_after_cancel(tmp_path):
    from smc.live.mode_t import ModeTDirector, ModeTLedger
    cancel = Mock(side_effect=lambda t: True)

    class FakeOutcome:
        def __init__(self):
            self.success = True
            self.retcode = 10008
            self.ticket = 42

    director = ModeTDirector(
        ledger=ModeTLedger(tmp_path / "ev.jsonl"),
        place_fn=lambda d, c: FakeOutcome(), cancel_fn=cancel,
        clock=_clock(),
    )
    director.consider(
        poi_id="poi-abcdef12", detection_tf="H4", trigger_letter="F",
        direction=Direction.LONG,
        proof_bar=0, proof_high=100.4, proof_low=99.6, proof_close=100.0,
        atr=2.0, session_ok=True, spread_gate_ok=True,
        product_ticket_active=False, concurrent_open=0, volume_min=0.01,
        bar_index=10,
    )
    assert director.latest_entry_marker() is not None
    # Rest-expiry cancels the ticket → the line must come off the chart.
    director.manage(bar_index=10 + 12, friday_eod=False, invalidated_pois=[])
    assert director.latest_entry_marker() is None


def test_entry_t_dry_run_row_is_flagged_not_sent(tmp_path):
    from smc.live.mode_t import ModeTDirector, ModeTLedger

    director = ModeTDirector(
        ledger=ModeTLedger(tmp_path / "ev.jsonl"),
        place_fn=None,                                  # dry_run wiring
        cancel_fn=None, clock=_clock(),
    )
    director.consider(
        poi_id="poi-abcdef12", detection_tf="H4", trigger_letter="F",
        direction=Direction.SHORT,
        proof_bar=5, proof_high=100.4, proof_low=99.6, proof_close=100.0,
        atr=2.0, session_ok=True, spread_gate_ok=True,
        product_ticket_active=False, concurrent_open=0, volume_min=0.01,
        bar_index=10,
    )
    marker = director.latest_entry_marker()
    assert marker is not None
    assert marker["direction"] == "SELL"
    assert marker["entry"] == 100.0
    assert "(dry-run, not sent)" in marker["text"]


def test_rejected_place_never_draws_entry_t(tmp_path):
    from smc.live.mode_t import ModeTDirector, ModeTLedger

    class RejectedOutcome:
        success = False
        retcode = 10004
        ticket = None

    director = ModeTDirector(
        ledger=ModeTLedger(tmp_path / "ev.jsonl"),
        place_fn=lambda d, c: RejectedOutcome(), cancel_fn=lambda t: True,
        clock=_clock(),
    )
    director.consider(
        poi_id="poi-abcdef12", detection_tf="H4", trigger_letter="F",
        direction=Direction.LONG,
        proof_bar=5, proof_high=100.4, proof_low=99.6, proof_close=100.0,
        atr=2.0, session_ok=True, spread_gate_ok=True,
        product_ticket_active=False, concurrent_open=0, volume_min=0.01,
        bar_index=10,
    )
    # Ledger keeps the decision trail — but the chart shows no phantom line.
    assert director.latest_entry_marker() is None
