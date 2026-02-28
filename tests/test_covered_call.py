"""Tests for the covered call strategy module."""

from __future__ import annotations

from unittest.mock import patch

from clawdfolio.analysis.bubble import BubbleRiskResult
from clawdfolio.strategies.covered_call import (
    CCAction,
    CoveredCallStrategy,
    check_cc_signals,
    get_cc_recommendation,
)


def _make_risk(score: float, regime: str = "moderate") -> BubbleRiskResult:
    """Create a BubbleRiskResult with the given drawdown risk score."""
    return BubbleRiskResult(
        drawdown_risk_score=score,
        composite_score=score,
        regime=regime,
        date="2026-02-28",
    )


class TestCoveredCallStrategy:
    """Tests for CoveredCallStrategy."""

    def test_pause_when_risk_below_threshold(self) -> None:
        risk = _make_risk(50.0, "moderate")
        with patch.object(CoveredCallStrategy, "_get_risk", return_value=risk):
            strategy = CoveredCallStrategy(tickers=["TQQQ"])
            signals = strategy.check_signals()
        assert len(signals) == 1
        assert signals[0].action == CCAction.PAUSE
        assert signals[0].strength == 0.0

    def test_sell_when_risk_at_threshold(self) -> None:
        risk = _make_risk(70.0, "high_risk")
        with patch.object(CoveredCallStrategy, "_get_risk", return_value=risk):
            strategy = CoveredCallStrategy(tickers=["TQQQ"])
            signals = strategy.check_signals()
        assert len(signals) == 1
        assert signals[0].action == CCAction.SELL
        assert signals[0].target_delta == 0.25

    def test_elevated_sell_when_risk_high(self) -> None:
        risk = _make_risk(80.0, "high_risk")
        with patch.object(CoveredCallStrategy, "_get_risk", return_value=risk):
            strategy = CoveredCallStrategy(tickers=["TQQQ"])
            signals = strategy.check_signals()
        assert len(signals) == 1
        assert signals[0].action == CCAction.SELL
        assert signals[0].target_delta == 0.30
        assert "Elevated risk" in signals[0].reason

    def test_multiple_tickers(self) -> None:
        risk = _make_risk(70.0, "high_risk")
        with patch.object(CoveredCallStrategy, "_get_risk", return_value=risk):
            strategy = CoveredCallStrategy(tickers=["TQQQ", "QQQ", "SPY"])
            signals = strategy.check_signals()
        assert len(signals) == 3
        tickers = [s.ticker for s in signals]
        assert tickers == ["TQQQ", "QQQ", "SPY"]

    def test_signal_fields_populated(self) -> None:
        risk = _make_risk(70.0, "high_risk")
        with patch.object(CoveredCallStrategy, "_get_risk", return_value=risk):
            strategy = CoveredCallStrategy(tickers=["TQQQ"])
            signals = strategy.check_signals()
        sig = signals[0]
        assert sig.bubble_risk_score == 70.0
        assert sig.regime == "high_risk"
        assert sig.target_dte == 35
        assert sig.profit_target_pct == 0.50
        assert sig.stop_loss_pct == 2.00
        assert sig.roll_dte == 14

    def test_custom_parameters(self) -> None:
        risk = _make_risk(55.0, "elevated")
        with patch.object(CoveredCallStrategy, "_get_risk", return_value=risk):
            strategy = CoveredCallStrategy(
                tickers=["QQQ"],
                risk_threshold=50.0,
                delta_normal=0.20,
                target_dte=45,
            )
            signals = strategy.check_signals()
        assert signals[0].action == CCAction.SELL
        assert signals[0].target_delta == 0.20
        assert signals[0].target_dte == 45

    def test_strength_capped_at_one(self) -> None:
        risk = _make_risk(100.0, "high_risk")
        with patch.object(CoveredCallStrategy, "_get_risk", return_value=risk):
            strategy = CoveredCallStrategy(tickers=["TQQQ"])
            signals = strategy.check_signals()
        assert signals[0].strength <= 1.0

    def test_with_portfolio_none(self) -> None:
        risk = _make_risk(50.0, "moderate")
        with patch.object(CoveredCallStrategy, "_get_risk", return_value=risk):
            strategy = CoveredCallStrategy(tickers=["TQQQ"])
            signals = strategy.check_signals(portfolio=None)
        assert len(signals) == 1


