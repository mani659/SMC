"""ENTRY QUALITY + FLOWCHART MATCH — books F and B (post-R1 year, read-only).

For human/Architect review: do the admitted books' fills look like the
intended SMC story (HTF POI -> interaction -> LTF confirmation -> entry), or
like chase / noise / wrong structure?

Inputs (existing artifacts only — no replay, no strategy code):
    06_RESEARCH/results/parallel_books_s3_rerun/<seg>/books_F-B-C-E-A_<hyp>/trades.csv
    07_DATA/XAUUSD_M1.parquet (chart rendering, read-only)

Outputs under 06_RESEARCH/results/entry_quality_f_b/ (gitignored):
    universe_features.csv   every F/B fill (union, deduped) + gates/flags
    sample_index.csv        the stratified review sample (blank architect cols)
    charts/<id>.png|.json    chart + sidecar per sampled fill
    summary.json            selection rule, distributions, failure modes

Scoring is a mechanical CHECKLIST over facts the export already carries
(no judgement about profitability, no expectancy). STRONG/PARTIAL/WEAK are
agent-draft labels for the Architect, not conclusions:

    G1 POI existed before interaction       armed_ts <= sweep_ts
    G2 interaction -> confirmation in window sweep_ts < completion_ts <= ENGINE window end
       (bar-counted: close of the detection bar at sweep_index + MENU_EXPIRY_BARS;
        NOT the stamp's `window_end_ts`, which is a wall-clock projection that
        ends early across market closures — see MENU_WINDOW_STAMP_RECONCILIATION.md)
    G3 LTF confirmation is the locked child  detect D1->H1 / H4->M5,M15 / H1->M1,M5 / M15->M1
    G4 entry limit inside the POI zone       zone_low <= entry <= zone_high
    Q4 entry not at the zone's chase edge    zone position <=92% (long) / >=8% (short)
    Q5 fill at the confirmation price        retrace >= -0.25 ATR
    G5 structural target (not ATR fallback)  tp_source == structural_swing

    STRONG 7/7 | PARTIAL 6/7 | WEAK <=5/7

Q4/Q5 are agent-draft entry-location proxies, NOT locked rules and not a
performance statement; the Architect may score any row differently.

The two window columns are kept apart on purpose:
    `window_end_bar_ts`  engine bound used by G2 (`window_end_source` = bar|open)
    `window_end_ts`      the stamp's nominal projection (audit/traceability only)
    `confirm_after_stamp` descriptive flag for a confirmation past the stamp;
                        it is NOT a gate and costs no point.

Descriptive only (never scored, because the locked stop is an ATR buffer
that may legitimately sit inside the HTF zone): stop beyond the zone's far
edge, sweep->fill latency, risk in ATR.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
S3 = REPO / "06_RESEARCH" / "results" / "parallel_books_s3_rerun"
OUT = REPO / "06_RESEARCH" / "results" / "entry_quality_f_b"
PARQUET = REPO / "07_DATA" / "XAUUSD_M1.parquet"

sys.path.insert(0, str(REPO / "06_RESEARCH" / "scripts"))
from lib.menu_window import bar_count_window_end  # noqa: E402

SEGMENTS = ("nov24", "dec24", "jan25", "feb25", "mar25", "apr25",
            "may25", "jun25", "jul25", "aug25", "sep25", "oct25")
HYPOTHESES = ("LONG", "SHORT")
BOOKS = ("F", "B")
UNIVERSE_BOOKS = ("F", "B", "C", "E", "A")
# Locked menu tier -> confirmation timeframes (00_LOCKED tier table).
CONFIRM_OK = {"D1": {"H1"}, "H4": {"M5", "M15"},
              "H1": {"M1", "M5"}, "M15": {"M1"}}

SAMPLE_PER_BOOK = 20


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def fill_key(row: dict) -> tuple:
    return (str(row["poi_id"]), str(row["trigger"]), str(row["entry_at"]),
            round(float(row["entry_price"]), 6), str(row["direction"]))


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(str(value))


def load_universe() -> list[dict]:
    """Union of every F/B fill in the 24 post-R1 runs (deduped by fill_key)."""
    seen: dict = {}
    for seg in SEGMENTS:
        for hyp in HYPOTHESES:
            d = S3 / seg / f"books_{'-'.join(UNIVERSE_BOOKS)}_{hyp}"
            for row in _read_csv(d / "trades.csv"):
                if row["trigger"] not in BOOKS:
                    continue
                row["run"] = f"{seg}/{hyp}"
                row["segment"] = seg
                row["hypothesis"] = hyp
                seen.setdefault(fill_key(row), row)
    rows = list(seen.values())
    for row in rows:
        stamp = json.loads(row["signal_data_json"])["product_menu"]
        row["_stamp"] = stamp
    rows.sort(key=lambda r: (SEGMENTS.index(r["segment"]), r["entry_at"]))
    return rows


def feature_row(row: dict) -> dict:
    """Deterministic facts + gates + descriptive flags for one fill."""
    row["_fid"] = (f"{row['trigger']}_{row['segment']}_{row['hypothesis'][0]}_"
                   f"{str(row['entry_at'])[:10]}_{row['poi_id']}")
    pm = row["_stamp"]
    lo, hi = float(row["zone_low"]), float(row["zone_high"])
    entry = float(row["entry_price"])
    sl = float(row["original_sl"] or row["sl"])
    long = row["direction"] == "long"
    atr = float(pm["atr_at_confirm"] or 0.0)
    armed, sweep = _dt(pm["armed_ts"]), _dt(pm["sweep_ts"])
    confirm, wend = _dt(pm["completion_ts"]), _dt(pm["window_end_ts"])
    fill = _dt(row["entry_at"])

    # G2 uses the ENGINE's window: close of the detection bar at
    # sweep_index + MENU_EXPIRY_BARS (None = that bar is beyond the loaded
    # segment, so the engine's own window has no upper bound — treated as open).
    # The stamp's ``window_end_ts`` is a wall-clock projection and is NOT used
    # for the gate (MENU_WINDOW_STAMP_RECONCILIATION.md).
    window_end_bar = bar_count_window_end(row["segment"], pm["detection_tf"], sweep)
    window_end_source = "bar" if window_end_bar is not None else "open"

    g1 = armed <= sweep
    g2 = (sweep < confirm <= window_end_bar if window_end_bar is not None
          else sweep < confirm)
    g3 = pm["confirmation_tf"] in CONFIRM_OK.get(pm["detection_tf"], set())
    g4 = lo <= entry <= hi
    g5 = row["tp_source"] == "structural_swing"

    # Descriptive geometry (used by the entry-location checks + report).
    sl_beyond = sl <= lo if long else sl >= hi
    retrace = ((float(pm["completion_close"]) - entry) / atr) if atr else None
    if retrace is not None and not long:
        retrace = -retrace
    no_pullback = retrace is not None and retrace <= -0.5
    # Bar-counted breach (a real one) vs the stamp's nominal projection (the
    # artefact class). Only the former is a gate failure.
    confirm_after_window = (window_end_bar is not None
                            and confirm > window_end_bar)
    confirm_after_stamp = confirm > wend
    latency_h = (fill - sweep).total_seconds() / 3600.0
    risk = abs(entry - sl)
    risk_atr = (risk / atr) if atr else None
    zone_pct = (100.0 * (entry - lo) / (hi - lo)) if hi > lo else None

    # Entry-location checks (agent-draft heuristics, NOT locked rules):
    # Q4 entry not pinned at the zone's chase edge (last 8% in trade direction)
    # Q5 filled at/within 0.25 ATR of the confirmation close (not beyond it)
    q4 = zone_pct is not None and (
        zone_pct <= 92.0 if long else zone_pct >= 8.0)
    q5 = retrace is not None and retrace >= -0.25
    gates = [g1, g2, g3, g4, q4, q5, g5]
    score = sum(gates)
    draft = ("STRONG" if score >= 7 else
             "PARTIAL" if score == 6 else "WEAK")

    flags = []
    if not g1:
        flags.append("order_inversion_armed_after_sweep")
    if not g2:
        flags.append("confirm_outside_window")
    if confirm_after_stamp:
        flags.append("confirm_after_stamp_window")
    if not g3:
        flags.append("confirm_tf_off_locked_map")
    if not g4:
        flags.append("entry_outside_zone")
    if not q4:
        flags.append("entry_at_zone_chase_edge")
    if not q5:
        flags.append("fill_beyond_confirm_close")
    if not g5:
        flags.append("atr_fallback_tp")
    if not sl_beyond:
        flags.append("stop_inside_zone")
    if latency_h > 24.0:
        flags.append("sweep_to_fill_gt_24h")
    if risk_atr is not None and risk_atr > 3.0:
        flags.append("risk_gt_3atr")

    return {
        "id": row["_fid"],
        "book": row["trigger"],
        "segment": row["segment"],
        "hypothesis": row["hypothesis"],
        "direction": row["direction"],
        "poi_id": row["poi_id"],
        "run": row["run"],
        "ticket": row["ticket"],
        "route_id": row.get("route_id") or "",
        "entry_at": row["entry_at"],
        "exit_at": row["exit_at"],
        "entry_price": entry,
        "zone_low": lo,
        "zone_high": hi,
        "original_sl": sl,
        "sl_beyond_zone": sl_beyond,
        "detection_tf": pm["detection_tf"],
        "tier": pm["tier"],
        "confirmation_tf": pm["confirmation_tf"],
        "label_at_confirm": pm["label_at_confirm"],
        "armed_ts": pm["armed_ts"],
        "sweep_ts": pm["sweep_ts"],
        "completion_ts": pm["completion_ts"],
        "window_end_ts": pm["window_end_ts"],
        "window_end_bar_ts": (window_end_bar.isoformat()
                              if window_end_bar is not None else ""),
        "window_end_source": window_end_source,
        "tp_source": row["tp_source"],
        "entry_anchor": row.get("entry_anchor") or "",
        "model_tags": row.get("model_tags") or "",
        "g1_poi_before_sweep": g1,
        "g2_confirm_in_window": g2,
        "g3_confirm_tf_locked": g3,
        "g4_entry_in_zone": g4,
        "g5_structural_tp": g5,
        "q4_entry_not_at_chase_edge": q4,
        "q5_fill_within_0p25atr_of_confirm": q5,
        "checks_passed": score,
        "agent_draft_score": draft,
        "flags": ";".join(flags),
        "confirm_after_window": confirm_after_window,
        "confirm_after_stamp": confirm_after_stamp,
        "retrace_at_confirm_atr": (round(retrace, 3)
                                   if retrace is not None else ""),
        "no_pullback_0p5atr": no_pullback,
        "sweep_to_fill_h": round(latency_h, 2),
        "risk_atr": round(risk_atr, 3) if risk_atr is not None else "",
        "zone_pct_of_height": round(zone_pct, 1) if zone_pct is not None else "",
    }


def select_sample(rows: list[dict], per_book: int = SAMPLE_PER_BOOK,
                  seed: int = 20261123) -> list[dict]:
    """Stratified, deterministic, anomaly-aware selection.

    1. Must-include: for each book, the earliest row of each anomaly class
       (order inversion, confirmation after window, entry outside zone,
       no pullback >= 0.5 ATR) — review should see the mismatches.
    2. Remaining slots: round-robin over (month, direction) strata in month
       order, picking the median-dated untouched candidate per stratum, so
       every month and both directions appear before any stratum repeats.
    3. If slots remain, evenly spaced picks over the ranked list (seedless;
       `seed` only breaks ties in the median pick).
    """
    rng = random.Random(seed)
    out: list[dict] = []
    for book in BOOKS:
        pool = [r for r in rows if r["book"] == book]
        chosen: list[dict] = []

        def add(row: dict) -> None:
            if row not in chosen:
                chosen.append(row)

        strata: dict = defaultdict(list)
        for row in pool:
            strata[(row["segment"], row["direction"])].append(row)

        # Pass A (first, so month coverage is never traded away): one row per
        # month, alternating the currently thinner direction.
        dir_count = Counter(r["direction"] for r in chosen)
        for seg in SEGMENTS:
            if len(chosen) >= per_book:
                break
            buckets = [(d, [r for r in strata.get((seg, d), [])
                            if r not in chosen]) for d in ("long", "short")]
            buckets = [(d, b) for d, b in buckets if b]
            if not buckets:
                continue
            buckets.sort(key=lambda item: (dir_count[item[0]], item[0]))
            direction, bucket = buckets[0]
            bucket.sort(key=lambda r: r["entry_at"])
            add(bucket[len(bucket) // 2])
            dir_count[direction] += 1

        anomaly_classes = [
            ("order_inversion", lambda r: not r["g1_poi_before_sweep"]),
            ("confirm_after_window", lambda r: r["confirm_after_window"]),
            ("confirm_after_stamp", lambda r: r["confirm_after_stamp"]),
            ("entry_outside_zone", lambda r: not r["g4_entry_in_zone"]),
            ("entry_at_chase_edge",
             lambda r: not r["q4_entry_not_at_chase_edge"]),
            ("no_pullback", lambda r: r["no_pullback_0p5atr"]),
            ("risk_gt_3atr",
             lambda r: r["risk_atr"] not in ("", None)
             and float(r["risk_atr"]) > 3.0),
        ]
        for _name, pred in anomaly_classes:
            if len(chosen) >= per_book:
                break
            hits = [r for r in pool if pred(r)]
            if hits:
                add(hits[0])
                if len(hits) > 1 and len(chosen) < per_book:
                    add(hits[len(hits) // 2])

        order = [(s, d) for s in SEGMENTS for d in ("long", "short")]
        progressed = True
        while len(chosen) < per_book and progressed:
            progressed = False
            for key in order:
                if len(chosen) >= per_book:
                    break
                bucket = [r for r in strata.get(key, []) if r not in chosen]
                if not bucket:
                    continue
                bucket.sort(key=lambda r: r["entry_at"])
                pick = bucket[len(bucket) // 2]
                if len(bucket) > 1:
                    pick = rng.choice(bucket) if len(chosen) % 2 else pick
                add(pick)
                progressed = True
        # Top up (rounded strata) with even spacing over the ranked pool.
        if len(chosen) < per_book:
            rest = [r for r in pool if r not in chosen]
            step = max(1, len(rest) // max(1, per_book - len(chosen)))
            for row in rest[::step]:
                if len(chosen) >= per_book:
                    break
                add(row)
        out.extend(chosen[:per_book])
    return out


def render(row: dict, m1, out_dir: Path, *, pad_hours: int = 12) -> dict:
    """Chart + sidecar in the trade_inspector visual language, plus the
    sweep / confirmation markers the flowchart review needs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    from matplotlib.patches import Rectangle

    pm = row["_stamp"]
    sweep, confirm = _dt(pm["sweep_ts"]), _dt(pm["completion_ts"])
    fill = _dt(row["entry_at"])
    exit_at = _dt(row["exit_at"])
    start = min(sweep, _dt(pm["armed_ts"])) - timedelta(hours=pad_hours)
    end = max(exit_at, confirm) + timedelta(hours=pad_hours)
    # Canonical parquet timestamps are naive UTC; trade stamps are aware.
    start, end = start.replace(tzinfo=None), end.replace(tzinfo=None)

    frame = m1.loc[(m1["timestamp"] >= pd.Timestamp(start)) &
                   (m1["timestamp"] <= pd.Timestamp(end))]
    if frame.empty:
        return {"id": row["id"], "chart": None, "note": "no M1 bars in window"}
    m5 = (frame.set_index("timestamp")
          .resample("5min")
          .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
          .dropna())
    ts = list(m5.index)
    opens = list(m5["open"])
    highs = list(m5["high"])
    lows = list(m5["low"])
    closes = list(m5["close"])
    n = len(ts)

    def x_of(stamp: datetime) -> int:
        key = pd.Timestamp(stamp.replace(tzinfo=None))
        return min(n - 1, max(0, bisect_left(ts, key)))

    fig, (ax, panel) = plt.subplots(
        2, 1, figsize=(13, 8.5), gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle(f"{row['id']}   {row['book']} {row['direction']}  "
                 f"{row['segment']}/{row['hypothesis']}  "
                 f"tier {pm['tier']}->{pm['confirmation_tf']}  "
                 f"draft {row['agent_draft_score']}", fontsize=11,
                 fontweight="bold")
    for i in range(n):
        color = "g" if closes[i] >= opens[i] else "r"
        ax.plot([i, i], [lows[i], highs[i]], color=color, linewidth=0.7)
        top, bottom = max(opens[i], closes[i]), min(opens[i], closes[i])
        ax.add_patch(Rectangle((i - 0.3, bottom), 0.6,
                               max(top - bottom, 1e-9),
                               facecolor=color, edgecolor=color))

    zone_lo, zone_hi = float(row["zone_low"]), float(row["zone_high"])
    ax.axhspan(zone_lo, zone_hi, color="purple", alpha=0.12,
               label="POI zone")
    ax.axhline(float(row["entry_price"]), color="blue", linewidth=1.2,
               label=f"entry {row['entry_price']}")
    ax.axhline(float(row["original_sl"]), color="red", linestyle="--",
               linewidth=1.1, label=f"SL {row['original_sl']}")
    tp = float(row["tp"]) if row.get("tp") else None
    if tp:
        ax.axhline(tp, color="green", linestyle=":", linewidth=1.0,
                   label=f"TP {tp} ({row['tp_source']})")

    ax.axvline(x_of(_dt(pm["armed_ts"])), color="grey", linestyle="-.",
               linewidth=1.0, label="POI armed")
    ax.axvline(x_of(sweep), color="orange", linestyle="--", linewidth=1.1,
               label="sweep")
    ax.axvline(x_of(confirm), color="teal", linestyle="--", linewidth=1.1,
               label="LTF confirm")
    ax.axvline(x_of(_dt(pm["window_end_ts"])), color="black",
               linestyle=":", linewidth=0.9, label="window end (stamp)")
    if row.get("window_end_bar_ts"):
        ax.axvline(x_of(_dt(row["window_end_bar_ts"])), color="black",
                   linestyle="-.", linewidth=0.9,
                   label="window end (bar count)")
    ax.plot(x_of(fill), float(row["entry_price"]), marker="^", markersize=11,
            color="blue", label="fill")
    ax.plot(x_of(exit_at), float(row["exit_price"]), marker="x", markersize=10,
            color="black", markeredgewidth=2, label="exit")

    lo_y = min(lows), max(highs)
    for level in [zone_lo, zone_hi, float(row["entry_price"]),
                  float(row["original_sl"])] + ([tp] if tp else []):
        lo_y = (min(lo_y[0], level), max(lo_y[1], level))
    pad_y = max((lo_y[1] - lo_y[0]) * 0.04, 1e-9)
    ax.set_ylim(lo_y[0] - pad_y, lo_y[1] + pad_y)
    ax.set_xlim(-1, n)
    ax.set_ylabel("price")
    ax.legend(loc="upper left", fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3)

    gate_keys = (("g1_poi_before_sweep", "G1 POI<sweep"),
                 ("g2_confirm_in_window", "G2 confirm<=win"),
                 ("g3_confirm_tf_locked", "G3 tf locked"),
                 ("g4_entry_in_zone", "G4 in zone"),
                 ("q4_entry_not_at_chase_edge", "Q4 no chase edge"),
                 ("q5_fill_within_0p25atr_of_confirm", "Q5 at confirm"),
                 ("g5_structural_tp", "G5 struct TP"))
    gate_str = "  ".join(
        f"{label}={'Y' if row[key] else 'n'}" for key, label in gate_keys)
    lines = [
        f"book {row['book']}  trigger {row['trigger']}  "
        f"{row['direction']}  models {row['model_tags'] or '-'}",
        f"poi {row['poi_id']}  route {row['route_id'] or '-'}  "
        f"anchors {row['entry_anchor'] or 'absent (B carries fib band)'}",
        f"tier {pm['tier']} det {pm['detection_tf']} "
        f"confirm {pm['confirmation_tf']}  label {pm['label_at_confirm']}",
        f"armed {pm['armed_ts']}  sweep {pm['sweep_ts']}",
        f"confirm {pm['completion_ts']}  window end stamp {pm['window_end_ts']} "
        f"({row['window_end_source']}: {row['window_end_bar_ts'] or 'open'})",
        f"fill {row['entry_at']}  exit {row['exit_at']}  "
        f"({row['close_kind']})  hold {row['bars_held']} bars",
        f"entry {row['entry_price']}  zone [{zone_lo}, {zone_hi}]  "
        f"pos {row['zone_pct_of_height']}%  SL {row['original_sl']} "
        f"({row['risk_atr']} ATR)  TP {tp} ({row['tp_source']})",
        f"{gate_str}  -> {row['checks_passed']}/7 {row['agent_draft_score']}",
        f"sweep->fill {row['sweep_to_fill_h']}h   "
        f"retrace {row['retrace_at_confirm_atr']} ATR   "
        f"flags: {row['flags'] or 'none'}",
        "ARCHITECT SCORE (STRONG/PARTIAL/WEAK/UNCLEAR) + NOTE:",
    ]
    panel.axis("off")
    panel.text(0.005, 0.97, "\n".join(lines), transform=panel.transAxes,
               fontsize=8.5, family="monospace", va="top",
               bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.35))

    charts = out_dir / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    png = charts / f"{row['id']}.png"
    fig.savefig(png, dpi=100)
    plt.close(fig)

    sidecar = {
        "id": row["id"], "book": row["book"], "run": row["run"],
        "trigger": row["trigger"], "direction": row["direction"],
        "poi_id": row["poi_id"], "route_id": row["route_id"],
        "entry_at": row["entry_at"], "exit_at": row["exit_at"],
        "entry_price": row["entry_price"],
        "zone": [zone_lo, zone_hi], "original_sl": row["original_sl"],
        "tp": tp, "tp_source": row["tp_source"],
        "entry_anchor": row["entry_anchor"],
        "model_tags": row["model_tags"],
        "tier": pm["tier"], "detection_tf": pm["detection_tf"],
        "confirmation_tf": pm["confirmation_tf"],
        "label_at_confirm": pm["label_at_confirm"],
        "sequence": {"armed": pm["armed_ts"], "sweep": pm["sweep_ts"],
                     "confirm": pm["completion_ts"],
                     "window_end_bar": row["window_end_bar_ts"],
                     "window_end_stamp": pm["window_end_ts"],
                     "window_end_source": row["window_end_source"]},
        "checks": {label: bool(row[key]) for key, label in gate_keys},
        "checks_passed": row["checks_passed"],
        "agent_draft_score": row["agent_draft_score"],
        "flags": row["flags"].split(";") if row["flags"] else [],
        "descriptive": {
            "sl_beyond_zone": row["sl_beyond_zone"],
            "retrace_at_confirm_atr": row["retrace_at_confirm_atr"],
            "no_pullback_0p5atr": row["no_pullback_0p5atr"],
            "sweep_to_fill_h": row["sweep_to_fill_h"],
            "risk_atr": row["risk_atr"],
            "zone_pct_of_height": row["zone_pct_of_height"],
        },
        "architect_score": "",
        "architect_note": "",
        "chart": str(png),
    }
    (charts / f"{row['id']}.json").write_text(
        json.dumps(sidecar, indent=2), encoding="utf-8")
    return sidecar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--per-book", type=int, default=SAMPLE_PER_BOOK)
    ap.add_argument("--no-charts", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    if not out.is_absolute():
        out = REPO / out
    out.mkdir(parents=True, exist_ok=True)

    universe = load_universe()
    counts = Counter(r["trigger"] for r in universe)
    if counts["F"] != 351 or counts["B"] != 241:
        raise SystemExit(f"F/B union mismatch: {dict(counts)}")
    features = [feature_row(r) for r in universe]

    sample_features = select_sample(features, args.per_book)
    sample_ids = {r["id"] for r in sample_features}
    by_id = {r["_fid"]: r for r in universe}

    cols = list(features[0].keys()) + [
        "architect_score", "architect_failure_mode", "architect_note"]
    def write_csv(path: Path, rows: list[dict], sample: bool) -> None:
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=cols)
            writer.writeheader()
            for row in rows:
                payload = dict(row)
                if sample:
                    payload.update({"architect_score": "",
                                    "architect_failure_mode": "",
                                    "architect_note": ""})
                writer.writerow(payload)

    write_csv(out / "universe_features.csv", features, sample=False)
    write_csv(out / "sample_index.csv", sample_features, sample=True)

    # Descriptive distributions over the full union (not the sample).
    def dist(key: str, book: str | None = None) -> dict:
        c = Counter(str(r[key]) for r in features
                    if book is None or r["book"] == book)
        return dict(sorted(c.items()))

    failure_modes = {}
    for book in BOOKS:
        rows = [r for r in features if r["book"] == book]
        failure_modes[book] = {
            "n": len(rows),
            "order_inversion": sum(1 for r in rows if not r["g1_poi_before_sweep"]),
            "confirm_after_window": sum(1 for r in rows if r["confirm_after_window"]),
            "confirm_after_stamp_window": sum(
                1 for r in rows if r["confirm_after_stamp"]),
            "entry_outside_zone": sum(1 for r in rows if not r["g4_entry_in_zone"]),
            "atr_fallback_tp": sum(1 for r in rows if not r["g5_structural_tp"]),
            "stop_inside_zone": sum(1 for r in rows if not r["sl_beyond_zone"]),
            "no_pullback_0p5atr": sum(1 for r in rows if r["no_pullback_0p5atr"]),
            "entry_at_chase_edge": sum(
                1 for r in rows if not r["q4_entry_not_at_chase_edge"]),
            "fill_beyond_confirm_0p25atr": sum(
                1 for r in rows if not r["q5_fill_within_0p25atr_of_confirm"]),
            "risk_gt_3atr": sum(
                1 for r in rows if r["risk_atr"] not in ("", None)
                and float(r["risk_atr"]) > 3.0),
            "sweep_to_fill_gt_24h": sum(
                1 for r in rows if float(r["sweep_to_fill_h"]) > 24.0),
        }

    summary = {
        "study": "entry_quality_f_b",
        "diagnostic_only": True,
        "not_performance": (
            "mechanical flowchart checklist; no expectancy, PF or edge claim"),
        "universe": {b: counts[b] for b in BOOKS},
        "universe_total": sum(counts.values()),
        "sample": {b: sum(1 for r in sample_features if r["book"] == b)
                   for b in BOOKS},
        "selection_rule": (
            "per book: earliest+median row of each anomaly class (order "
            "inversion, confirm after window, confirm after the stamp's "
            "nominal projection, entry outside zone, no pullback "
            ">=0.5 ATR), then round-robin over (month, direction) strata in "
            "month order picking the median-dated untouched row, then even "
            "spacing top-up; deterministic (seed 20261123)"),
        "checks": {
            "G1": "POI armed before interaction (armed_ts<=sweep_ts)",
            "G2": ("sweep<confirm<=engine window end (close of the detection "
                   "bar at sweep_index+MENU_EXPIRY_BARS; the stamp's "
                   "window_end_ts is a nominal projection and is not gated)"),
            "G3": "confirmation TF is the locked child tier",
            "G4": "entry limit inside POI zone",
            "Q4": "entry not pinned at the zone's chase edge (last 8%)",
            "Q5": "fill within 0.25 ATR of the confirmation close",
            "G5": "structural TP (not ATR fallback)"},
        "draft_rule": (
            "STRONG 7/7, PARTIAL 6/7, WEAK <=5/7 — agent-draft heuristic; "
            "Q4/Q5 are entry-location proxies for human override, not locked "
            "rules and not a performance statement"),
        "draft_scores": dist("agent_draft_score"),
        "draft_scores_by_book": {b: dist("agent_draft_score", b)
                                 for b in BOOKS},
        "failure_modes": failure_modes,
        "tier_mix": dist("tier"),
        "confirm_mix": dist("confirmation_tf"),
        "direction_mix": dist("direction"),
        "sample_strata": {
            b: dict(Counter(f"{r['segment']}/{r['direction']}"
                            for r in sample_features if r["book"] == b))
            for b in BOOKS},
    }
    rendered = []
    if not args.no_charts:
        import pandas as pd
        m1 = pd.read_parquet(PARQUET, columns=["timestamp", "open", "high",
                                               "low", "close"])
        for feature in sample_features:
            row = dict(by_id[feature["id"]])
            row.update(feature)          # gates/flags + _stamp for the panel
            rendered.append(render(row, m1, out))
        summary["charts"] = len([r for r in rendered if r.get("chart")])

    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"[f/b] universe {summary['universe']} total {summary['universe_total']}")
    print(f"[f/b] sample {summary['sample']} charts {summary.get('charts', 0)}")
    print(f"[f/b] draft {summary['draft_scores_by_book']}")
    print(f"[f/b] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
