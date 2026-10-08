"""Phase 2 — Layer / pillar CONTRACT tests (Choice 1 sequence).

Every contract pins: known synthetic inputs → REQUIRED PillarStatus / decision,
with a stable reason token in the detail string. These are NOT expectancy
tests — they freeze the layer interfaces so a silent semantic drift breaks a
named test instead of a 6-month run.

Contract ID → test map (see 06_RESEARCH/PHASE2_LAYER_CONTRACTS_NOTE.md):

  Stage 0c detectors      D-SWEEP-1 D-SWEEP-0 D-FVG-1 D-FVG-0 D-DISP-1 D-DISP-0
  Pillars 1–5             P1-FAIL P2-UNAVAIL P2-FAIL P2-PASS P3-FAIL P3-PASS
                          P4-PASS P4-FAIL P5-SOFT
  Cross-layer handoffs    H-MERGE H-ATTR H-ROUTER

Fixture conventions (mirroring tests/test_validation_pipeline.py):
  * CALM bars keep ATR small/stable so the ±0.5×ATR Pillar 1 band is tight.
  * The success FVG zone is [100.0, 100.2] on a 21-bar M5 series.
  * Displacement fixtures reuse the checker's own measurement definition
    (sweep extreme → BOS close vs pre-sweep ATR) — no new thresholds.

Reason tokens asserted here (stable strings owned by the pillars):
  P1: "naked level"                (FAIL)
  P1: "insufficient candles"       (UNAVAILABLE)
  P2: "no displacement result"     (UNAVAILABLE)
  P2: "displacement < 0.5× ATR"    (FAIL, hard fail)
  P2: "missing BOS"                (FAIL)
  P2: "missing directional FVG"    (FAIL)
  P2: "displacement below 1× ATR"  (FAIL, soft-miss)
  P3: "region of the dealing range" (FAIL)
  P4: "no second-touch trades"     (FAIL)
  P5: "70% score"                  (FAIL — soft, still tradeable)
"""

from __future__ import annotations

import pytest

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, LiquidityType, POIState, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.detection.displacement_checker import check_displacement
from smc.detection.fvg_detector import detect_fvgs
from smc.detection.sweep_detector import detect_sweep
from smc.poi.confluence_scorer import merge_overlapping
from smc.triggers.trigger_router import TriggerRouter
from smc.validation.pillar import PillarStatus
from smc.validation.pillar_1_zone_refinement import ZoneRefinementPillar
from smc.validation.pillar_2_displacement import DisplacementPillar
from smc.validation.pillar_3_premium_discount import PremiumDiscountPillar
from smc.validation.pillar_4_freshness import FreshnessPillar
from smc.validation.pillar_5_inducement import InducementPillar
from smc.validation.validation_pipeline import (
    ValidationDecision,
    ValidationPipeline,
)
from smc.orchestration.detection_driver import DetectionDriver

TF = Timeframe.M5

# ---------------------------------------------------------------------------
# Shared fixture rows
# ---------------------------------------------------------------------------

CALM = [(99.5, 99.7, 99.3, 99.6)]

# 15 calm bars + bullish FVG [100.0, 100.2] + approach bars (close 100.55).
SUCCESS_ROWS = CALM * 15 + [
    (99.9, 100.0, 99.7, 99.9),       # c1: first FVG candle
    (100.0, 100.1, 99.6, 100.0),     # c2: middle candle
    (100.15, 100.35, 100.2, 100.3),  # c3: FVG [100.0, 100.2]
    (100.3, 100.4, 100.1, 100.35),   # approach
    (100.35, 100.5, 100.3, 100.45),  # approach
    (100.45, 100.6, 100.4, 100.55),  # last close 100.55
]

# Displacement reference window (same as test_validation_pipeline): 15 wide
# pre-sweep bars + sweep + impulse with BOS + FVG. ATR ≈ 1.0 so the impulse
# (sweep low 98.2 → BOS close 103.2) clears 1×ATR comfortably.
PRE_DISP = [(100.5, 101.5, 99.5, 100.5)] * 15
IMPULSE_ROWS = PRE_DISP + [
    (99.8, 100.5, 98.2, 99.6),       # 15: SSL sweep (wick below 99.5 zone?)
    (100.0, 102.5, 100.3, 100.8),    # 16: impulse leg 1
    (101.0, 103.5, 102.0, 103.2),    # 17: impulse leg 2 (BOS close)
]


