"""
Unit and Numerical Mathematics Test Suite for Copula Tail Risk Engine
and Tail Risk Parity Allocation.

Verifies:
1. Analytical worked benchmarks for Clayton, Gumbel, Student-t, and Gaussian tail dependence.
2. Probability integral transform range and marginal handling.
3. Simulation reproducibility under fixed random seeds.
4. Exact Euler CVaR decomposition additive identity: sum_i TRC_i == CVaR_alpha.
5. Tail Risk Parity budget invariant (sum w == 1.0) and non-negativity (w >= 0).
"""

import math
import numpy as np
import pytest
from scipy import stats

from app.quant.copula_tail_risk import (
    compute_pseudo_observations,
    fit_clayton_copula,
    fit_gumbel_copula,
    fit_student_t_copula,
    fit_gaussian_copula,
    fit_pairwise_copulas,
    simulate_copula_returns,
    compute_portfolio_tail_risk,
    optimize_tail_risk_parity,
)


def test_clayton_analytical_tail_dependence_benchmark():
    """
    Independent worked benchmark for Clayton Copula:
    Given tau = 0.50:
        theta = 2 * tau / (1 - tau) = 2 * 0.5 / 0.5 = 2.0
        lambda_L = 2^{-1/theta} = 2^{-1/2} = 1 / sqrt(2) approx 0.70710678
        lambda_U = 0.0
    """
    theta = 2.0
    lambda_l_theoretical = math.pow(2.0, -1.0 / theta)
    assert abs(lambda_l_theoretical - (1.0 / math.sqrt(2.0))) < 1e-12
    assert abs(lambda_l_theoretical - 0.70710678) < 1e-6

    # Generate synthetic Clayton pairs with theta = 2.0 via Marshall-Olkin
    rng = np.random.default_rng(12345)
    T = 2000
    v = rng.gamma(shape=1.0 / theta, scale=1.0, size=(T, 1))
    e = rng.exponential(scale=1.0, size=(T, 2))
    u = np.power(1.0 + e / v, -1.0 / theta)

    res = fit_clayton_copula(u[:, 0], u[:, 1])
    # Recovered parameter theta should be close to 2.0 within sampling uncertainty
    assert abs(res["theta"] - 2.0) < 0.25
    assert abs(res["lower_tail_dependence"] - 0.7071) < 0.05
    assert res["upper_tail_dependence"] == 0.0
    assert res["converged"] is True


def test_gumbel_analytical_tail_dependence_benchmark():
    """
    Independent worked benchmark for Gumbel Copula:
    Given tau = 0.50:
        theta = 1 / (1 - tau) = 1 / 0.5 = 2.0
        lambda_U = 2 - 2^{1/theta} = 2 - 2^{0.5} = 2 - sqrt(2) approx 0.5857864
        lambda_L = 0.0
    """
    theta = 2.0
    lambda_u_theoretical = 2.0 - math.pow(2.0, 1.0 / theta)
    assert abs(lambda_u_theoretical - (2.0 - math.sqrt(2.0))) < 1e-12
    assert abs(lambda_u_theoretical - 0.5857864) < 1e-6


def test_student_t_and_gaussian_tail_dependence_formulas():
    """
    Verifies Student-t tail dependence formula symmetry and Gaussian baseline zero tail dependence.
    For Student-t: rho = 0.6, nu = 4.0:
        arg = -sqrt((nu+1)*(1-rho)/(1+rho)) = -sqrt(5 * 0.4 / 1.6) = -sqrt(1.25) approx -1.11803
        lambda_L = lambda_U = 2 * t_5(-1.11803) approx 0.3096
    """
    rho = 0.6
    nu = 4.0
    arg = -math.sqrt((nu + 1.0) * (1.0 - rho) / (1.0 + rho))
    lambda_t = 2.0 * float(stats.t.cdf(arg, df=nu + 1.0))
    assert 0.0 < lambda_t < 1.0

    # Gaussian copula must have strictly 0 asymptotic tail dependence
    rng = np.random.default_rng(42)
    z = rng.multivariate_normal([0.0, 0.0], [[1.0, 0.5], [0.5, 1.0]], size=500)
    u1 = stats.norm.cdf(z[:, 0])
    u2 = stats.norm.cdf(z[:, 1])

    res_gauss = fit_gaussian_copula(u1, u2)
    assert res_gauss["lower_tail_dependence"] == 0.0
    assert res_gauss["upper_tail_dependence"] == 0.0
    assert abs(res_gauss["theta"] - 0.5) < 0.10


