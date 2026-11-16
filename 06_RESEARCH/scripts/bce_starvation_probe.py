"""BCE STARVATION PROBE — why B/C/E never become filled plans (measurement only).

Question: for triggers B (Leading Diagonal), C (Ending Diagonal), E (RSI
Divergence) — which show material no-POI existence (1A: B 267 / C 75 / E 143)
and some POI-linked M5 completions (Scan 1B: B 185 / C 12 / E 21 occurrences)
but ZERO fills in product_1y — what is the FIRST hard gate that prevents a
FILLED plan?

GATE ORDER (product flow, code-verified; mirrors what the product runs):
  1. §15 compatibility matrix — every (model, trigger) cell is ALLOWED
     (grade = same-bar tie-break only), so ``MATRIX_BLOCKED`` can never be
     the gate; recorded as 0-by-construction with the grade as a secondary
     tag.
  2. MENU TIER SCOPE — ``ProductMenuEngine`` builds each detection tier's
     confirmation router from ``tier.trigger_types``: M15/H1/H4 tiers use
     ``_TIER_ADF = (A, D, F)``; ONLY the DAY tier (D1 detection, H1
     confirmation) carries all six triggers. A B/C/E confirmation is
     structurally impossible on M15/H1/H4-detected POIs.
  3. SWEEP → EPISODE — a one-shot episode opens on the first R2 zone sweep
     (direction-dependent predicate: LONG wick-below+close-back / SHORT
     inverse) after the arm instant (F5), inside ``MENU_EXPIRY_BARS = 20``
     detection bars (F2 window-open guard).
  4. H1 CONFIRMATION — the DAY tier confirms on H1 closed bars inside the
     window (earliest completion wins, F2). The Scan-1B M5 completion
     geometry is NEVER read by the menu — M5 completion ≠ H1 confirmation.
  5. C3 IN-BETWEEN — ``candidate_from_route`` rejects out-of-zone
     completions (episode stays ACTIVE, unconsumed).
  6. POST-MENU SEAM — winner → adapter intake (one-story guard), submit,
     place, fill. Per-POI placement flags are NOT exported by product_1y
     artifacts (aggregate only), so a replay winner that did not fill is
     reported as ``BCE_WON_NO_FILL`` with that indistinguishability noted.

METHOD:
- Reuses Scan 1B linkage (POI-linked B/C/E completion rows) — no full
  re-detection. 1A-only rows (no POI link) are counted via an exact
  (trigger, direction, bar_time_utc) join and get ``NO_POI_LINK``.
- For the D1-tier subset: a faithful offline replay of the product menu
  machinery per involved segment — ``ProductMenuEngine`` with the SAME
  wiring the product_1y harness used (``same_bar_asof=False``, no §5 state
  resolver — verified: phase3 never wires one; ``MENU_WARMUP_BARS = 300``
  warmup cursor; closed-prefix feed per M5 execution bar), the DAY tier
  router built from ALL SIX production triggers with an evaluate-logging
  wrapper, armed D1-detected POIs registered with real zone bounds and
  ``armed_ts`` from the armed records.
- Direction: armed records export no direction, and the sweep predicate and
  every trigger read ``zone.direction`` — so each segment is replayed TWICE
  (LONG and SHORT hypotheses). A reason that agrees across both hypotheses
  is direction-robust; disagreement is reported as ``DIRECTION_AMBIGUOUS``
  (never guessed). Omitting the state resolver makes the replay an UPPER
  BOUND on menu confirmations (the product's §5 blocking could only remove
  more) — documented.
- Cross-check (fail loud): B+C+E fills in product_1y must remain 0.

DIAGNOSTIC ONLY: no edge claim, no fix, no threshold/matrix/C3/TP/SL change;
production code imported, never reimplemented; D is out of scope (one-line
footnote: structurally dead on the zero-volume feed).
"""

from __future__ import annotations

