"""Phase 2 — Confluence scorer: equal tags, tiers, M8 bonus, zone merging (§1, §21/§26)."""

from datetime import datetime, timezone

import pytest

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.poi.confluence_scorer import (
    ConfluenceTier,
    merge_overlapping,
    quality_tier,
    score_poi,
)

TF = Timeframe.M5


def _zone(top: float, bottom: float, direction: Direction = Direction.LONG) -> Zone:
    return Zone(top=top, bottom=bottom, direction=direction, timeframe=TF)


def _poi(top, bottom, models, direction=Direction.LONG, htf_overlap=False, created_at=None):
    return POI(
        zone=_zone(top, bottom, direction),
        models=models,
        htf_overlap=htf_overlap,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_quality_tier_mapping():
    assert quality_tier(1) is ConfluenceTier.BASE
    assert quality_tier(2) is ConfluenceTier.ELEVATED
    assert quality_tier(3) is ConfluenceTier.INSTITUTIONAL
    assert quality_tier(5) is ConfluenceTier.INSTITUTIONAL
    with pytest.raises(ValueError):
        quality_tier(0)


def test_score_poi_counts_independent_tags_and_skips_duplicates():
    poi = _poi(101.0, 100.0, [ModelType.M1, ModelType.M2, ModelType.M1])
    score = score_poi(poi)
    assert score.tag_count == 2
    assert score.tier is ConfluenceTier.ELEVATED
    assert score.score == pytest.approx(2.0)


def test_score_poi_m8_overlap_bonus():
    poi = _poi(101.0, 100.0, [ModelType.M1, ModelType.M8], htf_overlap=True)
    score = score_poi(poi)
    assert score.tag_count == 2
    assert score.score == pytest.approx(2.1)  # +0.10 M8_HTF_OVERLAP_BONUS


def test_score_poi_m8_without_overlap_gets_no_bonus():
    poi = _poi(101.0, 100.0, [ModelType.M8])
    score = score_poi(poi)
    assert score.tag_count == 1
    assert score.tier is ConfluenceTier.BASE
    assert score.score == pytest.approx(1.0)


def test_score_poi_empty_raises():
    with pytest.raises(ValueError):
        score_poi(_poi(101.0, 100.0, []))


def test_merge_overlapping_unions_tags_and_zone():
    a = _poi(101.0, 100.0, [ModelType.M1], created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    b = _poi(102.0, 100.5, [ModelType.M2], created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    merged = merge_overlapping([a, b])
    assert len(merged) == 1
    assert merged[0].zone.top == 102.0
    assert merged[0].zone.bottom == 100.0
    assert set(merged[0].models) == {ModelType.M1, ModelType.M2}
    assert merged[0].id == a.id  # earliest creation time wins
    assert merged[0].created_at == a.created_at


def test_merge_overlapping_ors_htf_overlap_flag():
    a = _poi(101.0, 100.0, [ModelType.M8], htf_overlap=False)
    b = _poi(102.0, 100.5, [ModelType.M1], htf_overlap=True)
    merged = merge_overlapping([a, b])
    assert len(merged) == 1
    assert merged[0].htf_overlap is True


def test_merge_overlapping_keeps_non_overlapping_and_opposite_direction():
    bull = _poi(101.0, 100.0, [ModelType.M1], direction=Direction.LONG)
    far_bull = _poi(110.0, 109.0, [ModelType.M2], direction=Direction.LONG)
    bear = _poi(102.0, 100.5, [ModelType.M3], direction=Direction.SHORT)
    merged = merge_overlapping([bull, far_bull, bear])
    # bear overlaps bull in price but is the OPPOSITE direction -> no merge.
    assert len(merged) == 3
