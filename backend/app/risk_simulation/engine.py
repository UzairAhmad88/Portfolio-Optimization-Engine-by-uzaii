"""
Pure mathematical engine for Monte Carlo portfolio simulation and path generation.

Independent of web frameworks, database access, or file I/O.
"""

from __future__ import annotations

import math
from typing import Any
import numpy as np

from app.risk_simulation.models import (
    DistributionBin,
    DistributionModel,
    RebalancePolicy,
    SimulationPathPoint,
)


def project_covariance_psd(cov: np.ndarray, min_eigenval: float = 1e-8) -> tuple[np.ndarray, bool]:
    """
    Checks if covariance matrix is symmetric positive semi-definite (PSD).
    If negative eigenvalues are found, projects to the nearest PSD matrix in the Frobenius norm
    via spectral clipping.

    Returns:
        tuple of (projected_covariance_matrix, was_projected_bool).
    """
    sym_cov = 0.5 * (cov + cov.T)
    eigvals, eigvecs = np.linalg.eigh(sym_cov)

    if (eigvals >= -1e-10).all():
        # Valid PSD matrix; ensure diagonal symmetry
        return sym_cov, False

    # Perform spectral clipping
    clipped_eigvals = np.maximum(eigvals, min_eigenval)
    projected = eigvecs @ np.diag(clipped_eigvals) @ eigvecs.T
    projected = 0.5 * (projected + projected.T)
    return projected, True


def generate_multivariate_returns(
    mean_vector: np.ndarray,
    cov_matrix: np.ndarray,
    horizon_days: int,
    num_paths: int,
    seed: int,
    distribution: DistributionModel = DistributionModel.MULTIVARIATE_NORMAL,
    degrees_of_freedom: float = 5.0,
) -> tuple[np.ndarray, list[str]]:
    """
    Generates joint simulated asset returns over horizon_days across num_paths.

    Parameters:
        mean_vector: 1D array of expected periodic returns of length N.
        cov_matrix: 2D array of periodic covariance of shape (N, N).
        horizon_days: Number of forward periods (T >= 1).
        num_paths: Number of simulation trajectories (M >= 2).
        seed: Random seed for exact determinism.
        distribution: MULTIVARIATE_NORMAL or MULTIVARIATE_STUDENT_T.
        degrees_of_freedom: Degrees of freedom nu for Student-t (nu > 2).

    Returns:
        tuple of:
            returns_array: Shape (num_paths, horizon_days, N) of simulated returns.
            warnings: List of diagnostic warnings emitted during generation.
    """
    warnings: list[str] = []
    n_assets = len(mean_vector)

    if cov_matrix.shape != (n_assets, n_assets):
        raise ValueError(
            f"Covariance matrix shape {cov_matrix.shape} does not match mean vector length ({n_assets})."
        )

    # 1. Check & project PSD if necessary
    psd_cov, was_projected = project_covariance_psd(cov_matrix)
    if was_projected:
        warnings.append(
            "Covariance matrix exhibited negative eigenvalues and was projected onto the positive semi-definite cone."
        )

    # 2. Factorize covariance matrix via Cholesky decomposition
    try:
        L = np.linalg.cholesky(psd_cov)
    except np.linalg.LinAlgError:
        # Fallback to spectral square root factor: L = Q * sqrt(Lambda)
        eigvals, eigvecs = np.linalg.eigh(psd_cov)
        pos_eigvals = np.maximum(eigvals, 1e-9)
        L = eigvecs @ np.diag(np.sqrt(pos_eigvals))
        warnings.append("Cholesky factorization required spectral fallback factor decomposition.")

    # 3. Initialize modern NumPy Random Generator
    rng = np.random.default_rng(seed)

    # 4. Generate standard normal draws: shape (num_paths, horizon_days, n_assets)
    z = rng.standard_normal((num_paths, horizon_days, n_assets))

    # 5. Transform based on distribution
    if distribution == DistributionModel.MULTIVARIATE_NORMAL:
        # r = mu + z @ L.T
        correlated_shocks = z @ L.T
        returns = mean_vector + correlated_shocks

    elif distribution == DistributionModel.MULTIVARIATE_STUDENT_T:
        nu = float(degrees_of_freedom)
        if nu <= 2.0:
            raise ValueError(f"Student-t degrees of freedom must be strictly > 2.0, got {nu}.")

        # To preserve covariance Sigma: Cov(X) = (nu / (nu - 2)) * ScaleMatrix
        # ScaleMatrix = ((nu - 2) / nu) * Sigma => scale factor = sqrt((nu - 2) / nu)
        scale_adjustment = math.sqrt((nu - 2.0) / nu)

        # W ~ Chi2(nu), drawn for each path and time step: shape (num_paths, horizon_days, 1)
        w = rng.chisquare(df=nu, size=(num_paths, horizon_days, 1))
        # Prevent division by zero
        w = np.maximum(w, 1e-12)

        # Multiplier = sqrt(nu / W) * scale_adjustment
        t_multiplier = np.sqrt(nu / w) * scale_adjustment

        correlated_shocks = (z @ L.T) * t_multiplier
        returns = mean_vector + correlated_shocks

    else:
        raise ValueError(f"Unsupported distribution model: {distribution}.")

    return returns, warnings


