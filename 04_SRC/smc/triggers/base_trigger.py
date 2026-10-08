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
from typing import TYPE_CHECKING

from smc.config.locked_constants import ZONE_REFINEMENT_ATR
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.utils.atr import latest_atr

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from smc.backtest.series_state import SeriesState
else:
    from smc.backtest.series_state import SeriesState

__all__ = ["Trigger", "TriggerContext", "TriggerSignal", "atr_band_half_width",
           "structural_sl", "context_atr", "entry_within_zone",
           "zone_anchored_entry",
           "FR2_SL_BUFFER_ATR", "FR2_TP_ATR_MULTIPLE"]

DEFAULT_ATR_PERIOD = 14  # indicator parameter (matches smc.utils.atr)

# FR-2 interim numbers per FOUNDATION_RESET_PLAN R4/R5 pending formal § lock.
# These are NOT frozen locked constants: do not import them as such, do not
# tune them against backtests, and list them in the FR-2 note for a future
# formal lock ruling.
FR2_SL_BUFFER_ATR = 0.3   # structural stop buffer beyond the reference extreme
FR2_TP_ATR_MULTIPLE = 4.0  # fallback take-profit distance when no structural target exists


def atr_band_half_width(
    candles: list[Candle],
    up_to: int,
    atr_period: int = DEFAULT_ATR_PERIOD,
    *,
    atr_values: list | None = None,
) -> float:
    """V1 zone-context band half-width: ZONE_REFINEMENT_ATR (0.5) x ATR.

    Used by triggers C/E/F to accept a structural extreme "at the POI zone".
    Reuses the FROZEN §13 multiplier so no new number is invented (same
    UNFROZEN-V1 note as ``poi.base_model.level_band_half_width``); falls
    back to 0.0 when ATR history is insufficient.

    ``atr_values`` (Phase C perf): the caller's full-prefix Wilder ATR
    series — Wilder-fold identity makes ``atr_values[up_to - 1]`` exactly
    ``latest_atr(candles[:up_to])``, so an indexed read replaces the O(n)
    rebuild. When no series is supplied (or ``up_to`` is out of range) the
    legacy in-place computation runs.
    """
    if up_to <= 0:
        return 0.0
    if atr_values is not None and up_to <= len(atr_values):
        atr = atr_values[up_to - 1]
        return ZONE_REFINEMENT_ATR * atr if atr is not None else 0.0
    atr = latest_atr(candles[:up_to], atr_period)
    return ZONE_REFINEMENT_ATR * atr if atr is not None else 0.0


def context_atr(context: "TriggerContext", bar: int,
                atr_period: int = DEFAULT_ATR_PERIOD) -> float | None:
    """Wilder ATR through ``bar`` over the honest candle prefix.

    Prefers the caller's incremental ``hints.atr_values`` fold
    (``values[bar]`` is exactly ``latest_atr(candles[:bar + 1])`` by fold
    identity); falls back to a direct prefix computation. Returns None
    when history is insufficient — callers treat None as no-buffer /
    no-target (never invent volatility).
    """
    values = getattr(getattr(context, "hints", None), "atr_values", None)
    if values is not None and 0 <= bar < len(values):
        return values[bar]
    candles = getattr(context, "candles", None)
    if not candles or bar < 0:
        return None
    return latest_atr(candles[:bar + 1], atr_period)


def structural_sl(reference_price: float, direction: Direction,
                  atr: float | None,
                  buffer_atr: float = FR2_SL_BUFFER_ATR) -> float:
    """Stop beyond a structural reference by ``buffer_atr`` × ATR (R5).

    LONG stops sit below the reference, SHORT stops above it. A missing
    or non-positive ATR returns the reference unchanged (guarded fallback —
    the zero-buffer raw edge persists only when volatility is unknowable,
    never by silent default where ATR exists).
    """
    if atr is None or not atr > 0:
        return reference_price
    buffer = buffer_atr * atr
    if direction is Direction.LONG:
        return reference_price - buffer
    return reference_price + buffer


