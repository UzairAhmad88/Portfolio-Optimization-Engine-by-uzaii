"""
Pure Numerical Financial Mathematics Engine for Copula-Based Tail Dependency,
Non-Linear Extreme Co-Movement & Tail Risk Parity Portfolio Allocation.

Implements:
1. Sklar's theorem probability integral transforms:
   - Non-parametric empirical rank pseudo-observations: u_{i,t} = rank(x_{i,t}) / (T + 1) in (0, 1).
   - Parametric Student-t marginal probability integral transforms.
2. Copula estimation (Canonical Maximum Likelihood / Inversion of Kendall's Tau):
   - Bivariate & Pairwise Clayton Copula (asymmetric lower tail crash risk, lambda_L = 2^{-1/theta}, lambda_U = 0).
   - Bivariate & Pairwise Gumbel Copula (asymmetric upper tail co-movement, lambda_U = 2 - 2^{1/theta}, lambda_L = 0).
   - Bivariate & Multivariate Student-t Copula (symmetric fat tails, lambda_L = lambda_U = 2 * t_{nu+1}(-sqrt((nu+1)(1-rho)/(1+rho)))).
   - Bivariate & Multivariate Gaussian Copula (baseline zero tail dependence, lambda_L = lambda_U = 0).
   - Best-fit copula selection via Akaike Information Criterion (AIC) and Bayesian Information Criterion (BIC).
3. Multivariate dependent return simulation:
   - Exact Marshall-Olkin Archimedean generator for Clayton copula.
   - Cholesky decomposition & normal/Student-t multivariate generators for Gaussian and t-copula.
   - Conditional quantile inversion for Gumbel copula.
   - Inverse probability integral transform to empirical/parametric return space.
   - Deterministic random seed reproducibility.
4. Portfolio Tail Risk Measurement & Tail Risk Parity (TRP) Allocation:
   - Loss convention: L = -R_p.
   - Value at Risk (VaR_alpha) and Conditional Value at Risk (CVaR_alpha / Expected Shortfall).
   - Exact Euler Tail Risk Contributions (TRC_i = -w_i * E[R_i | L >= VaR_alpha]).
   - Additive Euler decomposition identity verification: sum_i TRC_i == CVaR_alpha.
   - SLSQP non-linear optimization for Tail Risk Parity (min dispersion of TRCs) subject to full investment (sum w = 1) and long-only (w >= 0).
   - Comparative benchmarking against Equal-Weight (1/N) and Inverse-Volatility portfolios.
"""

from __future__ import annotations

import math
from typing import Any, Literal
import numpy as np
from scipy import optimize, stats


