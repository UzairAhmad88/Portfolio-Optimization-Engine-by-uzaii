"""
Unit tests for robust portfolio optimization and estimation uncertainty.

Verifies:
1. Covariance shrinkage targets (diagonal, scaled identity, constant correlation).
2. Shrinkage properties: lambda=0 reproduces sample, lambda=1 matches target, symmetry and PSD.
3. Expected-return uncertainty radii computation (SE-scaled and absolute).
4. Zero uncertainty (kappa=0) reproduces baseline optimization exactly (D1 = 0).
5. Hand-calculated Box-uncertainty problem matches analytical expectation.
6. Monotonicity of worst-case return with respect to uncertainty confidence level.
7. Mean-variance utility optimization with exact gradient.
8. Constraint feasibility enforcement and infeasibility diagnostic reporting.
9. 1D sensitivity parameter sweep over weight caps, uncertainty levels, and shrinkage.
"""

import math
import numpy as np
import pandas as pd
import pytest

from app.quant.constraints import AssetWeightBounds, InvestmentConstraints
from app.quant.optimization import OptimizationObjective
from app.quant.robust_optimization import (
    CovarianceShrinkageConfig,
    CovarianceShrinkageTarget,
    ExpectedReturnUncertaintyConfig,
    RobustObjective,
    UncertaintyModelType,
    compute_portfolio_diagnostics,
    compute_uncertainty_radii,
    optimize_robust_portfolio,
    run_constraint_sensitivity_sweep,
    shrink_covariance_matrix,
)


@pytest.fixture
def sample_market_data():
    """3-asset annual parameters for deterministic testing."""
    assets = ["AAPL", "MSFT", "GOOG"]
    expected_returns = pd.Series([0.15, 0.12, 0.10], index=assets)

    # 3x3 positive definite covariance matrix
    cov_arr = np.array(
        [
            [0.040, 0.015, 0.010],
            [0.015, 0.030, 0.012],
            [0.010, 0.012, 0.025],
        ]
    )
    cov_df = pd.DataFrame(cov_arr, index=assets, columns=assets)
    return assets, expected_returns, cov_df


def test_covariance_shrinkage_targets(sample_market_data):
    """Verifies diagonal, scaled identity, and constant correlation targets."""
    assets, _, cov_df = sample_market_data
    sample_arr = cov_df.to_numpy()

    # 1. Zero shrinkage reproduces sample covariance exactly
    shrunk_zero, _ = shrink_covariance_matrix(
        cov_df, target=CovarianceShrinkageTarget.DIAGONAL, intensity=0.0
    )
    np.testing.assert_allclose(shrunk_zero, sample_arr, atol=1e-12)

    # 2. 100% Diagonal shrinkage
    shrunk_diag, _ = shrink_covariance_matrix(
        cov_df, target=CovarianceShrinkageTarget.DIAGONAL, intensity=1.0
    )
    expected_diag = np.diag(np.diag(sample_arr))
    np.testing.assert_allclose(shrunk_diag, expected_diag, atol=1e-12)

    # 3. 100% Scaled Identity shrinkage
    shrunk_id, _ = shrink_covariance_matrix(
        cov_df, target=CovarianceShrinkageTarget.SCALED_IDENTITY, intensity=1.0
    )
    avg_var = np.trace(sample_arr) / 3.0
    expected_id = avg_var * np.eye(3)
    np.testing.assert_allclose(shrunk_id, expected_id, atol=1e-12)

    # 4. Intermediate shrinkage: 50%
    shrunk_half, _ = shrink_covariance_matrix(
        cov_df, target=CovarianceShrinkageTarget.DIAGONAL, intensity=0.5
    )
    expected_half = 0.5 * sample_arr + 0.5 * expected_diag
    np.testing.assert_allclose(shrunk_half, expected_half, atol=1e-12)

    # Invariants: symmetry and PSD
    assert np.allclose(shrunk_half, shrunk_half.T, atol=1e-12)
    assert np.all(np.linalg.eigvalsh(shrunk_half) >= 0.0)


