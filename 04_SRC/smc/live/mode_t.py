"""Mode T — DIAGNOSTIC entry path (design lock 00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md).

CONSTANT HOME (binding, per the implementation prompt §1.1): every Mode T
design constant lives HERE — never in ``smc.config.locked_constants`` and
never operator-tunable (``operator_config`` rejects Mode T geometry keys).
The values freeze exactly the design note §2:

    T_MAX_GAP_ATR = 0.25   (§2.2)
    T_TP_ATR      = 1.0    (§2.3)
    T_REST_BARS   = 12     (§2.4)
    T_MAX_CONCURRENT = 2   (§2.3)
    T_MAX_PER_DAY    = 6   (§2.3)

POSTURE: Mode T is DIAGNOSTIC ONLY — visible activity + labelable tickets.
NOT production Mode A entry identity, NOT Mode B, NOT a reopened entry-rep
family, never an edge/expectancy claim. The product path stays scarce and
frozen; Mode T is an alternate builder at the candidate/limit seam only.

RULE T2 (the ONE primary rule, note §2.2): on Stage-3 proof completion of an
armed H4/H1 POI (observed from the product's own routed-workflow chain — no
fork of detection/§5), place ONE pending LIMIT at the proof-bar mid
``entry = (high(proof) + low(proof)) / 2`` in the thesis direction IFF
``abs(entry − close(proof)) / ATR <= T_MAX_GAP_ATR``; otherwise skip via the
frozen taxonomy. SL = the proof bar's ADVERSE extreme (Mode T's OWN bracket —
never a silent FR-2/product inherit); TP = ``entry ± T_TP_ATR × ATR``;
volume = min lot. Product wins ties (a live product ticket for the same POI
→ ``PRODUCT_PATH_TAKEN``). One Mode T decision per (poi, proof bar) event.

Every decision (PLACE or SKIP) emits ONE structured JSON line per note §2.5
to the ledger ``mode_t_events.jsonl`` — note-verbatim field names (including
``anomaly_ts_iso``, the note's own spelling of the decision timestamp).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from smc.core.enums import Direction

__all__ = [
    "T_MAX_GAP_ATR",
    "T_TP_ATR",
    "T_REST_BARS",
    "T_MAX_CONCURRENT",
    "T_MAX_PER_DAY",
    "MIN_LOT_FLOOR",
    "MODE_T_BANNER",
    "MODE_T_MARK",
    "MARKER_EOL_SECONDS",
    "SKIP_REASONS",
    "ACTION_PLACE",
    "ACTION_SKIP",
    "GAP_TOO_WIDE",
    "NO_ATR",
    "NO_SESSION",
    "SPREAD_GATE",
    "DUPLICATE_EPISODE",
    "PRODUCT_PATH_TAKEN",
    "CAP_CONCURRENT",
    "CAP_DAILY",
    "MINIMUM_VOLUME_ERROR",
    "INVALIDATED_BEFORE_PLACE",
    "place_rejected",
    "ModeTDecision",
    "decide_mode_t",
    "ModeTLedger",
    "ModeTDirector",
]

logger = logging.getLogger(__name__)

# --- Design note §2 constants (THEIR ONLY HOME — see module docstring) --- #
T_MAX_GAP_ATR = 0.25
T_TP_ATR = 1.0
T_REST_BARS = 12
T_MAX_CONCURRENT = 2
T_MAX_PER_DAY = 6
# Absolute volume floor of the diagnostic ticket (fixed micro risk; §2.3).
MIN_LOT_FLOOR = 0.01

# Startup banner when the flag is ON — EXACT string per design note §2.1.
MODE_T_BANNER = (
    "[MODE T] DIAGNOSTIC ENTRY PATH ACTIVE — every order logs mode=T; "
    "product Mode A path unchanged; diagnostic only, NOT a strategy claim"
)
# Order-comment prefix + ledger tag so diagnostics stay identifiable (§2.3).
MODE_T_MARK = "mode=T"
# Marker-file staleness budget mirrored by the EA (note §4.4, 30 s).
MARKER_EOL_SECONDS = 30

# --- Frozen skip taxonomy (note §2.2, EXHAUSTIVE — anything else is a bug) -- #
GAP_TOO_WIDE = "GAP_TOO_WIDE"
NO_ATR = "NO_ATR"
NO_SESSION = "NO_SESSION"
SPREAD_GATE = "SPREAD_GATE"
DUPLICATE_EPISODE = "DUPLICATE_EPISODE"
PRODUCT_PATH_TAKEN = "PRODUCT_PATH_TAKEN"
CAP_CONCURRENT = "CAP_CONCURRENT"
CAP_DAILY = "CAP_DAILY"
MINIMUM_VOLUME_ERROR = "MINIMUM_VOLUME_ERROR"
INVALIDATED_BEFORE_PLACE = "INVALIDATED_BEFORE_PLACE"

PLACE_REJECTED_PREFIX = "PLACE_REJECTED_"


def place_rejected(retcode) -> str:
    """The taxonomy's parametric tail: ``PLACE_REJECTED_<retcode>`` (§2.2)."""
    return f"{PLACE_REJECTED_PREFIX}{retcode}"


