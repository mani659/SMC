"""Chart-marker snapshot writer (design lock 00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md §4).

Python side of the marker contract: a FULL CSV snapshot rewritten atomically
(write-temp + ``os.replace`` retry, the heartbeat publisher's strategy) in the
SAME EA-readable directory discipline as the heartbeat. The MQL5 Safety
Watchdog reads the file on its 1 s timer and draws/deletes ``SMC_*`` chart
objects — markers never influence any safety or trading decision.

Schema (note §4.2, NORMATIVE — header row + one record per line)::

    id,symbol,kind,direction,price_high,price_low,timeframe_label,text,color_role,updated_at_utc,ephemeral

Draw caps (note §4.3): at most 11 objects — ≤ 8 armed POI zone rectangles,
ONE sweep line, ONE Mode T entry line, ONE corner label row. The writer
builds that on its own; callers hand it the snapshot + Mode T info only.

Failure policy (note §4.4): a marker write failure is logged and SKIPPED —
the EA clears the chart after the staleness timeout and the safety path is
untouched. Marker failure can never disable safety; conversely markers can
never fail a live session that works.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "MARKER_FILENAME",
    "MARKER_HEADER",
    "MAX_POI_MARKERS",
    "MAX_MARKER_OBJECTS",
    "MARKER_STALE_SECONDS",
    "MarkerRecord",
    "MarkerWriter",
    "snapshot_to_records",
]

logger = logging.getLogger(__name__)

MARKER_FILENAME = "smc_markers.csv"
MARKER_HEADER = (
    "id,symbol,kind,direction,price_high,price_low,timeframe_label,"
    "text,color_role,updated_at_utc,ephemeral"
)

# Draw caps (note §4.3 — frozen; the EA ignores anything beyond its own caps).
MAX_POI_MARKERS = 8
MAX_MARKER_OBJECTS = 11         # 8 zones + 1 sweep + 1 entry_t + 1 label
# Mirrors the EA side stale budget (note §4.4; also mode_t.MARKER_EOL_SECONDS).
MARKER_STALE_SECONDS = 30

_VALID_KINDS = frozenset({"poi", "sweep", "entry_t", "label"})
_VALID_DIRECTIONS = frozenset({"BULL", "BEAR", "SELL", "BUY", "NONE"})
_VALID_COLOR_ROLES = frozenset(
    {"bull_green", "bear_red", "mode_T_orange", "label_gray", "stale_red"}
)


@dataclass(frozen=True, slots=True)
class MarkerRecord:
    """One CSV marker row (validated shape; setters pre-format)."""

    id: str
    symbol: str
    kind: str
    direction: str
    price_high: float
    price_low: float
    timeframe_label: str
    text: str
    color_role: str
    updated_at_utc: str
    ephemeral: bool

    def to_csv_row(self) -> str:
        """CSV line — commas inside ``text`` are stripped (schema safety)."""
        text = str(self.text).replace(",", ";")
        return ",".join([
            str(self.id).replace(",", ";"),
            str(self.symbol),
            str(self.kind),
            str(self.direction),
            f"{float(self.price_high) if self.price_high is not None else 0.0:.2f}",
            f"{float(self.price_low) if self.price_low is not None else 0.0:.2f}",
            str(self.timeframe_label),
            text,
            str(self.color_role),
            str(self.updated_at_utc),
            "true" if self.ephemeral else "false",
        ])


def _num(value) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        out = 0.0
    return out


# ---------------------------------------------------------------------- #
# Snapshot → ≤11 records (build once; pure)
# ---------------------------------------------------------------------- #
def snapshot_to_records(
    *,
    symbol: str,
    structure: dict | None,
    mode: str,
    heartbeat_ok: bool,
    mode_t_poi: dict | None,
    updated_at_utc: str,
) -> list[MarkerRecord]:
    """Build the ≤11-row marker snapshot from authenticated inputs only.

    ``structure`` is the L1 read-only snapshot dict (POIS/SWEEPS). ``mode``
    is ``"A"`` or ``"T"``; ``heartbeat_ok`` False → the corner label reads
    ``HEARTBEAT STALE`` (safety information, never suppressed by markers).
    ``mode_t_poi`` is ``{poi_id, direction, entry, text}`` for the ONE entry
    line when a Mode T decision exists this cycle; ``None`` → none.
    """
    structure = structure or {}
    records: list[MarkerRecord] = []
    zone_text = str(mode or "A")
    label_text = (
        "HEARTBEAT STALE" if not heartbeat_ok else f"SMC Mode {zone_text}"
    )
    label_role = "stale_red" if not heartbeat_ok else (
        "mode_T_orange" if str(mode).upper() == "T" else "label_gray"
    )

    # ≤8 armed POI zones — armed rows only, newest-first from the snapshot.
    for row in (structure.get("pois") or [])[:MAX_POI_MARKERS]:
        if not row.get("armed"):
            continue
        high, low = _num(row.get("zone_high")), _num(row.get("zone_low"))
        if high == 0.0 and low == 0.0:
            continue
        direction = "BULL" if str(row.get("direction", "")).upper().startswith("BULL") else "BEAR"
        records.append(MarkerRecord(
            id=f"zone_{row.get('id_short') or 'na'}",
            symbol=symbol,
            kind="poi",
            direction=direction,
            price_high=high,
            price_low=low,
            timeframe_label=str(row.get("tf") or ""),
            text=f"{row.get('tf') or ''} {row.get('kind') or ''} armed".strip(),
            color_role="bull_green" if direction == "BULL" else "bear_red",
            updated_at_utc=updated_at_utc,
            ephemeral=False,
        ))
        if len(records) >= MAX_MARKER_OBJECTS - 3:   # keep sweep+entry+label room
            break

    # ONE sweep line (the snapshot's last sweep of any armed POI). The
    # sweep link itself carries NO price (side + magnitude only — honest
    # empties), so the sweep LEVEL is the linked armed POI's zone extreme
    # on the swept side; absent either half → no sweep marker (never
    # invented; the design's sweep line is optional, note §4.3).
    sweeps = structure.get("sweeps") or []
    pois_by_id = {
        row.get("id"): row for row in (structure.get("pois") or [])
    }
    if sweeps:
        last = sweeps[-1] if isinstance(sweeps[-1], dict) else {}
        linked = pois_by_id.get(last.get("poi_id")) or {}
        side = str(last.get("side") or "").upper()
        level = (
            _num(linked.get("zone_high")) if side.startswith("SELL")
            else (_num(linked.get("zone_low")) if side.startswith("BUY") else 0.0)
        )
        if last.get("poi_id") and level:
            records.append(MarkerRecord(
                id=f"sweep_{str(last.get('id_short') or 'na')}",
                symbol=symbol,
                kind="sweep",
                direction="SELL" if str(last.get("side", "")).upper().startswith("SELL") else "BUY",
                price_high=level,
                price_low=level,
                timeframe_label=str(last.get("tf") or ""),
                text="sweep last",
                color_role="bear_red",
                updated_at_utc=updated_at_utc,
                ephemeral=False,
            ))

    # ONE Mode T entry line (observations only — never invented).
    if mode_t_poi:
        entry = mode_t_poi.get("entry")
        if entry is not None:
            try:
                entry_value = float(entry)
            except (TypeError, ValueError):
                entry_value = None
            else:
                records.append(MarkerRecord(
                        id=f"entry_t_{str(mode_t_poi.get('poi_id') or 'na')[:8]}",
                        symbol=symbol,
                        kind="entry_t",
                        direction="BUY" if str(mode_t_poi.get("direction", "")).upper().startswith("BUY") else "SELL",
                        price_high=entry_value,
                        price_low=entry_value,
                        timeframe_label="M5",
                        text=str(mode_t_poi.get("text") or "Mode T entry").replace(",", ";"),
                        color_role="mode_T_orange",
                        updated_at_utc=updated_at_utc,
                        ephemeral=False,
                    ))

    # ONE corner label (always — screen-anchored; prices are 0.0 placeholders
    # the EA anchors in corner XY, never on price).
    records.append(MarkerRecord(
        id="label_session",
        symbol=symbol,
        kind="label",
        direction="NONE",
        price_high=0.0,
        price_low=0.0,
        timeframe_label="",
        text=label_text,
        color_role=label_role,
        updated_at_utc=updated_at_utc,
        ephemeral=False,
    ))
    return records[:MAX_MARKER_OBJECTS]


# ---------------------------------------------------------------------- #
# Writer (atomic, same Windows-coexistence strategy as the heartbeat)
# ---------------------------------------------------------------------- #
class MarkerWriter:
    """Full-snapshot CSV writer: write-temp + atomic replace with a small
    retry budget (mirrors ``smc.live.heartbeat.write_heartbeat``). Failure
    → logged, returns False; NEVER an exception to the session (§4.4)."""

    def __init__(self, path, *, replace_attempts: int = 5,
                 backoff_seconds: float = 0.02) -> None:
        self.path = Path(path)
        self._replace_attempts = replace_attempts
        self._backoff_seconds = backoff_seconds

    def write(self, records: list[MarkerRecord]) -> bool:
        rows = [MARKER_HEADER]
        rows.extend(record.to_csv_row() for record in records[:MAX_MARKER_OBJECTS])
        payload = "\n".join(rows) + "\n"
        target = self.path
        tmp = target.with_name(target.name + ".tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(payload, encoding="utf-8")
            import os
            import time as _time
            last_exc: Exception | None = None
            for _ in range(self._replace_attempts):
                try:
                    os.replace(tmp, target)
                    last_exc = None
                    break
                except OSError as exc:
                    last_exc = exc
                    _time.sleep(self._backoff_seconds)
            if last_exc is not None:
                # In-place overwrite needs only write-sharing (heartbeat
                # strategy step 3) — survives a read lock that blocks rename.
                with target.open("w", encoding="utf-8") as handle:
                    handle.write(payload)
                import os as _os
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
                return True
            return True
        except OSError as exc:
            logger.warning(
                "MARKER WRITE FAILED target=%s temp=%s error=%r",
                target, tmp, exc,
            )
            return False
