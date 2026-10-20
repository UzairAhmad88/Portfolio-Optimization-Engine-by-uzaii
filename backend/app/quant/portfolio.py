"""
Portfolio return and risk calculation module.

Provides mathematically rigorous, reproducible calculations of portfolio periodic
returns, expected returns, portfolio variance, portfolio volatility, and weight summaries.
Supports long-only and long-short positions. Handles floating-point numerical tolerances.

Independent of web frameworks or external I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PortfolioWeightSummary:
    """
    Summary metrics for a portfolio weight vector.

    Attributes:
        asset_count: Total number of assets in the weight vector.
        total_weight: Algebraic sum of all weights (net exposure).
        gross_exposure: Sum of absolute values of weights (sum(|w_i|)).
        net_exposure: Net market exposure (identical to total_weight).
        is_fully_invested: True if total_weight is within 1e-6 of 1.0.
        is_long_only: True if all weights are non-negative (>= -1e-12).
        has_short_positions: True if any weight is strictly negative (< -1e-12).
        max_weight: Maximum single asset weight.
        min_weight: Minimum single asset weight.
    """

    asset_count: int
    total_weight: float
    gross_exposure: float
    net_exposure: float
    is_fully_invested: bool
    is_long_only: bool
    has_short_positions: bool
    max_weight: float
    min_weight: float


def validate_weights(
    weights: pd.Series | Mapping[str, float] | Sequence[float],
    expected_assets: Sequence[str] | None = None,
) -> pd.Series:
    """
    Validates and standardizes portfolio weights into a pandas Series aligned with expected assets.

    Parameters:
        weights: Dictionary, pandas Series, or sequence of numeric weights.
        expected_assets: Optional sequence of asset identifiers to validate and align against.

    Returns:
        pandas Series of weights indexed by asset identifiers.

    Raises:
        ValueError: If weights contain NaNs, infinities, or fail to match expected_assets.
        TypeError: If weights format is unsupported.

    Notes:
        Does NOT silently renormalize weights. Does NOT enforce long-only or sum-to-one
        restrictions unless explicitly instructed by a downstream constraint validator.
    """
    if weights is None:
        raise ValueError("Portfolio weights cannot be None.")

    # Convert to pandas Series with explicit float dtype
    if isinstance(weights, pd.Series):
        s_weights = weights.astype(float)
    elif isinstance(weights, dict):
        s_weights = pd.Series(weights, dtype=float)
    elif isinstance(weights, (list, tuple, np.ndarray)):
        if expected_assets is None:
            s_weights = pd.Series(weights, dtype=float)
        else:
            if len(weights) != len(expected_assets):
                raise ValueError(
                    f"Weight count ({len(weights)}) does not match expected asset count ({len(expected_assets)})."
                )
            s_weights = pd.Series(
                list(weights), index=list(expected_assets), dtype=float
            )
    else:
        raise TypeError(f"Unsupported weights type: {type(weights).__name__}")

    if s_weights.empty:
        raise ValueError("Portfolio weights vector is empty.")

    # Validate finite values
    arr = s_weights.to_numpy(dtype=float)
    if np.isnan(arr).any():
        raise ValueError("Portfolio weights contain NaN values.")
    if np.isinf(arr).any():
        raise ValueError("Portfolio weights contain infinite values.")

    # Validate against expected assets if provided
    if expected_assets is not None:
        expected_list = list(expected_assets)
        # If weights had numeric index and expected_assets has same length
        if set(s_weights.index) != set(expected_list):
            missing = set(expected_list) - set(s_weights.index)
            extra = set(s_weights.index) - set(expected_list)
            raise ValueError(
                f"Weight index does not match expected assets. Missing: {missing}, Extra: {extra}."
            )
        # Reorder to match exact order of expected_assets
        s_weights = s_weights.reindex(expected_list)

    return s_weights


def summarize_weights(
    weights: pd.Series | Mapping[str, float] | Sequence[float],
) -> PortfolioWeightSummary:
    """
    Computes diagnostic summary metrics for a weight vector.
    """
    w_series = validate_weights(weights)
    arr = w_series.to_numpy(dtype=float)

    total_w = float(np.sum(arr))
    gross = float(np.sum(np.abs(arr)))
    min_w = float(np.min(arr))
    max_w = float(np.max(arr))

    is_invested = bool(np.isclose(total_w, 1.0, atol=1e-6))
    is_long = bool((arr >= -1e-12).all())
    has_short = bool((arr < -1e-12).any())

    return PortfolioWeightSummary(
        asset_count=len(arr),
        total_weight=total_w,
        gross_exposure=gross,
        net_exposure=total_w,
        is_fully_invested=is_invested,
        is_long_only=is_long,
        has_short_positions=has_short,
        max_weight=max_w,
        min_weight=min_w,
    )


def normalize_weights(
    weights: pd.Series | Mapping[str, float] | Sequence[float],
) -> pd.Series:
    """
    Explicitly renormalizes weights to sum to 1.0 (w_i_norm = w_i / sum(w)).

    Raises:
        ValueError: If total weight is zero or non-finite.
    """
    w_series = validate_weights(weights)
    total_w = float(w_series.sum())
    if np.isclose(total_w, 0.0, atol=1e-12):
        raise ValueError("Cannot normalize weights with zero sum (total_weight = 0.0).")
    return w_series / total_w


def portfolio_returns(
    returns: pd.DataFrame,
    weights: pd.Series | Mapping[str, float] | Sequence[float],
) -> pd.Series:
    """
    Calculates historical portfolio periodic returns:
        r_{p,t} = sum_{i=1}^N w_i * r_{i,t} = r_t * w

    Parameters:
        returns: pandas DataFrame of periodic returns.
        weights: Portfolio weights matching returns columns.

    Returns:
        pandas Series of portfolio periodic returns matching returns index.

    Raises:
        ValueError: If weights do not match assets or if returns contain non-finite values.

    Notes:
        Requires aligned returns. If any asset has NaN in a period, listwise deletion
        is applied to prevent partial-portfolio distortion.
    """
    if not isinstance(returns, pd.DataFrame):
        raise TypeError(
            f"Expected pandas DataFrame for returns, received {type(returns).__name__}."
        )
    if returns.empty:
        raise ValueError("Return DataFrame is empty.")

    w_series = validate_weights(weights, expected_assets=list(returns.columns))

    # Clean returns using listwise alignment
    aligned_returns = returns.dropna(how="any").astype(float)
    if aligned_returns.empty:
        raise ValueError("No common periods across all assets in return DataFrame.")

    # Dot product: (T, N) @ (N,) -> (T,)
    port_ret = aligned_returns.to_numpy() @ w_series.to_numpy()
    return pd.Series(port_ret, index=aligned_returns.index, name="portfolio_return")


def portfolio_expected_return(
    returns: pd.DataFrame,
    weights: pd.Series | Mapping[str, float] | Sequence[float],
    annualized: bool = False,
    periods_per_year: int = 252,
) -> float:
    """
    Calculates arithmetic expected portfolio return from historical periodic returns:
        mu_p = sum_{i=1}^N w_i * mean(r_i) = w^T mu

    Parameters:
        returns: pandas DataFrame of periodic returns.
        weights: Portfolio weights matching returns columns.
        annualized: If True, multiplies arithmetic mean by periods_per_year.
        periods_per_year: Scale factor for annualization (default 252).

    Returns:
        float expected return.

    Notes:
        This is an arithmetic historical sample estimate and does NOT constitute
        a predictive guarantee of future investment returns.
    """
    p_ret = portfolio_returns(returns, weights)
    mean_ret = float(p_ret.mean())
    if annualized:
        if periods_per_year <= 0:
            raise ValueError(
                f"periods_per_year must be positive, got {periods_per_year}."
            )
        return mean_ret * float(periods_per_year)
    return mean_ret


def portfolio_variance(
    weights: pd.Series | Mapping[str, float] | Sequence[float],
    cov_matrix: pd.DataFrame | np.ndarray,
    tolerance: float = 1e-12,
) -> float:
    """
    Calculates portfolio return variance:
        sigma_p^2 = w^T * Sigma * w

    Parameters:
        weights: Portfolio weights matching covariance matrix dimensions.
        cov_matrix: NxN symmetric covariance matrix (pandas DataFrame or NumPy array).
        tolerance: Numerical tolerance for tiny negative values resulting from floating-point
                   rounding error. If -tolerance <= variance < 0, it is clamped to 0.0.
                   If variance < -tolerance, ValueError is raised.

    Returns:
        float portfolio variance (>= 0.0).

    Raises:
        ValueError: If dimensions mismatch, matrix is not symmetric, or variance is materially negative.
    """
    # Standardize cov_matrix
    if isinstance(cov_matrix, pd.DataFrame):
        asset_names = list(cov_matrix.columns)
        if list(cov_matrix.index) != asset_names:
            raise ValueError("Covariance matrix index and columns must match.")
        w_series = validate_weights(weights, expected_assets=asset_names)
        cov_arr = cov_matrix.to_numpy(dtype=float)
        w_arr = w_series.to_numpy(dtype=float)
    elif isinstance(cov_matrix, np.ndarray):
        if cov_matrix.ndim != 2 or cov_matrix.shape[0] != cov_matrix.shape[1]:
            raise ValueError("Covariance array must be a 2D square matrix.")
        w_series = validate_weights(weights)
        if len(w_series) != cov_matrix.shape[0]:
            raise ValueError(
                f"Weight dimension ({len(w_series)}) does not match covariance dimension ({cov_matrix.shape[0]})."
            )
        cov_arr = cov_matrix.astype(float)
        w_arr = w_series.to_numpy(dtype=float)
    else:
        raise TypeError(
            f"Expected DataFrame or ndarray for cov_matrix, got {type(cov_matrix).__name__}."
        )

    # Validate symmetry
    if not np.allclose(cov_arr, cov_arr.T, atol=1e-10, rtol=1e-8):
        raise ValueError("Covariance matrix is not symmetric.")

    # Compute quadratic form: w^T * Sigma * w
    var = float(w_arr.T @ cov_arr @ w_arr)

    # Handle floating-point rounding around zero
    if -tolerance <= var < 0.0:
        return 0.0
    elif var < -tolerance:
        raise ValueError(
            f"Portfolio variance is materially negative ({var:.6e} < -{tolerance:.1e}). "
            "The covariance matrix may not be positive semi-definite."
        )

    return var


def portfolio_volatility(
    weights: pd.Series | Mapping[str, float] | Sequence[float],
    cov_matrix: pd.DataFrame | np.ndarray,
    tolerance: float = 1e-12,
) -> float:
    """
    Calculates portfolio volatility (standard deviation):
        sigma_p = sqrt(w^T * Sigma * w)

    Parameters:
        weights: Portfolio weights matching covariance matrix dimensions.
        cov_matrix: NxN symmetric covariance matrix.
        tolerance: Numerical tolerance for tiny negative values.

    Returns:
        float portfolio volatility (>= 0.0).
    """
    var = portfolio_variance(weights, cov_matrix, tolerance=tolerance)
    return float(np.sqrt(var))
