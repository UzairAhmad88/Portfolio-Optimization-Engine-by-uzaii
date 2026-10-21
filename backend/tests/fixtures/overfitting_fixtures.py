"""
Literature-verified analytical fixtures and synthetic return panels for Stage 33
backtest overfitting diagnostics, Deflated Sharpe Ratio (DSR), and CSCV.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class BaileyLopezDePradoFixture:
    """
    Standard benchmark case from Bailey & Lopez de Prado (2014),
    "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality".
    """
    n_trials: int = 100
    variance_trials: float = 0.25  # Std of trials = 0.5
    mean_trials: float = 0.0
    n_observations: int = 1260     # 5 years daily data
    skewness: float = 0.0
    kurtosis: float = 3.0          # Pearson kurtosis (Gaussian)
    nominal_sharpe: float = 1.0    # Annualized sample Sharpe ratio
    expected_sr_star_approx: float = 1.265389  # Expected max SR under H0
    expected_dsr_approx: float = 0.000000001   # Effectively zero (false discovery rejected)


@dataclass(frozen=True)
class NonGaussianFixture:
    """
    Fat-tailed, negatively skewed strategy trial to verify higher-moment corrections.
    """
    n_trials: int = 25
    variance_trials: float = 0.16  # Std of trials = 0.4
    mean_trials: float = 0.2
    n_observations: int = 756      # 3 years
    skewness: float = -1.2         # Strong negative crash risk
    kurtosis: float = 7.5          # Leptokurtic / fat-tailed
    nominal_sharpe: float = 1.5


def generate_synthetic_white_noise_panel(
    n_observations: int = 1260,
    n_trials: int = 50,
    seed: int = 42,
) -> np.ndarray:
    """
    Generates a T x N panel of uncorrelated zero-mean Gaussian returns.
    True underlying Sharpe ratio is exactly 0.0 for all strategies.
    Any high In-Sample Sharpe is pure selection bias / overfitting.
    """
    rng = np.random.default_rng(seed)
    return rng.normal(loc=0.0, scale=0.01, size=(n_observations, n_trials))


def generate_synthetic_alpha_panel(
    n_observations: int = 1260,
    n_trials: int = 50,
    alpha_strategy_index: int = 0,
    annualized_alpha_sharpe: float = 2.5,
    seed: int = 42,
) -> np.ndarray:
    """
    Generates a T x N panel where one designated strategy possesses genuine alpha,
    while the remaining N - 1 strategies are white noise.
    
    annualized_alpha_sharpe = 2.5 with 16% annualized volatility:
    daily volatility = 0.16 / sqrt(252) ~= 0.010079
    daily mean = 2.5 * 0.16 / 252 ~= 0.001587
    """
    panel = generate_synthetic_white_noise_panel(n_observations, n_trials, seed)
    daily_vol = 0.01
    daily_drift = (annualized_alpha_sharpe / math.sqrt(252.0)) * daily_vol
    panel[:, alpha_strategy_index] += daily_drift
    return panel


def generate_identical_runs_panel(
    n_observations: int = 500,
    n_trials: int = 10,
    seed: int = 42,
) -> np.ndarray:
    """
    Generates a T x N panel where all trials are identical copies.
    Cross-sectional variance V is exactly 0.0.
    """
    rng = np.random.default_rng(seed)
    single_series = rng.normal(loc=0.0005, scale=0.01, size=(n_observations, 1))
    return np.repeat(single_series, n_trials, axis=1)
