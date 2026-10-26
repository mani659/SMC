"""Pillar 4 — Freshness (§5, R1 §6 Pillar 4).

Strict 1-touch only: a validated POI must be untouched (CREATED or FRESH).
A POI already TESTED (touched once) or VIOLATED (closed beyond without a
touch) is rejected — no second-touch trades.

V1 BOUNDARY (documented): freshness is evaluated from the POI's §5 state,
which is owned by ``smc.validation.state_machine.POIStateMachine``. The
machine flips states as bars arrive (first touch → TESTED, close-beyond →
VIOLATED, unfilled-order expiry → TESTED after the frozen M5=12 / M1=30
bars). At validation time the zone has not been touched *since creation* by
definition, so this pillar gates on state rather than re-scanning candles —
the historical scan equivalent is the state the machine has already
accumulated for a re-validated POI.
"""

from __future__ import annotations

from smc.core.enums import POIState
from smc.validation.pillar import Pillar, PillarResult, PillarStatus, ValidationContext

__all__ = ["FreshnessPillar"]


class FreshnessPillar(Pillar):
    """§5 1-touch freshness gate (CREATED/FRESH only)."""

    number = 4
    name = "freshness"

    def run(self, context: ValidationContext) -> PillarResult:
        state = context.poi.state
        if state in (POIState.CREATED, POIState.FRESH):
            return PillarResult(
                pillar=self.number,
                name=self.name,
                status=PillarStatus.PASS,
                detail=f"POI is {state.value} (strict 1-touch rule)",
                data={"state": state.value},
            )
        return PillarResult(
            pillar=self.number,
            name=self.name,
            status=PillarStatus.FAIL,
            detail=(
                f"POI already {state.value} — no second-touch trades "
                "(strict 1-touch rule)"
            ),
            data={"state": state.value},
        )
