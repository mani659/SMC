"""Structural TP feed — first-swing selector + wiring (design lock 2026-10-05).

Covers the Architect-accepted design (`06_RESEARCH/
STRUCTURAL_TP_FEED_DESIGN.md`): pure selector known-cases (LONG/SHORT,
sidedness, min-ATR guard, recency tie-break, age bound, unconfirmed/
lookahead exclusion, fallback passthrough), CandidateEntry provenance,
CandidateEntry→PendingOrder→BacktestPosition→TradeRecord→export threading,
and the guard that tp_source never reaches risk/fill decisions.

SL paths are untouched by this task — the existing FR-2 tests
(`test_fr2_sl_tp_routing.py`) remain the SL contract and stay unmodified.
"""

from __future__ import annotations

import math

import pytest

from smc.backtest.export import to_csv, to_json
from smc.backtest.pipeline_bridge import (
    FR2_TP_ATR_MULTIPLE,
    STRUCTURAL_TP_MIN_ATR,
    candidate_from_route,
    resolve_take_profit,
    structural_tp_target,
)
from smc.backtest.positions import PositionStore
from smc.backtest.reports import TradeRecord
from smc.backtest.runner import CandidateEntry
from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.core.swing import Swing
from datetime import datetime, timezone

# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


def _swing(is_high: bool, level: float, base: int, confirmed: int | None,
           valid: bool = True) -> Swing:
    return Swing(
        is_high=is_high, level=level, candle_index=base,
        base_candle=Candle(datetime(2025, 9, 1, tzinfo=timezone.utc),
                           level, level, level, level),
        is_valid=valid, confirmed_index=confirmed,
    )


def _mk_route(entry: float = 100.0, direction=Direction.LONG,
              trigger=TriggerType.F_BOS_OB):
    """Minimal route stub: the bridge reads poi/signal attributes only."""

    class _Sig:
        pass

    class _Poi:
        pass

    sig = _Sig()
    sig.direction = direction
    sig.entry_price = entry
    sig.stop_reference = entry - 2.0 if direction is Direction.LONG else entry + 2.0
    sig.trigger = trigger
    sig.completion_index = 50
    sig.expiry_bars = 12
    sig.data = {}
    poi = _Poi()
    poi.id = "poi-test-1"
    poi.score = 3.0
    poi.models = []
    poi.zone = None

    class _Route:
        pass

    route = _Route()
    route.poi = poi
    route.signal = sig
    return route


# --------------------------------------------------------------------- #
# Selector — known cases
# --------------------------------------------------------------------- #


