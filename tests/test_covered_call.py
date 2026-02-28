"""Tests for the risk-guided covered call strategy."""

from unittest.mock import patch

from clawdfolio.analysis.bubble import BubbleRiskResult
from clawdfolio.strategies.covered_call import (
    CCAction,
    CoveredCallSignal,
    CoveredCallStrategy,
    check_cc_signals,
    get_cc_recommendation,
)


def _make_risk(score: float, regime: str = "moderate") -> BubbleRiskResult:
    """Helper to create a BubbleRiskResult with given score."""
    return BubbleRiskResult(
        drawdown_risk_score=score,
        composite_score=score,
        regime=regime,
        date="2026-02-28",
        components={"sma200_deviation": 10.0, "trend_acceleration": 5.0, "volatility_regime": 5.0},
    )


class TestCCAction:
    def test_enum_values(self):
        assert CCAction.SELL.value == "sell_call"
        assert CCAction.ROLL.value == "roll"
        assert CCAction.HOLD.value == "hold"
        assert CCAction.PAUSE.value == "pause"
        assert CCAction.CLOSE.value == "close"

    def test_str_enum(self):
        assert isinstance(CCAction.SELL, str)
        assert CCAction.SELL == "sell_call"


class TestCoveredCallSignal:
    def test_creation(self):
        sig = CoveredCallSignal(
            ticker="TQQQ",
            action=CCAction.SELL,
            target_delta=0.25,
            target_dte=35,
            reason="Test",
            bubble_risk_score=70.0,
            regime="elevated",
            strength=0.5,
        )
        assert sig.ticker == "TQQQ"
        assert sig.action == CCAction.SELL
        assert sig.target_delta == 0.25
        assert sig.profit_target_pct == 0.50
        assert sig.stop_loss_pct == 2.00
        assert sig.roll_dte == 14

    def test_defaults(self):
        sig = CoveredCallSignal(
            ticker="QQQ", action=CCAction.PAUSE, target_delta=0.20,
            target_dte=35, reason="low risk", bubble_risk_score=30.0,
            regime="low_risk", strength=0.0,
        )
        assert sig.profit_target_pct == 0.50
        assert sig.stop_loss_pct == 2.00
        assert sig.roll_dte == 14


class TestCoveredCallStrategy:
    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_pause_below_threshold(self, mock_fetch):
        mock_fetch.return_value = _make_risk(50.0, "moderate")
        strategy = CoveredCallStrategy(tickers=["TQQQ"])
        signals = strategy.check_signals()
        assert len(signals) == 1
        assert signals[0].action == CCAction.PAUSE
        assert signals[0].strength == 0.0
        assert "below threshold" in signals[0].reason

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_sell_at_threshold(self, mock_fetch):
        mock_fetch.return_value = _make_risk(66.0, "high_risk")
        strategy = CoveredCallStrategy(tickers=["TQQQ"])
        signals = strategy.check_signals()
        assert signals[0].action == CCAction.SELL
        assert signals[0].target_delta == 0.25

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_elevated_delta(self, mock_fetch):
        mock_fetch.return_value = _make_risk(80.0, "high_risk")
        strategy = CoveredCallStrategy(tickers=["TQQQ"])
        signals = strategy.check_signals()
        assert signals[0].action == CCAction.SELL
        assert signals[0].target_delta == 0.30
        assert signals[0].strength > 0

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_multiple_tickers(self, mock_fetch):
        mock_fetch.return_value = _make_risk(70.0, "elevated")
        strategy = CoveredCallStrategy(tickers=["TQQQ", "QQQ", "SPY"])
        signals = strategy.check_signals()
        assert len(signals) == 3
        for sig in signals:
            assert sig.action == CCAction.SELL

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_strength_capped_at_one(self, mock_fetch):
        mock_fetch.return_value = _make_risk(95.0, "high_risk")
        strategy = CoveredCallStrategy(tickers=["TQQQ"])
        signals = strategy.check_signals()
        assert signals[0].strength <= 1.0

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_custom_thresholds(self, mock_fetch):
        mock_fetch.return_value = _make_risk(55.0, "elevated")
        strategy = CoveredCallStrategy(
            tickers=["TQQQ"],
            risk_threshold=50.0,
            elevated_threshold=60.0,
        )
        signals = strategy.check_signals()
        assert signals[0].action == CCAction.SELL
        assert signals[0].target_delta == 0.25

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_format_signals_sell(self, mock_fetch):
        mock_fetch.return_value = _make_risk(70.0, "elevated")
        strategy = CoveredCallStrategy(tickers=["TQQQ"])
        signals = strategy.check_signals()
        output = strategy.format_signals(signals)
        assert "TQQQ" in output
        assert "sell_call" in output
        assert "δ=" in output
        assert "DTE=" in output

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_format_signals_pause(self, mock_fetch):
        mock_fetch.return_value = _make_risk(40.0, "low_risk")
        strategy = CoveredCallStrategy(tickers=["TQQQ"])
        signals = strategy.check_signals()
        output = strategy.format_signals(signals)
        assert "TQQQ" in output
        assert "pause" in output

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_format_signals_fetches_when_none(self, mock_fetch):
        mock_fetch.return_value = _make_risk(70.0, "elevated")
        strategy = CoveredCallStrategy(tickers=["TQQQ"])
        output = strategy.format_signals(None)
        assert "TQQQ" in output
        mock_fetch.assert_called()

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_risk_source_live(self, mock_fetch):
        strategy = CoveredCallStrategy(tickers=["TQQQ"], risk_source="live")
        with patch("clawdfolio.strategies.covered_call.CoveredCallStrategy._get_risk") as mock_get:
            mock_get.return_value = _make_risk(50.0, "moderate")
            signals = strategy.check_signals()
            assert len(signals) == 1


