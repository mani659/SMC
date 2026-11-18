"""Parallel dedicated confirmation books — spike tests.

Pins the spike's contract (design: ``PARALLEL_DEDICATED_PATH_DESIGN.md``):

1. **Default parity** — an empty selection keeps the shipped single menu, and
   the production book is the shipped tier table verbatim.
2. **Book definition** — a tag book reuses the shipped tier geometry and only
   narrows ``trigger_types``; ``D`` is refused (R-K).
3. **Isolation** — one book's win never consumes another book's POI one-shot
   and never closes its window (per-book one-story, R-A).
4. **Cross-book dedupe** — the SAME executable plan from two books produces one
   ticket, counted with a machine-readable reason (+ opposite-direction
   coexistence is counted, R-B left open).
5. **Identity** — comments carry ``SMC-<TAG>-`` for a dedicated book and stay
   byte-identical for production / unstamped candidates; magic offset is
   deterministic.
6. **Shared envelope** — the layer owns no risk component, and one engine's
   same-level memory gates both books.
"""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone

import pytest

from smc.backtest.runner import CandidateEntry
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.execution.order_identity import (
    MT5_COMMENT_MAX,
    book_comment,
    book_identity,
    book_magic,
)
from smc.orchestration.parallel_books import (
    MID_TIER_NAMES,
    PROD_BOOK_ID,
    ParallelBookMenu,
    cross_book_plan_key,
    resolve_book_selection,
    same_cross_book_plan,
)
from smc.orchestration.product_menu_mtf import (
    PRODUCT_MENU_TIERS,
    MenuEpisodeStatus,
    ProductMenuEngine,
)
from smc.risk.risk_engine import (
    BLOCK_SAME_LEVEL,
    EntryRequest,
    RiskAction,
    RiskEngine,
)
from smc.triggers.base_trigger import Trigger, TriggerContext, TriggerSignal
from smc.triggers.trigger_router import TriggerRouter

BASE = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
H4_CLOSE = BASE + timedelta(hours=4)
ZONE_LOW = 2490.0
ZONE_HIGH = 2500.0

_TT = {
    "A": TriggerType.A_CHOCH,
    "B": TriggerType.B_LEADING_DIAGONAL,
    "F": TriggerType.F_BOS_OB,
}


# --------------------------------------------------------------------------- #
# Fixtures (same geometry conventions as test_product_menu_mtf.py)
# --------------------------------------------------------------------------- #
class StubTrigger(Trigger):
    """Fires on every evaluation with a configurable trigger letter."""

    def __init__(self, trigger_type: TriggerType, fire: bool = True) -> None:
        self.type = trigger_type
        self.fire = fire
        self.calls = 0

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        self.calls += 1
        if not self.fire:
            return None
        candle = context.candles[context.bar_index]
        return TriggerSignal(
            trigger=self.type,
            direction=Direction.LONG,
            entry_price=candle.close + 0.5,
            stop_reference=candle.low - 1.0,
            completion_index=context.bar_index,
            expiry_bars=10,
            detail="stub-fire",
            data={},
        )


def _bar(tf: Timeframe, offset_minutes: float, *, low=2485.0, high=2505.0,
         close=2500.0, open_=2496.0) -> Candle:
    return Candle(
        timestamp=BASE + timedelta(minutes=offset_minutes),
        open=open_, high=high, low=low, close=close, timeframe=tf,
    )


def _sweep(tf: Timeframe, offset_minutes: float = 0.0) -> Candle:
    """LONG sweep of the 2490..2500 demand zone: wick below, body back inside."""
    return _bar(tf, offset_minutes, low=2485.0, high=2498.0, close=2492.0)


def _confirm(tf: Timeframe, offset_minutes: float, *, close=2497.0) -> Candle:
    return _bar(tf, offset_minutes, low=2491.0, high=2499.0, close=close)


def _demand_poi(tf: Timeframe = Timeframe.H4, poi_id: str = "poi-1") -> POI:
    zone = Zone(top=ZONE_HIGH, bottom=ZONE_LOW, direction=Direction.LONG,
                timeframe=tf)
    return POI(
        zone=zone, models=[ModelType.M8], score=3.0, state=POIState.CREATED,
        m8_kind="demand_supply", id=poi_id,
    )


def _menu(*book_ids: str) -> ParallelBookMenu:
    menu = ParallelBookMenu(resolve_book_selection(list(book_ids)),
                            symbol="TEST")
    for bid in book_ids:
        menu.engine(bid)._router = TriggerRouter(
            triggers=[StubTrigger(_TT[bid], fire=False)]
        )
    return menu


