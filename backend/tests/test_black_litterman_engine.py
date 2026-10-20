"""
Unit tests for the Black-Litterman mathematical optimization engine.
"""

import numpy as np
import pytest

from app.quant.black_litterman import (
    BlackLittermanView,
    calculate_implied_equilibrium_returns,
    build_view_matrices,
    compute_black_litterman_posterior,
    compute_unconstrained_bl_weights,
    optimize_black_litterman_portfolio,
    compute_black_litterman_diagnostics,
)


def test_implied_equilibrium_returns():
    """Verify Pi = gamma * Sigma * w_eq."""
    cov = np.array([
        [0.04, 0.01],
        [0.01, 0.09],
    ], dtype=np.float64)
    w_eq = np.array([0.5, 0.5], dtype=np.float64)
    gamma = 2.50

    pi = calculate_implied_equilibrium_returns(cov, w_eq, risk_aversion=gamma)

    # 2.5 * [0.5*0.04 + 0.5*0.01, 0.5*0.01 + 0.5*0.09] = 2.5 * [0.025, 0.050] = [0.0625, 0.1250]
    assert np.allclose(pi, [0.0625, 0.1250], atol=1e-12)


def test_hand_calculated_2_asset_relative_view_benchmark():
    """
    Verifies the analytical reference benchmark documented in docs/SESSION_18_CONTRACTS.md:
    2 assets: w_eq = [0.5, 0.5], gamma = 2.5, tau = 0.05
    View: Asset 1 outperforms Asset 2 by 2.0% (0.02)
    Analytical mu_BL = [0.07375, 0.09500] when Omega is calibrated via view variance.
    """
    assets = ["AAPL", "MSFT"]
    cov = np.array([
        [0.04, 0.01],
        [0.01, 0.09],
    ], dtype=np.float64)
    w_eq = np.array([0.5, 0.5], dtype=np.float64)
    tau = 0.05
    gamma = 2.50

    pi = calculate_implied_equilibrium_returns(cov, w_eq, risk_aversion=gamma)
    assert np.allclose(pi, [0.0625, 0.1250], atol=1e-12)

    # Single relative view: P = [1, -1], q = 0.02
    # In He-Litterman formulation: Omega = P * (tau * Sigma) * P^T = 0.0055
    # In Idzorek with confidence c = 0.50: (1 - 0.5)/0.5 = 1.0 => Omega = 0.0055 exactly!
    view = BlackLittermanView(
        view_type="relative",
        assets=("AAPL", "MSFT"),
        weights=(1.0, -1.0),
        target_return=0.02,
        confidence=0.50,
    )

    p, q, omega = build_view_matrices([view], assets, tau, cov)
    assert np.allclose(p, [[1.0, -1.0]], atol=1e-12)
    assert np.allclose(q, [0.02], atol=1e-12)
    assert np.isclose(omega[0, 0], 0.0055, atol=1e-8)

    mu_bl, sigma_post = compute_black_litterman_posterior(pi, cov, p, q, omega, tau)

    # Matches exact analytical solution: [0.07375, 0.09500]
    expected_mu = np.array([0.07375, 0.09500])
    assert np.allclose(mu_bl, expected_mu, atol=1e-5)

    # Check unconstrained weights tilt toward Asset 1
    w_bl = compute_unconstrained_bl_weights(mu_bl, cov, gamma)
    assert w_bl[0] > w_eq[0]  # AAPL weight increased above 50%
    assert w_bl[1] < w_eq[1]  # MSFT weight decreased below 50%
    assert np.isclose(np.sum(w_bl), 1.0, atol=1e-7)


