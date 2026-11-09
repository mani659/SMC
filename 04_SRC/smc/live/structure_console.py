"""Milestone L1 — live structure console (pure snapshot builder + renderer).

Operator command-prompt view of the LIVE structure state, in four sections:

    STRUCTURE SCAN — Console V2 (2026-11-02): merged detector geometry per
              detection TF BEFORE the locked pillar definition. CANDIDATES
              only: never armed, never routed, never tradeable, never a
              "POI"/"signal"/"entry". Sourced read-only from the batch
              report's ``scan`` rows (capped per TF).
    ARMED POI — Weekly / Daily / H4 / H1 ARMED POIs: direction, kind,
              zone_low-high, armed yes/no, short id (W1 first: the weekly
              provisioning directive's operator must-have). Locked
              definition only.
    SWEEPS  — the liquidity sweep linked to each armed POI (POI + TF +
              side) or an honest ``none``.
    SEEKING — armed POIs with their §5 state / arm posture and the trigger
              letter they are currently targeting (when a route exists).
    PLAN    — the routed candidate's direction / entry / SL / TP /
              tp_source / trigger / POI id, or ``PLAN: none``.

Design rules (directive 2026-10-06, milestone L1):

* **Read-only snapshot + render.** The builder only READS engine/adapter
  state (``tracked_pois`` / ``episode`` / ``state_machine.current`` /
  ``active_workflows``) and the loop's sweep links. It mutates nothing,
  re-derives no detection, and cannot influence a trading decision.
* **Live data, never hardcoded.** Every rendered value comes from the
  snapshot handed in — the tests pin that the W1 row carries the actual
  weekly zone numbers.
* **Honest empties.** A timeframe with zero armed POIs prints an empty
  section; missing sweeps print ``SWEEPS: none``.
* **Not an MT5 chart dashboard.** Text only, ASCII only (Windows console
  code page cannot be relied on for box-drawing glyphs).
* **Cadence** is the caller's (operator session): refresh on a new
  execution bar and/or HTF batch, rate-limited for readability.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

__all__ = [
    "SECTION_ORDER",
    "RESEARCH_SLICE_ACTIVE_STATUS_NAMES",
    "build_dumb_mtf_snapshot",
    "build_research_h4_zone_book_snapshot",
    "build_structure_snapshot",
    "render_structure_console",
]

#: POIS display order — weekly context first (provisioning directive).
SECTION_ORDER = ("W1", "D1", "H4", "H1")

#: Section rules used by the renderer (ASCII only — Windows console code page).
_RULE = "=" * 72
_SUBRULE = "-" * 72

#: Research slice episode statuses that count as live (non-terminal) for the
#: console ``armed`` annotation. NAME strings only — this module stays
#: agnostic of the slice package (display must not couple to strategy code).
RESEARCH_SLICE_ACTIVE_STATUS_NAMES = ("IN_ZONE_PRIMARY", "BOUNDARY_FALLBACK", "WON")

#: POIS display order — weekly context first (provisioning directive).
def _short(poi_id) -> str:
    """Short id for the console (first 8 chars, ``n/a`` when unknown)."""
    if not poi_id:
        return "n/a"
    return str(poi_id)[:8]


def _zone_book_short(poi_id) -> str:
    """Neutral short display id for the research H4 zone book (Console V2).

    Slice poi ids carry internal package prefixes that must never render on
    the product surface, so the display layer derives a STABLE neutral id:
    ``zb-`` + an 8-hex digest of the full internal id. Internal strings are
    untouched (the full ``poi_id`` stays in the snapshot ``id`` field).
    """
    if not poi_id:
        return "n/a"
    digest = hashlib.sha1(str(poi_id).encode("utf-8")).hexdigest()[:8]
    return f"zb-{digest}"


def _name(value) -> str | None:
    """Enum/str name helper — ``None`` stays ``None`` (never invented)."""
    if value is None:
        return None
    return getattr(value, "name", None) or str(value)


def _letter(value) -> str | None:
    """Trigger LETTER (``TriggerType.value``: A…F), never the enum name.

    Falls back to the string form for duck-typed candidates; ``None``
    stays ``None`` (no route yet — nothing invented).
    """
    if value is None:
        return None
    letter = getattr(value, "value", None)
    if isinstance(letter, str) and letter:
        return letter
    return str(value)


def _num(value):
    """Finite float or ``None`` (non-numeric input degrades to None)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_field(row, key):
    """Read one scan-row field from a dict or a duck-typed object."""
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _scan_rows(scan) -> list[dict]:
    """Normalize the runtime's read-only SCAN rows (dicts; never mutated).

    A scan row is a CANDIDATE: detector geometry that has NOT passed the
    locked pillar definition. Nothing here is armed, routed or tradeable.
    """
    rows: list[dict] = []
    for row in scan or []:
        rows.append({
            "tf": _row_field(row, "tf"),
            "direction": _row_field(row, "direction"),
            "kind": _row_field(row, "kind"),
            "zone_low": _num(_row_field(row, "zone_low")),
            "zone_high": _num(_row_field(row, "zone_high")),
            "mid": _num(_row_field(row, "mid")),
            "created_at": _row_field(row, "created_at"),
        })
    return rows


