"""LTF confirmation pack — focused tests (identification only).

Covers: deterministic sample selection (caps, interleaving, full-panel
sets), plain-tag presence (TF-suffixed labels, never module paths),
look-ahead consistency (existing constants only, same window rule for
every structure), and pinned strategy constants (no locked-constant
change may pass unnoticed).
"""

from __future__ import annotations

import importlib.util
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "ltf_confirmation_pack.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location("ltf_confirmation_pack", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ltf_confirmation_pack"] = module
    spec.loader.exec_module(module)
    return module


def _struct(idx: int, panels: int, active: bool) -> dict:
    ts = datetime(2025, 6, 1, tzinfo=timezone.utc) + timedelta(hours=idx)
    return {"event_id": f"evt-{idx:04d}", "panels": panels,
            "ts_utc": ts.isoformat(), "_active": active}


# --------------------------------------------------------------------------- #
# 1. Deterministic sample selection
# --------------------------------------------------------------------------- #
def test_selection_respects_all_caps():
    pack = _load_pack()
    active = [_struct(i, 3 if i % 2 else 2, True) for i in range(40)]
    silent = [_struct(100 + i, 2, False) for i in range(30)]
    picked = pack.select_structures(active, silent)
    assert len(picked) <= pack.MAX_ACTIVE + pack.MAX_SILENT
    assert sum(1 for p in picked if p["_active"]) <= pack.MAX_ACTIVE
    assert sum(1 for p in picked if not p["_active"]) <= pack.MAX_SILENT
    assert sum(p["panels"] for p in picked) <= pack.PANEL_CAP


def test_selection_is_stable_and_interleaves_classes():
    pack = _load_pack()
    active = [_struct(i, 3, True) for i in range(20)]
    silent = [_struct(100 + i, 2, False) for i in range(20)]
    a = pack.select_structures(active, silent)
    b = pack.select_structures(list(active), list(silent))
    assert [p["event_id"] for p in a] == [p["event_id"] for p in b]
    # Both classes represented (interleaved) — not 12 actives then leftovers.
    assert any(p["_active"] for p in a) and any(not p["_active"] for p in a)
    # First picked is active, second silent (pair order).
    assert a[0]["_active"] and not a[1]["_active"]


def test_selection_never_picks_partial_structures():
    pack = _load_pack()
    # One structure whose 3-panel set cannot fit the remaining budget:
    active = [_struct(0, 3, True), _struct(1, 40, True)]
    picked = pack.select_structures(active, [], panel_cap=10)
    assert [p["event_id"] for p in picked] == ["evt-0000"]  # second skipped


# --------------------------------------------------------------------------- #
# 2. Plain-tag presence
# --------------------------------------------------------------------------- #
def test_ledger_rows_carry_plain_tf_suffixed_tags_only():
    pack = _load_pack()
    structure = {"event_id": "evt-1", "plain_tag": "ORDER BLOCK (H4)",
                 "direction": "LONG", "zone_low": 100.0, "zone_high": 101.0,
                 "ts_utc": "2025-07-01T00:00:00+00:00",
                 "notes_base": "", "route": None}
    linked = [
        {"kind": "sweep", "tf": "M15", "tag": "SWEEP (M15)",
         "direction": "LONG", "ts": "2025-07-01T05:00:00+00:00",
         "lo": 100.5, "hi": 100.5, "level_text": "100.5",
         "relation": "inside", "trigger": "none", "notes": "kind=sweep"},
        {"kind": "trigger", "tf": "M5", "tag": "TRIGGER F (M5)",
         "direction": "LONG", "ts": "2025-07-01T04:30:00+00:00",
         "lo": 100.4, "hi": 100.4, "level_text": "100.4",
         "relation": "inside", "trigger": "F", "notes": "kind=trigger"},
    ]
    rows = pack.build_structure_row(structure, linked)
    assert len(rows) == 2
    for row in rows:
        for col in ("htf_plain_tag", "ltf_plain_tag"):
            tag = row[col]
            assert tag.endswith(("(H4)", "(M15)", "(M5)")), tag
            assert "smc." not in tag and "._" not in tag, tag
        assert row["route_would_form"] == "no"
    # Silent structure gets an explicit NONE row (never a module path).
    silent_rows = pack.build_structure_row(structure, [])
    assert silent_rows[0]["ltf_plain_tag"] == "NONE"
    assert silent_rows[0]["relation_to_htf"] == "none"
    assert silent_rows[0]["trigger_type"] == "none"


# --------------------------------------------------------------------------- #
# 3. Look-ahead consistency
# --------------------------------------------------------------------------- #
def test_lookahead_uses_existing_constants_only():
    from smc.config.locked_constants import TRIGGER_A_EXPIRY
    from smc.triggers.trigger_expiry import poi_give_up_bars
    pack = _load_pack()
    assert pack.LA_M5_BARS == poi_give_up_bars() == TRIGGER_A_EXPIRY == 20
    assert pack.LA_M15_BARS == math.ceil(20 * 5 / 15) == 7
    # M15 window covers at least the M5 window's wall-clock time.
    assert pack.LA_M15_BARS * 15 >= pack.LA_M5_BARS * 5


def test_lookahead_window_same_rule_every_structure():
    pack = _load_pack()
    # Identical length for every anchor (except the disclosed series-end clamp).
    windows = [pack.lookahead_window(arm, pack.LA_M5_BARS, 10_000)
               for arm in (0, 137, 5_000, 9_000)]
    lengths = [end - start + 1 for start, end in windows]
    assert len(set(lengths)) == 1            # == LA_M5_BARS + 1 bars
    assert lengths[0] == pack.LA_M5_BARS + 1
    start, end = pack.lookahead_window(9_995, pack.LA_M5_BARS, 10_000)
    assert end == 9_999                       # clamped at series end


def test_relation_to_zone_is_honest():
    pack = _load_pack()
    assert pack.relation_to_zone(100, 101, 100.5, 100.5) == "inside"
    assert pack.relation_to_zone(100, 101, 101.2, 101.2) == "above"
    assert pack.relation_to_zone(100, 101, 99.0, 99.0) == "below"
    assert pack.relation_to_zone(100, 101, 99.5, 100.2) == "retest"
    assert pack.relation_to_zone(100, 101, 99.0, 99.9) == "below"
    assert pack.relation_to_zone(100, 101, None, None) == "none"


# --------------------------------------------------------------------------- #
# 4. No strategy constant changes (pinned values — a change fails loudly)
# --------------------------------------------------------------------------- #
def test_strategy_constants_unchanged():
    from smc.config import locked_constants as lc
    assert lc.M5_EXPIRY_BARS == 12
    assert lc.M1_EXPIRY_BARS == 30
    assert lc.TRIGGER_A_EXPIRY == 20
    assert lc.TRIGGER_B_EXPIRY == 30
    assert lc.TRIGGER_C_EXPIRY_EXTRA == 3
    assert lc.TRIGGER_D_EXPIRY == 1
    assert lc.TRIGGER_E_EXPIRY == 15
    assert lc.TRIGGER_F_EXPIRY == 1