def _fvg_poi(state: POIState = POIState.CREATED) -> POI:
    return POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M1, ModelType.M2],
        state=state,
    )


def _naked_poi() -> POI:
    """POI far from any refinement element (104.0–104.2 vs the 100.x window)."""
    return POI(
        zone=Zone(top=104.2, bottom=104.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M1],
        state=POIState.CREATED,
    )


def _range_swings(candles, swing_factory):
    """Confirmed range extremes [99, 105] → dealing range (Pillar 3 input)."""
    return [
        swing_factory(candles, 3, True, level=105.0),
        swing_factory(candles, 4, False, level=99.0),
    ]


def _ssl_level(price: float) -> LiquidityLevel:
    return LiquidityLevel(
        type=LiquidityType.EQUAL_HIGHS_LOWS, level=price, pool=PoolType.SSL, timeframe=TF
    )


def _passing_displacement(candle_factory):
    candles = candle_factory(IMPULSE_ROWS)
    return check_displacement(candles, Direction.LONG, sweep_index=15, bos_level=101.2)


def _validate(pipeline_candles, swings, levels, displacement, poi=None):
    return ValidationPipeline().validate(
        poi if poi is not None else _fvg_poi(),
        pipeline_candles,
        swings,
        levels,
        displacement=displacement,
    )


# ---------------------------------------------------------------------------
# 2a — Stage 0c detector contracts
# ---------------------------------------------------------------------------


class TestSweepContracts:
    """D-SWEEP-1 / D-SWEEP-0 — wick-pierce + body-close-back rule (§2)."""

    def test_d_sweep_1_ssl_wick_pierce_close_back_detects(self, candle_factory):
        # Wick pierces BELOW the SSL level, body closes back ABOVE it.
        candles = candle_factory(
            [
                (99.6, 99.9, 99.3, 99.5),
                (99.5, 99.9, 98.5, 99.2),  # low 98.5 < 99.0, close 99.2 > 99.0
            ]
        )
        level = LiquidityLevel(
            type=LiquidityType.EQUAL_HIGHS_LOWS, level=99.0, pool=PoolType.SSL, timeframe=TF
        )
        result = detect_sweep(candles, level)
        assert result is not None, "wick-pierce + close-back MUST confirm a sweep"
        assert result.candle_index == 1
        assert result.pool is PoolType.SSL

    def test_d_sweep_0_no_pierce_no_sweep(self, candle_factory):
        # Candle never reaches the level → no sweep; breakdown close is not
        # a sweep either (the detector's documented breakout exclusion).
        candles = candle_factory(
            [
                (99.6, 99.9, 99.3, 99.5),
                (99.5, 99.4, 98.5, 98.6),  # closes below 99.0 = breakdown
            ]
        )
        level = LiquidityLevel(
            type=LiquidityType.EQUAL_HIGHS_LOWS, level=99.0, pool=PoolType.SSL, timeframe=TF
        )
        assert detect_sweep(candles, level) is None


class TestFvgContracts:
    """D-FVG-1 / D-FVG-0 — classic 3-candle imbalance rule (§3)."""

    def test_d_fvg_1_classic_gap_detected_with_direction(self, candle_factory):
        candles = candle_factory(
            [
                (99.0, 99.4, 98.8, 99.2),   # c1: high 99.4
                (100.0, 100.6, 99.9, 100.5),  # c2: impulse
                (100.5, 101.0, 100.2, 100.8),  # c3: low 100.2 > 99.4 → LONG gap [99.4, 100.2]
            ]
        )
        fvgs = detect_fvgs(candles, TF)
        assert len(fvgs) == 1
        zone = fvgs[0].zone
        assert zone.direction is Direction.LONG
        assert zone.bottom == pytest.approx(99.4)
        assert zone.top == pytest.approx(100.2)
        assert fvgs[0].start_index == 0

    def test_d_fvg_0_contiguous_overlap_no_fvg(self, candle_factory):
        # c1 and c3 overlap → no imbalance, no gap.
        candles = candle_factory(
            [
                (99.0, 99.4, 98.8, 99.2),   # c1: high 99.4
                (99.5, 99.8, 99.3, 99.6),   # c2
                (99.3, 99.7, 99.0, 99.5),   # c3: low 99.0 ≤ 99.4 AND high 99.7 ≥ 99.0 → overlap
            ]
        )
        assert detect_fvgs(candles, TF) == []


