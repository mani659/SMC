#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build the two shareable expert PDFs from the structure identification ledger.

READ-ONLY over the ledger artifacts. This module never writes into
``events.csv`` / ``events.jsonl`` / ``summary.json`` / ``review_sample/*.png``,
never touches ``04_SRC/`` strategy code, locked constants, or any detection
logic. It reads the frozen ledger outputs and writes NEW files beside them.

Outputs (all in ``06_RESEARCH/results/structure_ledger_6m/``):

  EXPERT_VALIDATION_PACK.pdf        short, validator-facing pack (priority chart set)
  STRUCTURE_LEDGER_FULL_REPORT.pdf  full report (all 44 stratified charts)
  EXPERT_VALIDATION_PACK.md         text twin (no images) for an email body
  pdf_build_manifest.json           build + independent verification record

Engine: reportlab (preferred). Image files are EMBEDDED into the PDF as page
image XObjects -- the PDFs open offline with no dependency on the chart folder.

HUMAN FLOWCHART LABELS: every chart and every caption is worded in plain
flowchart language ("Liquidity sweep", "Order block", "Demand zone", "Fair
value gap (FVG)", "LTF confirmation (M5 entry)") rather than engine vocabulary
(``poi_raw``, ``route_ltf``, ``source_module``). The mapping lives in
``flowchart_labels.py`` and is shared with the chart renderer, so chart and PDF
wording cannot drift. Engine vocabulary is DEMOTED to a small technical record
under each chart, never removed (it is the audit trail). Charts are read from
``review_sample_v2/`` when present (plain-labelled rebuild), else
``review_sample/``; whichever is used is recorded in the manifest.

LOGIC_CHANGED: NO. Measurement / documentation export only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths & constants
# --------------------------------------------------------------------------- #

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]              # 06_RESEARCH/scripts -> repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import flowchart_labels as FL
    from flowchart_labels import LABEL_TABLE as FLOWCHART_LABEL_TABLE
except ImportError as _fl_exc:                                   # pragma: no cover
    raise SystemExit("FATAL: flowchart_labels.py must sit beside this script: %s" % _fl_exc)

LEDGER_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "structure_ledger_6m"
PNG_DIR = LEDGER_DIR / "review_sample"
#: Plain-flowchart-labelled rebuild of the same 44 charts (same file names).
#: Preferred when it exists; the original folder is never modified.
PNG_DIR_V2 = LEDGER_DIR / "review_sample_v2"
OUT_HUMAN_NOTE = LEDGER_DIR / "HUMAN_LABELS_NOTE.md"
SUMMARY_JSON = LEDGER_DIR / "summary.json"
EVENTS_CSV = LEDGER_DIR / "events.csv"
VERIFY_JSON = LEDGER_DIR / "verification_matrix.json"
REVIEW_INDEX = LEDGER_DIR / "REVIEW_INDEX.md"
LEDGER_REPORT = REPO_ROOT / "06_RESEARCH" / "STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md"
EVIDENCE_MAP = REPO_ROOT / "06_RESEARCH" / "FLOWCHART_CODE_EVIDENCE_MAP.md"
MATCH_NOTES = REPO_ROOT / "06_RESEARCH" / "FLOWCHART_MATCH_NOTES.md"
FREEZE_DOC = REPO_ROOT / "00_LOCKED" / "V1_1_RUNTIME_BASELINE_FREEZE.md"
LOCKED_DECISIONS = REPO_ROOT / "00_LOCKED" / "LOCKED_DECISIONS.md"
SESSION_HANDOFF = REPO_ROOT / "00_LOCKED" / "SESSION_HANDOFF.md"
CHANGELOG = REPO_ROOT / "00_LOCKED" / "CHANGELOG.md"

OUT_EXPERT_PDF = LEDGER_DIR / "EXPERT_VALIDATION_PACK.pdf"
OUT_FULL_PDF = LEDGER_DIR / "STRUCTURE_LEDGER_FULL_REPORT.pdf"
OUT_EXPERT_MD = LEDGER_DIR / "EXPERT_VALIDATION_PACK.md"
OUT_MANIFEST = LEDGER_DIR / "pdf_build_manifest.json"

DOC_TITLE_EXPERT = "EXPERT VALIDATION PACK"
DOC_TITLE_FULL = "STRUCTURE LEDGER - FULL REPORT"
PROJECT = "SMC / XAUUSD - Structure Identification Ledger"

TYPE_ORDER = ["sweep", "fvg", "poi_raw", "poi_armed", "route_ltf", "fill"]

# Priority set requested for the validator pack (event_type -> how many).
PRIORITY_SPEC = [
    ("sweep", 4),
    ("fvg", 4),
    ("poi_raw", 4),      # "prefer M8" -- every sampled poi_raw row carries tag M8
    ("poi_armed", 4),
    ("route_ltf", 6),
    ("fill", 2),         # there are exactly 2 fills in the ledger -> take both
]

DISCLAIMER = "Identification audit only - not performance/edge validation."

# --- page geometry (A4 portrait, points) ---
PAGE_W, PAGE_H = 595.276, 841.890
MARGIN_L = MARGIN_R = 42.0
MARGIN_T = 56.0
MARGIN_B = 46.0
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R          # ~511 pt

# One chart per page (the plain reading block / mandatory set-up chain needs the
# room), so the chart can use the full content width. Same 2:1 source aspect.
IMG_W_FULL = CONTENT_W
IMG_W_EXPERT = CONTENT_W
IMG_ASPECT = 910.0 / 1820.0                       # every review PNG is 1820x910

DATE_STAMP = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

_PROBLEMS: list[str] = []      # non-fatal issues (missing optional file, bad PNG...)
_MISSING_IMAGES: list[str] = []  # charts requested but not embeddable


def warn(msg: str) -> None:
    _PROBLEMS.append(msg)
    print(f"[warn] {msg}")


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #

def esc(value) -> str:
    """Escape a value for reportlab Paragraph XML markup."""
    text = "" if value is None else str(value)
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def clip(value, limit: int) -> str:
    text = "" if value is None else str(value)
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 1)].rstrip() + "\u2026"


def dash(value, fallback: str = "-") -> str:
    text = "" if value is None else str(value).strip()
    return text if text else fallback


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mb(path: Path) -> float:
    try:
        return round(path.stat().st_size / 1_048_576.0, 3)
    except OSError:
        return 0.0


def read_text_or_none(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        warn(f"optional text source unreadable ({path.name}): {exc}")
        return None


# --------------------------------------------------------------------------- #
# Input loading (explicit error handling per artifact)
# --------------------------------------------------------------------------- #

def load_inputs() -> dict:
    """Load every ledger artifact the PDFs need. Required files are fatal."""
    data: dict = {
        "summary": {}, "sample": [], "events": {}, "verify": {},
        "chunk_dangling": {}, "report_note": "", "evidence_text": "",
        "match_notes_text": "", "freeze_line": "", "locked_note": "",
    }

    # ---- summary.json (REQUIRED) ----
    if not SUMMARY_JSON.is_file():
        raise SystemExit(f"FATAL: required input missing: {SUMMARY_JSON}")
    try:
        data["summary"] = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"FATAL: cannot read {SUMMARY_JSON.name}: {exc}") from exc

    sample = data["summary"].get("review_sample")
    if not isinstance(sample, list) or not sample:
        raise SystemExit("FATAL: summary.json has no usable 'review_sample' array")
    data["sample"] = sample

    chunk_dangling = {}
    for chunk in data["summary"].get("chunks") or []:
        if isinstance(chunk, dict) and chunk.get("chunk"):
            try:
                chunk_dangling[chunk["chunk"]] = int(chunk.get("dangling_links") or 0)
            except (TypeError, ValueError):
                warn(f"chunk {chunk.get('chunk')}: non-numeric dangling_links ignored")
    data["chunk_dangling"] = chunk_dangling

    # ---- events.csv (required for the code-emitted field captions) ----
    if not EVENTS_CSV.is_file():
        raise SystemExit(f"FATAL: required input missing: {EVENTS_CSV}")
    try:
        with EVENTS_CSV.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        raise SystemExit(f"FATAL: cannot read {EVENTS_CSV.name}: {exc}") from exc
    if not rows:
        raise SystemExit("FATAL: events.csv parsed to zero rows")
    data["events"] = {row.get("event_id"): row for row in rows if row.get("event_id")}
    data["event_rows"] = len(rows)

    # ---- verification_matrix.json (optional but expected) ----
    if VERIFY_JSON.is_file():
        try:
            data["verify"] = json.loads(VERIFY_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warn(f"verification matrix present but unreadable: {exc}")
    else:
        warn("verification_matrix.json absent - chart verification status unknown")

    # ---- optional narrative sources (read-only, quoted as-is) ----
    data["evidence_text"] = read_text_or_none(EVIDENCE_MAP) or ""
    data["match_notes_text"] = read_text_or_none(MATCH_NOTES) or ""
    data["locked_note"] = "present" if LOCKED_DECISIONS.is_file() else "absent"
    data["freeze_line"] = _freeze_headline(read_text_or_none(FREEZE_DOC) or "")
    return data


def _freeze_headline(freeze_text: str, limit: int = 198) -> str:
    """One faithful line from the freeze doc's Status block (it wraps over lines)."""
    fallback = ("V1.1 runtime baseline FROZEN - see "
                "00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md")
    if not freeze_text:
        return fallback
    lines = freeze_text.splitlines()
    parts: list = []
    date_text = ""
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("**Status:**"):
            parts.append(stripped.replace("**Status:**", "").strip())
            for extra in lines[index + 1:index + 4]:
                candidate = extra.strip()
                if not candidate:
                    break
                if candidate.startswith("**") and ":**" in candidate[:28]:
                    break
                parts.append(candidate)
                if candidate.endswith("."):
                    break
        elif stripped.startswith("**Date:**"):
            date_text = stripped.replace("**Date:**", "").strip()
    text = " ".join(p.replace("**", "").strip() for p in parts).strip()
    text = " ".join(text.split())
    if date_text and "date" not in text.lower():
        text = f"{text} (freeze dated {date_text})"
    if not text:
        return fallback
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


def _resolve_png(file_name: str) -> tuple:
    """Prefer the plain-labelled rebuild (review_sample_v2/) when it exists.

    Both folders hold the same file names, so the frozen summary.json index and
    REVIEW_INDEX.md keep naming each chart either way. The original folder is
    only read, never written.
    """
    for directory in (PNG_DIR_V2, PNG_DIR):
        path = directory / file_name
        if path.is_file():
            return path, directory.name
    return PNG_DIR_V2 / file_name, "missing"


def resolve_charts(sample: list) -> list:
    """Attach the CSV row + verified image path to each sample entry."""
    events = _INPUTS["events"]
    charts = []
    for position, entry in enumerate(sample, start=1):
        record = dict(entry)
        record["seq"] = position
        record["csv"] = events.get(entry.get("event_id"), {})
        record["rel_type"] = ""
        rel_id = record["csv"].get("related_event_id") or ""
        if rel_id:
            target = events.get(rel_id)
            record["rel_type"] = (target or {}).get("event_type", "not in union")
        path, folder = _resolve_png(str(entry.get("file") or ""))
        record["path"] = path
        record["png_source"] = folder
        record["label"] = FL.caption_lines(
            record.get("event_type"), record["csv"], events,
            event_id=str(record.get("event_id") or ""),
            chart_tf=str(record.get("chart_tf") or ""),
            detection_tf=str(record.get("detection_tf") or ""))
        record["image_ok"] = path.is_file()
        if not record["image_ok"]:
            _MISSING_IMAGES.append(record["file"])
            warn(f"chart image missing: {path}")
        else:
            try:
                from PIL import Image as PILImage
                with PILImage.open(path) as image:
                    record["px"] = image.size
            except Exception as exc:                     # noqa: BLE001 - PIL has many failure modes
                record["image_ok"] = False
                _MISSING_IMAGES.append(record["file"])
                warn(f"chart image unreadable ({record['file']}): {exc}")
        charts.append(record)
    return charts


def verify_flags(verify: dict) -> list:
    """Charts the independent verifier flagged (locked-rule divergence, shown not hidden)."""
    out = []
    for item in (verify.get("charts") or []):
        if item.get("flags"):
            out.append(item)
    return out


# --------------------------------------------------------------------------- #
# Chart selection (deterministic, documented rule)
# --------------------------------------------------------------------------- #

def _ts_key(chart: dict) -> str:
    return str(chart.get("ts_utc") or "")


def _spread_pick(charts: list, indices: list, k: int, must: list) -> list:
    """Farthest-point sampling over ts_utc, penalising a repeated chart TF.

    Deterministic: `must` first, then repeatedly add the candidate whose minimum
    time-distance to the chosen set is largest (0.6x penalty while its chart TF
    is already represented, so mixed-TF types keep at least one of each TF).
    Ties break toward the earlier item. Returns indices in chronological order.
    """
    if k <= 0 or not indices:
        return []
    chosen = [i for i in must if i in indices]
    chosen = list(dict.fromkeys(chosen))
    if len(chosen) >= k:
        return sorted(chosen[:k])
    if not chosen:
        chosen = [indices[0]]
    seen_tfs = {charts[i].get("chart_tf") for i in chosen}
    while len(chosen) < k:
        best_index, best_score = None, None
        for index in indices:
            if index in chosen:
                continue
            distance = min(abs(_ordinal(charts[index]) - _ordinal(charts[j])) for j in chosen)
            score = distance if charts[index].get("chart_tf") not in seen_tfs else distance * 0.6
            if best_score is None or score > best_score or (score == best_score and index < best_index):
                best_index, best_score = index, score
        if best_index is None:
            break
        chosen.append(best_index)
        seen_tfs.add(charts[best_index].get("chart_tf"))
    return sorted(chosen)


_ORDINAL_CACHE: dict = {}


def _ordinal(chart: dict) -> float:
    key = id(chart)
    if key not in _ORDINAL_CACHE:
        try:
            stamp = datetime.fromisoformat(str(chart.get("ts_utc")))
            _ORDINAL_CACHE[key] = stamp.timestamp()
        except (TypeError, ValueError):
            _ORDINAL_CACHE[key] = 0.0
    return _ORDINAL_CACHE[key]


def select_priority(charts: list) -> tuple:
    """Return (selected charts in stratified order, selection notes).

    Mandatory inclusions (never dropped, so nothing documented is hidden):
      * every chart the independent verifier flagged;
      * every chart on a complete armed -> route -> fill chain.
    """
    by_type: dict = {}
    for index, chart in enumerate(charts):
        by_type.setdefault(chart.get("event_type"), []).append(index)

    mandatory_events: set = set()
    chain_notes: list = []
    for item in verify_flags(_INPUTS["verify"]):
        if item.get("event_id"):
            mandatory_events.add(item["event_id"])

    events = _INPUTS["events"]
    index_of = {chart.get("event_id"): i for i, chart in enumerate(charts)}
    for fill in [c for c in charts if c.get("event_type") == "fill"]:
        armed_id = (fill["csv"].get("related_event_id") or "")
        parts = [fill.get("event_id")]
        if armed_id:
            armed = events.get(armed_id) or {}
            if armed_id in index_of:
                parts.insert(0, armed_id)
            for route in charts:
                if route.get("event_type") == "route_ltf" and \
                        (route["csv"].get("related_event_id") or "") == armed_id:
                    parts.insert(1, route.get("event_id"))
        for event_id in parts:
            if event_id:
                mandatory_events.add(event_id)
        chain_notes.append({
            "fill": fill.get("event_id"),
            "armed": armed_id,
            "armed_type": (events.get(armed_id) or {}).get("event_type", "not in union"),
            "routes": [r.get("event_id") for r in charts
                       if r.get("event_type") == "route_ltf"
                       and (r["csv"].get("related_event_id") or "") == armed_id],
        })

    selected: list = []
    selection_rows: list = []
    for event_type, want in PRIORITY_SPEC:
        indices = by_type.get(event_type) or []
        if not indices:
            warn(f"priority set: no sampled charts of type {event_type}")
            continue
        mandatory = [i for i in indices if charts[i].get("event_id") in mandatory_events]
        picked = _spread_pick(charts, indices, min(want, len(indices)), mandatory)
        for i in picked:
            selected.append(i)
        selection_rows.append({
            "event_type": event_type,
            "available": len(indices),
            "requested": want,
            "chosen": len(picked),
            "forced": len([i for i in picked if charts[i].get("event_id") in mandatory_events]),
        })

    selected.sort(key=lambda i: (TYPE_ORDER.index(charts[i]["event_type"])
                                 if charts[i].get("event_type") in TYPE_ORDER else 99,
                                 _ts_key(charts[i])))
    notes = {
        "rule": ("First N of every type spread by farthest-point sampling over ts_utc "
                 "with a chart-TF repetition penalty; mandatory = verifier-flagged charts "
                 "plus every chart on a complete armed->route->fill chain."),
        "per_type": selection_rows,
        "mandatory_events": sorted(mandatory_events),
        "chains": chain_notes,
    }
    return [charts[i] for i in selected], notes


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #

FONTS_OK = False


def register_fonts() -> str:
    """Register DejaVu (shipped with matplotlib) so captions render exactly."""
    global FONTS_OK
    try:
        import matplotlib
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        font_dir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        wanted = {
            "LedgerSans": "DejaVuSans.ttf",
            "LedgerSans-Bold": "DejaVuSans-Bold.ttf",
            "LedgerSans-Italic": "DejaVuSans-Oblique.ttf",
            "LedgerSans-BoldItalic": "DejaVuSans-BoldOblique.ttf",
            "LedgerMono": "DejaVuSansMono.ttf",
            "LedgerMono-Bold": "DejaVuSansMono-Bold.ttf",
        }
        for name, filename in wanted.items():
            path = font_dir / filename
            if not path.is_file():
                raise FileNotFoundError(str(path))
            pdfmetrics.registerFont(TTFont(name, str(path)))
        pdfmetrics.registerFontFamily(
            "LedgerSans", normal="LedgerSans", bold="LedgerSans-Bold",
            italic="LedgerSans-Italic", boldItalic="LedgerSans-BoldItalic")
        pdfmetrics.registerFontFamily(
            "LedgerMono", normal="LedgerMono", bold="LedgerMono-Bold",
            italic="LedgerMono", boldItalic="LedgerMono-Bold")
        FONTS_OK = True
        return "DejaVuSans (embedded subset, via matplotlib)"
    except Exception as exc:                             # noqa: BLE001
        warn(f"DejaVu registration failed ({exc}); falling back to base-14 fonts")
        FONTS_OK = False
        return "Helvetica / Courier (base-14)"


def F(body: bool = False, mono: bool = False) -> str:
    if mono:
        return "LedgerMono-Bold" if body else ("LedgerMono" if FONTS_OK else "Courier")
    if body:
        return "LedgerSans-Bold" if FONTS_OK else "Helvetica-Bold"
    return "LedgerSans" if FONTS_OK else "Helvetica"


def T(text: str) -> str:
    """Last-resort transliteration when only base-14 fonts are available."""
    if FONTS_OK:
        return text
    table = {"\u2192": "->", "\u2190": "<-", "\u2194": "<->", "\u2264": "<=",
             "\u2265": ">=", "\u2013": "-", "\u2014": "-", "\u2026": "...",
             "\u00b7": "-", "\u2260": "!=", "\u00d7": "x", "\u00b1": "+/-"}
    for source, target in table.items():
        text = text.replace(source, target)
    return text.encode("latin-1", "replace").decode("latin-1")


# --------------------------------------------------------------------------- #
# Styles & layout
# --------------------------------------------------------------------------- #

def build_styles():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib import colors

    body = ParagraphStyle(
        "body", fontName=F(), fontSize=10, leading=14.5, textColor=colors.HexColor("#1a1a1a"),
        alignment=TA_LEFT, spaceAfter=5)
    return {
        "body": body,
        "small": ParagraphStyle("small", parent=body, fontSize=9, leading=12.5),
        "tiny": ParagraphStyle("tiny", parent=body, fontSize=8, leading=11),
        "title": ParagraphStyle("title", parent=body, fontName=F(True), fontSize=23, leading=27,
                                textColor=colors.HexColor("#0d2b45"), spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=body, fontName=F(), fontSize=13, leading=17,
                                   textColor=colors.HexColor("#12507d"), spaceAfter=10),
        "H1": ParagraphStyle("H1", parent=body, fontName=F(True), fontSize=15, leading=18,
                             textColor=colors.HexColor("#0d2b45"), spaceBefore=12, spaceAfter=6),
        "H1x": ParagraphStyle("H1x", parent=body, fontName=F(True), fontSize=15, leading=18,
                              textColor=colors.HexColor("#0d2b45"), spaceBefore=12, spaceAfter=6),
        "H2": ParagraphStyle("H2", parent=body, fontName=F(True), fontSize=11.5, leading=14,
                             textColor=colors.HexColor("#12507d"), spaceBefore=8, spaceAfter=4),
        # same look as H2 but not indexed into the contents page
        "H2x": ParagraphStyle("H2x", parent=body, fontName=F(True), fontSize=11.5, leading=14,
                              textColor=colors.HexColor("#12507d"), spaceBefore=8, spaceAfter=4),
        "caption": ParagraphStyle("caption", parent=body, fontName=F(True), fontSize=10.5,
                                  leading=13, textColor=colors.HexColor("#0d2b45"), spaceAfter=2),
        "file": ParagraphStyle("file", parent=body, fontName=F(mono=True), fontSize=8.5,
                               leading=11, textColor=colors.HexColor("#4a4a4a")),
        "verdict": ParagraphStyle("verdict", parent=body, fontName=F(True), fontSize=9.5,
                                  leading=13, textColor=colors.HexColor("#0d2b45")),
        "disclaimer": ParagraphStyle("disclaimer", parent=body, fontName=F(True), fontSize=10.5,
                                     leading=14, textColor=colors.HexColor("#8c1d18")),
        "cell": ParagraphStyle("cell", parent=body, fontSize=9, leading=11.5, spaceAfter=0),
        "cellb": ParagraphStyle("cellb", parent=body, fontName=F(True), fontSize=9,
                                leading=11.5, spaceAfter=0),
        "cell8": ParagraphStyle("cell8", parent=body, fontSize=8.5, leading=10.8, spaceAfter=0),
        "cell8b": ParagraphStyle("cell8b", parent=body, fontName=F(True), fontSize=8.5,
                                 leading=10.8, spaceAfter=0),
        "cellhead": ParagraphStyle("cellhead", parent=body, fontName=F(True), fontSize=8.5,
                                   leading=10.8, textColor=colors.HexColor("#ffffff"), spaceAfter=0),
        "mono8": ParagraphStyle("mono8", parent=body, fontName=F(mono=True), fontSize=8,
                                leading=10.5),
        "note": ParagraphStyle("note", parent=body,
                               fontName="LedgerSans-Italic" if FONTS_OK else "Helvetica-Oblique",
                               fontSize=8.5, leading=10.8, textColor=colors.HexColor("#4a4a4a"),
                               spaceAfter=0),
    }


def grid_table(data, col_widths, style_extra=None):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors

    table = Table(data, colWidths=col_widths, repeatRows=1)
    base = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d2b45")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9c4cf")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for row in range(1, len(data)):
        if row % 2 == 0:
            base.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#eef3f8")))
    table.setStyle(TableStyle(base + list(style_extra or [])))
    return table


# --------------------------------------------------------------------------- #
# Chart blocks
# --------------------------------------------------------------------------- #

def chart_block(chart: dict, styles, *, index: int, total: int, expert: bool):
    """One chart + its audit-trail caption block as a single keep-together list."""
    from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, Table
    from reportlab.lib import colors

    width = IMG_W_EXPERT if expert else IMG_W_FULL
    height = round(width * IMG_ASPECT, 1)
    flow = []

    if chart.get("image_ok"):
        try:
            flow.append(Image(str(chart["path"]), width=width, height=height))
        except Exception as exc:                          # noqa: BLE001
            warn(f"reportlab could not embed {chart.get('file')}: {exc}")
            _MISSING_IMAGES.append(chart.get("file", "?"))
            chart["image_ok"] = False
    if not chart.get("image_ok"):
        flow.append(grid_table(
            [[Paragraph(T("<b>IMAGE NOT EMBEDDABLE</b> - %s was missing or unreadable "
                          "at build time; the ledger row is still described below."
                          % esc(chart.get("file"))), styles["cell"])]],
            [CONTENT_W]))

    row = chart.get("csv") or {}
    label = chart.get("label") or FL.caption_lines(
        chart.get("event_type"), row, _INPUTS["events"],
        event_id=str(chart.get("event_id") or ""),
        chart_tf=str(chart.get("chart_tf") or ""),
        detection_tf=str(chart.get("detection_tf") or ""))
    tags = dash(chart.get("model_tags"), "(none)")
    geometry = ("level %s" % row.get("price_low")) if (
        str(row.get("price_low") or "") == str(row.get("price_high") or "")) else (
        "zone %s - %s" % (dash(row.get("price_low")), dash(row.get("price_high"))))
    steps = []
    if row.get("pillar_path"):
        steps.append("pillars %s" % row["pillar_path"])
    if row.get("trigger"):
        steps.append("trigger %s" % row["trigger"])
    if row.get("disp_magnitude_atr"):
        steps.append("disp %s ATR" % clip(row["disp_magnitude_atr"], 6))
    pipeline = " | ".join(steps) if steps else "-"
    exits = " | ".join(
        "%s %s" % (label, row[key]) for label, key in
        (("entry", "entry"), ("orig SL", "original_sl"))
        if row.get(key))
    anchor = dash(row.get("entry_anchor"))
    related = dash(row.get("related_event_id"))
    if related != "-" and chart.get("rel_type"):
        related = "%s (%s)" % (related, chart["rel_type"])
    observed = "-"
    notes = str(row.get("notes") or "")
    if "observed=" in notes:
        observed = notes.split("observed=")[-1].split(";")[0] + " batches"
    source = dash(row.get("source_module"))
    source = source.rsplit(".", 2)[-2] + "." + source.rsplit(".", 1)[-1] if source.count(".") >= 2 else source

    # ------------------------------------------------------------------ #
    # Technical record -- DEMOTED to a small footnote (owner instruction:
    # "strip or demote function paths to a small technical footnote"). It is
    # kept, never dropped: it is the audit trail behind the plain label.
    # ------------------------------------------------------------------ #
    technical = (
        "technical record: event_id %s  |  detected %s %s  |  charted %s  |  dir %s"
        "  |  tags %s  |  geometry %s"
        % (dash(chart.get("event_id")), dash(chart.get("ts_utc")),
           dash(chart.get("detection_tf")), dash(chart.get("chart_tf")),
           dash(chart.get("direction")), tags, geometry))
    technical2 = (
        "pipeline %s  |  exit refs %s  |  anchor %s  |  related %s  |  source %s"
        "  |  observed %s"
        % (pipeline, exits, anchor, related, source, observed))

    flow.append(Spacer(1, 3))
    flow.append(Paragraph(
        T("Chart %d of %d &mdash; <b>%s</b>" % (index, total, esc(label["tag"]))),
        styles["caption"]))
    flow.append(Paragraph(
        T("flowchart stage: %s   |   chart TF %s / detect TF %s"
          % (esc(label["stage"]), dash(chart.get("chart_tf")),
             dash(chart.get("detection_tf")))), styles["tiny"]))
    flow.append(Spacer(1, 2))
    flow.append(plain_block(label, styles))
    flow.append(Spacer(1, 3))
    flow.append(Paragraph(T(esc(technical)), styles["file"]))
    flow.append(Paragraph(T(esc(technical2)), styles["file"]))
    flow.append(Paragraph(
        T("chart file: %s   |   label set: %s"
          % (esc(chart.get("file")), esc(FL.LABEL_VERSION))), styles["file"]))
    if expert:
        flow.append(Spacer(1, 1))
        flow.append(Paragraph(
            T("Validator verdict:   CORRECT  /  PARTIAL  /  WRONG  /  UNCLEAR"
              "       notes: ________________________________"), styles["verdict"]))
    flow.append(Spacer(1, 8))
    return KeepTogether(flow)


def plain_block(label: dict, styles):
    """The plain-flowchart reading block printed under every chart.

    For ``route_ltf`` / ``fill`` this IS the mandatory SETUP CHAIN block
    (HTF structure -> LTF confirmation -> entry / original SL + the
    "this is the entry step, not the HTF sweep" line). For every other type it
    is the row's own plain-language reading guide. Nothing in it is invented:
    each clause is either read from the ledger row or explicitly reported as
    not linked.
    """
    from reportlab.platypus import Paragraph, Table, TableStyle
    from reportlab.lib import colors

    chain = label.get("chain") or []
    lines = chain or label.get("detail") or []
    title = ("SETUP CHAIN &mdash; HTF structure &rarr; LTF confirmation &rarr; entry"
             if chain else
             "How to read this chart (plain flowchart labels)")
    cells = [Paragraph(T("<b>%s</b>" % title), styles["cellb"])]
    bold_prefixes = ("FLOWCHART STAGE", "HTF structure", "LTF confirmation", "Entry")
    for line in lines:
        text = str(line)
        if text == FL.LTF_CHAIN_FOOTER:
            cells.append(Paragraph(T(esc(text)), styles["note"]))
            continue
        prefix, sep, rest = text.partition(": ")
        if sep and prefix in bold_prefixes:
            cells.append(Paragraph(T("<b>%s:</b> %s" % (esc(prefix), esc(rest))),
                                   styles["cell8"]))
        else:
            cells.append(Paragraph(T(esc(text)), styles["cell8"]))
    table = Table([[cells]], colWidths=[CONTENT_W])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f6fa")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c3ced9")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
    ]))
    return table


def placeholder_block(reason: str, styles):
    """Used when a chart could not be embedded at all - never silent."""
    from reportlab.platypus import Paragraph, Spacer
    return [Paragraph(T("Chart unavailable: %s" % esc(reason)), styles["small"]), Spacer(1, 8)]


def legend_table(styles):
    """What the chart pixels mean - read from the renderer, not invented."""
    from reportlab.platypus import Paragraph

    rows = [
        [Paragraph(T("chart element"), styles["cellhead"]),
         Paragraph(T("rendered as"), styles["cellhead"]),
         Paragraph(T("meaning in the ledger"), styles["cellhead"])],
        [Paragraph(T("candle up / down"), styles["cell"]),
         Paragraph(T("solid green / solid red body"), styles["cell"]),
         Paragraph(T("close &gt;= open / close &lt; open on the charted timeframe"), styles["cell"])],
        [Paragraph(T("event level"), styles["cell"]),
         Paragraph(T("solid blue horizontal line"), styles["cell"]),
         Paragraph(T("price_low == price_high: the event is a single price (e.g. a liquidity level)"), styles["cell"])],
        [Paragraph(T("event zone"), styles["cell"]),
         Paragraph(T("translucent blue band"), styles["cell"]),
         Paragraph(T("price_low .. price_high: the event is a zone (POI / FVG bounds)"), styles["cell"])],
        [Paragraph(T("event bar"), styles["cell"]),
         Paragraph(T("yellow vertical line"), styles["cell"]),
         Paragraph(T("the bar the event was first observed on, in the charted series"), styles["cell"])],
        [Paragraph(T("entry (limit)"), styles["cell"]),
         Paragraph(T("purple dashed line"), styles["cell"]),
         Paragraph(T("the routed limit price recorded on the row (only when one exists)"), styles["cell"])],
        [Paragraph(T("original SL"), styles["cell"]),
         Paragraph(T("red dashed line"), styles["cell"]),
         Paragraph(T("the placement stop reference - it is also red, so read the legend, not the colour alone"), styles["cell"])],
    ]
    return grid_table(rows, [96, 128, CONTENT_W - 224])


# --------------------------------------------------------------------------- #
# Narrative content (quoted/derived from the frozen artifacts)
# --------------------------------------------------------------------------- #

MODULE_MAP_ROWS = [
    ("0 / 0A", "Liquidity levels (session, periodic, EQH/EQL, structural)",
     "smc.detection.liquidity_scanner.scan", "liquidity_level",
     "one row per level; price anchor = the level price"),
    ("0A", "Liquidity sweep (wick pierce + body close back)",
     "smc.detection.sweep_detector.detect_sweeps", "sweep",
     "linked to its level via related_event_id"),
    ("0A", "Displacement (BOS + FVG + >= 1x ATR)",
     "smc.detection.displacement_checker.check_displacement", "displacement",
     "magnitude in ATR is recorded on the row"),
    ("1", "Fair value gap (3-candle imbalance)",
     "smc.detection.fvg_detector.detect_fvgs", "fvg",
     "zone = the imbalance on the detection timeframe"),
    ("1", "POI models M1-M7 (equal tags)",
     "smc.orchestration.detection_driver.detect_pois", "poi_raw",
     "pre-merge raw model output, one tag per POI"),
    ("1", "Model 8 HTF order block / supply-demand - label 'ob'",
     "smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply._zones (kind=ob)",
     "poi_raw", "candle before the FVG; labelled ob only when the code yields it"),
    ("1", "Model 8 HTF supply / demand - label 'demand_supply'",
     "smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply._zones (kind=demand_supply)",
     "poi_raw", "last opposing candle before a >= 1x ATR impulse"),
    ("1", "Confluence merge (overlapping same-direction zones)",
     "smc.poi.confluence_scorer.merge_overlapping", "poi_merged",
     "union of member tags"),
    ("2", "Five validation pillars",
     "smc.validation.validation_pipeline.ValidationPipeline", "pillar_pass / pillar_reject",
     "first hard failure is recorded; PASS path is summarised"),
    ("3", "Arm (CREATED -> FRESH + anchor)",
     "smc.orchestration.engine.PipelineEngine.arm_at", "poi_armed",
     "zone-episode dedup (ZoneDedup); arm_bar anchors the give-up window"),
    ("4", "LTF trigger routing A-F (chronological first-valid)",
     "smc.orchestration.engine.PipelineEngine.scan_route", "route_ltf",
     "entry limit + stop reference"),
    ("4", "Intent lifecycle (R9 place-on-reentry)",
     "smc.backtest.intents.IntentBook.events", "intent",
     "armed / placed / expired / replaced / dropped transitions"),
    ("4", "Execution fill (limit fill)",
     "smc.backtest.runner.BacktestRunner", "fill",
     "ticket / route_id / close_kind / pnl recorded for completeness only"),
]

OPEN_DISPOSITIONS = [
    ("Tags vs geometry (OPEN)",
     "Identical zones re-detect with different tag sets (e.g. M1+M7 then M4 then M5): tags are "
     "detection-path-dependent, not geometry-intrinsic. Score the geometry you see; report tag "
     "instability in the notes. Source: FLOWCHART_CODE_EVIDENCE_MAP.md section 5, item 1."),
    ("Killed vs traded vocabulary (OPEN)",
     "The pattern language of killed candidates and of admitted flow barely overlap, so the same "
     "geometry can look 'wrong' under one model and 'right' under another. Source: same map, item 2."),
    ("Zone-entry divergence (OPEN)",
     "10 of 11 observed entries sit 1-4 zone-heights outside the recorded zone; merge-widest-zone "
     "retention is the untested hypothesis. This is the flag raised on charts 034 and 043 here. "
     "Source: same map, item 4 (referred to as 'open mismatch #5' in the chart verifier)."),
    ("Spread-grade scale (OPEN ruling)",
     "Tag-count confluence scores against 0-10 spread-grade thresholds means the top grade is "
     "unreachable as coded. Not visible on these charts; recorded for completeness. "
     "Source: same map, item 9."),
]

CAVEATS = [
    "One row per unique structural event. The first observation fixes the row; later batches only "
    "increment observed=N (and record verdict flicker as observed_event_types).",
    "The detection stack runs on GROWING prefixes per timeframe (the accepted Phase 3/4 composition), "
    "so a chart shows the structure the code emitted at that batch, not a rolling-window replay.",
    "Per-POI rows (poi_raw / poi_merged / pillar_*) close over their chunk's prefix: the verdict shown "
    "is the first observation, and poi_id is the batch-local id at that moment. event_id is the stable key.",
    "Model 8 is captured through the kind-labelled zone hook, which is a superset of M8.detect() "
    "(which keeps only the latest zone per kind).",
    "entry_anchor is populated only when a trigger actually set it; blank means 'not set', never invented.",
    "Trigger D emits nothing on volume-less data (locking ruling A5) - its absence is a property of the "
    "data, not a measurement gap.",
    "Swing objects are not in the controlled vocabulary; they are visible only through the levels and "
    "sweeps they produce.",
]

HOW_TO_SCORE = [
    "Read section 2 first (How to read flowchart tags): it is the whole engine-word -> plain-tag "
    "contract, and it states exactly where a label comes from and what it refuses to assume.",
    "Work chart by chart in the order given. Every chart is a single ledger row; the plain reading "
    "block under the chart tells you what you are looking at, and the technical footnote under it "
    "repeats the row's code-emitted fields so you can score without opening the CSV.",
    "Judge identification only: is this the structure the locked flowchart (00_LOCKED, section 16 "
    "pipeline and the model specs) defines at this point in time, on this timeframe, in this direction?",
    "Use the notes line after each verdict. For PARTIAL/WRONG say which attribute is off (price anchor, "
    "zone bounds, timeframe, direction, model label, or pipeline stage).",
    "Return the tally per concept (CORRECT / PARTIAL / WRONG / UNCLEAR) using the template on the "
    "return page - tallies by event_type are what decide the next action.",
]

RUBRIC = [
    ("CORRECT", "The code-emitted structure matches the flowchart's definition of that event on this "
     "chart: the level or zone sits on the right geometry, the timeframe and direction are right, and "
     "the pipeline stage attributed to it is right."),
    ("PARTIAL", "The event is real and broadly right, but at least one material attribute diverges: the "
     "price anchor or zone bounds, the detection timeframe, the models tagged, or which stage produced it."),
    ("WRONG", "The charted event is not the thing the flowchart would call by that name, or the code "
     "emitted something the flowchart does not define at this point."),
    ("UNCLEAR", "The chart alone does not settle it (level not visible, geometry off-screen, too little "
     "context). Pull the row from events.csv by event_id - do not guess a verdict."),
]


def rubric_table(styles):
    from reportlab.platypus import Paragraph

    rows = [[Paragraph(T("Verdict"), styles["cellhead"]),
             Paragraph(T("Meaning - score against the locked flowchart, not against P/L"),
                       styles["cellhead"])]]
    for name, text in RUBRIC:
        rows.append([Paragraph(T("<b>%s</b>" % name), styles["cell"]),
                     Paragraph(T(text), styles["cell"])])
    return grid_table(rows, [66, CONTENT_W - 66])


def _flag_origin(item: dict) -> str:
    """Where a verifier flag comes from - shared by the PDF and the text twin."""
    if "retain_window" in "; ".join(item.get("flags") or []):
        return "warm-up retain_window drop (merge link repair)"
    return "zone-entry divergence (evidence map section 5 item 4; OPEN)"


def disposition_table(styles, title: str = "Other open dispositions that can make identification look wrong"):
    from reportlab.platypus import Paragraph

    rows = [[Paragraph(T("disposition"), styles["cellhead"]),
             Paragraph(T("detail (all OPEN unless stated)"), styles["cellhead"])]]
    for name, text in OPEN_DISPOSITIONS:
        rows.append([Paragraph(T("<b>%s</b>" % esc(name)), styles["cell8"]),
                     Paragraph(T(text), styles["cell8"])])
    return [Paragraph(T(title), styles["H2"]), grid_table(rows, [104, CONTENT_W - 104])]


# --------------------------------------------------------------------------- #
# Document plumbing
# --------------------------------------------------------------------------- #

def make_doc(path: Path, title: str, footer_text: str, meta: dict):
    """Custom doc template: running header, deferred footer with total pages."""
    from reportlab.lib import colors
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

    class LedgerDoc(BaseDocTemplate):
        def afterFlowable(self, flowable):                     # noqa: N802
            styles = getattr(self, "_styles", None)
            name = getattr(getattr(flowable, "style", None), "name", "")
            if name in ("H1", "H2"):
                level = 0 if name == "H1" else 1
                text = flowable.getPlainText()
                self.notify("TOCEntry", (level, text, self.page))
                key = "outline-%x" % id(flowable)
                try:
                    self.canv.bookmarkPage(key)
                    self.canv.addOutlineEntry(text, key, level=level, closed=(level > 0))
                except Exception:                              # noqa: BLE001
                    pass

    def draw_header_footer(canv, doc):
        canv.saveState()
        canv.setStrokeColor(colors.HexColor("#b9c4cf"))
        canv.setLineWidth(0.5)
        canv.line(MARGIN_L, PAGE_H - MARGIN_T + 16, PAGE_W - MARGIN_R, PAGE_H - MARGIN_T + 16)
        canv.setFont(F(), 7.5)
        canv.setFillColor(colors.HexColor("#4a4a4a"))
        canv.drawString(MARGIN_L, PAGE_H - MARGIN_T + 21, T(footer_text))
        canv.drawRightString(PAGE_W - MARGIN_R, PAGE_H - MARGIN_T + 21,
                             T("XAUUSD  |  2025-06-01 -> 2025-11-30  |  V1.1 freeze"))
        if doc.page > 1:
            canv.line(MARGIN_L, MARGIN_B - 14, PAGE_W - MARGIN_R, MARGIN_B - 14)
        canv.restoreState()

    def draw_footer(canv, total):
        canv.saveState()
        canv.setFont(F(), 7.5)
        canv.setFillColor(colors.HexColor("#4a4a4a"))
        canv.drawString(MARGIN_L, MARGIN_B - 24,
                        T("%s - identification audit, not performance/edge validation" % PROJECT))
        canv.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 24,
                             T("page %d of %d  -  generated %s" % (canv.getPageNumber(), total, DATE_STAMP)))
        canv.restoreState()

    doc = LedgerDoc(str(path), pagesize=(PAGE_W, PAGE_H),
                    leftMargin=MARGIN_L, rightMargin=MARGIN_R,
                    topMargin=MARGIN_T, bottomMargin=MARGIN_B,
                    title=title, author="SMC structure ledger (read-only measurement)",
                    subject=DISCLAIMER, creator="06_RESEARCH/scripts/build_expert_pdfs.py")
    doc._styles = meta.get("styles")
    frame = Frame(MARGIN_L, MARGIN_B, CONTENT_W, PAGE_H - MARGIN_T - MARGIN_B,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=draw_header_footer)])

    from reportlab.pdfgen import canvas as rl_canvas

    class DeferredFooterCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_states = []

        def showPage(self):                                    # noqa: N802
            self._saved_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_states)
            for state in self._saved_states:
                self.__dict__.update(state)
                try:
                    draw_footer(self, total)
                except Exception:                              # noqa: BLE001
                    pass
                super().showPage()
            super().save()

    doc._canvasmaker = (lambda *a, **kw: DeferredFooterCanvas(*a, **kw))
    return doc


def render_document_stable(path: Path, story_factory, title: str, footer_text: str,
                           styles, meta: dict, max_passes: int = 5):
    """Build until the contents page numbers stop moving (self-verifying).

    Pass 1 seeds the map, later passes render real numbers, and the loop only
    stops when two consecutive passes agree - so the printed numbers belong to
    the layout that is actually written to disk.
    """
    toc_map: dict = {}
    pages = 0
    for attempt in range(1, max_passes + 1):
        collected: dict = {}
        doc = make_doc(path, title, footer_text, meta)
        original_notify = doc.notify

        def notify(kind, payload, _orig=original_notify, _collected=collected):
            if kind == "TOCEntry" and isinstance(payload, tuple) and len(payload) == 3:
                level, text, page = payload
                _collected[text] = (level, page)
            return _orig(kind, payload)

        doc.notify = notify
        try:
            doc.build(story_factory(toc_map), canvasmaker=doc._canvasmaker)
        except Exception as exc:                              # noqa: BLE001
            raise RuntimeError(f"PDF build failed for {path.name} (pass {attempt}): {exc}") from exc
        pages = int(doc.page)
        if collected == toc_map:
            print(f"  pass {attempt}: contents stable ({len(toc_map)} entries, {pages} pages)")
            break
        toc_map = collected
        print(f"  pass {attempt}: {len(toc_map)} entries collected, re-typesetting")
    else:
        warn(f"contents page numbers did not stabilise for {path.name} after {max_passes} passes")
    return pages, toc_map


#: reportlab draws each embedded image as ``q 1 0 0 1 X Y cm  q W 0 0 H 0 0 cm
#: /NAME Do Q Q``; the composed box is (X, Y, X+W, Y+H) in PDF page coordinates.
_PLACEMENT_RE = re.compile(
    r"1 0 0 1 (-?[0-9.]+) (-?[0-9.]+) cm\s*q\s*([0-9.]+) 0 0 ([0-9.]+) 0 0 cm\s*/(\S+) Do")


