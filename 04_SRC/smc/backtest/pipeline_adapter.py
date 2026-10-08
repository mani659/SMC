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

from smc.backtest.pipeline_bridge import candidate_from_route, structural_tp_target
from smc.backtest.runner import CandidateEntry
from smc.backtest.series_state import SeriesState
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import POIState
from smc.orchestration.engine import PipelineEngine, SeekPosture
from smc.risk.fill_regime_policy import market_reentered_zone
from smc.triggers.trigger_expiry import poi_give_up_bars, signal_expired

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
        atr_period: int = 14,
    ) -> None:
        self.engine = engine
        self.timeframe = timeframe
        self.atr_period = atr_period
        self._runner = None
        self._candles: list[Candle] = []
        # §11 one-shot: POI id → its single routed workflow (never two).
        self._workflows: dict[str, _Workflow] = {}
        # POIs that have ever produced a route — a POI is routed ONCE per
        # §11; a blocked verdict retries the SAME candidate, never a new
        # scan (re-scans would re-find the same route and could mint a
        # second candidate after the first was accepted).
        self._routed: set[str] = set()
        # First §5 touch bar per POI (§5 freshness bookkeeping — recorded,
        # no longer bounds the post-touch routing window: seek/scan redesign
        # R4.3, a TESTED state inside the seek span does not close the scan).
        self._tested_bar: dict[str, int] = {}
        # Perf (Phase B): next bar to evaluate per POI's ONE chronological
        # trigger scan. A POI that never routes used to re-run its whole
        # arm→now scan window EVERY bar (each evaluation rebuilding O(n)
        # swings/RSI/ATR/inversions over the growing prefix) — quadratic in
        # bar index. Since every trigger evaluation at bar b depends only on
        # candles ≤ b (no-lookahead contract), evaluating each bar exactly
        # once, when it is reached, returns the same first-fire route.
        self._scan_cursor: dict[str, int] = {}
        # Identity context (logging only — never read by scan/risk/fill):
        # POI id → (displacement, pillar_path) noted by whoever validated
        # the POI (live loop / research scripts via note_route_context) and
        # attached to the routed candidate. Absent entries stay unknown.
        self._route_context: dict[str, tuple] = {}
        # Perf (Phase C): incremental full-prefix series state — ATR/RSI
        # folds (both price spaces), §27 swings with §19 confirmations as
        # monotone first-confirm events, mirrored candles/swings, and
        # base-sorted swing indexes. Exactly value-equivalent to the O(n)
        # prefix recomputations it replaces (per-piece arguments in the
        # Phase C report; October golden replay pins it byte-for-byte).
        self._state: SeriesState | None = None

    # ------------------------------------------------------------------ #
    # Runner adapter protocol
    # ------------------------------------------------------------------ #
    def generate_candidates(
        self, bar: Candle, bar_index: int, now: datetime
    ) -> None:
        """Per-bar pipeline step (called by the runner's entry step)."""
        state = self._ensure_state(bar_index)
        for poi in self.engine.tracked_pois():
            # Pre-feed §5 state: governs whether a NEW route may be sought.
            state_machine = self.engine.state_machine
            workflow = self._workflows.get(poi.id)

            # §24 give-up backstop (R4.1a — EVERY posture): past arm_bar +
            # poi_give_up_bars() the scan range is empty — retire the scan
            # bookkeeping instead of re-deriving that fact with an O(n) swing
            # detection per bar. (Only the SCAN retires; the §5 feed below
            # runs for every tracked POI exactly as before; a workflow-live
            # episode keeps its own §24 signal expiry.)
            episode = self.engine.episode(poi)
            if (
                workflow is None
                and poi.id not in self._routed
                and episode is not None
                and bar_index > episode.arm_bar + poi_give_up_bars()
            ):
                self._routed.add(poi.id)
                self._scan_cursor.pop(poi.id, None)

            # 1. Trigger scan — only while the POI may still route and
            #    only when no route was ever produced (§11 one-shot).
            seek_route = (
                workflow is None
                and poi.id not in self._routed
                and self._may_route(
                    poi, state_machine.current(poi), bar_index, bar=bar)
            )
            if seek_route:
                # Incremental state (Phase C): the scan reads the FULL series
                # plus the SAME §27/§19 swing artifacts the prefix rebuild
                # produced — evaluations stay prefix-bounded by ``bar`` via
                # the cursor, so no evaluation ever reads a future candle.
                route = self.engine.scan_route(
                    poi,
                    state.candles,
                    state.swings,
                    to_bar=bar_index,  # cap: never a future bar
                    scan_from=self._scan_cursor.get(poi.id),  # resume, not restart
                    evaluation_candles=state.candles,
                    evaluation_swings=state.swings,
                    hints=state,
                )
                if route is not None:
                    ctx_disp, ctx_path = self._route_context.pop(
                        poi.id, (None, None))
                    workflow = _Workflow(
                        candidate=candidate_from_route(
                            route, displacement=ctx_disp,
                            pillar_path=ctx_path,
                            # FR-2 R4: honest-prefix ATR feeds the TP
                            # fallback (4×ATR when no structural target).
                            atr=self.current_atr(bar_index),
                            # Structural TP feed (design lock 2026-10-05,
                            # Architect-accepted): first-swing selector on
                            # the SAME §19-confirmed place-time prefix the
                            # scan just consumed. None → unchanged 4×ATR
                            # fallback. Age bound = documented CPU/age cap
                            # (NOT give-up semantics, Architect ruling 2).
                            structural_target=structural_tp_target(
                                state.swing_index.original.valid_highs
                                + state.swing_index.original.valid_lows,
                                route.signal.entry_price, route.signal.direction,
                                self.current_atr(bar_index),
                                placement_bar=bar_index,
                                max_age_bars=poi_give_up_bars())),
                        created_bar=bar_index,
                        completion_index=route.signal.completion_index,
                        expiry_bars=route.signal.expiry_bars,
                    )
                    self._workflows[poi.id] = workflow
                    self._routed.add(poi.id)
                    self._scan_cursor.pop(poi.id, None)
                else:
                    # Nothing fired up to and including this bar — resume the
                    # ONE chronological scan at the next bar (never re-derive).
                    self._scan_cursor[poi.id] = bar_index + 1

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

    def active_workflows(self) -> dict:
        """Public read-only snapshot: POI id → live CandidateEntry.

        L1 structure console seam (2026-10-06): the console reads routed
        candidates (trigger letter, entry/SL/TP plan) from here without
        touching private bookkeeping. A COPY — mutating it never affects
        the §11 one-shot workflow state.
        """
        return {
            poi_id: workflow.candidate
            for poi_id, workflow in self._workflows.items()
        }

    def note_route_context(self, poi_id: str, *, displacement=None,
                           pillar_path: str | None = None) -> None:
        """Retain route-time identity context for one POI (logging only).

        Called by whoever validated the POI (live loop / research scripts)
        with that POI's DisplacementResult (or None) and pillar-path summary
        string (or None). Consumed once at the next route for this POI id
        into the candidate; never read by scan, risk, or fill decisions.
        Unknown stays unknown — nothing is invented here.
        """
        self._route_context[poi_id] = (displacement, pillar_path)

    def notify_order_expired(self, poi_id: str, bars_open: int) -> None:
        """C1: a resting limit for ``poi_id`` hit §23/§24 unfilled-order
        expiry (the runner already cancelled it) — retire the POI.

        The engine stays the sole §5 authority: the state machine
        transitions the POI to TESTED through the frozen
        ``expire_unfilled`` path when a §23 rule exists for its timeframe
        (M5 = 12 / M1 = 30); otherwise the §24 give-up backstop applies
        (FRESH → TESTED directly). A TESTED POI can never route again
        (``_may_route`` requires FRESH, or TESTED only within the
        first-touch window). No-op when the POI is not tracked here or
        already terminal.
        """
        machine = self.engine.state_machine
        for poi in self.engine.tracked_pois():
            if poi.id != poi_id:
                continue
            if machine.expire_unfilled(poi, bars_open) is None:
                # No frozen §23 rule for this timeframe → give-up backstop.
                if machine.current(poi) is POIState.FRESH:
                    machine.transition(poi, POIState.TESTED)
            self._workflows.pop(poi_id, None)
            return

    def current_atr(self, bar_index: int) -> float:
        """I1: ATR at ``bar_index`` over the honest candle prefix.

        Capped at the current bar — never the future (same no-lookahead
        contract as the trigger scan). Returns 0.0 before the period
        warm-up so the ATR-dependent gates stay deterministically off
        (never an exception). The runner feeds this to ``set_atr`` each
        bar; the paper runner computes the same value from its own
        growing series.

        Phase C perf: read from the incremental Wilder fold — exactly the
        ``latest_atr(prefix)`` value (fold identity), without the O(n)
        prefix rebuild per bar.
        """
        state = self._ensure_state(min(bar_index, len(self._candles) - 1))
        values = state.atr_values
        if bar_index < len(values):
            atr = values[bar_index]
        elif values:
            # Legacy slice clamp: ``candles[:bar_index+1]`` beyond the end
            # yields the whole list, so the honest prefix is the full series.
            atr = values[-1]
        else:
            atr = None
        return float(atr) if atr is not None else 0.0

    def _ensure_state(self, bar_index: int) -> SeriesState:
        """Extend the incremental state through ``bar_index`` (idempotent).

        The runner may call ``current_atr`` (step 3b) before the entry step,
        so extension happens at the FIRST per-bar touchpoint; every later
        read in the same bar sees the same prefix. Re-running over an
        already-extended bar is a no-op.
        """
        state = self._state
        if state is None:
            state = self._state = SeriesState(self.timeframe, self.atr_period)
        candles = self._candles
        target = bar_index + 1
        while len(state.candles) < target and len(state.candles) < len(candles):
            state.extend(candles[len(state.candles)])
        return state

    def prune_terminal_pois(
        self, retain_ids: set[str] | None = None, bar_index: int | None = None
    ) -> list[str]:
        """I4: retire terminal POIs from the engine (runner calls per bar).

        ``retain_ids`` — POI ids still tied to a resting order or open
        position (the runner supplies them from its stores); workflow-live
        POIs (a routed candidate awaiting its risk verdict) are ALWAYS
        retained so a mid-flight one-shot is never orphaned. A TESTED POI
        still inside the first-touch routing window (touch bar + 1 — see
        :meth:`_may_route`) is also retained when ``bar_index`` is given:
        it may still produce its first workflow on this bar, so pruning it
        here would orphan the route the scan is about to create. Returns
        the pruned ids and drops their adapter bookkeeping (workflow /
        touch bar / routed flag) so a pruned POI cannot resurface.
        """
        retain = set(retain_ids or ())
        retain |= set(self._workflows)
        if bar_index is not None:
            for poi in self.engine.tracked_pois():
                state = self.engine.state_machine.current(poi)
                if self._may_route(poi, state, bar_index, bar=None):
                    retain.add(poi.id)
        pruned = self.engine.prune_terminal(retain)
        for poi_id in pruned:
            self._workflows.pop(poi_id, None)
            self._tested_bar.pop(poi_id, None)
            self._routed.discard(poi_id)
            self._scan_cursor.pop(poi_id, None)
        return pruned

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _reentered_zone(self, poi, bar: Candle, bar_index: int) -> bool:
        """Seek/scan redesign REVALIDATION gate (design §3 R2.3).

        Reuses the EXISTING named rule ``market_reentered_zone`` — its R7
        band path (a close within the frozen ``ZONE_REFINEMENT_ATR × ATR``
        band of the POI zone, same inclusive bounds as the R7 place
        guard) gates re-entry. The rule's limit-touch path is not
        applicable pre-route (no limit exists — this gate runs BEFORE any
        candidate), so ``limit_price=None`` disables it exactly as the
        function's contract prescribes. ATR comes from the incremental
        Phase C fold (honest prefix, capped at the current bar).

        Fail-closed on degenerate ATR: ``zone_place_allowed``'s documented
        dormancy (band undefined → allow) exists for the R7 PLACE guard;
        here the band IS the revalidation evidence, so an uncomputable
        band (ATR 0.0 / None in warm-up) must keep the gate CLOSED until
        a real ATR exists — never a vacuous re-entry. No new threshold:
        the band is the frozen ``ZONE_REFINEMENT_ATR`` multiplier.
        """
        episode = self.engine.episode(poi)
        if episode is None:
            return False  # not armed through the engine -> cannot revalidate
        zone = poi.zone
        atr = self.current_atr(bar_index)
        if not atr > 0.0:
            return False  # band uncomputable -> cannot verify -> fail closed
        return market_reentered_zone(
            zone.direction,
            float(zone.bottom),
            float(zone.top),
            None,          # no limit pre-route: touch path off by contract
            float(bar.close),
            atr,
        )

    def _may_route(self, poi, state: POIState, bar_index: int,
                   bar: Candle | None = None) -> bool:
        """True while a NEW route may still be sought for ``poi``.

        Seek/scan redesign (Option B, design §3): the seek span is the
        locked give-up window ``[arm, arm + poi_give_up_bars()]`` (R2.1/
        R3.1 — the caller's unchanged give-up retirement enforces the
        end); a §5 TESTED state inside that window no longer closes the
        scan (R4.3 — the touch is bookkeeping, not a seek terminator;
        Trigger D's next-bar contract is preserved by its own frozen
        ``TRIGGER_D_EXPIRY``). The §5 state still governs identity: only
        FRESH or TESTED episodes may route; VIOLATED is dead exactly as
        before (R4.1b).

        REVALIDATION (R2.3): a ``VIOLATION_AT_ARM`` episode — whose §5
        violation was deferred at arm (engine ``feed_bar`` skips the arm
        candle, so the POI stays FRESH) — routes only after a later close
        back inside the zone band via the existing named rule
        ``market_reentered_zone`` (adapter ATR, fail-closed on warm-up —
        see ``_reentered_zone``). Until re-entry, FRESH is necessary but
        NOT sufficient. The latch is written to the engine episode once
        (``revalidated_bar``) so the §5 feed's pre-re-entry continuation
        rule and this gate share one fact.

        ``bar=None`` keeps the legacy two-argument contract for callers
        without bar context (prune retention): such calls keep the
        pre-redesign semantics (FRESH/TESTED may route) — the
        REVALIDATION gate needs the bar to test re-entry geometry.
        """
        if state not in (POIState.FRESH, POIState.TESTED):
            return False  # CREATED / VIOLATED / terminal never route
        if bar is None:
            return True  # legacy no-bar contract (unchanged pre-redesign path)
        episode = self.engine.episode(poi)
        if (
            episode is not None
            and episode.posture is SeekPosture.VIOLATION_AT_ARM
            and episode.revalidated_bar is None
        ):
            if not self._reentered_zone(poi, bar, bar_index):
                return False
            episode.revalidated_bar = bar_index  # latch once, never re-tested
            # R2.3: a trigger completion BEFORE re-entry does not route — the
            # chronological scan starts at the re-entry bar (the evaluation
            # anchor stays at the arm bar; only the loop start moves).
            self._scan_cursor[poi.id] = bar_index
        if state is POIState.FRESH:
            return True
        # TESTED: seek continues to the give-up deadline (R4.3).
        if episode is None:
            return False
        return bar_index <= episode.arm_bar + poi_give_up_bars()

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
        universe — the incremental state extends through it bar by bar
        (no per-bar prefix slices).
        """
        self._candles = candles
        self._state = None
