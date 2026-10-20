"""
Pure mathematical functions for instantaneous asset price shocks and contribution attribution.
"""

from __future__ import annotations

import math
from app.scenarios.models import AssetShockContribution, ScenarioSummaryMetrics


def apply_instantaneous_shocks(
    weights: dict[str, float],
    shocks: dict[str, float],
    initial_capital: float,
    currency: str = "USD",
) -> tuple[ScenarioSummaryMetrics, list[AssetShockContribution]]:
    """
    Applies instantaneous price shocks to portfolio asset holdings.

    Formula:
        V_pre = sum(w_i * initial_capital) + Cash
        V_i_after = V_i_pre * (1 + s_i)
        V_after = sum(V_i_after) + Cash
        Delta_V = V_after - V_pre = sum(V_i_pre * s_i)

    Parameters:
        weights: Dictionary mapping asset ID -> portfolio weight (sum <= 1.0).
        shocks: Dictionary mapping asset ID -> fractional price shock (e.g. -0.10 for -10%).
        initial_capital: Total initial portfolio value.
        currency: Base valuation currency.

    Returns:
        tuple of (ScenarioSummaryMetrics, list of AssetShockContribution).
    """
    if initial_capital <= 0:
        raise ValueError(f"Initial capital must be strictly positive, got {initial_capital}")

    total_weight = sum(weights.values())
    if total_weight > 1.000001:
        raise ValueError(f"Total weights ({total_weight:.6f}) exceed 1.0")

    cash_weight = max(0.0, 1.0 - total_weight)
    cash_value = cash_weight * initial_capital

    baseline_portfolio_value = initial_capital
    contributions: list[AssetShockContribution] = []

    total_dollar_change = 0.0

    # 1. Compute individual asset changes
    for asset_id, w in weights.items():
        if not math.isfinite(w):
            raise ValueError(f"Non-finite weight encountered for asset '{asset_id}': {w}")

        s = shocks.get(asset_id, 0.0)
        if not math.isfinite(s):
            raise ValueError(f"Non-finite shock encountered for asset '{asset_id}': {s}")
        if s < -1.0:
            raise ValueError(
                f"Asset '{asset_id}' shock ({s:.4f}) cannot be less than -1.0 (-100% loss) for long holdings."
            )

        base_val = w * initial_capital
        stressed_val = base_val * (1.0 + s)
        val_change = stressed_val - base_val
        ret_contrib = w * s

        total_dollar_change += val_change

        ticker = asset_id.split(":")[0] if ":" in asset_id else asset_id

        contributions.append(
            AssetShockContribution(
                asset_id=asset_id,
                ticker=ticker,
                baseline_weight=round(w, 6),
                baseline_value=round(base_val, 2),
                shock_pct=round(s * 100.0, 4),
                stressed_value=round(stressed_val, 2),
                value_change=round(val_change, 2),
                return_contribution=round(ret_contrib, 6),
                share_of_total_change=0.0,  # Will normalize below
            )
        )

    stressed_portfolio_value = baseline_portfolio_value + total_dollar_change
    pct_change = total_dollar_change / baseline_portfolio_value if baseline_portfolio_value > 0 else 0.0

    # 2. Compute share of total change
    n = len(contributions)
    for c in contributions:
        if abs(total_dollar_change) > 1e-9:
            share = c.value_change / total_dollar_change
        else:
            share = 1.0 / n if n > 0 else 0.0
        c.share_of_total_change = round(share, 6)

    metrics = ScenarioSummaryMetrics(
        baseline_portfolio_value=round(baseline_portfolio_value, 2),
        stressed_portfolio_value=round(stressed_portfolio_value, 2),
        absolute_change=round(total_dollar_change, 2),
        percentage_change=round(pct_change, 6),
        currency=currency,
        cash_value=round(cash_value, 2),
    )

    return metrics, contributions