def _set_stub(menu: ParallelBookMenu, book_id: str, fire: bool) -> StubTrigger:
    stub = StubTrigger(_TT[book_id], fire=fire)
    menu.engine(book_id)._router = TriggerRouter(triggers=[stub])
    return stub


def _candidate(**over) -> CandidateEntry:
    stamp = over.pop("stamp", None)
    payload = {} if stamp is None else {"product_menu": stamp}
    base = dict(
        direction=Direction.LONG,
        entry_price=2500.0,
        sl_price=2490.0,
        tp_price=2520.0,
        poi_id="poi-1",
        trigger="B",
        route_id="poi-1:B@12",
        zone_low=ZONE_LOW,
        zone_high=ZONE_HIGH,
        signal_data_json=json.dumps(payload) if stamp is not None else None,
    )
    base.update(over)
    return CandidateEntry(**base)


# --------------------------------------------------------------------------- #
# 1. Default parity
# --------------------------------------------------------------------------- #
def test_empty_selection_means_the_shipped_single_menu():
    assert resolve_book_selection(None) == ()
    assert resolve_book_selection([]) == ()
    assert resolve_book_selection(()) == ()


def test_prod_book_is_the_shipped_tier_table_verbatim():
    (book,) = resolve_book_selection(["PROD"])
    assert book.book_id == PROD_BOOK_ID
    assert book.tag is None
    assert book.menu_tiers() == PRODUCT_MENU_TIERS
    assert book.detection_tiers == ("DAY", "H4", "H1", "M15")


def test_prod_book_menu_is_not_a_second_strategy_stack():
    """One production book == one shipped engine (same tiers, same surface)."""
    menu = ParallelBookMenu(resolve_book_selection(["PROD"]), symbol="TEST")
    assert menu.engine("PROD").tiers == PRODUCT_MENU_TIERS
    assert menu.detection_timeframes == (
        Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15)
    assert menu.confirmation_timeframes == (
        Timeframe.H1, Timeframe.M5, Timeframe.M15, Timeframe.M1)
    assert menu.tier_for(Timeframe.M1) is None


def test_tier_for_is_instance_scoped_and_keeps_the_module_fallback():
    from dataclasses import replace

    shipped = {t.name: t for t in PRODUCT_MENU_TIERS}
    narrowed = ProductMenuEngine(
        symbol="TEST",
        tiers=(replace(shipped["H4"], trigger_types=(TriggerType.B_LEADING_DIAGONAL,)),),
    )
    assert narrowed.tier_for(Timeframe.H4) is narrowed.tiers[0]
    assert narrowed.tier_for(Timeframe.H4).trigger_types == (
        TriggerType.B_LEADING_DIAGONAL,)
    # The module map stays the fallback (existing callers unchanged).
    assert narrowed.tier_for(Timeframe.H1) is shipped["H1"]
    # The multiplexer refuses to let that fallback cross a book boundary: a
    # mid-tier book carries H4/H1/M15 but never DAY.
    menu = _menu("B")
    assert menu.tier_for(Timeframe.H1) is not None
    assert menu.tier_for(Timeframe.D1) is None


# --------------------------------------------------------------------------- #
# 2. Book definition (shipped geometry, narrowed triggers)
# --------------------------------------------------------------------------- #
def test_tag_book_narrows_only_the_trigger_subset():
    (book,) = resolve_book_selection(["B"])
    assert book.tag is TriggerType.B_LEADING_DIAGONAL
    assert book.tag_letter == "B"
    assert book.detection_tiers == ("H4", "H1", "M15")
    shipped = {t.name: t for t in PRODUCT_MENU_TIERS}
    assert [t.name for t in book.menu_tiers()] == ["H4", "H1", "M15"]
    for tier in book.menu_tiers():
        assert tier.trigger_types == (TriggerType.B_LEADING_DIAGONAL,)
        assert tier.detection_tf is shipped[tier.name].detection_tf
        assert tier.confirmation_tfs == shipped[tier.name].confirmation_tfs
        assert tier.expiry_bars == shipped[tier.name].expiry_bars
    assert book.confirm_tf_map[Timeframe.H1] == (Timeframe.M5, Timeframe.M1)


def test_f_book_carries_all_four_tiers_evidenced_by_R1():
    (book,) = resolve_book_selection(["F"])
    assert book.detection_tiers == ("DAY", "H4", "H1", "M15")
    assert all(t.trigger_types == (TriggerType.F_BOS_OB,)
               for t in book.menu_tiers())


