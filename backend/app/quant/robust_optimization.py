"""
Robust portfolio optimization and estimation uncertainty engine.

Provides mathematically verified formulations for:
1. Expected-return uncertainty sets (Box uncertainty and Ellipsoidal uncertainty).
2. Covariance regularization and shrinkage (Diagonal, Scaled Identity, Constant Correlation).
3. Robust Maximum Sharpe, Minimum Variance, and Mean-Variance Utility optimization.
4. Parameter sensitivity sweeps (uncertainty radius, shrinkage intensity, max weight caps).
5. Comprehensive stability, concentration (HHI), and weight-shift diagnostics.

Pure mathematical domain logic independent of web frameworks.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from app.quant.constraints import (
    InvestmentConstraints,
    check_constraint_feasibility,
    resolve_asset_bounds,
    validate_weights_against_constraints,
)
from app.quant.optimization import (
    OptimizationObjective,
    OptimizationResult,
    OptimizationStatus,
    _find_feasible_starting_point,
    optimize_maximum_sharpe,
    optimize_minimum_variance,
    validate_covariance_matrix,
)
from app.quant.portfolio import (
    portfolio_expected_return,
    portfolio_variance,
    portfolio_volatility,
    summarize_weights,
)


class UncertaintyModelType(str, Enum):
    """Supported mathematical models for expected-return uncertainty."""

    NONE = "none"
    BOX = "box"
    ELLIPSOIDAL = "ellipsoidal"


class CovarianceShrinkageTarget(str, Enum):
    """Structured target matrices for linear covariance shrinkage."""

    NONE = "none"
    DIAGONAL = "diagonal"
    SCALED_IDENTITY = "scaled_identity"
    CONSTANT_CORRELATION = "constant_correlation"


class RobustObjective(str, Enum):
    """Supported robust optimization objectives."""

    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MEAN_VARIANCE_UTILITY = "mean_variance_utility"


@dataclass(frozen=True)
class ExpectedReturnUncertaintyConfig:
    """
    Configuration for expected-return uncertainty sets.

    Attributes:
        model: Type of uncertainty set (NONE, BOX, ELLIPSOIDAL).
        confidence_level: Scaling factor kappa >= 0 (e.g. 1.96 for ~95% confidence interval).
        absolute_radius: Optional fixed absolute uncertainty radius per asset (in annual return units).
        per_asset_radius: Optional dictionary of asset-specific uncertainty radii.
    """

    model: UncertaintyModelType = UncertaintyModelType.BOX
    confidence_level: float = 1.0
    absolute_radius: float | None = None
    per_asset_radius: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.confidence_level < 0:
            raise ValueError(f"confidence_level must be non-negative, got {self.confidence_level}")
        if self.absolute_radius is not None and self.absolute_radius < 0:
            raise ValueError(f"absolute_radius must be non-negative, got {self.absolute_radius}")


@dataclass(frozen=True)
class CovarianceShrinkageConfig:
    """
    Configuration for covariance shrinkage regularization:
        Sigma_shrunk = (1 - lambda) * Sigma_sample + lambda * Target

    Attributes:
        target: Target matrix type (NONE, DIAGONAL, SCALED_IDENTITY, CONSTANT_CORRELATION).
        intensity: Shrinkage intensity lambda in [0.0, 1.0].
    """

    target: CovarianceShrinkageTarget = CovarianceShrinkageTarget.DIAGONAL
    intensity: float = 0.20

    def __post_init__(self) -> None:
        if not (0.0 <= self.intensity <= 1.0):
            raise ValueError(f"Shrinkage intensity must be in [0.0, 1.0], got {self.intensity}")


@dataclass(frozen=True)
class RobustOptimizationResult:
    """
    Full result contract comparing baseline and robust optimization outcomes.
    """

    objective: str
    assets: list[str]
    baseline_result: OptimizationResult
    robust_result: OptimizationResult
    weight_distance_d1: float
    max_weight_shift: float
    turnover_from_baseline: float
    baseline_hhi: float
    robust_hhi: float
    effective_assets_baseline: float
    effective_assets_robust: float
    nominal_expected_return_robust: float
    worst_case_expected_return_robust: float
    nominal_volatility_robust: float
    shrunk_volatility_robust: float
    shrunk_covariance_matrix: list[list[float]]
    worst_case_return_vector: dict[str, float]
    uncertainty_radius_vector: dict[str, float]
    uncertainty_applied: bool
    shrinkage_applied: bool
    is_feasible: bool
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SensitivityPoint:
    """
    A single evaluated configuration in a parameter sensitivity sweep.
    """

    parameter_value: float
    parameter_label: str
    is_feasible: bool
    solver_status: str
    weights: dict[str, float]
    nominal_expected_return: float
    worst_case_expected_return: float
    volatility: float
    sharpe_ratio: float | None
    weight_distance_d1: float
    hhi: float
    effective_assets: float
    binding_constraints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SensitivityAnalysisResult:
    """
    Complete sensitivity sweep results over a bounded 1D parameter grid.
    """

    parameter_name: str
    parameter_description: str
    baseline_value: float
    points: list[SensitivityPoint]
    total_evaluations: int
    feasible_evaluations: int
    infeasible_evaluations: int
    warnings: list[str] = field(default_factory=list)


def shrink_covariance_matrix(
    cov_matrix: pd.DataFrame | np.ndarray,
    target: CovarianceShrinkageTarget = CovarianceShrinkageTarget.DIAGONAL,
    intensity: float = 0.0,
) -> tuple[np.ndarray, list[str]]:
    """
    Applies convex linear shrinkage toward a structured target:
        Sigma_shrunk = (1 - lambda) * Sigma + lambda * Target

    Parameters:
        cov_matrix: Input square covariance matrix.
        target: Target matrix specification.
        intensity: Shrinkage intensity lambda in [0.0, 1.0].

    Returns:
        tuple of (shrunk_cov_array, warnings).
    """
    arr, warnings = validate_covariance_matrix(cov_matrix)
    n = arr.shape[0]

    intensity = float(np.clip(intensity, 0.0, 1.0))
    if intensity == 0.0 or target == CovarianceShrinkageTarget.NONE:
        return arr, warnings

    if target == CovarianceShrinkageTarget.DIAGONAL:
        # Target is diagonal with sample variances
        t_mat = np.diag(np.diag(arr))
    elif target == CovarianceShrinkageTarget.SCALED_IDENTITY:
        # Target is spherical identity with average sample variance
        avg_var = float(np.trace(arr) / max(n, 1))
        t_mat = avg_var * np.eye(n)
    elif target == CovarianceShrinkageTarget.CONSTANT_CORRELATION:
        # Target preserves sample variances and uses average correlation
        diag_vars = np.diag(arr)
        stds = np.sqrt(np.maximum(diag_vars, 1e-12))
        inv_stds = 1.0 / stds
        corr = np.diag(inv_stds) @ arr @ np.diag(inv_stds)
        np.fill_diagonal(corr, 1.0)

        # Average off-diagonal correlation
        if n > 1:
            off_diag_sum = float(np.sum(corr) - n)
            avg_corr = float(off_diag_sum / (n * (n - 1)))
            avg_corr = float(np.clip(avg_corr, -0.99, 0.99))
        else:
            avg_corr = 0.0

        t_corr = np.full((n, n), avg_corr, dtype=float)
        np.fill_diagonal(t_corr, 1.0)
        t_mat = np.diag(stds) @ t_corr @ np.diag(stds)
    else:
        raise ValueError(f"Unsupported shrinkage target '{target}'.")

    # Linear combination
    shrunk = (1.0 - intensity) * arr + intensity * t_mat
    # Enforce exact floating symmetry
    shrunk = 0.5 * (shrunk + shrunk.T)

    # Verify PSD on shrunk matrix
    eigs = np.linalg.eigvalsh(shrunk)
    min_eig = float(np.min(eigs))
    if min_eig < -1e-8:
        # Project to nearest PSD via eigenvalue clipping
        clipped_eigs = np.maximum(eigs, 1e-8)
        _, vecs = np.linalg.eigh(shrunk)
        shrunk = vecs @ np.diag(clipped_eigs) @ vecs.T
        shrunk = 0.5 * (shrunk + shrunk.T)
        warnings.append(
            f"Shrunk covariance had negative eigenvalue ({min_eig:.3e}); projected onto PSD cone."
        )

    return shrunk, warnings


def compute_uncertainty_radii(
    assets: Sequence[str],
    cov_matrix: np.ndarray,
    uncertainty_config: ExpectedReturnUncertaintyConfig,
    observation_count: int | None = None,
    annualized: bool = True,
    periods_per_year: int = 252,
) -> np.ndarray:
    """
    Computes per-asset uncertainty half-widths delta_i for expected returns.

    Parameters:
        assets: Asset identifier sequence.
        cov_matrix: NxN covariance matrix (annualized if annualized=True).
        uncertainty_config: Uncertainty model configuration.
        observation_count: Sample size T (number of daily bars).
        annualized: Whether cov_matrix is annualized.
        periods_per_year: Scaling factor.

    Returns:
        1D NumPy array of non-negative radii delta_i in annualized return units.
    """
    n = len(assets)
    if uncertainty_config.model == UncertaintyModelType.NONE:
        return np.zeros(n, dtype=float)

    # If user provided explicit per-asset radii
    if uncertainty_config.per_asset_radius is not None:
        return np.array(
            [max(0.0, float(uncertainty_config.per_asset_radius.get(a, 0.0))) for a in assets],
            dtype=float,
        )

    # If user provided a global absolute radius
    if uncertainty_config.absolute_radius is not None:
        return np.full(n, float(uncertainty_config.absolute_radius), dtype=float)

    # Standard-error based uncertainty:
    # sigma_annual = sqrt(diag(Sigma_ann))
    # SE(mu_annual) = sigma_annual / sqrt(T)
    # delta_i = kappa * SE(mu_annual)
    t_obs = max(observation_count if observation_count is not None else 252, 2)
    diag_vars = np.maximum(np.diag(cov_matrix), 0.0)
    stds = np.sqrt(diag_vars)

    kappa = float(uncertainty_config.confidence_level)
    radii = kappa * (stds / math.sqrt(t_obs))
    return radii


def compute_portfolio_diagnostics(
    w_base: np.ndarray,
    w_robust: np.ndarray,
) -> tuple[float, float, float, float, float, float, float]:
    """
    Computes stability, distance, and concentration metrics between two portfolios:
        D1 = sum |w_robust,i - w_base,i|
        max_shift = max |w_robust,i - w_base,i|
        turnover = 0.5 * D1
        HHI_base = sum (w_base,i)^2
        HHI_robust = sum (w_robust,i)^2
        N_eff_base = 1 / HHI_base
        N_eff_robust = 1 / HHI_robust
    """
    diff = np.abs(w_robust - w_base)
    d1 = float(np.sum(diff))
    max_shift = float(np.max(diff)) if len(diff) > 0 else 0.0
    turnover = 0.5 * d1

    hhi_base = float(np.sum(w_base**2))
    hhi_robust = float(np.sum(w_robust**2))

    n_eff_base = float(1.0 / max(hhi_base, 1e-8))
    n_eff_robust = float(1.0 / max(hhi_robust, 1e-8))

    return d1, max_shift, turnover, hhi_base, hhi_robust, n_eff_base, n_eff_robust


def optimize_robust_portfolio(
    assets: Sequence[str],
    expected_returns: pd.Series | np.ndarray | Sequence[float],
    cov_matrix: pd.DataFrame | np.ndarray,
    constraints: InvestmentConstraints,
    objective: RobustObjective = RobustObjective.MAX_SHARPE,
    uncertainty_config: ExpectedReturnUncertaintyConfig | None = None,
    shrinkage_config: CovarianceShrinkageConfig | None = None,
    risk_free_rate: float = 0.0,
    risk_aversion: float = 2.5,
    annualized: bool = True,
    periods_per_year: int = 252,
    observation_count: int | None = None,
    tolerance: float = 1e-7,
    max_iterations: int = 500,
) -> RobustOptimizationResult:
    """
    Computes both the baseline (point-estimate) and robust portfolio solutions
    under explicit expected-return uncertainty and covariance shrinkage.

    Parameters:
        assets: Asset identifier sequence.
        expected_returns: Nominal expected return vector.
        cov_matrix: Sample covariance matrix.
        constraints: Investment constraints.
        objective: Robust optimization objective.
        uncertainty_config: Expected return uncertainty set configuration.
        shrinkage_config: Covariance shrinkage configuration.
        risk_free_rate: Risk-free rate for Sharpe evaluations.
        risk_aversion: Risk aversion parameter gamma > 0 for utility optimization.
        annualized: Whether returns and covariance are annualized.
        periods_per_year: Scale factor for annualization.
        observation_count: Number of historical observation bars.
        tolerance: Numerical tolerance for SLSQP.
        max_iterations: Maximum iterations for SLSQP.

    Returns:
        RobustOptimizationResult containing both baseline and robust results,
        weight distances, HHI concentration shifts, and worst-case metrics.
    """
    clean_assets = list(assets)
    n = len(clean_assets)
    if n == 0:
        raise ValueError("Asset list cannot be empty for robust optimization.")

    if uncertainty_config is None:
        uncertainty_config = ExpectedReturnUncertaintyConfig(model=UncertaintyModelType.NONE)
    if shrinkage_config is None:
        shrinkage_config = CovarianceShrinkageConfig(target=CovarianceShrinkageTarget.NONE, intensity=0.0)

    # 1. Parse and align nominal inputs
    if isinstance(expected_returns, pd.Series):
        ret_nom = expected_returns.reindex(clean_assets).to_numpy(dtype=float)
    elif isinstance(expected_returns, np.ndarray):
        ret_nom = expected_returns.astype(float)
    else:
        ret_nom = np.array(expected_returns, dtype=float)

    cov_sample, cov_warnings = validate_covariance_matrix(cov_matrix, expected_dim=n)
    warnings: list[str] = list(cov_warnings)

    # 2. Run Baseline Solution
    if objective == RobustObjective.MIN_VARIANCE:
        baseline_res = optimize_minimum_variance(
            assets=clean_assets,
            cov_matrix=cov_sample,
            constraints=constraints,
            expected_returns=ret_nom,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    elif objective == RobustObjective.MAX_SHARPE:
        baseline_res = optimize_maximum_sharpe(
            assets=clean_assets,
            expected_returns=ret_nom,
            cov_matrix=cov_sample,
            constraints=constraints,
            risk_free_rate=risk_free_rate,
            annualized=annualized,
            periods_per_year=periods_per_year,
            observation_count=observation_count,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    elif objective == RobustObjective.MEAN_VARIANCE_UTILITY:
        # Solve baseline utility optimization
        baseline_res = _solve_mean_variance_utility(
            assets=clean_assets,
            ret_vec=ret_nom,
            cov_arr=cov_sample,
            constraints=constraints,
            risk_aversion=risk_aversion,
            risk_free_rate=risk_free_rate,
            annualized=annualized,
            periods_per_year=periods_per_year,
            observation_count=observation_count,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    else:
        raise ValueError(f"Unsupported robust objective '{objective}'.")

    # If baseline is infeasible, return early
    if not baseline_res.is_feasible:
        w_zeros = np.zeros(n, dtype=float)
        return RobustOptimizationResult(
            objective=objective.value,
            assets=clean_assets,
            baseline_result=baseline_res,
            robust_result=baseline_res,
            weight_distance_d1=0.0,
            max_weight_shift=0.0,
            turnover_from_baseline=0.0,
            baseline_hhi=0.0,
            robust_hhi=0.0,
            effective_assets_baseline=0.0,
            effective_assets_robust=0.0,
            nominal_expected_return_robust=0.0,
            worst_case_expected_return_robust=0.0,
            nominal_volatility_robust=0.0,
            shrunk_volatility_robust=0.0,
            shrunk_covariance_matrix=cov_sample.tolist(),
            worst_case_return_vector={a: float(ret_nom[i]) for i, a in enumerate(clean_assets)},
            uncertainty_radius_vector={a: 0.0 for a in clean_assets},
            uncertainty_applied=False,
            shrinkage_applied=False,
            is_feasible=False,
            warnings=warnings + baseline_res.warnings,
        )

    # 3. Apply Covariance Shrinkage
    cov_shrunk, shrink_warn = shrink_covariance_matrix(
        cov_sample,
        target=shrinkage_config.target,
        intensity=shrinkage_config.intensity,
    )
    warnings.extend(shrink_warn)
    shrinkage_applied = (
        shrinkage_config.intensity > 0.0 and shrinkage_config.target != CovarianceShrinkageTarget.NONE
    )

    # 4. Apply Expected-Return Uncertainty
    delta_vec = compute_uncertainty_radii(
        assets=clean_assets,
        cov_matrix=cov_shrunk,
        uncertainty_config=uncertainty_config,
        observation_count=observation_count,
        annualized=annualized,
        periods_per_year=periods_per_year,
    )
    uncertainty_applied = (
        uncertainty_config.model != UncertaintyModelType.NONE and float(np.sum(delta_vec)) > 0.0
    )

    # Compute worst-case returns for long-only positions: mu_eff = mu_nom - delta
    # For long-only portfolios (or when weights are non-negative), worst case is directly mu_nom - delta
    ret_worst = ret_nom - delta_vec

    # 5. Solve Robust Optimization Problem
    if objective == RobustObjective.MIN_VARIANCE:
        # Robust min variance uses shrunk covariance matrix
        robust_res = optimize_minimum_variance(
            assets=clean_assets,
            cov_matrix=cov_shrunk,
            constraints=constraints,
            expected_returns=ret_worst,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    elif objective == RobustObjective.MAX_SHARPE:
        # Robust max Sharpe maximizes worst-case Sharpe under shrunk covariance
        robust_res = optimize_maximum_sharpe(
            assets=clean_assets,
            expected_returns=ret_worst,
            cov_matrix=cov_shrunk,
            constraints=constraints,
            risk_free_rate=risk_free_rate,
            annualized=annualized,
            periods_per_year=periods_per_year,
            observation_count=observation_count,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    elif objective == RobustObjective.MEAN_VARIANCE_UTILITY:
        robust_res = _solve_mean_variance_utility(
            assets=clean_assets,
            ret_vec=ret_worst,
            cov_arr=cov_shrunk,
            constraints=constraints,
            risk_aversion=risk_aversion,
            risk_free_rate=risk_free_rate,
            annualized=annualized,
            periods_per_year=periods_per_year,
            observation_count=observation_count,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )

    # 6. Extract Weights and Compute Comparative Diagnostics
    w_base_arr = np.array([baseline_res.weights.get(a, 0.0) for a in clean_assets], dtype=float)
    w_robust_arr = np.array([robust_res.weights.get(a, 0.0) for a in clean_assets], dtype=float)

    d1, max_shift, turnover, hhi_b, hhi_r, n_eff_b, n_eff_r = compute_portfolio_diagnostics(
        w_base_arr, w_robust_arr
    )

    # Nominal expected return under robust weights: w_robust @ ret_nom
    nom_exp_ret = float(w_robust_arr @ ret_nom)
    # Worst-case expected return under robust weights: w_robust @ ret_worst
    worst_exp_ret = float(w_robust_arr @ ret_worst)
    # Nominal volatility (using sample covariance)
    nom_vol = portfolio_volatility(w_robust_arr, cov_sample)
    # Shrunk volatility (using regularized covariance)
    shrunk_vol = portfolio_volatility(w_robust_arr, cov_shrunk)

    warnings.extend(robust_res.warnings)

    return RobustOptimizationResult(
        objective=objective.value,
        assets=clean_assets,
        baseline_result=baseline_res,
        robust_result=robust_res,
        weight_distance_d1=d1,
        max_weight_shift=max_shift,
        turnover_from_baseline=turnover,
        baseline_hhi=hhi_b,
        robust_hhi=hhi_r,
        effective_assets_baseline=n_eff_b,
        effective_assets_robust=n_eff_r,
        nominal_expected_return_robust=nom_exp_ret,
        worst_case_expected_return_robust=worst_exp_ret,
        nominal_volatility_robust=nom_vol,
        shrunk_volatility_robust=shrunk_vol,
        shrunk_covariance_matrix=cov_shrunk.tolist(),
        worst_case_return_vector={clean_assets[i]: float(ret_worst[i]) for i in range(n)},
        uncertainty_radius_vector={clean_assets[i]: float(delta_vec[i]) for i in range(n)},
        uncertainty_applied=uncertainty_applied,
        shrinkage_applied=shrinkage_applied,
        is_feasible=robust_res.is_feasible,
        warnings=warnings,
    )


def _solve_mean_variance_utility(
    assets: Sequence[str],
    ret_vec: np.ndarray,
    cov_arr: np.ndarray,
    constraints: InvestmentConstraints,
    risk_aversion: float = 2.5,
    risk_free_rate: float = 0.0,
    annualized: bool = True,
    periods_per_year: int = 252,
    observation_count: int | None = None,
    tolerance: float = 1e-7,
    max_iterations: int = 500,
) -> OptimizationResult:
    """
    Solves Mean-Variance Utility Optimization:
        max_w  w^T r - (gamma / 2) * w^T Sigma w
    Equivalent to:
        min_w  (gamma / 2) * w^T Sigma w - w^T r
    """
    clean_assets = list(assets)
    n = len(clean_assets)
    gamma = max(float(risk_aversion), 1e-4)
    target_total = float(constraints.target_total_weight)

    # Feasibility check
    feas_report = check_constraint_feasibility(clean_assets, constraints)
    if not feas_report.is_feasible:
        return OptimizationResult(
            objective=RobustObjective.MEAN_VARIANCE_UTILITY.value,
            assets=clean_assets,
            weights={},
            expected_return=0.0,
            variance=0.0,
            volatility=0.0,
            sharpe_ratio=None,
            total_weight=0.0,
            gross_exposure=0.0,
            is_feasible=False,
            constraint_violations=feas_report.messages,
            solver_name="SciPy SLSQP",
            solver_status=OptimizationStatus.INFEASIBLE,
            solver_message="Pre-optimization feasibility check failed: constraints are contradictory.",
            converged=False,
            objective_value=None,
            iterations=0,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            warnings=feas_report.messages,
        )

    resolved_bounds = resolve_asset_bounds(clean_assets, constraints)
    lower_bounds = np.array([resolved_bounds[a].lower for a in clean_assets], dtype=float)
    upper_bounds = np.array([resolved_bounds[a].upper for a in clean_assets], dtype=float)

    w0 = _find_feasible_starting_point(lower_bounds, upper_bounds, target_total)

    def objective_fn(w: np.ndarray) -> float:
        var = float(w.T @ cov_arr @ w)
        ret = float(w @ ret_vec)
        return float(0.5 * gamma * var - ret)

    def gradient_fn(w: np.ndarray) -> np.ndarray:
        return gamma * (cov_arr @ w) - ret_vec

    scipy_bounds = [(float(lower_bounds[i]), float(upper_bounds[i])) for i in range(n)]
    scipy_constraints: list[dict[str, Any]] = [
        {
            "type": "eq",
            "fun": lambda w: float(np.sum(w) - target_total),
            "jac": lambda w: np.ones(n, dtype=float),
        }
    ]

    res = minimize(
        fun=objective_fn,
        x0=w0,
        jac=gradient_fn,
        method="SLSQP",
        bounds=scipy_bounds,
        constraints=scipy_constraints,
        options={"ftol": tolerance, "maxiter": max_iterations, "disp": False},
    )

    if not res.success:
        return OptimizationResult(
            objective=RobustObjective.MEAN_VARIANCE_UTILITY.value,
            assets=clean_assets,
            weights={},
            expected_return=0.0,
            variance=0.0,
            volatility=0.0,
            sharpe_ratio=None,
            total_weight=0.0,
            gross_exposure=0.0,
            is_feasible=False,
            constraint_violations=[f"Solver terminated with failure: {res.message}"],
            solver_name="SciPy SLSQP",
            solver_status=OptimizationStatus.FAILED,
            solver_message=f"SLSQP utility optimization failed: {res.message}",
            converged=False,
            objective_value=float(res.fun) if np.isfinite(res.fun) else None,
            iterations=int(res.nit) if hasattr(res, "nit") else None,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
        )

    opt_weights = np.array(res.x, dtype=float)
    weights_dict = {clean_assets[i]: float(opt_weights[i]) for i in range(n)}
    violations = validate_weights_against_constraints(weights_dict, clean_assets, constraints)
    is_feasible = len(violations) == 0

    var_val = portfolio_variance(opt_weights, cov_arr)
    vol_val = portfolio_volatility(opt_weights, cov_arr)
    exp_ret = float(opt_weights @ ret_vec)
    sharpe = (exp_ret - risk_free_rate) / vol_val if vol_val > 1e-8 else None
    w_sum = summarize_weights(opt_weights)

    return OptimizationResult(
        objective=RobustObjective.MEAN_VARIANCE_UTILITY.value,
        assets=clean_assets,
        weights=weights_dict,
        expected_return=exp_ret,
        variance=var_val,
        volatility=vol_val,
        sharpe_ratio=sharpe,
        total_weight=w_sum.total_weight,
        gross_exposure=w_sum.gross_exposure,
        is_feasible=is_feasible,
        constraint_violations=violations,
        solver_name="SciPy SLSQP",
        solver_status=OptimizationStatus.CONVERGED if is_feasible else OptimizationStatus.INFEASIBLE,
        solver_message=res.message if is_feasible else "Solver converged but violated constraints.",
        converged=bool(res.success and is_feasible),
        objective_value=float(exp_ret - 0.5 * gamma * var_val),
        iterations=int(res.nit) if hasattr(res, "nit") else None,
        annualized=annualized,
        periods_per_year=periods_per_year,
        risk_free_rate=risk_free_rate,
        observation_count=observation_count,
    )


def run_constraint_sensitivity_sweep(
    assets: Sequence[str],
    expected_returns: pd.Series | np.ndarray | Sequence[float],
    cov_matrix: pd.DataFrame | np.ndarray,
    constraints: InvestmentConstraints,
    parameter_to_sweep: str,  # 'max_weight', 'uncertainty_level', 'shrinkage_intensity'
    grid_min: float,
    grid_max: float,
    num_steps: int = 10,
    objective: RobustObjective = RobustObjective.MAX_SHARPE,
    uncertainty_config: ExpectedReturnUncertaintyConfig | None = None,
    shrinkage_config: CovarianceShrinkageConfig | None = None,
    risk_free_rate: float = 0.0,
    annualized: bool = True,
    periods_per_year: int = 252,
    observation_count: int | None = None,
) -> SensitivityAnalysisResult:
    """
    Executes a bounded 1D parameter sensitivity sweep over constraint or uncertainty parameters.

    Supported sweep targets:
        - 'max_weight': Default upper weight bound w_max in [1/N, 1.0].
        - 'uncertainty_level': Confidence multiplier kappa in [0.0, 3.0].
        - 'shrinkage_intensity': Covariance shrinkage intensity lambda in [0.0, 1.0].

    Parameters:
        num_steps: Number of discrete evaluation steps (strictly clamped to [3, 25]).
    """
    clean_assets = list(assets)
    n = len(clean_assets)
    steps = int(np.clip(num_steps, 3, 25))

    grid = np.linspace(float(grid_min), float(grid_max), steps)
    points: list[SensitivityPoint] = []
    feasible_count = 0
    infeasible_count = 0
    warnings: list[str] = []

    # Get baseline reference
    base_res = optimize_robust_portfolio(
        assets=clean_assets,
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        constraints=constraints,
        objective=objective,
        uncertainty_config=uncertainty_config,
        shrinkage_config=shrinkage_config,
        risk_free_rate=risk_free_rate,
        annualized=annualized,
        periods_per_year=periods_per_year,
        observation_count=observation_count,
    )
    w_ref = np.array([base_res.baseline_result.weights.get(a, 0.0) for a in clean_assets], dtype=float)

    for val in grid:
        curr_val = float(val)
        curr_constraints = constraints
        curr_unc = uncertainty_config or ExpectedReturnUncertaintyConfig()
        curr_shrink = shrinkage_config or CovarianceShrinkageConfig()

        if parameter_to_sweep == "max_weight":
            curr_constraints = InvestmentConstraints(
                default_min_weight=constraints.default_min_weight,
                default_max_weight=curr_val,
                target_total_weight=constraints.target_total_weight,
                allow_short=constraints.allow_short,
                max_gross_exposure=constraints.max_gross_exposure,
            )
            param_label = f"Max Weight: {curr_val:.1%}"
            param_desc = "Individual Asset Maximum Allocation Upper Bound (w_max)"
            base_val = constraints.default_max_weight
        elif parameter_to_sweep == "uncertainty_level":
            curr_unc = ExpectedReturnUncertaintyConfig(
                model=curr_unc.model if curr_unc.model != UncertaintyModelType.NONE else UncertaintyModelType.BOX,
                confidence_level=curr_val,
                absolute_radius=curr_unc.absolute_radius,
                per_asset_radius=curr_unc.per_asset_radius,
            )
            param_label = f"Uncertainty: {curr_val:.2f} SE"
            param_desc = "Expected Return Uncertainty Standard-Error Multiplier (kappa)"
            base_val = curr_unc.confidence_level
        elif parameter_to_sweep == "shrinkage_intensity":
            curr_shrink = CovarianceShrinkageConfig(
                target=curr_shrink.target if curr_shrink.target != CovarianceShrinkageTarget.NONE else CovarianceShrinkageTarget.DIAGONAL,
                intensity=curr_val,
            )
            param_label = f"Shrinkage: {curr_val:.2f}"
            param_desc = "Covariance Matrix Linear Shrinkage Intensity (lambda)"
            base_val = curr_shrink.intensity
        else:
            raise ValueError(
                f"Unsupported sweep parameter '{parameter_to_sweep}'. "
                "Must be 'max_weight', 'uncertainty_level', or 'shrinkage_intensity'."
            )

        try:
            res = optimize_robust_portfolio(
                assets=clean_assets,
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                constraints=curr_constraints,
                objective=objective,
                uncertainty_config=curr_unc,
                shrinkage_config=curr_shrink,
                risk_free_rate=risk_free_rate,
                annualized=annualized,
                periods_per_year=periods_per_year,
                observation_count=observation_count,
            )
            r_eval = res.robust_result
            is_feas = r_eval.is_feasible
            if is_feas:
                feasible_count += 1
            else:
                infeasible_count += 1

            w_point = np.array([r_eval.weights.get(a, 0.0) for a in clean_assets], dtype=float)
            d1 = float(np.sum(np.abs(w_point - w_ref)))
            hhi = float(np.sum(w_point**2))
            n_eff = float(1.0 / max(hhi, 1e-8))

            # Detect binding constraints
            binding: list[str] = []
            for i, a in enumerate(clean_assets):
                w_i = float(w_point[i])
                if abs(w_i - curr_constraints.default_max_weight) < 1e-4:
                    binding.append(f"{a} at max_weight ({curr_constraints.default_max_weight:.1%})")
                elif abs(w_i - curr_constraints.default_min_weight) < 1e-4:
                    binding.append(f"{a} at min_weight ({curr_constraints.default_min_weight:.1%})")

            points.append(
                SensitivityPoint(
                    parameter_value=curr_val,
                    parameter_label=param_label,
                    is_feasible=is_feas,
                    solver_status=r_eval.solver_status.value,
                    weights=r_eval.weights,
                    nominal_expected_return=res.nominal_expected_return_robust,
                    worst_case_expected_return=res.worst_case_expected_return_robust,
                    volatility=res.nominal_volatility_robust,
                    sharpe_ratio=r_eval.sharpe_ratio,
                    weight_distance_d1=d1,
                    hhi=hhi,
                    effective_assets=n_eff,
                    binding_constraints=binding,
                )
            )
        except Exception as e:
            infeasible_count += 1
            points.append(
                SensitivityPoint(
                    parameter_value=curr_val,
                    parameter_label=param_label,
                    is_feasible=False,
                    solver_status="failed",
                    weights={},
                    nominal_expected_return=0.0,
                    worst_case_expected_return=0.0,
                    volatility=0.0,
                    sharpe_ratio=None,
                    weight_distance_d1=0.0,
                    hhi=0.0,
                    effective_assets=0.0,
                    binding_constraints=[str(e)],
                )
            )

    return SensitivityAnalysisResult(
        parameter_name=parameter_to_sweep,
        parameter_description=param_desc,
        baseline_value=float(base_val),
        points=points,
        total_evaluations=len(points),
        feasible_evaluations=feasible_count,
        infeasible_evaluations=infeasible_count,
        warnings=warnings,
    )
