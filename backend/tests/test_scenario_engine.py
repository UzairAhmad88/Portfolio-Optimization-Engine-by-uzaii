"""
Unit tests for Scenario Analysis, Stress Testing & Sensitivity Analysis pure mathematics.
Validates zero shocks, positive/negative asset shocks, cash preservation, contribution attribution,
covariance stress PSD checks, and sensitivity sweeps against analytical benchmarks.
"""

import math
import numpy as np
import pandas as pd
import pytest

from app.scenarios.sensitivity import evaluate_sensitivity_grid, generate_grid_values
from app.scenarios.shocks import apply_instantaneous_shocks
from app.scenarios.stress import extract_historical_window_shocks, stress_covariance_matrix


def test_zero_shocks_produce_zero_portfolio_change():
    """Applying 0.0% shock to all assets results in zero dollar and percentage change."""
    weights = {"AAPL:US": 0.60, "MSFT:US": 0.40}
    shocks = {"AAPL:US": 0.0, "MSFT:US": 0.0}
    initial_capital = 100000.0

    metrics, contributions = apply_instantaneous_shocks(weights, shocks, initial_capital)

    assert math.isclose(metrics.baseline_portfolio_value, 100000.0, abs_tol=1e-5)
    assert math.isclose(metrics.stressed_portfolio_value, 100000.0, abs_tol=1e-5)
    assert math.isclose(metrics.absolute_change, 0.0, abs_tol=1e-5)
    assert math.isclose(metrics.percentage_change, 0.0, abs_tol=1e-7)

    for c in contributions:
        assert math.isclose(c.value_change, 0.0, abs_tol=1e-5)
        assert math.isclose(c.return_contribution, 0.0, abs_tol=1e-7)


def test_custom_positive_and_negative_shocks_analytical_reconciliation():
    """
    Asset A: $60,000 with -10% shock -> $54,000 (-$6,000)
    Asset B: $40,000 with +20% shock -> $48,000 (+$8,000)
    Total Portfolio: $102,000 (+$2,000, +2.0%)
    """
    weights = {"A:US": 0.60, "B:US": 0.40}
    shocks = {"A:US": -0.10, "B:US": 0.20}
    initial_capital = 100000.0

    metrics, contributions = apply_instantaneous_shocks(weights, shocks, initial_capital)

    assert math.isclose(metrics.baseline_portfolio_value, 100000.0, abs_tol=1e-5)
    assert math.isclose(metrics.stressed_portfolio_value, 102000.0, abs_tol=1e-5)
    assert math.isclose(metrics.absolute_change, 2000.0, abs_tol=1e-5)
    assert math.isclose(metrics.percentage_change, 0.02, abs_tol=1e-6)

    contrib_map = {c.asset_id: c for c in contributions}
    assert math.isclose(contrib_map["A:US"].value_change, -6000.0, abs_tol=1e-5)
    assert math.isclose(contrib_map["A:US"].return_contribution, -0.06, abs_tol=1e-6)
    assert math.isclose(contrib_map["B:US"].value_change, 8000.0, abs_tol=1e-5)
    assert math.isclose(contrib_map["B:US"].return_contribution, 0.08, abs_tol=1e-6)


def test_dollar_contributions_conserve_total_portfolio_change():
    """The sum of individual asset dollar changes must exactly equal the total portfolio change."""
    weights = {"A:US": 0.30, "B:US": 0.25, "C:US": 0.45}
    shocks = {"A:US": -0.15, "B:US": -0.08, "C:US": 0.12}
    initial_capital = 500000.0

    metrics, contributions = apply_instantaneous_shocks(weights, shocks, initial_capital)

    sum_contrib = sum(c.value_change for c in contributions)
    assert math.isclose(sum_contrib, metrics.absolute_change, abs_tol=1e-4)

    sum_ret_contrib = sum(c.return_contribution for c in contributions)
    assert math.isclose(sum_ret_contrib, metrics.percentage_change, abs_tol=1e-6)


def test_cash_treatment_in_underinvested_portfolio():
    """
    Portfolio with 70% invested ($70,000) and 30% uninvested cash ($30,000).
    A -20% shock to invested holdings costs -$14,000.
    Cash is unaffected ($30,000). Total portfolio = $86,000 (-14%).
    """
    weights = {"AAPL:US": 0.70}  # 30% cash
    shocks = {"AAPL:US": -0.20}
    initial_capital = 100000.0

    metrics, contributions = apply_instantaneous_shocks(weights, shocks, initial_capital)

    assert math.isclose(metrics.cash_value, 30000.0, abs_tol=1e-5)
    assert math.isclose(metrics.stressed_portfolio_value, 86000.0, abs_tol=1e-5)
    assert math.isclose(metrics.absolute_change, -14000.0, abs_tol=1e-5)
    assert math.isclose(metrics.percentage_change, -0.14, abs_tol=1e-6)


def test_invalid_shocks_and_parameters_rejected():
    """Non-finite shocks, shocks < -1.0 (-100% loss), and weights > 1.0 are rejected."""
    # Shock < -1.0 (cannot lose 150% in long position)
    with pytest.raises(ValueError, match="cannot be less than -1.0"):
        apply_instantaneous_shocks({"A": 1.0}, {"A": -1.5}, 100000.0)

    # Non-finite shock
    with pytest.raises(ValueError, match="Non-finite shock"):
        apply_instantaneous_shocks({"A": 1.0}, {"A": float("nan")}, 100000.0)

    # Negative capital
    with pytest.raises(ValueError, match="Initial capital must be strictly positive"):
        apply_instantaneous_shocks({"A": 1.0}, {"A": -0.1}, -50000.0)

    # Weights exceeding 1.0
    with pytest.raises(ValueError, match="exceed 1.0"):
        apply_instantaneous_shocks({"A": 0.8, "B": 0.5}, {"A": -0.1}, 100000.0)


