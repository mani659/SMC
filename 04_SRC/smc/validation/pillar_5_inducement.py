"""Pillar 5 — Inducement (§7, R1 §6 Pillar 5).

SOFT PILLAR ONLY — never a hard reject. A visible inducement structure in
front of the POI scores 100% (INDUCEMENT_WITH_SCORE); without one the POI
scores 70% (INDUCEMENT_WITHOUT_SCORE) and remains tradeable.

V1 DETECTION (documented, deterministic — no invented thresholds):
an inducement structure for a LONG POI is any sell-side (SSL) liquidity
pool — an equal-lows level or an UNCONFIRMED (``is_valid=False``) minor
swing low — sitting strictly BETWEEN the zone boundary facing the approach
(the zone TOP) and the last close: price must travel through it before
entering the demand zone. SHORT POIs mirror with buy-side (BSL) pools
strictly between the last close and the zone BOTTOM. Structures inside the
zone body are the POI itself, not inducement. Trendline inducement is not
machine-testable from OHLCV in V1 and is not detected (it only ever costs
the 0.7 modifier, never a rejection).
"""

from __future__ import annotations

from smc.config.locked_constants import (
    INDUCEMENT_WITHOUT_SCORE,
    INDUCEMENT_WITH_SCORE,
)
from smc.core.enums import Direction, LiquidityType, PoolType
from smc.validation.pillar import Pillar, PillarResult, PillarStatus, ValidationContext

__all__ = ["InducementPillar"]


class InducementPillar(Pillar):
    """§7 soft inducement scoring: INDUCEMENT_WITH_SCORE with inducement,
    INDUCEMENT_WITHOUT_SCORE without (frozen ``locked_constants`` values)."""

    number = 5
    name = "inducement"

    def run(self, context: ValidationContext) -> PillarResult:
        if not context.candles:
            return PillarResult(
                pillar=self.number,
                name=self.name,
                status=PillarStatus.UNAVAILABLE,
                detail="no candles to locate inducement relative to price",
            )
        last_close = context.candles[-1].close
        zone = context.poi.zone
        direction = zone.direction

        if direction is Direction.LONG:
            lo, hi = zone.top, last_close  # approach side = above the zone
            want_pool = PoolType.SSL
        else:
            lo, hi = last_close, zone.bottom  # approach side = below the zone
            want_pool = PoolType.BSL

        found = self._levels_between(context, want_pool, lo, hi, direction)
        if found:
            kinds = sorted({kind for kind, _ in found})
            return PillarResult(
                pillar=self.number,
                name=self.name,
                status=PillarStatus.PASS,
                detail=f"inducement present: {', '.join(kinds)}",
                score_modifier=INDUCEMENT_WITH_SCORE,
                data={"kinds": kinds, "levels": [lv for _, lv in found]},
            )
        return PillarResult(
            pillar=self.number,
            name=self.name,
            status=PillarStatus.FAIL,
            detail=(
                "no inducement in front of POI — soft only: 70% score, "
                "still tradeable"
            ),
            score_modifier=INDUCEMENT_WITHOUT_SCORE,
            data={"kinds": [], "levels": []},
        )

    # ------------------------------------------------------------------ #
    def _levels_between(
        self,
        context: ValidationContext,
        pool: PoolType,
        lo: float,
        hi: float,
        direction: Direction,
    ) -> list[tuple[str, float]]:
        """SSL/BSL levels strictly inside (lo, hi) from Phase 1 outputs."""
        found: list[tuple[str, float]] = []
        last_index = len(context.candles) - 1

        for level in context.liquidity_levels:
            if level.pool is not pool or not (lo < level.level < hi):
                continue
            if level.type is LiquidityType.EQUAL_HIGHS_LOWS:
                kind = "equal_lows" if pool is PoolType.SSL else "equal_highs"
            else:
                kind = "liquidity_pool"
            found.append((kind, level.level))
        # Unconfirmed minor swing of the inducement polarity (§7: minor swing).
        is_high = direction is Direction.SHORT  # SHORT wants BSL = minor swing high
        for swing in context.swings:
            if (
                swing.is_high == is_high
                and not swing.is_valid
                and swing.candle_index < last_index
                and lo < swing.level < hi
            ):
                kind = "minor_swing_high" if is_high else "minor_swing_low"
                found.append((kind, swing.level))
        return found
