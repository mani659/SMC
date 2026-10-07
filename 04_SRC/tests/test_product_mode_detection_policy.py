"""Product-mode detection policy — H4+H1 enforced at construction.

Unified audit ruling (2026-10-06, LOCKED_DECISIONS §4/§21 supersession):
when ``allow_single_tf_degraded`` is False, a ``MultiTFProductRuntime``
cannot be constructed whose detection set omits H4 or H1 — the loud error
names every missing required timeframe. The explicit degraded opt-in skips
the check (tests/legacy only).
"""

from __future__ import annotations

import pytest

from smc.config.timeframe import Timeframe
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime

H1, H4, W1, D1 = (Timeframe.H1, Timeframe.H4, Timeframe.W1, Timeframe.D1)


def test_rejects_detection_set_missing_h1():
    with pytest.raises(ValueError) as excinfo:
        MultiTFProductRuntime(detection_timeframes=(H4,))
    message = str(excinfo.value)
    assert "H1" in message and "H4+H1" in message
    assert "allow_single_tf_degraded" in message


def test_rejects_detection_set_missing_h4():
    with pytest.raises(ValueError) as excinfo:
        MultiTFProductRuntime(detection_timeframes=(H1,))
    assert "H4" in str(excinfo.value)


def test_rejects_context_only_detection_set():
    with pytest.raises(ValueError) as excinfo:
        MultiTFProductRuntime(detection_timeframes=(W1, D1))
    message = str(excinfo.value)
    assert "H4" in message and "H1" in message


def test_accepts_h4_h1_and_extended_sets():
    for detection in ((H4, H1), (W1, H4, H1), (H4, H1, D1), (W1, D1, H4, H1)):
        runtime = MultiTFProductRuntime(detection_timeframes=detection)
        assert runtime.detection_timeframes == tuple(detection)


def test_default_construction_still_product_compliant():
    runtime = MultiTFProductRuntime()
    assert runtime.detection_timeframes == (H4, H1)
    assert runtime.allow_single_tf_degraded is False


def test_degraded_opt_in_still_allowed():
    # The explicit opt-in skips the construction-time H4+H1 check: an
    # incomplete detection set is allowed only here (tests/legacy).
    for detection in ((H4,), (H1,), (W1, D1)):
        runtime = MultiTFProductRuntime(
            detection_timeframes=detection, allow_single_tf_degraded=True)
        assert runtime.detection_timeframes == tuple(detection)
        assert runtime.allow_single_tf_degraded is True
