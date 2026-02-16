"""Longport (Longbridge) broker integration."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from ..core.exceptions import BrokerError
from ..core.types import Exchange, Portfolio, Position, Quote, Symbol
from ..utils.suppress import suppress_stdio
from .base import BaseBroker
from .registry import register_broker

if TYPE_CHECKING:
    from ..core.config import BrokerConfig

logger = logging.getLogger(__name__)

_OPTION_RE = re.compile(r"^[A-Z]{1,6}\d{6}[CP]\d+$")


def _is_option_symbol(sym: str) -> bool:
    """Check if a symbol looks like an OCC-format option (e.g. AAPL260618C00150000)."""
    base = sym.replace(".US", "")
    return bool(_OPTION_RE.match(base))


@register_broker("longport")
class LongportBroker(BaseBroker):
    """Longport (Longbridge) broker implementation.

    Requires environment variables:
    - LONGPORT_APP_KEY
    - LONGPORT_APP_SECRET
    - LONGPORT_ACCESS_TOKEN
    - LONGPORT_REGION (optional, defaults to 'us')
    """

    name = "longport"
    display_name = "Longport"

    def __init__(self, config: BrokerConfig | None = None):
        super().__init__(config)
        self._trade_ctx: Any = None
        self._quote_ctx: Any = None
        self._cfg: Any = None

    def connect(self) -> bool:
        """Connect to Longport API."""
        try:
            with suppress_stdio():
                from longport.openapi import Config, QuoteContext, TradeContext

                self._cfg = Config.from_env()
                self._trade_ctx = TradeContext(self._cfg)
                self._quote_ctx = QuoteContext(self._cfg)

            self._connected = True
            logger.info("Connected to Longport API")
            return True
        except Exception as e:
            raise BrokerError("longport", f"Connection failed: {e}") from e

    def disconnect(self) -> None:
        """Disconnect from Longport API."""
        self._trade_ctx = None
        self._quote_ctx = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected and self._trade_ctx is not None

    def get_portfolio(self) -> Portfolio:
        """Fetch complete portfolio from Longport."""
        if not self.is_connected():
            self.connect()

        positions = self.get_positions()

        # Get account balance
        with suppress_stdio():
            balances = self._trade_ctx.account_balance("USD")

        if not balances:
            raise BrokerError("longport", "No account balance data returned")

        acc = balances[0]
        net_assets = Decimal(str(acc.net_assets))
        cash = Decimal(str(acc.total_cash))
        buying_power = Decimal(str(getattr(acc, "buy_power", 0) or 0))

        total_mv = sum((p.market_value for p in positions), Decimal(0))
        total_day_pnl = sum((p.day_pnl for p in positions), Decimal(0))

        portfolio = Portfolio(
            positions=positions,
            cash=cash,
            net_assets=net_assets,
            market_value=total_mv,
            buying_power=buying_power,
            day_pnl=total_day_pnl,
            day_pnl_pct=float(total_day_pnl / net_assets) if net_assets > 0 else 0.0,
            currency="USD",
            source="longport",
            timestamp=datetime.now(),
        )

        return portfolio

    def get_positions(self) -> list[Position]:
        """Fetch current positions from Longport."""
        if not self.is_connected():
            self.connect()

        positions = []
        symbols_to_quote = []

        try:
            pos = self._trade_ctx.stock_positions()

            for ch in getattr(pos, "channels", []):
                for p in getattr(ch, "positions", []):
                    mkt = str(getattr(p, "market", "")).split(".")[-1].upper()
                    if mkt != "US":
                        continue

                    sym = str(p.symbol)
                    if _is_option_symbol(sym):
                        continue

                    qty = Decimal(str(p.quantity))
                    if abs(qty) < Decimal("0.000000001"):
                        continue

                    ticker = sym.replace(".US", "")
                    symbol = Symbol(ticker=ticker, exchange=Exchange.NYSE)

                    pos_obj = Position(
                        symbol=symbol,
                        quantity=qty,
                        avg_cost=Decimal(str(getattr(p, "cost_price", 0) or 0)),
                        name=str(getattr(p, "symbol_name", "")),
                        source="longport",
                    )
                    positions.append(pos_obj)
                    symbols_to_quote.append(sym)

            # Get quotes for positions
            if symbols_to_quote:
                quotes = self.get_quotes([p.symbol for p in positions])
                for pos in positions:
                    if pos.symbol.ticker in quotes:
                        pos.update_from_quote(quotes[pos.symbol.ticker])

        except Exception as e:
            raise BrokerError("longport", f"Failed to fetch positions: {e}") from e

        return positions

    def get_quote(self, symbol: Symbol) -> Quote:
        """Fetch quote for a single symbol."""
        quotes = self.get_quotes([symbol])
        if symbol.ticker not in quotes:
            raise BrokerError("longport", f"No quote for {symbol.ticker}")
        return quotes[symbol.ticker]

    def get_quotes(self, symbols: list[Symbol]) -> dict[str, Quote]:
        """Fetch quotes for multiple symbols."""
        if not self.is_connected():
            self.connect()

        if not symbols:
            return {}

        result = {}
        syms = [f"{s.ticker}.US" for s in symbols]

        try:
            with suppress_stdio():
                quotes = self._quote_ctx.quote(syms)

            for q in quotes:
                ticker = q.symbol.replace(".US", "")
                result[ticker] = Quote(
                    symbol=Symbol(ticker=ticker, exchange=Exchange.NYSE),
                    price=Decimal(str(q.last_done)),
                    prev_close=Decimal(str(q.prev_close)),
                    open=Decimal(str(getattr(q, "open", 0) or 0)) or None,
                    high=Decimal(str(getattr(q, "high", 0) or 0)) or None,
                    low=Decimal(str(getattr(q, "low", 0) or 0)) or None,
                    volume=int(getattr(q, "volume", 0) or 0),
                    turnover=Decimal(str(getattr(q, "turnover", 0) or 0)) or None,
                    timestamp=datetime.now(),
                    source="longport",
                )
        except Exception as e:
            raise BrokerError("longport", f"Failed to fetch quotes: {e}") from e

        return result