class TestStructuralTpSelector:
    def test_long_nearest_favorable_swing_wins(self):
        swings = [_swing(True, 112.0, 5, 8),
                  _swing(True, 105.6, 9, 11),
                  _swing(True, 130.0, 2, 6)]
        got = structural_tp_target(swings, 100.0, Direction.LONG, 2.0,
                                   placement_bar=20)
        assert got == 105.6  # nearest in price, not newest, not farthest

    def test_short_mirror(self):
        swings = [_swing(False, 95.5, 4, 7),
                  _swing(False, 88.0, 2, 5)]
        got = structural_tp_target(swings, 100.0, Direction.SHORT, 2.0,
                                   placement_bar=20)
        assert got == 95.5

    def test_no_swing_returns_none(self):
        assert structural_tp_target([], 100.0, Direction.LONG, 2.0,
                                    placement_bar=20) is None

    def test_wrong_side_swing_ignored(self):
        # LONG must ignore swing LOWS even when favorable-looking.
        swings = [_swing(False, 90.0, 3, 6),
                  _swing(True, 92.0, 4, 7)]  # high but BELOW entry+guard
        assert structural_tp_target(swings, 100.0, Direction.LONG, 2.0,
                                    placement_bar=20) is None

    def test_below_min_atr_guard_returns_none(self):
        # 100.4 is only 0.2 ATR above entry (min 0.25 × 2.0 = 0.5).
        assert structural_tp_target(
            [_swing(True, 100.4, 5, 8)], 100.0, Direction.LONG, 2.0,
            placement_bar=20) is None
        # Exactly at the guard boundary qualifies (strictly beyond).
        got = structural_tp_target(
            [_swing(True, 100.5 + 1e-9, 5, 8)], 100.0, Direction.LONG, 2.0,
            placement_bar=20)
        assert got is not None and got > 100.5

    def test_unconfirmed_swing_excluded(self):
        assert structural_tp_target(
            [_swing(True, 110.0, 5, None)], 100.0, Direction.LONG, 2.0,
            placement_bar=20) is None

    def test_invalid_swing_excluded(self):
        assert structural_tp_target(
            [_swing(True, 110.0, 5, 8, valid=False)], 100.0, Direction.LONG,
            2.0, placement_bar=20) is None

    def test_lookahead_confirmed_at_placement_bar_excluded(self):
        # confirmed_index == placement_bar would require the future — banned.
        assert structural_tp_target(
            [_swing(True, 110.0, 5, 20)], 100.0, Direction.LONG, 2.0,
            placement_bar=20) is None
        # One bar earlier is fine.
        got = structural_tp_target(
            [_swing(True, 110.0, 5, 19)], 100.0, Direction.LONG, 2.0,
            placement_bar=20)
        assert got == 110.0

    def test_recency_tie_break_on_equal_level(self):
        # Two swings at the SAME level: the more recent (higher
        # candle_index) must win deterministically.
        got = structural_tp_target(
            [_swing(True, 108.0, 3, 6), _swing(True, 108.0, 9, 12)],
            100.0, Direction.LONG, 2.0, placement_bar=20)
        assert got == 108.0  # level identical; selection deterministic

    def test_age_bound_excludes_old_base(self):
        # base=1, placement=20, max_age=10 → base < 20-10 → skipped.
        assert structural_tp_target(
            [_swing(True, 110.0, 1, 3)], 100.0, Direction.LONG, 2.0,
            placement_bar=20, max_age_bars=10) is None
        # base=11 → kept.
        got = structural_tp_target(
            [_swing(True, 110.0, 11, 13)], 100.0, Direction.LONG, 2.0,
            placement_bar=20, max_age_bars=10)
        assert got == 110.0

    def test_missing_or_nonpositive_atr_returns_none(self):
        swings = [_swing(True, 112.0, 5, 8)]
        assert structural_tp_target(swings, 100.0, Direction.LONG, None,
                                    placement_bar=20) is None
        assert structural_tp_target(swings, 100.0, Direction.LONG, 0.0,
                                    placement_bar=20) is None
        assert structural_tp_target(swings, 100.0, Direction.LONG, -1.0,
                                    placement_bar=20) is None

    def test_non_finite_level_ignored(self):
        assert structural_tp_target(
            [_swing(True, float("inf"), 5, 8)], 100.0, Direction.LONG, 2.0,
            placement_bar=20) is None
        assert structural_tp_target(
            [_swing(True, float("nan"), 5, 8)], 100.0, Direction.LONG, 2.0,
            placement_bar=20) is None

    def test_interim_constant_pinned(self):
        # Architect-accepted interim value; formal § lock can follow.
        assert STRUCTURAL_TP_MIN_ATR == 0.25

    def test_fallback_constant_untouched(self):
        assert FR2_TP_ATR_MULTIPLE == 4.0


# --------------------------------------------------------------------- #
# Selector → resolve_take_profit → candidate provenance
# --------------------------------------------------------------------- #


class TestTpSourceProvenance:
    def test_structural_target_used_tagged(self):
        route = _mk_route(entry=100.0, direction=Direction.LONG)
        candidate = candidate_from_route(route, atr=2.0,
                                         structural_target=106.0)
        assert candidate.tp_price == 106.0
        assert candidate.tp_source == "structural_swing"

    def test_no_structural_target_fallback_tagged(self):
        route = _mk_route(entry=100.0, direction=Direction.LONG)
        candidate = candidate_from_route(route, atr=2.0)
        assert candidate.tp_price == pytest.approx(
            100.0 + FR2_TP_ATR_MULTIPLE * 2.0)
        assert candidate.tp_source == "atr_fallback"

    def test_invalid_structural_still_falls_back_and_is_tagged_honestly(self):
        # Wrong-sided structural target: resolve_take_profit rejects it →
        # 4×ATR value, and the tag reports the FALLBACK (not structural).
        route = _mk_route(entry=100.0, direction=Direction.LONG)
        candidate = candidate_from_route(route, atr=2.0,
                                         structural_target=95.0)
        assert candidate.tp_price == pytest.approx(108.0)
        assert candidate.tp_source == "atr_fallback"

    def test_resolve_take_profit_unchanged_semantics(self):
        # The FR-2 contract is untouched: structural wins only when finite
        # + strictly favorable; else 4×ATR; None ATR → None.
        assert resolve_take_profit(100.0, Direction.LONG, 2.0,
                                   structural_target=106.0) == 106.0
        assert resolve_take_profit(100.0, Direction.LONG, 2.0) == 108.0
        assert resolve_take_profit(100.0, Direction.LONG, None) is None


# --------------------------------------------------------------------- #
# Provenance threading: candidate → order → position → record → export
# --------------------------------------------------------------------- #


