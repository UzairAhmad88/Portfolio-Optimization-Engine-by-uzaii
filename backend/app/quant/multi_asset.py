"""
Pure Numerical Financial Mathematics Core for Multi-Asset Class Allocation,
Cash Drag Modeling, and Multi-Currency FX Hedging.

Implements:
1. Exact multi-currency discrete simple return conversion under base reporting currency:
   (1 + R_base) = (1 + R_loc) * (1 + R_fx)
2. Currency hedging overlay with Covered Interest Parity (CIP) forward carry:
   R_hedged = R_base - h * (R_fx - Carry)
3. Structural FX currency risk decomposition (Asset Variance, FX Variance, Cross-Covariance).
4. Cash drag and risk-free yield interest accrual.
5. Hierarchical quadratic optimization under asset class group bounds and cash buffers.
6. Chronological multi-asset walk-forward backtesting with realistic rebalancing friction.
"""

from __future__ import annotations

import math
from typing import Any, Literal
import numpy as np
import pandas as pd
from scipy.optimize import minimize


def convert_local_returns_to_base(
    local_returns: np.ndarray,
    asset_currencies: list[str],
    base_currency: str,
    fx_returns: dict[str, np.ndarray],
    hedge_ratios: dict[str, float] | None = None,
    carry_rates: dict[str, float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Converts a matrix of local asset returns (T, N) to base reporting currency
    applying optional currency hedging and forward carry differentials.

    Args:
        local_returns: Array of shape (T, N) containing discrete simple asset returns.
        asset_currencies: List of length N with currency codes (e.g. ['USD', 'EUR', 'PKR']).
        base_currency: Base reporting currency (e.g. 'USD').
        fx_returns: Dict mapping currency code to simple FX return series of shape (T,).
                    Note: FX rate is defined as price of 1 unit of foreign currency in base currency.
        hedge_ratios: Dict mapping currency code to hedge ratio h in [0.0, 1.0].
        carry_rates: Dict mapping currency code to annualized forward carry rate (r_base - r_local).

    Returns:
        tuple of:
        - base_returns: Array of shape (T, N) of hedged base-currency returns.
        - unhedged_base_returns: Array of shape (T, N) of pure unhedged base-currency returns.
    """
    T, N = local_returns.shape
    base_returns = np.zeros((T, N), dtype=np.float64)
    unhedged_base_returns = np.zeros((T, N), dtype=np.float64)

    h_map = hedge_ratios or {}
    carry_map = carry_rates or {}

    for i in range(N):
        curr = asset_currencies[i]
        r_loc = local_returns[:, i]

        if curr.upper() == base_currency.upper():
            # Domestic asset, zero FX risk
            base_returns[:, i] = r_loc
            unhedged_base_returns[:, i] = r_loc
        else:
            if curr in fx_returns:
                r_fx = fx_returns[curr]
            else:
                # Default to zero FX return if currency pair not supplied
                r_fx = np.zeros(T, dtype=np.float64)

            # Exact simple return identity: (1 + R_loc) * (1 + R_fx) - 1
            r_base_unhedged = (1.0 + r_loc) * (1.0 + r_fx) - 1.0
            unhedged_base_returns[:, i] = r_base_unhedged

            # Apply hedge ratio h
            h = float(np.clip(h_map.get(curr, 0.0), 0.0, 1.0))
            daily_carry = float(carry_map.get(curr, 0.0)) / 252.0

            if h > 0.0:
                # Neutralize h share of FX fluctuations and earn/pay forward carry
                r_hedged = r_base_unhedged - h * (r_fx - daily_carry)
                base_returns[:, i] = r_hedged
            else:
                base_returns[:, i] = r_base_unhedged

    return base_returns, unhedged_base_returns


def decompose_multi_asset_fx_risk(
    weights: np.ndarray,
    local_returns: np.ndarray,
    unhedged_base_returns: np.ndarray,
    asset_currencies: list[str],
    base_currency: str,
    fx_returns: dict[str, np.ndarray],
    annualization_factor: int = 252,
) -> dict[str, float]:
    """
    Decomposes unhedged portfolio variance into asset price volatility vs FX currency volatility.
    
    Formula:
        sigma_p^2 = w^T Sigma_loc w + w^T Sigma_fx w + 2 w^T Sigma_cross w
    """
    T, N = local_returns.shape
    w = np.asarray(weights, dtype=np.float64)

    # 1. Local asset covariance
    cov_loc = np.cov(local_returns, rowvar=False) * annualization_factor
    if N == 1:
        cov_loc = np.array([[float(cov_loc)]])

    # 2. FX returns matrix for each asset
    fx_matrix = np.zeros((T, N), dtype=np.float64)
    for i in range(N):
        curr = asset_currencies[i]
        if curr.upper() != base_currency.upper() and curr in fx_returns:
            fx_matrix[:, i] = fx_returns[curr]

    cov_fx = np.cov(fx_matrix, rowvar=False) * annualization_factor
    if N == 1:
        cov_fx = np.array([[float(cov_fx)]])

    # 3. Cross-covariance between local returns and FX returns
    combined = np.column_stack([local_returns, fx_matrix])
    full_cov = np.cov(combined, rowvar=False) * annualization_factor
    cov_cross = full_cov[:N, N:]

    # Variances
    var_loc = float(w @ cov_loc @ w)
    var_fx = float(w @ cov_fx @ w)
    var_cross = float(2.0 * (w @ cov_cross @ w))
    total_var = max(1e-12, var_loc + var_fx + var_cross)

    return {
        "asset_local_variance": var_loc,
        "fx_currency_variance": var_fx,
        "cross_covariance": var_cross,
        "total_unhedged_variance": total_var,
        "asset_risk_share_pct": round(float(np.clip(var_loc / total_var * 100.0, 0.0, 100.0)), 2),
        "fx_risk_share_pct": round(float(np.clip((var_fx + var_cross) / total_var * 100.0, 0.0, 100.0)), 2),
        "unhedged_volatility": math.sqrt(total_var),
        "local_asset_volatility": math.sqrt(max(0.0, var_loc)),
    }


def solve_multi_asset_allocation(
    expected_returns: np.ndarray,
    covariance_matrix: np.ndarray,
    asset_classes: list[str],
    asset_class_limits: dict[str, dict[str, float]] | None = None,
    min_cash_weight: float = 0.05,
    max_cash_weight: float = 0.25,
    min_asset_weight: float = 0.0,
    max_asset_weight: float = 1.0,
    risk_free_rate: float = 0.03,
    objective: Literal["max_sharpe", "min_variance", "risk_parity"] = "max_sharpe",
    risk_aversion: float = 2.5,
    annualization_factor: int = 252,
) -> tuple[np.ndarray, float, bool, str]:
    """
    Solves hierarchical multi-asset optimization over risky assets and cash:
        x = [w_1, ..., w_N, w_cash] in R^(N+1)
    Subject to:
        sum(w_i) + w_cash = 1.0
        L_c <= sum_{i in class_c} w_i <= U_c
        w_cash in [min_cash, max_cash]
        w_i in [min_asset_weight, max_asset_weight]

    Returns:
        tuple of (optimal_risky_weights (N,), optimal_cash_weight: float, is_feasible: bool, message: str)
    """
    N = len(expected_returns)
    mu_risky = np.asarray(expected_returns, dtype=np.float64)
    Sigma_ann = np.asarray(covariance_matrix, dtype=np.float64)

    # Dimensionality N+1 (assets 0..N-1 are risky, index N is cash)
    dim = N + 1

    # Bounds
    bounds: list[tuple[float, float]] = []
    for _ in range(N):
        bounds.append((min_asset_weight, max_asset_weight))
    bounds.append((min_cash_weight, max_cash_weight))

    # Constraints
    # 1. Full Budget equality: sum(x) = 1.0
    constraints: list[dict[str, Any]] = [
        {
            "type": "eq",
            "fun": lambda x: np.sum(x) - 1.0,
            "jac": lambda x: np.ones(dim, dtype=np.float64),
        }
    ]

    # 2. Asset Class Group Constraints
    unique_classes = sorted(list(set(asset_classes)))
    class_indices: dict[str, list[int]] = {c: [] for c in unique_classes}
    for i, c in enumerate(asset_classes):
        class_indices[c].append(i)

    if asset_class_limits:
        for c, limits in asset_class_limits.items():
            if c in class_indices and class_indices[c]:
                idx = class_indices[c]
                min_lim = limits.get("min_weight")
                max_lim = limits.get("max_weight")

                grad_vec = np.zeros(dim, dtype=np.float64)
                grad_vec[idx] = 1.0

                if min_lim is not None:
                    constraints.append({
                        "type": "ineq",
                        "fun": (lambda x, g=grad_vec, lim=min_lim: float(np.dot(g, x) - lim)),
                        "jac": (lambda x, g=grad_vec: g),
                    })
                if max_lim is not None:
                    constraints.append({
                        "type": "ineq",
                        "fun": (lambda x, g=grad_vec, lim=max_lim: float(lim - np.dot(g, x))),
                        "jac": (lambda x, g=grad_vec: -g),
                    })

    # Expected return vector for all N+1 assets (cash earns r_f)
    mu_full = np.append(mu_risky, risk_free_rate)

    # Objectives
    if objective == "min_variance":
        def obj_fn(x: np.ndarray) -> float:
            w_r = x[:N]
            return float(0.5 * (w_r @ Sigma_ann @ w_r))

        def obj_grad(x: np.ndarray) -> np.ndarray:
            grad = np.zeros(dim, dtype=np.float64)
            grad[:N] = Sigma_ann @ x[:N]
            return grad

    elif objective == "max_sharpe":
        def obj_fn(x: np.ndarray) -> float:
            w_r = x[:N]
            w_cash = x[N]
            port_ret = float(w_r @ mu_risky + w_cash * risk_free_rate)
            port_var = float(w_r @ Sigma_ann @ w_r)
            port_vol = math.sqrt(max(port_var, 1e-10))
            # Maximize Sharpe ratio = -(port_ret - r_f) / port_vol
            excess_ret = port_ret - risk_free_rate
            return -excess_ret / port_vol if port_vol > 1e-8 else 0.0

        def obj_grad(x: np.ndarray) -> np.ndarray:
            w_r = x[:N]
            w_cash = x[N]
            port_ret = float(w_r @ mu_risky + w_cash * risk_free_rate)
            port_var = float(w_r @ Sigma_ann @ w_r)
            port_vol = math.sqrt(max(port_var, 1e-10))
            excess_ret = port_ret - risk_free_rate

            grad = np.zeros(dim, dtype=np.float64)
            if port_vol <= 1e-8:
                return grad

            # d(Sharpe)/dw_r = (mu_r * vol - excess * (Sigma w_r / vol)) / vol^2
            grad[:N] = -(mu_risky * port_vol - excess_ret * (Sigma_ann @ w_r) / port_vol) / (port_vol**2)
            # d(Sharpe)/dw_cash = -(r_f * vol - 0) / vol^2 = -r_f / vol (since cash has zero variance)
            grad[N] = -risk_free_rate / port_vol
            return grad
    else:
        # Default: Quadratic Utility: 0.5 * gamma * w^T Sigma w - w^T mu
        def obj_fn(x: np.ndarray) -> float:
            w_r = x[:N]
            w_cash = x[N]
            port_ret = float(w_r @ mu_risky + w_cash * risk_free_rate)
            port_var = float(w_r @ Sigma_ann @ w_r)
            return float(0.5 * risk_aversion * port_var - port_ret)

        def obj_grad(x: np.ndarray) -> np.ndarray:
            grad = np.zeros(dim, dtype=np.float64)
            grad[:N] = risk_aversion * (Sigma_ann @ x[:N]) - mu_risky
            grad[N] = -risk_free_rate
            return grad

    # Initial Feasible Guess
    # Give target cash to cash, split the rest evenly among risky assets
    target_cash = (min_cash_weight + max_cash_weight) / 2.0
    rem_risky = 1.0 - target_cash
    x0 = np.zeros(dim, dtype=np.float64)
    x0[:N] = rem_risky / N
    x0[N] = target_cash

    res = minimize(
        obj_fn,
        x0,
        jac=obj_grad,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 250, "ftol": 1e-7},
    )

    if res.success and not np.isnan(res.x).any():
        sol = np.clip(res.x, 0.0, 1.0)
        sol_sum = np.sum(sol)
        if sol_sum > 0:
            sol /= sol_sum
        return sol[:N], float(sol[N]), True, "Optimization converged."

    # Fallback: Relax group constraints
    if asset_class_limits:
        base_constraints = [{
            "type": "eq",
            "fun": lambda x: np.sum(x) - 1.0,
            "jac": lambda x: np.ones(dim, dtype=np.float64),
        }]
        res_relaxed = minimize(
            obj_fn,
            x0,
            jac=obj_grad,
            method="SLSQP",
            bounds=bounds,
            constraints=base_constraints,
            options={"maxiter": 250, "ftol": 1e-7},
        )
        if res_relaxed.success and not np.isnan(res_relaxed.x).any():
            sol = np.clip(res_relaxed.x, 0.0, 1.0)
            sol /= np.sum(sol)
            return sol[:N], float(sol[N]), False, "Converged with relaxed asset-class constraints."

    # Equal weight fallback
    w_fallback = np.full(N, rem_risky / N, dtype=np.float64)
    return w_fallback, target_cash, False, f"Optimization failed: {res.message}. Fell back to balanced cash."


def run_multi_asset_walk_forward_backtest(
    local_returns_df: pd.DataFrame,
    asset_classes: list[str],
    asset_currencies: list[str],
    base_currency: str = "USD",
    fx_rates_df: pd.DataFrame | None = None,
    hedge_ratios: dict[str, float] | None = None,
    carry_rates: dict[str, float] | None = None,
    asset_class_limits: dict[str, dict[str, float]] | None = None,
    min_cash_weight: float = 0.05,
    max_cash_weight: float = 0.25,
    rebalance_frequency: Literal["daily", "weekly", "biweekly", "monthly", "quarterly"] = "monthly",
    estimation_window: int = 60,
    objective: Literal["max_sharpe", "min_variance", "risk_parity"] = "max_sharpe",
    risk_free_rate: float = 0.03,
    transaction_cost_bps: float = 10.0,
    slippage_bps: float = 5.0,
    initial_capital: float = 100000.0,
    annualization_factor: int = 252,
) -> dict[str, Any]:
    """
    Executes a walk-forward multi-asset simulation with zero look-ahead bias,
    dynamic currency conversion, cash yield compounding, and weight drift.
    """
    T, N = local_returns_df.shape
    asset_names = list(local_returns_df.columns)
    dates = [str(d)[:10] for d in local_returns_df.index]

    if estimation_window < 20:
        raise ValueError(f"Estimation window ({estimation_window}) must be at least 20 trading days.")
    if T <= estimation_window + 5:
        raise ValueError(f"Insufficient history: {T} observations is too short for window {estimation_window}.")

    # Build FX returns dictionary
    fx_returns_dict: dict[str, np.ndarray] = {}
    if fx_rates_df is not None:
        for col in fx_rates_df.columns:
            fx_series = fx_rates_df[col].pct_change().fillna(0.0).to_numpy(dtype=np.float64)
            fx_returns_dict[col.upper()] = fx_series

    # Convert entire local returns matrix to hedged base-currency returns
    R_loc_matrix = local_returns_df.to_numpy(dtype=np.float64)
    R_base_matrix, R_unhedged_matrix = convert_local_returns_to_base(
        local_returns=R_loc_matrix,
        asset_currencies=asset_currencies,
        base_currency=base_currency,
        fx_returns=fx_returns_dict,
        hedge_ratios=hedge_ratios,
        carry_rates=carry_rates,
    )

    daily_rf = risk_free_rate / annualization_factor
    total_friction_rate = (transaction_cost_bps + slippage_bps) / 10000.0

    # Benchmark: 60/40 Equity/Bond (or equal weight if classes unspecified) + 10% Cash
    init_cash = min_cash_weight
    init_risky = np.full(N, (1.0 - init_cash) / N, dtype=np.float64)

    strategy_equity = initial_capital
    benchmark_equity = initial_capital
    peak_strategy_equity = initial_capital

    current_risky_w = init_risky.copy()
    drifted_risky_w = init_risky.copy()
    current_cash_w = init_cash
    drifted_cash_w = init_cash

    equity_curve: list[dict[str, Any]] = []
    rebalance_history: list[dict[str, Any]] = []
    asset_class_allocation_history: list[dict[str, Any]] = []
    cash_drag_series: list[float] = []

    daily_strategy_returns: list[float] = []
    daily_benchmark_returns: list[float] = []

    total_turnover = 0.0
    total_costs = 0.0
    total_rebalances = 0
    days_since_rebalance = 0
    first_rebalance = True

    # Unique asset classes
    unique_classes = sorted(list(set(asset_classes)))

    for t in range(estimation_window, T):
        curr_date = dates[t]
        prev_date = dates[t - 1]

        # Check rebalance
        if first_rebalance:
            is_rebal = True
        elif rebalance_frequency == "daily":
            is_rebal = True
        elif rebalance_frequency == "weekly":
            curr_dt = pd.to_datetime(curr_date)
            prev_dt = pd.to_datetime(prev_date)
            is_rebal = curr_dt.isocalendar().week != prev_dt.isocalendar().week
        elif rebalance_frequency == "biweekly":
            is_rebal = days_since_rebalance >= 10
        elif rebalance_frequency == "monthly":
            is_rebal = curr_date[:7] != prev_date[:7]
        elif rebalance_frequency == "quarterly":
            curr_m = int(curr_date[5:7])
            prev_m = int(prev_date[5:7])
            is_rebal = ((curr_m - 1) // 3) != ((prev_m - 1) // 3)
        else:
            is_rebal = False

        cost_incurred_today = 0.0
        turnover_today = 0.0

        if is_rebal:
            # STRICT ZERO LOOK-AHEAD:
            # Slices strictly ending at t - 1
            win_slice = R_base_matrix[t - estimation_window : t, :]

            mu_win = np.mean(win_slice, axis=0) * annualization_factor
            cov_win = np.cov(win_slice, rowvar=False) * annualization_factor
            if N == 1:
                cov_win = np.array([[float(cov_win)]])

            target_w_risky, target_w_cash, is_feas, status_msg = solve_multi_asset_allocation(
                expected_returns=mu_win,
                covariance_matrix=cov_win,
                asset_classes=asset_classes,
                asset_class_limits=asset_class_limits,
                min_cash_weight=min_cash_weight,
                max_cash_weight=max_cash_weight,
                risk_free_rate=risk_free_rate,
                objective=objective,
                annualization_factor=annualization_factor,
            )

            # Turnover on risky assets: 0.5 * sum(|w_new - w_drift|)
            turnover_today = float(0.5 * np.sum(np.abs(target_w_risky - drifted_risky_w)))
            traded_notional = 2.0 * turnover_today * strategy_equity
            cost_incurred_today = traded_notional * total_friction_rate

            strategy_equity = max(0.0, strategy_equity - cost_incurred_today)
            current_risky_w = target_w_risky.copy()
            drifted_risky_w = target_w_risky.copy()
            current_cash_w = target_w_cash
            drifted_cash_w = target_w_cash

            total_turnover += turnover_today
            total_costs += cost_incurred_today
            total_rebalances += 1
            days_since_rebalance = 0
            first_rebalance = False

            # Class allocations at rebalance
            class_allocs: dict[str, float] = {}
            for c in unique_classes:
                idx = [i for i, ac in enumerate(asset_classes) if ac == c]
                class_allocs[c] = round(float(np.sum(target_w_risky[idx])), 4)
            class_allocs["Cash"] = round(float(target_w_cash), 4)

            rebalance_history.append({
                "date": curr_date,
                "risky_weights": {asset_names[i]: round(float(target_w_risky[i]), 4) for i in range(N)},
                "cash_weight": round(float(target_w_cash), 4),
                "asset_class_allocations": class_allocs,
                "turnover": round(turnover_today, 4),
                "cost_incurred": round(cost_incurred_today, 2),
                "is_feasible": is_feas,
                "solver_message": status_msg,
            })
            asset_class_allocation_history.append({"date": curr_date, **class_allocs})
        else:
            days_since_rebalance += 1

        # Realize Day t Return
        r_today_risky = R_base_matrix[t, :]
        gross_risky_ret = float(np.dot(drifted_risky_w, r_today_risky))
        cash_ret = daily_rf * drifted_cash_w
        gross_strategy_ret = gross_risky_ret + cash_ret

        # Benchmark return: equal-weighted risky + 10% cash
        bm_risky = float(np.mean(r_today_risky)) * 0.90
        bm_cash = daily_rf * 0.10
        benchmark_ret = bm_risky + bm_cash

        # Cash drag calculation
        # Difference in return between fully-invested risky allocation vs actual strategy
        risky_weight_sum = np.sum(drifted_risky_w)
        if risky_weight_sum > 1e-6:
            fully_invested_ret = float(np.dot(drifted_risky_w / risky_weight_sum, r_today_risky))
            cash_drag_today = drifted_cash_w * (fully_invested_ret - daily_rf)
        else:
            cash_drag_today = 0.0
        cash_drag_series.append(cash_drag_today)

        # Advance Equity
        strategy_equity *= (1.0 + gross_strategy_ret)
        benchmark_equity *= (1.0 + benchmark_ret)

        daily_strategy_returns.append(gross_strategy_ret)
        daily_benchmark_returns.append(benchmark_ret)

        # Update weight drift for next day
        denom = 1.0 + gross_strategy_ret
        if denom > 1e-12:
            drifted_risky_w = (drifted_risky_w * (1.0 + r_today_risky)) / denom
            drifted_cash_w = (drifted_cash_w * (1.0 + daily_rf)) / denom
        else:
            drifted_risky_w = init_risky.copy()
            drifted_cash_w = init_cash

        if strategy_equity > peak_strategy_equity:
            peak_strategy_equity = strategy_equity
        drawdown = (strategy_equity - peak_strategy_equity) / peak_strategy_equity if peak_strategy_equity > 0 else 0.0

        equity_curve.append({
            "date": curr_date,
            "portfolio_equity": round(strategy_equity, 2),
            "benchmark_equity": round(benchmark_equity, 2),
            "portfolio_return": round(gross_strategy_ret, 6),
            "benchmark_return": round(benchmark_ret, 6),
            "drawdown": round(drawdown, 4),
            "cash_drag": round(cash_drag_today, 6),
        })

    # Summary Statistics
    strat_rets = np.array(daily_strategy_returns, dtype=np.float64)
    bm_rets = np.array(daily_benchmark_returns, dtype=np.float64)
    sim_days = len(strat_rets)

    total_return = (strategy_equity - initial_capital) / initial_capital
    cagr = (1.0 + total_return) ** (annualization_factor / max(1, sim_days)) - 1.0 if sim_days > 0 and total_return > -1.0 else 0.0
    vol = float(np.std(strat_rets, ddof=1) * math.sqrt(annualization_factor)) if sim_days > 1 else 0.0
    excess_ann = cagr - risk_free_rate
    sharpe = excess_ann / vol if vol > 1e-8 else 0.0

    downside_rets = strat_rets[strat_rets < 0.0]
    downside_vol = float(np.std(downside_rets, ddof=1) * math.sqrt(annualization_factor)) if len(downside_rets) > 1 else 1e-8
    sortino = excess_ann / downside_vol if downside_vol > 1e-8 else 0.0

    max_dd = float(min(p["drawdown"] for p in equity_curve)) if equity_curve else 0.0
    calmar = cagr / abs(max_dd) if abs(max_dd) > 1e-6 else 0.0

    # Benchmark stats
    bm_tot = (benchmark_equity - initial_capital) / initial_capital
    bm_cagr = (1.0 + bm_tot) ** (annualization_factor / max(1, sim_days)) - 1.0 if sim_days > 0 and bm_tot > -1.0 else 0.0
    bm_vol = float(np.std(bm_rets, ddof=1) * math.sqrt(annualization_factor)) if sim_days > 1 else 0.0
    bm_sharpe = (bm_cagr - risk_free_rate) / bm_vol if bm_vol > 1e-8 else 0.0

    active_rets = strat_rets - bm_rets
    active_return = cagr - bm_cagr
    tracking_error = float(np.std(active_rets, ddof=1) * math.sqrt(annualization_factor)) if sim_days > 1 else 0.0
    info_ratio = active_return / tracking_error if tracking_error > 1e-8 else 0.0

    # FX risk decomposition on full sample
    fx_decomp = decompose_multi_asset_fx_risk(
        weights=current_risky_w,
        local_returns=R_loc_matrix,
        unhedged_base_returns=R_unhedged_matrix,
        asset_currencies=asset_currencies,
        base_currency=base_currency,
        fx_returns=fx_returns_dict,
        annualization_factor=annualization_factor,
    )

    return {
        "summary": {
            "initial_capital": initial_capital,
            "final_equity": round(strategy_equity, 2),
            "total_return": round(total_return, 4),
            "cagr": round(cagr, 4),
            "annualized_volatility": round(vol, 4),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown": round(max_dd, 4),
            "calmar_ratio": round(calmar, 4),
            "total_turnover": round(total_turnover, 4),
            "total_transaction_costs": round(total_costs, 2),
            "total_rebalances": total_rebalances,
            "active_return": round(active_return, 4),
            "tracking_error": round(tracking_error, 4),
            "information_ratio": round(info_ratio, 4),
            "total_cash_drag": round(float(np.sum(cash_drag_series)), 4),
        },
        "benchmark": {
            "final_equity": round(benchmark_equity, 2),
            "total_return": round(bm_tot, 4),
            "cagr": round(bm_cagr, 4),
            "annualized_volatility": round(bm_vol, 4),
            "sharpe_ratio": round(bm_sharpe, 4),
        },
        "fx_risk_decomposition": fx_decomp,
        "equity_curve": equity_curve,
        "rebalance_history": rebalance_history,
        "asset_class_allocation_history": asset_class_allocation_history,
    }
