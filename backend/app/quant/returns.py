"""
Financial returns calculation module.

Provides mathematically rigorous, reproducible simple, logarithmic, cumulative,
and annualized return calculations for individual assets and multi-asset price panels.
Independent of web frameworks or external I/O.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd


def _validate_price_data(prices: pd.Series | pd.DataFrame) -> None:
    """
    Validates that price data contains only finite, strictly positive values.
    Raises ValueError on empty, non-positive, or non-finite observations.
    """
    if prices.empty:
        raise ValueError("Price series or panel is empty.")

    if isinstance(prices, pd.Series):
        valid_prices = prices.dropna()
        if valid_prices.empty:
            raise ValueError("Price series contains no valid non-null observations.")
        if np.isinf(valid_prices.to_numpy(dtype=float)).any():
            raise ValueError("Price series contains non-finite values (infinity).")
        if (valid_prices.to_numpy(dtype=float) <= 0.0).any():
            raise ValueError("Prices must be strictly positive (> 0.0).")
    elif isinstance(prices, pd.DataFrame):
        for col in prices.columns:
            valid_col = prices[col].dropna()
            if valid_col.empty:
                raise ValueError(
                    f"Price column '{col}' contains no valid non-null observations."
                )
            if np.isinf(valid_col.to_numpy(dtype=float)).any():
                raise ValueError(
                    f"Price column '{col}' contains non-finite values (infinity)."
                )
            if (valid_col.to_numpy(dtype=float) <= 0.0).any():
                raise ValueError(
                    f"Price column '{col}' contains non-positive values (<= 0.0)."
                )
    else:
        raise TypeError(
            f"Expected pandas Series or DataFrame, received {type(prices).__name__}."
        )


def simple_returns(prices: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """
    Calculates simple arithmetic discrete returns:
        r_t = (P_t / P_{t-1}) - 1 = (P_t - P_{t-1}) / P_{t-1}

    Parameters:
        prices: pandas Series or DataFrame of positive historical prices.
                Must be sorted in ascending chronological order.

    Returns:
        pandas Series or DataFrame of simple returns. The first observation
        is NaN because no prior price exists.

    Notes:
        Simple returns are linearly additive across assets in a portfolio:
            R_p = sum(w_i * R_i)
        They are NOT linearly additive across time.
    """
    _validate_price_data(prices)
    return prices.pct_change(fill_method=None)


def log_returns(prices: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """
    Calculates continuously compounded (logarithmic) returns:
        r_t = ln(P_t / P_{t-1}) = ln(P_t) - ln(P_{t-1})

    Parameters:
        prices: pandas Series or DataFrame of positive historical prices.
                Must be sorted in ascending chronological order.

    Returns:
        pandas Series or DataFrame of logarithmic returns. The first observation
        is NaN because no prior price exists.

    Notes:
        Logarithmic returns are linearly additive across time:
            r_{0 -> T} = sum_{t=1}^T r_t
        They are NOT linearly additive across assets in a portfolio:
            ln(w^T P_t) != w^T ln(P_t).
    """
    _validate_price_data(prices)
    if isinstance(prices, pd.Series):
        price_arr = prices.astype(float)
        return np.log(price_arr / price_arr.shift(1))
    else:
        price_df = prices.astype(float)
        return np.log(price_df / price_df.shift(1))


def cumulative_returns(
    returns: pd.Series | pd.DataFrame,
    as_wealth_index: bool = False,
) -> pd.Series | pd.DataFrame:
    """
    Calculates cumulative wealth growth from a sequence of discrete simple returns:
        R_cum(t) = prod_{tau=1}^t (1 + r_tau) - 1

    Parameters:
        returns: pandas Series or DataFrame of periodic simple returns.
        as_wealth_index: If True, returns the wealth curve starting at 1.0 (prod(1 + r_t)).
                         If False, returns cumulative return starting at 0.0 (prod(1 + r_t) - 1).

    Returns:
        pandas Series or DataFrame of cumulative return series.
    """
    if returns.empty:
        raise ValueError("Return series or panel is empty.")

    clean_returns = returns.copy()
    if isinstance(clean_returns, pd.Series):
        valid_returns = clean_returns.dropna()
        if valid_returns.empty:
            raise ValueError("Return series contains no valid non-null observations.")
        if np.isinf(valid_returns.to_numpy(dtype=float)).any():
            raise ValueError("Return series contains non-finite values (infinity).")
        if (valid_returns.to_numpy(dtype=float) < -1.0).any():
            raise ValueError(
                "Simple return cannot be less than -100% (total capital loss)."
            )

        # Compute cumulative growth on clean observations
        growth = (1.0 + valid_returns.astype(float)).cumprod()
        res = growth if as_wealth_index else (growth - 1.0)
        return res.reindex(clean_returns.index)
    elif isinstance(clean_returns, pd.DataFrame):
        for col in clean_returns.columns:
            valid_col = clean_returns[col].dropna()
            if valid_col.empty:
                raise ValueError(
                    f"Return column '{col}' contains no valid non-null observations."
                )
            if np.isinf(valid_col.to_numpy(dtype=float)).any():
                raise ValueError(
                    f"Return column '{col}' contains non-finite values (infinity)."
                )
            if (valid_col.to_numpy(dtype=float) < -1.0).any():
                raise ValueError(f"Return column '{col}' contains returns below -100%.")

        growth = (1.0 + clean_returns.astype(float)).cumprod()
        return growth if as_wealth_index else (growth - 1.0)
    else:
        raise TypeError(
            f"Expected pandas Series or DataFrame, received {type(returns).__name__}."
        )


def annualized_return(
    returns: pd.Series | pd.DataFrame,
    periods_per_year: int = 252,
    method: Literal["geometric", "arithmetic"] = "geometric",
) -> float | pd.Series:
    """
    Calculates annualized return for a periodic simple return series.

    Parameters:
        returns: pandas Series or DataFrame of simple returns.
        periods_per_year: Annualization scale factor (e.g. 252 for US equities,
                          250 for PSX equities, 52 for weekly, 12 for monthly).
        method:
            - "geometric" (Compound Annual Growth Rate / CAGR):
                CAGR = (prod(1 + r_t))^(periods_per_year / N) - 1
            - "arithmetic":
                R_ann = mean(r_t) * periods_per_year

    Returns:
        float (for Series input) or pd.Series (for DataFrame input).

    Notes:
        Annualization assumes identical periodic compounding and is an empirical
        historical summary, NOT a guarantee or forecast of future performance.
    """
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be a positive integer (> 0).")

    if method not in ("geometric", "arithmetic"):
        raise ValueError(
            f"Unknown annualization method '{method}'. Must be 'geometric' or 'arithmetic'."
        )

    if isinstance(returns, pd.Series):
        valid = returns.dropna().astype(float)
        n = len(valid)
        if n == 0:
            raise ValueError("Return series contains no valid observations.")
        if np.isinf(valid.to_numpy()).any():
            raise ValueError("Return series contains non-finite values.")
        if (valid.to_numpy() < -1.0).any():
            raise ValueError("Simple return cannot be less than -1.0 (-100%).")

        if method == "arithmetic":
            return float(valid.mean() * periods_per_year)
        else:
            total_growth = (1.0 + valid).prod()
            if total_growth <= 0.0:
                raise ValueError(
                    "Cumulative wealth is non-positive; geometric CAGR cannot be annualized."
                )
            return float(total_growth ** (periods_per_year / n) - 1.0)

    elif isinstance(returns, pd.DataFrame):
        res: dict[str, float] = {}
        for col in returns.columns:
            res[col] = annualized_return(
                returns[col], periods_per_year=periods_per_year, method=method
            )
        return pd.Series(res, name=f"annualized_return_{method}")
    else:
        raise TypeError(
            f"Expected pandas Series or DataFrame, received {type(returns).__name__}."
        )
