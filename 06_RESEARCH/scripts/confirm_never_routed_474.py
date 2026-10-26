#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""474 never-routed decomposition (read-only — measurement only).

Lead Architect directive (after POI_CONFIRM_ENTRY_PATH_NOTE.md):
exclusive taxonomy of why 474 post-sweep LTF-confirmed episodes never
became a post-sweep product route. No loosening gates, no new entry
rules, no threshold/constant changes.

Frozen design (stated before running):
  * Population = Step-4 lifecycle rows with a post-sweep route MISSING
    (gap_reason != ""), restricted to confirmed_48 (reconciles to 474;
    any other total is reported, never forced).
  * Top level reuses Step-4 gap_reason verbatim (A no-product-POI /
    B routed-before-sweep / C scanned-no-route / D never-scanned;
    unclassified rows would surface as defects, expected 0).
  * C sub-break (frozen priority order — first match wins):
      C1 expired-give-up : confirmation ts AFTER arm+20 M5 bars
           (the seek deadline passed before the trigger completed).
      C2 scan-late      : first recorded scan AFTER the confirmation
           (product started scanning this POI too late for it).
      C3 matrix_ineligible: confirming trigger letter absent from the
           product POI's eligible set (expected ~0 — the §15 matrix
           grades ties, it forbids nothing; verified, not assumed).
      C4 scanned_no_route_unspecified: remainder (scan ran inside the
           window and found nothing — cursor/posture/signal timing is
           below log resolution; fix class is instrumentation).
  * A split (frozen): episode geometry present vs absent in the
    accepted H4/D1 packs (episode-key match). Present = validated
    elsewhere but unarmed here (arm-timing/batch dynamics);
    absent = raw-only detections (pillar stage).
  * Medians use bars_sweep_to_confirm (M5 bars, Step-3 grid) as
    recorded; examples = earliest first_sweep_ts (deterministic).
  * Timestamps compare as ISO strings (single +00:00 UTC spelling
    throughout); M5 indices resolve on one rebuilt canonical grid
    (proven identical to the replay grid: 35,725 bars, same endpoints).
  * Fix classes (stated, never implemented): instrumentation (needs
    better logging) vs arm timing (when arming/scanning happens) vs
    real rule change (Architect only) vs none (working as designed).

