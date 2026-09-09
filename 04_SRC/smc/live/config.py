"""Phase 7 — live configuration (demo-first posture).

All values are V1 operational defaults; the trading-side risk inputs are the
same ones the runners consume (single sizing path §28.7 — the risk engine
clamps any fraction into the frozen band). Timing defaults match the
binding values in the Phase 7 brief unless a more specific project constant
exists (none does): 1 s heartbeat interval, 5 s stale timeout, 0.5 s bar
poll interval, 200-bar detection window.

``live_config_from_dict`` merges a plain dict over the defaults (timeframes
accepted as ``Timeframe``, its name, or minutes) so a JSON/env source can
drive it later without a second config schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from smc.config.timeframe import Timeframe
from smc.live.heartbeat import (
    HEARTBEAT_INTERVAL_SECONDS,
    WATCHDOG_STALE_TIMEOUT_SECONDS,
)

__all__ = ["LiveConfig", "live_config_from_dict"]

DEFAULT_WINDOW_BARS = 200
DEFAULT_POLL_INTERVAL = 0.5


@dataclass(slots=True)
class LiveConfig:
    """Demo/live run configuration for the Phase 7 loop."""

    # Broker / instrument.
    symbol: str = "XAUUSD.x"
    timeframe: Timeframe = Timeframe.M5
    magic: int = 0                 # 0 = no magic filtering (explicit demo)
    demo: bool = True              # safety posture — demo-first
    dry_run: bool = False          # evaluate + log only, never send orders

    # Risk inputs (the SAME single sizing path as backtest/paper).
    risk_fraction: float = 0.01
    pip_value_per_lot: float = 10.0
    min_lots: float = 0.01
    lot_step: float = 0.01
    allowed_sessions: tuple | list | None = None   # None = no session gate
    news_events: list = field(default_factory=list)
    spread_price: float = 0.0      # PRICE units; 0.0 leaves the spread gate off

    # Detection window.
    window_bars: int = DEFAULT_WINDOW_BARS

    # Heartbeat + watchdog.
    heartbeat_path: str = "smc_heartbeat.txt"
    heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS
    watchdog_timeout: float = WATCHDOG_STALE_TIMEOUT_SECONDS
    poll_interval: float = DEFAULT_POLL_INTERVAL


def _coerce_timeframe(value) -> Timeframe:
    if isinstance(value, Timeframe):
        return value
    if isinstance(value, int):
        return Timeframe(value)
    if isinstance(value, str):
        try:
            return Timeframe[value.strip().upper()]
        except KeyError:
            try:
                return Timeframe.from_minutes(int(value))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"unknown timeframe: {value!r}") from exc
    raise TypeError(f"cannot interpret timeframe: {value!r}")


def live_config_from_dict(data: dict) -> LiveConfig:
    """Build a :class:`LiveConfig` from a plain dict (overrides only)."""
    merged = {
        k: v
        for k, v in data.items()
        if k in LiveConfig.__dataclass_fields__  # type: ignore[attr-defined]
    }
    if "timeframe" in merged:
        merged["timeframe"] = _coerce_timeframe(merged["timeframe"])
    return LiveConfig(**merged)