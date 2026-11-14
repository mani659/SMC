"""Harness M15 hygiene — product diagnostics must be product-complete.

The product runtime requires the POI inventory set (D1, H4, H1, M15); a
harness supplying H1/H4/D1 only makes every batch fail and reports an empty
funnel. These tests pin the shared helper that derives the missing series
(closed bars only) or fails loudly naming them.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from smc.config.timeframe import Timeframe

_HELPER_PATH = (
    Path(__file__).resolve().parents[2]
    / "06_RESEARCH" / "scripts" / "lib" / "product_htf_series.py"
)
_spec = importlib.util.spec_from_file_location("product_htf_series", _HELPER_PATH)
helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helper)

TF = Timeframe.M5


def _bars(candle_factory, count=64, timeframe=TF):
    rows = [(100.0 + i * 0.1, 100.15 + i * 0.1, 99.9 + i * 0.1, 100.1 + i * 0.1)
            for i in range(count)]
    return candle_factory(rows, timeframe=timeframe)


# ---------------------------------------------------------------------- #
# T1 — missing M15 is derived from M5, non-empty and product-complete
# ---------------------------------------------------------------------- #
def test_t1_missing_m15_is_derived(candle_factory):
    m5 = _bars(candle_factory)
    frames = {
        Timeframe.H1: _bars(candle_factory, timeframe=Timeframe.H1),
        Timeframe.H4: _bars(candle_factory, timeframe=Timeframe.H4),
        Timeframe.D1: _bars(candle_factory, timeframe=Timeframe.D1),
    }
    out = helper.ensure_product_detection_frames(frames, source=m5)
    assert Timeframe.M15 in out and out[Timeframe.M15]
    helper.assert_product_detection_complete(out)


# ---------------------------------------------------------------------- #
# T2 — a genuinely missing required TF fails loudly and names it
# ---------------------------------------------------------------------- #
def test_t2_missing_h4_raises_with_name(candle_factory):
    frames = {Timeframe.M15: _bars(candle_factory, timeframe=Timeframe.M15)}
    with pytest.raises(helper.MissingProductHtfSeries) as excinfo:
        helper.assert_product_detection_complete(frames)
    assert "H4" in str(excinfo.value)

    with pytest.raises(helper.MissingProductHtfSeries) as excinfo:
        helper.ensure_product_detection_frames(frames)  # no source to resample
    assert "H4" in str(excinfo.value)


# ---------------------------------------------------------------------- #
# T3 — derived bars are closed-bar only (no future leak)
# ---------------------------------------------------------------------- #
def test_t3_derived_m15_is_closed_bar(candle_factory):
    m5 = _bars(candle_factory, count=64)
    # A 5-hour M5 slice has no closed D1 bucket; M15/H1/H4 are the derivable set.
    out = helper.ensure_product_detection_frames({}, source=m5, require_d1=False)
    m15 = out[Timeframe.M15]
    assert m15
    source_last = m5[-1]
    # last derived bucket must have closed by the source's last close ...
    from datetime import timedelta
    assert (m15[-1].timestamp + timedelta(minutes=15)
            <= source_last.timestamp + timedelta(minutes=5))
    # ... and never start after the last source bar
    assert m15[-1].timestamp <= source_last.timestamp


# --------------------------------------------------------------------- #
# T4 — the diagnostic entrypoint imports and is callable
# --------------------------------------------------------------------- #
def test_t4_post_c2_entrypoint_imports():
    path = (Path(__file__).resolve().parents[2]
            / "06_RESEARCH" / "scripts" / "post_c2_diagnostic.py")
    spec = importlib.util.spec_from_file_location("post_c2_diagnostic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.main)