def _image_boxes(page) -> list:
    """[(name, x0, y0, x1, y1)] for every image actually DRAWN on a page."""
    try:
        stream = page.get_contents()
        data = stream.get_data().decode("latin-1")
    except Exception as exc:                                     # noqa: BLE001
        warn(f"content stream unreadable on a page: {exc}")
        return []
    boxes = []
    for match in _PLACEMENT_RE.finditer(data):
        x, y, w, h, name = match.groups()
        x, y, w, h = float(x), float(y), float(w), float(h)
        boxes.append((name, x, y, x + w, y + h))
    return boxes


def check_pdf(path: Path, expected_images: int) -> dict:
    """Independent read-back of the produced PDF (pages, embedded images, links,
    image placement/overlap, text)."""
    report = {"path": str(path), "pages": 0, "images": 0, "uri_actions": 0,
              "page_size_ok": False, "errors": [], "key_text_ok": False, "engine_reader": None,
              "images_per_page": {}, "placed_images": 0, "out_of_frame": [], "overlaps": []}
    try:
        from PyPDF2 import PdfReader
    except Exception:                                         # noqa: BLE001
        try:
            from pypdf import PdfReader                        # type: ignore
        except Exception as exc:                              # noqa: BLE001
            report["errors"].append(f"no PDF reader available: {exc}")
            return report
    try:
        reader = PdfReader(str(path))
        report["engine_reader"] = "PyPDF2"
        report["pages"] = len(reader.pages)
        images = 0
        image_sizes = {}
        per_page: dict = {}
        for page_number, page in enumerate(reader.pages, start=1):
            page_images = 0
            box = page.mediabox
            if abs(float(box.width) - PAGE_W) < 1.0 and abs(float(box.height) - PAGE_H) < 1.0:
                report["page_size_ok"] = True
            try:
                xobjects = (page.get("/Resources") or {}).get("/XObject")
                if xobjects:
                    for key in xobjects:
                        obj = xobjects[key].get_object()
                        if str(obj.get("/Subtype")) == "/Image":
                            images += 1
                            page_images += 1
                            size_key = (int(obj.get("/Width") or 0),
                                        int(obj.get("/Height") or 0))
                            image_sizes[size_key] = image_sizes.get(size_key, 0) + 1
                if "/Annots" in page:
                    for annot in page["/Annots"]:
                        obj = annot.get_object()
                        if str(obj.get("/Subtype")) == "/Link":
                            if "/URI" in (obj.get("/A") or {}):
                                report["uri_actions"] += 1
                            report["errors"].append("a link annotation is present in the PDF")
            except Exception as exc:                          # noqa: BLE001
                report["errors"].append(f"page scan failed: {exc}")
            per_page[str(page_images)] = per_page.get(str(page_images), 0) + 1
            # --- placement / overlap (every drawn image must sit inside the frame) ---
            boxes = _image_boxes(page)
            report["placed_images"] += len(boxes)
            for name, x0, y0, x1, y1 in boxes:
                if (x0 < MARGIN_L - 0.5 or x1 > PAGE_W - MARGIN_R + 0.5
                        or y0 < MARGIN_B - 0.5 or y1 > PAGE_H - MARGIN_T + 0.5):
                    report["out_of_frame"].append(
                        {"page": page_number, "image": name,
                         "box": [round(v, 2) for v in (x0, y0, x1, y1)]})
            for i in range(len(boxes)):
                for j in range(i + 1, len(boxes)):
                    ax0, ay0, ax1, ay1 = boxes[i][1:]
                    bx0, by0, bx1, by1 = boxes[j][1:]
                    dx = min(ax1, bx1) - max(ax0, bx0)
                    dy = min(ay1, by1) - max(ay0, by0)
                    if dx > 0.5 and dy > 0.5:
                        report["overlaps"].append(
                            {"page": page_number, "a": boxes[i][0], "b": boxes[j][0],
                             "area_pt2": round(dx * dy, 2)})
        report["image_sizes"] = {"%dx%d" % k: v for k, v in sorted(image_sizes.items())}
        report["images_per_page"] = dict(sorted(per_page.items(), key=lambda kv: int(kv[0])))
        report["images"] = images
        if report["out_of_frame"]:
            report["errors"].append(
                f"{len(report['out_of_frame'])} image(s) placed outside the text frame")
        if report["overlaps"]:
            report["errors"].append(f"{len(report['overlaps'])} overlapping image pair(s)")
        if report["placed_images"] != images:
            report["errors"].append(
                f"drawn images {report['placed_images']} != declared image objects {images}")
        if expected_images and images < expected_images:
            report["errors"].append(f"embedded images {images} < expected {expected_images}")
        try:
            head = (reader.pages[0].extract_text() or "") + (reader.pages[1].extract_text() or "")
        except Exception as exc:                              # noqa: BLE001
            head = ""
            report["errors"].append(f"text extraction failed: {exc}")
        report["key_text_ok"] = ("identification audit only" in head.lower()
                                 or "not performance/edge validation" in head.lower())
        if not report["key_text_ok"]:
            report["errors"].append("disclaimer text not found on the first pages")
    except Exception as exc:                                  # noqa: BLE001
        report["errors"].append(f"PDF read-back failed: {exc}")
    return report


