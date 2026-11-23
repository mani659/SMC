"""PRODUCT-FILL GAP RECONCILIATION (read-only, no replay).

Explains the S3 post-R1 verdict's ``product_anchor_losses`` — 56 product
fills missing over 21 of 24 runs — one row at a time, by joining the
authoritative artifacts that the year harness already wrote:

    product anchor  06_RESEARCH/results/product_1y_one_story/run1/<seg>/trades.csv
    multi-book      06_RESEARCH/results/parallel_books_s3_rerun/<seg>/books_F-B-C-E-A_<hyp>/
                       fills.csv, winners.json, run_metrics.json
    pre-R1 ref      06_RESEARCH/results/parallel_books_full_bt/<seg>/... (evidence only)

Join key is the harness' own ``fill_key``
``(poi_id, trigger, entry_at, entry_price[6], direction)`` — the exact key
the year verdict used for ``missing_product_fills``. No second product
definition is invented and nothing is replayed.

Buckets (one primary per missing fill, precedence in ``classify``):

    C  R1 / identity      exact product fill present pre-R1, OR the same
                          executable plan (direction, entry_price, entry_at)
                          filled in the post-R1 run under another POI/trigger/
                          book (product fill reproduced, key re-attributed)
    B  story substitution the same POI traded in the run under a different
                          trigger (the product trigger's plan did not fill)
    A  never admitted     the POI has no menu winner at all in the run
    F  routed, unfilled   the product (poi, trigger) won a route but no fill
                          of that trigger exists anywhere in the run
    G  unjoinable         nothing above applies

No strategy code, no thresholds, no replay. Diagnostic only — the pnl
columns in the source artifacts are accounting residue, never performance.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
S3 = REPO / "06_RESEARCH" / "results" / "parallel_books_s3_rerun"
PRE = REPO / "06_RESEARCH" / "results" / "parallel_books_full_bt"
SRC = REPO / "06_RESEARCH" / "results" / "product_1y_one_story" / "run1"
OUT = REPO / "06_RESEARCH" / "results" / "product_gap_recon"

SEGMENTS = ("nov24", "dec24", "jan25", "feb25", "mar25", "apr25",
            "may25", "jun25", "jul25", "aug25", "sep25", "oct25")
HYPOTHESES = ("LONG", "SHORT")
BOOKS = ("F", "B", "C", "E", "A")

BUCKETS = {
    "C": "R1 identity collapse / re-attribution (plan reproduced or suppressed)",
    "B": "same POI traded under a different trigger (story substitution)",
    "A": "never admitted to the multi-book menu (no winner for the POI)",
    "F": "route emitted, no fill of that (poi, trigger) in the run",
    "G": "unjoinable / unexplained (no evidence)",
}


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def fill_key(row: dict) -> tuple:
    """The harness' own identity (identical to r1_pure_tag_books.fill_key)."""
    return (
        str(row["poi_id"]),
        str(row["trigger"]),
        str(row["entry_at"]),
        round(float(row["entry_price"]), 6),
        str(row["direction"]),
    )


def plan_key(row: dict) -> tuple:
    """R1 executable identity: direction + entry limit (+ the fill instant)."""
    return (
        str(row["direction"]),
        round(float(row["entry_price"]), 6),
        str(row["entry_at"]),
    )


