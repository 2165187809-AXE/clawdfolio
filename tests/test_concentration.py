"""Tests for concentration analysis module."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from clawdfolio.analysis.concentration import (
    analyze_concentration,
    calculate_concentration,
    calculate_hhi,
    effective_n,
    get_sector_exposure,
)
from clawdfolio.core.types import Exchange, Portfolio, Position, Symbol


def _make_portfolio(weights_and_tickers: list[tuple[str, float]]) -> Portfolio:
    """Create a portfolio with specified tickers and weights (via market_value)."""
    net_assets = Decimal("100000")
    positions = []
    for ticker, weight in weights_and_tickers:
        mv = Decimal(str(weight * 100000))
        positions.append(
            Position(
                symbol=Symbol(ticker=ticker, exchange=Exchange.NASDAQ),
                quantity=Decimal("100"),
                market_value=mv,
                current_price=mv / 100,
            )
        )
    return Portfolio(positions=positions, net_assets=net_assets, market_value=net_assets)


class TestCalculateHHI:
    """Tests for calculate_hhi."""

    def test_empty_weights(self):
        assert calculate_hhi([]) == 0.0

    def test_single_position(self):
        assert calculate_hhi([1.0]) == 1.0

    def test_equal_weights(self):
        # 4 equal positions: HHI = 4 * (0.25)^2 = 0.25
        assert abs(calculate_hhi([0.25, 0.25, 0.25, 0.25]) - 0.25) < 1e-9

    def test_concentrated(self):
        # One dominant position
        hhi = calculate_hhi([0.9, 0.05, 0.05])
        assert hhi > 0.8


class TestCalculateConcentration:
    """Tests for calculate_concentration."""

    def test_empty_portfolio(self):
        p = Portfolio(positions=[], net_assets=Decimal("0"), market_value=Decimal("0"))
        metrics = calculate_concentration(p)
        assert metrics.hhi == 0.0
        assert metrics.is_concentrated is False
        assert metrics.max_position_ticker == ""

    def test_single_position(self, sample_portfolio):
        metrics = calculate_concentration(sample_portfolio)
        assert metrics.max_position_ticker == "AAPL"
        assert metrics.top_5_weight > 0

    def test_concentrated_portfolio(self):
        p = _make_portfolio([("AAPL", 0.80), ("GOOG", 0.10), ("MSFT", 0.10)])
        metrics = calculate_concentration(p)
        assert metrics.is_concentrated is True
        assert metrics.max_position_weight > 0.25

    def test_diversified_portfolio(self):
        weights = [(f"T{i}", 0.05) for i in range(20)]
        p = _make_portfolio(weights)
        metrics = calculate_concentration(p)
        assert metrics.is_concentrated is False
        assert metrics.hhi < 0.15


class TestGetSectorExposure:
    """Tests for get_sector_exposure."""

    @patch("clawdfolio.analysis.concentration.get_sector")
    def test_sector_grouping(self, mock_get_sector):
        mock_get_sector.side_effect = lambda t: {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "JPM": "Financial",
        }.get(t, "Unknown")

        p = _make_portfolio([("AAPL", 0.4), ("MSFT", 0.3), ("JPM", 0.3)])
        sectors = get_sector_exposure(p)

        assert len(sectors) == 2
        # Sorted by weight desc, Technology first
        assert sectors[0].sector == "Technology"
        assert len(sectors[0].tickers) == 2
        assert abs(sectors[0].weight - 0.7) < 0.01

    @patch("clawdfolio.analysis.concentration.get_sector")
    def test_empty_portfolio(self, mock_get_sector):
        p = Portfolio(positions=[], net_assets=Decimal("0"), market_value=Decimal("0"))
        assert get_sector_exposure(p) == []


class TestAnalyzeConcentration:
    """Tests for analyze_concentration."""

    @patch("clawdfolio.analysis.concentration.get_sector")
    def test_concentrated_triggers_alerts(self, mock_get_sector):
        mock_get_sector.return_value = "Technology"
        p = _make_portfolio([("AAPL", 0.80), ("GOOG", 0.10), ("MSFT", 0.10)])
        result = analyze_concentration(p)

        assert result["is_concentrated"] is True
        alert_types = [a["type"] for a in result["alerts"]]
        assert "position_concentration" in alert_types
        assert "high_hhi" in alert_types

    @patch("clawdfolio.analysis.concentration.get_sector")
    def test_sector_concentration_alert(self, mock_get_sector):
        mock_get_sector.return_value = "Technology"
        p = _make_portfolio([("AAPL", 0.30), ("MSFT", 0.30), ("GOOG", 0.20), ("META", 0.20)])
        result = analyze_concentration(p, sector_threshold=0.40)
        alert_types = [a["type"] for a in result["alerts"]]
        assert "sector_concentration" in alert_types

    @patch("clawdfolio.analysis.concentration.get_sector")
    def test_top5_concentration_alert(self, mock_get_sector):
        mock_get_sector.return_value = "Tech"
        # All weight in 2 positions > 80%
        p = _make_portfolio([("AAPL", 0.50), ("GOOG", 0.50)])
        result = analyze_concentration(p)
        alert_types = [a["type"] for a in result["alerts"]]
        assert "top_5_concentration" in alert_types

    @patch("clawdfolio.analysis.concentration.get_sector")
    def test_no_alerts_diversified(self, mock_get_sector):
        mock_get_sector.side_effect = lambda t: f"Sector{t[-1]}"
        weights = [(f"T{i}", 0.05) for i in range(20)]
        p = _make_portfolio(weights)
        result = analyze_concentration(p)
        assert result["is_concentrated"] is False
        assert len(result["alerts"]) == 0


class TestEffectiveN:
    """Tests for effective_n."""

    def test_equal_weights(self):
        weights = [0.25, 0.25, 0.25, 0.25]
        assert abs(effective_n(weights) - 4.0) < 1e-9

    def test_single_position(self):
        assert abs(effective_n([1.0]) - 1.0) < 1e-9

    def test_empty_weights(self):
        assert effective_n([]) == 0.0

    def test_concentrated(self):
        result = effective_n([0.9, 0.1])
        assert 1.0 < result < 2.0

    def test_many_equal_weights(self):
        n = 20
        weights = [1.0 / n] * n
        assert abs(effective_n(weights) - float(n)) < 1e-6

    @patch("clawdfolio.analysis.concentration.get_sector")
    def test_analyze_concentration_has_effective_n(self, mock_get_sector):
        mock_get_sector.return_value = "Tech"
        p = _make_portfolio([("AAPL", 0.50), ("GOOG", 0.50)])
        result = analyze_concentration(p)
        assert "effective_n" in result
        assert abs(result["effective_n"] - 2.0) < 1e-9
        assert result["n_positions"] == 2
