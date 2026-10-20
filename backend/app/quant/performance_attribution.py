"""
Pure Numerical Financial Mathematics Core for Multi-Asset Performance Attribution,
Brinson-Fachler Active Return Decomposition, Multi-Period Cariño Linking,
and Systematic Factor Risk & Return Attribution.

Implements:
1. Single-Period Brinson-Hood-Beebower (BHB) & Brinson-Fachler (BF) Attribution.
2. Exact Allocation Effect, Selection Effect, and Interaction Effect reconciliation.
3. Multi-Period Cariño (1999) logarithmic linking algorithm eliminating residual compounding drift.
4. Sector/Segment aggregation from asset-level returns and weights.
5. Systematic Barra Multi-Factor active return and active tracking error risk decomposition.
"""

from __future__ import annotations

import math
from typing import Any, Literal
import numpy as np


def compute_single_period_brinson(
    portfolio_segment_weights: dict[str, float],
    benchmark_segment_weights: dict[str, float],
    portfolio_segment_returns: dict[str, float],
    benchmark_segment_returns: dict[str, float],
    method: Literal["brinson_fachler", "brinson_hood_beebower"] = "brinson_fachler",
) -> dict[str, Any]:
    """
    Computes single-period Brinson attribution across portfolio and benchmark segments.

    Formulas:
        R_p = sum_i w_{p,i} * R_{p,i}
        R_b = sum_i w_{b,i} * R_{b,i}
        Active Return Delta R = R_p - R_b

        Brinson-Fachler:
            Allocation Effect: A_i = (w_{p,i} - w_{b,i}) * (R_{b,i} - R_b)
            Selection Effect:  S_i = w_{b,i} * (R_{p,i} - R_{b,i})
            Interaction Effect: I_i = (w_{p,i} - w_{b,i}) * (R_{p,i} - R_{b,i})

        Brinson-Hood-Beebower:
            Allocation Effect: A_i = (w_{p,i} - w_{b,i}) * R_{b,i}
            Selection Effect:  S_i = w_{b,i} * (R_{p,i} - R_{b,i})
            Interaction Effect: I_i = (w_{p,i} - w_{b,i}) * (R_{p,i} - R_{b,i})

    Reconciliation Identity:
        sum_i A_i + sum_i S_i + sum_i I_i = R_p - R_b
    """
    all_segments = sorted(
        list(
            set(portfolio_segment_weights.keys())
            | set(benchmark_segment_weights.keys())
            | set(portfolio_segment_returns.keys())
            | set(benchmark_segment_returns.keys())
        )
    )

    # Normalize weights
    total_wp = sum(portfolio_segment_weights.get(s, 0.0) for s in all_segments)
    total_wb = sum(benchmark_segment_weights.get(s, 0.0) for s in all_segments)

    norm_wp = {
        s: (portfolio_segment_weights.get(s, 0.0) / total_wp) if total_wp > 1e-12 else 0.0
        for s in all_segments
    }
    norm_wb = {
        s: (benchmark_segment_weights.get(s, 0.0) / total_wb) if total_wb > 1e-12 else 0.0
        for s in all_segments
    }

    # Total portfolio and benchmark returns
    r_p = sum(norm_wp[s] * portfolio_segment_returns.get(s, 0.0) for s in all_segments)
    r_b = sum(norm_wb[s] * benchmark_segment_returns.get(s, 0.0) for s in all_segments)
    active_return = r_p - r_b

    segment_attributions: list[dict[str, Any]] = []
    tot_alloc = 0.0
    tot_select = 0.0
    tot_interact = 0.0

    for s in all_segments:
        wp_i = norm_wp[s]
        wb_i = norm_wb[s]
        rp_i = portfolio_segment_returns.get(s, 0.0)
        rb_i = benchmark_segment_returns.get(s, 0.0)

        if method == "brinson_fachler":
            alloc_i = (wp_i - wb_i) * (rb_i - r_b)
        else:
            alloc_i = (wp_i - wb_i) * rb_i

        select_i = wb_i * (rp_i - rb_i)
        interact_i = (wp_i - wb_i) * (rp_i - rb_i)
        total_contrib_i = alloc_i + select_i + interact_i

        tot_alloc += alloc_i
        tot_select += select_i
        tot_interact += interact_i

        segment_attributions.append({
            "segment": s,
            "portfolio_weight": float(wp_i),
            "benchmark_weight": float(wb_i),
            "active_weight": float(wp_i - wb_i),
            "portfolio_return": float(rp_i),
            "benchmark_return": float(rb_i),
            "active_segment_return": float(rp_i - rb_i),
            "allocation_effect": float(alloc_i),
            "selection_effect": float(select_i),
            "interaction_effect": float(interact_i),
            "total_contribution": float(total_contrib_i),
        })

    # Exact reconciliation check
    tot_effect = tot_alloc + tot_select + tot_interact
    reconciliation_error = abs(tot_effect - active_return)

    return {
        "method": method,
        "portfolio_return": float(r_p),
        "benchmark_return": float(r_b),
        "active_return": float(active_return),
        "total_allocation_effect": float(tot_alloc),
        "total_selection_effect": float(tot_select),
        "total_interaction_effect": float(tot_interact),
        "reconciliation_error": float(reconciliation_error),
        "segment_attributions": segment_attributions,
    }