def build_structure_snapshot(*, engine, adapter=None, sweeps=None,
                             scan=None, now: datetime | None = None) -> dict:
    """Read-only snapshot of the live structure state (no MT5, no mutation).

    ``engine`` supplies the armed-POI book + §5 state, ``adapter`` the
    routed workflows (optional — absence simply means no SEEKING trigger
    letters and ``PLAN: none``), ``sweeps`` the loop's cumulative
    sweep-link map (POI id → ``{"side", "magnitude_atr", ...}``), and
    ``scan`` the batch report's read-only candidate rows (Console V2).

    Every input is READ; the builder never arms, places, routes or mutates
    a POI/zone field. ``scan`` rows stay in their own key so no consumer
    can mistake them for the armed book.
    """
    pois: list[dict] = []
    tracked = list(engine.tracked_pois()) if engine is not None else []
    machine = getattr(engine, "state_machine", None) if engine is not None else None
    for poi in tracked:
        zone = getattr(poi, "zone", None)
        episode = engine.episode(poi) if engine is not None else None
        state = None
        if machine is not None:
            try:
                state = machine.current(poi)
            except Exception:            # noqa: BLE001 — display never raises
                state = None
        kind = getattr(poi, "m8_kind", None)
        if not kind:
            tags = [getattr(m, "name", str(m)) for m in (getattr(poi, "models", None) or [])]
            kind = ",".join(tags) or None
        pois.append({
            "id": getattr(poi, "id", None),
            "id_short": _short(getattr(poi, "id", None)),
            "tf": _name(getattr(zone, "timeframe", None)),
            "direction": _name(getattr(zone, "direction", None)),
            "kind": kind,
            "zone_low": _num(getattr(zone, "bottom", None)),
            "zone_high": _num(getattr(zone, "top", None)),
            "armed": episode is not None,
            "state": _name(state),
            "posture": _name(getattr(episode, "posture", None)),
            "arm_bar": getattr(episode, "arm_bar", None),
            "trigger": None,
        })

    workflows: dict = {}
    if adapter is not None:
        getter = getattr(adapter, "active_workflows", None)
        if callable(getter):
            try:
                workflows = dict(getter() or {})
            except Exception:            # noqa: BLE001 — display never raises
                workflows = {}

    by_id = {row["id"]: row for row in pois}
    for poi_id, candidate in workflows.items():
        row = by_id.get(poi_id)
        if row is not None:
            row["trigger"] = _letter(getattr(candidate, "trigger", None))

    sweep_rows: list[dict] = []
    for poi_id, info in (sweeps or {}).items():
        row = by_id.get(poi_id)
        if row is None:
            continue                      # only the CURRENT armed book
        info = info or {}
        sweep_rows.append({
            "poi_id": poi_id,
            "id_short": _short(poi_id),
            "tf": row["tf"],
            "side": info.get("side"),
            "magnitude_atr": _num(info.get("magnitude_atr")),
        })

    plan: list[dict] = []
    for poi_id, candidate in workflows.items():
        plan.append({
            "poi_id": poi_id,
            "id_short": _short(poi_id),
            "direction": _name(getattr(candidate, "direction", None)),
            "entry": _num(getattr(candidate, "entry_price", None)),
            "sl": _num(getattr(candidate, "sl_price", None)),
            "tp": _num(getattr(candidate, "tp_price", None)),
            "tp_source": getattr(candidate, "tp_source", None),
            "trigger": _letter(getattr(candidate, "trigger", None)),
        })

    armed_by_tf: dict[str, int] = {}
    for row in pois:
        if row.get("armed"):
            tf_name = str(row.get("tf") or "?")
            armed_by_tf[tf_name] = armed_by_tf.get(tf_name, 0) + 1

    return {
        "now": now,
        "pois": pois,
        "sweeps": sweep_rows,
        "plan": plan,
        "scan": _scan_rows(scan),
        "armed_by_tf": armed_by_tf,
    }


