#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Plain flowchart vocabulary for the structure-ledger review surface.

PRESENTATION ONLY - a pure text mapping. This module reads nothing, writes
nothing, and imports no project code. It exists so the two consumers that
render the review surface (``relabel_review_charts.py`` for the PNGs and
``build_expert_pdfs.py`` for the PDFs) derive their wording from ONE source
and can never drift apart.

Why: the ledger speaks engine vocabulary (``poi_raw``, ``route_ltf``,
``pillar_reject``, ``source_module``). A flowchart reviewer speaks
"Liquidity sweep", "Order block", "Demand zone", "Fair value gap (FVG)",
"LTF confirmation (M5 entry)". Same rows, reviewer language.

Honesty rule (strict): a plain label is emitted only when the ledger row
itself supports it - ``event_type``, ``direction``, ``model_tags``, or a
``kind=`` / ``level_type=`` field inside ``notes``. Where the code emitted no
kind label the tag says "unlabeled POI"; nothing is inferred from geometry,
price action, or proximity. This module never invents OB / FVG / S&D and
never invents a link between two ledger rows.

LOGIC_CHANGED: NO. No detection, threshold, pillar, trigger, zone-band, R7/R9
or locked-constant behaviour is touched or described differently.
"""

from __future__ import annotations

LABEL_VERSION = "flowchart-labels v1 (2026-09-25)"

#: Shown when the code gave a POI no kind label at all.
UNLABELED_POI = "unlabeled POI"

# --------------------------------------------------------------------------- #
# Vocabulary the ledger itself carries (read from notes / model_tags)
# --------------------------------------------------------------------------- #

#: ``level_type=`` values observed in the frozen ledger (sweep + liquidity_level).
LEVEL_TYPE_PLAIN = {
    "session": "session",
    "structural_swing": "structural swing",
    "previous_day": "previous day",
    "previous_week": "previous week",
    "equal_highs_lows": "equal highs / lows",
}

#: ``pool=`` values on sweep rows. SSL = liquidity resting below price,
#: BSL = liquidity resting above price (the ledger report's own wording:
#: "direction = the pool taken (SSL -> LONG)").
POOL_PLAIN = {
    "SSL": "sell-side liquidity (resting below)",
    "BSL": "buy-side liquidity (resting above)",
}

#: Flowchart stage per event_type. Mirrors the stage column already printed in
#: MODULE_MAP_ROWS / STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md section 2.
STAGE_OF = {
    "liquidity_level": "Stage 0A - liquidity map",
    "sweep": "Stage 0A - liquidity map and sweep",
    "fvg": "Stage 1 - imbalance (fair value gap)",
    "displacement": "Stage 1 - displacement",
    "poi_raw": "Stage 1 - POI (order block / supply / demand)",
    "poi_merged": "Stage 1 - confluence merge",
    "pillar_pass": "Stage 2 - validation pillars",
    "pillar_reject": "Stage 2 - validation pillars",
    "poi_armed": "Stage 3 - arm",
    "route_ltf": "Stage 4 - LTF confirmation (M5 entry trigger)",
    "intent": "Stage 4 - place intent (R9)",
    "fill": "Stage 4 - entry fill",
}

#: The tag shown when there is no row to read (the concept -> code maps).
GENERIC_TAG = {
    "liquidity_level": "Liquidity level (HTF / session)",
    "sweep": "Liquidity sweep",
    "fvg": "Fair value gap (FVG)",
    "displacement": "Displacement (BOS + FVG)",
    "poi_raw": "Order block / Demand zone / Supply zone",
    "poi_merged": "Merged POI (confluence)",
    "poi_armed": "Armed POI (passed validation)",
    "pillar_pass": "Validation pillars PASS",
    "pillar_reject": "Validation pillar reject",
    "pillar_pass / pillar_reject": "Validation pillars (pass / reject)",
    "route_ltf": "LTF confirmation (M5 entry)",
    "intent": "Place intent (R9)",
    "fill": "Entry fill",
}


#: The mandatory setup-chain footer, printed verbatim on route_ltf / fill charts
#: and in their PDF caption blocks, so a reviewer cannot mistake the M5 entry
#: step for the HTF structure that produced it.
LTF_CHAIN_FOOTER = ("This chart is the lower-timeframe entry step, "
                    "not the HTF sweep itself.")

#: Rows rendered on the M5 execution series (LTF completes there by design).
M5_EVENT_TYPES = {"route_ltf", "intent", "fill"}

#: Ordered (code event_type, plain tag, what it means) table for the
#: "How to read flowchart tags" page. Kept literal so the page can never
#: disagree with :func:`human_tag` for the common cases.
LABEL_TABLE = [
    ("liquidity_level", "Liquidity level (HTF / session)",
     "A mapped pool of resting liquidity: session, previous day / week, "
     "structural swing, or equal highs / lows. A single price, drawn as a "
     "solid blue line."),
    ("sweep", "Liquidity sweep",
     "A wick pierces a mapped level and the body closes back. Direction is "
     "the pool taken: sell-side liquidity swept -> LONG, buy-side -> SHORT. "
     "This is the HTF trigger event, drawn as the level plus the event bar."),
    ("fvg", "Fair value gap (FVG)",
     "A three-candle imbalance on the detection timeframe. The zone is the "
     "gap between candle 1 and candle 3, drawn as a translucent blue band."),
    ("displacement", "Displacement (BOS + FVG)",
     "A break of structure that leaves an imbalance, of at least one ATR. "
     "The magnitude in ATR is recorded on the row."),
    ("poi_raw", "Order block / Demand zone / Supply zone",
     "Model 8's HTF zone, labelled from the row's own code kind: "
     "'ob' -> Order block, 'demand_supply' + LONG -> Demand zone, "
     "'demand_supply' + SHORT -> Supply zone, 'fvg' -> Fair value gap. "
     "When the code emitted no kind the chart says \"unlabeled POI\" and "
     "nothing is guessed."),
    ("poi_merged", "Merged POI (confluence)",
     "Same-direction overlapping zones merged into a union of member model "
     "tags. The tag list is detection-path dependent (a documented open "
     "disposition), so score the geometry, not the tag list."),
    ("poi_armed", "Armed POI (passed validation)",
     "The POI that cleared the five pillars and armed (one arm per zone "
     "episode). This is the HTF structure the entry is taken from."),
    ("pillar_pass", "Validation pillars PASS",
     "All five pillars passed for that geometry."),
    ("pillar_reject", "Validation pillar reject",
     "The first hard pillar failure for that geometry is recorded."),
    ("route_ltf", "LTF confirmation (M5 entry)",
     "The M5 trigger (A-F, chronological first-valid) that routed the armed "
     "POI to an entry. The trigger letter is shown when the row carries it. "
     "This is the entry step, not the sweep."),
    ("intent", "Place intent (R9)",
     "An R9 place-on-reentry lifecycle transition "
     "(armed / placed / expired / replaced / dropped)."),
    ("fill", "Entry fill",
     "The routed limit was filled. The row carries the trade's own recorded "
     "outcome fields for chain completeness only - they are not a "
     "performance or edge statement."),
]


# --------------------------------------------------------------------------- #
# Small helpers over a ledger row (a dict with the events.csv columns)
# --------------------------------------------------------------------------- #

def parse_notes(notes) -> dict:
    """``'a=1;b=2;observed=3;chunk=chunkA'`` -> ``{'a': '1', 'b': '2', ...}``.

    Segments without ``=`` are ignored; the FIRST occurrence of a key wins, so
    a repeated key cannot silently change a label. The ledger appends its
    bookkeeping tail with ``' | '`` (``...;candle_close=3312.798 | rel_dangling;
    observed=1491;chunk=chunkA``) - that tail is stripped from the value it was
    glued to, so a price never arrives as ``'3312.798 | rel_dangling'``.
    """
    out: dict = {}
    for segment in str(notes or "").split(";"):
        if "=" not in segment:
            continue
        key, value = segment.split("=", 1)
        key = key.strip()
        value = value.strip()
        if " | " in value:
            head, _, tail = value.partition(" | ")
            if tail.startswith("rel_dangling") or tail.startswith("observed="):
                value = head.strip()
        if key and key not in out:
            out[key] = value
    return out


def detail_of(row) -> str:
    """Reconstruct the runner's free-text ``detail=`` field.

    The runner writes ``detail=BOS at bar 3425; first touch of origin OB at bar
    3427; entry anchor ...`` - the continuation segment carries no ``=``, so a
    plain key=value split would truncate it. Continuation segments begin with a
    space, which is how they are recognised here.
    """
    segments = str((row or {}).get("notes") or "").split(";")
    parts: list[str] = []
    for index, segment in enumerate(segments):
        if not segment.startswith("detail="):
            continue
        parts.append(segment.split("=", 1)[1].strip())
        for following in segments[index + 1:]:
            if not following.startswith(" "):
                break
            # ``entry anchor ...`` is the runner's next field, written without
            # a ``=``; it is not part of the free-text detail.
            if " | " in following or following.strip().startswith("entry anchor"):
                break
            parts.append(following.strip())
        break
    return "; ".join(part for part in parts if part)


def _direction(row) -> str:
    return str(row.get("direction") or "").strip().upper()


def _tags(row) -> str:
    return str(row.get("model_tags") or "").strip()


def _is_m8(row) -> bool:
    return "M8" in [part.strip() for part in _tags(row).split("|")]


def _htf_tf(row) -> str:
    """HTF the zone claims, from notes ``htf_tf=`` or the detection timeframe."""
    notes = parse_notes(row.get("notes"))
    return str(notes.get("htf_tf") or row.get("detection_tf") or "").strip()


def kind_of(row) -> str:
    """The code-emitted ``kind=`` on the row's notes (``''`` when absent)."""
    return str(parse_notes(row.get("notes")).get("kind") or "").strip()


