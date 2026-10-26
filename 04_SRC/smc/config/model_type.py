"""ModelType enum — the 8 equal POI tags (LOCKED_DECISIONS §1).

All 8 models are equal tags on the same price level; there is NO ranking.
The more independent models that tag a level, the higher the quality score.
"""

from __future__ import annotations

from enum import IntEnum

__all__ = ["ModelType", "MODEL_DESCRIPTIONS"]


class ModelType(IntEnum):
    """The eight modular POI model tags (M1–M8)."""

    M1 = 1
    M2 = 2
    M3 = 3
    M4 = 4
    M5 = 5
    M6 = 6
    M7 = 7
    M8 = 8


MODEL_DESCRIPTIONS: dict[ModelType, str] = {
    ModelType.M1: "Origin Demand/Supply Base",
    ModelType.M2: "RBS/SBR Breaker",
    ModelType.M3: "CHOCH Retest",
    ModelType.M4: "Quasimodo (QML)",
    ModelType.M5: "Extreme Equal Highs / Supply Origin",
    ModelType.M6: "Neckline / Double Top-Bottom",
    ModelType.M7: "Equal Resistance Shelf",
    ModelType.M8: "HTF Demand/Supply (D1/H4)",
}