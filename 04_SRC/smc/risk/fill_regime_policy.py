"""FR fill-regime policy (Lead Architect rulings R7 + R8, 2026-09-22).

Single source for the two fill-regime rules; imported by the backtest
runner/order book and the paper runner — no copy-paste policy.

* **R7 — place guard.** At place time, if the MARKET mid/reference price
  (bar close in both engine paths) sits outside the routed POI zone by
  more than the EXISTING FR-3 band (``ZONE_REFINEMENT_ATR × ATR`` — no
  new tolerance constant), the order is NOT placed. The MARKET is the
  tested quantity, not the limit: post-FR-3.1 every limit is zone-
  anchored by construction, so a limit-vs-zone check would be vacuous —
  the September 2025 runaway class is identified by the market having
  left the zone at signal time. The geometry is deliberately identical
  in spirit to ``smc.triggers.base_trigger.entry_within_zone`` (same
  frozen multiplier, same inclusive bounds) — R7 re-checks the placement
  pipeline, it does not widen or re-implement the gate.
* **R8 — HTF-aware resting bars.** Pending-limit lifetime in runner bars
  (§23 ``bars_open`` convention: the placement bar counts as the first
  open bar): H1-detected POIs rest 36 bars, H4/M8/D1-detected 48 bars,
  everything else keeps the frozen §23 default for the execution
  timeframe (12 on M5). M8 is a tag, not a timeframe — it wins over the
  detection timeframe by ruling.

Safe defaults (documented, deliberately):

* ``zone_place_allowed`` FAILS CLOSED when the zone is locatable and the
  price is provably outside the band; it is DORMANT (allows) when ATR is
  missing/non-positive (the band cannot be computed — never invented) and
  when the zone bounds are missing (M3-seam candidates carry no zone;
  R7 by ruling guards ROUTED POI placements, and the pipeline bridge
  always supplies zone bounds). Inverted/non-finite bounds also fail
  closed — unlocatable geometry is never placed.
* ``rest_bars_for`` falls back to the EXECUTION timeframe's frozen §23
  default (give-up backstop as last resort) for unknown/None timeframes
  — never raises, and never shortens the execution timeframe's own
  default (M5 run → 12, M1 run → 30).

Both helpers are pure functions — no clock, no MT5, no engine state.
"""

from __future__ import annotations

import math

from smc.config.locked_constants import ZONE_REFINEMENT_ATR
from smc.config.timeframe import Timeframe
from smc.triggers.trigger_expiry import poi_give_up_bars
from smc.validation.state_machine import expiry_bars_for

__all__ = ["zone_place_allowed", "rest_bars_for", "give_up_backstop_bars",
           "market_reentered_zone", "R8_REST_BARS_H1", "R8_REST_BARS_HTF",
           "SKIP_PLACE_FAR_FROM_ZONE", "INTENT_EXPIRED_NO_REENTRY"]

# R8 table (runner-bar units, §23 bars_open convention).
R8_REST_BARS_H1 = 36
R8_REST_BARS_HTF = 48  # H4 / M8 / D1

# Machine-readable skip reason for the R7 guard (blocked/skip logs).
SKIP_PLACE_FAR_FROM_ZONE = "skip_place_far_from_zone"

# Machine-readable terminal event for an R9 place-intent whose clock ran
# out with no re-entry (no order was ever placed; one-shot never consumed).
INTENT_EXPIRED_NO_REENTRY = "intent_expired_no_reentry"


