"""Pillar 2 — Displacement (§3, R1 §6 Pillar 2).

A validated POI needs a real impulsive move behind it: BOS (body close
beyond the prior swing extreme) + a directional FVG + magnitude ≥ 1× ATR.
A move below 0.5× ATR is a HARD FAIL (§3).

REUSE DECISION (documented): this pillar CONSUMES the Phase 1
``smc.detection.displacement_checker.check_displacement`` result supplied
in the context rather than re-deriving a sweep/BOS level from raw candles —
the POI detectors and orchestrator already know the sweep candle and prior
swing level, so re-computing blindly here would only introduce ambiguity.
When no displacement result is supplied the pillar is UNAVAILABLE (not a
silent pass).
"""

from __future__ import annotations

from smc.validation.pillar import Pillar, PillarResult, PillarStatus, ValidationContext

__all__ = ["DisplacementPillar"]


class DisplacementPillar(Pillar):
    """§3 displacement gate: BOS + FVG + magnitude ≥ 1× ATR (reuses Phase 1)."""

    number = 2
    name = "displacement"

    def run(self, context: ValidationContext) -> PillarResult:
        displacement = context.displacement
        if displacement is None:
            return PillarResult(
                pillar=self.number,
                name=self.name,
                status=PillarStatus.UNAVAILABLE,
                detail=(
                    "no displacement result supplied — pass a Phase 1 "
                    "check_displacement(...) output in the context"
                ),
            )

        data = {
            "direction": displacement.direction.value,
            "bos": displacement.bos,
            "fvg": displacement.fvg,
            "magnitude": displacement.magnitude,
            "magnitude_atr": displacement.magnitude_atr,
            "atr": displacement.atr,
            "is_preferred": displacement.is_preferred,
        }
        if displacement.passed and not displacement.hard_fail:
            return PillarResult(
                pillar=self.number,
                name=self.name,
                status=PillarStatus.PASS,
                detail="BOS + directional FVG + magnitude >= 1× ATR",
                data=data,
            )
        if displacement.hard_fail:
            reason = "displacement < 0.5× ATR (hard fail)"
        elif not displacement.bos:
            reason = "missing BOS (no body close beyond the prior swing)"
        elif not displacement.fvg:
            reason = "missing directional FVG"
        else:
            reason = "displacement below 1× ATR"
        return PillarResult(
            pillar=self.number,
            name=self.name,
            status=PillarStatus.FAIL,
            detail=reason,
            data=data,
        )
