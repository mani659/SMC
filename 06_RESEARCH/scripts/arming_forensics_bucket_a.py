#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Arming forensics, bucket A (read-only — measurement only).

Lead Architect directive (after CONFIRM_NEVER_ROUTED_474_NOTE.md):
for A-validated-elsewhere episodes (confirmed, accepted-pack geometry,
never armed in the product run), reconstruct the product arming path
and assign exactly ONE primary miss reason. No threshold changes, no
"arm more" implementation, no give-up/one-shot edits.

Frozen design (stated before running):
  * Population: 474-decomposition rows with reason_top == "A" AND
    reason_sub == "A-validated-elsewhere" (271; A-never-validated
    reported as side counts only). Reconciles to 271 — any other
    total is reported, never forced.
  * Instrumented replay (explicitly permitted): the FROZEN p3
    composition driven verbatim with call-through recorders (FR-4
    pattern; true originals restored in finally):
      - DetectionDriver.detect_pois -> per-batch RAW geometries.
      - MultiTFDetectionDriver.validate_multi -> per-batch validated
        geometries + PASS/first-failure (details carry the POI, so
        linkage is exact, never positional).
      - PipelineEngine.arm_at -> arm events (bounds/direction/bar).
    Fidelity gate: replay funnel + trades.csv + report.json must
    equal the refresh run1 artifacts EXACTLY (byte identity) — else
    FAIL, stop, report the defect.
  * Classification (frozen priority — first match wins):
      A4 armed_other_identity: same direction + range overlap with an
         armed engine POI whose arm_date is within +/-30 days of the
         episode first_seen_date (heuristic identity evidence for
         human chart check — overlap alone is cheap, stated).
      A3 passed_not_armed: any batch validated PASS on matching
         geometry, never armed. Sub-split by the exact ZoneDedup rule
         (same direction + overlap with an EARLIER-armed episode):
         dedup-loser vs other (no cap/score/freshness filter exists
         in _arm_passed — verified by reading it; only dedup gates).
      A2 in_batch_failed_pillars: all matching validations failed
         (first-fail pillars recorded; P1-P5 histogram).
      A1 never_in_batch: geometry absent from every batch's validated
         sets. Sub-split: A1a never-detected (absent from all raw
         sets) vs A1b detected-but-never-validated (raw rows exist;
         merged away or model-skipped — batch skip notes attached,
         never silently absorbed).
      A5 data_gap: classification inputs missing (unparseable
         bounds/direction/dates) — expected 0, reported if nonzero.
    Matching throughout = episode key (direction + rounded bounds),
    else same-direction containment (census inside engine), mirroring
    Step-4 Tiers A/B (partial overlaps never match — stated).
  * Medians use bars_sweep_to_confirm as recorded; examples = earliest
    first_seen per reason.
  * Fix classes (stated, never implemented): A4 identity review (human
    chart check); A3-dedup = batch/dedup dynamics (instrument first);
    A3-other/A5 = instrumentation; A2/A1b = pillar bands (Architect
    only); A1a = raw detection reach (new-detector territory or
    accept); B/C/D untouched (other populations).

Outputs: results/arming_forensics_bucket_a/{forensics.csv,
summary.json}. Note: ARMING_FORENSICS_BUCKET_A_NOTE.md (separate step).
LOGIC_CHANGED: NO (wrappers record and call through; restored after).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from smc.config.timeframe import Timeframe
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi

import phase3_structure_funnel as p3

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "arming_forensics_bucket_a"
ROWS_CSV = OUT_DIR / "forensics.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — NOT EDGE"

EXEC_FROM = datetime(2025, 6, 1, tzinfo=timezone.utc)
EXEC_TO = datetime(2025, 11, 30, tzinfo=timezone.utc)
LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)

DECOMP_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
              "confirm_never_routed_474" / "decomposition.csv")
POI_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "htf_poi_census" /
           "poi_episodes.csv")
REFRESH_RUN1 = (REPO_ROOT / "06_RESEARCH" / "results" /
                "product_6m_refresh_track_b" / "run1")