def market_reentered_zone(direction, zone_low, zone_high, limit_price,
                          close, atr, bar=None) -> bool:
    """R9: True when the market re-enters an armed place-intent's zone.

    Two trigger paths, exactly the blueprint's "enters band (or touches
    limit)":

    * **band re-entry** — the EXISTING R7 guard
      (``zone_place_allowed``: the bar's CLOSE within the frozen
      ``ZONE_REFINEMENT_ATR × ATR`` band of the POI zone, same dormancy
      and fail-closed rules, same per-bar ATR source);
    * **limit touch** — the locked fill-model touch rule (LONG:
      ``bar.low <= limit``; SHORT: ``bar.high >= limit``; inclusive)
      evaluated on the bar's RANGE. Mirrored inline to keep this module
      dependency-free; a unit test cross-checks it against
      ``smc.backtest.fill_model.limit_filled`` so the two never drift.

    ``close`` is the market reference for the band (bar close in both
    engine paths); ``bar`` carries the range for the touch (None →
    touch path disabled). Zone bounds missing → band check only (R9
    intents are only armed when the zone was locatable — defensive
    fallback).
    """
    if zone_place_allowed(direction, zone_low, zone_high, close, atr):
        return True  # band re-entry
    if limit_price is None or bar is None:
        return False  # no limit to touch / no bar range to test
    try:
        limit = float(limit_price)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(limit):
        return False
    low = getattr(bar, "low", None)
    high = getattr(bar, "high", None)
    if low is None or high is None:
        return False
    from smc.core.enums import Direction as _Direction
    if direction is _Direction.LONG:
        return bool(float(low) <= limit)
    if direction is _Direction.SHORT:
        return bool(float(high) >= limit)
    return False


def zone_place_allowed(direction, zone_low, zone_high, price, atr) -> bool:
    """R7: True when the MARKET may place a limit for this POI zone.

    ``price`` is the market mid/reference price AT PLACE TIME (the bar
    close in both engine paths) — NOT the order limit: after FR-3.1 the
    limit is always zone-anchored, so the runaway signal is the MARKET
    having left the zone (the September 2025 class: 54–162 units away at
    signal time), not the order geometry. Direction is accepted for
    call-site clarity and future symmetry; the band is direction-
    symmetric (same frozen ``ZONE_REFINEMENT_ATR`` multiplier on both
    sides — exactly the ``entry_within_zone`` bounds).
    """
    if zone_low is None or zone_high is None:
        return True  # no zone on the candidate (M3 seam) -> R7 dormant
    try:
        bottom = float(zone_low)
        top = float(zone_high)
    except (TypeError, ValueError):
        return False  # unlocatable zone -> fail closed
    if not (math.isfinite(bottom) and math.isfinite(top)) or not top >= bottom:
        return False  # non-finite / inverted zone -> fail closed
    if price is None:
        return False  # zone known, price unknown -> cannot verify -> fail closed
    try:
        entry = float(price)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(entry):
        return False  # NaN/inf price is unlocatable -> fail closed
    if atr is None:
        return True  # band undefined (never invented) -> R7 dormant
    try:
        atr_value = float(atr)
    except (TypeError, ValueError):
        return True
    if not atr_value > 0:
        return True  # degenerate ATR -> R7 dormant (matches gate's v25 note)
    tol = ZONE_REFINEMENT_ATR * atr_value
    return bottom - tol <= entry <= top + tol


def rest_bars_for(detection_tf, is_m8: bool = False,
                  execution_tf: "Timeframe | None" = Timeframe.M5) -> int:
    """R8: pending-order rest bars for one order's detection provenance.

    ``detection_tf`` accepts a ``Timeframe`` or any int-convertible value
    (MT5-style enum ints); ``None``/unknown falls back to the execution
    timeframe's frozen §23 default (give-up backstop as last resort) —
    the default branch NEVER shortens the lifetime the execution
    timeframe already grants (M5 run → 12, M1 run → 30). ``is_m8`` wins
    over the detection timeframe per ruling.
    """
    if is_m8:
        return R8_REST_BARS_HTF
    tf = None
    if isinstance(detection_tf, Timeframe):
        tf = detection_tf
    elif detection_tf is not None:
        try:
            tf = Timeframe(int(detection_tf))
        except (TypeError, ValueError):
            tf = None
    if tf in (Timeframe.H4, Timeframe.D1):
        return R8_REST_BARS_HTF
    if tf is Timeframe.H1:
        return R8_REST_BARS_H1
    default = expiry_bars_for(execution_tf if execution_tf is not None
                              else Timeframe.M5)
    return default if default is not None else poi_give_up_bars()


def give_up_backstop_bars(detection_tf=None, is_m8: bool = False) -> int:
    """Give-up backstop for one order: never below the R8 rest bars.

    The §24 V1 backstop (20 bars) stays a HARD ceiling only for default
    lifetimes; an R8-extended order must not be silently shortened by the
    backstop, so the effective backstop is ``max(20, rest_bars)``.
    """
    return max(poi_give_up_bars(), rest_bars_for(detection_tf, is_m8))
