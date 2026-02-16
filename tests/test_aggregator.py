"""Tests for multi-broker aggregation."""

from datetime import datetime
from decimal import Decimal

import pytest

from clawdfolio.brokers.aggregator import _merge_positions, aggregate_portfolios
from clawdfolio.core.exceptions import BrokerError
from clawdfolio.core.types import Exchange, Portfolio, Position, Symbol


def _make_portfolio(positions, cash=Decimal("5000"), source="test"):
    mv = sum(p.market_value for p in positions)
    net = cash + mv
    day_pnl = sum(p.day_pnl for p in positions)
    return Portfolio(
        positions=positions,
        cash=cash,
        net_assets=net,
        market_value=mv,
        buying_power=cash,
        day_pnl=day_pnl,
        day_pnl_pct=float(day_pnl / net) if net else 0.0,
        currency="USD",
        source=source,
        timestamp=datetime.now(),
    )


def _pos(ticker, qty=100, price=Decimal("100"), avg_cost=Decimal("90"), source="test"):
    mv = qty * price
    return Position(
        symbol=Symbol(ticker=ticker, exchange=Exchange.NYSE),
        quantity=Decimal(str(qty)),
        avg_cost=avg_cost,
        market_value=mv,
        unrealized_pnl=qty * (price - avg_cost),
        unrealized_pnl_pct=float((price - avg_cost) / avg_cost) if avg_cost else 0.0,
        day_pnl=Decimal("10"),
        day_pnl_pct=0.001,
        current_price=price,
        name=ticker,
        source=source,
    )


class TestMergePositions:
    """Tests for position merging logic."""

    def test_no_duplicates(self):
        positions = [_pos("AAPL"), _pos("MSFT")]
        merged = _merge_positions(positions)
        assert len(merged) == 2

    def test_merge_same_ticker(self):
        p1 = _pos("AAPL", qty=100, price=Decimal("150"), avg_cost=Decimal("140"), source="a")
        p2 = _pos("AAPL", qty=50, price=Decimal("150"), avg_cost=Decimal("130"), source="b")
        merged = _merge_positions([p1, p2])
        assert len(merged) == 1
        m = merged[0]
        assert m.quantity == Decimal("150")
        assert m.market_value == p1.market_value + p2.market_value
        assert m.day_pnl == p1.day_pnl + p2.day_pnl
        # Weighted avg cost: (140*100 + 130*50) / 150 = 136.67
        assert abs(float(m.avg_cost) - 136.67) < 0.01
        assert m.source == "a+b"

    def test_merge_preserves_unique(self):
        positions = [_pos("AAPL"), _pos("AAPL"), _pos("MSFT")]
        merged = _merge_positions(positions)
        tickers = [p.symbol.ticker for p in merged]
        assert sorted(tickers) == ["AAPL", "MSFT"]


class TestAggregatePortfolios:
    """Tests for multi-broker aggregation."""

    def test_single_broker(self):
        from unittest.mock import MagicMock

        broker = MagicMock()
        broker.name = "test"
        broker.is_connected.return_value = False
        broker.get_portfolio.return_value = _make_portfolio(
            [_pos("AAPL")], source="test"
        )
        result = aggregate_portfolios([broker])
        assert result.source == "test"
        assert len(result.positions) == 1

    def test_two_brokers_merged(self):
        from unittest.mock import MagicMock

        b1 = MagicMock()
        b1.name = "longport"
        b1.is_connected.return_value = False
        b1.get_portfolio.return_value = _make_portfolio(
            [_pos("AAPL", source="longport")], cash=Decimal("3000"), source="longport"
        )

        b2 = MagicMock()
        b2.name = "futu"
        b2.is_connected.return_value = False
        b2.get_portfolio.return_value = _make_portfolio(
            [_pos("MSFT", source="futu")], cash=Decimal("2000"), source="futu"
        )

        result = aggregate_portfolios([b1, b2])
        assert result.cash == Decimal("5000")
        assert "longport" in result.source
        assert "futu" in result.source
        tickers = [p.symbol.ticker for p in result.positions]
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_failing_broker_skipped(self):
        from unittest.mock import MagicMock

        good = MagicMock()
        good.name = "good"
        good.is_connected.return_value = False
        good.get_portfolio.return_value = _make_portfolio(
            [_pos("AAPL")], source="good"
        )

        bad = MagicMock()
        bad.name = "bad"
        bad.is_connected.return_value = False
        bad.connect.side_effect = Exception("connection failed")

        result = aggregate_portfolios([bad, good])
        assert result.source == "good"
        assert len(result.positions) == 1

    def test_all_brokers_fail(self):
        from unittest.mock import MagicMock

        bad = MagicMock()
        bad.name = "bad"
        bad.is_connected.return_value = False
        bad.connect.side_effect = Exception("fail")

        with pytest.raises(BrokerError, match="No broker returned data"):
            aggregate_portfolios([bad])