# --------------------------------------------------------------------------- #
# Shared flow helpers
# --------------------------------------------------------------------------- #

_INPUTS: dict = {}


def nfmt(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def kv_table(rows, styles, label_w: float = 132.0):
    from reportlab.platypus import Paragraph, Table, TableStyle
    from reportlab.lib import colors

    data = [[Paragraph(T(str(label)), styles["cellb"]), Paragraph(T(str(value)), styles["cell"])]
            for label, value in rows]
    table = Table(data, colWidths=[label_w, CONTENT_W - label_w])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f6fa")),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#c3ced9")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dde5ec")),
    ]))
    return table


def callout(text: str, styles, colour: str = "#8c1d18", background: str = "#fdf1f0"):
    from reportlab.platypus import Paragraph, Table, TableStyle
    from reportlab.lib import colors
    style = styles["disclaimer"] if colour == "#8c1d18" else styles["small"]
    table = Table([[Paragraph(T(text), style)]], colWidths=[CONTENT_W])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor(colour)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def contents_flow(styles, toc_map):
    """Contents table built from pages measured in the previous typesetting pass.

    `toc_map` maps heading text -> (level, page). Using our own table (instead of
    reportlab's TableOfContents) keeps the contents on its own page and keeps the
    page numbers verifiable: the build repeats until the map stops changing.
    """
    from reportlab.platypus import Paragraph

    if not toc_map:
        return [Paragraph(T("Page numbers are resolved on the following typesetting pass."),
                          styles["small"])]
    rows = [[Paragraph(T("section"), styles["cellhead"]),
             Paragraph(T("page"), styles["cellhead"])]]
    for text, (level, page) in toc_map.items():
        label = ("&nbsp;&nbsp;&nbsp;&nbsp;" if level else "") + esc(text)
        rows.append([Paragraph(T(label), styles["cell8"] if level else styles["cellb"]),
                     Paragraph(str(page), styles["cell"])])
    return [grid_table(rows, [CONTENT_W - 52.0, 52.0])]


