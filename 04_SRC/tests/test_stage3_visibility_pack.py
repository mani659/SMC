"""Stage 3 trigger visibility pack — focused tests (visibility only).

Covers the new pure helpers introduced by
``06_RESEARCH/scripts/stage3_trigger_visibility.py``: ledger schema,
deterministic trigger ids, detector-context selection, the deterministic
chart budget, the type-covering time-spread trigger sample, negative-example
selection, and pinned window/strategy constants.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "stage3_trigger_visibility.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "stage3_trigger_visibility", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage3_trigger_visibility"] = module
    spec.loader.exec_module(module)
    return module


def _row(rid: str, trig: str, hour: int) -> dict:
    ts = datetime(2025, 6, 1 + hour // 24, hour % 24, tzinfo=timezone.utc)
    return {"trigger_id": rid, "trigger_type": trig,
            "bar_time_utc": ts.isoformat()}


# --------------------------------------------------------------------------- #
# 1. Ledger schema (exact columns from the prompt)
# --------------------------------------------------------------------------- #
def test_ledger_columns_exact():
    pack = _load_pack()
    assert pack.LEDGER_COLUMNS == [
        "trigger_id", "trigger_type", "trigger_tf", "direction",
        "bar_time_utc", "entry_price_ref", "related_htf_event_id",
        "related_htf_plain_tag", "related_htf_zone_low",
        "related_htf_zone_high", "relation_to_htf", "detector_context",
        "route_would_form", "notes",
    ]


def test_trigger_id_deterministic_and_readable():
    pack = _load_pack()
    a = pack.trigger_id("F", "evt-abc", 25836)
    assert a == "s3-F-evt-abc-25836"
    assert a == pack.trigger_id("F", "evt-abc", 25836)
    assert pack.trigger_id("A", "evt-abc", 7) == "s3-A-evt-abc-00007"


# --------------------------------------------------------------------------- #
# 2. Detector context string
# --------------------------------------------------------------------------- #
def _det_row(tf: str, ts: str, tag: str) -> dict:
    return {"ltf_tf": tf, "ltf_ts_utc": ts, "ltf_plain_tag": tag}


def test_detector_context_nearest_preceding_per_tf():
    pack = _load_pack()
    rows = [
        _det_row("M5", "2025-06-01T10:05:00+00:00", "SWEEP (M5)"),
        _det_row("M5", "2025-06-01T11:55:00+00:00", "FAIR VALUE GAP (M5)"),
        _det_row("M15", "2025-06-01T11:45:00+00:00", "DISPLACEMENT (M15)"),
        _det_row("M5", "2025-06-01T13:10:00+00:00", "SWEEP (M5)"),  # after
    ]
    out = pack.detector_context_string(rows, "2025-06-01T12:00:00+00:00")
    parts = out.split("; ")
    assert len(parts) == 2                      # one per timeframe, max
    assert parts[0] == "FAIR VALUE GAP (M5)@2025-06-01 11:55"
    assert parts[1] == "DISPLACEMENT (M15)@2025-06-01 11:45"


def test_detector_context_none_when_no_preceding_rows():
    pack = _load_pack()
    assert pack.detector_context_string([], "2025-06-01T12:00:00+00:00") == "none in window"
    rows = [_det_row("M5", "2025-06-01T13:00:00+00:00", "SWEEP (M5)")]
    assert pack.detector_context_string(rows, "2025-06-01T12:00:00+00:00") == "none in window"


# --------------------------------------------------------------------------- #
# 3. Chart budget
# --------------------------------------------------------------------------- #
def test_chart_plan_respects_cap_and_priorities():
    pack = _load_pack()
    # Few triggers: full set + context + 6 negatives.
    p = pack.chart_plan(5, 6)
    assert p == {"trigger_panels": 5, "context_panels": 5,
                 "negative_panels": 6}
    assert sum(p.values()) <= 40
    # Boundary: 2*17 + 6 == 40 exactly.
    p = pack.chart_plan(17, 6)
    assert p["context_panels"] == 17 and sum(p.values()) == 40
    # Too many for contexts: contexts drop, negatives stay.
    p = pack.chart_plan(18, 6)
    assert p["context_panels"] == 0 and p["negative_panels"] == 6
    # Trigger charts capped at 30.
    p = pack.chart_plan(263, 6)
    assert p == {"trigger_panels": 30, "context_panels": 0,
                 "negative_panels": 6}
    assert sum(p.values()) <= 40
    # Zero triggers: negative examples still charted.
    p = pack.chart_plan(0, 6)
    assert p == {"trigger_panels": 0, "context_panels": 0,
                 "negative_panels": 6}
    # Degenerate tiny cap never exceeded.
    p = pack.chart_plan(10, 6, cap=8)
    assert sum(p.values()) <= 8


# --------------------------------------------------------------------------- #
# 4. Trigger chart sample (type coverage + time spread)
# --------------------------------------------------------------------------- #
def test_trigger_sample_returns_all_when_within_limit():
    pack = _load_pack()
    rows = [_row(f"r{i}", "F", i) for i in range(10)]
    assert pack.select_trigger_charts(rows, 30) == rows


def test_trigger_sample_seeds_every_type_and_is_stable():
    pack = _load_pack()
    rows: list[dict] = []
    # 3 A, 3 B, 40 F spread over time.
    for i, trig in enumerate(["A"] * 3 + ["B"] * 3 + ["F"] * 40):
        rows.append(_row(f"r{i:03d}", trig, i))
    rows.sort(key=lambda r: (r["bar_time_utc"], r["trigger_type"],
                             r["trigger_id"]))
    picked = pack.select_trigger_charts(rows, 10)
    assert len(picked) == 10
    types = {r["trigger_type"] for r in picked}
    assert types == {"A", "B", "F"}             # every type present
    # Deterministic + sorted output.
    again = pack.select_trigger_charts(list(rows), 10)
    assert [r["trigger_id"] for r in picked] == [r["trigger_id"] for r in again]
    assert picked == sorted(picked, key=lambda r: (r["bar_time_utc"],
                                                   r["trigger_type"],
                                                   r["trigger_id"]))


# --------------------------------------------------------------------------- #
# 5. Negative-example selection
# --------------------------------------------------------------------------- #
def test_select_negatives_excludes_triggered_and_ranks_by_activity():
    pack = _load_pack()
    def struct(eid: str, ts: str, n_rows: int) -> dict:
        return {"event_id": eid, "ts_utc": ts,
                "_detector_rows": [{} for _ in range(n_rows)]}
    structs = [
        struct("evt-hot", "2025-06-02T00:00:00+00:00", 50),
        struct("evt-trig", "2025-06-03T00:00:00+00:00", 99),  # excluded
        struct("evt-warm", "2025-06-04T00:00:00+00:00", 20),
        struct("evt-empty", "2025-06-05T00:00:00+00:00", 0),   # excluded
    ]
    picked = pack.select_negatives(structs, {"evt-trig"}, limit=6)
    ids = [s["event_id"] for s in picked]
    assert "evt-trig" not in ids and "evt-empty" not in ids
    assert ids[0] == "evt-hot"                  # highest activity first
    assert pack.select_negatives(structs, {"evt-trig"}, limit=6) == picked


# --------------------------------------------------------------------------- #
# 6. Route funnel classification
# --------------------------------------------------------------------------- #
def test_classify_route_funnel_buckets():
    pack = _load_pack()
    t0 = datetime(2025, 6, 1, tzinfo=timezone.utc)

    def iso(hours: int) -> str:
        return (t0 + timedelta(hours=hours)).isoformat()

    rows = [
        {"route_would_form": "yes", "related_htf_event_id": "s1",
         "bar_time_utc": iso(1)},                       # routed
        {"route_would_form": "no", "related_htf_event_id": "s2",
         "bar_time_utc": iso(9)},                       # after pop (tested)
        {"route_would_form": "no", "related_htf_event_id": "s2",
         "bar_time_utc": iso(10)},                      # after pop (tested)
        {"route_would_form": "no", "related_htf_event_id": "s3",
         "bar_time_utc": iso(3)},                       # inside open scan
        {"route_would_form": "no", "related_htf_event_id": "s4",
         "bar_time_utc": iso(6)},                       # after pop (violated)
        {"route_would_form": "no", "related_htf_event_id": "unknown",
         "bar_time_utc": iso(0)},                       # not probed
    ]
    gate = {
        "s1": {"last_scanned": 2, "pop_bar": None, "pop_reason": None,
               "route_bar": 1},
        "s2": {"last_scanned": 4, "pop_bar": 5, "pop_reason": "tested",
               "route_bar": None},
        "s3": {"last_scanned": 20, "pop_bar": None, "pop_reason": None,
               "route_bar": None},
        "s4": {"last_scanned": 5, "pop_bar": 6, "pop_reason": "violated",
               "route_bar": None},
    }
    m5_index = {t0 + timedelta(hours=h): h for h in range(0, 12)}
    out = pack.classify_route_funnel(rows, gate, m5_index)
    assert out == {"routed": 1, "scanned_not_routed": 1, "suppressed": 3,
                   "suppressed_tested": 2, "suppressed_violated": 1,
                   "suppressed_other": 0, "not_probed": 1}


# --------------------------------------------------------------------------- #
# 7. Pinned window / strategy constants
# --------------------------------------------------------------------------- #
def test_pinned_constants_unchanged():
    from smc.config import locked_constants as lc
    from smc.triggers.trigger_expiry import poi_give_up_bars
    pack = _load_pack()
    # Scan window = existing constant only.
    assert pack.ltf.LA_M5_BARS == poi_give_up_bars() == 20
    assert pack.ltf.LA_M5_BARS == lc.TRIGGER_A_EXPIRY == 20
    # §24 trigger windows (D/E/F referenced by the ledger contract).
    assert lc.TRIGGER_B_EXPIRY == 30
    assert lc.TRIGGER_C_EXPIRY_EXTRA == 3
    assert lc.TRIGGER_D_EXPIRY == 1
    assert lc.TRIGGER_E_EXPIRY == 15
    assert lc.TRIGGER_F_EXPIRY == 1
    # §23 order expiry untouched.
    assert lc.M5_EXPIRY_BARS == 12
    assert lc.M1_EXPIRY_BARS == 30
    # Footer wording mandated by the prompt.
    assert "NOT a trade claim" in pack.FOOTER
    assert pack.FOOTER.startswith("Stage 3 trigger visibility")
