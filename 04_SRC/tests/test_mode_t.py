"""Mode T seam tests (design lock 00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md).

Covers: the pure rule T2 decision matrix (§2.2), the frozen taxonomy
(exhaustive), the banner string (§2.1), the director book (caps, rest
expiry, §5 invalidation, Friday EOD, one-shot, PLACE_REJECTED tail), the
config surface (§2.1/§3.1/§5), and the constant home rule (§1 — Mode T
numbers live in smc.live.mode_t, never locked_constants).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from smc.core.enums import Direction
from smc.live.mode_t import (
    ACTION_PLACE,
    ACTION_SKIP,
    CAP_CONCURRENT,
    CAP_DAILY,
    GAP_TOO_WIDE,
    INVALIDATED_BEFORE_PLACE,
    MINIMUM_VOLUME_ERROR,
    MODE_T_BANNER,
    MIN_LOT_FLOOR,
    ModeTDecision,
    ModeTDirector,
    ModeTLedger,
    NO_ATR,
    NO_SESSION,
    PRODUCT_PATH_TAKEN,
    SPREAD_GATE,
    T_MAX_CONCURRENT,
    T_MAX_GAP_ATR,
    T_MAX_PER_DAY,
    T_REST_BARS,
    T_TP_ATR,
    SKIP_REASONS,
    decide_mode_t,
    is_skip_reason,
    place_rejected,
)


# --------------------------------------------------------------------- #
# 2.1 — banner + constants home
# --------------------------------------------------------------------- #
def test_banner_matches_design_verbatim():
    assert MODE_T_BANNER == (
        "[MODE T] DIAGNOSTIC ENTRY PATH ACTIVE — every order logs mode=T; "
        "product Mode A path unchanged; diagnostic only, NOT a strategy claim"
    )


def test_frozen_constants_match_design():
    assert T_MAX_GAP_ATR == 0.25
    assert T_TP_ATR == 1.0
    assert T_REST_BARS == 12
    assert T_MAX_CONCURRENT == 2
    assert T_MAX_PER_DAY == 6
    assert MIN_LOT_FLOOR == 0.01


def test_mode_t_constants_never_leak_into_locked_constants():
    import smc.config.locked_constants as locked

    names = [name for name in dir(locked) if name.startswith("T_")]
    assert not names


# --------------------------------------------------------------------- #
# 2.2 — the frozen skip taxonomy
# --------------------------------------------------------------------- #
def test_skip_taxonomy_exhaustive_membership():
    expected = {
        "GAP_TOO_WIDE", "NO_ATR", "NO_SESSION", "SPREAD_GATE",
        "DUPLICATE_EPISODE", "PRODUCT_PATH_TAKEN",
        "CAP_CONCURRENT", "CAP_DAILY", "MINIMUM_VOLUME_ERROR",
        "INVALIDATED_BEFORE_PLACE",
    }
    assert set(SKIP_REASONS) == expected
    for reason in expected:
        assert is_skip_reason(reason)
    assert not is_skip_reason("SOMETHING_INVENTED")
    assert is_skip_reason(place_rejected(10004))
    assert place_rejected(10004) == "PLACE_REJECTED_10004"


def _place_kwargs(**overrides):
    base = dict(
        proof_high=100.4,
        proof_low=99.6,
        proof_close=100.0,
        atr=2.0,
        direction=Direction.LONG,
        session_ok=True,
        spread_gate_ok=True,
        duplicate=False,
        product_ticket_active=False,
        concurrent_open=0,
        placed_today=0,
        volume_min=0.01,
    )
    base.update(overrides)
    return base


# --------------------------------------------------------------------- #
# 2.2 — rule T2 decision matrix
# --------------------------------------------------------------------- #
def test_t2_accept_places_limit_at_proof_mid():
    decision = decide_mode_t(**_place_kwargs())
    assert decision.action == ACTION_PLACE
    assert decision.entry == pytest.approx((100.4 + 99.6) / 2)   # mid
    assert decision.sl == pytest.approx(99.6)                     # adverse extreme (LONG)
    assert decision.tp == pytest.approx(decision.entry + 1.0 * 2.0)  # T_TP_ATR
    assert decision.volume == pytest.approx(0.01)                 # min lot
    assert decision.gap_atr == pytest.approx(0.0)                 # mid vs close 100.0
    assert decision.skip_reason is None


def test_t2_short_brackets_mirror():
    decision = decide_mode_t(**_place_kwargs(direction=Direction.SHORT))
    assert decision.action == ACTION_PLACE
    assert decision.sl == pytest.approx(100.4)                    # adverse extreme (SHORT)
    assert decision.tp == pytest.approx(decision.entry - 2.0)


def test_t2_rejects_gap_beyond_0_25_atr():
    # entry mid = 100.0; close 99.0 → gap = 1.0/2.0 = 0.5 > 0.25.
    decision = decide_mode_t(**_place_kwargs(proof_close=99.0))
    assert decision.action == ACTION_SKIP
    assert decision.skip_reason == GAP_TOO_WIDE
    assert decision.entry is None and decision.sl is None


def test_t2_gap_guard_quality_uses_small_atr_fail_closed():
    # entry mid 100.0; close 99.96 → gap = 0.04/0.02 = 2.0 > 0.25 → skip.
    decision = decide_mode_t(**_place_kwargs(proof_close=99.96, atr=0.02))
    assert decision.skip_reason == GAP_TOO_WIDE


def test_t2_no_atr_fails_closed_never_market():
    decision = decide_mode_t(**_place_kwargs(atr=None))
    assert decision.skip_reason == NO_ATR
    decision = decide_mode_t(**_place_kwargs(atr=0.0))
    assert decision.skip_reason == NO_ATR


def test_t2_session_and_spread_gates_precede_geometry():
    session = decide_mode_t(**_place_kwargs(session_ok=False))
    assert session.skip_reason == NO_SESSION
    spread = decide_mode_t(**_place_kwargs(spread_gate_ok=False))
    assert spread.skip_reason == SPREAD_GATE


def test_product_wins_ties():
    decision = decide_mode_t(**_place_kwargs(product_ticket_active=True))
    assert decision.action == ACTION_SKIP
    assert decision.skip_reason == PRODUCT_PATH_TAKEN


def test_caps_fire_after_geometry():
    concurrent = decide_mode_t(**_place_kwargs(concurrent_open=T_MAX_CONCURRENT))
    assert concurrent.skip_reason == CAP_CONCURRENT
    daily = decide_mode_t(**_place_kwargs(placed_today=T_MAX_PER_DAY))
    assert daily.skip_reason == CAP_DAILY


def test_minimum_volume_error_when_broker_volume_invalid():
    decision = decide_mode_t(**_place_kwargs(volume_min=0.0))
    assert decision.skip_reason == MINIMUM_VOLUME_ERROR


def test_duplicate_event_consumed():
    decision = decide_mode_t(**_place_kwargs(duplicate=True))
    assert decision.skip_reason == "DUPLICATE_EPISODE"


def test_ledger_line_fields_per_note_2_5():
    decision = decide_mode_t(**_place_kwargs())
    line = decision.ledger_line(anomaly_ts="2026-10-15T09:30:00")
    assert line["mode"] == "T"
    assert line["anomaly_ts_iso"] == "2026-10-15T09:30:00"
    assert line["exec_tf"] == "M5"
    assert "poi_id" in line and "entry" in line and "skip_reason" in line
    # Expert placeholders BLANK in V1 — never invented by code.
    assert line["level_ok"] is None
    assert line["sweep_ok"] is None
    assert line["confirm_ok"] is None
    assert line["timing"] is None
    assert line["would_take"] is None


# --------------------------------------------------------------------- #
# Director book (one-shot, caps counting, rest/invalidation/EOD, rejects)
# --------------------------------------------------------------------- #
class FakeOutcome:
    def __init__(self, success=True, retcode=10008, ticket=11):
        self.success = success
        self.retcode = retcode
        self.ticket = ticket


def _clock(s="2026-10-15T09:30:00"):
    return lambda: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_director_place_success_books_ticket(tmp_path):
    place = Mock(side_effect=lambda d, c: FakeOutcome(ticket=77))
    cancels = Mock(side_effect=lambda t: True)
    director = ModeTDirector(
        ledger=ModeTLedger(tmp_path / "ev.jsonl"),
        place_fn=place, cancel_fn=cancels, clock=_clock(),
    )
    decision = director.consider(
        poi_id="poi-abcdef12", detection_tf="H4", trigger_letter="F",
        direction=Direction.LONG,
        proof_bar=5, proof_high=100.4, proof_low=99.6, proof_close=100.0,
        atr=2.0, session_ok=True, spread_gate_ok=True,
        product_ticket_active=False, concurrent_open=0, volume_min=0.01,
        bar_index=10,
    )
    assert decision.action == ACTION_PLACE
    assert director.resting == {"poi-abcdef12": 77}
    # one-shot: re-draw same (poi, proof) → same stored decision, NO re-send
    again = director.consider(
        poi_id="poi-abcdef12", detection_tf="H4", trigger_letter="F",
        direction=Direction.LONG,
        proof_bar=5, proof_high=100.4, proof_low=99.6, proof_close=100.0,
        atr=2.0, session_ok=True, spread_gate_ok=True,
        product_ticket_active=False, concurrent_open=9, volume_min=0.01,
        bar_index=11,
    )
    assert again.action == ACTION_PLACE
    assert place.call_count == 1
    comment = place.call_args[0][1]
    assert comment == "mode=T|T2|poi-abcd@5"   # §2.3: poi prefix truncated to 8
    # ledger has exactly one decision line
    lines = (tmp_path / "ev.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["mode"] == "T"


def test_director_place_rejected_emits_taxonomy_tail(tmp_path):
    place = Mock(side_effect=lambda d, c: FakeOutcome(success=False, retcode=10004, ticket=None))
    director = ModeTDirector(
        ledger=ModeTLedger(tmp_path / "ev.jsonl"),
        place_fn=place, cancel_fn=lambda t: True, clock=_clock(),
    )
    decision = director.consider(
        poi_id="poi-abcdef12", detection_tf="H4", trigger_letter="F",
        direction=Direction.LONG,
        proof_bar=5, proof_high=100.4, proof_low=99.6, proof_close=100.0,
        atr=2.0, session_ok=True, spread_gate_ok=True,
        product_ticket_active=False, concurrent_open=0, volume_min=0.01,
        bar_index=10,
    )
    assert decision.action == ACTION_SKIP
    assert decision.skip_reason == "PLACE_REJECTED_10004"
    assert is_skip_reason(decision.skip_reason)
    lines = (tmp_path / "ev.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # the PLACE decision + the rejected outcome line


def test_director_rest_expiry_after_12_bars(tmp_path):
    cancel = Mock(side_effect=lambda t: True)
    director = ModeTDirector(
        ledger=ModeTLedger(tmp_path / "ev.jsonl"),
        place_fn=lambda d, c: FakeOutcome(ticket=5), cancel_fn=cancel,
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
    out = director.manage(bar_index=10 + T_REST_BARS - 1, friday_eod=False,
                          invalidated_pois=[])
    assert out == []
    out = director.manage(bar_index=10 + T_REST_BARS, friday_eod=False,
                          invalidated_pois=[])
    assert out == [("poi-abcdef12", "REST_EXPIRED")]
    assert director.resting == {}
    cancel.assert_called_once_with(5)


def test_director_invalidation_cancels(tmp_path):
    cancel = Mock(side_effect=lambda t: True)
    director = ModeTDirector(
        ledger=ModeTLedger(tmp_path / "ev.jsonl"),
        place_fn=lambda d, c: FakeOutcome(ticket=9), cancel_fn=cancel,
        clock=_clock(),
    )
    director.consider(
        poi_id="poi-abcdef12", detection_tf="H4", trigger_letter="F",
        direction=Direction.SHORT,
        proof_bar=0, proof_high=100.4, proof_low=99.6, proof_close=100.0,
        atr=2.0, session_ok=True, spread_gate_ok=True,
        product_ticket_active=False, concurrent_open=0, volume_min=0.01,
        bar_index=3,
    )
    out = director.manage(bar_index=4, friday_eod=False,
                          invalidated_pois=["poi-abcdef12"])
    assert out == [("poi-abcdef12", INVALIDATED_BEFORE_PLACE)]


def test_director_daily_cap_resets_on_new_utc_day(tmp_path):
    counter = {"n": 0}

    def place(d, c):
        counter["n"] += 1
        return FakeOutcome(ticket=100 + counter["n"])

    clock = {"day": "2026-10-15"}
    directors_clock = _clock(f"{clock['day']}T23:59:00")
    director = ModeTDirector(
        ledger=ModeTLedger(tmp_path / "ev.jsonl"),
        place_fn=place, cancel_fn=lambda t: True, clock=directors_clock,
    )

    def run_one(poi_suffix):
        director.consider(
            poi_id=f"poi-{poi_suffix}", detection_tf="H4",
            trigger_letter="F", direction=Direction.LONG,
            proof_bar=77, proof_high=100.4, proof_low=99.6,
            proof_close=100.0, atr=2.0,
            session_ok=True, spread_gate_ok=True,
            product_ticket_active=False,
            concurrent_open=0, volume_min=0.01, bar_index=1,
        )

    for i in range(3):
        run_one(f"aa{i}1")   # same UTC day (clock frozen)
    assert director.placed_today == 3
    run_one("aa4")
    assert director.placed_today == 4
    # the 5th/6th... a new UTC day resets the counter (hard test: wrap clock)
    director._clock = _clock("2026-10-16T00:05:00")
    run_one("aa7")
    assert director.placed_today == 1


# --------------------------------------------------------------------- #
# Config surface (§2.1 OFF product / §5 ON tester; knob)
# --------------------------------------------------------------------- #
def test_operator_config_defaults_off(tmp_path):
    from smc.live.operator_config import load_operator_config
    cfg_file = tmp_path / "c.json"
    cfg_file.write_text("{}", encoding="utf-8")
    cfg = load_operator_config(cfg_file)
    assert cfg.diagnostic_entries is False
    assert cfg.judge_interval_s == 60.0
    assert cfg.marker_enabled is True
    assert cfg.marker_path == ""


def test_tester_config_mode_t_on_and_demo():
    from smc.live.operator_config import load_operator_config
    p = Path(__file__).resolve().parents[2] / "config" / "live_tester.json"
    cfg = load_operator_config(p)
    assert cfg.diagnostic_entries is True
    assert cfg.require_demo is True
    assert cfg.judge_interval_s > 0
    assert cfg.marker_enabled is True


def test_demo_config_diagnostic_entries_absent_or_false():
    from smc.live.operator_config import load_operator_config
    p = Path(__file__).resolve().parents[2] / "config" / "live_demo.json"
    cfg = load_operator_config(p)
    assert cfg.diagnostic_entries is False


def test_session_start_payload_carries_mode_disriminator(tmp_path):
    """R2 (design §2.1): the session-start JSON must discriminate
    posture — "T" when diagnostic_entries is true, "A" otherwise;
    banner and log lines stay unchanged."""
    from smc.live.operator_config import load_operator_config
    from smc.live.run_operator import OperatorSession

    base = {
        "symbol": "XAUUSDm", "magic": 42, "dry_run": True,
        "log_dir": str(tmp_path / "logs"),
    }
    opt_file = tmp_path / "t.json"
    opt_file.write_text(json.dumps({**base, "diagnostic_entries": True}),
                        encoding="utf-8")
    session_t = OperatorSession(load_operator_config(opt_file))
    payload_t = session_t._session_start_payload()
    assert payload_t["mode"] == "T"

    off_file = tmp_path / "a.json"
    off_file.write_text(json.dumps(base), encoding="utf-8")
    session_a = OperatorSession(load_operator_config(off_file))
    payload_a = session_a._session_start_payload()
    assert payload_a["mode"] == "A"


def test_config_rejects_mode_t_geometry_keys(tmp_path):
    from smc.live.operator_config import ConfigError, load_operator_config
    cfg_file = tmp_path / "c.json"
    cfg_file.write_text(
        json.dumps({"t_max_gap_atr": 0.9}), encoding="utf-8"
    )
    with pytest.raises(ConfigError):
        load_operator_config(cfg_file)
    cfg_file.write_text(
        json.dumps({"diagnostic_entries": True, "t_tp_atr": 9.0}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_operator_config(cfg_file)


# --------------------------------------------------------------------- #
# Ledger tail honesty
# --------------------------------------------------------------------- #
def test_ledger_tail_empty_when_missing(tmp_path):
    assert ModeTLedger(tmp_path / "missing.jsonl").tail(5) == []
