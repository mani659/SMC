"""Trigger contract + shared signal/context types (Phase 4, LOCKED §12/§22–§24).

An LTF trigger converts a validated (FRESH) POI plus execution-timeframe
price structure into ONE entry signal. Trigger selection is FROZEN (§12):
chronological — the first trigger whose entry condition completes is the
one that fires; there is no priority hierarchy. R1 §11 event identity: one
validated POI + one LTF trigger + one execution.

Every trigger is a LIMIT entry (Trigger D is frozen at 50% of the engulfing
body, LOCKED §10; Model 8 entry is a limit within the HTF zone, R1 §7) —
no trigger emits a market order.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from smc.config.locked_constants import ZONE_REFINEMENT_ATR
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.utils.atr import latest_atr

__all__ = ["Trigger", "TriggerContext", "TriggerSignal", "atr_band_half_width"]

DEFAULT_ATR_PERIOD = 14  # indicator parameter (matches smc.utils.atr)


def atr_band_half_width(
    candles: list[Candle], up_to: int, atr_period: int = DEFAULT_ATR_PERIOD
) -> float:
    """V1 zone-context band half-width: ZONE_REFINEMENT_ATR (0.5) x ATR.

    Used by triggers C/E/F to accept a structural extreme "at the POI zone".
    Reuses the FROZEN §13 multiplier so no new number is invented (same
    UNFROZEN-V1 note as ``poi.base_model.level_band_half_width``); falls
    back to 0.0 when ATR history is insufficient.
    """
    if up_to <= 0:
        return 0.0
    atr = latest_atr(candles[:up_to], atr_period)
    return ZONE_REFINEMENT_ATR * atr if atr is not None else 0.0


@dataclass(slots=True)
class TriggerContext:
    """Everything one trigger evaluation may read for a single bar.

    ``candles`` is the execution-timeframe series UP TO AND INCLUDING the
    current bar (``bar_index``); triggers only report signals whose entry
    condition completes at or after ``from_bar`` (the bar the POI was
    validated/armed on) so a trigger cannot pre-date its own POI.
    ``swings`` are the §27 structural swings detected on the same series
    (the router/engine supplies them; may be ``[]`` for micro-triggers).
    """

    poi: POI
    candles: list[Candle]
    swings: list[Swing]
    bar_index: int = -1  # default: last candle
    from_bar: int = 0    # first bar the trigger may fire on (arm bar)
    execution_timeframe: Timeframe = Timeframe.M5

    @property
    def current_bar(self) -> int:
        """The anchored evaluation bar."""
        return len(self.candles) - 1 if self.bar_index < 0 else self.bar_index


@dataclass(frozen=True, slots=True)
class TriggerSignal:
    """One completed LTF trigger: an entry limit + stop reference.

    ``completion_index`` is the candle where the trigger's pattern/entry
    condition completed (the router's chronology key). ``expiry_bars`` is
    the frozen §24 validity window counted from that index (see
    ``smc.triggers.trigger_expiry`` for the anchor semantics per trigger).
    ``entry_price`` is the resting limit price; ``stop_reference`` is the
    geometric stop level from the frozen spec (beyond the sweep/pattern
    extreme, below Wave 1 origin, beyond the OB distal edge, ...).
    """

    trigger: TriggerType
    direction: Direction
    entry_price: float
    stop_reference: float
    completion_index: int
    expiry_bars: int
    detail: str = ""
    data: dict = field(default_factory=dict)


class Trigger(ABC):
    """Abstract base for the six LTF triggers A–F.

    Subclasses declare their ``type`` and implement :meth:`evaluate`,
    returning a signal ONLY when their full entry condition completes at the
    context's current bar (so a chronological scan sees every signal exactly
    once, at its completion bar). Instances are stateless.
    """

    type: TriggerType

    @abstractmethod
    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        """Return the trigger signal completed at the current bar, else None."""
        raise NotImplementedError