SKIP_REASONS = frozenset({
    GAP_TOO_WIDE,
    NO_ATR,
    NO_SESSION,
    SPREAD_GATE,
    DUPLICATE_EPISODE,
    PRODUCT_PATH_TAKEN,
    CAP_CONCURRENT,
    CAP_DAILY,
    MINIMUM_VOLUME_ERROR,
    INVALIDATED_BEFORE_PLACE,
})


def is_skip_reason(reason: str) -> bool:
    """True iff ``reason`` belongs to the frozen taxonomy (incl. the
    parametric ``PLACE_REJECTED_<retcode>`` tail)."""
    return (
        reason in SKIP_REASONS
        or (isinstance(reason, str)
            and reason.startswith(PLACE_REJECTED_PREFIX))
    )


ACTION_PLACE = "PLACE"
ACTION_SKIP = "SKIP"


# ---------------------------------------------------------------------- #
# Decision (pure, note §2.2 — unit-tested matrix)
# ---------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ModeTDecision:
    """ONE Mode T decision outcome (immutable record; ledger + console input)."""

    action: str                     # ACTION_PLACE | ACTION_SKIP
    poi_id: str
    detection_tf: str | None
    trigger_letter: str             # product §5 route letter or "T2"
    direction: Direction
    proof_bar: int                  # completion bar index of the proof
    entry: float | None             # None on SKIP
    sl: float | None
    tp: float | None
    gap_atr: float | None           # None on SKIP
    skip_reason: str | None         # None on PLACE; taxonomy member on SKIP
    volume: float | None            # None on SKIP
    cap_state_concurrent: int
    cap_state_daily: int
    defected: bool = False          # set only by the director's bookkeeping

    # Expert scorecard placeholders — NOTE §2.5: BLANK in V1, filled later by
    # human/measure rounds, NEVER by code.
    level_ok = None
    sweep_ok = None
    confirm_ok = None
    timing = None                   # "early|ok|late" space reserved, null
    would_take = None

    def ledger_line(self, *, anomaly_ts: str) -> dict:
        """The note-verbatim §2.5 ledger fields for this decision."""
        return {
            "mode": "T",
            "anomaly_ts_iso": anomaly_ts,
            "poi_id": self.poi_id,
            "detection_tf": self.detection_tf,
            "exec_tf": "M5",
            "proof_bar": self.proof_bar,
            "trigger_letter": self.trigger_letter,
            "action": self.action,
            "entry": self.entry,
            "sl": self.sl,
            "tp": self.tp,
            "gap_atr": self.gap_atr,
            "skip_reason": self.skip_reason,
            "volume": self.volume,
            "cap_state_concurrent": self.cap_state_concurrent,
            "cap_state_daily": self.cap_state_daily,
            "mode_t_ticket": "T",
            "level_ok": None,
            "sweep_ok": None,
            "confirm_ok": None,
            "timing": None,
            "would_take": None,
        }


