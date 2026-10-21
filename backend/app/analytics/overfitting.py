"""
Pure mathematical numerical computation engine for backtest overfitting diagnostics,
Deflated Sharpe Ratio (DSR), Minimum Backtest Length (MinBTL), Combinatorially Symmetric
Cross-Validation (CSCV), and Probability of Backtest Overfitting (PBO).

References:
- Bailey, D. H., & Lopez de Prado, M. (2014). The Deflated Sharpe Ratio: Correcting for
  Selection Bias, Backtest Overfitting and Non-Normality. Journal of Portfolio Management, 40(5), 94-107.
- Bailey, D. H., Borwein, J. M., Lopez de Prado, M., & Zhu, Q. J. (2016). The Probability of
  Backtest Overfitting. Journal of Computational Finance, 20(4), 39-69.
- Mertens, E. (2002). Comments on Why Measure Risk?: The Performance of Portfolios.
- Lo, A. W. (2002). The Statistics of Sharpe Ratios. Financial Analysts Journal, 58(4), 36-52.
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as stats

from app.research.overfitting_models import (
    CSCVCombinationsPoint,
    CSCVHistogramBin,
    DegradationRegression,
    OverfittingDiagnosticsResponse,
    RunOverfittingSummary,
    classify_pbo_risk,
)

EULER_MASCHERONI: float = 0.5772156649015328606


def calculate_expected_maximum_sharpe(
    n_trials: int,
    variance: float,
    mean: float = 0.0,
) -> float:
    """
    Computes the expected maximum Sharpe ratio under the null hypothesis of zero true alpha
    across N independent or weakly correlated strategy trials using Extreme Value Theory (EVT).

    Equation (Bailey & Lopez de Prado, 2014, Eq. 6):
        SR* = mean + sqrt(V) * [ (1 - gamma) * Phi^{-1}(1 - 1/N) + gamma * Phi^{-1}(1 - 1/(N*e)) ]

    Parameters:
        n_trials: Integer number of strategy trials evaluated (N >= 1).
        variance: Cross-sectional sample variance of trial Sharpe ratios (V >= 0.0).
        mean: Expected benchmark Sharpe ratio (default 0.0).

    Returns:
        float: Expected maximum Sharpe ratio SR*.

    Raises:
        ValueError: If n_trials < 1, variance < 0.0, or inputs are non-finite.
    """
    if not np.isfinite(n_trials) or not np.isfinite(variance) or not np.isfinite(mean):
        raise ValueError("Inputs to calculate_expected_maximum_sharpe must be finite.")
    if n_trials < 1:
        raise ValueError(f"n_trials must be at least 1, got {n_trials}.")
    if variance < 0.0:
        raise ValueError(f"variance cannot be negative, got {variance}.")

    if n_trials == 1 or variance <= 0.0:
        return float(mean)

    std = math.sqrt(variance)
    p1 = 1.0 - 1.0 / n_trials
    p2 = 1.0 - 1.0 / (n_trials * math.e)

    # Protect against floating point truncation near 1.0
    p1 = min(max(p1, 1e-15), 1.0 - 1e-15)
    p2 = min(max(p2, 1e-15), 1.0 - 1e-15)

    z1 = float(stats.norm.ppf(p1))
    z2 = float(stats.norm.ppf(p2))

    expected_z = (1.0 - EULER_MASCHERONI) * z1 + EULER_MASCHERONI * z2
    return float(mean + std * expected_z)


def calculate_deflated_sharpe_ratio(
    sharpe: float,
    trials_sharpes: list[float] | np.ndarray,
    n_observations: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    annualization_factor: int = 1,
) -> float:
    """
    Computes the Deflated Sharpe Ratio (DSR), which is the probability that the observed
    Sharpe ratio exceeds the expected maximum Sharpe ratio under selection bias, adjusted
    for non-normality (skewness and kurtosis) and sample length.

    Equation (Bailey & Lopez de Prado, 2014, Eq. 8):
        Z = (SR - SR*) * sqrt(T - 1) / sqrt(1 - gamma3 * SR + ((gamma4 - 1)/4) * SR^2)
        DSR = Phi(Z)

    Parameters:
        sharpe: Observed sample Sharpe ratio of the selected strategy.
        trials_sharpes: Collection of trial Sharpe ratios evaluated (length N).
        n_observations: Track record length T in observations (T >= 2).
        skewness: Sample return skewness gamma3 (0 for Gaussian).
        kurtosis: Sample return Pearson kurtosis gamma4 (3 for Gaussian).
        annualization_factor: Periods per year (e.g. 252 for daily). If > 1, Sharpe inputs
                              are de-annualized to periodic frequency for scale-invariant testing.

    Returns:
        float: Deflated Sharpe Ratio probability in [0.0, 1.0].
    """
    if not np.isfinite(sharpe) or not np.isfinite(skewness) or not np.isfinite(kurtosis):
        raise ValueError("Inputs to calculate_deflated_sharpe_ratio must be finite.")
    if n_observations < 2:
        raise ValueError(f"n_observations must be at least 2, got {n_observations}.")
    if annualization_factor < 1:
        raise ValueError(f"annualization_factor must be at least 1, got {annualization_factor}.")

    trials_arr = np.asarray(trials_sharpes, dtype=float)
    if trials_arr.size == 0:
        raise ValueError("trials_sharpes cannot be empty.")
    if not np.all(np.isfinite(trials_arr)):
        raise ValueError("trials_sharpes contains non-finite values.")

    n_trials = len(trials_arr)
    if n_trials <= 1:
        sr_star = 0.0
    else:
        var_trials = float(np.var(trials_arr, ddof=1))
        mean_trials = float(np.mean(trials_arr))
        sr_star = calculate_expected_maximum_sharpe(n_trials, var_trials, mean_trials)

    # De-annualize to periodic frequency if annualization factor > 1
    if annualization_factor > 1:
        sqrt_q = math.sqrt(annualization_factor)
        s_p = sharpe / sqrt_q
        s_star_p = sr_star / sqrt_q
    else:
        s_p = sharpe
        s_star_p = sr_star

    denom_sq = 1.0 - skewness * s_p + ((kurtosis - 1.0) / 4.0) * (s_p ** 2)
    denom = math.sqrt(max(denom_sq, 1e-12))

    z = (s_p - s_star_p) * math.sqrt(n_observations - 1) / denom
    return float(stats.norm.cdf(z))


def calculate_minimum_backtest_length(
    sharpe: float,
    trials_sharpes: list[float] | np.ndarray,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    alpha: float = 0.05,
    annualization_factor: int = 1,
) -> float:
    """
    Calculates the Minimum Backtest Length (MinBTL) in periodic observations required
    for the observed Sharpe ratio to reject false discovery at significance level alpha.

    Equation:
        MinBTL = 1 + [1 - gamma3 * SR + ((gamma4 - 1)/4) * SR^2] * (Z_alpha / (SR - SR*))^2

    Returns:
        float: Minimum observations T*. Returns float('inf') if sharpe <= sr_star.
    """
    if not np.isfinite(sharpe) or not np.isfinite(skewness) or not np.isfinite(kurtosis):
        raise ValueError("Inputs to calculate_minimum_backtest_length must be finite.")
    if alpha <= 0.0 or alpha >= 0.5:
        raise ValueError(f"alpha must be in (0.0, 0.5), got {alpha}.")
    if annualization_factor < 1:
        raise ValueError(f"annualization_factor must be at least 1, got {annualization_factor}.")

    trials_arr = np.asarray(trials_sharpes, dtype=float)
    if trials_arr.size == 0:
        raise ValueError("trials_sharpes cannot be empty.")
    if not np.all(np.isfinite(trials_arr)):
        raise ValueError("trials_sharpes contains non-finite values.")

    n_trials = len(trials_arr)
    if n_trials <= 1:
        sr_star = 0.0
    else:
        var_trials = float(np.var(trials_arr, ddof=1))
        mean_trials = float(np.mean(trials_arr))
        sr_star = calculate_expected_maximum_sharpe(n_trials, var_trials, mean_trials)

    if annualization_factor > 1:
        sqrt_q = math.sqrt(annualization_factor)
        s_p = sharpe / sqrt_q
        s_star_p = sr_star / sqrt_q
    else:
        s_p = sharpe
        s_star_p = sr_star

    excess = s_p - s_star_p
    if excess <= 1e-12:
        return float("inf")

    z_alpha = float(stats.norm.ppf(1.0 - alpha))
    denom_sq = 1.0 - skewness * s_p + ((kurtosis - 1.0) / 4.0) * (s_p ** 2)
    denom_sq = max(denom_sq, 1e-12)

    min_obs = 1.0 + denom_sq * ((z_alpha / excess) ** 2)
    return float(min_obs)


def run_combinatorial_cross_validation(
    returns_matrix: np.ndarray | pd.DataFrame,
    n_slices: int = 16,
    run_ids: list[str] | None = None,
    annualization_factor: int = 252,
) -> dict[str, Any]:
    """
    Executes Combinatorially Symmetric Cross-Validation (CSCV) across an aligned return panel.

    Parameters:
        returns_matrix: T x N matrix of daily returns (T observations, N strategies).
        n_slices: S contiguous temporal partitions (even integer, 4 <= S <= 16).
        run_ids: Optional list of N strategy identifiers.
        annualization_factor: Factor to annualize Sharpe ratios (default 252).

    Returns:
        dict containing PBO, degradation slope, combinations sample, rank histogram, and run summaries.
    """
    if isinstance(returns_matrix, pd.DataFrame):
        arr = returns_matrix.to_numpy(dtype=float)
    else:
        arr = np.asarray(returns_matrix, dtype=float)

    if arr.ndim != 2:
        raise ValueError(f"returns_matrix must be 2-dimensional (T x N), got shape {arr.shape}.")
    T, N = arr.shape
    if T < 20:
        raise ValueError(f"returns_matrix requires at least 20 observations, got {T}.")
    if N < 2:
        raise ValueError(f"CSCV requires at least 2 strategy columns, got {N}.")
    if not np.all(np.isfinite(arr)):
        raise ValueError("returns_matrix contains non-finite values (NaN or Inf).")

    if n_slices % 2 != 0:
        raise ValueError(f"n_slices must be an even integer, got {n_slices}.")
    if n_slices < 4 or n_slices > 16:
        raise ValueError(f"n_slices must be between 4 and 16, got {n_slices}.")
    if T < 2 * n_slices:
        raise ValueError(f"Observations T={T} too short for S={n_slices} slices (requires at least {2 * n_slices}).")

    if run_ids is None:
        strategy_ids = [f"strategy_{i+1}" for i in range(N)]
    else:
        if len(run_ids) != N:
            raise ValueError(f"run_ids length ({len(run_ids)}) does not match strategy count ({N}).")
        strategy_ids = [str(r) for r in run_ids]

    k = n_slices // 2
    slice_indices = np.array_split(np.arange(T), n_slices)
    slice_lens = np.array([len(s) for s in slice_indices], dtype=float)

    # Pre-aggregate slice sums and slice sum of squares (vectorized precomputation)
    slice_sums = np.zeros((n_slices, N), dtype=float)
    slice_sum_sqs = np.zeros((n_slices, N), dtype=float)

    for s_idx, s in enumerate(slice_indices):
        sub = arr[s, :]
        slice_sums[s_idx, :] = np.sum(sub, axis=0)
        slice_sum_sqs[s_idx, :] = np.sum(sub ** 2, axis=0)

    # Generate all C = binom(S, S/2) combinations
    comb_list = list(combinations(range(n_slices), k))
    C = len(comb_list)

    # Binary combination masks
    is_mask = np.zeros((C, n_slices), dtype=bool)
    for c_idx, c in enumerate(comb_list):
        is_mask[c_idx, list(c)] = True
    oos_mask = ~is_mask

    # Fast matrix multiplication for moments across all C combinations
    is_sums = is_mask.astype(float) @ slice_sums
    is_sum_sqs = is_mask.astype(float) @ slice_sum_sqs
    is_lens = is_mask.astype(float) @ slice_lens

    oos_sums = oos_mask.astype(float) @ slice_sums
    oos_sum_sqs = oos_mask.astype(float) @ slice_sum_sqs
    oos_lens = oos_mask.astype(float) @ slice_lens

    # Annualized In-Sample Sharpe Ratios: C x N
    sqrt_q = math.sqrt(annualization_factor)
    is_means = is_sums / is_lens[:, None]
    is_vars = (is_sum_sqs - (is_sums ** 2) / is_lens[:, None]) / np.maximum(is_lens[:, None] - 1.0, 1.0)
    is_stds = np.sqrt(np.maximum(is_vars, 1e-12))
    is_sharpes = (is_means / is_stds) * sqrt_q

    # Annualized Out-of-Sample Sharpe Ratios: C x N
    oos_means = oos_sums / oos_lens[:, None]
    oos_vars = (oos_sum_sqs - (oos_sums ** 2) / oos_lens[:, None]) / np.maximum(oos_lens[:, None] - 1.0, 1.0)
    oos_stds = np.sqrt(np.maximum(oos_vars, 1e-12))
    oos_sharpes = (oos_means / oos_stds) * sqrt_q

    # In-sample selection: best_is_idx = argmax_n IS_Sharpe (deterministic tie breaking: first index)
    best_is_idx = np.argmax(is_sharpes, axis=1)

    best_is_sharpes = is_sharpes[np.arange(C), best_is_idx]
    best_oos_sharpes = oos_sharpes[np.arange(C), best_is_idx]

    # Out-of-sample rank evaluation:
    # rank = sum_j (oos_sharpes[c, j] <= oos_sharpes[c, best_is_idx])
    # Relative rank: omega_bar_c = rank / (N + 1)
    ranks = np.sum(oos_sharpes <= best_oos_sharpes[:, None], axis=1)
    rel_ranks = ranks / (N + 1.0)

    # Probability of Backtest Overfitting (PBO):
    # Fraction of combinations where relative rank <= 0.5 (below-median out-of-sample performance)
    is_overfitted_arr = rel_ranks <= 0.5
    pbo = float(np.mean(is_overfitted_arr))

    # OLS Performance Degradation Regression: OOS Sharpe on IS Sharpe
    if np.var(best_is_sharpes) > 1e-12:
        slope, intercept, r_val, p_val, std_err = stats.linregress(best_is_sharpes, best_oos_sharpes)
        deg_reg = DegradationRegression(
            slope=float(slope),
            intercept=float(intercept),
            r_squared=float(r_val ** 2),
            p_value=float(p_val) if np.isfinite(p_val) else None,
            std_err=float(std_err) if np.isfinite(std_err) else None,
        )
    else:
        deg_reg = DegradationRegression(
            slope=0.0,
            intercept=float(np.mean(best_oos_sharpes)),
            r_squared=0.0,
            p_value=1.0,
            std_err=0.0,
        )

    # Combinations sampling for visualization (sub-sample if C > 500)
    max_sample = 500
    if C <= max_sample:
        sampled_indices = list(range(C))
    else:
        sampled_indices = np.linspace(0, C - 1, max_sample, dtype=int).tolist()

    comb_sample = [
        CSCVCombinationsPoint(
            combination_id=int(idx),
            selected_run_id=strategy_ids[best_is_idx[idx]],
            is_sharpe=float(best_is_sharpes[idx]),
            oos_sharpe=float(best_oos_sharpes[idx]),
            oos_rank=int(ranks[idx]),
            relative_rank=float(rel_ranks[idx]),
            is_overfitted=bool(is_overfitted_arr[idx]),
        )
        for idx in sampled_indices
    ]

    # Rank Distribution Histogram (10 standard decile bins across [0.0, 1.0])
    bin_edges = np.linspace(0.0, 1.0, 11)
    hist_bins: list[CSCVHistogramBin] = []
    for b_idx in range(10):
        b_start = float(bin_edges[b_idx])
        b_end = float(bin_edges[b_idx + 1])
        if b_idx == 9:
            in_bin = (rel_ranks >= b_start) & (rel_ranks <= b_end)
        else:
            in_bin = (rel_ranks >= b_start) & (rel_ranks < b_end)
        b_count = int(np.sum(in_bin))
        hist_bins.append(
            CSCVHistogramBin(
                bin_start=round(b_start, 2),
                bin_end=round(b_end, 2),
                count=b_count,
                relative_frequency=float(b_count / C),
            )
        )

    # Per-run summary
    # Full sample annualized nominal Sharpe for each strategy
    full_means = np.mean(arr, axis=0)
    full_vars = np.var(arr, axis=0, ddof=1)
    full_stds = np.sqrt(np.maximum(full_vars, 1e-12))
    nominal_sharpes = (full_means / full_stds) * sqrt_q

    runs_summary: list[RunOverfittingSummary] = []
    for s_i in range(N):
        selected_mask = (best_is_idx == s_i)
        sel_count = int(np.sum(selected_mask))
        sel_freq = float(sel_count / C)

        if sel_count > 0:
            mean_oos_sr = float(np.mean(oos_sharpes[selected_mask, s_i]))
            mean_oos_rk = float(np.mean(rel_ranks[selected_mask]))
        else:
            mean_oos_sr = None
            mean_oos_rk = None

        runs_summary.append(
            RunOverfittingSummary(
                run_id=strategy_ids[s_i],
                run_number=s_i + 1,
                nominal_sharpe=float(nominal_sharpes[s_i]),
                selection_frequency_is=sel_freq,
                mean_oos_sharpe_when_selected=mean_oos_sr,
                mean_oos_rank_when_selected=mean_oos_rk,
            )
        )

    return {
        "C": C,
        "pbo": pbo,
        "degradation_regression": deg_reg,
        "combinations_sample": comb_sample,
        "rank_distribution": hist_bins,
        "runs_summary": runs_summary,
        "nominal_sharpes": nominal_sharpes,
        "best_is_idx": best_is_idx,
        "best_is_sharpes": best_is_sharpes,
        "best_oos_sharpes": best_oos_sharpes,
        "rel_ranks": rel_ranks,
    }


def compute_overfitting_diagnostics(
    returns_matrix: np.ndarray | pd.DataFrame,
    run_metadata: list[dict[str, Any]] | None = None,
    n_slices: int = 16,
    alpha: float = 0.05,
    annualization_factor: int = 252,
    experiment_id: str = "exp-default",
    experiment_name: str = "Research Experiment",
    strategy_type: str = "target_weights",
    dataset_id: str = "dataset-default",
    snapshot_id: str | None = None,
) -> OverfittingDiagnosticsResponse:
    """
    Integrated calculation orchestrator returning a complete OverfittingDiagnosticsResponse.

    Parameters:
        returns_matrix: T x N aligned daily returns matrix.
        run_metadata: Optional list of dicts with 'run_id' and 'run_number' for each column.
        n_slices: Partition count S (default 16).
        alpha: Significance level threshold (default 0.05).
        annualization_factor: Return annualization factor (default 252).
        experiment_id: UUID of the parent experiment.
        experiment_name: Display name of the experiment.
        strategy_type: Strategy archetype.
        dataset_id: Target dataset UUID.
        snapshot_id: Dataset snapshot UUID (if bound).

    Returns:
        OverfittingDiagnosticsResponse: Validated Pydantic response contract.
    """
    if isinstance(returns_matrix, pd.DataFrame):
        arr = returns_matrix.to_numpy(dtype=float)
    else:
        arr = np.asarray(returns_matrix, dtype=float)

    T, N = arr.shape
    if run_metadata is None:
        run_ids = [f"run_{i+1}" for i in range(N)]
        run_numbers = list(range(1, N + 1))
    else:
        if len(run_metadata) != N:
            raise ValueError(f"run_metadata length ({len(run_metadata)}) does not match column count ({N}).")
        run_ids = [str(m.get("run_id", f"run_{i+1}")) for i, m in enumerate(run_metadata)]
        run_numbers = [int(m.get("run_number", i + 1)) for i, m in enumerate(run_metadata)]

    # 1. Run CSCV evaluation
    cscv_res = run_combinatorial_cross_validation(
        returns_matrix=arr,
        n_slices=n_slices,
        run_ids=run_ids,
        annualization_factor=annualization_factor,
    )

    pbo = cscv_res["pbo"]
    pbo_risk_level = classify_pbo_risk(pbo)
    nominal_sharpes = cscv_res["nominal_sharpes"]

    # Align run_numbers in runs_summary with run_metadata
    for s_i, item in enumerate(cscv_res["runs_summary"]):
        item.run_number = run_numbers[s_i]

    # 2. Select strategy with best full-sample nominal Sharpe
    best_idx = int(np.argmax(nominal_sharpes))
    best_run_id = run_ids[best_idx]
    best_run_number = run_numbers[best_idx]
    best_nominal_sharpe = float(nominal_sharpes[best_idx])

    # 3. Higher-moment calculations on the best strategy's daily returns
    best_returns = arr[:, best_idx]
    if len(best_returns) >= 4:
        raw_skew = float(stats.skew(best_returns))
        skew = raw_skew if np.isfinite(raw_skew) else 0.0
        # Pearson kurtosis (normal = 3.0)
        raw_kurt = float(stats.kurtosis(best_returns, fisher=False))
        kurt = raw_kurt if np.isfinite(raw_kurt) else 3.0
    else:
        skew = 0.0
        kurt = 3.0

    # 4. Expected Maximum Sharpe & Deflated Sharpe Ratio
    var_trials = float(np.var(nominal_sharpes, ddof=1)) if N > 1 else 0.0
    mean_trials = float(np.mean(nominal_sharpes)) if N > 1 else best_nominal_sharpe
    expected_max_sr = calculate_expected_maximum_sharpe(N, var_trials, mean_trials)

    dsr = calculate_deflated_sharpe_ratio(
        sharpe=best_nominal_sharpe,
        trials_sharpes=nominal_sharpes,
        n_observations=T,
        skewness=skew,
        kurtosis=kurt,
        annualization_factor=annualization_factor,
    )
    is_significant = bool(dsr >= (1.0 - alpha))

    # 5. Minimum Backtest Length (MinBTL)
    min_btl_obs = calculate_minimum_backtest_length(
        sharpe=best_nominal_sharpe,
        trials_sharpes=nominal_sharpes,
        skewness=skew,
        kurtosis=kurt,
        alpha=alpha,
        annualization_factor=annualization_factor,
    )
    if math.isinf(min_btl_obs) or min_btl_obs > 1e9:
        min_btl_years = None
    else:
        min_btl_years = float(min_btl_obs / annualization_factor)

    actual_btl_years = float(T / annualization_factor)

    # 6. Advisory warnings
    warnings: list[str] = []
    if N < 10:
        warnings.append("Low strategy trial count (N < 10). Deflated Sharpe Ratio and PBO statistical power may be limited.")
    if pbo > 0.50:
        warnings.append("Severe backtest overfitting detected (PBO > 50%). The in-sample optimal strategy is more likely than not to produce below-median out-of-sample performance.")
    if cscv_res["degradation_regression"].slope <= 0.0:
        warnings.append("Non-positive performance degradation slope. In-sample optimization does not positively translate out-of-sample.")
    if min_btl_years is None:
        warnings.append("Minimum Backtest Length is unreachable: the strategy's Sharpe ratio does not exceed the expected maximum under random selection.")

    return OverfittingDiagnosticsResponse(
        experiment_id=experiment_id,
        experiment_name=experiment_name,
        strategy_type=strategy_type,
        dataset_id=dataset_id,
        snapshot_id=snapshot_id,
        evaluated_runs_count=N,
        aligned_observations_count=T,
        n_slices=n_slices,
        total_combinations_count=cscv_res["C"],
        pbo=pbo,
        pbo_risk_level=pbo_risk_level,
        best_run_id=best_run_id,
        best_run_number=best_run_number,
        best_nominal_sharpe=best_nominal_sharpe,
        expected_max_sharpe=expected_max_sr,
        deflated_sharpe_ratio=dsr,
        is_statistically_significant=is_significant,
        min_backtest_length_years=min_btl_years,
        actual_backtest_length_years=actual_btl_years,
        skewness=skew,
        kurtosis=kurt,
        degradation_regression=cscv_res["degradation_regression"],
        combinations_sample=cscv_res["combinations_sample"],
        rank_distribution=cscv_res["rank_distribution"],
        runs_summary=cscv_res["runs_summary"],
        warnings=warnings,
    )
