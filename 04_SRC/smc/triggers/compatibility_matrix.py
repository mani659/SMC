"""POI × Trigger compatibility matrix (LOCKED_DECISIONS §15 / R1 §8 — frozen).

The frozen matrix grades every (model, trigger) cell as structurally
compatible (✓), possible-but-uncommon (○), or — for Model 8 × Ending
Diagonal — the PREFERRED pairing (✓★). The locked KEY defines no
incompatible cell, so every cell is ALLOWED; the grade carries routing
weight only as a deterministic tie-break when two triggers complete on the
same bar (chronological order is §12-frozen; equal-bar ties are not defined
by the locked docs, V1 tie-break below).

R1 §11 "highest priority model wins" for overlapping POIs is superseded by
the §1 equal-tag architecture (Phase 2 audit): POIs carry model TAGS, and a
trigger is eligible when it is compatible with ANY of the POI's tags.
"""

from __future__ import annotations

from enum import Enum

from smc.config.model_type import ModelType
from smc.core.enums import TriggerType

__all__ = [
    "CompatibilityGrade",
    "CompatibilityMatrix",
    "DEFAULT_MATRIX",
]

_GRADES = {
    #                     A          B          C          D          E          F
    ModelType.M1: {TriggerType.A_CHOCH: "structural", TriggerType.B_LEADING_DIAGONAL: "structural", TriggerType.C_ENDING_DIAGONAL: "structural", TriggerType.D_TWO_BAR_REVERSAL: "structural", TriggerType.E_RSI_DIVERGENCE: "structural", TriggerType.F_BOS_OB: "structural"},
    ModelType.M2: {TriggerType.A_CHOCH: "structural", TriggerType.B_LEADING_DIAGONAL: "uncommon", TriggerType.C_ENDING_DIAGONAL: "uncommon", TriggerType.D_TWO_BAR_REVERSAL: "structural", TriggerType.E_RSI_DIVERGENCE: "structural", TriggerType.F_BOS_OB: "structural"},
    ModelType.M3: {TriggerType.A_CHOCH: "structural", TriggerType.B_LEADING_DIAGONAL: "uncommon", TriggerType.C_ENDING_DIAGONAL: "uncommon", TriggerType.D_TWO_BAR_REVERSAL: "structural", TriggerType.E_RSI_DIVERGENCE: "structural", TriggerType.F_BOS_OB: "structural"},
    ModelType.M4: {TriggerType.A_CHOCH: "structural", TriggerType.B_LEADING_DIAGONAL: "uncommon", TriggerType.C_ENDING_DIAGONAL: "structural", TriggerType.D_TWO_BAR_REVERSAL: "structural", TriggerType.E_RSI_DIVERGENCE: "structural", TriggerType.F_BOS_OB: "uncommon"},
    ModelType.M5: {TriggerType.A_CHOCH: "structural", TriggerType.B_LEADING_DIAGONAL: "uncommon", TriggerType.C_ENDING_DIAGONAL: "uncommon", TriggerType.D_TWO_BAR_REVERSAL: "structural", TriggerType.E_RSI_DIVERGENCE: "structural", TriggerType.F_BOS_OB: "structural"},
    ModelType.M6: {TriggerType.A_CHOCH: "structural", TriggerType.B_LEADING_DIAGONAL: "uncommon", TriggerType.C_ENDING_DIAGONAL: "uncommon", TriggerType.D_TWO_BAR_REVERSAL: "structural", TriggerType.E_RSI_DIVERGENCE: "structural", TriggerType.F_BOS_OB: "structural"},
    ModelType.M7: {TriggerType.A_CHOCH: "structural", TriggerType.B_LEADING_DIAGONAL: "uncommon", TriggerType.C_ENDING_DIAGONAL: "uncommon", TriggerType.D_TWO_BAR_REVERSAL: "structural", TriggerType.E_RSI_DIVERGENCE: "structural", TriggerType.F_BOS_OB: "structural"},
    ModelType.M8: {TriggerType.A_CHOCH: "structural", TriggerType.B_LEADING_DIAGONAL: "structural", TriggerType.C_ENDING_DIAGONAL: "preferred", TriggerType.D_TWO_BAR_REVERSAL: "structural", TriggerType.E_RSI_DIVERGENCE: "structural", TriggerType.F_BOS_OB: "structural"},
}

# ✓★ Model 8 × Ending Diagonal — the expert's primary setup (frozen).
_PREFERRED = {(ModelType.M8, TriggerType.C_ENDING_DIAGONAL)}


class CompatibilityGrade(Enum):
    """§15 grade of one (model, trigger) cell."""

    UNCOMMON = 1    # ○ — possible but uncommon / less natural pairing
    STRUCTURAL = 2  # ✓ — structurally compatible
    PREFERRED = 3   # ✓★ — structural AND the expert's preferred pairing

    @property
    def is_preferred(self) -> bool:
        return self is CompatibilityGrade.PREFERRED

    @property
    def allowed(self) -> bool:
        """True when the pair may fire (all frozen cells are allowed)."""
        return True


_BY_NAME = {
    "uncommon": CompatibilityGrade.UNCOMMON,
    "structural": CompatibilityGrade.STRUCTURAL,
    "preferred": CompatibilityGrade.PREFERRED,
}


class CompatibilityMatrix:
    """Lookup over the frozen §15 table.

    Immutable by convention: instantiate once (``DEFAULT_MATRIX``) and reuse.
    """

    def __init__(self, grades: dict | None = None) -> None:
        source = grades if grades is not None else _GRADES
        self._grades: dict[tuple[ModelType, TriggerType], CompatibilityGrade] = {}
        for model, row in source.items():
            for trigger, name in row.items():
                grade = _BY_NAME[name]
                if (model, trigger) in _PREFERRED:
                    grade = CompatibilityGrade.PREFERRED
                self._grades[(model, trigger)] = grade

    def grade(self, model: ModelType, trigger: TriggerType) -> CompatibilityGrade:
        """Compatibility grade for one (model, trigger) cell."""
        return self._grades.get(
            (model, trigger), CompatibilityGrade.UNCOMMON
        )

    def eligible_triggers(
        self, models: list[ModelType]
    ) -> list[TriggerType]:
        """All triggers eligible for a POI carrying ``models``.

        A trigger is eligible when it is compatible with ANY tag (equal-tag
        architecture, §1). Result is sorted by (grade rank desc, letter) —
        grade rank is the V1 equal-bar tie-break; within an EQUAL grade the
        EARLIER letter wins (A before F, pinned post-audit) and is listed
        first.``TriggerRouter.evaluate_at`` applies the same (grade, letter)
        ordering, so the two stay aligned for same-bar ties.
        """
        if not models:
            return []
        by_grade: dict[CompatibilityGrade, list[TriggerType]] = {}
        for model in models:
            for trigger in TriggerType:
                grade = self.grade(model, trigger)
                by_grade.setdefault(grade, [])
                if trigger not in by_grade[grade]:
                    by_grade[grade].append(trigger)
        ordered: list[TriggerType] = []
        for grade in sorted(by_grade, key=lambda g: g.value, reverse=True):
            ordered.extend(sorted(by_grade[grade], key=lambda t: t.value))
        return ordered


DEFAULT_MATRIX = CompatibilityMatrix()
