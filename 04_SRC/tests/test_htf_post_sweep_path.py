"""HTF post-sweep path — focused tests (research only).

Locks the frozen pieces of
``06_RESEARCH/scripts/htf_post_sweep_path.py``: continuation direction
mapping, sweep-bar-exclusive window indexing, level-referenced sign
conventions on both sides, reclaim-fail definitions, frozen horizon
sets, and strict truncation. No threshold, no gate, no expectancy
assertion anywhere.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "htf_post_sweep_path.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "htf_post_sweep_path", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["htf_post_sweep_path"] = module
    spec.loader.exec_module(module)
    return module


def _bars(n, start=None, o=100.0, h=100.5, l=99.5, c=100.0, tf="H1"):
    from smc.config.timeframe import Timeframe
    from smc.core.candle import Candle
    t0 = start or datetime(2025, 6, 1, tzinfo=timezone.utc)
    step = {"H1": 60, "H4": 240, "M5": 5}[tf]
    return [Candle(timestamp=t0 + timedelta(minutes=step * i), open=o,
                   high=h, low=l, close=c,
                   timeframe=getattr(Timeframe, tf))
            for i in range(n)]


# --------------------------------------------------------------------------- #
# 1. Continuation mapping (reporting only, unknown pools are loud)
# --------------------------------------------------------------------------- #
def test_continuation_signs():
    pack = _load_pack()
    assert pack.continuation_signs("bsl") == (True, -1)    # downside
    assert pack.continuation_signs("ssl") == (False, 1)    # upside
    assert pack.continuation_signs("BSL") == (True, -1)
    try:
        pack.continuation_signs("major_structural")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown pool must raise, never mis-sign")


# --------------------------------------------------------------------------- #
# 2. Window indexing is exclusive of the sweep bar
# --------------------------------------------------------------------------- #
def test_window_excludes_sweep_bar():
    pack = _load_pack()
    t0 = datetime(2025, 6, 1, tzinfo=timezone.utc)
    # Bar 0 (the "sweep" bar) has huge range; bar 1 is exactly flat AT
    # the level. H=1 reads ONLY bar 1: zero excursion despite bar 0.
    bars = [_bars(1, start=t0, o=100.0, h=110.0, l=90.0, c=100.0,
                  tf="H1")[0],
            _bars(1, start=t0 + timedelta(hours=1), o=100.0, h=100.0,
                  l=100.0, c=100.0, tf="H1")[0]]
    m = pack.path_metrics(bars, 1, 1, level=100.0, is_short_cont=True,
                          atr=2.0)
    assert m["mfe_atr"] == 0.0 and m["mae_atr"] == 0.0
    assert m["hit_plus1atr"] is False and m["adverse_1atr"] is False
    assert m["time_to_mfe_bars"] is None and m["time_to_mae_bars"] is None


# --------------------------------------------------------------------------- #
# 3. Level-referenced sign conventions, both sides
# --------------------------------------------------------------------------- #
def test_sign_conventions_bsl_and_ssl():
    pack = _load_pack()
    # BSL: level 100 swept, next bar drops to 97 then closes 98.
    bars = [_bars(1)[0],
            _bars(1, start=datetime(2025, 6, 1, 1, tzinfo=timezone.utc),
                  o=99.0, h=99.5, l=97.0, c=98.0, tf="H1")[0]]
    m = pack.path_metrics(bars, 1, 1, level=100.0, is_short_cont=True,
                          atr=2.0)
    assert m["mfe_atr"] == (100.0 - 97.0) / 2.0   # downside favors BSL
    assert m["mae_atr"] == 0.0                    # high 99.5 < level
    assert m["reclaim_fail"] is False             # close 98 < 100
    # SSL mirror: level 100 swept, next bar rallies to 103, closes 102.
    bars2 = [_bars(1)[0],
             _bars(1, start=datetime(2025, 6, 1, 1, tzinfo=timezone.utc),
                   o=101.0, h=103.0, l=100.5, c=102.0, tf="H1")[0]]
    m2 = pack.path_metrics(bars2, 1, 1, level=100.0, is_short_cont=False,
                           atr=2.0)
    assert m2["mfe_atr"] == (103.0 - 100.0) / 2.0
    assert m2["mae_atr"] == 0.0
    assert m2["reclaim_fail"] is False


def test_reclaim_fail_definitions():
    pack = _load_pack()
    t0 = datetime(2025, 6, 1, tzinfo=timezone.utc)
    # BSL sweep (close back below 100), then a close back ABOVE -> fail.
    bars = [_bars(1, start=t0)[0],
            _bars(1, start=t0 + timedelta(hours=1), o=99.0, h=101.0,
                  l=98.0, c=100.5, tf="H1")[0]]
    m = pack.path_metrics(bars, 1, 1, level=100.0, is_short_cont=True,
                          atr=2.0)
    assert m["reclaim_fail"] is True
    # SSL mirror: close back BELOW the level -> fail.
    bars = [_bars(1, start=t0)[0],
            _bars(1, start=t0 + timedelta(hours=1), o=101.0, h=102.0,
                  l=99.0, c=99.5, tf="H1")[0]]
    m = pack.path_metrics(bars, 1, 1, level=100.0, is_short_cont=False,
                          atr=2.0)
    assert m["reclaim_fail"] is True
    # Exact-level close is not beyond -> no fail either side.
    bars = [_bars(1, start=t0)[0],
            _bars(1, start=t0 + timedelta(hours=1), o=99.0, h=100.0,
                  l=98.0, c=100.0, tf="H1")[0]]
    m = pack.path_metrics(bars, 1, 1, level=100.0, is_short_cont=True,
                          atr=2.0)
    assert m["reclaim_fail"] is False


def test_zero_atr_yields_nones_not_zeros():
    pack = _load_pack()
    bars = _bars(3)
    m = pack.path_metrics(bars, 1, 2, level=100.0, is_short_cont=True,
                          atr=0.0)
    assert all(v is None for v in m.values())


# --------------------------------------------------------------------------- #
# 4. Frozen horizon sets (directive values, no mining)
# --------------------------------------------------------------------------- #
def test_frozen_horizons_and_secondary():
    pack = _load_pack()
    assert pack.HORIZONS == (1, 3, 5, 10)
    assert pack.M5_SECONDARY == {"H4": 20, "H1": 5}
