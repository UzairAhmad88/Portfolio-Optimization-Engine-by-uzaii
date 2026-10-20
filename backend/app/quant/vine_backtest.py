"""
Pure Numerical Financial Mathematics Engine for Dynamic Walk-Forward
Vine Copula Tail Risk Parity (TRP) Backtesting.

Stage 24 Institutional Implementation.
Provides:
1. Strict causal chronological rolling estimation windows (zero look-ahead bias).
2. Dynamic C-Vine and D-Vine re-estimation and Monte Carlo scenario simulation.
3. Tail Risk Parity allocation optimization at defined rebalance frequencies.
4. Frictional discrete wealth compounding tracking weight drift, one-way turnover,
   and basis-point transaction costs.
5. Benchmark comparisons against Equal-Weight (1/N) and Static TRP.
6. Comprehensive out-of-sample performance, risk, and drawdown analytics.
"""

from __future__ import annotations

import math
from typing import Any, Literal
import numpy as np
import pandas as pd

from app.quant.copula_tail_risk import (
    compute_portfolio_tail_risk,
    optimize_tail_risk_parity,
)
from app.quant.execution import (
    compute_daily_liquidation_loss,
    compute_execution_horizon,
    compute_liquidity_adjusted_var_cvar,
    compute_multi_day_execution_schedule,
    compute_rebalance_market_impact,
    compute_regime_aware_execution_parameters,
    compute_scenario_endogenous_liquidity_risk,
)
from app.quant.regime_switching import GaussianHMM
from app.quant.tca import (
    TradeFill,
    compute_transaction_cost_analysis,
    reconcile_tca_with_backtest_costs,
)
from app.quant.vine_copula import (
    fit_c_vine,
    fit_d_vine,
    simulate_vine_returns,
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


def _execute_cash_financed_tranche(
    tranche_notionals: dict[str, float],
    strat_drifted: np.ndarray,
    strat_cash_drifted: float,
    strat_equity: float,
    asset_names: list[str],
    current_adv_dict: dict[str, float],
    rebal_vol_dict: dict[str, float],
    execution_horizon_days: float,
    max_participation_rate: float,
    participation_policy: str,
    execution_model: str,
    bid_ask_spread_bps: float,
    transaction_cost_bps: float,
    slippage_bps: float,
    c_temp: float,
    c_perm: float,
    default_adv: float,
    annualization_factor: int = 252,
) -> dict[str, Any]:
    """
    Executes a single daily trade tranche through the causal queue-based cash-financed execution engine.
    Applies sell priority, volume capping, fee pre-allocation, and strict cash budget conservation.
    """
    N = len(asset_names)
    exec_w = strat_drifted.copy()
    exec_notionals = {tk: 0.0 for tk in asset_names}

    sell_indices = [i for i in range(N) if tranche_notionals.get(asset_names[i], 0.0) < -1e-7]
    buy_indices = [i for i in range(N) if tranche_notionals.get(asset_names[i], 0.0) > 1e-7]

    # Check reject policy on tranche if policy is reject
    if participation_policy == "reject":
        for i in range(N):
            tk = asset_names[i]
            t_val = abs(float(tranche_notionals.get(tk, 0.0)))
            if t_val > 1e-6:
                adv_i = max(1000.0, float(current_adv_dict.get(tk, default_adv)))
                if (t_val / (adv_i * execution_horizon_days)) > max_participation_rate:
                    return {
                        "target_w": strat_drifted.copy(),
                        "strat_cash": strat_cash_drifted,
                        "cost_today": 0.0,
                        "spread_cost_today": 0.0,
                        "impact_cost_today": 0.0,
                        "commission_cost_today": 0.0,
                        "turnover_today": 0.0,
                        "max_pr_today": t_val / (adv_i * execution_horizon_days),
                        "part_warn_today": True,
                        "rebal_rejected_today": True,
                        "exec_notionals": exec_notionals,
                        "asset_impacts": [],
                    }

    total_exec_sells_dollars = 0.0
    for i in sell_indices:
        tk = asset_names[i]
        desired_sell_dollars = abs(float(tranche_notionals[tk]))
        adv = max(1000.0, float(current_adv_dict.get(tk, default_adv)))
        vol_cap_dollars = max_participation_rate * adv * execution_horizon_days
        exec_sell_dollars = min(desired_sell_dollars, vol_cap_dollars) if participation_policy == "cap" else desired_sell_dollars
        exec_notionals[tk] = exec_sell_dollars
        total_exec_sells_dollars += exec_sell_dollars
        exec_w[i] = strat_drifted[i] - (exec_sell_dollars / strat_equity) if strat_equity > 0 else strat_drifted[i]

    sell_traded = {asset_names[i]: exec_notionals[asset_names[i]] for i in sell_indices}
    if sell_traded:
        sell_impact_res = compute_rebalance_market_impact(
            traded_notionals=sell_traded,
            adv_dict=current_adv_dict,
            volatility_dict=rebal_vol_dict,
            spread_bps_dict={tk: bid_ask_spread_bps for tk in asset_names},
            execution_horizon_days=execution_horizon_days,
            impact_model=execution_model,
            c_temp=c_temp,
            c_perm=c_perm,
            commission_bps=transaction_cost_bps,
            max_participation_rate=max_participation_rate,
            participation_policy="warn",
        )
        total_sell_cost = float(sell_impact_res["summary"]["total_impact_cost"])
    else:
        total_sell_cost = 0.0

    pre_trade_cash_dollars = strat_cash_drifted * strat_equity
    available_cash_dollars = max(0.0, pre_trade_cash_dollars + total_exec_sells_dollars - total_sell_cost)

    capped_buy_dollars: dict[int, float] = {}
    total_capped_buy_dollars = 0.0
    est_buy_fees_dollars = 0.0

    for j in buy_indices:
        tk = asset_names[j]
        desired_buy_dollars = max(0.0, float(tranche_notionals[tk]))
        adv = max(1000.0, float(current_adv_dict.get(tk, default_adv)))
        vol_cap_dollars = max_participation_rate * adv * execution_horizon_days
        capped_dollars = min(desired_buy_dollars, vol_cap_dollars) if participation_policy == "cap" else desired_buy_dollars
        capped_buy_dollars[j] = capped_dollars
        total_capped_buy_dollars += capped_dollars

        ann_vol = max(0.001, float(rebal_vol_dict.get(tk, 0.20)))
        daily_vol = ann_vol / math.sqrt(annualization_factor)
        pr_j = capped_dollars / (adv * execution_horizon_days) if (adv * execution_horizon_days) > 0 else 0.0
        est_fee_rate_j = (bid_ask_spread_bps * 1e-4 / 2.0) + (transaction_cost_bps * 1e-4)
        if execution_model == "square_root":
            est_fee_rate_j += c_temp * daily_vol * min(math.sqrt(pr_j), 1.414) + c_perm * daily_vol * min(pr_j, 1.0)
        elif execution_model == "linear":
            est_fee_rate_j += c_temp * daily_vol * pr_j + c_perm * daily_vol * pr_j
        else:
            est_fee_rate_j += (slippage_bps * 1e-4)
        est_buy_fees_dollars += capped_dollars * est_fee_rate_j

    total_cash_needed = total_capped_buy_dollars + est_buy_fees_dollars
    psi = (available_cash_dollars / total_cash_needed) if (total_cash_needed > available_cash_dollars and total_cash_needed > 1e-12) else 1.0
    psi = max(0.0, min(1.0, psi))

    for j in buy_indices:
        tk = asset_names[j]
        exec_buy_dollars = capped_buy_dollars[j] * psi
        exec_notionals[tk] = exec_buy_dollars
        exec_w[j] = strat_drifted[j] + (exec_buy_dollars / strat_equity) if strat_equity > 0 else strat_drifted[j]

    post_trade_w = np.maximum(0.0, exec_w)
    tot_w = float(np.sum(post_trade_w))
    strat_cash = max(0.0, 1.0 - tot_w)

    final_impact_res = compute_rebalance_market_impact(
        traded_notionals=exec_notionals,
        adv_dict=current_adv_dict,
        volatility_dict=rebal_vol_dict,
        spread_bps_dict={tk: bid_ask_spread_bps for tk in asset_names},
        execution_horizon_days=execution_horizon_days,
        impact_model=execution_model,
        c_temp=c_temp,
        c_perm=c_perm,
        commission_bps=transaction_cost_bps,
        max_participation_rate=max_participation_rate,
        participation_policy="warn",
    )
    turnover_today = float(0.5 * np.sum(np.abs(post_trade_w - strat_drifted)))
    cost_today = float(final_impact_res["summary"]["total_impact_cost"])
    spread_cost_today = float(final_impact_res["summary"]["total_spread_cost"])
    impact_cost_today = float(final_impact_res["summary"]["total_market_impact_cost"])
    commission_cost_today = float(final_impact_res["summary"]["total_commission_cost"])
    max_pr_today = float(final_impact_res["summary"]["max_participation_rate_observed"])
    part_warn_today = bool(final_impact_res["summary"]["participation_warnings_count"] > 0)

    return {
        "target_w": post_trade_w,
        "strat_cash": strat_cash,
        "cost_today": cost_today,
        "spread_cost_today": spread_cost_today,
        "impact_cost_today": impact_cost_today,
        "commission_cost_today": commission_cost_today,
        "turnover_today": turnover_today,
        "max_pr_today": max_pr_today,
        "part_warn_today": part_warn_today,
        "rebal_rejected_today": False,
        "exec_notionals": exec_notionals,
        "asset_impacts": final_impact_res.get("asset_impacts", []),
    }


def _compute_strategy_kpis(
    daily_returns: list[float],
    equity_values: list[float],
    initial_capital: float,
    total_turnover: float,
    total_costs: float,
    risk_free_rate: float = 0.02,
    annualization_factor: int = 252,
    total_spread_costs: float = 0.0,
    total_market_impact_costs: float = 0.0,
    total_commission_costs: float = 0.0,
    max_participation_rate_observed: float = 0.0,
    participation_warnings_count: int = 0,
    average_liquidation_cost_pct: float = 0.0,
    average_cash_weight: float = 0.0,
    daily_losses_det: list[float] | None = None,
    daily_losses_stressed: list[float] | None = None,
    stress_var_uplift: float = 0.0,
    stress_cvar_uplift: float = 0.0,
) -> dict[str, Any]:
    """
    Computes annualized institutional performance, risk, and tail metrics
    from realized out-of-sample return series.
    """
    if not daily_returns:
        return {
            "total_return": 0.0,
            "total_return_net": 0.0,
            "total_return_gross": 0.0,
            "cagr": 0.0,
            "cagr_net": 0.0,
            "cagr_gross": 0.0,
            "annualized_volatility": 0.0,
            "annualized_volatility_gross": 0.0,
            "annualized_volatility_net": 0.0,
            "sharpe_ratio": 0.0,
            "sharpe_ratio_gross": 0.0,
            "sharpe_ratio_net": 0.0,
            "max_drawdown": 0.0,
            "calmar_ratio": 0.0,
            "historical_var_99": 0.0,
            "historical_cvar_99": 0.0,
            "l_var_99": 0.0,
            "l_cvar_99": 0.0,
            "stressed_l_var_99": 0.0,
            "stressed_l_cvar_99": 0.0,
            "average_cash_weight": 0.0,
            "total_turnover": 0.0,
            "total_transaction_costs": 0.0,
            "total_spread_costs": 0.0,
            "total_market_impact_costs": 0.0,
            "total_commission_costs": 0.0,
            "max_participation_rate_observed": 0.0,
            "participation_warnings_count": 0,
        }

    ret_arr_gross = np.array(daily_returns, dtype=np.float64)
    final_equity = equity_values[-1] if equity_values else initial_capital
    n_days = len(ret_arr_gross)
    years = max(1.0 / annualization_factor, n_days / annualization_factor)

    # Net daily returns derived from consecutive net equity observations (DEF-47-01)
    net_daily_returns: list[float] = []
    prev_eq = initial_capital
    for eq in equity_values:
        if prev_eq > 1e-8:
            r_net = float(eq / prev_eq - 1.0)
        else:
            r_net = 0.0
        net_daily_returns.append(r_net)
        prev_eq = eq

    ret_arr_net = np.array(net_daily_returns, dtype=np.float64)

    # Cumulative returns and CAGR
    total_return_net = float(final_equity / initial_capital - 1.0) if initial_capital > 0 else 0.0
    cagr_net = (
        float((final_equity / initial_capital) ** (1.0 / years) - 1.0)
        if (initial_capital > 0 and final_equity > 0)
        else total_return_net
    )

    if n_days > 0:
        total_return_gross = float(np.prod(1.0 + ret_arr_gross) - 1.0)
    else:
        total_return_gross = 0.0
    cagr_gross = (
        float((1.0 + total_return_gross) ** (1.0 / years) - 1.0)
        if (1.0 + total_return_gross) > 0
        else total_return_gross
    )

    # Gross Volatility and Sharpe
    vol_daily_gross = float(np.std(ret_arr_gross, ddof=1)) if n_days > 1 else 0.0
    ann_vol_gross = vol_daily_gross * math.sqrt(annualization_factor)
    excess_gross = ret_arr_gross - (risk_free_rate / annualization_factor)
    sharpe_gross = (
        float(np.mean(excess_gross) / vol_daily_gross * math.sqrt(annualization_factor))
        if vol_daily_gross > 1e-8
        else 0.0
    )

    # Net Volatility and Sharpe
    vol_daily_net = float(np.std(ret_arr_net, ddof=1)) if n_days > 1 else 0.0
    ann_vol_net = vol_daily_net * math.sqrt(annualization_factor)
    excess_net = ret_arr_net - (risk_free_rate / annualization_factor)
    sharpe_net = (
        float(np.mean(excess_net) / vol_daily_net * math.sqrt(annualization_factor))
        if vol_daily_net > 1e-8
        else 0.0
    )

    # Max Drawdown from net equity series
    eq_arr = np.array(equity_values, dtype=np.float64)
    peaks = np.maximum.accumulate(eq_arr)
    drawdowns = np.where(peaks > 0, (eq_arr - peaks) / peaks, 0.0)
    max_dd = float(np.min(drawdowns)) if len(drawdowns) > 0 else 0.0

    calmar = float(cagr_net / abs(max_dd)) if abs(max_dd) > 1e-6 else 0.0

    # Realized historical 99% VaR and CVaR (computed on gross portfolio losses)
    losses = -ret_arr_gross
    var_99 = float(np.quantile(losses, 0.99, method="linear"))
    tail_losses = losses[losses >= var_99]
    cvar_99 = float(np.mean(tail_losses)) if len(tail_losses) > 0 else var_99

    # Unified Out-of-Sample Liquidation Loss Distributions (DEF-35-02)
    if daily_losses_det is not None and len(daily_losses_det) > 0:
        det_arr = np.array(daily_losses_det, dtype=np.float64)
        l_var_99 = float(np.quantile(det_arr, 0.99, method="linear"))
        tail_det = det_arr[det_arr >= l_var_99]
        l_cvar_99 = float(np.mean(tail_det)) if len(tail_det) > 0 else l_var_99
    else:
        l_var_99 = var_99 + average_liquidation_cost_pct
        l_cvar_99 = cvar_99 + average_liquidation_cost_pct

    if daily_losses_stressed is not None and len(daily_losses_stressed) > 0:
        stress_arr = np.array(daily_losses_stressed, dtype=np.float64)
        stressed_l_var_99 = float(np.quantile(stress_arr, 0.99, method="linear"))
        tail_stress = stress_arr[stress_arr >= stressed_l_var_99]
        stressed_l_cvar_99 = float(np.mean(tail_stress)) if len(tail_stress) > 0 else stressed_l_var_99
    else:
        stressed_l_var_99 = l_var_99 + stress_var_uplift
        stressed_l_cvar_99 = l_cvar_99 + stress_cvar_uplift

    return {
        "total_return": round(total_return_net, 4),
        "total_return_net": round(total_return_net, 4),
        "total_return_gross": round(total_return_gross, 4),
        "cagr": round(cagr_net, 4),
        "cagr_net": round(cagr_net, 4),
        "cagr_gross": round(cagr_gross, 4),
        "annualized_volatility": round(ann_vol_gross, 4),
        "annualized_volatility_gross": round(ann_vol_gross, 4),
        "annualized_volatility_net": round(ann_vol_net, 4),
        "sharpe_ratio": round(sharpe_gross, 4),
        "sharpe_ratio_gross": round(sharpe_gross, 4),
        "sharpe_ratio_net": round(sharpe_net, 4),
        "max_drawdown": round(max_dd, 4),
        "calmar_ratio": round(calmar, 4),
        "historical_var_99": round(var_99, 4),
        "historical_cvar_99": round(cvar_99, 4),
        "l_var_99": round(l_var_99, 4),
        "l_cvar_99": round(l_cvar_99, 4),
        "stressed_l_var_99": round(stressed_l_var_99, 4),
        "stressed_l_cvar_99": round(stressed_l_cvar_99, 4),
        "average_cash_weight": round(average_cash_weight, 4),
        "total_turnover": round(total_turnover, 4),
        "total_transaction_costs": round(total_costs, 2),
        "total_spread_costs": round(total_spread_costs, 2),
        "total_market_impact_costs": round(total_market_impact_costs, 2),
        "total_commission_costs": round(total_commission_costs, 2),
        "max_participation_rate_observed": round(max_participation_rate_observed, 4),
        "participation_warnings_count": participation_warnings_count,
    }


def run_vine_tail_risk_parity_backtest(
    returns_df: pd.DataFrame,
    volumes_df: pd.DataFrame | None = None,
    vine_type: Literal["c_vine", "d_vine"] = "c_vine",
    estimation_window: int = 60,
    rebalance_frequency: Literal["daily", "weekly", "biweekly", "monthly", "quarterly"] = "monthly",
    num_simulations: int = 2000,
    confidence_level: float = 0.99,
    marginal_method: Literal["empirical", "student_t"] = "empirical",
    transaction_cost_bps: float = 10.0,
    slippage_bps: float = 5.0,
    initial_capital: float = 100000.0,
    risk_free_rate: float = 0.02,
    random_seed: int = 42,
    annualization_factor: int = 252,
    execution_model: Literal["fixed_bps", "linear", "square_root"] = "fixed_bps",
    bid_ask_spread_bps: float = 5.0,
    max_participation_rate: float = 0.10,
    participation_policy: Literal["warn", "cap", "reject"] = "warn",
    execution_horizon_days: float = 1.0,
    c_temp: float = 0.5,
    c_perm: float = 0.1,
    default_adv: float = 10_000_000.0,
    enable_endogenous_liquidity: bool = True,
    spread_stress_sensitivity: float = 5.0,
    adv_stress_sensitivity: float = 5.0,
    execution_scheduling_mode: Literal["single_day", "twap", "vwap", "almgren_chriss"] = "single_day",
    max_scheduling_days: int = 5,
    scheduling_risk_aversion: float = 1e-6,
    enable_regime_aware_execution: bool = False,
    regime_num_states: int = 2,
    regime_adaptation_strength: float = 0.5,
    min_participation_rate: float = 0.02,
) -> dict[str, Any]:
    """
    Executes a walk-forward dynamic Vine Tail Risk Parity backtest simulation
    with strict zero look-ahead bias, non-linear market impact friction,
    volume participation constraints, and liquidity-adjusted tail risk analytics.

    Parameters:
        returns_df: DataFrame of asset returns (rows: dates, cols: tickers)
        volumes_df: Optional DataFrame of historical traded volumes (rows: dates, cols: tickers)
        vine_type: "c_vine" or "d_vine"
        estimation_window: Lookback window W in trading days (must be >= 30)
        rebalance_frequency: "daily", "weekly", "biweekly", "monthly", or "quarterly"
        num_simulations: Monte Carlo scenario count M per rebalance (1000 - 20000)
        confidence_level: Tail Risk confidence level alpha (0.90 - 0.999)
        marginal_method: "empirical" or "student_t" marginal distribution fitting
        transaction_cost_bps: Commission friction in basis points
        slippage_bps: Market impact slippage in basis points (for fixed_bps model)
        initial_capital: Starting equity in currency units
        risk_free_rate: Annualized benchmark risk-free rate
        random_seed: Base seed for reproducible scenario generation
        annualization_factor: Trading days per year (252)
        execution_model: "square_root" (Almgren/Barra law), "linear", or "fixed_bps"
        bid_ask_spread_bps: Quoted full bid-ask spread in basis points (half-spread crossed)
        max_participation_rate: Maximum volume participation rate (e.g. 0.10 for 10% ADV)
        participation_policy: "warn", "cap", or "reject"
        execution_horizon_days: Horizon in days allocated for execution
        c_temp: Temporary market impact coefficient
        c_perm: Permanent market impact coefficient
        default_adv: Fallback Average Daily Dollar Volume when volume data is missing

    Returns:
        Structured dictionary matching VineBacktestResponse schema.
    """
    T, N = returns_df.shape
    asset_names = list(returns_df.columns)
    dates = [str(d)[:10] for d in returns_df.index]

    if N < 2:
        raise ValueError("Vine Tail Risk Parity backtest requires at least 2 distinct assets.")
    if estimation_window < 30:
        raise ValueError(f"Estimation window ({estimation_window}) must be at least 30 trading days.")
    if T <= estimation_window + 5:
        raise ValueError(
            f"Insufficient data: {T} total observations is too short for estimation window {estimation_window}."
        )

    R_matrix = returns_df.to_numpy(dtype=np.float64)
    total_friction_rate = (transaction_cost_bps + slippage_bps) / 10000.0

    # Benchmark: Equal-weighted baseline
    ew_weights = np.full(N, 1.0 / N, dtype=np.float64)

    # State Tracking: Strategy
    strat_equity = float(initial_capital)
    strat_peak = float(initial_capital)
    strat_weights = ew_weights.copy()
    strat_drifted = ew_weights.copy()
    strat_cash = 0.0
    strat_cash_drifted = 0.0
    strat_cash_history: list[float] = []
    strat_stressed_l_var_list: list[float] = []
    strat_stressed_l_cvar_list: list[float] = []
    strat_stress_uplift_var_list: list[float] = []
    strat_stress_uplift_cvar_list: list[float] = []
    strat_daily_rets: list[float] = []
    strat_equity_series: list[float] = []
    strat_total_turnover = 0.0
    strat_total_costs = 0.0
    strat_total_spread_costs = 0.0
    strat_total_impact_costs = 0.0
    strat_total_commission_costs = 0.0
    strat_max_pr_observed = 0.0
    strat_participation_warnings = 0
    strat_liquidation_costs_pct: list[float] = []
    strat_daily_losses_det: list[float] = []
    strat_daily_losses_stressed: list[float] = []
    strat_daily_liq_costs_pct: list[float] = []

    # State Tracking: Benchmark (Equal-Weight)
    bench_equity = float(initial_capital)
    bench_weights = ew_weights.copy()
    bench_drifted = ew_weights.copy()
    bench_daily_rets: list[float] = []
    bench_equity_series: list[float] = []
    bench_total_turnover = 0.0
    bench_total_costs = 0.0
    bench_total_spread_costs = 0.0
    bench_total_impact_costs = 0.0
    bench_total_commission_costs = 0.0
    bench_max_pr_observed = 0.0
    bench_participation_warnings = 0

    # State Tracking: Static TRP (Estimated once on initial window W)
    static_equity = float(initial_capital)
    static_drifted = ew_weights.copy()
    static_daily_rets: list[float] = []
    static_equity_series: list[float] = []
    static_total_costs = 0.0

    # Audit & Timeline Data
    equity_curve: list[dict[str, Any]] = []
    rebalance_history: list[dict[str, Any]] = []
    strat_trade_fills: list[TradeFill] = []

    total_rebalances = 0
    fallback_rebalances = 0
    days_since_rebalance = 0
    first_rebalance = True
    overall_adv_source = "market_observed" if (volumes_df is not None and not volumes_df.empty) else "model_fallback"

    # Initial Static TRP fit on window [0 : estimation_window]
    try:
        init_window = R_matrix[:estimation_window, :]
        init_sim_rets, _ = simulate_vine_returns(
            returns=init_window,
            tickers=asset_names,
            vine_type=vine_type,
            num_simulations=num_simulations,
            random_seed=random_seed,
            marginal_method=marginal_method,
        )
        init_trp_res = optimize_tail_risk_parity(
            simulated_returns=init_sim_rets,
            tickers=asset_names,
            confidence_level=confidence_level,
        )
        static_target = np.array([init_trp_res["weights"][tk] for tk in asset_names], dtype=np.float64)
        static_drifted = static_target.copy()

        # Deduct initial friction for static TRP
        if execution_model == "fixed_bps":
            init_to = float(0.5 * np.sum(np.abs(static_target - ew_weights)))
            init_cost = 2.0 * init_to * static_equity * total_friction_rate
        else:
            init_vol_dict = {
                asset_names[i]: max(0.001, float(np.std(init_window[:, i], ddof=1)) * math.sqrt(annualization_factor))
                for i in range(N)
            }
            init_adv_dict = {}
            for tk in asset_names:
                if volumes_df is not None and tk in volumes_df.columns:
                    v_slice = volumes_df[tk].iloc[:estimation_window].dropna()
                    if len(v_slice) >= 10 and float(v_slice.mean()) > 0:
                        init_adv_dict[tk] = float(v_slice.mean())
                    else:
                        init_adv_dict[tk] = default_adv
                else:
                    init_adv_dict[tk] = default_adv

            init_traded = {asset_names[i]: abs(static_target[i] - ew_weights[i]) * static_equity for i in range(N)}
            init_impact = compute_rebalance_market_impact(
                traded_notionals=init_traded,
                adv_dict=init_adv_dict,
                volatility_dict=init_vol_dict,
                spread_bps_dict={tk: bid_ask_spread_bps for tk in asset_names},
                execution_horizon_days=execution_horizon_days,
                impact_model=execution_model,
                c_temp=c_temp,
                c_perm=c_perm,
                commission_bps=transaction_cost_bps,
                max_participation_rate=max_participation_rate,
                participation_policy="warn",
            )
            init_cost = float(init_impact["summary"]["total_impact_cost"])

        static_equity = max(0.0, static_equity - init_cost)
        static_total_costs += init_cost
    except Exception:
        static_drifted = ew_weights.copy()

    # Pre-loop point-in-time ADV tracking
    current_adv_dict = {tk: default_adv for tk in asset_names}
    if volumes_df is not None and not volumes_df.empty:
        for tk in asset_names:
            if tk in volumes_df.columns:
                v_init = volumes_df[tk].iloc[:estimation_window].dropna()
                if len(v_init) >= 10 and float(v_init.mean()) > 0:
                    current_adv_dict[tk] = float(v_init.mean())

    # Multi-Day In-Flight Order Queue (Stage 28)
    in_flight_queue: dict[str, Any] | None = None

    # Walk-Forward Simulation Loop (Strictly starting at index estimation_window)
    for t in range(estimation_window, T):
        curr_date = dates[t]
        prev_date = dates[t - 1]

        # Check rebalance trigger for today
        is_rebal = first_rebalance or _is_rebalance_trigger(
            rebalance_frequency, curr_date, prev_date, days_since_rebalance
        )

        cost_today = 0.0
        turnover_today = 0.0
        spread_cost_today = 0.0
        impact_cost_today = 0.0
        commission_cost_today = 0.0
        max_pr_today = 0.0
        part_warn_today = False
        rebal_rejected_today = False
        rebal_adv_source = "model_fallback"

        if is_rebal:
            # STRICT ZERO LOOK-AHEAD:
            # Lookback window uses strictly observations in [t - estimation_window : t]
            # which ends at index t - 1 (the close prior to today's decision).
            window_slice = R_matrix[t - estimation_window : t, :]
            training_start = dates[t - estimation_window]
            training_end = dates[t - 1]

            rebal_seed = random_seed + total_rebalances * 1007
            rebal_converged = True
            solver_msg = "Optimized successfully."

            # Estimate point-in-time volatilities and ADVs strictly on [t - W : t]
            rebal_vol_dict = {
                asset_names[i]: max(0.001, float(np.std(window_slice[:, i], ddof=1)) * math.sqrt(annualization_factor))
                for i in range(N)
            }
            rebal_adv_dict = {}
            rebal_adv_source = "market_observed" if (volumes_df is not None and not volumes_df.empty) else "model_fallback"
            for tk in asset_names:
                if volumes_df is not None and tk in volumes_df.columns:
                    v_slice = volumes_df[tk].iloc[t - estimation_window : t].dropna()
                    if len(v_slice) >= 10 and float(v_slice.mean()) > 0:
                        rebal_adv_dict[tk] = float(v_slice.mean())
                    else:
                        rebal_adv_dict[tk] = default_adv
                        rebal_adv_source = "model_fallback"
                else:
                    rebal_adv_dict[tk] = default_adv

            current_adv_dict = rebal_adv_dict.copy()

            sim_rets = None
            try:
                # 1. Fit Vine and simulate out-of-sample scenarios
                sim_rets, diag = simulate_vine_returns(
                    returns=window_slice,
                    tickers=asset_names,
                    vine_type=vine_type,
                    num_simulations=num_simulations,
                    random_seed=rebal_seed,
                    marginal_method=marginal_method,
                )

                # 2. Solve Tail Risk Parity
                trp_res = optimize_tail_risk_parity(
                    simulated_returns=sim_rets,
                    tickers=asset_names,
                    confidence_level=confidence_level,
                )

                target_w = np.array([trp_res["weights"][tk] for tk in asset_names], dtype=np.float64)
                target_w = np.maximum(0.0, target_w)
                target_w /= np.sum(target_w)
                requested_target_w = target_w.copy()
                rebal_cvar = float(trp_res.get("portfolio_cvar", 0.0))
                rebal_var = float(trp_res.get("portfolio_var", 0.0))
                trcs = {tk: round(float(trp_res["tail_risk_contributions"].get(tk, 0.0)), 4) for tk in asset_names}

            except Exception as exc:
                # Fallback to existing drifted weights if optimization fails
                target_w = strat_drifted.copy()
                requested_target_w = strat_drifted.copy()
                rebal_converged = False
                fallback_rebalances += 1
                solver_msg = f"Rebalance solver fallback: {str(exc)}"
                rebal_cvar = 0.0
                rebal_var = 0.0
                trcs = {tk: round(float(target_w[i]), 4) for i, tk in enumerate(asset_names)}

            # 3. Calculate turnover and friction on Strategy
            # Cancel any existing in-flight queue upon new rebalance trigger (Conflict Resolution)
            if in_flight_queue is not None and len(in_flight_queue.get("remaining_tranches", [])) > 0:
                for rem_tranche in in_flight_queue["remaining_tranches"]:
                    for tk, tranche_n in rem_tranche.items():
                        if abs(tranche_n) > 1e-6:
                            dir_i = 1.0 if tranche_n > 0 else -1.0
                            asset_idx = asset_names.index(tk) if tk in asset_names else 0
                            strat_trade_fills.append(TradeFill(
                                date=curr_date,
                                ticker=tk,
                                direction=dir_i,
                                requested_notional=abs(tranche_n),
                                executed_notional=0.0,
                                arrival_price=100.0,
                                fill_price=100.0,
                                spread_cost=0.0,
                                temp_impact_cost=0.0,
                                perm_impact_cost=0.0,
                                commission_cost=0.0,
                                total_cost=0.0,
                                realized_asset_return=float(R_matrix[t, asset_idx]),
                                regime_state=in_flight_queue.get("regime_state"),
                                regime_p_turbulent=in_flight_queue.get("regime_p_turbulent", 0.0),
                                scheduling_mode="cancelled",
                                scheduled_horizon_days=in_flight_queue.get("total_scheduled_days", 1),
                                tranche_day_index=in_flight_queue.get("current_tranche_index", 0),
                                parent_order_notional=abs(in_flight_queue.get("parent_order_notionals", {}).get(tk, tranche_n)),
                                order_id=in_flight_queue.get("order_ids", {}).get(tk, f"CANCELLED_{tk}"),
                            ))
            in_flight_queue = None

            # Regime-Aware Execution Dynamics (Stage 29) State Initialization
            current_regime_state: int | None = None
            regime_probs_today: list[float] | None = None
            effective_pr_today: float = max_participation_rate
            effective_lambda_today: float = scheduling_risk_aversion

            if execution_model == "fixed_bps" and execution_scheduling_mode == "single_day":
                turnover_today = float(0.5 * np.sum(np.abs(target_w - strat_drifted)))
                traded_notional = 2.0 * turnover_today * strat_equity
                cost_today = traded_notional * total_friction_rate
                spread_cost_today = 0.0
                impact_cost_today = traded_notional * (slippage_bps / 10000.0)
                commission_cost_today = traded_notional * (transaction_cost_bps / 10000.0)
                max_pr_today = 0.0
                part_warn_today = False
                rebal_rejected_today = False
                strat_cash = max(0.0, 1.0 - float(np.sum(target_w)))
                scheduled_days = 1

                for i in range(N):
                    tk = asset_names[i]
                    delta_w = float(target_w[i] - strat_drifted[i])
                    if abs(delta_w) > 1e-6:
                        req_n = delta_w * strat_equity
                        exec_n = abs(req_n)
                        dir_i = 1.0 if req_n > 0 else -1.0
                        c_imp = exec_n * (slippage_bps / 10000.0)
                        c_com = exec_n * (transaction_cost_bps / 10000.0)
                        c_tot = c_imp + c_com
                        arr_p = 100.0
                        fill_p = arr_p * (1.0 + dir_i * (c_tot / exec_n)) if exec_n > 0 else arr_p
                        strat_trade_fills.append(TradeFill(
                            date=curr_date,
                            ticker=tk,
                            direction=dir_i,
                            requested_notional=abs(req_n),
                            executed_notional=exec_n,
                            arrival_price=arr_p,
                            fill_price=fill_p,
                            spread_cost=0.0,
                            temp_impact_cost=c_imp,
                            perm_impact_cost=0.0,
                            commission_cost=c_com,
                            total_cost=c_tot,
                            realized_asset_return=float(R_matrix[t, i]),
                            regime_state=current_regime_state,
                            regime_p_turbulent=regime_probs_today[-1] if regime_probs_today else 0.0,
                            scheduling_mode="single_day",
                            scheduled_horizon_days=1,
                            tranche_day_index=0,
                            parent_order_notional=abs(req_n),
                            order_id=f"REBAL_{total_rebalances + 1}_{tk}",
                        ))
            else:
                intended_notionals = {
                    asset_names[i]: float((target_w[i] - strat_drifted[i]) * strat_equity)
                    for i in range(N)
                }

                if enable_regime_aware_execution:
                    try:
                        # Estimate Gaussian HMM causally strictly on [t - estimation_window : t]
                        mkt_rets = np.mean(window_slice, axis=1, keepdims=True)
                        hmm = GaussianHMM(n_states=regime_num_states, random_state=rebal_seed)
                        hmm.fit(mkt_rets)
                        # Causal filtered state probabilities at decision time t (time t-1 close)
                        filtered_p = hmm.predict_proba(mkt_rets, causal=True)
                        regime_probs_today = [float(p) for p in filtered_p[-1]]
                        current_regime_state = int(np.argmax(regime_probs_today))

                        reg_params = compute_regime_aware_execution_parameters(
                            base_participation_rate=max_participation_rate,
                            base_risk_aversion=scheduling_risk_aversion,
                            regime_probs=regime_probs_today,
                            regime_adaptation_strength=regime_adaptation_strength,
                            min_participation_rate=min_participation_rate,
                            max_participation_rate_upper=max_participation_rate,
                        )
                        effective_pr_today = float(reg_params["effective_participation_rate"])
                        effective_lambda_today = float(reg_params["effective_risk_aversion"])
                    except Exception:
                        # Deterministic fallback to unadapted parameters
                        current_regime_state = 0
                        regime_probs_today = [1.0 / regime_num_states] * regime_num_states
                        effective_pr_today = max_participation_rate
                        effective_lambda_today = scheduling_risk_aversion

                # Causal volume profile construction for VWAP
                volume_profile_today = None
                if execution_scheduling_mode == "vwap" and volumes_df is not None and not volumes_df.empty:
                    try:
                        v_slice = volumes_df.iloc[t - estimation_window : t]
                        if isinstance(v_slice.index, pd.DatetimeIndex):
                            dow_means = v_slice.mean(axis=1).groupby(v_slice.index.dayofweek).mean()
                            target_dows = [pd.to_datetime(dates[min(T - 1, t + d)]).dayofweek for d in range(max_scheduling_days)]
                            vp = [float(dow_means.get(dow, 1.0)) for dow in target_dows]
                            if sum(vp) > 1e-12:
                                volume_profile_today = vp
                    except Exception:
                        volume_profile_today = None

                # Compute execution schedule
                if execution_scheduling_mode != "single_day":
                    sched_res = compute_multi_day_execution_schedule(
                        order_notionals=intended_notionals,
                        adv_dict=rebal_adv_dict,
                        volatility_dict=rebal_vol_dict,
                        max_participation_rate=max_participation_rate,
                        max_scheduling_days=max_scheduling_days,
                        scheduling_mode=execution_scheduling_mode,
                        scheduling_risk_aversion=scheduling_risk_aversion,
                        volume_profile=volume_profile_today,
                        default_adv=default_adv,
                        c_temp=c_temp,
                        regime_probs=regime_probs_today,
                        regime_adaptation_strength=regime_adaptation_strength if enable_regime_aware_execution else 0.0,
                        min_participation_rate=min_participation_rate,
                    )
                    scheduled_days = int(sched_res["horizon_days"])
                    today_tranche = sched_res["daily_schedules"][0]
                    effective_pr_today = sched_res.get("effective_participation_rate", effective_pr_today)
                    effective_lambda_today = sched_res.get("effective_risk_aversion", effective_lambda_today)
                    if scheduled_days > 1:
                        in_flight_queue = {
                            "remaining_tranches": sched_res["daily_schedules"][1:],
                            "scheduling_mode": execution_scheduling_mode,
                            "total_scheduled_days": scheduled_days,
                            "rebalance_index": total_rebalances + 1,
                            "effective_participation_rate": effective_pr_today,
                            "regime_state": current_regime_state,
                            "regime_p_turbulent": regime_probs_today[-1] if regime_probs_today else 0.0,
                            "current_tranche_index": 1,
                            "parent_order_notionals": {tk: abs(intended_notionals.get(tk, 0.0)) for tk in asset_names},
                            "order_ids": {tk: f"REBAL_{total_rebalances + 1}_{tk}" for tk in asset_names},
                        }
                    else:
                        in_flight_queue = None
                    eff_horizon = 1.0
                else:
                    scheduled_days = 1
                    today_tranche = intended_notionals
                    in_flight_queue = None
                    eff_horizon = execution_horizon_days

                exec_res = _execute_cash_financed_tranche(
                    tranche_notionals=today_tranche,
                    strat_drifted=strat_drifted,
                    strat_cash_drifted=strat_cash_drifted,
                    strat_equity=strat_equity,
                    asset_names=asset_names,
                    current_adv_dict=rebal_adv_dict,
                    rebal_vol_dict=rebal_vol_dict,
                    execution_horizon_days=eff_horizon,
                    max_participation_rate=effective_pr_today,
                    participation_policy=participation_policy,
                    execution_model=execution_model,
                    bid_ask_spread_bps=bid_ask_spread_bps,
                    transaction_cost_bps=transaction_cost_bps,
                    slippage_bps=slippage_bps,
                    c_temp=c_temp,
                    c_perm=c_perm,
                    default_adv=default_adv,
                    annualization_factor=annualization_factor,
                )

                rebal_rejected_today = exec_res["rebal_rejected_today"]
                if rebal_rejected_today:
                    target_w = strat_drifted.copy()
                    strat_cash = strat_cash_drifted
                    turnover_today = 0.0
                    cost_today = 0.0
                    spread_cost_today = 0.0
                    impact_cost_today = 0.0
                    commission_cost_today = 0.0
                    max_pr_today = exec_res["max_pr_today"]
                    part_warn_today = True
                    rebal_converged = False
                    solver_msg = "Rebalance rejected: trade notional exceeded volume participation limit."
                    in_flight_queue = None

                    # Emit zero-fill TradeFill records to record unexecuted notional & opportunity cost (DEF-42-05)
                    for i in range(N):
                        tk = asset_names[i]
                        intended_n = float(intended_notionals.get(tk, 0.0))
                        if abs(intended_n) > 1e-6:
                            dir_i = 1.0 if intended_n > 0 else -1.0
                            strat_trade_fills.append(TradeFill(
                                date=curr_date,
                                ticker=tk,
                                direction=dir_i,
                                requested_notional=abs(intended_n),
                                executed_notional=0.0,
                                arrival_price=100.0,
                                fill_price=100.0,
                                spread_cost=0.0,
                                temp_impact_cost=0.0,
                                perm_impact_cost=0.0,
                                commission_cost=0.0,
                                total_cost=0.0,
                                realized_asset_return=float(R_matrix[t, i]),
                                regime_state=current_regime_state,
                                regime_p_turbulent=regime_probs_today[-1] if regime_probs_today else 0.0,
                                scheduling_mode="rejected",
                                scheduled_horizon_days=1,
                                tranche_day_index=0,
                                parent_order_notional=abs(intended_n),
                                order_id=f"REJECTED_REBAL_{total_rebalances + 1}_{tk}",
                            ))
                else:
                    target_w = exec_res["target_w"]
                    strat_cash = exec_res["strat_cash"]
                    turnover_today = exec_res["turnover_today"]
                    cost_today = exec_res["cost_today"]
                    spread_cost_today = exec_res["spread_cost_today"]
                    impact_cost_today = exec_res["impact_cost_today"]
                    commission_cost_today = exec_res["commission_cost_today"]
                    max_pr_today = exec_res["max_pr_today"]
                    part_warn_today = exec_res["part_warn_today"]

                    impact_map = {a["ticker"]: a for a in exec_res.get("asset_impacts", [])}
                    for i in range(N):
                        tk = asset_names[i]
                        tranche_n = float(today_tranche.get(tk, 0.0))
                        if abs(tranche_n) > 1e-6:
                            exec_n = float(exec_res["exec_notionals"].get(tk, 0.0))
                            dir_i = 1.0 if tranche_n > 0 else -1.0
                            imp_info = impact_map.get(tk, {})
                            s_c = float(imp_info.get("spread_cost", 0.0))
                            t_c = float(imp_info.get("temporary_impact_cost", 0.0))
                            p_c = float(imp_info.get("permanent_impact_cost", 0.0))
                            cm_c = float(imp_info.get("commission_cost", 0.0))
                            tot_c = float(imp_info.get("total_cost", 0.0))
                            arr_p = 100.0
                            fill_p = arr_p * (1.0 + dir_i * (tot_c / exec_n)) if exec_n > 0 else arr_p
                            strat_trade_fills.append(TradeFill(
                                date=curr_date,
                                ticker=tk,
                                direction=dir_i,
                                requested_notional=abs(tranche_n),
                                executed_notional=exec_n,
                                arrival_price=arr_p,
                                fill_price=fill_p,
                                spread_cost=s_c,
                                temp_impact_cost=t_c,
                                perm_impact_cost=p_c,
                                commission_cost=cm_c,
                                total_cost=tot_c,
                                realized_asset_return=float(R_matrix[t, i]),
                                regime_state=current_regime_state,
                                regime_p_turbulent=regime_probs_today[-1] if regime_probs_today else 0.0,
                                scheduling_mode=execution_scheduling_mode if execution_scheduling_mode != "single_day" else "single_day",
                                scheduled_horizon_days=scheduled_days,
                                tranche_day_index=0,
                                parent_order_notional=abs(intended_notionals.get(tk, tranche_n)),
                                order_id=f"REBAL_{total_rebalances + 1}_{tk}",
                            ))

            # Deduct Strategy friction exactly once
            strat_equity = max(0.0, strat_equity - cost_today)
            strat_weights = target_w.copy()
            strat_drifted = target_w.copy()
            strat_cash_drifted = strat_cash
            strat_cash_history.append(strat_cash)

            strat_total_turnover += turnover_today
            strat_total_costs += cost_today
            strat_total_spread_costs += spread_cost_today
            strat_total_impact_costs += impact_cost_today
            strat_total_commission_costs += commission_cost_today
            strat_max_pr_observed = max(strat_max_pr_observed, max_pr_today)
            if part_warn_today:
                strat_participation_warnings += 1

            total_rebalances += 1
            days_since_rebalance = 0
            first_rebalance = False

            # Calculate Deterministic Liquidity-Adjusted VaR and CVaR
            liq_risk_res = compute_liquidity_adjusted_var_cvar(
                weights={asset_names[i]: float(target_w[i]) for i in range(N)},
                portfolio_equity=strat_equity,
                adv_dict=rebal_adv_dict,
                volatility_dict=rebal_vol_dict,
                market_var=rebal_var,
                market_cvar=rebal_cvar,
                spread_bps_dict={tk: bid_ask_spread_bps for tk in asset_names},
                execution_horizon_days=execution_horizon_days,
                impact_model=execution_model,
                c_temp=c_temp,
                c_perm=c_perm,
                fixed_bps_rate=slippage_bps,
                commission_bps=transaction_cost_bps,
            )
            l_var_today = float(liq_risk_res["l_var"])
            l_cvar_today = float(liq_risk_res["l_cvar"])
            liq_cost_pct_today = float(liq_risk_res["liquidation_cost"]) / strat_equity if strat_equity > 0 else 0.0
            strat_liquidation_costs_pct.append(liq_cost_pct_today)

            # Calculate Endogenous Stressed Liquidity Risk across joint return scenarios
            if enable_endogenous_liquidity and sim_rets is not None and len(sim_rets) > 0:
                endo_res = compute_scenario_endogenous_liquidity_risk(
                    weights={asset_names[i]: float(target_w[i]) for i in range(N)},
                    portfolio_equity=strat_equity,
                    adv_dict=rebal_adv_dict,
                    volatility_dict=rebal_vol_dict,
                    simulated_returns=sim_rets,
                    tickers=asset_names,
                    confidence_level=confidence_level,
                    spread_bps_dict={tk: bid_ask_spread_bps for tk in asset_names},
                    execution_horizon_days=execution_horizon_days,
                    impact_model=execution_model,
                    c_temp=c_temp,
                    c_perm=c_perm,
                    fixed_bps_rate=slippage_bps,
                    commission_bps=transaction_cost_bps,
                    spread_stress_sensitivity=spread_stress_sensitivity,
                    adv_stress_sensitivity=adv_stress_sensitivity,
                )
                stressed_l_var_today = float(endo_res["stressed_l_var"])
                stressed_l_cvar_today = float(endo_res["stressed_l_cvar"])
            else:
                stressed_l_var_today = l_var_today
                stressed_l_cvar_today = l_cvar_today

            strat_stressed_l_var_list.append(stressed_l_var_today)
            strat_stressed_l_cvar_list.append(stressed_l_cvar_today)
            strat_stress_uplift_var_list.append(max(0.0, stressed_l_var_today - l_var_today))
            strat_stress_uplift_cvar_list.append(max(0.0, stressed_l_cvar_today - l_cvar_today))

            # 4. Rebalance Benchmark (Equal-Weight) with friction
            bench_to = float(0.5 * np.sum(np.abs(ew_weights - bench_drifted)))
            if execution_model == "fixed_bps":
                bench_cost = 2.0 * bench_to * bench_equity * total_friction_rate
                bench_spread = 0.0
                bench_impact_c = 2.0 * bench_to * bench_equity * (slippage_bps / 10000.0)
                bench_comm = 2.0 * bench_to * bench_equity * (transaction_cost_bps / 10000.0)
            else:
                bench_traded = {
                    asset_names[i]: abs(ew_weights[i] - bench_drifted[i]) * bench_equity
                    for i in range(N)
                }
                b_impact = compute_rebalance_market_impact(
                    traded_notionals=bench_traded,
                    adv_dict=rebal_adv_dict,
                    volatility_dict=rebal_vol_dict,
                    spread_bps_dict={tk: bid_ask_spread_bps for tk in asset_names},
                    execution_horizon_days=execution_horizon_days,
                    impact_model=execution_model,
                    c_temp=c_temp,
                    c_perm=c_perm,
                    commission_bps=transaction_cost_bps,
                    max_participation_rate=max_participation_rate,
                    participation_policy="warn",
                )
                bench_cost = float(b_impact["summary"]["total_impact_cost"])
                bench_spread = float(b_impact["summary"]["total_spread_cost"])
                bench_impact_c = float(b_impact["summary"]["total_market_impact_cost"])
                bench_comm = float(b_impact["summary"]["total_commission_cost"])
                bench_max_pr_observed = max(bench_max_pr_observed, float(b_impact["summary"]["max_participation_rate_observed"]))
                if b_impact["summary"]["participation_warnings_count"] > 0:
                    bench_participation_warnings += 1

            bench_equity = max(0.0, bench_equity - bench_cost)
            bench_drifted = ew_weights.copy()
            bench_total_turnover += bench_to
            bench_total_costs += bench_cost
            bench_total_spread_costs += bench_spread
            bench_total_impact_costs += bench_impact_c
            bench_total_commission_costs += bench_comm

            # 5. Record Rebalance Audit Log
            rebalance_history.append({
                "rebalance_index": total_rebalances,
                "date": curr_date,
                "training_window_start": training_start,
                "training_window_end": training_end,
                "requested_weights": {asset_names[i]: round(float(requested_target_w[i]), 4) for i in range(N)},
                "executed_weights": {asset_names[i]: round(float(target_w[i]), 4) for i in range(N)},
                "weights": {asset_names[i]: round(float(target_w[i]), 4) for i in range(N)},
                "turnover": round(turnover_today, 4),
                "transaction_cost": round(cost_today, 2),
                "spread_cost": round(spread_cost_today, 2),
                "market_impact_cost": round(impact_cost_today, 2),
                "commission_cost": round(commission_cost_today, 2),
                "portfolio_cvar": round(rebal_cvar, 4),
                "portfolio_var": round(rebal_var, 4),
                "liquidity_adjusted_cvar": round(l_cvar_today, 4),
                "liquidity_adjusted_var": round(l_var_today, 4),
                "stressed_liquidity_adjusted_cvar": round(stressed_l_cvar_today, 4),
                "stressed_liquidity_adjusted_var": round(stressed_l_var_today, 4),
                "liquidation_cost_pct": round(liq_cost_pct_today, 4),
                "cash_weight": round(strat_cash, 4),
                "max_participation_rate": round(max_pr_today, 4),
                "participation_warning": part_warn_today,
                "rebalance_rejected": rebal_rejected_today,
                "adv_source": rebal_adv_source,
                "tail_risk_contributions": trcs,
                "converged": rebal_converged,
                "solver_message": solver_msg,
                "scheduled_days": scheduled_days,
                "scheduling_mode": execution_scheduling_mode if execution_scheduling_mode != "single_day" else "single_day",
                "regime_state": current_regime_state,
                "regime_probabilities": [round(float(p), 4) for p in regime_probs_today] if regime_probs_today is not None else None,
                "effective_participation_rate": round(float(effective_pr_today), 4),
                "effective_risk_aversion": round(float(effective_lambda_today), 6),
                "regime_adaptation_strength": regime_adaptation_strength if enable_regime_aware_execution else 0.0,
            })
        else:
            days_since_rebalance += 1
            if in_flight_queue is not None and len(in_flight_queue["remaining_tranches"]) > 0:
                today_tranche = in_flight_queue["remaining_tranches"].pop(0)
                queue_pr = in_flight_queue.get("effective_participation_rate", max_participation_rate)
                queue_regime_state = in_flight_queue.get("regime_state")
                queue_p_turbulent = in_flight_queue.get("regime_p_turbulent", 0.0)
                queue_mode = in_flight_queue.get("scheduling_mode", "single_day")
                queue_horizon = in_flight_queue.get("total_scheduled_days", 1)
                tranche_idx = in_flight_queue.get("current_tranche_index", 1)
                queue_parent_notionals = in_flight_queue.get("parent_order_notionals", {})
                queue_order_ids = in_flight_queue.get("order_ids", {})
                in_flight_queue["current_tranche_index"] = tranche_idx + 1
                if len(in_flight_queue["remaining_tranches"]) == 0:
                    in_flight_queue = None

                pt_slice_today = R_matrix[t - estimation_window : t, :]
                interim_vol_dict = {
                    asset_names[i]: max(0.001, float(np.std(pt_slice_today[:, i], ddof=1)) * math.sqrt(annualization_factor))
                    for i in range(N)
                }
                exec_res = _execute_cash_financed_tranche(
                    tranche_notionals=today_tranche,
                    strat_drifted=strat_drifted,
                    strat_cash_drifted=strat_cash_drifted,
                    strat_equity=strat_equity,
                    asset_names=asset_names,
                    current_adv_dict=current_adv_dict,
                    rebal_vol_dict=interim_vol_dict,
                    execution_horizon_days=1.0,
                    max_participation_rate=queue_pr,
                    participation_policy=participation_policy,
                    execution_model=execution_model,
                    bid_ask_spread_bps=bid_ask_spread_bps,
                    transaction_cost_bps=transaction_cost_bps,
                    slippage_bps=slippage_bps,
                    c_temp=c_temp,
                    c_perm=c_perm,
                    default_adv=default_adv,
                    annualization_factor=annualization_factor,
                )
                cost_today = exec_res["cost_today"]
                turnover_today = exec_res["turnover_today"]
                spread_cost_today = exec_res["spread_cost_today"]
                impact_cost_today = exec_res["impact_cost_today"]
                commission_cost_today = exec_res["commission_cost_today"]
                max_pr_today = exec_res["max_pr_today"]
                part_warn_today = exec_res["part_warn_today"]

                impact_map = {a["ticker"]: a for a in exec_res.get("asset_impacts", [])}
                for i in range(N):
                    tk = asset_names[i]
                    tranche_n = float(today_tranche.get(tk, 0.0))
                    if abs(tranche_n) > 1e-6:
                        exec_n = float(exec_res["exec_notionals"].get(tk, 0.0))
                        dir_i = 1.0 if tranche_n > 0 else -1.0
                        imp_info = impact_map.get(tk, {})
                        s_c = float(imp_info.get("spread_cost", 0.0))
                        t_c = float(imp_info.get("temporary_impact_cost", 0.0))
                        p_c = float(imp_info.get("permanent_impact_cost", 0.0))
                        cm_c = float(imp_info.get("commission_cost", 0.0))
                        tot_c = float(imp_info.get("total_cost", 0.0))
                        arr_p = 100.0
                        fill_p = arr_p * (1.0 + dir_i * (tot_c / exec_n)) if exec_n > 0 else arr_p
                        strat_trade_fills.append(TradeFill(
                            date=curr_date,
                            ticker=tk,
                            direction=dir_i,
                            requested_notional=abs(tranche_n),
                            executed_notional=exec_n,
                            arrival_price=arr_p,
                            fill_price=fill_p,
                            spread_cost=s_c,
                            temp_impact_cost=t_c,
                            perm_impact_cost=p_c,
                            commission_cost=cm_c,
                            total_cost=tot_c,
                            realized_asset_return=float(R_matrix[t, i]),
                            regime_state=queue_regime_state,
                            regime_p_turbulent=queue_p_turbulent,
                            scheduling_mode=queue_mode,
                            scheduled_horizon_days=queue_horizon,
                            tranche_day_index=tranche_idx,
                            parent_order_notional=abs(queue_parent_notionals.get(tk, tranche_n)),
                            order_id=queue_order_ids.get(tk, f"REBAL_{total_rebalances}_{tk}"),
                        ))

                strat_equity = max(0.0, strat_equity - cost_today)
                strat_drifted = exec_res["target_w"].copy()
                strat_cash_drifted = exec_res["strat_cash"]

                strat_total_turnover += turnover_today
                strat_total_costs += cost_today
                strat_total_spread_costs += spread_cost_today
                strat_total_impact_costs += impact_cost_today
                strat_total_commission_costs += commission_cost_today
                strat_max_pr_observed = max(strat_max_pr_observed, max_pr_today)
                if part_warn_today:
                    strat_participation_warnings += 1

        # Realize Day t Returns from historical market observations
        r_today = R_matrix[t, :]
        r_cash_today = float(risk_free_rate / annualization_factor)
        strat_gross_ret = float(np.dot(strat_drifted, r_today) + strat_cash_drifted * r_cash_today)
        bench_ret = float(np.dot(bench_drifted, r_today))
        static_ret = float(np.dot(static_drifted, r_today))

        # Point-in-time ADV, volatility and spread for day t liquidation loss (DEF-35-02)
        pt_slice = R_matrix[t - estimation_window : t, :]
        pt_vols = np.maximum(0.001, np.std(pt_slice, axis=0, ddof=1) * math.sqrt(annualization_factor))
        pt_advs = np.array([current_adv_dict.get(tk, default_adv) for tk in asset_names], dtype=np.float64)
        pt_spreads = np.array([bid_ask_spread_bps for _ in asset_names], dtype=np.float64)

        loss_det_t, loss_str_t, c_liq_det_t, c_liq_str_t = compute_daily_liquidation_loss(
            held_weights=strat_drifted,
            portfolio_equity=strat_equity,
            adv_arr=pt_advs,
            vol_arr=pt_vols,
            base_spreads_bps=pt_spreads,
            r_today=r_today,
            portfolio_gross_ret=strat_gross_ret,
            execution_horizon_days=execution_horizon_days,
            impact_model=execution_model,
            c_temp=c_temp,
            c_perm=c_perm,
            fixed_bps_rate=slippage_bps,
            commission_bps=transaction_cost_bps,
            spread_stress_sensitivity=spread_stress_sensitivity,
            adv_stress_sensitivity=adv_stress_sensitivity,
            enable_endogenous_liquidity=enable_endogenous_liquidity,
        )
        strat_daily_losses_det.append(loss_det_t)
        strat_daily_losses_stressed.append(loss_str_t)
        strat_daily_liq_costs_pct.append(c_liq_det_t)

        # Advance equities
        strat_equity *= (1.0 + strat_gross_ret)
        bench_equity *= (1.0 + bench_ret)
        static_equity *= (1.0 + static_ret)

        strat_daily_rets.append(strat_gross_ret)
        bench_daily_rets.append(bench_ret)
        static_daily_rets.append(static_ret)

        strat_equity_series.append(strat_equity)
        bench_equity_series.append(bench_equity)
        static_equity_series.append(static_equity)

        # Update weight drift for next day (t + 1)
        strat_denom = 1.0 + strat_gross_ret
        if strat_denom > 1e-12:
            strat_drifted = (strat_drifted * (1.0 + r_today)) / strat_denom
            strat_cash_drifted = (strat_cash_drifted * (1.0 + r_cash_today)) / strat_denom
        else:
            strat_drifted = ew_weights.copy()
            strat_cash_drifted = 0.0

        bench_denom = 1.0 + bench_ret
        if bench_denom > 1e-12:
            bench_drifted = (bench_drifted * (1.0 + r_today)) / bench_denom
        else:
            bench_drifted = ew_weights.copy()

        static_denom = 1.0 + static_ret
        if static_denom > 1e-12:
            static_drifted = (static_drifted * (1.0 + r_today)) / static_denom
        else:
            static_drifted = ew_weights.copy()

        # Update Strategy Drawdown
        if strat_equity > strat_peak:
            strat_peak = strat_equity
        strat_dd = (strat_equity - strat_peak) / strat_peak if strat_peak > 0 else 0.0

        equity_curve.append({
            "date": curr_date,
            "strategy_equity": round(float(strat_equity), 2),
            "benchmark_equity": round(float(bench_equity), 2),
            "static_trp_equity": round(float(static_equity), 2),
            "drawdown": round(float(strat_dd), 4),
        })

    # Record any unexecuted tranches remaining in queue at simulation horizon (DEF-42-02)
    if in_flight_queue is not None and len(in_flight_queue.get("remaining_tranches", [])) > 0:
        for rem_tranche in in_flight_queue["remaining_tranches"]:
            for tk, tranche_n in rem_tranche.items():
                if abs(tranche_n) > 1e-6:
                    dir_i = 1.0 if tranche_n > 0 else -1.0
                    strat_trade_fills.append(TradeFill(
                        date=dates[-1],
                        ticker=tk,
                        direction=dir_i,
                        requested_notional=abs(tranche_n),
                        executed_notional=0.0,
                        arrival_price=100.0,
                        fill_price=100.0,
                        spread_cost=0.0,
                        temp_impact_cost=0.0,
                        perm_impact_cost=0.0,
                        commission_cost=0.0,
                        total_cost=0.0,
                        realized_asset_return=0.0,
                        regime_state=in_flight_queue.get("regime_state"),
                        regime_p_turbulent=in_flight_queue.get("regime_p_turbulent", 0.0),
                        scheduling_mode="expired",
                        scheduled_horizon_days=in_flight_queue.get("total_scheduled_days", 1),
                        tranche_day_index=in_flight_queue.get("current_tranche_index", 0),
                        parent_order_notional=abs(in_flight_queue.get("parent_order_notionals", {}).get(tk, tranche_n)),
                        order_id=in_flight_queue.get("order_ids", {}).get(tk, f"EXPIRED_{tk}"),
                    ))
        in_flight_queue = None

    # Summary Performance Analytics
    avg_strat_liq_pct = float(np.mean(strat_liquidation_costs_pct)) if strat_liquidation_costs_pct else 0.0
    avg_stress_var_uplift = float(np.mean(strat_stress_uplift_var_list)) if strat_stress_uplift_var_list else 0.0
    avg_stress_cvar_uplift = float(np.mean(strat_stress_uplift_cvar_list)) if strat_stress_uplift_cvar_list else 0.0
    avg_cash_weight = float(np.mean(strat_cash_history)) if strat_cash_history else 0.0

    strategy_metrics = _compute_strategy_kpis(
        daily_returns=strat_daily_rets,
        equity_values=strat_equity_series,
        initial_capital=initial_capital,
        total_turnover=strat_total_turnover,
        total_costs=strat_total_costs,
        risk_free_rate=risk_free_rate,
        annualization_factor=annualization_factor,
        total_spread_costs=strat_total_spread_costs,
        total_market_impact_costs=strat_total_impact_costs,
        total_commission_costs=strat_total_commission_costs,
        max_participation_rate_observed=strat_max_pr_observed,
        participation_warnings_count=strat_participation_warnings,
        average_liquidation_cost_pct=avg_strat_liq_pct,
        average_cash_weight=avg_cash_weight,
        stress_var_uplift=avg_stress_var_uplift,
        stress_cvar_uplift=avg_stress_cvar_uplift,
        daily_losses_det=strat_daily_losses_det,
        daily_losses_stressed=strat_daily_losses_stressed,
    )

    benchmark_metrics = _compute_strategy_kpis(
        daily_returns=bench_daily_rets,
        equity_values=bench_equity_series,
        initial_capital=initial_capital,
        total_turnover=bench_total_turnover,
        total_costs=bench_total_costs,
        risk_free_rate=risk_free_rate,
        annualization_factor=annualization_factor,
        total_spread_costs=bench_total_spread_costs,
        total_market_impact_costs=bench_total_impact_costs,
        total_commission_costs=bench_total_commission_costs,
        max_participation_rate_observed=bench_max_pr_observed,
        participation_warnings_count=bench_participation_warnings,
    )

    static_trp_metrics = _compute_strategy_kpis(
        daily_returns=static_daily_rets,
        equity_values=static_equity_series,
        initial_capital=initial_capital,
        total_turnover=0.0,
        total_costs=static_total_costs,
        risk_free_rate=risk_free_rate,
        annualization_factor=annualization_factor,
        total_spread_costs=0.0,
        total_market_impact_costs=static_total_costs,
        total_commission_costs=0.0,
        max_participation_rate_observed=0.0,
        participation_warnings_count=0,
    )

    tca_report = compute_transaction_cost_analysis(
        fills=strat_trade_fills,
        initial_capital=initial_capital,
        annualization_factor=annualization_factor,
    )

    return {
        "vine_type": vine_type,
        "estimation_window": estimation_window,
        "rebalance_frequency": rebalance_frequency,
        "confidence_level": confidence_level,
        "num_simulations": num_simulations,
        "marginal_method": marginal_method,
        "evaluation_start_date": dates[estimation_window],
        "evaluation_end_date": dates[-1],
        "total_evaluation_days": len(strat_daily_rets),
        "total_rebalances": total_rebalances,
        "fallback_rebalances": fallback_rebalances,
        "execution_model": execution_model,
        "bid_ask_spread_bps": bid_ask_spread_bps,
        "max_participation_rate": max_participation_rate,
        "participation_policy": participation_policy,
        "enable_endogenous_liquidity": enable_endogenous_liquidity,
        "spread_stress_sensitivity": spread_stress_sensitivity,
        "adv_stress_sensitivity": adv_stress_sensitivity,
        "adv_source": overall_adv_source,
        "execution_scheduling_mode": execution_scheduling_mode,
        "max_scheduling_days": max_scheduling_days,
        "scheduling_risk_aversion": scheduling_risk_aversion,
        "enable_regime_aware_execution": enable_regime_aware_execution,
        "regime_num_states": regime_num_states,
        "regime_adaptation_strength": regime_adaptation_strength,
        "min_participation_rate": min_participation_rate,
        "strategy_metrics": strategy_metrics,
        "benchmark_metrics": benchmark_metrics,
        "static_trp_metrics": static_trp_metrics,
        "equity_curve": equity_curve,
        "rebalance_history": rebalance_history,
        "daily_liquidation_losses_det": [round(float(x), 6) for x in strat_daily_losses_det],
        "daily_liquidation_losses_stressed": [round(float(x), 6) for x in strat_daily_losses_stressed],
        "tca_report": tca_report,
    }

