"""
Pure Numerical Financial Mathematics Core for Dynamic Factor Walk-Forward Backtesting.

Implements:
1. Rolling lookback window factor synthesis (CAPM, FF3, Carhart4, PCA) with zero look-ahead bias.
2. Cross-sectional OLS factor loading estimation and structural Barra-style covariance matrix reconstruction.
3. Multi-factor alpha scoring and dynamic factor-tilted portfolio rebalancing.
4. SLSQP optimization under turnover penalization and multi-factor beta constraints.
5. Frictional discrete wealth compounding tracking weight drift, 1-way turnover, and bps transaction costs.
6. Factor exposure attribution time series (systematic vs idiosyncratic risk shares).
"""

from __future__ import annotations

import math
from typing import Any, Literal
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from app.quant.factor_model import (
    compute_structural_covariance_matrix,
    construct_synthetic_factors_from_returns,
    decompose_portfolio_factor_risk,
)


def _is_rebalance_trigger(
    frequency: str,
    current_date: str,
    prev_date: str,
    days_since_rebalance: int,
) -> bool:
    """
    Evaluates whether a portfolio rebalance is triggered on the current date.
    Uses calendar boundary transitions matching institutional accounting standards.
    """
    if frequency == "daily":
        return True
    if frequency == "weekly":
        curr_dt = pd.to_datetime(current_date)
        prev_dt = pd.to_datetime(prev_date)
        return curr_dt.isocalendar().week != prev_dt.isocalendar().week
    if frequency == "biweekly":
        return days_since_rebalance >= 10
    if frequency == "monthly":
        return current_date[:7] != prev_date[:7]
    if frequency == "quarterly":
        curr_m = int(current_date[5:7])
        prev_m = int(prev_date[5:7])
        return ((curr_m - 1) // 3) != ((prev_m - 1) // 3)
    return False


def estimate_window_factor_loadings(
    window_returns: np.ndarray,
    factors_matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Estimates multivariate OLS factor loadings, alphas, and idiosyncratic variances
    simultaneously across all assets using stable linear least squares:
        Y = X * Theta + E
        where X = [1, F_1, ..., F_K] in R^(W x (K+1))
              Y in R^(W x N)

    Args:
        window_returns: Matrix of asset returns of shape (W, N)
        factors_matrix: Matrix of factor returns of shape (W, K)

    Returns:
        tuple of:
        - B: Factor loadings matrix of shape (N, K)
        - alphas: Asset alphas array of shape (N,)
        - specific_variances: Specific variance array of shape (N,)
    """
    W, N = window_returns.shape
    K = factors_matrix.shape[1] if factors_matrix.ndim > 1 else 1
    F = factors_matrix if factors_matrix.ndim > 1 else factors_matrix.reshape(-1, 1)

    X = np.column_stack([np.ones(W, dtype=np.float64), F])
    theta, _, _, _ = np.linalg.lstsq(X, window_returns, rcond=None)

    alphas = theta[0, :]
    B = theta[1:, :].T  # Shape: (N, K)

    residuals = window_returns - (X @ theta)
    df = max(1, W - K - 1)
    specific_variances = np.sum(residuals**2, axis=0) / df
    # Safeguard against negative or near-zero variance
    specific_variances = np.maximum(specific_variances, 1e-10)

    return B, alphas, specific_variances


def solve_factor_tilted_weights(
    B: np.ndarray,
    Sigma_model: np.ndarray,
    factor_names: list[str],
    factor_tilts: dict[str, float] | None,
    factor_constraints: dict[str, dict[str, float]] | None,
    prev_weights: np.ndarray,
    strategy_type: str = "factor_tilt",
    top_n_assets: int = 5,
    risk_aversion: float = 2.5,
    turnover_penalty: float = 0.0,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
    risk_free_rate: float = 0.02,
    annualization_factor: int = 252,
) -> tuple[np.ndarray, bool, str]:
    """
    Computes optimal portfolio weights for a dynamic factor rebalance event.

    Args:
        B: Matrix of factor loadings of shape (N, K)
        Sigma_model: Daily structural covariance matrix of shape (N, N)
        factor_names: List of K factor names
        factor_tilts: Target factor tilt intensities (e.g. {"MOM": 0.5, "HML": 0.2})
        factor_constraints: Bounds on portfolio factor exposures (min_beta, max_beta)
        prev_weights: Pre-rebalance drifted portfolio weights of shape (N,)
        strategy_type: "factor_tilt", "factor_min_variance", or "factor_momentum_rotation"
        top_n_assets: Number of top assets for momentum rotation
        risk_aversion: Risk aversion coefficient gamma
        turnover_penalty: Penalty lambda for portfolio turnover
        min_weight: Minimum weight per asset
        max_weight: Maximum weight per asset
        risk_free_rate: Annualized risk-free rate
        annualization_factor: Number of trading periods per year (252)

    Returns:
        tuple of (optimal_weights of shape (N,), is_feasible: bool, message: str)
    """
    N, K = B.shape
    equal_weights = np.full(N, 1.0 / N, dtype=np.float64)

    # Strategy 3: Dynamic Factor Momentum Rotation (Cross-Sectional Top-N)
    if strategy_type == "factor_momentum_rotation":
        tilts = factor_tilts or {"MKT": 1.0}
        tilt_vec = np.array([tilts.get(name, 0.0) for name in factor_names], dtype=np.float64)
        if np.all(tilt_vec == 0.0):
            tilt_vec[0] = 1.0

        # Cross-sectional standardization of factor loadings
        B_std = np.zeros_like(B)
        for j in range(K):
            std_j = np.std(B[:, j])
            B_std[:, j] = (B[:, j] - np.mean(B[:, j])) / (std_j if std_j > 1e-8 else 1.0)

        composite_scores = B_std @ tilt_vec
        q = max(1, min(top_n_assets, N))
        top_indices = np.argsort(composite_scores)[-q:]

        w = np.zeros(N, dtype=np.float64)
        w[top_indices] = 1.0 / q
        # Clip to max_weight and min_weight if feasible
        w = np.clip(w, min_weight, max_weight)
        w_sum = np.sum(w)
        if w_sum > 0:
            w /= w_sum
        else:
            w = equal_weights
        return w, True, "Factor rotation allocation applied."

    # Strategy 1 & 2: Optimization via SLSQP
    Sigma_ann = Sigma_model * annualization_factor

    # Formulate Expected Returns
    if strategy_type == "factor_tilt":
        tilts = factor_tilts or {"MKT": 1.0}
        tilt_vec = np.array([tilts.get(name, 0.0) for name in factor_names], dtype=np.float64)
        if np.all(tilt_vec == 0.0):
            tilt_vec[0] = 1.0

        B_std = np.zeros_like(B)
        for j in range(K):
            std_j = np.std(B[:, j])
            B_std[:, j] = (B[:, j] - np.mean(B[:, j])) / (std_j if std_j > 1e-8 else 1.0)

        alpha_scores = B_std @ tilt_vec
        # Annualized expected return proxy: r_f + 0.10 * alpha_score
        mu_ann = risk_free_rate + 0.10 * alpha_scores
    else:
        # Minimum variance
        mu_ann = np.zeros(N, dtype=np.float64)

    # Bounds
    bounds = [(min_weight, max_weight) for _ in range(N)]

    # Budget constraint: sum(w) = 1.0
    constraints: list[dict[str, Any]] = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0, "jac": lambda w: np.ones(N)}
    ]

    # Factor exposure bounds: min_beta <= B_j^T * w <= max_beta
    if factor_constraints:
        for j, factor_name in enumerate(factor_names):
            if factor_name in factor_constraints:
                fc = factor_constraints[factor_name]
                min_b = fc.get("min_beta")
                max_b = fc.get("max_beta")
                bj = B[:, j].copy()
                if min_b is not None:
                    constraints.append({
                        "type": "ineq",
                        "fun": (lambda w, b=bj, limit=min_b: float(np.dot(b, w) - limit)),
                        "jac": (lambda w, b=bj: b),
                    })
                if max_b is not None:
                    constraints.append({
                        "type": "ineq",
                        "fun": (lambda w, b=bj, limit=max_b: float(limit - np.dot(b, w))),
                        "jac": (lambda w, b=bj: -b),
                    })

    # Objective function
    # Smooth turnover approximation: sqrt((w - w_prev)^2 + 1e-8) for differentiability
    def objective_fn(w: np.ndarray) -> float:
        variance_term = float(w @ Sigma_ann @ w)
        if strategy_type == "factor_tilt":
            utility = float(w @ mu_ann - 0.5 * risk_aversion * variance_term)
            if turnover_penalty > 0.0 and prev_weights is not None:
                turnover = float(np.sum(np.sqrt((w - prev_weights)**2 + 1e-8)))
                utility -= turnover_penalty * turnover
            return -utility
        else:
            # Min variance
            return 0.5 * variance_term

    def objective_grad(w: np.ndarray) -> np.ndarray:
        grad = Sigma_ann @ w
        if strategy_type == "factor_tilt":
            grad = -mu_ann + risk_aversion * (Sigma_ann @ w)
            if turnover_penalty > 0.0 and prev_weights is not None:
                smooth_diff = (w - prev_weights) / np.sqrt((w - prev_weights)**2 + 1e-8)
                grad += turnover_penalty * smooth_diff
            return grad
        return grad

    # Initial guess
    w0 = prev_weights.copy() if prev_weights is not None and len(prev_weights) == N else equal_weights.copy()
    w0 = np.clip(w0, min_weight, max_weight)
    w0_sum = np.sum(w0)
    if w0_sum > 0:
        w0 /= w0_sum
    else:
        w0 = equal_weights.copy()

    res = minimize(
        objective_fn,
        w0,
        jac=objective_grad,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 200, "ftol": 1e-7},
    )

    if res.success and not np.isnan(res.x).any():
        sol = np.clip(res.x, min_weight, max_weight)
        sol /= np.sum(sol)
        return sol, True, "Optimization converged."

    # Fallback: Relax factor constraints if infeasible
    if factor_constraints:
        base_constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0, "jac": lambda w: np.ones(N)}]
        res_relaxed = minimize(
            objective_fn,
            w0,
            jac=objective_grad,
            method="SLSQP",
            bounds=bounds,
            constraints=base_constraints,
            options={"maxiter": 200, "ftol": 1e-7},
        )
        if res_relaxed.success and not np.isnan(res_relaxed.x).any():
            sol = np.clip(res_relaxed.x, min_weight, max_weight)
            sol /= np.sum(sol)
            return sol, False, "Converged with relaxed factor constraints (infeasible limits)."

    # Final safe fallback: equal weights
    return equal_weights, False, f"Solver failed: {res.message}. Fell back to equal-weight."


def run_dynamic_factor_backtest(
    returns_df: pd.DataFrame,
    factor_model: Literal["capm", "ff3", "carhart4", "pca"] = "carhart4",
    num_pca_factors: int = 3,
    strategy_type: Literal["factor_tilt", "factor_min_variance", "factor_momentum_rotation"] = "factor_tilt",
    estimation_window: int = 60,
    rebalance_frequency: Literal["daily", "weekly", "biweekly", "monthly", "quarterly"] = "monthly",
    factor_tilts: dict[str, float] | None = None,
    factor_constraints: dict[str, dict[str, float]] | None = None,
    top_n_assets: int = 5,
    risk_aversion: float = 2.5,
    turnover_penalty: float = 0.0,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
    transaction_cost_bps: float = 10.0,
    slippage_bps: float = 5.0,
    initial_capital: float = 100000.0,
    risk_free_rate: float = 0.02,
    annualization_factor: int = 252,
) -> dict[str, Any]:
    """
    Executes a walk-forward dynamic factor backtest simulation with zero look-ahead bias.

    Args:
        returns_df: DataFrame of asset returns (rows: dates, cols: tickers)
        factor_model: "capm", "ff3", "carhart4", or "pca"
        num_pca_factors: Number of principal components if factor_model is "pca"
        strategy_type: "factor_tilt", "factor_min_variance", or "factor_momentum_rotation"
        estimation_window: Lookback window W (must be >= 30)
        rebalance_frequency: "daily", "weekly", "biweekly", "monthly", or "quarterly"
        factor_tilts: Multi-factor target tilt scores
        factor_constraints: Factor exposure constraints
        top_n_assets: Number of top assets for momentum rotation
        risk_aversion: Risk aversion parameter gamma
        turnover_penalty: Turnover penalization parameter lambda
        min_weight: Lower bound on asset weight
        max_weight: Upper bound on asset weight
        transaction_cost_bps: Commission in basis points
        slippage_bps: Slippage friction in basis points
        initial_capital: Starting equity in currency units
        risk_free_rate: Annualized risk-free rate
        annualization_factor: Trading periods per year (252)

    Returns:
        Structured dictionary matching DynamicFactorBacktestResponse.
    """
    T, N = returns_df.shape
    asset_names = list(returns_df.columns)
    dates = [str(d)[:10] for d in returns_df.index]

    if estimation_window < 30:
        raise ValueError(f"Estimation window ({estimation_window}) must be at least 30 trading days.")
    if T <= estimation_window + 5:
        raise ValueError(
            f"Insufficient data: {T} total observations is too short for estimation window {estimation_window}."
        )

    R_matrix = returns_df.to_numpy(dtype=np.float64)
    total_friction_rate = (transaction_cost_bps + slippage_bps) / 10000.0

    # Benchmark: Equal-weighted portfolio
    benchmark_weights = np.full(N, 1.0 / N, dtype=np.float64)

    # Simulation State Tracking
    strategy_equity = initial_capital
    benchmark_equity = initial_capital
    peak_strategy_equity = initial_capital

    current_weights = benchmark_weights.copy()
    drifted_weights = benchmark_weights.copy()

    equity_curve: list[dict[str, Any]] = []
    rebalance_history: list[dict[str, Any]] = []
    exposure_dates: list[str] = []
    exposure_series: dict[str, list[float]] = {}

    daily_strategy_returns: list[float] = []
    daily_benchmark_returns: list[float] = []

    total_turnover = 0.0
    total_costs = 0.0
    total_rebalances = 0
    days_since_rebalance = 0

    first_rebalance = True

    # Main Simulation Loop (Strictly starting at index estimation_window)
    for t in range(estimation_window, T):
        curr_date = dates[t]
        prev_date = dates[t - 1]

        # Check if rebalance is triggered today
        is_rebal = first_rebalance or _is_rebalance_trigger(
            rebalance_frequency, curr_date, prev_date, days_since_rebalance
        )

        cost_incurred_today = 0.0
        turnover_today = 0.0

        if is_rebal:
            # STRICT ZERO LOOK-AHEAD:
            # Trailing window uses strictly rows [t - estimation_window : t] (i.e. ending at t - 1)
            window_slice = R_matrix[t - estimation_window : t, :]

            # 1. Synthesize factors over window
            F_win, factor_names = construct_synthetic_factors_from_returns(
                returns_df=window_slice,
                factor_model=factor_model,
                num_pca_factors=num_pca_factors,
                risk_free_rate=risk_free_rate,
                annualization_factor=annualization_factor,
            )

            # Initialize exposure series tracking keys if not yet present
            if not exposure_series:
                for fname in factor_names:
                    exposure_series[fname] = []

            # 2. Estimate factor loadings B, alphas, and specific variances
            B_win, alphas_win, s_eps_win = estimate_window_factor_loadings(window_slice, F_win)

            # 3. Factor covariance Sigma_F
            Sigma_F_win = np.cov(F_win, rowvar=False)
            if Sigma_F_win.ndim == 0:
                Sigma_F_win = np.array([[float(Sigma_F_win)]])

            # 4. Construct structural Barra covariance
            Sigma_model_win = compute_structural_covariance_matrix(B_win, Sigma_F_win, s_eps_win)

            # 5. Solve for new optimal target weights
            target_w, is_feas, status_msg = solve_factor_tilted_weights(
                B=B_win,
                Sigma_model=Sigma_model_win,
                factor_names=factor_names,
                factor_tilts=factor_tilts,
                factor_constraints=factor_constraints,
                prev_weights=drifted_weights,
                strategy_type=strategy_type,
                top_n_assets=top_n_assets,
                risk_aversion=risk_aversion,
                turnover_penalty=turnover_penalty,
                min_weight=min_weight,
                max_weight=max_weight,
                risk_free_rate=risk_free_rate,
                annualization_factor=annualization_factor,
            )

            # 6. Calculate turnover and trading friction
            turnover_today = float(0.5 * np.sum(np.abs(target_w - drifted_weights)))
            traded_notional = 2.0 * turnover_today * strategy_equity
            cost_incurred_today = traded_notional * total_friction_rate

            strategy_equity = max(0.0, strategy_equity - cost_incurred_today)
            current_weights = target_w.copy()
            drifted_weights = target_w.copy()

            total_turnover += turnover_today
            total_costs += cost_incurred_today
            total_rebalances += 1
            days_since_rebalance = 0
            first_rebalance = False

            # 7. Record factor risk decomposition at rebalance
            risk_decomp = decompose_portfolio_factor_risk(
                weights=target_w,
                factor_loadings=B_win,
                factor_covariance=Sigma_F_win,
                specific_variances=s_eps_win,
                factor_names=factor_names,
            )

            p_betas = {name: float(risk_decomp["portfolio_betas"].get(name, 0.0)) for name in factor_names}
            exposure_dates.append(curr_date)
            for fname in factor_names:
                exposure_series[fname].append(p_betas.get(fname, 0.0))

            rebalance_history.append({
                "date": curr_date,
                "weights": {asset_names[i]: round(float(target_w[i]), 4) for i in range(N)},
                "portfolio_betas": {fname: round(p_betas[fname], 4) for fname in factor_names},
                "systematic_volatility": round(float(risk_decomp["systematic_volatility"]), 4),
                "idiosyncratic_volatility": round(float(risk_decomp["idiosyncratic_volatility"]), 4),
                "systematic_share_pct": round(float(risk_decomp.get("systematic_share_pct", 0.0)), 2),
                "turnover": round(turnover_today, 4),
                "cost_incurred": round(cost_incurred_today, 2),
                "is_feasible": is_feas,
                "solver_message": status_msg,
            })
        else:
            days_since_rebalance += 1

        # Realize Day t Returns
        r_today = R_matrix[t, :]
        gross_strategy_ret = float(np.dot(drifted_weights, r_today))
        benchmark_ret = float(np.dot(benchmark_weights, r_today))

        # Advance equity
        strategy_equity *= (1.0 + gross_strategy_ret)
        benchmark_equity *= (1.0 + benchmark_ret)

        daily_strategy_returns.append(gross_strategy_ret)
        daily_benchmark_returns.append(benchmark_ret)

        # Update weight drift for next period
        denom = 1.0 + gross_strategy_ret
        if denom > 1e-12:
            drifted_weights = (drifted_weights * (1.0 + r_today)) / denom
        else:
            drifted_weights = benchmark_weights.copy()

        # Update drawdown
        if strategy_equity > peak_strategy_equity:
            peak_strategy_equity = strategy_equity
        drawdown = (strategy_equity - peak_strategy_equity) / peak_strategy_equity if peak_strategy_equity > 0 else 0.0

        equity_curve.append({
            "date": curr_date,
            "strategy_equity": round(float(strategy_equity), 2),
            "benchmark_equity": round(float(benchmark_equity), 2),
            "drawdown": round(float(drawdown), 4),
        })

    # Summary Performance Analytics
    n_days = len(daily_strategy_returns)
    years = max(1.0 / annualization_factor, n_days / annualization_factor)

    strat_ret_arr = np.array(daily_strategy_returns, dtype=np.float64)
    bench_ret_arr = np.array(daily_benchmark_returns, dtype=np.float64)

    total_return = float(strategy_equity / initial_capital - 1.0)
    cagr = float((strategy_equity / initial_capital) ** (1.0 / years) - 1.0) if strategy_equity > 0 else total_return

    vol_daily = float(np.std(strat_ret_arr, ddof=1)) if len(strat_ret_arr) > 1 else 0.0
    ann_vol = vol_daily * math.sqrt(annualization_factor)

    excess_ret = strat_ret_arr - (risk_free_rate / annualization_factor)
    sharpe = float(np.mean(excess_ret) / vol_daily * math.sqrt(annualization_factor)) if vol_daily > 1e-8 else 0.0

    # Downside deviation for Sortino
    neg_rets = np.minimum(excess_ret, 0.0)
    downside_vol = float(np.std(neg_rets, ddof=1)) if len(neg_rets) > 1 else 0.0
    sortino = float(np.mean(excess_ret) / downside_vol * math.sqrt(annualization_factor)) if downside_vol > 1e-8 else 0.0

    # Max Drawdown
    drawdowns = [pt["drawdown"] for pt in equity_curve]
    max_dd = float(min(drawdowns)) if drawdowns else 0.0
    calmar = float(cagr / abs(max_dd)) if abs(max_dd) > 1e-6 else 0.0

    # Benchmark metrics
    bench_total_ret = float(benchmark_equity / initial_capital - 1.0)
    bench_cagr = float((benchmark_equity / initial_capital) ** (1.0 / years) - 1.0) if benchmark_equity > 0 else bench_total_ret
    bench_vol_daily = float(np.std(bench_ret_arr, ddof=1)) if len(bench_ret_arr) > 1 else 0.0
    bench_ann_vol = bench_vol_daily * math.sqrt(annualization_factor)
    bench_excess = bench_ret_arr - (risk_free_rate / annualization_factor)
    bench_sharpe = float(np.mean(bench_excess) / bench_vol_daily * math.sqrt(annualization_factor)) if bench_vol_daily > 1e-8 else 0.0

    # Active Metrics
    active_daily = strat_ret_arr - bench_ret_arr
    active_return = float(cagr - bench_cagr)
    tracking_error = float(np.std(active_daily, ddof=1) * math.sqrt(annualization_factor)) if len(active_daily) > 1 else 0.0
    info_ratio = float(active_return / tracking_error) if tracking_error > 1e-8 else 0.0

    avg_turnover = float(total_turnover / total_rebalances) if total_rebalances > 0 else 0.0

    summary_metrics = {
        "total_return": round(total_return, 4),
        "cagr": round(cagr, 4),
        "annualized_volatility": round(ann_vol, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "max_drawdown": round(max_dd, 4),
        "calmar_ratio": round(calmar, 4),
        "active_return": round(active_return, 4),
        "tracking_error": round(tracking_error, 4),
        "information_ratio": round(info_ratio, 4),
        "average_turnover": round(avg_turnover, 4),
        "total_transaction_costs": round(total_costs, 2),
    }

    benchmark_metrics = {
        "total_return": round(bench_total_ret, 4),
        "cagr": round(bench_cagr, 4),
        "annualized_volatility": round(bench_ann_vol, 4),
        "sharpe_ratio": round(bench_sharpe, 4),
        "max_drawdown": round(float(min([pt["benchmark_equity"] / initial_capital - 1.0 for pt in equity_curve] or [0.0])), 4),
    }

    return {
        "strategy_type": strategy_type,
        "factor_model": factor_model,
        "estimation_window": estimation_window,
        "rebalance_frequency": rebalance_frequency,
        "total_rebalances": total_rebalances,
        "summary_metrics": summary_metrics,
        "benchmark_metrics": benchmark_metrics,
        "equity_curve": equity_curve,
        "rebalance_history": rebalance_history,
        "factor_exposure_series": {
            "dates": exposure_dates,
            "exposures": {fname: [round(v, 4) for v in vals] for fname, vals in exposure_series.items()},
        },
    }