def simulate_portfolio_wealth(
    initial_capital: float,
    asset_weights: np.ndarray,
    simulated_returns: np.ndarray,
    rebalance_policy: RebalancePolicy = RebalancePolicy.BUY_AND_HOLD,
) -> np.ndarray:
    """
    Compounds portfolio wealth over the simulation horizon across all paths.

    Parameters:
        initial_capital: Baseline portfolio value V_0 > 0.
        asset_weights: 1D array of portfolio weights of length N (sum <= 1.0).
        simulated_returns: 3D array of returns of shape (num_paths, horizon_days, N).
        rebalance_policy: BUY_AND_HOLD or CONSTANT_WEIGHTS.

    Returns:
        wealth_paths: 2D array of shape (num_paths, horizon_days + 1) where day 0 is initial_capital.
    """
    num_paths, horizon_days, n_assets = simulated_returns.shape
    if len(asset_weights) != n_assets:
        raise ValueError(f"Weight vector length {len(asset_weights)} != assets {n_assets}.")

    total_weight = float(np.sum(asset_weights))
    if total_weight > 1.0 + 1e-6:
        raise ValueError(f"Sum of asset weights ({total_weight:.4f}) cannot exceed 1.0.")

    # Cash reserve
    cash = max(0.0, initial_capital * (1.0 - total_weight))
    initial_asset_values = initial_capital * asset_weights  # shape (N,)

    wealth_paths = np.empty((num_paths, horizon_days + 1), dtype=float)
    wealth_paths[:, 0] = initial_capital

    if rebalance_policy == RebalancePolicy.BUY_AND_HOLD:
        # Multiplicative compounding of individual asset values
        # Asset values at t=0: shape (num_paths, N)
        current_assets = np.tile(initial_asset_values, (num_paths, 1))

        for t in range(horizon_days):
            ret_t = simulated_returns[:, t, :]  # shape (num_paths, N)
            # Limited liability floor at 0.0
            current_assets = np.maximum(0.0, current_assets * (1.0 + ret_t))
            wealth_paths[:, t + 1] = cash + np.sum(current_assets, axis=1)

    elif rebalance_policy == RebalancePolicy.CONSTANT_WEIGHTS:
        # Constant weight rebalancing: portfolio return = sum(w_i * r_{i,t})
        weights_2d = asset_weights.reshape(1, n_assets)
        current_wealth = np.full(num_paths, initial_capital, dtype=float)

        for t in range(horizon_days):
            ret_t = simulated_returns[:, t, :]  # shape (num_paths, N)
            port_ret_t = np.sum(ret_t * weights_2d, axis=1)  # shape (num_paths,)
            # Wealth compounds with port_ret_t; floors at cash if total loss
            current_wealth = np.maximum(cash, current_wealth * (1.0 + port_ret_t))
            wealth_paths[:, t + 1] = current_wealth

    else:
        raise ValueError(f"Unsupported rebalance policy: {rebalance_policy}.")

    return wealth_paths


def compute_distribution_histogram(
    values: np.ndarray,
    num_bins: int = 30,
) -> list[DistributionBin]:
    """
    Computes histogram bins with counts and relative frequencies for values array.
    """
    if len(values) == 0:
        return []

    counts, bin_edges = np.histogram(values, bins=num_bins)
    total_count = len(values)

    bins: list[DistributionBin] = []
    for i in range(len(counts)):
        bins.append(
            DistributionBin(
                bin_start=float(bin_edges[i]),
                bin_end=float(bin_edges[i + 1]),
                count=int(counts[i]),
                relative_frequency=float(counts[i] / total_count),
            )
        )
    return bins


def downsample_trajectories(
    wealth_paths: np.ndarray,
    max_sample_paths: int = 25,
) -> list[SimulationPathPoint]:
    """
    Constructs trajectory summary across the horizon containing:
    - Median portfolio value
    - 5th percentile
    - 95th percentile
    - Up to max_sample_paths individual simulated paths
    """
    num_paths, num_days = wealth_paths.shape
    sample_indices = np.linspace(0, num_paths - 1, min(max_sample_paths, num_paths), dtype=int)

    trajectory: list[SimulationPathPoint] = []
    for day in range(num_days):
        day_values = wealth_paths[:, day]
        median_val = float(np.median(day_values))
        p5_val = float(np.percentile(day_values, 5))
        p95_val = float(np.percentile(day_values, 95))
        samples = [float(wealth_paths[idx, day]) for idx in sample_indices]

        trajectory.append(
            SimulationPathPoint(
                day=day,
                median_value=median_val,
                percentile_5=p5_val,
                percentile_95=p95_val,
                sample_paths=samples,
            )
        )

    return trajectory