import csv
import json
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "04_SRC"))
sys.path.insert(0, str(REPO / "06_RESEARCH" / "scripts"))

from smc.config.model_type import ModelType  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.enums import Direction, TriggerType  # noqa: E402
from smc.core.poi import POI  # noqa: E402
from smc.core.zone import Zone  # noqa: E402
from smc.data.parquet_loader import load_ohlcv_parquet  # noqa: E402
from smc.data.resample import resample_multi  # noqa: E402
from smc.triggers.compatibility_matrix import DEFAULT_MATRIX  # noqa: E402
from smc.triggers.trigger_expiry import poi_give_up_bars  # noqa: E402
from smc.triggers.trigger_router import (  # noqa: E402
    TriggerRouter,
    default_triggers,
)
from smc.orchestration.product_menu_mtf import (  # noqa: E402
    MENU_EXPIRY_BARS,
    MenuEpisodeStatus,
    ProductMenuEngine,
    _TIER_ADF,
)

SRC = REPO / "06_RESEARCH" / "results" / "product_1y_one_story" / "run1"
P1Y_SUMMARY = (REPO / "06_RESEARCH" / "results" / "product_1y_one_story"
               / "summary.json")
SCAN1A_EVENTS = (REPO / "06_RESEARCH" / "results" / "scan1a_ltf_no_poi"
                 / "events_scan1a_completions.csv")
SCAN1B_EVENTS = (REPO / "06_RESEARCH" / "results" / "scan1b_ltf_with_poi"
                 / "events_scan1b_completions.csv")
OUT = REPO / "06_RESEARCH" / "results" / "bce_starvation"
SAMPLES = OUT / "samples"

EXEC_FROM, EXEC_TO = "2024-11-01", "2025-10-31"
LOAD_FROM = "2024-09-01"
MENU_WARMUP_BARS = 300                     # phase3 mirror (frozen harness)
M5_MIN = Timeframe.M5.minutes

BCE = ("B", "C", "E")
_GRADES = {t.value: DEFAULT_MATRIX.grade(m, t)
           for m in ModelType for t in TriggerType}
GRADE_NAME = {1: "uncommon", 2: "structural", 3: "preferred"}

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

# Fixed primary-reason enum (product gate order; extends the spec's seed
# enum with precisely-defined entries — documented in the report).
REASON_ORDER = [
    "MATRIX_BLOCKED",           # §15 matrix forbids the pair (expected 0)
    "MENU_TIER_EXCLUDED",       # trigger absent from the detection tier's
                                # confirmation router (_TIER_ADF tiers)
    "NO_SWEEP_NO_EPISODE",      # no post-arm R2 sweep opened a window
    "EPISODE_NO_CONFIRMATION",  # window opened; no H1 B/C/E completion
    "CONFIRMED_OTHER_TRIGGER",  # window won by A/D/F (POI consumed)
    "BCE_C3_REJECTED",          # B/C/E route reached _win; C3 rejected
    "BCE_WON_NO_FILL",          # replay winner; product never filled
                                # (guard/submit/place seam, aggregate-only)
    "DIRECTION_AMBIGUOUS",      # replay hypotheses disagree (DATA_GAP class)
    "NO_POI_LINK",              # 1A-only rows (counted separately)
    "OTHER_DATA_GAP",           # must carry a note; keep rare
]


def fail_loud(msg: str) -> None:
    raise SystemExit(f"[bce-starve] FAIL LOUD: {msg}")


def parse_models(tags: str) -> list[ModelType]:
    out = []
    for part in str(tags or "").split("|"):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(ModelType[part])
        except KeyError:
            pass
    return out or [ModelType.M8]


_TT_BY_LETTER = {t.value: t for t in TriggerType}


def best_grade(tags: str, letter: str) -> str:
    """Best §15 grade across the POI's tags for one trigger letter."""
    tt = _TT_BY_LETTER[letter]
    grade = max((DEFAULT_MATRIX.grade(m, tt) for m in parse_models(tags)),
                key=lambda g: g.value)
    return grade.name.lower()


