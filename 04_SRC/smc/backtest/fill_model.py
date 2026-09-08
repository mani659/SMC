"""Pure fill model (Phase 6, Milestone 2).

LOCKED V1 fill semantics (Lead Architect decisions, SMC_PHASE_6_DESIGN.md
§5 / M2 instruction):

* **Limit fill = touch.** A BUY limit fills when the bar's LOW reaches or
  trades through the limit (``low <= limit``); a SELL limit when the bar's
  HIGH reaches or trades through it (``high >= limit``). Touch counts —
  no gap requirement, no mid-bar path reconstruction.
* **Fill price = the LIMIT price** (conservative — no optimistic
  better-of-open fills, no price improvement when the bar gaps through).
* **No partial fills** — full fill or none.
* **Same-bar SL + TP → SL wins** (worst case, counts as a loss).
* **Entry + SL in the same bar → SL wins** too: the position opens on the
  touch and, if that same bar's range also reaches the stop, it is stopped
  out on that bar (conservative; a touch gives no intra-bar ordering
  information, so we never assume the favourable path).

Every decision function is PURE over ``(Candle, price(s))`` — no clock, no
state, no MT5. Same-bar priority is resolved by explicit rule, not by
evaluation order, so the results are order-independent.
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.core.candle import Candle
from smc.core.enums import Direction

__all__ = [
    "limit_filled",
    "fill_price",
    "sl_hit",
    "tp_hit",
    "BarClose",
    "CloseKind",
    "evaluate_position_bar",
]


# ---------------------------------------------------------------------- #
# Pending limit fills
# ---------------------------------------------------------------------- #
def limit_filled(direction: Direction, limit_price: float, bar: Candle) -> bool:
    """True when ``bar`` trades at/through ``limit_price`` (touch = fill).

    BUY limit: filled when the bar's LOW is at or below the limit
    (price came down to the resting buy). SELL limit: filled when the bar's
    HIGH is at or above the limit. Boundaries are inclusive — an exact
    touch fills.
    """
    if direction is Direction.LONG:
        return bar.low <= limit_price
    return bar.high >= limit_price


def fill_price(direction: Direction, limit_price: float, bar: Candle) -> float:
    """The fill price for a touched limit — ALWAYS the limit price (locked).

    The bar is accepted for contract clarity (callers assert
    :func:`limit_filled` first); no better-of-open / gap improvement is
    applied by design.
    """
    if not limit_filled(direction, limit_price, bar):
        raise ValueError("fill_price called for a bar that does not touch the limit")
    return limit_price


# ---------------------------------------------------------------------- #
# SL / TP hits on an open position
# ---------------------------------------------------------------------- #
def sl_hit(direction: Direction, sl_price: float, bar: Candle) -> bool:
    """True when the bar's range reaches the stop (inclusive touch).

    LONG: stopped when ``bar.low <= sl``; SHORT: stopped when
    ``bar.high >= sl``.
    """
    if direction is Direction.LONG:
        return bar.low <= sl_price
    return bar.high >= sl_price


def tp_hit(direction: Direction, tp_price: float, bar: Candle) -> bool:
    """True when the bar's range reaches the target (inclusive touch).

    LONG: target when ``bar.high >= tp``; SHORT: target when
    ``bar.low <= tp``.
    """
    if direction is Direction.LONG:
        return bar.high >= tp_price
    return bar.low <= tp_price


class CloseKind:
    """Machine-readable close kinds (for the trade log / risk recording)."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


@dataclass(frozen=True, slots=True)
class BarClose:
    """The close decision for ONE open position over ONE bar."""

    closed: bool
    kind: str | None = None   # CloseKind.STOP_LOSS / TAKE_PROFIT when closed
    price: float | None = None
    win: bool | None = None   # SL → loss, TP → win (same bar: SL wins)


def evaluate_position_bar(
    direction: Direction,
    sl_price: float | None,
    tp_price: float | None,
    bar: Candle,
) -> BarClose:
    """SL/TP close decision for one open position over one bar.

    Same-bar rule (locked): if BOTH the SL and the TP level sit inside the
    bar's range, the STOP wins — the position closes at the SL price as a
    loss. This is worst-case and independent of open/close ordering (no
    intra-bar path is reconstructed in V1).
    """
    if sl_price is not None and sl_hit(direction, sl_price, bar):
        return BarClose(closed=True, kind=CloseKind.STOP_LOSS, price=sl_price, win=False)
    if tp_price is not None and tp_hit(direction, tp_price, bar):
        return BarClose(closed=True, kind=CloseKind.TAKE_PROFIT, price=tp_price, win=True)
    return BarClose(closed=False)
