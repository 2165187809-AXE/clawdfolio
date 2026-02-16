"""Tests for core types and configuration."""

from decimal import Decimal

import pytest

from clawdfolio.core.config import Config, load_config
from clawdfolio.core.exceptions import (
    BrokerError,
    PortfolioMonitorError,
)
from clawdfolio.core.types import (
    Alert,
    AlertSeverity,
    AlertType,
    Exchange,
    Quote,
    Symbol,
)


class TestSymbol:
    """Tests for Symbol class."""

    def test_create_symbol(self):
        """Test basic symbol creation."""
        sym = Symbol(ticker="AAPL", exchange=Exchange.NYSE)
        assert sym.ticker == "AAPL"
        assert sym.exchange == Exchange.NYSE

    def test_symbol_from_full_ticker(self):
        """Test symbol creation from full ticker with suffix."""
        sym = Symbol(ticker="AAPL.US")
        assert sym.ticker == "AAPL"
        assert sym.exchange == Exchange.NYSE

    def test_symbol_full_symbol(self):
        """Test full_symbol property."""
        sym = Symbol(ticker="AAPL", exchange=Exchange.NYSE)
        assert sym.full_symbol == "AAPL.US"

    def test_symbol_hash(self):
        """Test symbol is hashable."""
        sym1 = Symbol(ticker="AAPL", exchange=Exchange.NYSE)
        sym2 = Symbol(ticker="AAPL", exchange=Exchange.NYSE)
        assert hash(sym1) == hash(sym2)


class TestQuote:
    """Tests for Quote class."""

    def test_quote_change(self, sample_symbol):
        """Test quote change calculation."""
        quote = Quote(
            symbol=sample_symbol,
            price=Decimal("175.50"),
            prev_close=Decimal("170.00"),
        )
        assert quote.change == Decimal("5.50")

    def test_quote_change_pct(self, sample_symbol):
        """Test quote change percentage calculation."""
        quote = Quote(
            symbol=sample_symbol,
            price=Decimal("175.50"),
            prev_close=Decimal("170.00"),
        )
        assert abs(quote.change_pct - 0.0323) < 0.001


class TestPosition:
    """Tests for Position class."""

    def test_position_weight(self, sample_position):
        """Test position weight property."""
        sample_position.weight = 0.35
        assert sample_position.weight == 0.35

    def test_position_update_from_quote(self, sample_position, sample_quote):
        """Test updating position from quote."""
        sample_position.update_from_quote(sample_quote)
        assert sample_position.current_price == Decimal("175.50")
        assert sample_position.prev_close == Decimal("173.00")


class TestPortfolio:
    """Tests for Portfolio class."""

    def test_portfolio_sorted_by_weight(self, sample_portfolio):
        """Test positions sorted by weight."""
        sorted_pos = sample_portfolio.sorted_by_weight
        weights = [p.weight for p in sorted_pos]
        assert weights == sorted(weights, reverse=True)

    def test_portfolio_top_holdings(self, sample_portfolio):
        """Test top holdings property."""
        top = sample_portfolio.top_holdings
        assert len(top) <= 10

    def test_portfolio_get_position(self, sample_portfolio):
        """Test getting position by ticker."""
        pos = sample_portfolio.get_position("AAPL")
        assert pos is not None
        assert pos.symbol.ticker == "AAPL"

    def test_portfolio_get_position_not_found(self, sample_portfolio):
        """Test getting non-existent position."""
        pos = sample_portfolio.get_position("INVALID")
        assert pos is None


class TestAlert:
    """Tests for Alert class."""

    def test_alert_str(self):
        """Test alert string representation."""
        alert = Alert(
            type=AlertType.PRICE_MOVE,
            severity=AlertSeverity.WARNING,
            title="AAPL up 5%",
            message="Apple stock rose significantly",
            ticker="AAPL",
        )
        assert "AAPL up 5%" in str(alert)
        assert "Apple stock" in str(alert)


class TestConfig:
    """Tests for Config class."""

    def test_default_config(self):
        """Test default configuration."""
        config = load_config()
        assert config.currency == "USD"
        assert "demo" in config.brokers

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "currency": "HKD",
            "alerts": {
                "pnl_trigger": 1000.0,
            },
        }
        config = Config.from_dict(data)
        assert config.currency == "HKD"
        assert config.alerts.pnl_trigger == 1000.0

    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        config = Config(currency="EUR")
        data = config.to_dict()
        assert data["currency"] == "EUR"

    def test_option_buyback_config_roundtrip(self):
        """Test option buyback config parsing and serialization."""
        data = {
            "option_buyback": {
                "enabled": True,
                "symbol": "TQQQ",
                "state_path": "/tmp/option_buyback_state.json",
                "targets": [
                    {
                        "name": "target1",
                        "strike": 60,
                        "expiry": "2026-06-18",
                        "type": "C",
                        "trigger_price": 1.6,
                        "qty": 2,
                        "reset_pct": 0.2,
                    }
                ],
            }
        }
        config = Config.from_dict(data)
        assert config.option_buyback.enabled is True
        assert config.option_buyback.symbol == "TQQQ"
        assert len(config.option_buyback.targets) == 1
        assert config.option_buyback.targets[0].option_type == "C"

        back = config.to_dict()
        assert back["option_buyback"]["enabled"] is True
        assert back["option_buyback"]["targets"][0]["type"] == "C"


class TestConfigValidation:
    """Tests for config input validation."""

    def test_rsi_low_out_of_range(self):
        """Test that rsi_low outside 1-100 raises ConfigError."""
        from clawdfolio.core.exceptions import ConfigError
        with pytest.raises(ConfigError, match="rsi_low"):
            Config.from_dict({"alerts": {"rsi_low": 0}})

    def test_rsi_high_out_of_range(self):
        """Test that rsi_high outside 1-100 raises ConfigError."""
        from clawdfolio.core.exceptions import ConfigError
        with pytest.raises(ConfigError, match="rsi_high"):
            Config.from_dict({"alerts": {"rsi_high": 101}})

    def test_rsi_low_ge_rsi_high(self):
        """Test that rsi_low >= rsi_high raises ConfigError."""
        from clawdfolio.core.exceptions import ConfigError
        with pytest.raises(ConfigError, match="rsi_low"):
            Config.from_dict({"alerts": {"rsi_low": 80, "rsi_high": 80}})

    def test_negative_pnl_trigger(self):
        """Test that negative pnl_trigger raises ConfigError."""
        from clawdfolio.core.exceptions import ConfigError
        with pytest.raises(ConfigError, match="pnl_trigger"):
            Config.from_dict({"alerts": {"pnl_trigger": -100}})

    def test_zero_pnl_trigger(self):
        """Test that zero pnl_trigger raises ConfigError."""
        from clawdfolio.core.exceptions import ConfigError
        with pytest.raises(ConfigError, match="pnl_trigger"):
            Config.from_dict({"alerts": {"pnl_trigger": 0}})


class TestExceptions:
    """Tests for custom exceptions."""

    def test_broker_error(self):
        """Test BrokerError formatting."""
        err = BrokerError("longport", "Connection failed")
        assert "[longport]" in str(err)
        assert "Connection failed" in str(err)

    def test_clawdfolio_error_inheritance(self):
        """Test exception inheritance."""
        err = BrokerError("test", "test message")
        assert isinstance(err, PortfolioMonitorError)
