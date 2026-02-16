"""Futu/Moomoo broker integration."""

from __future__ import annotations

import logging
import socket
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

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11111


def _check_connectivity(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if OpenD is running and accessible."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (TimeoutError, OSError):
        return False


@register_broker("futu")
class FutuBroker(BaseBroker):
    """Futu/Moomoo broker implementation.

    Requires moomoo OpenD to be running locally.
    Default connection: 127.0.0.1:11111
    """

    name = "futu"
    display_name = "Moomoo"

    def __init__(self, config: BrokerConfig | None = None):
        super().__init__(config)
        self._trade_ctx: Any = None
        self._quote_ctx: Any = None

        # Get host/port from config or defaults
        self._host = DEFAULT_HOST
        self._port = DEFAULT_PORT
        if config and config.extra:
            self._host = config.extra.get("host", DEFAULT_HOST)
            self._port = config.extra.get("port", DEFAULT_PORT)

    def connect(self) -> bool:
        """Connect to Moomoo OpenD."""
        if not _check_connectivity(self._host, self._port):
            raise BrokerError(
                "futu",
                f"OpenD not accessible at {self._host}:{self._port}. "
                "Please ensure moomoo OpenD is running."
            )

        try:
            # Suppress futu logger
            from futu.common import ft_logger

            ft_logger.logger.console_level = 50

            from futu import (
                OpenQuoteContext,
                OpenSecTradeContext,
                SecurityFirm,
                TrdMarket,
            )

            self._trade_ctx = OpenSecTradeContext(
                filter_trdmarket=TrdMarket.US,
                host=self._host,
                port=self._port,
                security_firm=SecurityFirm.FUTUINC,
            )

            self._quote_ctx = OpenQuoteContext(
                host=self._host,
                port=self._port,
            )

            self._connected = True
            logger.info("Connected to Moomoo OpenD at %s:%s", self._host, self._port)
            return True
        except Exception as e:
            raise BrokerError("futu", f"Connection failed: {e}") from e

    def disconnect(self) -> None:
        """Disconnect from Moomoo OpenD."""
        if self._trade_ctx:
            self._trade_ctx.close()
        if self._quote_ctx:
            self._quote_ctx.close()
        self._trade_ctx = None
        self._quote_ctx = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected and self._trade_ctx is not None

    def get_portfolio(self) -> Portfolio:
        """Fetch complete portfolio from Moomoo."""
        if not self.is_connected():
            self.connect()

        from futu import RET_OK, Currency, TrdEnv

        positions = self.get_positions()

        # Get account balance
        ret, funds = self._trade_ctx.accinfo_query(
            trd_env=TrdEnv.REAL,
            currency=Currency.USD
        )

        if ret != RET_OK:
            raise BrokerError("futu", f"Failed to fetch account info: {funds}")

        if funds.empty:
            raise BrokerError("futu", "No account balance data returned")

        row = funds.iloc[0]
        net_assets = Decimal(str(row.get("total_assets", 0)))
        cash = Decimal(str(row.get("cash", 0)))
        market_value = Decimal(str(row.get("market_val", 0)))
        buying_power = Decimal(str(row.get("power", 0) or 0))

        total_day_pnl = sum((p.day_pnl for p in positions), Decimal(0))

        portfolio = Portfolio(
            positions=positions,
            cash=cash,
            net_assets=net_assets,
            market_value=market_value,
            buying_power=buying_power,
            day_pnl=total_day_pnl,
            day_pnl_pct=float(total_day_pnl / net_assets) if net_assets > 0 else 0.0,
            currency="USD",
            source="futu",
            timestamp=datetime.now(),
        )

        return portfolio

    def get_positions(self) -> list[Position]:
        """Fetch current positions from Moomoo."""
        if not self.is_connected():
            self.connect()

        from futu import RET_OK, TrdEnv, TrdMarket

        positions = []

        try:
            ret, pos_df = self._trade_ctx.position_list_query(
                trd_env=TrdEnv.REAL,
                position_market=TrdMarket.US
            )

            if ret != RET_OK:
                raise BrokerError("futu", f"Failed to fetch positions: {pos_df}")

            for _, r in pos_df.iterrows():
                code = str(r.get("code", ""))
                if not code.startswith("US."):
                    continue

                ticker = code.split(".", 1)[1]
                symbol = Symbol(ticker=ticker, exchange=Exchange.NYSE)

                qty = Decimal(str(r.get("qty", 0)))
                avg_cost = Decimal(str(r.get("cost_price", 0) or 0))
                price = Decimal(str(r.get("nominal_price", 0) or 0))
                market_value = Decimal(str(r.get("market_val", 0) or 0))
                day_pnl = Decimal(str(r.get("today_pl_val", 0) or 0))

                # Calculate day P&L percentage
                day_pnl_pct = 0.0
                if market_value > 0 and day_pnl != 0:
                    start_val = market_value - day_pnl
                    if start_val > 0:
                        day_pnl_pct = float(day_pnl / start_val)

                # Calculate unrealized P&L
                unrealized_pnl = Decimal("0")
                unrealized_pnl_pct = 0.0
                if avg_cost > 0 and qty > 0:
                    unrealized_pnl = qty * (price - avg_cost)
                    unrealized_pnl_pct = float((price - avg_cost) / avg_cost)

                positions.append(Position(
                    symbol=symbol,
                    quantity=qty,
                    avg_cost=avg_cost,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=unrealized_pnl_pct,
                    day_pnl=day_pnl,
                    day_pnl_pct=day_pnl_pct,
                    current_price=price,
                    name=str(r.get("stock_name", "")),
                    source="futu",
                ))

        except BrokerError:
            raise
        except Exception as e:
            raise BrokerError("futu", f"Failed to fetch positions: {e}") from e

        return positions

    def get_quote(self, symbol: Symbol) -> Quote:
        """Fetch quote for a single symbol."""
        quotes = self.get_quotes([symbol])
        if symbol.ticker not in quotes:
            raise BrokerError("futu", f"No quote for {symbol.ticker}")
        return quotes[symbol.ticker]

    def get_quotes(self, symbols: list[Symbol]) -> dict[str, Quote]:
        """Fetch quotes for multiple symbols."""
        if not self.is_connected():
            self.connect()

        if not symbols:
            return {}

        from futu import RET_OK

        result = {}
        codes = [f"US.{s.ticker}" for s in symbols]

        try:
            with suppress_stdio():
                ret, df = self._quote_ctx.get_market_snapshot(codes)

            if ret != RET_OK or df is None or df.empty:
                # Fallback to individual quotes
                for sym in symbols:
                    with suppress_stdio():
                        ret2, df2 = self._quote_ctx.get_stock_quote([f"US.{sym.ticker}"])
                    if ret2 == RET_OK and df2 is not None and not df2.empty:
                        r = df2.iloc[0]
                        result[sym.ticker] = Quote(
                            symbol=sym,
                            price=Decimal(str(r.get("last_price", 0))),
                            prev_close=Decimal(str(r.get("prev_close", 0) or 0)) or None,
                            timestamp=datetime.now(),
                            source="futu",
                        )
                return result

            for _, r in df.iterrows():
                code = str(r.get("code", ""))
                if not code.startswith("US."):
                    continue

                ticker = code.split(".", 1)[1]
                price = r.get("last_price")
                if price is None:
                    continue

                result[ticker] = Quote(
                    symbol=Symbol(ticker=ticker, exchange=Exchange.NYSE),
                    price=Decimal(str(price)),
                    prev_close=Decimal(str(r.get("prev_close_price") or 0)) or None,
                    open=Decimal(str(r.get("open_price") or 0)) or None,
                    high=Decimal(str(r.get("high_price") or 0)) or None,
                    low=Decimal(str(r.get("low_price") or 0)) or None,
                    volume=int(r.get("volume") or 0),
                    turnover=Decimal(str(r.get("turnover") or 0)) or None,
                    timestamp=datetime.now(),
                    source="futu",
                )

        except Exception as e:
            raise BrokerError("futu", f"Failed to fetch quotes: {e}") from e

        return result
