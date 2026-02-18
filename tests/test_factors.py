"""Tests for Fama-French factor exposure module."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

from clawdfolio.analysis.factors import FactorExposure, analyze_factor_exposure


def _make_ff_data(n: int = 252) -> pd.DataFrame:
    """Generate synthetic Fama-French factor data."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2023-01-01", periods=n)
    return pd.DataFrame(
        {
            "Mkt-RF": rng.normal(0.0004, 0.01, n),
            "SMB": rng.normal(0.0001, 0.005, n),
            "HML": rng.normal(0.0001, 0.005, n),
            "RF": np.full(n, 0.0002),
        },
        index=dates,
    )


def _make_portfolio_returns(ff_data: pd.DataFrame, seed: int = 99) -> pd.Series:
    """Generate synthetic portfolio returns correlated with factors."""
    rng = np.random.default_rng(seed)
    port = (
        1.1 * ff_data["Mkt-RF"]
        + 0.3 * ff_data["SMB"]
        - 0.2 * ff_data["HML"]
        + ff_data["RF"]
        + rng.normal(0, 0.003, len(ff_data))
    )
    return pd.Series(port.values, index=ff_data.index)


class TestAnalyzeFactorExposure:
    def test_returns_factor_exposure(self) -> None:
        ff = _make_ff_data()
        port = _make_portfolio_returns(ff)

        with patch("clawdfolio.analysis.factors.download_ff_factors", return_value=ff):
            result = analyze_factor_exposure(port, period="1y")

        assert isinstance(result, FactorExposure)
        assert "Mkt-RF" in result.factor_loadings
        assert "SMB" in result.factor_loadings
        assert "HML" in result.factor_loadings

    def test_market_beta_close_to_expected(self) -> None:
        ff = _make_ff_data(500)
        port = _make_portfolio_returns(ff)

        with patch("clawdfolio.analysis.factors.download_ff_factors", return_value=ff):
            result = analyze_factor_exposure(port, period="1y")

        assert abs(result.factor_loadings["Mkt-RF"] - 1.1) < 0.3

    def test_r_squared_positive(self) -> None:
        ff = _make_ff_data()
        port = _make_portfolio_returns(ff)

        with patch("clawdfolio.analysis.factors.download_ff_factors", return_value=ff):
            result = analyze_factor_exposure(port, period="1y")

        assert result.r_squared > 0.5

    def test_too_few_observations(self) -> None:
        ff = _make_ff_data(10)
        port = _make_portfolio_returns(ff)

        with patch("clawdfolio.analysis.factors.download_ff_factors", return_value=ff):
            result = analyze_factor_exposure(port, period="1y")

        assert result.factor_loadings == {}

    def test_p_values_present(self) -> None:
        ff = _make_ff_data()
        port = _make_portfolio_returns(ff)

        with patch("clawdfolio.analysis.factors.download_ff_factors", return_value=ff):
            result = analyze_factor_exposure(port, period="1y")

        for factor in ["Mkt-RF", "SMB", "HML"]:
            assert factor in result.p_values
            assert 0.0 <= result.p_values[factor] <= 1.0