def test_zero_views_reproduces_equilibrium_prior():
    """When no views are provided, posterior expected return matches equilibrium prior."""
    cov = np.array([
        [0.05, 0.01],
        [0.01, 0.04],
    ])
    w_eq = np.array([0.6, 0.4])
    pi = calculate_implied_equilibrium_returns(cov, w_eq, risk_aversion=3.0)

    p = np.zeros((0, 2))
    q = np.zeros(0)
    omega = np.zeros((0, 0))

    mu_bl, sigma_post = compute_black_litterman_posterior(pi, cov, p, q, omega, tau=0.05)

    assert np.allclose(mu_bl, pi, atol=1e-12)
    assert np.allclose(sigma_post, 1.05 * cov, atol=1e-12)

    # 1. Unconstrained BL weights exactly reproduce equilibrium weights
    w_unconstrained = compute_unconstrained_bl_weights(mu_bl, cov, risk_aversion=3.0)
    assert np.allclose(w_unconstrained, w_eq, atol=1e-12)

    # 2. As tau -> 0, constrained utility optimization reproduces w_eq exactly
    opt_zero_tau = optimize_black_litterman_portfolio(
        posterior_mean=mu_bl,
        posterior_covariance=cov,  # tau = 0 limit
        objective="mean_variance_utility",
        risk_aversion=3.0,
        min_weight=0.0,
        max_weight=1.0,
    )
    assert opt_zero_tau["is_feasible"]
    assert np.allclose(opt_zero_tau["weights"], w_eq, atol=1e-6)

    # 3. For tau > 0, constrained utility optimization analytically yields
    # w = (1/(1+tau)) * w_eq + (tau/(1+tau)) * w_GMV
    # For this covariance matrix, w_GMV = [3/7, 4/7]
    inv_cov = np.linalg.inv(cov)
    w_gmv = (inv_cov @ np.ones(2)) / np.sum(inv_cov)
    expected_tau_w = (1.0 / 1.05) * w_eq + (0.05 / 1.05) * w_gmv

    opt_tau = optimize_black_litterman_portfolio(
        posterior_mean=mu_bl,
        posterior_covariance=sigma_post,
        objective="mean_variance_utility",
        risk_aversion=3.0,
        min_weight=0.0,
        max_weight=1.0,
    )
    assert opt_tau["is_feasible"]
    assert np.allclose(opt_tau["weights"], expected_tau_w, atol=1e-5)


def test_confidence_scaling_monotonicity():
    """Higher confidence in a bullish view causes greater active tilt."""
    assets = ["A", "B"]
    cov = np.array([
        [0.04, 0.00],
        [0.00, 0.04],
    ])
    w_eq = np.array([0.5, 0.5])
    pi = calculate_implied_equilibrium_returns(cov, w_eq, risk_aversion=2.5)

    # Low confidence view (c = 0.20)
    view_low = BlackLittermanView("absolute", ("A",), (1.0,), target_return=0.15, confidence=0.20)
    p_l, q_l, o_l = build_view_matrices([view_low], assets, 0.05, cov)
    mu_low, _ = compute_black_litterman_posterior(pi, cov, p_l, q_l, o_l, 0.05)

    # High confidence view (c = 0.85)
    view_high = BlackLittermanView("absolute", ("A",), (1.0,), target_return=0.15, confidence=0.85)
    p_h, q_h, o_h = build_view_matrices([view_high], assets, 0.05, cov)
    mu_high, _ = compute_black_litterman_posterior(pi, cov, p_h, q_h, o_h, 0.05)

    # Asset A's posterior return should be strictly higher under higher confidence
    assert mu_high[0] > mu_low[0] > pi[0]


def test_constrained_black_litterman_solver():
    """Verify max weight constraint is strictly respected by the optimizer."""
    assets = ["A", "B", "C"]
    cov = np.array([
        [0.04, 0.01, 0.01],
        [0.01, 0.05, 0.01],
        [0.01, 0.01, 0.06],
    ])
    mu_bl = np.array([0.20, 0.05, 0.05])  # Strong view for A
    sigma_post = cov * 1.05

    opt = optimize_black_litterman_portfolio(
        posterior_mean=mu_bl,
        posterior_covariance=sigma_post,
        objective="max_sharpe",
        min_weight=0.0,
        max_weight=0.45,  # Cap at 45%
    )

    assert opt["is_feasible"]
    assert opt["weights"][0] <= 0.45 + 1e-6
    assert np.isclose(np.sum(opt["weights"]), 1.0, atol=1e-6)
    assert np.all(opt["weights"] >= -1e-6)


def test_diagnostics_calculation():
    """Verify D1 distance, active tilts, and HHI metrics."""
    assets = ["A", "B"]
    w_eq = np.array([0.5, 0.5])
    w_opt = np.array([0.7, 0.3])
    pi = np.array([0.08, 0.08])
    mu_bl = np.array([0.10, 0.06])
    view = BlackLittermanView("relative", ("A", "B"), (1.0, -1.0), 0.04, confidence=0.6)
    p = np.array([[1.0, -1.0]])
    q = np.array([0.04])

    diag = compute_black_litterman_diagnostics(assets, w_eq, w_opt, pi, mu_bl, [view], p, q)

    assert np.isclose(diag["weight_distance_d1"], 0.4, atol=1e-8)  # |0.7-0.5| + |0.3-0.5| = 0.4
    assert np.isclose(diag["active_tilts"]["A"], 0.2, atol=1e-8)
    assert np.isclose(diag["active_tilts"]["B"], -0.2, atol=1e-8)
    assert len(diag["views_summary"]) == 1
    assert diag["views_summary"][0]["absorbed_difference"] > 0
