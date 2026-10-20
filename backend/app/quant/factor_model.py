"""
Pure Numerical Financial Mathematics Core for Multi-Factor Modeling & Risk Decomposition.

Implements:
1. Ordinary Least Squares (OLS) multi-factor regression with analytical standard errors,
   t-statistics, p-values, and R-squared.
2. Factor generation from market return panels (CAPM, Fama-French proxies, Carhart momentum, PCA).
3. Barra-style structural covariance matrix construction: Sigma = B * Sigma_F * B^T + Sigma_eps.
4. Portfolio systematic vs idiosyncratic risk decomposition and factor contribution analysis.
5. Factor-constrained portfolio optimization using SciPy SLSQP.
"""

from __future__ import annotations

import math
from typing import Any, Literal
import numpy as np
from scipy import stats
from scipy.optimize import minimize


def estimate_single_asset_factor_regression(
    asset_excess_returns: np.ndarray,
    factors_matrix: np.ndarray,
    factor_names: list[str],
    annualization_factor: int = 252,
) -> dict[str, Any]:
    """
    Executes OLS regression of an asset's excess returns against a factor matrix:
        R_i^e = alpha_i + sum_k beta_{i,k} * F_k + eps_i

    Args:
        asset_excess_returns: 1D array of shape (T,)
        factors_matrix: 2D array of shape (T, K)
        factor_names: List of K factor names
        annualization_factor: Trading periods per year (default 252)

    Returns:
        Dictionary containing alpha, betas, standard errors, t-statistics, p-values,
        specific variance, and R-squared.
    """
    y = np.asarray(asset_excess_returns, dtype=np.float64)
    F = np.asarray(factors_matrix, dtype=np.float64)

    T = len(y)
    K = F.shape[1] if F.ndim > 1 else 1
    if F.ndim == 1:
        F = F.reshape(-1, 1)

    if T != F.shape[0]:
        raise ValueError(f"Length mismatch: asset returns ({T}) vs factors ({F.shape[0]}).")
    if T <= K + 1:
        raise ValueError(f"Insufficient observations: {T} observations for {K} factors.")
    if np.isnan(y).any() or np.isinf(y).any():
        raise ValueError("Asset returns contain NaN or infinite values.")
    if np.isnan(F).any() or np.isinf(F).any():
        raise ValueError("Factors matrix contains NaN or infinite values.")

    # Design matrix X = [1, F_1, ..., F_K]
    X = np.column_stack([np.ones(T, dtype=np.float64), F])

    # OLS estimation via lstsq
    theta, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)

    # Compute residuals and specific variance
    y_pred = X @ theta
    eps = y - y_pred
    df = T - K - 1
    rss = np.sum(eps**2)
    s_eps_sq = rss / df  # Specific variance per period

    # Total sum of squares for R^2
    y_mean = np.mean(y)
    tss = np.sum((y - y_mean) ** 2)
    r_squared = float(1.0 - rss / tss) if tss > 1e-12 else 0.0
    r_squared_adj = float(1.0 - (1.0 - r_squared) * (T - 1) / df) if df > 0 else r_squared

    # Covariance of coefficients: (X^T X)^-1 * s_eps_sq
    try:
        XtX_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        XtX_inv = np.linalg.pinv(X.T @ X)

    var_theta = np.diag(XtX_inv) * s_eps_sq
    se_theta = np.sqrt(np.maximum(1e-16, var_theta))

    # t-statistics and two-sided p-values
    t_stats = theta / se_theta
    p_values = [2.0 * float(stats.t.sf(abs(t), df=df)) for t in t_stats]

    # Annualize alpha and specific variance
    alpha_annualized = float(theta[0] * annualization_factor)
    alpha_se_annualized = float(se_theta[0] * math.sqrt(annualization_factor))
    specific_variance_annualized = float(s_eps_sq * annualization_factor)

    betas_dict: dict[str, dict[str, float]] = {}
    for k in range(K):
        fname = factor_names[k] if k < len(factor_names) else f"Factor_{k+1}"
        betas_dict[fname] = {
            "beta": float(round(theta[k + 1], 6)),
            "stderr": float(round(se_theta[k + 1], 6)),
            "tstat": float(round(t_stats[k + 1], 4)),
            "pvalue": float(round(p_values[k + 1], 6)),
        }

    return {
        "alpha_annualized": float(round(alpha_annualized, 6)),
        "alpha_stderr": float(round(alpha_se_annualized, 6)),
        "alpha_tstat": float(round(t_stats[0], 4)),
        "alpha_pvalue": float(round(p_values[0], 6)),
        "betas": betas_dict,
        "r_squared": float(round(r_squared, 4)),
        "r_squared_adj": float(round(r_squared_adj, 4)),
        "specific_variance_annualized": float(round(specific_variance_annualized, 8)),
        "specific_volatility_annualized": float(round(math.sqrt(max(0.0, specific_variance_annualized)), 6)),
    }


