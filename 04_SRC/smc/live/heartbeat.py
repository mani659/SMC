"""Phase 7 — heartbeat publisher + watchdog decision (live readiness).

Heartbeat transport (V1): a single PLAIN-TEXT FILE is the simplest reliable
mechanism the MQL5 Safety Watchdog EA can read (``FileOpen`` with
``FILE_READ|FILE_TXT|FILE_ANSI``) with zero dependencies. Redis was
considered and rejected for V1: the project has no Redis deployment and the
EA cannot read Redis without a third-party socket library — a file both
sides can see is the least-movable contract.

File format (stable — the EA parses line 1 only)::

    <unix_epoch_seconds> <monotonic_sequence>
    state=<running|shutdown>

* ``unix_epoch_seconds`` — UTC epoch seconds written by the (injected)
  clock; the EA compares it against ``TimeGMT()`` (also UTC epoch).
* ``sequence`` — monotonically increasing writer counter (observability).
* ``state`` — ``running`` while the loop is alive; ``shutdown`` is written
  once on a CLEAN stop so operators can tell a graceful stop from a crash.
  The watchdog does NOT distinguish: it treats ANY stale / missing /
  unreadable heartbeat as dead-Python and requests the emergency action
  (fail-closed).

Watchdog contract (tested reference): the EA implements exactly the decision
of :func:`evaluate_watchdog` — healthy heartbeat → no action; stale or
unreadable → emergency close-all + cancel-all. The Python simulation below
is the spec the MQL5 code is reviewed against.

Defaults (UNFROZEN operational timing, not trading thresholds — the project
has no existing heartbeat constants): 1 s heartbeat interval, 5 s stale
timeout. Both are config-overridable (``smc.live.config.LiveConfig``).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "HEARTBEAT_INTERVAL_SECONDS",
    "WATCHDOG_STALE_TIMEOUT_SECONDS",
    "HeartbeatRecord",
    "HeartbeatWriteError",
    "HeartbeatPublisher",
    "WatchdogDecision",
    "write_heartbeat",
    "read_heartbeat",
    "heartbeat_age",
    "is_stale",
    "evaluate_watchdog",
]

HEARTBEAT_INTERVAL_SECONDS = 1.0
WATCHDOG_STALE_TIMEOUT_SECONDS = 5.0
# Windows coexistence (2026-10-08): the watchdog EA opens the heartbeat file
# briefly each timer tick (open → read → close). If that read overlaps the
# Python atomic rename, ``os.replace`` fails with a transient sharing
# violation ([WinError 5] Access is denied). Retry the rename a few times
# before falling back to an in-place overwrite (which needs only write
# sharing, not delete sharing). Operational timing only — not a trading
# constant.
HEARTBEAT_REPLACE_ATTEMPTS = 5
HEARTBEAT_REPLACE_BACKOFF_SECONDS = 0.02

STATE_RUNNING = "running"
STATE_SHUTDOWN = "shutdown"
logger = logging.getLogger(__name__)
_read_failures: dict[str, tuple[str, str]] = {}


class HeartbeatWriteError(PermissionError):
    """Heartbeat publication failed and watchdog liveness is no longer assured."""


@dataclass(frozen=True, slots=True)
class HeartbeatRecord:
    """One successfully parsed heartbeat file."""

    unix_ts: int      # UTC epoch seconds (writer clock)
    sequence: int     # monotonic writer counter
    state: str = STATE_RUNNING


@dataclass(frozen=True, slots=True)
class WatchdogDecision:
    """Pure-Python simulation of the MQL5 Safety Watchdog decision."""

    action: str                    # "no_action" | "emergency"
    reason: str
    record: HeartbeatRecord | None = None

    @property
    def emergency(self) -> bool:
        return self.action == "emergency"


# ---------------------------------------------------------------------- #
# File format
# ---------------------------------------------------------------------- #
def write_heartbeat(
    path,
    unix_ts: float,
    sequence: int,
    state: str = STATE_RUNNING,
    *,
    replace_attempts: int = HEARTBEAT_REPLACE_ATTEMPTS,
    backoff_seconds: float = HEARTBEAT_REPLACE_BACKOFF_SECONDS,
) -> None:
    """Write one heartbeat record so the EA can read it WHILE we write.

    Strategy (Windows coexistence — 2026-10-08):

    1. Write the full payload to ``<target>.tmp``.
    2. Atomically rename it over the target (``os.replace``); if that raises
       a transient sharing violation (the EA is mid-read), retry a few times
       with a short backoff.
    3. If the rename still fails, fall back to an IN-PLACE overwrite of the
       target (open + truncate + write + flush). In-place writes need only
       write sharing, not delete sharing, so they survive a read lock that
       blocks the rename.

    Only when the temp write, every rename attempt, AND the in-place fallback
    all fail does this raise :class:`HeartbeatWriteError` — a single transient
    'Access is denied' collision must NOT fail the session closed. Operators
    still get the real call site (target + temp) in the message/events.log.
    """
    target = Path(path)
    tmp = target.with_name(target.name + ".tmp")
    payload = f"{int(unix_ts)} {sequence}\nstate={state}\n"
    try:
        tmp.write_text(payload, encoding="ascii")
    except OSError as exc:
        raise HeartbeatWriteError(
            f"heartbeat write temporary file failed target={target} "
            f"temp={tmp}: {exc}"
        ) from exc

    attempts = max(1, int(replace_attempts))
    last_replace_exc: OSError | None = None
    for attempt in range(1, attempts + 1):
        try:
            os.replace(tmp, target)
            return
        except OSError as exc:
            last_replace_exc = exc
            if attempt < attempts:
                time.sleep(max(0.0, float(backoff_seconds)))

    # Rename blocked (EA read lock / sharing violation). Fall back to an
    # in-place overwrite: needs write sharing only, so it coexists with an
    # active reader. Logged as a recovery, never a fail-closed.
    try:
        _write_in_place(target, payload)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        logger.warning(
            "heartbeat atomic replace blocked after %d attempts; wrote in "
            "place target=%s temp=%s last_replace_error=%r",
            attempts,
            target,
            tmp,
            last_replace_exc,
        )
        return
    except OSError as exc:
        raise HeartbeatWriteError(
            f"heartbeat publish failed after {attempts} replace attempts and "
            f"in-place fallback target={target} temp={tmp}: "
            f"replace_error={last_replace_exc!r} inplace_error={exc!r}"
        ) from exc


def _write_in_place(target: Path, payload: str) -> None:
    """Overwrite ``target`` in place (open + truncate + write + fsync).

    Needs only write sharing, so it coexists with an EA that holds the file
    open for reading — unlike an atomic rename, which needs delete sharing.
    """
    with target.open("w", encoding="ascii") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())


def read_heartbeat(path) -> HeartbeatRecord | None:
    """Parse the heartbeat file; ``None`` for missing/unreadable/garbage.

    ``None`` is the FAIL-CLOSED case: the watchdog must treat anything it
    cannot positively confirm as stale (a dead Python cannot write a fresh
    heartbeat, and a corrupted file is no safer to trust).
    """
    target = Path(path)
    key = str(target)
    try:
        text = target.read_text(encoding="ascii")
    except OSError as exc:
        signature = (type(exc).__name__, str(exc))
        if _read_failures.get(key) != signature:
            logger.error(
                "heartbeat read failed operation=open path=%s error=%r",
                target,
                exc,
                exc_info=True,
            )
        _read_failures[key] = signature
        return None
    except ValueError as exc:
        logger.error(
            "heartbeat read failed operation=decode path=%s error=%r",
            target,
            exc,
            exc_info=True,
        )
        return None
    if _read_failures.pop(key, None) is not None:
        logger.info("heartbeat read recovered operation=open path=%s", target)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    parts = lines[0].split()
    if len(parts) < 2:
        return None
    try:
        unix_ts = int(parts[0])
        sequence = int(parts[1])
    except ValueError:
        return None
    if unix_ts <= 0:
        return None
    state = STATE_RUNNING
    for line in lines[1:]:
        if line.startswith("state="):
            state = line.split("=", 1)[1]
    return HeartbeatRecord(unix_ts=unix_ts, sequence=sequence, state=state)


def heartbeat_age(record: HeartbeatRecord | None, now_unix: float) -> float:
    """Age of the heartbeat in seconds (``+inf`` when unreadable)."""
    if record is None:
        return float("inf")
    return max(now_unix - record.unix_ts, 0.0)


def is_stale(
    record: HeartbeatRecord | None, now_unix: float, timeout: float
) -> bool:
    """True when the heartbeat is older than ``timeout`` (or unreadable)."""
    return heartbeat_age(record, now_unix) > timeout


# ---------------------------------------------------------------------- #
# Watchdog decision — the tested spec the EA implements
# ---------------------------------------------------------------------- #
def evaluate_watchdog(
    heartbeat_path, now_unix: float, timeout: float
) -> WatchdogDecision:
    """The watchdog decision for one check (mirrors the EA's OnTimer).

    * heartbeat readable and fresh  → ``no_action``
    * heartbeat stale               → ``emergency`` ("stale")
    * heartbeat missing/unreadable  → ``emergency`` ("unreadable") — fail-closed

    The EA performs exactly this decision, then executes the emergency
    action (close ALL scoped positions + delete ALL scoped pendings).
    """
    record = read_heartbeat(heartbeat_path)
    if record is None:
        return WatchdogDecision(
            action="emergency", reason="unreadable", record=None
        )
    if is_stale(record, now_unix, timeout):
        return WatchdogDecision(
            action="emergency", reason="stale", record=record
        )
    return WatchdogDecision(action="no_action", reason="healthy", record=record)


# ---------------------------------------------------------------------- #
# Publisher (interval-bounded writes; injected clock for determinism)
# ---------------------------------------------------------------------- #
class HeartbeatPublisher:
    """Writes the heartbeat file, at most once per ``interval_seconds``.

    The clock is INJECTED (``now`` → timezone-aware datetime) so tests and
    the live loop are deterministic; the live loop passes the default wall
    clock. ``publish_shutdown`` records a clean stop (the watchdog still
    treats any stale heartbeat as dead — documented fail-closed).
    """

    def __init__(
        self,
        path,
        *,
        interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS,
        now=None,
    ) -> None:
        self.path = path
        self.interval_seconds = interval_seconds
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._sequence = 0
        self._last_unix: float | None = None
        self.state = STATE_RUNNING

    # ------------------------------------------------------------------ #
    def _unix(self) -> float:
        return self._now().timestamp()

    def publish(self) -> None:
        """Force a heartbeat write (ignores the interval)."""
        self._sequence += 1
        write_heartbeat(self.path, self._unix(), self._sequence, self.state)
        self._last_unix = self._unix()

    def maybe_publish(self) -> bool:
        """Write only when the interval has elapsed; True when written."""
        if self._last_unix is not None:
            if self._unix() - self._last_unix < self.interval_seconds:
                return False
        self.publish()
        return True

    def publish_shutdown(self) -> None:
        """Mark a CLEAN stop (operator observability; watchdog unchanged)."""
        self.state = STATE_SHUTDOWN
        self.publish()

    @property
    def sequence(self) -> int:
        return self._sequence