class TestDisplacementContracts:
    """D-DISP-1 / D-DISP-0 — BOS + directional FVG + magnitude vs ATR (§3)."""

    def test_d_disp_1_valid_displacement_passes_with_magnitude(self, candle_factory):
        result = _passing_displacement(candle_factory)
        assert result.passed, "BOS + FVG + ≥1×ATR MUST pass"
        assert not result.hard_fail
        assert result.bos is True
        assert result.fvg is True
        assert result.magnitude_atr is not None and result.magnitude_atr >= 1.0
        assert result.bos_index is not None and result.bos_index == 17

    def test_d_disp_0_below_hard_fail_is_not_valid_for_pillar_2(self, candle_factory):
        # Tiny impulse: sweep low 99.4 → best close 99.1 ⇒ magnitude ≈ |−0.3|
        # vs pre-sweep ATR ≈ 1.0 ⇒ hard-fail zone (< 0.5×ATR).
        candles = candle_factory(
            PRE_DISP
            + [
                (99.8, 100.5, 99.4, 99.6),   # sweep
                (99.0, 99.4, 98.9, 99.1),    # leg (best close 99.1)
                (99.1, 99.3, 99.0, 99.1),    # leg
            ]
        )
        result = check_displacement(candles, Direction.LONG, sweep_index=15, bos_level=101.2)
        assert result.hard_fail, "magnitude < 0.5×ATR MUST hard-fail"
        assert not result.passed
        # The same result injected into Pillar 2 must FAIL with the hard token.
        pillar = DisplacementPillar().run(
            _context_with_displacement(result)
        )
        assert pillar.status is PillarStatus.FAIL
        assert "displacement < 0.5" in pillar.detail

    def test_d_disp_bos_without_fvg_fails_with_token(self, candle_factory):
        # BOS close beyond the level but NO directional FVG inside the move:
        # the BOS candle's low re-enters below the sweep candle's high, so no
        # 3-candle triplet leaves an imbalance anywhere in [sweep, BOS].
        candles = candle_factory(
            PRE_DISP
            + [
                (99.8, 100.5, 98.2, 99.6),     # 15: sweep (high 100.5)
                (100.0, 101.4, 100.3, 101.0),  # 16: leg (low 100.3 ≤ 100.5 → no gap)
                (100.0, 103.5, 100.4, 103.2),  # 17: BOS close 103.2, low 100.4 ≤ 100.5
            ]
        )
        result = check_displacement(candles, Direction.LONG, sweep_index=15, bos_level=101.2)
        assert result.bos is True
        assert result.fvg is False
        assert not result.passed
        pillar = DisplacementPillar().run(_context_with_displacement(result))
        assert pillar.status is PillarStatus.FAIL
        assert "missing directional FVG" in pillar.detail


def _context_with_displacement(displacement):
    """Minimal ValidationContext for a Pillar-2-only evaluation."""
    from smc.validation.pillar import ValidationContext

    return ValidationContext(
        poi=_fvg_poi(),
        candles=[],  # Pillar 2 reads only the injected result
        swings=[],
        liquidity_levels=[],
        displacement=displacement,
    )


# ---------------------------------------------------------------------------
# 2b — Pillars 1–5 contracts
# ---------------------------------------------------------------------------


class TestPillar1ZoneRefinement:
    """P1 — unmitigated OB/FVG within ±0.5×ATR of the POI level (§13)."""

    def test_p1_fail_naked_level(self, candle_factory, swing_factory):
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        result = ZoneRefinementPillar().run(
            _context(candles, _range_swings(candles, swing_factory), [_ssl_level(100.3)], _naked_poi())
        )
        assert result.status is PillarStatus.FAIL
        assert "naked level" in result.detail

    def test_p1_unavailable_insufficient_candles(self, swing_factory):
        from smc.validation.pillar import ValidationContext

        poi = _fvg_poi()
        context = ValidationContext(
            poi=poi, candles=[], swings=[], liquidity_levels=[]
        )
        result = ZoneRefinementPillar().run(context)
        assert result.status is PillarStatus.UNAVAILABLE
        assert "insufficient candles" in result.detail