def test_covariance_volatility_scaling():
    """
    Scaling volatility by factor alpha scales standard deviation by alpha and variance by alpha^2.
    """
    cov_data = [[0.04, 0.01], [0.01, 0.09]]
    cov_df = pd.DataFrame(cov_data, index=["A", "B"], columns=["A", "B"])
    weights = {"A": 0.5, "B": 0.5}

    # Volatility multiplier = 1.5 (+50% volatility)
    stressed_cov, base_vol, stressed_vol, vol_change, _ = stress_covariance_matrix(
        cov_df, weights, volatility_multiplier=1.5, correlation_multiplier=1.0
    )

    assert math.isclose(stressed_vol, base_vol * 1.5, rel_tol=1e-5)
    assert math.isclose(vol_change, base_vol * 0.5, rel_tol=1e-5)
    # Variances on diagonal scaled by 1.5^2 = 2.25
    assert math.isclose(stressed_cov.loc["A", "A"], 0.04 * 2.25, rel_tol=1e-5)
    assert math.isclose(stressed_cov.loc["B", "B"], 0.09 * 2.25, rel_tol=1e-5)


def test_covariance_psd_projection_when_correlation_stressed():
    """
    Stress that produces negative eigenvalues is either rejected or projected to positive semi-definite.
    """
    # 3-asset intransitive correlation matrix with negative eigenvalue
    bad_cov = pd.DataFrame(
        [
            [1.0, 0.8, -0.8],
            [0.8, 1.0, 0.8],
            [-0.8, 0.8, 1.0],
        ],
        index=["A", "B", "C"],
        columns=["A", "B", "C"],
    )
    weights = {"A": 0.333, "B": 0.333, "C": 0.334}

    # With auto_project_psd=True, projects it to PSD
    stressed_cov, base_vol, stressed_vol, _, warnings = stress_covariance_matrix(
        bad_cov, weights, volatility_multiplier=1.0, correlation_multiplier=1.0, auto_project_psd=True
    )

    # Matrix must be positive semi-definite
    eigs = np.linalg.eigvalsh(stressed_cov.to_numpy())
    assert np.all(eigs >= -1e-8)
    assert len(warnings) > 0  # Warned about spectral clipping

    # With auto_project_psd=False, raises ValueError
    with pytest.raises(ValueError, match="non-positive-semidefinite"):
        stress_covariance_matrix(bad_cov, weights, auto_project_psd=False)


def test_historical_window_shock_extraction():
    """Extracts actual observed returns over calendar window without fabrication."""
    prices = pd.DataFrame(
        {
            "A": [100.0, 105.0, 110.0, 120.0],
            "B": [50.0, 48.0, 45.0, 40.0],
        },
        index=["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"],
    )

    shocks, start_d, end_d, warnings = extract_historical_window_shocks(
        prices, start_date="2023-01-01", end_date="2023-01-04"
    )

    # Asset A: (120 - 100) / 100 = +20%
    assert math.isclose(shocks["A"], 0.20, abs_tol=1e-5)
    # Asset B: (40 - 50) / 50 = -20%
    assert math.isclose(shocks["B"], -0.20, abs_tol=1e-5)
    assert start_d == "2023-01-01"
    assert end_d == "2023-01-04"


def test_sensitivity_1d_curve_and_2d_grid_evaluations():
    """Tests 1-factor curve sweep and 2-factor grid sweep calculations."""
    weights = {"A": 0.50, "B": 0.50}
    capital = 100000.0

    # 1D sweep on Asset A: -20% to +20% in 5 steps: [-0.20, -0.10, 0.0, 0.10, 0.20]
    shocks_1 = generate_grid_values(-0.20, 0.20, 5)
    grid_1d = evaluate_sensitivity_grid(weights, capital, "A", shocks_1)

    assert len(grid_1d) == 5
    # Center point (shock = 0.0) -> $100,000
    assert math.isclose(grid_1d[2].stressed_portfolio_value, 100000.0, abs_tol=1e-2)
    # First point (shock = -0.20) -> w_A * -0.20 = -10% -> $90,000
    assert math.isclose(grid_1d[0].stressed_portfolio_value, 90000.0, abs_tol=1e-2)
    assert math.isclose(grid_1d[0].percentage_change, -0.10, abs_tol=1e-5)
    # Last point (shock = +0.20) -> w_A * +0.20 = +10% -> $110,000
    assert math.isclose(grid_1d[4].stressed_portfolio_value, 110000.0, abs_tol=1e-2)

    # 2D sweep: Factor A (3 steps) x Factor B (3 steps) = 9 points
    shocks_2 = generate_grid_values(-0.10, 0.10, 3)
    grid_2d = evaluate_sensitivity_grid(
        weights, capital, "A", shocks_1[:3], factor_2_asset="B", factor_2_shocks=shocks_2
    )
    assert len(grid_2d) == 9
    for pt in grid_2d:
        assert pt.factor_2_value is not None
        expected_ret = 0.5 * pt.factor_1_value + 0.5 * pt.factor_2_value
        assert math.isclose(pt.percentage_change, expected_ret, abs_tol=1e-5)
