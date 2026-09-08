"""Phase 4 — TriggerRouter: chronological first-valid over the §15 matrix."""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.triggers.base_trigger import Trigger, TriggerContext, TriggerSignal
from smc.triggers.compatibility_matrix import DEFAULT_MATRIX
from smc.triggers.trigger_router import TriggerRouter

TF = Timeframe.M5

# Reuse the Trigger A bullish CHOCH geometry (fires only at bar 13).
_BULLISH_ROWS = [
    (100.0, 100.4, 99.8, 100.2),    # 0
    (100.2, 100.7, 100.0, 100.5),   # 1
    (100.5, 101.1, 100.4, 100.9),   # 2
    (100.9, 101.5, 100.7, 101.3),   # 3 last valid high 101.5
    (101.3, 101.6, 101.0, 101.2),   # 4
    (101.1, 101.4, 100.8, 100.9),   # 5
    (100.9, 101.1, 100.5, 100.6),   # 6
    (100.6, 100.8, 100.1, 100.2),   # 7
    (100.2, 100.4, 99.5, 99.9),     # 8 last valid low 99.5
    (99.9, 100.1, 99.4, 99.8),      # 9 sweep
    (99.8, 100.0, 99.6, 99.7),      # 10
    (99.7, 100.0, 99.5, 99.9),      # 11
    (100.0, 100.4, 99.8, 100.2),    # 12
    (100.3, 102.0, 100.1, 101.8),   # 13 CHOCH break
]


def _poi(direction=Direction.LONG):
    return POI(
        zone=Zone(top=100.0, bottom=98.0, direction=direction, timeframe=TF),
        models=[ModelType.M1],
    )


def test_scan_returns_first_chronological_route(candle_factory, swing_factory):
    candles = candle_factory(_BULLISH_ROWS, timeframe=TF)
    swings = [
        swing_factory(candles, 3, True, level=101.5),
        swing_factory(candles, 8, False, level=99.5),
    ]
    router = TriggerRouter()
    route = router.scan(_poi(), candles, swings, from_bar=8)
    assert route is not None
    assert route.bar == 13
    assert route.signal.trigger is TriggerType.A_CHOCH
    assert route.signal.direction is Direction.LONG


def test_scan_returns_none_when_no_trigger_completes(candle_factory, swing_factory):
    candles = candle_factory(_BULLISH_ROWS, timeframe=TF)
    swings = [
        swing_factory(candles, 3, True, level=101.5),
        swing_factory(candles, 8, False, level=99.5),
    ]
    # SHORT POI: the fixture only completes a bullish (LONG) CHOCH.
    router = TriggerRouter()
    assert router.scan(_poi(direction=Direction.SHORT), candles, swings, from_bar=8) is None


def test_evaluate_at_returns_signal_only_at_completion_bar(candle_factory, swing_factory):
    candles = candle_factory(_BULLISH_ROWS, timeframe=TF)
    swings = [
        swing_factory(candles, 3, True, level=101.5),
        swing_factory(candles, 8, False, level=99.5),
    ]
    router = TriggerRouter()
    assert router.evaluate_at(_poi(), candles, swings, 12, from_bar=8) is None
    route = router.evaluate_at(_poi(), candles, swings, 13, from_bar=8)
    assert route is not None and route.signal.trigger is TriggerType.A_CHOCH


def test_eligible_types_cover_all_triggers_for_m1(candle_factory):
    router = TriggerRouter()
    assert set(router.eligible_types(_poi())) == set(TriggerType)


class _StubTrigger(Trigger):
    """Deterministic trigger that fires a signal at EVERY evaluated bar."""

    def __init__(self, trigger_type: TriggerType):
        self.type = trigger_type

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        return TriggerSignal(
            trigger=self.type,
            direction=context.poi.zone.direction,
            entry_price=100.0,
            stop_reference=99.0,
            completion_index=context.current_bar,
            expiry_bars=20,
            detail=f"stub {self.type.value}",
        )


def _router_with(triggers: list[Trigger]) -> TriggerRouter:
    return TriggerRouter(triggers=triggers, matrix=DEFAULT_MATRIX)


def test_same_bar_equal_grade_earlier_letter_wins_over_f(candle_factory):
    """I3 regression: on equal bar + equal grade, A must beat F.

    The stub F is evaluated FIRST in the trigger list, so an implementation
    that let the later letter win on equal grade (or kept the last signal)
    would return F and fail this test.
    """
    candles = candle_factory(_BULLISH_ROWS, timeframe=TF)
    poi = _poi()
    # Deliberately F before A — list order must NOT decide the tie-break.
    router = _router_with(
        [_StubTrigger(TriggerType.F_BOS_OB), _StubTrigger(TriggerType.A_CHOCH)]
    )
    route = router.evaluate_at(poi, candles, [], bar=13, from_bar=8)
    assert route is not None
    assert route.signal.trigger is TriggerType.A_CHOCH  # A wins, not F


def test_same_bar_higher_grade_still_wins_over_letter(candle_factory):
    """Grade outranks letter: C (preferred for M8) beats A on the same bar."""
    candles = candle_factory(_BULLISH_ROWS, timeframe=TF)
    poi = POI(
        zone=Zone(top=100.0, bottom=98.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M8],  # C is PREFERRED for M8
    )
    router = _router_with(
        [
            _StubTrigger(TriggerType.A_CHOCH),
            _StubTrigger(TriggerType.C_ENDING_DIAGONAL),
        ]
    )
    route = router.evaluate_at(poi, candles, [], bar=13, from_bar=8)
    assert route is not None
    assert route.signal.trigger is TriggerType.C_ENDING_DIAGONAL


def test_eligible_ordering_is_letter_ascending_within_grade():
    # Matrix alignment (I3): within an equal grade the earlier letter comes
    # first — for M1 every trigger is STRUCTURAL, so the list is A..F.
    eligible = DEFAULT_MATRIX.eligible_triggers([ModelType.M1])
    assert eligible == sorted(eligible, key=lambda t: t.value)
    assert eligible[0] is TriggerType.A_CHOCH
    assert eligible.index(TriggerType.A_CHOCH) < eligible.index(TriggerType.F_BOS_OB)