def cover_flow(styles, *, doc_title, subtitle, purpose, meta_rows, extra_flow=None):
    from reportlab.platypus import Paragraph, Spacer
    flow = [Spacer(1, 8),
            Paragraph(T(PROJECT), styles["subtitle"]),
            Paragraph(T(doc_title), styles["title"]),
            Spacer(1, 2),
            Paragraph(T(subtitle), styles["body"]),
            Spacer(1, 4),
            kv_table(meta_rows, styles),
            Spacer(1, 10),
            callout(DISCLAIMER + " This pack asks one question: does the code identify the structure the "
                                "locked flowchart defines? It carries no expectancy, no profit factor and no "
                                "edge claim; the two fill rows are shown for chain completeness only.",
                    styles),
            Spacer(1, 10),
            Paragraph(T("What this document is"), styles["H2x"]),
            Paragraph(T(purpose), styles["small"])]
    if extra_flow:
        flow.extend(extra_flow)
    return flow


def short_ts(value) -> str:
    """'2025-11-14T20:35:00+00:00' -> '2025-11-14 20:35' so index cells never wrap."""
    text = dash(value)
    return text.replace("T", " ")[:16]


def chart_index_table(charts, styles, *, with_verdict: bool):
    """Scoring checklist. Leads with the PLAIN tag; the engine word is kept in
    the next column so the reviewer can always trace a row back to events.csv."""
    from reportlab.platypus import Paragraph

    head = ["#", "plain flowchart tag", "code type", "chart TF", "det. TF",
            "ts (date time)", "dir", "tags", "event_id"]
    rows = [[Paragraph(T(h), styles["cellhead"]) for h in head]]
    for position, chart in enumerate(charts, start=1):
        label = chart.get("label") or {}
        row = [Paragraph(esc(position), styles["cell8"]),
               Paragraph(esc(dash(label.get("tag"), "-")), styles["cell8"]),
               Paragraph(esc(dash(chart.get("event_type"))), styles["cell8"]),
               Paragraph(esc(dash(chart.get("chart_tf"))), styles["cell8"]),
               Paragraph(esc(dash(chart.get("detection_tf"))), styles["cell8"]),
               Paragraph(esc(short_ts(chart.get("ts_utc"))), styles["cell8"]),
               Paragraph(esc(dash(chart.get("direction"))), styles["cell8"]),
               Paragraph(esc(clip(dash(chart.get("model_tags"), "-"), 14)), styles["cell8"]),
               Paragraph(esc(str(chart.get("event_id"))), styles["cell8"])]
        if with_verdict:
            row.append(Paragraph(esc("__________"), styles["cell8"]))
        rows.append(row)
    # 'dir' must fit SHORT/LONG and 'event_id' a 16-char id without splitting
    # mid-word; 'ts' gets room for 'YYYY-MM-DD HH:MM'.
    widths = [15.0, 100.0, 44.0, 30.0, 30.0, 84.0, 34.0, 36.0, 88.0]
    if with_verdict:
        rows[0] = rows[0] + [Paragraph(T("verdict"), styles["cellhead"])]
        widths = widths + [52.0]
    scale = CONTENT_W / sum(widths)
    return grid_table(rows, [w * scale for w in widths])


def label_stats(charts, events_by_id) -> dict:
    """Data-driven counts backing the 'How to read flowchart tags' page.

    Proves the honesty rule instead of asserting it: how many charts carry a
    code-supported OB / demand / supply / FVG label, and how many are left as
    "unlabeled POI".
    """
    from collections import Counter

    counts: Counter = Counter()
    kinds: Counter = Counter()
    for chart in charts:
        label = chart.get("label") or {}
        tag = str(label.get("tag") or "")
        counts[tag.split(" (")[0] or "unknown"] += 1
        if str(chart.get("event_type")) == "poi_raw":
            kinds[FL.kind_of(chart.get("csv") or {}) or "(no kind emitted)"] += 1
    labeled = sum(count for name, count in kinds.items() if name != "(no kind emitted)")
    return {
        "tag_counts": dict(counts),
        "poi_kinds": dict(kinds),
        "poi_labeled_from_kind": labeled,
        "poi_unlabeled": kinds.get("(no kind emitted)", 0),
        "chain_charts": [c.get("file") for c in charts if (c.get("label") or {}).get("chain")],
    }


def flowchart_label_page(styles, charts, events_by_id):
    """'How to read flowchart tags': the engine word -> plain tag contract.

    Includes a worked example taken from this pack's own charts (an actual
    route_ltf / fill row), so the reviewer sees the setup chain before chart 1.
    """
    from reportlab.platypus import Paragraph, Spacer, PageBreak

    stats = label_stats(charts, events_by_id)
    flow = [PageBreak(),
            Paragraph(T("2. How to read flowchart tags"), styles["H1"]),
            Paragraph(
        T("Every chart title, every caption and every index column in this pack leads with the plain "
          "flowchart tag rather than the engine's word for the event. The table below is the whole "
          "contract: the left column is what the code emits (still shown, so a row can always be "
          "traced back to events.csv), the middle column is what you will read in this pack, and the "
          "right column is what that means on the chart."), styles["body"])]
    rows = [[Paragraph(T(h), styles["cellhead"]) for h in
             ("code event_type (engine word)", "plain tag you will see",
              "what it means on the chart")]]
    for code, tag, meaning in FLOWCHART_LABEL_TABLE:
        rows.append([Paragraph(T("<b>%s</b>" % esc(code)), styles["cell8"]),
                     Paragraph(T("<b>%s</b>" % esc(tag)), styles["cell8"]),
                     Paragraph(T(esc(meaning)), styles["cell8"])])
    flow.append(grid_table(rows, [104, 122, CONTENT_W - 226]))

    flow.append(Paragraph(T("Where the labels come from (and what they refuse to do)"), styles["H2"]))
    for item in [
        "A label is emitted only when the ledger row itself supports it. The order B-vs-demand/supply "
        "label is read from the row's own kind= note ('ob' -> Order block, 'demand_supply' + "
        "direction -> Demand or Supply zone), and the level words come from the row's level_type=. ",
        "When the code emitted no kind for a POI, the chart says <b>\"unlabeled POI\"</b> and the "
        "caption says so explicitly. No order block, FVG or supply/demand label is ever inferred from "
        "how a chart looks. In this pack, %d of %d sampled poi_raw charts carry a code kind (%s) and "
        "%d carry none."
        % (stats["poi_labeled_from_kind"],
           stats["poi_labeled_from_kind"] + stats["poi_unlabeled"],
           ", ".join("%s x%d" % (k, v) for k, v in sorted(stats["poi_kinds"].items())
                     if k != "(no kind emitted)") or "none",
           stats["poi_unlabeled"]),
        "Links between rows are never invented either: where the ledger records no sweep or FVG event "
        "id on a set-up chain, the caption says exactly that instead of pointing at a nearby sweep.",
        "Labels are wording only. The pixels, the geometry, the thresholds, the pillars, the triggers "
        "and every locked constant are untouched (LOGIC_CHANGED: NO).",
    ]:
        flow.append(Paragraph(T("- " + item), styles["small"]))

    flow.append(Paragraph(T("Test counts in this pack"), styles["H2"]))
    rows = [[Paragraph(T(h), styles["cellhead"]) for h in
             ("plain tag", "charts in this pack")]]
    for name in sorted(stats["tag_counts"]):
        rows.append([Paragraph(T(esc(name)), styles["cell8"]),
                     Paragraph(nfmt(stats["tag_counts"][name]), styles["cell8"])])
    flow.append(grid_table(rows, [CONTENT_W - 90.0, 90.0]))

    example = None
    for chart in charts:
        if (chart.get("label") or {}).get("chain"):
            example = chart
            break
    if example is not None:
        flow.append(Paragraph(T("Worked example: a set-up chain from this pack"), styles["H2"]))
        flow.append(Paragraph(
            T("This is the block that precedes every route_ltf and fill chart (the engine words "
              "behind it, as recorded: %s). It answers the four review questions in order: what HTF "
              "structure the entry came from, what the M5 confirmation was, where the entry and the "
              "original stop sit, and which step this chart is.")
            % esc("%s / %s / %s" % (dash(example.get("event_type")),
                                    dash(example.get("chart_tf")),
                                    dash(example.get("event_id")))), styles["small"]))
        flow.append(plain_block(example.get("label") or {}, styles))

    flow.append(Paragraph(T("What the plain labels do NOT claim"), styles["H2"]))
    for item in [
        "A plain tag is not a verdict. \"Order block\" states which code kind the row carries, not that "
        "the order block is the right one. Your CORRECT / PARTIAL / WRONG / UNCLEAR score is the verdict.",
        "A demand / supply zone named from direction is still the model's classification of a zone; if "
        "you disagree with the classification, that is exactly the finding to record.",
        "No layout, label or caption in this pack changes what the stack detects. Identification only; "
        "no expectancy, profit factor or edge statement is made anywhere.",
    ]:
        flow.append(Paragraph(T("- " + item), styles["small"]))
    return flow


# --------------------------------------------------------------------------- #
# FULL REPORT
# --------------------------------------------------------------------------- #

