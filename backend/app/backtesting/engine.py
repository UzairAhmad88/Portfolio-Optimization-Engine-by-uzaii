"""
Core quantitative backtesting simulation engine.

Executes reproducible historical simulations with explicit accounting for:
- Wealth compounding (discrete simple returns).
- Asset weight drift between rebalance dates.
- Scheduled rebalancing (buy-and-hold, daily, weekly, monthly, quarterly).
- Transaction costs (basis-point commissions on traded notional).
- Slippage friction (basis-point price impact on traded notional).
- Chronological walk-forward optimization with zero look-ahead bias.

Independent of web frameworks or external I/O.
"""

from __future__ import annotations

from typing import Any, Literal
import numpy as np
import pandas as pd

from app.backtesting.costs import (
    calculate_slippage_cost,
    calculate_traded_notional,
    calculate_transaction_cost,
    calculate_turnover,
)
from app.backtesting.metrics import compute_backtest_metrics
from app.backtesting.models import (
    BacktestResponse,
    BacktestSummaryMetrics,
    EquityPoint,
    OptimizationObjective,
    RebalanceEvent,
    RebalanceFrequency,
    StrategyType,
)
from app.quant.constraints import InvestmentConstraints
from app.quant.covariance import covariance_matrix
from app.quant.optimization import (
    OptimizationError,
    optimize_maximum_sharpe,
    optimize_minimum_variance,
)
from app.quant.returns import simple_returns


def _is_rebalance_due(
    frequency: RebalanceFrequency,
    current_date_str: str,
    prev_date_str: str,
    days_since_rebalance: int,
) -> bool:
    """
    Determines if a scheduled rebalance event is triggered on the current date.
    Uses calendar boundary transitions to align with institutional accounting conventions.
    """
    if frequency == "buy_and_hold":
        return False
    if frequency == "daily":
        return True
    if frequency == "weekly":
        # Check if week has changed (using ISO week or 5-day cycle)
        curr_dt = pd.to_datetime(current_date_str)
        prev_dt = pd.to_datetime(prev_date_str)
        return curr_dt.isocalendar().week != prev_dt.isocalendar().week
    if frequency == "monthly":
        # Check if calendar month (YYYY-MM) changed
        return current_date_str[:7] != prev_date_str[:7]
    if frequency == "quarterly":
        # Check if calendar quarter changed
        curr_m = int(current_date_str[5:7])
        prev_m = int(prev_date_str[5:7])
        curr_q = (curr_m - 1) // 3
        prev_q = (prev_m - 1) // 3
        return curr_q != prev_q
    return False


def _solve_walk_forward_weights(
    train_prices: pd.DataFrame,
    assets: list[str],
    objective: OptimizationObjective,
    risk_free_rate: float,
    periods_per_year: int,
) -> dict[str, float]:
    """
    Optimizes portfolio weights strictly using in-sample training window prices.
    Enforces that zero future observations leak into the estimation.
    """
    n_assets = len(assets)
    equal_w = {a: 1.0 / n_assets for a in assets}

    if len(train_prices) < 5 or n_assets < 2:
        return equal_w

    try:
        ret_df = simple_returns(train_prices).dropna(how="any").astype(float)
        if len(ret_df) < 5:
            return equal_w

        exp_rets = ret_df.mean() * periods_per_year
        cov_df = covariance_matrix(ret_df, method="ledoit_wolf", annualized=True, periods_per_year=periods_per_year)

        constraints = InvestmentConstraints(
            allow_short=False,
            default_min_weight=0.0,
            default_max_weight=1.0,
        )

        if objective == "max_sharpe":
            try:
                opt_res = optimize_maximum_sharpe(
                    assets=assets,
                    expected_returns=exp_rets,
                    cov_matrix=cov_df,
                    constraints=constraints,
                    risk_free_rate=risk_free_rate,
                    annualized=True,
                    periods_per_year=periods_per_year,
                )
                if opt_res.converged and opt_res.is_feasible:
                    return {a: float(opt_res.weights.get(a, 0.0)) for a in assets}
            except Exception:
                pass  # Fall back to min_variance

        # Minimum variance fallback
        opt_res = optimize_minimum_variance(
            assets=assets,
            expected_returns=exp_rets,
            cov_matrix=cov_df,
            constraints=constraints,
            annualized=True,
            periods_per_year=periods_per_year,
        )
        if opt_res.converged and opt_res.is_feasible:
            return {a: float(opt_res.weights.get(a, 0.0)) for a in assets}

    except Exception:
        pass

    return equal_w


