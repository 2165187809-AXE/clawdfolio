"""Base broker interface for Portfolio Monitor."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.config import BrokerConfig
    from ..core.types import Portfolio, Position, Quote, Symbol


class BaseBroker(ABC):
    """Abstract base class for broker integrations.

    All broker implementations must inherit from this class and implement
    the required abstract methods.

    Example:
        >>> from clawdfolio.brokers import BaseBroker, register_broker
        >>>
        >>> @register_broker("my_broker")
        >>> class MyBroker(BaseBroker):
        ...     def connect(self) -> bool:
        ...         # Implementation
        ...         return True
        ...
        ...     def get_portfolio(self) -> Portfolio:
        ...         # Implementation
        ...         pass
    """

    name: str = "base"
    display_name: str = "Base Broker"

    def __init__(self, config: BrokerConfig | None = None):
        """Initialize broker with optional configuration.

        Args:
            config: Broker-specific configuration
        """
        self.config = config
        self._connected = False

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to broker.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close broker connection."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if broker is currently connected.

        Returns:
            True if connected, False otherwise
        """
        pass

    @abstractmethod
    def get_portfolio(self) -> Portfolio:
        """Fetch complete portfolio data.

        Returns:
            Portfolio object with positions, balances, etc.

        Raises:
            BrokerError: If portfolio fetch fails
        """
        pass

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Fetch current positions.

        Returns:
            List of Position objects

        Raises:
            BrokerError: If positions fetch fails
        """
        pass

    @abstractmethod
    def get_quote(self, symbol: Symbol) -> Quote:
        """Fetch real-time quote for a symbol.

        Args:
            symbol: Symbol to get quote for

        Returns:
            Quote object with current price data

        Raises:
            BrokerError: If quote fetch fails
        """
        pass

    @abstractmethod
    def get_quotes(self, symbols: list[Symbol]) -> dict[str, Quote]:
        """Fetch real-time quotes for multiple symbols.

        Args:
            symbols: List of symbols to get quotes for

        Returns:
            Dictionary mapping ticker to Quote

        Raises:
            BrokerError: If quotes fetch fails
        """
        pass

    def __enter__(self) -> BaseBroker:
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(connected={self.is_connected()})>"
