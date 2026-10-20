"""
Black-Litterman Portfolio Optimization & Bayesian View Incorporation Module.

This module provides pure mathematical functions for:
1. Deriving market implied equilibrium returns via reverse optimization.
2. Formulating investor views (absolute and relative) with confidence-weighted uncertainty.
3. Deriving the analytical Bayesian posterior expected returns and covariance matrix.
4. Solving constrained Black-Litterman allocations (Max Sharpe, Min Volatility, Utility).
5. Calculating view impact and active tilt diagnostics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BlackLittermanView:
    """Individual analyst or quantitative view."""
    view_type: str  # 'absolute' or 'relative'
    assets: tuple[str, ...]  # Assets involved in the view
    weights: tuple[float, ...]  # Pick vector weights P_k for the assets
    target_return: float  # Annualized view target return q_k
    confidence: float = 0.50  # Confidence in [0.01, 0.99]


def calculate_implied_equilibrium_returns(
    covariance: np.ndarray,
    equilibrium_weights: np.ndarray,
    risk_aversion: float = 2.50,
    risk_free_rate: float = 0.0,
) -> np.ndarray:
    """
    Computes market implied equilibrium returns via reverse optimization:
    Pi = risk_free_rate * 1 + gamma * Sigma * w_eq

    Args:
        covariance: Annualized asset covariance matrix (N x N).
        equilibrium_weights: Benchmark or market equilibrium asset weights (N,).
        risk_aversion: Market risk aversion coefficient gamma > 0.
        risk_free_rate: Annualized risk-free rate Rf >= 0 (defaults to 0.0 for pure excess returns).

    Returns:
        Vector of implied equilibrium returns Pi (N,).
    """
    if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
        raise ValueError("Covariance matrix must be square (N x N).")
    n = covariance.shape[0]
    if equilibrium_weights.shape != (n,):
        raise ValueError(f"Equilibrium weights must have shape ({n},). Got {equilibrium_weights.shape}.")
    if risk_aversion <= 0:
        raise ValueError("Risk aversion coefficient must be strictly positive.")

    # Matrix multiplication Pi = risk_free_rate + gamma * Sigma * w_eq
    pi = risk_free_rate + risk_aversion * (covariance @ equilibrium_weights)
    return pi


def build_view_matrices(
    views: list[BlackLittermanView],
    asset_order: list[str],
    tau: float,
    covariance: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Builds the pick matrix P (K x N), target return vector q (K,), and
    view uncertainty covariance matrix Omega (K x K).

    View uncertainty Omega_kk is calibrated via Idzorek's confidence method:
    Omega_kk = ((1 - c_k) / c_k) * P_k (tau * Sigma) P_k^T

    Args:
        views: List of BlackLittermanView definitions.
        asset_order: Ordered list of asset tickers/identifiers (length N).
        tau: Scalar scalar tuning uncertainty in the prior distribution.
        covariance: Sample or shrunk covariance matrix (N x N).

    Returns:
        (P, q, Omega) matrices.
    """
    n = len(asset_order)
    k = len(views)
    asset_idx_map = {asset: i for i, asset in enumerate(asset_order)}

    if k == 0:
        return np.zeros((0, n)), np.zeros(0), np.zeros((0, 0))

    p = np.zeros((k, n), dtype=np.float64)
    q = np.zeros(k, dtype=np.float64)
    omega = np.zeros((k, k), dtype=np.float64)

    tau_sigma = tau * covariance

    for row_idx, view in enumerate(views):
        q[row_idx] = view.target_return
        for asset, weight in zip(view.assets, view.weights):
            if asset in asset_idx_map:
                p[row_idx, asset_idx_map[asset]] = float(weight)
            else:
                raise ValueError(f"View asset '{asset}' not present in asset universe.")

        # Variance of view portfolio: P_k * (tau * Sigma) * P_k^T
        view_var = float(p[row_idx] @ tau_sigma @ p[row_idx])
        if view_var <= 1e-12:
            view_var = 1e-6

        # Idzorek confidence weighting: confidence in (0, 1)
        # c -> 1.0 => Omega -> 0 (view absolute constraint)
        # c -> 0.0 => Omega -> inf (view ignored)
        conf = float(np.clip(view.confidence, 0.01, 0.99))
        omega_kk = ((1.0 - conf) / conf) * view_var
        omega[row_idx, row_idx] = max(omega_kk, 1e-8)

    return p, q, omega


