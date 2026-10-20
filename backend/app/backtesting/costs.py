"""
Pure mathematical functions for calculating portfolio turnover, traded notional,
transaction costs, and execution slippage.
"""

from __future__ import annotations


def calculate_turnover(
    pre_weights: dict[str, float],
    target_weights: dict[str, float],
) -> float:
    """
    Computes two-sided portfolio turnover:
        tau = 0.5 * sum_i |w_{target, i} - w_{pre, i}|

    Parameters:
        pre_weights: Normalized dictionary of current portfolio weights before rebalance.
        target_weights: Normalized dictionary of target portfolio weights.

    Returns:
        Turnover fraction bounded between 0.0 (no trade) and 1.0 (complete liquidation/reallocation).
    """
    all_assets = set(pre_weights.keys()).union(set(target_weights.keys()))
    abs_diff_sum = sum(
        abs(target_weights.get(a, 0.0) - pre_weights.get(a, 0.0))
        for a in all_assets
    )
    return float(0.5 * abs_diff_sum)


def calculate_traded_notional(
    pre_weights: dict[str, float],
    target_weights: dict[str, float],
    portfolio_value: float,
) -> float:
    """
    Calculates total two-sided traded gross notional across all buy and sell orders:
        Traded Notional = V * sum_i |w_{target, i} - w_{pre, i}| = 2.0 * tau * V

    Parameters:
        pre_weights: Current portfolio weights before rebalancing.
        target_weights: Desired portfolio weights after rebalancing.
        portfolio_value: Total pre-rebalance portfolio equity.

    Returns:
        Absolute currency amount traded across all buying and selling legs.
    """
    if portfolio_value <= 0.0:
        return 0.0

    all_assets = set(pre_weights.keys()).union(set(target_weights.keys()))
    diff_sum = sum(
        abs(target_weights.get(a, 0.0) - pre_weights.get(a, 0.0))
        for a in all_assets
    )
    return float(diff_sum * portfolio_value)


def calculate_transaction_cost(
    traded_notional: float,
    fee_bps: float,
) -> float:
    """
    Computes broker/exchange transaction fee based on basis-point rate:
        Cost = Traded Notional * (fee_bps / 10,000)

    Parameters:
        traded_notional: Total currency value of all buy and sell transactions.
        fee_bps: Proportional fee rate in basis points (10.0 bps = 0.0010 = 0.1%).

    Returns:
        Currency fee amount deducted from portfolio cash/equity.
    """
    if traded_notional <= 0.0 or fee_bps <= 0.0:
        return 0.0
    return float(traded_notional * (fee_bps / 10_000.0))


def calculate_slippage_cost(
    traded_notional: float,
    slippage_bps: float,
) -> float:
    """
    Computes execution price slippage drag based on basis-point rate:
        Slippage = Traded Notional * (slippage_bps / 10,000)

    Parameters:
        traded_notional: Total currency value of all buy and sell transactions.
        slippage_bps: Slippage rate in basis points (5.0 bps = 0.0005 = 0.05%).

    Returns:
        Currency slippage cost deducted from portfolio equity.
    """
    if traded_notional <= 0.0 or slippage_bps <= 0.0:
        return 0.0
    return float(traded_notional * (slippage_bps / 10_000.0))