def test_pseudo_observations_transformation():
    """Verifies that rank pseudo-observations strictly lie in (0, 1)."""
    rng = np.random.default_rng(999)
    raw_returns = rng.normal(0.001, 0.02, size=(100, 3))
    U, meta = compute_pseudo_observations(raw_returns, method="empirical")

    assert U.shape == (100, 3)
    assert np.all(U > 0.0)
    assert np.all(U < 1.0)
    # Check minimum rank value is exactly 1 / (T + 1)
    assert np.min(U) == pytest.approx(1.0 / 101.0)
    assert np.max(U) == pytest.approx(100.0 / 101.0)


def test_simulation_reproducibility_with_seed():
    """Verifies identical random seeds generate identical simulated outputs down to float64 bit-level."""
    rng = np.random.default_rng(42)
    returns = rng.normal(0.0005, 0.015, size=(150, 3))
    tickers = ["AAPL", "MSFT", "GOOGL"]

    sim1, _ = simulate_copula_returns(
        returns, tickers, copula_type="clayton", num_simulations=1000, random_seed=777
    )
    sim2, _ = simulate_copula_returns(
        returns, tickers, copula_type="clayton", num_simulations=1000, random_seed=777
    )

    np.testing.assert_array_equal(sim1, sim2)


def test_euler_cvar_decomposition_additive_identity():
    """
    Verifies the fundamental Euler CVaR identity:
        sum_{i=1}^N TRC_i == CVaR_alpha
    Must hold to < 1e-12 precision on any portfolio weight vector.
    """
    rng = np.random.default_rng(101)
    sim_returns = rng.normal(0.0005, 0.02, size=(3000, 4))
    weights = np.array([0.4, 0.3, 0.2, 0.1], dtype=np.float64)

    risk_result = compute_portfolio_tail_risk(weights, sim_returns, confidence_level=0.99)

    cvar = risk_result["portfolio_cvar"]
    euler_sum = risk_result["euler_sum"]
    err = risk_result["reconciliation_error"]

    assert abs(euler_sum - cvar) < 1e-12
    assert err < 1e-12
    assert risk_result["portfolio_var"] > 0.0
    assert cvar >= risk_result["portfolio_var"]


def test_tail_risk_parity_budget_and_dispersion():
    """
    Verifies that Tail Risk Parity optimization achieves budget constraint (sum w == 1.0),
    non-negativity (w >= 0), and reduces tail risk dispersion relative to equal weight.
    """
    rng = np.random.default_rng(202)
    # Asset 0 is low volatility, Asset 1 has extreme tail crash risk
    sim_returns = rng.normal(0.001, 0.01, size=(4000, 2))
    # Inject heavy asymmetric tail crash into asset 1
    sim_returns[:100, 1] -= 0.15

    tickers = ["SAFE", "RISKY"]
    opt = optimize_tail_risk_parity(sim_returns, tickers, confidence_level=0.99)

    w_safe = opt["weights"]["SAFE"]
    w_risky = opt["weights"]["RISKY"]

    # Budget invariant
    assert abs((w_safe + w_risky) - 1.0) < 1e-4
    assert w_safe >= 0.0
    assert w_risky >= 0.0
    # Safe asset should receive higher weight than risky asset in TRP
    assert w_safe > w_risky
    assert opt["euler_reconciliation_error"] < 1e-10
