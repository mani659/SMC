"""PRODUCT 6-MONTH MENU + ONE-STORY DIAGNOSTIC (measurement only).

Runs the locked product MENU law (PFE-2 bounded-window convention) with the
ONE STORY -> ONE PLAN guard ON, dual-run for determinism, and answers:

1) how many UNIQUE stories (plans) appear - not raw fill spam;
2) is the engine a single storyline or diversified (trigger/direction/model/
   detection-TF/month mixes on the book);
3) is multi-fill on identical plans zero under the guard.

Window (pre-registered, reused verbatim from PFE-2 section 1 - the continuous
6-month menu run is documented infeasible there, PFE2 report section 1.1, so
the menu evidence is the SAME three frozen 10-day windows, each dual-run):
    jun: exec 2025-06-01 -> 2025-06-10, load 2025-05-01
    sep: exec 2025-09-01 -> 2025-09-10, load 2025-05-01
    oct: exec 2025-10-01 -> 2025-10-10, load 2025-05-01  (PFE-2 primary)

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

OUT_ROOT = REPO / "06_RESEARCH" / "results" / "product_6m_one_story"
PFE2 = REPO / "06_RESEARCH" / "results" / "pfe2_6m"
PHASE3 = REPO / "06_RESEARCH" / "scripts" / "phase3_structure_funnel.py"
DATA = REPO / "07_DATA" / "XAUUSD_M1.parquet"

WINDOWS = {  # tag -> (exec_from, exec_to, load_from)  (PFE-2 section 1, verbatim)
    "jun": ("2025-06-01", "2025-06-10", "2025-05-01"),
    "sep": ("2025-09-01", "2025-09-10", "2025-05-01"),
    "oct": ("2025-10-01", "2025-10-10", "2025-05-01"),  # PFE-2 primary
}
IGNORE_KEYS = {"runtime_seconds", "tag", "notes"}


def fail_loud(msg: str) -> None:
    raise SystemExit(f"[6m-one-story] FAIL LOUD: {msg}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_window(tag: str, wtag: str, out_dir: Path) -> dict:
    exec_from, exec_to, load_from = WINDOWS[wtag]
    cmd = [
        sys.executable, "-X", "utf8", str(PHASE3),
        "--tag", tag,
        "--out-root", str(out_dir),
        "--exec-from", exec_from,
        "--exec-to", exec_to,
        "--load-from", load_from,
        "--composition", "menu",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
    if proc.returncode != 0:
        fail_loud(f"phase3 {tag} exit {proc.returncode}\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    summary = json.loads((out_dir / "funnel_summary.json").read_text(encoding="utf-8"))
    return summary


def load_trades(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(row: dict, key: str):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return None


def trade_key(row: dict):
    """Plan identity of a FILLED trade - the story_guard rules 2-6."""
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


def _parse_ts(value: str):
    try:
        return datetime.fromisoformat(value.replace(" ", "T"))
    except (TypeError, ValueError):
        return None


def plan_groups(trades: list[dict]) -> list[list[dict]]:
    """Union-find groups of trades sharing one executable plan (rules 2-6).

    Sameness needs known zone bounds on BOTH sides (rule 3) - a trade with
    unknown zone is never collapsed into any group.
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

    keys = [trade_key(t) for t in trades]
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


def _detection_tf(row: dict) -> str:
    """Detection TF of the plan (menu stamp in signal_data_json); else unknown."""
    try:
        sd = json.loads(row.get("signal_data_json") or "{}")
        value = ((sd.get("product_menu") or {}).get("detection_tf"))
        return str(value) if value else "unknown"
    except (TypeError, ValueError):
        return "unknown"


def mix(trades: list[dict], key: str) -> dict:
    if key == "detection_tf":
        return dict(sorted(Counter(_detection_tf(t) for t in trades).items()))
    return dict(sorted(Counter((t.get(key) or "?") for t in trades).items()))


def agg_window(run_dir: Path, wtag: str) -> dict:
    s = json.loads((run_dir / "funnel_summary.json").read_text(encoding="utf-8"))
    trades = load_trades(run_dir / "trades.csv")
    groups = plan_groups(trades)
    multi = [g for g in groups if len(g) > 1]
    overlapping = [g for g in multi
                   if any(interval_overlap(a, b) for a, b in combinations(g, 2))]
    return {
        "window": wtag,
        "exec_window": s["window"]["start"] + " -> " + s["window"]["end"],
        "load_from": s["window"]["load_from"],
        "bars_m5": s["bars_m5"],
        "funnel": {k: s.get(k) for k in (
            "htf_batches", "batch_errors", "merged_pois", "passed_validation",
            "armed", "armed_by_tf", "armed_m8", "duplicates_suppressed",
            "routes", "routes_by_trigger", "menu_winners", "menu_episodes",
            "menu_errors", "menu_counters", "story_counters", "placed",
            "placed_with_tp", "fills", "trades", "trades_by_trigger",
            "sample_audit_rows")},
        "raw_fills": len(trades),
        "unique_filled_plans": len(groups),
        "identical_plan_groups": len(multi),
        "identical_plan_groups_overlapping": len(overlapping),
        "fills_by_trigger": mix(trades, "trigger"),
        "fills_by_direction": mix(trades, "direction"),
        "fills_by_model_tags": mix(trades, "model_tags"),
        "fills_by_detection_tf": mix(trades, "detection_tf"),
        "fills_by_month": dict(sorted(Counter(
            (t.get("entry_at") or "")[:7] for t in trades).items())),
        "exit_close_kind": mix(trades, "close_kind"),
        "exit_tp_source": mix(trades, "tp_source"),
    }


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


