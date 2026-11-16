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
import ntpath
import os
from pathlib import Path, PurePath, PureWindowsPath

logger = logging.getLogger(__name__)

HEARTBEAT_FILENAME = "smc_heartbeat.txt"
_FILES_SUBDIR = Path("MQL5") / "Files"

EA_READABLE_DEFAULT_FILENAME = HEARTBEAT_FILENAME


def _looks_like_windows_path(raw: str) -> bool:
    s = str(raw).strip()
    if len(s) >= 2 and s[1] == ":":
        return True
    return s.startswith("\\\\") or s.startswith("//")


class _WinPathCompat(PureWindowsPath):
    """Windows-style path with POSIX-friendly component semantics."""

    def __new__(cls, *args):
        if len(args) == 1 and isinstance(args[0], PurePath):
            norm = ntpath.normpath(str(args[0]))
        elif len(args) == 1:
            norm = ntpath.normpath(os.fspath(args[0]))
        else:
            norm = ntpath.normpath(ntpath.join(*(os.fspath(a) for a in args)))
        return super().__new__(cls, norm)

    def __eq__(self, other):
        try:
            if isinstance(other, (str, os.PathLike)):
                other_s = os.fspath(other)
            else:
                return NotImplemented
        except Exception:
            return NotImplemented
        return ntpath.normpath(str(self)) == ntpath.normpath(str(other_s))

    def __hash__(self):
        return hash(ntpath.normpath(str(self)))

    def __truediv__(self, other):
        return _WinPathCompat(str(self), os.fspath(other))

    def __rtruediv__(self, other):
        return _WinPathCompat(os.fspath(other), str(self))

    def joinpath(self, *args):
        return _WinPathCompat(str(self), *(os.fspath(a) for a in args))

    @property
    def parent(self):
        p = super().parent
        return _WinPathCompat(str(p))


def _win_path(*parts: str) -> Path:
    """Windows-style path object.

    On POSIX hosts we return a Windows-compatible path wrapper so `.name`,
    `.parent`, joins and equality remain correct for MT5-derived paths in CI,
    while avoiding cwd-relative mangling of drive-letter strings.
    """
    norm = ntpath.normpath(ntpath.join(*parts))
    return Path(norm) if os.name == "nt" else _WinPathCompat(norm)  # type: ignore[return-value]


def terminal_dir(terminal_path: str) -> Path | None:
    """Terminal install directory derived from a terminal64.exe path.

    Returns ``None`` when the path cannot be interpreted as a terminal exe
    (so callers can fall back instead of guessing).
    """
    if terminal_path is None:
        return None
    raw = str(terminal_path).strip()
    if not raw:
        return None
    if _looks_like_windows_path(raw):
        base = ntpath.basename(raw)
        if not base:
            return None
        if base.lower().endswith("terminal64.exe"):
            parent = ntpath.dirname(raw)
        else:
            parent = raw
        if not parent:
            return None
        try:
            norm = ntpath.normpath(parent)
            return Path(norm).resolve(strict=False) if os.name == "nt" else _WinPathCompat(norm)  # type: ignore[return-value]
        except (OSError, ValueError):
            logger.exception(
                "heartbeat path resolution failed operation=resolve_terminal_path "
                "path=%s",
                raw,
            )
            return None
    tp = Path(raw)
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
            raw,
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
    if _looks_like_windows_path(str(terminal_path)):
        return _win_path(str(td), "MQL5", "Files")
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
    raw = str(terminal_data_path).strip()
    if not raw:
        return None
    if _looks_like_windows_path(raw):
        base = ntpath.basename(raw.rstrip("\\/"))
        if not base and not (len(raw) >= 2 and raw[1] == ":"):
            return None
        try:
            return _win_path(raw, "MQL5", "Files", HEARTBEAT_FILENAME)
        except (OSError, ValueError):
            logger.exception(
                "heartbeat path resolution failed operation=resolve_data_path "
                "path=%s",
                raw,
            )
            return None
    dp = Path(raw)
    if not dp.name:
        return None
    try:
        return dp.resolve(strict=False) / _FILES_SUBDIR / HEARTBEAT_FILENAME
    except (OSError, ValueError):
        logger.exception(
            "heartbeat path resolution failed operation=resolve_data_path "
            "path=%s",
            raw,
        )
        return None


def ea_readable_heartbeat_path(terminal_path: str) -> Path | None:
    """EA-readable full path for the default heartbeat file, derived from
    ``terminal_path``.

    This is the path the operator should write to so the EA sees the heartbeat
    with its default ``InpHeartbeatFile = "smc_heartbeat.txt"``.
    """
    if _looks_like_windows_path(str(terminal_path or "")):
        td = terminal_dir(terminal_path)
        if td is None:
            return None
        return _win_path(str(td), "MQL5", "Files", HEARTBEAT_FILENAME)
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
        raw = str(explicit_heartbeat_path).strip()
        if _looks_like_windows_path(raw):
            out.append(("config", Path(ntpath.normpath(raw))))
        else:
            out.append(("config", Path(raw)))
    out.append(("default", Path(default_fallback)))
    seen: set[str] = set()
    uniq: list[tuple[str, Path]] = []
    for source, p in out:
        key = str(p)
        if key not in seen:
            seen.add(key)
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
    except (OSError, AttributeError, NotImplementedError):
        # AttributeError/NotImplementedError: non-concrete/pure paths (e.g.
        # Windows-derived paths represented on POSIX CI) are not writable here.
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
