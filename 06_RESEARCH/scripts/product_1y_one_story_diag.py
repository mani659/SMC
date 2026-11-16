"""PRODUCT ~1Y MENU + ONE-STORY DIAGNOSTIC (measurement only).

Target window (frozen, pre-registered): exec 2024-11-01 -> 2025-10-31 UTC
(12 calendar months), load 2024-09-01 (61 days warm-up). The canonical
XAUUSD M1 parquet covers 2021-04-12 -> 2026-04-10, so the target is fully
inside the data.

MODE LOGIC (pre-registered):
- PRIMARY: one TRUE continuous menu run over the 12 months. The continuous
  attempt is profiled live (phase3 prints bars/s every 2000 bars) and given
  a bounded wall-time budget. PFE-2 section 1.1 documented the continuous
  menu collapse (<2 bars/s by bar 4000, quadratic menu bookkeeping, stopped
  BEFORE any funnel was read).
- If the continuous attempt cannot complete in the budget, this driver runs
  SEGMENTED CONTINUOUS coverage: 12 ADJACENT calendar-month segments that
  exactly tile 2024-11-01 -> 2025-10-31 (no gaps, no overlaps), dual-run per
  segment. This is NOT "three random 10-day windows" - it is a full tiling
  of the same year, with explicit merge + boundary-dedupe rules below.

MERGE RULES (explicit, mechanical):
1. Every fill happens at exactly one timestamp inside exactly one segment ->
   no double-count by construction.
2. armed / merged / passed / menu-winners are NOT summed across segments:
   menu state restarts per segment, so zones near boundaries re-arm (counts
   reported per segment only, with the boundary caveat).
3. Boundary dedupe (counted, never silent): a fill whose plan identity
   (story_guard rules 2-6) equals an earlier fill, where the earlier fill is
   within the last 10 days of its segment and the later fill within the
   first 10 days of the next segment, is treated as a boundary re-arm
   artifact: the LATER fill is dropped. Both counts (before/after) are
   reported. Guard-legal re-arms OUTSIDE the boundary bands are kept.
4. Hard check: overlapping identical-plan groups (concurrent duplicates)
   must be 0 at year scale.

DIAGNOSTIC ONLY: no edge claim, no ranking, no threshold/gate change.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "04_SRC"))

from smc.risk.story_guard import same_story, story_key  # noqa: E402

OUT_ROOT = REPO / "06_RESEARCH" / "results" / "product_1y_one_story"
SIX_M = REPO / "06_RESEARCH" / "results" / "product_6m_one_story" / "run1"
PHASE3 = REPO / "06_RESEARCH" / "scripts" / "phase3_structure_funnel.py"
DATA = REPO / "07_DATA" / "XAUUSD_M1.parquet"

LOAD_FROM = "2024-09-01"  # 61 days before exec start (pre-registered)
# 12 adjacent calendar months, exec-to inclusive (phase3 convention).
SEGMENTS = {
    "nov24": ("2024-11-01", "2024-11-30"),
    "dec24": ("2024-12-01", "2024-12-31"),
    "jan25": ("2025-01-01", "2025-01-31"),
    "feb25": ("2025-02-01", "2025-02-28"),
    "mar25": ("2025-03-01", "2025-03-31"),
    "apr25": ("2025-04-01", "2025-04-30"),
    "may25": ("2025-05-01", "2025-05-31"),
    "jun25": ("2025-06-01", "2025-06-30"),
    "jul25": ("2025-07-01", "2025-07-31"),
    "aug25": ("2025-08-01", "2025-08-31"),
    "sep25": ("2025-09-01", "2025-09-30"),
    "oct25": ("2025-10-01", "2025-10-31"),
}
IGNORE_KEYS = {"runtime_seconds", "tag", "notes"}


def fail_loud(msg: str) -> None:
    raise SystemExit(f"[1y-one-story] FAIL LOUD: {msg}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_segment(segwtag: str, rtag: str, out_dir: Path) -> dict:
    exec_from, exec_to = SEGMENTS[segwtag]
    cmd = [
        sys.executable, "-X", "utf8", str(PHASE3),
        "--tag", f"{segwtag}_{rtag}",
        "--out-root", str(out_dir),
        "--exec-from", exec_from,
        "--exec-to", exec_to,
        "--load-from", LOAD_FROM,
        "--composition", "menu",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
    if proc.returncode != 0:
        fail_loud(f"phase3 {segwtag}/{rtag} exit {proc.returncode}\n"
                  f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    return json.loads((out_dir / "funnel_summary.json").read_text(
        encoding="utf-8"))


def load_trades(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(row: dict, key: str):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return None


def _parse_ts(value: str):
    try:
        ts = datetime.fromisoformat(value.replace(" ", "T"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _detection_tf(row: dict) -> str:
    try:
        sd = json.loads(row.get("signal_data_json") or "{}")
        value = (sd.get("product_menu") or {}).get("detection_tf")
        return str(value) if value else "unknown"
    except (TypeError, ValueError):
        return "unknown"


def _plan_key(row: dict):
    class _Obj:  # duck for story_key()
        pass
    o = _Obj()
    o.entry_price = _f(row, "entry_price")
    o.sl_price = _f(row, "sl")
    o.tp_price = _f(row, "tp")
    o.direction = row.get("direction") or None
    o.trigger = (row.get("trigger") or "").strip() or None
    o.zone_low = _f(row, "zone_low")
    o.zone_high = _f(row, "zone_high")
    return story_key(o)


def plan_groups(trades: list[dict]) -> list[list[dict]]:
    """Union-find groups of trades sharing one executable plan (rules 2-6).

    Sameness needs known zone bounds on BOTH sides; unknown zone is never
    collapsed into any group.
    """
    n = len(trades)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    keys = [_plan_key(t) for t in trades]
    for i, j in combinations(range(n), 2):
        if same_story(keys[i], keys[j]):
            union(i, j)
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return [[trades[i] for i in members] for members in groups.values()]


def interval_overlap(a: dict, b: dict) -> bool:
    ea, xa = _parse_ts(a.get("entry_at", "")), _parse_ts(a.get("exit_at", ""))
    eb, xb = _parse_ts(b.get("entry_at", "")), _parse_ts(b.get("exit_at", ""))
    if None in (ea, xa, eb, xb):
        return False  # unresolvable time - never asserted
    return ea <= xb and eb <= xa


def _segment_of(trade: dict) -> str:
    """Segment tag by entry date (fills are unique-timestamp events)."""
    day = (trade.get("entry_at") or "")[:10]
    for tag, (lo, hi) in SEGMENTS.items():
        if lo <= day <= hi:
            return tag
    return "outside"


def boundary_dedupe(trades: list[dict]) -> tuple[list[dict], int]:
    """Rule 3 of the merge rules: drop LATER boundary re-arm artifacts."""
    if len(trades) < 2:
        return trades, 0
    trades_sorted = sorted(trades, key=lambda t: (t.get("entry_at") or "",
                                                  t.get("ticket", "")))
    dropped = set()
    seg_order = list(SEGMENTS)
    for i, j in combinations(range(len(trades_sorted)), 2):
        a, b = trades_sorted[i], trades_sorted[j]
        if j in dropped or not same_story(_plan_key(a), _plan_key(b)):
            continue
        sa, sb = _segment_of(a), _segment_of(b)
        if sa == sb or sa not in seg_order or sb not in seg_order:
            continue
        if seg_order.index(sb) != seg_order.index(sa) + 1:
            continue
        ea = _parse_ts(a.get("entry_at", ""))
        eb = _parse_ts(b.get("entry_at", ""))
        hi_a = _parse_ts(SEGMENTS[sa][1] + "T23:55:00")
        lo_b = _parse_ts(SEGMENTS[sb][0] + "T00:00:00")
        if ea is None or eb is None or hi_a is None or lo_b is None:
            continue
        if (hi_a - ea).days * 1 <= 10 and (eb - lo_b).days * 1 <= 10:
            dropped.add(j)
    kept = [t for k, t in enumerate(trades_sorted) if k not in dropped]
    return kept, len(dropped)


def mix(trades: list[dict], key: str) -> dict:
    if key == "detection_tf":
        return dict(sorted(Counter(_detection_tf(t) for t in trades).items()))
    return dict(sorted(Counter((t.get(key) or "?") for t in trades).items()))


def compare_summary_files(a: Path, b: Path) -> list[str]:
    sa = json.loads(a.read_text(encoding="utf-8"))
    sb = json.loads(b.read_text(encoding="utf-8"))
    diffs = []
    for key in sorted(set(sa) | set(sb)):
        if key in IGNORE_KEYS:
            continue
        if json.dumps(sa.get(key), sort_keys=True, default=str) != \
           json.dumps(sb.get(key), sort_keys=True, default=str):
            diffs.append(key)
    return diffs


def seg_funnel_keys(s: dict) -> dict:
    return {k: s.get(k) for k in (
        "htf_batches", "batch_errors", "merged_pois", "passed_validation",
        "armed", "armed_by_tf", "armed_m8", "menu_episodes", "menu_winners",
        "menu_errors", "menu_counters", "story_counters", "placed",
        "fills", "trades", "routes_by_trigger", "sample_audit_rows",
        "bars_m5")}


def main() -> int:
    if not DATA.exists() or DATA.stat().st_size == 0:
        fail_loud(f"missing M1 parquet twin: {DATA}")
    print(f"[1y] data ok: {DATA.name} ({DATA.stat().st_size} bytes)", flush=True)

    continuous_done = (OUT_ROOT / "run1" / "continuous" / "trades.csv").exists()
    mode = "continuous" if continuous_done else "segmented"
    print(f"[1y] mode: {mode} (continuous artifact present: {continuous_done})",
          flush=True)

    summary = {"tag": "product_1y_one_story", "composition": "menu",
               "guard": "one_story_one_trade ON (shipped intake seam)",
               "diagnostic_only": True,
               "target_window": {"exec": "2024-11-01 -> 2025-10-31 UTC",
                                 "load_from": LOAD_FROM,
                                 "load_days_before_exec": 61},
               "mode": mode, "segments": {}}

    for segwtag in SEGMENTS:
        for rtag in ("run1", "run2"):
            out = OUT_ROOT / rtag / segwtag
            out.mkdir(parents=True, exist_ok=True)
            if (out / "funnel_summary.json").exists():
                print(f"[1y] {segwtag}/{rtag}: reused existing artifacts",
                      flush=True)
                continue
            t0 = datetime.now(timezone.utc)
            s = run_segment(segwtag, rtag, out)
            print(f"[1y] {segwtag}/{rtag}: armed={s['armed']} "
                  f"fills={s['fills']} placed={s['placed']} "
                  f"runtime={s['runtime_seconds']}s "
                  f"({(datetime.now(timezone.utc) - t0).total_seconds():.0f}s "
                  f"wall)", flush=True)
        d1, d2 = OUT_ROOT / "run1" / segwtag, OUT_ROOT / "run2" / segwtag
        trades_identical = (sha256_file(d1 / "trades.csv")
                            == sha256_file(d2 / "trades.csv"))
        report_identical = (sha256_file(d1 / "report.json")
                            == sha256_file(d2 / "report.json"))
        summary_diffs = compare_summary_files(d1 / "funnel_summary.json",
                                              d2 / "funnel_summary.json")
        if not (trades_identical and report_identical and not summary_diffs):
            fail_loud(f"determinism {segwtag}: trades={trades_identical} "
                      f"report={report_identical} summary_diffs={summary_diffs}")
        s1 = json.loads((d1 / "funnel_summary.json").read_text(
            encoding="utf-8"))
        summary["segments"][segwtag] = {
            "exec_window": SEGMENTS[segwtag][0] + " -> " + SEGMENTS[segwtag][1],
            "load_from": LOAD_FROM,
            "funnel": seg_funnel_keys(s1),
            "fills": s1["fills"], "placed": s1["placed"],
            "determinism": {"trades_csv": "PASS", "report_json": "PASS",
                            "funnel_summary": "PASS"}}
        print(f"[1y] {segwtag}: determinism PASS "
              f"(armed={s1['armed']} fills={s1['fills']})", flush=True)

    # ---- combined book (run1 across segments) ------------------------------ #
    raw_trades = []
    for segwtag in SEGMENTS:
        raw_trades.extend(load_trades(OUT_ROOT / "run1" / segwtag / "trades.csv"))
    for t in raw_trades:
        t["_seg"] = _segment_of(t)
        if t["_seg"] == "outside":
            fail_loud(f"fill outside all segments: {t.get('entry_at')} "
                      f"{t.get('ticket')}")
    deduped, n_dropped = boundary_dedupe(raw_trades)
    groups = plan_groups(deduped)
    multi = [g for g in groups if len(g) > 1]
    overlapping = [g for g in multi
                   if any(interval_overlap(a, b) for a, b in combinations(g, 2))]
    combined = {
        "raw_fills_before_boundary_dedupe": len(raw_trades),
        "boundary_dedupe_dropped": n_dropped,
        "raw_fills": len(deduped),
        "unique_filled_plans": len(groups),
        "identical_plan_groups_total": len(multi),
        "identical_plan_groups_overlapping": len(overlapping),
        "non_overlapping_rearm_groups": len(multi) - len(overlapping),
        "fills_by_trigger": mix(deduped, "trigger"),
        "fills_by_direction": mix(deduped, "direction"),
        "fills_by_model_tags": mix(deduped, "model_tags"),
        "fills_by_detection_tf": mix(deduped, "detection_tf"),
        "fills_by_month": dict(sorted(Counter(
            (t.get("entry_at") or "")[:7] for t in deduped).items())),
        "fills_by_segment": dict(sorted(Counter(
            t["_seg"] for t in deduped).items())),
        "exit_close_kind": mix(deduped, "close_kind"),
        "exit_tp_source": mix(deduped, "tp_source"),
        "placed_total": sum(summary["segments"][s]["placed"]
                            for s in SEGMENTS),
        "fills_total": sum(summary["segments"][s]["fills"] for s in SEGMENTS),
    }
    summary["combined"] = combined

    # ---- comparison vs the 6m three-window diagnostic ---------------------- #
    six_trades = []
    for w in ("jun", "sep", "oct"):
        six_trades.extend(load_trades(SIX_M / w / "trades.csv"))
    six_groups = plan_groups(six_trades)
    summary["comparison_vs_6m"] = {
        "six_m_windows": "jun/sep/oct 2025 10-day (PRODUCT_6M report)",
        "pre_guard_raw_fills": 27, "pre_guard_unique_plans": 8,
        "post_guard_raw_fills": len(six_trades),
        "post_guard_unique_plans": len(six_groups),
        "this_1y_raw_fills": combined["raw_fills"],
        "this_1y_unique_filled_plans": combined["unique_filled_plans"],
    }

    # ---- hard checks -------------------------------------------------------- #
    guard_fired = any(
        (summary["segments"][s]["funnel"]["story_counters"] or {}).get(
            "duplicate_story_dropped", 0) > 0 for s in SEGMENTS)
    checks = {
        "determinism_all_segments": True,
        "menu_errors_zero": all(
            summary["segments"][s]["funnel"]["menu_errors"] == 0
            for s in SEGMENTS),
        "guard_engaged_at_least_once": guard_fired,
        "no_overlapping_identical_plan_groups":
            combined["identical_plan_groups_overlapping"] == 0,
        "fills_accounted": combined["fills_total"]
        == combined["raw_fills_before_boundary_dedupe"],
    }
    summary["checks"] = checks
    for name, ok in checks.items():
        if not ok:
            fail_loud(f"check failed: {name}")
    print("[1y] all hard checks PASS", flush=True)

    (OUT_ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"[1y] wrote {OUT_ROOT / 'summary.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
