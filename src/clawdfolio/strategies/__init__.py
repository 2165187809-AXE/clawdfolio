"""Investment strategies."""

from .covered_call import (
    CCAction,
    CoveredCallSignal,
    CoveredCallStrategy,
    check_cc_signals,
    get_cc_recommendation,
)
from .dca import DCASignal, DCAStrategy, check_dca_signals

__all__ = [
    # Covered Call
    "CCAction",
    "CoveredCallSignal",
    "CoveredCallStrategy",
    "check_cc_signals",
    "get_cc_recommendation",
    # DCA
    "DCAStrategy",
    "DCASignal",
    "check_dca_signals",
]
