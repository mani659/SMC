"""Step-3 LTF confirmation — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/poi_swept_ltf_confirm.py``: window containment
(strict-greater, inclusive end), trigger-letter normalization across
shapes, earliest-confirmation selection, nested-horizon monotonicity,
and episode-POI model mapping. Trigger evaluation itself is product
code (already tested). No threshold, no gate, no expectancy assertion.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "poi_swept_ltf_confirm.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "poi_swept_ltf_confirm", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["poi_swept_ltf_confirm"] = module
    spec.loader.exec_module(module)
    return module


def _comp(bar, letter):
    return {"bar": bar,
            "trigger": SimpleNamespace(value=f"{letter}_x")}


# --------------------------------------------------------------------------- #
# 1. Window rule: sweep_bar < bar <= sweep_bar + H (both edges pinned)
# --------------------------------------------------------------------------- #
def test_window_edges_strict_start_inclusive_end():
    pack = _load_pack()
    comps = [_comp(10, "F"), _comp(15, "A"), _comp(20, "B")]
    in5 = pack.completions_in_window(comps, 10, 5)
    assert [c["bar"] for c in in5] == [15]      # bar==sweep excluded ...
    in10 = pack.completions_in_window(comps, 10, 10)
    assert [c["bar"] for c in in10] == [15, 20]  # ... bar==sweep+H kept
    assert pack.completions_in_window(comps, 10, 4) == []
    assert pack.completions_in_window([], 10, 48) == []


def test_nested_horizons_monotonic():
    pack = _load_pack()
    comps = [_comp(3, "F"), _comp(12, "A"), _comp(47, "B")]
    counts = [len(pack.completions_in_window(comps, 0, h))
              for h in (5, 12, 20, 48)]
    assert counts == [1, 2, 2, 3]               # nested, never shrinking
    flags = [bool(pack.completions_in_window(comps, 0, h))
             for h in (5, 12, 20, 48)]
    assert flags == [True, True, True, True]
    assert [bool(pack.completions_in_window(comps, 40, h))
            for h in (5, 12)] == [False, True]


# --------------------------------------------------------------------------- #
# 2. Trigger letter across shapes (enum / object-with-type / string)
# --------------------------------------------------------------------------- #
def test_trigger_letter_shapes():
    pack = _load_pack()
    assert pack.trigger_letter(SimpleNamespace(value="f_bos_ob")) == "F"
    assert pack.trigger_letter(
        SimpleNamespace(type=SimpleNamespace(value="a_choch"))) == "A"
    assert pack.trigger_letter("C") == "C"
    assert pack.trigger_letter("ending_diagonal") == "ENDING"


# --------------------------------------------------------------------------- #
# 3. Earliest confirmation (bar, then letter — deterministic)
# --------------------------------------------------------------------------- #
def test_first_confirmation_order():
    pack = _load_pack()
    assert pack.first_confirmation([]) is None
    first = pack.first_confirmation([_comp(20, "F"), _comp(12, "A"),
                                     _comp(12, "B")])
    assert first["bar"] == 12
    assert pack.trigger_letter(first["trigger"]) == "A"  # tie -> letter


# --------------------------------------------------------------------------- #
# 4. Episode POI models (product-compatible tags, M8 facet preserved)
# --------------------------------------------------------------------------- #
def test_episode_poi_models():
    from smc.config.model_type import ModelType
    pack = _load_pack()
    poi = pack.episode_poi({
        "tf": "H1", "kind_tag": "M1", "all_tags": "M1+M7",
        "m8_kind": "", "direction": "LONG",
        "zone_low": 100.0, "zone_high": 110.0})
    assert poi.models == [ModelType.M1, ModelType.M7]
    assert poi.m8_kind is None
    assert poi.zone.bottom == 100.0 and poi.zone.top == 110.0
    m8 = pack.episode_poi({
        "tf": "M8-D1", "kind_tag": "M8-fvg", "all_tags": "M8-fvg",
        "m8_kind": "fvg", "direction": "SHORT",
        "zone_low": 200.0, "zone_high": 210.0})
    assert m8.models == [ModelType.M8]
    assert m8.m8_kind == "fvg"
