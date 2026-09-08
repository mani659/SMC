"""Timeframe enum — values match MetaTrader5 ``TIMEFRAME_*`` constants.

The integer values are identical to the MetaTrader5 Python package's
``TIMEFRAME_*`` constants (M1=1 … D1=16408), so an ``int(tf)`` cast is a
valid MT5 timeframe and no mapping table is needed in ``smc/data``.
"""

from __future__ import annotations

from enum import IntEnum

__all__ = ["Timeframe"]


class Timeframe(IntEnum):
    """The seven locked detection/execution timeframes (LOCKED_DECISIONS §4/§27)."""

    M1 = 1
    M5 = 5
    M15 = 15
    M30 = 30
    H1 = 16385
    H4 = 16388
    D1 = 16408

    @property
    def minutes(self) -> int:
        """Nominal duration of one bar in minutes."""
        return {
            Timeframe.M1: 1,
            Timeframe.M5: 5,
            Timeframe.M15: 15,
            Timeframe.M30: 30,
            Timeframe.H1: 60,
            Timeframe.H4: 240,
            Timeframe.D1: 1440,
        }[self]

    def is_htf(self) -> bool:
        """True for the HTF swing-confirmation class (§27: Daily/H4/H1, N=5)."""
        return self in (Timeframe.D1, Timeframe.H4, Timeframe.H1)

    def is_ltf(self) -> bool:
        """True for the LTF swing-confirmation class (§27: M30/M15/M5/M1, N=3)."""
        return not self.is_htf()

    @classmethod
    def from_minutes(cls, minutes: int) -> Timeframe:
        """Look up a timeframe by its bar duration in minutes."""
        for tf in cls:
            if tf.minutes == minutes:
                return tf
        raise ValueError(f"No Timeframe with {minutes} minute bars")

    @classmethod
    def n_bar_confirmation(cls, tf: Timeframe) -> int:
        """Return the frozen N-bar confirmation value for a timeframe (§27)."""
        from smc.config.locked_constants import N_BAR_HTF, N_BAR_LTF

        return N_BAR_HTF if tf.is_htf() else N_BAR_LTF