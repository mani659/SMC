"""Model registry — maps ModelType to POIModel instances.

Registry pattern per DEVELOPMENT_PLAN Phase 2: each model is registered
under its ``ModelType`` tag and can be looked up by the validation /
trigger / pipeline layers. Registry construction is idempotent per tag
(registering the same tag twice raises).
"""

from __future__ import annotations

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.poi.base_model import POIModel

__all__ = ["ModelRegistry", "build_registry"]


class ModelRegistry:
    """Holds exactly one model instance per ModelType tag."""

    def __init__(self) -> None:
        self._models: dict[ModelType, POIModel] = {}

    def register(self, model: POIModel) -> None:
        """Register a model under its ``tag``."""
        if model.tag in self._models:
            raise ValueError(f"Model {model.tag.name} is already registered")
        self._models[model.tag] = model

    def get(self, model_type: ModelType) -> POIModel:
        """Return the registered model for a tag (raises KeyError if absent)."""
        if model_type not in self._models:
            raise KeyError(f"No model registered for {model_type.name}")
        return self._models[model_type]

    def __contains__(self, model_type: ModelType) -> bool:
        return model_type in self._models

    def all(self) -> list[POIModel]:
        """All registered models in tag order."""
        return [self._models[tag] for tag in sorted(self._models)]

    def tags(self) -> list[ModelType]:
        return [m.tag for m in self.all()]


def build_registry(
    timeframe: Timeframe,
    htf_candles: dict[Timeframe, list] | None = None,
    atr_period: int = 14,
) -> ModelRegistry:
    """Instantiate and register all eight POI models (M1–M8).

    Parameters
    ----------
    timeframe:
        Detection timeframe used for Models 1–7.
    htf_candles:
        Optional ``{Timeframe: candles}`` map of D1/H4 series consumed by
        Model 8 (required for M8 to emit HTF zones; M8 registers either way).
    atr_period:
        Shared ATR indicator period for zone sizing / displacement checks.
    """
    from smc.poi.models.m1_origin_base import M1OriginBase
    from smc.poi.models.m2_rbs_sbr_breaker import M2RbsSbrBreaker
    from smc.poi.models.m3_choch_retest import M3ChochRetest
    from smc.poi.models.m4_quasimodo import M4Quasimodo
    from smc.poi.models.m5_extreme_equal_highs import M5ExtremeEqualHighs
    from smc.poi.models.m6_neckline_retest import M6NecklineRetest
    from smc.poi.models.m7_equal_resistance import M7EqualResistance
    from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply

    registry = ModelRegistry()
    registry.register(M1OriginBase(timeframe, atr_period=atr_period))
    registry.register(M2RbsSbrBreaker(timeframe, atr_period=atr_period))
    registry.register(M3ChochRetest(timeframe, atr_period=atr_period))
    registry.register(M4Quasimodo(timeframe, atr_period=atr_period))
    registry.register(M5ExtremeEqualHighs(timeframe, atr_period=atr_period))
    registry.register(M6NecklineRetest(timeframe, atr_period=atr_period))
    registry.register(M7EqualResistance(timeframe, atr_period=atr_period))
    registry.register(
        M8HtfDemandSupply(timeframe, htf_candles=htf_candles, atr_period=atr_period)
    )
    return registry