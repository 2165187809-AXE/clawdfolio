"""Custom exceptions for Clawdfolio."""

from __future__ import annotations


class PortfolioMonitorError(Exception):
    """Base exception for all Clawdfolio errors."""

    pass


class BrokerError(PortfolioMonitorError):
    """Raised when broker connection or API call fails."""

    def __init__(self, broker: str, message: str):
        self.broker = broker
        super().__init__(f"[{broker}] {message}")


class ConfigError(PortfolioMonitorError):
    """Raised when configuration is invalid or missing."""

    pass


class MarketDataError(PortfolioMonitorError):
    """Raised when market data fetch fails."""

    def __init__(self, ticker: str, source: str, message: str):
        self.ticker = ticker
        self.source = source
        super().__init__(f"[{source}] {ticker}: {message}")


class AuthenticationError(BrokerError):
    """Raised when broker authentication fails."""

    def __init__(self, broker: str):
        super().__init__(broker, "Authentication failed - check credentials")


class RateLimitError(BrokerError):
    """Raised when broker rate limit is exceeded."""

    def __init__(self, broker: str, retry_after: int | None = None):
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        if retry_after:
            msg += f" - retry after {retry_after}s"
        super().__init__(broker, msg)


class MarketClosedError(PortfolioMonitorError):
    """Raised when trying to access real-time data while market is closed."""

    def __init__(self, market: str = "US"):
        self.market = market
        super().__init__(f"{market} market is currently closed")
