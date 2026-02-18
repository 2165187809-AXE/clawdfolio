"""GARCH(1,1) volatility forecasting."""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd

TRADING_DAYS_YEAR = 252


def fit_garch(
    returns: pd.Series,
    p: int = 1,
    q: int = 1,
) -> Any:
    """Fit a GARCH(p, q) model to a return series.

    Args:
        returns: Daily return series
        p: GARCH lag order
        q: ARCH lag order

    Returns:
        Fitted arch model result
    """
    from arch import arch_model

    # Scale to percentage returns for numerical stability
    scaled = returns.dropna() * 100

    model = arch_model(scaled, vol="GARCH", p=p, q=q, mean="Zero", rescale=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = model.fit(disp="off")

    return result


def forecast_volatility(
    returns: pd.Series,
    horizon: int = 5,
    p: int = 1,
    q: int = 1,
) -> float | None:
    """Forecast annualized volatility using GARCH(p, q).

    Args:
        returns: Daily return series
        horizon: Forecast horizon in trading days
        p: GARCH lag order
        q: ARCH lag order

    Returns:
        Annualized volatility forecast, or None if fitting fails
    """
    if len(returns.dropna()) < 60:
        return None

    try:
        result = fit_garch(returns, p=p, q=q)
        fcast = result.forecast(horizon=horizon)
        # fcast.variance is in percentage-squared units; average over horizon
        avg_var = float(fcast.variance.iloc[-1].mean())
        # Convert back from percentage variance to decimal daily vol, then annualize
        daily_vol = np.sqrt(avg_var) / 100.0
        return float(daily_vol * np.sqrt(TRADING_DAYS_YEAR))
    except Exception:
        return None


def compare_vol_estimates(returns: pd.Series) -> dict[str, float | None]:
    """Compare rolling and GARCH volatility estimates.

    Args:
        returns: Daily return series

    Returns:
        Dictionary with rolling_20d, rolling_60d, and garch_forecast volatility
    """
    returns_clean = returns.dropna()

    rolling_20d: float | None = None
    rolling_60d: float | None = None

    if len(returns_clean) >= 20:
        rolling_20d = float(np.std(returns_clean[-20:], ddof=1) * np.sqrt(TRADING_DAYS_YEAR))

    if len(returns_clean) >= 60:
        rolling_60d = float(np.std(returns_clean[-60:], ddof=1) * np.sqrt(TRADING_DAYS_YEAR))

    garch_forecast = forecast_volatility(returns)

    return {
        "rolling_20d": rolling_20d,
        "rolling_60d": rolling_60d,
        "garch_forecast": garch_forecast,
    }