def run_portfolio_simulation(
    prices: pd.DataFrame,
    strategy_type: StrategyType = "target_weights",
    target_weights: dict[str, float] | None = None,
    rebalance_frequency: RebalanceFrequency = "monthly",
    initial_capital: float = 100_000.0,
    transaction_cost_bps: float = 10.0,
    slippage_bps: float = 5.0,
    training_window: int = 126,
    test_window: int = 21,
    optimization_objective: OptimizationObjective = "max_sharpe",
    periods_per_year: int = 252,
    risk_free_rate: float = 0.02,
) -> tuple[BacktestSummaryMetrics, list[EquityPoint], list[RebalanceEvent]]:
    """
    Executes a pure numerical historical backtest simulation.

    Returns:
        tuple of (BacktestSummaryMetrics, list[EquityPoint], list[RebalanceEvent]).
    """
    all_dates = list(prices.index)
    assets = list(prices.columns)
    n_assets = len(assets)

    if n_assets == 0 or len(all_dates) < 2:
        raise ValueError("Prices panel must contain at least 1 asset and 2 trading days.")

    # 1. Determine simulation start index
    if strategy_type == "walk_forward_optimization":
        if len(all_dates) <= training_window + 1:
            raise ValueError(
                f"Walk-forward optimization requires at least {training_window + 2} observations "
                f"(received {len(all_dates)})."
            )
        start_idx = training_window
    else:
        start_idx = 0

    sim_dates = all_dates[start_idx:]
    n_sim_days = len(sim_dates)

    # 2. Inception Allocation on day 0 of simulation (sim_dates[0])
    date_0 = sim_dates[0]
    if strategy_type == "walk_forward_optimization":
        train_slice = prices.iloc[0:start_idx]
        current_target_w = _solve_walk_forward_weights(
            train_prices=train_slice,
            assets=assets,
            objective=optimization_objective,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
        )
    elif strategy_type == "equal_weight":
        current_target_w = {a: 1.0 / n_assets for a in assets}
    else:
        current_target_w = {}
        for a in assets:
            if target_weights:
                w_val = target_weights.get(a, target_weights.get(a.split(":")[0], 0.0))
                current_target_w[a] = float(w_val)
            else:
                current_target_w[a] = 1.0 / n_assets


    # Inception transaction costs
    v_gross = float(initial_capital)
    v_net = float(initial_capital)

    init_traded_notional = v_net
    init_trans_cost = calculate_transaction_cost(init_traded_notional, transaction_cost_bps)
    init_slip_cost = calculate_slippage_cost(init_traded_notional, slippage_bps)
    init_total_friction = init_trans_cost + init_slip_cost

    v_net -= init_total_friction

    rebalance_events: list[RebalanceEvent] = [
        RebalanceEvent(
            date=date_0,
            reason="Initial Allocation",
            turnover=1.0,
            traded_notional=init_traded_notional,
            transaction_cost=init_trans_cost,
            slippage_cost=init_slip_cost,
            portfolio_value_before=initial_capital,
            portfolio_value_after=v_net,
            pre_weights={a: 0.0 for a in assets},
            post_weights=dict(current_target_w),
        )
    ]

    total_turnover = 1.0
    total_trans_costs = init_trans_cost
    total_slip_costs = init_slip_cost
    num_rebalances = 1

    # Establish initial asset holdings
    holdings_gross = {a: v_gross * current_target_w[a] for a in assets}
    holdings_net = {a: v_net * current_target_w[a] for a in assets}

    equity_curve: list[EquityPoint] = [
        EquityPoint(
            date=date_0,
            portfolio_value_net=v_net,
            portfolio_value_gross=v_gross,
            return_net=0.0,
            return_gross=0.0,
            drawdown_net=0.0,
            drawdown_gross=0.0,
        )
    ]

    daily_rets_net: list[float] = []
    daily_rets_gross: list[float] = []

    peak_gross = v_gross
    peak_net = v_net

    days_since_rebalance = 0

    # 3. Step forward through historical trading days
    for step_i in range(1, n_sim_days):
        d_prev = sim_dates[step_i - 1]
        d_curr = sim_dates[step_i]

        p_prev = prices.loc[d_prev]
        p_curr = prices.loc[d_curr]

        # Asset returns
        asset_rets = {a: (float(p_curr[a]) / float(p_prev[a])) - 1.0 for a in assets}

        # Value before rebalancing on d_curr
        v_gross_prev = v_gross
        v_net_prev = v_net

        holdings_gross = {a: holdings_gross[a] * (1.0 + asset_rets[a]) for a in assets}
        v_gross = sum(holdings_gross.values())

        holdings_net = {a: holdings_net[a] * (1.0 + asset_rets[a]) for a in assets}
        v_net_pre = sum(holdings_net.values())

        # Drifted weights before rebalance
        if v_net_pre > 0.0:
            drifted_weights = {a: holdings_net[a] / v_net_pre for a in assets}
        else:
            drifted_weights = {a: 0.0 for a in assets}

        days_since_rebalance += 1

        # Check if rebalance is triggered on d_curr
        is_reb = _is_rebalance_due(rebalance_frequency, d_curr, d_prev, days_since_rebalance)

        if strategy_type == "walk_forward_optimization":
            # For walk-forward, rebalance can also be driven by test_window
            if days_since_rebalance >= test_window:
                is_reb = True

        v_net_post = v_net_pre

        if is_reb:
            # Determine new target weights
            if strategy_type == "walk_forward_optimization":
                # Lookback window ends strictly at d_curr index in prices
                curr_loc = prices.index.get_loc(d_curr)
                train_slice = prices.iloc[max(0, curr_loc - training_window) : curr_loc]
                new_target_w = _solve_walk_forward_weights(
                    train_prices=train_slice,
                    assets=assets,
                    objective=optimization_objective,
                    risk_free_rate=risk_free_rate,
                    periods_per_year=periods_per_year,
                )
            elif strategy_type == "equal_weight":
                new_target_w = {a: 1.0 / n_assets for a in assets}
            else:
                new_target_w = dict(current_target_w)

            # Calculate turnover and friction
            reb_turnover = calculate_turnover(drifted_weights, new_target_w)
            traded_notional = calculate_traded_notional(drifted_weights, new_target_w, v_net_pre)
            trans_cost = calculate_transaction_cost(traded_notional, transaction_cost_bps)
            slip_cost = calculate_slippage_cost(traded_notional, slippage_bps)
            friction = trans_cost + slip_cost

            # Only execute if turnover exceeds numerical noise
            if reb_turnover > 1e-5:
                v_net_post = v_net_pre - friction
                holdings_net = {a: v_net_post * new_target_w[a] for a in assets}
                holdings_gross = {a: v_gross * new_target_w[a] for a in assets}
                current_target_w = new_target_w

                total_turnover += reb_turnover
                total_trans_costs += trans_cost
                total_slip_costs += slip_cost
                num_rebalances += 1
                days_since_rebalance = 0

                rebalance_events.append(
                    RebalanceEvent(
                        date=d_curr,
                        reason=f"Scheduled {rebalance_frequency.capitalize()} Rebalance",
                        turnover=reb_turnover,
                        traded_notional=traded_notional,
                        transaction_cost=trans_cost,
                        slippage_cost=slip_cost,
                        portfolio_value_before=v_net_pre,
                        portfolio_value_after=v_net_post,
                        pre_weights=drifted_weights,
                        post_weights=dict(new_target_w),
                    )
                )

        v_net = v_net_post

        # Portfolio simple returns for day step_i
        ret_gross = (v_gross - v_gross_prev) / v_gross_prev if v_gross_prev > 0 else 0.0
        ret_net = (v_net - v_net_prev) / v_net_prev if v_net_prev > 0 else 0.0

        daily_rets_gross.append(ret_gross)
        daily_rets_net.append(ret_net)

        # Drawdowns
        if v_gross > peak_gross:
            peak_gross = v_gross
        dd_gross = (v_gross - peak_gross) / peak_gross if peak_gross > 0 else 0.0

        if v_net > peak_net:
            peak_net = v_net
        dd_net = (v_net - peak_net) / peak_net if peak_net > 0 else 0.0

        equity_curve.append(
            EquityPoint(
                date=d_curr,
                portfolio_value_net=v_net,
                portfolio_value_gross=v_gross,
                return_net=ret_net,
                return_gross=ret_gross,
                drawdown_net=dd_net,
                drawdown_gross=dd_gross,
            )
        )

    # 4. Compute performance and risk summary
    series_net = pd.Series(daily_rets_net, index=sim_dates[1:])
    series_gross = pd.Series(daily_rets_gross, index=sim_dates[1:])
    equity_net_vals = [pt.portfolio_value_net for pt in equity_curve]
    equity_gross_vals = [pt.portfolio_value_gross for pt in equity_curve]

    metrics = compute_backtest_metrics(
        daily_returns_net=series_net,
        daily_returns_gross=series_gross,
        equity_net=equity_net_vals,
        equity_gross=equity_gross_vals,
        initial_capital=initial_capital,
        dates=sim_dates,
        periods_per_year=periods_per_year,
        risk_free_rate=risk_free_rate,
        total_turnover=total_turnover,
        total_transaction_costs=total_trans_costs,
        total_slippage_costs=total_slip_costs,
        number_of_rebalances=num_rebalances,
    )

    return metrics, equity_curve, rebalance_events