def test_d_book_is_refused_R_K():
    with pytest.raises(ValueError, match="excluded"):
        resolve_book_selection(["D"])


def test_unknown_and_duplicate_books_are_refused():
    with pytest.raises(ValueError, match="unknown book"):
        resolve_book_selection(["Z"])
    with pytest.raises(ValueError, match="duplicate book ids"):
        resolve_book_selection(["B", "B"])
    with pytest.raises(ValueError, match="unknown tiers"):
        resolve_book_selection([{"book_id": "B", "tag": "B",
                                 "detection_tiers": ["M1"]}])


def test_mid_tier_set_matches_the_design():
    assert MID_TIER_NAMES == ("H4", "H1", "M15")


def test_book_cannot_arm_a_detection_tier_it_does_not_carry():
    menu = _menu("B")
    poi = _demand_poi(Timeframe.D1, "poi-d1")
    assert menu.register_armed(poi, Timeframe.D1) is False
    assert menu.engine("B")._armed == {}


# --------------------------------------------------------------------------- #
# 3. Isolation: per-book one-shot (R-A)
# --------------------------------------------------------------------------- #
def test_a_win_in_one_book_does_not_consume_another_books_poi():
    menu = _menu("F", "B")
    _set_stub(menu, "B", fire=True)
    _set_stub(menu, "F", fire=False)
    poi = _demand_poi(Timeframe.H4, "poi-twin")
    assert menu.register_armed(poi, Timeframe.H4) is True

    menu.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]},
                          as_of=H4_CLOSE)
    # Both books opened their OWN one-shot window: no cross-book arbitration.
    assert len(menu.engine("B").episodes()) == 1
    assert len(menu.engine("F").episodes()) == 1

    winners = menu.on_execution_bar(
        {Timeframe.M15: [_confirm(Timeframe.M15, 300)]},
        as_of=BASE + timedelta(hours=5, minutes=15),
    )
    assert [w.trigger for w in winners] == ["B"]
    assert "poi-twin" in menu.engine("B")._consumed
    assert "poi-twin" not in menu.engine("F")._consumed
    assert menu.engine("F").episodes()[0].status is MenuEpisodeStatus.ACTIVE


# --------------------------------------------------------------------------- #
# 4. Cross-book plan identity + dedupe (R-H) and direction coexistence (R-B)
# --------------------------------------------------------------------------- #
def test_cross_book_identity_ignores_the_trigger_letter():
    b = _candidate(trigger="B")
    f = _candidate(trigger="F", route_id="poi-1:F@12")
    assert cross_book_plan_key(b) is not None
    assert same_cross_book_plan(cross_book_plan_key(b), cross_book_plan_key(f))
    # A different entry price is a different order.
    other = _candidate(entry_price=2501.0, trigger="F")
    assert not same_cross_book_plan(
        cross_book_plan_key(b), cross_book_plan_key(other))
    # Opposite direction is a DIFFERENT order (R-B case, counted not merged).
    flipped = _candidate(direction=Direction.SHORT, trigger="F")
    assert not same_cross_book_plan(
        cross_book_plan_key(b), cross_book_plan_key(flipped))
    # Unknown geometry is never collapsed.
    assert cross_book_plan_key(_candidate(sl_price=None)) is None
    unknown = _candidate(zone_low=None, zone_high=None)
    assert not same_cross_book_plan(
        cross_book_plan_key(b), cross_book_plan_key(unknown))


def test_identical_plan_from_two_books_places_one_ticket():
    menu = _menu("B", "F")
    _set_stub(menu, "B", fire=True)
    _set_stub(menu, "F", fire=True)
    poi = _demand_poi(Timeframe.H4, "poi-1")
    menu.register_armed(poi, Timeframe.H4)
    menu.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]},
                          as_of=H4_CLOSE)
    emitted = menu.on_execution_bar(
        {Timeframe.M15: [_confirm(Timeframe.M15, 300)]},
        as_of=BASE + timedelta(hours=5, minutes=15),
    )
    # Both books won their own window; only ONE ticket is emitted.
    assert len(menu.engine("B").winners) == 1
    assert len(menu.engine("F").winners) == 1
    assert len(emitted) == 1
    assert emitted[0].trigger == "B"          # fixed book order: B before F
    counters = menu.counters()
    assert counters["cross_book_duplicates"] == 1
    assert counters["book_emitted_counts"] == {"B": 1, "F": 0}
    (event,) = menu.cross_book_events()
    assert event["event"] == "cross_book_duplicate"
    assert event["book_id"] == "F" and event["owner_book"] == "B"
    assert event["poi_id"] == "poi-1" and event["owner_poi"] == "poi-1"
    menu.assert_tag_purity()                   # no cross-tag leak


