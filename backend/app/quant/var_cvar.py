"""
Pure financial mathematics module for Value at Risk (VaR) and Conditional Value at Risk (CVaR).

Provides empirical, parametric (variance-covariance), and historical estimators with
explicit loss-sign conventions and comprehensive mathematical validation.

Loss Convention:
    Loss L = V_0 - V_T (monetary) or L_% = (V_0 - V_T) / V_0 (fractional).
    Positive VaR and CVaR represent positive economic losses.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
from scipy.stats import norm


@dataclass(frozen=True)
class VaRCVaRResult:
    """
    Structured outcome of a Value at Risk and Conditional Value at Risk calculation.

    Attributes:
        var_absolute: Absolute monetary loss at the specified quantile (e.g. $10,000).
        var_percentage: Fractional/percentage loss relative to initial capital (e.g. 0.10 for 10%).
        cvar_absolute: Expected monetary loss given that loss >= VaR.
        cvar_percentage: Expected fractional loss given that loss >= VaR.
        confidence_level: Quantile confidence level (e.g. 0.95 or 0.99).
        loss_sample_count: Number of loss observations used in evaluation.
    """

    var_absolute: float
    var_percentage: float
    cvar_absolute: float
    cvar_percentage: float
    confidence_level: float
    loss_sample_count: int


def empirical_var(
    losses: np.ndarray | list[float] | pd.Series,
    confidence_level: float = 0.95,
) -> float:
    """
    Computes empirical Value at Risk (VaR) from an array of observed or simulated losses.

    Parameters:
        losses: 1D array of portfolio losses where positive numbers represent economic losses
                (L = V_0 - V_T).
        confidence_level: Probability confidence level, typically 0.95 or 0.99.
                          Must be strictly in (0.0, 1.0).

    Returns:
        float: The q-quantile of the empirical loss distribution.

    Raises:
        ValueError: If confidence_level is outside (0.0, 1.0) or sample has fewer than 2 elements.
    """
    if not (0.0 < confidence_level < 1.0):
        raise ValueError(
            f"Confidence level must be strictly between 0.0 and 1.0, got {confidence_level}."
        )

    arr = np.asarray(losses, dtype=float)
    if arr.ndim != 1 or arr.size < 2:
        raise ValueError(f"Loss array must be 1-dimensional with at least 2 observations, got {arr.size}.")

    if not np.isfinite(arr).all():
        raise ValueError("Loss array contains non-finite values (NaN or Inf).")

    # Linear interpolation quantile matching standard empirical definition
    return float(np.quantile(arr, confidence_level, method="linear"))


def empirical_cvar(
    losses: np.ndarray | list[float] | pd.Series,
    confidence_level: float = 0.95,
    var_threshold: float | None = None,
) -> float:
    """
    Computes empirical Conditional Value at Risk (CVaR / Expected Shortfall) from losses.

    Defined as the average loss in the worst (1 - confidence_level) tail:
        CVaR_q = E[L | L >= VaR_q]

    Parameters:
        losses: 1D array of portfolio losses (L = V_0 - V_T).
        confidence_level: Probability confidence level in (0.0, 1.0).
        var_threshold: Optional precomputed VaR threshold. If None, computed via empirical_var.

    Returns:
        float: Expected loss given loss >= VaR_q. Always satisfies CVaR >= VaR within precision.
    """
    arr = np.asarray(losses, dtype=float)
    if var_threshold is None:
        var_val = empirical_var(arr, confidence_level=confidence_level)
    else:
        var_val = float(var_threshold)

    # Tail losses at or beyond VaR
    tail = arr[arr >= var_val]
    if tail.size == 0:
        # Extreme finite-sample edge case where strict inequality filter is empty
        return var_val

    cvar_val = float(np.mean(tail))
    # Guarantee CVaR >= VaR within floating-point tolerance
    return max(var_val, cvar_val)


def calculate_empirical_var_cvar(
    terminal_losses: np.ndarray,
    initial_capital: float,
    confidence_level: float = 0.95,
) -> VaRCVaRResult:
    """
    Computes monetary and percentage empirical VaR and CVaR from terminal losses.

    Parameters:
        terminal_losses: Array of absolute losses L = V_0 - V_T.
        initial_capital: Baseline portfolio valuation V_0 > 0.
        confidence_level: Quantile level in (0.0, 1.0).

    Returns:
        VaRCVaRResult dataclass.
    """
    if initial_capital <= 0.0:
        raise ValueError(f"Initial capital must be strictly positive, got {initial_capital}.")

    var_abs = empirical_var(terminal_losses, confidence_level=confidence_level)
    cvar_abs = empirical_cvar(terminal_losses, confidence_level=confidence_level, var_threshold=var_abs)

    var_pct = var_abs / initial_capital
    cvar_pct = cvar_abs / initial_capital

    return VaRCVaRResult(
        var_absolute=var_abs,
        var_percentage=var_pct,
        cvar_absolute=cvar_abs,
        cvar_percentage=cvar_pct,
        confidence_level=confidence_level,
        loss_sample_count=int(len(terminal_losses)),
    )


def parametric_var_cvar(
    initial_capital: float,
    periodic_mean_return: float,
    periodic_volatility: float,
    horizon_periods: int = 1,
    confidence_level: float = 0.95,
) -> VaRCVaRResult:
    """
    Computes analytical parametric (variance-covariance) VaR and CVaR under the assumption
    of normally distributed independent returns over the given horizon.

    Formulas:
        mu_H = periodic_mean_return * horizon_periods
        sigma_H = periodic_volatility * sqrt(horizon_periods)
        VaR_% = -mu_H + z_q * sigma_H
        CVaR_% = -mu_H + (phi(z_q) / (1 - q)) * sigma_H

    Parameters:
        initial_capital: Baseline capital V_0 > 0.
        periodic_mean_return: Expected periodic portfolio return.
        periodic_volatility: Periodic portfolio standard deviation >= 0.
        horizon_periods: Horizon length in periods (e.g. days) >= 1.
        confidence_level: Probability level in (0.0, 1.0).

    Returns:
        VaRCVaRResult dataclass.
    """
    if initial_capital <= 0.0:
        raise ValueError(f"Initial capital must be strictly positive, got {initial_capital}.")
    if periodic_volatility < 0.0 or not math.isfinite(periodic_volatility):
        raise ValueError(f"Periodic volatility must be finite and non-negative, got {periodic_volatility}.")
    if horizon_periods < 1:
        raise ValueError(f"Horizon periods must be at least 1, got {horizon_periods}.")
    if not (0.0 < confidence_level < 1.0):
        raise ValueError(f"Confidence level must be in (0.0, 1.0), got {confidence_level}.")

    # Horizon scaling
    mu_h = periodic_mean_return * float(horizon_periods)
    sigma_h = periodic_volatility * math.sqrt(float(horizon_periods))

    z_q = float(norm.ppf(confidence_level))
    phi_z_q = float(norm.pdf(z_q))

    # Loss percentage: L_% = -R_p
    var_pct = -mu_h + (z_q * sigma_h)
    cvar_pct = -mu_h + ((phi_z_q / (1.0 - confidence_level)) * sigma_h)

    var_abs = var_pct * initial_capital
    cvar_abs = cvar_pct * initial_capital

    return VaRCVaRResult(
        var_absolute=var_abs,
        var_percentage=var_pct,
        cvar_absolute=cvar_abs,
        cvar_percentage=cvar_pct,
        confidence_level=confidence_level,
        loss_sample_count=horizon_periods,
    )


def historical_var_cvar(
    historical_portfolio_returns: pd.Series | np.ndarray,
    initial_capital: float,
    horizon_periods: int = 1,
    confidence_level: float = 0.95,
) -> VaRCVaRResult:
    """
    Computes empirical VaR and CVaR from observed historical portfolio returns.

    If horizon_periods == 1, discrete 1-period returns are used directly.
    If horizon_periods > 1, rolling compound returns over non-overlapping or rolling windows
    are computed:
        R_H = prod_{k=1}^H (1 + r_{t+k}) - 1

    Parameters:
        historical_portfolio_returns: Series or 1D array of historical periodic returns.
        initial_capital: Baseline portfolio value V_0 > 0.
        horizon_periods: Horizon in periods >= 1.
        confidence_level: Confidence level in (0.0, 1.0).

    Returns:
        VaRCVaRResult dataclass.
    """
    if initial_capital <= 0.0:
        raise ValueError(f"Initial capital must be strictly positive, got {initial_capital}.")
    if horizon_periods < 1:
        raise ValueError(f"Horizon periods must be at least 1, got {horizon_periods}.")

    arr = np.asarray(historical_portfolio_returns, dtype=float)
    if arr.ndim != 1 or arr.size < 2:
        raise ValueError(f"Historical returns must contain at least 2 observations, got {arr.size}.")

    if horizon_periods == 1:
        horizon_returns = arr
    else:
        # Compute rolling compound returns
        if arr.size < horizon_periods:
            raise ValueError(
                f"Historical series length ({arr.size}) is shorter than horizon ({horizon_periods})."
            )
        # 1 + r
        gross = 1.0 + arr
        # Sliding product
        horizon_returns_list = []
        for i in range(len(gross) - horizon_periods + 1):
            prod_val = float(np.prod(gross[i : i + horizon_periods]) - 1.0)
            horizon_returns_list.append(prod_val)
        horizon_returns = np.array(horizon_returns_list, dtype=float)

    # Losses = -returns * initial_capital
    historical_losses = -horizon_returns * initial_capital
    return calculate_empirical_var_cvar(
        terminal_losses=historical_losses,
        initial_capital=initial_capital,
        confidence_level=confidence_level,
    )
