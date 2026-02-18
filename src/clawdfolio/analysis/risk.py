"""Risk analysis calculations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..analysis.technical import calculate_rsi
from ..core.types import RiskMetrics
from ..market.data import get_history_multi, risk_free_rate

if TYPE_CHECKING:
    from ..core.types import Portfolio

TRADING_DAYS_YEAR = 252


def calculate_volatility(
    returns: pd.Series | np.ndarray,
    window: int = 20,
    annualize: bool = True
) -> float | None:
    """Calculate rolling volatility.

    Args:
        returns: Series of daily returns
        window: Rolling window size
        annualize: Whether to annualize the result

    Returns:
        Volatility as a decimal (e.g., 0.25 for 25%)
    """
    if len(returns) < window:
        return None

    vol = np.std(returns[-window:], ddof=1)

    if annualize:
        vol *= np.sqrt(TRADING_DAYS_YEAR)

    return float(vol)


def calculate_beta(
    asset_returns: pd.Series | np.ndarray,
    benchmark_returns: pd.Series | np.ndarray,
) -> float | None:
    """Calculate beta against a benchmark.

    Args:
        asset_returns: Daily returns of the asset/portfolio
        benchmark_returns: Daily returns of the benchmark

    Returns:
        Beta coefficient
    """
    if len(asset_returns) < 20 or len(benchmark_returns) < 20:
        return None

    # Align lengths and flatten to 1D
    min_len = min(len(asset_returns), len(benchmark_returns))
    asset = np.array(asset_returns).flatten()[-min_len:]
    bench = np.array(benchmark_returns).flatten()[-min_len:]

    # Remove NaN
    mask = ~(np.isnan(asset) | np.isnan(bench))
    asset = asset[mask]
    bench = bench[mask]

    if len(asset) < 20:
        return None

    covariance = np.cov(asset, bench)[0, 1]
    variance = np.var(bench, ddof=1)

    if variance == 0:
        return None

    return float(covariance / variance)


def calculate_sharpe_ratio(
    returns: pd.Series | np.ndarray,
    rf_rate: float | None = None,
) -> float | None:
    """Calculate Sharpe ratio.

    Args:
        returns: Daily returns
        rf_rate: Annual risk-free rate (defaults to current 10Y Treasury)

    Returns:
        Sharpe ratio
    """
    if len(returns) < 20:
        return None

    if rf_rate is None:
        rf_rate = risk_free_rate()

    returns_arr = np.array(returns)
    returns_arr = returns_arr[~np.isnan(returns_arr)]

    if len(returns_arr) < 20:
        return None

    # Daily risk-free rate
    rf_daily = rf_rate / TRADING_DAYS_YEAR

    excess_returns = returns_arr - rf_daily
    mean_excess = np.mean(excess_returns)
    std_excess = np.std(excess_returns, ddof=1)

    if std_excess == 0:
        return None

    # Annualize
    sharpe = (mean_excess / std_excess) * np.sqrt(TRADING_DAYS_YEAR)

    return float(sharpe)


def calculate_sortino_ratio(
    returns: pd.Series | np.ndarray,
    rf_rate: float | None = None,
) -> float | None:
    """Calculate Sortino ratio (penalizes only downside volatility)."""
    if len(returns) < 20:
        return None
    if rf_rate is None:
        rf_rate = risk_free_rate()
    returns_arr = np.array(returns)
    returns_arr = returns_arr[~np.isnan(returns_arr)]
    if len(returns_arr) < 20:
        return None
    rf_daily = rf_rate / TRADING_DAYS_YEAR
    excess_returns = returns_arr - rf_daily
    downside_returns = excess_returns[excess_returns < 0]
    if len(downside_returns) == 0:
        return None
    downside_std = np.std(downside_returns, ddof=1)
    if downside_std == 0:
        return None
    sortino = (np.mean(excess_returns) / downside_std) * np.sqrt(TRADING_DAYS_YEAR)
    return float(sortino)


def calculate_cvar(
    returns: pd.Series | np.ndarray,
    confidence: float = 0.95,
    portfolio_value: float | None = None,
) -> tuple[float, float | None]:
    """Calculate Conditional VaR (Expected Shortfall)."""
    returns_arr = np.array(returns)
    returns_arr = returns_arr[~np.isnan(returns_arr)]
    if len(returns_arr) < 20:
        return 0.0, None
    var_threshold = np.percentile(returns_arr, (1 - confidence) * 100)
    tail_returns = returns_arr[returns_arr <= var_threshold]
    if len(tail_returns) == 0:
        return 0.0, None
    cvar_pct = float(abs(np.mean(tail_returns)))
    cvar_amount = None
    if portfolio_value:
        cvar_amount = cvar_pct * portfolio_value
    return cvar_pct, cvar_amount


def calculate_var(
    returns: pd.Series | np.ndarray,
    confidence: float = 0.95,
    portfolio_value: float | None = None,
) -> tuple[float, float | None]:
    """Calculate Value at Risk (Historical).

    Args:
        returns: Daily returns
        confidence: Confidence level (e.g., 0.95 for 95%)
        portfolio_value: Optional portfolio value for absolute VaR

    Returns:
        Tuple of (VaR percentage, VaR amount if portfolio_value provided)
    """
    returns_arr = np.array(returns)
    returns_arr = returns_arr[~np.isnan(returns_arr)]

    if len(returns_arr) < 20:
        return 0.0, None

    var_pct = float(np.percentile(returns_arr, (1 - confidence) * 100))
    var_amount = None

    if portfolio_value:
        var_amount = abs(var_pct * portfolio_value)

    return abs(var_pct), var_amount


def calculate_max_drawdown(prices: pd.Series | np.ndarray) -> tuple[float, float]:
    """Calculate maximum drawdown.

    Args:
        prices: Price series

    Returns:
        Tuple of (max_drawdown, current_drawdown) as percentages
    """
    prices_arr = np.array(prices)
    prices_arr = prices_arr[~np.isnan(prices_arr)]

    if len(prices_arr) < 2:
        return 0.0, 0.0

    # Running maximum
    running_max = np.maximum.accumulate(prices_arr)

    # Drawdown series
    drawdown = (prices_arr - running_max) / running_max

    max_dd = float(abs(np.min(drawdown)))
    current_dd = float(abs(drawdown[-1]))

    return max_dd, current_dd


def calculate_correlation_matrix(
    tickers: list[str],
    period: str = "1y",
) -> pd.DataFrame:
    """Calculate correlation matrix for a list of tickers.

    Args:
        tickers: List of tickers
        period: Historical period

    Returns:
        Correlation matrix DataFrame
    """
    if len(tickers) < 2:
        return pd.DataFrame()

    prices = get_history_multi(tickers, period)
    if prices.empty:
        return pd.DataFrame()

    returns = prices.pct_change().dropna()
    return returns.corr()


def find_high_correlations(
    corr_matrix: pd.DataFrame,
    threshold: float = 0.8,
) -> list[tuple[str, str, float]]:
    """Find pairs with correlation above threshold.

    Args:
        corr_matrix: Correlation matrix
        threshold: Correlation threshold

    Returns:
        List of (ticker1, ticker2, correlation) tuples
    """
    pairs = []
    tickers = list(corr_matrix.columns)

    for i, t1 in enumerate(tickers):
        for j, t2 in enumerate(tickers):
            if i < j:  # Only upper triangle
                corr = corr_matrix.loc[t1, t2]
                if abs(corr) >= threshold:
                    pairs.append((t1, t2, float(corr)))

    return sorted(pairs, key=lambda x: abs(x[2]), reverse=True)


def analyze_risk(portfolio: Portfolio) -> RiskMetrics:
    """Comprehensive risk analysis for a portfolio.

    Args:
        portfolio: Portfolio object

    Returns:
        RiskMetrics object with all calculated metrics
    """
    metrics = RiskMetrics(timestamp=datetime.now())

    if not portfolio.positions:
        return metrics

    # Get tickers and weights
    tickers = [p.symbol.ticker for p in portfolio.positions]
    weights = np.array([p.weight for p in portfolio.positions])

    # Get historical prices
    prices = get_history_multi(tickers, period="1y")
    if prices.empty:
        return metrics

    returns = prices.pct_change().dropna()
    if returns.empty:
        return metrics

    # Calculate portfolio returns (weighted)
    # Align weights with available tickers in returns
    available_tickers = [t for t in tickers if t in returns.columns]
    if not available_tickers:
        return metrics

    ticker_weights = {t: w for t, w in zip(tickers, weights, strict=False) if t in available_tickers}
    w = np.array([ticker_weights[t] for t in available_tickers])
    if w.sum() == 0:
        return metrics
    w = w / w.sum()  # Renormalize

    port_returns = (returns[available_tickers] * w).sum(axis=1)

    # Volatility
    metrics.volatility_20d = calculate_volatility(port_returns, window=20)
    metrics.volatility_60d = calculate_volatility(port_returns, window=60)
    metrics.volatility_annualized = metrics.volatility_20d

    # Beta
    bench_prices = get_history_multi(["SPY", "QQQ"], period="1y")

    if not bench_prices.empty and "SPY" in bench_prices.columns:
        spy_returns = bench_prices["SPY"].pct_change().dropna()
        metrics.beta_spy = calculate_beta(port_returns, spy_returns)

    if not bench_prices.empty and "QQQ" in bench_prices.columns:
        qqq_returns = bench_prices["QQQ"].pct_change().dropna()
        metrics.beta_qqq = calculate_beta(port_returns, qqq_returns)

    # Sharpe Ratio
    rf = risk_free_rate()
    metrics.risk_free_rate = rf
    metrics.sharpe_ratio = calculate_sharpe_ratio(port_returns, rf)
    metrics.sortino_ratio = calculate_sortino_ratio(port_returns, rf)

    # VaR
    net_assets = float(portfolio.net_assets)
    metrics.var_95, var_95_amt = calculate_var(port_returns, 0.95, net_assets)
    metrics.var_99, var_99_amt = calculate_var(port_returns, 0.99, net_assets)
    if var_95_amt:
        metrics.var_95_amount = Decimal(str(round(var_95_amt, 2)))
    if var_99_amt:
        metrics.var_99_amount = Decimal(str(round(var_99_amt, 2)))

    # CVaR (Expected Shortfall)
    metrics.cvar_95, _ = calculate_cvar(port_returns, 0.95, net_assets)
    metrics.cvar_99, _ = calculate_cvar(port_returns, 0.99, net_assets)

    # Max Drawdown (using portfolio value proxy)
    port_value = (1 + port_returns).cumprod()
    metrics.max_drawdown, metrics.current_drawdown = calculate_max_drawdown(port_value)

    # Portfolio-level RSI
    metrics.rsi_portfolio = calculate_rsi(port_value.values.tolist(), period=14)

    # GARCH volatility forecast
    try:
        from .volatility import forecast_volatility as _garch_forecast

        metrics.garch_vol_forecast = _garch_forecast(port_returns)
    except Exception:
        pass

    # Correlation analysis
    if len(available_tickers) >= 2:
        corr_matrix = returns[available_tickers].corr()
        metrics.high_corr_pairs = find_high_correlations(corr_matrix, threshold=0.8)

    return metrics