def test_every_emitted_candidate_is_stamped_with_its_book():
    menu = _menu("B")
    _set_stub(menu, "B", fire=True)
    poi = _demand_poi(Timeframe.H4, "poi-1")
    menu.register_armed(poi, Timeframe.H4)
    menu.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]},
                          as_of=H4_CLOSE)
    (winner,) = menu.on_execution_bar(
        {Timeframe.M15: [_confirm(Timeframe.M15, 300)]},
        as_of=BASE + timedelta(hours=5, minutes=15),
    )
    stamp = json.loads(winner.candidate.signal_data_json)["product_menu"]
    assert stamp["book_id"] == "B" and stamp["book_tag"] == "B"
    assert book_identity(winner.candidate) == ("B", "B")
    # R-J: direction is on the candidate for journal identity (no inference).
    assert getattr(winner.candidate, "direction", None) is Direction.LONG


def test_cross_tag_leak_in_a_pure_book_fails_loud():
    menu = _menu("F")
    # A book whose router emits the WRONG letter is exactly the leak R1
    # failed loud on; the multiplexer owns the same check.
    menu.engine("F")._router = TriggerRouter(
        triggers=[StubTrigger(TriggerType.B_LEADING_DIAGONAL, fire=True)]
    )
    poi = _demand_poi(Timeframe.H4, "poi-1")
    menu.register_armed(poi, Timeframe.H4)
    menu.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]},
                          as_of=H4_CLOSE)
    menu.on_execution_bar({Timeframe.M15: [_confirm(Timeframe.M15, 300)]},
                          as_of=BASE + timedelta(hours=5, minutes=15))
    with pytest.raises(RuntimeError, match="CROSS_TAG_LEAK"):
        menu.assert_tag_purity()


# --------------------------------------------------------------------------- #
# 5. Order identity (R-D: comment now, magic only with sign-off)
# --------------------------------------------------------------------------- #
def test_comment_names_the_book_for_a_dedicated_book():
    cand = _candidate(stamp={"book_id": "B", "book_tag": "B"})
    assert book_comment(cand, "poi-1:B@12") == "SMC-B-poi-1:B@12"
    assert book_comment(cand, "") == "SMC-B"


def test_comment_is_byte_identical_for_production_and_unstamped_candidates():
    base = "poi-1:F@4521"
    assert book_comment(_candidate(), base) == base
    assert book_comment(_candidate(stamp={"book_id": "PROD"}), base) == base
    assert book_identity(_candidate()) == (None, None)


def test_comment_respects_the_mt5_width():
    long_id = "poi-000123456789:B@123456789"
    cand = _candidate(stamp={"book_id": "F", "book_tag": "F"})
    comment = book_comment(cand, long_id)
    assert len(comment) <= MT5_COMMENT_MAX
    assert comment.startswith("SMC-F-")


def test_book_magic_is_a_deterministic_offset():
    assert book_magic(20260919, 0) == 20260919
    assert book_magic(20260919, 2) == 20260921
    with pytest.raises(ValueError):
        book_magic(20260919, -1)


# --------------------------------------------------------------------------- #
# 6. Shared risk envelope
# --------------------------------------------------------------------------- #
def test_parallel_books_own_no_risk_component():
    params = inspect.signature(ParallelBookMenu.__init__).parameters
    assert "risk_engine" not in params
    menu = _menu("B", "F")
    assert not hasattr(menu, "risk_engine")


def test_one_envelope_gates_both_books():
    """One account-level guard blocks a level from BOTH books."""
    risk = RiskEngine()
    risk.same_level_guard.record_close(2490.0, 10)

    def request() -> EntryRequest:
        return EntryRequest(
            direction=Direction.LONG, entry_price=2500.0, sl_price=2490.0,
            atr=10.0, current_bar=11, now=BASE, equity=10_000.0,
            risk_fraction=0.01, pip_value_per_lot=100.0,
            min_lots=0.01, lot_step=0.01, allowed_sessions=None,
        )

    book_b = risk.evaluate_entry(request())   # book B's candidate
    book_f = risk.evaluate_entry(request())   # book F's candidate
    assert book_b.blocked_by == book_f.blocked_by == BLOCK_SAME_LEVEL
    # A per-book envelope would have let the second book through — the shared
    # one is what prevents the same level being taken twice.
    fresh = RiskEngine()
    assert fresh.evaluate_entry(request()).action is RiskAction.ENTER
