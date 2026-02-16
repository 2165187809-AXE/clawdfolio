"""Tests for broker integrations."""


import pytest

from clawdfolio.brokers.base import BaseBroker
from clawdfolio.brokers.demo import DemoBroker
from clawdfolio.brokers.registry import (
    get_broker,
    list_brokers,
    register_broker,
    unregister_broker,
)
from clawdfolio.core.types import Exchange, Symbol


class TestBrokerRegistry:
    """Tests for broker registry."""

    def test_register_broker(self):
        """Test registering a new broker."""
        @register_broker("test_broker")
        class TestBroker(BaseBroker):
            def connect(self):
                return True

            def disconnect(self):
                pass

            def is_connected(self):
                return True

            def get_portfolio(self):
                pass

            def get_positions(self):
                return []

            def get_quote(self, symbol):
                pass

            def get_quotes(self, symbols):
                return {}

        assert "test_broker" in list_brokers()
        unregister_broker("test_broker")

    def test_get_broker(self):
        """Test getting a registered broker."""
        # Register demo broker first
        from clawdfolio.brokers.demo import DemoBroker  # noqa

        broker = get_broker("demo")
        assert isinstance(broker, DemoBroker)

    def test_get_unknown_broker(self):
        """Test getting unknown broker raises error."""
        with pytest.raises(KeyError):
            get_broker("nonexistent")

    def test_register_duplicate_broker(self):
        """Test registering duplicate broker raises error."""
        @register_broker("duplicate_test")
        class TestBroker1(BaseBroker):
            def connect(self): return True
            def disconnect(self): pass
            def is_connected(self): return True
            def get_portfolio(self): pass
            def get_positions(self): return []
            def get_quote(self, s): pass
            def get_quotes(self, s): return {}

        with pytest.raises(ValueError):
            @register_broker("duplicate_test")
            class TestBroker2(BaseBroker):
                def connect(self): return True
                def disconnect(self): pass
                def is_connected(self): return True
                def get_portfolio(self): pass
                def get_positions(self): return []
                def get_quote(self, s): pass
                def get_quotes(self, s): return {}

        unregister_broker("duplicate_test")


class TestFutuEmptyData:
    """Tests for futu broker empty data handling."""

    def test_futu_empty_funds_raises_broker_error(self):
        """Test that empty account balance DataFrame raises BrokerError."""
        from unittest.mock import MagicMock, patch

        import pandas as pd

        from clawdfolio.core.exceptions import BrokerError

        with patch.dict("sys.modules", {
            "futu": MagicMock(),
            "futu.common": MagicMock(),
            "futu.common.ft_logger": MagicMock(),
        }):
            from clawdfolio.brokers.futu import FutuBroker
            broker = FutuBroker()
            broker._connected = True
            broker._trade_ctx = MagicMock()
            broker._quote_ctx = MagicMock()

            # Mock RET_OK
            futu_mod = MagicMock()
            futu_mod.RET_OK = 0
            futu_mod.Currency.USD = "USD"
            futu_mod.TrdEnv.REAL = "REAL"

            broker._trade_ctx.position_list_query.return_value = (0, pd.DataFrame())
            broker._trade_ctx.accinfo_query.return_value = (0, pd.DataFrame())

            with patch.dict("sys.modules", {"futu": futu_mod}):
                with pytest.raises(BrokerError, match="No account balance data"):
                    broker.get_portfolio()


class TestLongportEmptyBalance:
    """Tests for longport broker empty balance handling."""

    def test_longport_empty_balance_raises_broker_error(self):
        """Test that empty account balance list raises BrokerError."""
        from unittest.mock import MagicMock, patch

        from clawdfolio.core.exceptions import BrokerError

        with patch.dict("sys.modules", {
            "longport": MagicMock(),
            "longport.openapi": MagicMock(),
        }):
            from clawdfolio.brokers.longport import LongportBroker
            broker = LongportBroker()
            broker._connected = True
            broker._trade_ctx = MagicMock()
            broker._quote_ctx = MagicMock()

            # stock_positions returns empty channels
            pos_result = MagicMock()
            pos_result.channels = []
            broker._trade_ctx.stock_positions.return_value = pos_result

            # account_balance returns empty list
            broker._trade_ctx.account_balance.return_value = []

            with pytest.raises(BrokerError, match="No account balance data"):
                broker.get_portfolio()


class TestDemoBroker:
    """Tests for demo broker."""

    def test_demo_broker_connect(self):
        """Test demo broker connection."""

        broker = DemoBroker()
        assert broker.connect() is True
        assert broker.is_connected() is True

    def test_demo_broker_disconnect(self):
        """Test demo broker disconnection."""

        broker = DemoBroker()
        broker.connect()
        broker.disconnect()
        assert broker.is_connected() is False

    def test_demo_broker_get_portfolio(self):
        """Test demo broker portfolio."""

        broker = DemoBroker()
        broker.connect()
        portfolio = broker.get_portfolio()

        assert portfolio is not None
        assert portfolio.net_assets > 0
        assert len(portfolio.positions) > 0
        assert portfolio.source == "demo"

    def test_demo_broker_get_positions(self):
        """Test demo broker positions."""

        broker = DemoBroker()
        broker.connect()
        positions = broker.get_positions()

        assert len(positions) > 0
        for pos in positions:
            assert pos.quantity > 0
            assert pos.market_value > 0

    def test_demo_broker_get_quote(self):
        """Test demo broker quote."""

        broker = DemoBroker()
        broker.connect()

        symbol = Symbol(ticker="AAPL", exchange=Exchange.NYSE)
        quote = broker.get_quote(symbol)

        assert quote is not None
        assert quote.price > 0
        assert quote.source == "demo"

    def test_demo_broker_get_quotes(self):
        """Test demo broker multiple quotes."""

        broker = DemoBroker()
        broker.connect()

        symbols = [
            Symbol(ticker="AAPL"),
            Symbol(ticker="MSFT"),
            Symbol(ticker="GOOGL"),
        ]
        quotes = broker.get_quotes(symbols)

        assert len(quotes) == 3
        assert "AAPL" in quotes
        assert "MSFT" in quotes

    def test_demo_broker_context_manager(self):
        """Test demo broker as context manager."""

        with DemoBroker() as broker:
            assert broker.is_connected()
            portfolio = broker.get_portfolio()
            assert portfolio is not None

    def test_demo_broker_add_position(self):
        """Test adding custom position to demo broker."""

        broker = DemoBroker()
        broker.connect()

        initial_count = len(broker.get_positions())
        broker.add_demo_position("TEST", "Test Stock", 100, 50.0, 45.0)

        assert len(broker.get_positions()) == initial_count + 1

    def test_demo_broker_reset(self):
        """Test resetting demo broker."""

        broker = DemoBroker()
        broker.connect()

        broker.add_demo_position("TEST", "Test Stock", 100, 50.0, 45.0)
        broker.reset()

        # Should be back to default positions
        positions = broker.get_positions()
        tickers = [p.symbol.ticker for p in positions]
        assert "TEST" not in tickers