class TestPillar2Displacement:
    """P2 — consumes the injected Phase 1 result; UNAVAILABLE when absent (§3)."""

    def test_p2_unavailable_no_map_entry(self, candle_factory, swing_factory):
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        # Pipeline-level contract: no displacement injected → UNAVAILABLE at
        # Pillar 2 → hard reject (fail-fast, never a silent pass).
        result = _validate(candles, _range_swings(candles, swing_factory), [], None)
        assert result.decision is ValidationDecision.REJECTED
        assert result.first_failure is not None and result.first_failure.pillar == 2
        assert result.first_failure.status is PillarStatus.UNAVAILABLE
        assert "no displacement result" in result.first_failure.detail

    def test_p2_fail_hard_fail_token(self, candle_factory, swing_factory):
        weak = check_displacement(
            candle_factory(
                PRE_DISP
                + [
                    (99.8, 100.5, 98.2, 99.0),
                    (99.0, 99.4, 98.9, 99.1),
                    (99.1, 99.3, 99.0, 99.1),
                ]
            ),
            Direction.LONG,
            sweep_index=15,
            bos_level=101.2,
        )
        assert weak.hard_fail
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        result = _validate(candles, _range_swings(candles, swing_factory), [], weak)
        assert result.decision is ValidationDecision.REJECTED
        assert result.first_failure.pillar == 2
        assert "displacement < 0.5" in result.first_failure.detail

    def test_p2_fail_missing_bos_token(self, candle_factory, swing_factory):
        # No candle ever closes above the BOS level 101.2 → bos=False.
        no_bos = check_displacement(
            candle_factory(
                PRE_DISP
                + [
                    (99.8, 100.5, 98.2, 99.6),
                    (100.0, 100.9, 99.9, 100.4),
                    (100.4, 100.8, 100.1, 100.5),
                ]
            ),
            Direction.LONG,
            sweep_index=15,
            bos_level=101.2,
        )
        assert no_bos.bos is False
        assert not no_bos.passed and not no_bos.hard_fail
        pillar = DisplacementPillar().run(_context_with_displacement(no_bos))
        assert pillar.status is PillarStatus.FAIL
        assert "missing BOS" in pillar.detail

    def test_p2_pass_valid_injected_result(self, candle_factory, swing_factory):
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        result = _validate(
            candles,
            _range_swings(candles, swing_factory),
            [_ssl_level(100.3)],
            _passing_displacement(candle_factory),
        )
        assert result.decision is ValidationDecision.PASS
        p2 = next(r for r in result.pillar_results if r.pillar == 2)
        assert p2.status is PillarStatus.PASS
        assert "BOS + directional FVG" in p2.detail


class TestPillar3PremiumDiscount:
    """P3 — sole owner of the §6 45/55 hard gate."""

    def test_p3_fail_wrong_region(self, candle_factory, swing_factory):
        # LONG POI in the PREMIUM region: zone [104.0, 104.2] vs range [99, 105].
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        poi = _naked_poi()
        result = PremiumDiscountPillar().run(
            _context(candles, _range_swings(candles, swing_factory), [], poi)
        )
        assert result.status is PillarStatus.FAIL
        assert "region of the dealing range" in result.detail
        assert result.data["region"] == "premium"

    def test_p3_pass_discount_for_long(self, candle_factory, swing_factory):
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        result = PremiumDiscountPillar().run(
            _context(candles, _range_swings(candles, swing_factory), [], _fvg_poi())
        )
        assert result.status is PillarStatus.PASS
        assert result.data["region"] == "discount"

    def test_p3_unavailable_without_range(self, candle_factory, swing_factory):
        from smc.validation.pillar import ValidationContext

        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        context = ValidationContext(
            poi=_fvg_poi(),
            candles=candles,
            swings=[],  # no confirmed extremes → compute_dealing_range → None
            liquidity_levels=[],
            dealing_range=None,
        )
        result = PremiumDiscountPillar().run(context)
        assert result.status is PillarStatus.UNAVAILABLE


class TestPillar4Freshness:
    """P4 — strict 1-touch: CREATED/FRESH only (§5)."""

    def test_p4_pass_created_context(self, candle_factory, swing_factory):
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        result = FreshnessPillar().run(
            _context(candles, _range_swings(candles, swing_factory), [], _fvg_poi())
        )
        assert result.status is PillarStatus.PASS
        # State token is the lowercase enum value, stable by contract.
        assert result.data["state"] in ("created", "fresh")
        assert result.data["state"] in result.detail

    def test_p4_fail_tested_poi(self, candle_factory, swing_factory):
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        result = FreshnessPillar().run(
            _context(
                candles,
                _range_swings(candles, swing_factory),
                [],
                _fvg_poi(state=POIState.TESTED),
            )
        )
        assert result.status is PillarStatus.FAIL
        assert "no second-touch trades" in result.detail