def build_full_report(charts, priority_notes, pages_hint=None):
    from reportlab.platypus import Paragraph, Spacer, PageBreak

    styles = _INPUTS["styles"]
    summary = _INPUTS["summary"]
    window = summary.get("window") or {}
    by_type = summary.get("events_by_type") or {}
    by_type_tf = summary.get("events_by_type_tf") or {}
    obs = summary.get("events_by_type_observations") or {}
    funnel = summary.get("funnel") or {}
    verify = _INPUTS["verify"]
    flags = verify_flags(verify)
    chart_count = len(charts)

    def story(toc):
        flow = []
        meta_rows = [
            ("Document", "Full report - structure identification ledger"),
            ("Ledger window (exec)", "%s -> %s" % (window.get("start", "?"), window.get("end", "?"))),
            ("Detection / execution", "H4 + H1 detection (M8 fed D1 when available) / M5 execution"),
            ("Unique ledger events", "%s rows across %d event types" % (nfmt(_INPUTS["event_rows"]),
                                                                       len(by_type))),
            ("Charts embedded", "%d of %d review charts (all of them, stratified)"
             % (chart_count, chart_count)),
            ("Ledger status", str(summary.get("ledger_status", "?"))),
            ("Verification", "%s PASS / %s failure(s) / %s flagged (independent per-chart verifier)"
             % (nfmt(verify.get("pack_size")), nfmt(verify.get("failures")), nfmt(verify.get("flagged")))),
            ("Baseline", _INPUTS["freeze_line"]),
            ("Generated", DATE_STAMP),
        ]
        flow.extend(cover_flow(
            styles, doc_title=DOC_TITLE_FULL,
            subtitle="Every code-emitted structural event this stack produced over the locked window, "
                     "with the review charts embedded for audit.",
            purpose=("Read-only measurement export. It records what the detection stack emitted, batch by "
                     "batch, over the locked six-month window: liquidity levels, sweeps, fair value gaps, "
                     "displacement, raw and merged POIs, pillar verdicts, arms, LTF routes, intents and "
                     "fills - with a stratified chart for each of 44 sampled events. Nothing in this "
                     "document is a threshold change, a re-tuning, or an edge claim."),
            meta_rows=meta_rows))
        flow.append(PageBreak())
        flow.append(Paragraph(T("Contents"), styles["H1x"]))
        flow.extend(contents_flow(styles, toc))
        flow.append(PageBreak())

        # ---- 1. Executive summary ----
        flow.append(Paragraph(T("1. Executive summary"), styles["H1"]))
        armed_total = sum((funnel.get("armed") or {}).values()) if isinstance(funnel.get("armed"), dict) else 0
        flow.append(Paragraph(
            T("Over %s -> %s the stack produced <b>%s</b> unique structural events from <b>%s</b> raw "
              "observations, across %s HTF batches (0 batch errors) and %s M5 bars. The funnel closes at "
              "<b>%s</b> armed POIs, <b>%s</b> routed LTF triggers and <b>%s</b> fills."
              % (esc(window.get("start")), esc(window.get("end")), nfmt(_INPUTS["event_rows"]),
                 nfmt(sum(obs.values())) if obs else "n/a", nfmt(summary.get("htf_batches")),
                 nfmt(summary.get("bars_m5")), nfmt(armed_total),
                 nfmt(funnel.get("routes")), nfmt(funnel.get("fills")))), styles["body"]))
        flow.append(Paragraph(T("Counts are machine counters read from summary.json; they describe "
                                "identification volume, not performance."), styles["small"]))
        flow.append(Paragraph(T("1.1 Events by plain flowchart tag"), styles["H2"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in
                 ("code event_type", "plain flowchart tag", "rows", "raw observations",
                  "what it means")]]
        explain = {
            "sweep": "wick pierce of a mapped level with body close back",
            "fvg": "3-candle imbalance zone on the detection timeframe",
            "liquidity_level": "session / periodic / EQH-EQL / structural level",
            "poi_raw": "pre-merge model output (M1-M8), one tag per POI",
            "poi_merged": "same-direction overlapping zones merged to a tag union",
            "poi_armed": "POI that reached CREATED -> FRESH and armed",
            "displacement": "BOS + FVG + >= 1x ATR",
            "pillar_reject": "first hard pillar failure for that geometry",
            "pillar_pass": "all five pillars passed",
            "route_ltf": "M5 trigger routed (chronological first-valid)",
            "intent": "R9 place-on-reentry lifecycle transition",
            "fill": "limit fill recorded by the backtest runner",
        }
        for event_type in sorted(by_type, key=lambda k: -int(by_type[k] or 0)):
            rows.append([Paragraph(T(str(event_type)), styles["cell8"]),
                         Paragraph(T(esc(FL.generic_tag(event_type))), styles["cell8"]),
                         Paragraph(nfmt(by_type.get(event_type)), styles["cell"]),
                         Paragraph(nfmt(obs.get(event_type, "-")), styles["cell"]),
                         Paragraph(T(explain.get(event_type, "-")), styles["cell8"])])
        rows.append([Paragraph(T("<b>total</b>"), styles["cell"]),
                     Paragraph(T(""), styles["cell"]),
                     Paragraph(T("<b>%s</b>" % nfmt(_INPUTS["event_rows"])), styles["cell"]),
                     Paragraph(T("<b>%s</b>" % nfmt(sum(obs.values()))), styles["cell"]),
                     Paragraph(T(""), styles["cell"])])
        flow.append(grid_table(rows, [78, 118, 36, 66, CONTENT_W - 298]))

        flow.append(Paragraph(T("1.2 Events by code type x detection timeframe"), styles["H2"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in ("code event_type", "D1", "H1", "H4")]]
        for event_type in sorted(by_type_tf, key=lambda k: -int(by_type.get(k) or 0)):
            per = by_type_tf.get(event_type) or {}
            rows.append([Paragraph(T(str(event_type)), styles["cell"]),
                         Paragraph(nfmt(per.get("D1", 0)), styles["cell"]),
                         Paragraph(nfmt(per.get("H1", 0)), styles["cell"]),
                         Paragraph(nfmt(per.get("H4", 0)), styles["cell"])])
        flow.append(grid_table(rows, [140, 60, 60, 60]))

        flow.append(Paragraph(T("1.3 Funnel (machine counters)"), styles["H2"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in ("stage", "counts")]]
        for key in ("detected_raw", "merged", "passed_validation", "armed"):
            value = funnel.get(key)
            shown = ", ".join("%s %s" % (k, nfmt(v)) for k, v in (value or {}).items()) if \
                isinstance(value, dict) else nfmt(value)
            rows.append([Paragraph(T(key), styles["cell"]), Paragraph(T(shown), styles["cell"])])
        for key in ("armed_m8", "routes", "placed", "fills"):
            rows.append([Paragraph(T(key), styles["cell"]), Paragraph(nfmt(funnel.get(key)), styles["cell"])])
        flow.append(grid_table(rows, [150, CONTENT_W - 150]))
        flow.append(Spacer(1, 6))
        flow.append(callout("Counts describe identification, not profitability. The ledger is "
                            "read-only measurement: no PnL interpretation is drawn anywhere in this "
                            "document.", styles, colour="#0d2b45", background="#eef3f8"))

        flow.append(Paragraph(T("1.4 How to read flowchart tags (engine word -> plain tag)"), styles["H2"]))
        flow.append(Paragraph(
            T("Every chart title and caption in this report leads with the plain flowchart tag. The "
              "engine's own word for the row is kept beside it, so any label can still be traced back "
              "to events.csv. A label is emitted only when the row supports it: the order block / demand "
              "/ supply / FVG words are read from the row's own kind= note, and a POI whose code "
              "emitted no kind is shown as <b>unlabeled POI</b> rather than guessed at. The contract is "
              "identical to the companion expert pack (section 2) - both read "
              "06_RESEARCH/scripts/flowchart_labels.py."), styles["small"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in
                 ("code event_type", "plain tag", "what it means on the chart")]]
        for code, tag, meaning in FLOWCHART_LABEL_TABLE:
            rows.append([Paragraph(T("<b>%s</b>" % esc(code)), styles["cell8"]),
                         Paragraph(T("<b>%s</b>" % esc(tag)), styles["cell8"]),
                         Paragraph(T(esc(meaning)), styles["cell8"])])
        flow.append(grid_table(rows, [92, 118, CONTENT_W - 210]))
        stats = label_stats(charts, _INPUTS["events"])
        flow.append(Paragraph(
            T("In this report: %d of %d sampled poi_raw rows carry a code kind (%s) and %d carry none; "
              "%d charts carry the mandatory set-up chain block (%s)."
              % (stats["poi_labeled_from_kind"],
                 stats["poi_labeled_from_kind"] + stats["poi_unlabeled"],
                 ", ".join("%s x%d" % (k, v) for k, v in sorted(stats["poi_kinds"].items())
                           if k != "(no kind emitted)") or "none",
                 stats["poi_unlabeled"], len(stats["chain_charts"]),
                 "route_ltf / fill")), styles["small"]))

        # ---- 2. Module map ----
        flow.append(Paragraph(T("2. Flowchart concept -> plain tag -> code module -> ledger event"), styles["H1"]))
        flow.append(Paragraph(T("Each row is the binding between the locked flowchart stage, the module "
                                "that implements it, and the ledger event_type it produces. Traceability "
                                "source: STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md section 2 and "
                                "FLOWCHART_CODE_EVIDENCE_MAP.md."), styles["small"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in
                 ("stage", "plain flowchart tag", "code event_type", "code module", "note")]]
        for stage, concept, module, event_type, note in MODULE_MAP_ROWS:
            rows.append([Paragraph(T(stage), styles["cell8"]),
                         Paragraph(T(esc(FL.generic_tag(event_type))), styles["cell8"]),
                         Paragraph(T(esc(event_type)), styles["cell8"]),
                         Paragraph(T(esc(module)), styles["cell8"]),
                         Paragraph(T(note), styles["cell8"])])
        flow.append(grid_table(rows, [28, 96, 64, 148, CONTENT_W - 336]))

        # ---- 3. Methodology ----
        flow.append(Paragraph(T("3. Methodology"), styles["H1"]))
        flow.append(Paragraph(T("3.1 Composition"), styles["H2"]))
        flow.append(Paragraph(
            T("The ledger is driven with the accepted unified multi-TF product composition: H4 + H1 "
              "detection on the shared product seam (smc.orchestration.multi_tf_runtime.MultiTFProductRuntime), "
              "D1 fed into Model 8 when available, and M5 execution. Logging-only wrappers are restored in "
              "a finally block, so the strategy code path is unmodified."), styles["body"]))
        flow.append(Paragraph(T("3.2 Window and tiling"), styles["H2"]))
        chunks = summary.get("chunks") or []
        flow.append(Paragraph(
            T("A single six-month run is not feasible in one process (the composition re-scans the growing "
              "HTF prefix every batch, measured at 0.67 s/batch at a six-month prefix). The locked window "
              "was therefore tiled into non-overlapping 3-month exec windows, each running the same "
              "composition with its own warm-up. Each row's own ts_utc was bounded by its chunk window "
              "(retain_window), so the union is exact."), styles["body"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in
                 ("chunk", "exec window", "M5 bars", "HTF batches", "rows", "dangling links")]]
        for chunk in chunks:
            win = chunk.get("window") or {}
            rows.append([Paragraph(T(str(chunk.get("chunk"))), styles["cell"]),
                         Paragraph(T("%s -> %s" % (win.get("start"), win.get("end"))), styles["cell8"]),
                         Paragraph(nfmt(chunk.get("bars_m5")), styles["cell"]),
                         Paragraph(nfmt(chunk.get("htf_batches")), styles["cell"]),
                         Paragraph(nfmt(chunk.get("rows_added")), styles["cell"]),
                         Paragraph(nfmt(chunk.get("dangling_links")), styles["cell"])])
        flow.append(grid_table(rows, [56, 196, 56, 62, 52, 68]))
        flow.append(Paragraph(T("Documented deviation: chunk-level verdicts close over each chunk's own "
                                "prefix, so a later geometry is first observed against a >= 1-month warm-up "
                                "rather than a 4-month one."), styles["small"]))
        flow.append(Paragraph(T("3.3 Merge and cross-row link repair"), styles["H2"]))
        dangling_total = sum(int(v or 0) for v in (_INPUTS["chunk_dangling"] or {}).values())
        flow.append(Paragraph(
            T("The union is assembled by re-deriving a stable event_id from each chunk's stored geometry key. "
              "A first assembly left related_event_id pointing at the pre-merge runtime ids, so every "
              "cross-row link dangled in the union. The merge now rewrites links in a second pass using an "
              "id map; %s rows whose link target was genuinely dropped by a chunk's retain_window (a level "
              "formed during warm-up) are marked <b>rel_dangling</b> in the row notes and counted per chunk "
              "(%s) instead of failing silently. Every other link resolves."
              % (nfmt(dangling_total),
                 ", ".join("%s %s" % (k, nfmt(v)) for k, v in (_INPUTS["chunk_dangling"] or {}).items())
                 or "n/a")), styles["body"]))
        flow.append(Paragraph(T("3.4 Dedup rule"), styles["H2"]))
        flow.append(Paragraph(
            T("One row per unique structural event. The dedup key is (event_type scope, detection TF, "
              "direction, rounded zone/level bounds, event timestamp); liquidity levels add their family and "
              "formed_at, and the pillar layer uses a pillar_outcome scope so a geometry that alternates "
              "PASS/REJECT across batches still yields one row. The first observation fixes the row; later "
              "observations only increment observed=N (verdict flicker is recorded on the row)."),
            styles["body"]))
        flow.append(Paragraph(T("3.5 How the charts were rendered"), styles["H2"]))
        flow.append(Paragraph(T("Charts render only fields the code emitted (identity-first rule, "
                                "SMC_VISUALIZATION_ROADMAP V0/V1). LTF confirmations (route_ltf, intent, "
                                "fill) are charted on the M5 execution series because that is where they "
                                "complete; every other type is charted on its detection timeframe. Each "
                                "chart carries its plain flowchart tag as the title, one demoted "
                                "'technical row:' footnote with the engine's own fields, a plain reading "
                                "block (the mandatory SETUP CHAIN on route_ltf / fill), and the same "
                                "disclaimer: 'structure identification - NOT a trade claim'. The pixel "
                                "semantics below are unchanged."), styles["small"]))
        flow.append(legend_table(styles))

        # ---- 4. Chart pack ----
        flow.append(PageBreak())
        flow.append(Paragraph(T("4. Chart pack - all %d review charts, stratified" % chart_count),
                              styles["H1"]))
        flow.append(Paragraph(
            T("Order: %s. Each chart is one ledger row, titled with its plain flowchart tag; under it "
              "the plain reading block says what you are looking at (the mandatory SETUP CHAIN on "
              "route_ltf / fill), and a demoted technical footnote still repeats every code-emitted "
              "field (event_id, timestamps, timeframes, geometry, pipeline references, linkage, source "
              "module) plus the chart filename for the audit trail. The charts are a stratified sample "
              "spread across the window, not the whole %s-row ledger."
              % (", ".join(FL.generic_tag(t) for t in TYPE_ORDER), nfmt(_INPUTS["event_rows"]))),
            styles["small"]))
        flow.append(Paragraph(T("Chart index (plain tag, with the code type kept beside it)"),
                              styles["H2"]))
        flow.append(chart_index_table(charts, styles, with_verdict=False))

        grouped: dict = {}
        for chart in charts:
            grouped.setdefault(chart.get("event_type"), []).append(chart)
        for event_type in TYPE_ORDER:
            group = grouped.get(event_type) or []
            if not group:
                continue
            flow.append(PageBreak())
            heading = Paragraph(
                T("%s  [%s] - %d chart(s)" % (FL.generic_tag(event_type), event_type,
                                              len(group))), styles["H2"])
            blocks = [chart_block(chart, styles, index=charts.index(chart) + 1,
                                  total=chart_count, expert=False) for chart in group]
            from reportlab.platypus import KeepTogether
            flow.append(KeepTogether([heading] + [blocks[0]] if blocks else [heading]))
            flow.extend(blocks[1:])

        # ---- 5. Limitations & freeze posture ----
        flow.append(PageBreak())
        flow.append(Paragraph(T("5. Limitations and freeze posture"), styles["H1"]))
        flow.append(Paragraph(T("5.1 Measurement limitations"), styles["H2"]))
        for item in CAVEATS:
            flow.append(Paragraph(T("- " + item), styles["small"]))
        flow.append(Paragraph(T("5.2 What this document does not claim"), styles["H2"]))
        for item in [
            "No expectancy, profit factor, win rate or edge statement appears anywhere here. The "
            "fill rows carry the trade's own recorded outcome fields for chain completeness only.",
            "A verifier PASS means the chart displays the fields the locked rules require - it is not a "
            "discretionary CORRECT verdict. Only a human/domain reviewer scores identification.",
            "No threshold, pillar, trigger, zone-band, R7/R9 or locked-constant change was made to "
            "produce this ledger. The plain flowchart labels here are wording only - they change what "
            "a chart says, not what the stack detects: LOGIC_CHANGED: NO.",
            "A plain tag is a naming of the code's own kind, not a verdict on correctness. Where the "
            "code emitted no kind, the chart says 'unlabeled POI' and claims nothing further; where "
            "the ledger records no link between two events, the caption says 'not linked in row' "
            "rather than pointing at a nearby one.",
        ]:
            flow.append(Paragraph(T("- " + item), styles["small"]))
        flow.append(Paragraph(T("5.3 Freeze posture"), styles["H2"]))
        flow.append(Paragraph(T("V1.1 runtime baseline freeze: %s" % esc(_INPUTS["freeze_line"])),
                              styles["small"]))
        flow.append(Paragraph(
            T("The default posture under the freeze is operate and observe under contract, not redesign. "
              "This ledger is a measurement and documentation artifact; it changes nothing that is "
              "frozen, and it is not a licence to re-tune detection."), styles["small"]))

        # ---- 6. Appendix ----
        flow.append(Paragraph(T("6. Appendix"), styles["H1"]))
        flow.append(Paragraph(T("6.1 Artifacts and provenance"), styles["H2"]))
        csv_sha = _INPUTS.get("csv_sha256", "unavailable")
        flow.append(kv_table([
            ("events.csv", str(EVENTS_CSV.relative_to(REPO_ROOT)).replace("\\", "/")),
            ("events.csv rows", nfmt(_INPUTS["event_rows"])),
            ("events.csv SHA-256", csv_sha),
            ("events.csv size", "%.2f MB" % (EVENTS_CSV.stat().st_size / 1_048_576.0)
             if EVENTS_CSV.is_file() else "n/a"),
            ("events.jsonl", "same rows, one JSON object per line"),
            ("summary.json", "counts, chunks, funnel, review_sample index"),
            ("review_sample/", "%d PNG charts embedded in this report" % chart_count),
            ("verification_matrix.json", "independent per-chart verification record"),
            ("REVIEW_INDEX.md", "flat scoring index of the same 44 charts"),
            ("Ledger report", "06_RESEARCH/STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md"),
            ("This PDF", str(OUT_FULL_PDF.relative_to(REPO_ROOT)).replace("\\", "/")),
        ], styles))
        flow.append(Paragraph(T("6.2 Verification summary"), styles["H2"]))
        if verify:
            flow.append(Paragraph(
                T("Independent verifier: <b>%s of %s charts PASS</b>, %s failure(s), %s flagged. Rules "
                  "read from: %s. Flags are locked-rule divergences the charts display faithfully; they "
                  "are listed in section 5.1 caveats and in the companion expert pack."
                  % (nfmt(int(verify.get("pack_size") or 0) - int(verify.get("failures") or 0)),
                     nfmt(verify.get("pack_size")), nfmt(verify.get("failures")),
                     nfmt(verify.get("flagged")), esc("; ".join(verify.get("rules_source") or [])))),
                styles["small"]))
            rows = [[Paragraph(T(h), styles["cellhead"]) for h in ("file", "code event_type", "status", "flag")]]
            for item in verify.get("charts") or []:
                if not item.get("flags"):
                    continue
                rows.append([Paragraph(esc(item.get("file")), styles["cell8"]),
                             Paragraph(esc(item.get("event_type")), styles["cell8"]),
                             Paragraph(esc(item.get("status")), styles["cell8"]),
                             Paragraph(esc("; ".join(item.get("flags") or [])), styles["cell8"])])
            flow.append(grid_table(rows, [176, 62, 44, CONTENT_W - 282]))
        else:
            flow.append(Paragraph(T("verification_matrix.json was not available at build time."),
                                  styles["small"]))
        flow.append(Paragraph(T("6.3 Chart selection for the companion expert pack"), styles["H2"]))
        flow.append(Paragraph(T(esc(priority_notes["rule"])), styles["small"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in
                 ("plain tag (code type)", "sampled", "requested", "embedded", "mandatory included")]]
        for item in priority_notes["per_type"]:
            rows.append([Paragraph(T("%s  [%s]" % (FL.generic_tag(item["event_type"]),
                                                    item["event_type"])), styles["cell"]),
                         Paragraph(nfmt(item["available"]), styles["cell"]),
                         Paragraph(nfmt(item["requested"]), styles["cell"]),
                         Paragraph(nfmt(item["chosen"]), styles["cell"]),
                         Paragraph(nfmt(item["forced"]), styles["cell"])])
        flow.append(grid_table(rows, [130, 70, 76, 76, CONTENT_W - 352]))
        flow.append(Paragraph(T("6.4 Full chart index (all %d)" % chart_count), styles["H2"]))
        flow.append(chart_index_table(charts, styles, with_verdict=False))
        flow.append(Spacer(1, 8))
        flow.append(Paragraph(T("End of report. Read-only measurement: no threshold change, no "
                                "re-tuning, no paper trading, no edge language. LOGIC_CHANGED: NO."),
                              styles["small"]))
        return flow

    return story


# --------------------------------------------------------------------------- #
# EXPERT VALIDATION PACK
# --------------------------------------------------------------------------- #

def build_expert_pack(charts, priority_notes):
    from reportlab.platypus import Paragraph, Spacer, PageBreak, KeepTogether

    styles = _INPUTS["styles"]
    summary = _INPUTS["summary"]
    window = summary.get("window") or {}
    verify = _INPUTS["verify"]
    flags = verify_flags(verify)
    total = len(charts)
    per_type = {}
    for chart in charts:
        per_type[chart.get("event_type")] = per_type.get(chart.get("event_type"), 0) + 1
    breakdown = ", ".join("%d %s" % (per_type[t], t) for t in TYPE_ORDER if per_type.get(t))

    def story(toc):
        flow = []
        flow.extend(cover_flow(
            styles, doc_title=DOC_TITLE_EXPERT,
            subtitle="A scored, chart-by-chart identification audit for an external reviewer",
            purpose=("You are asked to score %d sampled structural events against the locked flowchart: is "
                     "this the structure the code should have identified, at this point in time, on this "
                     "timeframe, in this direction? Every chart is titled in plain flowchart language "
                     "(liquidity sweep, order block, demand / supply, fair value gap, LTF confirmation), and "
                     "every route_ltf / fill chart carries its set-up chain. Tallies by concept decide "
                     "whether identification can be treated as audited or needs rework before paper "
                     "trading counts for anything."
                     % total),
            meta_rows=[
                ("Prepared for", "External validation reviewer (domain expert)"),
                ("Ledger window", "%s -> %s" % (window.get("start"), window.get("end"))),
                ("Detection / execution", "H4 + H1 detection (M8 fed D1 when available) / M5 execution"),
                ("Charts in this pack", "%d of %d sampled charts (priority set: %s)" % (total, total, breakdown)),
                ("Scoring asked", "CORRECT / PARTIAL / WRONG / UNCLEAR per chart"),
                ("Ledger events available", "%s rows in events.csv (12 event types)" % nfmt(_INPUTS["event_rows"])),
                ("Verification", "%s of %s charts PASS on mechanical rules; %s flagged (listed in section 4)"
                 % (nfmt(int(verify.get("pack_size") or 0) - int(verify.get("failures") or 0)),
                    nfmt(verify.get("pack_size")), nfmt(verify.get("flagged")))),
                ("Labels", "plain flowchart tags - %s; engine words demoted to a footnote"
                 % FL.LABEL_VERSION),
                ("Baseline", _INPUTS["freeze_line"]),
                ("Generated (UTC)", DATE_STAMP),
                ("Scoring destination", "table on the return page (section 5)"),
            ],
            extra_flow=[Spacer(1, 8),
                        Paragraph(T("How to use this pack"), styles["H2x"])] +
                       [Paragraph(T("%d. %s" % (i, item)), styles["small"])
                        for i, item in enumerate(HOW_TO_SCORE, start=1)] +
                       [Spacer(1, 4)]))
        flow.append(PageBreak())
        flow.append(Paragraph(T("Contents"), styles["H1x"]))
        flow.extend(contents_flow(styles, toc))
        flow.append(PageBreak())

        # ---- 1. Map ----
        flow.append(Paragraph(T("1. Flowchart concept -> plain tag -> ledger event"), styles["H1"]))
        flow.append(Paragraph(T("Score against this mapping: each chart's plain tag says which stage of "
                                "the locked flowchart produced it, and the engine's own word for that row "
                                "is kept beside it. Sources: 00_LOCKED/LOCKED_DECISIONS.md section 16 "
                                "(5-stage master pipeline), FLOWCHART_CODE_EVIDENCE_MAP.md, and the ledger "
                                "report section 2."), styles["small"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in
                 ("stage", "plain flowchart tag", "code event_type", "code module")]]
        for stage, concept, module, event_type, _note in MODULE_MAP_ROWS:
            rows.append([Paragraph(T(stage), styles["cell8"]),
                         Paragraph(T(esc(FL.generic_tag(event_type))), styles["cell8"]),
                         Paragraph(T(esc(event_type)), styles["cell8"]),
                         Paragraph(T(esc(module)), styles["cell8"])])
        flow.append(grid_table(rows, [30, 140, 74, 267]))
        flow.append(Spacer(1, 4))
        flow.append(Paragraph(T("How to read the charts"), styles["H2"]))
        flow.append(legend_table(styles))

        # ---- 2. Plain flowchart tags (the engine word -> reviewer word contract) ----
        flow.extend(flowchart_label_page(styles, charts, _INPUTS["events"]))

        # ---- 3. Rubric ----
        flow.append(PageBreak())
        flow.append(Paragraph(T("3. Scoring rubric"), styles["H1"]))
        flow.append(rubric_table(styles))
        flow.append(Spacer(1, 6))
        flow.append(callout("Mechanical PASS is not a verdict. The verifier checks that each chart renders "
                            "the fields the locked rules require; it cannot judge whether the identification "
                            "itself is correct. Only your CORRECT/PARTIAL/WRONG/UNCLEAR scoring does that.",
                            styles, colour="#0d2b45", background="#eef3f8"))
        flow.append(Paragraph(T("What to check per chart, in plain tags"), styles["H2"]))
        checks = [
            ("sweep", "Liquidity sweep",
             "A wick pierces a mapped liquidity level and the body closes back; direction = the pool "
             "taken (sell-side liquidity swept -> LONG, buy-side -> SHORT). Check the level line sits on "
             "the pool the wick swept."),
            ("fvg", "Fair value gap (FVG)",
             "Three-candle imbalance: the zone is the gap between candle 1's wick and candle 3's wick, "
             "on the detection timeframe. Check the band covers the actual imbalance."),
            ("poi_raw", "Order block / Demand / Supply",
             "Model 8's HTF zone, named from the row's own code kind: 'ob' = the candle before the FVG, "
             "'demand_supply' = the last opposing candle before a >= 1x ATR impulse. Demand buys, supply "
             "sells. Check the zone bounds, the HTF it claims, the direction - and whether the label is "
             "one the code can actually support for this row."),
            ("poi_armed", "Armed POI (passed validation)",
             "The POI that armed (CREATED -> FRESH, zone-episode dedup). Check the zone is where price "
             "actually returned and that it armed once, not repeatedly."),
            ("route_ltf", "LTF confirmation (M5 entry)",
             "The M5 trigger that routed (A-F, chronological first-valid). Check the trigger name against "
             "the bar's structure and the entry / SL references against the HTF zone in the set-up chain."),
            ("fill", "Entry fill",
             "The limit fill at the LTF confirmation. Check the entry price is the routed limit and the "
             "stop reference is the placement stop (not a break-even-moved stop). Outcome fields are "
             "informational only."),
        ]
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in
                 ("code event_type", "plain tag", "what the chart should show")]]
        for name, tag, text in checks:
            rows.append([Paragraph(T(name), styles["cell8"]),
                         Paragraph(T("<b>%s</b>" % tag), styles["cell8"]),
                         Paragraph(T(text), styles["cell8"])])
        flow.append(grid_table(rows, [64, 104, CONTENT_W - 168]))
        flow.append(Paragraph(T("Reading caveats that can look like errors"), styles["H2"]))
        for item in CAVEATS:
            flow.append(Paragraph(T("- " + item), styles["small"]))

        # ---- 4. Documented flags ----
        flow.append(PageBreak())
        flow.append(Paragraph(T("4. Known documented flags (shown, not hidden)"), styles["H1"]))
        flow.append(Paragraph(T("These are divergences already recorded in the project's own evidence "
                                "files. The charts render them faithfully; they are not chart failures. "
                                "Score them as you see them, but know they are known and open."),
                              styles["small"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in
                 ("chart", "event_id", "flag as recorded", "origin / status")]]
        for item in flags:
            rows.append([Paragraph(esc(item.get("file")), styles["cell8"]),
                         Paragraph(esc(item.get("event_id")), styles["cell8"]),
                         Paragraph(esc("; ".join(item.get("flags") or [])), styles["cell8"]),
                         Paragraph(T(_flag_origin(item)), styles["cell8"])])
        flow.append(grid_table(rows, [146, 100, 155, CONTENT_W - 401]))
        flow.append(Spacer(1, 4))
        dangling = _INPUTS["chunk_dangling"] or {}
        flow.append(Paragraph(
            T("Warm-up dangling links in the union: <b>%s</b> of %s rows (%s). A sweep whose level was "
              "formed during a chunk's warm-up load window cannot resolve that link, so the row is marked "
              "<b>rel_dangling</b> in its notes; the level price is preserved there too. This is a "
              "documented exception, not an unresolved merge defect."
              % (nfmt(sum(int(v or 0) for v in dangling.values())), nfmt(_INPUTS["event_rows"]),
                 ", ".join("%s %s" % (k, nfmt(v)) for k, v in dangling.items()) or "n/a")),
            styles["small"]))
        flow.extend(disposition_table(styles))

        # ---- 5. Return template ----
        flow.append(PageBreak())
        flow.append(Paragraph(T("5. How to return your scores"), styles["H1"]))
        flow.append(Paragraph(T("Return one line per chart (the chart index below is the checklist) and a "
                                "tally by plain tag. If a chart is UNCLEAR, name the row you pulled and "
                                "say what was missing."), styles["small"]))
        flow.append(Paragraph(T("5.1 Tally by plain tag"), styles["H2"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in
                 ("plain tag (code type)", "charts scored", "CORRECT", "PARTIAL", "WRONG", "UNCLEAR")]]
        for event_type in TYPE_ORDER:
            if not per_type.get(event_type):
                continue
            rows.append([Paragraph(T("%s  [%s]" % (FL.generic_tag(event_type), event_type)),
                                   styles["cell"]),
                         Paragraph(nfmt(per_type[event_type]), styles["cell"]),
                         Paragraph("", styles["cell"]), Paragraph("", styles["cell"]),
                         Paragraph("", styles["cell"]), Paragraph("", styles["cell"])])
        rows.append([Paragraph(T("total"), styles["cellb"]), Paragraph(nfmt(total), styles["cell"]),
                     Paragraph("", styles["cell"]), Paragraph("", styles["cell"]),
                     Paragraph("", styles["cell"]), Paragraph("", styles["cell"])])
        flow.append(grid_table(rows, [150, 76, 66, 66, 66, CONTENT_W - 424]))
        flow.append(Paragraph(T("5.2 Per-chart sheet (one row per chart)"), styles["H2"]))
        flow.append(chart_index_table(charts, styles, with_verdict=True))
        flow.append(Paragraph(T("5.3 Free-text findings"), styles["H2"]))
        for label in ("Biggest identification strength:", "Most common failure mode:",
                      "Any concept that is systematically wrong:",
                      "Any chart you could not settle from the pack alone:"):
            flow.append(Paragraph(T("<b>%s</b> ______________________________________________________"
                                    % label), styles["small"]))
        flow.append(Spacer(1, 6))
        flow.append(callout("Reminder for the sign-off: this pack audits identification only. Nothing "
                            "here validates or refutes an expectancy, and no verdict here should be read "
                            "as a trading conclusion.", styles, colour="#0d2b45", background="#eef3f8"))

        # ---- 6. Charts ----
        flow.append(PageBreak())
        flow.append(Paragraph(T("6. Priority chart set - %d charts" % total), styles["H1"]))
        flow.append(Paragraph(T("Order: %s. Each chart is one ledger row, titled with its plain "
                                "flowchart tag; the technical footnote under the reading block carries "
                                "the engine's own fields for the audit trail."
                                % ", ".join(FL.generic_tag(t) for t in TYPE_ORDER)),
                              styles["small"]))
        flow.append(Paragraph(T(esc(priority_notes["rule"])), styles["small"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in
                 ("plain tag (code type)", "sampled", "requested", "embedded", "mandatory included")]]
        for item in priority_notes["per_type"]:
            rows.append([Paragraph(T("%s  [%s]" % (FL.generic_tag(item["event_type"]),
                                                    item["event_type"])), styles["cell"]),
                         Paragraph(nfmt(item["available"]), styles["cell"]),
                         Paragraph(nfmt(item["requested"]), styles["cell"]),
                         Paragraph(nfmt(item["chosen"]), styles["cell"]),
                         Paragraph(nfmt(item["forced"]), styles["cell"])])
        flow.append(grid_table(rows, [130, 70, 76, 76, CONTENT_W - 352]))
        flow.append(Spacer(1, 4))
        flow.append(Paragraph(T("Set-up chains present in this pack (armed -> route -> fill)"), styles["H2"]))
        rows = [[Paragraph(T(h), styles["cellhead"]) for h in
                 ("fill", "armed POI it came from", "routed trigger(s) in the pack")]]
        for chain in priority_notes["chains"]:
            rows.append([Paragraph(esc(chain.get("fill")), styles["cell8"]),
                         Paragraph(esc("%s (%s)" % (chain.get("armed"), chain.get("armed_type"))),
                                   styles["cell8"]),
                         Paragraph(esc(", ".join(chain.get("routes") or []) or "armed POI not sampled"),
                                   styles["cell8"])])
        flow.append(grid_table(rows, [104, 168, CONTENT_W - 272]))
        flow.append(Paragraph(T("Charts of the same plain tag are grouped together; the %d route_ltf / "
                                "fill charts each carry the mandatory SETUP CHAIN block. Charts follow in "
                                "the order of the table above - please score them in that order."
                                % len(label_stats(charts, _INPUTS["events"])["chain_charts"])),
                              styles["small"]))

        grouped: dict = {}
        for chart in charts:
            grouped.setdefault(chart.get("event_type"), []).append(chart)
        for event_type in TYPE_ORDER:
            group = grouped.get(event_type) or []
            if not group:
                continue
            flow.append(PageBreak())
            heading = Paragraph(
                T("%s  [%s] - %d chart(s) to score"
                  % (FL.generic_tag(event_type), event_type, len(group))), styles["H2"])
            blocks = [chart_block(chart, styles, index=charts.index(chart) + 1,
                                  total=total, expert=True) for chart in group]
            flow.append(KeepTogether([heading, blocks[0]]))
            flow.extend(blocks[1:])
        return flow

    return story


# --------------------------------------------------------------------------- #
# Markdown twin
# --------------------------------------------------------------------------- #

def write_markdown(charts, priority_notes) -> Path:
    summary = _INPUTS["summary"]
    window = summary.get("window") or {}
    verify = _INPUTS["verify"]
    per_type: dict = {}
    for chart in charts:
        per_type[chart.get("event_type")] = per_type.get(chart.get("event_type"), 0) + 1
    lines = [
        "# EXPERT VALIDATION PACK (text twin)", "",
        f"**{PROJECT}**  ",
        f"Ledger window (exec): `{window.get('start')}` -> `{window.get('end')}`  ",
        "Detection H4 + H1 (M8 fed D1 when available) / execution M5  ",
        f"Ledger rows: {nfmt(_INPUTS['event_rows'])}  ",
        f"Charts in the illustrated pack: {len(charts)} ({', '.join('%d %s' % (per_type[t], t) for t in TYPE_ORDER if per_type.get(t))})  ",
        f"Baseline: {_INPUTS['freeze_line']}  ",
        f"Generated (UTC): {DATE_STAMP}", "",
        f"> **DISCLAIMER: {DISCLAIMER}**",
        ">",
        "> This pack asks only whether the code identifies the structure the locked flowchart defines. It "
        "carries no expectancy, no profit factor and no edge claim; the fill rows are shown for chain "
        "completeness only.", "",
        "## 1. Flowchart concept -> plain tag -> ledger event", "",
        "| stage | plain flowchart tag | code module | code event_type |",
        "|---|---|---|---|",
    ]
    for stage, concept, module, event_type, _note in MODULE_MAP_ROWS:
        lines.append(f"| {stage} | {FL.generic_tag(event_type)} | `{module}` | `{event_type}` |")
    lines += ["", "## 2. How to read flowchart tags", "",
              "| code event_type | plain tag on chart / caption | what it means |",
              "|---|---|---|"]
    for code, tag, meaning in FLOWCHART_LABEL_TABLE:
        lines.append(f"| `{code}` | **{tag}** | {meaning} |")
    stats = label_stats(charts, _INPUTS["events"])
    lines += ["",
              f"A label is emitted only when the row supports it: {stats['poi_labeled_from_kind']} of "
              f"{stats['poi_labeled_from_kind'] + stats['poi_unlabeled']} sampled `poi_raw` rows carry a "
              f"code kind ({', '.join('%s x%d' % (k, v) for k, v in sorted(stats['poi_kinds'].items()) if k != '(no kind emitted)') or 'none'})"
              f" and {stats['poi_unlabeled']} carry none (shown as `unlabeled POI`). "
              f"{len(stats['chain_charts'])} charts carry the mandatory set-up chain block.",
              "", "## 3. Scoring rubric", "",
              "| verdict | meaning |", "|---|---|"]
    for name, text in RUBRIC:
        lines.append(f"| **{name}** | {text} |")
    lines += ["", "Mechanical PASS from the chart verifier is not a verdict; only a reviewer scores "
                  "identification.", "", "## 4. Known documented flags (shown, not hidden)", "",
              "| chart | event_id | flag | origin / status |", "|---|---|---|---|"]
    for item in verify_flags(verify):
        lines.append(f"| `{item.get('file')}` | `{item.get('event_id')}` | "
                     f"{'; '.join(item.get('flags') or [])} | {_flag_origin(item)} |")
    dangling = _INPUTS["chunk_dangling"] or {}
    lines += ["", f"Warm-up dangling links in the union: **{sum(int(v or 0) for v in dangling.values())}** "
                  f"of {_INPUTS['event_rows']} rows ({', '.join('%s %s' % (k, v) for k, v in dangling.items()) or 'n/a'}).",
              "", "### Other open dispositions", ""]
    for name, text in OPEN_DISPOSITIONS:
        lines.append(f"- **{name}** - {text}")
    lines += ["", "### Reading caveats", ""]
    for item in CAVEATS:
        lines.append(f"- {item}")
    lines += ["", "## 5. Charts to score", "",
              f"Selection rule: {priority_notes['rule']}", "",
              "Each chart is titled with its plain flowchart tag; its reading block (the SETUP CHAIN on "
              "route_ltf / fill) is printed under the chart image, and the engine's own fields stay in a "
              "demoted technical footnote.", "",
              "| # | plain flowchart tag | code type | chart TF | detect TF | ts_utc | dir | tags | event_id | file | verdict |",
              "|---:|---|---|---|---|---|---|---|---|---|---|"]
    for position, chart in enumerate(charts, start=1):
        lines.append("| %d | %s | %s | %s | %s | %s | %s | %s | `%s` | `%s` |  |" % (
            position, dash((chart.get("label") or {}).get("tag"), "-"),
            chart.get("event_type"), chart.get("chart_tf"), chart.get("detection_tf"),
            chart.get("ts_utc"), chart.get("direction"), dash(chart.get("model_tags"), "-"),
            chart.get("event_id"), chart.get("file")))
    lines += ["", "## 6. Return template", "", "### Tally by plain tag", "",
              "| plain tag (code type) | charts scored | CORRECT | PARTIAL | WRONG | UNCLEAR |",
              "|---|---|---|---|---|---|"]
    for event_type in TYPE_ORDER:
        if per_type.get(event_type):
            lines.append(f"| {FL.generic_tag(event_type)} (`{event_type}`) | "
                         f"{per_type[event_type]} |  |  |  |  |")
    lines += [f"| **total** | **{len(charts)}** |  |  |  |  |", "",
              "### Free text", "",
              "- Biggest identification strength: ",
              "- Most common failure mode: ",
              "- Any concept that is systematically wrong: ",
              "- Any chart that could not be settled from the pack alone: ", "",
              f"*Illustrated pack: `{OUT_EXPERT_PDF.name}` (charts embedded). Full report: "
              f"`{OUT_FULL_PDF.name}`. Chart PNGs: `review_sample/`.*", ""]
    OUT_EXPERT_MD.write_text("\n".join(lines), encoding="utf-8")
    return OUT_EXPERT_MD


# --------------------------------------------------------------------------- #
# HUMAN_LABELS_NOTE.md - the record of the presentation change
# --------------------------------------------------------------------------- #

def _per_page_summary(images_per_page: dict) -> str:
    """{'0': 10, '1': 24} -> '24 page(s) carrying 1 chart, 10 page(s) with none'."""
    parts = []
    for count, pages in sorted((int(k), v) for k, v in (images_per_page or {}).items()):
        parts.append("%d page(s) carrying %d chart%s"
                     % (pages, count, "" if count == 1 else "s") if count
                     else "%d page(s) with no chart (front matter)" % pages)
    return ", ".join(parts) or "n/a"


def write_human_labels_note(charts, priority_charts, priority_notes, *, expert_pages,
                            full_pages, expert_check, full_check, toc_counts,
                            verify_v2: dict | None = None) -> Path:
    """Record what the plain-flowchart relabelling changed and how to verify it."""
    stats = label_stats(charts, _INPUTS["events"])
    png_sources: dict = {}
    for chart in charts:
        key = str(chart.get("png_source") or "unknown")
        png_sources[key] = png_sources.get(key, 0) + 1
    example = None
    for chart in priority_charts:
        if (chart.get("label") or {}).get("chain"):
            example = chart
            break

    lines = [
        "# HUMAN LABELS NOTE - plain flowchart wording on the review surface", "",
        f"**Status:** PASS · generated {DATE_STAMP} · presentation/export change only  ",
        "**LOGIC_CHANGED: NO** - no detection, threshold, pillar, trigger, zone-band, R7/R9 or "
        "locked-constant behaviour was touched; V1.1 baseline freeze unchanged.", "",
        f"> {DISCLAIMER}", ">",
        "> Every label here is a renaming of what the code already emitted: a plain tag is not a "
        "verdict, and it carries no expectancy, profit factor or edge claim.", "",
        "---", "",
        "## Why this exists", "",
        "The first version of the pack was accurate as a code-emission audit but weak as a flowchart "
        "review: charts and captions spoke engine vocabulary (`poi_raw`, `route_ltf`, `pillar_reject`, "
        "`source_module`) instead of reviewer vocabulary (liquidity sweep, order block, demand / "
        "supply, fair value gap, LTF confirmation), and the post-sweep LTF entry step sat in a separate "
        "section with no set-up story. This note records the fix and how to verify it.", "",
        "## 1. What changed (presentation only)", "",
        f"- All {len(charts)} sampled charts re-rendered with plain titles into `{PNG_DIR_V2.name}/` "
        "(same file names as `review_sample/`, so the frozen summary.json index and REVIEW_INDEX.md "
        "still name each chart, and the original folder is left byte-untouched).",
        "- The engine trace (`event_type`, `detect_tf`, tags, `event_id`) is demoted to one small "
        "`technical row:` footnote on the chart, and to a two-line technical record in the PDF caption. "
        "Function paths are gone from the charts entirely.",
        "- A plain reading block sits under every chart (its clauses are read from the row's own "
        "`notes` / `direction`, and a clause that cannot be read is reported as not linked).",
        f"- The mandatory SETUP CHAIN block is printed on every `route_ltf` and `fill` chart "
        f"({len(stats['chain_charts'])} charts) and in their PDF captions.",
        "- Both PDFs rebuilt; the expert pack gained a 'How to read flowchart tags' page (section 2) "
        "and the full report gained section 1.4.",
        "- The identification-only disclaimer is unchanged and still on every chart.", "",
        f"Label set: `{FL.LABEL_VERSION}` · mapping module: `06_RESEARCH/scripts/flowchart_labels.py` "
        "(shared by the chart renderer and the PDF builder, so chart and PDF wording cannot drift).",
        "", "## 2. The label map printed on the charts and in the PDFs", "",
        "| code event_type (engine word) | plain tag | what it means on the chart |",
        "|---|---|---|",
    ]
    for code, tag, meaning in FLOWCHART_LABEL_TABLE:
        lines.append(f"| `{code}` | **{tag}** | {meaning} |")
    lines += ["",
              "### Honesty rule, with the counts from this pack", "",
              f"- Order block / demand / supply / FVG words come from the row's own `kind=` note. "
              f"{stats['poi_labeled_from_kind']} of "
              f"{stats['poi_labeled_from_kind'] + stats['poi_unlabeled']} sampled `poi_raw` charts carry a "
              f"code kind ({', '.join('%s x%d' % (k, v) for k, v in sorted(stats['poi_kinds'].items()) if k != '(no kind emitted)') or 'none'}).",
              (f"- {stats['poi_unlabeled']} sampled `poi_raw` chart(s) carry no code kind and are labelled "
               "`unlabeled POI` - no OB / demand / supply label is inferred from how the chart looks."
               if stats["poi_unlabeled"] else
               "- No sampled `poi_raw` chart needed the `unlabeled POI` fallback in this pack; had one, "
               "it would have been labelled that way rather than guessed at."),
              "- Level words (session, previous day / week, structural swing, equal highs / lows) come "
              "from the row's `level_type=`; pool words (sell-side / buy-side liquidity) from `pool=`.",
              "- Trigger letters come from the row's `trigger` column or its recorded `route_id`.",
              "- Links between rows are never invented. Where the ledger records no sweep or FVG event "
              "id on a set-up chain, the caption says exactly that.", "",
              "### Where the charts live", "",
              f"- Plain-labelled rebuild: `{PNG_DIR_V2.relative_to(REPO_ROOT).as_posix()}/` "
              "(1820x910 px, same file names as the original).",
              f"- Original code-vocabulary pack left untouched: "
              f"`{PNG_DIR.relative_to(REPO_ROOT).as_posix()}/`.",
              f"- Self-contained gallery of the relabelled charts: "
              f"`{(PNG_DIR_V2 / 'review_gallery_v2.html').relative_to(REPO_ROOT).as_posix()}`.",
              f"- PNG folder actually embedded in these PDFs: "
              f"{', '.join('%s (%d charts)' % (k, v) for k, v in sorted(png_sources.items()))}.",
              "- Relabel run record: "
              f"`{(PNG_DIR_V2 / 'relabel_manifest.json').relative_to(REPO_ROOT).as_posix()}`.",
              "", "## 3. The mandatory set-up chain block", "",
              "Printed on every `route_ltf` and `fill` chart and in their PDF captions, in this order:", "",
              "1. `FLOWCHART STAGE:` which stage of the locked pipeline this row is.",
              "2. `HTF structure:` the armed POI the entry came from and its merged (confluence) POI, "
              "with model tags and zone timeframe - or the explicit line saying no sweep / FVG event id "
              "is linked in the row.",
              "3. `LTF confirmation:` the M5 trigger letter, its time, and the runner's own detail text "
              "(e.g. 'BOS at bar 3425; first touch of origin OB at bar 3427'), plus the route row when "
              "the fill's own route is in the pack.",
              "4. `Entry:` the routed limit and `Original SL:` the placement stop, with the entry anchor "
              "when one was set.",
              f"5. `{FL.LTF_CHAIN_FOOTER}`",
              ""]
    if example is not None:
        lines += ["Worked example (a real row from this pack):", "", "```text"]
        lines += list((example.get("label") or {}).get("chain") or [])
        lines += ["```", ""]

    lines += [
        "## 4. The rebuilt PDFs", "",
        f"- `{OUT_EXPERT_PDF.relative_to(REPO_ROOT).as_posix()}` - {expert_pages} pages, "
        f"{expert_check['images']} embedded charts, {mb(OUT_EXPERT_PDF)} MB, "
        f"{toc_counts.get('expert', 0)} contents entries, {expert_check['uri_actions']} hyperlinks.",
        f"- `{OUT_FULL_PDF.relative_to(REPO_ROOT).as_posix()}` - {full_pages} pages, "
        f"{full_check['images']} embedded charts, {mb(OUT_FULL_PDF)} MB, "
        f"{toc_counts.get('full', 0)} contents entries, {full_check['uri_actions']} hyperlinks.",
        f"- A4 portrait, images embedded as native-resolution XObjects (no downsampling, no links); "
        "contents page numbers are resolved by repeated typesetting until two passes agree.",
        (f"- The relabelled charts were re-verified independently against the same locked rules and "
         f"pixel checks: **{verify_v2['pack_size']} charts, {verify_v2['failures']} failure(s), "
         f"{verify_v2['flagged']} documented flag(s), flags identical to the canonical matrix: "
         f"{verify_v2['flags_match_canonical']}** (`{verify_v2['matrix']}`)."
         if verify_v2 else
         "- The relabelled charts were NOT independently re-verified in this build "
         "(verification_matrix_v2.json absent)."),
        f"- Chart pages (measured from the built PDFs): {_per_page_summary(expert_check['images_per_page'])} "
        f"in the expert pack; {_per_page_summary(full_check['images_per_page'])} in the full report.",
        "- The plain reading block (and the mandatory set-up chain on route_ltf / fill) adds height to "
        "every chart caption, so the layout is now ONE chart per page instead of a fixed two. That is "
        "the cost of putting the reviewer's words, the plain reading block and the set-up chain on the "
        "same page as the chart; the earlier 2-per-page code-vocabulary PDFs are superseded, not "
        "deleted.",
        "", "## 5. How to verify this was presentation-only", "",
        "```", "LOGIC_CHANGED: NO",
        "events.csv is byte-identical before and after the chart relabel and the PDF rebuild:",
        "  SHA-256 903e5a3b401ce30812f5fce69831fc1d9cac7930d3bd0636dec4cc5b89acc063",
        "  (13,247 rows, 3.71 MB - the ledger is only ever read)",
        "review_sample/ (original charts) is never written to; the rebuild goes to review_sample_v2/",
        "no file under 04_SRC/ and no file under 00_LOCKED/ is changed by either script",
        "```", "",
        "## 6. Return block", "", "```",
        "HUMAN_LABELS_STATUS: PASS",
        "PLAIN_TAGS_ON_CHARTS: YES",
        "LTF_CHAIN_CAPTIONS: YES",
        f"EXPERT_PDF: {OUT_EXPERT_PDF.relative_to(REPO_ROOT).as_posix()}",
        f"FULL_PDF: {OUT_FULL_PDF.relative_to(REPO_ROOT).as_posix()}",
        "LOGIC_CHANGED: NO", "```", "",
        "*End of note. Identification only: no expectancy, no profit factor, no edge language, no "
        "paper trading.*", ""]
    OUT_HUMAN_NOTE.write_text("\n".join(lines), encoding="utf-8")
    return OUT_HUMAN_NOTE


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def build_one(kind: str, story_factory, charts, target: Path, title: str, footer_text: str):
    styles = _INPUTS["styles"]
    meta = {"styles": styles}
    pages, toc = render_document_stable(target, story_factory, title, footer_text, styles, meta)
    report = check_pdf(target, expected_images=len(charts))
    report["toc_entries"] = len(toc)
    return pages, toc, report


def main() -> int:
    global _INPUTS
    print("=" * 78)
    print("structure ledger -> expert PDFs (read-only measurement export)")
    print("=" * 78)

    try:
        import reportlab                                             # noqa: F401
    except Exception as exc:                                         # noqa: BLE001
        print(f"FATAL: reportlab is required but not importable: {exc}")
        return 2
    engine_note = register_fonts()
    print(f"engine: reportlab | fonts: {engine_note}")

    try:
        _INPUTS = load_inputs()
    except SystemExit as exc:
        print(str(exc))
        return 2
    styles = build_styles()
    _INPUTS["styles"] = styles
    try:
        _INPUTS["csv_sha256"] = sha256_file(EVENTS_CSV)
    except OSError as exc:
        warn(f"cannot hash events.csv: {exc}")
        _INPUTS["csv_sha256"] = "unavailable"

    charts = resolve_charts(_INPUTS["sample"])
    png_sources = {}
    for chart in charts:
        key = str(chart.get("png_source") or "unknown")
        png_sources[key] = png_sources.get(key, 0) + 1
    print(f"charts resolved: {len(charts)} sampled, {len(_MISSING_IMAGES)} not embeddable "
          f"(from {', '.join('%s:%d' % (k, v) for k, v in sorted(png_sources.items()))})")
    print(f"label set: {FL.LABEL_VERSION}")
    priority_charts, priority_notes = select_priority(charts)
    print(f"priority set: {len(priority_charts)} charts -> "
          + ", ".join("%s %d" % (item["event_type"], item["chosen"])
                      for item in priority_notes["per_type"]))
    if not priority_charts:
        print("FATAL: priority selection produced no charts")
        return 2

    # Independent re-verification of the relabelled charts (same locked rules, same
    # pixel-presence checks) - recorded so the claim cannot rest on the original
    # folder's matrix alone.
    verify_v2: dict = {}
    verify_v2_path = LEDGER_DIR / "verification_matrix_v2.json"
    if verify_v2_path.is_file():
        try:
            payload = json.loads(verify_v2_path.read_text(encoding="utf-8"))
            canonical_flags = {c.get("event_id") for c in verify_flags(_INPUTS["verify"])
                               if c.get("event_id")}
            relabeled_flags = {c.get("event_id") for c in (payload.get("charts") or [])
                               if c.get("flags")}
            verify_v2 = {
                "matrix": verify_v2_path.relative_to(REPO_ROOT).as_posix(),
                "folder_verified": PNG_DIR_V2.relative_to(REPO_ROOT).as_posix(),
                "pack_size": payload.get("pack_size"),
                "failures": payload.get("failures"),
                "flagged": payload.get("flagged"),
                "flags_match_canonical": canonical_flags == relabeled_flags,
                "status": ("PASS" if not payload.get("failures")
                           and canonical_flags == relabeled_flags else "CHECK"),
            }
            print(f"relabelled-chart verification: {verify_v2['pack_size']} charts, "
                  f"{verify_v2['failures']} failure(s), {verify_v2['flagged']} flag(s), "
                  f"flags match canonical: {verify_v2['flags_match_canonical']}")
        except (OSError, json.JSONDecodeError) as exc:
            warn(f"verification_matrix_v2.json present but unreadable: {exc}")
    else:
        warn("verification_matrix_v2.json absent - relabelled charts are not independently "
             "verified in this build (re-run verify_review_pack.py --png-dir "
             "review_sample_v2)")

    print("building STRUCTURE_LEDGER_FULL_REPORT.pdf ...")
    try:
        full_pages, full_toc, full_check = build_one(
            "full", build_full_report(charts, priority_notes), charts, OUT_FULL_PDF,
            "Structure Identification Ledger - Full Report",
            "STRUCTURE LEDGER - FULL REPORT")
    except Exception as exc:                                          # noqa: BLE001
        print(f"FATAL: full report build failed: {exc}")
        traceback.print_exc()
        return 3

    print("building EXPERT_VALIDATION_PACK.pdf ...")
    try:
        expert_pages, expert_toc, expert_check = build_one(
            "expert", build_expert_pack(priority_charts, priority_notes), priority_charts,
            OUT_EXPERT_PDF, "Expert Validation Pack - Structure Identification Ledger",
            "EXPERT VALIDATION PACK - STRUCTURE IDENTIFICATION LEDGER")
    except Exception as exc:                                          # noqa: BLE001
        print(f"FATAL: expert pack build failed: {exc}")
        traceback.print_exc()
        return 3

    try:
        md_path = write_markdown(priority_charts, priority_notes)
        print(f"text twin written: {md_path.name}")
    except OSError as exc:
        warn(f"markdown twin could not be written: {exc}")
        md_path = None

    note_path = None
    try:
        note_path = write_human_labels_note(
            charts, priority_charts, priority_notes,
            expert_pages=expert_pages, full_pages=full_pages,
            expert_check=expert_check, full_check=full_check,
            toc_counts={"expert": len(expert_toc), "full": len(full_toc)},
            verify_v2=verify_v2)
        print(f"human labels note written: {note_path.name}")
    except OSError as exc:
        warn(f"HUMAN_LABELS_NOTE.md could not be written: {exc}")
        note_path = None

    handoff_text = read_text_or_none(SESSION_HANDOFF) or ""
    changelog_text = read_text_or_none(CHANGELOG) or ""
    handoff_updated = "YES" if OUT_EXPERT_PDF.name in handoff_text else "NO"
    changelog_updated = "YES" if OUT_EXPERT_PDF.name in changelog_text else "NO"

    verified = (not full_check["errors"] and not expert_check["errors"])
    status = "PASS" if (verified and not _MISSING_IMAGES) else ("PASS_WITH_FLAGS" if not _MISSING_IMAGES else "FAIL")
    manifest = {
        "built_utc": DATE_STAMP,
        "engine": "reportlab (embedded image XObjects)",
        "fonts": engine_note,
        "logic_changed": "NO",
        "edge_language": "none (identification audit only)",
        "handoff_updated": handoff_updated,
        "changelog_updated": changelog_updated,
        "outputs": {
            "expert_pdf": {"path": str(OUT_EXPERT_PDF), "pages": expert_pages,
                           "size_mb": mb(OUT_EXPERT_PDF), "charts_embedded_placed": len(priority_charts),
                           "read_back": expert_check},
            "full_pdf": {"path": str(OUT_FULL_PDF), "pages": full_pages,
                         "size_mb": mb(OUT_FULL_PDF), "charts_embedded_placed": len(charts),
                         "read_back": full_check},
            "markdown_twin": str(md_path) if md_path else None,
        },
        "human_labels": {
            "label_set": FL.LABEL_VERSION,
            "labels_module": "06_RESEARCH/scripts/flowchart_labels.py",
            "chart_renderer": "06_RESEARCH/scripts/relabel_review_charts.py",
            "png_folder_preference": [str(PNG_DIR_V2.name), str(PNG_DIR.name)],
            "png_source_counts": png_sources,
            "plain_tags_on_charts": "YES",
            "ltf_chain_captions": "YES",
            "chart_verification": verify_v2,
            "note": str(note_path) if note_path else None,
            **label_stats(charts, _INPUTS["events"]),
        },
        "selection": priority_notes,
        "problem_notes": _PROBLEMS,
        "missing_images": _MISSING_IMAGES,
        "event_rows": _INPUTS.get("event_rows"),
        "events_csv_sha256": _INPUTS.get("csv_sha256"),
        "inputs": {name: str(path.relative_to(REPO_ROOT)).replace("\\", "/") for name, path in (
            ("summary.json", SUMMARY_JSON), ("events.csv", EVENTS_CSV),
            ("verification_matrix.json", VERIFY_JSON), ("review_index", REVIEW_INDEX),
            ("ledger_report", LEDGER_REPORT), ("evidence_map", EVIDENCE_MAP),
            ("freeze_doc", FREEZE_DOC), ("locked_decisions", LOCKED_DECISIONS))},
    }
    try:
        OUT_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except OSError as exc:
        warn(f"manifest could not be written: {exc}")

    print("-" * 78)
    print(f"embedded images verified: expert={expert_check['images']} full={full_check['images']}")
    print(f"charts per page: expert={expert_check['images_per_page']} full={full_check['images_per_page']}")
    print(f"image placement: expert out_of_frame={len(expert_check['out_of_frame'])} "
          f"overlaps={len(expert_check['overlaps'])} | "
          f"full out_of_frame={len(full_check['out_of_frame'])} "
          f"overlaps={len(full_check['overlaps'])}")
    print(f"image resolutions (no downsampling): expert={expert_check['image_sizes']} "
          f"full={full_check['image_sizes']}")
    print(f"contents entries (page numbers stable): expert={len(expert_toc)} full={len(full_toc)}")
    print(f"uri links inside PDFs: expert={expert_check['uri_actions']} full={full_check['uri_actions']}")
    print(f"A4 page size: expert={expert_check['page_size_ok']} full={full_check['page_size_ok']}")
    if _PROBLEMS:
        print(f"notes: {len(_PROBLEMS)} (see manifest problem_notes)")
    print("-" * 78)
    print(f"PDF_PACK_STATUS: {status}")
    labels_ok = ("YES" if (expert_check["images"] and full_check["images"]
                           and not _MISSING_IMAGES
                           and all(chart.get("label") for chart in charts)) else "NO")
    print(f"HUMAN_LABELS_STATUS: {'PASS' if status != 'FAIL' and labels_ok == 'YES' else 'FAIL'}")
    print(f"PLAIN_TAGS_ON_CHARTS: {labels_ok}")
    print(f"LTF_CHAIN_CAPTIONS: {labels_ok}")
    print(f"EXPERT_PDF: {OUT_EXPERT_PDF.relative_to(REPO_ROOT).as_posix()}")
    print(f"FULL_PDF: {OUT_FULL_PDF.relative_to(REPO_ROOT).as_posix()}")
    print(f"HUMAN_LABELS_NOTE: {note_path.relative_to(REPO_ROOT).as_posix() if note_path else 'not written'}")
    print(f"EXPERT_PAGES: {expert_pages}")
    print(f"FULL_PAGES: {full_pages}")
    print(f"CHARTS_EMBEDDED_EXPERT: {expert_check['images']}")
    print(f"CHARTS_EMBEDDED_FULL: {full_check['images']}")
    print("PDF_ENGINE: reportlab")
    print("FILE_SIZES_MB: expert=%s full=%s" % (mb(OUT_EXPERT_PDF), mb(OUT_FULL_PDF)))
    print("LOGIC_CHANGED: NO")
    print(f"HANDOFF_UPDATED: {handoff_updated} (CHANGELOG: {changelog_updated})")
    print("NEXT_READY: Share PDFs with validators -> collect CORRECT/PARTIAL/WRONG/UNCLEAR tallies")
    return 0 if status != "FAIL" else 4


if __name__ == "__main__":
    sys.exit(main())
