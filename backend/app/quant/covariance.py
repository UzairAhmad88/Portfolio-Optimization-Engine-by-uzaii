"""
Covariance and correlation matrix calculation module.

Provides mathematically rigorous, reproducible sample and population covariance
and correlation matrices for multi-asset return panels.
Preserves asset column ordering and verifies symmetry and diagonal consistency.

Independent of web frameworks or external I/O.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd


def _validate_returns_df(returns: pd.DataFrame) -> None:
    """
    Validates that the input is a non-empty pandas DataFrame with at least 1 column.
    """
    if not isinstance(returns, pd.DataFrame):
        raise TypeError(
            f"Expected pandas DataFrame for multi-asset covariance, received {type(returns).__name__}."
        )
    if returns.empty:
        raise ValueError("Return DataFrame is empty.")
    if len(returns.columns) < 1:
        raise ValueError("Return DataFrame must have at least one asset column.")


def covariance_matrix(
    returns: pd.DataFrame,
    ddof: int = 1,
    handle_na: Literal["drop_any", "pairwise"] = "drop_any",
    annualized: bool = False,
    periods_per_year: int = 252,
) -> pd.DataFrame:
    """
    Calculates sample or population covariance matrix:
        Sigma_{i,j} = (1 / (N - ddof)) * sum_{t=1}^N (r_{i,t} - mean(r_i)) * (r_{j,t} - mean(r_j))

    Parameters:
        returns: pandas DataFrame of periodic returns for multiple assets.
                 Columns are asset identifiers; rows are time periods.
        ddof: Degrees of freedom delta:
              - ddof=1: Sample covariance (unbiased).
              - ddof=0: Population covariance (maximum likelihood).
        handle_na:
              - "drop_any": (Default & Recommended) Listwise deletion. Drops any time period
                            where at least one asset is missing. Guarantees that all covariances
                            are computed over the exact same time window, preventing
                            non-positive-semidefinite artifacts caused by asynchronous panels.
              - "pairwise": Pairwise deletion. Calculates each element (i,j) using all periods
                            where both asset i and asset j have valid observations.
        annualized: If True, scales matrix by periods_per_year: Sigma_ann = Sigma * periods_per_year.
        periods_per_year: Scale factor for annualization (e.g. 252 for US, 250 for PSX).

    Returns:
        pandas DataFrame representing the symmetric NxN covariance matrix,
        preserving original column order for both index and columns.

    Raises:
        ValueError: If observations are non-finite, insufficient (< ddof + 1),
                    or if the resulting matrix fails numerical symmetry checks.

    Notes:
        In continuous markets, sample covariance matrices computed from aligned empirical data
        are positive semidefinite (rank <= min(N_assets, T_periods - 1)). If T < N, the matrix
        is singular.
    """
    _validate_returns_df(returns)

    if ddof not in (0, 1):
        raise ValueError(f"ddof must be 0 (population) or 1 (sample), got {ddof}.")
    if annualized and periods_per_year <= 0:
        raise ValueError(f"periods_per_year must be positive, got {periods_per_year}.")

    asset_names = list(returns.columns)
    min_obs = ddof + 1

    if handle_na == "drop_any":
        aligned_df = returns.dropna(how="any").astype(float)
        n_obs = len(aligned_df)
        if n_obs < min_obs:
            raise ValueError(
                f"Insufficient aligned observations for covariance calculation with ddof={ddof}: "
                f"requires at least {min_obs}, got {n_obs} after dropping missing values."
            )
        # Check finite
        mat = aligned_df.to_numpy()
        if np.isinf(mat).any():
            raise ValueError(
                "Return DataFrame contains non-finite values (inf / -inf)."
            )

        cov_arr = np.cov(mat, rowvar=False, ddof=ddof)
        # For single asset, np.cov returns a 0-d scalar array; convert to 2D
        if cov_arr.ndim == 0:
            cov_arr = np.array([[float(cov_arr)]])
        elif cov_arr.ndim == 1:
            cov_arr = cov_arr.reshape((1, 1))

    elif handle_na == "pairwise":
        # Pairwise calculation
        n_assets = len(asset_names)
        cov_arr = np.zeros((n_assets, n_assets), dtype=float)

        for i in range(n_assets):
            col_i = returns[asset_names[i]]
            for j in range(i, n_assets):
                col_j = returns[asset_names[j]]
                pair = pd.concat([col_i, col_j], axis=1).dropna().astype(float)
                if len(pair) < min_obs:
                    raise ValueError(
                        f"Insufficient pairwise observations between '{asset_names[i]}' "
                        f"and '{asset_names[j]}': requires >= {min_obs}, got {len(pair)}."
                    )
                pair_mat = pair.to_numpy()
                if np.isinf(pair_mat).any():
                    raise ValueError(
                        f"Pair ({asset_names[i]}, {asset_names[j]}) contains non-finite values."
                    )

                val = float(np.cov(pair_mat[:, 0], pair_mat[:, 1], ddof=ddof)[0, 1])
                cov_arr[i, j] = val
                cov_arr[j, i] = val
    else:
        raise ValueError(
            f"Unknown handle_na strategy '{handle_na}'. Must be 'drop_any' or 'pairwise'."
        )

    # Verify symmetry within numerical tolerance
    if not np.allclose(cov_arr, cov_arr.T, atol=1e-12, rtol=1e-10):
        raise ValueError("Computed covariance matrix failed symmetry validation.")

    # Annualization scaling
    if annualized:
        cov_arr = cov_arr * float(periods_per_year)

    cov_df = pd.DataFrame(cov_arr, index=asset_names, columns=asset_names)
    return cov_df


def correlation_matrix(
    returns: pd.DataFrame,
    ddof: int = 1,
    handle_na: Literal["drop_any", "pairwise"] = "drop_any",
) -> pd.DataFrame:
    """
    Calculates the Pearson correlation matrix for multi-asset returns:
        Rho_{i,j} = Cov(r_i, r_j) / (sigma_i * sigma_j)

    Parameters:
        returns: pandas DataFrame of periodic returns.
        ddof: Degrees of freedom (default 1 for sample).
        handle_na: "drop_any" (default) or "pairwise".

    Returns:
        pandas DataFrame representing the symmetric NxN correlation matrix,
        with 1.0 along the main diagonal.

    Raises:
        ValueError: If any asset has zero variance (constant returns) or non-finite values.
    """
    cov_df = covariance_matrix(
        returns, ddof=ddof, handle_na=handle_na, annualized=False
    )
    cov_arr = cov_df.to_numpy()
    variances = np.diag(cov_arr)

    if (variances <= 0.0).any():
        zero_var_idx = np.where(variances <= 0.0)[0]
        zero_var_assets = [cov_df.columns[i] for i in zero_var_idx]
        raise ValueError(
            f"Cannot calculate correlation: asset(s) {zero_var_assets} have non-positive variance."
        )

    stds = np.sqrt(variances)
    inv_stds = 1.0 / stds
    # Rho = D^-1 * Sigma * D^-1
    corr_arr = cov_arr * np.outer(inv_stds, inv_stds)

    # Force exact 1.0 on diagonal and enforce [-1.0, 1.0] bounds against numerical noise
    np.fill_diagonal(corr_arr, 1.0)
    corr_arr = np.clip(corr_arr, -1.0, 1.0)

    # Symmetrize against float noise
    corr_arr = 0.5 * (corr_arr + corr_arr.T)

    return pd.DataFrame(corr_arr, index=cov_df.index, columns=cov_df.columns)
