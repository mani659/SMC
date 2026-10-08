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
from smc.triggers.base_trigger import FR2_TP_ATR_MULTIPLE

__all__ = ["candidate_from_route", "fvg_context_for_route",
           "pillar_path_summary", "resolve_take_profit",
           "structural_tp_target"]

# Structural TP feed (design lock 2026-10-05, Architect-accepted as INTERIM
# — same class as the FR-2 constants; exact value pinned in tests; pending
# formal § lock).
STRUCTURAL_TP_MIN_ATR = 0.25


def pillar_path_summary(result) -> str | None:
    """Summarize one POI's validation path as a log string (duck-typed).

    PASS → ``"PASS:1+2+3+4+5;inducement=1.0"`` (pillar numbers in run order
    plus the soft Pillar-5 modifier); FAIL → ``"FAIL@<pillar>:<name>:<status>
    :<detail>"`` from the first hard failure. ``None`` input → ``None``
    (unknown — never invented). Pure formatting; no decision content.
    """
    if result is None:
        return None
    if bool(getattr(result, "passed", False)):
        nums = "+".join(
            str(getattr(pr, "pillar", "?"))
            for pr in (getattr(result, "pillar_results", None) or [])
        )
        return f"PASS:{nums};inducement={getattr(result, 'inducement_modifier', '?')}"
    first = None
    try:
        first = result.first_failure
    except AttributeError:
        first = None
    if first is None:
        return "FAIL:unknown"
    status = getattr(getattr(first, "status", None), "name", None)
    if status is None:
        status = str(getattr(first, "status", None))
    return (f"FAIL@{getattr(first, 'pillar', '?')}:"
            f"{getattr(first, 'name', '?')}:{status}:"
            f"{getattr(first, 'detail', '')}")


def resolve_take_profit(entry_price: float, direction: Direction,
                        atr: float | None,
                        structural_target=None) -> float | None:
    """Take-profit price per FR-2 policy R4 (FOUNDATION_RESET_PLAN).

    A caller-supplied structural target wins when it is finite and strictly
    favorable (LONG above entry, SHORT below); anything else — absent,
    wrong-sided, non-finite — falls back to entry ± 4×ATR in trade
    direction. A missing/non-positive ATR yields None (same as the old
    always-None path, documented — never an invented fill level).
    Today no trigger emits a structural target, so the live path is the
    4×ATR fallback; the structural branch is wired and unit-tested for
    future triggers (no Fib engines invented here).
    """
    import math

    target = None
    if structural_target is not None:
        try:
            candidate = float(structural_target)
        except (TypeError, ValueError):
            candidate = None
        if candidate is not None and math.isfinite(candidate):
            if direction is Direction.LONG and candidate > entry_price:
                target = candidate
            elif direction is not Direction.LONG and candidate < entry_price:
                target = candidate
    if target is not None:
        return target
    if atr is None or not atr > 0:
        return None
    if direction is Direction.LONG:
        return entry_price + FR2_TP_ATR_MULTIPLE * atr
    return entry_price - FR2_TP_ATR_MULTIPLE * atr


def structural_tp_target(swings, entry_price: float, direction: Direction,
                         atr: float | None,
                         placement_bar: int | None = None,
                         max_age_bars: int | None = None) -> float | None:
    """First-swing structural TP selector (design lock 2026-10-05).

    Among §19-confirmed swings of the opposing polarity on the place-time
    prefix, choose the nearest favorable swing in price (recency
    tie-break on equal levels) that satisfies:

      * strictly favorable vs the entry (LONG: level > entry_price;
        SHORT: level < entry_price) — wrong-side swings are ignored;
      * at least ``STRUCTURAL_TP_MIN_ATR × atr`` beyond entry (noise
        guard; absent/non-positive ATR → no structural TP — fail to the
        4×ATR fallback rather than approximate);
      * §19-confirmed strictly before the placement bar
        (``confirmed_index is not None and confirmed_index <
        placement_bar``) — lookahead ban: an unconfirmed extreme or one
        confirmed at/after the decision bar is never used;
      * optional CPU/age cap ``max_age_bars``: a swing whose base candle
        index is older than ``placement_bar - max_age_bars`` is skipped
        (Architect ruling: a documented BOUND, not give-up semantics —
        the primary rule is the confirmed-prefix rule above).

    Returns the swing's level as the target, or ``None`` when no swing
    qualifies — the caller then feeds ``structural_target=None`` and
    ``resolve_take_profit`` takes its unchanged 4×ATR fallback. Pure
    function: reads only the snapshot given; deterministic tie-breaks;
    no clock, no RNG, no engine state.
    """
    import math

    if atr is None or not atr > 0:
        return None
    min_dist = STRUCTURAL_TP_MIN_ATR * atr
    is_long = direction is Direction.LONG
    best = None          # ((distance, -candle_index), level)
    for swing in swings:
        level = getattr(swing, "level", None)
        if level is None:
            continue
        try:
            level = float(level)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(level):
            continue
        # Lookahead ban + §19 confirmation (primary rule, Architect ruling 2).
        ci = getattr(swing, "confirmed_index", None)
        if not swing.is_valid or ci is None:
            continue
        if placement_bar is not None and ci >= placement_bar:
            continue
        # Optional age bound (CPU/age cap — NOT give-up semantics).
        if (placement_bar is not None and max_age_bars is not None
                and swing.candle_index < placement_bar - max_age_bars):
            continue
        # Sidedness + noise guard.
        if is_long:
            if not level > entry_price + min_dist:
                continue
            dist = level - entry_price
        else:
            if not level < entry_price - min_dist:
                continue
            dist = entry_price - level
        key = (dist, -swing.candle_index)
        if best is None or key < best[0]:
            best = (key, level)
    return None if best is None else best[1]


