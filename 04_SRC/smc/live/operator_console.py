"""Phase D operator pack — live console status board (pure renderer).

An operator-friendly SNAPSHOT renderer, not a spam firehose: the entrypoint
refreshes the console every ``console_refresh_s`` seconds with one board
(plus a one-shot startup banner at session start).
Pure functions of their inputs — unit-testable without a terminal.

Every field degrades to ``n/a`` when unknown so a partially-instrumented
state still renders (ops reality: some values only exist after the first
bar/tick/decision of the session).

ASCII-only output throughout: the Windows console code page cannot be
relied on for box-drawing glyphs.
"""

from __future__ import annotations

__all__ = ["render_status_board", "render_startup_banner"]


def _fmt(value, fmt: str = "{}", na: str = "n/a") -> str:
    if value is None:
        return na
    try:
        return fmt.format(value)
    except (TypeError, ValueError):
        return str(value)


def render_status_board(s: dict) -> str:
    """Render ONE status board from an operator state dict.

    Expected keys (all optional — missing keys render ``n/a``):
        now_utc, terminal_dir, server, account, is_demo, symbol,
        dry_run, magic, hb_seq, hb_age_s, hb_state,
        last_bar_utc, spread, atr, gate_pass, gate_detail,
        htf_batches, htf_armed, arm_errors, htf_last (C1 multi-TF status),
        candidates, blocked, placed, cancelled, rejects,
        open_positions, kpi (dict of counters), bars_processed,
        errors, session_started_utc
    """
    lines: list[str] = []
    push = lines.append

    push("=" * 68)
    push(f" SMC OPERATOR  |  {_fmt(s.get('now_utc'))} UTC")
    push("=" * 68)
    push(
        f" terminal : {_fmt(s.get('terminal_dir'))}"
        f"  server: {_fmt(s.get('server'))}"
    )
    push(
        f" account  : {_fmt(s.get('account'))}"
        f"  demo: {_fmt(s.get('is_demo'))}"
        f"  symbol: {_fmt(s.get('symbol'))}"
        f"  magic: {_fmt(s.get('magic'))}"
    )
    push(
        f" dry_run  : {_fmt(s.get('dry_run'))}"
        f"   started: {_fmt(s.get('session_started_utc'))}"
    )
    push("-" * 68)
    push(
        f" heartbeat: seq {_fmt(s.get('hb_seq'))}"
        f"  age {_fmt(s.get('hb_age_s'), '{:.1f}s')}"
        f"  state {_fmt(s.get('hb_state'))}"
    )
    push(
        f" bar      : last {_fmt(s.get('last_bar_utc'))}"
        f"   processed {_fmt(s.get('bars_processed'))}"
    )
    push(
        f" market   : spread {_fmt(s.get('spread'), '{:.3f}')}"
        f"  ATR {_fmt(s.get('atr'), '{:.3f}')}"
        f"  gate {_fmt(s.get('gate_pass'))}"
        f"  {_fmt(s.get('gate_detail'))}"
    )
    push("-" * 68)
    push(
        f" detect   : htf batches {_fmt(s.get('htf_batches'))}"
        f"  armed {_fmt(s.get('htf_armed'))}"
        f"  arm-errors {_fmt(s.get('arm_errors'))}"
    )
    push(f"            {_fmt(s.get('htf_last'), na='(no batch yet)')}")
    push("-" * 68)
    push(
        f" flow     : candidates {_fmt(s.get('candidates'))}"
        f"  blocked {_fmt(s.get('blocked'))}"
        f"  placed {_fmt(s.get('placed'))}"
        f"  cancelled {_fmt(s.get('cancelled'))}"
        f"  rejects {_fmt(s.get('rejects'))}"
    )
    push(f" book     : open positions {_fmt(s.get('open_positions'))}")
    kpi = s.get("kpi") if isinstance(s.get("kpi"), dict) else {}
    push(
        " kpi      : decisions "
        + _fmt(kpi.get("decisions"))
        + "  fills "
        + _fmt(kpi.get("fills"))
        + "  closed "
        + _fmt(kpi.get("trades_closed"))
        + "  missed-bar eps "
        + _fmt(kpi.get("missed_bar_episodes"))
        + "  hard-cancels "
        + _fmt(kpi.get("hard_cancels"))
        + "  friday-closes "
        + _fmt(kpi.get("friday_closes"))
    )
    errors = s.get("errors")
    if errors:
        shown = errors[-3:]
        push(f" errors   : {len(errors)} total — last: {shown}")
    else:
        push(" errors   : 0")
    push("=" * 68)
    return "\n".join(lines)


_BANNER_TITLE = (
    "  ____  __  __  ___     ____   ___  _____",
    " / ___||  \\/  |/ ___|  | __ ) / _ \\|_   _|",
    " \\___ \\| |\\/| | |      |  _ \\| | | | | |",
    "  ___) | |  | | |___   | |_) | |_| | | |",
    " |____/|_|  |_|\\____|  |____/ \\___/  |_|",
)


def _cadence_text(console_refresh_s) -> str:
    """Human cadence line, e.g. 900 -> 'every 900s (15 min)'."""
    try:
        s = float(console_refresh_s)
    except (TypeError, ValueError):
        return "n/a"
    if s < 0:
        return "n/a"
    if s >= 60:
        minutes = s / 60.0
        return f"every {s:.0f}s ({minutes:g} min)"
    return f"every {s:g}s"


def render_startup_banner(
    facts: dict,
    *,
    timeframe: str = "n/a",
    console_refresh_s=None,
    log_dir: str | None = None,
) -> str:
    """Render the one-shot session startup banner (ASCII-only).

    ``facts`` is the identity-gate dict (all keys optional — missing keys
    render ``n/a``). Printed once after identity PASS; the full facts remain
    in ``identity.json`` + ``events.log``.
    """
    if not isinstance(facts, dict):
        facts = {}
    lines: list[str] = []
    push = lines.append

    push("=" * 68)
    push("")
    for row in _BANNER_TITLE:
        push(row)
    push("")
    push(f"  PHASE D OPERATOR  |  PAPER TRADING ON DEMO  |  dry_run: "
         f"{_fmt(facts.get('dry_run'))}")
    push("=" * 68)
    push(
        f" terminal : {_fmt(facts.get('terminal_dir_live'))}"
    )
    push(
        f" account  : {_fmt(facts.get('login'))}"
        f" @ {_fmt(facts.get('server'))}"
        f"  ({_fmt(facts.get('mode'))}"
        f", {_fmt(facts.get('currency'))}"
        f" 1:{_fmt(facts.get('leverage'))})"
        f"  trade allowed: {_fmt(facts.get('trade_allowed'))}"
    )
    push(
        f" market   : {_fmt(facts.get('symbol'))}"
        f"  magic: {_fmt(facts.get('magic'))}"
        f"  timeframe: {_fmt(timeframe)}"
    )
    push(
        f" console  : live board now, then {_cadence_text(console_refresh_s)}"
    )
    push(
        f" backend  : events.log + console_mirror.log + kpi_records.jsonl"
        f"  ({_fmt(log_dir)})"
    )
    push("-" * 68)
    push(" Ctrl+C stops the session cleanly (heartbeat shutdown marker).")
    push("=" * 68)
    return "\n".join(lines)
