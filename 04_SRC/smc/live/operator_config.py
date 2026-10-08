"""Phase D operator pack — external mutable config (strict whitelist).

Design (Lead Architect instruction, Phase D operator pack):

* the operator may tune ONLY operational parameters — terminal path, symbol,
  magic, dry-run, poll/console cadence, log directory, heartbeat, and
  ``risk_fraction`` WITHIN the frozen band (``RISK_PCT_MIN``..``RISK_PCT_MAX``);
* any attempt to set a LOCKED quantity (spread-gate constants, BE rules,
  circuit breaker, trigger geometry, freshness/expiry, lot cap, …) is
  **rejected loudly** — the loader raises, listing the offending keys;
* unknown keys are rejected too (typos must not silently no-op);
* the file is JSON (no YAML dependency exists in the repo).

The validated result is an :class:`OperatorConfig` frozen dataclass; the
raw file is archived at startup by the entrypoint for auditability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from smc.config.locked_constants import RISK_PCT_MAX, RISK_PCT_MIN

__all__ = [
    "ConfigError",
    "OperatorConfig",
    "REQUIRED_TERMINAL_PATH",
    "load_operator_config",
    "normalize_terminal_dir",
]

REQUIRED_TERMINAL_PATH = (
    r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe"
)

# Allowed config keys — everything else is rejected (typo protection).
ALLOWED_KEYS = frozenset({
    "terminal_path",
    "symbol",
    "magic",
    "dry_run",
    "require_demo",
    "risk_fraction",
    "timeframe",
    "detection_timeframes",        # C1: explicit detection TF list (H4+H1)
    "allow_single_tf_degraded",    # C1: test-only single-TF opt-in (default False)
    "allowed_sessions",
    "heartbeat_path",
    "heartbeat_interval_s",
    "poll_interval_s",
    "console_refresh_s",
    "console_mode",               # "event" (default) | "board" (legacy timed)
    "alive_interval_s",           # event mode: short alive line every N s (0 = off)
    "log_dir",
})

# LOCKED quantities that must never appear in an operator config. Values are
# frozen in smc.config.locked_constants; naming them here is documentation
# + loud rejection, not a second source of truth.
LOCKED_FORBIDDEN_KEYS = frozenset({
    "LOT_MAX_SAFETY", "lot_max_safety", "max_lots",
    "SPREAD_MAX_ATR", "spread_max_atr",
    "spread_grade_multipliers", "spread_grade_score_thresholds",
    "BE_ATR", "be_atr", "be_buffer", "be_buffer_atr",
    "circuit_breaker", "breaker_daily_loss", "breaker_consecutive",
    "sweep_threshold", "same_level_threshold",
    "trigger_geometry", "freshness_bars", "expiry_bars",
    "locked_constants", "risk_pct_min", "risk_pct_max",
    "atr_period", "spread_price",
})


class ConfigError(ValueError):
    """Raised for any operator-config violation (loud, never silent)."""


def normalize_terminal_dir(path: str) -> str:
    """Case/separator-insensitive terminal DIRECTORY for identity checks.

    ``terminal_info().path`` returns the terminal directory WITHOUT the
    ``terminal64.exe`` suffix, so comparisons are done on the directory:
    the configured exe path's parent, normalized to backslashes, stripped
    and lowercased.
    """
    norm = str(path).replace("/", "\\").strip().rstrip("\\").lower()
    if norm.endswith("\\terminal64.exe"):
        norm = norm[: -len("\\terminal64.exe")]
    return norm


def _coerce_bool(value, key: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigError(f"config.{key} must be a JSON bool, got {value!r}")


def _coerce_positive_number(value, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"config.{key} must be a number, got {value!r}")
    if value <= 0:
        raise ConfigError(f"config.{key} must be > 0, got {value!r}")
    return float(value)


@dataclass(frozen=True, slots=True)
class OperatorConfig:
    """Validated operator config (Phase D demo/live run surface)."""

    terminal_path: str = REQUIRED_TERMINAL_PATH
    symbol: str = "XAUUSDm"
    magic: int = 20260919
    dry_run: bool = True
    require_demo: bool = True
    risk_fraction: float = 0.01
    timeframe: str = "M5"
    # C1 product runtime (contract: 00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md).
    # Detection timeframes are operational config, but they are validated
    # against the contract: detect==exec is rejected unless degraded mode is
    # explicitly requested (no silent single-TF detect in product mode).
    detection_timeframes: tuple[str, ...] = ("H4", "H1")
    allow_single_tf_degraded: bool = False
    allowed_sessions: tuple[str, ...] | None = None   # None = no session gate
    # Heartbeat is written where the MQL5 Safety Watchdog EA can read it.
    # When ``terminal_path`` is set, the operator resolves the write path to
    # ``<terminal_dir>/MQL5/Files/smc_heartbeat.txt`` so the EA sees it with
    # its default ``InpHeartbeatFile = "smc_heartbeat.txt"``. When
    # ``terminal_path`` is absent/untidy the operator falls back to the
    # explicit ``heartbeat_path``, then to this log-local default and should
    # log that the EA may not read it.
    heartbeat_path: str = "logs/phase_d/heartbeat.txt"
    heartbeat_interval_s: float = 1.0
    poll_interval_s: float = 0.5
    console_refresh_s: float = 5.0
    # Event-driven console (2026-10-07): "event" = mostly silent, prints the
    # full board only on major events (session start, new bar, HTF batch,
    # flow/KPI change, new error, shutdown) plus a short one-line alive ping
    # every ``alive_interval_s``. "board" = legacy timed full refresh every
    # ``console_refresh_s`` (kept for debugging). ``console_refresh_s`` still
    # rate-limits the display-only structure-snapshot rebuilds on new bars
    # in both modes; batch changes always rebuild immediately.
    console_mode: str = "event"
    alive_interval_s: float = 300.0
    log_dir: str = "logs/phase_d"
    source_path: str | None = None
    raw: dict = field(default_factory=dict, repr=False, compare=False)


def load_operator_config(path: str | Path) -> OperatorConfig:
    """Load + validate an operator config file (strict whitelist).

    Raises :class:`ConfigError` on unknown keys, locked keys, out-of-band
    ``risk_fraction``, or malformed values. All validation happens BEFORE
    any terminal connection is attempted.
    """
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"config file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("config root must be a JSON object")

    forbidden = sorted(LOCKED_FORBIDDEN_KEYS & data.keys())
    if forbidden:
        raise ConfigError(
            "config attempts to set LOCKED constants — rejected: "
            + ", ".join(forbidden)
            + " (locked values live in smc.config.locked_constants only)"
        )
    unknown = sorted(set(data.keys()) - ALLOWED_KEYS)
    if unknown:
        raise ConfigError(
            "unknown config keys — rejected (typos are not silently ignored): "
            + ", ".join(unknown)
            + f"; allowed keys: {sorted(ALLOWED_KEYS)}"
        )

    kwargs: dict = {"source_path": str(p), "raw": dict(data)}

    if "terminal_path" in data:
        tp = str(data["terminal_path"]).strip()
        if not tp:
            raise ConfigError("config.terminal_path must be a non-empty string")
        kwargs["terminal_path"] = tp
    if "symbol" in data:
        sym = str(data["symbol"]).strip()
        if not sym:
            raise ConfigError("config.symbol must be a non-empty string")
        kwargs["symbol"] = sym
    if "magic" in data:
        magic = data["magic"]
        if isinstance(magic, bool) or not isinstance(magic, int) or magic <= 0:
            raise ConfigError(
                f"config.magic must be a positive integer (dedicated per phase), "
                f"got {magic!r}"
            )
        kwargs["magic"] = magic
    if "dry_run" in data:
        kwargs["dry_run"] = _coerce_bool(data["dry_run"], "dry_run")
    if "require_demo" in data:
        kwargs["require_demo"] = _coerce_bool(data["require_demo"], "require_demo")
    if "risk_fraction" in data:
        rf = _coerce_positive_number(data["risk_fraction"], "risk_fraction")
        lo, hi = RISK_PCT_MIN / 100.0, RISK_PCT_MAX / 100.0
        if not (lo <= rf <= hi):
            raise ConfigError(
                f"config.risk_fraction {rf} outside the LOCKED band "
                f"[{RISK_PCT_MIN}% .. {RISK_PCT_MAX}%] — rejected"
            )
        kwargs["risk_fraction"] = rf
    if "timeframe" in data:
        kwargs["timeframe"] = str(data["timeframe"]).strip().upper()
    if "allow_single_tf_degraded" in data:
        kwargs["allow_single_tf_degraded"] = _coerce_bool(
            data["allow_single_tf_degraded"], "allow_single_tf_degraded"
        )
    if "detection_timeframes" in data:
        raw_tfs = data["detection_timeframes"]
        if not isinstance(raw_tfs, list) or not raw_tfs or not all(
            isinstance(tf, str) and tf.strip() for tf in raw_tfs
        ):
            raise ConfigError(
                'config.detection_timeframes must be a non-empty list of '
                'timeframe names (e.g. ["H4", "H1"])'
            )
        names = tuple(tf.strip().upper() for tf in raw_tfs)
        from smc.config.timeframe import Timeframe as _TF  # local: avoid cycle
        unknown_tfs = [n for n in names if n not in _TF.__members__]
        if unknown_tfs:
            raise ConfigError(
                "config.detection_timeframes has unknown names — rejected: "
                + ", ".join(unknown_tfs)
                + f"; known: {sorted(_TF.__members__)}"
            )
        kwargs["detection_timeframes"] = names
    execution_name = kwargs.get("timeframe", "M5")
    detection_names = kwargs.get("detection_timeframes", ("H4", "H1"))
    degraded = kwargs.get("allow_single_tf_degraded", False)
    if not degraded and set(detection_names) <= {execution_name}:
        raise ConfigError(
            "config.detection_timeframes collapse onto the execution timeframe "
            f"({execution_name}) — that is single-TF detect+exec, prohibited by "
            "the product runtime contract; set allow_single_tf_degraded=true "
            "only for tests"
        )
    if "allowed_sessions" in data:
        raw_sessions = data["allowed_sessions"]
        if raw_sessions is None:
            kwargs["allowed_sessions"] = None
        elif isinstance(raw_sessions, list) and all(
            isinstance(s, str) and s.strip() for s in raw_sessions
        ):
            kwargs["allowed_sessions"] = tuple(
                s.strip().upper() for s in raw_sessions
            )
        else:
            raise ConfigError(
                "config.allowed_sessions must be null or a list of non-empty "
                'strings (e.g. ["LONDON", "NEW_YORK"])'
            )
    if "heartbeat_path" in data:
        hp = str(data["heartbeat_path"]).strip()
        if not hp:
            raise ConfigError("config.heartbeat_path must be a non-empty string")
        kwargs["heartbeat_path"] = hp
    if "heartbeat_interval_s" in data:
        kwargs["heartbeat_interval_s"] = _coerce_positive_number(
            data["heartbeat_interval_s"], "heartbeat_interval_s"
        )
    if "poll_interval_s" in data:
        kwargs["poll_interval_s"] = _coerce_positive_number(
            data["poll_interval_s"], "poll_interval_s"
        )
    if "console_refresh_s" in data:
        kwargs["console_refresh_s"] = _coerce_positive_number(
            data["console_refresh_s"], "console_refresh_s"
        )
    if "console_mode" in data:
        mode = str(data["console_mode"]).strip().lower()
        if mode not in ("event", "board"):
            raise ConfigError(
                'config.console_mode must be "event" or "board", got '
                f"{data['console_mode']!r}"
            )
        kwargs["console_mode"] = mode
    if "alive_interval_s" in data:
        value = data["alive_interval_s"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(
                f"config.alive_interval_s must be a number, got {value!r}"
            )
        if value < 0:
            raise ConfigError(
                f"config.alive_interval_s must be >= 0 (0 disables the ping), "
                f"got {value!r}"
            )
        kwargs["alive_interval_s"] = float(value)
    if "log_dir" in data:
        ld = str(data["log_dir"]).strip()
        if not ld:
            raise ConfigError("config.log_dir must be a non-empty string")
        kwargs["log_dir"] = ld

    return OperatorConfig(**kwargs)
