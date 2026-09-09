"""Phase 6 M4 — Pipeline → backtest bridge (real detection → risk → orders).

Turns a validated trigger route from :class:`~smc.orchestration.engine.PipelineEngine`
into the :class:`~smc.backtest.runner.CandidateEntry` the M3 runner consumes,
and derives the per-trade context that must ride along:

* **Route → candidate** (:func:`candidate_from_route`) — pure mapping of the
  route's signal (direction / entry limit / SL / TP) plus the §15 matrix
  confluence score and the POI/trigger identity. Route identity (POI id +
  trigger type) is part of the event identity (R1 §11: one validated POI +
  one LTF trigger + one execution).
* **FVG context mapping** (:func:`fvg_context_for_route`) — the honest
  derivation only: the trigger signal's OWN signal FVG (Trigger F emits
  ``fvg`` in its signal ``data``; v25 ports that FVG to the trade for
  structural invalidation). When the signal cannot supply a real FVG the
  context is ``None`` — the runner then skips FVG invalidation for that
  trade rather than inventing geometry (M4 constraint: no fabricated FVG).

Both helpers are pure functions — no clock, no MT5, no engine state.
"""

from __future__ import annotations

from smc.backtest.runner import CandidateEntry
from smc.core.enums import Direction, TriggerType
from smc.orchestration.engine import TriggerRoute
from smc.risk.fvg_invalidation import FvgContext

__all__ = ["candidate_from_route", "fvg_context_for_route"]


def candidate_from_route(route: TriggerRoute) -> CandidateEntry:
    """Map a winning trigger route to a runner candidate entry.

    The signal's ``entry_price`` is the resting limit and ``stop_reference``
    the SL (the limit-order contract is frozen — §10: triggers are never
    market orders). TP stays ``None``: V1 exits are physical SL + FVG
    invalidation + PureRunner BE; no fixed-RR TP is invented here.

    ``score`` is the POI's §1 confluence score (tag count) so the runner's
    spread grading (§28.5) sees the same quality input the live path uses.
    """
    poi = route.poi
    signal = route.signal
    return CandidateEntry(
        direction=signal.direction,
        entry_price=signal.entry_price,
        sl_price=signal.stop_reference,
        tp_price=None,
        score=float(poi.score),
        poi_id=poi.id,
        trigger=signal.trigger,
        # §11 event identity string — same format the engine's limit-request
        # comment uses (POI prefix : trigger @ completion bar).
        route_id=f"{poi.id}:{signal.trigger.value}@{signal.completion_index}",
        # Honest FVG derivation bound NOW (frozen dataclass — never mutated
        # later): the runner calls ``candidate.fvg_context()`` at fill and
        # attaches the context only when the signal can supply a real FVG.
        fvg_provider=lambda route=route: fvg_context_for_route(route),
    )


def fvg_context_for_route(route: TriggerRoute) -> FvgContext | None:
    """Derive the trade's FVG context from the signal — honestly or not at all.

    The mapping (design note §FVG):

    * Trigger F (BOS→OB continuation) emits the origin OB's FVG in
      ``signal.data["fvg"]`` (the displacement leg's gap that anchored the
      OB); a LONG trade maps it to a bull FVG, a SHORT to a bear FVG —
      exactly the v25 ``g_activeFVGCtx`` snapshot at trade open.
    * Every other trigger (and any F whose signal carries no FVG) returns
      ``None``: the runner leaves the context absent and FVG invalidation
      is skipped for that trade. Geometry is never reconstructed from the
      zone or invented.
    """
    signal = route.signal
    if signal.trigger is not TriggerType.F_BOS_OB:
        return None
    fvg = signal.data.get("fvg") if signal.data else None
    if not isinstance(fvg, dict):
        return None
    try:
        low = float(fvg["low"])
        high = float(fvg["high"])
    except (KeyError, TypeError, ValueError):
        return None
    if not high > low:  # degenerate geometry → absent, never invented
        return None
    # A bull FVG underpins LONG trades, a bear FVG caps SHORT trades —
    # the direction this FVG belongs to (v25 semantics).
    direction = Direction.LONG if signal.direction is Direction.LONG else Direction.SHORT
    return FvgContext(valid=True, low=low, high=high, direction=direction)
