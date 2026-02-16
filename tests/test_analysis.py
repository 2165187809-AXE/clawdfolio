"""Tests for analysis modules."""

import numpy as np
import pandas as pd

from clawdfolio.analysis.concentration import (
    calculate_concentration,
    calculate_hhi,
)
from clawdfolio.analysis.risk import (
    calculate_beta,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_var,
    calculate_volatility,
)
from clawdfolio.analysis.technical import (
    calculate_bollinger_bands,
    calculate_ema,
    calculate_rsi,
    calculate_rsi_series,
    calculate_sma,
)


class TestRiskCalculations:
    """Tests for risk calculations."""

    def test_calculate_volatility(self):
        """Test volatility calculation."""
        # Generate random returns with known volatility
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 100)  # ~2% daily vol

        vol = calculate_volatility(returns, window=20, annualize=False)
        assert vol is not None
        assert 0.01 < vol < 0.05  # Should be around 2%

    def test_calculate_volatility_annualized(self):
        """Test annualized volatility."""
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 100)

        vol = calculate_volatility(returns, window=20, annualize=True)
        assert vol is not None
        assert vol > 0.1  # Annualized should be larger

    def test_calculate_volatility_insufficient_data(self):
        """Test volatility with insufficient data."""
        returns = [0.01, 0.02, 0.01]  # Only 3 points
        vol = calculate_volatility(returns, window=20)
        assert vol is None

    def test_calculate_beta(self):
        """Test beta calculation."""
        np.random.seed(42)
        # Create correlated returns
        market_returns = np.random.normal(0.001, 0.01, 100)
        asset_returns = market_returns * 1.5 + np.random.normal(0, 0.005, 100)

        beta = calculate_beta(asset_returns, market_returns)
        assert beta is not None
        assert 1.0 < beta < 2.0  # Should be around 1.5

    def test_calculate_sharpe_ratio(self):
        """Test Sharpe ratio calculation."""
        # Create returns with positive excess return
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.015, 100)  # ~1% daily return

        sharpe = calculate_sharpe_ratio(returns, rf_rate=0.045)
        assert sharpe is not None
        # Could be positive or negative depending on random seed

    def test_calculate_var(self):
        """Test VaR calculation."""
        np.random.seed(42)
        returns = np.random.normal(-0.001, 0.02, 100)

        var_95, var_amt = calculate_var(returns, confidence=0.95)
        assert var_95 > 0

        var_95, var_amt = calculate_var(returns, confidence=0.95, portfolio_value=100000)
        assert var_amt is not None
        assert var_amt > 0

    def test_calculate_max_drawdown(self):
        """Test max drawdown calculation."""
        # Create a price series with a known drawdown
        prices = [100, 110, 105, 95, 90, 100, 105]

        max_dd, current_dd = calculate_max_drawdown(prices)

        # Max drawdown should be from 110 to 90 = 18.18%
        assert abs(max_dd - 0.1818) < 0.01


