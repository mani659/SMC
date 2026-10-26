"""Phase 2 — Model registry: ModelType <-> POIModel mapping."""

import pytest

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.poi.model_registry import ModelRegistry, build_registry


def test_build_registry_registers_all_eight_models():
    registry = build_registry(Timeframe.M15)
    assert len(registry.all()) == 8
    assert registry.tags() == [
        ModelType.M1,
        ModelType.M2,
        ModelType.M3,
        ModelType.M4,
        ModelType.M5,
        ModelType.M6,
        ModelType.M7,
        ModelType.M8,
    ]


def test_registry_get_and_contains():
    registry = build_registry(Timeframe.M15)
    model = registry.get(ModelType.M1)
    assert model.tag is ModelType.M1
    assert model.timeframe is Timeframe.M15
    assert ModelType.M8 in registry


def test_registry_duplicate_register_raises():
    registry = ModelRegistry()
    first = build_registry(Timeframe.M15).get(ModelType.M2)
    registry.register(first)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(first)


def test_registry_unregistered_get_raises_keyerror():
    registry = ModelRegistry()
    with pytest.raises(KeyError):
        registry.get(ModelType.M3)


def test_m8_registers_without_htf_candles():
    """M8 must register even when no HTF series are supplied (emits nothing)."""
    registry = build_registry(Timeframe.M30)
    m8 = registry.get(ModelType.M8)
    assert m8.detect([], [], []) == []
