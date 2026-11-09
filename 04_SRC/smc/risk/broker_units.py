"""F3 — broker-derived sizing units (money safety).

The §28.7 sizing formula divides by ``sl_distance × pip_value_per_lot``, so
that input must be the **account-currency value of a 1.0 price-unit move per
1.0 lot**. That is a broker fact, not a strategy constant, and it is not
frozen anywhere: for XAUUSD on a 100 oz contract one dollar of price move is
100.00 per lot, so a hardcoded 10.0 sizes **ten times** too large and leaves
``LOT_MAX_SAFETY`` as the only barrier between the account and a 10× risk
error (Phase C: every trade came out at exactly 0.10 lots — the cap masked
the unit error).

This module DERIVES the value from ``symbol_info`` and compares it with the
configured one. It never guesses (no per-symbol table, no XAU default) and
never silently overwrites: a mismatch refuses the session in
``smc.live.run_operator``. No MetaTrader5 import — callers pass any object
exposing the standard ``symbol_info`` fields (``trade_tick_size``,
``trade_tick_value*``, ``trade_contract_size``, ``currency_profit``).

Derivation order:

1. **Tick path (preferred, currency-safe):** ``trade_tick_value_loss /
   trade_tick_size`` — the loss-side value when the broker reports it (that
   is the side a stop loss is charged on), else ``trade_tick_value``, else
   ``trade_tick_value_profit``. Broker values are already in account
   currency, so no FX assumption is made.
2. **Contract path (fallback):** ``trade_contract_size`` — valid only when
   the symbol's profit currency is the account currency (checked; refused
   otherwise). This is the "gold 100 oz" case and the generic
   USD-denominated case.
3. **Nothing usable → refuse.** A missing spec is a refusal, never a guess.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "SIZING_PIN_TOLERANCE_REL",
    "BrokerUnits",
    "BrokerUnitsError",
    "SizingPin",
    "SizingPinError",
    "derive_price_value_per_lot",
    "check_sizing_pin",
    "assert_sizing_pin",
]

#: Tight relative tolerance for configured-vs-derived. A unit error is 10×
#: (900 %) not 2 %, so anything above 1 % is a real disagreement.
SIZING_PIN_TOLERANCE_REL = 0.01


class BrokerUnitsError(RuntimeError):
    """``symbol_info`` cannot yield a unit value — refuse, never guess."""


class SizingPinError(RuntimeError):
    """Configured ``pip_value_per_lot`` disagrees with the broker."""


@dataclass(frozen=True, slots=True)
class BrokerUnits:
    """Derived unit value plus the exact broker fields it came from."""

    symbol: str
    price_value_per_lot: float
    source: str                       # "tick_value" | "contract_size"
    contract_size: float | None = None
    tick_size: float | None = None
    tick_value: float | None = None
    currency_profit: str | None = None
    account_currency: str | None = None

    def summary(self) -> str:
        """One-line provenance for logs (never a bare number)."""
        parts = [
            f"symbol={self.symbol!r}",
            f"price_value_per_lot={self.price_value_per_lot:.6g}",
            f"source={self.source}",
        ]
        if self.tick_size is not None:
            parts.append(f"tick_size={self.tick_size:.10g}")
        if self.tick_value is not None:
            parts.append(f"tick_value={self.tick_value:.10g}")
        if self.contract_size is not None:
            parts.append(f"contract_size={self.contract_size:.10g}")
        if self.currency_profit is not None:
            parts.append(f"currency_profit={self.currency_profit!r}")
        if self.account_currency is not None:
            parts.append(f"account_currency={self.account_currency!r}")
        return " ".join(parts)


def _number(info, name: str) -> float | None:
    """Read a numeric symbol_info field; ``None``/NaN/absent → ``None``."""
    value = getattr(info, name, None)
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _tick_value(info) -> float | None:
    """Loss-side per-tick value when reported, else plain, else profit side."""
    for name in ("trade_tick_value_loss", "trade_tick_value", "trade_tick_value_profit"):
        value = _number(info, name)
        if value is not None and value > 0.0:
            return value
    return None


def derive_price_value_per_lot(info, *, account_currency: str | None = None) -> BrokerUnits:
    """Derive the value of one price unit per lot from ``symbol_info``.

    Raises :class:`BrokerUnitsError` when the broker spec exposes nothing
    usable (or the contract-size fallback cannot be currency-verified). The
    caller must refuse the session on that error — sizing without a verified
    unit is exactly the defect F3 exists to close.
    """
    if info is None:
        raise BrokerUnitsError("symbol_info returned None — cannot verify sizing units")

    symbol = str(getattr(info, "name", "") or "")
    tick_size = _number(info, "trade_tick_size")
    tick_value = _tick_value(info)
    contract_size = _number(info, "trade_contract_size")
    currency_profit = getattr(info, "currency_profit", None)

    if tick_size is not None and tick_size > 0.0 and tick_value is not None:
        return BrokerUnits(
            symbol=symbol,
            price_value_per_lot=tick_value / tick_size,
            source="tick_value",
            contract_size=contract_size,
            tick_size=tick_size,
            tick_value=tick_value,
            currency_profit=str(currency_profit) if currency_profit else None,
            account_currency=account_currency,
        )

    if contract_size is not None and contract_size > 0.0:
        # Contract size is only a money value when the quote/profit currency
        # is the account currency; otherwise a conversion is missing and the
        # value would be a guess.
        if not account_currency:
            raise BrokerUnitsError(
                f"symbol_info for {symbol!r} has contract_size={contract_size!r} "
                "but no tick value, and the account currency is unknown — "
                "refusing an unverified unit value"
            )
        if not currency_profit:
            raise BrokerUnitsError(
                f"symbol_info for {symbol!r} has contract_size={contract_size!r} "
                "but no tick value and no currency_profit — refusing an "
                "unverified unit value"
            )
        if str(currency_profit).strip().upper() != str(account_currency).strip().upper():
            raise BrokerUnitsError(
                f"symbol_info for {symbol!r} has contract_size={contract_size!r} "
                f"and currency_profit={currency_profit!r} != account currency "
                f"{account_currency!r}; no conversion is available — refusing"
            )
        return BrokerUnits(
            symbol=symbol,
            price_value_per_lot=contract_size,
            source="contract_size",
            contract_size=contract_size,
            currency_profit=str(currency_profit),
            account_currency=account_currency,
        )

    raise BrokerUnitsError(
        f"symbol_info for {symbol!r} exposes no usable trade_tick_value/"
        "trade_tick_size or trade_contract_size — refusing to size trade"
    )


@dataclass(frozen=True, slots=True)
class SizingPin:
    """Result of comparing the configured unit value with the broker's."""

    ok: bool
    configured: float
    derived: float
    relative_diff: float
    tolerance: float
    reason: str | None = None
    units: BrokerUnits | None = None

    def summary(self) -> str:
        verdict = "PASS" if self.ok else "MISMATCH"
        text = (
            f"SIZING PIN {verdict}: configured={self.configured:.6g} "
            f"derived={self.derived:.6g} "
            f"relative_diff={self.relative_diff:.4%} tolerance={self.tolerance:.2%}"
        )
        if self.units is not None:
            text += f" ({self.units.summary()})"
        if self.reason:
            text += f" reason={self.reason}"
        return text


