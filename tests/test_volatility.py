"""Tests for GARCH volatility module."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _make_returns(n: int = 300, seed: int = 42) -> pd.Series:
    """Generate synthetic daily returns."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0005, 0.015, size=n)
    return pd.Series(returns, index=pd.bdate_range("2023-01-01", periods=n))


class TestFitGarch:
    def test_fit_garch_returns_result(self) -> None:
        from clawdfolio.analysis.volatility import fit_garch

        returns = _make_returns()
        result = fit_garch(returns)
        assert result is not None
        assert hasattr(result, "params")

    def test_fit_garch_short_series(self) -> None:
        from clawdfolio.analysis.volatility import fit_garch

        returns = _make_returns(n=30)
        result = fit_garch(returns)
        assert result is not None


class TestForecastVolatility:
    def test_forecast_returns_float(self) -> None:
        from clawdfolio.analysis.volatility import forecast_volatility

        returns = _make_returns()
        vol = forecast_volatility(returns, horizon=5)
        assert vol is not None
        assert isinstance(vol, float)
        assert vol > 0

    def test_forecast_too_short_returns_none(self) -> None:
        from clawdfolio.analysis.volatility import forecast_volatility

        returns = _make_returns(n=20)
        vol = forecast_volatility(returns)
        assert vol is None

    def test_forecast_reasonable_range(self) -> None:
        from clawdfolio.analysis.volatility import forecast_volatility

        returns = _make_returns()
        vol = forecast_volatility(returns)
        assert vol is not None
        assert 0.05 < vol < 1.0


class TestCompareVolEstimates:
    def test_compare_returns_all_keys(self) -> None:
        from clawdfolio.analysis.volatility import compare_vol_estimates

        returns = _make_returns()
        result = compare_vol_estimates(returns)
        assert "rolling_20d" in result
        assert "rolling_60d" in result
        assert "garch_forecast" in result

    def test_compare_short_series(self) -> None:
        from clawdfolio.analysis.volatility import compare_vol_estimates

        returns = _make_returns(n=15)
        result = compare_vol_estimates(returns)
        assert result["rolling_20d"] is None
        assert result["rolling_60d"] is None
        assert result["garch_forecast"] is None