def build_dumb_mtf_snapshot(*, feed=None, machine=None,
                            now: datetime | None = None,
                            mode_note: str | None = None) -> dict:
    """Console V2 MTF-slice snapshot (display-only, read-only).

    Same contract and shape as :func:`build_research_h4_zone_book_snapshot`
    — the zone book is the slice's own read-only inventory annotated with its
    episode machine's status; CANDIDATES only, never armed/routed/tradeable by
    this builder. Kept as a named entry point because the dedicated slice
    console and its tests call it directly.
    """
    return build_research_h4_zone_book_snapshot(
        feed=feed, machine=machine, now=now, mode_note=mode_note
    )


def build_research_h4_zone_book_snapshot(*, feed=None, machine=None,
                                         now: datetime | None = None,
                                         mode_note: str | None = None) -> dict:
    """Research H4 zone-book console snapshot (display-only, read-only; V2).

    Research-only slice modes (``research_h4_zone_book``) own NO product
    engine: no batch report, no locked-Pillar armed book — the product
    structure console is structurally absent there (operator finding
    2026-11-02). This builder surfaces the slice's OWN read-only
    inventories in the same snapshot shape, so the bat-started session
    still prints SCAN vs ARMED:

    * ``scan`` — the research H4 zone book: merged detector geometry from
      the read-only M8 H4 scan, REPLACED on every closed H4 slice (exactly
      the batch-scan shape; CANDIDATES only — never armed, never routed,
      never tradeable by this builder).
    * ``pois`` — the same zones annotated with the research slice episode
      status: ``armed=yes`` iff an ACTIVE episode exists on the zone. That
      is the research slice book, NOT the product locked-Pillar engine
      book (the snapshot ``note`` says so verbatim on the board).

    Reads only; never mutates the feed, the machine, or any geometry field;
    never calls arm/confirm/advance/place.
    """
    scan: list[dict] = []
    pois: list[dict] = []

    # Zone-POI index of the research slice's sequential episode machine
    # (read-only).
    by_zone: dict[str, list] = {}
    if machine is not None:
        for episode in dict(getattr(machine, "_episodes", {}) or {}).values():
            key = getattr(episode, "key", None)
            zone_id = str(getattr(key, "poi_id", "") or "")
            if zone_id:
                by_zone.setdefault(zone_id, []).append(episode)

    # Accept either the live feed (attribute ``_h4_pois``) or a plain
    # zone-book dict (tests / research callers); both are READ-ONLY here.
    zone_book = feed
    if not isinstance(feed, dict):
        zone_book = getattr(feed, "_h4_pois", {}) or {}
    for poi_id, poi in dict(zone_book).items():
        zone = getattr(poi, "zone", None)
        if zone is None:
            continue                      # display never invents geometry
        parts = str(poi_id).split("|")
        kind = parts[1] if len(parts) > 1 and parts[1] else "m8"
        base = {
            "id": poi_id,
            "id_short": _zone_book_short(poi_id),
            "tf": _name(getattr(zone, "timeframe", None)),
            "direction": _name(getattr(zone, "direction", None)),
            "kind": kind,
            "zone_low": _num(getattr(zone, "bottom", None)),
            "zone_high": _num(getattr(zone, "top", None)),
        }
        scan.append(dict(base, created_at=None, mid=None))
        episodes = by_zone.get(str(poi_id)) or []
        chosen = None
        for episode in episodes:          # prefer a live status; else newest
            status_name = str(getattr(getattr(episode, "status", None), "name",
                                      getattr(episode, "status", "")))
            if status_name in RESEARCH_SLICE_ACTIVE_STATUS_NAMES:
                chosen = episode
                chosen_status = status_name
                break
        if chosen is None and episodes:
            chosen = max(
                (e for e in episodes),
                key=lambda e: int(getattr(e, "zone_entry_clock_bar", -1) or -1),
            )
            chosen_status = str(getattr(getattr(chosen, "status", None), "name",
                                        getattr(chosen, "status", "")))
        pois.append(dict(
            base,
            armed=bool(chosen_status in RESEARCH_SLICE_ACTIVE_STATUS_NAMES if chosen else False),
            state=chosen_status if chosen else None,
            posture=None,                 # research slice has no §5 postures
            arm_bar=getattr(chosen, "zone_entry_clock_bar", None) if chosen else None,
            trigger=None,                 # slice confirm geometry, not a route
        ))

    armed_by_tf: dict[str, int] = {}
    for row in pois:
        if row.get("armed"):
            tf_name = str(row.get("tf") or "?")
            armed_by_tf[tf_name] = armed_by_tf.get(tf_name, 0) + 1

    return {
        "now": now,
        "note": mode_note,
        "pois": pois,
        "sweeps": [],                     # sweep links are L1/runtime-owned
        "plan": [],                       # slice winners flow via candidates
        "scan": scan,
        "armed_by_tf": armed_by_tf,
    }


