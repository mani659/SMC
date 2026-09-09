"""Phase 6 M4 — pipeline adapter: real detection inside the backtest bar loop.

:class:`PipelineAdapter` is the narrow seam between the Phase 4
``PipelineEngine`` (find → validate → route) and the M3 ``BacktestRunner``
(risk gate → pending limits → fills). It implements the runner's adapter
protocol: ``generate_candidates(bar, bar_index, now)`` is called at the
runner's ENTRY step every bar (after risk exits + fills, so the locked
M3 bar order stays coherent) and drives, per tracked POI:

1. **Trigger scan** (:meth:`PipelineEngine.scan_route`) over the candle
   prefix ``[: bar_index + 1]`` — capped at the current bar, never the
   future (no lookahead). §19 swings are recomputed on that same prefix
   (V1 honesty: caller-supplied full-history swing lists are not assumed
   prefix-safe; recomputing keeps the backtest strictly causal). A scan
   only RUNS while the POI may still route: FRESH, or TESTED within the
   first-touch workflow window (the touch bar itself + the bar after —
   Trigger D's entry bar is exactly the bar after the engulfing touch).
2. **Workflow drive** — the FIRST winning route creates the POI's
   one-shot *workflow* (R1 §11: one validated POI + one trigger + one
   execution) whose candidate is submitted to the runner for THIS bar's
   risk verdict. The workflow is re-submitted every bar until:

   * the risk engine ACCEPTS → the pending limit is placed and the runner
     calls :meth:`on_candidate_accepted` → the workflow (one-shot) is
     consumed;
   * the risk engine BLOCKS (news/session/breaker/spread/...) → nothing is
     placed, NOTHING is consumed — the workflow simply survives and is
     re-submitted on the next bar (mirrors the engine's own I2 blocked
     semantics in ``execute_route``);
   * the signal's §24 validity window expires
     (:func:`smc.triggers.trigger_expiry.signal_expired`) → the workflow
     is dropped without an execution;
   * the POI's §5 state leaves FRESH → see below.

3. **§5 freshness feed** (:meth:`PipelineEngine.feed_bar`) — the engine
   stays the SOLE §5 authority (touch → TESTED, close beyond → VIOLATED).
   The feed runs AFTER the scan: Trigger D's engulfing bar overlaps the
   zone by definition, so feeding first would flip the POI to TESTED
   before the pattern completing on that same bar could be routed. The
   scan-before-feed order plus the touch-window rule implements §5's
   "first touch OK" without ever bypassing the state machine.

   * VIOLATED → the workflow is dropped AND any resting limit the POI
     already placed is cancelled (``runner.cancel_pending_for_poi``) —
     a violated zone is a dead thesis; no ghost order may fill later.
   * TESTED → the touch bar is recorded; the existing workflow (created
     on/before the touch) lives on and its resting limit fills normally.

Backtest safety: the adapter NEVER touches the live order manager —
``PipelineEngine.execute_route`` (which assumes a live ``OrderManager``)
is deliberately not called; placement goes through the runner's M2
``PendingOrderBook`` via the SAME risk-gated path as the M3 seam. The
engine is used only in its backtest-safe role (merge/validate/arm/
feed_bar/scan_route).

Determinism: everything is driven by the injected bar + clock; state is
plain dicts/sets keyed by POI id; iteration follows ``tracked_pois()``
arm order; no wall clock, no randomness, no MT5. Re-running the same
series reproduces the same orders, fills and closes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from smc.backtest.pipeline_bridge import candidate_from_route
from smc.backtest.runner import CandidateEntry
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import POIState
from smc.detection.structural_swing_detector import detect_swings
from smc.orchestration.engine import PipelineEngine
from smc.triggers.trigger_expiry import signal_expired

__all__ = ["PipelineAdapter"]


@dataclass(slots=True)
class _Workflow:
    """One-shot episode: a routed candidate awaiting its risk verdict."""

    candidate: CandidateEntry
    created_bar: int
    completion_index: int  # signal §24 anchor
    expiry_bars: int       # signal §24 window


class PipelineAdapter:
    """Drive the real pipeline each bar and queue risk-bound candidates."""

    def __init__(
        self,
        engine: PipelineEngine,
        *,
        timeframe: Timeframe = Timeframe.M5,
    ) -> None:
        self.engine = engine
        self.timeframe = timeframe
        self._runner = None
        self._candles: list[Candle] = []
        # §11 one-shot: POI id → its single routed workflow (never two).
        self._workflows: dict[str, _Workflow] = {}
        # POIs that have ever produced a route — a POI is routed ONCE per
        # §11; a blocked verdict retries the SAME candidate, never a new
        # scan (re-scans would re-find the same route and could mint a
        # second candidate after the first was accepted).
        self._routed: set[str] = set()
        # First §5 touch bar per POI (bounds the post-touch routing window).
        self._tested_bar: dict[str, int] = {}

    # ------------------------------------------------------------------ #
    # Runner adapter protocol
    # ------------------------------------------------------------------ #
    def generate_candidates(
        self, bar: Candle, bar_index: int, now: datetime
    ) -> None:
        """Per-bar pipeline step (called by the runner's entry step)."""
        for poi in self.engine.tracked_pois():
            # Pre-feed §5 state: governs whether a NEW route may be sought.
            state = self.engine.state_machine.current(poi)
            workflow = self._workflows.get(poi.id)

            # 1. Trigger scan — only while the POI may still route and
            #    only when no route was ever produced (§11 one-shot).
            if (
                workflow is None
                and poi.id not in self._routed
                and self._may_route(poi, state, bar_index)
            ):
                prefix = self._candles[: bar_index + 1]
                route = self.engine.scan_route(
                    poi,
                    prefix,
                    detect_swings(prefix, self.timeframe),
                    to_bar=bar_index,  # cap: never a future bar
                )
                if route is not None:
                    workflow = _Workflow(
                        candidate=candidate_from_route(route),
                        created_bar=bar_index,
                        completion_index=route.signal.completion_index,
                        expiry_bars=route.signal.expiry_bars,
                    )
                    self._workflows[poi.id] = workflow
                    self._routed.add(poi.id)

            # 2. Drive the active workflow: submit for THIS bar's risk
            #    verdict (accepted → consumed via on_candidate_accepted;
            #    blocked → nothing consumed, resubmitted next bar).
            if workflow is not None:
                if signal_expired(
                    workflow.completion_index, workflow.expiry_bars, bar_index
                ):
                    self._workflows.pop(poi.id, None)  # §24: dead signal
                elif self._runner is not None:
                    self._runner.submit_entry(workflow.candidate)

            # 3. §5 freshness feed — engine authority, AFTER the scan (the
            #    touch bar itself must still be routable: first touch OK).
            result = self.engine.feed_bar(poi, bar)
            if result == POIState.VIOLATED.value:
                # Dead thesis: drop the workflow and pull any resting
                # limit so it can never fill against a violated zone.
                self._workflows.pop(poi.id, None)
                if self._runner is not None:
                    self._runner.cancel_pending_for_poi(poi.id)
            elif result == POIState.TESTED.value:
                self._tested_bar.setdefault(poi.id, bar_index)

    def on_candidate_accepted(self, candidate: CandidateEntry) -> None:
        """Consume the POI one-shot — called ONLY on an accepted placement."""
        if candidate.poi_id is not None:
            self._workflows.pop(candidate.poi_id, None)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _may_route(self, poi, state: POIState, bar_index: int) -> bool:
        """True while a NEW route may still be sought for ``poi``.

        FRESH: the normal case. TESTED: §5's "first touch OK" gives the
        in-flight trigger workflow the touch bar itself plus one bar
        (Trigger D's entry condition completes exactly there); after that
        a touched POI is never routed again (1-touch rule).
        """
        if state is POIState.FRESH:
            return True
        if state is POIState.TESTED:
            tested_bar = self._tested_bar.get(poi.id)
            return tested_bar is not None and bar_index <= tested_bar + 1
        return False  # CREATED / terminal states never route

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def attach(self, runner) -> None:
        """Attach to a :class:`~smc.backtest.runner.BacktestRunner`."""
        self._runner = runner
        runner.set_pipeline_adapter(self)

    def set_candles(self, candles: list[Candle]) -> None:
        """Point the adapter at the execution-TF series (scan input).

        The runner's own bars drive ``feed_bar``; this series is the scan
        universe sliced per bar into honest prefixes.
        """
        self._candles = candles
