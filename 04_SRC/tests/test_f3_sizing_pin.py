"""F3 — sizing pinned to the broker (unit value, refusal, cap KPI).

Money-safety tests only: the derivation of "account currency per 1.0 price
unit per 1.0 lot" from ``symbol_info``, the configured-vs-derived pin and its
refusal, and the §28.7 cap KPI. No strategy/threshold assertions.
"""

from __future__ import annotations

import json
import sys
import types
from datetime import datetime

import pytest

from smc.config.locked_constants import LOT_MAX_SAFETY
from smc.core.enums import Direction
from smc.live.operator_config import ALLOWED_KEYS, ConfigError, OperatorConfig, load_operator_config
from smc.live.run_operator import OperatorSession
from smc.paper.runner import PaperRunner
from smc.risk.broker_units import (
    SIZING_PIN_TOLERANCE_REL,
    BrokerUnitsError,
    SizingPinError,
    assert_sizing_pin,
    check_sizing_pin,
    derive_price_value_per_lot,
)
from smc.risk.lot_sizing import sized_lots, sized_lots_detail
from smc.risk.risk_engine import RiskAction, RiskEngine
from smc.risk.risk_engine import EntryRequest


def _symbol_info(**overrides):
    """Standard broker symbol_info surface (XAUUSD: 100 oz, 0.01 tick)."""
    base = dict(
        name="XAUUSDm",
        digits=3,
        trade_contract_size=100.0,
        trade_tick_size=0.01,
        trade_tick_value=1.0,
        trade_tick_value_profit=1.0,
        trade_tick_value_loss=1.0,
        currency_profit="USD",
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


# --------------------------------------------------------------------------- #
# Derivation
# --------------------------------------------------------------------------- #
def test_gold_100oz_derives_100_per_price_unit():
    units = derive_price_value_per_lot(_symbol_info(), account_currency="USD")
    assert units.price_value_per_lot == pytest.approx(100.0)
    assert units.source == "tick_value"
    assert units.contract_size == pytest.approx(100.0)


def test_loss_side_tick_value_is_preferred():
    info = _symbol_info(trade_tick_value_loss=0.2, trade_tick_value=1.0)
    units = derive_price_value_per_lot(info, account_currency="USD")
    # 0.2 per 0.01 tick = 20.0 per price unit — the side a stop is charged on.
    assert units.price_value_per_lot == pytest.approx(20.0)


def test_contract_size_fallback_when_currency_matches():
    info = _symbol_info(trade_tick_size=0.0, trade_tick_value=0.0)
    units = derive_price_value_per_lot(info, account_currency="usd")
    assert units.price_value_per_lot == pytest.approx(100.0)
    assert units.source == "contract_size"


def test_contract_fallback_refuses_currency_mismatch():
    info = _symbol_info(trade_tick_size=0.0, trade_tick_value=0.0, currency_profit="EUR")
    with pytest.raises(BrokerUnitsError, match="no conversion"):
        derive_price_value_per_lot(info, account_currency="USD")


def test_contract_fallback_refuses_unknown_account_currency():
    info = _symbol_info(trade_tick_size=0.0, trade_tick_value=0.0)
    with pytest.raises(BrokerUnitsError, match="account currency is unknown"):
        derive_price_value_per_lot(info)


def test_unusable_spec_refuses_instead_of_guessing():
    info = _symbol_info(trade_tick_size=0.0, trade_tick_value=0.0, trade_contract_size=0.0)
    with pytest.raises(BrokerUnitsError, match="no usable"):
        derive_price_value_per_lot(info, account_currency="USD")
    with pytest.raises(BrokerUnitsError):
        derive_price_value_per_lot(None)


# --------------------------------------------------------------------------- #
# Pin
# --------------------------------------------------------------------------- #
def test_pin_passes_on_match_and_within_tolerance():
    units = derive_price_value_per_lot(_symbol_info(), account_currency="USD")
    assert check_sizing_pin(100.0, units).ok
    edge = 100.0 * (1.0 + SIZING_PIN_TOLERANCE_REL)
    assert check_sizing_pin(edge, units).ok


def test_pin_refuses_the_10x_unit_error():
    units = derive_price_value_per_lot(_symbol_info(), account_currency="USD")
    verdict = check_sizing_pin(10.0, units)
    assert verdict.ok is False
    assert verdict.relative_diff == pytest.approx(0.9)
    assert verdict.configured == 10.0 and verdict.derived == 100.0


def test_pin_refuses_beyond_tolerance_and_on_nonpositive():
    units = derive_price_value_per_lot(_symbol_info(), account_currency="USD")
    assert not check_sizing_pin(101.5, units).ok
    assert not check_sizing_pin(0.0, units).ok


def test_assert_pin_raises_with_both_values_in_message():
    units = derive_price_value_per_lot(_symbol_info(), account_currency="USD")
    with pytest.raises(SizingPinError) as caught:
        assert_sizing_pin(10.0, units)
    message = str(caught.value)
    assert "configured=10" in message
    assert "derived=100" in message
    assert "MISMATCH" in message


# --------------------------------------------------------------------------- #
# Sizing KPI (cap + effective risk)
# --------------------------------------------------------------------------- #
def test_cap_binds_and_effective_risk_is_reported():
    # 10k × 1% / (5.0 × 100) = 0.20 → capped to 0.10 → real risk 0.5 %.
    decision = sized_lots_detail(10_000.0, 0.01, 5.0, 100.0, 0.01, 0.01)
    assert decision.lots == pytest.approx(LOT_MAX_SAFETY)
    assert decision.uncapped_lots == pytest.approx(0.20)
    assert decision.capped is True
    assert decision.effective_risk_fraction == pytest.approx(0.005)


def test_uncapped_size_carries_the_requested_risk():
    # 10k × 1% / (50.0 × 100) = 0.02 lots — inside the cap, real risk 1 %.
    decision = sized_lots_detail(10_000.0, 0.01, 50.0, 100.0, 0.01, 0.01)
    assert decision.lots == pytest.approx(0.02)
    assert decision.capped is False
    assert decision.effective_risk_fraction == pytest.approx(0.01)


def test_sized_lots_still_single_computation():
    args = (10_000.0, 0.01, 5.0, 100.0, 0.01, 0.01)
    assert sized_lots(*args) == pytest.approx(sized_lots_detail(*args).lots)
    assert sized_lots(0.0, 0.01, 5.0, 100.0, 0.01, 0.01) == 0.0


def test_risk_engine_decision_carries_sizing_kpi():
    engine = RiskEngine()
    decision = engine.evaluate_entry(
        EntryRequest(
            direction=Direction.LONG,
            entry_price=2000.0,
            sl_price=1995.0,
            atr=2.0,
            current_bar=10,
            now=datetime(2026, 11, 9, 12, 0),
            equity=10_000.0,
            risk_fraction=0.01,
            pip_value_per_lot=100.0,
            min_lots=0.01,
            lot_step=0.01,
            allowed_sessions=None,
        )
    )
    assert decision.action is RiskAction.ENTER
    assert decision.sizing_capped is True
    assert decision.effective_risk_fraction == pytest.approx(0.005)
    assert decision.uncapped_lots == pytest.approx(0.20)


def test_paper_runner_sizing_kpi_aggregates_cap_events():
    runner = PaperRunner.__new__(PaperRunner)
    runner._sizing = {
        "entries_sized": 0,
        "sizing_capped": 0,
        "max_effective_risk_fraction": 0.0,
        "last_effective_risk_fraction": 0.0,
    }
    runner.kpi = types.SimpleNamespace(calls=[], record=lambda kind, **kw: runner.kpi.calls.append((kind, kw)))
    candidate = types.SimpleNamespace(poi_id="p1", route_id="r1")
    now = datetime(2026, 11, 9, 12, 0)

    capped = types.SimpleNamespace(lots=0.10, uncapped_lots=0.20, sizing_capped=True, effective_risk_fraction=0.005)
    uncapped = types.SimpleNamespace(lots=0.02, uncapped_lots=0.02, sizing_capped=False, effective_risk_fraction=0.01)
    PaperRunner._record_sizing(runner, now, 1, candidate, capped)
    PaperRunner._record_sizing(runner, now, 2, candidate, uncapped)

    kpi = runner.sizing_kpi()
    assert kpi["entries_sized"] == 2
    assert kpi["sizing_capped"] == 1
    assert kpi["max_effective_risk_fraction"] == pytest.approx(0.01)
    assert kpi["last_effective_risk_fraction"] == pytest.approx(0.01)
    assert [kind for kind, _ in runner.kpi.calls] == ["entry_sized", "entry_sized"]
    assert runner.kpi.calls[0][1]["effective_risk_pct"] == pytest.approx(0.5)
    assert runner.kpi.calls[0][1]["sizing_capped"] is True


# --------------------------------------------------------------------------- #
# Operator config + session gate
# --------------------------------------------------------------------------- #
def test_operator_config_accepts_and_validates_the_unit_value(tmp_path):
    assert "pip_value_per_lot" in ALLOWED_KEYS
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"pip_value_per_lot": 100.0}), encoding="utf-8")
    assert load_operator_config(path).pip_value_per_lot == pytest.approx(100.0)

    path.write_text(json.dumps({"pip_value_per_lot": 0}), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_operator_config(path)
    path.write_text(json.dumps({"pip_value_per_lot": -1}), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_operator_config(path)


class _FakeTerm:
    path = r"C:\MT5"
    connected = True
    trade_allowed = True
    data_path = ""


class _FakeAcct:
    trade_mode = 0
    login = 1
    server = "Broker-Demo"
    company = "Broker"
    currency = "USD"
    leverage = 100


def _install_fake_mt5(monkeypatch, symbol_info):
    fake = types.SimpleNamespace(
        initialize=lambda path=None: True,
        terminal_info=lambda: _FakeTerm(),
        account_info=lambda: _FakeAcct(),
        symbol_select=lambda symbol, enable: True,
        symbol_info=lambda symbol: symbol_info,
        version=lambda: (5, 0, 0),
        last_error=lambda: (0, "ok"),
    )
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    return fake


def test_session_refuses_start_on_unit_mismatch(tmp_path, monkeypatch):
    _install_fake_mt5(monkeypatch, _symbol_info())
    session = OperatorSession(
        OperatorConfig(
            terminal_path=r"C:\MT5\terminal64.exe",
            log_dir=str(tmp_path / "logs"),
            pip_value_per_lot=10.0,   # the pre-F3 value: 10× too small
        )
    )
    with pytest.raises(SystemExit) as caught:
        session.identity_check()
    message = str(caught.value)
    assert "configured=10" in message and "derived=100" in message
    events = (tmp_path / "logs" / "events.log").read_text(encoding="utf-8")
    assert "SIZING PIN MISMATCH" in events


def test_session_records_the_pin_on_pass(tmp_path, monkeypatch):
    _install_fake_mt5(monkeypatch, _symbol_info())
    session = OperatorSession(
        OperatorConfig(
            terminal_path=r"C:\MT5\terminal64.exe",
            log_dir=str(tmp_path / "logs"),
        )
    )
    assert session.config.pip_value_per_lot == pytest.approx(100.0)
    session.identity_check()
    record = json.loads((tmp_path / "logs" / "sizing_pin.json").read_text(encoding="utf-8"))
    assert record["ok"] is True
    assert record["configured"] == pytest.approx(100.0)
    assert record["derived"] == pytest.approx(100.0)
    assert record["source"] == "tick_value"
    assert session.state["sizing_pin"]["derived"] == pytest.approx(100.0)


def test_session_refuses_when_symbol_info_is_unreadable(tmp_path, monkeypatch):
    _install_fake_mt5(monkeypatch, None)
    session = OperatorSession(
        OperatorConfig(
            terminal_path=r"C:\MT5\terminal64.exe",
            log_dir=str(tmp_path / "logs"),
        )
    )
    with pytest.raises(SystemExit, match="sizing units unverifiable"):
        session.identity_check()