def main() -> int:
    if not DATA.exists() or DATA.stat().st_size == 0:
        fail_loud(f"missing M1 parquet twin: {DATA}")
    print(f"[6m] data ok: {DATA.name} ({DATA.stat().st_size} bytes)", flush=True)

    summary = {"tag": "product_6m_one_story", "composition": "menu",
               "guard": "one_story_one_trade ON (shipped intake seam)",
               "diagnostic_only": True, "windows": {}}
    for wtag in WINDOWS:
        for rtag in ("run1", "run2"):
            out = OUT_ROOT / rtag / wtag
            out.mkdir(parents=True, exist_ok=True)
            if (out / "funnel_summary.json").exists():
                s = json.loads((out / "funnel_summary.json").read_text(encoding="utf-8"))
                print(f"[6m] {wtag}/{rtag}: reused existing artifacts", flush=True)
                continue
            t0 = datetime.now(timezone.utc)
            s = run_window(f"{wtag}_{rtag}", wtag, out)
            print(f"[6m] {wtag}/{rtag}: armed={s['armed']} fills={s['fills']} "
                  f"placed={s['placed']} runtime={s['runtime_seconds']}s",
                  flush=True)
        # determinism per window
        d1, d2 = OUT_ROOT / "run1" / wtag, OUT_ROOT / "run2" / wtag
        trades_identical = (sha256_file(d1 / "trades.csv")
                            == sha256_file(d2 / "trades.csv"))
        report_identical = (sha256_file(d1 / "report.json")
                            == sha256_file(d2 / "report.json"))
        summary_diffs = compare_summary_files(d1 / "funnel_summary.json",
                                              d2 / "funnel_summary.json")
        if not (trades_identical and report_identical and not summary_diffs):
            fail_loud(f"determinism {wtag}: trades={trades_identical} "
                      f"report={report_identical} summary_diffs={summary_diffs}")
        summary["windows"][wtag] = agg_window(d1, wtag)
        summary["windows"][wtag]["determinism"] = {
            "trades_csv": "PASS", "report_json": "PASS", "funnel_summary": "PASS"}
        print(f"[6m] {wtag}: determinism PASS", flush=True)

    # ---- combined book shape ------------------------------------------------
    all_trades = []
    for wtag in WINDOWS:
        all_trades.extend(load_trades(OUT_ROOT / "run1" / wtag / "trades.csv"))
    groups = plan_groups(all_trades)
    multi = [g for g in groups if len(g) > 1]
    overlapping = [g for g in multi
                   if any(interval_overlap(a, b) for a, b in combinations(g, 2))]
    combined = {
        "raw_fills": len(all_trades),
        "unique_filled_plans": len(groups),
        "identical_plan_groups": len(multi),
        "identical_plan_groups_overlapping": len(overlapping),
        "fills_by_trigger": mix(all_trades, "trigger"),
        "fills_by_direction": mix(all_trades, "direction"),
        "fills_by_model_tags": mix(all_trades, "model_tags"),
        "fills_by_detection_tf": mix(all_trades, "detection_tf"),
        "fills_by_month": dict(sorted(Counter(
            (t.get("entry_at") or "")[:7] for t in all_trades).items())),
        "exit_close_kind": mix(all_trades, "close_kind"),
        "exit_tp_source": mix(all_trades, "tp_source"),
        "routes_by_trigger": {w: summary["windows"][w]["funnel"]["routes_by_trigger"]
                              for w in WINDOWS},
        "armed_by_tf": {w: summary["windows"][w]["funnel"]["armed_by_tf"]
                        for w in WINDOWS},
    }
    summary["combined"] = combined

    # ---- comparison vs the pre-guard PFE-2 menu runs (same plan key) --------
    pre = {}
    pre_trades_all = []
    for wtag, dir_name in (("jun", "menu_short_jun"), ("sep", "menu_short_sep"),
                           ("oct", "menu_short_oct")):
        src = PFE2 / dir_name / "run1" / "trades.csv"
        if not src.exists():
            fail_loud(f"missing pre-guard comparison artifact: {src}")
        t = load_trades(src)
        pre_trades_all.extend(t)
        g = plan_groups(t)
        pre[wtag] = {"raw_fills": len(t), "unique_plans": len(g)}
    g_pre = plan_groups(pre_trades_all)
    summary["comparison_vs_pfe2_pre_guard"] = {
        "plan_key": "identical story_guard rules 2-6 applied to both sides",
        "pre_guard": {"raw_fills": len(pre_trades_all),
                      "unique_plans": len(g_pre), "by_window": pre},
        "post_guard": {"raw_fills": combined["raw_fills"],
                       "unique_plans": combined["unique_filled_plans"]},
    }

    # ---- hard checks (fail loud) --------------------------------------------
    guard_fired = any(
        summary["windows"][w]["funnel"]["story_counters"]["duplicate_story_dropped"] > 0
        for w in WINDOWS)
    checks = {
        "determinism_all_windows": True,
        "menu_errors_zero": all(
            summary["windows"][w]["funnel"]["menu_errors"] == 0 for w in WINDOWS),
        "guard_engaged_at_least_once": guard_fired,
        "no_identical_plan_overlap": combined["identical_plan_groups_overlapping"] == 0,
    }
    summary["checks"] = checks
    for name, ok in checks.items():
        if not ok:
            fail_loud(f"check failed: {name}")
    print("[6m] all hard checks PASS", flush=True)

    (OUT_ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"[6m] wrote {OUT_ROOT / 'summary.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
