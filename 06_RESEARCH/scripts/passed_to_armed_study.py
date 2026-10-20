"""LEG 4 — passed → armed attribution (PASS disposition audit).

Authority: ``00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md`` (LEG 4).

Question: LEG 3 cleared PLACE → FILL. The frozen product funnel still shows
``passed_validation = 2,021`` against ``armed = 30`` — roughly 1.5% of
validation passes ever enter the seek/scan book. This leg attributes *every*
pass to exactly one disposition bucket and ranks the killers. No rule change.

What the script does
--------------------
1. Drives the frozen product composition by importing
   ``phase3_structure_funnel.run`` unmodified (same seam as LEG 1/LEG 3 — not
   a fork) and installs four **logging-only** wrappers, restored in
   ``finally``:
     * ``MultiTFProductRuntime.run_batch`` — batch context (index, as_of,
       arm_bar) + the batch report's own armed / duplicates / skipped ids;
     * ``MultiTFDetectionDriver.validate_multi`` — the exact per-TF
       ``passed`` list and ``ValidationResult`` list the arm loop will walk
       (identity fields: TF, direction, zone bounds, models, pillar path,
       displacement magnitude);
     * ``ZoneDedup.seen`` / ``ZoneDedup.register`` — the dedup decision per
       POI *and* the blocking (already-armed) zone, with overlap geometry and
       the blocker's arm batch (age);
     * ``PipelineEngine.episode`` / ``PipelineEngine.arm_at`` — the
       already-tracked check and the arm attempt (success or the same
       exception the product would have raised).
   Nothing is re-derived by simulation: every bucket is read from the
   decision the product itself took.
2. Classifies every PASS event into exactly one pre-registered bucket. The
   arm path in ``MultiTFProductRuntime._arm_passed`` has exactly three gates
   (``engine.episode`` → ``dedup.seen`` → ``engine.arm_at``), so any bucket
   other than those three is *code-impossible today* and is reported as 0
   (it stays in the table so the absence is evidence, not an omission).
3. Reports the event-level histogram, the episode-clustered view under the
   product's own ZoneDedup rule, an exact-geometry census, dedup overlap
   geometry, a deterministic autopsy sample, and light time structure.
4. Applies ONE pre-registered label.

Pre-registered label rule (fixed before the run)
------------------------------------------------
    INCONCLUSIVE_LOW_N        n_pass_events < 50
    MIXED                     WIRING_BUG (DATA_GAP or SKIP_OTHER > 1% of
                              passes) — a wiring hole is never hidden
                              behind a filter label
    DEDUP_DOMINATED           dedup share >= 50% AND the dedup matches are
                              same-episode (median coverage of the PASS
                              zone by its blocker >= 0.50)
    ARM_FILTER_IS_BOTTLENECK  dedup share >= 50% but the matches are NOT
                              same-episode (distinct structures swallowed),
                              or the combined intentional-policy share
                              (dedup+freshness+posture+give-up+one-shot+
                              registry+tf+merge) >= 50% with no single
                              bucket reaching 50%
    FRESHNESS_DOMINATED       freshness/touch share >= 50%
    ARM_PATH_HEALTHY          no bucket >= 50%, wiring clean
    MIXED                     otherwise

``coverage`` = overlap / width of the *PASS* zone: 1.0 means the passing zone
sits entirely inside (or exactly on) the blocker, i.e. the same structure
re-emitted. It is a geometric measure only — no rate or edge claim.

Usage:
  python 06_RESEARCH/scripts/passed_to_armed_study.py --capture
  python 06_RESEARCH/scripts/passed_to_armed_study.py --analyze-only
  python 06_RESEARCH/scripts/passed_to_armed_study.py --capture \
      --load-from 2023-11-01 --exec-from 2023-12-01 --exec-to 2025-05-31 \
      --out-dir 06_RESEARCH/results/passed_to_armed/secondary_18m

Diagnostic only — NOT edge.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "passed_to_armed"
EVENTS_PATH = OUT_DIR / "pass_events.jsonl.gz"
SUMMARY_PATH = OUT_DIR / "summary.json"
CSV_PATH = OUT_DIR / "pass_disposition.csv"
BANNER = "DIAGNOSTIC — NOT EDGE"

# Primary window = the frozen 6m product window used by Phase 3 / FR-4 /
# LEG 1 / LEG 3 (warm-up month outside the execution window).
DEFAULT_LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)
DEFAULT_EXEC_FROM = datetime(2025, 6, 1, tzinfo=timezone.utc)
DEFAULT_EXEC_TO = datetime(2025, 11, 30, 23, 59, tzinfo=timezone.utc)
LOAD_FROM = DEFAULT_LOAD_FROM
EXEC_FROM = DEFAULT_EXEC_FROM
EXEC_TO = DEFAULT_EXEC_TO

#: Below this many PASS events no ranking is claimed.
MIN_PASSES_FOR_LABEL = 50
#: A wiring hole is surfaced as MIXED once it reaches this share of passes.
WIRING_SHARE_LIMIT = 0.01
#: A dedup match counts as "same episode" at or above this coverage.
SAME_EPISODE_COVERAGE = 0.50
AUTOPSY_TARGET = 20

BUCKET_ARMED = "ARMED"
BUCKET_DEDUP = "SKIP_DEDUP_EPISODE"
BUCKET_TRACKED = "SKIP_TRACKED"
BUCKET_FRESHNESS = "SKIP_FRESHNESS_TOUCH"
BUCKET_POSTURE = "SKIP_POSTURE"
BUCKET_GIVE_UP = "SKIP_GIVE_UP_EXPIRY"
BUCKET_ONE_SHOT = "SKIP_ONE_SHOT"
BUCKET_REGISTRY = "SKIP_REGISTRY_CAP"
BUCKET_TF = "SKIP_TF_POLICY"
BUCKET_MERGE = "SKIP_MERGE_ORDER"
BUCKET_OTHER = "SKIP_OTHER"
BUCKET_GAP = "DATA_GAP"

BUCKETS = (
    BUCKET_ARMED, BUCKET_DEDUP, BUCKET_TRACKED, BUCKET_FRESHNESS,
    BUCKET_POSTURE, BUCKET_GIVE_UP, BUCKET_ONE_SHOT, BUCKET_REGISTRY,
    BUCKET_TF, BUCKET_MERGE, BUCKET_OTHER, BUCKET_GAP,
)

#: Buckets with no code path in the current product arm loop. They are kept
#: in the table (reported as 0) so the report can state the *absence* of a
#: gate rather than merely omit it.
CODE_IMPOSSIBLE_BUCKETS = (
    BUCKET_FRESHNESS, BUCKET_POSTURE, BUCKET_GIVE_UP, BUCKET_ONE_SHOT,
    BUCKET_REGISTRY, BUCKET_TF, BUCKET_MERGE,
)

#: Buckets that represent deliberate product policy (not a wiring defect).
INTENTIONAL_BUCKETS = (
    BUCKET_DEDUP, BUCKET_FRESHNESS, BUCKET_POSTURE, BUCKET_GIVE_UP,
    BUCKET_ONE_SHOT, BUCKET_REGISTRY, BUCKET_TF, BUCKET_MERGE,
)

# ---------------------------------------------------------------------- #
# Capture (logging-only wrappers, restored in finally)
# ---------------------------------------------------------------------- #

_PASSES: list[dict] = []
_ORIG = {}
_CTX: dict = {
    "active": False,
    "batch": None,
    "n_batches": 0,
    "cur_id": None,
    "cur_pending": False,
    "last_armed": None,
}
_DEC: dict[str, dict] = {}
_REGISTRY: list[dict] = []
_REPORTS: list[dict] = []


def _reset_capture() -> None:
    _PASSES.clear()
    _DEC.clear()
    _REGISTRY.clear()
    _REPORTS.clear()
    _CTX.update(active=False, batch=None, n_batches=0, cur_id=None,
                cur_pending=False, last_armed=None)


def _decode(value) -> dict:
    """Per-POI decision record (created on first touch)."""
    rec = _DEC.get(value)
    if rec is None:
        rec = {
            "episode_calls": 0,
            "tracked": None,
            "dedup_calls": 0,
            "dedup": None,
            "blocker": None,
            "armed": False,
            "arm_error": None,
        }
        _DEC[value] = rec
    return rec


def _zone_bounds(zone) -> tuple[float, float]:
    return float(zone.bottom), float(zone.top)


def overlap_metrics(cand_low: float, cand_high: float,
                    blocker_low: float, blocker_high: float) -> dict:
    """Overlap of a PASS zone with its blocking (already armed) zone.

    ``coverage`` is the share of the PASS zone covered by the blocker:
    1.0 = the passing zone sits entirely inside / on the blocker, i.e. the
    same structure re-emitted. Purely geometric; no inference about outcome.
    """
    overlap = min(cand_high, blocker_high) - max(cand_low, blocker_low)
    if overlap <= 0:
        overlap = 0.0
    cand_width = cand_high - cand_low
    blocker_width = blocker_high - blocker_low
    union = max(cand_high, blocker_high) - min(cand_low, blocker_low)
    return {
        "overlap_abs": overlap,
        "coverage": (overlap / cand_width) if cand_width > 0 else 0.0,
        "blocker_coverage": (overlap / blocker_width) if blocker_width > 0 else 0.0,
        "jaccard": (overlap / union) if union > 0 else 0.0,
        "identical_bounds": (
            round(cand_low, 6) == round(blocker_low, 6)
            and round(cand_high, 6) == round(blocker_high, 6)
        ),
    }


def _match_blocker(registered: list[tuple[str, float, float]],
                   direction: str, low: float, high: float):
    """First registered zone the product's own predicate would match.

    Mirrors ``ZoneDedup.seen`` exactly (same direction, inclusive overlap,
    registration order, 6dp canonical bounds) so the reported blocker is the
    one the product actually compared against.
    """
    for index, (known_direction, known_top, known_bottom) in enumerate(registered):
        if known_direction != direction:
            continue
        if known_top >= low and high >= known_bottom:
            return index, known_top, known_bottom
    return None, None, None


def install_capture():
    """Install the logging-only wrappers; returns the restore callable."""
    from smc.orchestration.engine import PipelineEngine
    from smc.orchestration.multi_tf import MultiTFDetectionDriver
    from smc.orchestration.multi_tf_runtime import (MultiTFProductRuntime,
                                                    ZoneDedup)

    _ORIG["run_batch"] = MultiTFProductRuntime.run_batch
    _ORIG["validate_multi"] = MultiTFDetectionDriver.validate_multi
    _ORIG["seen"] = ZoneDedup.seen
    _ORIG["register"] = ZoneDedup.register
    _ORIG["episode"] = PipelineEngine.episode
    _ORIG["arm_at"] = PipelineEngine.arm_at

    orig_run_batch = _ORIG["run_batch"]
    orig_validate_multi = _ORIG["validate_multi"]
    orig_seen = _ORIG["seen"]
    orig_register = _ORIG["register"]
    orig_episode = _ORIG["episode"]
    orig_arm_at = _ORIG["arm_at"]

    def run_batch_probe(self, **kwargs):
        _CTX["n_batches"] += 1
        _CTX["batch"] = {
            "idx": _CTX["n_batches"],
            "as_of": kwargs.get("as_of"),
            "arm_bar": kwargs.get("arm_bar"),
        }
        report = orig_run_batch(self, **kwargs)
        _REPORTS.append({
            "batch_idx": _CTX["batch"]["idx"],
            "as_of": kwargs.get("as_of"),
            "armed": [p.id for p in report.armed],
            "duplicates": list(report.duplicates),
            "skipped_tracked": list(report.skipped_tracked),
            "errors": dict(report.errors),
        })
        _CTX["batch"] = None
        return report

    def validate_multi_probe(self, series_by_tf, engine=None, arm_bars=None,
                             return_details=False):
        _CTX["cur_id"] = None
        _CTX["cur_pending"] = False
        result = orig_validate_multi(
            self, series_by_tf, engine=engine, arm_bars=arm_bars,
            return_details=True)
        batch = _CTX["batch"] or {}
        tf_order = {tf: i for i, tf in enumerate(self.detection_timeframes)}
        for tf, info in (getattr(result, "details", {}) or {}).items():
            if not info:
                continue
            tf_name = getattr(tf, "name", str(tf))
            results_by_id = {r.poi.id: r for r in info.get("results", [])}
            disp_map = info.get("disp_map", {}) or {}
            for order, poi in enumerate(info.get("passed", [])):
                val = results_by_id.get(poi.id)
                pillar_path = ""
                if val is not None:
                    try:
                        from smc.backtest.pipeline_bridge import (
                            pillar_path_summary)
                        pillar_path = pillar_path_summary(val) or ""
                    except Exception:  # noqa: BLE001 — identity never blocks
                        pillar_path = ""
                disp = disp_map.get(poi.id)
                low, high = _zone_bounds(poi.zone)
                zone_tf = getattr(getattr(poi.zone, "timeframe", None),
                                  "name", "")
                _PASSES.append({
                    "seq": len(_PASSES),
                    "batch_idx": batch.get("idx"),
                    "as_of": batch.get("as_of"),
                    "arm_bar": batch.get("arm_bar"),
                    "detection_tf": tf_name,
                    "tf_order": tf_order.get(tf, 99),
                    "list_order": order,
                    "poi_id": poi.id,
                    "zone_tf": zone_tf,
                    "direction": str(getattr(poi.zone, "direction", "")),
                    "zone_low": low,
                    "zone_high": high,
                    "score": getattr(poi, "score", None),
                    "models": sorted(getattr(m, "name", str(m))
                                     for m in getattr(poi, "models", [])),
                    "pillar_path": pillar_path,
                    "disp_magnitude_atr": (
                        getattr(disp, "magnitude_atr", None)
                        if disp is not None else None),
                    "disposition": None,
                    "blocker": None,
                })
        return result

    def seen_probe(self, zone):
        result = orig_seen(self, zone)
        if _CTX["active"] and _CTX["cur_pending"]:
            cur = _CTX["cur_id"]
            rec = _decode(cur)
            rec["dedup_calls"] += 1
            rec["dedup"] = bool(result)
            if result:
                low, high = _zone_bounds(zone)
                direction = str(getattr(zone, "direction", ""))
                registered = list(getattr(self, "_zones", []))
                index, known_top, known_bottom = _match_blocker(
                    registered, direction, low, high)
                blocker = None
                if index is not None:
                    geo = overlap_metrics(low, high, known_bottom, known_top)
                    meta = (_REGISTRY[index] if index < len(_REGISTRY)
                            else {})
                    blocker = {
                        "blocker_poi_id": meta.get("poi_id"),
                        "blocker_batch_idx": meta.get("batch_idx"),
                        "blocker_as_of": meta.get("as_of"),
                        "blocker_zone_low": known_bottom,
                        "blocker_zone_high": known_top,
                        **geo,
                    }
                    if _CTX["batch"] is not None and meta.get("batch_idx"):
                        blocker["same_batch"] = (
                            meta["batch_idx"] == _CTX["batch"]["idx"])
                        blocker["age_batches"] = (
                            _CTX["batch"]["idx"] - meta["batch_idx"])
                        if isinstance(meta.get("as_of"), datetime) and isinstance(
                                _CTX["batch"].get("as_of"), datetime):
                            blocker["age_days"] = round(
                                (_CTX["batch"]["as_of"]
                                 - meta["as_of"]).total_seconds() / 86400.0, 3)
                rec["blocker"] = blocker
            _CTX["cur_pending"] = False
        return result

    def register_probe(self, zone):
        out = orig_register(self, zone)
        if _CTX["active"]:
            low, high = _zone_bounds(zone)
            meta = _CTX.get("last_armed") or {}
            _REGISTRY.append({
                "direction": str(getattr(zone, "direction", "")),
                "zone_low": round(low, 6),
                "zone_high": round(high, 6),
                "poi_id": meta.get("poi_id"),
                "batch_idx": meta.get("batch_idx"),
                "as_of": meta.get("as_of"),
                "arm_bar": meta.get("arm_bar"),
            })
        return out

    def episode_probe(self, poi):
        result = orig_episode(self, poi)
        if _CTX["active"]:
            rec = _decode(poi.id)
            rec["episode_calls"] += 1
            rec["tracked"] = result is not None
            _CTX["cur_id"] = poi.id
            _CTX["cur_pending"] = True
        return result

    def arm_at_probe(self, poi, arm_bar=None, **kwargs):
        if not _CTX["active"]:
            return orig_arm_at(self, poi, arm_bar, **kwargs)
        try:
            out = orig_arm_at(self, poi, arm_bar, **kwargs)
        except Exception as exc:  # noqa: BLE001 — recorded, then re-raised
            rec = _decode(poi.id)
            rec["arm_error"] = f"{type(exc).__name__}: {exc}"
            _CTX["cur_pending"] = False
            raise
        rec = _decode(poi.id)
        rec["armed"] = True
        rec["episode_calls"] += 0  # already counted by episode()
        batch = _CTX["batch"] or {}
        _CTX["last_armed"] = {
            "poi_id": poi.id,
            "batch_idx": batch.get("idx"),
            "as_of": batch.get("as_of"),
            "arm_bar": arm_bar if arm_bar is not None
            else (batch.get("arm_bar")),
        }
        _CTX["cur_pending"] = False
        return out

    MultiTFProductRuntime.run_batch = run_batch_probe
    MultiTFDetectionDriver.validate_multi = validate_multi_probe
    ZoneDedup.seen = seen_probe
    ZoneDedup.register = register_probe
    PipelineEngine.episode = episode_probe
    PipelineEngine.arm_at = arm_at_probe
    _CTX["active"] = True

    def restore() -> None:
        _CTX["active"] = False
        MultiTFProductRuntime.run_batch = _ORIG["run_batch"]
        MultiTFDetectionDriver.validate_multi = _ORIG["validate_multi"]
        ZoneDedup.seen = _ORIG["seen"]
        ZoneDedup.register = _ORIG["register"]
        PipelineEngine.episode = _ORIG["episode"]
        PipelineEngine.arm_at = _ORIG["arm_at"]

    return restore


# ---------------------------------------------------------------------- #
# Pure helpers — disposition, clustering, interpretation
# ---------------------------------------------------------------------- #

def classify_event(event: dict, decision: dict | None) -> tuple[str, str]:
    """One bucket per PASS event, read from the product's own decisions.

    Decision order is the arm loop's own order
    (``engine.episode`` → ``dedup.seen`` → ``engine.arm_at``); the returned
    note names the machine reason for ``SKIP_OTHER`` / ``DATA_GAP`` rows.
    """
    if decision is None:
        return BUCKET_GAP, "no decision observed for this POI id"
    if decision.get("armed"):
        return BUCKET_ARMED, "engine.arm_at returned"
    if decision.get("arm_error"):
        return BUCKET_OTHER, decision["arm_error"]
    if decision.get("dedup"):
        return BUCKET_DEDUP, "ZoneDedup.seen() is True"
    if decision.get("tracked"):
        return BUCKET_TRACKED, "engine.episode() is not None"
    return BUCKET_GAP, (
        "passed POI reached no gate: episode_calls="
        f"{decision.get('episode_calls')} dedup_calls="
        f"{decision.get('dedup_calls')}")


def _norm_zone(direction: str, low: float, high: float) -> tuple:
    return (str(direction), round(float(low), 6), round(float(high), 6))


def cluster_events(events: list[dict]) -> list[dict]:
    """Greedy episode clustering under the product's own dedup rule.

    Replays ``ZoneDedup`` (same direction + inclusive overlap on 6dp bounds,
    first match wins, registration order) over *every* PASS event — armed or
    not — so the episode view answers "how many distinct structures ever
    passed", not "how many arm attempts happened".

    Overlap chaining means a cluster is an UPPER bound on distinct
    structures (the exact-geometry census is the lower bound); both are
    reported.
    """
    clusters: list[dict] = []
    for event in events:
        direction = str(event.get("direction", ""))
        low = float(event["zone_low"])
        high = float(event["zone_high"])
        target = None
        for cluster in clusters:
            if cluster["direction"] != direction:
                continue
            if (cluster["zone_high"] >= low and high >= cluster["zone_low"]):
                target = cluster
                break
        if target is None:
            target = {
                "cluster_id": len(clusters) + 1,
                "direction": direction,
                "zone_low": round(low, 6),
                "zone_high": round(high, 6),
                "events": [],
                "armed": 0,
                "deduped": 0,
                "detection_tfs": [],
                "first_as_of": event.get("as_of"),
                "last_as_of": event.get("as_of"),
            }
            clusters.append(target)
        target["events"].append(event["seq"])
        if event.get("disposition") == BUCKET_ARMED:
            target["armed"] += 1
        elif event.get("disposition") == BUCKET_DEDUP:
            target["deduped"] += 1
        tf = event.get("detection_tf")
        if tf and tf not in target["detection_tfs"]:
            target["detection_tfs"].append(tf)
        target["last_as_of"] = event.get("as_of")
    return clusters


def geometry_census(events: list[dict]) -> dict:
    """Distinct exact geometries (6dp bounds + direction) among PASS events."""
    counter = Counter(
        _norm_zone(e.get("direction", ""), e["zone_low"], e["zone_high"])
        for e in events
    )
    armed_geoms = {
        _norm_zone(e.get("direction", ""), e["zone_low"], e["zone_high"])
        for e in events if e.get("disposition") == BUCKET_ARMED
    }
    never_armed = [geom for geom in counter if geom not in armed_geoms]
    return {
        "n_events": len(events),
        "n_distinct_geometries": len(counter),
        "n_distinct_geometries_armed": len(armed_geoms),
        "n_distinct_geometries_never_armed": len(never_armed),
        "reemission_per_geometry_median": _median(list(counter.values())),
        "reemission_per_geometry_max": max(counter.values()) if counter else None,
        "top_reemitted": [
            {"direction": geom[0], "zone_low": geom[1], "zone_high": geom[2],
             "pass_events": count}
            for geom, count in counter.most_common(10)
        ],
    }


def disposition_counts(events: list[dict]) -> dict:
    """Bucket histogram with every pre-registered bucket present."""
    counter = Counter(e.get("disposition") for e in events)
    n = len(events)
    out = {}
    for bucket in BUCKETS:
        count = int(counter.get(bucket, 0))
        out[bucket] = {
            "count": count,
            "pct_of_passes": round(_pct(count, n), 2),
            "code_impossible_today": bucket in CODE_IMPOSSIBLE_BUCKETS,
        }
    unknown = {k: v for k, v in counter.items() if k not in BUCKETS}
    if unknown:
        out["_unclassified"] = unknown
    out["_total"] = n
    return out


def dedup_geometry(events: list[dict]) -> dict:
    """Geometry + age of every dedup match (is dedup the same episode?)."""
    rows = [e for e in events
            if e.get("disposition") == BUCKET_DEDUP and e.get("blocker")]
    coverages = [float(r["blocker"]["coverage"]) for r in rows]
    ages = [float(r["blocker"]["age_days"]) for r in rows
            if r["blocker"].get("age_days") is not None]
    return {
        "n_dedup_events": len(rows),
        "n_dedup_with_blocker": sum(
            1 for r in rows if r["blocker"].get("blocker_poi_id")),
        "identical_bounds": sum(
            1 for r in rows if r["blocker"].get("identical_bounds")),
        "pct_identical_bounds": round(_pct(
            sum(1 for r in rows if r["blocker"].get("identical_bounds")),
            len(rows)), 2),
        "coverage_median": _median(coverages),
        "coverage_p10": _percentile(coverages, 10),
        "coverage_p90": _percentile(coverages, 90),
        "pct_coverage_ge_0_5": round(_pct(
            sum(1 for c in coverages if c >= SAME_EPISODE_COVERAGE),
            len(coverages)), 2),
        "pct_coverage_eq_1": round(_pct(
            sum(1 for c in coverages if c >= 0.999999), len(coverages)), 2),
        "same_batch": sum(1 for r in rows if r["blocker"].get("same_batch")),
        "cross_batch": sum(
            1 for r in rows if r["blocker"].get("same_batch") is False),
        "age_days_median": _median(ages),
        "age_days_max": max(ages) if ages else None,
        "distinct_blockers": len({r["blocker"].get("blocker_poi_id")
                                  for r in rows
                                  if r["blocker"].get("blocker_poi_id")}),
    }


def coverage_bands(events: list[dict]) -> list[dict]:
    """Dedup events split by how much of the PASS zone the blocker covers.

    Descriptive only: 1.0 = the passing zone is entirely inside (or exactly
    on) the armed zone — the same structure re-emitted; a low band means the
    two zones merely touch. ``geometries_never_armed`` counts the band's
    exact geometries that never armed anywhere in the window.
    """
    armed_geoms = {
        _norm_zone(e.get("direction", ""), e["zone_low"], e["zone_high"])
        for e in events if e.get("disposition") == BUCKET_ARMED
    }
    bands = (("1.00", 1.0, 1.000001), ("0.75-1.00", 0.75, 1.0),
             ("0.50-0.75", 0.50, 0.75), ("0.25-0.50", 0.25, 0.50),
             ("0.00-0.25", 0.0, 0.25))
    rows = []
    for label, low, high in bands:
        members = []
        for event in events:
            blocker = event.get("blocker") or {}
            if event.get("disposition") != BUCKET_DEDUP or not blocker:
                continue
            coverage = float(blocker.get("coverage") or 0.0)
            if low <= coverage < high or (
                    label == "1.00" and coverage >= 1.0):
                members.append(event)
        geometries = {
            _norm_zone(e.get("direction", ""), e["zone_low"], e["zone_high"])
            for e in members
        }
        rows.append({
            "coverage_band": label,
            "n_events": len(members),
            "pct_of_dedup": round(_pct(len(members), sum(
                1 for e in events
                if e.get("disposition") == BUCKET_DEDUP)), 2),
            "distinct_geometries": len(geometries),
            "geometries_never_armed": len(geometries - armed_geoms),
            "median_blocker_age_days": _median([
                (e.get("blocker") or {}).get("age_days") for e in members]),
            "median_pass_zone_width": _median([
                float(e["zone_high"]) - float(e["zone_low"])
                for e in members]),
        })
    return rows


def episode_table(clusters: list[dict], events: list[dict]) -> list[dict]:
    """One row per episode (the 30-row view an Architect can read)."""
    by_seq = {e["seq"]: e for e in events}
    rows = []
    for cluster in clusters:
        members = [by_seq[seq] for seq in cluster["events"] if seq in by_seq]
        geometries = {
            _norm_zone(e.get("direction", ""), e["zone_low"], e["zone_high"])
            for e in members
        }
        armed = [e for e in members
                 if e.get("disposition") == BUCKET_ARMED]
        rows.append({
            "cluster_id": cluster["cluster_id"],
            "direction": cluster["direction"],
            "zone_low": cluster["zone_low"],
            "zone_high": cluster["zone_high"],
            "first_as_of": (cluster.get("first_as_of").isoformat()
                            if isinstance(cluster.get("first_as_of"), datetime)
                            else cluster.get("first_as_of")),
            "last_as_of": (cluster.get("last_as_of").isoformat()
                           if isinstance(cluster.get("last_as_of"), datetime)
                           else cluster.get("last_as_of")),
            "pass_events": len(members),
            "armed_events": cluster["armed"],
            "dedup_events": cluster["deduped"],
            "detection_tfs": cluster["detection_tfs"],
            "distinct_geometries": len(geometries),
            "armed_detection_tf": (armed[0].get("detection_tf")
                                   if armed else None),
            "armed_zone_tf": (armed[0].get("zone_tf") if armed else None),
            "armed_models": (armed[0].get("models") if armed else None),
        })
    return rows


def interpret(counts: dict, n_events: int, dedup: dict) -> tuple[str, str]:
    """The pre-registered label rule (fixed before the run)."""
    if n_events < MIN_PASSES_FOR_LABEL:
        return "INCONCLUSIVE_LOW_N", (
            f"n_pass_events={n_events} < {MIN_PASSES_FOR_LABEL}: no ranking "
            "is claimed from this window.")

    shares = {b: counts[b]["pct_of_passes"] / 100.0 for b in BUCKETS}
    wiring = shares[BUCKET_GAP] + shares[BUCKET_OTHER]
    if wiring > WIRING_SHARE_LIMIT:
        return "MIXED", (
            f"wiring defect: {counts[BUCKET_GAP]['count']} DATA_GAP + "
            f"{counts[BUCKET_OTHER]['count']} SKIP_OTHER "
            f"({wiring * 100:.2f}% of passes) — a hole is never hidden "
            "behind a filter label.")

    dedup_share = shares[BUCKET_DEDUP]
    if dedup_share >= 0.5:
        cov = dedup.get("coverage_median")
        if cov is not None and cov >= SAME_EPISODE_COVERAGE:
            return "DEDUP_DOMINATED", (
                f"dedup suppresses {dedup_share * 100:.1f}% of passes and the "
                f"median PASS zone is {cov * 100:.1f}% covered by its "
                "already-armed blocker "
                f"({dedup['pct_identical_bounds']}% identical bounds): the "
                "gate is re-arming the SAME episode, not filtering "
                "structures.")
        return "ARM_FILTER_IS_BOTTLENECK", (
            f"dedup suppresses {dedup_share * 100:.1f}% of passes but the "
            f"median coverage is only {(cov or 0) * 100:.1f}% — overlapping "
            "but distinct structures are being folded into older episodes.")

    if shares[BUCKET_FRESHNESS] >= 0.5:
        return "FRESHNESS_DOMINATED", (
            f"freshness/touch policy explains "
            f"{shares[BUCKET_FRESHNESS] * 100:.1f}% of passes.")

    intentional = sum(shares[b] for b in INTENTIONAL_BUCKETS)
    if intentional >= 0.5:
        return "ARM_FILTER_IS_BOTTLENECK", (
            f"intentional policy gates account for {intentional * 100:.1f}% "
            "of passes with no single dominant bucket.")

    if max(shares.values()) < 0.5:
        return "ARM_PATH_HEALTHY", (
            "no bucket reaches 50% of passes and no wiring defect was "
            "observed: the arm path adds no dominant filter.")

    return "MIXED", "no pre-registered branch matched the observed shares."


def select_autopsy(events: list[dict], target: int = AUTOPSY_TARGET) -> list[dict]:
    """Deterministic non-armed sample spread across the top buckets.

    Within the dominant bucket the sample is spread by coverage (most
    identical → least overlapping) so the autopsy shows both the benign
    re-emission and the loosest match. Buckets are visited in count order.
    """
    non_armed = [e for e in events if e.get("disposition") != BUCKET_ARMED]
    if not non_armed:
        return []
    by_bucket: dict[str, list[dict]] = defaultdict(list)
    for event in non_armed:
        by_bucket[event["disposition"]].append(event)
    ordered = sorted(by_bucket.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    quota = max(1, target // max(1, len(ordered)))
    picked: list[dict] = []
    for bucket, rows in ordered:
        if bucket == BUCKET_DEDUP:
            rows = sorted(
                rows,
                key=lambda r: -float(
                    (r.get("blocker") or {}).get("coverage") or 0.0))
            rows = _spread(rows, quota)
        else:
            rows = _spread(sorted(rows, key=lambda r: r["seq"]), quota)
        picked.extend(rows)
    picked = picked[:max(target, len(picked))]
    return picked


def _spread(rows: list[dict], n: int) -> list[dict]:
    """Evenly spaced deterministic pick of ``n`` rows."""
    if n <= 0 or not rows:
        return []
    if len(rows) <= n:
        return list(rows)
    step = (len(rows) - 1) / (n - 1) if n > 1 else 0
    indices = sorted({int(round(i * step)) for i in range(n)})
    return [rows[i] for i in indices]


def time_structure(events: list[dict], clusters: list[dict]) -> list[dict]:
    """Descriptive passes / armed / dedup per calendar month (UTC)."""
    months: dict[str, dict] = {}
    for event in events:
        as_of = event.get("as_of")
        key = (as_of.date().isoformat()[:7]
               if isinstance(as_of, datetime) else "unknown")
        row = months.setdefault(key, {"month": key, "passes": 0, "armed": 0,
                                      "dedup": 0, "clusters_first_seen": 0})
        row["passes"] += 1
        if event.get("disposition") == BUCKET_ARMED:
            row["armed"] += 1
        elif event.get("disposition") == BUCKET_DEDUP:
            row["dedup"] += 1
    for cluster in clusters:
        as_of = cluster.get("first_as_of")
        key = (as_of.date().isoformat()[:7]
               if isinstance(as_of, datetime) else "unknown")
        row = months.setdefault(key, {"month": key, "passes": 0, "armed": 0,
                                      "dedup": 0, "clusters_first_seen": 0})
        row["clusters_first_seen"] += 1
    return [months[k] for k in sorted(months)]


def _median(values) -> float | None:
    clean = [float(v) for v in values if v is not None]
    return round(statistics.median(clean), 6) if clean else None


def _percentile(values, q: float) -> float | None:
    clean = sorted(float(v) for v in values if v is not None)
    if not clean:
        return None
    if len(clean) == 1:
        return round(clean[0], 6)
    pos = (len(clean) - 1) * q / 100.0
    low = int(pos)
    high = min(low + 1, len(clean) - 1)
    frac = pos - low
    return round(clean[low] * (1 - frac) + clean[high] * frac, 6)


def _pct(numerator: int, denominator: int) -> float:
    return (100.0 * numerator / denominator) if denominator else 0.0


# ---------------------------------------------------------------------- #
# Capture driver
# ---------------------------------------------------------------------- #

def run_capture() -> dict:
    """Drive the frozen composition and persist one row per PASS event."""
    import phase3_structure_funnel as funnel

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _reset_capture()
    restore = install_capture()
    args = argparse.Namespace(
        tag="passed_to_armed",
        out_root=str(OUT_DIR.relative_to(REPO_ROOT) / "_funnel_capture"),
        load_from=LOAD_FROM.date().isoformat(),
        exec_from=EXEC_FROM.date().isoformat(),
        exec_to=EXEC_TO.date().isoformat(),
        cost_config=None,
        episode_store=None,
    )
    t0 = time.perf_counter()
    try:
        funnel_summary = funnel.run(args)
    finally:
        restore()
    elapsed = round(time.perf_counter() - t0, 1)

    # Attribute every pass from the decisions recorded during the run.
    for event in _PASSES:
        decision = _DEC.get(event["poi_id"])
        bucket, note = classify_event(event, decision)
        event["disposition"] = bucket
        event["reason"] = note
        event["blocker"] = (decision or {}).get("blocker")
        event["episode_calls"] = (decision or {}).get("episode_calls")
        event["dedup_calls"] = (decision or {}).get("dedup_calls")

    meta = {
        "runtime_seconds": elapsed,
        "n_pass_events": len(_PASSES),
        "n_batches": _CTX["n_batches"],
        "funnel_summary": funnel_summary,
        "batch_reports": _REPORTS,
    }
    with gzip.open(EVENTS_PATH, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "funnel", "data": funnel_summary},
                            default=str) + "\n")
        fh.write(json.dumps({"kind": "meta", "data": meta},
                            default=str) + "\n")
        for event in _PASSES:
            fh.write(json.dumps({"kind": "event", "data": event},
                                default=str) + "\n")
    print(f"[l4] captured {len(_PASSES)} PASS events in {elapsed}s -> "
          f"{EVENTS_PATH}", flush=True)
    return meta


def load_events() -> tuple[list[dict], dict]:
    if not EVENTS_PATH.exists():
        raise SystemExit(
            f"missing capture: {EVENTS_PATH} — run --capture first")
    events: list[dict] = []
    meta: dict = {}
    funnel_summary: dict = {}
    with gzip.open(EVENTS_PATH, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row["kind"] == "event":
                data = row["data"]
                for key in ("as_of",):
                    if isinstance(data.get(key), str):
                        data[key] = datetime.fromisoformat(data[key])
                events.append(data)
            elif row["kind"] == "meta":
                meta = row["data"]
            elif row["kind"] == "funnel":
                funnel_summary = row["data"]
    meta.setdefault("funnel_summary", funnel_summary)
    return events, meta


# ---------------------------------------------------------------------- #
# Analysis
# ---------------------------------------------------------------------- #

def _integrity(events: list[dict], meta: dict, counts: dict) -> dict:
    """Cross-check the attribution against the composition's own counters."""
    funnel = meta.get("funnel_summary") or {}
    reports = meta.get("batch_reports") or []
    reported_armed = [pid for r in reports for pid in r.get("armed", [])]
    reported_dup = [pid for r in reports for pid in r.get("duplicates", [])]
    reported_tracked = [pid for r in reports
                        for pid in r.get("skipped_tracked", [])]
    ours_armed = {e["poi_id"] for e in events
                  if e["disposition"] == BUCKET_ARMED}
    ours_dup = {e["poi_id"] for e in events
                if e["disposition"] == BUCKET_DEDUP}
    ours_tracked = {e["poi_id"] for e in events
                    if e["disposition"] == BUCKET_TRACKED}
    passes = len(events)
    return {
        "n_pass_events": passes,
        "funnel_passed_validation": funnel.get("passed_validation"),
        "passed_matches_funnel": passes == funnel.get("passed_validation"),
        "funnel_armed": funnel.get("armed"),
        "armed_matches_funnel": (
            counts[BUCKET_ARMED]["count"] == funnel.get("armed")),
        "funnel_duplicates_suppressed": funnel.get("duplicates_suppressed"),
        "dedup_matches_funnel": (
            counts[BUCKET_DEDUP]["count"]
            == funnel.get("duplicates_suppressed")),
        "funnel_skipped_tracked": funnel.get("skipped_tracked"),
        "tracked_matches_funnel": (
            counts[BUCKET_TRACKED]["count"] == funnel.get("skipped_tracked")),
        "arm_ids_match_report": ours_armed == set(reported_armed),
        "dedup_ids_match_report": ours_dup == set(reported_dup),
        "tracked_ids_match_report": ours_tracked == set(reported_tracked),
        "every_pass_has_one_bucket": (
            all(e["disposition"] in BUCKETS for e in events)),
        "bucket_sum_equals_passes": (
            sum(counts[b]["count"] for b in BUCKETS) == passes),
        "batch_errors": funnel.get("batch_errors"),
        "note": ("pass counts are compared against the composition's own "
                 "funnel_summary; ids against each batch report's armed / "
                 "duplicates / skipped_tracked lists"),
    }


