"""Phase 0 validation — MT5Connector wrapper methods exist and delegate.

MetaTrader5 is mocked out entirely (it is imported lazily, so no real
terminal/package is required).
"""

import builtins
from unittest.mock import Mock, patch

import pytest

from smc.config.timeframe import Timeframe
from smc.data.mt5_connector import MT5Connector, MT5NotAvailableError


@pytest.fixture
def mt5():
    module = Mock()
    module.TIMEFRAME_M5 = 5  # sanity: connector must pass int(tf), not the enum
    module.copy_rates_from_pos = Mock(return_value="rates")
    module.account_info = Mock(return_value="account")
    module.positions_get = Mock(return_value=("pos1", "pos2"))
    module.order_send = Mock(return_value="order_result")
    module.order_check = Mock(return_value="check_result")
    module.initialize = Mock(return_value=True)
    module.login = Mock(return_value=True)
    module.shutdown = Mock()
    module.last_error = Mock(return_value=(0, "ok"))
    return module


@pytest.fixture
def connector(mt5):
    with patch.object(MT5Connector, "_mt5", staticmethod(lambda: mt5)):
        yield MT5Connector(symbol="XAUUSD.x", magic=999, deviation=20)


def test_all_required_methods_exist(connector):
    for method in (
        "copy_rates",
        "order_send",
        "account_info",
        "positions_get",
        "order_check",
    ):
        assert callable(getattr(connector, method)), f"missing method {method}"


def test_copy_rates_maps_timeframe(mt5, connector):
    result = connector.copy_rates("XAUUSD.x", Timeframe.M5, 0, 100)
    assert result == "rates"
    mt5.copy_rates_from_pos.assert_called_once_with("XAUUSD.x", 5, 0, 100)


def test_account_info(mt5, connector):
    assert connector.account_info() == "account"
    mt5.account_info.assert_called_once()


def test_positions_get_with_and_without_symbol(mt5, connector):
    connector.positions_get()
    mt5.positions_get.assert_called_once_with()
    mt5.positions_get.reset_mock()

    connector.positions_get(symbol="XAUUSD.x")
    mt5.positions_get.assert_called_once_with(symbol="XAUUSD.x")


def test_order_send_injects_magic_and_deviation(mt5, connector):
    request = {"action": "deal", "symbol": "XAUUSD.x"}
    assert connector.order_send(request) == "order_result"
    assert request["magic"] == 999
    assert request["deviation"] == 20
    mt5.order_send.assert_called_once_with(request)


def test_order_check(mt5, connector):
    assert connector.order_check({"action": "deal"}) == "check_result"
    mt5.order_check.assert_called_once()


def test_connect_initializes_and_logs_in(mt5, connector):
    ok = connector.connect(login=12345, password="secret", server="Broker-Server")
    assert ok is True
    mt5.initialize.assert_called_once_with(path=None)
    mt5.login.assert_called_once_with(
        12345, password="secret", server="Broker-Server"
    )


def test_connect_skips_login_without_credentials(mt5, connector):
    assert connector.connect() is True
    mt5.login.assert_not_called()


def test_connect_shuts_down_on_failed_login(mt5, connector):
    mt5.login.return_value = False
    assert connector.connect(login=1, password="x", server="s") is False
    mt5.shutdown.assert_called_once()


def test_last_error_delegates(mt5, connector):
    assert connector.last_error() == (0, "ok")


def test_mt5_not_available_error_on_missing_package():
    """Exercise the real lazy-import path when MetaTrader5 is absent."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "MetaTrader5":
            raise ImportError("No module named 'MetaTrader5'")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        with pytest.raises(MT5NotAvailableError):
            MT5Connector().connect()


def test_connect_returns_false_when_initialize_fails(mt5, connector):
    mt5.initialize.return_value = False
    assert connector.connect() is False