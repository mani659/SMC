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

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from smc.backtest.pipeline_bridge import candidate_from_route, structural_tp_target
from smc.backtest.runner import CandidateEntry
from smc.backtest.series_state import SeriesState
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import POIState
from smc.orchestration.engine import PipelineEngine, SeekPosture
from smc.orchestration.parallel_books import (
    cross_book_plan_key,
    same_cross_book_plan,
)
from smc.risk.fill_regime_policy import market_reentered_zone
from smc.risk.story_guard import same_story, story_key
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
        menu_confirmation=None,
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
        # LEG 5 (design R3.4): the session's effective ZoneDedup handle,
        # bound ONCE by MultiTFProductRuntime from the arm seam so the
        # object this adapter retires from IS the object ``seen()`` reads.
        # None (unbound) → retirement is a no-op (design R6).
        self._dedup_registry = None
        # LEG 5 R3.2 bookkeeping: ids already sent to retire (the two
        # retirement sources may overlap; re-sending an id would only
        # inflate ``retire_misses``). Pure dedup bookkeeping — retirement
        # itself is idempotent either way.
        self._retire_sent: set[str] = set()
        # Product menu confirmation wiring & dedup (Phase C seam):
        self.menu_confirmation = menu_confirmation
        self._menu_candidates: list[CandidateEntry] = []
        self._menu_claimed_pois: set[str] = set()
        self._menu_covered_timeframes: set[Timeframe] = set()
        # F7: confirmed menu winners awaiting an accepted placement. Only
        # populated when the runner reports per-candidate outcomes (the live
        # paper runner does; research submit-captures do not, and keep the
        # historical one-submit semantics).
        # C-1/M-2: keyed by ROUTE identity — ``<book>|<poi>`` for a book-stamped
        # candidate, the plain POI id otherwise. Two books winning on the SAME
        # POI with DIFFERENT plans therefore keep two independent pendings
        # (and two independent claims) instead of silently overwriting one.
        self._menu_pending: dict[str, dict] = {}
        # M-3: POIs whose detection tier NO selected book carries. They must
        # not fall through to the legacy single-menu seek path; counted once.
        self._outside_book_pois: set[str] = set()
        # ONE STORY → ONE PLAN → ONE LIVE ORDER (locked product rule,
        # 2026-11-15; design 06_RESEARCH/ONE_STORY_ONE_TRADE_DESIGN.md).
        # ``_story_claims`` holds the plan identity of every candidate this
        # adapter has accepted for submission; a claim lives exactly as long
        # as the plan does (resting order / open position / in-flight
        # candidate). A second candidate with the SAME plan is dropped at
        # intake — before the runner's risk gate — so it can never place.
        # Claims are explicit, not inferred: an UNSEALED claim means its
        # candidate is still in flight (routed workflow / queued winner) and
        # blocks duplicates until it places or is released. ``on_candidate_
        # accepted`` seals it; from then on the claim follows the BOOK (a
        # sealed claim is pruned once no resting order / open position / live
        # intent carries its plan), so a later identical plan is a new story.
        self._story_claims: list[dict] = []
        self._story_bar: int | None = None
        self._story_stats: dict[str, int] = {
            "stories_claimed": 0,
            "stories_pruned": 0,
            "duplicate_story_dropped": 0,
            "duplicate_story_seek": 0,
            "duplicate_story_menu": 0,
            # C-1: dropped by the trigger-EXCLUDED cross-book plan identity
            # (the ONE-STORY key includes the trigger and can never catch a
            # second tag).
            "duplicate_story_cross_book": 0,
        }
        self._menu_stats: dict[str, int] = {
            "menu_submitted": 0,
            "menu_accepted": 0,
            "menu_retry_blocked": 0,
            "menu_resubmitted": 0,
            "menu_expired_unplaced": 0,
            "menu_dropped_poi_retired": 0,
            # M-3: POIs skipped because no book carries their tier.
            "poi_outside_books": 0,
        }
        if menu_confirmation is not None:
            self.set_menu_confirmation(menu_confirmation)

    def set_menu_confirmation(self, menu) -> None:
        """Attach the product menu engine for dedup and candidate routing."""
        self.menu_confirmation = menu
        # F6: the menu must read the ONE §5 state store (the pipeline
        # engine's machine), never keep a second copy. Binding here means
        # every adapter (live, paper, research) gates identically.
        state_machine = getattr(self.engine, "state_machine", None)
        set_source = getattr(menu, "set_state_source", None)
        if callable(set_source):
            if state_machine is not None and callable(
                getattr(state_machine, "current", None)
            ):
                set_source(lambda poi, _m=state_machine: _m.current(poi))
            else:
                set_source(lambda poi: getattr(poi, "state", None))
        if menu is not None:
            det_tfs = getattr(menu, "detection_timeframes", None)
            if det_tfs:
                self._menu_covered_timeframes.update(det_tfs)

    def claim_poi_for_menu(self, poi_id: str) -> None:
        """Explicitly claim a POI for menu confirmation (skips adapter scan)."""
        if poi_id:
            self._menu_claimed_pois.add(str(poi_id))

    def menu_covers_poi(self, poi) -> bool:
        """True when this POI is claimed or covered by the menu confirmation flow."""
        poi_id = getattr(poi, "id", None)
        if poi_id is not None and str(poi_id) in self._menu_claimed_pois:
            return True
        zone_tf = getattr(getattr(poi, "zone", None), "timeframe", None)
        if zone_tf is not None and zone_tf in self._menu_covered_timeframes:
            return True
        menu = self.menu_confirmation
        if menu is not None:
            if poi_id is not None:
                pid = str(poi_id)
                if pid in getattr(menu, "_armed", {}):
                    return True
                if pid in getattr(menu, "_consumed", set()):
                    return True
                for ep in getattr(menu, "_episodes", ()) or ():
                    if getattr(ep, "poi_id", None) == pid:
                        return True
            tier_fn = getattr(menu, "tier_for", None)
            if callable(tier_fn) and zone_tf is not None and tier_fn(zone_tf) is not None:
                return True
        return False

    def _outside_book_tiers(self, poi) -> bool:
        """M-3: True when NO selected book carries this POI's tier.

        Only the parallel multiplexer opts in (``refuses_uncovered_tiers``):
        it owns the whole menu, so a POI it cannot carry must be skipped and
        counted (``poi_outside_books``) rather than routed through the
        archived legacy seek path — that path would place without a book
        stamp, without the ``SMC-<TAG>-`` comment and without cross-book
        dedupe. The shipped single menu carries every tier, so its behaviour
        is untouched.
        """
        menu = self.menu_confirmation
        if not getattr(menu, "refuses_uncovered_tiers", False):
            return False
        if self.menu_covers_poi(poi):
            return False
        zone_tf = getattr(getattr(poi, "zone", None), "timeframe", None)
        tier_fn = getattr(menu, "tier_for", None)
        if zone_tf is None or not callable(tier_fn):
            return False
        return tier_fn(zone_tf) is None

    # ------------------------------------------------------------------ #
    # ONE STORY → ONE PLAN → ONE LIVE ORDER (locked rule, 2026-11-15)
    # ------------------------------------------------------------------ #
    def story_counters(self) -> dict:
        """Measurement surface for the uniqueness rule (never an input)."""
        return {**self._story_stats, "story_claims": len(self._story_claims)}

    @staticmethod
    def _menu_stamp(candidate) -> dict:
        """The candidate's ``product_menu`` stamp (``{}`` when absent)."""
        raw = getattr(candidate, "signal_data_json", None)
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        if not isinstance(payload, dict):
            return {}
        stamp = payload.get("product_menu")
        return stamp if isinstance(stamp, dict) else {}

    def _book_id(self, candidate) -> str | None:
        """The stamping book (``None`` for the legacy single-menu path)."""
        book = self._menu_stamp(candidate).get("book_id")
        return str(book) if book else None

    def _route_key(self, candidate) -> str | None:
        """Route identity: ``<book>|<poi>`` when stamped, else the POI id.

        This is the ONE key for pending confirmation slots and story claims;
        book-stamping it is what stops two books' different plans on the same
        POI from colliding (M-2) while leaving the legacy single-menu keys
        byte-identical.
        """
        poi_id = getattr(candidate, "poi_id", None)
        if poi_id is None:
            return None
        book = self._book_id(candidate)
        return f"{book}|{poi_id}" if book else str(poi_id)

    def _pending_keys_for_poi(self, poi_id) -> list[str]:
        """Every pending slot owned by ``poi_id`` (one per book)."""
        wanted = str(poi_id)
        return [
            key for key, pending in self._menu_pending.items()
            if key == wanted or pending.get("poi_id") == wanted
        ]

    def _pop_pending_for_poi(self, poi_id) -> int:
        keys = self._pending_keys_for_poi(poi_id)
        for key in keys:
            self._menu_pending.pop(key, None)
        return len(keys)

    def _release_menu_plan(self, route_key) -> None:
        """C-1 liveness seam: the plan can no longer trade — forget it.

        The book layer keeps cross-book plan memory until the plan dies (not
        until its menu window closes); this is the signal it dies.
        """
        menu = self.menu_confirmation
        release = getattr(menu, "release_plan", None)
        if callable(release):
            release(route_key)

    def _live_story_keys(self) -> list:
        """Plan identity of everything that currently trades (liveness set).

        Derived from the actual book, never from a timer: resting orders,
        open positions and live R9 intents come from the runner
        (``story_live_plans``), plus this adapter's own in-flight candidates
        (menu pendings, routed workflows, queued menu candidates).
        """
        objects: list = []
        provider = getattr(self._runner, "story_live_plans", None)
        if callable(provider):
            objects.extend(list(provider() or ()))
        objects.extend(
            pending["candidate"] for pending in self._menu_pending.values()
        )
        objects.extend(w.candidate for w in self._workflows.values())
        objects.extend(self._menu_candidates)
        keys = []
        for obj in objects:
            key = story_key(obj)
            if key is not None:
                keys.append(key)
        return keys

    def _prune_story_claims(self) -> None:
        """Drop SEALED claims whose plan no longer lives in the book.

        An UNSEALED claim is released explicitly (workflow dropped, window
        closed, POI retired) rather than guessed from the book: between
        intake and placement a research submit-capture runner keeps no
        record of the candidate, and inferring "gone" there would end the
        block one bar too early — exactly the spray this rule forbids.
        """
        if not self._story_claims:
            return
        live = self._live_story_keys()
        kept: list[dict] = []
        ended: list[dict] = []
        for claim in self._story_claims:
            if not claim["sealed"] or any(
                same_story(claim["key"], other) for other in live
            ):
                kept.append(claim)
            else:
                ended.append(claim)
        self._story_stats["stories_pruned"] += len(ended)
        self._story_claims = kept
        # C-1: a plan that stopped trading frees the book layer's durable
        # memory too, so a LATER identical plan is a new story (over-
        # suppression would be safe but wrong: the account holds nothing).
        for claim in ended:
            self._release_menu_plan(claim.get("owner"))

    def _claim_story(self, candidate) -> None:
        """Record the plan of a candidate accepted for entry (unsealed)."""
        key = story_key(candidate)
        if key is None:
            return
        poi_id = getattr(candidate, "poi_id", None)
        if poi_id is None:
            return  # no episode identity → no claim (M3 test seam only)
        owner = self._route_key(candidate) or str(poi_id)
        self._story_claims.append(
            {"key": key, "owner": owner, "poi": str(poi_id),
             # C-1: the SAME order without the trigger, so a second book's
             # confirmation of this plan is recognised even after its
             # window would have "forgotten" it.
             "cross": cross_book_plan_key(candidate),
             "book_id": self._book_id(candidate),
             "sealed": False, "bar": self._story_bar}
        )
        self._story_stats["stories_claimed"] += 1

    def seal_story(self, poi_id) -> None:
        """A real placement happened: the claim now follows the book.

        ``poi_id`` is a route key (``<book>|<poi>``, precise when two books
        own the same POI) or a plain POI id (legacy/unstamped: every claim of
        that POI is sealed, as before).
        """
        if poi_id is None:
            return
        wanted = str(poi_id)
        for claim in self._story_claims:
            if claim["owner"] == wanted or claim.get("poi") == wanted:
                claim["sealed"] = True

    def release_story(self, poi_id) -> None:
        """The claiming candidate can no longer trade — free its plan."""
        if poi_id is None:
            return
        wanted = str(poi_id)
        self._story_claims = [
            claim for claim in self._story_claims
            if claim["owner"] != wanted and claim.get("poi") != wanted
        ]
        # C-1: the book layer's durable plan memory follows the same clock.
        self._release_menu_plan(wanted)

    def _duplicate_story(self, candidate, *, source: str) -> str | None:
        """Claiming poi id when ``candidate`` repeats a LIVE story, else None.

        Called at intake (menu winner or seek route) — before the runner's
        risk gate — so a duplicate plan never becomes a second order, never
        consumes sizing, and never mints a second ticket. An unprovable key
        (missing entry/SL, unknown zone bounds) is never collapsed.
        """
        self._prune_story_claims()
        key = story_key(candidate)
        if key is None:
            return None
        for claim in self._story_claims:
            if same_story(key, claim["key"]):
                self._note_duplicate(source)
                return claim["owner"]
        # C-1 BACKSTOP (independent of the book layer's registry): plan
        # identity WITHOUT the trigger. ``story_key`` includes the trigger by
        # design, so it can never arbitrate between two tags — a B plan and an
        # F plan of the same order are not ``same_story``. Book-stamped
        # candidates are compared on the trigger-excluded key against every
        # LIVE claim (resting, pending, in-flight), which is exactly the set
        # the menu window does not see.
        cross = cross_book_plan_key(candidate)
        book_id = self._book_id(candidate)
        if cross is not None and book_id is not None:
            for claim in self._story_claims:
                other = claim.get("cross")
                if other is None:
                    continue
                if claim.get("book_id") == book_id:
                    continue  # one book: the ONE-STORY key already covers it
                if same_cross_book_plan(cross, other):
                    self._story_stats["duplicate_story_cross_book"] += 1
                    self._note_duplicate(source)
                    return claim["owner"]
        return None

    def _note_duplicate(self, source: str) -> None:
        """Count one dropped duplicate (aggregate + per intake path)."""
        self._story_stats["duplicate_story_dropped"] += 1
        counter = f"duplicate_story_{source}"
        self._story_stats[counter] = self._story_stats.get(counter, 0) + 1

    def _drop_duplicate_poi(self, candidate) -> None:
        """Retire the losing POI so it cannot re-propose the same plan.

        The duplicate's story is already being traded through another POI;
        keeping its workflow alive would place the same plan later, after the
        first order resolved — exactly the spray this rule forbids.
        """
        poi_id = getattr(candidate, "poi_id", None)
        if poi_id is None:
            return
        pid = str(poi_id)
        self._menu_claimed_pois.add(pid)
        self._routed.add(pid)
        self._workflows.pop(pid, None)
        self._pop_pending_for_poi(pid)
        self._scan_cursor.pop(pid, None)

    def queue_menu_candidate(self, candidate: CandidateEntry) -> None:
        """Receive a winner candidate confirmed by the product menu.

        F7: the confirmation is submitted now and, when the runner reports
        per-candidate outcomes, resubmitted each bar until it is accepted or
        its menu window closes — a risk gate (news/session/breaker) must not
        silently destroy a confirmation that is still inside its window.

        ONE STORY (locked 2026-11-15): a winner whose plan already lives is
        dropped here — it won its window, but its story is already being
        traded, so this POI is retired instead of placing a second ticket.
        """
        if candidate is None:
            return
        if self._duplicate_story(candidate, source="menu") is not None:
            self._drop_duplicate_poi(candidate)
            return
        self._claim_story(candidate)
        self._menu_stats["menu_submitted"] += 1
        poi_id = getattr(candidate, "poi_id", None)
        if poi_id:
            pid = str(poi_id)
            self._menu_claimed_pois.add(pid)
            self._routed.add(pid)
            self._scan_cursor.pop(pid, None)
            self._workflows.pop(pid, None)
        if self._runner is not None:
            if poi_id and self._runner_reports_outcomes():
                # No window stamp → no bounded retry. Never invent a deadline.
                deadline = self._menu_deadline(candidate)
                route_key = self._route_key(candidate) or str(poi_id)
                if deadline is not None:
                    # The pending entry owns the submission: this bar's
                    # ``generate_candidates`` submits it ONCE (before the
                    # runner drains its queue), and every later bar resubmits
                    # it once more. Submitting here as well would double-enter
                    # the same confirmation within one bar.
                    self._menu_pending[route_key] = {
                        "candidate": candidate,
                        "deadline": deadline,
                        "attempted": False,
                        "poi_id": str(poi_id),
                        "book_id": self._book_id(candidate),
                    }
                    return
            self._runner.submit_entry(candidate)
        else:
            self._menu_candidates.append(candidate)

    # ------------------------------------------------------------------ #
    # F7 — menu winner resubmission
    # ------------------------------------------------------------------ #
    def menu_counters(self) -> dict:
        """F7 measurement surface (never read by a decision)."""
        return {**self._menu_stats, "menu_pending": len(self._menu_pending)}

    def _runner_reports_outcomes(self) -> bool:
        """True when the runner can say accepted/rejected per candidate."""
        # ONLY the explicit capability counts: a stub runner (research
        # submit-capture) never reports outcomes, so retrying there would
        # only inflate its submit count.
        return bool(getattr(self._runner, "supports_candidate_outcomes", False))

    def _menu_deadline(self, candidate):
        """Last instant the confirmation may still be submitted.

        Read from the candidate's own menu stamp (``window_end_ts`` — the
        engine's window end). When the stamp cannot supply it, fall back to
        the locked expiry over the stamped detection timeframe; when even
        that is missing the confirmation is not retried (no invented
        deadline).
        """
        stamp = self._menu_stamp(candidate)
        end = stamp.get("window_end_ts")
        if end:
            try:
                return datetime.fromisoformat(str(end))
            except ValueError:
                pass
        sweep = stamp.get("sweep_ts")
        det_name = stamp.get("detection_tf")
        if sweep and det_name:
            try:
                det = Timeframe[str(det_name).upper()]
                start = datetime.fromisoformat(str(sweep))
            except (KeyError, ValueError):
                return None
            from smc.orchestration.product_menu_mtf import MENU_EXPIRY_BARS

            return start + timedelta(
                minutes=(det.minutes * MENU_EXPIRY_BARS) + det.minutes
            )
        return None

    def _settle_menu_candidate(self, route_key, accepted: bool, reason) -> None:
        """Settle one pending menu confirmation (F7).

        ``route_key`` is ``<book>|<poi>`` (or a plain POI id for the legacy
        single-menu path). A bare POI id also settles that POI's book-stamped
        slots, so old callers keep their meaning.
        """
        key = str(route_key)
        if key not in self._menu_pending:
            matches = [
                k for k, pending in self._menu_pending.items()
                if pending.get("poi_id") == key
            ]
            if not matches:
                return
            key = matches[0]
        if accepted:
            self._menu_pending.pop(key, None)
            self._menu_stats["menu_accepted"] += 1
            return
        # Not accepted: keep it pending for the next bar's resubmission.
        self._menu_stats["menu_retry_blocked"] += 1

    def notify_candidate_outcome(self, candidate, *, accepted: bool, reason=None) -> None:
        """Runner seam (F7): did the runner accept this candidate this bar?

        ``accepted=False`` keeps the confirmation pending for the next bar;
        ``accepted=True`` settles it (placed, deferred to an R9 intent, or a
        dry-run placement that the runner counts as placed).
        """
        route_key = self._route_key(candidate)
        if route_key is None:
            return
        self._settle_menu_candidate(route_key, accepted, reason)

    def _resubmit_menu_pending(self, now: datetime) -> None:
        """F7: one resubmission attempt per bar, bounded by the window."""
        if not self._menu_pending or self._runner is None:
            return
        for route_key, pending in list(self._menu_pending.items()):
            deadline = pending.get("deadline")
            poi_id = pending.get("poi_id") or route_key
            if deadline is not None and now > deadline:
                self._menu_pending.pop(route_key, None)
                self._menu_stats["menu_expired_unplaced"] += 1
                # ONE STORY: window closed unplaced — frees the claim AND the
                # book layer's durable plan memory for this route key.
                self.release_story(route_key)
                # Release the claim: the menu window is closed, so the normal
                # scan may own this POI again if it is still live.
                if not self._pending_keys_for_poi(poi_id):
                    self._menu_claimed_pois.discard(poi_id)
                    self._routed.discard(poi_id)
                continue
            self._runner.submit_entry(pending["candidate"])
            if pending["attempted"]:
                self._menu_stats["menu_resubmitted"] += 1
            pending["attempted"] = True

    # ------------------------------------------------------------------ #
    # Runner adapter protocol
    # ------------------------------------------------------------------ #
    def generate_candidates(
        self, bar: Candle, bar_index: int, now: datetime
    ) -> None:
        """Per-bar pipeline step (called by the runner's entry step)."""
        state = self._ensure_state(bar_index)
        self._story_bar = bar_index
        # ONE STORY: claims follow the book — prune the sealed ones whose
        # plan is no longer live (order cancelled/expired/closed).
        self._prune_story_claims()
        # F7: retry confirmed-but-unaccepted menu winners before the scan.
        self._resubmit_menu_pending(now)
        if self._runner is not None and self._menu_candidates:
            while self._menu_candidates:
                cand = self._menu_candidates.pop(0)
                self._runner.submit_entry(cand)

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
            #    only when no route was ever produced (§11 one-shot)
            #    and NOT claimed or covered by menu confirmation
            #    and (M-3) NOT outside every selected book's tier set.
            outside_books = self._outside_book_tiers(poi)
            if outside_books:
                # The multiplexer owns this POI's tiers and no book carries
                # its detection tier: the archived single-menu seek path must
                # NOT quietly take it back (no book stamp, no SMC-<TAG>-,
                # no cross-book dedupe). Skip once, counted.
                if poi.id not in self._outside_book_pois:
                    self._outside_book_pois.add(poi.id)
                    self._menu_stats["poi_outside_books"] += 1
                self._routed.add(poi.id)
                self._scan_cursor.pop(poi.id, None)
            seek_route = (
                workflow is None
                and poi.id not in self._routed
                and not outside_books
                and not self.menu_covers_poi(poi)
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
                    # C3 slow-path in-between gate: validity reads the
                    # completion bar's CLOSE (never the limit price).
                    completion_bar = route.signal.completion_index
                    completion_close = (
                        float(state.candles[completion_bar].close)
                        if 0 <= completion_bar < len(state.candles)
                        else None
                    )
                    candidate = candidate_from_route(
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
                                max_age_bars=poi_give_up_bars()),
                            completion_price=completion_close)
                    if candidate is None:
                        # C3: completion outside the POI body. No route from
                        # this completion — resume the chronological scan on
                        # the next bar (a later in-between completion may win).
                        self._scan_cursor[poi.id] = bar_index + 1
                    elif self._duplicate_story(candidate, source="seek") is not None:
                        # ONE STORY (locked 2026-11-15): this POI's plan is
                        # already live through another POI. Burn this POI's
                        # one-shot instead of retrying it every bar — a
                        # retry would place the same plan after the first
                        # order resolved (the spray the rule forbids).
                        self._routed.add(poi.id)
                        self._scan_cursor.pop(poi.id, None)
                    else:
                        self._claim_story(candidate)
                        workflow = _Workflow(
                            candidate=candidate,
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
                    self.release_story(poi.id)  # ONE STORY: free the plan
                elif self._runner is not None:
                    self._runner.submit_entry(workflow.candidate)

            # 3. §5 freshness feed — engine authority, AFTER the scan (the
            #    touch bar itself must still be routable: first touch OK).
            result = self.engine.feed_bar(poi, bar)
            if result == POIState.VIOLATED.value:
                # Dead thesis: drop the workflow and pull any resting
                # limit so it can never fill against a violated zone.
                self._workflows.pop(poi.id, None)
                self.release_story(poi.id)  # ONE STORY: dead thesis, free plan
                if self._runner is not None:
                    self._runner.cancel_pending_for_poi(poi.id)
            elif result == POIState.TESTED.value:
                self._tested_bar.setdefault(poi.id, bar_index)

    def on_candidate_accepted(self, candidate: CandidateEntry) -> None:
        """Consume the POI one-shot — called ONLY on an accepted placement.

        THE single accept seam (this method used to be defined twice; the
        later definition silently shadowed the F7 settle, so the two are
        merged here): a real placement consumes the §11 one-shot, settles an
        F7 pending confirmation (a placed winner must not be resubmitted),
        and seals the ONE STORY claim (the plan now follows the book).
        """
        if candidate.poi_id is not None:
            pid = str(candidate.poi_id)
            # C-1/M-2: settle and seal THIS route only — a second book's
            # pending/claim on the same POI is a different order.
            route_key = self._route_key(candidate) or pid
            self._workflows.pop(candidate.poi_id, None)
            self._menu_claimed_pois.add(pid)
            self._routed.add(pid)
            self._settle_menu_candidate(route_key, True, "placed")
            self.seal_story(route_key)

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
            self.release_story(poi_id)  # ONE STORY: no placement, free plan
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
            # F6: keep the menu's arming book bounded by live POIs.
            menu = self.menu_confirmation
            retire = getattr(menu, "retire", None)
            if callable(retire):
                retire(poi_id)
            # F7: a dead POI's pending confirmations die with it (every book).
            if self._pop_pending_for_poi(poi_id):
                self._menu_stats["menu_dropped_poi_retired"] += 1
                self._menu_claimed_pois.discard(poi_id)
                self._release_menu_plan(poi_id)
        # LEG 5 (design R3.2): engine first, registry second — the ids this
        # prune just released lose their ZoneDedup keys in the SAME step,
        # then the still-tracked episodes that satisfy the R3.1 death
        # predicate (no live obligation AND terminal-or-past-give-up) are
        # swept. The engine's own retention is deliberately untouched
        # (design §1.1: adapter ``bar=None`` retention keeps FRESH/TESTED;
        # the registry is the lifecycle subject, not the engine's list).
        # NOTE: the sweep receives the RUNNER-SUPPLIED obligation ids
        # (orders / positions / alive intents) — NOT the ``_may_route``
        # retention additions above, which keep an episode routable but are
        # NOT a live trade obligation (F-1 distinction).
        self._retire_dead_keys(pruned, set(retain_ids or ()), bar_index)
        return pruned

    def bind_dedup_registry(self, dedup) -> None:
        """LEG 5 R3.4: bind the session's effective ZoneDedup handle.

        Called by ``MultiTFProductRuntime`` in the arm seam so the object
        this adapter retires from IS the object ``seen()`` reads for that
        session (``run_batch``'s ``dedup`` override, else the runtime's own
        registry). Idempotent for the same handle; silently rebinding a
        DIFFERENT handle would split identity — refused loudly.
        """
        if self._dedup_registry is not None and self._dedup_registry is not dedup:
            raise ValueError(
                "adapter already bound to a different dedup registry "
                "(LEG 5 R3.4 handle identity)")
        self._dedup_registry = dedup

    def _retire_dead_keys(self, pruned_ids, retain, bar_index) -> None:
        """LEG 5 R3.1/R3.2: release ZoneDedup keys of product-dead episodes.

        Death (design R3.1) = the owning episode has NO live obligation
        (no resting order, no open position, no alive R9 intent — carried
        in ``retain`` by the runners' ``_prune_engine_state`` — and no
        in-flight workflow) AND (§5 state VIOLATED OR
        ``bar_index > arm_bar + poi_give_up_bars()`` — the SAME clock the
        give-up scan closure already uses). FRESH/TESTED inside the
        window stay live even with no obligation (the episode may still
        route — P1 conservatism); any obligated POI stays live
        regardless of state or clock.

        Fail-safe (design R6): no handle → no-op; a per-POI evaluation
        failure never breaks the bar loop. Nothing is cleared wholesale,
        no arm may raise because of retirement, and no new threshold
        exists (the clock is the shipped ``poi_give_up_bars()``).
        """
        dedup = self._dedup_registry
        if dedup is None or not callable(getattr(dedup, "retire", None)):
            return
        try:
            for poi_id in pruned_ids:
                if poi_id in self._retire_sent:
                    continue
                self._retire_sent.add(poi_id)
                dedup.retire(poi_id)
            if bar_index is None:
                return  # legacy no-bar prune: terminal release only
            obligations = set(retain or ())
            obligations |= set(self._workflows)
            give_up = poi_give_up_bars()
            machine = self.engine.state_machine
            for poi in self.engine.tracked_pois():
                if poi.id in obligations or poi.id in self._retire_sent:
                    continue
                if machine.current(poi) is not POIState.VIOLATED:
                    episode = self.engine.episode(poi)
                    if episode is None:
                        continue
                    if not bar_index > episode.arm_bar + give_up:
                        continue  # still inside its seek window — live
                self._retire_sent.add(poi.id)
                dedup.retire(poi.id)
        except Exception:  # noqa: BLE001 — retirement must never break the bar
            return

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
        """Attach to a runner (:class:`~smc.backtest.runner.BacktestRunner` or PaperRunner)."""
        self._runner = runner
        set_adapter = getattr(runner, "set_pipeline_adapter", None)
        if callable(set_adapter):
            set_adapter(self)
        if self._runner is not None and self._menu_candidates:
            while self._menu_candidates:
                cand = self._menu_candidates.pop(0)
                self._runner.submit_entry(cand)

    def set_candles(self, candles: list[Candle]) -> None:
        """Point the adapter at the execution-TF series (scan input).

        The runner's own bars drive ``feed_bar``; this series is the scan
        universe — the incremental state extends through it bar by bar
        (no per-bar prefix slices).
        """
        self._candles = candles
        self._state = None