class TestConvenienceFunctions:
    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_check_cc_signals_default(self, mock_fetch):
        mock_fetch.return_value = _make_risk(70.0, "elevated")
        signals = check_cc_signals()
        assert len(signals) == 1
        assert signals[0].ticker == "TQQQ"
        assert signals[0].action == CCAction.SELL

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_check_cc_signals_custom(self, mock_fetch):
        mock_fetch.return_value = _make_risk(30.0, "low_risk")
        signals = check_cc_signals(tickers=["SPY"], risk_threshold=50.0)
        assert signals[0].action == CCAction.PAUSE

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_get_cc_recommendation_sell(self, mock_fetch):
        mock_fetch.return_value = _make_risk(70.0, "elevated")
        rec = get_cc_recommendation("TQQQ")
        assert "SELL CC" in rec
        assert "TQQQ" in rec

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_get_cc_recommendation_hold(self, mock_fetch):
        mock_fetch.return_value = _make_risk(40.0, "low_risk")
        rec = get_cc_recommendation("TQQQ")
        assert "HOLD" in rec

    @patch("clawdfolio.strategies.covered_call.fetch_bubble_risk")
    def test_get_cc_recommendation_no_signals(self, mock_fetch):
        mock_fetch.return_value = _make_risk(40.0, "low_risk")
        strategy = CoveredCallStrategy(tickers=[])
        signals = strategy.check_signals()
        assert len(signals) == 0


class TestBubbleRiskResult:
    def test_should_sell_cc_true(self):
        risk = _make_risk(70.0, "elevated")
        assert risk.should_sell_cc is True

    def test_should_sell_cc_false(self):
        risk = _make_risk(50.0, "moderate")
        assert risk.should_sell_cc is False

    def test_should_sell_cc_boundary(self):
        risk = _make_risk(66.0, "high_risk")
        assert risk.should_sell_cc is True

    def test_cc_delta_high_risk(self):
        risk = _make_risk(80.0, "high_risk")
        assert risk.cc_delta == 0.30

    def test_cc_delta_optimal(self):
        risk = _make_risk(70.0, "elevated")
        assert risk.cc_delta == 0.25

    def test_cc_delta_low(self):
        risk = _make_risk(50.0, "moderate")
        assert risk.cc_delta == 0.20

    def test_components_dict(self):
        risk = _make_risk(60.0, "elevated")
        assert "sma200_deviation" in risk.components
        assert "trend_acceleration" in risk.components
        assert "volatility_regime" in risk.components
