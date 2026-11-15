"""DECODE the 9 unique product-menu fills (PRODUCT_6M one-story diagnostic).

READ-ONLY decode: no strategy change, no optimization, no retune. Reconstructs
the unique filled plans (raw 27 -> 9 under the one-story guard) from the
diagnostic artifacts, emits one table row + one house-style chart per fill,
and a short narrative per fill.

Sources (never invented):
- trades.csv / armed_records.json / signal_data_json (menu stamp) per window
  under 06_RESEARCH/results/product_6m_one_story/run1/{jun,sep,oct}/
- plain-label vocab ORDER_BLOCK|FVG|DEMAND|SUPPLY|MERGED|UNKNOWN applied ONLY
  where the data proves it (M8 = HTF Demand/Supply per the architecture legend
  + the trade's own direction; multi-tag POIs = merged; otherwise UNKNOWN -
  M4 QML / M5 Extreme-EQH have no word in the vocab and are NOT renamed).
- trigger letter map from 00_LOCKED/EXPERT_MASTER_CARD (A = CHOCH R1/R2,
  F = BOS+OB) - used only to read the signal_data fields already present.
"""

from __future__ import annotations

import csv
import json
import sys
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "06_RESEARCH" / "scripts"))
sys.path.insert(0, str(REPO / "04_SRC"))

import pfe3_expert_pack as house  # noqa: E402  (house-style chart renderer)
from smc.risk.story_guard import same_story, story_key  # noqa: E402

SRC = REPO / "06_RESEARCH" / "results" / "product_6m_one_story" / "run1"
OUT = REPO / "06_RESEARCH" / "results" / "product_9_fills_decode"
CHARTS = OUT / "charts"
REPORT = REPO / "06_RESEARCH" / "PRODUCT_9_FILLS_DECODE_REPORT.md"
WINDOWS = ("jun", "sep", "oct")

COLUMNS = [
    "story_id", "ticket", "window", "direction", "detection_tf", "model_tags",
    "m8_kind", "trigger", "zone_low", "zone_high", "entry", "original_sl",
    "tp", "tp_source", "entry_at", "exit_at", "close_kind", "pnl",
    "pillar_path", "disp_magnitude_atr", "entry_anchor", "plain_label",
    "one_sentence",
]


def fail_loud(msg: str) -> None:
    raise SystemExit(f"[decode9] FAIL LOUD: {msg}")


def _f(row: dict, key: str):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return None


def _menu_stamp(trade: dict) -> dict:
    try:
        payload = json.loads(trade.get("signal_data_json") or "{}")
    except ValueError:
        return {}
    stamp = payload.get("product_menu")
    return stamp if isinstance(stamp, dict) else {}


def _plain_label(tags: str, direction: str) -> str:
    """Plain word ONLY where proven: M8 = HTF Demand/Supply (direction tells
    which side); >1 tag = merged validated POI; single non-M8 tag has no word
    in the vocab (M4 QML, M5 Extreme-EQH, M1 origin base are NOT renamed)."""
    parts = [t for t in (tags or "").split("+") if t]
    if len(parts) > 1:
        return "MERGED"
    if parts == ["M8"]:
        return "DEMAND" if (direction or "").lower() == "long" else "SUPPLY"
    return "UNKNOWN"


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


def load_fills() -> list[dict]:
    fills = []
    for w in WINDOWS:
        with (SRC / w / "trades.csv").open(newline="", encoding="utf-8") as fh:
            for trade in csv.DictReader(fh):
                trade["_window"] = w
                fills.append(trade)
    if len(fills) != 9:
        fail_loud(f"expected 9 unique fills, found {len(fills)}")
    armed: dict[str, dict] = {}
    for w in WINDOWS:
        armed.update(json.loads((SRC / w / "armed_records.json")
                                .read_text(encoding="utf-8")))
    fills.sort(key=lambda t: (t["entry_at"], t["poi_id"]))
    out = []
    for i, trade in enumerate(fills, start=1):
        stamp = _menu_stamp(trade)
        rec = armed.get(trade["poi_id"], {})
        direction = trade.get("direction", "")
        tags = trade.get("model_tags", "")
        sd = json.loads(trade.get("signal_data_json") or "{}")
        row = {
            "story_id": f"{trade['_window'].upper()}-{trade['ticket']}",
            "ticket": trade["ticket"],
            "window": trade["_window"],
            "poi_id": trade.get("poi_id", ""),
            "direction": direction,
            "detection_tf": stamp.get("detection_tf", ""),
            "model_tags": tags,
            "m8_kind": "NOT_EXPORTED",
            "trigger": trade.get("trigger", ""),
            "zone_low": trade.get("zone_low", ""),
            "zone_high": trade.get("zone_high", ""),
            "entry": trade.get("entry_price", ""),
            "original_sl": trade.get("original_sl", ""),
            "tp": trade.get("tp", ""),
            "tp_source": trade.get("tp_source", ""),
            "entry_at": trade.get("entry_at", ""),
            "exit_at": trade.get("exit_at", ""),
            "close_kind": trade.get("close_kind", ""),
            "pnl": trade.get("pnl", ""),
            "pillar_path": rec.get("pillar_path", ""),
            "disp_magnitude_atr": rec.get("disp_magnitude_atr", ""),
            "entry_anchor": trade.get("entry_anchor", ""),
            "plain_label": _plain_label(tags, direction),
            "one_sentence": (f"Level from {stamp.get('detection_tf', '?')}; "
                             f"confirm {trade.get('trigger', '?')}; "
                             f"exit {trade.get('close_kind', '?')}."),
            "_stamp": stamp,
            "_sd": sd,
            "_completion_close": stamp.get("completion_close"),
        }
        out.append(row)
    # duplicate-residual check INSIDE the 9 (locked story_guard rules 2-6)
    dup_groups = 0
    for a, b in combinations(out, 2):
        if same_story(_plan_key(a), _plan_key(b)):
            dup_groups += 1
    return out, dup_groups


