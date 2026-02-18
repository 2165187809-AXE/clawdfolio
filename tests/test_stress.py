"""Tests for stress testing module."""

from __future__ import annotations

from decimal import Decimal

from clawdfolio.analysis.stress import (
    LEVERAGED_ETFS,
    SCENARIOS,
    Scenario,
    StressResult,
    stress_test_portfolio,
)
from clawdfolio.core.types import Portfolio, Position, Symbol


def _make_portfolio() -> Portfolio:
    """Create a mock portfolio for testing."""
    positions = [
        Position(
            symbol=Symbol("SPY"),
            quantity=Decimal("100"),
            market_value=Decimal("50000"),
        ),
        Position(
            symbol=Symbol("QQQ"),
            quantity=Decimal("50"),
            market_value=Decimal("25000"),
        ),
        Position(
            symbol=Symbol("TQQQ"),
            quantity=Decimal("200"),
            market_value=Decimal("25000"),
        ),
    ]
    portfolio = Portfolio(
        positions=positions,
        net_assets=Decimal("100000"),
        market_value=Decimal("100000"),
    )
    return portfolio


class TestStressTestPortfolio:
    def test_returns_results_for_all_scenarios(self) -> None:
        portfolio = _make_portfolio()
        results = stress_test_portfolio(portfolio)
        assert len(results) == len(SCENARIOS)

    def test_result_is_stress_result(self) -> None:
        portfolio = _make_portfolio()
        results = stress_test_portfolio(portfolio)
        for r in results:
            assert isinstance(r, StressResult)
            assert isinstance(r.portfolio_impact, float)

    def test_leveraged_etf_amplified(self) -> None:
        portfolio = _make_portfolio()
        results = stress_test_portfolio(portfolio)

        covid = next(r for r in results if "COVID" in r.scenario)
        tqqq_impact = next(
            pi for pi in covid.position_impacts if pi["ticker"] == "TQQQ"
        )
        qqq_impact = next(
            pi for pi in covid.position_impacts if pi["ticker"] == "QQQ"
        )
        assert abs(float(tqqq_impact["impact"])) > abs(float(qqq_impact["impact"]))

    def test_empty_portfolio(self) -> None:
        portfolio = Portfolio()
        results = stress_test_portfolio(portfolio)
        assert results == []

    def test_custom_scenarios(self) -> None:
        portfolio = _make_portfolio()
        custom = [Scenario("Test -50%", {"SPY": -0.50, "QQQ": -0.50})]
        results = stress_test_portfolio(portfolio, scenarios=custom)
        assert len(results) == 1
        assert results[0].scenario == "Test -50%"
        assert results[0].portfolio_impact < -0.30

    def test_position_impacts_sum_to_total(self) -> None:
        portfolio = _make_portfolio()
        results = stress_test_portfolio(portfolio)
        for r in results:
            summed = sum(float(pi["impact"]) for pi in r.position_impacts)
            assert abs(summed - r.portfolio_impact) < 1e-10


class TestLeveragedEtfs:
    def test_known_leveraged_etfs(self) -> None:
        assert LEVERAGED_ETFS["TQQQ"] == 3.0
        assert LEVERAGED_ETFS["SQQQ"] == -3.0
        assert LEVERAGED_ETFS["SOXL"] == 3.0

    def test_non_leveraged_not_in_map(self) -> None:
        assert "AAPL" not in LEVERAGED_ETFS
        assert "SPY" not in LEVERAGED_ETFS