def entry_within_zone(entry_price: float, zone,
                      atr: float | None,
                      tol_mult: float = ZONE_REFINEMENT_ATR) -> bool:
    """True when a routed entry belongs to its POI thesis zone (FR-3).

    Bounds are ``[zone.bottom - tol, zone.top + tol]`` with
    ``tol = tol_mult × ATR`` (default the frozen §13 refinement
    tolerance — no new number). With unknowable ATR the tolerance is 0
    (strict containment). Zone bounds are read duck-typed; a missing or
    inverted zone returns False (never route on unlocatable geometry).
    """
    try:
        bottom = float(getattr(zone, "bottom", None))
        top = float(getattr(zone, "top", None))
        entry = float(entry_price)
    except (TypeError, ValueError):
        return False
    if not top >= bottom:
        return False
    tol = tol_mult * atr if atr is not None and atr > 0 else 0.0
    return bottom - tol <= entry <= top + tol


def zone_anchored_entry(direction: Direction, zone_low: float,
                        zone_high: float, reference_price: float) -> float:
    """FR-3.1: anchor a trigger's limit entry INTO its routed POI zone.

    Direction-aware PROXIMAL anchoring (the edge the retracement reaches
    first): LONG demand-style entries anchor to the zone HIGH, SHORT
    supply-style entries to the zone LOW. An on-zone reference passes
    through bit-exactly (pre-FR-3.1 on-zone behavior is unchanged); an
    off-zone reference re-anchors to the direction's proximal edge so an
    HTF thesis routes onto its own zone instead of being silently rejected
    off-zone. The symmetric deep shapes (reference beyond the far edge)
    cannot occur for a live POI — price would have crossed the zone to get
    there, terminating it (§5 touch) before any trigger scan — and anchor
    to the proximal edge safely; the trigger's own reachability guard
    rejects them.

    Pure containment geometry — the FR-3 §13 tolerance band is NOT applied
    here (widening the entry set with it is explicitly banned; the gate
    stays the last line of defense). An inverted or NaN (unlocatable) zone
    returns the reference unchanged so the FR-3 gate — not the anchor — is
    what rejects it.
    """
    try:
        low = float(zone_low)
        high = float(zone_high)
        reference = float(reference_price)
    except (TypeError, ValueError):
        return reference_price
    if not high >= low:  # inverted or NaN bounds -> unlocatable geometry
        return reference_price
    if low <= reference <= high:
        return reference
    return high if direction is Direction.LONG else low


@dataclass(slots=True)
class TriggerContext:
    """Everything one trigger evaluation may read for a single bar.

    ``candles`` is the execution-timeframe series UP TO AND INCLUDING the
    current bar (``bar_index``); triggers only report signals whose entry
    condition completes at or after ``from_bar`` (the bar the POI was
    validated/armed on) so a trigger cannot pre-date its own POI.
    ``swings`` are the §27 structural swings detected on the same series
    (the router/engine supplies them; may be ``[]`` for micro-triggers).

    ``hints`` (Phase C perf, duck-typed, optional): the caller's
    incremental full-prefix artifacts — ATR/RSI series in both price
    spaces (Wilder folds: the ``[:up_to]`` tail IS the prefix-slice
    value), the mirrored candles/swings (every mirrored read is index- or
    suffix-bounded, so mirror evaluations are slice-identical), and
    base-sorted swing indexes (bisect answers over the SAME selections
    the linear scans produce). ``None`` keeps the legacy in-place path.
    The individual fields are read defensively (getattr), so any hint
    carrier works.
    """

    poi: POI
    candles: list[Candle]
    swings: list[Swing]
    bar_index: int = -1  # default: last candle
    from_bar: int = 0    # first bar the trigger may fire on (arm bar)
    execution_timeframe: Timeframe = Timeframe.M5
    hints: "SeriesState | None" = None

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