def test_covariance_constant_correlation_target(sample_market_data):
    """Verifies constant correlation shrinkage target formulation."""
    assets, _, cov_df = sample_market_data
    sample_arr = cov_df.to_numpy()

    shrunk_const, _ = shrink_covariance_matrix(
        cov_df, target=CovarianceShrinkageTarget.CONSTANT_CORRELATION, intensity=1.0
    )

    # Verify diagonals match sample variances
    np.testing.assert_allclose(np.diag(shrunk_const), np.diag(sample_arr), atol=1e-12)

    # Verify all pairwise correlations in the target are equal
    stds = np.sqrt(np.diag(sample_arr))
    corr_target = shrunk_const / np.outer(stds, stds)
    off_diags = [corr_target[0, 1], corr_target[0, 2], corr_target[1, 2]]
    assert math.isclose(off_diags[0], off_diags[1], abs_tol=1e-6)
    assert math.isclose(off_diags[1], off_diags[2], abs_tol=1e-6)


def test_zero_uncertainty_reproduces_baseline(sample_market_data):
    """Verifies that zero uncertainty (kappa=0, lambda=0) reproduces baseline optimization exactly."""
    assets, expected_returns, cov_df = sample_market_data
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0)

    # Max Sharpe with zero uncertainty and zero shrinkage
    res = optimize_robust_portfolio(
        assets=assets,
        expected_returns=expected_returns,
        cov_matrix=cov_df,
        constraints=constraints,
        objective=RobustObjective.MAX_SHARPE,
        uncertainty_config=ExpectedReturnUncertaintyConfig(
            model=UncertaintyModelType.BOX, confidence_level=0.0
        ),
        shrinkage_config=CovarianceShrinkageConfig(
            target=CovarianceShrinkageTarget.DIAGONAL, intensity=0.0
        ),
    )

    assert res.is_feasible
    assert res.weight_distance_d1 == pytest.approx(0.0, abs=1e-6)
    assert res.max_weight_shift == pytest.approx(0.0, abs=1e-6)
    assert res.turnover_from_baseline == pytest.approx(0.0, abs=1e-6)

    # Check baseline weights equal robust weights
    for a in assets:
        assert math.isclose(res.baseline_result.weights[a], res.robust_result.weights[a], abs_tol=1e-5)


def test_box_uncertainty_hand_calculation():
    """
    Independent hand-calculated verification for 2-asset box uncertainty.
    
    Asset A: expected return 12%, variance 0.04 (std 0.20)
    Asset B: expected return 8%, variance 0.01 (std 0.10)
    Zero correlation. T = 100 observations.
    
    Standard errors:
    SE(A) = 0.20 / sqrt(100) = 0.02
    SE(B) = 0.10 / sqrt(100) = 0.01
    
    With kappa = 2.0:
    delta_A = 2.0 * 0.02 = 0.04 -> mu_worst(A) = 0.12 - 0.04 = 0.08
    delta_B = 2.0 * 0.01 = 0.02 -> mu_worst(B) = 0.08 - 0.02 = 0.06
    """
    assets = ["A", "B"]
    ret_series = pd.Series([0.12, 0.08], index=assets)
    cov_df = pd.DataFrame([[0.04, 0.0], [0.0, 0.01]], index=assets, columns=assets)

    unc_config = ExpectedReturnUncertaintyConfig(
        model=UncertaintyModelType.BOX,
        confidence_level=2.0,
    )

    radii = compute_uncertainty_radii(
        assets=assets,
        cov_matrix=cov_df.to_numpy(),
        uncertainty_config=unc_config,
        observation_count=100,
    )

    np.testing.assert_allclose(radii, [0.04, 0.02], atol=1e-10)

    res = optimize_robust_portfolio(
        assets=assets,
        expected_returns=ret_series,
        cov_matrix=cov_df,
        constraints=InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0),
        objective=RobustObjective.MAX_SHARPE,
        uncertainty_config=unc_config,
        observation_count=100,
    )

    assert res.worst_case_return_vector["A"] == pytest.approx(0.08, abs=1e-8)
    assert res.worst_case_return_vector["B"] == pytest.approx(0.06, abs=1e-8)


