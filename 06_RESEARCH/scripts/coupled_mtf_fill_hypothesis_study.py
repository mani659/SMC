"""Coupled full-menu 443-fill hypothesis study — R / MFE / MAE (post-fill analytics).

DIAGNOSTIC ONLY — NOT PERFORMANCE / NOT EDGE.

Authority: Lead Architect "HYPOTHESIS-OUTCOME + R / MFE / MAE ON COUPLED FULL-
MENU FILLS (443)" (2026-11-01). Pure research script (06_RESEARCH only): no
04_SRC strategy changes, no locked_constants edits, no chain re-run.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path

# --- Pre-registered taxonomy (project labels; anything unresolvable = DATA_GAP)
LABELS = [
    "TP_REACHED",
    "SL_THEN_TP_PATH",
    "MFE_ONLY",
    "REJECTED",
    "BE_SCRATCH",
    "DATA_GAP",
]

BANNER = "DIAGNOSTIC ONLY — NOT PERFORMANCE / NOT EDGE"

# Fill-leg schema (one row per fill). Any missing field stays per-column
# "unknown" — NEVER invented (Part 0 of the directive).
LEG_FIELDS = [
    "fill_id",
    "tier",
    "trigger",
    "confirm_tf",
    "level_family",
    "direction",
    "volume",
    "identity",
    "entry",
    "sl_original",   # placement SL (1R reference). BE-modified SL is ignored.
    "tp",
    "place_ts",
    "fill_ts",
    "exit_ts",
    "close_kind",
    "exit_price",
    "pnl_raw",
    "win",
    "hold_bars",
    # derived (computed, not persisted-invented):
    "mfe_price",
    "mae_price",
    "mfe_r",
    "mae_r",
    "label",
]

# Pre-registered close_kind → taxonomy label mapping (DOCUMENTED MAPPING,
# nothing invented): capture persists close_kind verbatim (enum value or
# runner reason string) and the label is mapped mechanically:
#   take_profit → TP_REACHED ; stop_loss → REJECTED (entry rejected by price)
# Any OTHER kind (e.g. portfolio reason strings like "friday_eod") is
# sub-classified ONLY by persisted geometry:
#   exit_price == entry_price → BE_SCRATCH
#   otherwise                → MFE_ONLY (closed without reaching placed TP)
# SL_THEN_TP_PATH is reserved for an explicitly recorded re-entry chain
# (not produced by this capture) and therefore stays DATA_GAP otherwise.
CLOSE_KIND_LABELS = {
    "take_profit": "TP_REACHED",
    "stop_loss": "REJECTED",
}


def map_label(row: dict) -> str:
    """Mechanical, pre-registered close_kind → label resolution."""
    kind = row.get("close_kind")
    if kind in (None, "unknown", ""):
        return "DATA_GAP"
    label = CLOSE_KIND_LABELS.get(str(kind))
    if label is not None:
        return label
    entry = row.get("entry")
    exit_price = row.get("exit_price")
    if entry not in ("unknown", None) and exit_price not in ("unknown", None, ""):
        if float(exit_price) == float(entry):
            return "BE_SCRATCH"
        return "MFE_ONLY"
    return "DATA_GAP"

CANONICAL_SOURCES = {
    "summary": "06_RESEARCH/results/coupled_mtf_full_menu_diag/summary.json",
    "candidates": "06_RESEARCH/results/coupled_mtf_full_menu_diag/run1/candidates.json",
    "events": "06_RESEARCH/results/coupled_mtf_full_menu_diag/run1/checkpoint_events.jsonl",
    "checkpoints": [
        "06_RESEARCH/results/coupled_mtf_full_menu_diag/run1/checkpoint.json",
        "06_RESEARCH/results/coupled_mtf_full_menu_diag/run2/checkpoint.json",
    ],
}


def load_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_leg_records(path: Path) -> list[dict]:
    """Normalize a persisted capture ``fill_legs.jsonl`` into one row per fill.

    Capture format: ``placed`` / ``fill`` / ``exit`` events sharing a ticket;
    the FILL record carries geometry/identity, the EXIT record carries
    close_kind / exit_ts / pnl / MFE / MAE. Both are merged per ticket
    (nothing invented: absent fields stay unset, later → unknown/"None").
    A plain already-merged legs JSONL (one record per fill) is tolerated.
    """
    events: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                events.append(json.loads(line))

    if not any(ev.get("event") == "fill" for ev in events):
        return events  # already merged per-fill records

    fills: dict[int, dict] = {}
    exits: dict[int, dict] = {}
    placed: dict[int, dict] = {}
    for ev in events:
        ticket = ev.get("ticket")
        kind = ev.get("event")
        if kind == "fill":
            fills[ticket] = ev
        elif kind == "exit":
            exits[ticket] = ev
        elif kind == "placed":
            placed[ticket] = ev

    rows: list[dict] = []
    for ticket in sorted(set(fills) | set(exits)):
        f = fills.get(ticket, {})
        x = exits.get(ticket, {})
        if not f:
            rows.append({  # exit without a persisted fill — DATA_GAP rule
                "fill_id": f"exit-{ticket}",
                "ticket": ticket,
                "close_kind": x.get("close_kind"),
                "exit_ts": x.get("time_utc"),
                "exit_price": x.get("exit_price"),
            })
            continue
        rows.append({
            "fill_id": f.get("leg_id", f"fill-{ticket}"),
            "ticket": ticket,
            "identity": f.get("route_id"),
            "tier": f.get("detection_tier"),
            "trigger": f.get("trigger"),
            "confirm_tf": f.get("confirm_tf"),
            "direction": f.get("direction"),
            "volume": f.get("volume"),
            "entry": f.get("entry_price"),
            "sl_original": f.get("sl_original"),
            "tp": f.get("tp"),
            "place_ts": (placed.get(ticket) or {}).get("time_utc"),
            "fill_ts": f.get("time_utc"),
            "exit_ts": x.get("time_utc"),
            "close_kind": x.get("close_kind"),
            "exit_price": x.get("exit_price"),
            "pnl_raw": x.get("pnl_raw"),
            "win": x.get("win"),
            "hold_bars": x.get("hold_bars"),
            "mfe_price": x.get("mfe_price"),
            "mae_price": x.get("mae_price"),
        })
    return rows


def resolve_fills_from_records(summary: dict, leg_records: list[dict],
                               candidates_path: Path | None = None) -> list[dict]:
    """Join persisted leg records to candidate identity fields.

    ``leg_records`` must come from an instrumented capture (fill_legs.jsonl).
    Identity fields (tier/trigger/...) are joined when the record carries
    ``identity`` (route_id = episode.identity_tag) matching a candidates.json
    entry; otherwise they stay ``unknown``.

    Join key discipline: candidates.json ``identity`` is ALREADY the
    JSON-ENCODED identity string (e.g. ``["XAUUSD","M15",...]``) — the same
    ``identity_tag`` carried verbatim as order comment/route_id on each fill.
    Key therefore MUST be the RAW string; re-encoding it via json.dumps would
    double-encode and silently break the join (unknowns only).
    """
    by_identity: dict[str, dict] = {}
    if candidates_path is None:
        candidates_path = Path(CANONICAL_SOURCES["candidates"])
    candidates = load_json(candidates_path)
    for cand in candidates:
        if isinstance(cand, dict):
            by_identity.setdefault(cand.get("identity"), cand)
    rows: list[dict] = []
    for i, leg in enumerate(sorted(leg_records, key=lambda r: str(r.get("fill_ts", "")))):
        row: dict[str, object] = {f: "unknown" for f in LEG_FIELDS}
        row["fill_id"] = leg.get("fill_id", f"fill{i}")
        for src_field, dst_field in (
            ("tier", "tier"),
            ("trigger", "trigger"),
            ("confirm_tf", "confirm_tf"),
            ("level_family", "level_family"),
            ("identity", "identity"),
        ):
            if leg.get(src_field) is not None:
                row[dst_field] = leg[src_field]
        cand = by_identity.get(leg.get("identity"))
        if cand is not None:
            for field in ("tier", "trigger", "confirm_tf", "level_family"):
                if row[field] == "unknown":
                    row[field] = cand.get(field, "unknown")
        # persisted legs (never invented — copied verbatim when present)
        for field in (
            "direction",
            "volume",
            "entry",
            "sl_original",
            "tp",
            "place_ts",
            "fill_ts",
            "exit_ts",
            "close_kind",
            "exit_price",
            "pnl_raw",
            "win",
            "hold_bars",
            "mfe_price",
            "mae_price",
        ):
            if leg.get(field) is not None:
                row[field] = leg[field]
        rows.append(compute_r(row))
    return rows


def compute_r(row: dict) -> dict:
    """R/MFE/MAE computation. Pre-registered: 1R = ORIGINAL placement SL distance.

    Requires entry + sl_original + a persisted directional excursion pair
    (mfe_price/mae_price). Missing inputs → label stays/goes DATA_GAP.
    """
    entry, sl = row.get("entry"), row.get("sl_original")
    if entry != "unknown" and sl != "unknown" and row.get("direction") not in ("unknown", None):
        r1 = abs(float(entry) - float(sl))
        if r1 > 0 and row.get("mfe_price") not in ("unknown", None):
            row["mfe_r"] = round(
                abs(float(row["mfe_price"]) - float(entry)) / r1, 4
            )
        if r1 > 0 and row.get("mae_price") not in ("unknown", None):
            row["mae_r"] = round(
                abs(float(entry) - float(row["mae_price"])) / r1, 4
            )
    # Label resolution (pre-registered mechanical mapping above). An
    # explicitly persisted label (already taxonomy-valued) is kept verbatim.
    if row.get("close_kind") in LABELS[:-1]:
        row["label"] = row["close_kind"]
    else:
        row["label"] = map_label(row)
    return row


def aggregate(rows: list[dict]) -> dict:
    """Pre-registered aggregates: overall + by trigger / tier / confirm_tf."""

    def bucket(group_rows: list[dict]) -> dict:
        mfe = [float(r["mfe_r"]) for r in group_rows
               if r.get("mfe_r") not in ("unknown", None)]
        mae = [float(r["mae_r"]) for r in group_rows
               if r.get("mae_r") not in ("unknown", None)]
        n = len(group_rows)
        return {
            "n": n,
            "n_r_resolved": len(mfe),
            "median_mfe_r": round(statistics.median(mfe), 4) if mfe else None,
            "median_mae_r": round(statistics.median(mae), 4) if mae else None,
            "pct_mfe_ge_1r": round(100.0 * sum(m >= 1.0 for m in mfe) / len(mfe), 1) if mfe else None,
            "pct_mfe_ge_2r": round(100.0 * sum(m >= 2.0 for m in mfe) / len(mfe), 1) if mfe else None,
            "mfe_ge_mae_median_asymmetry": (
                round(statistics.median(mfe) - statistics.median(mae), 4)
                if mfe and mae else None
            ),
            "label_mix": dict(Counter(str(r.get("label")) for r in group_rows)),
        }

    def split(field: str) -> dict:
        groups: dict[str, list] = {}
        for r in rows:
            groups.setdefault(str(r.get(field)), []).append(r)
        return {k: bucket(v) for k, v in sorted(groups.items())}

    out = {"banner": BANNER, "overall": bucket(rows)}
    if rows:
        out["by_trigger"] = split("trigger")
        out["by_tier"] = split("tier")
        out["by_confirm_tf"] = split("confirm_tf")
        out["by_level_family"] = split("level_family")
    # Honest small-sample flags (Part 2): no cell with n < something is
    # silently aggregated as a "note"; the count itself carries the flag.
    out["small_sample_flags"] = {
        k: v["n"] for k, v in out.get("by_trigger", {}).items() if v["n"] < 100
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--legs",
        type=Path,
        default=None,
        help="Optional persisted fill-legs JSONL (from an instrumented "
        "capture GO-approved by the Architect). Absent = coverage-only mode.",
    )
    args = parser.parse_args()

    diag = Path("06_RESEARCH/results/coupled_mtf_full_menu_diag")
    summary = load_json(diag / "summary.json")
    orders = summary.get("orders", {})
    fills_total = int(orders.get("filled_total", 0))
    placed_total = int(orders.get("placed_total", 0))

    out_dir = Path("06_RESEARCH/results/coupled_mtf_fill_hypothesis")
    out_dir.mkdir(parents=True, exist_ok=True)

    leg_records: list = []
    candidates_path: Path | None = None
    if args.legs is not None and args.legs.exists():
        leg_records = load_leg_records(args.legs)
        # Identity join prefers the candidates.json sitting next to the
        # capture legs (same instrumented tree), falling back to the
        # canonical dual-run candidates (identical funnel, byte-proven).
        local = args.legs.parent / "candidates.json"
        candidates_path = local if local.exists() else None

    rows = (resolve_fills_from_records(summary, leg_records,
                                       candidates_path=candidates_path)
            if leg_records else [])
    fills_resolved = len(rows)
    coverage = round(100.0 * fills_resolved / fills_total, 1) if fills_total else 0.0

    agg = aggregate(rows)

    # Data-gap residual (Part 0 rule): the 2026-10-31 diagnostic persisted
    # counters only (CountingBook/CountingPositions) — zero trade legs on disk.
    data_gap = fills_total > 0 and fills_resolved == 0

    result = {
        "banner": BANNER,
        "study": "coupled_mtf_fill_hypothesis",
        "sources": CANONICAL_SOURCES,
        "run": {
            "mode": summary.get("mode"),
            "window": summary.get("window"),
            "execution_bars_total": (summary.get("run_completion") or {}).get(
                "execution_bars_total_frozen"
            ),
            "determinism_status": (summary.get("determinism") or {}).get("status"),
        },
        "context_funnel": {
            "candidates_emitted": summary.get("totals", {}).get("candidates_emitted"),
            "orders": summary.get("orders"),
            "filled_per_tier": summary.get("funnel", {}).get("filled"),
            "placed_per_tier": summary.get("funnel", {}).get("placed"),
        },
        "fills": {
            "fills_total": fills_total,
            "fills_resolved": fills_resolved,
            "placed_total_context": placed_total,
            "coverage_pct": coverage,
            "data_gap": data_gap,
            "gap_explanation": (
                "The 2026-10-31 full-menu diagnostic persisted ONLY counters "
                "(CountingBook/CountingPositions increments). No entry / sl / "
                "tp / exit / close_kind / pnl leg was written to disk, so the "
                "443 fills are not joinable to candidate identities. Per the "
                "directive Part 0 rule this is documented as a residual "
                "DATA_GAP; no field was invented and no chain re-run was "
                "performed. Extracting legs requires an instrumented "
                "single-pass capture pending GO (no strategy change)."
            ) if data_gap else None,
        },
        "aggregates": agg if rows else {
            "banner": BANNER,
            "overall": None,
            "note": "N/A — zero fills resolvable on persisted artifacts "
            "(coverage 0%). Aggregation activates via --legs with persisted "
            "trade legs; the schema/labels are pre-registered above.",
        },
        "taxonomy": LABELS,
        "r_definition": "1R = |entry - sl_original| (placement SL; BE-modified SL ignored)",
    }

    with open(out_dir / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, ensure_ascii=False)

    with open(out_dir / "fills_hypothesis.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LEG_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print(f"[{BANNER}]")
    print(
        f"fills_total={fills_total} fills_resolved={fills_resolved} "
        f"coverage={coverage}% data_gap={data_gap}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