def level_type_of(row) -> str:
    return str(parse_notes(row.get("notes")).get("level_type") or "").strip()


def pool_of(row) -> str:
    return str(parse_notes(row.get("notes")).get("pool") or "").strip()


def trigger_letter(row) -> str:
    """Trigger A-F for a routed row.

    Prefers the row's own ``trigger`` column; falls back to parsing the
    ``route_id`` the runner recorded (``poi-0024417:F@9657`` -> ``F``), which is
    how the two fill rows carry it (their ``trigger`` column is populated too,
    but the route id is the authoritative source).
    """
    direct = str(row.get("trigger") or "").strip()
    if direct:
        return direct
    notes = parse_notes(row.get("notes"))
    route_id = str(notes.get("route_id") or "")
    if ":" in route_id:
        tail = route_id.split(":", 1)[1]
        letter = tail.split("@", 1)[0].strip()
        if letter:
            return letter
    return ""


def route_id_of(row) -> str:
    return str(parse_notes(row.get("notes")).get("route_id") or "").strip()


def ts_plain(value) -> str:
    """``'2025-06-01T22:00:00+00:00'`` -> ``'2025-06-01 22:00 UTC'``."""
    text = str(value or "").strip()
    if not text:
        return "n/a"
    text = text.replace("T", " ")
    if len(text) >= 16:
        return text[:16] + " UTC"
    return text