def decide_mode_t(
    *,
    proof_high: float,
    proof_low: float,
    proof_close: float,
    atr: float | None,
    direction: Direction,
    session_ok: bool,
    spread_gate_ok: bool,
    duplicate: bool,
    product_ticket_active: bool,
    concurrent_open: int,
    placed_today: int,
    volume_min: float,
) -> ModeTDecision:
    """Pure rule T2 (note §2.2) — accept or skip with a taxonomy reason.

    Frozen evaluation order (documented once here, tested as a matrix):

        1. duplicate event  -> DUPLICATE_EPISODE
        2. session gate     -> NO_SESSION
        3. spread gate      -> SPREAD_GATE
        4. product ticket   -> PRODUCT_PATH_TAKEN   (product wins ties)
        5. ATR availability -> NO_ATR               (fail-closed)
        6. gap guard        -> GAP_TOO_WIDE
        7. concurrent cap   -> CAP_CONCURRENT
        8. daily cap        -> CAP_DAILY
        9. min volume       -> MINIMUM_VOLUME_ERROR
       10. PLACE

    The geometry (proof-bar mid entry / adverse-extreme SL / ±T_TP_ATR TP /
    min-lot volume) is computed once and returned on PLACE; on SKIP only
    ``cap_state_*`` and None-valued geometry ride along (never invented).
    """

    def _skip(reason: str) -> ModeTDecision:
        return ModeTDecision(
            action=ACTION_SKIP,
            poi_id="",                      # caller stamps identity
            detection_tf=None,
            trigger_letter="T2",
            direction=direction,
            proof_bar=0,
            entry=None, sl=None, tp=None, gap_atr=None,
            skip_reason=reason,
            volume=None,
            cap_state_concurrent=concurrent_open,
            cap_state_daily=placed_today,
        )

    # 1..4 — preconditions (note order: session, spread, product).
    if duplicate:
        return _skip(DUPLICATE_EPISODE)
    if not session_ok:
        return _skip(NO_SESSION)
    if not spread_gate_ok:
        return _skip(SPREAD_GATE)
    if product_ticket_active:
        return _skip(PRODUCT_PATH_TAKEN)
    # 5..9 — geometry then resources.
    if atr is None or not atr > 0:
        return _skip(NO_ATR)
    entry = float(proof_high + proof_low) / 2.0
    gap_atr = abs(entry - float(proof_close)) / float(atr)
    if gap_atr > T_MAX_GAP_ATR:
        return _skip(GAP_TOO_WIDE)
    if concurrent_open >= T_MAX_CONCURRENT:
        return _skip(CAP_CONCURRENT)
    if placed_today >= T_MAX_PER_DAY:
        return _skip(CAP_DAILY)
    if volume_min is None or not float(volume_min) > 0:
        return _skip(MINIMUM_VOLUME_ERROR)
    volume = max(MIN_LOT_FLOOR, float(volume_min))
    if volume <= 0:
        return _skip(MINIMUM_VOLUME_ERROR)
    sl = float(proof_low) if direction is Direction.LONG else float(proof_high)
    if direction is Direction.LONG:
        tp = entry + T_TP_ATR * float(atr)
    else:
        tp = entry - T_TP_ATR * float(atr)
    return ModeTDecision(
        action=ACTION_PLACE,
        poi_id="",                          # caller stamps identity
        detection_tf=None,
        trigger_letter="T2",
        direction=direction,
        proof_bar=0,
        entry=entry,
        sl=sl,
        tp=tp,
        gap_atr=gap_atr,
        skip_reason=None,
        volume=volume,
        cap_state_concurrent=concurrent_open,
        cap_state_daily=placed_today,
    )


def _stamp(decision: ModeTDecision, *, poi_id: str, detection_tf, proof_bar) -> ModeTDecision:
    """Attach caller-side identity to a decision (frozen dataclass — rebuild)."""
    return ModeTDecision(
        action=decision.action,
        poi_id=poi_id,
        detection_tf=detection_tf,
        trigger_letter=decision.trigger_letter,
        direction=decision.direction,
        proof_bar=proof_bar,
        entry=decision.entry,
        sl=decision.sl,
        tp=decision.tp,
        gap_atr=decision.gap_atr,
        skip_reason=decision.skip_reason,
        volume=decision.volume,
        cap_state_concurrent=decision.cap_state_concurrent,
        cap_state_daily=decision.cap_state_daily,
    )


