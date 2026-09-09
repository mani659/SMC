"""Phase 6 M6 — operational KPI logging for the paper runner.

Future Flexibility Clause evidence: the paper runner logs the operational
health metrics (decision latency, order ack latency, order success/reject
counts, management delays, missed bars, hard-cancels, Friday closes) as
structured, append-only records. V1 deliberately logs METRICS ONLY — no
pass/fail threshold engine exists here (thresholds are not frozen).

Determinism contract:

* every record's timestamp is INJECTED (``at=``) — never read from the
  wall clock; the paper runner passes bar-clock timestamps and measures
  LATENCIES with an injected monotonic source (``time.perf_counter`` in
  production, a fake in tests), so identical scenarios emit identical
  records;
* records are append-only: :meth:`KPILogger.record` never mutates or
  reorders earlier records;
* :meth:`KPILogger.counters` is a pure fold over the record list;
* :meth:`KPILogger.to_json` / ``write_jsonl`` / ``write_csv`` are
  deterministic for identical inputs (``sort_keys`` everywhere, sorted
  CSV header union).

Record shape (one JSON object per event; ``fields`` flattened at export):

===================  =====================================================
event                fields
===================  =====================================================
``decision``         latency_ms, candidates, placed, blocked, rejected,
                     bar_index — one per processed bar (bar-close →
                     decision-complete latency of THIS cycle's compute)
``order_ack``        latency_ms, success, retcode, ticket — decision →
                     broker-ack latency per placement attempt
``management``       op (modify_sl | close | cancel), ticket, success,
                     latency_ms — SL modify / exit close / cancel ops
``fill``             ticket, poi_id, trigger, volume — broker fill
                     observed for one of our pendings
``trade_closed``     ticket, kind, win, poi_id, exit_price — broker close
                     observed or runner-initiated (win may be None when
                     honestly undeterminable)
``missed_bar``       expected_at, gap_bars — bar-close feed gap detected
``hard_cancel``      cancelled — §11 pre-news cancel episode
``friday_close``     closed, cancelled — §28.4 portfolio EOD episode
===================  =====================================================
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime

__all__ = ["KpiRecord", "KPILogger"]


def _iso(value) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


@dataclass(frozen=True, slots=True)
class KpiRecord:
    """One operational event (append-only log entry)."""

    event: str
    at: object                 # injected UTC datetime (bar clock)
    fields: dict = field(default_factory=dict)  # treat as read-only


class KPILogger:
    """Append-only structured KPI log with derived counters + exports."""

    def __init__(self) -> None:
        self._records: list[KpiRecord] = []

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #
    def record(self, event: str, *, at, **fields) -> KpiRecord:
        """Append one event record (timestamps injected, never wall clock)."""
        rec = KpiRecord(event=event, at=at, fields=dict(fields))
        self._records.append(rec)
        return rec

    def record_decision(
        self, *, at, latency_ms: float, candidates: int, placed: int,
        blocked: int, rejected: int, bar_index: int,
    ) -> KpiRecord:
        """Bar-close → decision-complete latency for one processed bar."""
        return self.record(
            "decision",
            at=at,
            latency_ms=latency_ms,
            candidates=candidates,
            placed=placed,
            blocked=blocked,
            rejected=rejected,
            bar_index=bar_index,
        )

    def record_order_ack(
        self, *, at, latency_ms: float, success: bool, retcode: int,
        ticket: int | None = None,
    ) -> KpiRecord:
        """Decision → broker-ack latency for one placement attempt."""
        return self.record(
            "order_ack",
            at=at,
            latency_ms=latency_ms,
            success=bool(success),
            retcode=int(retcode),
            ticket=ticket,
        )

    def record_management(
        self, *, at, op: str, ticket: int, success: bool, latency_ms: float = 0.0,
    ) -> KpiRecord:
        """One broker management op (modify_sl | close | cancel)."""
        return self.record(
            "management",
            at=at,
            op=op,
            ticket=int(ticket),
            success=bool(success),
            latency_ms=latency_ms,
        )

    def record_fill(self, *, at, ticket: int, poi_id, trigger, volume: float) -> KpiRecord:
        """Broker fill observed for one of our pendings."""
        return self.record(
            "fill",
            at=at,
            ticket=int(ticket),
            poi_id=poi_id,
            trigger=getattr(trigger, "value", trigger),
            volume=volume,
        )

    def record_trade_closed(
        self, *, at, ticket: int, kind: str, win: bool | None,
        poi_id=None, exit_price: float | None = None,
    ) -> KpiRecord:
        """Broker close observed / runner-initiated close applied."""
        return self.record(
            "trade_closed",
            at=at,
            ticket=int(ticket),
            kind=kind,
            win=win,
            poi_id=poi_id,
            exit_price=exit_price,
        )

    def record_missed_bar(self, *, at, expected_at, gap_bars: int) -> KpiRecord:
        """Bar-close feed gap: ``gap_bars`` bars missing before this one."""
        return self.record(
            "missed_bar", at=at, expected_at=_iso(expected_at), gap_bars=int(gap_bars)
        )

    def record_hard_cancel(self, *, at, cancelled: int) -> KpiRecord:
        """§11 pre-news hard-cancel episode (all pendings cancelled)."""
        return self.record("hard_cancel", at=at, cancelled=int(cancelled))

    def record_friday_close(self, *, at, closed: int, cancelled: int) -> KpiRecord:
        """§28.4 Friday EOD portfolio close episode."""
        return self.record(
            "friday_close", at=at, closed=int(closed), cancelled=int(cancelled)
        )

    # ------------------------------------------------------------------ #
    # Reading
    # ------------------------------------------------------------------ #
    @property
    def records(self) -> list[KpiRecord]:
        """Copy of the record list in append order (deterministic)."""
        return list(self._records)

    def counters(self) -> dict[str, int]:
        """Derived event counts — a pure fold over the records."""
        out = {
            "decisions": 0,
            "orders_placed": 0,
            "orders_rejected": 0,
            "sl_modify_success": 0,
            "sl_modify_failures": 0,
            "exit_close_success": 0,
            "exit_close_failures": 0,
            "cancel_success": 0,
            "cancel_failures": 0,
            "fills": 0,
            "trades_closed": 0,
            "hard_cancels": 0,
            "friday_closes": 0,
            "missed_bar_episodes": 0,
            "bars_missed": 0,
        }
        for rec in self._records:
            event, f = rec.event, rec.fields
            if event == "decision":
                out["decisions"] += 1
            elif event == "order_ack":
                out["orders_placed" if f["success"] else "orders_rejected"] += 1
            elif event == "management":
                op, ok = f["op"], f["success"]
                if op == "modify_sl":
                    out["sl_modify_success" if ok else "sl_modify_failures"] += 1
                elif op == "close":
                    out["exit_close_success" if ok else "exit_close_failures"] += 1
                elif op == "cancel":
                    out["cancel_success" if ok else "cancel_failures"] += 1
            elif event == "fill":
                out["fills"] += 1
            elif event == "trade_closed":
                out["trades_closed"] += 1
            elif event == "hard_cancel":
                out["hard_cancels"] += 1
            elif event == "friday_close":
                out["friday_closes"] += 1
            elif event == "missed_bar":
                out["missed_bar_episodes"] += 1
                out["bars_missed"] += int(f.get("gap_bars", 0))
        return out

    # ------------------------------------------------------------------ #
    # Export (deterministic for identical inputs)
    # ------------------------------------------------------------------ #
    def _rows(self) -> list[dict]:
        return [{"event": r.event, "at": _iso(r.at), **r.fields} for r in self._records]

    def to_json(self) -> str:
        """Full record list as deterministic JSON (``sort_keys``)."""
        return json.dumps(self._rows(), sort_keys=True, default=str)

    def write_jsonl(self, path) -> None:
        """Append-friendly JSONL: one record object per line."""
        with open(path, "w", encoding="utf-8") as handle:
            for row in self._rows():
                handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")

    def write_csv(self, path) -> None:
        """Flat CSV: event/at + the sorted union of all field names."""
        extra = sorted({key for r in self._records for key in r.fields})
        fieldnames = ["event", "at", *extra]
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in self._rows():
                writer.writerow({name: row.get(name, "") for name in fieldnames})