def compute_pseudo_observations(
    returns: np.ndarray,
    method: Literal["empirical", "student_t"] = "empirical",
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Transforms return observations X into uniform pseudo-observations U in (0, 1).

    Parameters:
        returns: (T, N) float64 array of asset returns.
        method: "empirical" (rank-based) or "student_t" (parametric).

    Returns:
        U: (T, N) float64 array of uniform variables in (0, 1).
        metadata: fitting parameters and marginal diagnostics.
    """
    T, N = returns.shape
    if T < 10:
        raise ValueError(f"Insufficient observations (T={T}, min 10 required) for copula estimation.")

    # Guard against constant or non-finite series
    for j in range(N):
        col = returns[:, j]
        if not np.all(np.isfinite(col)):
            raise ValueError(f"Non-finite values detected in asset column {j}.")
        if np.std(col) < 1e-12:
            raise ValueError(f"Degenerate constant return series detected in asset column {j}.")

    U = np.zeros((T, N), dtype=np.float64)
    marginal_params: list[dict[str, Any]] = []

    if method == "empirical":
        for j in range(N):
            col = returns[:, j]
            # 1-based ranks: rank / (T + 1) guarantees U in [1/(T+1), T/(T+1)] strictly in (0, 1)
            ranks = stats.rankdata(col, method="average")
            U[:, j] = ranks / (T + 1.0)
            marginal_params.append({
                "asset_index": j,
                "method": "empirical",
                "mean": float(np.mean(col)),
                "std": float(np.std(col)),
                "skew": float(stats.skew(col)),
                "kurtosis": float(stats.kurtosis(col)),
            })
    else:
        for j in range(N):
            col = returns[:, j]
            try:
                df, loc, scale = stats.t.fit(col)
                df = max(2.1, float(df))
                scale = max(1e-8, float(scale))
                u_col = stats.t.cdf(col, df=df, loc=loc, scale=scale)
                # Clip to prevent numerical underflow/overflow at extreme boundaries
                U[:, j] = np.clip(u_col, 1e-6, 1.0 - 1e-6)
                marginal_params.append({
                    "asset_index": j,
                    "method": "student_t",
                    "df": df,
                    "loc": float(loc),
                    "scale": float(scale),
                })
            except Exception:
                # Fallback to empirical rank if parametric fit fails
                ranks = stats.rankdata(col, method="average")
                U[:, j] = ranks / (T + 1.0)
                marginal_params.append({
                    "asset_index": j,
                    "method": "empirical_fallback",
                    "mean": float(np.mean(col)),
                    "std": float(np.std(col)),
                })

    return U, {"method": method, "marginals": marginal_params}


# ============================================================================
# Pairwise Bivariate Copula Fitting & Tail Dependence
# ============================================================================

def fit_clayton_copula(u1: np.ndarray, u2: np.ndarray) -> dict[str, Any]:
    """
    Fits bivariate Clayton copula via Canonical Maximum Likelihood (CML)
    initialized from Kendall's tau inversion.

    Formulas:
        C_theta(u1, u2) = (u1^{-theta} + u2^{-theta} - 1)^{-1/theta}, theta > 0
        lambda_L = 2^{-1/theta}, lambda_U = 0
        tau = theta / (theta + 2) => theta_tau = 2*tau / (1 - tau)
    """
    T = len(u1)
    tau, _ = stats.kendalltau(u1, u2)
    tau_val = float(tau) if np.isfinite(tau) else 0.0

    # Invert tau for initial estimate (Clayton only models positive dependence tau > 0)
    pos_tau = max(0.01, min(0.95, tau_val))
    theta_init = 2.0 * pos_tau / (1.0 - pos_tau)

    # Log-likelihood of Clayton copula
    def neg_log_lik(theta_arr: np.ndarray) -> float:
        th = float(theta_arr[0])
        if th <= 1e-5 or th > 50.0:
            return 1e10
        # Term 1: T * ln(1 + theta)
        term1 = T * math.log(1.0 + th)
        # Term 2: -(1 + theta) * sum(ln(u1) + ln(u2))
        term2 = -(1.0 + th) * np.sum(np.log(u1) + np.log(u2))
        # Term 3: -(2 + 1/theta) * sum(ln(u1^{-theta} + u2^{-theta} - 1))
        base = np.power(u1, -th) + np.power(u2, -th) - 1.0
        base = np.maximum(1e-12, base)
        term3 = -(2.0 + 1.0 / th) * np.sum(np.log(base))
        ll = term1 + term2 + term3
        return -ll if np.isfinite(ll) else 1e10

    res = optimize.minimize(
        neg_log_lik,
        x0=[theta_init],
        bounds=[(0.01, 40.0)],
        method="L-BFGS-B",
    )

    theta = float(res.x[0]) if res.success and res.x[0] > 0 else theta_init
    theta = max(0.01, min(40.0, theta))
    log_lik = -float(neg_log_lik(np.array([theta])))

    # Theoretical tail dependence
    lambda_l = math.pow(2.0, -1.0 / theta)
    lambda_u = 0.0

    # AIC / BIC (k = 1 parameter)
    aic = 2.0 * 1 - 2.0 * log_lik
    bic = 1.0 * math.log(T) - 2.0 * log_lik

    return {
        "copula_type": "clayton",
        "theta": theta,
        "kendall_tau": tau_val,
        "log_likelihood": log_lik,
        "lower_tail_dependence": lambda_l,
        "upper_tail_dependence": lambda_u,
        "aic": aic,
        "bic": bic,
        "converged": bool(res.success),
    }


def fit_gumbel_copula(u1: np.ndarray, u2: np.ndarray) -> dict[str, Any]:
    """
    Fits bivariate Gumbel copula via CML initialized from Kendall's tau inversion.

    Formulas:
        C_theta(u1, u2) = exp( - [ (-ln u1)^theta + (-ln u2)^theta ]^{1/theta} ), theta >= 1
        lambda_L = 0, lambda_U = 2 - 2^{1/theta}
        tau = 1 - 1/theta => theta_tau = 1 / (1 - tau)
    """
    T = len(u1)
    tau, _ = stats.kendalltau(u1, u2)
    tau_val = float(tau) if np.isfinite(tau) else 0.0

    pos_tau = max(0.0, min(0.95, tau_val))
    theta_init = 1.0 / (1.0 - pos_tau) if pos_tau < 0.95 else 10.0

    x = -np.log(np.maximum(1e-12, u1))
    y = -np.log(np.maximum(1e-12, u2))

    def neg_log_lik(theta_arr: np.ndarray) -> float:
        th = float(theta_arr[0])
        if th < 1.0 or th > 50.0:
            return 1e10
        # A = x^theta + y^theta
        A = np.power(x, th) + np.power(y, th)
        A = np.maximum(1e-12, A)
        A_inv_th = np.power(A, 1.0 / th)

        # log c(u1, u2) = -A^{1/th} - ln(u1*u2) + (th - 1)*(ln x + ln y) - (2 - 1/th)*ln A + ln(A^{1/th} + th - 1)
        term1 = -A_inv_th
        term2 = -(np.log(u1) + np.log(u2))
        term3 = (th - 1.0) * (np.log(x) + np.log(y))
        term4 = -(2.0 - 1.0 / th) * np.log(A)
        bracket = np.maximum(1e-12, A_inv_th + th - 1.0)
        term5 = np.log(bracket)

        ll = np.sum(term1 + term2 + term3 + term4 + term5)
        return -float(ll) if np.isfinite(ll) else 1e10

    res = optimize.minimize(
        neg_log_lik,
        x0=[theta_init],
        bounds=[(1.0, 40.0)],
        method="L-BFGS-B",
    )

    theta = float(res.x[0]) if res.success and res.x[0] >= 1.0 else theta_init
    theta = max(1.0, min(40.0, theta))
    log_lik = -float(neg_log_lik(np.array([theta])))

    lambda_l = 0.0
    lambda_u = 2.0 - math.pow(2.0, 1.0 / theta)

    aic = 2.0 * 1 - 2.0 * log_lik
    bic = 1.0 * math.log(T) - 2.0 * log_lik

    return {
        "copula_type": "gumbel",
        "theta": theta,
        "kendall_tau": tau_val,
        "log_likelihood": log_lik,
        "lower_tail_dependence": lambda_l,
        "upper_tail_dependence": lambda_u,
        "aic": aic,
        "bic": bic,
        "converged": bool(res.success),
    }


def fit_student_t_copula(u1: np.ndarray, u2: np.ndarray) -> dict[str, Any]:
    """
    Fits bivariate Student-t copula.

    Formulas:
        lambda_L = lambda_U = 2 * t_{nu+1}( - sqrt( (nu+1)(1-rho) / (1+rho) ) )
    """
    T = len(u1)
    tau, _ = stats.kendalltau(u1, u2)
    tau_val = float(tau) if np.isfinite(tau) else 0.0

    # Initial correlation from Kendall's tau inversion for elliptical copulas: rho = sin(pi/2 * tau)
    rho_init = math.sin(0.5 * math.pi * max(-0.95, min(0.95, tau_val)))
    nu_init = 4.0

    def neg_log_lik(params: np.ndarray) -> float:
        rho = float(params[0])
        nu = float(params[1])
        if abs(rho) >= 0.999 or nu < 2.1 or nu > 40.0:
            return 1e10

        z1 = stats.t.ppf(u1, df=nu)
        z2 = stats.t.ppf(u2, df=nu)
        if not (np.all(np.isfinite(z1)) and np.all(np.isfinite(z2))):
            return 1e10

        # Bivariate t-copula log-density
        log_gamma_factor = (
            math.lgamma(0.5 * (nu + 2.0))
            + math.lgamma(0.5 * nu)
            - 2.0 * math.lgamma(0.5 * (nu + 1.0))
        )
        det_term = -0.5 * math.log(1.0 - rho * rho)

        # Q(z1, z2) = (z1^2 + z2^2 - 2*rho*z1*z2) / (nu * (1 - rho^2))
        q = (z1 * z1 + z2 * z2 - 2.0 * rho * z1 * z2) / (nu * (1.0 - rho * rho))
        joint_term = -0.5 * (nu + 2.0) * np.log(np.maximum(1e-12, 1.0 + q))
        marg_term = 0.5 * (nu + 1.0) * (
            np.log(np.maximum(1e-12, 1.0 + (z1 * z1) / nu))
            + np.log(np.maximum(1e-12, 1.0 + (z2 * z2) / nu))
        )

        ll = np.sum(log_gamma_factor + det_term + joint_term + marg_term)
        return -float(ll) if np.isfinite(ll) else 1e10

    res = optimize.minimize(
        neg_log_lik,
        x0=[rho_init, nu_init],
        bounds=[(-0.99, 0.99), (2.1, 35.0)],
        method="L-BFGS-B",
    )

    if res.success:
        rho = float(res.x[0])
        nu = float(res.x[1])
    else:
        rho = rho_init
        nu = nu_init

    log_lik = -float(neg_log_lik(np.array([rho, nu])))

    # Theoretical tail dependence: lambda_L = lambda_U = 2 * t_{nu+1}(-sqrt((nu+1)(1-rho)/(1+rho)))
    if rho >= 0.9999:
        lambda_val = 1.0
    elif rho <= -0.9999:
        lambda_val = 0.0
    else:
        arg = -math.sqrt((nu + 1.0) * (1.0 - rho) / (1.0 + rho))
        lambda_val = 2.0 * float(stats.t.cdf(arg, df=nu + 1.0))

    aic = 2.0 * 2 - 2.0 * log_lik
    bic = 2.0 * math.log(T) - 2.0 * log_lik

    return {
        "copula_type": "student_t",
        "theta": rho,
        "df": nu,
        "kendall_tau": tau_val,
        "log_likelihood": log_lik,
        "lower_tail_dependence": lambda_val,
        "upper_tail_dependence": lambda_val,
        "aic": aic,
        "bic": bic,
        "converged": bool(res.success),
    }


def fit_gaussian_copula(u1: np.ndarray, u2: np.ndarray) -> dict[str, Any]:
    """
    Fits bivariate Gaussian copula baseline.

    Formulas:
        lambda_L = lambda_U = 0 for rho < 1
    """
    T = len(u1)
    tau, _ = stats.kendalltau(u1, u2)
    tau_val = float(tau) if np.isfinite(tau) else 0.0

    z1 = stats.norm.ppf(u1)
    z2 = stats.norm.ppf(u2)

    # Linear correlation on Gaussian scores
    rho = float(np.corrcoef(z1, z2)[0, 1]) if np.std(z1) > 1e-12 and np.std(z2) > 1e-12 else 0.0
    rho = max(-0.999, min(0.999, rho))

    # Log-likelihood
    one_minus_rho2 = max(1e-12, 1.0 - rho * rho)
    det_term = -0.5 * T * math.log(one_minus_rho2)
    exp_term = -0.5 / one_minus_rho2 * np.sum(rho * rho * (z1 * z1 + z2 * z2) - 2.0 * rho * z1 * z2)
    log_lik = det_term + exp_term

    aic = 2.0 * 1 - 2.0 * log_lik
    bic = 1.0 * math.log(T) - 2.0 * log_lik

    return {
        "copula_type": "gaussian",
        "theta": rho,
        "kendall_tau": tau_val,
        "log_likelihood": log_lik,
        "lower_tail_dependence": 0.0,
        "upper_tail_dependence": 0.0,
        "aic": aic,
        "bic": bic,
        "converged": True,
    }


def fit_pairwise_copulas(
    U: np.ndarray,
    tickers: list[str],
    copula_type: Literal["clayton", "gumbel", "student_t", "gaussian", "best_fit"] = "best_fit",
) -> dict[str, Any]:
    """
    Fits bivariate copulas for all pairs (i, j) in the universe.
    Constructs tail dependence matrix lambda_L and Kendall's tau matrix.
    """
    T, N = U.shape
    tail_dep_matrix = np.zeros((N, N), dtype=np.float64)
    kendall_tau_matrix = np.zeros((N, N), dtype=np.float64)
    pearson_corr_matrix = np.zeros((N, N), dtype=np.float64)

    pairwise_results: list[dict[str, Any]] = []

    for i in range(N):
        tail_dep_matrix[i, i] = 1.0
        kendall_tau_matrix[i, i] = 1.0
        pearson_corr_matrix[i, i] = 1.0

        for j in range(i + 1, N):
            u1 = U[:, i]
            u2 = U[:, j]

            p_corr = float(np.corrcoef(u1, u2)[0, 1])

            if copula_type == "clayton":
                res = fit_clayton_copula(u1, u2)
            elif copula_type == "gumbel":
                res = fit_gumbel_copula(u1, u2)
            elif copula_type == "student_t":
                res = fit_student_t_copula(u1, u2)
            elif copula_type == "gaussian":
                res = fit_gaussian_copula(u1, u2)
            else:
                # Best fit across all 4 families via minimum AIC
                c_clayton = fit_clayton_copula(u1, u2)
                c_gumbel = fit_gumbel_copula(u1, u2)
                c_t = fit_student_t_copula(u1, u2)
                c_gauss = fit_gaussian_copula(u1, u2)

                candidates = [c_clayton, c_gumbel, c_t, c_gauss]
                res = min(candidates, key=lambda c: c["aic"])

            lambda_l = float(res["lower_tail_dependence"])
            tau = float(res["kendall_tau"])

            tail_dep_matrix[i, j] = lambda_l
            tail_dep_matrix[j, i] = lambda_l
            kendall_tau_matrix[i, j] = tau
            kendall_tau_matrix[j, i] = tau
            pearson_corr_matrix[i, j] = p_corr
            pearson_corr_matrix[j, i] = p_corr

            pairwise_results.append({
                "asset_1": tickers[i],
                "asset_2": tickers[j],
                "copula_type": res["copula_type"],
                "theta": round(float(res["theta"]), 4),
                "df": round(float(res.get("df", 0.0)), 2) if "df" in res else None,
                "kendall_tau": round(tau, 4),
                "pearson_corr": round(p_corr, 4),
                "lower_tail_dependence": round(lambda_l, 4),
                "upper_tail_dependence": round(float(res["upper_tail_dependence"]), 4),
                "aic": round(float(res["aic"]), 2),
                "bic": round(float(res["bic"]), 2),
            })

    return {
        "tickers": tickers,
        "tail_dependence_matrix": tail_dep_matrix.round(4).tolist(),
        "kendall_tau_matrix": kendall_tau_matrix.round(4).tolist(),
        "pearson_corr_matrix": pearson_corr_matrix.round(4).tolist(),
        "pairwise_results": pairwise_results,
    }


# ============================================================================
# Multivariate Dependent Return Simulation
# ============================================================================

def simulate_copula_returns(
    returns: np.ndarray,
    tickers: list[str],
    copula_type: Literal["clayton", "gumbel", "student_t", "gaussian"] = "clayton",
    num_simulations: int = 5000,
    random_seed: int = 42,
    marginal_method: Literal["empirical", "student_t"] = "empirical",
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Simulates M multivariate return scenarios preserving the dependence structure
    of the fitted copula and mapped to empirical or parametric margins.

    Returns:
        simulated_returns: (M, N) float64 array of simulated asset returns.
        diagnostics: dictionary of model parameters and simulation metadata.
    """
    T, N = returns.shape
    U, marg_info = compute_pseudo_observations(returns, method=marginal_method)
    rng = np.random.default_rng(random_seed)

    U_sim = np.zeros((num_simulations, N), dtype=np.float64)

    if copula_type == "gaussian":
        # Correlation matrix of Gaussian scores
        Z = stats.norm.ppf(U)
        R = np.corrcoef(Z, rowvar=False)
        # Eigenvalue clipping for strict positive definiteness
        eigvals, eigvecs = np.linalg.eigh(R)
        eigvals = np.maximum(1e-6, eigvals)
        R_pd = eigvecs @ np.diag(eigvals) @ eigvecs.T
        d_inv = 1.0 / np.sqrt(np.diag(R_pd))
        R_norm = np.outer(d_inv, d_inv) * R_pd

        L = np.linalg.cholesky(R_norm)
        z_raw = rng.standard_normal((num_simulations, N))
        z_corr = z_raw @ L.T
        U_sim = stats.norm.cdf(z_corr)

    elif copula_type == "student_t":
        # Estimate average degrees of freedom across pairs or default to 4.5
        all_dfs = []
        for i in range(N):
            for j in range(i + 1, N):
                res_t = fit_student_t_copula(U[:, i], U[:, j])
                all_dfs.append(res_t.get("df", 4.5))
        avg_df = float(np.median(all_dfs)) if all_dfs else 4.5
        avg_df = max(2.5, min(30.0, avg_df))

        Z_t = stats.t.ppf(U, df=avg_df)
        R_t = np.corrcoef(Z_t, rowvar=False)
        eigvals, eigvecs = np.linalg.eigh(R_t)
        eigvals = np.maximum(1e-6, eigvals)
        R_pd = eigvecs @ np.diag(eigvals) @ eigvecs.T
        d_inv = 1.0 / np.sqrt(np.diag(R_pd))
        R_norm = np.outer(d_inv, d_inv) * R_pd

        L = np.linalg.cholesky(R_norm)
        z_raw = rng.standard_normal((num_simulations, N))
        z_corr = z_raw @ L.T
        # Scale by chi-square for multivariate Student-t
        chi2 = rng.chisquare(df=avg_df, size=num_simulations)
        scaling = np.sqrt(chi2 / avg_df)[:, np.newaxis]
        t_corr = z_corr / scaling
        U_sim = stats.t.cdf(t_corr, df=avg_df)

    elif copula_type == "clayton":
        # Average pairwise theta or median across all pairs
        thetas = []
        for i in range(N):
            for j in range(i + 1, N):
                res_c = fit_clayton_copula(U[:, i], U[:, j])
                thetas.append(res_c["theta"])
        avg_theta = float(np.median(thetas)) if thetas else 1.5
        avg_theta = max(0.05, min(30.0, avg_theta))

        # Marshall-Olkin Archimedean generator for Clayton copula:
        # 1. V ~ Gamma(1/theta, 1)
        # 2. E_i ~ Exponential(1)
        # 3. U_i = (1 + E_i / V)^{-1/theta}
        v = rng.gamma(shape=1.0 / avg_theta, scale=1.0, size=(num_simulations, 1))
        e = rng.exponential(scale=1.0, size=(num_simulations, N))
        U_sim = np.power(1.0 + e / v, -1.0 / avg_theta)

    elif copula_type == "gumbel":
        # Remediated in Session 28 (DEF-28-01): Exact Chambers-Mallows-Stuck (1976)
        # positive-stable frailty generator V ~ S(1/theta, 1, (cos(pi/(2*theta)))^(1/theta), 0)
        thetas = []
        for i in range(N):
            for j in range(i + 1, N):
                res_g = fit_gumbel_copula(U[:, i], U[:, j])
                thetas.append(res_g["theta"])
        avg_theta = float(np.median(thetas)) if thetas else 1.5
        avg_theta = max(1.0, min(30.0, avg_theta))

        alpha = 1.0 / avg_theta
        if alpha >= 0.9999:
            # Independent uniforms
            U_sim = rng.uniform(1e-6, 1.0 - 1e-6, size=(num_simulations, N))
        else:
            # CMS positive stable variable V of shape (num_simulations, 1)
            u_unif = rng.uniform(-0.5 * math.pi, 0.5 * math.pi, size=(num_simulations, 1))
            w_exp = rng.exponential(scale=1.0, size=(num_simulations, 1))
            w_exp = np.maximum(1e-12, w_exp)

            u_shifted = u_unif + 0.5 * math.pi
            alpha_u = alpha * u_shifted
            ratio1 = np.sin(alpha_u) / np.maximum(1e-12, np.power(np.cos(u_unif), 1.0 / alpha))
            ratio2 = np.maximum(1e-12, np.cos(u_unif - alpha_u)) / w_exp
            v = ratio1 * np.power(ratio2, (1.0 - alpha) / alpha)
            v = np.maximum(1e-12, v)

            # E_i ~ Exponential(1) for each asset
            e = rng.exponential(scale=1.0, size=(num_simulations, N))
            # U_i = exp( - (E_i / V)^(1/avg_theta) )
            arg = np.power(e / v, 1.0 / avg_theta)
            U_sim = np.exp(-arg)

    # Strictly clip U_sim to (1e-6, 1 - 1e-6)
    U_sim = np.clip(U_sim, 1e-6, 1.0 - 1e-6)

    # Invert to Return Space via marginal quantiles
    simulated_returns = np.zeros((num_simulations, N), dtype=np.float64)
    if marginal_method == "empirical":
        for j in range(N):
            simulated_returns[:, j] = np.quantile(returns[:, j], U_sim[:, j], method="linear")
    else:
        for j in range(N):
            m_info = marg_info["marginals"][j]
            if m_info["method"] == "student_t":
                simulated_returns[:, j] = stats.t.ppf(
                    U_sim[:, j], df=m_info["df"], loc=m_info["loc"], scale=m_info["scale"]
                )
            else:
                simulated_returns[:, j] = np.quantile(returns[:, j], U_sim[:, j], method="linear")

    diagnostics = {
        "copula_type": copula_type,
        "num_simulations": num_simulations,
        "random_seed": random_seed,
        "marginal_method": marginal_method,
        "tickers": tickers,
    }

    return simulated_returns, diagnostics


# ============================================================================
# Portfolio Tail Risk & Tail Risk Parity (TRP) Allocation
# ============================================================================

def compute_portfolio_tail_risk(
    weights: np.ndarray,
    simulated_returns: np.ndarray,
    confidence_level: float = 0.99,
) -> dict[str, Any]:
    """
    Computes portfolio Value at Risk (VaR), Conditional Value at Risk (CVaR),
    and exact Euler Tail Risk Contributions (TRC_i = -w_i * E[R_i | L >= VaR]).

    Identity:
        sum_i TRC_i == CVaR
    """
    # Normalize weights
    total_w = float(np.sum(weights))
    w = weights / total_w if total_w > 1e-12 else np.full_like(weights, 1.0 / len(weights))

    # Portfolio returns & loss
    port_rets = simulated_returns @ w  # (M,)
    losses = -port_rets                # (M,) Loss L = -R_p

    # VaR_alpha = quantile_alpha(Loss)
    var_alpha = float(np.quantile(losses, confidence_level, method="linear"))

    # Tail indicator: L >= VaR_alpha
    tail_mask = losses >= var_alpha
    num_tail = int(np.sum(tail_mask))

    if num_tail == 0:
        # Fallback if no observations strictly exceed quantile
        cvar_alpha = var_alpha
        trcs = w * var_alpha
    else:
        cvar_alpha = float(np.mean(losses[tail_mask]))
        # Euler risk contribution: TRC_i = w_i * E[Loss_i | L >= VaR] = -w_i * E[R_i | L >= VaR]
        tail_asset_losses = -simulated_returns[tail_mask, :]  # (num_tail, N)
        mean_tail_losses = np.mean(tail_asset_losses, axis=0) # (N,)
        trcs = w * mean_tail_losses                           # (N,)

    # Euler reconciliation check
    tot_trc = float(np.sum(trcs))
    reconciliation_error = abs(tot_trc - cvar_alpha)

    return {
        "portfolio_var": var_alpha,
        "portfolio_cvar": cvar_alpha,
        "tail_risk_contributions": trcs,
        "euler_sum": tot_trc,
        "reconciliation_error": reconciliation_error,
        "portfolio_losses": losses,
    }


def optimize_tail_risk_parity(
    simulated_returns: np.ndarray,
    tickers: list[str],
    confidence_level: float = 0.99,
    max_iter: int = 500,
) -> dict[str, Any]:
    """
    Solves for Tail Risk Parity (TRP) portfolio weights:
        min_w sum_{i=1}^N ( TRC_i(w) / sum_k TRC_k(w) - 1/N )^2
        s.t. sum w_i = 1, w_i >= 0

    Compares against:
    1. Equal-Weight Portfolio (1/N).
    2. Inverse-Volatility Portfolio (w_i proportional to 1 / sigma_i).
    """
    N = len(tickers)
    M = simulated_returns.shape[0]

    # Compute baseline metrics for Equal-Weight (1/N)
    w_ew = np.full(N, 1.0 / N, dtype=np.float64)
    ew_risk = compute_portfolio_tail_risk(w_ew, simulated_returns, confidence_level)

    # Compute baseline metrics for Inverse-Volatility
    vol_assets = np.std(simulated_returns, axis=0)
    inv_vol = np.where(vol_assets > 1e-8, 1.0 / vol_assets, 1.0)
    w_iv = inv_vol / np.sum(inv_vol)
    iv_risk = compute_portfolio_tail_risk(w_iv, simulated_returns, confidence_level)

    # Objective function: squared dispersion of relative tail risk contributions
    def trp_objective(w_arr: np.ndarray) -> float:
        w_norm = np.maximum(0.0, w_arr)
        s = np.sum(w_norm)
        if s > 1e-12:
            w_norm = w_norm / s
        else:
            w_norm = np.full(N, 1.0 / N)

        # Vectorized portfolio loss calculation for speed
        p_loss = -(simulated_returns @ w_norm)
        v = np.quantile(p_loss, confidence_level)
        t_mask = p_loss >= v
        if np.sum(t_mask) == 0:
            return 0.0

        mean_asset_losses = np.mean(-simulated_returns[t_mask, :], axis=0)
        trc = w_norm * mean_asset_losses
        sum_trc = np.sum(trc)
        if abs(sum_trc) < 1e-12:
            return 0.0

        rel_trc = trc / sum_trc
        target = 1.0 / N
        return float(np.sum((rel_trc - target) ** 2))

    # Constraints: sum(w) = 1.0
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = [(0.0, 1.0) for _ in range(N)]

    # Multi-start optimization (EW and IV starts)
    best_res = None
    min_obj = 1e12

    for start_w in [w_ew, w_iv]:
        res = optimize.minimize(
            trp_objective,
            x0=start_w,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": max_iter, "ftol": 1e-8},
        )
        if res.success and res.fun < min_obj:
            min_obj = res.fun
            best_res = res

    if best_res is not None and best_res.success:
        w_trp = np.maximum(0.0, best_res.x)
        w_trp = w_trp / np.sum(w_trp)
        opt_converged = True
    else:
        # Fallback to inverse volatility if solver failed
        w_trp = w_iv
        opt_converged = False

    trp_risk = compute_portfolio_tail_risk(w_trp, simulated_returns, confidence_level)

    # Sample loss distribution for visualization (first 500 samples)
    sample_losses = [round(float(l), 6) for l in trp_risk["portfolio_losses"][:500]]

    return {
        "converged": opt_converged,
        "confidence_level": confidence_level,
        "weights": {tickers[i]: round(float(w_trp[i]), 4) for i in range(N)},
        "tail_risk_contributions": {
            tickers[i]: round(float(trp_risk["tail_risk_contributions"][i]), 6) for i in range(N)
        },
        "portfolio_var": round(float(trp_risk["portfolio_var"]), 6),
        "portfolio_cvar": round(float(trp_risk["portfolio_cvar"]), 6),
        "euler_reconciliation_error": round(float(trp_risk["reconciliation_error"]), 12),
        "simulated_loss_distribution": sample_losses,
        "baselines": {
            "equal_weight": {
                "weights": {tickers[i]: round(float(w_ew[i]), 4) for i in range(N)},
                "portfolio_var": round(float(ew_risk["portfolio_var"]), 6),
                "portfolio_cvar": round(float(ew_risk["portfolio_cvar"]), 6),
                "tail_risk_contributions": {
                    tickers[i]: round(float(ew_risk["tail_risk_contributions"][i]), 6) for i in range(N)
                },
            },
            "inverse_volatility": {
                "weights": {tickers[i]: round(float(w_iv[i]), 4) for i in range(N)},
                "portfolio_var": round(float(iv_risk["portfolio_var"]), 6),
                "portfolio_cvar": round(float(iv_risk["portfolio_cvar"]), 6),
                "tail_risk_contributions": {
                    tickers[i]: round(float(iv_risk["tail_risk_contributions"][i]), 6) for i in range(N)
                },
            },
        },
    }