def check_sizing_pin(
    configured: float,
    units: BrokerUnits,
    *,
    tolerance: float = SIZING_PIN_TOLERANCE_REL,
) -> SizingPin:
    """Compare the configured unit value against the derived one.

    ``ok`` is False when either value is non-positive or the relative
    difference exceeds ``tolerance``. Nothing is adjusted — the caller
    refuses the session on a mismatch (no silent overwrite).
    """
    derived = float(units.price_value_per_lot)
    configured = float(configured)
    if not math.isfinite(configured) or configured <= 0.0:
        return SizingPin(
            ok=False,
            configured=configured,
            derived=derived,
            relative_diff=float("inf"),
            tolerance=tolerance,
            reason="configured value must be a positive number",
            units=units,
        )
    if not math.isfinite(derived) or derived <= 0.0:
        return SizingPin(
            ok=False,
            configured=configured,
            derived=derived,
            relative_diff=float("inf"),
            tolerance=tolerance,
            reason="derived value must be a positive number",
            units=units,
        )
    relative = abs(configured - derived) / derived
    ok = relative <= tolerance
    return SizingPin(
        ok=ok,
        configured=configured,
        derived=derived,
        relative_diff=relative,
        tolerance=tolerance,
        reason=None if ok else "configured value disagrees with the broker spec",
        units=units,
    )


def assert_sizing_pin(
    configured: float,
    units: BrokerUnits,
    *,
    tolerance: float = SIZING_PIN_TOLERANCE_REL,
) -> SizingPin:
    """``check_sizing_pin`` that raises :class:`SizingPinError` on mismatch."""
    verdict = check_sizing_pin(configured, units, tolerance=tolerance)
    if not verdict.ok:
        raise SizingPinError(verdict.summary())
    return verdict
