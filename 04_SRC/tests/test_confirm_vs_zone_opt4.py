"""OPT-4 place-side distance + R7 verdict tests (logging ONLY).

Design: 06_RESEARCH/CONFIRM_VS_ZONE_DESIGN.md OPT-4 (place-side join).
Extends OPT-1 (confirm-side stamps + ``menu_confirm``) with the SUBMIT-BAR
frame at the R7 seam: every place decision (placed / skip_far_from_zone /
other block code) carries ``distance_at_place_atr`` (nearest zone edge,
0 inside, in ATR — the ONE OPT-1 convention) and ``r7_verdict`` (the EXISTING
machine-readable code), plus the menu-stamp join keys already on the
candidate. Nothing here is read by a decision; the place/skip boolean
outcomes must stay byte-stable versus the pre-change fixtures (same runs
already pinned by test_fill_regime_r7_r8 / test_r9_place_on_reentry).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from smc.backtest.runner import CandidateEntry
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.execution.order_manager import OrderManager
from smc.execution.position_manager import PositionManager
from smc.paper.kpi_logger import KPILogger
from smc.paper.runner import PaperConfig, PaperRunner
from smc.risk.fill_regime_policy import (
    SKIP_PLACE_FAR_FROM_ZONE,
)
from smc.risk.risk_engine import BLOCK_SESSION, RiskEngine
from smc.utils.timestamps import Session

ROOT = Path(__file__).resolve().parents[2]
TF = Timeframe.M5
START = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)  # Thursday, London

# CALM: close 100.3 inside the [99, 101] zone and its band; resting buy-limit
# 100.0 never touched by low 100.1 (same frozen fixtures as the R7/R9 tests).
CALM = (100.25, 100.45, 100.1, 100.3)
# FAR: a runaway close (the September 2025 class) — R7 must skip.
FAR = (104.0, 104.5, 103.5, 104.2)

SESSIONS = (Session.LONDON, Session.NEW_YORK)


class _StubAdapter:
    def __init__(self) -> None:
        self._candles = []
        self._runner = None
        self._queued = []
        self.accepted = []          # on_candidate_accepted — stays EMPTY on skips

    def bind(self, runner) -> None:
        self._runner = runner

    def generate_candidates(self, bar, bar_index, now) -> None:
        for candidate in self._queued:
            self._runner.submit_entry(candidate)
        self._queued = []

    def queue(self, candidate) -> None:
        self._queued.append(candidate)

    def on_candidate_accepted(self, candidate) -> None:
        self.accepted.append(candidate)


def _paper_runner(*, config=None, kpi=None):
    from tests.test_paper_runner import FakeConnector

    connector = FakeConnector()
    adapter = _StubAdapter()
    runner = PaperRunner(
        connector=connector,
        risk_engine=RiskEngine(),
        pipeline=adapter,
        order_manager=OrderManager(connector, symbol="XAUUSD.x", magic=999),
        position_manager=PositionManager(connector, symbol="XAUUSD.x"),
        config=config if config is not None else PaperConfig(),
        kpi=kpi,
        perf=lambda: 0.0,
    )
    adapter.bind(runner)
    return runner, adapter


def _seed(n=14):
    """14 warm-up bars of TR 2.0 → Wilder ATR 2.0 at the submit bar."""
    return [
        Candle(timestamp=START - timedelta(minutes=5 * (n - i)), open=100.0,
               high=101.0, low=99.0, close=100.0, timeframe=TF)
        for i in range(n)
    ]


def _paper_bar(minutes_after_start, row=CALM):
    ts = START + timedelta(minutes=minutes_after_start)
    o, h, l, c = row
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, timeframe=TF)


def _menu_stamp(**overrides) -> dict:
    """The OPT-1 menu stamp shape (as ProductMenuEngine._candidate builds)."""
    stamp = {
        "menu": "PRODUCT_MTF_MENU",
        "tier": "H4",
        "detection_tf": "H4",
        "confirmation_tf": "M15",
        "trigger": "F",
        "poi_id": "poi-1",
        "zone": [99.0, 101.0],
        "episode_id": "ep-1",
        "sweep_ts": START.isoformat(),
        "zone_direction": "long",
        "completion_index": 3,
        "completion_ts": START.isoformat(),
        "completion_close": 100.6,
        "atr_at_confirm": 2.0,
        "distance_at_confirm_atr": 0.0,
        "label_at_confirm": "LATE",
    }
    stamp.update(overrides)
    return stamp


def _candidate(**overrides) -> CandidateEntry:
    kwargs = dict(
        direction=Direction.LONG,
        entry_price=100.0,
        sl_price=99.0,
        tp_price=104.0,
        score=10.0,  # A+ spread grade — the spread gate never blocks
        zone_low=99.0,
        zone_high=101.0,
        route_id="poi-1:F@5",
        poi_id="poi-1",
        trigger=TriggerType.F_BOS_OB,
        detection_tf=Timeframe.H4,
    )
    kwargs.update(overrides)
    return CandidateEntry(**kwargs)


def _records(kpi, event):
    return [r for r in kpi.records if r.event == event]


# --------------------------------------------------------------------------- #
# 1. Place path — distance + verdict logged when R7 places
# --------------------------------------------------------------------------- #
def test_place_path_logs_distance_and_verdict():
    kpi = KPILogger()
    runner, _adapter = _paper_runner(kpi=kpi)
    _adapter._candles = _seed()
    _adapter.queue(_candidate())                       # market close in-band
    runner.run_one_cycle(_paper_bar(0))
    placed = _records(kpi, "place_placed")
    assert len(placed) == 1
    fields = placed[0].fields
    assert fields["r7_verdict"] == "placed"
    # close 100.3 is INSIDE the [99, 101] zone → 0.0 nearest-edge distance
    assert fields["distance_at_place_atr"] == 0.0
    assert fields["poi_id"] == "poi-1"
    assert fields["route_id"] == "poi-1:F@5"
    # the seam logged exactly one verdict; no skip anywhere
    assert _records(kpi, "place_skip") == []
    # byte-stable outcome: the order WAS placed (same as before the change)
    assert len(runner._pendings) == 1
    assert _records(kpi, "entry_blocked") == []


def test_dry_run_still_records_the_placed_verdict():
    kpi = KPILogger()
    runner, _adapter = _paper_runner(
        config=PaperConfig(dry_run=True), kpi=kpi)
    _adapter._candles = _seed()
    _adapter.queue(_candidate())
    runner.run_one_cycle(_paper_bar(0))
    placed = _records(kpi, "place_placed")
    assert len(placed) == 1
    assert placed[0].fields["r7_verdict"] == "placed"
    assert placed[0].fields["dry_run"] is True
    assert len(runner._pendings) == 0                  # dry-run: never sent
    assert len(_adapter.accepted) == 0


# --------------------------------------------------------------------------- #
# 2. Skip_far path — skip verdict + distance logged when R7 skips
# --------------------------------------------------------------------------- #
def test_skip_far_path_logs_skip_verdict_and_distance():
    kpi = KPILogger()
    runner, _adapter = _paper_runner(kpi=kpi)
    _adapter._candles = _seed()
    # Market (close 104.2) beyond [99,101]+band(1.0)=102 → R7 skip, exactly
    # the fixture semantics test_fill_regime_r7_r8 pins (band 0.5×ATR=1.0).
    _adapter.queue(_candidate(entry_price=91.0, zone_low=90.0, zone_high=92.0))
    runner.run_one_cycle(_paper_bar(0, FAR))
    skips = _records(kpi, "place_skip")
    assert len(skips) == 1
    fields = skips[0].fields
    assert fields["r7_verdict"] == SKIP_PLACE_FAR_FROM_ZONE
    assert fields["reason"] == SKIP_PLACE_FAR_FROM_ZONE    # existing code kept
    # nearest edge = 92.0; the FAR bar extends the scan series before the
    # entry step (TR 4.5 vs prev close) → Wilder ATR = (2.0·13+4.5)/14 =
    # 2.1785714…; (104.2 − 92.0)/ATR = 5.6 exactly — the seam's own atr.
    assert fields["distance_at_place_atr"] == pytest.approx(5.6)
    # byte-stable outcomes (identical to the pre-change fixture expectations):
    assert runner._pendings == {}                       # nothing placed
    assert _adapter.accepted == []                      # one-shot unburned
    assert len(runner.intents.alive_intents()) == 1     # R9 intent armed
    assert _records(kpi, "place_placed") == []          # no new verdict class


def test_placed_and_skip_verdict_classes_match_r7_boolean_exactly():
    """The verdict string follows the SAME seam boolean — never diverges."""
    kpi_on = KPILogger()
    runner, adapter = _paper_runner(kpi=kpi_on)
    adapter._candles = _seed()
    adapter.queue(_candidate())
    runner.run_one_cycle(_paper_bar(0))                 # CALM → placed
    kpi_off = KPILogger()
    runner2, adapter2 = _paper_runner(kpi=kpi_off)
    adapter2._candles = _seed()
    adapter2.queue(_candidate(entry_price=91.0, zone_low=90.0, zone_high=92.0))
    runner2.run_one_cycle(_paper_bar(0, FAR))           # FAR → skipped
    verdicts = [_r.fields["r7_verdict"] for _r in
                _records(kpi_on, "place_placed")
                + _records(kpi_off, "place_skip")]
    assert verdicts == ["placed", SKIP_PLACE_FAR_FROM_ZONE]


# --------------------------------------------------------------------------- #
# 3. Join keys from the OPT-1 menu stamp flow through the seam records
# --------------------------------------------------------------------------- #
def test_menu_stamp_join_keys_carry_onto_skip_record():
    kpi = KPILogger()
    runner, _adapter = _paper_runner(kpi=kpi)
    _adapter._candles = _seed()
    candidate = _candidate(
        entry_price=91.0, zone_low=90.0, zone_high=92.0,
        signal_data_json=json.dumps(
            {"trigger_signal_data": {}, "product_menu": _menu_stamp()}),
    )
    _adapter.queue(candidate)
    runner.run_one_cycle(_paper_bar(0, FAR))
    fields = _records(kpi, "place_skip")[0].fields
    assert fields["label_at_confirm"] == "LATE"
    assert fields["completion_ts"] == START.isoformat()


def test_menu_stamp_join_keys_carry_onto_placed_record():
    kpi = KPILogger()
    runner, _adapter = _paper_runner(kpi=kpi)
    _adapter._candles = _seed()
    _adapter.queue(_candidate(
        signal_data_json=json.dumps(
            {"trigger_signal_data": {}, "product_menu": _menu_stamp()})))
    runner.run_one_cycle(_paper_bar(0))
    fields = _records(kpi, "place_placed")[0].fields
    assert fields["label_at_confirm"] == "LATE"
    assert fields["completion_ts"] == START.isoformat()


def test_adapter_path_without_stamp_yields_none_join_keys_not_invention():
    kpi = KPILogger()
    runner, _adapter = _paper_runner(kpi=kpi)
    _adapter._candles = _seed()
    _adapter.queue(_candidate())          # no signal_data_json at all
    runner.run_one_cycle(_paper_bar(0))
    fields = _records(kpi, "place_placed")[0].fields
    assert fields["label_at_confirm"] is None
    assert fields["completion_ts"] is None


def test_entry_blocked_carries_verdict_code_and_distance_when_resolvable():
    """Risk blocks get the same treatment: verdict = the EXISTING code."""
    kpi = KPILogger()
    runner, _adapter = _paper_runner(
        config=PaperConfig(allowed_sessions=()), kpi=kpi)
    _adapter._candles = _seed()
    _adapter.queue(_candidate())
    runner.run_one_cycle(_paper_bar(0))          # outside every session
    blocked = _records(kpi, "entry_blocked")
    assert len(blocked) == 1
    fields = blocked[0].fields
    assert fields["r7_verdict"] == BLOCK_SESSION   # existing machine-readable code
    assert fields["distance_at_place_atr"] == 0.0
    assert fields["poi_id"] == "poi-1"
    # byte-stable: nothing placed, same block surface as before
    assert runner._pendings == {}
    assert runner.block_reasons() == {"session": 1}


# --------------------------------------------------------------------------- #
# 4. The helper itself — OPT-1 convention, honest None, no invention
# --------------------------------------------------------------------------- #
def test_place_distance_helper_matches_the_opt1_formula():
    from smc.orchestration.product_menu_mtf import (
        completion_zone_edge_distance_atr,
    )

    zone = _candidate()                          # zone [99, 101]
    assert _place_distance_atr(zone, 100.3, 2.0) == 0.0
    assert _place_distance_atr(zone, 104.2, 2.0) == 1.6
    assert _place_distance_atr(zone, 97.0, 2.0) == 1.0
    # parity with the OPT-1 helper for the identical inputs (one formula)
    for close, atr in ((100.3, 2.0), (104.2, 2.0), (97.0, 2.0), (100.0, 0.5)):
        assert _place_distance_atr(zone, close, atr) == \
            completion_zone_edge_distance_atr(99.0, 101.0, close, atr)


def test_place_distance_helper_honest_none():
    assert _place_distance_atr(_candidate(zone_low=None, zone_high=None),
                               100.3, 2.0) is None
    assert _place_distance_atr(_candidate(), None, 2.0) is None
    assert _place_distance_atr(_candidate(), 100.3, None) is None


def _place_distance_atr(candidate, market_close, atr):
    from smc.paper.runner import _place_distance_atr as runner_helper
    return runner_helper(candidate, market_close, atr)


# --------------------------------------------------------------------------- #
# 5. Flag / freeze discipline
# --------------------------------------------------------------------------- #
def test_opt_b_flag_default_is_still_off_and_live_flag_is_false():
    from smc.orchestration.product_menu_mtf import ProductMenuEngine

    assert ProductMenuEngine(symbol="TEST").same_bar_asof is False
    cfg = json.loads(
        (ROOT / "config" / "live_demo.json").read_text(encoding="utf-8"))
    assert cfg["enable_opt_b_same_bar_confirm"] is False
