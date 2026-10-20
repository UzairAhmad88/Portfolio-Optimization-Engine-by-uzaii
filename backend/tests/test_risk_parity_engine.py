"""
Unit tests for Equal Risk Contribution (ERC) and Hierarchical Risk Parity (HRP) mathematical engine.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.quant.black_litterman import (
    calculate_implied_equilibrium_returns,
    compute_black_litterman_posterior,
    compute_unconstrained_bl_weights,
)
from app.quant.risk_parity import (
    calculate_risk_contributions,
    compute_risk_parity_diagnostics,
    solve_equal_risk_contribution,
    solve_hierarchical_risk_parity,
    solve_inverse_variance_portfolio,
)


def test_euler_risk_decomposition():
    """
    Verifies Euler's risk decomposition properties:
    - sum(TRC_i) == portfolio_volatility
    - sum(%RC_i) == 1.0
    """
    cov = np.array([
        [0.04, 0.01, 0.005],
        [0.01, 0.09, 0.02],
        [0.005, 0.02, 0.06],
    ], dtype=np.float64)
    w = np.array([0.4, 0.35, 0.25], dtype=np.float64)

    mrc, trc, prc, port_vol = calculate_risk_contributions(w, cov)

    assert port_vol > 0.0
    assert np.isclose(np.sum(trc), port_vol, atol=1e-10)
    assert np.isclose(np.sum(prc), 1.0, atol=1e-10)
    assert np.all(trc > 0.0)


def test_erc_analytical_benchmark():
    """
    Verifies the independent 2-asset analytical benchmark from docs/SESSION_19_CONTRACTS.md:
    Asset 1: sigma1 = 0.20 (var1 = 0.04)
    Asset 2: sigma2 = 0.30 (var2 = 0.09)
    Covariance = 0.0
    Analytical ERC solution:
        w1 * sigma1 = w2 * sigma2 => w1 * 0.20 = w2 * 0.30 => w1 = 1.5 w2
        w1 + w2 = 1.0 => w1 = 0.60, w2 = 0.40
        %RC1 = 50.0%, %RC2 = 50.0%
        Risk Gini = 0.0
    """
    cov = np.array([
        [0.04, 0.00],
        [0.00, 0.09],
    ], dtype=np.float64)

    res = solve_equal_risk_contribution(cov)

    assert res["is_feasible"] is True
    assert res["solver_status"] == "optimal"

    w_opt = res["weights"]
    prc = res["percentage_risk_contributions"]

    # Match analytical weights [0.60, 0.40] within numerical solver tolerance
    assert np.allclose(w_opt, [0.60, 0.40], atol=1e-5)

    # Risk contributions must be exactly equal (50% each)
    assert np.allclose(prc, [0.50, 0.50], atol=1e-5)
    assert np.isclose(res["risk_gini_coefficient"], 0.0, atol=1e-5)
    assert np.isclose(res["effective_number_of_bets"], 2.0, atol=1e-4)


def test_custom_risk_budgets():
    """
    Verifies general Risk Budgeting with asymmetric budgets b = [0.70, 0.30].
    """
    cov = np.array([
        [0.04, 0.00],
        [0.00, 0.04],
    ], dtype=np.float64)
    b = np.array([0.70, 0.30], dtype=np.float64)

    res = solve_equal_risk_contribution(cov, risk_budgets=b)

    assert res["is_feasible"] is True
    prc = res["percentage_risk_contributions"]
    assert np.allclose(prc, [0.70, 0.30], atol=1e-4)


def test_hrp_analytical_benchmark_and_invariance():
    """
    Verifies Hierarchical Risk Parity (HRP) tree clustering and allocation:
    - Weights sum to 1.0.
    - Higher volatility assets receive lower weights.
    - Diagnostics are within mathematical bounds.
    """
    cov = np.array([
        [0.04, 0.01, 0.00],
        [0.01, 0.09, 0.02],
        [0.00, 0.02, 0.16],
    ], dtype=np.float64)

    res = solve_hierarchical_risk_parity(cov, linkage_method="single")

    assert res["is_feasible"] is True
    w = res["weights"]
    assert np.isclose(np.sum(w), 1.0, atol=1e-10)
    assert np.all(w > 0.0)
    # Lowest volatility asset (Asset 0) should receive the highest weight
    assert w[0] > w[1] > w[2]

    # Reordered indices should be a permutation of range(3)
    assert sorted(res["reordered_indices"]) == [0, 1, 2]
    assert res["diversification_ratio"] >= 1.0


def test_hrp_singular_covariance_immunity():
    """
    Verifies HRP's signature theoretical property: complete immunity to singular,
    rank-deficient covariance matrices where quadratic programming fails.
    """
    # Create rank-deficient covariance (Assets 1 and 2 are perfectly collinear duplicates)
    col = np.array([0.2, 0.3, 0.3])
    corr = np.array([
        [1.0, 0.5, 0.5],
        [0.5, 1.0, 1.0],  # perfect collinearity between assets 1 and 2
        [0.5, 1.0, 1.0],
    ])
    cov = np.outer(col, col) * corr

    # Verify cov is singular (det == 0)
    assert np.isclose(np.linalg.det(cov), 0.0, atol=1e-12)

    # HRP executes cleanly without matrix inversion
    res = solve_hierarchical_risk_parity(cov, linkage_method="single")

    assert res["is_feasible"] is True
    assert res["solver_status"] == "optimal"
    assert np.isclose(np.sum(res["weights"]), 1.0, atol=1e-10)
    assert np.all(res["weights"] > 0.0)


def test_risk_parity_diagnostics():
    """
    Verifies diagnostic metrics across Inverse-Variance and Equal-Weight allocations.
    """
    cov = np.array([
        [0.04, 0.01],
        [0.01, 0.09],
    ], dtype=np.float64)

    w_iv = solve_inverse_variance_portfolio(cov)
    # Inverse variances: 1/0.04 = 25, 1/0.09 = 11.1111 => total = 36.1111
    # w1 = 25 / 36.1111 = 0.6923, w2 = 11.1111 / 36.1111 = 0.3077
    assert np.isclose(w_iv[0], 25.0 / (25.0 + 100.0 / 9.0), atol=1e-6)

    diag = compute_risk_parity_diagnostics(w_iv, cov)
    assert 0.0 <= diag["risk_gini_coefficient"] <= 1.0
    assert diag["effective_number_of_bets"] >= 1.0
    assert diag["diversification_ratio"] >= 1.0


def test_black_litterman_excess_return_zero_view_refinement():
    """
    Verifies the Session 18 prerequisite refinement:
    When views are zero, compute_unconstrained_bl_weights on excess return
    (mu_BL - rf * 1) recovers equilibrium weights w_eq exactly for any rf >= 0.
    """
    cov = np.array([
        [0.04, 0.01],
        [0.01, 0.04],
    ], dtype=np.float64)
    w_eq = np.array([0.65, 0.35], dtype=np.float64)
    gamma = 2.50
    rf = 0.03

    pi = calculate_implied_equilibrium_returns(cov, w_eq, risk_aversion=gamma, risk_free_rate=rf)

    mu_bl, _ = compute_black_litterman_posterior(
        implied_returns=pi,
        covariance=cov,
        p=np.zeros((0, 2)),
        q=np.zeros(0),
        omega=np.zeros((0, 0)),
        tau=0.05,
    )

    # With risk_free_rate passed, it subtracts rf and recovers w_eq
    uncon_w = compute_unconstrained_bl_weights(
        posterior_mean=mu_bl,
        covariance=cov,
        risk_aversion=gamma,
        risk_free_rate=rf,
    )

    assert np.allclose(uncon_w, w_eq, atol=1e-10)
