"""Phase 3 — Pillar 4 (Freshness): strict 1-touch state gate (§5).

CREATED and FRESH are tradeable; TESTED (already touched) and VIOLATED
(closed beyond without a touch) are terminal and rejected on validation.
Per-bar touch/expiry transitions are owned by ``POIStateMachine`` (see
``test_state_machine.py``).
"""

from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, POIState
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.validation.pillar import PillarStatus, ValidationContext
from smc.validation.pillar_4_freshness import FreshnessPillar

TF = Timeframe.M5


def _poi(state: POIState) -> POI:
    return POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
        models=[],
        state=state,
    )


def _run(state: POIState):
    ctx = ValidationContext(poi=_poi(state), candles=[], swings=[], liquidity_levels=[])
    return FreshnessPillar().run(ctx)


def test_created_passes():
    result = _run(POIState.CREATED)
    assert result.status is PillarStatus.PASS
    assert result.data["state"] == "created"


def test_fresh_passes():
    result = _run(POIState.FRESH)
    assert result.status is PillarStatus.PASS


def test_tested_fails():
    result = _run(POIState.TESTED)
    assert result.status is PillarStatus.FAIL
    assert "second-touch" in result.detail


def test_violated_fails():
    result = _run(POIState.VIOLATED)
    assert result.status is PillarStatus.FAIL
