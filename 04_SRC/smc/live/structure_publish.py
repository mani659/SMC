"""Structure-draw file publisher (design lock 2026-10-22, §1–§2).

Python side of the STRUCTURE DRAW seam: Python OWNS levels — this module
writes a FULL snapshot text file the MQL5 draw EA reads. **VISUALIZATION
ONLY — NOT A STRATEGY CHANGE.** The EA draws; it never decides anything,
and nothing here feeds back into any trading decision.

Same publishing discipline as the accepted surfaces:

* **Full snapshot, rewritten atomically** each refresh (write-temp +
  ``os.replace`` with a small retry budget + in-place fallback — the
  ``smc.live.heartbeat.write_heartbeat`` Windows-coexistence strategy,
  because the EA's ``FileOpen``/close each timer tick can collide with a
  rename the same way it can for the heartbeat/markers).
* **EA-readable path discipline** identical to the heartbeat: the
  authoritative target is the terminal DATA folder
  ``<terminal_data_path>/MQL5/Files/`` (the EA's real sandbox), then the
  install-dir derivation ``<terminal_dir>/MQL5/Files/`` (portable
  terminals), then an explicit path, then the session log dir.
* **Fail-safe**: every publish failure is logged and swallowed here —
  a broken draw file can never abort an operator session.

Schema (design lock, NORMATIVE — implement exactly)::

    Line 1:  SMC_STRUCTURE_DRAW v1
    Line 2:  ts_utc=YYYY-MM-DDTHH:MM:SSZ symbol=<symbol>
    Records (pipe-delimited, one per line):
      POI|id|tf|side|zlow|zhigh|state
      SWEEP|poi_id|side|price|atr_mult
      SEEK|poi_id|state|posture
      PLAN|poi_id|entry|sl|tp

Input is the accepted L1 structure snapshot dict
(``smc.live.structure_console.build_structure_snapshot``): ``pois``
(id/tf/direction/zone_low/zone_high/armed/state/posture), ``sweeps``
(poi_id/side/magnitude_atr), ``plan`` (poi_id/entry/sl/tp).

**Documented derivation (sweep price):** the sweep LINK in the snapshot
carries side + magnitude only — no price (an honest empty kept from the
L1 design). Like the accepted marker writer
(``smc.live.marker_writer.snapshot_to_records``), the SWEEP record's
price is therefore the linked POI's zone extreme on the swept side;
absent either half → no SWEEP record. Never invented.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from pathlib import Path

from smc.live.heartbeat_path import terminal_dir

logger = logging.getLogger(__name__)

__all__ = [
    "STRUCTURE_DRAW_FILENAME",
    "SCHEMA_LINE",
    "MAX_ZONES",
    "StructureDrawPublisher",
    "resolve_structure_draw_path",
]

#: File the EA reads with its default ``InpFileName`` (MQL5/Files sandbox).
STRUCTURE_DRAW_FILENAME = "smc_structure_draw.txt"

SCHEMA_LINE = "SMC_STRUCTURE_DRAW v1"

#: Chart readability cap (design lock §2): at most this many POI records.
MAX_ZONES = 40

#: Console section order = draw priority order (weekly context first).
_SECTION_ORDER = ("W1", "D1", "H4", "H1")

_FILES_SUBDIR = Path("MQL5") / "Files"


def _safe_id(raw) -> str:
    """Object-name-safe id: anything outside ``[A-Za-z0-9_-]`` → ``_``."""
    text = str(raw or "")
    out = "".join(ch if (ch.isalnum() and ch.isascii()) or ch in "_-" else "_"
                  for ch in text)
    return out or "na"


def _num(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v == v else None          # NaN → None


def _fmt(value, digits: int = 2) -> str:
    v = _num(value)
    return "0" if v is None else f"{v:.{digits}f}"


def _side_text(direction) -> str:
    d = str(direction or "").upper()
    if d.startswith("BULL") or d == "LONG" or d.startswith("LONG"):
        return "BULL"
    if d.startswith("BEAR") or d.startswith("SHORT"):
        return "BEAR"
    return ""


def _zone_rank(tf) -> int:
    name = str(tf or "").upper()
    order = {name: i for i, name in enumerate(_SECTION_ORDER)}
    return order.get(name, len(_SECTION_ORDER))


# ---------------------------------------------------------------------- #
# Path resolution (same policy order as the heartbeat)                    #
# ---------------------------------------------------------------------- #
def resolve_structure_draw_path(
    terminal_path: str | None,
    terminal_data_path: str | None = None,
    explicit_path: str | None = None,
    default_fallback: str | None = None,
) -> Path:
    """Best EA-readable path for the draw file, policy-ordered.

    1. ``terminal_data_path`` (live ``terminal_info().data_path``) — the
       EA's actual sandbox; authoritative when available.
    2. Else ``<terminal_dir>/MQL5/Files/`` from ``terminal_path`` if
       parseable (portable terminals).
    3. Else ``explicit_path``.
    4. Else ``default_fallback`` (caller typically passes the session
       log dir) — the EA may not see it; the operator logs that.
    """
    if terminal_data_path:
        dp = Path(str(terminal_data_path).strip())
        if dp.name:
            return dp.resolve(strict=False) / _FILES_SUBDIR / STRUCTURE_DRAW_FILENAME
    td = terminal_dir(terminal_path) if terminal_path else None
    if td is not None:
        return td / _FILES_SUBDIR / STRUCTURE_DRAW_FILENAME
    if explicit_path:
        return Path(str(explicit_path).strip())
    return Path(str(default_fallback) if default_fallback else STRUCTURE_DRAW_FILENAME)


# ---------------------------------------------------------------------- #
# Atomic text write (mirrors smc.live.heartbeat.write_heartbeat strategy) #
# ---------------------------------------------------------------------- #
def _atomic_write_text(target: Path, text: str, *, attempts: int = 5,
                       backoff_seconds: float = 0.02) -> None:
    """Write-temp + ``os.replace`` (retried) with an in-place fallback.

    Same Windows-coexistence reasoning as the heartbeat/marker writers:
    the EA opens the file briefly each 1 s tick, an overlapping read can
    trip the rename with a transient sharing violation, so after the
    retry budget the write degrades to an in-place overwrite (write
    sharing only) — the EA then re-reads whatever is on disk next tick.
    """
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text, encoding="ascii", newline="")
    last_exc: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            os.replace(tmp, target)
            return
        except OSError as exc:
            last_exc = exc
            if attempt < attempts:
                time.sleep(max(0.0, backoff_seconds))
    # In-place fallback (needs write sharing, not delete sharing) — the
    # stale tmp is deliberately discarded, the target itself is rewritten.
    try:
        data = text.encode("ascii")
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
        fd = os.open(target, flags, 0o644)
        try:
            os.write(fd, data)
            os.ftruncate(fd, len(data))
        finally:
            os.close(fd)
    except OSError:
        raise last_exc  # the original renaming failure is the honest error


# ---------------------------------------------------------------------- #
# Record builder (pure)                                                   #
# ---------------------------------------------------------------------- #
def build_structure_draw_payload(
    snapshot: dict | None,
    *,
    symbol: str,
    now: datetime | None = None,
    max_zones: int = MAX_ZONES,
) -> str:
    """Full schema-v1 payload from an L1 structure snapshot (pure).

    Empty/None snapshot → header-only payload: the EA's record loop then
    sees zero records and clears its prefix objects (fail-safe "the
    chart says nothing rather than showing old state").
    """
    snapshot = snapshot or {}
    stamp = (now or datetime.utcnow()).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [SCHEMA_LINE, f"ts_utc={stamp} symbol={str(symbol or '').strip()}"]

    pois_out = snapshot.get("pois") or []
    # Cap: armed first, then console section order (W1 → D1 → H4 → H1).
    armed = [r for r in pois_out if (r or {}).get("armed")]
    unarmed = [r for r in pois_out if not (r or {}).get("armed")]
    armed.sort(key=lambda r: _zone_rank((r or {}).get("tf")))
    unarmed.sort(key=lambda r: _zone_rank((r or {}).get("tf")))
    capped = (armed + unarmed)[:max(0, max_zones)]
    kept_ids = set()

    by_id: dict = {}
    for row in capped:
        low, high = _num((row or {}).get("zone_low")), _num((row or {}).get("zone_high"))
        poi_id = _safe_id((row or {}).get("id") or "")
        if not poi_id or low is None or high is None or not _side_text((row or {}).get("direction")):
            continue
        kept_ids.add(poi_id)
        by_id[poi_id] = row
        state_txt = "ARMED" if (row or {}).get("armed") else "UNARMED"
        lines.append(
            f"POI|{poi_id}|{str((row or {}).get('tf') or '').upper()}|"
            f"{_side_text((row or {}).get('direction'))}|"
            f"{_fmt(low, 5)}|{_fmt(high, 5)}|{state_txt}"
        )

    # SWEEP — linked POI's swept-side zone edge (documented derivation).
    for sw in (snapshot.get("sweeps") or []):
        sw = sw or {}
        poi_id = _safe_id(sw.get("poi_id") or "")
        if poi_id not in kept_ids:
            continue                        # only capped/armed book is drawn
        side_raw = str(sw.get("side") or "").upper()
        side = "SELL" if side_raw.startswith("SELL") else ("BUY" if side_raw.startswith("BUY") else "")
        if not side:
            continue
        linked = by_id.get(poi_id) or {}
        level = _num(linked.get("zone_high")) if side == "SELL" else _num(linked.get("zone_low"))
        mag = _num(sw.get("magnitude_atr"))
        if level is None:
            continue                        # never invented
        lines.append(
            f"SWEEP|{poi_id}|{side}|{_fmt(level, 5)}|"
            + ("n/a" if mag is None else f"{mag:.2f}")
        )

    # SEEK — armed POIs with their §5 state/posture.
    for polyline in capped:
        if polyline.get("armed"):
            poi_id = _safe_id(polyline.get("id") or "")
            state = str(polyline.get("state") or "n/a")
            posture = str(polyline.get("posture") or "n/a").replace("|", " ")
            lines.append(f"SEEK|{poi_id}|{state}|{posture}")

    # PLAN — routed candidate levels only when ALL THREE exist.
    for pl in (snapshot.get("plan") or [])[:4]:
        pl = pl or {}
        poi_id = _safe_id(pl.get("poi_id") or "")
        entry, sl, tp = _num(pl.get("entry")), _num(pl.get("sl")), _num(pl.get("tp"))
        if not poi_id or entry is None or sl is None or tp is None:
            continue                        # omit if unknown (no invention)
        lines.append(f"PLAN|{poi_id}|{_fmt(entry, 5)}|{_fmt(sl, 5)}|{_fmt(tp, 5)}")

    return "".join(line + "\n" for line in lines)


# ---------------------------------------------------------------------- #
# Publisher (session-facing; fail-safe — never raises to the session)     #
# ---------------------------------------------------------------------- #
class StructureDrawPublisher:
    """Full-snapshot publisher for ``smc_structure_draw.txt``.

    Failure → logged, returns ``False``; NEVER an exception into the
    session (mirrors ``MarkerWriter`` fail-safety). Publishes are
    whole-file rewrites — a stale file refreshes fully on the next
    publish, and a stopped operator leaves the EA's ``InpMaxAgeSec``
    staleness rule to clear the chart.
    """

    def __init__(self, path, *, replace_attempts: int = 5,
                 backoff_seconds: float = 0.02) -> None:
        self.path = Path(path)
        self.last_payload: str | None = None
        self.last_published_utc: str | None = None
        self._replace_attempts = replace_attempts
        self._backoff_seconds = backoff_seconds

    def publish(self, snapshot: dict | None, *, symbol: str,
                now: datetime | None = None, max_zones: int = MAX_ZONES) -> bool:
        """Atomically rewrite the draw file from ``snapshot`` (full rewrite)."""
        suffix = symbol or ""
        payload = ""
        try:
            payload = build_structure_draw_payload(
                snapshot, symbol=symbol, now=now, max_zones=max_zones)
        except Exception as exc:            # noqa: BLE001 — never fatal
            logger.error(
                "STRUCTURE DRAW payload build failed path=%s error=%r",
                self.path, exc, exc_info=True)
            return False
        try:
            # Self-sufficient parent creation: an explicit structure_draw_path
            # config may point to a directory no other component made first.
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(self.path, payload,
                               attempts=self._replace_attempts,
                               backoff_seconds=self._backoff_seconds)
        except OSError as exc:
            logger.error(
                "STRUCTURE DRAW write failed path=%s python_pid=%s error=%r",
                self.path, os.getpid(), exc, exc_info=True)
            return False
        self.last_payload = payload
        self.last_published_utc = payload.splitlines()[1] if "\n" in payload else None
        logger.debug(
            "STRUCTURE DRAW published path=%s symbol=%s bytes=%d",
            self.path, suffix, len(payload))
        return True