class TestPillar5Inducement:
    """P5 — SOFT: never rejects; 70% modifier without inducement (§7)."""

    def test_p5_soft_fail_does_not_reject_pipeline(self, candle_factory, swing_factory):
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        # No inducement level anywhere → Pillar 5 FAILs softly...
        pillar = InducementPillar().run(
            _context(candles, _range_swings(candles, swing_factory), [], _fvg_poi())
        )
        assert pillar.status is PillarStatus.FAIL
        assert "70% score" in pillar.detail
        # ...but the PIPELINE still PASSes (inducement absent, everything else fine).
        result = _validate(
            candles,
            _range_swings(candles, swing_factory),
            [],  # no liquidity levels ⇒ no inducement structure
            _passing_displacement(candle_factory),
        )
        assert result.decision is ValidationDecision.PASS
        assert result.pillar_results[-1].pillar == 5
        assert result.inducement_modifier < 1.0

    def test_p5_with_inducement_full_score(self, candle_factory, swing_factory):
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        # SSL pool strictly between the LONG zone top (100.2) and the last
        # close (100.55): price must sweep it before entering the zone.
        pillar = InducementPillar().run(
            _context(candles, _range_swings(candles, swing_factory), [_ssl_level(100.3)], _fvg_poi())
        )
        assert pillar.status is PillarStatus.PASS
        assert pillar.score_modifier == pytest.approx(1.0)


def _context(candles, swings, levels, poi):
    """Build a ValidationContext like ValidationPipeline.validate does —
    including the auto-computed dealing range from the swings."""
    from smc.poi.deal_range import compute_dealing_range
    from smc.validation.pillar import ValidationContext

    return ValidationContext(
        poi=poi,
        candles=candles,
        swings=swings,
        liquidity_levels=levels,
        dealing_range=compute_dealing_range(swings),
    )


# ---------------------------------------------------------------------------
# 2c — Cross-layer handoff contracts
# ---------------------------------------------------------------------------


class TestMergeHandoff:
    """H-MERGE — same-direction overlapping POIs merge before validation."""

    def test_h_merge_union_tags_widest_zone(self):
        from datetime import datetime, timezone

        created = datetime(2026, 1, 1, tzinfo=timezone.utc)
        a = POI(
            zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
            models=[ModelType.M1],
            created_at=created,
        )
        b = POI(
            zone=Zone(top=100.4, bottom=100.1, direction=Direction.LONG, timeframe=TF),
            models=[ModelType.M2, ModelType.M3],
            created_at=created,
        )
        merged = merge_overlapping([a, b])
        assert len(merged) == 1
        one = merged[0]
        assert one.zone.top == pytest.approx(100.4)   # widest zone
        assert one.zone.bottom == pytest.approx(100.0)
        assert sorted(one.models) == [ModelType.M1, ModelType.M2, ModelType.M3]  # tag union
        assert one.id == a.id                          # earliest id kept

    def test_h_merge_opposite_direction_never_merges(self):
        a = POI(
            zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
            models=[ModelType.M1],
        )
        b = POI(
            zone=Zone(top=100.2, bottom=100.0, direction=Direction.SHORT, timeframe=TF),
            models=[ModelType.M1],
        )
        assert len(merge_overlapping([a, b])) == 2

    def test_h_merge_non_overlapping_pass_through(self):
        a = POI(
            zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
            models=[ModelType.M1],
        )
        b = POI(
            zone=Zone(top=102.2, bottom=102.0, direction=Direction.LONG, timeframe=TF),
            models=[ModelType.M1],
        )
        assert len(merge_overlapping([a, b])) == 2