def build_rows(events: list[dict]) -> list[dict]:
    """Flat CSV rows (one per PASS event, audit trail)."""
    rows = []
    for event in events:
        blocker = event.get("blocker") or {}
        rows.append({
            "seq": event["seq"],
            "batch_idx": event.get("batch_idx"),
            "as_of": (event["as_of"].isoformat()
                      if isinstance(event.get("as_of"), datetime)
                      else event.get("as_of")),
            "arm_bar": event.get("arm_bar"),
            "detection_tf": event.get("detection_tf"),
            "zone_tf": event.get("zone_tf"),
            "direction": event.get("direction"),
            "zone_low": f"{float(event['zone_low']):.6f}",
            "zone_high": f"{float(event['zone_high']):.6f}",
            "zone_width": f"{float(event['zone_high']) - float(event['zone_low']):.6f}",
            "score": event.get("score"),
            "models": "|".join(event.get("models") or []),
            "pillar_path": event.get("pillar_path") or "",
            "disp_magnitude_atr": event.get("disp_magnitude_atr"),
            "disposition": event.get("disposition"),
            "reason": event.get("reason") or "",
            "blocker_poi_id": blocker.get("blocker_poi_id") or "",
            "blocker_batch_idx": blocker.get("blocker_batch_idx") or "",
            "blocker_as_of": blocker.get("blocker_as_of") or "",
            "blocker_zone_low": ("" if blocker.get("blocker_zone_low") is None
                                 else f"{float(blocker['blocker_zone_low']):.6f}"),
            "blocker_zone_high": ("" if blocker.get("blocker_zone_high") is None
                                  else f"{float(blocker['blocker_zone_high']):.6f}"),
            "overlap_abs": blocker.get("overlap_abs"),
            "coverage": blocker.get("coverage"),
            "blocker_coverage": blocker.get("blocker_coverage"),
            "jaccard": blocker.get("jaccard"),
            "identical_bounds": blocker.get("identical_bounds"),
            "same_batch": blocker.get("same_batch"),
            "age_batches": blocker.get("age_batches"),
            "age_days": blocker.get("age_days"),
        })
    return rows