def _fmt_price(value) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _fmt_zone(low, high) -> str:
    if low is None and high is None:
        return "n/a"
    return f"{_fmt_price(low)}-{_fmt_price(high)}"


def _scan_time(value) -> str:
    """Compact scan-row timestamp (``n/a`` when absent; never invented)."""
    if value is None:
        return "n/a"
    return str(value)[:16]


def _scan_section_order(rows: list[dict]) -> list[str]:
    """Console TF order for SCAN rows (W1/D1/H4/H1 first, then any others)."""
    present = {str(row.get("tf")) for row in rows if row.get("tf")}
    ordered = [tf for tf in SECTION_ORDER if tf in present]
    ordered.extend(sorted(present - set(ordered)))
    return ordered


def _push_scan_tf(push, tf, section: list[dict]) -> None:
    """One TF's SCAN block: candidate count by kind + capped geometry rows."""
    if not section:
        push(f"   {str(tf):<3}: (none)")
        return
    kinds: dict[str, int] = {}
    for row in section:
        kind = str(row.get("kind") or "other")
        kinds[kind] = kinds.get(kind, 0) + 1
    kind_txt = " | ".join(f"{name} {count}" for name, count in sorted(kinds.items()))
    push(f"   {str(tf):<3}: {len(section)} candidate(s)  {kind_txt}")
    for row in section:
        push(
            f"      {str(row.get('direction') or 'n/a'):<5}"
            f" {str(row.get('kind') or 'n/a'):<14}"
            f" {_fmt_zone(row.get('zone_low'), row.get('zone_high')):<19}"
            f" t={_scan_time(row.get('created_at'))}"
        )


