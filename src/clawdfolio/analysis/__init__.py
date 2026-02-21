"""Portfolio analysis and risk metrics."""

from .bubble import (
    BubbleIndexResult,
    BubbleRiskResult,
    IndicatorResult,
    calculate_bubble_index,
    calculate_bubble_risk,
    fetch_bubble_risk,
)
from .concentration import (
    analyze_concentration,
    calculate_concentration,
    calculate_hhi,
    effective_n,
    get_sector_exposure,
)
from .factors import FactorExposure, analyze_factor_exposure, download_ff_factors
from .risk import (
    analyze_risk,
    calculate_beta,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_var,
    calculate_volatility,
)
from .stress import SCENARIOS, StressResult, stress_test_portfolio
from .technical import (
    calculate_bollinger_bands,
    calculate_ema,
    calculate_rsi,
    calculate_sma,
    detect_rsi_extremes,
)
from .volatility import compare_vol_estimates, forecast_volatility

__all__ = [
    # Bubble risk
    "BubbleRiskResult",
    "calculate_bubble_risk",
    "fetch_bubble_risk",
    # Risk
    "calculate_volatility",
    "calculate_beta",
    "calculate_sharpe_ratio",
    "calculate_var",
    "calculate_max_drawdown",
    "analyze_risk",
    # Technical
    "calculate_rsi",
    "calculate_sma",
    "calculate_ema",
    "calculate_bollinger_bands",
    "detect_rsi_extremes",
    # Concentration
    "calculate_hhi",
    "calculate_concentration",
    "get_sector_exposure",
    "analyze_concentration",
    "effective_n",
    # Volatility
    "forecast_volatility",
    "compare_vol_estimates",
    # Factors
    "FactorExposure",
    "analyze_factor_exposure",
    "download_ff_factors",
    # Stress
    "SCENARIOS",
    "StressResult",
    "stress_test_portfolio",
    # Bubble
    "BubbleIndexResult",
    "IndicatorResult",
    "calculate_bubble_index",
]