def analyze() -> dict:
    events, meta = load_events()
    counts = disposition_counts(events)
    clusters = cluster_events(events)
    census = geometry_census(events)
    dedup = dedup_geometry(events)
    label, why = interpret(counts, len(events), dedup)

    cluster_view = {
        "n_clusters": len(clusters),
        "n_clusters_with_armed_member": sum(1 for c in clusters
                                            if c["armed"] > 0),
        "n_clusters_with_multiple_armed": sum(1 for c in clusters
                                              if c["armed"] > 1),
        "n_clusters_never_armed": sum(1 for c in clusters
                                      if c["armed"] == 0),
        "cluster_size_median": _median([len(c["events"]) for c in clusters]),
        "cluster_size_max": max((len(c["events"]) for c in clusters),
                                default=None),
        "multi_tf_clusters": sum(1 for c in clusters
                                 if len(c["detection_tfs"]) > 1),
        "events_per_cluster_median": _median([c["deduped"] + c["armed"]
                                              for c in clusters]),
        "note": ("clusters replay the product's own ZoneDedup rule over every "
                 "PASS event; overlap chaining makes a cluster an UPPER bound "
                 "on distinct structures (see geometry_census for the exact "
                 "lower bound)"),
    }

    by_tf = {}
    for tf in sorted({e.get("detection_tf") for e in events}):
        rows = [e for e in events if e.get("detection_tf") == tf]
        by_tf[tf] = {
            "passes": len(rows),
            "armed": sum(1 for e in rows
                         if e["disposition"] == BUCKET_ARMED),
            "dedup": sum(1 for e in rows
                         if e["disposition"] == BUCKET_DEDUP),
            "distinct_geometries": len({
                _norm_zone(e.get("direction", ""), e["zone_low"],
                           e["zone_high"]) for e in rows}),
        }

    autopsy = select_autopsy(events)
    summary = {
        "banner": BANNER,
        "authority": "00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md (LEG 4)",
        "window": {
            "load_from": LOAD_FROM.isoformat(),
            "exec_from": EXEC_FROM.isoformat(),
            "exec_to": EXEC_TO.isoformat(),
            "exec_tf": "M5",
        },
        "capture": {
            "runtime_seconds": meta.get("runtime_seconds"),
            "n_batches": meta.get("n_batches"),
            "n_pass_events": len(events),
        },
        "funnel": {
            k: (meta.get("funnel_summary") or {}).get(k) for k in
            ("htf_batches", "merged_pois", "passed_validation", "armed",
             "duplicates_suppressed", "skipped_tracked", "routes", "placed",
             "fills", "trades")
        },
        "dispositions": counts,
        "ranking": [
            {"bucket": b, **counts[b]} for b in sorted(
                BUCKETS, key=lambda b: -counts[b]["count"])
        ],
        "by_detection_tf": by_tf,
        "episode_clusters": cluster_view,
        "geometry_census": census,
        "dedup_geometry": dedup,
        "coverage_bands": coverage_bands(events),
        "episodes": episode_table(clusters, events),
        "autopsy": [
            {"seq": e["seq"],
             "as_of": (e["as_of"].isoformat()
                       if isinstance(e.get("as_of"), datetime) else None),
             "detection_tf": e.get("detection_tf"),
             "zone_tf": e.get("zone_tf"),
             "direction": e.get("direction"),
             "zone_low": e["zone_low"],
             "zone_high": e["zone_high"],
             "models": e.get("models"),
             "pillar_path": e.get("pillar_path"),
             "disposition": e["disposition"],
             "reason": e.get("reason"),
             "blocker_zone_low": (e.get("blocker") or {}).get("blocker_zone_low"),
             "blocker_zone_high": (e.get("blocker") or {}).get("blocker_zone_high"),
             "coverage": (e.get("blocker") or {}).get("coverage"),
             "age_days": (e.get("blocker") or {}).get("age_days"),
             "same_batch": (e.get("blocker") or {}).get("same_batch")}
            for e in autopsy
        ],
        "time_structure": time_structure(events, clusters),
        "integrity": _integrity(events, meta, counts),
        "interpretation": {"label": label, "why": why},
        "guards": {
            "logic_changed": "NO",
            "locked_constants_touched": "NO",
            "arm_policy_changed": "NO",
            "edge_or_expectancy_claim": "NO",
            "multi_symbol": "NO",
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str),
                            encoding="utf-8")
    rows = build_rows(events)
    if rows:
        with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps({
        "passes": len(events),
        "armed": counts[BUCKET_ARMED]["count"],
        "top": [(b, counts[b]["count"], counts[b]["pct_of_passes"])
                for b in sorted(BUCKETS, key=lambda b: -counts[b]["count"])[:3]],
        "clusters": len(clusters),
        "label": label,
        "integrity_ok": (
            summary["integrity"]["passed_matches_funnel"]
            and summary["integrity"]["armed_matches_funnel"]
            and summary["integrity"]["dedup_matches_funnel"]),
    }, indent=2))
    return summary


def _parse_day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main() -> int:
    global LOAD_FROM, EXEC_FROM, EXEC_TO, OUT_DIR, EVENTS_PATH, \
        SUMMARY_PATH, CSV_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--analyze-only", action="store_true")
    ap.add_argument("--load-from", default=None)
    ap.add_argument("--exec-from", default=None)
    ap.add_argument("--exec-to", default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    if not args.capture and not args.analyze_only:
        ap.error("choose --capture or --analyze-only")
    if args.load_from:
        LOAD_FROM = _parse_day(args.load_from)
    if args.exec_from:
        EXEC_FROM = _parse_day(args.exec_from)
    if args.exec_to:
        EXEC_TO = _parse_day(args.exec_to) + timedelta(days=1) - timedelta(minutes=1)
    if args.out_dir:
        OUT_DIR = REPO_ROOT / args.out_dir
        EVENTS_PATH = OUT_DIR / "pass_events.jsonl.gz"
        SUMMARY_PATH = OUT_DIR / "summary.json"
        CSV_PATH = OUT_DIR / "pass_disposition.csv"
    if args.capture:
        run_capture()
    analyze()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