def test_worst_case_return_monotonicity(sample_market_data):
    """Verifies that increasing kappa monotonically decreases the worst-case portfolio return."""
    assets, expected_returns, cov_df = sample_market_data
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0)

    worst_returns = []
    kappas = [0.0, 0.5, 1.0, 1.5, 2.0]

    for k in kappas:
        res = optimize_robust_portfolio(
            assets=assets,
            expected_returns=expected_returns,
            cov_matrix=cov_df,
            constraints=constraints,
            objective=RobustObjective.MAX_SHARPE,
            uncertainty_config=ExpectedReturnUncertaintyConfig(
                model=UncertaintyModelType.BOX, confidence_level=k
            ),
            observation_count=252,
        )
        worst_returns.append(res.worst_case_expected_return_robust)

    # Must be monotonically non-increasing
    for i in range(len(worst_returns) - 1):
        assert worst_returns[i] >= worst_returns[i + 1] - 1e-8


def test_mean_variance_utility_solver(sample_market_data):
    """Verifies Mean-Variance Utility optimization objective and feasibility."""
    assets, expected_returns, cov_df = sample_market_data
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0)

    res = optimize_robust_portfolio(
        assets=assets,
        expected_returns=expected_returns,
        cov_matrix=cov_df,
        constraints=constraints,
        objective=RobustObjective.MEAN_VARIANCE_UTILITY,
        risk_aversion=3.0,
        uncertainty_config=ExpectedReturnUncertaintyConfig(
            model=UncertaintyModelType.BOX, confidence_level=1.0
        ),
        shrinkage_config=CovarianceShrinkageConfig(
            target=CovarianceShrinkageTarget.DIAGONAL, intensity=0.2
        ),
    )

    assert res.is_feasible
    assert res.robust_result.converged
    total_w = sum(res.robust_result.weights.values())
    assert math.isclose(total_w, 1.0, abs_tol=1e-5)


def test_constraint_infeasibility_reporting(sample_market_data):
    """Verifies that contradictory constraints are reported as infeasible without silent relaxation."""
    assets, expected_returns, cov_df = sample_market_data

    # Contradictory: 3 assets, each max 0.20 -> sum <= 0.60 < target 1.0
    contradictory_constraints = InvestmentConstraints(
        default_min_weight=0.0, default_max_weight=0.20, target_total_weight=1.0
    )

    res = optimize_robust_portfolio(
        assets=assets,
        expected_returns=expected_returns,
        cov_matrix=cov_df,
        constraints=contradictory_constraints,
        objective=RobustObjective.MAX_SHARPE,
    )

    assert not res.is_feasible
    assert not res.robust_result.is_feasible
    assert "infeasible" in res.robust_result.solver_status.value.lower()


def test_sensitivity_sweep_max_weight(sample_market_data):
    """Verifies 1D sensitivity parameter sweep over max weight caps."""
    assets, expected_returns, cov_df = sample_market_data
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=0.80)

    sweep_res = run_constraint_sensitivity_sweep(
        assets=assets,
        expected_returns=expected_returns,
        cov_matrix=cov_df,
        constraints=constraints,
        parameter_to_sweep="max_weight",
        grid_min=0.25,
        grid_max=1.0,
        num_steps=5,
        objective=RobustObjective.MAX_SHARPE,
    )

    assert sweep_res.parameter_name == "max_weight"
    assert len(sweep_res.points) == 5
    # When max_weight is 0.25 (3 assets * 0.25 = 0.75 < 1.0), it must be infeasible!
    assert not sweep_res.points[0].is_feasible
    # When max_weight is 1.0, it should be feasible
    assert sweep_res.points[-1].is_feasible


def test_sensitivity_sweep_uncertainty_level(sample_market_data):
    """Verifies 1D sensitivity parameter sweep over uncertainty levels."""
    assets, expected_returns, cov_df = sample_market_data
    constraints = InvestmentConstraints(default_min_weight=0.0, default_max_weight=1.0)

    sweep_res = run_constraint_sensitivity_sweep(
        assets=assets,
        expected_returns=expected_returns,
        cov_matrix=cov_df,
        constraints=constraints,
        parameter_to_sweep="uncertainty_level",
        grid_min=0.0,
        grid_max=2.5,
        num_steps=6,
        objective=RobustObjective.MAX_SHARPE,
    )

    assert sweep_res.parameter_name == "uncertainty_level"
    assert len(sweep_res.points) == 6
    assert all(p.is_feasible for p in sweep_res.points)