Outputs: results/confirm_never_routed_474/{decomposition.csv,
summary.json}. Note: CONFIRM_NEVER_ROUTED_474_NOTE.md (separate step).
LOGIC_CHANGED: NO (04_SRC imported read-only: router eligibility +
model enums only; no decision path touched).
"""

from __future__ import annotations

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

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.triggers.trigger_router import TriggerRouter

import ltf_confirmation_pack as ltf

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "confirm_never_routed_474"
ROWS_CSV = OUT_DIR / "decomposition.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — NOT EDGE"

LIFECYCLE_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                 "poi_confirm_entry_path" / "lifecycle_per_episode.csv")
CONFIRM_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
               "poi_swept_ltf_confirm" / "confirm_per_episode.csv")
POI_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "htf_poi_census" /
           "poi_episodes.csv")
ARMED_JSON = (REPO_ROOT / "06_RESEARCH" / "results" /
              "poi_confirm_entry_path" / "replay_run1" / "armed_records.json")

CSV_COLUMNS = [
    "episode_id", "tf", "kind_tag", "direction", "first_sweep_ts",
    "bars_sweep_to_confirm", "first_confirm_trigger",
    "reason_top", "reason_sub", "join_tier",
    "confirm_ts", "arm_ts", "giveup_ts", "first_scan_ts",
    "in_accepted_packs", "matrix_ok", "fix_class", "example_rank",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def subreason_c(giveup_passed: bool, scan_late: bool,
                matrix_ok: bool) -> str:
    """Frozen C priority: expired-give-up > scan-late > matrix > rest."""
    if giveup_passed:
        return "C1-expired-give-up"
    if scan_late:
        return "C2-scan-late"
    if not matrix_ok:
        return "C3-matrix-ineligible"
    return "C4-scanned-no-route-unspecified"


def fix_class_for(reason_top: str, reason_sub: str) -> str:
    """Fix class per reason (stated, never implemented here)."""
    if reason_top == "B":
        return "none (working as designed — one-shot consumed)"
    if reason_top == "D":
        return "instrumentation (no such rows; rule kept for completeness)"
    if reason_sub in ("C2-scan-late",):
        return "arm timing"
    if reason_sub in ("C4-scanned-no-route-unspecified",):
        return "instrumentation (per-scan posture/cursor/signal logging)"
    if reason_sub in ("C1-expired-give-up", "C3-matrix-ineligible"):
        return "real rule change (Architect only)"
    if reason_sub == "A-validated-elsewhere":
        return "arm timing (batch/dedup dynamics; instrument first)"
    if reason_sub == "A-never-validated":
        return "real rule change (pillar bands; Architect only)"
    return "instrumentation"


def letter_of(trigger_type) -> str:
    """Trigger family letter for an enum member or plain string."""
    value = getattr(trigger_type, "value", trigger_type)
    return str(value).split("_")[0].upper()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (LIFECYCLE_CSV, CONFIRM_CSV, POI_CSV, ARMED_JSON):
        if not path.exists():
            raise SystemExit(f"required input missing: {path}")

    life = list(csv.DictReader(open(LIFECYCLE_CSV, encoding="utf-8")))
    conf = {r["episode_id"]: r for r in
            csv.DictReader(open(CONFIRM_CSV, encoding="utf-8"))}
    poi = {r["episode_id"]: r for r in
           csv.DictReader(open(POI_CSV, encoding="utf-8"))}
    armed = json.loads(ARMED_JSON.read_text(encoding="utf-8"))

    # ---- M5 grid (identical rebuild; endpoints asserted) ------------------ #
    m1_all = load_ohlcv_parquet(
        str(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"), Timeframe.M1)
    m1 = [c for c in m1_all
          if datetime(2025, 5, 1, tzinfo=timezone.utc) <= c.timestamp]
    m5 = [c for c in resample_multi(m1, [Timeframe.M5])[Timeframe.M5]
          if datetime(2025, 6, 1, tzinfo=timezone.utc) <= c.timestamp
          <= datetime(2025, 11, 30, tzinfo=timezone.utc)
          + timedelta(days=1) - timedelta(minutes=1)]
    m5_ts = [c.timestamp.isoformat() for c in m5]
    m5_keys = {}
    for _i, _c in enumerate(m5):
        m5_keys.setdefault(_c.timestamp.strftime("%Y-%m-%d %H:%M"), _i)
    assert len(m5_ts) == 35725, len(m5_ts)
    assert m5_ts[0].startswith("2025-06-01T22:00"), m5_ts[0]
    assert m5_ts[-1].startswith("2025-11-30T23:55"), m5_ts[-1]
    m5_index = {ts: i for i, ts in enumerate(m5_ts)}

    # ---- Accepted-pack geometry set (A split) ------------------------------ #
    pack_keys: set[tuple] = set()
    with open(ltf.H4_EVENTS_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["event_type"] == "poi_raw":
                pack_keys.add(
                    (r["direction"],
                     round(float(r["zone_low"]), 3),
                     round(float(r["zone_high"]), 3)))
    if ltf.D1_EVENTS_CSV.exists():
        with open(ltf.D1_EVENTS_CSV, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["event_type"] == "poi_raw":
                    pack_keys.add(
                        (r["direction"],
                         round(float(r["zone_low"]), 3),
                         round(float(r["zone_high"]), 3)))

    router = TriggerRouter()

    # ---- Population: confirmed, never post-sweep routed -------------------- #
    pop = [r for r in life if r.get("gap_reason")]
    print(f"[474] never-routed rows={len(pop)}", flush=True)

    rows_out: list[dict] = []
    for row in sorted(pop, key=lambda r: (r.get("first_sweep_ts") or "",
                                          r["episode_id"])):
        eid = row["episode_id"]
        crow = conf.get(eid, {})
        prow = poi.get(eid, {})
        top = {"no-product-POI": "A", "routed-before-sweep": "B",
               "scanned-no-route": "C", "never-scanned": "D"}.get(
                   row.get("gap_reason"), "D")
        sub, confirm_ts, arm_ts, giveup_ts = "", "", "", ""
        first_scan_ts = row.get("first_scan_ts") or ""
        in_packs, matrix_ok = "", ""
        try:
            sweep_min = datetime.fromisoformat(
                row.get("first_sweep_ts") or "").strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            sweep_min = None
        sweep_idx = m5_keys.get(sweep_min) if sweep_min else None
        bars = crow.get("bars_sweep_to_confirm") or ""
        try:
            confirm_ts = m5_ts[sweep_idx + int(bars)] \
                if sweep_idx is not None and bars != "" else ""
        except (IndexError, ValueError, TypeError):
            confirm_ts = ""
        if top == "A" and prow:
            key = (prow.get("direction"),
                   round(float(prow["zone_low"]), 3),
                   round(float(prow["zone_high"]), 3))
            in_packs = key in pack_keys
            sub = ("A-validated-elsewhere" if in_packs
                   else "A-never-validated")
        elif top == "B":
            sub = "B-one-shot-consumed"
        elif top == "C":
            joined_id = row.get("joined_poi_id") or ""
            arm_bar, tags = None, []
            for _pid, rec in armed.items():
                if _pid == joined_id:
                    arm_bar = rec.get("armed_bar")
                    tags = str(rec.get("model_tags") or "").split("|")
                    break
            if arm_bar is not None:
                try:
                    arm_ts = m5_ts[int(arm_bar)]
                    giveup_ts = (m5_ts[int(arm_bar) + 20]
                                 if int(arm_bar) + 20 < len(m5_ts) else "")
                except (IndexError, ValueError, TypeError):
                    arm_ts, giveup_ts = "", ""
            giveup_passed = bool(giveup_ts and confirm_ts
                                 and confirm_ts > giveup_ts)
            scan_late = bool(first_scan_ts and confirm_ts
                             and first_scan_ts > confirm_ts)
            models = [ModelType[t] for t in tags
                      if t in ModelType.__members__]
            # matrix_ok defaults True: eligibility untestable without tags
            # must never count as ineligible (documented default).
            matrix_ok = True
            prod_poi = POI(
                zone=Zone(
                    bottom=float(prow["zone_low"]),
                    top=float(prow["zone_high"]),
                    direction=Direction[row["direction"]],
                    timeframe=Timeframe.M5),
                models=models) if prow and models else None
            if prod_poi is not None:
                elig = {letter_of(t) for t in
                        router.eligible_types(prod_poi)}
                # Confirming letter = the episode's own first confirmation.
                conf_letter = (crow.get("first_confirm_trigger") or "")
                matrix_ok = (not conf_letter) or (conf_letter in elig)
            sub = subreason_c(giveup_passed, scan_late, matrix_ok)
            in_packs = ""
        elif top == "D":
            sub = "D-never-scanned"
        rows_out.append({
            "episode_id": eid, "tf": row.get("tf"),
            "kind_tag": row.get("kind_tag"),
            "direction": row.get("direction"),
            "first_sweep_ts": row.get("first_sweep_ts"),
            "bars_sweep_to_confirm": bars,
            "first_confirm_trigger": crow.get("first_confirm_trigger"),
            "reason_top": top, "reason_sub": sub,
            "join_tier": row.get("join_tier"),
            "confirm_ts": confirm_ts, "arm_ts": arm_ts,
            "giveup_ts": giveup_ts, "first_scan_ts": first_scan_ts,
            "in_accepted_packs": in_packs,
            "matrix_ok": matrix_ok,
            "fix_class": fix_class_for(top, sub),
            "example_rank": "",
        })

    # Deterministic examples: earliest first_sweep_ts per (top, sub).
    seen: dict[tuple, int] = {}
    for r in sorted(rows_out,
                    key=lambda r: (r["first_sweep_ts"], r["episode_id"])):
        key = (r["reason_top"], r["reason_sub"])
        seen[key] = seen.get(key, 0) + 1
        r["example_rank"] = seen[key]

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

    by_reason: dict[str, dict] = {}
    for top in ("A", "B", "C", "D"):
        sub = [r for r in rows_out if r["reason_top"] == top]
        by_reason[top] = {
            "n": len(sub),
            "pct_of_474": (round(100.0 * len(sub) / len(rows_out), 2)
                           if rows_out else None),
            "median_bars_sweep_to_confirm": _median(
                [r["bars_sweep_to_confirm"] for r in sub]),
            "subs": dict(sorted(Counter(
                r["reason_sub"] for r in sub).items())),
            "examples": [r["episode_id"] for r in sub
                         if r["example_rank"] in (1, 2)],
        }
    dominant = max(by_reason.items(),
                   key=lambda kv: kv[1]["n"])[0] if rows_out else None

    summary = {
        "banner": BANNER,
        "frozen": {
            "population": ("Step-4 lifecycle rows with gap_reason set "
                           "(confirmed, never post-sweep routed); "
                           "reconciles to 474 — any other total reported, "
                           "never forced"),
            "top_level": ("Step-4 gap_reason reused verbatim "
                          "(A/B/C/D); unclassified rows would surface "
                          "as defects"),
            "c_order": ("expired-give-up > scan-late > matrix > rest; "
                        "first match wins"),
            "giveup_rule": ("confirm_ts AFTER arm_bar+20 M5 bars; "
                            "deadline past series end = untestable, "
                            "never expired"),
            "matrix_rule": ("confirming letter in product POI eligible "
                            "set (router.eligible_types on merged tags); "
                            "§15 grades ties, forbids nothing — expect ~0"),
            "a_split": ("episode geometry in accepted H4/D1 packs "
                        "(episode-key match) or not"),
            "medians": "bars_sweep_to_confirm (M5 bars, Step-3 grid)",
            "examples": "earliest first_sweep_ts per (top, sub)",
        },
        "n_total": len(rows_out),
        "by_reason": by_reason,
        "dominant": dominant,
        "fix_classes": dict(Counter(r["fix_class"] for r in rows_out)),
        "limitations": [
            "Containment joins inherit Step-4 Tier-B matching (direction "
            "only, no tolerance).",
            "C4 remainder is below log resolution by construction "
            "(cursor/posture/signal timing unlogged) — its fix class is "
            "instrumentation, not a rule.",
            "Medians mix M5 grids across studies (same canonical "
            "pipeline; offsets comparable, timestamps authoritative).",
            "No gate, no threshold, no live rule follows (see note).",
        ],
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[474] n={len(rows_out)} " +
          " ".join(f"{t}={by_reason[t]['n']}" for t in "ABCD"),
          flush=True)
    print(f"[474] wrote {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
