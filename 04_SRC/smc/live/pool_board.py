"""Read-only pool board for the structure console (wire-light).

Turns whatever candle window the operator already holds into:

* active pool levels (P2a ``LiquidityPool``), and
* recent enter_at-safe sweep hits (P2b ``attribute_sweeps``).

Observability only. Nothing here gates an entry, ranks levels, or feeds a
risk/trigger decision. EQH/EQL is never constructed (R-EQH-C).

Live V1 honesty: the operator window is the execution series (M5, ~300 bars),
so the board shows what that window can actually support — session levels and,
when the window covers a completed prior day, PDH/PDL. PWH/PWL needs a prior
completed week and structural pool levels need H4/H1, so those families render
``(none)`` in this V1 until the caller supplies longer/HTF series. Missing
family data is reported, never fabricated.
"""

from __future__ import annotations

from datetime import datetime

from smc.config.timeframe import Timeframe
from smc.core.enums import LiquidityType
from smc.detection.periodic_levels import detect_periodic_levels
from smc.detection.session_levels import detect_session_levels
from smc.detection.structural_swing_detector import detect_swings
from smc.liquidity import (
    LiquidityPool,
    from_pdh_pdl,
    from_pwh_pwl,
    from_session,
    from_structural,
    attribute_sweeps,
)
from smc.utils.timestamps import detect_session as detect_session_window

__all__ = ["MAX_HITS", "build_live_pool_board"]

#: Recent pool sweeps shown on the board (display constant, NOT a locked one).
MAX_HITS = 8


def _session_levels(candles, tf: Timeframe) -> list:
    out = []
    for level in detect_session_levels(candles, tf):
        if level.formed_at is None:
            continue
        formed = level.formed_at
        window = detect_session_window(formed)
        if window is None:
            continue
        out.append(
            from_session(
                level,
                session=window.name,
                day=formed.date(),
                source_tf=Timeframe.M5,
            )
        )
    return out


def _periodic_levels(candles, tf: Timeframe) -> list:
    out = []
    for level in detect_periodic_levels(candles, tf):
        if level.type is LiquidityType.PREVIOUS_DAY:
            out.append(from_pdh_pdl(level, tf))
        elif level.type is LiquidityType.PREVIOUS_WEEK:
            out.append(from_pwh_pwl(level, tf))
    return out


def _structural_levels(candles, tf: Timeframe) -> list:
    """Pool structural levels only for HTF detection series (§4a)."""
    if tf not in (Timeframe.H4, Timeframe.H1):
        return []
    out = []
    for swing in detect_swings(candles, tf):
        if swing.is_valid:
            out.append(from_structural(swing, candles, tf))
    return out


def _hit_groups(pool: LiquidityPool, candles, tf: Timeframe) -> list[dict]:
    """Recent pool sweeps grouped per bar (all levels listed, no winner)."""
    tf_levels = [lv for lv in pool.all_levels() if lv.source_tf is tf]
    if not tf_levels:
        return []
    report = attribute_sweeps(pool, candles, levels=tf_levels)
    by_bar: dict = {}
    for hit in report.hits:
        by_bar.setdefault(hit.sweep_bar_ts, []).append(hit)

    groups = []
    for ts in sorted(by_bar)[-MAX_HITS:]:
        items = by_bar[ts]
        groups.append({
            "ts": ts,
            "ts_short": ts.strftime("%m-%d %H:%M"),
            "n": len(items),
            "items": [
                {
                    "family": hit.family,
                    "side": hit.side,
                    "price": hit.price,
                    "level_id": "|".join(hit.level_id),
                    "enter_at": hit.enter_at,
                }
                for hit in items
            ],
        })
    return groups


def build_live_pool_board(
    candles,
    *,
    timeframe: Timeframe | None = None,
    now: datetime | None = None,
) -> dict:
    """Build the console pool board from the candles already in hand.

    Returns a render-ready dict ``{levels, hits, n_active, note}``. Failures in
    one family never abort the board: the note records what could not be
    built, and the caller renders ``n/a (<reason>)``.
    """
    candles = list(candles or [])
    if not candles:
        return {"levels": [], "hits": [], "n_active": 0, "note": "n/a (no candles yet)"}

    tf = timeframe or getattr(candles[-1], "timeframe", Timeframe.M5)

    pool = LiquidityPool()
    candidates = []
    try:
        candidates += _session_levels(candles, tf)
    except Exception as exc:  # noqa: BLE001 — display never dies
        return {"levels": [], "hits": [], "n_active": 0,
                "note": f"n/a (session build: {type(exc).__name__})"}
    try:
        candidates += _periodic_levels(candles, tf)
    except Exception:  # noqa: BLE001 — periodic family is best-effort in live V1
        pass
    try:
        candidates += _structural_levels(candles, tf)
    except Exception:  # noqa: BLE001
        pass

    for level in sorted(
        candidates, key=lambda lv: (lv.enter_at, lv.family.value, lv.side.value, lv.period_id)
    ):
        try:
            pool.add(level)
        except ValueError:
            continue                      # duplicate identity / out-of-order guard

    levels = [
        {
            "family": lv.family.value,
            "side": lv.side.value.upper(),
            "price": lv.price,
            "period_id": lv.period_id,
            "source_tf": lv.source_tf.name,
            "enter_at": lv.enter_at,
        }
        for lv in pool.inventory(candles[-1].timestamp)
    ]

    try:
        hits = _hit_groups(pool, candles, tf)
    except Exception as exc:  # noqa: BLE001
        return {"levels": levels, "hits": [], "n_active": len(levels),
                "note": f"n/a (attribution: {type(exc).__name__})"}

    return {"levels": levels, "hits": hits, "n_active": len(levels), "note": None}