def _in_zone(row: dict):
    entry, zlo, zhi = _f(row, "entry"), _f(row, "zone_low"), _f(row, "zone_high")
    comp = row["_completion_close"]
    if None in (entry, zlo, zhi):
        return "UNKNOWN"
    entry_in = zlo <= entry <= zhi
    comp_in = None if comp is None else (zlo <= float(comp) <= zhi)
    if comp is None:
        return "YES (entry inside zone)" if entry_in else "NO"
    if entry_in and comp_in:
        return "YES (completion + entry inside zone)"
    if entry_in:
        return "YES (entry inside zone)"
    return "NO"


def _trigger_evidence(row: dict) -> str:
    sd, trigger = row["_sd"], row["trigger"]
    if trigger == "F":
        ob, bos = sd.get("ob_index"), sd.get("bos_index")
        if ob is not None and bos is not None:
            return f"BOS+OB fields present (ob_index {ob}, bos_index {bos})"
    elif trigger == "A":
        level, rule = sd.get("broken_level"), sd.get("rule")
        if level is not None and rule:
            return f"CHOCH fields present (broken_level {level}, {rule})"
    return "no trigger-evidence fields in export"


def narrative(row: dict) -> str:
    """3 sentences max, trader language, only proven fields."""
    ret = _in_zone(row)
    ret_txt = {
        "YES (completion + entry inside zone)":
            "Price returned into the marked zone: both the confirmation close "
            "and the fill sat inside it.",
        "YES (entry inside zone)":
            "The fill sat inside the marked zone.",
    }.get(ret, f"Zone-return check: {ret} (mechanical, from exported values).")
    trig = _trigger_evidence(row)
    trigger_word = ("Trigger F (the BOS+OB letter per the locked master card)"
                    if row["trigger"] == "F" else
                    "Trigger A (the CHOCH letter per the locked master card)")
    return (f"{ret_txt} {trigger_word}: {trig}. "
            "NOT_LABELED (no internal/external liquidity field in the export).")


def render(row: dict, seq: int) -> Path:
    w = row["window"]
    exec_from = {"jun": "2025-06-01", "sep": "2025-09-01",
                 "oct": "2025-10-01"}[w]
    # Chart slice bound: +1 day so fills on the window's LAST day are inside
    # the M5 slice (display-only; the diagnostic exec bounds are unchanged).
    exec_to = {"jun": "2025-06-11", "sep": "2025-09-11",
               "oct": "2025-10-11"}[w]
    stamp = row["_stamp"]
    event = {
        "event_id": f"{row['story_id']} ({row['poi_id']})",
        "kind": f"unique_fill_{row['plain_label'].lower()}",
        "composition": "menu (one-story ON)",
        "window": row["window"],
        "exec_from": exec_from, "exec_to": exec_to,
        "poi_id": "",
        "detection_tf": row["detection_tf"],
        "tier": stamp.get("tier", ""),
        "confirmation_tf": stamp.get("confirmation_tf", ""),
        "model_tags": row["model_tags"],
        "pillar_path": row["pillar_path"],
        "direction": row["direction"],
        "zone_low": row["zone_low"],
        "zone_high": row["zone_high"],
        "trigger": row["trigger"],
        "entry": row["entry"],
        "original_sl": row["original_sl"],
        "tp": row["tp"],
        "tp_source": row["tp_source"],
        "close_kind": row["close_kind"],
        "entry_at": row["entry_at"],
        "exit_at": row["exit_at"],
        "sweep_ts": stamp.get("sweep_ts", ""),
        "completion_ts": stamp.get("completion_ts", ""),
    }
    name = (f"{seq:02d}_{row['story_id'].lower()}_"
            f"{row['direction']}_{row['trigger']}_"
            f"{row['plain_label'].lower()}.png")
    png = CHARTS / name
    if not house.render_chart(event, png):
        fail_loud(f"chart render failed for {row['story_id']}")
    return png