class LoggingRouter(TriggerRouter):
    """DAY-tier router (all six production triggers) with evaluate logging."""

    def __init__(self, log: list) -> None:
        super().__init__(triggers=default_triggers())
        self.log = log

    def evaluate_at(self, poi, candles, swings, bar, from_bar=0, **kw):
        route = super().evaluate_at(poi, candles, swings, bar,
                                    from_bar, **kw)
        candle = candles[bar]
        self.log.append({
            "poi_key": poi.id,
            "close_ts": (candle.timestamp
                         + timedelta(minutes=candle.timeframe.minutes)),
            "trigger": (route.signal.trigger.value if route else None),
        })
        return route


def segment_series(lo: str, hi: str) -> tuple[list, list, list]:
    """(M5 exec-only, H1 warmup, D1 warmup) — phase3 resample conventions."""
    lo_dt = datetime.fromisoformat(lo).replace(tzinfo=timezone.utc)
    hi_dt = (datetime.fromisoformat(hi).replace(tzinfo=timezone.utc)
             + timedelta(days=1) - timedelta(minutes=1))
    load_lo = datetime.fromisoformat(LOAD_FROM).replace(tzinfo=timezone.utc)
    m1 = [c for c in load_ohlcv_parquet(REPO / "07_DATA" / "XAUUSD_M1.parquet")
          if load_lo <= c.timestamp <= hi_dt + timedelta(days=1)]
    multi = resample_multi(m1, [Timeframe.M5, Timeframe.H1, Timeframe.D1])
    m5 = [c for c in multi[Timeframe.M5] if lo_dt <= c.timestamp <= hi_dt]
    return m5, multi[Timeframe.H1], multi[Timeframe.D1]


def replay_menu_for_segment(seg: str, m5: list, h1: list, d1: list,
                            armed_d1: list[dict], direction: Direction
                            ) -> dict:
    """Faithful offline replay of the product menu machinery for one segment.

    Wiring mirrors phase3/product_1y exactly: ProductMenuEngine with
    ``same_bar_asof=False``, NO §5 state resolver (the product_1y harness
    never wires one — verified), ``MENU_WARMUP_BARS = 300`` warmup cursor,
    closed-prefix feed per M5 execution bar. Only the DAY tier's streams
    (D1 detection, H1 confirmation) are fed — the other tiers' streams are
    never read by a D1 episode, so their omission is state-identical.
    """
    engine = ProductMenuEngine(symbol="XAUUSD", same_bar_asof=False)
    log: list = []
    engine._tier_routers["DAY"] = LoggingRouter(log)

    registry: dict[str, str] = {}   # constructed poi.id -> armed record id
    arm_ts: dict[str, str] = {}
    for rec in armed_d1:
        poi = POI(zone=Zone(bottom=float(rec["zone_low"]),
                            top=float(rec["zone_high"]),
                            direction=direction,
                            timeframe=Timeframe.D1),
                  models=parse_models(rec["model_tags"]), m8_kind=None)
        registry[poi.id] = rec["poi_id"]
        ts = m5[int(rec["armed_bar"])].timestamp
        arm_ts[rec["poi_id"]] = ts.isoformat()
        if not engine.register_armed(poi, Timeframe.D1, armed_ts=ts):
            fail_loud(f"{seg}: register_armed rejected {rec['poi_id']}")

    det_closes = [c.timestamp + timedelta(minutes=Timeframe.D1.minutes)
                  for c in d1]
    conf_closes = [c.timestamp + timedelta(minutes=Timeframe.H1.minutes)
                   for c in h1]
    cursor: dict[str, int] = {}
    for bar in m5:
        as_of = bar.timestamp + timedelta(minutes=M5_MIN)
        closed = {}
        for tf, series, closes, key in ((Timeframe.D1, d1, det_closes, "D1"),
                                        (Timeframe.H1, h1, conf_closes, "H1")):
            end = bisect_right(closes, as_of)
            start = cursor.get(key)
            if start is None:
                start = max(0, end - MENU_WARMUP_BARS)
            cursor[key] = max(start, end)
            # Feed the closed prefix slice [start, end) — the warmup window on
            # the first call, then only bars new since the last call. The
            # engine keeps only bars newer than its stored tail, so its state
            # is identical to phase3's full-prefix feed.
            closed[tf] = series[start:end]
        engine.on_execution_bar(closed, as_of=as_of)

    by_key: dict[str, list] = defaultdict(list)
    for ep in engine.episodes():
        by_key[ep.poi_id].append(ep)
    return {
        "episodes_by_key": by_key,
        "log": log,
        "registry": registry,
        "arm_ts": arm_ts,
        "counters": dict(engine._counters),
        "winners": [(w.poi_id, w.trigger) for w in engine.winners],
    }


