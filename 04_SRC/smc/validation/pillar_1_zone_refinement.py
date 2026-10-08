"""Pillar 1 — Zone Refinement (§13, R1 §6 Pillar 1).

An unmitigated Order Block or Fair Value Gap must exist within the frozen
±0.5× ATR band of the POI's structural level. A level with no refinement
element is a "naked level" — HARD FAIL.

V1 rules (documented):
* Structural level = the POI zone midpoint; the band is
  ``level ± ZONE_REFINEMENT_ATR (0.5) × ATR`` on the POI detection series.
* Refinement candidates = FVG zones (Phase 1 detector) and the OB = the
  candle immediately before the first candle of each FVG (R1 §3.1), zone =
  that candle's full wick range.
* A candidate is MITIGATED (excluded) once price closes beyond its opposite
  extreme after formation: a demand zone (LONG) closes below its bottom, a
  supply zone (SHORT) closes above its top. Only unmitigated candidates
  refine.
* UNAVAILABLE when there is not enough data to detect FVGs or to compute
  the reference ATR.
"""

from __future__ import annotations

from smc.config.locked_constants import ZONE_REFINEMENT_ATR
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.detection.fvg_detector import detect_fvgs
from smc.poi.base_model import zone_for_candle
from smc.utils.atr import latest_atr
from smc.validation.pillar import Pillar, PillarResult, PillarStatus, ValidationContext

__all__ = ["ZoneRefinementPillar"]


class ZoneRefinementPillar(Pillar):
    """§13 OB/FVG refinement check (±0.5× ATR of the POI level)."""

    number = 1
    name = "zone_refinement"

    def run(self, context: ValidationContext) -> PillarResult:
        candles = context.candles
        poi = context.poi
        if len(candles) < 3:
            return PillarResult(
                pillar=self.number,
                name=self.name,
                status=PillarStatus.UNAVAILABLE,
                detail="insufficient candles to detect FVG/OB candidates",
            )
        atr = latest_atr(candles, context.atr_period)
        if atr is None:
            return PillarResult(
                pillar=self.number,
                name=self.name,
                status=PillarStatus.UNAVAILABLE,
                detail="insufficient history to compute the reference ATR",
            )

        half = ZONE_REFINEMENT_ATR * atr
        level = poi.zone.midpoint
        band_lo, band_hi = level - half, level + half
        # Phase C perf: per-window shared artifacts (identical values to
        # the per-POI recomputations — see ``window_cache.WindowCache``).
        cache = context.window_cache
        fvgs = cache.fvgs if cache is not None and cache.fvgs is not None else detect_fvgs(candles, poi.zone.timeframe)
        min_close_suffix = cache.min_close_suffix if cache is not None else None
        max_close_suffix = cache.max_close_suffix if cache is not None else None

        found: list[str] = []
        for fvg in fvgs:
            active = fvg.start_index + 2  # third candle of the triplet (R1 §3.1)
            if not _mitigated(
                fvg.zone, candles, active,
                min_close_suffix=min_close_suffix, max_close_suffix=max_close_suffix,
            ) and _overlaps_band(
                fvg.zone.top, fvg.zone.bottom, band_lo, band_hi
            ):
                found.append("fvg")
            ob_index = fvg.start_index - 1
            if ob_index < 0:
                continue
            ob = candles[ob_index]
            ob_zone = zone_for_candle(ob, fvg.zone.direction, poi.zone.timeframe)
            if not _mitigated(
                ob_zone, candles, ob_index,
                min_close_suffix=min_close_suffix, max_close_suffix=max_close_suffix,
            ) and _overlaps_band(
                ob_zone.top, ob_zone.bottom, band_lo, band_hi
            ):
                found.append("ob")

        if found:
            kinds = sorted(set(found))
            return PillarResult(
                pillar=self.number,
                name=self.name,
                status=PillarStatus.PASS,
                detail=f"unmitigated refinement present: {', '.join(kinds)}",
                data={"band": (band_lo, band_hi), "atr": atr, "refinements": kinds},
            )
        return PillarResult(
            pillar=self.number,
            name=self.name,
            status=PillarStatus.FAIL,
            detail="naked level: no unmitigated OB/FVG within ±0.5× ATR",
            data={"band": (band_lo, band_hi), "atr": atr, "refinements": []},
        )


def _overlaps_band(
    zone_top: float, zone_bottom: float, band_lo: float, band_hi: float
) -> bool:
    """True when a zone [bottom, top] intersects the level band."""
    return zone_top >= band_lo and zone_bottom <= band_hi


def _mitigated(
    zone,
    candles: list[Candle],
    active_index: int,
    *,
    min_close_suffix: list[float] | None = None,
    max_close_suffix: list[float] | None = None,
) -> bool:
    """True when price closed beyond the zone's opposite extreme after it formed.

    Demand (LONG) zones are mitigated by a close below the zone bottom;
    supply (SHORT) zones by a close above the zone top. With the window's
    close-suffix arrays supplied, the per-candidate re-scan becomes two
    O(1) reads over the SAME comparison set (see ``window_cache``).
    """
    if zone.direction is Direction.LONG:
        if min_close_suffix is not None:
            return min_close_suffix[active_index + 1] < zone.bottom
        return any(
            candle.close < zone.bottom for candle in candles[active_index + 1 :]
        )
    if max_close_suffix is not None:
        return max_close_suffix[active_index + 1] > zone.top
    return any(
        candle.close > zone.top for candle in candles[active_index + 1 :]
    )
