"""Tests for bubble risk score and drawdown model."""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from clawdfolio.analysis.bubble import (
    BubbleRiskResult,
    _sma200_deviation,
    _trend_acceleration,
    _volatility_regime,
    calculate_bubble_risk,
    fetch_bubble_risk,
)


class TestSma200Deviation:
    def test_normal_deviation(self):
        prices = pd.Series(np.linspace(100, 120, 250))
        dev = _sma200_deviation(prices)
        assert dev > 0

    def test_insufficient_data(self):
        prices = pd.Series(np.linspace(100, 110, 50))
        assert _sma200_deviation(prices) == 0.0

    def test_zero_sma(self):
        prices = pd.Series([0.0] * 250)
        assert _sma200_deviation(prices) == 0.0


class TestTrendAcceleration:
    def test_uptrend(self):
        prices = pd.Series(np.exp(np.linspace(0, 1, 100)))
        accel = _trend_acceleration(prices)
        assert isinstance(accel, float)

    def test_insufficient_data(self):
        prices = pd.Series([100.0] * 10)
        assert _trend_acceleration(prices) == 0.0


class TestVolatilityRegime:
    def test_normal_vol(self):
        np.random.seed(42)
        prices = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0, 0.01, 100))))
        vol = _volatility_regime(prices)
        assert 0 < vol < 2.0

    def test_insufficient_data(self):
        prices = pd.Series([100.0] * 5)
        assert _volatility_regime(prices) == 0.5


class TestCalculateBubbleRisk:
    @patch("clawdfolio.analysis.bubble._safe_download")
    @patch("clawdfolio.analysis.bubble._get_close")
    def test_normal_calculation(self, mock_close, mock_download):
        np.random.seed(42)
        prices = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0.001, 0.02, 300))))
        mock_download.return_value = pd.DataFrame({"Close": prices})
        mock_close.return_value = prices

        result = calculate_bubble_risk("QQQ")
        assert isinstance(result, BubbleRiskResult)
        assert 0 <= result.drawdown_risk_score <= 100
        assert result.regime in ("low_risk", "moderate", "elevated", "high_risk")
        assert "sma200_deviation" in result.components

    @patch("clawdfolio.analysis.bubble._safe_download")
    @patch("clawdfolio.analysis.bubble._get_close")
    def test_insufficient_data_fallback(self, mock_close, mock_download):
        mock_download.return_value = pd.DataFrame({"Close": [100.0] * 50})
        mock_close.return_value = pd.Series([100.0] * 50)

        result = calculate_bubble_risk("QQQ")
        assert result.drawdown_risk_score == 50.0
        assert result.regime == "moderate"

    @patch("clawdfolio.analysis.bubble._safe_download")
    @patch("clawdfolio.analysis.bubble._get_close")
    def test_empty_data(self, mock_close, mock_download):
        mock_download.return_value = pd.DataFrame()
        mock_close.return_value = pd.Series(dtype=float)

        result = calculate_bubble_risk("QQQ")
        assert result.drawdown_risk_score == 50.0


class TestFetchBubbleRisk:
    @patch("urllib.request.urlopen")
    def test_fetch_success(self, mock_urlopen):
        mock_data = {
            "history": [
                {
                    "date": "2026-02-28",
                    "drawdown_risk_score": 72.5,
                    "composite_score": 68.0,
                    "components": {"sma200": 15.0},
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_bubble_risk()
        assert result.drawdown_risk_score == 72.5
        assert result.regime == "high_risk"
        assert result.date == "2026-02-28"

    @patch("urllib.request.urlopen")
    def test_fetch_low_risk(self, mock_urlopen):
        mock_data = {"history": [{"date": "2026-02-28", "drawdown_risk_score": 30.0, "composite_score": 25.0}]}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_bubble_risk()
        assert result.regime == "low_risk"

    @patch("urllib.request.urlopen")
    def test_fetch_elevated(self, mock_urlopen):
        mock_data = {"history": [{"date": "2026-02-28", "drawdown_risk_score": 58.0, "composite_score": 55.0}]}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_bubble_risk()
        assert result.regime == "elevated"

    @patch("urllib.request.urlopen")
    def test_fetch_moderate(self, mock_urlopen):
        mock_data = {"history": [{"date": "2026-02-28", "drawdown_risk_score": 45.0, "composite_score": 42.0}]}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_bubble_risk()
        assert result.regime == "moderate"

    @patch("urllib.request.urlopen", side_effect=Exception("Network error"))
    @patch("clawdfolio.analysis.bubble.calculate_bubble_risk")
    def test_fetch_fallback_on_error(self, mock_calc, mock_urlopen):
        mock_calc.return_value = BubbleRiskResult(
            drawdown_risk_score=50.0, composite_score=50.0,
            regime="moderate", date="2026-02-28",
        )
        result = fetch_bubble_risk()
        assert result.drawdown_risk_score == 50.0
        mock_calc.assert_called_once()

    @patch("urllib.request.urlopen")
    @patch("clawdfolio.analysis.bubble.calculate_bubble_risk")
    def test_fetch_empty_history_fallback(self, mock_calc, mock_urlopen):
        mock_data = {"history": []}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        mock_calc.return_value = BubbleRiskResult(
            drawdown_risk_score=50.0, composite_score=50.0,
            regime="moderate", date="2026-02-28",
        )
        fetch_bubble_risk()
        mock_calc.assert_called_once()


