"""
Quantitative analytics and statistical validation module.
"""

from app.analytics.overfitting import (
    calculate_deflated_sharpe_ratio,
    calculate_expected_maximum_sharpe,
    calculate_minimum_backtest_length,
    compute_overfitting_diagnostics,
    run_combinatorial_cross_validation,
)

__all__ = [
    "calculate_expected_maximum_sharpe",
    "calculate_deflated_sharpe_ratio",
    "calculate_minimum_backtest_length",
    "run_combinatorial_cross_validation",
    "compute_overfitting_diagnostics",
]
