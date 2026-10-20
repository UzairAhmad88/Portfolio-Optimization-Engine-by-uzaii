"""
Pure financial mathematics module for portfolio performance attribution,
benchmark comparison, and risk-adjusted metrics evaluation.

Independent of web frameworks or external I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.quant.returns import annualized_return, cumulative_returns
from app.quant.risk import (
    annual_to_periodic_rate,
    annualized_volatility,
    maximum_drawdown,
    sharpe_ratio,
    sortino_ratio,
)


@dataclass(frozen=True)
class PerformanceMetricsResult:
    """
    Comprehensive structured comparison metrics between a portfolio and benchmark.
    """

    observation_count: int
    periods_per_year: int
    start_date: str | None
    end_date: str | None

    # Portfolio Standalone
    portfolio_cumulative_return: float
    portfolio_annualized_return: float
    portfolio_annualized_volatility: float
    portfolio_sharpe_ratio: float | None
    portfolio_sortino_ratio: float | None
    portfolio_max_drawdown: float

    # Benchmark Standalone
    benchmark_cumulative_return: float
    benchmark_annualized_return: float
    benchmark_annualized_volatility: float
    benchmark_sharpe_ratio: float | None
    benchmark_sortino_ratio: float | None
    benchmark_max_drawdown: float

    # Comparative / Active
    arithmetic_active_return: float  # R_p - R_b
    geometric_excess_return: float  # (1 + R_p) / (1 + R_b) - 1
    annualized_active_return: float  # mean(a_t) * m
    tracking_error: float  # std(a_t) * sqrt(m)
    information_ratio: float | None
    beta: float | None
    alpha_annualized: float | None  # Jensen's alpha
    treynor_ratio: float | None
    up_capture_ratio: float | None
    down_capture_ratio: float | None


def align_return_series(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """
    Synchronizes portfolio and benchmark returns via strict inner join on exact dates.
    Drops NaNs and verifies finite values.
    """
    if not isinstance(portfolio_returns, pd.Series):
        raise TypeError(f"portfolio_returns must be a pandas Series, got {type(portfolio_returns).__name__}")
    if not isinstance(benchmark_returns, pd.Series):
        raise TypeError(f"benchmark_returns must be a pandas Series, got {type(benchmark_returns).__name__}")

    combined = pd.concat([portfolio_returns, benchmark_returns], axis=1, join="inner").dropna()
    if combined.empty:
        raise ValueError("Portfolio and benchmark return series share zero overlapping trading dates.")

    p_clean = combined.iloc[:, 0].astype(float)
    b_clean = combined.iloc[:, 1].astype(float)

    if not np.isfinite(p_clean.to_numpy()).all() or not np.isfinite(b_clean.to_numpy()).all():
        raise ValueError("Aligned return series contain non-finite values (NaN or Inf).")

    return p_clean, b_clean


def calculate_active_returns(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> pd.Series:
    """
    Calculates the periodic active return series:
        a_t = r_{p,t} - r_{b,t}
    """
    p_clean, b_clean = align_return_series(portfolio_returns, benchmark_returns)
    return p_clean - b_clean


def calculate_tracking_error(
    active_returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """
    Annualized standard deviation of periodic active returns:
        TE = std(a_t) * sqrt(m)
    """
    if not isinstance(active_returns, pd.Series):
        raise TypeError(f"active_returns must be a pandas Series, got {type(active_returns).__name__}")

    clean = active_returns.dropna()
    if len(clean) < 2:
        return 0.0

    sample_std = float(clean.std(ddof=1))
    return sample_std * np.sqrt(periods_per_year)


def calculate_information_ratio(
    active_returns: pd.Series,
    periods_per_year: int = 252,
) -> float | None:
    """
    Information Ratio:
        IR = (mean(a_t) * m) / TE
    Returns None if tracking error is zero or sample size < 3.
    """
    if not isinstance(active_returns, pd.Series):
        raise TypeError(f"active_returns must be a pandas Series, got {type(active_returns).__name__}")

    clean = active_returns.dropna()
    if len(clean) < 3:
        return None

    te = calculate_tracking_error(clean, periods_per_year=periods_per_year)
    if te <= 1e-12:
        return None

    mean_active = float(clean.mean())
    annualized_active = mean_active * periods_per_year
    return annualized_active / te


def calculate_beta(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float | None:
    """
    Calculates portfolio Beta relative to a benchmark:
        beta = Cov(r_p, r_b) / Var(r_b)
    Returns None if benchmark variance is zero or sample size < 3.
    """
    p_clean, b_clean = align_return_series(portfolio_returns, benchmark_returns)
    if len(p_clean) < 3:
        return None

    var_b = float(b_clean.var(ddof=1))
    if var_b <= 1e-12:
        return None

    cov_pb = float(p_clean.cov(b_clean))
    return cov_pb / var_b


def calculate_jensens_alpha(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate_annual: float = 0.0,
    periods_per_year: int = 252,
) -> float | None:
    """
    Calculates annualized Jensen's Alpha:
        alpha_periodic = (mean(r_p) - r_f) - beta * (mean(r_b) - r_f)
        alpha_annualized = alpha_periodic * periods_per_year
    Returns None if Beta is undefined.
    """
    p_clean, b_clean = align_return_series(portfolio_returns, benchmark_returns)
    beta = calculate_beta(p_clean, b_clean)
    if beta is None:
        return None

    r_f_periodic = annual_to_periodic_rate(risk_free_rate_annual, periods_per_year=periods_per_year)
    mean_p = float(p_clean.mean())
    mean_b = float(b_clean.mean())

    excess_p = mean_p - r_f_periodic
    excess_b = mean_b - r_f_periodic

    alpha_periodic = excess_p - (beta * excess_b)
    return alpha_periodic * periods_per_year


def calculate_treynor_ratio(
    portfolio_returns: pd.Series,
    beta: float | None,
    risk_free_rate_annual: float = 0.0,
    periods_per_year: int = 252,
) -> float | None:
    """
    Calculates Treynor Ratio:
        Treynor = (mean(r_p) - r_f) * m / beta
    Returns None if Beta is zero, negative, or undefined.
    """
    if beta is None or abs(beta) <= 1e-12:
        return None

    valid = portfolio_returns.dropna()
    if valid.empty:
        return None

    r_f_periodic = annual_to_periodic_rate(risk_free_rate_annual, periods_per_year=periods_per_year)
    mean_p = float(valid.mean())
    annualized_excess = (mean_p - r_f_periodic) * periods_per_year
    return annualized_excess / beta


def calculate_capture_ratios(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> tuple[float | None, float | None]:
    """
    Calculates Up-Market Capture and Down-Market Capture ratios:
        Up-Capture = R_{p, up} / R_{b, up} where r_{b,t} > 0
        Down-Capture = R_{p, down} / R_{b, down} where r_{b,t} < 0
    Returns (up_capture, down_capture).
    """
    p_clean, b_clean = align_return_series(portfolio_returns, benchmark_returns)

    up_mask = b_clean > 0.0
    down_mask = b_clean < 0.0

    up_capture: float | None = None
    if up_mask.sum() > 0:
        p_up_cum = float(np.prod(1.0 + p_clean[up_mask]) - 1.0)
        b_up_cum = float(np.prod(1.0 + b_clean[up_mask]) - 1.0)
        if abs(b_up_cum) > 1e-12:
            up_capture = p_up_cum / b_up_cum

    down_capture: float | None = None
    if down_mask.sum() > 0:
        p_down_cum = float(np.prod(1.0 + p_clean[down_mask]) - 1.0)
        b_down_cum = float(np.prod(1.0 + b_clean[down_mask]) - 1.0)
        if abs(b_down_cum) > 1e-12:
            down_capture = p_down_cum / b_down_cum

    return up_capture, down_capture


def calculate_single_period_contributions(
    weights: dict[str, float] | pd.Series,
    returns: dict[str, float] | pd.Series,
) -> dict[str, float]:
    """
    Calculates single-period asset contributions:
        c_i = w_{i, t-1} * r_{i, t}
    """
    if isinstance(weights, pd.Series):
        w_dict = weights.to_dict()
    else:
        w_dict = dict(weights)

    if isinstance(returns, pd.Series):
        r_dict = returns.to_dict()
    else:
        r_dict = dict(returns)

    contributions: dict[str, float] = {}
    for asset, w in w_dict.items():
        r = r_dict.get(asset, 0.0)
        contributions[asset] = float(w * r)

    return contributions


def calculate_multi_period_contributions(
    asset_returns_df: pd.DataFrame,
    weights: dict[str, float] | pd.DataFrame,
) -> dict[str, float]:
    """
    Computes exact additive multi-period asset contributions using Menchero (2000) Logarithmic Linking.
    Guarantees:
        sum_i C_i = R_p (compounded cumulative portfolio return)

    Parameters:
        asset_returns_df: DataFrame with date index and asset tickers as columns.
        weights: Either a static dict of target weights or a DataFrame of weights over time.

    Returns:
        Dict mapping asset ticker to linked cumulative return contribution.
    """
    if asset_returns_df.empty:
        raise ValueError("Asset returns DataFrame is empty.")

    clean_ret = asset_returns_df.dropna().astype(float)
    if clean_ret.empty:
        raise ValueError("Asset returns DataFrame contains no overlapping observations across assets.")

    tickers = list(clean_ret.columns)
    t_steps = len(clean_ret)

    # Resolve daily weights matrix (T x N)
    if isinstance(weights, dict):
        w_row = np.array([weights.get(tk, 0.0) for tk in tickers], dtype=float)
        w_mat = np.tile(w_row, (t_steps, 1))
    elif isinstance(weights, pd.DataFrame):
        aligned_w = weights.reindex(index=clean_ret.index, columns=tickers).ffill().bfill().fillna(0.0)
        w_mat = aligned_w.to_numpy(dtype=float)
    else:
        raise TypeError("weights must be a dict or a pandas DataFrame.")

    ret_mat = clean_ret.to_numpy(dtype=float)

    # Daily period asset contributions: c_{i, t} = w_{i, t-1} * r_{i, t}
    daily_contrib = w_mat * ret_mat  # Shape: (T, N)
    daily_port_return = daily_contrib.sum(axis=1)  # Shape: (T,)

    # Cumulative portfolio return: R_p = prod(1 + r_p) - 1
    cum_port_return = float(np.prod(1.0 + daily_port_return) - 1.0)

    # Menchero Linking Coefficients:
    # L_t = [ln(1 + r_{p,t}) / r_{p,t}] * [R_p / ln(1 + R_p)]
    if abs(cum_port_return) < 1e-12:
        # Near zero cumulative return; unlinked sum is valid
        linking_factors = np.ones(t_steps, dtype=float)
    else:
        log_cum = np.log(1.0 + cum_port_return)
        linking_factors = np.zeros(t_steps, dtype=float)
        for t in range(t_steps):
            r_pt = daily_port_return[t]
            if abs(r_pt) < 1e-12:
                linking_factors[t] = 1.0
            else:
                linking_factors[t] = (np.log(1.0 + r_pt) / r_pt) * (cum_port_return / log_cum)

    # Linked contribution for asset i: C_i = sum_t L_t * c_{i,t}
    linked_contrib_mat = daily_contrib * linking_factors[:, np.newaxis]
    total_linked_contrib = linked_contrib_mat.sum(axis=0)

    result = {tickers[i]: float(total_linked_contrib[i]) for i in range(len(tickers))}
    return result


def evaluate_comparative_performance(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate_annual: float = 0.0,
    periods_per_year: int = 252,
) -> PerformanceMetricsResult:
    """
    Executes a comprehensive benchmark comparison evaluation between a portfolio and benchmark.
    Computes all active risk, standalone risk, and risk-adjusted metrics under consistent conventions.
    """
    p_clean, b_clean = align_return_series(portfolio_returns, benchmark_returns)
    n = len(p_clean)

    start_date = str(p_clean.index[0]) if n > 0 else None
    end_date = str(p_clean.index[-1]) if n > 0 else None

    # Standalone Portfolio
    p_cum = float(np.prod(1.0 + p_clean) - 1.0)
    p_ann_ret = annualized_return(p_clean, periods_per_year=periods_per_year)
    p_ann_vol = annualized_volatility(p_clean, periods_per_year=periods_per_year)
    try:
        p_sharpe: float | None = sharpe_ratio(p_clean, risk_free_rate=risk_free_rate_annual, periods_per_year=periods_per_year)
    except ValueError:
        p_sharpe = None
    try:
        p_sortino: float | None = sortino_ratio(p_clean, required_return=risk_free_rate_annual, periods_per_year=periods_per_year)
    except ValueError:
        p_sortino = None
    p_dd_res = maximum_drawdown(p_clean)

    # Standalone Benchmark
    b_cum = float(np.prod(1.0 + b_clean) - 1.0)
    b_ann_ret = annualized_return(b_clean, periods_per_year=periods_per_year)
    b_ann_vol = annualized_volatility(b_clean, periods_per_year=periods_per_year)
    try:
        b_sharpe: float | None = sharpe_ratio(b_clean, risk_free_rate=risk_free_rate_annual, periods_per_year=periods_per_year)
    except ValueError:
        b_sharpe = None
    try:
        b_sortino: float | None = sortino_ratio(b_clean, required_return=risk_free_rate_annual, periods_per_year=periods_per_year)
    except ValueError:
        b_sortino = None
    b_dd_res = maximum_drawdown(b_clean)

    # Active Series
    active_series = p_clean - b_clean
    arithmetic_active = p_cum - b_cum
    geometric_excess = ((1.0 + p_cum) / (1.0 + b_cum)) - 1.0 if abs(1.0 + b_cum) > 1e-12 else 0.0

    mean_active = float(active_series.mean())
    ann_active = mean_active * periods_per_year
    te = calculate_tracking_error(active_series, periods_per_year=periods_per_year)
    ir = calculate_information_ratio(active_series, periods_per_year=periods_per_year)
    beta = calculate_beta(p_clean, b_clean)
    alpha = calculate_jensens_alpha(
        p_clean,
        b_clean,
        risk_free_rate_annual=risk_free_rate_annual,
        periods_per_year=periods_per_year,
    )
    treynor = calculate_treynor_ratio(
        p_clean,
        beta,
        risk_free_rate_annual=risk_free_rate_annual,
        periods_per_year=periods_per_year,
    )
    up_cap, down_cap = calculate_capture_ratios(p_clean, b_clean)

    return PerformanceMetricsResult(
        observation_count=n,
        periods_per_year=periods_per_year,
        start_date=start_date,
        end_date=end_date,
        portfolio_cumulative_return=p_cum,
        portfolio_annualized_return=p_ann_ret,
        portfolio_annualized_volatility=p_ann_vol,
        portfolio_sharpe_ratio=p_sharpe,
        portfolio_sortino_ratio=p_sortino,
        portfolio_max_drawdown=p_dd_res.max_drawdown,
        benchmark_cumulative_return=b_cum,
        benchmark_annualized_return=b_ann_ret,
        benchmark_annualized_volatility=b_ann_vol,
        benchmark_sharpe_ratio=b_sharpe,
        benchmark_sortino_ratio=b_sortino,
        benchmark_max_drawdown=b_dd_res.max_drawdown,
        arithmetic_active_return=arithmetic_active,
        geometric_excess_return=geometric_excess,
        annualized_active_return=ann_active,
        tracking_error=te,
        information_ratio=ir,
        beta=beta,
        alpha_annualized=alpha,
        treynor_ratio=treynor,
        up_capture_ratio=up_cap,
        down_capture_ratio=down_cap,
    )
