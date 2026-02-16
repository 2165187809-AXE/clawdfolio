"""Clawdfolio — quantitative portfolio toolkit with multi-broker aggregation, risk analytics, and options strategy management."""

__version__ = "2.2.0"
__author__ = "YICHENG YANG"

from .core.config import Config, load_config
from .core.exceptions import (
    BrokerError,
    ConfigError,
    MarketDataError,
    PortfolioMonitorError,
)
from .core.types import Alert, Portfolio, Position, Quote, RiskMetrics, Symbol

__all__ = [
    # Core types
    "Symbol",
    "Position",
    "Quote",
    "Portfolio",
    "RiskMetrics",
    "Alert",
    # Config
    "Config",
    "load_config",
    # Exceptions
    "PortfolioMonitorError",
    "BrokerError",
    "ConfigError",
    "MarketDataError",
]
