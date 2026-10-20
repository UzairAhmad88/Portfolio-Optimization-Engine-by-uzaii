"""
Regime-Switching Asset Allocation, Hidden Markov Models (HMM) & Dynamic Volatility Targeting module.
"""

from app.regime_switching.models import (
    RegimeDetectionRequest,
    RegimeDetectionResponse,
    RegimeBacktestRequest,
    RegimeBacktestResponse,
)
from app.regime_switching.service import (
    execute_regime_detection,
    execute_regime_backtest,
)

__all__ = [
    "RegimeDetectionRequest",
    "RegimeDetectionResponse",
    "RegimeBacktestRequest",
    "RegimeBacktestResponse",
    "execute_regime_detection",
    "execute_regime_backtest",
]
