"""Phase 5 — same-level SL re-entry guard (v25_DIAG v23 "Same-SL Block",
ported to Python).

LOCKED_DECISIONS §28.3: block a new entry when the new stop-loss would sit
within ``SAME_LEVEL_GUARD_ATR`` (0.15) × ATR of the LAST closed trade's SL
level, and fewer than ``SAME_LEVEL_GUARD_COOLDOWN_BARS`` (4) bars have
passed since that close.

v25_DIAG semantics preserved verbatim:

* the guard records the SL level + bar index of every closed trade
  (``g_lastSLLevel`` / ``g_lastSLCloseBar`` in v25);
* the entry gate computes ``bars_since_close = current_bar - last_sl_close_bar``
  and only blocks while that is BELOW the cooldown (``< InpSameSLCooldown``);
* within the cooldown, a candidate is blocked when
  ``abs(new_sl - last_sl_level) <= SAME_LEVEL_GUARD_ATR × atr``;
* with no recorded SL (``last_sl_level <= 0``) or zero ATR the gate passes
  (v25 requires ``g_lastSLLevel > 0.0 && g_atr > 0.0``).

The guard is PURE state over injected scalars — no MT5 dependency, fully
unit-testable with synthetic state (:class:`SameLevelGuardState` may be
injected for replay).
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.config.locked_constants import (
    SAME_LEVEL_GUARD_ATR,
    SAME_LEVEL_GUARD_COOLDOWN_BARS,
)

__all__ = ["SameLevelGuard", "SameLevelGuardState"]


@dataclass(slots=True)
class SameLevelGuardState:
    """Synthetic state of one same-level guard (replayable / unit-testable)."""

    last_sl_level: float = 0.0      # SL of the last closed trade (0 = none)
    last_sl_close_bar: int = 0      # bar index of that close


class SameLevelGuard:
    """Same-SL re-entry guard (LOCKED_DECISIONS §28.3).

    Thresholds are imported from ``locked_constants`` — zero hardcoding.
    """

    def __init__(
        self,
        *,
        zone_atr: float = SAME_LEVEL_GUARD_ATR,
        cooldown_bars: int = SAME_LEVEL_GUARD_COOLDOWN_BARS,
        state: SameLevelGuardState | None = None,
    ) -> None:
        self.zone_atr = zone_atr
        self.cooldown_bars = cooldown_bars
        self._state = state if state is not None else SameLevelGuardState()

    @property
    def state(self) -> SameLevelGuardState:
        """Read-only handle on the guard's synthetic state."""
        return self._state

    # ------------------------------------------------------------------ #
    # Trade-close recording
    # ------------------------------------------------------------------ #
    def record_close(self, sl_level: float, bar_index: int) -> None:
        """Record the SL level + close bar of a closed trade (any exit)."""
        self._state.last_sl_level = sl_level
        self._state.last_sl_close_bar = bar_index

    def reset(self) -> None:
        """Clear the recorded SL reference (v25 daily rollover resets
        ``g_lastSLLevel`` on a new day)."""
        self._state.last_sl_level = 0.0
        self._state.last_sl_close_bar = 0

    # ------------------------------------------------------------------ #
    # Entry gate
    # ------------------------------------------------------------------ #
    def is_blocked(self, new_sl: float, atr: float, current_bar: int) -> bool:
        """True when a new entry at ``new_sl`` is blocked by the guard.

        Requires a recorded SL level and positive ATR; blocks only when the
        cooldown has not elapsed AND the new SL is within
        ``zone_atr × atr`` of the last SL level.
        """
        if self._state.last_sl_level <= 0.0 or atr <= 0.0:
            return False
        bars_since_close = current_bar - self._state.last_sl_close_bar
        if bars_since_close >= self.cooldown_bars:
            return False
        sl_distance = abs(new_sl - self._state.last_sl_level)
        return sl_distance <= self.zone_atr * atr