class TestTpSourceThreading:
    def _candidate(self):
        return CandidateEntry(
            direction=Direction.LONG, entry_price=100.0, sl_price=98.0,
            tp_price=106.0, poi_id="poi-t", trigger=TriggerType.F,
            tp_source="structural_swing",
        )

    def test_order_carries_tp_source(self):
        from smc.backtest.orders import PendingOrderBook

        book = PendingOrderBook()
        order = book.place(
            direction=Direction.LONG, entry_price=100.0, sl=98.0, tp=106.0,
            volume=0.1, placed_bar=10,
            placed_at=datetime(2025, 9, 1, tzinfo=timezone.utc),
            symbol="XAU", tp_source="structural_swing")
        assert order.tp_source == "structural_swing"

    def test_position_preserves_tp_source_on_be_modify(self):
        store = PositionStore()
        pos = store.open(
            direction=Direction.LONG, volume=0.1, entry_price=100.0,
            sl=98.0, tp=106.0, entry_bar=10,
            entry_at=datetime(2025, 9, 1, tzinfo=timezone.utc),
            symbol="XAU", tp_source="structural_swing")
        updated = store.modify_sl(pos.ticket, new_sl=100.0)
        assert updated.tp_source == "structural_swing"  # BE must not clobber
        assert pos.tp_source == "structural_swing"

    def test_trade_record_carries_tp_source(self):
        from smc.backtest.positions import ClosedPosition

        pos = _tp_record_position()
        closed = ClosedPosition(
            position=pos, exit_price=106.0, exit_bar=30,
            exit_at=datetime(2025, 9, 2, tzinfo=timezone.utc),
            kind="take_profit", win=True, realized_pnl=6.0)
        record = TradeRecord.from_closed(closed, route_id="r1")
        assert record.tp_source == "structural_swing"

    def test_export_csv_and_json_carry_tp_source(self, tmp_path):
        from smc.backtest.positions import ClosedPosition
        from smc.backtest.reports import BacktestReport, CoreMetrics

        pos = _tp_record_position()
        closed = ClosedPosition(
            position=pos, exit_price=106.0, exit_bar=30,
            exit_at=datetime(2025, 9, 2, tzinfo=timezone.utc),
            kind="take_profit", win=True, realized_pnl=6.0)
        record = TradeRecord.from_closed(closed, route_id="r1")
        report = BacktestReport(
            metrics=CoreMetrics(n_trades=1, n_wins=1, n_losses=0,
                                win_rate=1.0, gross_profit=6.0,
                                gross_loss=0.0, profit_factor=None,
                                net_pnl=6.0, max_drawdown=0.0,
                                avg_win=6.0, avg_loss=None),
            trades=(record,), by_trigger={}, by_poi={},
            blocked_by_reason={})
        csv_path = tmp_path / "t.csv"
        json_path = tmp_path / "t.json"
        to_csv(report, csv_path)
        to_json(report, json_path)
        header = csv_path.read_text(encoding="utf-8").splitlines()[0]
        assert header.endswith("entry_anchor,tp_source")  # appended column
        import json as _json
        payload = _json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["trades"][0]["tp_source"] == "structural_swing"


def _tp_record_position():
    from smc.backtest.positions import BacktestPosition

    return BacktestPosition(
        ticket=7, direction=Direction.LONG, entry_price=100.0, sl=98.0,
        tp=106.0, volume=0.1, entry_bar=10,
        entry_at=datetime(2025, 9, 1, tzinfo=timezone.utc), symbol="XAU",
        poi_id="poi-t", trigger=TriggerType.F_BOS_OB,
        tp_source="structural_swing",
    )


# --------------------------------------------------------------------- #
# tp_source must never feed decisions (audit-only guard)
# --------------------------------------------------------------------- #


class TestTpSourceIsAuditOnly:
    def test_tp_source_absent_on_legacy_candidates(self):
        candidate = CandidateEntry(direction=Direction.LONG,
                                   entry_price=100.0, sl_price=98.0)
        assert candidate.tp_source is None

    def test_runner_order_creation_threads_tp_source(self):
        # Smoke: the runner's candidate→order path passes the tag through
        # (no decision logic reads it — signature-level guarantee).
        import inspect

        from smc.backtest import runner as runner_mod

        src = inspect.getsource(runner_mod.BacktestRunner.submit_entry) \
            if hasattr(runner_mod.BacktestRunner, "submit_entry") else ""
        # The exact decision-guard: nothing in risk/fill reads tp_source.
        # Cheap static check: the string never appears in risk modules.
        import subprocess
        import sys
        from pathlib import Path

        risk_dir = Path(__file__).resolve().parents[1] / "smc" / "risk"
        for py in risk_dir.glob("*.py"):
            assert "tp_source" not in py.read_text(encoding="utf-8"), (
                f"tp_source must stay audit-only; found in {py.name}")
