"""Abstract POI model base + shared detection geometry helpers.

Model contract (DEVELOPMENT_PLAN Phase 2):

    detect(self, candles, swings, liquidity_levels) -> list[POI]

Detection semantics (V1, documented): a model evaluates the window given
to it and emits the most recent qualifying setup per side. Window slicing
(lookback) is the CALLER's responsibility — the model never invents a
lookback. Candles are assumed chronological UTC.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.core.zone import Zone
from smc.detection.fvg_detector import detect_fvgs
from smc.utils.atr import latest_atr

__all__ = [
    "POIModel",
    "zone_for_candle",
    "zone_for_swing",
    "zone_for_level",
    "first_close_beyond",
    "has_directional_fvg_after",
    "atr_up_to",
    "most_recent_swing",
    "level_band_half_width",
]

# --------------------------------------------------------------------------- #
# Geometry helpers (pure functions shared by the model detectors)
# --------------------------------------------------------------------------- #
DEFAULT_ATR_PERIOD = 14  # indicator parameter (matches smc.utils.atr default)


def zone_for_candle(candle: Candle, direction: Direction, timeframe: Timeframe) -> Zone:
    """Full wick zone of one candle."""
    return Zone(
        top=max(candle.high, candle.low),
        bottom=min(candle.high, candle.low),
        direction=direction,
        timeframe=timeframe,
    )


def level_band_half_width(candles: list[Candle], up_to: int, atr_period: int) -> float:
    """V1 zone half-width for bare levels: ZONE_REFINEMENT_ATR (0.5) x ATR.

    Reuses the FROZEN §13 multiplier (0.5× ATR) as the half-width so no new
    number is invented; flagged as an UNFROZEN-V1 geometry choice (see
    report/ambiguities) rather than a locked constant. Falls back to 0.0
    when there is not enough history to compute ATR.
    """
    from smc.config.locked_constants import ZONE_REFINEMENT_ATR

    atr = atr_up_to(candles, up_to, atr_period)
    return ZONE_REFINEMENT_ATR * atr if atr is not None else 0.0


def zone_for_level(
    level: float,
    direction: Direction,
    timeframe: Timeframe,
    candles: list[Candle],
    up_to: int,
    atr_period: int = DEFAULT_ATR_PERIOD,
) -> Zone:
    """Thin zone around a bare price level: level ± 0.5×ATR (V1 geometry)."""
    half = level_band_half_width(candles, up_to, atr_period)
    return Zone(
        top=level + half,
        bottom=level - half,
        direction=direction,
        timeframe=timeframe,
    )


def zone_for_swing(
    swing: Swing,
    direction: Direction,
    timeframe: Timeframe,
    candles: list[Candle],
    atr_period: int = DEFAULT_ATR_PERIOD,
) -> Zone:
    """Zone for a structural swing: its base candle's full range when the
    swing level falls inside that candle, otherwise a thin ±0.5×ATR band."""
    candle = swing.base_candle
    if candle.low <= swing.level <= candle.high:
        return zone_for_candle(candle, direction, timeframe)
    return zone_for_level(
        swing.level, direction, timeframe, candles, swing.candle_index, atr_period
    )


def first_close_beyond(
    candles: list[Candle],
    start: int,
    level: float,
    above: bool,
) -> int | None:
    """Index of the first candle (>= start) closing beyond ``level``."""
    for index in range(start, len(candles)):
        close = candles[index].close
        if (close > level) if above else (close < level):
            return index
    return None


def atr_up_to(candles: list[Candle], index: int, atr_period: int) -> float | None:
    """Pre-bar ATR: Wilder ATR over candles strictly before ``index``."""
    if index <= 0:
        return None
    return latest_atr(candles[:index], atr_period)


def has_directional_fvg_after(
    candles: list[Candle],
    start: int,
    direction: Direction,
    timeframe: Timeframe,
) -> bool:
    """True when a FVG of ``direction`` starts at/after ``start``."""
    return any(
        fvg.start_index >= start and fvg.zone.direction is direction
        for fvg in detect_fvgs(candles, timeframe)
    )


def most_recent_swing(
    swings: list[Swing],
    is_high: bool,
    before_index: int | None = None,
) -> Swing | None:
    """Most recent swing of one side (optionally strictly before an index)."""
    candidates = [s for s in swings if s.is_high == is_high]
    if before_index is not None:
        candidates = [s for s in candidates if s.candle_index < before_index]
    return max(candidates, key=lambda s: s.candle_index, default=None)


# --------------------------------------------------------------------------- #
# Abstract model
# --------------------------------------------------------------------------- #
class POIModel(ABC):
    """Base class for all 8 POI models (§1 — equal tags, never suppressed).

    Subclasses implement :meth:`detect` and declare their ModelType tag.
    Models are instantiated per detection timeframe; §4's per-timeframe
    guidance is advisory (registry/caller routes accordingly).
    """

    tag: ModelType
    supported_timeframes: tuple[Timeframe, ...] = tuple(Timeframe)

    def __init__(self, timeframe: Timeframe, atr_period: int = DEFAULT_ATR_PERIOD) -> None:
        self.timeframe = timeframe
        self.atr_period = atr_period

    @abstractmethod
    def detect(
        self,
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
    ) -> list[POI]:
        """Detect qualifying POIs on the supplied window.

        Parameters mirror DEVELOPMENT_PLAN Phase 2. The window is
        caller-supplied; models emit only setups whose geometry completes
        inside it (most recent qualifying setup per direction).
        """
        raise NotImplementedError

    def _new_poi(self, zone: Zone) -> POI:
        return POI(zone=zone, models=[self.tag], state=POIState.CREATED)