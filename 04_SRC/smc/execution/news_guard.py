"""News protocol — high-impact event guard (LOCKED_DECISIONS §11 — frozen).

§11: HARD-cancel all pending POI limit orders 15 minutes before high-impact
news (``NEWS_HARD_CANCEL_MINUTES``); re-evaluate after the dust settles,
typically 30 minutes post-release (``NEWS_RE_EVALUATE_MINUTES``).

High-impact events: US CPI, NFP, FOMC — matched by ``NewsEvent.kind``
(strings from the locked docs; the calendar feed is a Phase 6/7 concern —
the guard is a pure policy function over supplied events).

The guard only decides; cancelling orders is ``OrderManager.cancel_order``
(engine orchestrates).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from smc.config.locked_constants import (
    NEWS_HARD_CANCEL_MINUTES,
    NEWS_RE_EVALUATE_MINUTES,
)
from smc.utils.timestamps import to_utc

__all__ = ["NewsEvent", "HIGH_IMPACT_EVENTS", "should_hard_cancel", "should_block_entry"]

HIGH_IMPACT_EVENTS = frozenset({"CPI", "NFP", "FOMC"})


@dataclass(frozen=True, slots=True)
class NewsEvent:
    """One scheduled high-impact event (kind ∈ §11 high-impact names)."""

    kind: str
    at: datetime  # event time (UTC-normalized)


def should_hard_cancel(now: datetime, events: list[NewsEvent]) -> bool:
    """True when any high-impact event starts within the §11 pre-window."""
    now = to_utc(now)
    window = timedelta(minutes=NEWS_HARD_CANCEL_MINUTES)
    return any(
        event.kind in HIGH_IMPACT_EVENTS
        and timedelta(0) <= (to_utc(event.at) - now) <= window
        for event in events
    )


def should_block_entry(now: datetime, events: list[NewsEvent]) -> bool:
    """True while entries are blocked around a high-impact event.

    Blocked from the pre-event hard-cancel window until
    ``NEWS_RE_EVALUATE_MINUTES`` after the release (§11 re-evaluate).
    """
    now = to_utc(now)
    pre = timedelta(minutes=NEWS_HARD_CANCEL_MINUTES)
    post = timedelta(minutes=NEWS_RE_EVALUATE_MINUTES)
    for event in events:
        if event.kind not in HIGH_IMPACT_EVENTS:
            continue
        start = to_utc(event.at)
        if start - pre <= now <= start + post:
            return True
    return False