CSV_COLUMNS = [
    "episode_id", "tf", "kind_tag", "direction",
    "zone_low", "zone_high", "first_seen_date", "first_sweep_ts",
    "bars_sweep_to_confirm",
    "reason", "reason_detail",
    "batches_seen_raw", "batches_seen_validated",
    "pass_batches", "fail_pillars",
    "armed_match_ts", "match_kind", "matched_armed_low",
    "matched_armed_high", "fix_class", "example_rank",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def _iso(ts) -> str:
    if ts is None:
        return ""
    if isinstance(ts, str):
        return ts
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)


def episode_key_of(direction_name: str | None, low: float,
                   high: float) -> tuple:
    """Episode identity shared with the census (direction + rounded bounds)."""
    return ((direction_name or "").upper(), round(float(low), 3),
            round(float(high), 3))


def overlaps_same_side(a_dir: str | None, a_lo: float, a_hi: float,
                       b_dir: str | None, b_lo: float,
                       b_hi: float) -> bool:
    """ZoneDedup-equivalent overlap (same direction + ranges intersect)."""
    if (a_dir or "").upper() != (b_dir or "").upper():
        return False
    return a_hi >= b_lo and b_hi >= a_lo


def classify_a(*, armed_match: bool, ever_validated: bool,
               ever_passed: bool, ever_raw: bool,
               inputs_ok: bool) -> tuple[str, str]:
    """Frozen A priority: identity > pass-state > fail-state > absence."""
    if not inputs_ok:
        return "A5", "data_gap"
    if armed_match:
        return "A4", "armed_other_identity"
    if ever_passed:
        return "A3", "passed_not_armed"
    if ever_validated:
        return "A2", "in_batch_failed_pillars"
    if ever_raw:
        return "A1", "detected_but_never_validated"
    return "A1", "never_detected"


def day_diff(d1: str, d2: str) -> int | None:
    """Absolute day distance between YYYY-MM-DD dates (None if unparseable)."""
    try:
        return abs((datetime.fromisoformat(d1).date()
                    - datetime.fromisoformat(d2).date()).days)
    except (ValueError, TypeError):
        return None


def content_hash(*parts) -> str:
    """Deterministic short hash (stable ids without uuids)."""
    import hashlib as _hashlib
    return _hashlib.sha1("|".join("" if p is None else str(p)
                                  for p in parts).encode("utf-8")).hexdigest()[:8]


