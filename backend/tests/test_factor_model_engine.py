"""
Unit and Analytical Benchmark Tests for Multi-Factor Model & Risk Decomposition Engine.
"""

import math
import numpy as np
import pytest
from app.quant.factor_model import (
    estimate_single_asset_factor_regression,
    construct_synthetic_factors_from_returns,
    compute_structural_covariance_matrix,
    decompose_portfolio_factor_risk,
    solve_factor_constrained_portfolio,
)


def test_single_asset_ols_regression_analytical():
    """Verifies single asset OLS regression against exact known parameters."""
    np.random.seed(42)
    T = 252
    F = np.random.normal(0.0005, 0.01, size=(T, 2))  # Two factors
    true_alpha = 0.0002
    true_beta = np.array([1.2, -0.5])
    eps = np.random.normal(0, 0.005, size=T)
    y = true_alpha + F @ true_beta + eps

    res = estimate_single_asset_factor_regression(
        asset_excess_returns=y,
        factors_matrix=F,
        factor_names=["F1", "F2"],
        annualization_factor=252,
    )

    # Betas should be estimated close to true values
    assert abs(res["betas"]["F1"]["beta"] - 1.2) < 0.15
    assert abs(res["betas"]["F2"]["beta"] - (-0.5)) < 0.15
    assert res["r_squared"] > 0.60
    assert res["betas"]["F1"]["tstat"] > 5.0
    assert res["betas"]["F1"]["pvalue"] < 0.001


def test_2_asset_1_factor_analytical_benchmark():
    """
    Evaluates exact hand-calculated benchmark from SESSION_20_CONTRACTS.md:
    beta_1 = 1.20, beta_2 = 0.80, sigma_F^2 = 0.04
    specific var: s1 = 0.01, s2 = 0.02
    Equal weights w = [0.5, 0.5]
    beta_p = 1.00
    sys_var = 1.0^2 * 0.04 = 0.0400
    idio_var = 0.5^2 * 0.01 + 0.5^2 * 0.02 = 0.0025 + 0.0050 = 0.0075
    total_var = 0.0475
    sys_share = 0.0400 / 0.0475 = 84.2105%
    idio_share = 0.0075 / 0.0475 = 15.7895%
    """
    weights = np.array([0.5, 0.5])
    factor_loadings = np.array([[1.20], [0.80]])
    factor_cov = np.array([[0.04]])
    specific_variances = np.array([0.01, 0.02])

    decomp = decompose_portfolio_factor_risk(
        weights=weights,
        factor_loadings=factor_loadings,
        factor_covariance=factor_cov,
        specific_variances=specific_variances,
        factor_names=["MKT"],
    )

    assert abs(decomp["portfolio_betas"]["MKT"] - 1.00) < 1e-9
    assert abs(decomp["systematic_variance"] - 0.0400) < 1e-8
    assert abs(decomp["idiosyncratic_variance"] - 0.0075) < 1e-8
    assert abs(decomp["total_variance"] - 0.0475) < 1e-8
    assert abs(decomp["systematic_share_pct"] - 84.21) < 0.02
    assert abs(decomp["idiosyncratic_share_pct"] - 15.79) < 0.02
    assert abs(decomp["factor_contributions"]["MKT"]["pct_of_systematic_risk"] - 100.0) < 1e-6


def test_structural_covariance_symmetry_and_psd():
    """Verifies that the structural covariance matrix is symmetric and strictly positive definite."""
    B = np.array([[1.1, 0.2], [0.8, -0.3], [1.3, 0.5]])
    Sigma_F = np.array([[0.04, 0.005], [0.005, 0.02]])
    s_eps = np.array([0.01, 0.015, 0.02])

    Sigma = compute_structural_covariance_matrix(B, Sigma_F, s_eps)

    # Symmetry
    assert np.allclose(Sigma, Sigma.T, atol=1e-12)
    # Positive definiteness (all eigenvalues > 0)
    eigvals = np.linalg.eigvalsh(Sigma)
    assert np.all(eigvals > 0)


def test_synthetic_factor_generation():
    """Verifies deterministic synthetic factor extraction from returns panel."""
    np.random.seed(123)
    T, N = 100, 5
    R = np.random.normal(0.0005, 0.01, size=(T, N))

    f_capm, names_capm = construct_synthetic_factors_from_returns(R, factor_model="capm")
    assert f_capm.shape == (T, 1)
    assert names_capm == ["MKT"]

    f_ff3, names_ff3 = construct_synthetic_factors_from_returns(R, factor_model="ff3")
    assert f_ff3.shape == (T, 3)
    assert names_ff3 == ["MKT", "SMB", "HML"]

    f_c4, names_c4 = construct_synthetic_factors_from_returns(R, factor_model="carhart4")
    assert f_c4.shape == (T, 4)
    assert names_c4 == ["MKT", "SMB", "HML", "MOM"]

    f_pca, names_pca = construct_synthetic_factors_from_returns(R, factor_model="pca", num_pca_factors=2)
    assert f_pca.shape == (T, 2)
    assert names_pca == ["PC_1", "PC_2"]


def test_factor_constrained_optimization_enforces_bounds():
    """Verifies that factor-constrained optimization strictly respects beta tilt constraints."""
    expected_returns = np.array([0.12, 0.08, 0.15])
    B = np.array([[1.5, 0.4], [0.5, -0.2], [1.2, 0.1]])  # 3 assets, 2 factors
    Sigma_F = np.diag([0.04, 0.02])
    s_eps = np.array([0.01, 0.01, 0.01])
    factor_names = ["MKT", "SMB"]

    # Target: Market Beta constrained strictly to [0.6, 0.8]
    w_opt, feasible, msg = solve_factor_constrained_portfolio(
        expected_returns=expected_returns,
        factor_loadings=B,
        factor_covariance=Sigma_F,
        specific_variances=s_eps,
        factor_names=factor_names,
        objective="min_variance",
        factor_constraints={"MKT": (0.6, 0.8)},
        min_weight=0.0,
        max_weight=1.0,
    )

    assert feasible is True
    assert abs(np.sum(w_opt) - 1.0) < 1e-6
    assert np.all(w_opt >= -1e-6)

    # Check that portfolio market beta is within [0.6, 0.8]
    port_mkt_beta = float(B[:, 0] @ w_opt)
    assert port_mkt_beta >= 0.5999
    assert port_mkt_beta <= 0.8001