class TestGetRisk:
    """Tests for _get_risk method with different risk sources."""

    def test_api_source(self) -> None:
        risk = _make_risk(60.0)
        with patch("clawdfolio.strategies.covered_call.fetch_bubble_risk", return_value=risk):
            strategy = CoveredCallStrategy(risk_source="api")
            result = strategy._get_risk()
        assert result.drawdown_risk_score == 60.0

    def test_live_source(self) -> None:
        risk = _make_risk(55.0)
        with patch(
            "clawdfolio.strategies.covered_call.CoveredCallStrategy._get_risk",
            return_value=risk,
        ):
            strategy = CoveredCallStrategy(risk_source="live")
            result = strategy._get_risk()
        assert result.drawdown_risk_score == 55.0


class TestFormatSignals:
    """Tests for format_signals method."""

    def test_format_sell_signal(self) -> None:
        risk = _make_risk(70.0, "high_risk")
        with patch.object(CoveredCallStrategy, "_get_risk", return_value=risk):
            strategy = CoveredCallStrategy(tickers=["TQQQ"])
            signals = strategy.check_signals()
            output = strategy.format_signals(signals)
        assert "TQQQ" in output
        assert "Covered Call Signal Dashboard" in output
        assert "Target:" in output

    def test_format_pause_signal(self) -> None:
        risk = _make_risk(40.0, "low_risk")
        with patch.object(CoveredCallStrategy, "_get_risk", return_value=risk):
            strategy = CoveredCallStrategy(tickers=["TQQQ"])
            signals = strategy.check_signals()
            output = strategy.format_signals(signals)
        assert "TQQQ" in output
        assert "Target:" not in output

    def test_format_auto_fetches_signals(self) -> None:
        risk = _make_risk(50.0, "moderate")
        with patch.object(CoveredCallStrategy, "_get_risk", return_value=risk):
            strategy = CoveredCallStrategy(tickers=["TQQQ"])
            output = strategy.format_signals(None)
        assert "TQQQ" in output


class TestConvenienceFunctions:
    """Tests for check_cc_signals and get_cc_recommendation."""

    def test_check_cc_signals_default(self) -> None:
        risk = _make_risk(70.0, "high_risk")
        with patch("clawdfolio.strategies.covered_call.fetch_bubble_risk", return_value=risk):
            signals = check_cc_signals()
        assert len(signals) == 1
        assert signals[0].ticker == "TQQQ"

    def test_check_cc_signals_custom_tickers(self) -> None:
        risk = _make_risk(50.0, "moderate")
        with patch("clawdfolio.strategies.covered_call.fetch_bubble_risk", return_value=risk):
            signals = check_cc_signals(tickers=["QQQ", "SPY"])
        assert len(signals) == 2

    def test_get_cc_recommendation_sell(self) -> None:
        risk = _make_risk(70.0, "high_risk")
        with patch("clawdfolio.strategies.covered_call.fetch_bubble_risk", return_value=risk):
            rec = get_cc_recommendation("TQQQ")
        assert "SELL CC" in rec
        assert "TQQQ" in rec

    def test_get_cc_recommendation_hold(self) -> None:
        risk = _make_risk(40.0, "low_risk")
        with patch("clawdfolio.strategies.covered_call.fetch_bubble_risk", return_value=risk):
            rec = get_cc_recommendation("TQQQ")
        assert "HOLD" in rec
        assert "TQQQ" in rec
