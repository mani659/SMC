"""Confluence scorer (LOCKED_DECISIONS §1, §21/§26).

All 8 models are EQUAL tags on a level; quality grows with the number of
independent tags that label it (frozen tiers): 1 = base, 2 = elevated,
3+ = institutional-grade. No model is suppressed and none overrides another.

V1 numeric convention (documented): the quality ``score`` is the number of
independent model tags on the POI, plus ``M8_HTF_OVERLAP_BONUS`` (+0.10,
quality-score only — never position size) when Model 8 is present and the
POI is flagged ``htf_overlap=True`` (§21/§26).

Overlapping POIs whose zones intersect (same direction) are merged into one
POI carrying the union of tags, the widest zone, the earliest id/creation
time, and the OR of ``htf_overlap`` flags.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from smc.config.locked_constants import (
    CONFLUENCE_BASE_TAGS,
    CONFLUENCE_ELEVATED_TAGS,
    CONFLUENCE_INSTITUTIONAL_TAGS,
    M8_HTF_OVERLAP_BONUS,
)
from smc.config.model_type import ModelType
from smc.core.poi import POI
from smc.core.zone import Zone

__all__ = [
    "ConfluenceTier",
    "ConfluenceScore",
    "quality_tier",
    "score_poi",
    "merge_overlapping",
]


class ConfluenceTier(Enum):
    """Quality tiers from independent tag count (§1)."""

    BASE = "base"                    # 1 tag — tradeable
    ELEVATED = "elevated"            # 2 tags — preferred
    INSTITUTIONAL = "institutional"  # 3+ tags — highest quality


@dataclass(frozen=True, slots=True)
class ConfluenceScore:
    tag_count: int
    tier: ConfluenceTier
    score: float


def quality_tier(tag_count: int) -> ConfluenceTier:
    """Tier for an independent model-tag count (§1 frozen mapping)."""
    if tag_count >= CONFLUENCE_INSTITUTIONAL_TAGS:
        return ConfluenceTier.INSTITUTIONAL
    if tag_count >= CONFLUENCE_ELEVATED_TAGS:
        return ConfluenceTier.ELEVATED
    if tag_count >= CONFLUENCE_BASE_TAGS:
        return ConfluenceTier.BASE
    raise ValueError("a POI must carry at least one model tag")


def score_poi(poi: POI) -> ConfluenceScore:
    """Quality score of a POI from its independent tags (§1 + §21/§26 bonus)."""
    tags = sorted({m for m in poi.models})  # dedupe, independence by model
    if not tags:
        raise ValueError("a POI must carry at least one model tag")
    bonus = M8_HTF_OVERLAP_BONUS if (
        ModelType.M8 in tags and poi.htf_overlap
    ) else 0.0
    return ConfluenceScore(
        tag_count=len(tags),
        tier=quality_tier(len(tags)),
        score=float(len(tags)) + bonus,
    )


def merge_overlapping(pois: list[POI]) -> list[POI]:
    """Merge same-direction POIs whose zones intersect into one POI each.

    Merging rule (V1, documented): when zones overlap, keep the union zone
    [min(bottom), max(top)], the union of model tags (sorted), the earliest
    id/creation time, and OR the ``htf_overlap`` flags. Non-overlapping POIs
    pass through untouched.
    """
    remaining = list(pois)
    merged: list[POI] = []
    while remaining:
        base = remaining.pop(0)
        group = [base]
        others: list[POI] = []
        for candidate in remaining:
            if _zones_overlap(base.zone, candidate.zone):
                group.append(candidate)
            else:
                others.append(candidate)
        remaining = others
        if len(group) == 1:
            merged.append(base)
            continue

        zone = base.zone
        for member in group[1:]:
            zone = Zone(
                top=max(zone.top, member.zone.top),
                bottom=min(zone.bottom, member.zone.bottom),
                direction=zone.direction,
                timeframe=zone.timeframe,
            )
        tags = sorted({m for poi in group for m in poi.models})
        earliest = min(group, key=lambda p: p.created_at)
        merged.append(
            POI(
                zone=zone,
                models=tags,
                created_at=earliest.created_at,
                htf_overlap=any(p.htf_overlap for p in group),
                id=earliest.id,
            )
        )
    return merged


def _zones_overlap(a: Zone, b: Zone) -> bool:
    if a.direction is not b.direction:
        return False
    return a.bottom <= b.top and b.bottom <= a.top