def construct_synthetic_factors_from_returns(
    returns_df: np.ndarray,
    factor_model: Literal["capm", "ff3", "carhart4", "pca"] = "carhart4",
    num_pca_factors: int = 3,
    risk_free_rate: float = 0.02,
    annualization_factor: int = 252,
) -> tuple[np.ndarray, list[str]]:
    """
    Constructs deterministic benchmark factor return time-series directly from an asset returns matrix
    without fabricating external data:
    - CAPM: Market factor (MKT) = equal-weight cross-sectional excess return.
    - FF3: Adds Size (SMB = bottom-volatility minus top-volatility proxy) and Value (HML = reversal spread).
    - Carhart4: Adds Momentum (MOM = high recent return minus low recent return).
    - PCA: Top K eigenvectors from standardized returns.

    Returns:
        tuple of (factors_matrix of shape (T, K), list of factor names).
    """
    R = np.asarray(returns_df, dtype=np.float64)
    T, N = R.shape
    daily_rf = risk_free_rate / annualization_factor

    # Market Factor: Equal-weighted portfolio excess return
    mkt_raw = np.mean(R, axis=1)
    mkt_excess = mkt_raw - daily_rf

    if factor_model == "capm":
        return mkt_excess.reshape(-1, 1), ["MKT"]

    elif factor_model in ("ff3", "carhart4"):
        # Asset total volatilities for size proxy (low vol ~ large cap, high vol ~ small cap)
        asset_vols = np.std(R, axis=0)
        sort_vol_idx = np.argsort(asset_vols)
        n_third = max(1, N // 3)

        small_idx = sort_vol_idx[-n_third:]  # higher vol ~ small cap
        big_idx = sort_vol_idx[:n_third]     # lower vol ~ big cap
        smb = np.mean(R[:, small_idx], axis=1) - np.mean(R[:, big_idx], axis=1)

        # Value Proxy (HML): based on cumulative return divergence / value spread
        cum_ret = np.prod(1.0 + R, axis=0) - 1.0
        sort_val_idx = np.argsort(cum_ret)
        value_idx = sort_val_idx[:n_third]   # lagged performers ~ value proxy
        growth_idx = sort_val_idx[-n_third:] # high growth performers
        hml = np.mean(R[:, value_idx], axis=1) - np.mean(R[:, growth_idx], axis=1)

        if factor_model == "ff3":
            F = np.column_stack([mkt_excess, smb, hml])
            return F, ["MKT", "SMB", "HML"]

        # Carhart 4: Adds Momentum (MOM)
        # 1-month rolling return for momentum spread
        window = min(21, T // 4)
        rolling_mom = np.zeros(N)
        for i in range(N):
            rolling_mom[i] = np.mean(R[-window:, i]) if T >= window else np.mean(R[:, i])

        sort_mom_idx = np.argsort(rolling_mom)
        losers_idx = sort_mom_idx[:n_third]
        winners_idx = sort_mom_idx[-n_third:]
        mom = np.mean(R[:, winners_idx], axis=1) - np.mean(R[:, losers_idx], axis=1)

        F = np.column_stack([mkt_excess, smb, hml, mom])
        return F, ["MKT", "SMB", "HML", "MOM"]

    elif factor_model == "pca":
        k = max(1, min(num_pca_factors, N, T - 1))
        # Standardize returns
        means = np.mean(R, axis=0)
        stds = np.std(R, axis=0)
        stds[stds < 1e-12] = 1.0
        R_std = (R - means) / stds

        # SVD of standardized returns
        U, S, Vt = np.linalg.svd(R_std, full_matrices=False)
        # Principal component scores: R_std @ V^T = U * S
        F_pca = R_std @ Vt[:k].T
        names = [f"PC_{i+1}" for i in range(k)]
        return F_pca, names

    raise ValueError(f"Unsupported factor model '{factor_model}'.")


def compute_structural_covariance_matrix(
    factor_loadings: np.ndarray,
    factor_covariance: np.ndarray,
    specific_variances: np.ndarray,
) -> np.ndarray:
    """
    Computes structural Barra-style multi-factor covariance matrix:
        Sigma_model = B * Sigma_F * B^T + Sigma_eps

    Args:
        factor_loadings: Matrix B of shape (N, K)
        factor_covariance: Matrix Sigma_F of shape (K, K)
        specific_variances: 1D array of shape (N,) containing specific variances

    Returns:
        Symmetric positive-definite covariance matrix of shape (N, N).
    """
    B = np.asarray(factor_loadings, dtype=np.float64)
    Sigma_F = np.asarray(factor_covariance, dtype=np.float64)
    s_eps = np.asarray(specific_variances, dtype=np.float64)

    # Systematic covariance B * Sigma_F * B^T
    systematic_cov = B @ Sigma_F @ B.T

    # Total covariance
    cov_model = systematic_cov + np.diag(s_eps)

    # Enforce exact mathematical symmetry
    cov_model = 0.5 * (cov_model + cov_model.T)
    return cov_model


def decompose_portfolio_factor_risk(
    weights: np.ndarray,
    factor_loadings: np.ndarray,
    factor_covariance: np.ndarray,
    specific_variances: np.ndarray,
    factor_names: list[str],
) -> dict[str, Any]:
    """
    Performs exact portfolio systematic vs idiosyncratic risk decomposition:
        sigma_p^2 = beta_p^T * Sigma_F * beta_p + w^T * Sigma_eps * w

    Returns:
        Comprehensive risk decomposition metrics including portfolio betas,
        systematic volatility, idiosyncratic volatility, percentage shares,
        and individual factor contributions.
    """
    w = np.asarray(weights, dtype=np.float64)
    B = np.asarray(factor_loadings, dtype=np.float64)
    Sigma_F = np.asarray(factor_covariance, dtype=np.float64)
    s_eps = np.asarray(specific_variances, dtype=np.float64)

    K = len(factor_names)

    # Portfolio factor loadings beta_p = B^T * w (shape K,)
    beta_p = B.T @ w

    # Systematic variance: beta_p^T * Sigma_F * beta_p
    sys_var = float(beta_p.T @ Sigma_F @ beta_p)
    sys_var = max(0.0, sys_var)

    # Idiosyncratic variance: sum_i w_i^2 * s_eps_i
    idio_var = float(np.sum((w**2) * s_eps))
    idio_var = max(0.0, idio_var)

    # Total model portfolio variance
    total_var = sys_var + idio_var
    total_vol = math.sqrt(max(1e-14, total_var))
    sys_vol = math.sqrt(sys_var)
    idio_vol = math.sqrt(idio_var)

    # Percentage shares
    sys_share_pct = float((sys_var / total_var) * 100.0) if total_var > 1e-12 else 0.0
    idio_share_pct = float((idio_var / total_var) * 100.0) if total_var > 1e-12 else 0.0

    # Individual factor variance attribution
    # Total factor variance = beta_p^T * Sigma_F * beta_p = sum_k beta_p,k * (Sigma_F * beta_p)_k
    marginal_factor_contrib = Sigma_F @ beta_p
    total_factor_contrib = beta_p * marginal_factor_contrib

    factor_contrib_dict: dict[str, dict[str, float]] = {}
    for k in range(K):
        fname = factor_names[k]
        tfc = float(total_factor_contrib[k])
        pct_share = float((tfc / sys_var) * 100.0) if sys_var > 1e-12 else 0.0
        factor_contrib_dict[fname] = {
            "exposure": float(round(beta_p[k], 4)),
            "marginal_contrib": float(round(marginal_factor_contrib[k], 6)),
            "total_variance_contrib": float(round(tfc, 8)),
            "pct_of_systematic_risk": float(round(pct_share, 2)),
        }

    return {
        "portfolio_betas": {factor_names[k]: float(round(beta_p[k], 4)) for k in range(K)},
        "total_volatility": float(round(total_vol, 6)),
        "systematic_volatility": float(round(sys_vol, 6)),
        "idiosyncratic_volatility": float(round(idio_vol, 6)),
        "systematic_variance": float(round(sys_var, 8)),
        "idiosyncratic_variance": float(round(idio_var, 8)),
        "total_variance": float(round(total_var, 8)),
        "systematic_share_pct": float(round(sys_share_pct, 2)),
        "idiosyncratic_share_pct": float(round(idio_share_pct, 2)),
        "factor_contributions": factor_contrib_dict,
    }


def solve_factor_constrained_portfolio(
    expected_returns: np.ndarray,
    factor_loadings: np.ndarray,
    factor_covariance: np.ndarray,
    specific_variances: np.ndarray,
    factor_names: list[str],
    objective: Literal["min_variance", "max_sharpe", "max_utility"] = "min_variance",
    factor_constraints: dict[str, tuple[float | None, float | None]] | None = None,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
    risk_free_rate: float = 0.02,
    risk_aversion: float = 2.5,
) -> tuple[np.ndarray, bool, str]:
    """
    Solves factor-constrained portfolio optimization via SciPy SLSQP:
        min w^T Sigma_model w   or   max Sharpe   or   max w^T mu - 0.5 * gamma * w^T Sigma w
    subject to:
        sum w_i = 1.0
        w_min <= w_i <= w_max
        beta_min <= B^T * w <= beta_max for constrained factors

    Returns:
        tuple of (optimal_weights, is_feasible, solver_message).
    """
    mu = np.asarray(expected_returns, dtype=np.float64)
    B = np.asarray(factor_loadings, dtype=np.float64)
    Sigma_F = np.asarray(factor_covariance, dtype=np.float64)
    s_eps = np.asarray(specific_variances, dtype=np.float64)

    N, K = B.shape
    Sigma = compute_structural_covariance_matrix(B, Sigma_F, s_eps)

    # Initial guess: equal weights
    w0 = np.full(N, 1.0 / N, dtype=np.float64)

    # Bounds
    bounds = [(float(min_weight), float(max_weight)) for _ in range(N)]

    # Budget constraint: sum w = 1.0
    constraints: list[dict[str, Any]] = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0, "jac": lambda w: np.ones(N)}
    ]

    # Factor exposure constraints
    if factor_constraints:
        for fname, (low, high) in factor_constraints.items():
            if fname in factor_names:
                k = factor_names.index(fname)
                b_k = B[:, k]

                if low is not None:
                    # B^T * w >= low  <=>  B^T * w - low >= 0
                    constraints.append({
                        "type": "ineq",
                        "fun": lambda w, k=k, bound=low: np.dot(B[:, k], w) - bound,
                        "jac": lambda w, k=k: B[:, k],
                    })
                if high is not None:
                    # B^T * w <= high <=>  high - B^T * w >= 0
                    constraints.append({
                        "type": "ineq",
                        "fun": lambda w, k=k, bound=high: bound - np.dot(B[:, k], w),
                        "jac": lambda w, k=k: -B[:, k],
                    })

    # Objective functions and analytical gradients
    if objective == "min_variance":
        def obj(w: np.ndarray) -> float:
            return float(0.5 * w.T @ Sigma @ w)

        def grad(w: np.ndarray) -> np.ndarray:
            return Sigma @ w

    elif objective == "max_utility":
        gamma = max(0.1, float(risk_aversion))

        def obj(w: np.ndarray) -> float:
            return float(- (w.T @ mu - 0.5 * gamma * (w.T @ Sigma @ w)))

        def grad(w: np.ndarray) -> np.ndarray:
            return -mu + gamma * (Sigma @ w)

    else:  # max_sharpe
        rf = float(risk_free_rate)

        def obj(w: np.ndarray) -> float:
            port_ret = float(w.T @ mu)
            port_vol = math.sqrt(max(1e-12, float(w.T @ Sigma @ w)))
            return - float((port_ret - rf) / port_vol)

        def grad(w: np.ndarray) -> np.ndarray:
            port_ret = float(w.T @ mu)
            var = max(1e-12, float(w.T @ Sigma @ w))
            port_vol = math.sqrt(var)
            diff = port_ret - rf
            # d/dw [ -(w^T mu - rf) / sqrt(w^T Sigma w) ]
            # = - mu / vol + diff * (Sigma w) / (vol^3)
            return -mu / port_vol + (diff / (var * port_vol)) * (Sigma @ w)

    res = minimize(
        obj,
        w0,
        jac=grad,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-9},
    )

    if res.success:
        w_opt = res.x
        # Project onto exact simplex sum
        w_opt = np.maximum(min_weight, np.minimum(max_weight, w_opt))
        w_opt = w_opt / np.sum(w_opt)
        return w_opt, True, "Factor-constrained optimization converged successfully."
    else:
        # Fallback to bounded equal weights if solver failed
        return w0, False, f"Solver failed to converge: {res.message}"
