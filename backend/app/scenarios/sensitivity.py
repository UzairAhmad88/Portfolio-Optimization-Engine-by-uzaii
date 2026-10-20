"""
Pure mathematical functions for 1-factor and 2-factor parametric sensitivity sweeps.
"""

from __future__ import annotations

import math
import numpy as np
from app.scenarios.models import SensitivityGridPoint


def generate_grid_values(min_val: float, max_val: float, steps: int) -> list[float]:
    """
    Generates linearly spaced values for a sensitivity factor.
    """
    if steps < 2:
        raise ValueError(f"Steps must be at least 2, got {steps}")
    if min_val >= max_val:
        raise ValueError(f"min_val ({min_val}) must be strictly less than max_val ({max_val})")
    
    vals = np.linspace(min_val, max_val, steps)
    return [round(float(v), 6) for v in vals]


def evaluate_sensitivity_grid(
    weights: dict[str, float],
    initial_capital: float,
    factor_1_asset: str,
    factor_1_shocks: list[float],
    factor_2_asset: str | None = None,
    factor_2_shocks: list[float] | None = None,
) -> list[SensitivityGridPoint]:
    """
    Evaluates portfolio valuation and percentage changes across a 1D or 2D grid of asset shocks.

    Parameters:
        weights: Dictionary mapping asset ID -> weight.
        initial_capital: Total portfolio base value.
        factor_1_asset: Asset identifier for factor 1.
        factor_1_shocks: List of shocks to evaluate for factor 1.
        factor_2_asset: Optional asset identifier for factor 2.
        factor_2_shocks: Optional list of shocks to evaluate for factor 2.

    Returns:
        list of SensitivityGridPoint.
    """
    w1 = weights.get(factor_1_asset, 0.0)
    w2 = weights.get(factor_2_asset, 0.0) if factor_2_asset else 0.0

    points: list[SensitivityGridPoint] = []

    if factor_2_asset and factor_2_shocks:
        # 2D Grid Sweep
        for s1 in factor_1_shocks:
            for s2 in factor_2_shocks:
                dollar_change = (w1 * s1 + w2 * s2) * initial_capital
                stressed_val = initial_capital + dollar_change
                pct_change = dollar_change / initial_capital if initial_capital > 0 else 0.0

                points.append(
                    SensitivityGridPoint(
                        factor_1_value=round(s1, 6),
                        factor_2_value=round(s2, 6),
                        stressed_portfolio_value=round(stressed_val, 2),
                        percentage_change=round(pct_change, 6),
                        absolute_change=round(dollar_change, 2),
                    )
                )
    else:
        # 1D Curve Sweep
        for s1 in factor_1_shocks:
            dollar_change = (w1 * s1) * initial_capital
            stressed_val = initial_capital + dollar_change
            pct_change = dollar_change / initial_capital if initial_capital > 0 else 0.0

            points.append(
                SensitivityGridPoint(
                    factor_1_value=round(s1, 6),
                    factor_2_value=None,
                    stressed_portfolio_value=round(stressed_val, 2),
                    percentage_change=round(pct_change, 6),
                    absolute_change=round(dollar_change, 2),
                )
            )

    return points
