"""Leverage-adjusted stress testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.types import Portfolio


@dataclass
class Scenario:
    """A historical or hypothetical stress scenario."""

    name: str
    moves: dict[str, float]  # benchmark ticker -> return (e.g., -0.34 for -34%)


@dataclass
class StressResult:
    """Result of a single stress scenario on the portfolio."""

    scenario: str
    portfolio_impact: float  # Total portfolio return under the scenario
    position_impacts: list[dict[str, float | str]] = field(default_factory=list)


SCENARIOS = [
    Scenario("COVID Crash (Mar 2020)", {"SPY": -0.34, "QQQ": -0.28}),
    Scenario("Aug 5 2024 Selloff", {"SPY": -0.08, "QQQ": -0.10}),
    Scenario("2022 Bear Market", {"SPY": -0.25, "QQQ": -0.33}),
    Scenario("Flash Crash 2010", {"SPY": -0.07, "QQQ": -0.08}),
    Scenario("Custom -10%", {"SPY": -0.10, "QQQ": -0.10}),
]

# Leveraged ETF multipliers (ticker -> leverage factor)
LEVERAGED_ETFS: dict[str, float] = {
    "TQQQ": 3.0,
    "SQQQ": -3.0,
    "SOXL": 3.0,
    "SOXS": -3.0,
    "UPRO": 3.0,
    "SPXU": -3.0,
    "QLD": 2.0,
    "QID": -2.0,
    "SSO": 2.0,
    "SDS": -2.0,
    "SPXS": -3.0,
    "LABU": 3.0,
    "LABD": -3.0,
    "TNA": 3.0,
    "TZA": -3.0,
    "FAS": 3.0,
    "FAZ": -3.0,
    "TECL": 3.0,
    "TECS": -3.0,
    "FNGU": 3.0,
    "FNGD": -3.0,
    "BULZ": 3.0,
    "BERZ": -3.0,
}

# Map tickers to their underlying benchmark for scenario moves
BENCHMARK_MAP: dict[str, str] = {
    # QQQ-linked
    "QQQ": "QQQ",
    "TQQQ": "QQQ",
    "SQQQ": "QQQ",
    "QLD": "QQQ",
    "QID": "QQQ",
    # SPY-linked
    "SPY": "SPY",
    "UPRO": "SPY",
    "SPXU": "SPY",
    "SSO": "SPY",
    "SDS": "SPY",
    "SPXS": "SPY",
    "VOO": "SPY",
    "IVV": "SPY",
}


def _get_leverage_factor(ticker: str) -> float:
    """Get the leverage factor for a ticker (1.0 for non-leveraged)."""
    return LEVERAGED_ETFS.get(ticker, 1.0)


def _get_benchmark(ticker: str) -> str:
    """Get the benchmark ticker for a given position ticker."""
    return BENCHMARK_MAP.get(ticker, "SPY")


def stress_test_portfolio(
    portfolio: Portfolio,
    scenarios: list[Scenario] | None = None,
) -> list[StressResult]:
    """Run stress test scenarios on the portfolio.

    For each position, the estimated impact is:
        position_weight * leverage_factor * scenario_benchmark_move

    Args:
        portfolio: Portfolio object
        scenarios: List of scenarios to test (defaults to built-in SCENARIOS)

    Returns:
        List of StressResult for each scenario
    """
    if scenarios is None:
        scenarios = SCENARIOS

    if not portfolio.positions:
        return []

    results = []

    for scenario in scenarios:
        total_impact = 0.0
        position_impacts: list[dict[str, float | str]] = []

        for pos in portfolio.positions:
            ticker = pos.symbol.ticker
            weight = pos.weight
            leverage = _get_leverage_factor(ticker)
            benchmark = _get_benchmark(ticker)

            # Use the scenario move for the position's benchmark
            bench_move = scenario.moves.get(benchmark, scenario.moves.get("SPY", -0.10))
            position_impact = weight * leverage * bench_move

            total_impact += position_impact
            position_impacts.append({
                "ticker": ticker,
                "weight": weight,
                "leverage": leverage,
                "benchmark": benchmark,
                "bench_move": bench_move,
                "impact": position_impact,
            })

        results.append(StressResult(
            scenario=scenario.name,
            portfolio_impact=total_impact,
            position_impacts=position_impacts,
        ))

    return results
