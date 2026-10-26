"""Milestone L1 — live structure console (pure snapshot builder + renderer).

Operator command-prompt view of the LIVE structure state, in four sections:

    POIS    — Weekly / Daily / H4 / H1 armed POIs: direction, kind,
              zone_low-high, armed yes/no, short id (W1 first: the weekly
              provisioning directive's operator must-have).
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

from datetime import datetime

__all__ = [
    "SECTION_ORDER",
    "build_structure_snapshot",
    "render_structure_console",
]

#: POIS display order — weekly context first (provisioning directive).
SECTION_ORDER = ("W1", "D1", "H4", "H1")

_RULE = "=" * 72
_SUBRULE = "-" * 72


def _short(poi_id) -> str:
    """Short id for the console (first 8 chars, ``n/a`` when unknown)."""
    if not poi_id:
        return "n/a"
    return str(poi_id)[:8]


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


def build_structure_snapshot(*, engine, adapter=None, sweeps=None,
                             now: datetime | None = None) -> dict:
    """Read-only snapshot of the live structure state (no MT5, no mutation).

    ``engine`` supplies the armed-POI book + §5 state, ``adapter`` the
    routed workflows (optional — absence simply means no SEEKING trigger
    letters and ``PLAN: none``), ``sweeps`` the loop's cumulative
    sweep-link map (POI id → ``{"side", "magnitude_atr", ...}``).
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

    return {"now": now, "pois": pois, "sweeps": sweep_rows, "plan": plan}


def _fmt_price(value) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _fmt_zone(low, high) -> str:
    if low is None and high is None:
        return "n/a"
    return f"{_fmt_price(low)}-{_fmt_price(high)}"


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

    # --- POIS --------------------------------------------------------- #
    push(" POIS")
    rows = snapshot.get("pois") or []
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
