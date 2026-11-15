"""ONE STORY → ONE PLAN → AT MOST ONE LIVE ORDER (locked product rule).

Locked by the Lead Architect on 2026-11-15 (see
``06_RESEARCH/ONE_STORY_ONE_TRADE_DESIGN.md``): one concrete story yields one
plan, and at most one live candidate order may exist for that plan.

Many *ways to read* structure stay: every POI model, BOS/CHOCH, FVG and
trigger type keeps producing its own story. What collapses is the exotic
case the product measured in PFE-2/PFE-3 — several POI ids whose confirmed
routes resolve to the *same executable plan*.

Definition of "same story" (normative, do not soften):

1. same symbol — implicit in V1 (single symbol per session);
2. same direction;
3. overlapping POI zone — the ``ZoneDedup`` geometric rule (inclusive span
   overlap), reused here through :func:`zones_overlap` so there is exactly
   one overlap implementation in the codebase;
4. same trigger type;
5. same entry price (exact float as planned — no pip tolerance is invented);
6. same SL and same TP (exact floats as planned).

Everything is *plan* identity: no threshold, no statistical band, and no
reading of PnL. A key that cannot be built (no entry/SL, or unknown zone
bounds) is never treated as a duplicate — sameness is only ever asserted
from known geometry, never guessed.

The guard itself is stateless bookkeeping: callers hold
:class:`~story_guard.StoryKey` claims and prune them against the plans that
are still live (resting order, open position, in-flight candidate). This
module therefore imports nothing from the orchestration or execution layers.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["StoryKey", "story_key", "same_story", "zones_overlap"]


def zones_overlap(top_a, bottom_a, top_b, bottom_b) -> bool:
    """Inclusive span overlap — the ZoneDedup rule (single implementation).

    Same semantics as ``ZoneDedup.seen``: ``known_top >= bottom and
    top >= known_bottom``. The caller supplies already-validated floats.
    """
    return float(top_a) >= float(bottom_b) and float(top_b) >= float(bottom_a)


def _attr(obj, *names):
    """First non-None attribute among ``names`` (None when none exist)."""
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return None


def _price(value) -> float | None:
    """Float price or None — never a coerced string, never a guess."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _trigger_id(value):
    """Trigger identity as a plain value (enums compare by their value)."""
    return getattr(value, "value", value)


@dataclass(frozen=True, slots=True)
class StoryKey:
    """The executable plan of one candidate/order (rule 1-6 identity)."""

    direction: object
    trigger: object
    entry_price: float | None
    sl: float | None
    tp: float | None
    zone_low: float | None
    zone_high: float | None


def story_key(candidate) -> StoryKey | None:
    """Build the plan identity of a candidate/order/position (None = unknown).

    Absent entry or SL means there is no executable plan to compare, so the
    object has no story identity and can never be collapsed.
    """
    entry = _price(_attr(candidate, "entry_price", "entry"))
    sl = _price(_attr(candidate, "sl_price", "sl"))
    if entry is None or sl is None:
        return None
    return StoryKey(
        direction=_attr(candidate, "direction"),
        trigger=_trigger_id(_attr(candidate, "trigger")),
        entry_price=entry,
        sl=sl,
        tp=_price(_attr(candidate, "tp_price", "tp", "take_profit")),
        zone_low=_price(_attr(candidate, "zone_low")),
        zone_high=_price(_attr(candidate, "zone_high")),
    )


def same_story(a: StoryKey | None, b: StoryKey | None) -> bool:
    """True when both keys describe the SAME executable plan (rules 2-6).

    Rule 1 (same symbol) is implicit: V1 runs one symbol per session, so the
    caller's book only ever contains that symbol.
    """
    if a is None or b is None:
        return False
    if a.direction != b.direction:
        return False
    if a.trigger != b.trigger:
        return False
    if a.entry_price != b.entry_price or a.sl != b.sl:
        return False
    if a.tp != b.tp:
        return False
    if (a.zone_low is None or a.zone_high is None
            or b.zone_low is None or b.zone_high is None):
        # Rule 3 needs known zone bounds; without them sameness is unproven
        # (never a softer merge).
        return False
    return zones_overlap(a.zone_high, a.zone_low, b.zone_high, b.zone_low)
