"""Heartbeat path resolution for the MQL5 Safety Watchdog.

The Python side writes a plain-text heartbeat file; the MQL5 Safety Watchdog
EA reads it with the default input ``InpHeartbeatFile = "smc_heartbeat.txt"``,
which resolves in MT5 under the terminal's ``MQL5/Files/`` sandbox.

To make the EA see the heartbeat by default, the operator resolves the
heartbeat path from ``terminal_path`` when that is set::

    <directory of terminal64.exe>/MQL5/Files/smc_heartbeat.txt

This is operational plumbing only — no strategy, no threshold, no locked
constant logic lives here.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

HEARTBEAT_FILENAME = "smc_heartbeat.txt"
_FILES_SUBDIR = Path("MQL5") / "Files"

EA_READABLE_DEFAULT_FILENAME = HEARTBEAT_FILENAME


def terminal_dir(terminal_path: str) -> Path | None:
    """Terminal install directory derived from a terminal64.exe path.

    Returns ``None`` when the path cannot be interpreted as a terminal exe
    (so callers can fall back instead of guessing).
    """
    if terminal_path is None:
        return None
    tp = Path(str(terminal_path).strip())
    if not tp.name:
        return None
    if tp.name.lower().endswith("terminal64.exe"):
        parent = tp.parent
    else:
        parent = tp
    try:
        return parent.resolve(strict=False)
    except (OSError, ValueError):
        logger.exception(
            "heartbeat path resolution failed operation=resolve_terminal_path "
            "path=%s",
            tp,
        )
        return None


def ea_readable_heartbeat_dir(terminal_path: str) -> Path | None:
    """Directory the EA reads its default heartbeat file from, derived from
    ``terminal_path``.

    That directory is ``<terminal_dir>/MQL5/Files``. Returns ``None`` when
    ``terminal_path`` cannot be resolved to a terminal directory.
    """
    td = terminal_dir(terminal_path)
    if td is None:
        return None
    return td / _FILES_SUBDIR


def data_folder_heartbeat_path(terminal_data_path: str) -> Path | None:
    """EA-readable heartbeat path derived from the terminal DATA folder.

    For an installed (non-portable) MT5 the EA's ``FileOpen`` sandbox is the
    terminal data folder (``terminal_info().data_path``), NOT the install
    directory — this is the authoritative target whenever a live terminal
    connection is available.
    """
    if not terminal_data_path:
        return None
    dp = Path(str(terminal_data_path).strip())
    if not dp.name:
        return None
    try:
        return dp.resolve(strict=False) / _FILES_SUBDIR / HEARTBEAT_FILENAME
    except (OSError, ValueError):
        logger.exception(
            "heartbeat path resolution failed operation=resolve_data_path "
            "path=%s",
            dp,
        )
        return None


def ea_readable_heartbeat_path(terminal_path: str) -> Path | None:
    """EA-readable full path for the default heartbeat file, derived from
    ``terminal_path``.

    This is the path the operator should write to so the EA sees the heartbeat
    with its default ``InpHeartbeatFile = "smc_heartbeat.txt"``.
    """
    d = ea_readable_heartbeat_dir(terminal_path)
    if d is None:
        return None
    return d / HEARTBEAT_FILENAME


def heartbeat_path_candidates(
    terminal_path: str | None,
    explicit_heartbeat_path: str | None,
    *,
    default_fallback: str = "logs/phase_d/heartbeat.txt",
    terminal_data_path: str | None = None,
) -> list[tuple[str, Path]]:
    """Ordered (source, path) candidates, best first.

    Order: live terminal data folder > install-dir derivation > explicit
    config path > project/log-local default. ``resolve_heartbeat_path``
    returns the first candidate; callers that want a write-probe fallback
    (e.g. Program Files ACLs) iterate the list instead.
    """
    out: list[tuple[str, Path]] = []
    if terminal_data_path:
        p = data_folder_heartbeat_path(str(terminal_data_path))
        if p is not None:
            out.append(("terminal_data_path", p))
    if terminal_path:
        p = ea_readable_heartbeat_path(str(terminal_path))
        if p is not None:
            out.append(("terminal_path", p))
    if explicit_heartbeat_path:
        out.append(("config", Path(str(explicit_heartbeat_path).strip())))
    out.append(("default", Path(default_fallback)))
    seen: set[Path] = set()
    uniq: list[tuple[str, Path]] = []
    for source, p in out:
        if p not in seen:
            seen.add(p)
            uniq.append((source, p))
    return uniq


def probe_writable(path: Path) -> bool:
    """True when ``path``'s parent can be created and a probe file written.

    Catches at STARTUP what would otherwise be a PermissionError mid-session
    (e.g. the derived path lives under ``C:\\Program Files`` and the operator
    process is not elevated).
    """
    operation = "create heartbeat directory"
    probe = path.parent / (path.name + ".probe")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        operation = "write heartbeat probe"
        probe.write_text("probe", encoding="ascii")
        operation = "remove heartbeat probe"
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        logger.exception(
            "heartbeat path probe failed operation=%s target=%s probe=%s",
            operation,
            path,
            probe,
        )
        return False


def resolve_heartbeat_path(
    terminal_path: str | None,
    explicit_heartbeat_path: str | None,
    *,
    default_fallback: str = "logs/phase_d/heartbeat.txt",
    terminal_data_path: str | None = None,
) -> Path:
    """Best heartbeat path to write, policy-ordered.

    Order:

    1. ``terminal_data_path`` (from the LIVE ``mt5.terminal_info().data_path``)
       when available — the EA's actual ``FileOpen`` sandbox for installed
       (non-portable) terminals. Authoritative.
    2. Else, if ``terminal_path`` is set and parseable, the install-dir
       derivation ``<terminal_dir>/MQL5/Files/smc_heartbeat.txt`` (correct for
       portable-mode terminals; approximate otherwise). The caller is
       responsible for ensuring the parent ``MQL5/Files`` directory exists.
    3. Otherwise fall back to an explicit ``heartbeat_path`` if one was given.
    4. Otherwise fall back to ``default_fallback`` (project/log-local) and the
       caller should log that the EA may not read it.
    """
    return heartbeat_path_candidates(
        terminal_path,
        explicit_heartbeat_path,
        terminal_data_path=terminal_data_path,
        default_fallback=default_fallback,
    )[0][1]