def candidate_from_route(route: TriggerRoute, *, displacement=None,
                         pillar_path: str | None = None,
                         atr: float | None = None,
                         structural_target=None) -> CandidateEntry:
    """Map a winning trigger route to a runner candidate entry.

    The signal's ``entry_price`` is the resting limit and ``stop_reference``
    the SL (the limit-order contract is frozen — §10: triggers are never
    market orders). TP follows :func:`resolve_take_profit` (structural
    target else 4×ATR; None only when ATR is unknowable).

    ``score`` is the POI's §1 confluence score (tag count) so the runner's
    spread grading (§28.5) sees the same quality input the live path uses.

    Identity enrichment (logging only — the entry/SL/trigger mapping is
    untouched): ``model_tags`` always comes from ``route.poi.models``;
    ``displacement`` (a DisplacementResult or None) contributes its
    ``magnitude_atr``; ``pillar_path`` is a preformatted summary string
    (see :func:`pillar_path_summary`). Absent inputs stay ``None``.
    """
    poi = route.poi
    signal = route.signal
    tags = tuple(getattr(m, "name", str(m)) for m in (poi.models or [])) or None
    magnitude_atr = getattr(displacement, "magnitude_atr", None)
    try:
        magnitude_atr = None if magnitude_atr is None else float(magnitude_atr)
    except (TypeError, ValueError):
        magnitude_atr = None
    # Structural TP provenance (design lock 2026-10-05): the TP came from
    # the structural branch exactly when a structural target was supplied
    # AND resolve_take_profit returned it verbatim (its sidedness/
    # finiteness re-validation passed). Otherwise the 4×ATR fallback
    # produced it (or ATR was unknowable → None TP; tagged as fallback
    # origin for audit honesty).
    tp_value = resolve_take_profit(
        signal.entry_price, signal.direction, atr,
        structural_target=structural_target)
    if structural_target is not None:
        try:
            used = (tp_value is not None
                    and tp_value == float(structural_target))
        except (TypeError, ValueError):
            used = False
        tp_source = "structural_swing" if used else "atr_fallback"
    else:
        tp_source = "atr_fallback"
    zone = getattr(poi, "zone", None)
    zone_low = getattr(zone, "bottom", None)
    zone_high = getattr(zone, "top", None)
    try:
        zone_low = None if zone_low is None else float(zone_low)
        zone_high = None if zone_high is None else float(zone_high)
    except (TypeError, ValueError):
        zone_low, zone_high = None, None
    signal_data = getattr(signal, "data", None)
    if signal_data:
        try:
            import json as _json
            signal_data_json = _json.dumps(signal_data, sort_keys=True,
                                           default=str)
        except (TypeError, ValueError):
            signal_data_json = None
    else:
        signal_data_json = None
    # E1: first-class entry-anchor provenance — read from the signal's data
    # dict only when the trigger actually set it (a string); absent/None or
    # non-string values stay None (never coerced, never invented).
    anchor = signal_data.get("entry_anchor") if signal_data else None
    if not isinstance(anchor, str) or not anchor:
        anchor = None
    return CandidateEntry(
        direction=signal.direction,
        entry_price=signal.entry_price,
        sl_price=signal.stop_reference,
        tp_price=tp_value,
        score=float(poi.score),
        poi_id=poi.id,
        trigger=signal.trigger,
        # §11 event identity string — same format the engine's limit-request
        # comment uses (POI prefix : trigger @ completion bar).
        route_id=f"{poi.id}:{signal.trigger.value}@{signal.completion_index}",
        # Honest FVG derivation bound NOW (frozen dataclass — never mutated
        # later): the runner calls ``candidate.fvg_context()`` at fill and
        # attaches the context only when the signal can supply one.
        fvg_provider=lambda route=route: fvg_context_for_route(route),
        model_tags=tags,
        pillar_path=pillar_path,
        disp_magnitude_atr=magnitude_atr,
        # Placement-time snapshot: original_sl EQUALS the placement SL here
        # by construction (BE modifies must never touch this field —
        # enforced by test); zone/signal geometry when available.
        original_sl=signal.stop_reference,
        zone_low=zone_low,
        zone_high=zone_high,
        signal_data_json=signal_data_json,
        entry_anchor=anchor,
        tp_source=tp_source,
        # FR fill-regime provenance (R7 place guard + R8 rest bars):
        # detection timeframe rides on the POI's zone; M8 is a model TAG,
        # not a timeframe. Both are set from the route POI only — never
        # invented when the POI/zone lacks them (None/False = defaults).
        detection_tf=getattr(zone, "timeframe", None),
        is_m8="M8" in (tags or ()),
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
