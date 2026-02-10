"""Technical analysis indicators."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..market.data import get_history


@dataclass
class RSIResult:
    """RSI calculation result."""
    ticker: str
    rsi: float
    is_overbought: bool
    is_oversold: bool


@dataclass
class BollingerBands:
    """Bollinger Bands result."""
    upper: float
    middle: float
    lower: float
    bandwidth: float
    percent_b: float  # Position relative to bands


def calculate_rsi(
    prices: pd.Series | np.ndarray,
    period: int = 14,
) -> float | None:
    """Calculate Relative Strength Index.

    Args:
        prices: Price series
        period: RSI period (default 14)

    Returns:
        RSI value (0-100) or None if insufficient data
    """
    if period <= 0:
        return None

    prices_series = pd.Series(np.array(prices), dtype="float64").dropna()
    if len(prices_series) < period + 1:
        return None

    rsi_series = calculate_rsi_series(prices_series, period=period).dropna()
    if rsi_series.empty:
        return None

    return float(rsi_series.iloc[-1])


def calculate_rsi_series(
    prices: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Calculate RSI as a series.

    Args:
        prices: Price series
        period: RSI period

    Returns:
        RSI series
    """
    if period <= 0:
        return pd.Series(dtype="float64")

    prices = prices.astype("float64")
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))

    # Wilder-style smoothing via EMA(alpha=1/period).
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    # Convention: no losses => RSI 100, no gains and no losses => RSI 50.
    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)

    return rsi


def calculate_sma(
    prices: pd.Series | np.ndarray,
    period: int = 20,
) -> float | None:
    """Calculate Simple Moving Average.

    Args:
        prices: Price series
        period: SMA period

    Returns:
        SMA value or None if insufficient data
    """
    prices_arr = np.array(prices)
    if len(prices_arr) < period:
        return None

    return float(np.mean(prices_arr[-period:]))


def calculate_ema(
    prices: pd.Series | np.ndarray,
    period: int = 20,
) -> float | None:
    """Calculate Exponential Moving Average.

    Args:
        prices: Price series
        period: EMA period

    Returns:
        EMA value or None if insufficient data
    """
    prices_arr = np.array(prices)
    if len(prices_arr) < period:
        return None

    # Calculate multiplier
    multiplier = 2 / (period + 1)

    # Start with SMA
    ema = np.mean(prices_arr[:period])

    # Calculate EMA
    for price in prices_arr[period:]:
        ema = (price - ema) * multiplier + ema

    return float(ema)


def calculate_bollinger_bands(
    prices: pd.Series | np.ndarray,
    period: int = 20,
    std_dev: float = 2.0,
) -> BollingerBands | None:
    """Calculate Bollinger Bands.

    Args:
        prices: Price series
        period: Moving average period
        std_dev: Number of standard deviations

    Returns:
        BollingerBands object or None if insufficient data
    """
    prices_arr = np.array(prices)
    if len(prices_arr) < period:
        return None

    recent = prices_arr[-period:]
    middle = float(np.mean(recent))
    std = float(np.std(recent, ddof=1))

    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)

    bandwidth = (upper - lower) / middle if middle != 0 else 0
    current_price = float(prices_arr[-1])

    # Percent B: position within bands
    if upper != lower:
        percent_b = (current_price - lower) / (upper - lower)
    else:
        percent_b = 0.5

    return BollingerBands(
        upper=upper,
        middle=middle,
        lower=lower,
        bandwidth=bandwidth,
        percent_b=percent_b,
    )


def detect_rsi_extremes(
    tickers: list[str],
    overbought: int = 70,
    oversold: int = 30,
    period: str = "1mo",
) -> list[RSIResult]:
    """Detect RSI extremes for multiple tickers.

    Args:
        tickers: List of tickers to check
        overbought: Overbought threshold (default 70)
        oversold: Oversold threshold (default 30)
        period: Historical period for calculation

    Returns:
        List of RSIResult for tickers with extreme RSI
    """
    results = []

    for ticker in tickers:
        hist = get_history(ticker, period=period)
        if hist.empty or len(hist) < 15:
            continue

        try:
            prices = hist["Close"]
            if isinstance(prices, pd.DataFrame):
                prices = prices.iloc[:, 0]
            prices = prices.dropna()

            rsi = calculate_rsi(prices)
            if rsi is None:
                continue

            is_overbought = rsi >= overbought
            is_oversold = rsi <= oversold

            if is_overbought or is_oversold:
                results.append(RSIResult(
                    ticker=ticker,
                    rsi=rsi,
                    is_overbought=is_overbought,
                    is_oversold=is_oversold,
                ))
        except Exception:
            continue

    return results


def calculate_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD indicator.

    Args:
        prices: Price series
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period

    Returns:
        Tuple of (MACD line, Signal line, Histogram)
    """
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def is_golden_cross(
    prices: pd.Series | np.ndarray,
    fast: int = 50,
    slow: int = 200,
) -> bool:
    """Check for golden cross (fast MA crosses above slow MA).

    Args:
        prices: Price series
        fast: Fast moving average period
        slow: Slow moving average period

    Returns:
        True if golden cross detected
    """
    prices_arr = np.array(prices)
    if len(prices_arr) < slow + 2:
        return False

    fast_ma_prev = np.mean(prices_arr[-(fast + 1):-1])
    fast_ma_curr = np.mean(prices_arr[-fast:])
    slow_ma_prev = np.mean(prices_arr[-(slow + 1):-1])
    slow_ma_curr = np.mean(prices_arr[-slow:])

    return fast_ma_prev <= slow_ma_prev and fast_ma_curr > slow_ma_curr


def is_death_cross(
    prices: pd.Series | np.ndarray,
    fast: int = 50,
    slow: int = 200,
) -> bool:
    """Check for death cross (fast MA crosses below slow MA).

    Args:
        prices: Price series
        fast: Fast moving average period
        slow: Slow moving average period

    Returns:
        True if death cross detected
    """
    prices_arr = np.array(prices)
    if len(prices_arr) < slow + 2:
        return False

    fast_ma_prev = np.mean(prices_arr[-(fast + 1):-1])
    fast_ma_curr = np.mean(prices_arr[-fast:])
    slow_ma_prev = np.mean(prices_arr[-(slow + 1):-1])
    slow_ma_curr = np.mean(prices_arr[-slow:])

    return fast_ma_prev >= slow_ma_prev and fast_ma_curr < slow_ma_curr
