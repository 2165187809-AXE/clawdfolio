"""Portfolio concentration analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..market.data import get_sector

if TYPE_CHECKING:
    from ..core.types import Portfolio


@dataclass
class ConcentrationMetrics:
    """Concentration analysis results."""
    hhi: float  # Herfindahl-Hirschman Index
    top_5_weight: float
    top_10_weight: float
    max_position_weight: float
    max_position_ticker: str
    is_concentrated: bool  # True if HHI > 0.25 or single position > 25%


@dataclass
class SectorExposure:
    """Sector exposure breakdown."""
    sector: str
    weight: float
    tickers: list[str] = field(default_factory=list)


def calculate_hhi(weights: list[float]) -> float:
    """Calculate Herfindahl-Hirschman Index.

    The HHI is a measure of concentration:
    - 0 to 0.15: Low concentration
    - 0.15 to 0.25: Moderate concentration
    - 0.25 to 1.0: High concentration

    Args:
        weights: List of position weights (should sum to ~1)

    Returns:
        HHI value between 0 and 1
    """
    if not weights:
        return 0.0

    return sum(w ** 2 for w in weights)


def calculate_concentration(portfolio: Portfolio) -> ConcentrationMetrics:
    """Calculate portfolio concentration metrics.

    Args:
        portfolio: Portfolio object

    Returns:
        ConcentrationMetrics with all concentration measures
    """
    if not portfolio.positions:
        return ConcentrationMetrics(
            hhi=0.0,
            top_5_weight=0.0,
            top_10_weight=0.0,
            max_position_weight=0.0,
            max_position_ticker="",
            is_concentrated=False,
        )

    # Sort by weight
    sorted_positions = portfolio.sorted_by_weight
    weights = [p.weight for p in sorted_positions]

    # HHI
    hhi = calculate_hhi(weights)

    # Top N weights
    top_5_weight = sum(weights[:5])
    top_10_weight = sum(weights[:10])

    # Max position
    max_pos = sorted_positions[0]
    max_weight = max_pos.weight
    max_ticker = max_pos.symbol.ticker

    # Is concentrated?
    is_concentrated = hhi > 0.25 or max_weight > 0.25

    return ConcentrationMetrics(
        hhi=hhi,
        top_5_weight=top_5_weight,
        top_10_weight=top_10_weight,
        max_position_weight=max_weight,
        max_position_ticker=max_ticker,
        is_concentrated=is_concentrated,
    )


def get_sector_exposure(portfolio: Portfolio) -> list[SectorExposure]:
    """Calculate sector exposure breakdown.

    Args:
        portfolio: Portfolio object

    Returns:
        List of SectorExposure sorted by weight (descending)
    """
    if not portfolio.positions:
        return []

    sector_map: dict[str, SectorExposure] = {}

    for pos in portfolio.positions:
        ticker = pos.symbol.ticker
        sector = get_sector(ticker) or "Unknown"

        if sector not in sector_map:
            sector_map[sector] = SectorExposure(sector=sector, weight=0.0, tickers=[])

        sector_map[sector].weight += pos.weight
        sector_map[sector].tickers.append(ticker)

    # Sort by weight
    exposures = sorted(sector_map.values(), key=lambda x: x.weight, reverse=True)

    return exposures


def analyze_concentration(
    portfolio: Portfolio,
    concentration_threshold: float = 0.25,
    sector_threshold: float = 0.40,
) -> dict:
    """Full concentration analysis with alerts.

    Args:
        portfolio: Portfolio object
        concentration_threshold: Single position concentration threshold
        sector_threshold: Single sector concentration threshold

    Returns:
        Dictionary with concentration metrics and alerts
    """
    metrics = calculate_concentration(portfolio)
    sectors = get_sector_exposure(portfolio)

    alerts = []

    # Single position concentration
    if metrics.max_position_weight > concentration_threshold:
        alerts.append({
            "type": "position_concentration",
            "ticker": metrics.max_position_ticker,
            "weight": metrics.max_position_weight,
            "threshold": concentration_threshold,
            "message": f"{metrics.max_position_ticker} accounts for {metrics.max_position_weight:.1%} of portfolio",
        })

    # High HHI
    if metrics.hhi > 0.25:
        alerts.append({
            "type": "high_hhi",
            "value": metrics.hhi,
            "message": f"Portfolio HHI of {metrics.hhi:.3f} indicates high concentration",
        })

    # Sector concentration
    for sector in sectors:
        if sector.weight > sector_threshold:
            alerts.append({
                "type": "sector_concentration",
                "sector": sector.sector,
                "weight": sector.weight,
                "tickers": sector.tickers,
                "threshold": sector_threshold,
                "message": f"{sector.sector} sector accounts for {sector.weight:.1%} of portfolio",
            })

    # Top 5 concentration
    if metrics.top_5_weight > 0.80:
        alerts.append({
            "type": "top_5_concentration",
            "weight": metrics.top_5_weight,
            "message": f"Top 5 holdings account for {metrics.top_5_weight:.1%} of portfolio",
        })

    return {
        "metrics": metrics,
        "sectors": sectors,
        "alerts": alerts,
        "is_concentrated": len(alerts) > 0,
        "diversification_score": diversification_score(portfolio),
    }


def diversification_score(portfolio: Portfolio) -> float:
    """Calculate a diversification score (0-100).

    Higher score = better diversified.

    Args:
        portfolio: Portfolio object

    Returns:
        Diversification score
    """
    if not portfolio.positions or len(portfolio.positions) < 2:
        return 0.0

    metrics = calculate_concentration(portfolio)
    sectors = get_sector_exposure(portfolio)

    # Base score from HHI (inverted)
    hhi_score = (1 - metrics.hhi) * 40  # Max 40 points

    # Position count score
    n_positions = len(portfolio.positions)
    position_score = min(n_positions / 20, 1.0) * 20  # Max 20 points for 20+ positions

    # Sector diversity score
    n_sectors = len([s for s in sectors if s.weight > 0.01])
    sector_score = min(n_sectors / 8, 1.0) * 20  # Max 20 points for 8+ sectors

    # Max position penalty
    max_pos_score = (1 - metrics.max_position_weight) * 20  # Max 20 points

    total = hhi_score + position_score + sector_score + max_pos_score

    return min(max(total, 0), 100)
