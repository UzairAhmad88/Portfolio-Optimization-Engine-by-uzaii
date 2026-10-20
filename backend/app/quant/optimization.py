"""
Quantitative portfolio optimization engine.

Provides mathematically rigorous, numerically verified solvers for:
1. Minimum-Variance Portfolio Optimization.
2. Maximum-Sharpe-Ratio Portfolio Optimization.
3. Equal-Weight Comparison Baseline.

Uses SciPy sequential least squares programming (SLSQP) with analytical gradients.
Enforces typed domain models, independent post-optimization constraint verification,
and explicit error diagnostics for infeasible, degenerate, or ill-conditioned problems.

Independent of web frameworks or external I/O.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import linprog, minimize

from app.quant.constraints import (
    ConstraintInfeasibleError,
    ConstraintValidationError,
    InvestmentConstraints,
    check_constraint_feasibility,
    resolve_asset_bounds,
    validate_weights_against_constraints,
)
from app.quant.portfolio import (
    portfolio_expected_return,
    portfolio_variance,
    portfolio_volatility,
    summarize_weights,
    validate_weights,
)


class OptimizationObjective(str, Enum):
    """Supported mathematical optimization objectives."""

    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    EQUAL_WEIGHT = "equal_weight"
    TARGET_RETURN = "target_return"


class OptimizationStatus(str, Enum):
    """Exit status of the numerical optimization process."""

    CONVERGED = "converged"
    FEASIBLE_BASELINE = "feasible_baseline"
    INVALID_FOR_CONSTRAINTS = "invalid_for_constraints"
    INFEASIBLE = "infeasible"
    ILL_CONDITIONED = "ill_conditioned"
    NON_POSITIVE_EXCESS_RETURNS = "non_positive_excess_returns"
    FAILED = "failed"


class OptimizationError(ValueError):
    """Raised when an optimization problem is fundamentally malformed or invalid."""


@dataclass(frozen=True)
class OptimizationResult:
    """
    Standardized result contract for all portfolio optimization calculations.

    All metrics are independently calculated from the returned weights using
    the verified financial mathematics core.
    """

    objective: str
    assets: list[str]
    weights: dict[str, float]
    expected_return: float
    variance: float
    volatility: float
    sharpe_ratio: float | None
    total_weight: float
    gross_exposure: float
    is_feasible: bool
    constraint_violations: list[str]
    solver_name: str
    solver_status: OptimizationStatus
    solver_message: str
    converged: bool
    objective_value: float | None
    iterations: int | None
    annualized: bool
    periods_per_year: int
    risk_free_rate: float
    observation_count: int | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FrontierPoint:
    """
    Representation of an individual portfolio along the risk-return spectrum.

    Attributes:
        target_return: The requested expected return constraint.
        actual_return: The actual expected return calculated from final weights.
        variance: Independently calculated portfolio variance (w^T Sigma w).
        volatility: Independently calculated portfolio volatility (sqrt(variance)).
        sharpe_ratio: Annualized or periodic Sharpe ratio (None if volatility near zero).
        weights: Dictionary mapping asset identifier to optimal portfolio weight.
        is_feasible: Whether weights strictly satisfy all constraints within tolerance.
        status: Optimization status enum.
        classification: Frontier classification ('efficient', 'dominated_inefficient', 'infeasible', 'failed').
        solver_message: Solver completion or error diagnostic message.
        target_residual: Absolute difference |actual_return - target_return|.
        constraint_violations: List of violation descriptions if any.
        warnings: Non-fatal analytical warnings.
    """

    target_return: float
    actual_return: float
    variance: float
    volatility: float
    sharpe_ratio: float | None
    weights: dict[str, float]
    is_feasible: bool
    status: OptimizationStatus
    classification: str
    solver_message: str
    target_residual: float
    constraint_violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EfficientFrontierResult:
    """
    Complete result contract for an efficient-frontier computation.

    Contains ordered risk-return points, Global Minimum-Variance portfolio reference,
    and completeness/feasibility metadata.
    """

    points: list[FrontierPoint]
    assets: list[str]
    global_minimum_variance: OptimizationResult | None
    requested_count: int
    successful_count: int
    failed_count: int
    is_complete: bool
    annualized: bool
    periods_per_year: int
    risk_free_rate: float
    min_feasible_return: float | None
    max_feasible_return: float | None
    currency: str | None = None
    observation_count: int | None = None
    warnings: list[str] = field(default_factory=list)


def validate_covariance_matrix(
    cov_matrix: pd.DataFrame | np.ndarray,
    expected_dim: int | None = None,
    tolerance: float = 1e-10,
) -> tuple[np.ndarray, list[str]]:
    """
    Validates a covariance matrix for mathematical integrity:
    1. 2D square matrix format.
    2. Finite numeric elements (rejects NaN/Inf).
    3. Symmetry within numerical tolerance.
    4. Positive semi-definiteness via eigenvalue decomposition.
    5. Condition number check for ill-conditioned or singular matrices.

    Parameters:
        cov_matrix: NxN covariance matrix (DataFrame or NumPy array).
        expected_dim: Expected dimension N if known.
        tolerance: Numerical tolerance for symmetry.

    Returns:
        Tuple of (clean 2D NumPy array, list of non-blocking warning messages).

    Raises:
        OptimizationError: If matrix is malformed, non-symmetric, or materially non-PSD.
    """
    warnings: list[str] = []

    if isinstance(cov_matrix, pd.DataFrame):
        arr = cov_matrix.to_numpy(dtype=float)
    elif isinstance(cov_matrix, np.ndarray):
        arr = cov_matrix.astype(float)
    else:
        raise OptimizationError(
            f"Expected pd.DataFrame or np.ndarray for covariance, got {type(cov_matrix).__name__}."
        )

    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise OptimizationError(
            f"Covariance matrix must be a 2D square matrix, got shape {arr.shape}."
        )

    n = arr.shape[0]
    if n == 0:
        raise OptimizationError("Covariance matrix is empty.")

    if expected_dim is not None and n != expected_dim:
        raise OptimizationError(
            f"Covariance matrix dimension ({n}x{n}) does not match expected asset count ({expected_dim})."
        )

    if not np.isfinite(arr).all():
        raise OptimizationError("Covariance matrix contains non-finite values (NaN or Inf).")

    # Symmetry check
    asymmetry = np.max(np.abs(arr - arr.T))
    if asymmetry > tolerance:
        raise OptimizationError(
            f"Covariance matrix is not symmetric: max |Sigma - Sigma^T| = {asymmetry:.6e} > {tolerance:.1e}."
        )

    # Enforce exact floating symmetry
    arr = 0.5 * (arr + arr.T)

    # Eigenvalue decomposition for positive semi-definiteness
    # np.linalg.eigvalsh is specialized for real symmetric matrices
    eigenvalues = np.linalg.eigvalsh(arr)
    min_eig = float(np.min(eigenvalues))
    max_eig = float(np.max(eigenvalues))

    # Tolerance for floating-point noise around zero for empirical PSD matrices
    psd_tol = -1e-8
    if min_eig < psd_tol:
        raise OptimizationError(
            f"Covariance matrix is materially non-positive semi-definite. "
            f"Minimum eigenvalue is {min_eig:.6e} (< {psd_tol:.1e}). "
            "Optimization cannot proceed on non-PSD covariance."
        )

    if min_eig < 0.0:
        warnings.append(
            f"Covariance matrix has slight negative eigenvalue ({min_eig:.3e}) within numerical tolerance; "
            "sample covariance may be rank-deficient (T < N)."
        )

    # Condition number check
    if max_eig > 0:
        effective_min = max(min_eig, 1e-16)
        cond = max_eig / effective_min
        if cond > 1e10 or min_eig <= 1e-12:
            warnings.append(
                f"Covariance matrix is ill-conditioned or singular (condition number ~ {cond:.2e}, min eig = {min_eig:.3e}). "
                "Minimum-variance solution may not be unique or may exhibit high sensitivity."
            )

    return arr, warnings


def _find_feasible_starting_point(
    lower_bounds: np.ndarray,
    upper_bounds: np.ndarray,
    target_total: float,
) -> np.ndarray:
    """
    Computes a strictly feasible starting weight vector w_0 satisfying:
        l_i <= w_0,i <= u_i  for all i
        sum(w_0,i) = target_total

    Uses the analytical convex interpolation between lower and upper bounds:
        alpha = (target - sum(l)) / (sum(u) - sum(l))
        w_0 = (1 - alpha) * l + alpha * u
    """
    sum_l = float(np.sum(lower_bounds))
    sum_u = float(np.sum(upper_bounds))

    denom = sum_u - sum_l
    if abs(denom) < 1e-12:
        return lower_bounds.copy()

    alpha = (target_total - sum_l) / denom
    # Clamp alpha to [0, 1] for safety against tiny floating noise
    alpha = float(np.clip(alpha, 0.0, 1.0))

    w0 = (1.0 - alpha) * lower_bounds + alpha * upper_bounds
    # Fine correction for exact sum
    residual = target_total - np.sum(w0)
    w0[0] += residual
    # If boundary violated by residual, clip and re-adjust
    w0 = np.clip(w0, lower_bounds, upper_bounds)
    diff = target_total - np.sum(w0)
    if abs(diff) > 1e-10:
        # Distribute diff across unconstrained components
        slack = upper_bounds - w0 if diff > 0 else w0 - lower_bounds
        if np.sum(slack) > 1e-12:
            w0 += diff * (slack / np.sum(slack))

    return w0


def optimize_minimum_variance(
    assets: Sequence[str],
    cov_matrix: pd.DataFrame | np.ndarray,
    constraints: InvestmentConstraints,
    expected_returns: pd.Series | np.ndarray | None = None,
    annualized: bool = True,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
    observation_count: int | None = None,
    tolerance: float = 1e-7,
    max_iterations: int = 500,
) -> OptimizationResult:
    """
    Solves the Minimum-Variance Portfolio Optimization problem:
        min_w  w^T Sigma w
        s.t.   l_i <= w_i <= u_i
               sum(w_i) = target_total_weight
               (and gross exposure limits if configured)

    Parameters:
        assets: List of unique asset identifiers in exact calculation order.
        cov_matrix: Symmetric covariance matrix.
        constraints: InvestmentConstraints specification.
        expected_returns: Optional expected returns for portfolio expected return calculation.
        annualized: Whether inputs/outputs are annualized.
        periods_per_year: Scale factor for annualization.
        risk_free_rate: Risk-free rate for Sharpe ratio calculation.
        observation_count: Number of historical observations used for estimates.
        tolerance: Solver optimization tolerance.
        max_iterations: Maximum SLSQP iterations.

    Returns:
        OptimizationResult with verified weights, portfolio variance, volatility, and diagnostics.
    """
    clean_assets = list(assets)
    n = len(clean_assets)
    if n == 0:
        raise OptimizationError("Asset list cannot be empty for optimization.")

    cov_arr, cov_warnings = validate_covariance_matrix(cov_matrix, expected_dim=n)

    # Feasibility check
    feas_report = check_constraint_feasibility(clean_assets, constraints)
    if not feas_report.is_feasible:
        # Infeasible problem
        return OptimizationResult(
            objective=OptimizationObjective.MIN_VARIANCE.value,
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
            warnings=cov_warnings + feas_report.messages,
        )

    # Resolve per-asset bounds
    resolved_bounds = resolve_asset_bounds(clean_assets, constraints)
    lower_bounds = np.array([resolved_bounds[a].lower for a in clean_assets], dtype=float)
    upper_bounds = np.array([resolved_bounds[a].upper for a in clean_assets], dtype=float)
    target_total = float(constraints.target_total_weight)

    # Trivial single-asset case
    if n == 1:
        w_val = target_total
        weights_dict = {clean_assets[0]: w_val}
        var_val = float(cov_arr[0, 0] * (w_val**2))
        vol_val = float(np.sqrt(max(var_val, 0.0)))
        exp_ret = 0.0
        if expected_returns is not None:
            r_val = float(expected_returns[0] if isinstance(expected_returns, (list, np.ndarray)) else expected_returns.iloc[0])
            exp_ret = w_val * r_val
        sharpe = (exp_ret - risk_free_rate) / vol_val if vol_val > 1e-8 else None

        violations = validate_weights_against_constraints(weights_dict, clean_assets, constraints)
        return OptimizationResult(
            objective=OptimizationObjective.MIN_VARIANCE.value,
            assets=clean_assets,
            weights=weights_dict,
            expected_return=exp_ret,
            variance=var_val,
            volatility=vol_val,
            sharpe_ratio=sharpe,
            total_weight=w_val,
            gross_exposure=abs(w_val),
            is_feasible=len(violations) == 0,
            constraint_violations=violations,
            solver_name="Analytical",
            solver_status=OptimizationStatus.CONVERGED,
            solver_message="Exact single-asset solution.",
            converged=True,
            objective_value=var_val,
            iterations=1,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            warnings=cov_warnings,
        )

    # Initial feasible guess
    w0 = _find_feasible_starting_point(lower_bounds, upper_bounds, target_total)

    # Objective: 0.5 * w^T * Sigma * w
    # Gradient: Sigma * w
    def objective_fn(w: np.ndarray) -> float:
        return 0.5 * float(w.T @ cov_arr @ w)

    def gradient_fn(w: np.ndarray) -> np.ndarray:
        return cov_arr @ w

    # Constraints list
    scipy_bounds = [(float(lower_bounds[i]), float(upper_bounds[i])) for i in range(n)]

    scipy_constraints: list[dict[str, Any]] = [
        {
            "type": "eq",
            "fun": lambda w: float(np.sum(w) - target_total),
            "jac": lambda w: np.ones(n, dtype=float),
        }
    ]

    # Gross exposure limit if shorting permitted and cap specified
    if constraints.allow_short and constraints.max_gross_exposure is not None:
        max_gross = float(constraints.max_gross_exposure)
        scipy_constraints.append(
            {
                "type": "ineq",
                "fun": lambda w: float(max_gross - np.sum(np.abs(w))),
            }
        )

    # Run SciPy SLSQP
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
            objective=OptimizationObjective.MIN_VARIANCE.value,
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
            solver_message=f"SLSQP failed: {res.message}",
            converged=False,
            objective_value=float(res.fun) if np.isfinite(res.fun) else None,
            iterations=int(res.nit) if hasattr(res, "nit") else None,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            warnings=cov_warnings,
        )

    opt_weights = np.array(res.x, dtype=float)
    # Check non-finite
    if not np.isfinite(opt_weights).all():
        raise OptimizationError("Solver returned non-finite weights (NaN or Inf).")

    weights_dict = {clean_assets[i]: float(opt_weights[i]) for i in range(n)}

    # Independent solution verification
    violations = validate_weights_against_constraints(
        weights_dict, clean_assets, constraints, tolerance=1e-5
    )
    is_feasible = len(violations) == 0

    # Independently calculate portfolio metrics using pure math core
    var_val = portfolio_variance(opt_weights, cov_arr)
    vol_val = portfolio_volatility(opt_weights, cov_arr)

    exp_ret = 0.0
    if expected_returns is not None:
        if isinstance(expected_returns, pd.Series):
            ret_arr = expected_returns.reindex(clean_assets).to_numpy(dtype=float)
        elif isinstance(expected_returns, np.ndarray):
            ret_arr = expected_returns.astype(float)
        else:
            ret_arr = np.array(expected_returns, dtype=float)
        exp_ret = float(opt_weights @ ret_arr)

    sharpe: float | None = None
    if vol_val > 1e-8:
        sharpe = float((exp_ret - risk_free_rate) / vol_val)
    else:
        cov_warnings.append("Portfolio volatility is near-zero; Sharpe ratio is undefined.")

    w_summary = summarize_weights(opt_weights)

    return OptimizationResult(
        objective=OptimizationObjective.MIN_VARIANCE.value,
        assets=clean_assets,
        weights=weights_dict,
        expected_return=exp_ret,
        variance=var_val,
        volatility=vol_val,
        sharpe_ratio=sharpe,
        total_weight=w_summary.total_weight,
        gross_exposure=w_summary.gross_exposure,
        is_feasible=is_feasible,
        constraint_violations=violations,
        solver_name="SciPy SLSQP",
        solver_status=OptimizationStatus.CONVERGED if is_feasible else OptimizationStatus.INFEASIBLE,
        solver_message=res.message if is_feasible else "Solver converged but weights violate constraints.",
        converged=bool(res.success and is_feasible),
        objective_value=var_val,
        iterations=int(res.nit) if hasattr(res, "nit") else None,
        annualized=annualized,
        periods_per_year=periods_per_year,
        risk_free_rate=risk_free_rate,
        observation_count=observation_count,
        warnings=cov_warnings,
    )


def optimize_maximum_sharpe(
    assets: Sequence[str],
    expected_returns: pd.Series | np.ndarray,
    cov_matrix: pd.DataFrame | np.ndarray,
    constraints: InvestmentConstraints,
    risk_free_rate: float = 0.0,
    annualized: bool = True,
    periods_per_year: int = 252,
    observation_count: int | None = None,
    tolerance: float = 1e-7,
    max_iterations: int = 500,
) -> OptimizationResult:
    """
    Solves the Maximum Sharpe Ratio Portfolio Optimization problem:
        max_w  (w^T mu - R_f) / sqrt(w^T Sigma w)
        s.t.   l_i <= w_i <= u_i
               sum(w_i) = target_total_weight
               (and gross exposure limits if configured)

    Requirements & Safeguards:
    - Verifies that at least one asset or feasible combination offers expected return > R_f.
    - If maximum excess return <= 0, rejects the optimization with an explicit failure status
      because maximizing the Sharpe ratio with negative excess return is economically invalid
      (it artificially maximizes volatility to make the negative ratio less negative).
    - Minimizes negative Sharpe ratio using exact analytical gradient:
          grad(-S) = -mu / sigma_p + ((mu_p - R_f) * Sigma * w) / sigma_p^3
    - Independently recalculates Sharpe ratio from returned weights.
    """
    clean_assets = list(assets)
    n = len(clean_assets)
    if n == 0:
        raise OptimizationError("Asset list cannot be empty for optimization.")

    cov_arr, cov_warnings = validate_covariance_matrix(cov_matrix, expected_dim=n)

    # Standardize expected returns array aligned with clean_assets
    if isinstance(expected_returns, pd.Series):
        if set(expected_returns.index) != set(clean_assets):
            raise OptimizationError(
                f"Expected returns index does not match assets. Missing: {set(clean_assets) - set(expected_returns.index)}."
            )
        ret_arr = expected_returns.reindex(clean_assets).to_numpy(dtype=float)
    elif isinstance(expected_returns, np.ndarray):
        if len(expected_returns) != n:
            raise OptimizationError(
                f"Expected returns length ({len(expected_returns)}) does not match asset count ({n})."
            )
        ret_arr = expected_returns.astype(float)
    else:
        ret_arr = np.array(expected_returns, dtype=float)
        if len(ret_arr) != n:
            raise OptimizationError(
                f"Expected returns length ({len(ret_arr)}) does not match asset count ({n})."
            )

    if not np.isfinite(ret_arr).all():
        raise OptimizationError("Expected returns contain non-finite values (NaN or Inf).")

    # Check feasibility
    feas_report = check_constraint_feasibility(clean_assets, constraints)
    if not feas_report.is_feasible:
        return OptimizationResult(
            objective=OptimizationObjective.MAX_SHARPE.value,
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
            warnings=cov_warnings + feas_report.messages,
        )

    # Check economic validity: max expected return must exceed risk_free_rate
    max_asset_ret = float(np.max(ret_arr))
    if max_asset_ret <= risk_free_rate + 1e-8:
        msg = (
            f"Maximum asset expected return ({max_asset_ret:.4f}) does not exceed the risk-free rate "
            f"({risk_free_rate:.4f}). When excess returns are non-positive, maximizing the Sharpe ratio "
            "is economically invalid as it penalizes lower volatility. Consider Minimum-Variance instead."
        )
        return OptimizationResult(
            objective=OptimizationObjective.MAX_SHARPE.value,
            assets=clean_assets,
            weights={},
            expected_return=0.0,
            variance=0.0,
            volatility=0.0,
            sharpe_ratio=None,
            total_weight=0.0,
            gross_exposure=0.0,
            is_feasible=False,
            constraint_violations=[msg],
            solver_name="SciPy SLSQP",
            solver_status=OptimizationStatus.NON_POSITIVE_EXCESS_RETURNS,
            solver_message=msg,
            converged=False,
            objective_value=None,
            iterations=0,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            warnings=cov_warnings + [msg],
        )

    # Resolve bounds
    resolved_bounds = resolve_asset_bounds(clean_assets, constraints)
    lower_bounds = np.array([resolved_bounds[a].lower for a in clean_assets], dtype=float)
    upper_bounds = np.array([resolved_bounds[a].upper for a in clean_assets], dtype=float)
    target_total = float(constraints.target_total_weight)

    # Single-asset case
    if n == 1:
        w_val = target_total
        weights_dict = {clean_assets[0]: w_val}
        var_val = float(cov_arr[0, 0] * (w_val**2))
        vol_val = float(np.sqrt(max(var_val, 0.0)))
        exp_ret = float(w_val * ret_arr[0])
        if vol_val > 1e-8:
            sharpe = (exp_ret - risk_free_rate) / vol_val
        else:
            cov_warnings.append("Portfolio volatility is near-zero; Sharpe ratio is undefined.")
            sharpe = None

        violations = validate_weights_against_constraints(weights_dict, clean_assets, constraints)
        return OptimizationResult(
            objective=OptimizationObjective.MAX_SHARPE.value,
            assets=clean_assets,
            weights=weights_dict,
            expected_return=exp_ret,
            variance=var_val,
            volatility=vol_val,
            sharpe_ratio=sharpe,
            total_weight=w_val,
            gross_exposure=abs(w_val),
            is_feasible=len(violations) == 0,
            constraint_violations=violations,
            solver_name="Analytical",
            solver_status=OptimizationStatus.CONVERGED,
            solver_message="Exact single-asset solution.",
            converged=True,
            objective_value=-sharpe if sharpe is not None else None,
            iterations=1,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            warnings=cov_warnings,
        )

    # Negative Sharpe Objective: - (w^T mu - Rf) / sqrt(w^T Sigma w + eps)
    eps = 1e-16

    def neg_sharpe_objective(w: np.ndarray) -> float:
        var = float(w.T @ cov_arr @ w)
        vol = float(np.sqrt(max(var, 0.0) + eps))
        mu_p = float(w @ ret_arr)
        excess = mu_p - risk_free_rate
        return -float(excess / vol)

    def neg_sharpe_gradient(w: np.ndarray) -> np.ndarray:
        var = float(w.T @ cov_arr @ w)
        vol = float(np.sqrt(max(var, 0.0) + eps))
        mu_p = float(w @ ret_arr)
        excess = mu_p - risk_free_rate
        # d(-S)/dw = -mu / vol + (excess * Sigma * w) / vol^3
        return -ret_arr / vol + (excess * (cov_arr @ w)) / (vol**3)

    scipy_bounds = [(float(lower_bounds[i]), float(upper_bounds[i])) for i in range(n)]

    scipy_constraints: list[dict[str, Any]] = [
        {
            "type": "eq",
            "fun": lambda w: float(np.sum(w) - target_total),
            "jac": lambda w: np.ones(n, dtype=float),
        }
    ]

    if constraints.allow_short and constraints.max_gross_exposure is not None:
        max_gross = float(constraints.max_gross_exposure)
        scipy_constraints.append(
            {
                "type": "ineq",
                "fun": lambda w: float(max_gross - np.sum(np.abs(w))),
            }
        )

    # Initialization: test feasible starting point and single-asset projections
    candidate_w0s: list[np.ndarray] = [
        _find_feasible_starting_point(lower_bounds, upper_bounds, target_total)
    ]

    # Add best individual Sharpe asset if within bounds
    diag_vols = np.sqrt(np.maximum(np.diag(cov_arr), 1e-12))
    asset_sharpes = (ret_arr - risk_free_rate) / diag_vols
    best_idx = int(np.argmax(asset_sharpes))
    if lower_bounds[best_idx] <= target_total <= upper_bounds[best_idx]:
        w_single = np.zeros(n, dtype=float)
        w_single[best_idx] = target_total
        # Ensure box bounds
        w_single = np.clip(w_single, lower_bounds, upper_bounds)
        if abs(np.sum(w_single) - target_total) < 1e-6:
            candidate_w0s.append(w_single)

    best_res = None
    best_fun = float("inf")

    for w0 in candidate_w0s:
        res = minimize(
            fun=neg_sharpe_objective,
            x0=w0,
            jac=neg_sharpe_gradient,
            method="SLSQP",
            bounds=scipy_bounds,
            constraints=scipy_constraints,
            options={"ftol": tolerance, "maxiter": max_iterations, "disp": False},
        )
        if res.success and res.fun < best_fun:
            best_res = res
            best_fun = res.fun

    if best_res is None or not best_res.success:
        # Fall back to first result for diagnostics
        res = best_res if best_res is not None else res
        return OptimizationResult(
            objective=OptimizationObjective.MAX_SHARPE.value,
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
            solver_message=f"SLSQP failed to find Max-Sharpe solution: {res.message}",
            converged=False,
            objective_value=float(res.fun) if np.isfinite(res.fun) else None,
            iterations=int(res.nit) if hasattr(res, "nit") else None,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            warnings=cov_warnings,
        )

    opt_weights = np.array(best_res.x, dtype=float)
    if not np.isfinite(opt_weights).all():
        raise OptimizationError("Solver returned non-finite weights (NaN or Inf).")

    weights_dict = {clean_assets[i]: float(opt_weights[i]) for i in range(n)}

    violations = validate_weights_against_constraints(
        weights_dict, clean_assets, constraints, tolerance=1e-5
    )
    is_feasible = len(violations) == 0

    var_val = portfolio_variance(opt_weights, cov_arr)
    vol_val = portfolio_volatility(opt_weights, cov_arr)
    exp_ret = float(opt_weights @ ret_arr)

    if vol_val <= 1e-8:
        cov_warnings.append("Portfolio volatility is near-zero; Sharpe ratio is undefined.")
        sharpe = None
    else:
        sharpe = float((exp_ret - risk_free_rate) / vol_val)

    w_summary = summarize_weights(opt_weights)

    return OptimizationResult(
        objective=OptimizationObjective.MAX_SHARPE.value,
        assets=clean_assets,
        weights=weights_dict,
        expected_return=exp_ret,
        variance=var_val,
        volatility=vol_val,
        sharpe_ratio=sharpe,
        total_weight=w_summary.total_weight,
        gross_exposure=w_summary.gross_exposure,
        is_feasible=is_feasible,
        constraint_violations=violations,
        solver_name="SciPy SLSQP",
        solver_status=OptimizationStatus.CONVERGED if is_feasible else OptimizationStatus.INFEASIBLE,
        solver_message=best_res.message if is_feasible else "Solver converged but weights violate constraints.",
        converged=bool(best_res.success and is_feasible),
        objective_value=sharpe,
        iterations=int(best_res.nit) if hasattr(best_res, "nit") else None,
        annualized=annualized,
        periods_per_year=periods_per_year,
        risk_free_rate=risk_free_rate,
        observation_count=observation_count,
        warnings=cov_warnings,
    )


def compute_equal_weight_baseline(
    assets: Sequence[str],
    cov_matrix: pd.DataFrame | np.ndarray,
    constraints: InvestmentConstraints,
    expected_returns: pd.Series | np.ndarray | None = None,
    risk_free_rate: float = 0.0,
    annualized: bool = True,
    periods_per_year: int = 252,
    observation_count: int | None = None,
) -> OptimizationResult:
    """
    Constructs a deterministic equal-weight benchmark allocation:
        w_i = target_total_weight / N

    Validates whether equal-weight satisfies the requested constraints:
    - If equal weights violate constraints (e.g. upper bound caps an asset below 1/N),
      marks the baseline as invalid for that configuration with explanatory violations.
    - Independently calculates expected return, variance, volatility, and Sharpe ratio.
    """
    clean_assets = list(assets)
    n = len(clean_assets)
    if n == 0:
        raise OptimizationError("Asset list cannot be empty for equal-weight calculation.")

    cov_arr, cov_warnings = validate_covariance_matrix(cov_matrix, expected_dim=n)

    target_total = float(constraints.target_total_weight)
    eq_w = target_total / float(n)
    weights_arr = np.full(n, eq_w, dtype=float)
    weights_dict = {clean_assets[i]: eq_w for i in range(n)}

    # Validate against constraints
    violations = validate_weights_against_constraints(
        weights_dict, clean_assets, constraints, tolerance=1e-5
    )
    is_feasible = len(violations) == 0

    var_val = portfolio_variance(weights_arr, cov_arr)
    vol_val = portfolio_volatility(weights_arr, cov_arr)

    exp_ret = 0.0
    if expected_returns is not None:
        if isinstance(expected_returns, pd.Series):
            ret_arr = expected_returns.reindex(clean_assets).to_numpy(dtype=float)
        elif isinstance(expected_returns, np.ndarray):
            ret_arr = expected_returns.astype(float)
        else:
            ret_arr = np.array(expected_returns, dtype=float)
        exp_ret = float(weights_arr @ ret_arr)

    sharpe: float | None = None
    if vol_val > 1e-8:
        sharpe = float((exp_ret - risk_free_rate) / vol_val)

    w_summary = summarize_weights(weights_arr)

    status = (
        OptimizationStatus.FEASIBLE_BASELINE
        if is_feasible
        else OptimizationStatus.INVALID_FOR_CONSTRAINTS
    )
    msg = (
        "Equal-weight baseline satisfies all configured investment constraints."
        if is_feasible
        else f"Equal-weight baseline is invalid for this configuration: {'; '.join(violations)}"
    )

    return OptimizationResult(
        objective=OptimizationObjective.EQUAL_WEIGHT.value,
        assets=clean_assets,
        weights=weights_dict,
        expected_return=exp_ret,
        variance=var_val,
        volatility=vol_val,
        sharpe_ratio=sharpe,
        total_weight=w_summary.total_weight,
        gross_exposure=w_summary.gross_exposure,
        is_feasible=is_feasible,
        constraint_violations=violations,
        solver_name="Deterministic Equal-Weight",
        solver_status=status,
        solver_message=msg,
        converged=is_feasible,
        objective_value=var_val,
        iterations=1,
        annualized=annualized,
        periods_per_year=periods_per_year,
        risk_free_rate=risk_free_rate,
        observation_count=observation_count,
        warnings=cov_warnings + ([] if is_feasible else [msg]),
    )


def calculate_feasible_return_bounds(
    assets: Sequence[str],
    expected_returns: pd.Series | np.ndarray,
    constraints: InvestmentConstraints,
) -> tuple[float, float, np.ndarray, np.ndarray]:
    """
    Computes the exact minimum and maximum achievable expected portfolio return
    under the linear investment constraints (box bounds and target total weight).

    Uses linear programming (SciPy linprog with HiGHS dual-simplex solver):
        min/max  w^T mu
        s.t.     l_i <= w_i <= u_i
                 sum(w_i) = target_total_weight

    Returns:
        Tuple of (min_return, max_return, min_weights, max_weights).

    Raises:
        OptimizationError: If the linear constraint system is infeasible or solver fails.
    """
    clean_assets = list(assets)
    n = len(clean_assets)
    if n == 0:
        raise OptimizationError("Asset list cannot be empty.")

    # Align expected returns
    if isinstance(expected_returns, pd.Series):
        if set(expected_returns.index) != set(clean_assets):
            raise OptimizationError("Expected returns index does not match asset list.")
        ret_arr = expected_returns.reindex(clean_assets).to_numpy(dtype=float)
    elif isinstance(expected_returns, np.ndarray):
        ret_arr = expected_returns.astype(float)
    else:
        ret_arr = np.array(expected_returns, dtype=float)

    if ret_arr.shape != (n,):
        raise OptimizationError(f"Expected returns shape {ret_arr.shape} does not match asset count {n}.")

    resolved_bounds = resolve_asset_bounds(clean_assets, constraints)
    lower_bounds = np.array([resolved_bounds[a].lower for a in clean_assets], dtype=float)
    upper_bounds = np.array([resolved_bounds[a].upper for a in clean_assets], dtype=float)
    target_total = float(constraints.target_total_weight)

    bounds = [(float(lower_bounds[i]), float(upper_bounds[i])) for i in range(n)]
    A_eq = np.ones((1, n), dtype=float)
    b_eq = np.array([target_total], dtype=float)

    # Solve Min return
    res_min = linprog(c=ret_arr, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not res_min.success:
        raise OptimizationError(f"Failed to find minimum feasible return: {res_min.message}")

    # Solve Max return (min -ret_arr)
    res_max = linprog(c=-ret_arr, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not res_max.success:
        raise OptimizationError(f"Failed to find maximum feasible return: {res_max.message}")

    w_min = np.array(res_min.x, dtype=float)
    w_max = np.array(res_max.x, dtype=float)
    min_ret = float(w_min @ ret_arr)
    max_ret = float(w_max @ ret_arr)

    return min_ret, max_ret, w_min, w_max


def optimize_target_return_min_variance(
    assets: Sequence[str],
    expected_returns: pd.Series | np.ndarray,
    cov_matrix: pd.DataFrame | np.ndarray,
    constraints: InvestmentConstraints,
    target_return: float,
    annualized: bool = True,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
    observation_count: int | None = None,
    tolerance: float = 1e-7,
    max_iterations: int = 500,
) -> OptimizationResult:
    """
    Solves the Target-Return Minimum-Variance Optimization problem:
        min_w  1/2 * w^T Sigma w
        s.t.   sum(w_i) = target_total_weight
               w^T mu = target_return
               l_i <= w_i <= u_i
               (and gross exposure limit if configured)

    Uses SciPy SLSQP with exact analytical gradients:
        Gradient of 1/2 w^T Sigma w = Sigma w.
    """
    clean_assets = list(assets)
    n = len(clean_assets)
    if n == 0:
        raise OptimizationError("Asset list cannot be empty for optimization.")

    cov_arr, cov_warnings = validate_covariance_matrix(cov_matrix, expected_dim=n)

    if isinstance(expected_returns, pd.Series):
        if set(expected_returns.index) != set(clean_assets):
            raise OptimizationError("Expected returns index does not match asset list.")
        ret_arr = expected_returns.reindex(clean_assets).to_numpy(dtype=float)
    elif isinstance(expected_returns, np.ndarray):
        ret_arr = expected_returns.astype(float)
    else:
        ret_arr = np.array(expected_returns, dtype=float)

    if ret_arr.shape != (n,):
        raise OptimizationError(f"Expected returns shape {ret_arr.shape} does not match asset count {n}.")

    # 1. Feasibility check of investment constraints
    feas_report = check_constraint_feasibility(clean_assets, constraints)
    if not feas_report.is_feasible:
        return OptimizationResult(
            objective=OptimizationObjective.TARGET_RETURN.value,
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
            solver_message="Constraint system is infeasible: " + "; ".join(feas_report.messages),
            converged=False,
            objective_value=None,
            iterations=0,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            warnings=cov_warnings + feas_report.messages,
        )

    # 2. Check target-return feasibility via exact linear programming bounds
    min_ret, max_ret, w_min, w_max = calculate_feasible_return_bounds(clean_assets, ret_arr, constraints)

    if target_return < min_ret - 1e-5 or target_return > max_ret + 1e-5:
        return OptimizationResult(
            objective=OptimizationObjective.TARGET_RETURN.value,
            assets=clean_assets,
            weights={},
            expected_return=0.0,
            variance=0.0,
            volatility=0.0,
            sharpe_ratio=None,
            total_weight=0.0,
            gross_exposure=0.0,
            is_feasible=False,
            constraint_violations=[
                f"Target return {target_return:.6f} is infeasible. "
                f"Feasible range under constraints is [{min_ret:.6f}, {max_ret:.6f}]."
            ],
            solver_name="SciPy SLSQP",
            solver_status=OptimizationStatus.INFEASIBLE,
            solver_message=(
                f"Infeasible target return: requested {target_return:.6f}, "
                f"feasible range is [{min_ret:.6f}, {max_ret:.6f}]."
            ),
            converged=False,
            objective_value=None,
            iterations=0,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            warnings=cov_warnings,
        )

    # 3. Construct strictly feasible initial guess w0
    if abs(max_ret - min_ret) < 1e-12:
        w0 = w_min.copy()
    else:
        alpha = float(np.clip((target_return - min_ret) / (max_ret - min_ret), 0.0, 1.0))
        w0 = (1.0 - alpha) * w_min + alpha * w_max

    resolved_bounds = resolve_asset_bounds(clean_assets, constraints)
    lower_bounds = np.array([resolved_bounds[a].lower for a in clean_assets], dtype=float)
    upper_bounds = np.array([resolved_bounds[a].upper for a in clean_assets], dtype=float)
    target_total = float(constraints.target_total_weight)

    # Objective: 0.5 * w^T * Sigma * w
    def objective_fn(w: np.ndarray) -> float:
        return 0.5 * float(w.T @ cov_arr @ w)

    def gradient_fn(w: np.ndarray) -> np.ndarray:
        return cov_arr @ w

    scipy_bounds = [(float(lower_bounds[i]), float(upper_bounds[i])) for i in range(n)]

    scipy_constraints: list[dict[str, Any]] = [
        {
            "type": "eq",
            "fun": lambda w: float(np.sum(w) - target_total),
            "jac": lambda w: np.ones(n, dtype=float),
        },
        {
            "type": "eq",
            "fun": lambda w: float(w @ ret_arr - target_return),
            "jac": lambda w: ret_arr,
        },
    ]

    if constraints.allow_short and constraints.max_gross_exposure is not None:
        max_gross = float(constraints.max_gross_exposure)
        scipy_constraints.append(
            {
                "type": "ineq",
                "fun": lambda w: float(max_gross - np.sum(np.abs(w))),
            }
        )

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
            objective=OptimizationObjective.TARGET_RETURN.value,
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
            solver_message=f"SLSQP failed: {res.message}",
            converged=False,
            objective_value=float(res.fun) if np.isfinite(res.fun) else None,
            iterations=int(res.nit) if hasattr(res, "nit") else None,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            warnings=cov_warnings,
        )

    opt_weights = np.array(res.x, dtype=float)
    if not np.isfinite(opt_weights).all():
        raise OptimizationError("Solver returned non-finite weights (NaN or Inf).")

    weights_dict = {clean_assets[i]: float(opt_weights[i]) for i in range(n)}

    # Independent solution verification
    violations = validate_weights_against_constraints(
        weights_dict, clean_assets, constraints, tolerance=1e-5
    )

    var_val = portfolio_variance(opt_weights, cov_arr)
    vol_val = portfolio_volatility(opt_weights, cov_arr)
    actual_ret = float(opt_weights @ ret_arr)

    target_residual = abs(actual_ret - target_return)
    if target_residual > 1e-4:
        violations.append(
            f"Target return residual {target_residual:.2e} exceeds tolerance 1e-4 "
            f"(target={target_return:.6f}, actual={actual_ret:.6f})."
        )

    is_feasible = len(violations) == 0

    sharpe: float | None = None
    if vol_val > 1e-8:
        sharpe = float((actual_ret - risk_free_rate) / vol_val)
    else:
        cov_warnings.append("Portfolio volatility is near-zero; Sharpe ratio is undefined.")

    w_summary = summarize_weights(opt_weights)

    return OptimizationResult(
        objective=OptimizationObjective.TARGET_RETURN.value,
        assets=clean_assets,
        weights=weights_dict,
        expected_return=actual_ret,
        variance=var_val,
        volatility=vol_val,
        sharpe_ratio=sharpe,
        total_weight=w_summary.total_weight,
        gross_exposure=w_summary.gross_exposure,
        is_feasible=is_feasible,
        constraint_violations=violations,
        solver_name="SciPy SLSQP",
        solver_status=OptimizationStatus.CONVERGED if is_feasible else OptimizationStatus.INFEASIBLE,
        solver_message=res.message if is_feasible else "Solver converged but weights violate constraints.",
        converged=bool(res.success and is_feasible),
        objective_value=var_val,
        iterations=int(res.nit) if hasattr(res, "nit") else None,
        annualized=annualized,
        periods_per_year=periods_per_year,
        risk_free_rate=risk_free_rate,
        observation_count=observation_count,
        warnings=cov_warnings,
    )


def generate_efficient_frontier(
    assets: Sequence[str],
    cov_matrix: pd.DataFrame | np.ndarray,
    expected_returns: pd.Series | np.ndarray,
    constraints: InvestmentConstraints,
    target_returns: Sequence[float] | None = None,
    target_count: int = 20,
    risk_free_rate: float = 0.0,
    annualized: bool = True,
    periods_per_year: int = 252,
    observation_count: int | None = None,
    currency: str | None = None,
    tolerance: float = 1e-7,
    max_iterations: int = 500,
) -> EfficientFrontierResult:
    """
    Generates the Markowitz portfolio risk-return curve and identifies the efficient frontier.

    Solves a sequence of target-return minimum-variance optimizations across either:
    1. User-supplied target expected returns in exact order, or
    2. An evenly spaced grid of target returns spanning the mathematically feasible range.

    Frontier Integrity Safeguards:
    - Calculates exact linear programming feasibility bounds [mu_min, mu_max].
    - Computes the Global Minimum-Variance (GMV) portfolio as anchor.
    - Classifies points with R_target < R_GMV as 'dominated_inefficient' (lower branch).
    - Classifies points with R_target >= R_GMV as 'efficient' (upper non-dominated frontier).
    - Infeasible targets explicitly marked as 'infeasible' with empty weights (no fabricated points).
    - Detects numerically duplicate points and logs warnings.
    - Accurately tracks requested_count, successful_count, and failed_count.
    """
    clean_assets = list(assets)
    n = len(clean_assets)
    if n == 0:
        raise OptimizationError("Asset list cannot be empty for efficient frontier generation.")

    cov_arr, cov_warnings = validate_covariance_matrix(cov_matrix, expected_dim=n)

    if isinstance(expected_returns, pd.Series):
        if set(expected_returns.index) != set(clean_assets):
            raise OptimizationError("Expected returns index does not match asset list.")
        ret_arr = expected_returns.reindex(clean_assets).to_numpy(dtype=float)
    elif isinstance(expected_returns, np.ndarray):
        ret_arr = expected_returns.astype(float)
    else:
        ret_arr = np.array(expected_returns, dtype=float)

    if ret_arr.shape != (n,):
        raise OptimizationError(f"Expected returns shape {ret_arr.shape} does not match asset count {n}.")

    feas_report = check_constraint_feasibility(clean_assets, constraints)
    if not feas_report.is_feasible:
        return EfficientFrontierResult(
            points=[],
            assets=clean_assets,
            global_minimum_variance=None,
            requested_count=0,
            successful_count=0,
            failed_count=0,
            is_complete=False,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            min_feasible_return=None,
            max_feasible_return=None,
            currency=currency,
            observation_count=observation_count,
            warnings=cov_warnings + feas_report.messages,
        )

    # Feasible bounds via LP
    min_ret, max_ret, _, _ = calculate_feasible_return_bounds(clean_assets, ret_arr, constraints)

    # Global Minimum-Variance portfolio
    gmv_result = optimize_minimum_variance(
        assets=clean_assets,
        cov_matrix=cov_arr,
        constraints=constraints,
        expected_returns=ret_arr,
        annualized=annualized,
        periods_per_year=periods_per_year,
        risk_free_rate=risk_free_rate,
        observation_count=observation_count,
        tolerance=tolerance,
        max_iterations=max_iterations,
    )
    gmv_return = gmv_result.expected_return if gmv_result.is_feasible else min_ret

    # Determine targets
    if target_returns is not None:
        targets = [float(t) for t in target_returns]
    else:
        if target_count < 2:
            raise OptimizationError("target_count must be at least 2 when generating a grid.")
        if abs(max_ret - min_ret) < 1e-8:
            targets = [min_ret]
        else:
            targets = [float(x) for x in np.linspace(min_ret, max_ret, target_count)]

    points: list[FrontierPoint] = []
    frontier_warnings: list[str] = list(cov_warnings)

    for t in targets:
        # Check feasibility
        if t < min_ret - 1e-5 or t > max_ret + 1e-5:
            points.append(
                FrontierPoint(
                    target_return=t,
                    actual_return=0.0,
                    variance=0.0,
                    volatility=0.0,
                    sharpe_ratio=None,
                    weights={},
                    is_feasible=False,
                    status=OptimizationStatus.INFEASIBLE,
                    classification="infeasible",
                    solver_message=(
                        f"Target return {t:.6f} is outside feasible range [{min_ret:.6f}, {max_ret:.6f}]."
                    ),
                    target_residual=0.0,
                    constraint_violations=[
                        f"Target return {t:.6f} is outside feasible range [{min_ret:.6f}, {max_ret:.6f}]."
                    ],
                )
            )
            continue

        res = optimize_target_return_min_variance(
            assets=clean_assets,
            expected_returns=ret_arr,
            cov_matrix=cov_arr,
            constraints=constraints,
            target_return=t,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )

        if not res.is_feasible or not res.converged:
            points.append(
                FrontierPoint(
                    target_return=t,
                    actual_return=res.expected_return,
                    variance=res.variance,
                    volatility=res.volatility,
                    sharpe_ratio=res.sharpe_ratio,
                    weights={},
                    is_feasible=False,
                    status=res.solver_status,
                    classification="failed",
                    solver_message=res.solver_message,
                    target_residual=abs(res.expected_return - t),
                    constraint_violations=res.constraint_violations,
                    warnings=res.warnings,
                )
            )
        else:
            # Dominance classification:
            # Dominated if actual expected return is strictly below GMV return
            if res.expected_return < gmv_return - 1e-5:
                classification = "dominated_inefficient"
            else:
                classification = "efficient"

            points.append(
                FrontierPoint(
                    target_return=t,
                    actual_return=res.expected_return,
                    variance=res.variance,
                    volatility=res.volatility,
                    sharpe_ratio=res.sharpe_ratio,
                    weights=res.weights,
                    is_feasible=True,
                    status=res.solver_status,
                    classification=classification,
                    solver_message=res.solver_message,
                    target_residual=abs(res.expected_return - t),
                    constraint_violations=[],
                    warnings=res.warnings,
                )
            )

    # Detect duplicate points among successful solutions
    successful_points = [p for p in points if p.is_feasible]
    duplicate_count = 0
    for i in range(len(successful_points)):
        for j in range(i + 1, len(successful_points)):
            p1, p2 = successful_points[i], successful_points[j]
            if abs(p1.volatility - p2.volatility) < 1e-6 and abs(p1.actual_return - p2.actual_return) < 1e-6:
                duplicate_count += 1

    if duplicate_count > 0:
        frontier_warnings.append(f"Detected {duplicate_count} numerically duplicate frontier points.")

    requested_count = len(targets)
    successful_count = len(successful_points)
    failed_count = requested_count - successful_count
    is_complete = failed_count == 0

    return EfficientFrontierResult(
        points=points,
        assets=clean_assets,
        global_minimum_variance=gmv_result if gmv_result.is_feasible else None,
        requested_count=requested_count,
        successful_count=successful_count,
        failed_count=failed_count,
        is_complete=is_complete,
        annualized=annualized,
        periods_per_year=periods_per_year,
        risk_free_rate=risk_free_rate,
        min_feasible_return=min_ret,
        max_feasible_return=max_ret,
        currency=currency,
        observation_count=observation_count,
        warnings=frontier_warnings,
    )


def optimize_portfolio(
    assets: Sequence[str],
    cov_matrix: pd.DataFrame | np.ndarray,
    constraints: InvestmentConstraints,
    objective: OptimizationObjective | str = OptimizationObjective.MIN_VARIANCE,
    expected_returns: pd.Series | np.ndarray | None = None,
    target_return: float | None = None,
    risk_free_rate: float = 0.0,
    annualized: bool = True,
    periods_per_year: int = 252,
    observation_count: int | None = None,
    tolerance: float = 1e-7,
    max_iterations: int = 500,
) -> OptimizationResult:
    """
    Primary entry point for quantitative portfolio optimization.

    Dispatches to the appropriate mathematical engine based on objective.
    """
    obj_str = objective.value if isinstance(objective, OptimizationObjective) else str(objective).lower()

    if obj_str == OptimizationObjective.MIN_VARIANCE.value:
        return optimize_minimum_variance(
            assets=assets,
            cov_matrix=cov_matrix,
            constraints=constraints,
            expected_returns=expected_returns,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    elif obj_str == OptimizationObjective.MAX_SHARPE.value:
        if expected_returns is None:
            raise OptimizationError("Expected returns are required for Maximum Sharpe Ratio optimization.")
        return optimize_maximum_sharpe(
            assets=assets,
            expected_returns=expected_returns,
            cov_matrix=cov_matrix,
            constraints=constraints,
            risk_free_rate=risk_free_rate,
            annualized=annualized,
            periods_per_year=periods_per_year,
            observation_count=observation_count,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    elif obj_str == OptimizationObjective.EQUAL_WEIGHT.value:
        return compute_equal_weight_baseline(
            assets=assets,
            cov_matrix=cov_matrix,
            constraints=constraints,
            expected_returns=expected_returns,
            risk_free_rate=risk_free_rate,
            annualized=annualized,
            periods_per_year=periods_per_year,
            observation_count=observation_count,
        )
    elif obj_str == OptimizationObjective.TARGET_RETURN.value:
        if expected_returns is None:
            raise OptimizationError("Expected returns are required for Target Return optimization.")
        if target_return is None:
            raise OptimizationError("target_return parameter is required for TARGET_RETURN objective.")
        return optimize_target_return_min_variance(
            assets=assets,
            expected_returns=expected_returns,
            cov_matrix=cov_matrix,
            constraints=constraints,
            target_return=target_return,
            annualized=annualized,
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
            observation_count=observation_count,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    else:
        raise OptimizationError(
            f"Unsupported optimization objective '{objective}'. "
            f"Supported objectives: {[o.value for o in OptimizationObjective]}."
        )

