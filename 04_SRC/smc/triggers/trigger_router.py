"""Trigger routing — chronological first-valid wins (LOCKED §12, R1 §11).

The router scans the execution-timeframe series bar by bar from the POI's
arm bar onward. At each bar every MATRIX-ELIGIBLE trigger for the POI's
model tags is evaluated (each detector only reports a signal whose entry
condition completes at that bar). The FIRST bar at which any eligible
trigger fires is the winner — frozen chronological rule; there is no
priority hierarchy.

Event identity (R1 §11): one validated POI + one LTF trigger + one
execution. When two triggers complete on the SAME bar, §12 is silent; the
V1 tie-break is the §15 compatibility grade (PREFERRED > STRUCTURAL >
UNCOMMON, computed across the POI's tags), then trigger letter order with
the EARLIER letter winning (A before F, pinned post-audit) — the matrix
therefore influences routing as a tie-break only (no frozen cell is
forbidden; see ``compatibility_matrix``).

Only a FRESH POI is routed (the engine guarantees ``can_trade``).
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.core.candle import Candle
from smc.core.enums import TriggerType
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.triggers.base_trigger import Trigger, TriggerContext, TriggerSignal
from smc.triggers.compatibility_matrix import (
    DEFAULT_MATRIX,
    CompatibilityMatrix,
)
from smc.triggers.trigger_a_choch import ChochReversalTrigger
from smc.triggers.trigger_b_leading_diagonal import LeadingDiagonalTrigger
from smc.triggers.trigger_c_ending_diagonal import EndingDiagonalTrigger
from smc.triggers.trigger_d_two_bar import TwoBarReversalTrigger
from smc.triggers.trigger_e_rsi_divergence import RsiDivergenceTrigger
from smc.triggers.trigger_expiry import poi_give_up_bars
from smc.triggers.trigger_f_bos_ob import BosObContinuationTrigger

__all__ = ["TriggerRouter", "TriggerRoute", "default_triggers", "DEFAULT_TRIGGERS"]


@dataclass(frozen=True, slots=True)
class TriggerRoute:
    """The winning trigger signal for one POI at one bar."""

    poi: POI
    bar: int
    signal: TriggerSignal


def default_triggers() -> list[Trigger]:
    """The six triggers A–F (order-independent — chronological scan rules)."""
    return [
        ChochReversalTrigger(),
        LeadingDiagonalTrigger(),
        EndingDiagonalTrigger(),
        TwoBarReversalTrigger(),
        RsiDivergenceTrigger(),
        BosObContinuationTrigger(),
    ]


DEFAULT_TRIGGERS = default_triggers()


class TriggerRouter:
    """Chronological first-valid router over matrix-eligible triggers."""

    def __init__(
        self,
        triggers: list[Trigger] | None = None,
        matrix: CompatibilityMatrix = DEFAULT_MATRIX,
    ) -> None:
        self.triggers = triggers if triggers is not None else DEFAULT_TRIGGERS
        self._by_type = {t.type: t for t in self.triggers}
        self.matrix = matrix

    # ------------------------------------------------------------------ #
    def eligible_types(self, poi: POI) -> list[TriggerType]:
        """Trigger letters eligible for the POI's tags (§15 matrix)."""
        return self.matrix.eligible_triggers(poi.models)

    def evaluate_at(
        self,
        poi: POI,
        candles: list[Candle],
        swings: list[Swing],
        bar: int,
        from_bar: int = 0,
        *,
        evaluation_candles: list[Candle] | None = None,
        evaluation_swings: list[Swing] | None = None,
        hints=None,
    ) -> TriggerRoute | None:
        """Best trigger signal completing at ``bar`` (grade tie-break).

        Same-bar tie-break (pinned post-audit): higher §15 grade wins; on
        EQUAL grade the EARLIER trigger letter wins (A before F). The key is
        ascending-negated grade so a strict ``<`` comparison keeps the first
        trigger at equal grade — A never loses to F on the same bar/grade.

        ``evaluation_candles`` / ``evaluation_swings`` (Phase C perf) are
        the incremental full-prefix series the evaluations read INSTEAD of
        prefix slices (every trigger read is bar-index-bounded, so the
        full series evaluates identically to the slice it replaces).
        ``hints`` (Phase C perf, duck-typed) carries the pre-computed
        full-prefix artifacts — ATR/RSI series (both price spaces), the
        mirrored candles/swings, and the base-sorted swing indexes — each
        value-identical to what the evaluation would rebuild in place
        (see the Phase C report). ``None`` keeps the legacy in-place path.
        """
        best: TriggerRoute | None = None
        best_key: tuple[int, str] | None = None
        eval_candles = candles if evaluation_candles is None else evaluation_candles
        eval_swings = swings if evaluation_swings is None else evaluation_swings
        for trigger_type in self.eligible_types(poi):
            trigger = self._by_type.get(trigger_type)
            if trigger is None:
                continue
            context = TriggerContext(
                poi=poi,
                candles=eval_candles,
                swings=eval_swings,
                bar_index=bar,
                from_bar=from_bar,
                hints=hints,
            )
            signal = trigger.evaluate(context)
            if signal is None:
                continue
            grade = max(
                (self.matrix.grade(model, trigger_type) for model in poi.models),
                key=lambda g: g.value,
            )
            key = (-grade.value, trigger_type.value)
            if best_key is None or key < best_key:
                best_key = key
                best = TriggerRoute(poi=poi, bar=bar, signal=signal)
        return best

    def scan(
        self,
        poi: POI,
        candles: list[Candle],
        swings: list[Swing],
        from_bar: int = 0,
        to_bar: int | None = None,
        *,
        scan_from: int | None = None,
        evaluation_candles: list[Candle] | None = None,
        evaluation_swings: list[Swing] | None = None,
        hints=None,
    ) -> TriggerRoute | None:
        """Chronological scan: the FIRST bar in ``[from_bar, to_bar]`` that fires.

        ``to_bar`` defaults to the last candle; the scan may be bounded by
        the POI give-up window (``from_bar + poi_give_up_bars()``) by the
        caller. Returns the earliest route (chronological rule, §12).

        ``scan_from`` (Phase B perf) starts the bar loop LATER without
        touching the evaluation anchor: every evaluated bar still receives
        ``from_bar`` (the episode anchor triggers A/D/E require — "the
        pattern must post-date the POI arming"), so a resumed scan returns
        the identical first route a full re-scan returns.

        ``evaluation_candles`` / ``evaluation_swings`` (Phase C perf) pass
        through to every evaluation (see ``evaluate_at``); ``to_bar`` still
        bounds the bar loop and the nominal ``candles``/``swings`` anchor
        the evaluated count. With no evaluation series supplied the scan
        reads ``candles``/``swings`` exactly as before — the give-up
        deadline is also re-derived from the NOMINAL series length (the
        historical behavior; the Phase C caller caps ``to_bar`` itself).
        """
        first = max(from_bar, scan_from) if scan_from is not None else from_bar
        if to_bar is None:
            to_bar = len(candles) - 1
        last = min(to_bar, len(candles) - 1)
        for bar in range(max(first, 0), last + 1):
            route = self.evaluate_at(
                poi, candles, swings, bar, from_bar,
                evaluation_candles=evaluation_candles,
                evaluation_swings=evaluation_swings,
                hints=hints,
            )
            if route is not None:
                return route
        return None

    def deadline_bars(self) -> int:
        """POI-wide \"no trigger fired\" window (§24 — V1, see trigger_expiry)."""
        return poi_give_up_bars()
