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
from enum import Enum
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

__all__ = [
    "PipelineEngine",
    "ExecutionOutcome",
    "build_limit_request",
    "SeekPosture",
]


class SeekPosture(str, Enum):
    """Seek/scan contract redesign (Option B) — initial arm-bar posture.

    Design: ``06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md`` §3 R1.2
    (DESIGN_LOCK accepted 2026-10-05). Classifies the arm bar's
    relationship to the POI zone so the seek contract can treat the
    arm-bar artifacts differently from live post-arm price action:

    * ``CLEAN_ARM`` — arm bar neither touches the zone nor closes beyond
      it adversely: today's behaviour, unchanged.
    * ``IN_ZONE_AT_ARM`` — the arm bar's range intersects the zone
      (inclusive, ``touches_zone`` semantics): the HTF-zone wick contact
      is initial presence, NOT a §5 touch terminator; the scan opens at
      arm (design R1.2a/R2.1/R2.2 — no re-entry gate).
    * ``VIOLATION_AT_ARM`` — the arm bar closes beyond the zone on the
      adverse side (design R1.2b): the §5-VIOLATED transition is DEFERRED
      (design R4.2); the episode is in REVALIDATION and may route only
      after a close back inside the zone (adapter gate via the existing
      named rule ``market_reentered_zone``).
    """

    CLEAN_ARM = "CLEAN_ARM"
    IN_ZONE_AT_ARM = "IN_ZONE_AT_ARM"
    VIOLATION_AT_ARM = "VIOLATION_AT_ARM"


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
    posture: SeekPosture = SeekPosture.CLEAN_ARM
    arm_candle_ts: Optional[datetime] = None
    revalidated_bar: Optional[int] = None
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