def classify(missing: dict, *, fkeys: set, plans: dict, wins: list[dict],
             fills: list[dict], pre_keys: set) -> tuple[str, dict]:
    """One primary bucket + the evidence that put it there."""
    key = fill_key(missing)
    poi = str(missing["poi_id"])
    trigger = str(missing["trigger"])

    poi_wins = [w for w in wins if str(w["poi_id"]) == poi]
    routed_trigger = any(str(w["trigger"]) == trigger for w in poi_wins)
    other_fills = [
        r for r in fills
        if str(r["poi_id"]) == poi and str(r["trigger"]) != trigger
    ]
    plan_match = plans.get(plan_key(missing))
    evidence = {
        "routed_any": bool(poi_wins),
        "routed_trigger": routed_trigger,
        "r1_plan_fill_book": plan_match["book_id"] if plan_match else "",
        "r1_plan_fill_trigger": plan_match["trigger"] if plan_match else "",
        "r1_plan_fill_poi": plan_match["poi_id"] if plan_match else "",
        "in_pre_r1": key in pre_keys,
        "other_trigger_fill_n": len(other_fills),
        "other_trigger_fill_books": ",".join(
            sorted({str(r["book_id"]) for r in other_fills})),
        "poi_winners": ",".join(
            sorted({f"{w['trigger']}@{w['book_id']}" for w in poi_wins})),
    }
    if plan_match is not None or key in pre_keys:
        return "C", evidence
    if other_fills:
        return "B", evidence
    if not poi_wins:
        return "A", evidence
    if routed_trigger:
        return "F", evidence
    return "G", evidence


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out)
    if not out.is_absolute():
        out = REPO / out
    out.mkdir(parents=True, exist_ok=True)

    verdict = json.loads((S3 / "verdict.json").read_text(encoding="utf-8"))
    verdict_by_run = {
        row["run"]: row for row in verdict["product_anchor_losses"]}

    rows: list[dict] = []
    run_stats: dict = {}
    totals = Counter()
    product_total = 0
    replayed_total = 0

    for seg in SEGMENTS:
        prod = _read_csv(SRC / seg / "trades.csv")
        product_total += len(prod)
        for hyp in HYPOTHESES:
            run = f"{seg}/{hyp}"
            d = S3 / seg / f"books_{'-'.join(BOOKS)}_{hyp}"
            fills = _read_csv(d / "fills.csv")
            wins = json.loads((d / "winners.json").read_text(
                encoding="utf-8"))["winners"]
            metrics = json.loads((d / "run_metrics.json").read_text(
                encoding="utf-8"))
            replayed_total += len(fills)

            fkeys = {fill_key(r) for r in fills}
            # One plan index per run; first row wins (plans are unique by
            # construction — repeated identity would be a double lot).
            plans: dict = {}
            for r in fills:
                plans.setdefault(plan_key(r), r)
            pre_path = PRE / seg / f"books_{'-'.join(BOOKS)}_{hyp}" / "fills.csv"
            pre_keys = ({fill_key(r) for r in _read_csv(pre_path)}
                        if pre_path.exists() else set())

            missing = [r for r in prod if fill_key(r) not in fkeys]
            run_stats[run] = {
                "missing": len(missing),
                "product_fills": len(prod),
                "replayed": len(fills),
                "placed": metrics["placed"],
                "fills": metrics["fills"],
                "winners_total": metrics["winners_total"],
                "story_dropped": metrics["story_counters"][
                    "duplicate_story_menu"],
                "shared_risk_skips": sum(
                    (metrics["checks"]["shared_risk_skips"] or {}).values()),
            }
            expected = verdict_by_run.get(run)
            if expected is not None and expected["missing_product_fills"] != len(missing):
                raise SystemExit(
                    f"{run}: missing {len(missing)} != verdict "
                    f"{expected['missing_product_fills']}")

            for m in missing:
                bucket, ev = classify(
                    m, fkeys=fkeys, plans=plans, wins=wins, fills=fills,
                    pre_keys=pre_keys)
                totals[bucket] += 1
                totals[f"trigger_{m['trigger']}"] += 1
                rows.append({
                    "run": run,
                    "segment": seg,
                    "hypothesis": hyp,
                    "poi_id": m["poi_id"],
                    "trigger": m["trigger"],
                    "direction": m["direction"],
                    "entry_at": m["entry_at"],
                    "entry_price": m["entry_price"],
                    "route_id": m.get("route_id", ""),
                    "bucket": bucket,
                    **{k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                       for k, v in ev.items()},
                })

    if len(rows) != verdict["product_anchor_losses"] and sum(
            r["missing"] for r in run_stats.values()) != len(rows):
        raise SystemExit("row count does not reconcile with per-run totals")

    csv_path = out / "missing_fills.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    by_bucket = {b: totals[b] for b in "CBAFG"}
    by_run_bucket: dict = defaultdict(lambda: Counter())
    for row in rows:
        by_run_bucket[row["run"]][row["bucket"]] += 1

    payload = {
        "reconciliation": "parallel_books_product_fill_gap",
        "diagnostic_only": True,
        "not_performance": (
            "read-only artifact join; pnl fields in sources are accounting "
            "residue, never a performance claim"),
        "sources": {
            "product_anchor": str(SRC.relative_to(REPO)),
            "multi_book": str(S3.relative_to(REPO)),
            "pre_r1_reference": str(PRE.relative_to(REPO)),
            "verdict": str((S3 / "verdict.json").relative_to(REPO)),
        },
        "join_key": ["poi_id", "trigger", "entry_at", "entry_price(6)",
                     "direction"],
        "product_fills": product_total,
        "replayed_fills": replayed_total,
        "missing_n": len(rows),
        "buckets": by_bucket,
        "bucket_definitions": BUCKETS,
        "trigger_mix_missing": {
            t: totals[f"trigger_{t}"] for t in sorted({r["trigger"] for r in rows})
        },
        "per_run": run_stats,
        "per_run_buckets": {k: dict(v) for k, v in sorted(by_run_bucket.items())},
        "unresolved": by_bucket["G"],
        "note": (
            "D (shared risk) is not assigned per fill: the runner exports "
            "blocked reasons only as run counters, so no per-fill join exists. "
            "Run-level blocked counts are recorded as a co-factor in per_run."),
    }
    (out / "recon.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print(f"[gap-recon] missing {len(rows)} / product {product_total} unique "
          f"fills / replayed {replayed_total} (all 24 runs)")
    print(f"[gap-recon] buckets {by_bucket}")
    print(f"[gap-recon] wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
