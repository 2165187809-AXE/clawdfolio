"""Core data types for Portfolio Monitor."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class Exchange(str, Enum):
    """Supported exchanges."""

    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    AMEX = "AMEX"
    HKEX = "HKEX"
    SSE = "SSE"  # Shanghai
    SZSE = "SZSE"  # Shenzhen
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_suffix(cls, suffix: str) -> Exchange:
        """Parse exchange from ticker suffix (e.g., '.US', '.HK')."""
        mapping = {
            "US": cls.NYSE,  # Default US to NYSE
            "HK": cls.HKEX,
            "SH": cls.SSE,
            "SZ": cls.SZSE,
        }
        return mapping.get(suffix.upper(), cls.UNKNOWN)


class AlertType(str, Enum):
    """Types of alerts."""

    PRICE_MOVE = "price_move"
    RSI_EXTREME = "rsi_extreme"
    CONCENTRATION = "concentration"
    PNL_THRESHOLD = "pnl_threshold"
    EARNINGS = "earnings"
    GAP = "gap"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Symbol:
    """Represents a tradable symbol."""

    ticker: str
    exchange: Exchange = Exchange.UNKNOWN
    name: str = ""

    def __post_init__(self) -> None:
        # Normalize ticker (remove exchange suffix if present)
        if "." in self.ticker:
            parts = self.ticker.rsplit(".", 1)
            self.ticker = parts[0]
            if self.exchange == Exchange.UNKNOWN:
                self.exchange = Exchange.from_suffix(parts[1])

    @property
    def full_symbol(self) -> str:
        """Return full symbol with exchange suffix."""
        suffix_map = {
            Exchange.NYSE: "US",
            Exchange.NASDAQ: "US",
            Exchange.AMEX: "US",
            Exchange.HKEX: "HK",
            Exchange.SSE: "SH",
            Exchange.SZSE: "SZ",
        }
        suffix = suffix_map.get(self.exchange, "")
        return f"{self.ticker}.{suffix}" if suffix else self.ticker

    def __str__(self) -> str:
        return self.ticker

    def __hash__(self) -> int:
        return hash((self.ticker, self.exchange))


@dataclass
class Quote:
    """Real-time quote data."""

    symbol: Symbol
    price: Decimal
    prev_close: Decimal | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    volume: int = 0
    turnover: Decimal | None = None
    timestamp: datetime | None = None
    source: str = ""

    @property
    def change(self) -> Decimal | None:
        """Price change from previous close."""
        if self.prev_close and self.prev_close > 0:
            return self.price - self.prev_close
        return None

    @property
    def change_pct(self) -> float | None:
        """Percentage change from previous close."""
        if self.prev_close and self.prev_close > 0:
            return float((self.price - self.prev_close) / self.prev_close)
        return None


@dataclass
class Position:
    """Represents a portfolio position."""

    symbol: Symbol
    quantity: Decimal
    avg_cost: Decimal | None = None
    market_value: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    unrealized_pnl_pct: float = 0.0
    day_pnl: Decimal = Decimal("0")
    day_pnl_pct: float = 0.0
    current_price: Decimal | None = None
    prev_close: Decimal | None = None
    name: str = ""
    source: str = ""
    is_option: bool = False
    _weight: float = field(default=0.0, init=False, repr=False)

    @property
    def weight(self) -> float:
        """Position weight - must be set externally based on portfolio."""
        return self._weight

    @weight.setter
    def weight(self, value: float) -> None:
        self._weight = value

    def update_from_quote(self, quote: Quote) -> None:
        """Update position with latest quote data."""
        self.current_price = quote.price
        self.prev_close = quote.prev_close
        self.market_value = self.quantity * quote.price

        if quote.prev_close:
            self.day_pnl = self.quantity * (quote.price - quote.prev_close)
            self.day_pnl_pct = float(quote.change_pct or 0)

        if self.avg_cost and self.avg_cost > 0:
            self.unrealized_pnl = self.quantity * (quote.price - self.avg_cost)
            self.unrealized_pnl_pct = float(
                (quote.price - self.avg_cost) / self.avg_cost
            )


@dataclass
class Portfolio:
    """Aggregated portfolio data."""

    positions: list[Position] = field(default_factory=list)
    _ticker_index: dict[str, Position] = field(default_factory=dict, init=False, repr=False)
    cash: Decimal = Decimal("0")
    net_assets: Decimal = Decimal("0")
    market_value: Decimal = Decimal("0")
    buying_power: Decimal = Decimal("0")
    day_pnl: Decimal = Decimal("0")
    day_pnl_pct: float = 0.0
    currency: str = "USD"
    source: str = ""
    timestamp: datetime | None = None

    def __post_init__(self) -> None:
        self._update_weights()
        self._ticker_index = {p.symbol.ticker: p for p in self.positions}

    def _update_weights(self) -> None:
        """Update position weights based on net assets."""
        if self.net_assets > 0:
            for pos in self.positions:
                pos.weight = float(pos.market_value / self.net_assets)

    def add_position(self, position: Position) -> None:
        """Add a position and update weights."""
        self.positions.append(position)
        self._ticker_index[position.symbol.ticker] = position
        self._update_weights()

    @property
    def sorted_by_weight(self) -> list[Position]:
        """Return positions sorted by weight (descending)."""
        return sorted(self.positions, key=lambda p: p.weight, reverse=True)

    @property
    def top_holdings(self) -> list[Position]:
        """Return top 10 holdings by weight."""
        return self.sorted_by_weight[:10]

    def get_position(self, ticker: str) -> Position | None:
        """Get position by ticker."""
        return self._ticker_index.get(ticker)


@dataclass
class RiskMetrics:
    """Portfolio risk metrics."""

    # Volatility
    volatility_20d: float | None = None
    volatility_60d: float | None = None
    volatility_annualized: float | None = None

    # Beta
    beta_spy: float | None = None
    beta_qqq: float | None = None

    # Sharpe Ratio
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    risk_free_rate: float = 0.045

    # Value at Risk
    var_95: float | None = None  # 95% VaR as percentage
    var_99: float | None = None  # 99% VaR as percentage
    var_95_amount: Decimal | None = None  # 95% VaR in currency
    var_99_amount: Decimal | None = None  # 99% VaR in currency
    cvar_95: float | None = None
    cvar_99: float | None = None

    # Concentration
    hhi: float | None = None  # Herfindahl-Hirschman Index
    top_5_concentration: float | None = None
    max_position_weight: float | None = None

    # Technical
    rsi_portfolio: float | None = None

    # Correlation
    high_corr_pairs: list[tuple[str, str, float]] = field(default_factory=list)

    # Max Drawdown
    max_drawdown: float | None = None
    current_drawdown: float | None = None

    # GARCH volatility
    garch_vol_forecast: float | None = None

    timestamp: datetime | None = None


@dataclass
class Alert:
    """Represents a portfolio alert."""

    type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    ticker: str | None = None
    value: float | None = None
    threshold: float | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        prefix = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🚨",
        }.get(self.severity, "")
        return f"{prefix} {self.title}\n{self.message}"