def compute_black_litterman_posterior(
    implied_returns: np.ndarray,
    covariance: np.ndarray,
    p: np.ndarray,
    q: np.ndarray,
    omega: np.ndarray,
    tau: float = 0.05,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Computes the Black-Litterman posterior expected return vector mu_BL and
    posterior covariance matrix Sigma_post.

    Uses the Woodbury matrix identity formulation:
    mu_BL = Pi + tau*Sigma*P^T [P*(tau*Sigma)*P^T + Omega]^-1 (q - P*Pi)
    M = tau*Sigma - tau*Sigma*P^T [P*(tau*Sigma)*P^T + Omega]^-1 P*(tau*Sigma)
    Sigma_post = Sigma + M

    Args:
        implied_returns: Prior equilibrium returns Pi (N,).
        covariance: Asset covariance matrix Sigma (N x N).
        p: Pick matrix P (K x N).
        q: Target returns vector q (K,).
        omega: View uncertainty matrix Omega (K x K).
        tau: Prior uncertainty scalar.

    Returns:
        (posterior_mean, posterior_covariance)
    """
    n = covariance.shape[0]
    k = p.shape[0]

    if k == 0:
        # Zero views: posterior matches equilibrium prior
        mu_bl = implied_returns.copy()
        sigma_post = (1.0 + tau) * covariance
        return mu_bl, sigma_post

    tau_sigma = tau * covariance
    p_tau_sigma = p @ tau_sigma  # (K x N)
    middle_term = p_tau_sigma @ p.T + omega  # (K x K)

    # Invert the K x K view space matrix
    try:
        middle_inv = np.linalg.inv(middle_term)
    except np.linalg.LinAlgError:
        middle_inv = np.linalg.pinv(middle_term)

    # Compute posterior expected returns mu_BL
    view_spread = q - (p @ implied_returns)
    adjustment = tau_sigma @ p.T @ middle_inv @ view_spread
    mu_bl = implied_returns + adjustment

    # Compute posterior covariance M and Sigma_post
    m_matrix = tau_sigma - (tau_sigma @ p.T @ middle_inv @ p_tau_sigma)
    sigma_post = covariance + m_matrix

    # Symmetrize and enforce positive definiteness
    sigma_post = 0.5 * (sigma_post + sigma_post.T)
    min_eig = np.min(np.linalg.eigvalsh(sigma_post))
    if min_eig < 1e-10:
        sigma_post += np.eye(n) * (1e-8 - min_eig)

    return mu_bl, sigma_post


def compute_unconstrained_bl_weights(
    posterior_mean: np.ndarray,
    covariance: np.ndarray,
    risk_aversion: float = 2.50,
    risk_free_rate: float = 0.0,
) -> np.ndarray:
    """
    Computes unconstrained Black-Litterman weights:
    w = (1 / gamma) * Sigma^-1 * (mu_BL - risk_free_rate * 1)
    normalized to sum to 1.0.
    """
    try:
        inv_cov = np.linalg.inv(covariance)
    except np.linalg.LinAlgError:
        inv_cov = np.linalg.pinv(covariance)

    excess_mean = posterior_mean - risk_free_rate
    raw_weights = (1.0 / risk_aversion) * (inv_cov @ excess_mean)
    total = np.sum(raw_weights)
    if abs(total) > 1e-12:
        return raw_weights / total
    return np.full_like(raw_weights, 1.0 / len(raw_weights))


def optimize_black_litterman_portfolio(
    posterior_mean: np.ndarray,
    posterior_covariance: np.ndarray,
    objective: str = "max_sharpe",
    risk_free_rate: float = 0.02,
    risk_aversion: float = 2.50,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
    max_gross_exposure: float = 1.0,
) -> dict[str, Any]:
    """
    Solves constrained quadratic portfolio allocation under Black-Litterman posterior inputs.

    Objectives:
    - 'max_sharpe': Maximize (w^T mu_BL - Rf) / sqrt(w^T Sigma_post w)
    - 'min_variance': Minimize w^T Sigma_post w
    - 'mean_variance_utility': Maximize w^T mu_BL - 0.5 * gamma * w^T Sigma_post w

    Returns:
        Dictionary containing optimal weights, expected return, volatility, Sharpe,
        is_feasible, and solver status.
    """
    n = len(posterior_mean)
    init_weights = np.full(n, 1.0 / n, dtype=np.float64)

    bounds = tuple((min_weight, max_weight) for _ in range(n))
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    if max_gross_exposure < 5.0 and min_weight < 0:
        constraints.append({"type": "ineq", "fun": lambda w: max_gross_exposure - np.sum(np.abs(w))})

    if objective == "min_variance":
        def loss_fn(w: np.ndarray) -> float:
            return float(w @ posterior_covariance @ w)

        def grad_fn(w: np.ndarray) -> np.ndarray:
            return 2.0 * (posterior_covariance @ w)

    elif objective == "mean_variance_utility":
        def loss_fn(w: np.ndarray) -> float:
            ret = float(w @ posterior_mean)
            var = float(w @ posterior_covariance @ w)
            return -(ret - 0.5 * risk_aversion * var)

        def grad_fn(w: np.ndarray) -> np.ndarray:
            return -(posterior_mean - risk_aversion * (posterior_covariance @ w))

    else:
        # Default: Maximum Sharpe Ratio
        # Check economic validity: at least one asset must have worst/posterior return > Rf
        if np.max(posterior_mean) <= risk_free_rate:
            return {
                "weights": init_weights,
                "expected_return": float(init_weights @ posterior_mean),
                "volatility": float(np.sqrt(init_weights @ posterior_covariance @ init_weights)),
                "sharpe_ratio": None,
                "is_feasible": False,
                "solver_status": "infeasible_excess_returns",
                "solver_message": "All assets have posterior expected returns below or equal to risk-free rate.",
            }

        def loss_fn(w: np.ndarray) -> float:
            ret = float(w @ posterior_mean)
            vol = float(np.sqrt(max(w @ posterior_covariance @ w, 1e-12)))
            excess = ret - risk_free_rate
            if excess <= 0:
                return 1e6 - excess
            return -excess / vol

        grad_fn = None  # SciPy approximation for Sharpe ratio quotient

    res = minimize(
        loss_fn,
        init_weights,
        method="SLSQP",
        jac=grad_fn,
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-10, "maxiter": 500},
    )

    opt_weights = np.array(res.x, dtype=np.float64)
    # Numerical snap of near-zero values
    opt_weights = np.where(np.abs(opt_weights) < 1e-7, 0.0, opt_weights)
    sum_w = np.sum(opt_weights)
    if abs(sum_w) > 1e-12:
        opt_weights = opt_weights / sum_w

    exp_ret = float(opt_weights @ posterior_mean)
    vol = float(np.sqrt(max(opt_weights @ posterior_covariance @ opt_weights, 1e-12)))
    sharpe = float((exp_ret - risk_free_rate) / vol) if vol > 1e-8 else None

    return {
        "weights": opt_weights,
        "expected_return": exp_ret,
        "volatility": vol,
        "sharpe_ratio": sharpe,
        "is_feasible": bool(res.success),
        "solver_status": "converged" if res.success else "solver_failed",
        "solver_message": str(res.message),
        "iterations": int(res.nit),
    }


def compute_black_litterman_diagnostics(
    asset_order: list[str],
    equilibrium_weights: np.ndarray,
    optimal_weights: np.ndarray,
    implied_returns: np.ndarray,
    posterior_returns: np.ndarray,
    views: list[BlackLittermanView],
    p: np.ndarray,
    q: np.ndarray,
) -> dict[str, Any]:
    """
    Computes stability, active tilt, and view impact diagnostics.
    """
    n = len(asset_order)
    active_tilts = optimal_weights - equilibrium_weights
    abs_tilts = np.abs(active_tilts)
    d1_distance = float(np.sum(abs_tilts))
    max_tilt_idx = int(np.argmax(abs_tilts))
    max_tilt_asset = asset_order[max_tilt_idx]
    max_tilt_val = float(active_tilts[max_tilt_idx])

    # Concentration metrics (HHI & N_eff)
    hhi_prior = float(np.sum(equilibrium_weights ** 2))
    hhi_optimal = float(np.sum(optimal_weights ** 2))
    n_eff_prior = 1.0 / hhi_prior if hhi_prior > 1e-10 else 1.0
    n_eff_optimal = 1.0 / hhi_optimal if hhi_optimal > 1e-10 else 1.0

    # Views impact summary
    views_summary = []
    for k, view in enumerate(views):
        prior_val = float(p[k] @ implied_returns) if k < p.shape[0] else 0.0
        post_val = float(p[k] @ posterior_returns) if k < p.shape[0] else 0.0
        target = float(q[k]) if k < len(q) else view.target_return

        if view.view_type == "relative" and len(view.assets) >= 2:
            desc = f"{view.assets[0]} outperforms {view.assets[1]} by {(view.target_return * 100):.1f}%"
        else:
            desc = f"{view.assets[0]} expected return {(view.target_return * 100):.1f}%"

        views_summary.append({
            "description": desc,
            "view_type": view.view_type,
            "confidence": view.confidence,
            "target_return": target,
            "prior_expected_spread": prior_val,
            "posterior_expected_spread": post_val,
            "absorbed_difference": post_val - prior_val,
        })

    return {
        "active_tilts": {asset_order[i]: float(active_tilts[i]) for i in range(n)},
        "weight_distance_d1": d1_distance,
        "max_tilt_asset": max_tilt_asset,
        "max_tilt_value": max_tilt_val,
        "hhi_prior": hhi_prior,
        "hhi_optimal": hhi_optimal,
        "effective_assets_prior": n_eff_prior,
        "effective_assets_optimal": n_eff_optimal,
        "views_summary": views_summary,
    }