def compute_carino_multi_period_linking(
    period_attributions: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Applies the Cariño (1999) logarithmic smoothing factor to link single-period
    Brinson attributions across multiple periods, eliminating compounding residuals.

    Mathematical Formulation:
        R_p^{cum} = prod_{t=1}^T (1 + R_{p,t}) - 1
        R_b^{cum} = prod_{t=1}^T (1 + R_{b,t}) - 1
        Delta R^{cum} = R_p^{cum} - R_b^{cum}

        a_t = [ln(1 + R_{p,t}) - ln(1 + R_{b,t})] / (R_{p,t} - R_{b,t})
        a^{cum} = [ln(1 + R_p^{cum}) - ln(1 + R_b^{cum})] / (R_p^{cum} - R_b^{cum})
        k_t = a_t / a^{cum}

    Linked Effects:
        tilde{A}_i = sum_t k_t * A_{i,t}
        tilde{S}_i = sum_t k_t * S_{i,t}
        tilde{I}_i = sum_t k_t * I_{i,t}

    Identity:
        sum_i (tilde{A}_i + tilde{S}_i + tilde{I}_i) == Delta R^{cum}
    """
    if not period_attributions:
        raise ValueError("period_attributions list cannot be empty.")

    T = len(period_attributions)

    # 1. Compute cumulative compounded returns
    cum_port_growth = 1.0
    cum_bmk_growth = 1.0

    for p in period_attributions:
        cum_port_growth *= (1.0 + float(p["portfolio_return"]))
        cum_bmk_growth *= (1.0 + float(p["benchmark_return"]))

    r_p_cum = cum_port_growth - 1.0
    r_b_cum = cum_bmk_growth - 1.0
    active_cum = r_p_cum - r_b_cum

    # 2. Compute a^{cum}
    if abs(active_cum) < 1e-12:
        a_cum = 1.0 / max(1e-12, 1.0 + r_b_cum)
    else:
        log_diff_cum = math.log(max(1e-12, 1.0 + r_p_cum)) - math.log(max(1e-12, 1.0 + r_b_cum))
        a_cum = log_diff_cum / active_cum

    # 3. Compute k_t scaling factors
    k_factors: list[float] = []
    for p in period_attributions:
        rp_t = float(p["portfolio_return"])
        rb_t = float(p["benchmark_return"])
        diff_t = rp_t - rb_t

        if abs(diff_t) < 1e-12:
            a_t = 1.0 / max(1e-12, 1.0 + rb_t)
        else:
            log_diff_t = math.log(max(1e-12, 1.0 + rp_t)) - math.log(max(1e-12, 1.0 + rb_t))
            a_t = log_diff_t / diff_t

        k_t = a_t / a_cum if abs(a_cum) > 1e-12 else 1.0
        k_factors.append(k_t)

    # 4. Accumulate linked segment contributions
    all_segments = sorted(
        list(set(seg["segment"] for p in period_attributions for seg in p["segment_attributions"]))
    )

    linked_segments: dict[str, dict[str, float]] = {
        s: {
            "allocation": 0.0,
            "selection": 0.0,
            "interaction": 0.0,
            "total_contribution": 0.0,
            "avg_portfolio_weight": 0.0,
            "avg_benchmark_weight": 0.0,
        }
        for s in all_segments
    }

    tot_linked_alloc = 0.0
    tot_linked_select = 0.0
    tot_linked_interact = 0.0

    for t_idx, p in enumerate(period_attributions):
        kt = k_factors[t_idx]
        seg_map = {seg["segment"]: seg for seg in p["segment_attributions"]}

        for s in all_segments:
            seg = seg_map.get(s, {})
            alloc_t = float(seg.get("allocation_effect", 0.0))
            select_t = float(seg.get("selection_effect", 0.0))
            interact_t = float(seg.get("interaction_effect", 0.0))
            wp_t = float(seg.get("portfolio_weight", 0.0))
            wb_t = float(seg.get("benchmark_weight", 0.0))

            scaled_alloc = kt * alloc_t
            scaled_select = kt * select_t
            scaled_interact = kt * interact_t

            linked_segments[s]["allocation"] += scaled_alloc
            linked_segments[s]["selection"] += scaled_select
            linked_segments[s]["interaction"] += scaled_interact
            linked_segments[s]["total_contribution"] += (scaled_alloc + scaled_select + scaled_interact)
            linked_segments[s]["avg_portfolio_weight"] += wp_t / T
            linked_segments[s]["avg_benchmark_weight"] += wb_t / T

            tot_linked_alloc += scaled_alloc
            tot_linked_select += scaled_select
            tot_linked_interact += scaled_interact

    tot_linked_effect = tot_linked_alloc + tot_linked_select + tot_linked_interact
    reconciliation_error = abs(tot_linked_effect - active_cum)

    segment_summary = [
        {
            "segment": s,
            "average_portfolio_weight": round(linked_segments[s]["avg_portfolio_weight"], 6),
            "average_benchmark_weight": round(linked_segments[s]["avg_benchmark_weight"], 6),
            "active_weight": round(
                linked_segments[s]["avg_portfolio_weight"] - linked_segments[s]["avg_benchmark_weight"], 6
            ),
            "linked_allocation_effect": round(linked_segments[s]["allocation"], 8),
            "linked_selection_effect": round(linked_segments[s]["selection"], 8),
            "linked_interaction_effect": round(linked_segments[s]["interaction"], 8),
            "total_contribution": round(linked_segments[s]["total_contribution"], 8),
        }
        for s in all_segments
    ]

    return {
        "cumulative_portfolio_return": round(r_p_cum, 8),
        "cumulative_benchmark_return": round(r_b_cum, 8),
        "cumulative_active_return": round(active_cum, 8),
        "linked_allocation_effect": round(tot_linked_alloc, 8),
        "linked_selection_effect": round(tot_linked_select, 8),
        "linked_interaction_effect": round(tot_linked_interact, 8),
        "reconciliation_error": round(reconciliation_error, 12),
        "segment_attribution": segment_summary,
        "k_factors": [round(k, 6) for k in k_factors],
    }


def compute_multi_period_brinson_attribution(
    price_matrix: np.ndarray,
    dates: list[str],
    tickers: list[str],
    portfolio_weights: dict[str, float],
    benchmark_weights: dict[str, float],
    segment_mapping: dict[str, str],
    frequency: Literal["daily", "weekly", "monthly"] = "monthly",
    method: Literal["brinson_fachler", "brinson_hood_beebower"] = "brinson_fachler",
) -> dict[str, Any]:
    """
    Executes full multi-period Brinson attribution from asset price time series.

    1. Computes asset returns.
    2. Groups into periodic intervals (daily, weekly, monthly).
    3. Aggregates asset weights and returns into segments (e.g. sectors or asset classes).
    4. Computes single-period Brinson attribution for each interval.
    5. Links periods via Cariño algorithm.
    """
    T, N = price_matrix.shape
    if T < 5:
        raise ValueError("Insufficient price observations for attribution analysis (min 5 bars).")

    # Asset simple returns
    asset_rets = np.zeros((T - 1, N), dtype=np.float64)
    for i in range(N):
        p = price_matrix[:, i]
        asset_rets[:, i] = (p[1:] - p[:-1]) / np.maximum(1e-12, p[:-1])

    ret_dates = dates[1:]
    ticker_to_idx = {t: i for i, t in enumerate(tickers)}

    # Map segment for each ticker
    all_segments = sorted(list(set(segment_mapping.get(t, "Other") for t in tickers)))

    # Determine sub-period interval step size
    step = 21 if frequency == "monthly" else (5 if frequency == "weekly" else 1)
    period_attributions: list[dict[str, Any]] = []
    time_series_points: list[dict[str, Any]] = []

    num_bars = len(ret_dates)
    period_starts = list(range(0, num_bars, step))

    for idx, p_start in enumerate(period_starts):
        p_end = min(num_bars, p_start + step)
        if p_start >= p_end:
            continue

        # Compounded return of each asset over the sub-period
        sub_rets = asset_rets[p_start:p_end]
        asset_compounded = np.prod(1.0 + sub_rets, axis=0) - 1.0

        # Segment weights and returns for this period
        wp_seg: dict[str, float] = {s: 0.0 for s in all_segments}
        wb_seg: dict[str, float] = {s: 0.0 for s in all_segments}
        rp_seg_weighted: dict[str, float] = {s: 0.0 for s in all_segments}
        rb_seg_weighted: dict[str, float] = {s: 0.0 for s in all_segments}

        for t in tickers:
            s = segment_mapping.get(t, "Other")
            a_idx = ticker_to_idx.get(t)
            if a_idx is None:
                continue

            ret_a = float(asset_compounded[a_idx])
            wp = float(portfolio_weights.get(t, 0.0))
            wb = float(benchmark_weights.get(t, 0.0))

            wp_seg[s] += wp
            wb_seg[s] += wb
            rp_seg_weighted[s] += wp * ret_a
            rb_seg_weighted[s] += wb * ret_a

        # Segment returns = weighted sum / segment weight
        rp_seg: dict[str, float] = {}
        rb_seg: dict[str, float] = {}
        for s in all_segments:
            rp_seg[s] = (rp_seg_weighted[s] / wp_seg[s]) if wp_seg[s] > 1e-12 else 0.0
            rb_seg[s] = (rb_seg_weighted[s] / wb_seg[s]) if wb_seg[s] > 1e-12 else 0.0

        single_attr = compute_single_period_brinson(
            portfolio_segment_weights=wp_seg,
            benchmark_segment_weights=wb_seg,
            portfolio_segment_returns=rp_seg,
            benchmark_segment_returns=rb_seg,
            method=method,
        )
        period_attributions.append(single_attr)

        time_series_points.append({
            "period_index": idx,
            "start_date": ret_dates[p_start],
            "end_date": ret_dates[p_end - 1],
            "portfolio_return": single_attr["portfolio_return"],
            "benchmark_return": single_attr["benchmark_return"],
            "active_return": single_attr["active_return"],
            "allocation_effect": single_attr["total_allocation_effect"],
            "selection_effect": single_attr["total_selection_effect"],
            "interaction_effect": single_attr["total_interaction_effect"],
        })

    # Apply Cariño multi-period linking
    linked_result = compute_carino_multi_period_linking(period_attributions)

    return {
        "method": method,
        "frequency": frequency,
        "summary": {
            "cumulative_portfolio_return": linked_result["cumulative_portfolio_return"],
            "cumulative_benchmark_return": linked_result["cumulative_benchmark_return"],
            "cumulative_active_return": linked_result["cumulative_active_return"],
            "total_allocation_effect": linked_result["linked_allocation_effect"],
            "total_selection_effect": linked_result["linked_selection_effect"],
            "total_interaction_effect": linked_result["linked_interaction_effect"],
            "reconciliation_error": linked_result["reconciliation_error"],
            "total_periods": len(period_attributions),
        },
        "segment_attribution": linked_result["segment_attribution"],
        "time_series": time_series_points,
    }


def compute_factor_attribution(
    portfolio_weights: dict[str, float],
    benchmark_weights: dict[str, float],
    asset_returns: np.ndarray,
    factor_returns: np.ndarray,
    factor_names: list[str],
) -> dict[str, Any]:
    """
    Decomposes active portfolio return and active tracking variance into
    systematic factor contributions and idiosyncratic stock selection.

    Formulation:
        R_{i, t} = alpha_i + sum_k beta_{i, k} F_{k, t} + eps_{i, t}
        Active Beta: Delta beta_k = sum_i w_{p,i} beta_{i,k} - sum_i w_{b,i} beta_{i,k}
        Factor Active Return: FactorReturn_k = Delta beta_k * mean(F_k) * 252
        Systematic Active Return = sum_k FactorReturn_k
        Specific Active Return = Delta R - Systematic Active Return

        Active Variance:
            sigma_active^2 = Delta beta^T Sigma_F Delta beta + Delta w^T Sigma_eps Delta w
    """
    T, N = asset_returns.shape
    K = factor_returns.shape[1]

    if len(factor_names) != K:
        raise ValueError(f"factor_names length ({len(factor_names)}) != K ({K})")

    # 1. Multivariate OLS factor regression for each asset
    X = np.column_stack([np.ones(T), factor_returns])  # (T, K+1)
    betas = np.zeros((N, K), dtype=np.float64)
    residuals = np.zeros((T, N), dtype=np.float64)

    for i in range(N):
        y = asset_returns[:, i]
        try:
            coeffs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
            betas[i] = coeffs[1:]
            residuals[:, i] = y - X @ coeffs
        except np.linalg.LinAlgError:
            betas[i] = 1.0 / K

    # 2. Vectorized weights
    all_tickers = sorted(list(set(portfolio_weights.keys()) | set(benchmark_weights.keys())))
    N_eff = len(all_tickers)
    wp = np.array([portfolio_weights.get(t, 0.0) for t in all_tickers], dtype=np.float64)
    wb = np.array([benchmark_weights.get(t, 0.0) for t in all_tickers], dtype=np.float64)

    wp = wp / max(1e-12, float(np.sum(wp)))
    wb = wb / max(1e-12, float(np.sum(wb)))
    delta_w = wp - wb

    # Portfolio and Benchmark returns
    port_rets = asset_returns @ wp[:N]
    bmk_rets = asset_returns @ wb[:N]

    mean_port = float(np.mean(port_rets) * 252.0)
    mean_bmk = float(np.mean(bmk_rets) * 252.0)
    active_return = mean_port - mean_bmk

    # Active betas
    beta_p = wp[:N] @ betas[:N]  # (K,)
    beta_b = wb[:N] @ betas[:N]  # (K,)
    delta_beta = beta_p - beta_b # (K,)

    mean_factors = np.mean(factor_returns, axis=0) * 252.0  # (K,)
    factor_contribs = delta_beta * mean_factors

    sys_active_return = float(np.sum(factor_contribs))
    spec_active_return = float(active_return - sys_active_return)

    # 3. Active Risk Decomposition
    cov_F = np.cov(factor_returns, rowvar=False) * 252.0
    if K == 1:
        cov_F = np.array([[float(cov_F)]])

    res_var = np.var(residuals[:N], axis=0) * 252.0
    cov_eps = np.diag(res_var)

    sys_active_var = float(delta_beta @ cov_F @ delta_beta)
    spec_active_var = float(delta_w[:N] @ cov_eps @ delta_w[:N])
    tot_active_var = max(1e-12, sys_active_var + spec_active_var)
    tot_active_risk = math.sqrt(tot_active_var)

    sys_share = (sys_active_var / tot_active_var) * 100.0
    spec_share = (spec_active_var / tot_active_var) * 100.0

    factor_breakdown = [
        {
            "factor": factor_names[k],
            "portfolio_beta": round(float(beta_p[k]), 4),
            "benchmark_beta": round(float(beta_b[k]), 4),
            "active_beta": round(float(delta_beta[k]), 4),
            "annualized_factor_return": round(float(mean_factors[k]), 4),
            "annualized_contribution": round(float(factor_contribs[k]), 6),
        }
        for k in range(K)
    ]

    return {
        "annualized_portfolio_return": round(mean_port, 6),
        "annualized_benchmark_return": round(mean_bmk, 6),
        "total_active_return": round(active_return, 6),
        "systematic_active_return": round(sys_active_return, 6),
        "specific_active_return": round(spec_active_return, 6),
        "total_tracking_error": round(tot_active_risk, 6),
        "systematic_tracking_error": round(math.sqrt(max(0.0, sys_active_var)), 6),
        "specific_tracking_error": round(math.sqrt(max(0.0, spec_active_var)), 6),
        "systematic_risk_percent": round(sys_share, 2),
        "specific_risk_percent": round(spec_share, 2),
        "factor_contributions": factor_breakdown,
    }
