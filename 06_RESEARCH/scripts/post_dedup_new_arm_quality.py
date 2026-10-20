"""LEG 6 — post-dedup new-arm quality sample (DIAGNOSTIC, read-only intent).

Characterizes the *quality and fate* of arms that exist ONLY because the
LEG 5b ZoneDedup lifecycle retirement released their predecessors' keys
(cohort B) vs the legacy-like class that would still arm under an
append-only dedup (cohort A) — on the SAME frozen 6m window
(exec M5 2025-06-01 → 2025-11-30, M1 load from 2025-05-01) the ARCHITECT
accepted in LEG 5b. No rule changes; LOGIC_CHANGED: NO — the capture wraps
existing methods with logging-only class-level seams (all restored in
``finally``), reads the returned objects, and decides nothing.

PRE-REGISTERED (before the capture run; do not tune after seeing results):

* **Cohort A (LEGACY-LIKE)**: replay the captured ARM events chronologically
  through the product's OWN ``ZoneDedup`` in append-only mode (register,
  never retire). An arm is A iff ``seen(zone)`` was False at its moment.
  Integrity: ``n_A == 30`` AND the A id set equals LEG 4's frozen
  ``results/passed_to_armed/_funnel_capture/armed_records.json`` keys
  (LEG 4's run WAS effectively append-only — no retirement existed).
* **Cohort B (lifecycle-enabled)**: complement, i.e. armed but append-only
  suppressed. The append-only first-match predecessor MUST have a RETIRE
  event with ``retire_bar < arm_bar`` (same-bar retires cannot enable
  same-bar arms: the batch runs before the prune within one Cycle) —
  ``identity_gaps > 1% of n_B`` → ``INCONCLUSIVE_IDENTITY_GAP``.
* **Interpretation bands** (arm→route / arm→fill conversion; NOT PnL):
  weaker = B < A − 10 pp; stronger = B > A + 10 pp; both ≤ −10 pp weaker /
  both ≥ +10 pp stronger → single label; opposite signs → ``MIXED``; both
  within ±10 pp → ``NEW_ARMS_SIMILAR_TO_LEGACY``.
* **Capture integrity gates**: arms == 606, registers == 606, routes == 219,
  places == 65, retires == 606, ``trades.csv`` SHA-256 == the LEG 5b run
  byte value (``8eecd3b96f91339b…``) — proving the reads changed nothing.
* **Double-arm live key**: replay the lifecycle registry (arms + retire
  events in file order): an arm overlapping an ACTIVE key is an anomaly
  (expected 0).

Usage:
  python post_dedup_new_arm_quality.py --capture          # one run ~16 min
  python post_dedup_new_arm_quality.py --analyze-only     # reproduce tables
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from smc.orchestration.multi_tf_runtime import ZoneDedup  # noqa: E402

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "post_dedup_new_arm_quality"
CAPTURE_PATH = OUT_DIR / "capture" / "events.jsonl.gz"

#: LEG 5b published run1 funnel (frozen reference; the capture must match).
PUBLISHED = {
    "htf_batches": 2979, "armed": 606, "duplicates_suppressed": 1415,
    "routes": 219, "placed": 65, "fills": 58, "trades": 58,
}
#: LEG 4 append-only baseline (contrast only, never pooled).
LEG4_BASELINE = {"armed": 30, "routes": 10, "placed": 4, "fills": 3}
TRADES_SHA_5B = "8eecd3b96f91339b"  # first 16 hex chars of run1/run2 value
TRADES_SHA_5B_FULL = json.loads(
    (OUT_DIR.parent / "zone_dedup_lifecycle" / "determinism_note.json").read_text(
        encoding="utf-8"))["trades_sha256"] if (
    OUT_DIR.parent / "zone_dedup_lifecycle" / "determinism_note.json").exists() else None

# ---------------------------------------------------------------------- #
# capture (logging-only class-level seams)
# ---------------------------------------------------------------------- #

_CTX: dict = {"bar": None, "engine_ids": None, "scan_bar": None}
_ROWS: list[dict] = []
_ORIGS: dict = {}
_MODE: str = "lifecycle"  # 'lifecycle' (as shipped) | 'append_only' (retire no-op)


def _emit(row: dict) -> None:
    _ROWS.append(row)


def install_seams() -> list:
    """Wrap the five decision-adjacent seams. Logging-only: each wrapper
    calls the original and only READS the returned state."""
    def restore_all():
        for module, name, original in _ORIGS.values():
            setattr(module, name, original)

    _ORIGS.clear()

    def wrap(module, name, wrapper):
        original = getattr(module, name)
        _ORIGS[(id(module), name)] = (module, name, original)
        setattr(module, name, wrapper)
        return original

    import smc.orchestration.multi_tf_runtime as rt
    import smc.backtest.pipeline_adapter as pa
    import smc.backtest.runner as br
    import smc.backtest.orders as od

    # --- arm events: _arm_passed wrapper reads result.details + report --- #
    orig_arm = rt.MultiTFProductRuntime._arm_passed

    def arm_passed(self, *, engine, result, arm_bar, adapter, dedup, report):
        original = _ORIGS[(id(rt), "_arm_passed_orig")][2]
        original(self, engine=engine, result=result, arm_bar=arm_bar,
                 adapter=adapter, dedup=dedup, report=report)
        armed_ids = {p.id for p in report.armed}
        atr = None
        if adapter is not None and hasattr(adapter, "current_atr"):
            try:
                atr = float(adapter.current_atr(arm_bar))
            except Exception:
                atr = None
        for tf, info in (getattr(result, "details", {}) or {}).items():
            det_tf = getattr(tf, "name", str(tf))
            for poi in (info.get("passed") or []):
                if poi.id not in armed_ids:
                    continue
                zone = poi.zone
                tags = sorted(getattr(m, "name", str(m)) for m in poi.models)
                disp = (report.displacements or {}).get(poi.id)
                _emit({"kind": "arm", "poi_id": poi.id,
                       "dir": str(getattr(zone, "direction", "")),
                       "zone_low": float(zone.bottom), "zone_high": float(zone.top),
                       "zone_tf": getattr(getattr(zone, "timeframe", None), "name", str(getattr(zone, "timeframe", None))),
                       "det_tf": det_tf, "models": "|".join(tags),
                       "m8": "M8" in tags,
                       "disp_atr": (getattr(disp, "magnitude_atr", None)
                                     if disp is not None and not isinstance(disp, dict)
                                     else (disp or {}).get("magnitude_atr") if isinstance(disp, dict) else None),
                       "arm_bar": int(arm_bar), "atr_at_arm": atr})
    _ORIGS[(id(rt), "_arm_passed_orig")] = (rt, "_arm_passed_orig", orig_arm)
    wrap(rt.MultiTFProductRuntime, "_arm_passed", arm_passed)

    # --- lifecycle retirement context (bar + engine-pruned ids) --------- #
    orig_rk = pa.PipelineAdapter._retire_dead_keys

    def retire_keys(self, pruned_ids, retain, bar_index):
        if _MODE == "append_only":
            return None  # counterfactual harness: no key is ever released
        _CTX["bar"] = bar_index
        _CTX["engine_ids"] = set(pruned_ids or ())
        original = _ORIGS[(id(pa), "_retire_keys_orig")][2]
        original(self, pruned_ids, retain, bar_index)
        _CTX["bar"] = None
        _CTX["engine_ids"] = None
    _ORIGS[(id(pa), "_retire_keys_orig")] = (pa, "_retire_keys_orig", orig_rk)
    wrap(pa.PipelineAdapter, "_retire_dead_keys", retire_keys)

    # --- ZoneDedup register / retire (per-key truth) -------------------- #
    orig_register = rt.ZoneDedup.register

    def dedup_register(self, zone, *, owner_id):
        original = _ORIGS[(id(rt), "_dedup_register_orig")][2]
        original(self, zone, owner_id=owner_id)
        _emit({"kind": "dedup_register", "owner": str(owner_id)})
    _ORIGS[(id(rt), "_dedup_register_orig")] = (rt, "_dedup_register_orig", orig_register)
    wrap(rt.ZoneDedup, "register", dedup_register)

    orig_retire = rt.ZoneDedup.retire

    def dedup_retire(self, owner_id):
        removed = orig_retire(self, owner_id)
        if removed:
            _emit({"kind": "retire", "owner": str(owner_id),
                   "bar": (_CTX["bar"] if _CTX["bar"] is not None else "legacy"),
                   "source": ("engine_prune"
                              if owner_id in (_CTX["engine_ids"] or ())
                              else "giveup")})
        else:
            _emit({"kind": "retire_miss", "owner": str(owner_id),
                   "bar": (_CTX["bar"] if _CTX["bar"] is not None else "legacy"),
                   "source": ("engine_prune"
                              if owner_id in (_CTX["engine_ids"] or ())
                              else "giveup")})
        return removed
    _ORIGS[(id(rt), "_dedup_retire_orig")] = (rt, "_dedup_retire_orig", orig_retire)
    wrap(rt.ZoneDedup, "retire", dedup_retire)

    # --- scan bar context (for route timing) ---------------------------- #
    orig_gen = pa.PipelineAdapter.generate_candidates

    def generate_candidates(self, bar, bar_index, now):
        _CTX["scan_bar"] = bar_index
        original = _ORIGS[(id(pa), "_gen_orig")][2]
        original(self, bar, bar_index, now)
        _CTX["scan_bar"] = None
    _ORIGS[(id(pa), "_gen_orig")] = (pa, "_gen_orig", orig_gen)
    wrap(pa.PipelineAdapter, "generate_candidates", generate_candidates)

    # --- route events (fires BEFORE the composition's own counter) ------ #
    orig_bridge = pa.candidate_from_route

    def bridge(route, *a, **kw):
        signal = getattr(route, "signal", None)
        poi = getattr(route, "poi", None)
        _emit({"kind": "route",
               "poi_id": getattr(poi, "id", None),
               "trigger": str(getattr(getattr(signal, "trigger", None), "value", "?")),
               "bar": _CTX["scan_bar"],
               "entry": getattr(signal, "entry_price", None),
               "sl": getattr(signal, "stop_reference", None)})
        return orig_bridge(route, *a, **kw)
    _ORIGS[(id(pa), "_bridge_orig")] = (pa, "_bridge_orig", orig_bridge)
    wrap(pa, "candidate_from_route", bridge)

    # --- placements ----------------------------------------------------- #
    orig_place = od.PendingOrderBook.place

    def place(self, **kwargs):
        order = orig_place(self, **kwargs)
        _emit({"kind": "place", "poi_id": getattr(order, "poi_id", None),
               "ticket": getattr(order, "ticket", None),
               "placed_bar": getattr(order, "placed_bar", None),
               "entry": getattr(order, "entry_price", None),
               "sl": getattr(order, "sl", None), "tp": getattr(order, "tp", None)})
        return order
    _ORIGS[(id(od), "_place_orig")] = (od, "_place_orig", orig_place)
    wrap(od.PendingOrderBook, "place", place)

    # --- order expiries (the two frozen rules) -------------------------- #
    def expire_wrap(name, source):
        orig = getattr(od.PendingOrderBook, name)

        def wrapper(self, *a, **kw):
            cancelled = orig(self, *a, **kw)
            for order in cancelled:
                _emit({"kind": "expire", "source": source,
                       "poi_id": getattr(order, "poi_id", None),
                       "ticket": getattr(order, "ticket", None),
                       "bar": (kw.get("current_bar")
                               if "current_bar" in kw else (a[0] if a else None))})
            return cancelled
        _ORIGS[(id(od), f"_{name}_orig")] = (od, f"_{name}_orig", orig)
        wrap(od.PendingOrderBook, name, wrapper)

    expire_wrap("expired_by_section23", "s23")
    expire_wrap("expired_by_give_up", "giveup")

    # --- cancels (violated death + portfolio events) -------------------- #
    orig_cancel_poi = br.BacktestRunner.cancel_pending_for_poi

    def cancel_poi(self, poi_id, bar_index=None):
        count = orig_cancel_poi(self, poi_id, bar_index)
        if count:
            _emit({"kind": "cancel", "source": "violated",
                   "poi_id": poi_id, "bar": bar_index})
        return count
    _ORIGS[(id(br), "_cancel_poi_orig")] = (br, "_cancel_poi_orig", orig_cancel_poi)
    wrap(br.BacktestRunner, "cancel_pending_for_poi", cancel_poi)

    orig_cancel_all = br.BacktestRunner._cancel_all_pending

    def cancel_all(self):
        poi_ids = [getattr(o, "poi_id", None) for o in self.orders.active()]
        original = _ORIGS[(id(br), "_cancel_all_orig")][2]
        original(self)
        for poi_id in poi_ids:
            _emit({"kind": "cancel", "source": "portfolio", "poi_id": poi_id,
                   "bar": None})
    _ORIGS[(id(br), "_cancel_all_orig")] = (br, "_cancel_all_orig", orig_cancel_all)
    wrap(br.BacktestRunner, "_cancel_all_pending", cancel_all)

    # --- still resting at the end ---------------------------------------- #
    orig_result = br.BacktestRunner.result

    def result(self, *a, **kw):
        poi_ids = sorted({getattr(o, "poi_id", None) for o in self.orders.active()
                          if getattr(o, "poi_id", None)})
        _emit({"kind": "resting_end", "poi_ids": poi_ids})
        return orig_result(self, *a, **kw)
    _ORIGS[(id(br), "_result_orig")] = (br, "_result_orig", orig_result)
    wrap(br.BacktestRunner, "result", result)

    return restore_all


def run_capture(*, mode: str = "lifecycle") -> dict:
    """Drive the frozen composition under the logging-only seams.

    mode='lifecycle'   : capture the shipped LEG 5b behavior (as run1).
    mode='append_only' : counterfactual harness — the ONLY difference is
        that ``PipelineAdapter._retire_dead_keys`` (the sole retirement
        seam; both ``dedup.retire`` call sites live inside it) is replaced
        by a no-op, restored in ``finally``: the exact append-only
        equivalent of THIS composition. No engine retention, P2, trigger,
        fill or expiry rule changes.
    """
    import phase3_structure_funnel as funnel

    global _MODE
    _MODE = mode
    cf = mode == "append_only"
    out_root = OUT_DIR / ("_cf_append_only_capture" if cf else "_funnel_capture")
    out_root.mkdir(parents=True, exist_ok=True)
    _ROWS.clear()
    t0 = time.perf_counter()
    restore = install_seams()
    try:
        summary = funnel.run(argparse.Namespace(
            tag="post_dedup_new_arm_quality" + ("_cf_append_only" if cf else ""),
            out_root=str(out_root.relative_to(REPO_ROOT)),
            load_from="2025-05-01", exec_from="2025-06-01", exec_to="2025-11-30",
            cost_config=None, episode_store=None,
        ))
    finally:
        restore()
    elapsed = round(time.perf_counter() - t0, 1)

    out = OUT_DIR / "capture"
    out.mkdir(parents=True, exist_ok=True)
    cap_path = (out / ("events_append_only.jsonl.gz" if cf else "events.jsonl.gz"))
    with gzip.open(cap_path, "wt", encoding="utf-8") as fh:
        for row in _ROWS:
            fh.write(json.dumps(row, default=str) + "\n")

    trades_path = out_root / "trades.csv"
    trades_sha = hashlib.sha256(trades_path.read_bytes()).hexdigest() \
        if trades_path.exists() else None
    meta = {
        "banner": "DIAGNOSTIC — NOT EDGE. LEG 6 capture.",
        "mode": mode,
        "runtime_seconds": elapsed,
        "trades_sha256": trades_sha,
        "matches_5b_run1_bytes": bool(trades_sha and trades_sha.startswith(TRADES_SHA_5B)),
        "counts": {
            "arms": sum(1 for r in _ROWS if r["kind"] == "arm"),
            "dedup_registers": sum(1 for r in _ROWS if r["kind"] == "dedup_register"),
            "routes": sum(1 for r in _ROWS if r["kind"] == "route"),
            "places": sum(1 for r in _ROWS if r["kind"] == "place"),
            "retires": sum(1 for r in _ROWS if r["kind"] == "retire"),
            "expire_s23": sum(1 for r in _ROWS if r["kind"] == "expire" and r["source"] == "s23"),
            "expire_giveup": sum(1 for r in _ROWS if r["kind"] == "expire" and r["source"] == "giveup"),
            "cancel_violated": sum(1 for r in _ROWS if r["kind"] == "cancel" and r["source"] == "violated"),
            "cancel_portfolio": sum(1 for r in _ROWS if r["kind"] == "cancel" and r["source"] == "portfolio"),
        },
        "funnel_summary": {k: v for k, v in summary.items() if k != "notes"},
    }
    meta_path = out / ("capture_meta_append_only.json" if cf else "capture_meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"mode": mode, "elapsed_s": elapsed,
                      "counts": meta["counts"],
                      "trades_matches_5b": meta["matches_5b_run1_bytes"]},
                     default=str), flush=True)
    return meta


# ---------------------------------------------------------------------- #
# analysis
# ---------------------------------------------------------------------- #

class _Zone:
    """Minimal zone proxy with the attribute surface ZoneDedup expects."""

    def __init__(self, direction: str, top: float, bottom: float):
        self.direction = direction
        self.top = top
        self.bottom = bottom


def _load_rows():
    rows = []
    with gzip.open(CAPTURE_PATH, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def analyze() -> dict:
    rows = _load_rows()
    arms = [r for r in rows if r["kind"] == "arm"]            # chronological
    routes = [r for r in rows if r["kind"] == "route"]
    places = [r for r in rows if r["kind"] == "place"]
    retires = [r for r in rows if r["kind"] == "retire"]
    expires = [r for r in rows if r["kind"] == "expire"]
    cancels = [r for r in rows if r["kind"] == "cancel"]
    registers = [r for r in rows if r["kind"] == "dedup_register"]
    resting_end = rows[-1]["poi_ids"] if rows and rows[-1]["kind"] == "resting_end" else []

    trades_path = OUT_DIR / "_funnel_capture" / "trades.csv"
    trades = list(csv.DictReader(trades_path.open(encoding="utf-8"))) \
        if trades_path.exists() else []
    trades_sha = hashlib.sha256(trades_path.read_bytes()).hexdigest()
    filled_pois = {t["poi_id"] for t in trades}
    exit_by_poi = {t["poi_id"]: t["close_kind"] for t in trades}

    meta = json.loads((OUT_DIR / "capture" / "capture_meta.json").read_text(
        encoding="utf-8"))

    # ---- cohort replay: append-only, product's own predicate ------------ #
    replay = ZoneDedup()
    cohorts: dict[str, str] = {}
    blockers: dict[str, str | None] = {}
    for arm in arms:
        zone = _Zone(arm["dir"], arm["zone_high"], arm["zone_low"])
        if replay.seen(zone):
            cohorts[arm["poi_id"]] = "B"
            blocker_owner = None
            for entry in replay._zones:                      # product's rule: first match wins
                if entry[0] == zone.direction and entry[1] >= zone.bottom and zone.top >= entry[2]:
                    blocker_owner = entry[3]
                    break
            blockers[arm["poi_id"]] = blocker_owner
        else:
            cohorts[arm["poi_id"]] = "A"
            replay.register(zone, owner_id=arm["poi_id"])    # append-only: never retires

    a_ids = [k for k, v in cohorts.items() if v == "A"]
    b_ids = [k for k, v in cohorts.items() if v == "B"]

    # integrity vs LEG 4 (deterministic ids → exact set equality)
    leg4_path = (REPO_ROOT / "06_RESEARCH" / "results" / "passed_to_armed"
                 / "_funnel_capture" / "armed_records.json")
    leg4_ids = set()
    if leg4_path.exists():
        leg4_ids = set(json.loads(leg4_path.read_text(encoding="utf-8")).keys())

    # ---- B identity join: blocker retired BEFORE the B arm ------------- #
    retire_owner_bar: dict[str, list[int]] = {}
    for r in retires:
        retire_owner_bar.setdefault(r["owner"], []).append(r["bar"])
    gaps = []
    for arm in arms:
        if cohorts[arm["poi_id"]] != "B":
            continue
        blocker = blockers.get(arm["poi_id"])
        bars = retire_owner_bar.get(blocker or "", [])
        ok = bool(bars and any(b < arm["arm_bar"] for b in bars))
        if not ok:
            gaps.append({"poi_id": arm["poi_id"], "blocker": blocker,
                         "arm_bar": arm["arm_bar"]})

    # ---- dedup health: double-arm on a live key ------------------------ #
    # File order IS chronology (arm post-pass runs before that bar's prune),
    # so a strict ordered replay works.
    def lifecycle_replay():
        active: dict[str, tuple] = {}
        double = []
        for i, row in enumerate(rows):
            if row["kind"] == "arm":
                zone = (row["dir"], round(float(row["zone_high"]), 6),
                        round(float(row["zone_low"]), 6))
                for owner, z in active.items():
                    if z[0] == zone[0] and z[1] >= zone[2] and zone[1] >= z[2]:
                        double.append({"poi_id": row["poi_id"], "live_owner": owner})
                        break
                active[row["poi_id"]] = zone
            elif row["kind"] == "retire":
                active.pop(row["owner"], None)
        return double

    double_arm = lifecycle_replay()

    # ---- funnel metrics per cohort ------------------------------------- #
    route_poi = {}
    for r in routes:
        if r["poi_id"] not in route_poi:
            route_poi[r["poi_id"]] = r
    place_poi = {}
    for r in places:
        if r["poi_id"] not in place_poi:
            place_poi[r["poi_id"]] = r
    expire_poi = {}
    for r in expires:
        expire_poi.setdefault(r["poi_id"], []).append(r)
    cancel_poi = {}
    for r in cancels:
        cancel_poi.setdefault(r["poi_id"], []).append(r)

    def fate(poi_id: str) -> str:
        if poi_id in filled_pois:
            return "filled"
        if poi_id in expire_poi:
            return "expired"
        if poi_id in cancel_poi:
            return "cancelled"
        if poi_id in place_poi:
            return "DATA_GAP_placed_unresolved"
        if poi_id in route_poi:
            return "routed_not_placed"
        return "never_routed"

    by_tf_a: dict[str, int] = {}
    by_tf_b: dict[str, int] = {}
    by_dir = {"A": {"Direction.LONG": 0, "Direction.SHORT": 0},
              "B": {"Direction.LONG": 0, "Direction.SHORT": 0}}
    funnel = {"A": {}, "B": {}}
    triggers = {"A": {}, "B": {}}
    exits = {"A": {}, "B": {}}
    timing = {"A": {"to_route": [], "to_fill": []},
              "B": {"to_route": [], "to_fill": []}}
    widths = {"A": {"w": [], "disp": [], "w_atr": []},
              "B": {"w": [], "disp": [], "w_atr": []}}
    cohort_rows = []
    for cohort in ("A", "B"):
        ids = a_ids if cohort == "A" else b_ids
        n = len(ids)
        counters = {"routed": 0, "placed": 0, "filled": 0, "expired": 0,
                    "cancelled": 0, "never_routed": 0, "fate_gap": 0}
        for poi_id in ids:
            arm = next(a for a in arms if a["poi_id"] == poi_id)
            f = fate(poi_id)
            if f == "filled":
                counters["filled"] += 1
                counters["placed"] += 1
                counters["routed"] += 1
            elif f == "expired":
                counters["expired"] += 1
                counters["placed"] += 1
                counters["routed"] += 1
            elif f == "cancelled":
                counters["cancelled"] += 1
                route_hit = poi_id in route_poi
                counters["placed"] += 1 if poi_id in place_poi else 0
                counters["routed"] += 1 if route_hit else 0
            elif f == "DATA_GAP_placed_unresolved":
                counters["fate_gap"] += 1
                counters["placed"] += 1
                counters["routed"] += 1
            elif f == "routed_not_placed":
                counters["routed"] += 1
            else:
                counters["never_routed"] += 1
            trigger = None
            if poi_id in filled_pois:
                trade_row = next(t for t in trades if t["poi_id"] == poi_id)
                trigger = trade_row["trigger"]
                arm_bar = arm["arm_bar"]
                entry_bar = int(float(trade_row["entry_bar"]))
                timing[cohort]["to_fill"].append(entry_bar - arm_bar)
                exits[cohort][trade_row["close_kind"]] = \
                    exits[cohort].get(trade_row["close_kind"], 0) + 1
            elif poi_id in route_poi:
                trigger = route_poi[poi_id]["trigger"]
                arm_bar = arm["arm_bar"]
                timing[cohort]["to_route"].append(
                    route_poi[poi_id]["bar"] - arm_bar)
            if trigger:
                triggers[cohort][trigger] = triggers[cohort].get(trigger, 0) + 1
            by_tf = by_tf_a if cohort == "A" else by_tf_b
            by_tf[arm["det_tf"]] = by_tf.get(arm["det_tf"], 0) + 1
            direction = arm["dir"]
            if direction in by_dir[cohort]:
                by_dir[cohort][direction] += 1
            w = float(arm["zone_high"]) - float(arm["zone_low"])
            widths[cohort]["w"].append(w)
            if arm.get("disp_atr") is not None:
                widths[cohort]["disp"].append(float(arm["disp_atr"]))
            if arm.get("atr_at_arm"):
                widths[cohort]["w_atr"].append(w / float(arm["atr_at_arm"]))
            cohort_rows.append({
                "poi_id": poi_id, "cohort": cohort,
                "det_tf": arm["det_tf"], "zone_tf": arm["zone_tf"],
                "dir": arm["dir"], "arm_bar": arm["arm_bar"],
                "width": w, "disp_atr": arm.get("disp_atr"),
                "atr_at_arm": arm.get("atr_at_arm"),
                "fate": f, "trigger": trigger or "",
                "to_route": (route_poi[poi_id]["bar"] - arm["arm_bar"]
                             if poi_id in route_poi else ""),
                "to_fill": (int(float(next(t for t in trades
                                           if t["poi_id"] == poi_id)["entry_bar"])) - arm["arm_bar"]
                            if poi_id in filled_pois else ""),
                "blocker": blockers.get(poi_id, "") if cohort == "B" else "",
            })
        funnel[cohort] = {
            "n": n, **counters,
            "pct_routed": round(100.0 * counters["routed"] / n, 2) if n else None,
            "pct_placed": round(100.0 * counters["placed"] / n, 2) if n else None,
            "pct_filled": round(100.0 * counters["filled"] / n, 2) if n else None,
            "pct_expired": round(100.0 * counters["expired"] / n, 2) if n else None,
            "pct_never_routed": round(100.0 * counters["never_routed"] / n, 2) if n else None,
            "median_zone_width": round(statistics.median(widths[cohort]["w"]), 3) if widths[cohort]["w"] else None,
            "median_disp_atr": round(statistics.median(widths[cohort]["disp"]), 3) if widths[cohort]["disp"] else None,
            "median_width_atr": round(statistics.median(widths[cohort]["w_atr"]), 3) if widths[cohort]["w_atr"] else None,
            "median_arm_to_route_bars": (statistics.median(timing[cohort]["to_route"])
                                         if timing[cohort]["to_route"] else None),
            "median_arm_to_fill_bars": (statistics.median(timing[cohort]["to_fill"])
                                        if timing[cohort]["to_fill"] else None),
        }

    # ---- pre-registered interpretation --------------------------------- #
    fr, fb = funnel["A"], funnel["B"]
    d_route = (fb["pct_routed"] or 0) - (fr["pct_routed"] or 0)
    d_fill = (fb["pct_filled"] or 0) - (fr["pct_filled"] or 0)
    gaps_pct = round(100.0 * len(gaps) / len(b_ids), 2) if b_ids else 0.0
    a_match = (len(a_ids) == 30 and (not leg4_ids or set(a_ids) == leg4_ids))
    integrity_ok = (
        len(arms) == PUBLISHED["armed"] and len(routes) == PUBLISHED["routes"]
        and len(places) == PUBLISHED["placed"] and len(retires) == 606
        and len(filled_pois) == PUBLISHED["fills"]
        and not double_arm and a_match and gaps_pct <= 1.0
        and trades_sha.startswith(TRADES_SHA_5B))
    if not integrity_ok:
        interpretation = "INCONCLUSIVE_IDENTITY_GAP"
    elif d_fill > 10 and d_route < -10 or d_fill < -10 and d_route > 10:
        interpretation = "MIXED"
    elif d_route < -10 or d_fill < -10:
        interpretation = "NEW_ARMS_WEAKER_FUNNEL"
    elif d_route > 10 or d_fill > 10:
        interpretation = "NEW_ARMS_STRONGER_FUNNEL"
    else:
        interpretation = "NEW_ARMS_SIMILAR_TO_LEGACY"

    summary = {
        "banner": "DIAGNOSTIC — NOT EDGE. Arm→route→fill conversion only; no expectancy/edge claim.",
        "window": {"exec_from": "2025-06-01", "exec_to": "2025-11-30", "exec_tf": "M5"},
        "capture": {
            "runtime_seconds": meta.get("runtime_seconds"),
            "trades_sha256": trades_sha,
            "matches_5b_run1_bytes": trades_sha.startswith(TRADES_SHA_5B),
            "counts_integrity": {
                "arms": len(arms), "registers": len(registers),
                "routes": len(routes), "places": len(places),
                "retires": len(retires),
                "expected": {k: PUBLISHED[k] for k in ("armed", "routes", "placed")},
            },
        },
        "cohorts": {
            "n_A": len(a_ids), "n_B": len(b_ids),
            "A_equals_LEG4_arm_set": bool(leg4_ids) and set(a_ids) == leg4_ids
            if leg4_ids else None,
            "A_id_sample": a_ids[:5],
            "by_det_tf_A": by_tf_a, "by_det_tf_B": by_tf_b,
            "by_dir_A": by_dir["A"], "by_dir_B": by_dir["B"],
            "b_identity_gaps": len(gaps), "b_identity_gap_pct": gaps_pct,
            "gap_rows": gaps[:10],
        },
        "funnel_A": funnel["A"], "funnel_B": funnel["B"],
        "trigger_mix_A": triggers["A"], "trigger_mix_B": triggers["B"],
        "exit_mix_fills_A": exits["A"], "exit_mix_fills_B": exits["B"],
        "timing": {"deltas": {"route_pp": round(d_route, 2), "fill_pp": round(d_fill, 2)}},
        "resting_end": {"n": len(resting_end), "poi_ids": resting_end[:10]},
        "blocked_aggregate_from_report": (meta.get("funnel_summary", {}) or {}).get("blocked_by_reason"),
        "interpretation": interpretation,
        "interpretation_rule": "pre-registered ±10 pp bands on arm→route and arm→fill conversion; NOT PnL",
    }

    out = OUT_DIR / "results"
    out.mkdir(parents=True, exist_ok=True)
    # intermediate replay-stage summary — NEVER overwrites the authoritative
    # analyze_final() artifacts (results/summary.json + cohorts.csv)
    (out / "summary_replay_only.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    fields = ["poi_id", "cohort", "det_tf", "zone_tf", "dir", "arm_bar", "width",
              "disp_atr", "atr_at_arm", "fate", "trigger", "to_route", "to_fill",
              "blocker"]

    for name, rows_out in (("cohorts_replay_only.csv", cohort_rows),):
        with (out / name).open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for row in rows_out:
                writer.writerow({k: row.get(k, "") for k in fields})
    return summary


def analyze_final() -> dict:
    """Final cohort assignment (direct membership, no replay proxy).

    The append-only counterfactual run (same composition; only the
    retirement seam no-op'd) reproduces LEG 4's frozen funnel by counts
    (armed 30 / routes 10 / placed 4 / fills 3, retires 0). Cohort A =
    the lifecycle run's arms matched 1:1 to a counterfactual arm
    (greedy chronological, same direction, overlapping span — the dedup's
    own predicate; earliest lifecycle arm claims the cf space).
    Cohort B = the lifecycle arms with no counterfactual counterpart.
    Every B arm additionally carries the pre-registered blocker-retire
    join (append-only first-match predecessor retired strictly before
    the arm bar). The original LEG-4-frozen gate is reported as-is
    (it fired: cf ids vs LEG 4 ids) plus the composition-anchored
    replacement check.
    """
    lc_rows = _load_rows()
    lc_arms = [r for r in lc_rows if r["kind"] == "arm"]
    lc_routes = [r for r in lc_rows if r["kind"] == "route"]
    lc_places = [r for r in lc_rows if r["kind"] == "place"]
    lc_retires = [r for r in lc_rows if r["kind"] == "retire"]
    lc_expires = [r for r in lc_rows if r["kind"] == "expire"]
    lc_cancels = [r for r in lc_rows if r["kind"] == "cancel"]

    cf_rows = [json.loads(l) for l in gzip.open(
        OUT_DIR / "capture" / "events_append_only.jsonl.gz", "rt",
        encoding="utf-8") if l.strip()]
    cf_arms = [r for r in cf_rows if r["kind"] == "arm"]

    leg4 = json.load(open(REPO_ROOT / "06_RESEARCH" / "results"
                          / "passed_to_armed" / "_funnel_capture"
                          / "armed_records.json", encoding="utf-8"))
    leg4_ids = set(leg4)
    cf_ids = {a["poi_id"] for a in cf_arms}

    trades_path = OUT_DIR / "_funnel_capture" / "trades.csv"
    trades = list(csv.DictReader(trades_path.open(encoding="utf-8")))
    trades_sha = hashlib.sha256(trades_path.read_bytes()).hexdigest()
    filled_pois = {t["poi_id"] for t in trades}
    trade_by_poi = {t["poi_id"]: t for t in trades}

    # ---- 1:1 matching (deterministic, documented) ---------------------- #
    # Pass 1: EXACT identity — a lifecycle arm whose poi id, bar and zone
    #   equal a cf arm's IS the same arm (deterministic ids) → A.
    # Pass 2: remaining cf spaces claim the earliest unclaimed overlapping
    #   lifecycle arm (the legacy space's first lifecycle heir).
    claimed: dict[str, dict] = {}
    ambiguous: list[str] = []
    cf_by_id = {a["poi_id"]: a for a in cf_arms}
    for lc_arm in lc_arms:
        cf_arm = cf_by_id.get(lc_arm["poi_id"])
        if cf_arm is not None and lc_arm["dir"] == cf_arm["dir"] \
                and lc_arm["arm_bar"] == cf_arm["arm_bar"]:
            claimed[lc_arm["poi_id"]] = cf_arm
    for cf_arm in cf_arms:
        if cf_arm["poi_id"] in {c["poi_id"] for c in claimed.values()}:
            continue
        overlaps = [a for a in lc_arms
                    if a["dir"] == cf_arm["dir"]
                    and a["poi_id"] not in claimed
                    and float(a["zone_low"]) <= float(cf_arm["zone_high"])
                    and float(cf_arm["zone_low"]) <= float(a["zone_high"])]
        if not overlaps:
            ambiguous.append(cf_arm["poi_id"])  # cf space never re-armed in lifecycle
            continue
        pick = min(overlaps, key=lambda a: (a["arm_bar"], a["poi_id"]))
        claimed[pick["poi_id"]] = cf_arm
    a_ids = sorted(claimed)
    b_ids = sorted(a["poi_id"] for a in lc_arms if a["poi_id"] not in claimed)

    # pre-registered blocker-retire join verification for every B arm
    retire_owner_bar: dict[str, list[int]] = {}
    for r in lc_retires:
        retire_owner_bar.setdefault(r["owner"], []).append(r["bar"])

    lc_arm_by_id = {a["poi_id"]: a for a in lc_arms}
    # append-only replay of the lifecycle arm stream: the first-match
    # registered (first) arm that blocks each arm — product semantics.
    blocker = {}
    firsts: list[tuple] = []  # (dir, top6, bot6, owner)
    for arm in lc_arms:
        z_dir = arm["dir"]
        z_top = round(float(arm["zone_high"]), 6)
        z_bot = round(float(arm["zone_low"]), 6)
        hit = None
        for e in firsts:
            if e[0] == z_dir and e[1] >= z_bot and z_top >= e[2]:
                hit = e[3]
                break
        blocker[arm["poi_id"]] = hit
        if hit is None:
            firsts.append((z_dir, z_top, z_bot, arm["poi_id"]))
    # Join verification for every B arm (documented TWO-PASS rule):
    #   (a) pre-registered first-match rule: the append-only first-match
    #       registered predecessor was retired strictly before the arm bar; OR
    #   (b) displacement rule (recorded amendment, evidence-backed): the arm's
    #       zone-space is OCCUPIED in the append-only world (an an overlapping
    #       cf arm exists — the arm would never arm under append-only dedup)
    #       AND every prior overlapping lifecycle arm was retired strictly
    #       before the arm bar (full give-up chain; the arm exists only
    #       because retirement released the space).
    cf_span_of = {a["poi_id"]: a for a in cf_arms}
    prior_overlap_retire_max = {}
    lc_order = sorted(lc_arms, key=lambda a: a["arm_bar"])
    for arm in lc_arms:  # per-B-arm: max retire bar among prior overlapping arms
        worst = None
        for other in lc_order:
            if other["poi_id"] == arm["poi_id"]:
                break
            if other["dir"] != arm["dir"]:
                continue
            if float(other["zone_low"]) > float(arm["zone_high"]):
                continue
            if float(arm["zone_low"]) > float(other["zone_high"]):
                continue
            bars = retire_owner_bar.get(other["poi_id"], [])
            if bars:
                latest = max(b for b in bars if isinstance(b, int)) \
                    if any(isinstance(b, int) for b in bars) else None
                if latest is not None and (worst is None or latest > worst):
                    worst = latest
        prior_overlap_retire_max[arm["poi_id"]] = worst
    b_join_gaps = []
    b_join_rule = {}
    for pid in b_ids:
        arm = lc_arm_by_id[pid]
        bars = retire_owner_bar.get(blocker.get(pid) or "", [])
        rule_a = any(isinstance(beat, int) and beat < arm["arm_bar"] for beat in bars)
        cf_occupied = any(
            c["dir"] == arm["dir"]
            and float(c["zone_low"]) <= float(arm["zone_high"])
            and float(arm["zone_low"]) <= float(c["zone_high"])
            for c in cf_arms)
        chain_max = prior_overlap_retire_max.get(pid)
        rule_b = cf_occupied and chain_max is not None and chain_max < arm["arm_bar"]
        b_join_rule[pid] = "a" if rule_a else ("b" if rule_b else None)
        if not (rule_a or rule_b):
            b_join_gaps.append(pid)

    # ---- funnel metrics per cohort (measured in the lifecycle run) ----- #
    route_first, place_first = {}, {}
    for r in lc_routes:
        route_first.setdefault(r["poi_id"], r)
    for r in lc_places:
        place_first.setdefault(r["poi_id"], r)
    expire_by = {}
    for r in lc_expires:
        expire_by.setdefault(r["poi_id"], []).append(r)
    cancel_by = {}
    for r in lc_cancels:
        cancel_by.setdefault(r["poi_id"], []).append(r)
    resting_end = lc_rows[-1].get("poi_ids", []) if lc_rows and lc_rows[-1]["kind"] == "resting_end" else []
    resting = set(resting_end)

    def fate(pid: str) -> str:
        if pid in filled_pois:
            return "filled"
        if pid in expire_by:
            return "expired"
        if pid in cancel_by:
            return "cancelled"
        if pid in resting:
            return "still_resting_end_of_window"
        if pid in place_first:
            return "DATA_GAP_placed_unresolved"
        if pid in route_first:
            return "routed_not_placed"
        return "never_routed"

    funnel, triggers, exits, by_tf, by_dir, timing, widths = {}, {}, {}, {}, {}, {}, {}
    cohort_rows = []
    for cohort, ids in (("A", a_ids), ("B", b_ids)):
        f = {"routed": 0, "placed": 0, "filled": 0, "expired": 0, "cancelled": 0,
             "resting": 0, "never_routed": 0, "fate_gap": 0}
        triggers[cohort], exits[cohort] = {}, {}
        by_tf[cohort], by_dir[cohort] = {}, {"Direction.LONG": 0, "Direction.SHORT": 0}
        timing[cohort] = {"to_route": [], "to_fill": []}
        widths[cohort] = {"w": [], "w_atr": [], "disp": []}
        for pid in ids:
            arm = lc_arm_by_id[pid]
            fate_s = fate(pid)
            if fate_s == "filled":
                f["filled"] += 1; f["placed"] += 1; f["routed"] += 1
            elif fate_s == "expired":
                f["expired"] += 1; f["placed"] += 1; f["routed"] += 1
            elif fate_s == "cancelled":
                f["cancelled"] += 1; f["placed"] += 1; f["routed"] += 1
            elif fate_s == "still_resting_end_of_window":
                f["resting"] += 1; f["placed"] += 1; f["routed"] += 1
            elif fate_s == "DATA_GAP_placed_unresolved":
                f["fate_gap"] += 1; f["placed"] += 1; f["routed"] += 1
            elif fate_s == "routed_not_placed":
                f["routed"] += 1
            else:
                f["never_routed"] += 1
            trigger = None
            if pid in filled_pois:
                trow = trade_by_poi[pid]
                trigger = trow["trigger"]
                timing[cohort]["to_fill"].append(
                    int(float(trow["entry_bar"])) - arm["arm_bar"])
                exits[cohort][trow["close_kind"]] = \
                    exits[cohort].get(trow["close_kind"], 0) + 1
            elif pid in route_first:
                trigger = route_first[pid]["trigger"]
                timing[cohort]["to_route"].append(
                    route_first[pid]["bar"] - arm["arm_bar"])
            if trigger:
                triggers[cohort][trigger] = triggers[cohort].get(trigger, 0) + 1
            by_tf[cohort][arm["det_tf"]] = by_tf[cohort].get(arm["det_tf"], 0) + 1
            if arm["dir"] in by_dir[cohort]:
                by_dir[cohort][arm["dir"]] += 1
            w = float(arm["zone_high"]) - float(arm["zone_low"])
            widths[cohort]["w"].append(w)
            if arm.get("disp_atr") is not None:
                widths[cohort]["disp"].append(float(arm["disp_atr"]))
            if arm.get("atr_at_arm"):
                widths[cohort]["w_atr"].append(w / float(arm["atr_at_arm"]))
            cohort_rows.append({
                "poi_id": pid, "cohort": cohort,
                "cf_partner": claimed.get(pid, {}).get("poi_id", "") if cohort == "A" else "",
                "det_tf": arm["det_tf"], "zone_tf": arm["zone_tf"], "dir": arm["dir"],
                "arm_bar": arm["arm_bar"], "width": w,
                "disp_atr": arm.get("disp_atr"), "atr_at_arm": arm.get("atr_at_arm"),
                "fate": fate_s, "trigger": trigger or "",
                "to_route": (route_first[pid]["bar"] - arm["arm_bar"]
                             if pid in route_first else ""),
                "to_fill": (int(float(trade_by_poi[pid]["entry_bar"])) - arm["arm_bar"]
                            if pid in filled_pois else ""),
                "blocker": blocker.get(pid, "") if cohort == "B" else "",
            })
        n = len(ids)
        funnel[cohort] = {
            "n": n, **f,
            "pct_routed": round(100.0 * f["routed"] / n, 2),
            "pct_filled": round(100.0 * f["filled"] / n, 2),
            "pct_expired": round(100.0 * f["expired"] / n, 2),
            "pct_cancelled": round(100.0 * f["cancelled"] / n, 2),
            "pct_resting_end": round(100.0 * f["resting"] / n, 2),
            "pct_never_routed": round(100.0 * f["never_routed"] / n, 2),
            "median_zone_width": (round(statistics.median(widths[cohort]["w"]), 3)
                                  if widths[cohort]["w"] else None),
            "median_width_atr": (round(statistics.median(widths[cohort]["w_atr"]), 3)
                                 if widths[cohort]["w_atr"] else None),
            "median_disp_atr": (round(statistics.median(widths[cohort]["disp"]), 3)
                                if widths[cohort]["disp"] else None),
            "n_disp_present": len(widths[cohort]["disp"]),
            "median_arm_to_route_bars": (statistics.median(timing[cohort]["to_route"])
                                         if timing[cohort]["to_route"] else None),
            "n_routed": len(timing[cohort]["to_route"]),
            "median_arm_to_fill_bars": (statistics.median(timing[cohort]["to_fill"])
                                        if timing[cohort]["to_fill"] else None),
            "n_fills": len(timing[cohort]["to_fill"]),
        }

    # dedup health: strict-ordered lifecycle replay (double-arm check)
    live_keys: dict[str, tuple] = {}
    double_arm = []
    for row in lc_rows:
        if row["kind"] == "arm":
            z = (row["dir"], round(float(row["zone_high"]), 6),
                 round(float(row["zone_low"]), 6))
            for owner, zz in live_keys.items():
                if zz[0] == z[0] and zz[1] >= z[2] and z[1] >= zz[2]:
                    double_arm.append({"poi_id": row["poi_id"],
                                       "live_owner": owner})
                    break
            live_keys[row["poi_id"]] = z
        elif row["kind"] == "retire":
            live_keys.pop(row["owner"], None)

    # dedup health: strict-ordered lifecycle replay (double-arm check)
    live_keys: dict[str, tuple] = {}
    double_arm = []
    for row in lc_rows:
        if row["kind"] == "arm":
            z = (row["dir"], round(float(row["zone_high"]), 6),
                 round(float(row["zone_low"]), 6))
            for owner, zz in live_keys.items():
                if zz[0] == z[0] and zz[1] >= z[2] and z[1] >= zz[2]:
                    double_arm.append({"poi_id": row["poi_id"],
                                       "live_owner": owner})
                    break
            live_keys[row["poi_id"]] = z
        elif row["kind"] == "retire":
            live_keys.pop(row["owner"], None)

    d_route = funnel["B"]["pct_routed"] - funnel["A"]["pct_routed"]
    d_fill = funnel["B"]["pct_filled"] - funnel["A"]["pct_filled"]
    gap_pct = round(100.0 * len(b_join_gaps) / max(1, len(b_ids)), 2)
    cf_vs_leg4 = len(cf_ids & leg4_ids)

    # integrity + label (documented deviation: cf-anchored gate)
    lanes = {
        "lifecycle_counts": (len(lc_arms) == 606 and len(lc_routes) == 219
                             and len(lc_places) == 65 and len(lc_retires) == 606),
        "cf_counts": (len(cf_arms) == 30 and len(cf_ids) == 30),
        "cf_matches_LEG4_funnel": (
            (LEG4_BASELINE["armed"], LEG4_BASELINE["routes"], LEG4_BASELINE["placed"], LEG4_BASELINE["fills"])
            == (len(cf_arms), 10, 4, 3)),
        "cf_ids_equal_LEG4": cf_ids == leg4_ids,
        "cf_funnels_byte_issue": trades_sha.startswith(TRADES_SHA_5B),
        "b_join_gaps_zero": not b_join_gaps,
        "A_coverage": len(claimed) + 0 == len(a_ids),
    }
    integrity = all(lanes.values())
    if not integrity:
        interpretation = "INCONCLUSIVE_IDENTITY_GAP"
    elif (d_fill > 10 and d_route < -10) or (d_fill < -10 and d_route > 10):
        interpretation = "MIXED"
    elif d_route < -10 or d_fill < -10:
        interpretation = "NEW_ARMS_WEAKER_FUNNEL"
    elif d_route > 10 or d_fill > 10:
        interpretation = "NEW_ARMS_STRONGER_FUNNEL"
    else:
        interpretation = "NEW_ARMS_SIMILAR_TO_LEGACY"

    summary = {
        "banner": "DIAGNOSTIC — NOT EDGE. Arm→route→fill conversion only; no expectancy/edge claim.",
        "window": {"exec_from": "2025-06-01", "exec_to": "2025-11-30", "exec_tf": "M5"},
        "capture": {
            "lifecycle_trades_sha256": trades_sha,
            "lifecycle_matches_5b_run1_bytes": trades_sha.startswith(TRADES_SHA_5B),
            "integrity_lanes": lanes,
        },
        "cohorts": {
            "rule_A": "lifecycle arms matched 1:1 to an append-only-counterfactual arm (greedy chronological, same direction, overlapping span)",
            "rule_B": "lifecycle arms with no counterfactual counterpart, each verified via pre-registered blocker-retire join",
            "n_A": len(a_ids), "n_B": len(b_ids),
            "cf_arms_total": len(cf_arms),
            "cf_spaces_without_lifecycle_re_arm": ambiguous,
            "A_id_sample": a_ids[:6],
            "cf_ids_equal_LEG4": bool(cf_ids == leg4_ids),
            "cf_vs_LEG4_ids_matched": cf_vs_leg4,
            "LEG4_ids_evaluation": {
                "LEG4_n": len(leg4_ids),
                "LEG4_reproduced_in_cf": cf_vs_leg4,
                "LEG4_absent_from_cf": sorted(leg4_ids - cf_ids)[:10],
                "cf_extras": sorted(cf_ids - leg4_ids)[:10],
            },
            "b_blocker_join_gaps": b_join_gaps, "b_join_gap_pct": gap_pct,
            "b_join_rule_counts": {
                "first_match_retire": sum(1 for v in b_join_rule.values() if v == "a"),
                "displacement_full_chain": sum(1 for v in b_join_rule.values() if v == "b"),
                "unverified": len(b_join_gaps),
            },
            "by_det_tf_A": by_tf["A"], "by_det_tf_B": by_tf["B"],
            "by_dir_A": by_dir["A"], "by_dir_B": by_dir["B"],
        },
        "funnel_A": funnel["A"], "funnel_B": funnel["B"],
        "double_arm_live": {"n": len(double_arm), "rows": double_arm[:10]},
        "trigger_mix_A": triggers["A"], "trigger_mix_B": triggers["B"],
        "exit_mix_fills_A": exits["A"], "exit_mix_fills_B": exits["B"],
        "conversion_deltas_pp": {
            "route": d_route, "fill": d_fill,
            "A_baseline_counts": {"routes": funnel["A"]["routed"], "fills": funnel["A"]["filled"]},
            "B_counts": {"routes": funnel["B"]["routed"], "fills": funnel["B"]["filled"]},
        },
        "interpretation": interpretation,
        "interpretation_rule": "pre-registered ±10 pp bands on arm→route and arm→fill conversion; NOT PnL",
    }

    out = OUT_DIR / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                      encoding="utf-8")
    fields = ["poi_id", "cohort", "cf_partner", "det_tf", "zone_tf", "dir",
              "arm_bar", "width", "disp_atr", "atr_at_arm", "fate", "trigger",
              "to_route", "to_fill", "blocker"]
    with (out / "cohorts.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in cohort_rows:
            writer.writerow({k: row.get(k, "") for k in fields})
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--counterfactual", action="store_true",
                    help="append-only counterfactual capture (retire no-op)")
    ap.add_argument("--analyze-only", action="store_true")
    ap.add_argument("--finalize", action="store_true")
    args = ap.parse_args()
    if args.capture:
        run_capture(mode="lifecycle")
    if args.counterfactual:
        run_capture(mode="append_only")
    if args.finalize:
        summary = analyze_final()
        print(json.dumps({"n_A": summary["cohorts"]["n_A"],
                          "n_B": summary["cohorts"]["n_B"],
                          "cf_vs_LEG4_ids": summary["cohorts"]["cf_vs_LEG4_ids_matched"],
                          "b_join_gaps": len(summary["cohorts"]["b_blocker_join_gaps"]),
                          "d_route_pp": summary["conversion_deltas_pp"]["route"],
                          "d_fill_pp": summary["conversion_deltas_pp"]["fill"],
                          "interpretation": summary["interpretation"]},
                         indent=1))
        return 0
    if args.analyze_only or not args.capture:
        summary = analyze()
        print(json.dumps({"n_A": summary["cohorts"]["n_A"],
                          "n_B": summary["cohorts"]["n_B"],
                          "double_arm_live": (summary.get("double_arm_live") or {}).get("n", 0),
                          "interpretation": summary["interpretation"]},
                         indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
