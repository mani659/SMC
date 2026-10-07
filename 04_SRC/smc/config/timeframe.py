"""Timeframe enum — values match MetaTrader5 ``TIMEFRAME_*`` constants.

The integer values are identical to the MetaTrader5 Python package's
``TIMEFRAME_*`` constants (M1=1 … D1=16408), so an ``int(tf)`` cast is a
valid MT5 timeframe and no mapping table is needed in ``smc/data``.
"""

from __future__ import annotations

from enum import IntEnum

__all__ = ["Timeframe"]


class Timeframe(IntEnum):
    """The locked detection/execution timeframes (LOCKED_DECISIONS §4/§27)
    plus the Weekly HTF context timeframe.

    W1 (added 2026-10-06, Lead Architect weekly-provisioning directive) is
    an ABOVE-DAILY HTF **context** timeframe: its value matches MT5's
    ``PERIOD_W1`` so ``int(tf)`` stays a valid MT5 timeframe, it belongs to
    the §27 HTF confirmation class (N=5, unchanged), and it never serves as
    an execution timeframe. Values are identical to the MetaTrader5 Python
    package's ``TIMEFRAME_*`` constants (M1=1 … D1=16408, W1=32769), so an
    ``int(tf)`` cast is a valid MT5 timeframe and no mapping table is needed
    in ``smc/data``.

    NOTE (dry-run fix 2026-10-06): W1 = 32769 (0x8001), NOT 32768 — the
    MetaTrader5 package's ``TIMEFRAME_W1`` is 32769 and
    ``copy_rates_from_pos`` rejects 32768 with "Invalid params" (caught
    live on the EXNESS Copy terminal). 32768 is never valid for any
    MT5 timeframe request.
    """

    M1 = 1
    M5 = 5
    M15 = 15
    M30 = 30
    H1 = 16385
    H4 = 16388
    D1 = 16408
    W1 = 32769

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
            Timeframe.W1: 10080,  # 7 × 1440 (one trading week)
        }[self]

    def is_htf(self) -> bool:
        """True for the HTF swing-confirmation class.

        §27 (frozen): Daily/H4/H1, N=5. W1 (weekly) is above-daily HTF
        context (provisioning directive 2026-10-06) and shares the same
        N=5 class; ``N_BAR_HTF`` itself is unchanged.
        """
        return self in (Timeframe.W1, Timeframe.D1, Timeframe.H4, Timeframe.H1)

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