def classify_poi(episodes: list, attempts: list[dict]) -> tuple:
    """First-gate classification for one POI under one direction hypothesis.

    Attempts are attributed to the episode whose sweep opened at or before
    the attempt's close instant (a POI has at most one ACTIVE episode at a
    time; a new window can open only after expiry — one-shot discipline).
    """
    if not episodes:
        return "NO_SWEEP_NO_EPISODE", "", None
    eps = sorted(episodes, key=lambda e: e.sweep_close_ts)
    att_by_ep: dict[int, list] = defaultdict(list)
    for a in sorted((x for x in attempts if x["close_ts"] is not None),
                    key=lambda x: x["close_ts"]):
        owner = None
        for i, ep in enumerate(eps):
            if ep.sweep_close_ts <= a["close_ts"]:
                owner = i
            else:
                break
        if owner is not None:
            att_by_ep[owner].append(a)
    for i, ep in enumerate(eps):
        att = att_by_ep.get(i, [])
        bce_att = [a for a in att if a["trigger"] in BCE]
        if ep.status is MenuEpisodeStatus.WON:
            win_trig = ""
            for d in ep.decisions:
                if d.startswith("won_"):
                    win_trig = d.split("_", 2)[2]
            if bce_att:
                # a B/C/E route reached _win and was C3-rejected before the
                # episode was later won by another trigger (or the win IS the
                # B/C/E route — disambiguated below)
                if win_trig in BCE:
                    return ("BCE_WON_NO_FILL",
                            f"replay winner {win_trig} on H1; product never "
                            "filled (guard/submit/place seam, per-POI "
                            "placement flags not exported)", ep.sweep_ts)
                return ("BCE_C3_REJECTED",
                        f"B/C/E route attempted in window, C3 rejected; "
                        f"episode won by {win_trig or '?'}", ep.sweep_ts)
            return ("CONFIRMED_OTHER_TRIGGER",
                    f"episode won on H1 by {win_trig or '?'}; B/C/E never "
                    "completed in window", ep.sweep_ts)
        # EXPIRED episode
        if bce_att:
            return ("BCE_C3_REJECTED",
                    "B/C/E route attempted in window, C3 rejected; window "
                    "expired", ep.sweep_ts)
    return ("EPISODE_NO_CONFIRMATION",
            "no B/C/E completion on H1 in any opened window",
            eps[0].sweep_ts)