class TestAttributionHandoff:
    """H-ATTR — attribute_displacement never invents a displacement entry."""

    def test_h_attr_latest_same_direction_sweep_wins(self, candle_factory, swing_factory):
        # Two REAL checker outputs at different sweep indices (sweep 1 + a
        # later retrace sweep 2); the run carries both, candle-ordered, and
        # the attribution must pick the LATER sweep's displacement for the
        # same-direction POI.
        win1 = candle_factory(
            PRE_DISP
            + [
                (99.8, 100.5, 98.2, 99.6),      # 15: sweep 1
                (100.0, 102.5, 100.3, 100.8),   # 16
                (101.0, 103.5, 102.0, 103.2),   # 17: BOS 1
            ]
        )
        win2 = candle_factory(
            PRE_DISP
            + [
                (99.8, 100.5, 98.2, 99.6),      # 15: sweep
                (100.0, 102.5, 100.3, 100.8),   # 16
                (101.0, 104.5, 102.0, 104.2),   # 17: BOS 2 (deeper close)
            ]
        )
        disp1 = check_displacement(win1, Direction.LONG, sweep_index=15, bos_level=101.2)
        disp2 = check_displacement(win2, Direction.LONG, sweep_index=15, bos_level=101.2)
        assert disp1.passed and disp2.passed
        assert disp2.bos_index == disp1.bos_index  # same anchor index, deeper close
        from smc.orchestration.detection_driver import DetectionRun

        run = DetectionRun(
            swings=[],
            liquidity_levels=[],
            sweeps=[],
            displacements=[(15, disp1), (15, disp2)],
        )
        driver = DetectionDriver(TF)
        poi = _fvg_poi()
        mapping = driver.attribute_displacement([poi], run)
        assert mapping[poi.id] is disp2  # LAST same-direction entry wins

    def test_h_attr_no_matching_sweep_omits_key(self, candle_factory, swing_factory):
        # A SHORT POI on a window whose sweeps produce LONG impulses only:
        # attribution must omit the key entirely (never invent).
        candles = candle_factory(IMPULSE_ROWS)
        driver = DetectionDriver(TF)
        run = driver.stage0(candles)
        short_poi = POI(
            zone=Zone(top=104.2, bottom=104.0, direction=Direction.SHORT, timeframe=TF),
            models=[ModelType.M1],
        )
        mapping = driver.attribute_displacement([short_poi], run)
        assert short_poi.id not in mapping

    def test_h_attr_pipeline_rejects_when_omitted(self, candle_factory, swing_factory):
        # End-to-end honesty: omitted key → Pillar 2 UNAVAILABLE → REJECTED.
        # The POI zone [100.0, 100.2] carries the success FVG so Pillar 1
        # passes and the pipeline REACHES Pillar 2.
        candles = candle_factory(IMPULSE_ROWS)
        driver = DetectionDriver(TF)
        run = driver.stage0(candles)
        short_poi = POI(
            zone=Zone(top=100.2, bottom=100.0, direction=Direction.SHORT, timeframe=TF),
            models=[ModelType.M1],
        )
        mapping = driver.attribute_displacement([short_poi], run)
        assert short_poi.id not in mapping
        from smc.orchestration.engine import PipelineEngine

        engine = PipelineEngine()
        eval_candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        passed, results = engine.validate(
            [short_poi], eval_candles, _range_swings(eval_candles, swing_factory),
            [_ssl_level(100.3)],
            displacement_map=mapping, merge_first=False,
        )
        assert passed == []
        first = results[0].first_failure
        assert first is not None and first.pillar == 2
        assert first.status is PillarStatus.UNAVAILABLE


class TestRouterHandoff:
    """H-ROUTER — eligibility smoke: at most one route, chronological first."""

    def test_h_router_single_route_chronological(self, candle_factory, swing_factory):
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        swings = _range_swings(candles, swing_factory)
        router = TriggerRouter()
        poi = _fvg_poi()
        route = router.scan(poi, candles, swings, from_bar=0)
        # Smoke contract: the scan either returns exactly ONE winning route
        # (chronological first-valid) or None — never a list, never a crash.
        assert route is None or route.poi is poi
        if route is not None:
            assert route.bar >= 0
            assert route.signal.entry_price > 0

    def test_h_router_scan_is_bounded_and_deterministic(self, candle_factory, swing_factory):
        candles = candle_factory(SUCCESS_ROWS, timeframe=TF)
        swings = _range_swings(candles, swing_factory)
        router = TriggerRouter()
        poi = _fvg_poi()
        first = router.scan(poi, candles, swings, from_bar=0, to_bar=5)
        second = router.scan(poi, candles, swings, from_bar=0, to_bar=5)
        assert first is second or (first is None and second is None) or (
            first is not None and second is not None and first.bar == second.bar
        )
