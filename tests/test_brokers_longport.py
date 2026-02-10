"""Unit tests for Longport broker logic that do not require SDK/network."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from clawdfolio.brokers.longport import LongportBroker
from clawdfolio.core.types import Exchange, Quote, Symbol


class TestLongportBroker:
    """Tests for LongportBroker internals."""

    def test_get_positions_quotes_with_instance_symbols(self, monkeypatch):
        """get_positions should pass instance symbols into get_quotes."""
        broker = LongportBroker()
        broker._connected = True

        fake_pos = SimpleNamespace(
            market="US",
            symbol="AAPL.US",
            quantity="10",
            cost_price="100",
            symbol_name="Apple Inc.",
        )
        fake_channel = SimpleNamespace(positions=[fake_pos])
        broker._trade_ctx = SimpleNamespace(
            stock_positions=lambda: SimpleNamespace(channels=[fake_channel])
        )

        called = {"tickers": []}

        def _fake_get_quotes(symbols):
            called["tickers"] = [s.ticker for s in symbols]
            return {
                "AAPL": Quote(
                    symbol=Symbol(ticker="AAPL", exchange=Exchange.NYSE),
                    price=Decimal("110"),
                    prev_close=Decimal("108"),
                    source="test",
                )
            }

        monkeypatch.setattr(broker, "get_quotes", _fake_get_quotes)

        positions = broker.get_positions()

        assert called["tickers"] == ["AAPL"]
        assert len(positions) == 1
        assert positions[0].current_price == Decimal("110")
        assert positions[0].prev_close == Decimal("108")
        assert positions[0].day_pnl > 0