def render_structure_console(snapshot: dict) -> str:
    """Render ONE structure console board from a snapshot dict (pure)."""
    snapshot = snapshot or {}
    lines: list[str] = []
    push = lines.append

    now = snapshot.get("now")
    now_txt = now.isoformat(timespec="seconds") if isinstance(now, datetime) else "n/a"
    armed_total = sum(1 for r in (snapshot.get("pois") or [])
                      if r.get("armed"))
    push(_RULE)
    push(f" STRUCTURE CONSOLE  |  {now_txt} UTC   (read-only snapshot;"
         f" armed {armed_total})")
    push(_RULE)

    note = snapshot.get("note")
    if note:                             # mode clarification (Console V2)
        push(f" {note}")

    rows = snapshot.get("pois") or []

    # --- STRUCTURE SCAN (Console V2: candidates, NOT armed) ------------ #
    # Locked POI definition is deliberately NOT applied here: these rows are
    # raw merged detector geometry for operator orientation only. The
    # wording bans (no "armed"/"POI"/"signal"/"entry") are part of the
    # contract - scan rows are never tradeable and never seek.
    push(" STRUCTURE SCAN  (candidates - NOT armed)")
    push("   Locked POI definition NOT applied - not tradeable / not seeking")
    scan_rows = snapshot.get("scan") or []
    for tf in _scan_section_order(scan_rows):
        _push_scan_tf(push, tf, [r for r in scan_rows if str(r.get("tf")) == tf])
    if not scan_rows:
        push("   (none) - no merged geometry in the last batch")
    push(_SUBRULE)

    # --- ARMED POI (locked definition only) ----------------------------- #
    push(" ARMED POI  (locked definition only)")
    for tf in SECTION_ORDER:
        section = [r for r in rows if r.get("tf") == tf]
        if not section:
            push(f"   {tf:<3}: (none)")
            continue
        for row in section:
            push(
                f"   {tf:<3}: {str(row.get('direction') or 'n/a'):<5}"
                f" {str(row.get('kind') or 'n/a'):<14}"
                f" {_fmt_zone(row.get('zone_low'), row.get('zone_high')):<19}"
                f" armed={'yes' if row.get('armed') else 'no'}"
                f"  state={row.get('state') or 'n/a'}"
                f"  id={row.get('id_short') or 'n/a'}"
            )
    # Armed POIs whose timeframe is outside the four console sections are
    # shown honestly rather than hidden.
    other = [r for r in rows if r.get("tf") not in SECTION_ORDER]
    for row in other:
        push(
            f"   {str(row.get('tf') or '?'):<3}: "
            f"{str(row.get('direction') or 'n/a'):<5}"
            f" {str(row.get('kind') or 'n/a'):<14}"
            f" {_fmt_zone(row.get('zone_low'), row.get('zone_high')):<19}"
            f" armed={'yes' if row.get('armed') else 'no'}"
            f"  state={row.get('state') or 'n/a'}"
            f"  id={row.get('id_short') or 'n/a'}"
        )
    if not rows:
        push("   (no armed POIs)")

    # --- SWEEPS ------------------------------------------------------- #
    push(_SUBRULE)
    push(" SWEEPS")
    sweeps = snapshot.get("sweeps") or []
    if not sweeps:
        push("   SWEEPS: none")
    else:
        for row in sweeps:
            mag = row.get("magnitude_atr")
            mag_txt = "n/a" if mag is None else f"{mag:.2f}x ATR"
            push(
                f"   {str(row.get('tf') or 'n/a'):<3} side={str(row.get('side') or 'n/a'):<5}"
                f" {mag_txt:<12} -> poi {row.get('id_short') or 'n/a'}"
            )

    # --- SEEKING ------------------------------------------------------ #
    push(_SUBRULE)
    push(" SEEKING")
    armed = [r for r in rows if r.get("armed")]
    if not armed:
        push("   SEEKING: none")
    else:
        for row in armed:
            push(
                f"   {row.get('id_short') or 'n/a'}  {str(row.get('tf') or 'n/a'):<3}"
                f" state={row.get('state') or 'n/a':<8}"
                f" posture={row.get('posture') or 'n/a':<16}"
                f" trigger={row.get('trigger') or '-'}"
            )

    # --- PLAN --------------------------------------------------------- #
    push(_SUBRULE)
    push(" PLAN")
    plan = snapshot.get("plan") or []
    if not plan:
        push("   PLAN: none")
    else:
        for row in plan:
            push(
                f"   {str(row.get('direction') or 'n/a'):<5}"
                f" entry={_fmt_price(row.get('entry'))}"
                f"  sl={_fmt_price(row.get('sl'))}"
                f"  tp={_fmt_price(row.get('tp'))}"
                f"  src={row.get('tp_source') or 'n/a'}"
                f"  trig={row.get('trigger') or 'n/a'}"
                f"  poi={row.get('id_short') or 'n/a'}"
            )
    push(_RULE)
    return "\n".join(lines)