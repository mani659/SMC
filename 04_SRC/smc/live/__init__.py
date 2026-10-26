"""Phase 7 — Live: main loop, heartbeat publisher, watchdog integration.

Python owns ALL trading logic (Option A); the MQL5 Safety Watchdog EA
(``05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5``) only monitors the heartbeat
file and emergency-protects the account when Python dies.
"""

from smc.live.config import LiveConfig, live_config_from_dict
from smc.live.heartbeat import (
    HEARTBEAT_INTERVAL_SECONDS,
    WATCHDOG_STALE_TIMEOUT_SECONDS,
    HeartbeatPublisher,
    HeartbeatRecord,
    WatchdogDecision,
    evaluate_watchdog,
    heartbeat_age,
    is_stale,
    read_heartbeat,
    write_heartbeat,
)
from smc.live.loop import LiveLoop

__all__ = [
    "LiveConfig",
    "live_config_from_dict",
    "LiveLoop",
    "HeartbeatPublisher",
    "HeartbeatRecord",
    "WatchdogDecision",
    "HEARTBEAT_INTERVAL_SECONDS",
    "WATCHDOG_STALE_TIMEOUT_SECONDS",
    "evaluate_watchdog",
    "heartbeat_age",
    "is_stale",
    "read_heartbeat",
    "write_heartbeat",
]