def _classify_arm_posture(poi: POI, candle: Candle) -> SeekPosture:
    """Design §3 R1.2 — classify the arm bar into its initial seek posture.

    ``VIOLATION_AT_ARM`` wins over ``IN_ZONE_AT_ARM`` when the arm bar
    both touches and closes through: the adverse close is the decisive
    fact (the episode must revalidate), and a wick contact of a bar
    closing beyond the zone is not a meaningful interaction.
    """
    zone = poi.zone
    if zone.direction is Direction.LONG:
        closed_through = candle.close < zone.bottom
    else:
        closed_through = candle.close > zone.top
    if closed_through:
        return SeekPosture.VIOLATION_AT_ARM
    if POIStateMachine.touches_zone(poi, candle):
        return SeekPosture.IN_ZONE_AT_ARM
    return SeekPosture.CLEAN_ARM


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
        # I1 (coherence patch): ONE §5 state machine instance. The pipeline
        # and the engine must share the same machine — no dual-machine
        # coherence via ``poi.state`` fallback. Whichever side is supplied,
        # the other adopts it; supplying two DIFFERENT machines is a loud
        # error, never a silent split.
        if pipeline is None and state_machine is None:
            state_machine = POIStateMachine()
            pipeline = ValidationPipeline(state_machine=state_machine)
        elif pipeline is None:
            pipeline = ValidationPipeline(state_machine=state_machine)
        elif state_machine is None:
            state_machine = pipeline.state_machine
        elif pipeline.state_machine is not state_machine:
            raise ValueError(
                "pipeline and state_machine must be the same POIStateMachine "
                "instance (single §5 authority)"
            )
        self.pipeline = pipeline
        self.state_machine = state_machine
        self.router = router if router is not None else TriggerRouter(matrix=matrix)
        self.order_manager = order_manager
        self.symbol = symbol
        self._episodes: dict[str, _PoiEpisode] = {}
        self._armed_order: list[POI] = []  # M4: arm-order registry for tracked_pois()

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
        window_cache=None,
    ) -> tuple[list[POI], list[ValidationResult]]:
        """Merge (optional), validate each POI, return (passed, results).

        ``displacement_map`` maps each FINAL poi id (post-merge) to its Phase
        1 displacement result — the Pillar 2 injection contract. When a POI
        has no entry, Pillar 2 is UNAVAILABLE and the POI is rejected
        (fail-fast — never a silent pass). ``window_cache`` (Phase C perf)
        carries the detection window's shared artifacts for pillar reuse;
        ``None`` keeps the per-POI in-place computation.
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
                window_cache=window_cache,
            )
            results.append(result)
            if result.passed:
                passed.append(poi)
        return passed, results

    # ------------------------------------------------------------------ #
    # Stage 3 — arm bookkeeping
    # ------------------------------------------------------------------ #
    def arm_at(
        self,
        poi: POI,
        arm_bar: int,
        *,
        arm_candle: Candle | None = None,
    ) -> None:
        """Arm a CREATED POI (CREATED → FRESH) and record its arm bar.

        POIs validated through :meth:`validate` are already FRESH; this also
        accepts them. The arm bar anchors the §24 no-trigger give-up window.

        Seek/scan redesign (Option B, design §3 R1.2): when ``arm_candle``
        is supplied, the arm bar is classified into its initial seek
        posture — ``IN_ZONE_AT_ARM`` (range intersects the zone, inclusive
        §5 ``touches_zone`` semantics), ``VIOLATION_AT_ARM`` (closes beyond
        the zone on the adverse side), or ``CLEAN_ARM``. Callers that do
        not pass the arm candle keep today's behaviour exactly
        (``CLEAN_ARM``): the posture never changes arming, the §5 state,
        or the arm bar — it is engine bookkeeping the adapter reads to
        apply the new scan contract.
        """
        if poi.state is POIState.CREATED:
            self.state_machine.arm(poi)
        if poi.state is not POIState.FRESH:
            raise ValueError("arm_at expects a CREATED or FRESH POI")
        posture = SeekPosture.CLEAN_ARM
        arm_candle_ts: Optional[datetime] = None
        if arm_candle is not None:
            posture = _classify_arm_posture(poi, arm_candle)
            arm_candle_ts = arm_candle.timestamp
        self._episodes[poi.id] = _PoiEpisode(
            arm_bar=arm_bar, posture=posture, arm_candle_ts=arm_candle_ts)
        if poi.id not in {p.id for p in self._armed_order}:
            self._armed_order.append(poi)

    def episode(self, poi: POI) -> _PoiEpisode | None:
        """Engine bookkeeping for a POI (None when not armed through this engine)."""
        return self._episodes.get(poi.id)

    def tracked_pois(self) -> list[POI]:
        """All POIs armed through this engine, in arm order (M4 adapter seam).

        Arm order is insertion order of the episode dict — deterministic
        per construction; the bar-loop caller processes them in that order.
        """
        return list(self._armed_order)

    # ------------------------------------------------------------------ #
    # Stage 3 — per-bar trigger scan + state feed (Pillar 4 events)
    # ------------------------------------------------------------------ #
    def feed_bar(self, poi: POI, candle: Candle) -> str:
        """Feed one execution-TF bar into the §5 machine (touch/violation).

        Returns the resulting state name. Only FRESH POIs move; a first
        touch → TESTED, a close beyond the zone without a touch → VIOLATED.

        Seek/scan redesign (Option B, design §3 R1.2/R4.2): the ARM BAR
        itself (matched by its stored candle timestamp) does not feed the
        §5 machine for a non-CLEAN posture — the arming candle belongs to
        the HTF candle that created the POI, so reading it as fresh LTF
        price action would yield the measured zero-bar / two-bar seek
        collapse. Post-arm bars feed with one REVALIDATION exception: a
        ``VIOLATION_AT_ARM`` episode whose zone re-entry has not yet been
        latched (``revalidated_bar`` set by the adapter's gate) treats a
        close beyond the zone as the CONTINUATION of the arm-bar
        condition (the episode retires at the give-up deadline if it
        never re-enters — design R4.2), while a wick contact is still
        recorded through the §5 machine. After re-entry, the standard §5
        feed applies: an adverse close is terminal (R4.1b, unchanged).
        """
        current = self.state_machine.current(poi)
        if current is not POIState.FRESH:
            return current.value
        episode = self._episodes.get(poi.id)
        if episode is not None:
            if (episode.posture is not SeekPosture.CLEAN_ARM
                    and episode.arm_candle_ts is not None
                    and candle.timestamp == episode.arm_candle_ts):
                return POIState.FRESH.value  # initial presence / deferred
            if (episode.posture is SeekPosture.VIOLATION_AT_ARM
                    and episode.revalidated_bar is None
                    and not self.state_machine.touches_zone(poi, candle)):
                return POIState.FRESH.value  # pre-re-entry continuation
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
        to_bar: int | None = None,
        *,
        scan_from: int | None = None,
        evaluation_candles: list[Candle] | None = None,
        evaluation_swings: list[Swing] | None = None,
        hints=None,
    ) -> TriggerRoute | None:
        """Chronological trigger scan within the §24 give-up window.

        Returns the FIRST valid route (bar order, §12). The scan is bounded
        by ``arm_bar + poi_give_up_bars()`` (V1, documented — see
        ``trigger_expiry.poi_give_up_bars``). ``to_bar`` (M4) optionally
        caps the scan at the CURRENT bar — the backtest adapter passes the
        bar-loop index so the scan never sees future candles (no lookahead).

        ``scan_from`` (Phase B perf) resumes the ONE chronological scan at
        the given bar instead of re-deriving already-evaluated bars. Only
        safe when every trigger evaluation at bar b depends solely on
        candles ≤ b (the engine's no-lookahead contract — true for all six
        triggers A–F), in which case the returned first-fire route is
        identical to a full re-scan from the arm bar. The evaluation
        anchor stays at the arm bar — only the loop start moves.

        ``evaluation_candles`` / ``evaluation_swings`` (Phase C perf) are
        the adapter's incremental full-prefix artifacts handed to the
        evaluations INSTEAD of prefix slices: every trigger read stays
        bounded by the evaluated bar, so the values are identical to the
        slices (see ``base_trigger.TriggerContext`` for the read contracts).
        ``hints`` (Phase C perf) carries the same series' pre-computed
        indicator/mirror/index artifacts for the per-evaluation hoists.
        """
        episode = self._episodes.get(poi.id)
        arm = episode.arm_bar if episode is not None else (from_bar or 0)
        deadline = arm + poi_give_up_bars()  # §24 window anchored at the ARM bar
        if to_bar is not None:
            deadline = min(deadline, to_bar)
        # ``from_bar=arm`` keeps the evaluation ANCHOR at the arming bar
        # (triggers A/D/E require the pattern to post-date arming) while
        # ``scan_from`` only moves the bar loop's start.
        return self.router.scan(
            poi, candles, swings, from_bar=arm, to_bar=deadline, scan_from=scan_from,
            evaluation_candles=evaluation_candles, evaluation_swings=evaluation_swings,
            hints=hints,
        )

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

        V1.1 (coherence patch I3): superseded as the placement seam. The
        shipped runners do NOT call this method — the backtest adapter
        places through the runner's ``PendingOrderBook`` and the paper
        runner through its ``BrokerAdapter``, both building ``OrderRequest``
        at their own boundaries (``comment`` carries the §11 route
        identity). This helper is retained for tests and direct live use;
        ``build_limit_request`` remains its single request builder (no
        third construction path).
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
    # I4 — terminal-state retention
    # ------------------------------------------------------------------ #
    def prune_terminal(self, retain_ids: set[str] | None = None) -> list[str]:
        """I4: drop terminal (TESTED/VIOLATED) POIs from the arm indexes.

        Long runs must not keep every terminal POI/episode forever. A POI
        is pruned when its §5 state is terminal AND its id is not in
        ``retain_ids`` — the caller supplies the ids still tied to a
        resting order / open position / in-flight workflow (the runners do
        this per bar). The state machine's per-id store is deliberately
        left intact (it is shared with the validation pipeline and a pruned
        id costs nothing); the POI object and its episode — the heavy part
        — are released. Returns the pruned POI ids.
        """
        retain = set(retain_ids or ())
        kept: list[POI] = []
        pruned: list[str] = []
        for poi in self._armed_order:
            if poi.id in retain:
                kept.append(poi)
                continue
            if self.state_machine.current(poi) in (POIState.TESTED, POIState.VIOLATED):
                self._episodes.pop(poi.id, None)
                pruned.append(poi.id)
            else:
                kept.append(poi)
        self._armed_order = kept
        return pruned

    # ------------------------------------------------------------------ #
    def _mark_fired(self, poi: POI, episode: _PoiEpisode, outcome: ExecutionOutcome) -> None:
        """Event identity (§11): one POI → one trigger → one execution."""
        episode.fired = True
        episode.outcome = outcome
