"""
Pure mathematical functions for historical stress window extraction and covariance stress.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd


def extract_historical_window_shocks(
    price_df: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[dict[str, float], str, str, list[str]]:
    """
    Extracts observed historical asset returns over a verified calendar window.

    Formula:
        r_i = (P_{i, end} - P_{i, start}) / P_{i, start}

    Parameters:
        price_df: Synchronized historical price DataFrame (sorted chronologically).
        start_date: Desired starting date (YYYY-MM-DD) or None for inception.
        end_date: Desired ending date (YYYY-MM-DD) or None for latest.

    Returns:
        tuple of (asset_shocks, effective_start_date, effective_end_date, warnings).
    """
    if price_df.empty or len(price_df) < 2:
        raise ValueError("Price DataFrame must have at least 2 historical observations.")

    df = price_df.copy()
    all_dates = list(df.index)

    # Filter by date if specified
    if start_date:
        df = df[df.index >= str(start_date)]
    if end_date:
        df = df[df.index <= str(end_date)]

    if len(df) < 2:
        raise ValueError(
            f"Specified historical window [{start_date} to {end_date}] contains fewer than 2 valid observations."
        )

    effective_start = str(df.index[0])
    effective_end = str(df.index[-1])
    warnings: list[str] = []

    if start_date and effective_start != str(start_date):
        warnings.append(f"Historical window start adjusted to nearest trading session: {effective_start}")
    if end_date and effective_end != str(end_date):
        warnings.append(f"Historical window end adjusted to nearest trading session: {effective_end}")

    shocks: dict[str, float] = {}
    for col in df.columns:
        p_start = df[col].iloc[0]
        p_end = df[col].iloc[-1]

        if not math.isfinite(p_start) or not math.isfinite(p_end) or p_start <= 0:
            raise ValueError(f"Invalid non-positive or non-finite price encountered for asset '{col}'.")

        ret = (p_end - p_start) / p_start
        shocks[str(col)] = float(ret)

    return shocks, effective_start, effective_end, warnings


def stress_covariance_matrix(
    cov_matrix: pd.DataFrame,
    weights: dict[str, float],
    volatility_multiplier: float | None = 1.0,
    correlation_multiplier: float | None = 1.0,
    auto_project_psd: bool = True,
) -> tuple[pd.DataFrame, float, float, float, list[str]]:
    """
    Applies volatility scaling and correlation perturbations to a baseline covariance matrix.
    Enforces matrix symmetry and positive semi-definiteness (PSD).

    Parameters:
        cov_matrix: Baseline N x N covariance DataFrame.
        weights: Dictionary mapping asset ID -> weight.
        volatility_multiplier: Factor to scale standard deviations (default 1.0, > 0).
        correlation_multiplier: Factor to scale off-diagonal correlations (default 1.0, > 0).
        auto_project_psd: If True, projects matrix with negative eigenvalues to nearest PSD matrix.

    Returns:
        tuple of (stressed_cov_df, baseline_vol, stressed_vol, vol_change, warnings).
    """
    vol_scale = float(volatility_multiplier) if volatility_multiplier is not None else 1.0
    corr_scale = float(correlation_multiplier) if correlation_multiplier is not None else 1.0

    if vol_scale <= 0:
        raise ValueError(f"Volatility multiplier must be strictly positive, got {vol_scale}")
    if corr_scale <= 0 or corr_scale > 2.0:
        raise ValueError(f"Correlation multiplier must be in (0, 2.0], got {corr_scale}")

    assets = list(cov_matrix.columns)
    N = len(assets)
    warnings: list[str] = []

    # 1. Align weights vector
    w_vec = np.array([weights.get(a, 0.0) for a in assets], dtype=np.float64)

    sigma_0 = cov_matrix.to_numpy(dtype=np.float64)

    # Baseline portfolio volatility
    var_0 = float(w_vec @ sigma_0 @ w_vec)
    base_vol = math.sqrt(max(0.0, var_0))

    # Decompose into standard deviations and correlation matrix
    diag_var = np.diag(sigma_0)
    if np.any(diag_var <= 0):
        raise ValueError("Baseline covariance matrix contains non-positive diagonal variances.")

    std_0 = np.sqrt(diag_var)
    inv_std = 1.0 / std_0
    D_inv = np.diag(inv_std)
    R_0 = D_inv @ sigma_0 @ D_inv

    # Ensure correlation bounds [-1, 1] on baseline
    np.fill_diagonal(R_0, 1.0)
    R_0 = np.clip(R_0, -1.0, 1.0)

    # 2. Apply stress
    # Stressed standard deviations
    std_stressed = std_0 * vol_scale

    # Stressed correlation matrix
    R_stressed = R_0.copy()
    if abs(corr_scale - 1.0) > 1e-6:
        # Scale off-diagonal elements
        for i in range(N):
            for j in range(N):
                if i != j:
                    R_stressed[i, j] = np.clip(R_0[i, j] * corr_scale, -0.999, 0.999)
        # Symmetrize
        R_stressed = 0.5 * (R_stressed + R_stressed.T)
        np.fill_diagonal(R_stressed, 1.0)

    # 3. Check Positive Semi-Definiteness
    eigenvalues, eigenvectors = np.linalg.eigh(R_stressed)
    min_eig = float(np.min(eigenvalues))

    if min_eig < -1e-8:
        if not auto_project_psd:
            raise ValueError(
                f"Correlation stress produced non-positive-semidefinite matrix (minimum eigenvalue = {min_eig:.6f})."
            )
        # Spectral clipping projection
        clipped_eigs = np.maximum(eigenvalues, 1e-8)
        R_stressed = eigenvectors @ np.diag(clipped_eigs) @ eigenvectors.T
        # Normalize diagonals back to 1.0
        D_R = np.sqrt(np.diag(R_stressed))
        R_stressed = R_stressed / np.outer(D_R, D_R)
        np.fill_diagonal(R_stressed, 1.0)
        warnings.append(
            f"Stressed correlation matrix had negative eigenvalues (min = {min_eig:.6f}); "
            "projected to nearest positive semi-definite matrix via spectral clipping."
        )

    # 4. Reconstruct Covariance Matrix
    D_stressed = np.diag(std_stressed)
    sigma_stressed = D_stressed @ R_stressed @ D_stressed
    # Symmetrize
    sigma_stressed = 0.5 * (sigma_stressed + sigma_stressed.T)

    var_stressed = float(w_vec @ sigma_stressed @ w_vec)
    stressed_vol = math.sqrt(max(0.0, var_stressed))
    vol_change = stressed_vol - base_vol

    stressed_df = pd.DataFrame(sigma_stressed, index=assets, columns=assets)

    return stressed_df, base_vol, stressed_vol, vol_change, warnings
