"""PipelineEngine — the Phase 4 integration seam (Stage 2 → 3 → 4).

The engine composes the frozen stages for ONE POI episode per the Phase 4
prompt's integration requirements:

* **Merge before validate** — same-direction overlapping POIs are merged by
  Phase 2 ``merge_overlapping`` BEFORE validation so Pillar 1's refinement
  scan and the §1 confluence score see every tag on the merged zone.
* **Displacement injection** — Phase 1 ``check_displacement`` results are
  injected per POI id; Pillar 2 stays UNAVAILABLE (reject) otherwise.
* **Score assignment** — ``score_poi`` runs only on validation PASS and only
  when ``poi.score == 0.0`` (owned by the Phase 3 pipeline).
* **M8 freshness** — M8 zones are NOT special-cased: they arm through the
  same §5 ``POIStateMachine`` and deactivate on first touch.
* **Pillar 4 is state-based** — the engine feeds per-bar touch/violation
  events from the POI's creation bar onward.
* **§7 inducement constants** — the inducement modifiers are consumed from
  ``locked_constants`` by the Phase 3 pipeline (no literals here).

Stage 3 routing is chronological first-valid (§12); the winning signal
becomes a LIMIT order (Trigger D is never a market order, §10). News (§11)
and session (§2) gates run before the order is placed.

The engine records each POI's ARM BAR so the §24 no-trigger give-up window
(``trigger_expiry.poi_give_up_bars``, V1 — Trigger A's frozen 20 M5 bars)
and the §23 unfilled-order expiry can be enforced against the §5 machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.detection.displacement_checker import DisplacementResult
from smc.execution.news_guard import NewsEvent, should_block_entry
from smc.execution.order_manager import OrderKind, OrderManager, OrderRequest, OrderResult
from smc.execution.session_filter import Session, is_allowed_session
from smc.poi.confluence_scorer import merge_overlapping
from smc.risk.lot_sizing import sized_lots
from smc.triggers.compatibility_matrix import DEFAULT_MATRIX, CompatibilityMatrix
from smc.triggers.trigger_expiry import poi_give_up_bars
from smc.triggers.trigger_router import TriggerRoute, TriggerRouter
from smc.validation.state_machine import POIStateMachine
from smc.validation.validation_pipeline import (
    ValidationPipeline,
    ValidationResult,
)

__all__ = ["PipelineEngine", "ExecutionOutcome", "build_limit_request"]


@dataclass(slots=True)
class ExecutionOutcome:
    """Result of routing one trigger to the execution layer."""

    route: TriggerRoute | None = None
    request: OrderRequest | None = None
    order_result: Optional[OrderResult] = None
    blocked: str | None = None  # reason when news/session gated the entry


@dataclass(slots=True)
class _PoiEpisode:
    """Engine bookkeeping per POI (in-memory V1 store)."""

    arm_bar: int
    fired: bool = False
    outcome: ExecutionOutcome | None = None


def build_limit_request(
    poi: POI,
    route: TriggerRoute,
    volume: float,
    symbol: str = "XAUUSD.x",
) -> OrderRequest:
    """Build the semantic LIMIT request for a winning trigger route.

    All six triggers are limit entries; ``route.signal.entry_price`` is the
    resting price and ``stop_reference`` the geometric stop level from the
    frozen spec (no buffer — broker stops-level/spread offset is a Phase 5
    execution concern).
    """
    return OrderRequest(
        symbol=symbol,
        kind=OrderKind.LIMIT,
        direction=route.signal.direction,
        volume=volume,
        price=route.signal.entry_price,
        sl=route.signal.stop_reference,
        comment=f"{poi.id[:8]}:{route.signal.trigger.value}@{route.bar}",
    )


class PipelineEngine:
    """Wires merge → validate → arm → trigger scan → limit execution."""

    def __init__(
        self,
        *,
        pipeline: ValidationPipeline | None = None,
        state_machine: POIStateMachine | None = None,
        router: TriggerRouter | None = None,
        order_manager: OrderManager | None = None,
        matrix: CompatibilityMatrix = DEFAULT_MATRIX,
        symbol: str = "XAUUSD.x",
    ) -> None:
        self.pipeline = pipeline if pipeline is not None else ValidationPipeline()
        self.state_machine = (
            state_machine if state_machine is not None else POIStateMachine()
        )
        self.router = router if router is not None else TriggerRouter(matrix=matrix)
        self.order_manager = order_manager
        self.symbol = symbol
        self._episodes: dict[str, _PoiEpisode] = {}

    # ------------------------------------------------------------------ #
    # Stage 2 — merge + validate
    # ------------------------------------------------------------------ #
    def merge(self, pois: list[POI]) -> list[POI]:
        """Merge same-direction overlapping POIs (tag union) BEFORE validation."""
        return merge_overlapping(pois)

    def validate(
        self,
        pois: list[POI],
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
        displacement_map: dict[str, DisplacementResult] | None = None,
        *,
        merge_first: bool = True,
        dealing_range=None,
        atr_period: int = 14,
    ) -> tuple[list[POI], list[ValidationResult]]:
        """Merge (optional), validate each POI, return (passed, results).

        ``displacement_map`` maps each FINAL poi id (post-merge) to its Phase
        1 displacement result — the Pillar 2 injection contract. When a POI
        has no entry, Pillar 2 is UNAVAILABLE and the POI is rejected
        (fail-fast — never a silent pass).
        """
        if merge_first:
            pois = self.merge(pois)
        displacement_map = displacement_map or {}
        passed: list[POI] = []
        results: list[ValidationResult] = []
        for poi in pois:
            result = self.pipeline.validate(
                poi,
                candles,
                swings,
                liquidity_levels,
                dealing_range=dealing_range,
                displacement=displacement_map.get(poi.id),
                atr_period=atr_period,
            )
            results.append(result)
            if result.passed:
                passed.append(poi)
        return passed, results

    # ------------------------------------------------------------------ #
    # Stage 3 — arm bookkeeping
    # ------------------------------------------------------------------ #
    def arm_at(self, poi: POI, arm_bar: int) -> None:
        """Arm a CREATED POI (CREATED → FRESH) and record its arm bar.

        POIs validated through :meth:`validate` are already FRESH; this also
        accepts them. The arm bar anchors the §24 no-trigger give-up window.
        """
        if poi.state is POIState.CREATED:
            self.state_machine.arm(poi)
        if poi.state is not POIState.FRESH:
            raise ValueError("arm_at expects a CREATED or FRESH POI")
        self._episodes[poi.id] = _PoiEpisode(arm_bar=arm_bar)

    def episode(self, poi: POI) -> _PoiEpisode | None:
        """Engine bookkeeping for a POI (None when not armed through this engine)."""
        return self._episodes.get(poi.id)

    # ------------------------------------------------------------------ #
    # Stage 3 — per-bar trigger scan + state feed (Pillar 4 events)
    # ------------------------------------------------------------------ #
    def feed_bar(self, poi: POI, candle: Candle) -> str:
        """Feed one execution-TF bar into the §5 machine (touch/violation).

        Returns the resulting state name. Only FRESH POIs move; a first
        touch → TESTED, a close beyond the zone without a touch → VIOLATED.
        """
        current = self.state_machine.current(poi)
        if current is not POIState.FRESH:
            return current.value
        if self.state_machine.touches_zone(poi, candle):
            return self.state_machine.on_touch(poi).value
        zone = poi.zone
        violated = (
            candle.high < zone.bottom
            if zone.direction is Direction.LONG
            else candle.low > zone.top
        )
        if violated:
            return self.state_machine.on_violation(poi).value
        return POIState.FRESH.value

    def scan_route(
        self,
        poi: POI,
        candles: list[Candle],
        swings: list[Swing],
        from_bar: int | None = None,
    ) -> TriggerRoute | None:
        """Chronological trigger scan within the §24 give-up window.

        Returns the FIRST valid route (bar order, §12). The scan is bounded
        by ``arm_bar + poi_give_up_bars()`` (V1, documented — see
        ``trigger_expiry.poi_give_up_bars``).
        """
        episode = self._episodes.get(poi.id)
        start = episode.arm_bar if episode is not None else (from_bar or 0)
        deadline = start + poi_give_up_bars()
        return self.router.scan(poi, candles, swings, from_bar=start, to_bar=deadline)

    # ------------------------------------------------------------------ #
    # Stage 4 — route → order (news + session gates)
    # ------------------------------------------------------------------ #
    def execute_route(
        self,
        route: TriggerRoute,
        *,
        volume: float,
        now: datetime,
        news_events: list[NewsEvent] | None = None,
        allowed_sessions: list[Session] | tuple[Session, ...] | None = None,
    ) -> ExecutionOutcome:
        """Turn a winning route into a placed LIMIT order (guarded).

        §11 news guard: no entries around CPI/NFP/FOMC. §2 session gate:
        entries only in the allowed sessions (``None`` = no session gate).
        The clock is INJECTED — ``now`` is a required keyword (never
        ``datetime.now()``) so backtest runs stay fully deterministic.

        Blocked outcomes (news/session) do NOT consume the §11 one-shot
        event identity: only an accepted execution attempt marks the POI as
        fired, so a route blocked now may be re-attempted later.

        The order volume comes from :meth:`compute_risk_lots` (the §28.7
        policy path — band clamp + ``LOT_MAX_SAFETY`` cap).
        """
        poi = route.poi
        episode = self._episodes.get(poi.id)
        if episode is None:
            raise ValueError("route POI was not armed through this engine")
        if episode.fired:
            return episode.outcome or ExecutionOutcome(route=route)

        if news_events and should_block_entry(now, news_events):
            # I2: blocked → keep the one-shot; the POI may fire later.
            return ExecutionOutcome(route=route, blocked="news")
        if allowed_sessions is not None and not is_allowed_session(now, allowed_sessions):
            # I2: blocked → keep the one-shot; the POI may fire later.
            return ExecutionOutcome(route=route, blocked="session")

        request = build_limit_request(poi, route, volume, self.symbol)
        result = None
        if self.order_manager is not None:
            result = self.order_manager.place_limit(request)
        outcome = ExecutionOutcome(route=route, request=request, order_result=result)
        self._mark_fired(poi, episode, outcome)
        return outcome

    def compute_risk_lots(
        self,
        route: TriggerRoute,
        equity: float,
        risk_fraction: float,
        pip_value_per_lot: float,
        min_lots: float,
        lot_step: float,
    ) -> float:
        """Sized lots for a route's SL distance through the Phase-5 POLICY layer.

        Single sizing path (§28.7): the risk fraction is clamped into the
        frozen ``RISK_PCT_MIN``–``RISK_PCT_MAX`` band and the result is capped
        at ``LOT_MAX_SAFETY`` (``smc.risk.lot_sizing.sized_lots``). No public
        sizing helper sizes outside the band or above the cap.
        """
        signal = route.signal
        sl_distance = abs(signal.entry_price - signal.stop_reference)
        return sized_lots(
            equity,
            risk_fraction,
            sl_distance,
            pip_value_per_lot,
            min_lots,
            lot_step,
        )

    # ------------------------------------------------------------------ #
    def _mark_fired(self, poi: POI, episode: _PoiEpisode, outcome: ExecutionOutcome) -> None:
        """Event identity (§11): one POI → one trigger → one execution."""
        episode.fired = True
        episode.outcome = outcome
