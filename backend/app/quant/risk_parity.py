"""
Equal Risk Contribution (ERC) & Hierarchical Risk Parity (HRP) Quantitative Module.

This module provides pure mathematical functions for:
1. Euler's decomposition of portfolio risk (MRC, TRC, %RC).
2. Equal Risk Contribution (ERC) and general Risk Budgeting optimization via convex log-barrier.
3. Hierarchical Risk Parity (HRP) via correlation distance clustering, quasi-diagonalization,
   and recursive bisection (Marcos López de Prado, 2016).
4. Inverse-variance and equal-weight benchmark portfolio construction.
5. Risk concentration diagnostics (Risk Gini, Effective Number of Bets, Diversification Ratio).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from scipy.cluster.hierarchy import linkage, to_tree
from scipy.optimize import minimize
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


def calculate_risk_contributions(
    weights: np.ndarray,
    covariance: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """
    Computes Euler risk decomposition for a portfolio:
    - Marginal Risk Contribution (MRC): d(sigma_p)/d(w_i) = (Sigma * w)_i / sigma_p
    - Total Risk Contribution (TRC): w_i * MRC_i = w_i * (Sigma * w)_i / sigma_p
    - Percentage Risk Contribution (%RC): TRC_i / sigma_p = w_i * (Sigma * w)_i / (w^T * Sigma * w)
    - Portfolio Volatility (sigma_p): sqrt(w^T * Sigma * w)

    Returns:
        (mrc, trc, prc, portfolio_volatility)
    """
    w = np.asarray(weights, dtype=np.float64)
    sigma = np.asarray(covariance, dtype=np.float64)

    port_var = float(w @ sigma @ w)
    port_vol = float(np.sqrt(max(port_var, 1e-12)))

    cov_w = sigma @ w
    mrc = cov_w / port_vol
    trc = w * mrc

    if port_var > 1e-12:
        prc = trc / port_vol
    else:
        prc = np.full_like(w, 1.0 / len(w))

    return mrc, trc, prc, port_vol


def solve_equal_risk_contribution(
    covariance: np.ndarray,
    risk_budgets: np.ndarray | None = None,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
) -> dict[str, Any]:
    """
    Solves for the Equal Risk Contribution (ERC) or general Risk Budgeting portfolio.

    For unconstrained long-only portfolios (min_weight=0, max_weight=1), uses the strictly
    convex log-barrier formulation (Maillard, Roncalli & Teïletche 2010):
        min_x  0.5 * x^T * Sigma * x - sum(b_i * ln(x_i))  s.t. x > 0
    Normalized: w_i = x_i / sum(x_j)

    For box-constrained portfolios, solves via SLSQP minimizing the sum of squared differences
    in risk contributions: sum((%RC_i - b_i)^2).

    Args:
        covariance: Positive definite asset covariance matrix (N x N).
        risk_budgets: Target risk budget vector b (N,), sum(b)=1, b_i > 0. Defaults to 1/N.
        min_weight: Minimum asset weight bound.
        max_weight: Maximum asset weight bound.

    Returns:
        Dictionary containing optimal weights, risk contributions, diagnostics, and status.
    """
    n = covariance.shape[0]
    if risk_budgets is None:
        b = np.full(n, 1.0 / n, dtype=np.float64)
    else:
        b = np.asarray(risk_budgets, dtype=np.float64)
        if len(b) != n or np.any(b <= 0):
            raise ValueError("Risk budgets must be strictly positive and match covariance dimension.")
        b = b / np.sum(b)

    volatilities = np.sqrt(np.maximum(np.diag(covariance), 1e-12))
    # Initial guess: inverse volatility
    inv_vol = 1.0 / volatilities
    x0 = inv_vol / np.sum(inv_vol)

    # Use strictly convex log-barrier if unconstrained long-only
    is_standard_bounds = (abs(min_weight - 0.0) < 1e-6 and abs(max_weight - 1.0) < 1e-6)

    if is_standard_bounds:
        def objective(x: np.ndarray) -> float:
            # 0.5 * x^T * Sigma * x - sum(b_i * ln(x_i))
            x_safe = np.maximum(x, 1e-10)
            return float(0.5 * (x_safe @ covariance @ x_safe) - np.sum(b * np.log(x_safe)))

        def gradient(x: np.ndarray) -> np.ndarray:
            x_safe = np.maximum(x, 1e-10)
            return (covariance @ x_safe) - (b / x_safe)

        bounds = tuple((1e-8, None) for _ in range(n))
        res = minimize(
            objective,
            x0,
            jac=gradient,
            bounds=bounds,
            method="L-BFGS-B",
            options={"ftol": 1e-14, "gtol": 1e-10, "maxiter": 500},
        )

        if res.success and np.sum(res.x) > 1e-12:
            w_opt = res.x / np.sum(res.x)
            status = "optimal"
            is_feasible = True
            msg = "Convex log-barrier optimization converged successfully."
        else:
            w_opt = x0
            status = "suboptimal"
            is_feasible = False
            msg = str(res.message)
    else:
        # Box-constrained SLSQP minimizing squared risk-budget dispersion
        def disp_objective(w: np.ndarray) -> float:
            _, _, prc, _ = calculate_risk_contributions(w, covariance)
            return float(np.sum((prc - b) ** 2))

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = tuple((min_weight, max_weight) for _ in range(n))
        res = minimize(
            disp_objective,
            x0,
            bounds=bounds,
            constraints=constraints,
            method="SLSQP",
            options={"ftol": 1e-12, "maxiter": 500},
        )

        w_opt = np.clip(res.x, min_weight, max_weight)
        w_opt = w_opt / np.sum(w_opt)
        is_feasible = bool(res.success)
        status = "optimal" if res.success else "numerical_warning"
        msg = str(res.message)

    mrc, trc, prc, port_vol = calculate_risk_contributions(w_opt, covariance)
    diagnostics = compute_risk_parity_diagnostics(w_opt, covariance, prc)

    return {
        "weights": w_opt,
        "marginal_risk_contributions": mrc,
        "total_risk_contributions": trc,
        "percentage_risk_contributions": prc,
        "portfolio_volatility": port_vol,
        "risk_gini_coefficient": diagnostics["risk_gini_coefficient"],
        "effective_number_of_bets": diagnostics["effective_number_of_bets"],
        "diversification_ratio": diagnostics["diversification_ratio"],
        "is_feasible": is_feasible,
        "solver_status": status,
        "solver_message": msg,
    }


def _get_quasi_diag_order(linkage_matrix: np.ndarray) -> list[int]:
    """
    Extracts leaf order from a hierarchical linkage tree to perform quasi-diagonalization.
    """
    root = to_tree(linkage_matrix, rd=False)

    def _traverse(node: Any) -> list[int]:
        if node.is_leaf():
            return [node.id]
        return _traverse(node.left) + _traverse(node.right)

    return _traverse(root)


def solve_hierarchical_risk_parity(
    covariance: np.ndarray,
    correlation: np.ndarray | None = None,
    linkage_method: str = "single",
) -> dict[str, Any]:
    """
    Solves for the Hierarchical Risk Parity (HRP) portfolio (Marcos López de Prado, 2016):
    1. Distance matrix computation D_ij = sqrt(0.5 * (1 - rho_ij)).
    2. Hierarchical clustering using linkage.
    3. Quasi-diagonalization to reorder assets contiguously.
    4. Recursive bisection allocating weights by inverse cluster variance.

    HRP requires zero matrix inversions and is immune to ill-conditioned covariance matrices.

    Args:
        covariance: Asset covariance matrix (N x N).
        correlation: Optional pre-computed correlation matrix (N x N).
        linkage_method: Hierarchical clustering linkage ('single', 'complete', 'average').

    Returns:
        Dictionary containing optimal weights, risk contributions, reordered asset indices,
        and diagnostics.
    """
    n = covariance.shape[0]
    if n == 1:
        w_opt = np.array([1.0], dtype=np.float64)
        mrc, trc, prc, port_vol = calculate_risk_contributions(w_opt, covariance)
        return {
            "weights": w_opt,
            "marginal_risk_contributions": mrc,
            "total_risk_contributions": trc,
            "percentage_risk_contributions": prc,
            "portfolio_volatility": port_vol,
            "reordered_indices": [0],
            "risk_gini_coefficient": 0.0,
            "effective_number_of_bets": 1.0,
            "diversification_ratio": 1.0,
            "is_feasible": True,
            "solver_status": "optimal",
            "solver_message": "Single asset universe.",
        }

    # Step 1: Correlation & Distance Matrix
    if correlation is None:
        vols = np.sqrt(np.maximum(np.diag(covariance), 1e-12))
        corr = covariance / np.outer(vols, vols)
        np.fill_diagonal(corr, 1.0)
    else:
        corr = correlation.copy()

    # Metric distance matrix D_ij = sqrt(0.5 * (1 - rho_ij))
    dist = np.sqrt(np.maximum(0.5 * (1.0 - corr), 0.0))
    np.fill_diagonal(dist, 0.0)

    # Condensed distance matrix for scipy linkage
    condensed_dist = squareform(dist, checks=False)

    # Step 2: Hierarchical Clustering
    valid_methods = {"single", "complete", "average"}
    if linkage_method not in valid_methods:
        linkage_method = "single"
    z = linkage(condensed_dist, method=linkage_method)

    # Step 3: Quasi-Diagonalization (leaf ordering)
    sorted_indices = _get_quasi_diag_order(z)

    # Step 4: Recursive Bisection
    weights = np.ones(n, dtype=np.float64)
    cluster_items = [sorted_indices]

    while len(cluster_items) > 0:
        # Bisect clusters
        next_clusters = []
        for cluster in cluster_items:
            if len(cluster) > 1:
                mid = len(cluster) // 2
                c1 = cluster[:mid]
                c2 = cluster[mid:]

                # Compute variance of cluster 1: V1 = w1^T * Sigma1 * w1
                cov1 = covariance[np.ix_(c1, c1)]
                inv_diag1 = 1.0 / np.maximum(np.diag(cov1), 1e-12)
                w1 = inv_diag1 / np.sum(inv_diag1)
                v1 = float(w1 @ cov1 @ w1)

                # Compute variance of cluster 2: V2 = w2^T * Sigma2 * w2
                cov2 = covariance[np.ix_(c2, c2)]
                inv_diag2 = 1.0 / np.maximum(np.diag(cov2), 1e-12)
                w2 = inv_diag2 / np.sum(inv_diag2)
                v2 = float(w2 @ cov2 @ w2)

                # Allocation factor alpha = 1 - V1 / (V1 + V2) = V2 / (V1 + V2)
                total_v = v1 + v2
                alpha = 1.0 - (v1 / total_v) if total_v > 1e-12 else 0.50

                # Weight updates
                for idx in c1:
                    weights[idx] *= alpha
                for idx in c2:
                    weights[idx] *= (1.0 - alpha)

                if len(c1) > 1:
                    next_clusters.append(c1)
                if len(c2) > 1:
                    next_clusters.append(c2)

        cluster_items = next_clusters

    # Normalize weights
    w_opt = weights / np.sum(weights)

    mrc, trc, prc, port_vol = calculate_risk_contributions(w_opt, covariance)
    diagnostics = compute_risk_parity_diagnostics(w_opt, covariance, prc)

    return {
        "weights": w_opt,
        "marginal_risk_contributions": mrc,
        "total_risk_contributions": trc,
        "percentage_risk_contributions": prc,
        "portfolio_volatility": port_vol,
        "reordered_indices": sorted_indices,
        "risk_gini_coefficient": diagnostics["risk_gini_coefficient"],
        "effective_number_of_bets": diagnostics["effective_number_of_bets"],
        "diversification_ratio": diagnostics["diversification_ratio"],
        "is_feasible": True,
        "solver_status": "optimal",
        "solver_message": "Hierarchical tree clustering and recursive bisection completed successfully.",
    }


def solve_inverse_variance_portfolio(covariance: np.ndarray) -> np.ndarray:
    """
    Computes Inverse-Variance (IV) portfolio weights:
    w_i = (1 / sigma_i^2) / sum(1 / sigma_j^2)
    """
    variances = np.maximum(np.diag(covariance), 1e-12)
    inv_var = 1.0 / variances
    return inv_var / np.sum(inv_var)


def compute_risk_parity_diagnostics(
    weights: np.ndarray,
    covariance: np.ndarray,
    percentage_risk_contributions: np.ndarray | None = None,
) -> dict[str, float]:
    """
    Computes comprehensive risk parity and diversification metrics:
    - Risk Gini coefficient G_risk in [0, 1]
    - Effective Number of Bets (Meucci 2009)
    - Effective Number of Constituents (Inverse Herfindahl of weights)
    - Diversification Ratio (DR >= 1.0)
    """
    w = np.asarray(weights, dtype=np.float64)
    n = len(w)

    if percentage_risk_contributions is None:
        _, _, prc, port_vol = calculate_risk_contributions(w, covariance)
    else:
        prc = np.asarray(percentage_risk_contributions, dtype=np.float64)
        port_vol = float(np.sqrt(max(w @ covariance @ w, 1e-12)))

    # Risk Gini Coefficient: G = sum_i sum_j |prc_i - prc_j| / (2 * N * sum(prc))
    prc_diff = np.abs(prc[:, None] - prc[None, :])
    risk_gini = float(np.sum(prc_diff) / (2.0 * n * max(np.sum(prc), 1e-12)))

    # Effective Number of Bets: exp(- sum(prc * ln(prc)))
    prc_clipped = np.maximum(prc, 1e-12)
    entropy = -np.sum(prc_clipped * np.log(prc_clipped))
    effective_bets = float(np.exp(entropy))

    # Weight Herfindahl: HHI = sum(w_i^2), N_eff = 1 / HHI
    hhi = float(np.sum(w ** 2))
    effective_constituents = float(1.0 / max(hhi, 1e-12))

    # Diversification Ratio: DR = sum(w_i * sigma_i) / sigma_p
    asset_vols = np.sqrt(np.maximum(np.diag(covariance), 1e-12))
    weighted_vol = float(np.sum(w * asset_vols))
    diversification_ratio = float(weighted_vol / max(port_vol, 1e-12))

    return {
        "risk_gini_coefficient": round(risk_gini, 6),
        "effective_number_of_bets": round(effective_bets, 4),
        "effective_number_of_constituents": round(effective_constituents, 4),
        "diversification_ratio": round(diversification_ratio, 4),
        "herfindahl_index": round(hhi, 6),
    }
