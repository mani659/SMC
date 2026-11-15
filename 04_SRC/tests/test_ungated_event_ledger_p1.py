"""Unit tests for new pure helpers in the ungated observation ledger."""

from pathlib import Path
import sys

import pytest

from smc.config.timeframe import Timeframe

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))
from ungated_event_ledger_p1 import _classify_bias_break, _opposite_color_index


def test_bias_break_first_and_with_bias_are_bos():
    assert _classify_bias_break(None, "LONG") == ("BOS", "LONG")
    assert _classify_bias_break("LONG", "LONG") == ("BOS", "LONG")


def test_bias_break_against_bias_is_choch_and_flips():
    assert _classify_bias_break("LONG", "SHORT") == ("CHOCH", "SHORT")
    assert _classify_bias_break("SHORT", "LONG") == ("CHOCH", "LONG")


def test_bias_break_rejects_unknown_direction():
    with pytest.raises(ValueError, match="invalid break direction"):
        _classify_bias_break(None, "FLAT")


def test_ob_helper_uses_nearest_prior_opposite_body_and_skips_doji():
    from conftest import make_candles

    candles = make_candles([
        (100, 101, 99, 100),   # doji, not opposite to either direction
        (100, 102, 98, 99),    # bearish, opposite to LONG
        (99, 103, 99, 102),    # bullish, nearest opposite to SHORT
        (102, 104, 101, 101),  # BOS bar excluded from origin search
    ], timeframe=Timeframe.M5)
    assert _opposite_color_index(candles, 3, "SHORT") == 2
    assert _opposite_color_index(candles, 3, "LONG") == 1


def test_ob_helper_returns_none_when_no_prior_opposite_body():
    from conftest import make_candles

    candles = make_candles([
        (100, 101, 99, 100),
        (100, 102, 99, 101),
    ], timeframe=Timeframe.M5)
    assert _opposite_color_index(candles, 1, "LONG") is None