def main() -> int:
    import time
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    SAMPLES.mkdir(parents=True, exist_ok=True)

    # ---- cross-check: B+C+E fills == 0 (fail loud) ------------------------- #
    p1y = json.loads(P1Y_SUMMARY.read_text(encoding="utf-8"))
    mix = p1y["combined"]["fills_by_trigger"]
    if any(k in mix for k in BCE):
        fail_loud(f"B/C/E fills non-zero in product_1y: {mix}")
    fills_all = []
    for seg in sorted(SRC.iterdir()):
        if not seg.is_dir():
            continue
        with (seg / "trades.csv").open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                fills_all.append(row)
                if row.get("trigger") in BCE:
                    fail_loud(f"{seg}: trade with B/C/E trigger "
                              f"{row.get('trigger')}")
    d1_fills = [r for r in fills_all
                if json.loads(r.get("signal_data_json") or "{}")
                .get("product_menu", {}).get("detection_tf") == "D1"]
    d1_fill_trigs = Counter(r["trigger"] for r in d1_fills)

    # ---- armed records ----------------------------------------------------- #
    armed: dict[tuple, dict] = {}        # (segment, poi_id) -> record
    for seg in SEGMENTS:
        recs = json.loads((SRC / seg / "armed_records.json").read_text(
            encoding="utf-8"))
        for pid, rec in recs.items():
            rec["_segment"] = seg
            rec["_poi_id"] = pid
            armed[(seg, pid)] = rec

    # ---- Scan 1B POI-linked B/C/E rows ------------------------------------- #
    with SCAN1B_EVENTS.open(newline="", encoding="utf-8") as fh:
        bce_rows = [r for r in csv.DictReader(fh) if r["trigger"] in BCE]
    if not bce_rows:
        fail_loud("no B/C/E POI-linked rows found in scan1b events")

    for r in bce_rows:
        rec = armed[(r["segment"], r["poi_id"])]
        rec.setdefault("_targets", []).append(r)
        r["_detection_tf"] = rec["detection_tf"]
        r["_model_tags"] = rec["model_tags"]
        r["_routed"] = rec.get("routed", "")

    tier_excluded = [r for r in bce_rows if r["_detection_tf"] != "D1"]
    d1_rows = [r for r in bce_rows if r["_detection_tf"] == "D1"]

    # ---- D1-subset menu replay (both direction hypotheses) ----------------- #
    d1_pois: dict[str, list[dict]] = defaultdict(list)   # segment -> records
    for r in d1_rows:
        rec = armed[(r["segment"], r["poi_id"])]
        if rec not in d1_pois[r["segment"]]:
            d1_pois[r["segment"]].append(rec)
    poi_reason: dict[tuple, tuple] = {}
    arm_ts_by_poi: dict[tuple, str] = {}
    replay_meta: dict[str, dict] = {}
    for seg, recs in sorted(d1_pois.items()):
        m5, h1, d1 = segment_series(*SEGMENTS[seg])
        for rec in recs:
            if not (0 <= int(rec["armed_bar"]) < len(m5)):
                fail_loud(f"{seg}: armed_bar {rec['armed_bar']} out of range")
        hyp = {}
        for direction in (Direction.LONG, Direction.SHORT):
            rp = replay_menu_for_segment(seg, m5, h1, d1, recs, direction)
            per_poi = {}
            key_for = {v: k for k, v in rp["registry"].items()}
            for rec in recs:
                pid = rec["poi_id"]
                attempts = [e for e in rp["log"]
                            if e["poi_key"] == key_for[pid]]
                per_poi[pid] = classify_poi(rp["episodes_by_key"]
                                            .get(key_for[pid], []),
                                            attempts)
            hyp[direction.name] = per_poi
            if direction is Direction.LONG:
                for pid, ts in rp["arm_ts"].items():
                    arm_ts_by_poi[(seg, pid)] = ts
            print(f"[bce-starve] {seg} {direction.name}: episodes "
                  f"{len(rp['episodes_by_key'])} winners "
                  f"{len(rp['winners'])} opened="
                  f"{rp['counters'].get('episodes_opened')}", flush=True)
        for rec in recs:
            pid = rec["poi_id"]
            rl, rn, sl = hyp["LONG"][pid]
            rs, sn, ss = hyp["SHORT"][pid]
            if rl == rs:
                poi_reason[(seg, pid)] = (rl, f"both directions agree: {rn}",
                                          sl)
            else:
                poi_reason[(seg, pid)] = (
                    "DIRECTION_AMBIGUOUS",
                    f"LONG:{rl}({rn}) | SHORT:{rs}({sn})", None)
        replay_meta[seg] = {
            "m5_bars": len(m5), "h1_bars": len(h1), "d1_bars": len(d1),
            "n_d1_armed": len(recs),
        }
        print(f"[bce-starve] {seg}: D1 replay classified "
              f"{len(recs)} POIs", flush=True)

    # ---- 1A-only join (NO_POI_LINK) ---------------------------------------- #
    with SCAN1A_EVENTS.open(newline="", encoding="utf-8") as fh:
        a_rows = [r for r in csv.DictReader(fh) if r["trigger"] in BCE]
    b_keys = {(r["trigger"], r["direction"], r["bar_time_utc"])
              for r in bce_rows}
    a_only = [r for r in a_rows
              if (r["trigger"], r["direction"], r["bar_time_utc"])
              not in b_keys]

    # ---- starvation rows ---------------------------------------------------- #
    out_rows = []
    for r in bce_rows:
        key = (r["segment"], r["poi_id"])
        if r["_detection_tf"] != "D1":
            reason, note = "MENU_TIER_EXCLUDED", (
                f"detection_tf={r['_detection_tf']}; the "
                f"{r['_detection_tf']} tier's confirmation router carries "
                "only A/D/F (_TIER_ADF) — B/C/E not confirmable on this tier")
        else:
            reason, note, sweep_ts = poi_reason.get(
                key, ("OTHER_DATA_GAP", "unmapped", None))
        rec = armed[key]
        row = {
            "trigger": r["trigger"], "segment": r["segment"],
            "poi_id": r["poi_id"], "detection_tf": r["_detection_tf"],
            "model_tags": r["_model_tags"],
            "grade": best_grade(r["_model_tags"], r["trigger"]),
            "bar_time_utc": r["bar_time_utc"],
            "product_routed": r["_routed"],
            "primary_reason": reason, "note": note,
            "row_class": "POI_LINKED",
        }
        if r["_detection_tf"] == "D1":
            row["arm_ts"] = arm_ts_by_poi.get(key, "")
            row["sweep_ts"] = (sweep_ts.isoformat() if sweep_ts else "")
        out_rows.append(row)
    for r in a_only:
        out_rows.append({
            "trigger": r["trigger"], "segment": "", "poi_id": "",
            "detection_tf": "", "model_tags": "", "grade": "",
            "bar_time_utc": r["bar_time_utc"],
            "product_routed": "",
            "primary_reason": "NO_POI_LINK",
            "note": ("1A completion outside every armed-POI window "
                     "(trigger+direction+bar_time join)"),
            "row_class": "1A_ONLY",
        })

    cols = ["trigger", "segment", "poi_id", "detection_tf", "model_tags",
            "grade", "bar_time_utc", "product_routed", "primary_reason",
            "note", "row_class", "arm_ts", "sweep_ts"]
    with (OUT / "starvation_rows.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for row in out_rows:
            w.writerow({k: row.get(k, "") for k in cols})

    # ---- headline counts ----------------------------------------------------- #
    linked = [r for r in out_rows if r["row_class"] == "POI_LINKED"]
    headline = {t: dict(sorted(Counter(
        r["primary_reason"] for r in linked
        if r["trigger"] == t).items())) for t in BCE}
    a_only_by_trigger = {t: sum(1 for r in a_only if r["trigger"] == t)
                         for t in BCE}

    # ---- samples (<= 15 narrative timelines) --------------------------------- #
    sample_rows: list[dict] = []
    seen: set = set()
    for r in sorted(linked, key=lambda x: x["bar_time_utc"]):
        if len(sample_rows) >= 15:
            break
        k = (r["trigger"], r["primary_reason"])
        if k in seen:
            continue
        seen.add(k)
        sample_rows.append(r)
    for r in sorted(a_only, key=lambda x: x["bar_time_utc"]):
        if len(sample_rows) >= 15:
            break
        k = (r["trigger"], "NO_POI_LINK")
        if k in seen:
            continue
        seen.add(k)
        sample_rows.append({
            "trigger": r["trigger"], "segment": "", "poi_id": "",
            "detection_tf": "", "model_tags": "", "grade": "",
            "bar_time_utc": r["bar_time_utc"], "product_routed": "",
            "primary_reason": "NO_POI_LINK",
            "note": "1A-only geometry (no armed window contains it)",
        })
    index = []
    for i, r in enumerate(sample_rows, start=1):
        path = SAMPLES / (f"sample_{i:02d}_{r['trigger']}_"
                          f"{r['primary_reason'].lower()}.json")
        path.write_text(json.dumps(r, indent=2, default=str),
                        encoding="utf-8")
        index.append({"seq": i, "file": path.name, **{
            k: r.get(k) for k in ("trigger", "primary_reason",
                                  "segment", "poi_id", "bar_time_utc")}})

    # ---- contrast: F/A occurrences by POI detection_tf ----------------------- #
    with SCAN1B_EVENTS.open(newline="", encoding="utf-8") as fh:
        fa_occ = Counter()
        for r in csv.DictReader(fh):
            if r["trigger"] in ("F", "A"):
                fa_occ[(r["trigger"],
                        armed[(r["segment"], r["poi_id"])]["detection_tf"])] += 1
    contrast = {
        t: dict(sorted((tf, n) for (tt, tf), n in fa_occ.items() if tt == t))
        for t in ("A", "F")}

    summary = {
        "tag": "bce_starvation_probe",
        "diagnostic_only": True,
        "window": {"exec": f"{EXEC_FROM} -> {EXEC_TO}",
                   "load_from": LOAD_FROM,
                   "mode": "Scan1B linkage + D1-subset menu replay"},
        "enum": REASON_ORDER,
        "cross_checks": {
            "bce_fills_product_1y": 0,
            "fills_by_trigger": mix,
            "d1_fills": len(d1_fills),
            "d1_fill_triggers": dict(sorted(d1_fill_trigs.items())),
        },
        "headline_poi_linked": headline,
        "rows": {
            "poi_linked": len(linked),
            "tier_excluded": len(tier_excluded),
            "d1_subset_rows": len(d1_rows),
            "d1_subset_pois": sum(len(v) for v in d1_pois.values()),
            "a_only_rows": len(a_only),
            "a_only_by_trigger": a_only_by_trigger,
        },
        "a_only_share": {
            t: {"1a_total": sum(1 for r in a_rows if r["trigger"] == t),
                "no_poi_link": a_only_by_trigger[t],
                "poi_linked_occurrences": sum(headline.get(t, {}).values())}
            for t in BCE},
        "contrast_fa_by_detection_tf": contrast,
        "replay": {
            "wiring": ("ProductMenuEngine same_bar_asof=False, NO §5 state "
                       "resolver (product_1y harness mirror), "
                       "MENU_WARMUP_BARS=300, closed-prefix feed per M5 bar, "
                       "DAY-tier streams only (D1 detection + H1 "
                       "confirmation — state-identical for D1 episodes)"),
            "directions": "LONG and SHORT hypotheses (direction not exported)",
            "upper_bound_note": ("state resolver omitted ⇒ replay is an "
                                 "UPPER BOUND on menu confirmations"),
            "menu_expiry_bars": MENU_EXPIRY_BARS,
            "per_segment": replay_meta,
        },
        "samples_index": index,
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print(f"[bce-starve] rows {len(out_rows)} "
          f"(poi-linked {len(linked)}, 1A-only {len(a_only)})", flush=True)
    print(f"[bce-starve] headline {json.dumps(headline)}", flush=True)
    print(f"[bce-starve] wrote {OUT / 'summary.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
