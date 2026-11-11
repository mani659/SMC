"""Liquidity pool registry (P2a) — membership, identity, lifecycle.

Design authority: ``06_RESEARCH/P2_LIQUIDITY_POOL_DESIGN.md`` accepted with
amendments R1–R5 (2026-11-11).

Scope of this package is deliberately thin:

* pool member set + ``level_id`` identity,
* enter/exit lifecycle derived from supersession,
* a read-only ``active_asof`` view.

It contains **no** ranking, no scoring, no sweep detection, no wiring into
the live/paper loop, triggers, risk or POI layers. Detection mathematics
(PDH/PDL, PWH/PWL, session, structural, EQH/EQL) is untouched.

R-EQH-C: equal highs/lows are **not** pool members. Offering one raises.
"""

from __future__ import annotations

from smc.liquidity.pool import (
    POOL_FAMILIES,
    LiquidityPool,
    PoolFamily,
    PoolLevel,
    PoolLevelId,
    PoolSide,
    PoolStatus,
    from_pdh_pdl,
    from_pwh_pwl,
    from_session,
    from_structural,
    inventory_sort_key,
)

__all__ = [
    "POOL_FAMILIES",
    "LiquidityPool",
    "PoolFamily",
    "PoolLevel",
    "PoolLevelId",
    "PoolSide",
    "PoolStatus",
    "from_pdh_pdl",
    "from_pwh_pwl",
    "from_session",
    "from_structural",
    "inventory_sort_key",
]
