"""
Deterministic mathematical and algorithmic tests for Value at Risk (VaR),
Conditional Value at Risk (CVaR), and Monte Carlo portfolio simulation engine.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from app.quant.var_cvar import (
    calculate_empirical_var_cvar,
    empirical_cvar,
    empirical_var,
    historical_var_cvar,
    parametric_var_cvar,
)
from app.risk_simulation.engine import (
    compute_distribution_histogram,
    downsample_trajectories,
    generate_multivariate_returns,
    project_covariance_psd,
    simulate_portfolio_wealth,
)
from app.risk_simulation.models import DistributionModel, RebalancePolicy


# ---------------------------------------------------------------------------
# 1. Pure VaR & CVaR Mathematical Tests
# ---------------------------------------------------------------------------

def test_empirical_var_and_cvar_hand_calculated_small_sample():
    """
    Validates empirical VaR and CVaR against an independent hand-calculated sample.
    Loss sample: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100] (10 items).
    For q = 0.50 (median loss):
        np.quantile(losses, 0.50) = 55.0.
        Tail losses >= 55.0 are [60, 70, 80, 90, 100].
        Expected tail mean (CVaR) = (60 + 70 + 80 + 90 + 100) / 5 = 80.0.
    """
    losses = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0])

    var_50 = empirical_var(losses, confidence_level=0.50)
    cvar_50 = empirical_cvar(losses, confidence_level=0.50)

    assert math.isclose(var_50, 55.0, abs_tol=1e-6)
    assert math.isclose(cvar_50, 80.0, abs_tol=1e-6)
    assert cvar_50 >= var_50


def test_empirical_var_cvar_extreme_quantile_and_ties():
    """
    Validates empirical VaR and CVaR with ties and at extreme confidence levels (q = 0.90).
    """
    losses = np.array([5.0, 10.0, 10.0, 20.0, 20.0, 20.0, 30.0, 40.0, 50.0, 100.0])

    var_90 = empirical_var(losses, confidence_level=0.90)
    cvar_90 = empirical_cvar(losses, confidence_level=0.90)

    # 90th percentile of this 10-element array:
    # index = 9 * 0.9 = 8.1 -> loss[8] + 0.1 * (loss[9] - loss[8]) = 50.0 + 0.1 * (100 - 50) = 55.0
    assert math.isclose(var_90, 55.0, abs_tol=1e-5)
    # Tail >= 55.0 is only [100.0]
    assert math.isclose(cvar_90, 100.0, abs_tol=1e-5)
    assert cvar_90 >= var_90


def test_calculate_empirical_var_cvar_monetary_and_percentage():
    """Verifies that monetary losses and percentage losses scale consistently with initial capital."""
    capital = 200000.0
    losses = np.array([0.0, 10000.0, 20000.0, 30000.0, 40000.0, 50000.0])

    res = calculate_empirical_var_cvar(
        terminal_losses=losses,
        initial_capital=capital,
        confidence_level=0.80,
    )

    assert math.isclose(res.var_absolute, res.var_percentage * capital, abs_tol=1e-6)
    assert math.isclose(res.cvar_absolute, res.cvar_percentage * capital, abs_tol=1e-6)
    assert res.cvar_absolute >= res.var_absolute


def test_parametric_var_cvar_analytical_benchmark():
    """
    Validates parametric normal VaR and CVaR against standard normal analytical formula:
        mu = 0.0, sigma = 0.20, horizon = 1, capital = $100,000, q = 0.95.
        z_0.95 = 1.6448536269514722
        VaR_% = 1.6448536 * 0.20 = 0.3289707 -> $32,897.07
        phi(z) = 0.10313564
        CVaR_% = (0.10313564 / 0.05) * 0.20 = 2.0627128 * 0.20 = 0.4125426 -> $41,254.26
    """
    res = parametric_var_cvar(
        initial_capital=100000.0,
        periodic_mean_return=0.0,
        periodic_volatility=0.20,
        horizon_periods=1,
        confidence_level=0.95,
    )

    assert math.isclose(res.var_percentage, 0.3289707, rel_tol=1e-4)
    assert math.isclose(res.var_absolute, 32897.07, rel_tol=1e-4)
    assert math.isclose(res.cvar_percentage, 0.4125426, rel_tol=1e-4)
    assert math.isclose(res.cvar_absolute, 41254.26, rel_tol=1e-4)
    assert res.cvar_absolute >= res.var_absolute


def test_historical_var_cvar_basic():
    """Verifies that historical VaR and CVaR execute on discrete return series without error."""
    hist_returns = np.array([0.02, -0.01, -0.03, 0.01, -0.05, 0.04, -0.02, 0.01, -0.04, 0.03])
    capital = 100000.0

    res = historical_var_cvar(
        historical_portfolio_returns=hist_returns,
        initial_capital=capital,
        horizon_periods=1,
        confidence_level=0.90,
    )

    assert res.var_absolute > 0.0
    assert res.cvar_absolute >= res.var_absolute


def test_var_cvar_rejection_of_invalid_inputs():
    """Rejects out-of-bound confidence levels and non-finite values."""
    with pytest.raises(ValueError, match="Confidence level must be strictly between 0.0 and 1.0"):
        empirical_var([10.0, 20.0], confidence_level=1.0)

    with pytest.raises(ValueError, match="Confidence level must be strictly between 0.0 and 1.0"):
        empirical_var([10.0, 20.0], confidence_level=0.0)

    with pytest.raises(ValueError, match="Loss array contains non-finite values"):
        empirical_var([10.0, np.nan, 20.0], confidence_level=0.95)

    with pytest.raises(ValueError, match="Initial capital must be strictly positive"):
        parametric_var_cvar(initial_capital=0.0, periodic_mean_return=0.0, periodic_volatility=0.1)


# ---------------------------------------------------------------------------
# 2. Monte Carlo Simulation Engine Tests
# ---------------------------------------------------------------------------

def test_monte_carlo_seed_reproducibility():
    """Identical seed and parameters produce bit-for-bit identical simulated returns."""
    mu = np.array([0.0005, 0.0003])
    cov = np.array([[0.0004, 0.0001], [0.0001, 0.0003]])

    r1, _ = generate_multivariate_returns(
        mean_vector=mu,
        cov_matrix=cov,
        horizon_days=10,
        num_paths=100,
        seed=42,
        distribution=DistributionModel.MULTIVARIATE_NORMAL,
    )

    r2, _ = generate_multivariate_returns(
        mean_vector=mu,
        cov_matrix=cov,
        horizon_days=10,
        num_paths=100,
        seed=42,
        distribution=DistributionModel.MULTIVARIATE_NORMAL,
    )

    r3, _ = generate_multivariate_returns(
        mean_vector=mu,
        cov_matrix=cov,
        horizon_days=10,
        num_paths=100,
        seed=999,
        distribution=DistributionModel.MULTIVARIATE_NORMAL,
    )

    assert np.array_equal(r1, r2)
    assert not np.array_equal(r1, r3)


def test_monte_carlo_moment_convergence():
    """
    Over a large sample (5,000 paths), simulated returns converge to theoretical
    mean and covariance within CLT standard error bounds (±3 sigma / sqrt(M)).
    """
    mu = np.array([0.001, -0.0005])
    cov = np.array([[0.0004, 0.0001], [0.0001, 0.00025]])
    m_paths = 5000

    sim_returns, _ = generate_multivariate_returns(
        mean_vector=mu,
        cov_matrix=cov,
        horizon_days=1,
        num_paths=m_paths,
        seed=12345,
        distribution=DistributionModel.MULTIVARIATE_NORMAL,
    )

    # Flatten across days: shape (5000, 2)
    returns_2d = sim_returns[:, 0, :]
    sample_mean = np.mean(returns_2d, axis=0)
    sample_cov = np.cov(returns_2d, rowvar=False)

    # Standard errors of the mean
    se_mean_0 = math.sqrt(cov[0, 0] / m_paths)
    se_mean_1 = math.sqrt(cov[1, 1] / m_paths)

    assert abs(sample_mean[0] - mu[0]) <= 3.5 * se_mean_0
    assert abs(sample_mean[1] - mu[1]) <= 3.5 * se_mean_1

    # Covariance convergence (within 15% relative tolerance for 5000 samples)
    assert math.isclose(sample_cov[0, 0], cov[0, 0], rel_tol=0.15)
    assert math.isclose(sample_cov[1, 1], cov[1, 1], rel_tol=0.15)
    assert math.isclose(sample_cov[0, 1], cov[0, 1], rel_tol=0.25)


def test_student_t_distribution_heavier_tails():
    """
    Verifies that multivariate Student-t generates finite returns and exhibits
    fatter tails than normal distribution with calibrated covariance.
    """
    mu = np.array([0.0])
    cov = np.array([[0.0004]])  # std = 0.02

    sim_norm, _ = generate_multivariate_returns(
        mean_vector=mu,
        cov_matrix=cov,
        horizon_days=1,
        num_paths=10000,
        seed=42,
        distribution=DistributionModel.MULTIVARIATE_NORMAL,
    )

    sim_t, _ = generate_multivariate_returns(
        mean_vector=mu,
        cov_matrix=cov,
        horizon_days=1,
        num_paths=10000,
        seed=42,
        distribution=DistributionModel.MULTIVARIATE_STUDENT_T,
        degrees_of_freedom=3.5,
    )

    # Kurtosis of Student-t with nu=3.5 should exceed normal (kurtosis > 3.0)
    flat_norm = sim_norm[:, 0, 0]
    flat_t = sim_t[:, 0, 0]

    # Extreme tail values: Student-t max absolute loss/gain should exceed normal
    assert np.max(np.abs(flat_t)) > np.max(np.abs(flat_norm))
    # Variance should still be approximately equal to cov[0, 0]
    assert math.isclose(np.var(flat_t), cov[0, 0], rel_tol=0.25)


def test_non_psd_covariance_spectral_projection():
    """Verifies that non-positive-semidefinite covariance matrix is projected to PSD cone."""
    # Construct invalid covariance matrix with negative eigenvalue
    invalid_cov = np.array([
        [1.0, 0.9, 0.9],
        [0.9, 1.0, -0.9],
        [0.9, -0.9, 1.0],
    ]) * 0.0004

    min_eig_before = float(np.min(np.linalg.eigvalsh(invalid_cov)))
    assert min_eig_before < 0.0

    psd_cov, was_projected = project_covariance_psd(invalid_cov)
    assert was_projected is True
    min_eig_after = float(np.min(np.linalg.eigvalsh(psd_cov)))
    assert min_eig_after >= 0.0

    # Simulation runs without throwing LinAlgError
    mu = np.zeros(3)
    returns, warnings = generate_multivariate_returns(
        mean_vector=mu,
        cov_matrix=invalid_cov,
        horizon_days=5,
        num_paths=50,
        seed=77,
    )
    assert returns.shape == (50, 5, 3)
    assert len(warnings) > 0


def test_portfolio_wealth_compounding_buy_and_hold_vs_constant_weights():
    """
    Verifies portfolio wealth compounding mechanics under:
    1. Buy-and-hold (natural drift)
    2. Constant-weights rebalancing
    """
    v0 = 100000.0
    weights = np.array([0.6, 0.4])  # fully invested

    # Deterministic 2-day returns for 1 path:
    # Day 1: Asset 0 +10%, Asset 1 -10%
    # Day 2: Asset 0 -10%, Asset 1 +10%
    returns = np.array([
        [
            [0.10, -0.10],
            [-0.10, 0.10],
        ]
    ])  # shape (1, 2, 2)

    # 1. Buy and hold:
    # Day 0: Asset 0 = 60,000, Asset 1 = 40,000. Total = 100,000.
    # Day 1: Asset 0 = 66,000, Asset 1 = 36,000. Total = 102,000.
    # Day 2: Asset 0 = 66,000 * 0.90 = 59,400. Asset 1 = 36,000 * 1.10 = 39,600. Total = 99,000.
    bh_paths = simulate_portfolio_wealth(
        initial_capital=v0,
        asset_weights=weights,
        simulated_returns=returns,
        rebalance_policy=RebalancePolicy.BUY_AND_HOLD,
    )
    assert math.isclose(bh_paths[0, 0], 100000.0)
    assert math.isclose(bh_paths[0, 1], 102000.0)
    assert math.isclose(bh_paths[0, 2], 99000.0)

    # 2. Constant weights:
    # Day 0: 100,000
    # Day 1 port return: 0.6*0.10 + 0.4*(-0.10) = 0.02 (+2%) -> 102,000.
    # Day 2 port return: 0.6*(-0.10) + 0.4*(0.10) = -0.02 (-2%) -> 102,000 * (1 - 0.02) = 99,960.
    cw_paths = simulate_portfolio_wealth(
        initial_capital=v0,
        asset_weights=weights,
        simulated_returns=returns,
        rebalance_policy=RebalancePolicy.CONSTANT_WEIGHTS,
    )
    assert math.isclose(cw_paths[0, 0], 100000.0)
    assert math.isclose(cw_paths[0, 1], 102000.0)
    assert math.isclose(cw_paths[0, 2], 99960.0)


def test_downsample_trajectories_and_histogram():
    """Verifies that trajectory summaries and histogram bins are created correctly."""
    wealth = np.random.uniform(90000.0, 110000.0, size=(100, 10))

    trajectory = downsample_trajectories(wealth, max_sample_paths=15)
    assert len(trajectory) == 10
    assert len(trajectory[0].sample_paths) == 15
    assert trajectory[0].median_value >= trajectory[0].percentile_5
    assert trajectory[0].percentile_95 >= trajectory[0].median_value

    bins = compute_distribution_histogram(wealth[:, -1], num_bins=20)
    assert len(bins) == 20
    assert sum(b.count for b in bins) == 100
    assert math.isclose(sum(b.relative_frequency for b in bins), 1.0, abs_tol=1e-5)