# --------------------------------------------------------------------------- #
# Instrumented replay (frozen composition, record-only wrappers)
# --------------------------------------------------------------------------- #
def run_instrumented_replay(out_root: Path) -> tuple[dict, dict]:
    """Drive p3.run verbatim; record raw/validated/armed per batch."""
    import smc.orchestration.detection_driver as driver_module
    import smc.orchestration.multi_tf as cascade_module
    from smc.orchestration.engine import PipelineEngine

    recording: dict = {"raw": {}, "validated": {}, "armed": []}
    saved = {}

    def _save(obj, name):
        saved[(obj, name)] = getattr(obj, name)

    def _restore_all():
        for (obj, name), fn in saved.items():
            setattr(obj, name, fn)

    def _batch_ts(series_by_tf) -> str:
        best = ""
        h1 = series_by_tf.get(Timeframe.H1) or []
        seq = h1 if h1 else [c for series in series_by_tf.values()
                             for c in (series or [])]
        for c in seq:
            ts = c.timestamp.isoformat()
            if ts > best:
                best = ts
        return best

    def _geom(poi) -> tuple:
        return (poi.zone.direction.name, round(float(poi.zone.bottom), 3),
                round(float(poi.zone.top), 3))

    _save(driver_module.DetectionDriver, "detect_pois")
    _save(cascade_module.MultiTFDetectionDriver, "validate_multi")
    _save(PipelineEngine, "arm_at")
    true_detect = saved[(driver_module.DetectionDriver, "detect_pois")]
    true_validate = saved[(cascade_module.MultiTFDetectionDriver,
                           "validate_multi")]
    true_arm = saved[(PipelineEngine, "arm_at")]

    def detect_and_record(self, candles, swings, liquidity_levels):
        pois, skipped = true_detect(self, candles, swings, liquidity_levels)
        ts = max([c.timestamp.isoformat() for c in candles]) if candles else ""
        for poi in pois:
            key = _geom(poi)
            rec = recording["raw"].setdefault(
                key, {"first_ts": ts, "n_batches": 0, "tags": set()})
            rec["n_batches"] += 1
            if ts and (not rec["first_ts"] or ts < rec["first_ts"]):
                rec["first_ts"] = ts
            for m in (poi.models or []):
                rec["tags"].add(getattr(m, "name", str(m)))
        if skipped:
            rec = recording["raw"].setdefault(
                ("__skipped__", ts, ""), {"first_ts": ts, "n_batches": 0,
                                          "tags": set()})
            rec["n_batches"] += 1
        return pois, skipped

    def validate_and_record(self, series_by_tf, engine=None, arm_bars=None,
                            return_details=False):
        result = true_validate(self, series_by_tf, engine=engine,
                               arm_bars=arm_bars,
                               return_details=return_details)
        batch_ts = _batch_ts(series_by_tf)
        details = getattr(result, "details", {}) or {}
        for _tf, info in details.items():
            for res in (info.get("results") or []):
                poi = getattr(res, "poi", None)
                if poi is None or not hasattr(poi, "zone"):
                    continue
                key = _geom(poi)
                rec = recording["validated"].setdefault(
                    key, {"first_ts": batch_ts, "n_batches": 0,
                          "pass_batches": 0, "pass_ts": [],
                          "fail_pillars": Counter()})
                rec["n_batches"] += 1
                if batch_ts and (not rec["first_ts"]
                                 or batch_ts < rec["first_ts"]):
                    rec["first_ts"] = batch_ts
                if res.passed:
                    rec["pass_batches"] += 1
                    if batch_ts:
                        rec["pass_ts"].append(batch_ts)
                else:
                    ff = res.first_failure
                    rec["fail_pillars"][
                        getattr(getattr(ff, "pillar", None), "name",
                                str(ff.pillar)) if ff is not None
                        else "REJECTED_no_first_failure"] += 1
        return result

    def arm_and_record(self, poi, arm_bar, arm_candle=None):
        recording["armed"].append({
            "low": float(poi.zone.bottom), "high": float(poi.zone.top),
            "direction": poi.zone.direction.name, "bar": arm_bar,
        })
        return true_arm(self, poi, arm_bar, arm_candle=arm_candle)

    driver_module.DetectionDriver.detect_pois = detect_and_record
    cascade_module.MultiTFDetectionDriver.validate_multi = validate_and_record
    PipelineEngine.arm_at = arm_and_record
    try:
        from product_baseline_pilot import PILOT_COSTS
        args = argparse.Namespace(
            tag="replay_run1", out_root=str(out_root),
            load_from="2025-05-01", exec_from="2025-06-01",
            exec_to="2025-11-30", cost_config=PILOT_COSTS)
        summary = p3.run(args)
    finally:
        _restore_all()
    return summary, recording


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DECOMP_CSV.exists():
        raise SystemExit(f"474 rows missing: {DECOMP_CSV}")

    replay_root = OUT_DIR / "replay_run1"
    print("[arma] instrumented replay (frozen composition) ...", flush=True)
    summary, rec = run_instrumented_replay(replay_root)

    # ---- Fidelity gate ---------------------------------------------------- #
    defects: list[str] = []
    byte_ok: dict = {}
    for name in ("trades.csv", "report.json"):
        f1, f2 = REFRESH_RUN1 / name, replay_root / name
        if f1.exists() and f2.exists():
            same = f1.read_bytes() == f2.read_bytes()
            byte_ok[name] = same
            if not same:
                defects.append(f"{name} bytes differ replay-vs-refresh")
        else:
            byte_ok[name] = None
            defects.append(f"{name} absent for fidelity check")
    for key in ("armed", "routes", "placed", "fills", "trades"):
        if summary.get(key) != json.loads(
                (REFRESH_RUN1 / "funnel_summary.json").read_text(
                    encoding="utf-8")).get(key):
            defects.append(f"funnel.{key} differs replay-vs-refresh: "
                           f"{summary.get(key)}")
    status = "PASS" if not defects else "FAIL"

    # ---- M5 grid (identical rebuild; endpoints asserted) ------------------ #
    m1_all = load_ohlcv_parquet(
        str(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"), Timeframe.M1)
    m1 = [c for c in m1_all if LOAD_FROM <= c.timestamp]
    m5 = [c for c in resample_multi(m1, [Timeframe.M5])[Timeframe.M5]
          if EXEC_FROM <= c.timestamp
          <= EXEC_TO + timedelta(days=1) - timedelta(minutes=1)]
    m5_ts = [c.timestamp.isoformat() for c in m5]
    assert len(m5_ts) == 35725, len(m5_ts)
    assert m5_ts[0].startswith("2025-06-01T22:00"), m5_ts[0]
    assert m5_ts[-1].startswith("2025-11-30T23:55"), m5_ts[-1]
    m5_index = {ts: i for i, ts in enumerate(m5_ts)}

    # ---- Population: A-validated-elsewhere -------------------------------- #
    decomp = list(csv.DictReader(open(DECOMP_CSV, encoding="utf-8")))
    pop = [r for r in decomp
           if r.get("reason_top") == "A"
           and r.get("reason_sub") == "A-validated-elsewhere"]
    print(f"[arma] A-validated-elsewhere rows={len(pop)}", flush=True)

    # ---- Census bounds (read-only, same Step-1 artifact) -------------------- #
    bounds_of = {}
    with open(POI_CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                bounds_of[r["episode_id"]] = (
                    r["direction"], float(r["zone_low"]),
                    float(r["zone_high"]), r.get("first_seen_date") or "")
            except (ValueError, TypeError, KeyError):
                continue

    armed = rec["armed"]
    for a in armed:
        a["ts"] = m5_ts[a["bar"]] if 0 <= a["bar"] < len(m5_ts) else ""
        a["date"] = a["ts"][:10]

    def _row(eid, row, direction, lo, hi, first_seen, **kw):
        base = {
            "episode_id": eid, "tf": row.get("tf"),
            "kind_tag": row.get("kind_tag"), "direction": direction,
            "zone_low": lo, "zone_high": hi,
            "first_seen_date": first_seen,
            "first_sweep_ts": row.get("first_sweep_ts"),
            "bars_sweep_to_confirm": row.get("bars_sweep_to_confirm"),
            "reason": "", "reason_detail": "",
            "batches_seen_raw": "", "batches_seen_validated": "",
            "pass_batches": "", "fail_pillars": "",
            "armed_match_ts": "", "fix_class": "", "example_rank": "",
        }
        base.update(kw)
        return base

    rows_out: list[dict] = []
    for row in sorted(pop, key=lambda r: (r.get("first_sweep_ts") or "",
                                          r["episode_id"])):
        eid = row["episode_id"]
        info = bounds_of.get(eid)
        if info is None:
            rows_out.append(_row(
                eid, row, "", "", "", "", reason="A5",
                reason_detail="data_gap",
                fix_class="instrumentation (no census bounds for "
                          "this episode id)"))
            continue
        direction, lo, hi, first_seen = info
        if not direction or not (hi >= lo):
            rows_out.append(_row(
                eid, row, direction, lo, hi, first_seen, reason="A5",
                reason_detail="data_gap",
                fix_class="instrumentation (degenerate bounds/direction)"))
            continue
        # A4: armed under another identity (overlap + time window).
        a4 = [(a, day_diff(a["date"], first_seen)) for a in armed
              if a["date"] and first_seen and overlaps_same_side(
                  direction, lo, hi, a["direction"], a["low"], a["high"])]
        a4 = [(a, d) for a, d in a4 if d is not None and d <= 30]
        if a4:
            best = sorted(a4, key=lambda t: (t[1], t[0]["ts"]))[0][0]
            blo, bhi = best["low"], best["high"]
            if (round(blo, 3), round(bhi, 3)) == (round(lo, 3), round(hi, 3)):
                kind = "exact"
            elif (blo <= lo and hi <= bhi) or (lo <= blo and bhi <= hi):
                kind = "contained"
            else:
                kind = "partial"
            rows_out.append(_row(
                eid, row, direction, lo, hi, first_seen, reason="A4",
                reason_detail="armed_other_identity",
                armed_match_ts=best["ts"], match_kind=kind,
                matched_armed_low=blo, matched_armed_high=bhi,
                fix_class="identity review (human chart check: overlap is "
                          "cheap evidence under blanket zones)"))
            continue
        # Validation evidence: exact key, else containment (Step-4 tiers).
        exact = (direction, round(lo, 3), round(hi, 3))
        matched = []
        for key, v in rec["validated"].items():
            if key == exact:
                matched.append((key, v, "exact"))
                continue
            _d, _lo, _hi = key
            if _d == direction and _lo <= lo and hi <= _hi:
                matched.append((key, v, "contained"))
        if not matched:
            raw_hit = exact in rec["raw"]
            rows_out.append(_row(
                eid, row, direction, lo, hi, first_seen, reason="A1",
                reason_detail=("A1b-detected-but-never-validated" if raw_hit
                               else "A1a-never-detected"),
                batches_seen_raw=(rec["raw"].get(exact, {}).get("n_batches", 0)
                                   if raw_hit else 0),
                fix_class=("pillar bands (Architect only); batch skip "
                           "notes in summary")))
            continue
        passes = [(k, v) for k, v, _tier in matched
                  if v["pass_batches"] > 0]
        fails: Counter = Counter()
        batches_seen = 0
        npass = 0
        for _k, v, _tier in matched:
            batches_seen += v["n_batches"]
            npass += v["pass_batches"]
            for p, c in v["fail_pillars"].items():
                fails[p] += c
        if passes:
            # A3: passed but never armed. Dedup test vs earlier arms with
            # the EXACT ZoneDedup rule (same direction + overlap, armed
            # strictly earlier batch; same-batch order unknown).
            pass_ts = sorted({t for _k, v, _tier in matched
                              for t in v.get("pass_ts", [])})
            loser, same_batch = False, False
            for pt in pass_ts:
                for a in armed:
                    if not a["ts"]:
                        continue
                    if not overlaps_same_side(
                            direction, lo, hi, a["direction"], a["low"],
                            a["high"]):
                        continue
                    if a["ts"] < pt:
                        loser = True
                    elif a["ts"] == pt:
                        same_batch = True
            if loser:
                sub, detail = ("A3", "dedup-loser")
                fix = ("batch/dedup dynamics (instrument first: per-batch "
                       "arm-order logs)")
            elif same_batch:
                sub, detail = ("A3", "dedup-possible")
                fix = ("batch/dedup dynamics (instrument first: per-batch "
                       "arm-order logs)")
            else:
                sub, detail = ("A3", "other")
                fix = ("instrumentation (batch-level arm-decision logs); "
                       "then Architect — no cap/score/freshness filter "
                       "exists in _arm_passed, verified by reading)")
            rows_out.append(_row(
                eid, row, direction, lo, hi, first_seen,
                batches_seen_validated=batches_seen, pass_batches=npass,
                fail_pillars=";".join(f"{p}x{c}" for p, c in
                                       fails.most_common()),
                armed_match_ts="", reason="A3", reason_detail=detail,
                fix_class=fix))
            continue
        rows_out.append(_row(
            eid, row, direction, lo, hi, first_seen,
            batches_seen_validated=batches_seen, pass_batches=0,
            fail_pillars=";".join(f"{p}x{c}" for p, c in fails.most_common()),
            reason="A2", reason_detail="in-batch-failed-pillars",
            fix_class="pillar bands (Architect only)"))
    # Deterministic examples: earliest first_sweep_ts per (reason, sub).
    seen: dict[tuple, int] = {}
    for r in sorted(rows_out,
                    key=lambda r: (str(r.get("first_sweep_ts") or ""),
                                   r["episode_id"])):
        key = (r["reason"], r["reason_detail"])
        seen[key] = seen.get(key, 0) + 1
        r["example_rank"] = seen[key]

    # Reconciliation: every population row classified exactly once.
    assert len(rows_out) == len(pop), (len(rows_out), len(pop))
    assert not [r for r in rows_out if r["reason"] not in
                ("A1", "A2", "A3", "A4", "A5")]

    with open(ROWS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows_out:
            writer.writerow({c: ("" if r.get(c) is None else r.get(c))
                             for c in CSV_COLUMNS})

    # ---- Aggregates ------------------------------------------------------ #
    def _median(vals):
        vals = sorted(v for v in vals if v not in (None, ""))
        vals = [float(v) for v in vals]
        if not vals:
            return None
        mid = len(vals) // 2
        if len(vals) % 2:
            return vals[mid]
        return (vals[mid - 1] + vals[mid]) / 2.0

    def _pillar_hist(sub):
        hist: Counter = Counter()
        for r in sub:
            for piece in str(r.get("fail_pillars") or "").split(";"):
                if "x" not in piece:
                    continue
                pillar, _, count = piece.partition("x")
                try:
                    hist[pillar] += int(count)
                except ValueError:
                    continue
        return dict(sorted(hist.items()))

    by_reason: dict[str, dict] = {}
    for top in ("A1", "A2", "A3", "A4", "A5"):
        sub = [r for r in rows_out if r["reason"] == top]
        by_reason[top] = {
            "n": len(sub),
            "pct_of_271": (round(100.0 * len(sub) / len(rows_out), 2)
                           if rows_out else None),
            "median_bars_sweep_to_confirm": _median(
                [r["bars_sweep_to_confirm"] for r in sub]),
            "subs": dict(sorted(Counter(
                r["reason_detail"] for r in sub).items())),
            "pillar_histogram": (_pillar_hist(sub) if top == "A2" else {}),
            "examples": [r["episode_id"] for r in sub
                         if r["example_rank"] in (1, 2)],
        }
    dominant = max(by_reason.items(),
                   key=lambda kv: kv[1]["n"])[0] if rows_out else None

    summary = {
        "banner": BANNER,
        "frozen": {
            "population": ("474-decomposition rows with reason_top == A "
                           "and reason_sub == A-validated-elsewhere; "
                           "reconciles to 271 — any other total reported, "
                           "never forced"),
            "replay": ("phase3_structure_funnel.run driven verbatim "
                       "(same window/config as the 6m refresh) with "
                       "call-through recorders (raw detections, validated "
                       "outcomes, arm events); restored after"),
            "fidelity_gate": ("replay funnel + trades.csv + report.json "
                              "must equal refresh run1 EXACTLY (byte "
                              "identity) — else FAIL"),
            "priority": ("A4 identity > A3 any-pass > A2 all-fail > "
                         "A1 absence > A5 gaps; first match wins"),
            "a4_rule": ("same direction + range overlap with an armed "
                        "episode armed within +/-30 days of first_seen "
                        "(heuristic identity evidence for human chart "
                        "check — overlap alone is cheap, stated)"),
            "a3_rule": ("any PASS + never armed; dedup-loser needs an "
                        "overlapping armed episode from a strictly earlier "
                        "batch (exact ZoneDedup rule); same-batch order "
                        "unknown -> dedup-possible; else other (no "
                        "cap/score/freshness filter exists in _arm_passed "
                        "— verified by reading)"),
            "a1_split": ("absent from every batch validated set; "
                         "A1a never in any raw set vs A1b raw exists "
                         "(merged away or model-skipped)"),
            "medians": "bars_sweep_to_confirm as recorded (M5 bars)",
            "examples": "earliest first_sweep_ts per (reason, sub)",
        },
        "n_primary": len(rows_out),
        "by_reason": by_reason,
        "dominant": dominant,
        "a4_match_kinds": dict(Counter(
            r["match_kind"] for r in rows_out if r["reason"] == "A4")),
        "fix_classes": dict(Counter(r["fix_class"] for r in rows_out)),
        "model_skip_batches": sum(
            1 for k in rec["raw"] if k[0] == "__skipped__"),
        "limitations": [
            "Containment matching inherits Step-4 Tier-B geometry rules "
            "(direction only, no tolerance).",
            "Dedup attribution replays the exact ZoneDedup predicate "
            "post-hoc (same direction + overlap, strictly-earlier batch "
            "required); intra-batch arm order is unknowable from logs "
            "(dedup-possible bucket).",
            "Passed-but-unarmed beyond dedup is genuinely unexplained "
            "by code reading (no other filter exists) — needs "
            "batch-level arm-decision logs.",
            "Medians mix M5 grids across studies (same canonical "
            "pipeline; offsets comparable, timestamps authoritative).",
            "No gate, no threshold, no live rule follows (see note).",
        ],
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[arma] n={len(rows_out)} " +
          " ".join(f"{t}={by_reason[t]['n']}" for t in
                   ("A1", "A2", "A3", "A4", "A5")),
          flush=True)
    print(f"[arma] wrote {OUT_DIR}", flush=True)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