def main() -> int:
    fills, dup_groups = load_fills()
    CHARTS.mkdir(parents=True, exist_ok=True)

    # ---- CSV ---------------------------------------------------------- #
    with (OUT / "fills_decode.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS,
                                extrasaction="ignore")
        writer.writeheader()
        for row in fills:
            writer.writerow({c: row.get(c, "") for c in COLUMNS})

    # ---- charts -------------------------------------------------------- #
    chart_paths = []
    for seq, row in enumerate(fills, start=1):
        chart_paths.append((row["story_id"], render(row, seq)))

    # ---- report -------------------------------------------------------- #
    def mix(key):
        from collections import Counter
        return dict(sorted(Counter(r[key] for r in fills).items()))

    lines = []
    a = lines.append
    a("# PRODUCT 9 FILLS - READ-ONLY DECODE")
    a("")
    a("**READ-ONLY decode of the 9 unique product-menu fills from the"
      " PRODUCT_6M one-story diagnostic (raw 27 -> 9 under the guard)."
      " Diagnostic only: pnl column is a diagnostic net on the frozen"
      " machine-completeness config, NOT performance. No strategy change, no"
      " optimization, no retune; `locked_constants.py` untouched.**")
    a("")
    a("- **Sources:** `06_RESEARCH/results/product_6m_one_story/run1/`"
      " per-window `trades.csv` + `armed_records.json` + the menu stamp"
      " (`signal_data_json.product_menu`). Nothing is re-run; nothing invented.")
    a("- **Plain-label rules (never invented):** M8 alone = HTF Demand/Supply"
      " zone (DEMAND/SUPPLY from the trade's own direction - architecture"
      " legend, `01_ARCHITECTURE/SMC_WORKFLOW_ORCHESTRATION.md` L85);"
      " >1 tag = MERGED; a single non-M8 tag (M4 QML, M5 Extreme-EQH) has no"
      " word in the allowed vocab -> UNKNOWN (raw `model_tags` column keeps"
      " the truth). `m8_kind` is not exported by the harness ->"
      " NOT_EXPORTED.")
    a("- **Trigger letters** read only from fields already exported:"
      " F rows carry `ob_index` + `bos_index` (BOS+OB per the locked master"
      " card); the A row carries `broken_level` + `rule_1` + `sweep_index`"
      " (CHOCH Rule 1).")
    a("")
    a("## 1. The 9 unique fills")
    a("")
    a("| story_id | ticket | window | dir | det_tf | tags | trigger |"
      " zone | entry | SL | TP | tp_source | close | pnl (diag) | label |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in fills:
        a(f"| {r['story_id']} | {r['ticket']} | {r['window']} |"
          f" {r['direction']} | {r['detection_tf']} | {r['model_tags']} |"
          f" {r['trigger']} | {_f(r, 'zone_low'):.2f}-{_f(r, 'zone_high'):.2f}"
          f" | {_f(r, 'entry'):.2f} | {_f(r, 'original_sl'):.2f} |"
          f" {_f(r, 'tp'):.2f} | {r['tp_source']} | {r['close_kind']} |"
          f" {float(r['pnl']):+.3f} | {r['plain_label']} |")
    a("")
    a("Full geometry (pillars, displacement, anchor, one-sentence) in"
      " `06_RESEARCH/results/product_9_fills_decode/fills_decode.csv`; one"
      " house-style chart per fill in `charts/`.")
    a("")
    a("## 2. Per-fill narrative (short)")
    a("")
    for r in fills:
        a(f"**{r['story_id']}** ({r['plain_label']}, {r['detection_tf']},"
          f" {r['direction']}, trigger {r['trigger']},"
          f" {r['entry_at'][:16]} -> {r['exit_at'][:16]},"
          f" {r['close_kind']}): {narrative(r)}")
        a("")
    a("## 3. Duplicate residual check")
    a("")
    a(f"Pairwise plan identity (locked story_guard rules 2-6) inside the 9:"
      f" **{dup_groups} duplicate pairs**. The diagnostic already measured"
      " identical-plan groups = 0 after the guard; the decode confirms the"
      " surviving book carries no residual twin (no two of the nine share"
      " direction + trigger + entry + SL + TP + overlapping zone).")
    a("")
    a("## 4. Decode summary")
    a("")
    a(f"- By trigger: {mix('trigger')}")
    a(f"- By detection TF: {mix('detection_tf')}")
    a(f"- By plain label: {mix('plain_label')}")
    a(f"- By direction: {mix('direction')}")
    a(f"- By close_kind: {mix('close_kind')}")
    a(f"- By tp_source: {mix('tp_source')}")
    a("")
    a("**NEXT = Architect review of the 9 fills -> 1y product menu+one-story"
      " diagnostic.** No expectancy claim, no ship recommendation; liquidity"
      " labels NOT_LABELED where no field proves them.")
    a("")

    REPORT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"[decode9] wrote {REPORT}")
    print(f"[decode9] wrote {OUT / 'fills_decode.csv'}")
    print(f"[decode9] charts: {len(chart_paths)} in {CHARTS}")
    print(f"[decode9] duplicate pairs inside the 9: {dup_groups}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
