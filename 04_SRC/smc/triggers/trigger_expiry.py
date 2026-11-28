"""Trigger validity / expiry (LOCKED_DECISIONS §23 + §24 — frozen).

Two expiry regimes coexist:

1. §24 — trigger validity windows. Each trigger may only fire inside its
   frozen window:

       A – CHOCH Reversal ..... 20 M5 bars          (TRIGGER_A_EXPIRY)
       B – Leading Diagonal ... 30 bars after Wave 5 (TRIGGER_B_EXPIRY)
       C – Ending Diagonal .... sweep candle + 3     (TRIGGER_C_EXPIRY_EXTRA)
       D – Two-Bar Reversal ... bar immediately following (TRIGGER_D_EXPIRY)
       E – RSI Divergence ..... 15 bars after pattern (TRIGGER_E_EXPIRY)
       F – BOS + OB ........... first touch only     (TRIGGER_F_EXPIRY)

   ``window_bars_for`` maps trigger → bars-from-anchor. The engine counts
   these from each signal's ``completion_index`` (its own anchor).

2. §23 — unfilled ORDER expiry (M5 = 12 / M1 = 30 bars) — already owned by
   ``smc.validation.state_machine.POIStateMachine.expire_unfilled``; once a
   limit order rests unfilled past its bars the POI goes STATE_TESTED.

C — knowability anchor (amendment C1, 2026-11-28). C's window above is
counted from the diagonal's terminal, but a terminal is a §27 structural
swing: it does not EXIST as data until ``N(tf)`` bars after its fractal. On
the product DAY tier (D1 → H1, ``N_BAR_HTF = 5``) the 3-bar window therefore
closed before the pattern could ever be seen. ``ending_diagonal_anchor``
moves the clock start to the first bar the terminal is observable, keeping
the frozen 3 bars of life: legal bars are ``anchor … anchor + 3``. No
constant changes; the design is ``06_RESEARCH/BRANCH_C_DESIGN_LOCK.md``.

POI-level give-up window (V1, documented): Trigger A is compatible with
every model (§15 all ✓) and its §24 window (20 M5 bars) is the only row
anchored without a pattern reference, so the engine uses it as the POI-wide
\"no trigger fired → STATE_TESTED\" deadline measured from the arm bar
(flowchart STAGE 3 rule). Other triggers' windows are anchored to their own
pattern completions and can only shorten that horizon.
"""

from __future__ import annotations

from smc.config.locked_constants import (
    TRIGGER_A_EXPIRY,
    TRIGGER_B_EXPIRY,
    TRIGGER_C_EXPIRY_EXTRA,
    TRIGGER_D_EXPIRY,
    TRIGGER_E_EXPIRY,
    TRIGGER_F_EXPIRY,
)
from smc.config.timeframe import Timeframe
from smc.core.enums import TriggerType

__all__ = [
    "window_bars_for",
    "poi_give_up_bars",
    "signal_expired",
    "ending_diagonal_anchor",
]


def window_bars_for(trigger: TriggerType) -> int:
    """§24 validity bars for one trigger, counted from its own anchor."""
    return {
        TriggerType.A_CHOCH: TRIGGER_A_EXPIRY,
        TriggerType.B_LEADING_DIAGONAL: TRIGGER_B_EXPIRY,
        TriggerType.C_ENDING_DIAGONAL: TRIGGER_C_EXPIRY_EXTRA,
        TriggerType.D_TWO_BAR_REVERSAL: TRIGGER_D_EXPIRY,
        TriggerType.E_RSI_DIVERGENCE: TRIGGER_E_EXPIRY,
        TriggerType.F_BOS_OB: TRIGGER_F_EXPIRY,
    }[trigger]


def poi_give_up_bars() -> int:
    """POI-wide \"no trigger fired\" deadline in bars from the arm bar (V1).

    Uses Trigger A's frozen 20-M5-bar window (§24) because A is compatible
    with every model (§15) and its window is the only pattern-free anchor.
    """
    return TRIGGER_A_EXPIRY


def ending_diagonal_anchor(terminal_index: int, timeframe: Timeframe) -> int:
    """First bar Trigger C's terminal swing is observable (amendment C1).

    ``detect_swings`` reports a fractal only once ``N`` bars to its right
exist (§27), so a diagonal terminal cannot be known before
``candle_index + N(timeframe)``. The frozen ``TRIGGER_C_EXPIRY_EXTRA``
then runs from THAT bar instead of from the terminal candle.

    ``timeframe`` is the CONFIRMATION series the swings were detected on
    (``Swing.timeframe``), never ``TriggerContext.execution_timeframe`` —
    the router does not populate the latter, so it stays ``M5`` even when
    the series is H1 and ``N`` must be 5, not 3.

    Conservative by construction: the §18 base candle of a swing low may
    sit one bar before the fractal, so the anchor can be up to one bar
    early — it can only shorten C's life, never lengthen it.
    """
    return terminal_index + Timeframe.n_bar_confirmation(timeframe)


def signal_expired(signal_completion_index: int, expiry_bars: int, current_bar: int) -> bool:
    """True when a signal's §24 window has elapsed by ``current_bar``.

    The window covers the completion bar itself plus ``expiry_bars`` bars
    after it: a signal completing at bar N with 1 bar of validity is still
    live at bar N+1 and dead from bar N+2.
    """
    return current_bar > signal_completion_index + expiry_bars
