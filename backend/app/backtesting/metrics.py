"""
Performance and risk analytics calculation module for portfolio backtesting.
Reuses tested pure mathematics functions from app.quant.risk.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd

from app.backtesting.models import BacktestSummaryMetrics
from app.quant.risk import (
    annualized_volatility,
    maximum_drawdown,
    sharpe_ratio,
    sortino_ratio,
)


def compute_backtest_metrics(
    daily_returns_net: pd.Series,
    daily_returns_gross: pd.Series,
    equity_net: list[float],
    equity_gross: list[float],
    initial_capital: float,
    dates: list[str],
    periods_per_year: int = 252,
    risk_free_rate: float = 0.02,
    total_turnover: float = 0.0,
    total_transaction_costs: float = 0.0,
    total_slippage_costs: float = 0.0,
    number_of_rebalances: int = 0,
) -> BacktestSummaryMetrics:
    """
    Computes summary performance and risk metrics for a completed backtest run.
    Distinguishes net metrics (post-frictions) from gross metrics (pre-frictions).
    """
    n_obs = len(dates)
    effective_start = dates[0] if dates else ""
    effective_end = dates[-1] if dates else ""

    final_val_net = float(equity_net[-1]) if equity_net else initial_capital
    final_val_gross = float(equity_gross[-1]) if equity_gross else initial_capital

    cum_ret_net = float(final_val_net / initial_capital - 1.0)
    cum_ret_gross = float(final_val_gross / initial_capital - 1.0)

    # Compound Annual Growth Rate (CAGR)
    # T = number of trading days. If T > 0, CAGR = (V_final / V_initial) ** (periods_per_year / T) - 1
    if n_obs > 1 and final_val_net > 0.0:
        years = float(n_obs) / float(periods_per_year)
        cagr_net = float((final_val_net / initial_capital) ** (1.0 / years) - 1.0)
    else:
        cagr_net = cum_ret_net

    if n_obs > 1 and final_val_gross > 0.0:
        years = float(n_obs) / float(periods_per_year)
        cagr_gross = float((final_val_gross / initial_capital) ** (1.0 / years) - 1.0)
    else:
        cagr_gross = cum_ret_gross

    # Arithmetic Annualized Return
    mean_ret_net = float(daily_returns_net.mean()) if not daily_returns_net.empty else 0.0
    mean_ret_gross = float(daily_returns_gross.mean()) if not daily_returns_gross.empty else 0.0
    ann_ret_net = float(mean_ret_net * periods_per_year)
    ann_ret_gross = float(mean_ret_gross * periods_per_year)

    # Annualized Volatility
    if len(daily_returns_net) >= 2:
        vol_ann_net = float(
            annualized_volatility(daily_returns_net, periods_per_year=periods_per_year, ddof=1)
        )
    else:
        vol_ann_net = 0.0

    if len(daily_returns_gross) >= 2:
        vol_ann_gross = float(
            annualized_volatility(daily_returns_gross, periods_per_year=periods_per_year, ddof=1)
        )
    else:
        vol_ann_gross = 0.0

    # Sharpe Ratio
    sharpe_net: float | None = None
    sharpe_gross: float | None = None
    if len(daily_returns_net) >= 2:
        try:
            sharpe_net = sharpe_ratio(
                daily_returns_net,
                risk_free_rate=risk_free_rate,
                annualized=True,
                periods_per_year=periods_per_year,
                ddof=1,
            )
        except ValueError:
            sharpe_net = None

    if len(daily_returns_gross) >= 2:
        try:
            sharpe_gross = sharpe_ratio(
                daily_returns_gross,
                risk_free_rate=risk_free_rate,
                annualized=True,
                periods_per_year=periods_per_year,
                ddof=1,
            )
        except ValueError:
            sharpe_gross = None

    # Sortino Ratio
    sortino_net: float | None = None
    sortino_gross: float | None = None
    if len(daily_returns_net) >= 2:
        try:
            sortino_net = sortino_ratio(
                daily_returns_net,
                required_return=0.0,
                annualized=True,
                periods_per_year=periods_per_year,
                ddof=0,
            )
        except ValueError:
            sortino_net = None

    if len(daily_returns_gross) >= 2:
        try:
            sortino_gross = sortino_ratio(
                daily_returns_gross,
                required_return=0.0,
                annualized=True,
                periods_per_year=periods_per_year,
                ddof=0,
            )
        except ValueError:
            sortino_gross = None

    # Maximum Drawdown from Net/Gross Wealth Curves
    # Using maximum_drawdown on the daily return series
    if len(daily_returns_net) >= 2:
        dd_net_res = maximum_drawdown(daily_returns_net)
        max_dd_net = float(dd_net_res.max_drawdown)
        peak_date = str(dd_net_res.peak_date) if dd_net_res.peak_date else None
        trough_date = str(dd_net_res.trough_date) if dd_net_res.trough_date else None
    else:
        max_dd_net = 0.0
        peak_date = None
        trough_date = None

    if len(daily_returns_gross) >= 2:
        dd_gross_res = maximum_drawdown(daily_returns_gross)
        max_dd_gross = float(dd_gross_res.max_drawdown)
    else:
        max_dd_gross = 0.0

    total_friction = float(total_transaction_costs + total_slippage_costs)

    return BacktestSummaryMetrics(
        initial_value=float(initial_capital),
        final_value_net=final_val_net,
        final_value_gross=final_val_gross,
        cumulative_return_net=cum_ret_net,
        cumulative_return_gross=cum_ret_gross,
        cagr_net=cagr_net,
        cagr_gross=cagr_gross,
        annualized_return_net=ann_ret_net,
        annualized_return_gross=ann_ret_gross,
        volatility_annualized_net=vol_ann_net,
        volatility_annualized_gross=vol_ann_gross,
        sharpe_ratio_net=sharpe_net,
        sharpe_ratio_gross=sharpe_gross,
        sortino_ratio_net=sortino_net,
        sortino_ratio_gross=sortino_gross,
        max_drawdown_net=max_dd_net,
        max_drawdown_gross=max_dd_gross,
        drawdown_peak_date=peak_date,
        drawdown_trough_date=trough_date,
        total_turnover=float(total_turnover),
        total_transaction_costs=float(total_transaction_costs),
        total_slippage_costs=float(total_slippage_costs),
        total_friction_costs=total_friction,
        number_of_rebalances=number_of_rebalances,
        observation_count=n_obs,
        periods_per_year=periods_per_year,
        effective_start_date=effective_start,
        effective_end_date=effective_end,
    )
