"""Product-mode detection policy — M2 menu tiers accepted.

M2: product mode accepts detection sets that include the menu tiers
{D1, H4, H1, M15}. The legacy H4+H1-only minimum is relaxed; loud-fail
on empty/nonsensical sets remains. The explicit degraded opt-in skips the
check (tests/legacy only).
"""

from __future__ import annotations

import pytest

from smc.config.timeframe import Timeframe
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime

H1, H4, W1, D1, M15 = (Timeframe.H1, Timeframe.H4, Timeframe.W1, Timeframe.D1, Timeframe.M15)


def test_accepts_menu_tier_alone():
    for detection in ((H4,), (H1,), (D1,), (M15,)):
        runtime = MultiTFProductRuntime(detection_timeframes=detection)
        assert runtime.detection_timeframes == tuple(detection)


def test_accepts_h4_h1_and_extended_sets():
    for detection in ((H4, H1), (W1, H4, H1), (H4, H1, D1), (W1, D1, H4, H1), (D1, H4, H1, M15)):
        runtime = MultiTFProductRuntime(detection_timeframes=detection)
        assert runtime.detection_timeframes == tuple(detection)


def test_rejects_context_only_detection_set():
    with pytest.raises(ValueError) as excinfo:
        MultiTFProductRuntime(detection_timeframes=(W1,))
    message = str(excinfo.value)
    assert "menu detection timeframe" in message
    assert "allow_single_tf_degraded" in message


def test_default_construction_still_product_compliant():
    runtime = MultiTFProductRuntime()
    assert runtime.detection_timeframes == (D1, H4, H1, M15)
    assert runtime.allow_single_tf_degraded is False


def test_degraded_opt_in_still_allowed():
    # The explicit opt-in skips the construction-time H4+H1 check: an
    # incomplete detection set is allowed only here (tests/legacy).
    for detection in ((H4,), (H1,), (W1, D1)):
        runtime = MultiTFProductRuntime(
            detection_timeframes=detection, allow_single_tf_degraded=True)
        assert runtime.detection_timeframes == tuple(detection)
        assert runtime.allow_single_tf_degraded is True
