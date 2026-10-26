"""Structure-draw publisher — focused tests (visualization only).

Locks the design-lock-2026-10-22 publisher (``smc.live.structure_publish``):
schema-v1 header shape, record fields, the ≤40-zone readability cap
(armed-first, W1→D1→H4→H1 order), the documented sweep-price derivation
(linked POI's swept-side zone edge — never invented), PLAN omission when a
level is unknown, empty-snapshot clear payload, atomic publish behavior,
and policy-ordered path resolution. NO MT5 import is needed and none is
made — pure parsing + temp-path writes only.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from smc.live.heartbeat_path import (
    HEARTBEAT_FILENAME,
    ea_readable_heartbeat_path,
)
from smc.live.structure_publish import (
    MAX_ZONES,
    SCHEMA_LINE,
    STRUCTURE_DRAW_FILENAME,
    StructureDrawPublisher,
    build_structure_draw_payload,
    resolve_structure_draw_path,
)

_STAMP = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
_NOW_EPOCH = _STAMP.strftime("%Y-%m-%dT%H:%M:%SZ")


def _poi(poi_id: str, tf: str, side: str, low: float, high: float,
         *, armed: bool = True, state: str = "SEEKING",
         posture: str = "posture|ok") -> dict:
    return {"id": poi_id, "tf": tf, "direction": side, "zone_low": low,
            "zone_high": high, "armed": armed, "state": state,
            "posture": posture}


def _snapshot(pois=None, sweeps=None, plan=None) -> dict:
    return {"now": _STAMP, "pois": pois or [], "sweeps": sweeps or [],
            "plan": plan or []}


def _records(payload: str) -> list[str]:
    """All record lines (schema + header dropped)."""
    return payload.splitlines()[2:]


def _find(records: list[str], kind: str, poi_id: str | None = None):
    out = []
    for line in records:
        f = line.split("|")
        if f[0] != kind:
            continue
        if poi_id is not None and f[1] != poi_id:
            continue
        out.append(f)
    return out


# --------------------------------------------------------------------------- #
# 1. Header shape: schema line + ts_utc/symbol, then records only
# --------------------------------------------------------------------------- #
def test_header_shape_and_symbol():
    payload = build_structure_draw_payload(
        _snapshot([_poi("p1", "H1", "BULL", 4000.0, 4001.0)]),
        symbol="XAUUSDm", now=_STAMP)
    lines = payload.splitlines()
    assert lines[0] == SCHEMA_LINE == "SMC_STRUCTURE_DRAW v1"
    assert lines[1] == f"ts_utc={_NOW_EPOCH} symbol=XAUUSDm"
    assert _find(_records(payload), "POI")


# --------------------------------------------------------------------------- #
# 2. POI record fields; malformed rows never emitted
# --------------------------------------------------------------------------- #
def test_poi_record_fields():
    payload = build_structure_draw_payload(
        _snapshot([_poi("poi #1", "H1", "BULLISH", 4000.0, 4001.5)]),
        symbol="XAUUSDm", now=_STAMP)
    rows = _find(_records(payload), "POI")
    # Object-name-safe id (spaces → _), mnemonically same; never crash.
    assert rows[0][:6] == ["POI", "poi__1", "H1", "BULL", "4000.00000", "4001.50000"]
    assert rows[0][6] == "ARMED"


def test_poi_row_missing_zone_or_side_is_skipped():
    payload = build_structure_draw_payload(
        _snapshot([
            {"id": "x", "tf": "H1", "direction": "BULL",
             "zone_low": None, "zone_high": 4001.0, "armed": False},
            {"id": "y", "tf": "H1", "direction": "so-so",
             "zone_low": 4000.0, "zone_high": 4001.0, "armed": False},
            _poi("ok", "H1", "BEAR", 3999.0, 4001.0, armed=False),
        ]), symbol="XAUUSDm", now=_STAMP)
    rows = _find(_records(payload), "POI")
    assert len(rows) == 1 and rows[0][1] == "ok" and rows[0][6] == "UNARMED"


# --------------------------------------------------------------------------- #
# 3. Cap: max 40 zones, armed first, W1 → D1 → H4 → H1 section order
# --------------------------------------------------------------------------- #
def test_cap_keeps_armed_and_respects_section_order():
    pois = []
    # 45 unarmed H1 zones flood the cap; 3 armed zones (H1/D1/W1) survive.
    for i in range(45):
        pois.append(_poi(f"h{i}", "H1", "BULL", 4000, 4001, armed=False))
    pois.append(_poi("armed_h1", "H1", "BULL", 4000, 4001))
    pois.append(_poi("armed_d1", "D1", "BEAR", 3990, 3991))
    pois.append(_poi("armed_w1", "W1", "BULL", 3980, 3981))
    payload = build_structure_draw_payload(
        _snapshot(pois), symbol="XAUUSDm", now=_STAMP)
    rows = _find(_records(payload), "POI")
    armed = [r for r in rows if r[6] == "ARMED"]
    assert len(rows) == MAX_ZONES == 40
    assert [r[1] for r in armed] == ["armed_w1", "armed_d1", "armed_h1"]


# --------------------------------------------------------------------------- #
# 4. Sweep derivation (documented): linked POI's swept-side zone edge;
#    never invented; sweeps of capped-away POIs are not drawn
# --------------------------------------------------------------------------- #
def test_sweep_level_is_linked_poi_swept_side_edge():
    snap = _snapshot(
        pois=[_poi("p1", "H1", "BEAR", 4000.0, 4001.0)],
        sweeps=[{"poi_id": "p1", "side": "SELL", "magnitude_atr": 1.25}],
    )
    rows = _find(_records(_records_snapshot_payload(snap)), "SWEEP")
    assert len(rows) == 1
    assert rows[0] == ["SWEEP", "p1", "SELL", "4001.00000", "1.25"]


def test_sweep_buy_side_uses_zone_low_and_missing_link_is_dropped():
    snap = _snapshot(
        pois=[_poi("p1", "H1", "BULL", 4000.0, 4001.0),
              _poi("p2", "H4", "BULL", 3900.0, 3901.0)],
        sweeps=[{"poi_id": "p1", "side": "BUY", "magnitude_atr": None},
                {"poi_id": "ghost", "side": "BUY", "magnitude_atr": 2.0},
                {"poi_id": "p2", "side": "weird", "magnitude_atr": 1.0}],
    )
    rows = _find(_records(_records_snapshot_payload(snap)), "SWEEP")
    assert len(rows) == 1
    assert rows[0] == ["SWEEP", "p1", "BUY", "4000.00000", "n/a"]


def _records_snapshot_payload(snap) -> str:
    return build_structure_draw_payload(snap, symbol="XAUUSDm", now=_STAMP)


# --------------------------------------------------------------------------- #
# 5. SEEK records: armed POIs only, posture pipes flattened; zone gets
#    the state, the raw posture text is never carried verbatim
# --------------------------------------------------------------------------- #
def test_seek_records_for_armed_pois_with_pipe_safe_posture():
    snap = _snapshot([
        _poi("p1", "H1", "BULL", 4000.0, 4001.0, state="TESTED", posture="a|b"),
        _poi("p2", "H1", "BULL", 4000.0, 4001.0, armed=False),
    ])
    rows = _find(_records(_records_snapshot_payload(snap)), "SEEK")
    assert len(rows) == 1
    assert rows[0] == ["SEEK", "p1", "TESTED", "a b"]


# --------------------------------------------------------------------------- #
# 6. PLAN: emitted only when ALL THREE levels exist (omit if unknown)
# --------------------------------------------------------------------------- #
def test_plan_requires_all_three_levels():
    snap = _snapshot(plan=[
        {"poi_id": "p_full", "entry": 4000.5, "sl": 3998.0, "tp": 4005.0},
        {"poi_id": "p_partial", "entry": 4000.5, "sl": 3998.0, "tp": None},
    ])
    rows = _find(_records(_records_snapshot_payload(snap)), "PLAN")
    assert len(rows) == 1
    assert rows[0] == ["PLAN", "p_full", "4000.50000", "3998.00000", "4005.00000"]


# --------------------------------------------------------------------------- #
# 7. Empty snapshot → header-only payload (the EA clears its prefix)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("snapshot", [None, {}, _snapshot()])
def test_empty_snapshot_is_header_only_clear_payload(snapshot):
    payload = build_structure_draw_payload(snapshot, symbol="XAUUSDm",
                                           now=_STAMP)
    lines = payload.splitlines()
    assert lines[0] == SCHEMA_LINE
    assert lines[1] == f"ts_utc={_NOW_EPOCH} symbol=XAUUSDm"
    assert len(lines) == 2


# --------------------------------------------------------------------------- #
# 8. Path resolution: data folder > install-dir derivation > explicit > fallback
# --------------------------------------------------------------------------- #
def test_path_resolution_order(tmp_path: Path):
    data = tmp_path / "data"
    derived = resolve_structure_draw_path(None, str(data))
    assert derived == data / "MQL5" / "Files" / STRUCTURE_DRAW_FILENAME

    install = tmp_path / "terminal64.exe"
    explicit = tmp_path / "elsewhere" / "draw.txt"
    via_install = resolve_structure_draw_path(str(install), None)
    assert via_install == install.parent / "MQL5" / "Files" / STRUCTURE_DRAW_FILENAME

    via_explicit = resolve_structure_draw_path(
        str(install), str(data), explicit_path=str(explicit))
    # Data folder still wins over explicit when present (EA-sandbox=truth).
    assert via_explicit == data / "MQL5" / "Files" / STRUCTURE_DRAW_FILENAME

    fallback = resolve_structure_draw_path(None, None, default_fallback="logs/x.txt")
    assert fallback == Path("logs/x.txt")


def test_draw_path_mirrors_heartbeat_directory(tmp_path: Path):
    """Same MQL5/Files dir as the heartbeat when terminal_path is portable."""
    hp = ea_readable_heartbeat_path(str(tmp_path / "terminal64.exe"))
    dp = resolve_structure_draw_path(str(tmp_path / "terminal64.exe"))
    assert hp.name == HEARTBEAT_FILENAME
    assert dp.name == STRUCTURE_DRAW_FILENAME
    assert dp.parent == hp.parent


# --------------------------------------------------------------------------- #
# 9. Publisher: atomic full rewrite; clear-content publish; failure → False
# --------------------------------------------------------------------------- #
def test_publisher_writes_full_and_then_clear(tmp_path: Path):
    pub = StructureDrawPublisher(tmp_path / "sub" / STRUCTURE_DRAW_FILENAME)
    assert (tmp_path / "sub").exists() is False  # no dir made until publish
    ok = pub.publish(_snapshot([_poi("p1", "H1", "BULL", 4000.0, 4001.0)]),
                     symbol="XAUUSDm", now=_STAMP)
    assert ok is True
    text = (tmp_path / "sub" / STRUCTURE_DRAW_FILENAME).read_text()
    assert text.splitlines()[0] == SCHEMA_LINE
    assert _find(_records(text), "POI")
    assert not pub.last_payload.endswith("\n") is False

    # Empty snapshot → header-only (the EA's clear path), same file.
    assert pub.publish(None, symbol="XAUUSDm", now=_STAMP) is True
    text2 = (tmp_path / "sub" / STRUCTURE_DRAW_FILENAME).read_text()
    assert len(text2.splitlines()) == 2
    # No tmp residue after publish (atomic rename completed).
    assert not list(tmp_path.rglob("*.tmp"))


def test_publisher_fails_safe(tmp_path: Path):
    # A directory where the file should be → OSError path → False, no raise.
    bad = tmp_path / "blocked"
    bad.mkdir()
    pub = StructureDrawPublisher(bad)
    (bad / STRUCTURE_DRAW_FILENAME).mkdir()   # write target is a directory
    assert pub.publish(_snapshot(), symbol="XAUUSDm", now=_STAMP) is False


def test_publisher_ascii_only_output(tmp_path: Path):
    payload = build_structure_draw_payload(
        _snapshot([_poi("p1", "H1", "BULL", 4000.0, 4001.0)]),
        symbol="XAUUSDm", now=_STAMP)
    payload.encode("ascii")              # must never raise
    os_label = (tmp_path / "probe.txt")
    os_label.write_text(payload, encoding="ascii")


# --------------------------------------------------------------------------- #
# 10. Import discipline: no MT5 anywhere in this module
# --------------------------------------------------------------------------- #
def test_no_mt5_import_needed():
    import smc.live.structure_publish as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert 'import MT5' not in src and 'import MetaTrader5' not in src