def _num(value, places: int = 3) -> str:
    """Format a price, or return the raw text when it is not numeric."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value or "").strip()
    text = f"{number:.{places}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def zone_plain(row) -> str:
    """``'zone 3356.328 - 3363.545'`` or ``'level 3304.498'``, never invented."""
    low, high = row.get("price_low"), row.get("price_high")
    try:
        low_f, high_f = float(low), float(high)
    except (TypeError, ValueError):
        return "geometry not recorded"
    if abs(high_f - low_f) < 1e-9:
        return "level %s" % _num(low_f)
    return "zone %s - %s" % (_num(low_f), _num(high_f))


# --------------------------------------------------------------------------- #
# The label itself
# --------------------------------------------------------------------------- #

def human_tag(event_type, row) -> str:
    """The plain flowchart tag for a ledger row.

    See the module docstring for the honesty rule. Never raises: an unknown
    event_type is echoed back unchanged rather than guessed at.
    """
    et = str(event_type or "").strip().lower()
    row = row or {}
    notes = parse_notes(row.get("notes"))

    if et == "liquidity_level":
        level_type = LEVEL_TYPE_PLAIN.get(str(notes.get("level_type") or "").strip())
        return "Liquidity level (%s)" % level_type if level_type else "Liquidity level (HTF / session)"

    if et == "sweep":
        return "Liquidity sweep"

    if et == "fvg":
        return "Fair value gap (FVG)"

    if et == "displacement":
        return "Displacement (BOS + FVG)"

    if et == "poi_raw":
        kind = kind_of(row)
        source = "M8 HTF" if _is_m8(row) else (_tags(row) or "POI model")
        if kind == "ob":
            return "Order block (%s)" % source
        if kind == "demand_supply":
            direction = _direction(row)
            if direction == "LONG":
                return "Demand zone (%s)" % source
            if direction == "SHORT":
                return "Supply zone (%s)" % source
            return "Supply / demand zone (%s)" % source
        if kind == "fvg":
            return "Fair value gap (%s)" % source
        # No code kind -> say so rather than infer one.
        return "%s (%s)" % (UNLABELED_POI, source)

    if et == "poi_merged":
        return "Merged POI (confluence)"

    if et == "poi_armed":
        return "Armed POI (passed validation)"

    if et == "pillar_pass":
        return "Validation pillars PASS"

    if et == "pillar_reject":
        return "Validation pillar reject"

    if et == "route_ltf":
        letter = trigger_letter(row)
        return "LTF confirmation (M5 entry, trigger %s)" % letter if letter else "LTF confirmation (M5 entry)"

    if et == "intent":
        return "Place intent (R9)"

    if et == "fill":
        return "Entry fill"

    return str(event_type or "unknown event")


def headline(event_type, row, chart_tf) -> str:
    """`"LIQUIDITY SWEEP  |  H1  |  2025-06-01 22:00 UTC  |  LONG"`."""
    parts = [
        human_tag(event_type, row).upper(),
        str(chart_tf or "").strip() or "n/a",
        ts_plain(row.get("ts_utc")),
        _direction(row) or "n/a",
    ]
    return "  |  ".join(parts)


def technical_line(event_type, row, *, event_id: str, chart_tf: str, detection_tf: str,
                   seq: int | None = None, total: int | None = None) -> str:
    """The demoted, small-print engine trace kept under every headline."""
    bits = [
        "technical row: event_type=%s" % (str(event_type or "").strip() or "n/a"),
        "detect_tf=%s" % (str(detection_tf or "").strip() or "n/a"),
        "chart_tf=%s" % (str(chart_tf or "").strip() or "n/a"),
        "tags=%s" % (_tags(row) or "-"),
        "event_id=%s" % (str(event_id or "").strip() or "n/a"),
    ]
    if seq is not None and total is not None:
        bits.append("chart %d/%d" % (seq, total))
    return " | ".join(bits)


def generic_tag(event_type) -> str:
    """The plain tag for a vocabulary entry with no row behind it."""
    et = str(event_type or "").strip().lower()
    if et in GENERIC_TAG:
        return GENERIC_TAG[et]
    return " / ".join(GENERIC_TAG.get(part.strip(), part.strip())
                      for part in et.split(" / "))


def stage_line(event_type) -> str:
    return "FLOWCHART STAGE: %s" % STAGE_OF.get(str(event_type or "").strip().lower(),
                                                 "not in the mapped vocabulary")


# --------------------------------------------------------------------------- #
# "What you are looking at" - every clause is read from the row
# --------------------------------------------------------------------------- #

def detail_lines(event_type, row) -> list[str]:
    """Plain-language reading guide for one row (2-4 short lines)."""
    et = str(event_type or "").strip().lower()
    notes = parse_notes(row.get("notes"))
    lines: list[str] = []

    if et == "liquidity_level":
        level_type = LEVEL_TYPE_PLAIN.get(level_type_of(row), level_type_of(row) or "unclassified")
        lines.append("Pool: %s  |  price %s" % (level_type, zone_plain(row)))
        if notes.get("formed_at"):
            lines.append("formed at %s" % ts_plain(notes.get("formed_at")))

    elif et == "sweep":
        pool = pool_of(row)
        lines.append("Pool taken: %s" % POOL_PLAIN.get(pool, pool or "not recorded"))
        lines.append("Level swept: %s  |  level type: %s"
                     % (_num(notes.get("level")), LEVEL_TYPE_PLAIN.get(level_type_of(row),
                                                                      level_type_of(row) or "n/a")))
        if notes.get("candle_high") or notes.get("candle_low"):
            lines.append("Sweeping candle: high %s / low %s / close %s"
                         % (_num(notes.get("candle_high")), _num(notes.get("candle_low")),
                            _num(notes.get("candle_close"))))
        if str(notes.get("rel_dangling") or "").strip() or "rel_dangling" in str(row.get("notes") or ""):
            lines.append("Its mapped level was formed during a chunk warm-up, so the level link is "
                         "recorded as rel_dangling (price preserved on the row).")

    elif et == "fvg":
        lines.append("Imbalance: %s  (kind %s)"
                     % (zone_plain(row), notes.get("kind") or "fvg"))
        if notes.get("first_bar"):
            lines.append("First bar of the three-candle gap: %s" % ts_plain(notes.get("first_bar")))
        lines.append("Zone timeframe: %s" % (notes.get("zone_tf") or row.get("detection_tf") or "n/a"))

    elif et == "displacement":
        lines.append("Displacement of %s ATR" % (row.get("disp_magnitude_atr") or "n/a"))

    elif et == "poi_raw":
        kind = kind_of(row)
        lines.append("M8 HTF zone  |  code kind '%s' (%s)"
                     % (kind or "none emitted", notes.get("kind_label") or "no kind_label"))
        lines.append("Claimed HTF: %s  |  zone timeframe: %s  |  %s"
                     % (_htf_tf(row) or "n/a", notes.get("zone_tf") or "n/a", zone_plain(row)))
        if notes.get("origin_bar"):
            lines.append("Origin bar: %s  |  htf_vs_ltf: %s"
                         % (ts_plain(notes.get("origin_bar")), notes.get("htf_vs_ltf") or "n/a"))
        if not kind:
            lines.append("The code emitted no kind for this zone, so no OB / demand / supply label "
                         "is claimed here.")

    elif et == "poi_merged":
        lines.append("Confluence merge (%s)  |  member models: %s"
                     % (notes.get("merge") or "tag union", _tags(row) or "-"))
        lines.append("Zone timeframe: %s  |  %s  |  confluence score %s"
                     % (notes.get("zone_tf") or "n/a", zone_plain(row), notes.get("score") or "n/a"))
        lines.append("Member tags are detection-path dependent (documented open disposition): "
                     "score the geometry, not the tag list.")

    elif et == "poi_armed":
        lines.append("Armed POI  |  zone timeframe: %s  |  %s"
                     % (notes.get("zone_tf") or "n/a", zone_plain(row)))
        lines.append("Arm bar %s  |  dedup %s  |  HTF overlap %s"
                     % (notes.get("arm_bar") or "n/a", notes.get("dedup") or "n/a",
                        notes.get("htf_overlap") or "n/a"))
        lines.append("Model tags on the armed row: %s" % (_tags(row) or "-"))

    elif et in ("pillar_pass", "pillar_reject"):
        lines.append("Pillar path: %s" % (row.get("pillar_path") or "not recorded"))
        lines.append("%s" % zone_plain(row))

    elif et == "route_ltf":
        lines.append("Routed trigger %s  |  route %s"
                     % (trigger_letter(row) or "n/a", route_id_of(row) or "not recorded"))
        detail = detail_of(row)
        if detail:
            lines.append("Trigger detail: %s" % detail)
        lines.append("Entry limit %s  |  original SL %s  |  anchor %s"
                     % (_num(row.get("entry")), _num(row.get("original_sl")),
                        row.get("entry_anchor") or "not set"))

    elif et == "intent":
        lines.append("R9 intent lifecycle transition")
        if notes.get("transition"):
            lines.append("Transition: %s" % notes.get("transition"))

    elif et == "fill":
        lines.append("Routed limit filled  |  route %s  |  trigger %s"
                     % (route_id_of(row) or "n/a", trigger_letter(row) or "n/a"))
        lines.append("Entry %s  |  original SL %s  |  entry anchor %s"
                     % (_num(row.get("entry")), _num(row.get("original_sl")),
                        row.get("entry_anchor") or "not set"))
        lines.append("Recorded close_kind %s (informational only, not a performance claim)"
                     % (notes.get("close_kind") or "n/a"))

    if not lines:
        lines.append("No plain-language detail is derivable from this row's recorded fields.")
    return lines


# --------------------------------------------------------------------------- #
# Mandatory setup chain (route_ltf and fill pages)
# --------------------------------------------------------------------------- #

def chain_for(row, events_by_id: dict) -> dict:
    """Resolve the ledger's own links around a routed/filled row.

    Returns only what the ledger records. ``missing`` names whatever the ledger
    does NOT link, so the caption can say "not linked in this row" instead of
    inventing a sweep or FVG.
    """
    row = row or {}
    events_by_id = events_by_id or {}
    chain: dict = {"armed": None, "merged": None, "route": None, "missing": []}

    def _lookup(event_id):
        return events_by_id.get(event_id) if event_id else None

    armed_id = str(row.get("related_event_id") or "").strip()
    armed = _lookup(armed_id)
    if armed is None:
        chain["missing"].append("armed POI link")
    else:
        chain["armed"] = armed
        merged_id = str(armed.get("related_event_id") or "").strip()
        merged = _lookup(merged_id)
        if merged is None:
            chain["missing"].append("merged POI link")
        else:
            chain["merged"] = merged

    # A fill links to its armed POI; the routed trigger row (if any) links to
    # the same armed POI. Find it by identity, never by proximity in time.
    self_id = str(row.get("event_id") or "").strip()
    armed_id = str(row.get("related_event_id") or "").strip()
    if armed_id:
        for candidate in events_by_id.values():
            if candidate.get("event_type") != "route_ltf":
                continue
            if str(candidate.get("event_id") or "").strip() == self_id:
                continue
            if str(candidate.get("related_event_id") or "").strip() == armed_id:
                chain["route"] = candidate
                break

    chain["missing"].append("sweep / FVG event id on this chain")
    return chain


def setup_chain_lines(row, events_by_id: dict, *, include_route_row: bool = True) -> list[str]:
    """The plain 'HTF structure -> LTF confirmation -> entry' block.

    Printed verbatim on every route_ltf / fill chart and in their PDF caption
    blocks. Every clause is either read from the ledger or explicitly reported
    as not linked.
    """
    row = row or {}
    chain = chain_for(row, events_by_id)
    lines = [stage_line(row.get("event_type"))]

    # --- HTF structure -----------------------------------------------------
    htf_bits = []
    armed = chain.get("armed")
    merged = chain.get("merged")
    if armed is not None:
        htf_bits.append("Armed POI %s (tags %s, zone tf %s, %s)"
                        % (armed.get("event_id"), _tags(armed) or "-",
                           parse_notes(armed.get("notes")).get("zone_tf") or armed.get("detection_tf") or "n/a",
                           zone_plain(armed)))
    if merged is not None:
            htf_bits.append("Merged POI %s (confluence, member models %s, zone tf %s)"
                            % (merged.get("event_id"), _tags(merged) or "-",
                               parse_notes(merged.get("notes")).get("zone_tf") or "n/a"))
    if htf_bits:
        lines.append("HTF structure: " + " -> ".join(htf_bits))
    lines.append("HTF structure not linked in row: the ledger records no sweep and no FVG event id "
                 "on this chain, so none is claimed here.")

    # --- LTF confirmation --------------------------------------------------
    letter = trigger_letter(row) or "n/a"
    route_row = chain.get("route")
    if str(row.get("event_type") or "").strip().lower() == "route_ltf":
        detail = detail_of(row)
        lines.append("LTF confirmation: M5 trigger %s on %s%s"
                     % (letter, ts_plain(row.get("ts_utc")),
                        "  |  %s" % detail if detail else ""))
    else:
        route_note = ""
        if route_row is not None and include_route_row:
            route_note = "  |  route row %s (in this pack)" % route_row.get("event_id")
        elif route_row is not None:
            route_note = "  |  route row %s" % route_row.get("event_id")
        lines.append("LTF confirmation: M5 trigger %s%s" % (letter, route_note))

    # --- Entry / stop ------------------------------------------------------
    entry = _num(row.get("entry"))
    stop = _num(row.get("original_sl"))
    if not entry:
        entry = "not set"
    if not stop:
        stop = "not set"
    entry_line = "Entry: %s (routed limit)   Original SL: %s" % (entry, stop)
    anchor = str(row.get("entry_anchor") or "").strip()
    if anchor:
        entry_line += "   anchor: %s" % anchor
    lines.append(entry_line)
    if str(row.get("event_type") or "").strip().lower() == "fill":
        close_kind = parse_notes(row.get("notes")).get("close_kind") or "n/a"
        lines.append("Fill time: %s   Recorded close_kind: %s (informational only)"
                     % (ts_plain(row.get("ts_utc")), close_kind))

    lines.append(LTF_CHAIN_FOOTER)
    return lines


# --------------------------------------------------------------------------- #
# Caption block used by the PDF builder (one place for both PDFs)
# --------------------------------------------------------------------------- #

def caption_lines(event_type, row, events_by_id: dict, *, event_id: str, chart_tf: str,
                  detection_tf: str) -> dict:
    """Everything the PDF caption needs for one row, already in plain language.

    Returns ``{'tag', 'headline', 'technical', 'detail': [...], 'chain': [...]}``
    where ``chain`` is populated only for route_ltf / fill.
    """
    et = str(event_type or "").strip().lower()
    out = {
        "tag": human_tag(et, row),
        "headline": headline(et, row, chart_tf),
        "technical": technical_line(et, row, event_id=event_id, chart_tf=chart_tf,
                                    detection_tf=detection_tf),
        "stage": STAGE_OF.get(et, "not in the mapped vocabulary"),
        "detail": detail_lines(et, row),
        "chain": [],
    }
    if et in M5_EVENT_TYPES and et in ("route_ltf", "fill"):
        out["chain"] = setup_chain_lines(row, events_by_id)
    return out
