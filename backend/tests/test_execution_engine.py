"""
Unit tests and analytical mathematical benchmarks for Stage 19:
Almgren-Chriss Optimal Execution & Market Impact Modeling Engine.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from app.quant.execution import (
    compute_almgren_chriss_trajectory,
    compute_rebalance_market_impact,
)


def test_almgren_chriss_hand_calculated_analytical_benchmark():
    """
    Verifies the closed-form 2-period Almgren-Chriss benchmark specified in docs/SESSION_23_CONTRACTS.md:
    - X_0 = 1,000,000 shares
    - S_0 = $50.00
    - N = 2 periods, tau = 0.5 days
    - sigma = $1.00/share-day (sigma^2 = 1.0)
    - eta = 2.5e-6
    - gamma = 0.0
    - spread = $0.00
    - lambda = 5.0e-6

    Analytical Solution:
    - cosh(kappa * tau) = 1 + 0.5 * (5e-6 * 1.0 * 0.25) / 2.5e-6 = 1.25
    - kappa * tau = arccosh(1.25) = ln(2.0)
    - x_1^* = X_0 / (2 * cosh(kappa * tau)) = 1,000,000 / 2.5 = 400,000 shares
    - n_1^* = 600,000 shares, n_2^* = 400,000 shares
    - Expected Cost E[I] = $2,600,000
    - Timing Variance V[I] = 8.0e10
    - Utility U^* = $3,000,000
    - TWAP Utility U_TWAP = $3,125,000
    - Cost savings = $125,000
    """
    res = compute_almgren_chriss_trajectory(
        order_size=1_000_000.0,
        asset_price=50.0,
        daily_volume=10_000_000.0,
        daily_volatility=1.0,
        bid_ask_spread=0.0,
        horizon_periods=2,
        trading_hours=6.5,
        risk_aversion=5.0e-6,
        temporary_impact_factor=2.5e-6,
        permanent_impact_factor=0.0,
    )

    schedule = res["schedule"]
    summary = res["summary"]

    # Verify period 1 trade and remaining
    np.testing.assert_allclose(schedule[0]["almgren_chriss_shares"], 600_000.0, atol=1e-6)
    np.testing.assert_allclose(schedule[0]["almgren_chriss_remaining"], 400_000.0, atol=1e-6)

    # Verify period 2 trade and remaining
    np.testing.assert_allclose(schedule[1]["almgren_chriss_shares"], 400_000.0, atol=1e-6)
    np.testing.assert_allclose(schedule[1]["almgren_chriss_remaining"], 0.0, atol=1e-6)

    # Verify TWAP baseline
    np.testing.assert_allclose(schedule[0]["twap_shares"], 500_000.0, atol=1e-6)
    np.testing.assert_allclose(schedule[1]["twap_shares"], 500_000.0, atol=1e-6)

    # Verify costs, variance, and utilities
    np.testing.assert_allclose(summary["expected_cost"], 2_600_000.0, atol=1e-2)
    np.testing.assert_allclose(summary["timing_risk_variance"], 8.0e10, atol=1e-2)
    np.testing.assert_allclose(summary["execution_utility"], 3_000_000.0, atol=1e-2)

    np.testing.assert_allclose(summary["twap_expected_cost"], 2_500_000.0, atol=1e-2)
    np.testing.assert_allclose(summary["twap_utility"], 3_125_000.0, atol=1e-2)
    np.testing.assert_allclose(summary["cost_savings_vs_twap"], 125_000.0, atol=1e-2)


def test_almgren_chriss_risk_neutral_twap_convergence():
    """
    Verifies that when risk aversion lambda = 0 (risk-neutral), the Almgren-Chriss
    optimal trajectory converges identically to the linear TWAP schedule.
    """
    res = compute_almgren_chriss_trajectory(
        order_size=500_000.0,
        asset_price=100.0,
        daily_volume=5_000_000.0,
        daily_volatility=2.0,
        horizon_periods=10,
        risk_aversion=0.0,  # Risk-neutral
    )

    schedule = res["schedule"]
    expected_shares_per_period = 500_000.0 / 10

    for pt in schedule:
        np.testing.assert_allclose(pt["almgren_chriss_shares"], expected_shares_per_period, atol=1e-6)
        np.testing.assert_allclose(pt["almgren_chriss_shares"], pt["twap_shares"], atol=1e-6)

    # Cost savings vs TWAP must be zero
    assert abs(res["summary"]["cost_savings_vs_twap"]) < 1e-4


def test_almgren_chriss_convexity_and_risk_aversion_monotonicity():
    """
    Verifies that increasing risk aversion lambda accelerates execution:
    higher lambda -> larger initial trade n_1 -> strictly lower remaining shares x_1.
    """
    lambdas = [1e-8, 1e-6, 1e-4]
    n1_trades = []
    x1_remaining = []

    for lam in lambdas:
        res = compute_almgren_chriss_trajectory(
            order_size=100_000.0,
            asset_price=50.0,
            daily_volume=2_000_000.0,
            daily_volatility=1.5,
            horizon_periods=5,
            risk_aversion=lam,
        )
        n1_trades.append(res["schedule"][0]["almgren_chriss_shares"])
        x1_remaining.append(res["schedule"][0]["almgren_chriss_remaining"])

    # Monotonicity checks
    assert n1_trades[0] < n1_trades[1] < n1_trades[2]
    assert x1_remaining[0] > x1_remaining[1] > x1_remaining[2]


def test_almgren_chriss_vwap_profile_tracking():
    """
    Verifies that the VWAP schedule accurately reflects the specified intraday volume weights.
    """
    custom_profile = [0.25, 0.15, 0.10, 0.20, 0.30]  # Sum = 1.0
    res = compute_almgren_chriss_trajectory(
        order_size=200_000.0,
        asset_price=40.0,
        daily_volume=1_000_000.0,
        daily_volatility=1.0,
        horizon_periods=5,
        volume_profile=custom_profile,
    )

    schedule = res["schedule"]
    for i, w in enumerate(custom_profile):
        expected_shares = 200_000.0 * w
        np.testing.assert_allclose(schedule[i]["vwap_shares"], expected_shares, atol=1e-6)


def test_rebalance_market_impact_square_root_law_scaling():
    """
    Verifies non-linear cost scaling under the Square-Root Law of market impact:
    Trading $10M of an asset with $5M ADV incurs a vastly higher basis-point cost
    than trading $100k of the same asset.
    """
    small_trade = {"AAPL": 100_000.0}
    large_trade = {"AAPL": 10_000_000.0}
    adv_dict = {"AAPL": 5_000_000.0}
    vol_dict = {"AAPL": 0.25}

    res_small = compute_rebalance_market_impact(
        traded_notionals=small_trade,
        adv_dict=adv_dict,
        volatility_dict=vol_dict,
        spread_bps_dict={"AAPL": 2.0},
        impact_model="square_root",
    )

    res_large = compute_rebalance_market_impact(
        traded_notionals=large_trade,
        adv_dict=adv_dict,
        volatility_dict=vol_dict,
        spread_bps_dict={"AAPL": 2.0},
        impact_model="square_root",
    )

    bps_small = res_small["summary"]["effective_cost_bps"]
    bps_large = res_large["summary"]["effective_cost_bps"]

    # Non-linear scaling: large trade BPS must be significantly higher than small trade BPS
    assert bps_large > bps_small * 3.0
    assert res_large["asset_impacts"][0]["participation_rate_pct"] == 200.0  # 10M / 5M * 100


def test_execution_input_validation_boundaries():
    """Verifies that non-positive inputs and invalid horizons raise ValueError."""
    with pytest.raises(ValueError, match="Order size"):
        compute_almgren_chriss_trajectory(
            order_size=-100.0,
            asset_price=50.0,
            daily_volume=1_000_000.0,
            daily_volatility=1.0,
        )

    with pytest.raises(ValueError, match="Horizon periods"):
        compute_almgren_chriss_trajectory(
            order_size=100.0,
            asset_price=50.0,
            daily_volume=1_000_000.0,
            daily_volatility=1.0,
            horizon_periods=1,
        )
