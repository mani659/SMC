"""Console judgement board (design lock 00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md §3).

A pure renderer over an operator-supplied snapshot — same discipline as the
L1 ``structure_console`` (read-only, live data never hardcoded, honest
empties, ASCII-only). The board is SUPERSET of the §3.2 block order:

    MODE        A, or A + the exact Mode T banner line (§2.1)
    POIS        per-TF counts + the armed POIs' plain-language zones
    SWEEPS      last/active per armed POI or an honest ``none``
    SEEKING     poi_id + §5 state + posture (+ trigger letter) or ``none``
    JUDGEMENT   one line per live workflow (ENTER/SKIP + taxonomy reason)
    BOOK        open positions / pendings, product first, mode=T tagged
    HEARTBEAT   seq / age / EA-path readability hint

Forbidden (restated from note §3.3): fill-only status, raw tracebacks as
status, invented desirability text. Judgement content comes ONLY from the
read-only structure snapshot + the Mode T decision records handed in.
"""

from __future__ import annotations

from datetime import datetime

__all__ = ["judge_interval_used", "render_judgement_board"]

_RULE = "=" * 72
_SUBRULE = "-" * 72


def judge_interval_used(judge_interval_s) -> bool:
    """Whether the flat-guarantee judge cadence is active (``0`` = off)."""
    try:
        return float(judge_interval_s) > 0
    except (TypeError, ValueError):
        return False


def _short(value) -> str:
    return "n/a" if not value else str(value)[:8]


def _fmt_price(value) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _fmt_zone(low, high) -> str:
    if low is None and high is None:
        return "n/a"
    return f"{_fmt_price(low)}-{_fmt_price(high)}"


def render_judgement_board(
    *,
    now_utc: str,
    mode: str,
    mode_t_banner: str | None,
    structure: dict | None,
    mode_t_events: list[dict],
    book_product_positions: int | None,
    book_product_pendings: int | None,
    book_mode_t_positions: int | None,
    book_mode_t_pendings: int | None,
    hb_seq,
    hb_age_s,
    hb_state,
) -> str:
    """Render ONE judgement board (pure; ASCII only)."""
    lines: list[str] = []
    push = lines.append
    structure = structure or {}

    push(_RULE)
    # --- MODE block --------------------------------------------------- #
    push(" MODE")
    push(f"   {str(mode or 'A')}")
    if mode_t_banner:
        push(f"   {mode_t_banner}")
    push(_SUBRULE)

    # --- POIS block ---------------------------------------------------- #
    rows = structure.get("pois") or []
    push(" POIS")
    by_tf: dict[str, int] = {}
    armed_rows = []
    for row in rows:
        tf = str(row.get("tf") or "?")
        by_tf[tf] = by_tf.get(tf, 0) + 1
        if row.get("armed"):
            armed_rows.append(row)
    parts = [f"{tf} {n}" for tf, n in sorted(by_tf.items())]
    push("   counts: " + (" ".join(parts) if parts else "(none)"))
    if armed_rows:
        for row in armed_rows:
            push(
                f"   {_short(row.get('tf')):<3}"
                f" {str(row.get('direction') or 'n/a'):<5}"
                f" {str(row.get('kind') or 'n/a'):<16}"
                f" {_fmt_zone(row.get('zone_low'), row.get('zone_high')):<20}"
                f" id={row.get('id_short') or 'n/a'}"
            )
    else:
        push("   (no armed POIs)")
    push(_SUBRULE)

    # --- SWEEPS block --------------------------------------------------- #
    push(" SWEEPS")
    sweeps = structure.get("sweeps") or []
    if not sweeps:
        push("   SWEEPS: none")
    else:
        for row in sweeps:
            mag = row.get("magnitude_atr")
            mag_txt = "n/a" if mag is None else f"{mag:.2f}x ATR"
            push(
                f"   {str(row.get('tf') or 'n/a'):<3}"
                f" side={str(row.get('side') or 'n/a'):<5}"
                f" {mag_txt:<12} -> poi {row.get('id_short') or 'n/a'}"
            )
    push(_SUBRULE)

    # --- SEEKING block --------------------------------------------------- #
    push(" SEEKING")
    if not armed_rows:
        push("   SEEKING: none")
    else:
        for row in armed_rows:
            push(
                f"   {row.get('id_short') or 'n/a'}"
                f"  {str(row.get('tf') or 'n/a'):<3}"
                f" state={row.get('state') or 'n/a'}"
                f" posture={row.get('posture') or 'n/a'}"
                f" trigger={row.get('trigger') or '-'}"
            )
    push(_SUBRULE)

    # --- JUDGEMENT block -------------------------------------------------- #
    push(" JUDGEMENT")
    if mode_t_events:
        for ev in mode_t_events:
            push(f"   {str(ev)}")
    else:
        push("   JUDGEMENT: flat (no armed POI · no workflow · idle)")
    push(_SUBRULE)

    # --- BOOK block -------------------------------------------------------- #
    product_positions = (
        book_product_positions if book_product_positions is not None else 0
    )
    product_pendings = (
        book_product_pendings if book_product_pendings is not None else 0
    )
    mode_t_positions = (
        book_mode_t_positions if book_mode_t_positions is not None else 0
    )
    mode_t_pendings = (
        book_mode_t_pendings if book_mode_t_pendings is not None else 0
    )
    push(" BOOK")
    push(
        f"   product: positions {product_positions}"
        f"  pendings {product_pendings}"
    )
    push(
        f"   mode=T : positions {mode_t_positions}"
        f"  pendings {mode_t_pendings}"
    )
    push(_SUBRULE)

    # --- HEARTBEAT ---------------------------------------------------------- #
    push(" HEARTBEAT")
    hb_age_txt = (
        f"{hb_age_s:.1f}s" if isinstance(hb_age_s, (int, float)) else "n/a"
    )
    push(
        f"   seq {_short(hb_seq)}  age {hb_age_txt}  state {_short(hb_state)}"
    )
    push(_RULE)
    header = f" JUDGEMENT BOARD  |  {now_utc or 'n/a'} UTC"
    return header + "\n" + "\n".join(lines)
