"""Phase 4 — POI × Trigger compatibility matrix tests (§15 / R1 §8)."""

from smc.config.model_type import ModelType
from smc.core.enums import TriggerType
from smc.triggers.compatibility_matrix import (
    DEFAULT_MATRIX,
    CompatibilityGrade,
)


def test_model8_ending_diagonal_is_preferred():
    assert (
        DEFAULT_MATRIX.grade(ModelType.M8, TriggerType.C_ENDING_DIAGONAL)
        is CompatibilityGrade.PREFERRED
    )


def test_model4_bos_ob_is_uncommon():
    assert (
        DEFAULT_MATRIX.grade(ModelType.M4, TriggerType.F_BOS_OB)
        is CompatibilityGrade.UNCOMMON
    )


def test_model1_all_triggers_structural():
    for trigger in TriggerType:
        assert (
            DEFAULT_MATRIX.grade(ModelType.M1, trigger)
            is CompatibilityGrade.STRUCTURAL
        )


def test_all_frozen_cells_allowed():
    for model in ModelType:
        for trigger in TriggerType:
            assert DEFAULT_MATRIX.grade(model, trigger).allowed


def test_eligible_ordering_preferred_first_for_m8():
    eligible = DEFAULT_MATRIX.eligible_triggers([ModelType.M8])
    assert eligible[0] is TriggerType.C_ENDING_DIAGONAL  # ✓★ preferred
    assert set(eligible) == set(TriggerType)


def test_eligible_uses_any_tag_union():
    # M4: C is structural, F is uncommon — union still contains everything,
    # but letter ordering within equal grade keeps A first for M4.
    eligible = DEFAULT_MATRIX.eligible_triggers([ModelType.M4])
    assert set(eligible) == set(TriggerType)
    assert eligible.index(TriggerType.A_CHOCH) < eligible.index(TriggerType.F_BOS_OB)