# ---------------------------------------------------------------------- #
# Ledger (note §2.5 — one JSON line per decision; fail-loud on OSError)
# ---------------------------------------------------------------------- #
class ModeTLedger:
    """Append-only ``mode_t_events.jsonl`` writer (note §2.5)."""

    def __init__(self, path) -> None:
        self.path = Path(path)

    def append(self, record: dict) -> None:
        line = json.dumps(record, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def tail(self, n: int = 5) -> list[dict]:
        """Last ``n`` records (console JUDGEMENT input; missing → empty)."""
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                lines = handle.readlines()[-n:]
        except OSError:
            return []
        out: list[dict] = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out


# ---------------------------------------------------------------------- #
# Director — operator-side Mode T book (live wiring in run_operator)
# ---------------------------------------------------------------------- #
@dataclass
class _TDiagnosis:
    """Manager state of ONE placed Mode T order (resting / filled / dead)."""

    poi_id: str
    ticket: int
    placed_bar: int
    resting: bool = True
    filled: bool = False


class ModeTDirector:
    """Owns the Mode T book: decisions, ledger, caps, rest/invalidation/EOD.

    Live wiring (``run_operator``) supplies the broker callbacks; the helper
    objects (ledger, banner) live here. The director NEVER touches detection,
    §5 state, or risk logic — it only READS what the caller hands in and
    manages its OWN tickets (note §2.4: 12-bar rest, §5 invalidation cancel,
    Friday EOD cancel; no separate news cancel — no news feed on the live
    path, disclosed).
    """

    def __init__(
        self,
        *,
        ledger: ModeTLedger,
        place_fn=None,        # (decision, comment) -> PlaceOutcome-like
        cancel_fn=None,       # (ticket) -> bool
        clock=None,           # () -> datetime (UTC); decision timestamp
    ) -> None:
        self.ledger = ledger
        self._place_fn = place_fn
        self._cancel_fn = cancel_fn
        self._clock = clock          # () -> datetime; UTC in production wiring
        # (poi_id, proof_bar) → decision — the one-shot event identity.
        self._decided: dict[tuple[str, int], ModeTDecision] = {}
        self._open: dict[str, _TDiagnosis] = {}   # poi_id → open resting/filled
        self._placed_today = 0
        self._day: str | None = None              # "YYYY-MM-DD" UTC set on use
        self._logger = logging.getLogger(f"smc.mode_t.{id(self)}")

    # -- banner (note §2.1 — session prints this exactly once) ----------- #
    def banner(self) -> str:
        return MODE_T_BANNER

    # -- decision path --------------------------------------------------- #
    @property
    def placed_today(self) -> int:
        return self._placed_today

    @property
    def resting(self) -> dict[str, int]:
        """poi_id → resting ticket (pending orders the director tracks)."""
        return {pid: d.ticket for pid, d in self._open.items() if d.resting}

    @property
    def open_pois(self) -> list[str]:
        """POIs with ANY live Mode T ticket (resting or filled)."""
        return sorted(self._open.keys())

    def decision_for(self, poi_id: str, proof_bar: int) -> ModeTDecision | None:
        return self._decided.get((poi_id, int(proof_bar)))

    def consider(
        self,
        *,
        poi_id: str,
        detection_tf,
        trigger_letter: str,
        direction: Direction,
        proof_bar: int,
        proof_high: float,
        proof_low: float,
        proof_close: float,
        atr: float | None,
        session_ok: bool,
        spread_gate_ok: bool,
        product_ticket_active: bool,
        concurrent_open: int,
        volume_min: float,
        bar_index: int,
    ) -> ModeTDecision:
        """Evaluate rule T2 once per (poi, proof) event and act on PLACE.

        Idempotent: a (poi, proof) event already decided returns the stored
        decision WITHOUT a re-sent broker call (the one-shot). Caller checks
        ``decision.action``/``skip_reason`` for console/marker output.
        """
        key = (str(poi_id), int(proof_bar))
        existing = self._decided.get(key)
        if existing is not None:
            return existing

        today = self._today()
        if today != self._day:
            # Hard daily cap counter rolls on the UTC date (note §2.3 cap).
            self._day = today
            self._placed_today = 0

        decision = decide_mode_t(
            proof_high=proof_high,
            proof_low=proof_low,
            proof_close=proof_close,
            atr=atr,
            direction=direction,
            session_ok=session_ok,
            spread_gate_ok=spread_gate_ok,
            duplicate=False,          # one-shot enforced above (already-decided)
            product_ticket_active=product_ticket_active,
            concurrent_open=concurrent_open,
            placed_today=self._placed_today,
            volume_min=volume_min,
        )
        decision = _stamp(
            decision, poi_id=str(poi_id), detection_tf=detection_tf,
            proof_bar=int(proof_bar),
        )
        if trigger_letter:
            decision = ModeTDecision(
                action=decision.action,
                poi_id=decision.poi_id,
                detection_tf=decision.detection_tf,
                trigger_letter=str(trigger_letter),
                direction=decision.direction,
                proof_bar=decision.proof_bar,
                entry=decision.entry,
                sl=decision.sl,
                tp=decision.tp,
                gap_atr=decision.gap_atr,
                skip_reason=decision.skip_reason,
                volume=decision.volume,
                cap_state_concurrent=decision.cap_state_concurrent,
                cap_state_daily=decision.cap_state_daily,
            )
        self._decided[key] = decision
        self._emit(decision)

        if decision.action is not ACTION_PLACE:
            return decision

        comment = (
            f"{MODE_T_MARK}|T2|{str(poi_id)[:8]}@{int(proof_bar)}"
        )
        ticket_ok, retcode, ticket = self._send(decision, comment)
        if not ticket_ok:
            rejected = _stamp(
                decide_mode_t(
                    proof_high=proof_high,
                    proof_low=proof_low,
                    proof_close=proof_close,
                    atr=atr,
                    direction=direction,
                    session_ok=True,
                    spread_gate_ok=True,
                    duplicate=False,
                    product_ticket_active=False,
                    concurrent_open=concurrent_open,
                    placed_today=self._placed_today,
                    volume_min=volume_min,
                ),
                poi_id=str(poi_id), detection_tf=detection_tf,
                proof_bar=int(proof_bar),
            )
            rejected = _as_skip(rejected, place_rejected(retcode))
            self._emit(rejected)
            return rejected

        self._open[str(poi_id)] = _TDiagnosis(
            poi_id=str(poi_id), ticket=ticket, placed_bar=int(bar_index)
        )
        self._placed_today += 1
        self._logger.info(
            "MODE T PLACED poi=%s proof=%s entry=%.2f sl=%.2f tp=%.2f "
            "gap_atr=%.3f ticket=%s bar=%s",
            decision.poi_id, decision.proof_bar, decision.entry,
            decision.sl, decision.tp, decision.gap_atr, ticket, bar_index,
        )
        return decision

    # -- management (note §2.4: rest expiry / §5 invalidation / Friday) --- #
    def manage(
        self,
        *,
        bar_index: int,
        friday_eod: bool,
        invalidated_pois,
        filled_tickets=None,
    ) -> list[tuple[str, str]]:
        """Age out / invalidate / EOD-cancel Mode T tickets. Returns the
        cancels as ``(poi_id, reason)`` — console BOOK + events.log input.
        Reasons use the note's own vocabulary (rest=archive expiry semantics):
        ``REST_EXPIRED``, ``INVALIDATED``, ``FRIDAY_EOD``.
        """
        cancels: list[tuple[str, str]] = []
        if isinstance(filled_tickets, (set, frozenset, list, tuple)):
            filled = set(filled_tickets)
        else:
            filled = set()
        for poi_id in sorted(self._open.keys()):
            diag = self._open[poi_id]
            if diag.ticket in filled:
                if diag.resting:
                    diag.resting = False
                    diag.filled = True
                else:
                    diag.filled = True
                continue
            dead = False
            reason = None
            if poi_id in set(invalidated_pois or ()):
                reason = INVALIDATED_BEFORE_PLACE
                dead = True
            elif diag.resting and (int(bar_index) - diag.placed_bar) >= T_REST_BARS:
                reason = "REST_EXPIRED"
                dead = True
            elif friday_eod and diag.resting:
                reason = "FRIDAY_EOD"
                dead = True
            if not dead:
                continue
            if diag.resting and self._cancel_fn is not None:
                ok = bool(self._cancel_fn(diag.ticket))
                if not ok:
                    self._logger.warning(
                        "MODE T CANCEL FAILED poi=%s ticket=%s reason=%s",
                        poi_id, diag.ticket, reason,
                    )
                    continue        # stays in the book; retried next cycle
            self._open.pop(poi_id, None)
            cancels.append((poi_id, reason))
            self._logger.info(
                "MODE T CANCELLED poi=%s ticket=%s reason=%s",
                poi_id, diag.ticket, reason,
            )
        return cancels

    def shutdown(self) -> list[tuple[str, str]]:
        """Clean-session stop: cancel EVERY resting Mode T ticket (§2.4;
        open diagnostic positions are left to the static watchdog exactly
        like product tickets). Returns the cancels for the events log."""
        cancels: list[tuple[str, str]] = []
        for poi_id in sorted(self._open.keys()):
            diag = self._open[poi_id]
            if diag.resting and self._cancel_fn is not None:
                bool(self._cancel_fn(diag.ticket))
            self._open.pop(poi_id, None)
            cancels.append((poi_id, "SESSION_STOP"))
        return cancels

    # -- helpers ---------------------------------------------------------- #
    def _today(self) -> str:
        now = self._utcnow()
        return f"{now.year:04d}-{now.month:02d}-{now.day:02d}"

    def _utcnow(self) -> datetime:
        if self._clock is not None:
            return self._clock()
        return datetime.now(timezone.utc)  # fallback; production passes a UTC clock

    def _send(self, decision: ModeTDecision, comment: str) -> tuple[bool, str, int | None]:
        """Broker send through the injected callback. ``(ok, retcode, ticket)``
        — with NO configured callback the diagnostic line still records
        (dry-run parity: decisions logged even when nothing is sent, §1.4)."""
        if self._place_fn is None:
            return False, "DRYRUN_NO_SEND", None
        try:
            outcome = self._place_fn(decision, comment)
        except Exception as exc:            # noqa: BLE001 — broker boundary
            self._logger.error("MODE T SEND FAILED error=%r", exc)
            return False, "EXCEPTION", None
        ok = bool(getattr(outcome, "success", False))
        return ok, str(getattr(outcome, "retcode", "")), getattr(outcome, "ticket", None)

    def _emit(self, decision: ModeTDecision) -> None:
        ts = self._utcnow()
        record = decision.ledger_line(anomaly_ts=ts.isoformat(timespec="seconds"))
        try:
            self.ledger.append(record)
        except OSError as exc:
            self._logger.error(
                "MODE T LEDGER WRITE FAILED path=%s error=%r", self.ledger.path, exc
            )
            raise


def _as_skip(decision: ModeTDecision, reason: str) -> ModeTDecision:
    """Rebuild a PLACE decision as a taxonomy SKIP (place-rejected path)."""
    return ModeTDecision(
        action=ACTION_SKIP,
        poi_id=decision.poi_id,
        detection_tf=decision.detection_tf,
        trigger_letter=decision.trigger_letter,
        direction=decision.direction,
        proof_bar=decision.proof_bar,
        entry=None,
        sl=None,
        tp=None,
        gap_atr=None,
        skip_reason=reason,
        volume=None,
        cap_state_concurrent=decision.cap_state_concurrent,
        cap_state_daily=decision.cap_state_daily,
    )