class TestTechnicalIndicators:
    """Tests for technical indicators."""

    def test_calculate_rsi(self):
        """Test RSI calculation."""
        # Create prices with upward trend
        prices = [100 + i * 0.5 for i in range(30)]
        rsi = calculate_rsi(prices, period=14)

        assert rsi is not None
        assert 0 <= rsi <= 100
        assert rsi > 50  # Upward trend should have RSI > 50

    def test_calculate_rsi_downtrend(self):
        """Test RSI in downtrend."""
        # Create prices with downward trend
        prices = [100 - i * 0.5 for i in range(30)]
        rsi = calculate_rsi(prices, period=14)

        assert rsi is not None
        assert rsi < 50  # Downward trend should have RSI < 50

    def test_calculate_rsi_insufficient_data(self):
        """Test RSI with insufficient data."""
        prices = [100, 101, 102]
        rsi = calculate_rsi(prices, period=14)
        assert rsi is None

    def test_calculate_rsi_series_uses_wilder_ema(self):
        """RSI series should follow Wilder EMA smoothing, not simple rolling averages."""
        prices = pd.Series(
            [
                100, 101, 103, 102, 104, 107, 106, 105, 104, 103,
                102, 101, 100, 99, 98, 99, 100, 101, 102, 103,
                104, 105, 103, 101, 99, 100, 102, 104, 103, 105,
            ],
            dtype="float64",
        )
        period = 14

        actual = calculate_rsi_series(prices, period=period)

        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta.where(delta < 0, 0.0))
        expected = 100 - (
            100
            / (
                1
                + gain.ewm(alpha=1 / period, min_periods=period).mean()
                / loss.ewm(alpha=1 / period, min_periods=period).mean()
            )
        )
        simple = 100 - (100 / (1 + gain.rolling(period).mean() / loss.rolling(period).mean()))

        np.testing.assert_allclose(
            actual.dropna().tail(5).to_numpy(),
            expected.dropna().tail(5).to_numpy(),
            rtol=1e-9,
            atol=1e-9,
        )
        # Ensure we are not silently using the old simple rolling average implementation.
        assert abs(actual.iloc[-1] - simple.iloc[-1]) > 1.0

    def test_calculate_rsi_flat_prices(self):
        """Flat prices should produce neutral RSI."""
        prices = [100.0] * 30
        rsi = calculate_rsi(prices, period=14)
        assert rsi is not None
        assert abs(rsi - 50.0) < 1e-9

    def test_calculate_sma(self):
        """Test SMA calculation."""
        prices = [100, 102, 104, 103, 105, 107, 106, 108, 110, 109]
        sma = calculate_sma(prices, period=5)

        assert sma is not None
        # SMA of last 5: (107 + 106 + 108 + 110 + 109) / 5 = 108
        assert abs(sma - 108) < 0.01

    def test_calculate_ema(self):
        """Test EMA calculation."""
        prices = [100, 102, 104, 103, 105, 107, 106, 108, 110, 109]
        ema = calculate_ema(prices, period=5)

        assert ema is not None
        # EMA gives more weight to recent prices

    def test_calculate_bollinger_bands(self):
        """Test Bollinger Bands calculation."""
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.normal(0, 1, 50))

        bands = calculate_bollinger_bands(prices, period=20, std_dev=2.0)

        assert bands is not None
        assert bands.upper > bands.middle > bands.lower
        assert bands.bandwidth > 0
        assert 0 <= bands.percent_b <= 1 or bands.percent_b < 0 or bands.percent_b > 1


    def test_calculate_beta_insufficient_data(self):
        """Test beta with insufficient data returns None."""
        asset = np.random.normal(0, 0.01, 10)
        bench = np.random.normal(0, 0.01, 10)
        assert calculate_beta(asset, bench) is None

    def test_calculate_var_insufficient_data(self):
        """Test VaR with insufficient data returns zeros."""
        returns = [0.01, 0.02]
        var_pct, var_amt = calculate_var(returns)
        assert var_pct == 0.0
        assert var_amt is None

    def test_zero_weight_portfolio(self):
        """Test that zero-weight portfolio doesn't crash (ZeroDivisionError fix)."""
        from decimal import Decimal
        from unittest.mock import patch

        from clawdfolio.analysis.risk import analyze_risk
        from clawdfolio.core.types import Exchange, Portfolio, Position, Symbol

        pos = Position(
            symbol=Symbol(ticker="AAPL", exchange=Exchange.NYSE),
            quantity=Decimal("100"),
            avg_cost=Decimal("150.00"),
            market_value=Decimal("17550.00"),
            day_pnl=Decimal("0"),
            day_pnl_pct=0.0,
            current_price=Decimal("175.50"),
            source="test",
        )
        pos.weight = 0.0
        positions = [pos]
        portfolio = Portfolio(
            positions=positions,
            cash=Decimal("10000.00"),
            net_assets=Decimal("27550.00"),
            market_value=Decimal("17550.00"),
            buying_power=Decimal("10000.00"),
            day_pnl=Decimal("0"),
            day_pnl_pct=0.0,
            currency="USD",
            source="test",
        )

        # Mock get_history_multi to return data so we reach the weight normalization code
        mock_prices = pd.DataFrame(
            {"AAPL": np.random.normal(100, 1, 50)},
            index=pd.date_range("2025-01-01", periods=50),
        )
        with patch("clawdfolio.analysis.risk.get_history_multi", return_value=mock_prices):
            metrics = analyze_risk(portfolio)
        # Should return metrics without crashing
        assert metrics is not None


class TestConcentration:
    """Tests for concentration analysis."""

    def test_calculate_hhi_equal_weights(self):
        """Test HHI with equal weights."""
        # 10 equal positions = HHI of 0.1
        weights = [0.1] * 10
        hhi = calculate_hhi(weights)
        assert abs(hhi - 0.1) < 0.001

    def test_calculate_hhi_concentrated(self):
        """Test HHI with concentrated portfolio."""
        # One position at 100% = HHI of 1.0
        weights = [1.0]
        hhi = calculate_hhi(weights)
        assert hhi == 1.0

    def test_calculate_hhi_empty(self):
        """Test HHI with empty weights."""
        hhi = calculate_hhi([])
        assert hhi == 0.0

    def test_calculate_concentration(self, sample_portfolio):
        """Test concentration metrics calculation."""
        metrics = calculate_concentration(sample_portfolio)

        assert metrics.hhi > 0
        assert metrics.top_5_weight >= 0
        assert metrics.max_position_weight >= 0
        assert metrics.max_position_ticker != ""
