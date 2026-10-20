"""
Service Layer for Factor Attribution & Factor-Constrained Portfolio Optimization.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import check_dataset_access
from app.backtesting.data import prepare_backtest_data
from app.db.models import UserModel
from app.portfolio.service import get_dataset_assets
from app.quant.returns import simple_returns
from app.quant.factor_model import (
    construct_synthetic_factors_from_returns,
    estimate_single_asset_factor_regression,
    decompose_portfolio_factor_risk,
    solve_factor_constrained_portfolio,
)
from app.quant.dynamic_factor_backtest import run_dynamic_factor_backtest
from app.factor_investing.models import (
    AssetFactorProfile,
    DynamicFactorBacktestRequest,
    DynamicFactorBacktestResponse,
    DynamicFactorBenchmarkMetrics,
    DynamicFactorEquityPoint,
    DynamicFactorExposureSeries,
    DynamicFactorRebalanceEvent,
    DynamicFactorSummaryMetrics,
    FactorAttributionRequest,
    FactorAttributionResponse,
    FactorBetaMetric,
    FactorConstrainedOptimizeRequest,
    FactorConstrainedOptimizeResponse,
    PortfolioRiskDecomposition,
)


def _load_asset_returns(
    dataset_id: str,
    current_user: UserModel,
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Loads cleaned asset returns matrix from persistent dataset, enforcing tenant permissions."""
    check_dataset_access(db, dataset_id, current_user)

    meta_assets = get_dataset_assets(dataset_id)
    if not meta_assets or len(meta_assets) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Factor analysis requires a dataset with at least 2 distinct assets.",
        )

    asset_ids = [a.asset_id for a in meta_assets]
    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=dataset_id,
        requested_assets=asset_ids,
        start_date=start_date,
        end_date=end_date,
        user=current_user,
        session=db,
        min_required_observations=20,
    )

    if clean_prices.empty or len(clean_prices.columns) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Factor analysis requires at least 2 distinct assets with valid price observations.",
        )

    returns_df = simple_returns(clean_prices).dropna()
    return returns_df, list(clean_prices.columns)


def _normalize_model_name(factor_model: str) -> str:
    if factor_model == "fama_french_3":
        return "ff3"
    if factor_model == "carhart_4":
        return "carhart4"
    return factor_model


def run_factor_attribution(
    request: FactorAttributionRequest,
    current_user: UserModel,
    db: Session,
) -> FactorAttributionResponse:
    """Executes multi-factor regression and Barra-style systematic risk decomposition."""
    returns_df, resolved_assets = _load_asset_returns(
        dataset_id=request.dataset_id,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    N = len(resolved_assets)
    R = returns_df.values  # (T, N)
    T = R.shape[0]

    factor_model_key = _normalize_model_name(request.factor_model)

    # Construct factors from returns
    F, factor_names = construct_synthetic_factors_from_returns(
        returns_df=R,
        factor_model=factor_model_key,
        num_pca_factors=request.num_pca_factors,
        risk_free_rate=request.risk_free_rate,
        annualization_factor=252,
    )
    K = len(factor_names)

    # Factor covariance annualized: (K, K)
    factor_cov_daily = np.cov(F, rowvar=False)
    if K == 1:
        factor_cov_daily = np.array([[float(factor_cov_daily)]])
    factor_cov_annual = factor_cov_daily * 252.0

    # Estimate regression for each asset
    daily_rf = request.risk_free_rate / 252.0
    asset_profiles: dict[str, AssetFactorProfile] = {}
    B = np.zeros((N, K), dtype=np.float64)
    s_eps = np.zeros(N, dtype=np.float64)

    for i, asset in enumerate(resolved_assets):
        excess_ret = R[:, i] - daily_rf
        reg = estimate_single_asset_factor_regression(
            asset_excess_returns=excess_ret,
            factors_matrix=F,
            factor_names=factor_names,
            annualization_factor=252,
        )

        for k, fname in enumerate(factor_names):
            B[i, k] = reg["betas"][fname]["beta"]
        s_eps[i] = reg["specific_variance_annualized"]

        betas_typed = {
            fname: FactorBetaMetric(**b_val)
            for fname, b_val in reg["betas"].items()
        }

        # Store profile under both canonical ID and raw ticker for convenience
        profile = AssetFactorProfile(
            alpha_annualized=reg["alpha_annualized"],
            alpha_stderr=reg["alpha_stderr"],
            alpha_tstat=reg["alpha_tstat"],
            alpha_pvalue=reg["alpha_pvalue"],
            betas=betas_typed,
            r_squared=reg["r_squared"],
            r_squared_adj=reg["r_squared_adj"],
            specific_variance_annualized=reg["specific_variance_annualized"],
            specific_volatility_annualized=reg["specific_volatility_annualized"],
        )
        asset_profiles[asset] = profile

    # Parse and validate portfolio weights
    if request.weights:
        raw_weights = []
        for asset in resolved_assets:
            w_val = request.weights.get(asset, 0.0)
            if asset not in request.weights:
                ticker = asset.split(":")[0] if ":" in asset else asset
                w_val = request.weights.get(ticker, 0.0)
            raw_weights.append(max(0.0, float(w_val)))
        total_w = sum(raw_weights)
        if total_w <= 1e-6:
            weights = np.full(N, 1.0 / N, dtype=np.float64)
        else:
            weights = np.array(raw_weights, dtype=np.float64) / total_w
    else:
        weights = np.full(N, 1.0 / N, dtype=np.float64)

    weights_dict = {asset: float(round(weights[i], 6)) for i, asset in enumerate(resolved_assets)}

    # Decompose portfolio factor risk
    decomp = decompose_portfolio_factor_risk(
        weights=weights,
        factor_loadings=B,
        factor_covariance=factor_cov_annual,
        specific_variances=s_eps,
        factor_names=factor_names,
    )

    factor_cov_list = [[float(round(val, 8)) for val in row] for row in factor_cov_annual]

    return FactorAttributionResponse(
        dataset_id=request.dataset_id,
        factor_model=request.factor_model,
        factors=factor_names,
        assets=resolved_assets,
        weights=weights_dict,
        asset_profiles=asset_profiles,
        risk_decomposition=PortfolioRiskDecomposition(**decomp),
        factor_covariance=factor_cov_list,
    )


def run_factor_constrained_optimization(
    request: FactorConstrainedOptimizeRequest,
    current_user: UserModel,
    db: Session,
) -> FactorConstrainedOptimizeResponse:
    """Solves factor-constrained portfolio optimization."""
    returns_df, resolved_assets = _load_asset_returns(
        dataset_id=request.dataset_id,
        current_user=current_user,
        db=db,
    )

    N = len(resolved_assets)
    R = returns_df.values
    mu_annual = np.mean(R, axis=0) * 252.0

    factor_model_key = _normalize_model_name(request.factor_model)

    # Construct factors
    F, factor_names = construct_synthetic_factors_from_returns(
        returns_df=R,
        factor_model=factor_model_key,
        num_pca_factors=request.num_pca_factors,
        risk_free_rate=request.risk_free_rate,
        annualization_factor=252,
    )
    K = len(factor_names)

    factor_cov_daily = np.cov(F, rowvar=False)
    if K == 1:
        factor_cov_daily = np.array([[float(factor_cov_daily)]])
    factor_cov_annual = factor_cov_daily * 252.0

    # Estimate loadings and specific variances
    daily_rf = request.risk_free_rate / 252.0
    B = np.zeros((N, K), dtype=np.float64)
    s_eps = np.zeros(N, dtype=np.float64)

    for i, asset in enumerate(resolved_assets):
        excess_ret = R[:, i] - daily_rf
        reg = estimate_single_asset_factor_regression(
            asset_excess_returns=excess_ret,
            factors_matrix=F,
            factor_names=factor_names,
            annualization_factor=252,
        )
        for k, fname in enumerate(factor_names):
            B[i, k] = reg["betas"][fname]["beta"]
        s_eps[i] = reg["specific_variance_annualized"]

    # Parse factor constraints
    factor_constraints_parsed: dict[str, tuple[float | None, float | None]] = {}
    if request.factor_constraints:
        for fname, bound in request.factor_constraints.items():
            factor_constraints_parsed[fname] = (bound.min_beta, bound.max_beta)

    # Solve optimization
    w_opt, is_feasible, solver_msg = solve_factor_constrained_portfolio(
        expected_returns=mu_annual,
        factor_loadings=B,
        factor_covariance=factor_cov_annual,
        specific_variances=s_eps,
        factor_names=factor_names,
        objective=request.objective,
        factor_constraints=factor_constraints_parsed,
        min_weight=request.min_weight,
        max_weight=request.max_weight,
        risk_free_rate=request.risk_free_rate,
        risk_aversion=request.risk_aversion,
    )

    weights_dict = {asset: float(round(w_opt[i], 6)) for i, asset in enumerate(resolved_assets)}

    decomp = decompose_portfolio_factor_risk(
        weights=w_opt,
        factor_loadings=B,
        factor_covariance=factor_cov_annual,
        specific_variances=s_eps,
        factor_names=factor_names,
    )

    return FactorConstrainedOptimizeResponse(
        dataset_id=request.dataset_id,
        factor_model=request.factor_model,
        objective=request.objective,
        assets=resolved_assets,
        weights=weights_dict,
        portfolio_betas=decomp["portfolio_betas"],
        risk_decomposition=PortfolioRiskDecomposition(**decomp),
        is_feasible=is_feasible,
        solver_status="Optimal" if is_feasible else "Infeasible",
        solver_message=solver_msg,
    )


def execute_dynamic_factor_backtest(
    request: DynamicFactorBacktestRequest,
    current_user: UserModel,
    db: Session,
) -> DynamicFactorBacktestResponse:
    """
    Executes an institutional walk-forward dynamic factor backtest simulation with zero look-ahead bias.
    """
    check_dataset_access(db, request.dataset_id, current_user)

    returns_df, resolved_assets = _load_asset_returns(
        dataset_id=request.dataset_id,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    if len(returns_df) <= request.estimation_window + 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Dataset contains {len(returns_df)} observations, which is insufficient "
                f"for estimation window {request.estimation_window} + 5 evaluation days."
            ),
        )

    # Convert factor constraints to dict format
    factor_constraints_parsed: dict[str, dict[str, float]] | None = None
    if request.factor_constraints:
        factor_constraints_parsed = {}
        for fname, bound in request.factor_constraints.items():
            entry: dict[str, float] = {}
            if bound.min_beta is not None:
                entry["min_beta"] = bound.min_beta
            if bound.max_beta is not None:
                entry["max_beta"] = bound.max_beta
            factor_constraints_parsed[fname] = entry

    factor_model_key = request.factor_model
    if factor_model_key == "fama_french_3":
        factor_model_key = "ff3"
    elif factor_model_key == "carhart_4":
        factor_model_key = "carhart4"

    try:
        raw_res = run_dynamic_factor_backtest(
            returns_df=returns_df,
            factor_model=factor_model_key,  # type: ignore
            num_pca_factors=request.num_pca_factors,
            strategy_type=request.strategy_type,  # type: ignore
            estimation_window=request.estimation_window,
            rebalance_frequency=request.rebalance_frequency,  # type: ignore
            factor_tilts=request.factor_tilts,
            factor_constraints=factor_constraints_parsed,
            top_n_assets=request.top_n_assets,
            risk_aversion=request.risk_aversion,
            turnover_penalty=request.turnover_penalty,
            min_weight=request.min_weight,
            max_weight=request.max_weight,
            transaction_cost_bps=request.transaction_cost_bps,
            slippage_bps=request.slippage_bps,
            initial_capital=request.initial_capital,
            risk_free_rate=request.risk_free_rate,
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dynamic factor simulation validation error: {str(ve)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dynamic factor simulation failed: {str(e)}",
        )

    return DynamicFactorBacktestResponse(
        dataset_id=request.dataset_id,
        strategy_type=raw_res["strategy_type"],
        factor_model=raw_res["factor_model"],
        estimation_window=raw_res["estimation_window"],
        rebalance_frequency=raw_res["rebalance_frequency"],
        total_rebalances=raw_res["total_rebalances"],
        summary_metrics=DynamicFactorSummaryMetrics(**raw_res["summary_metrics"]),
        benchmark_metrics=DynamicFactorBenchmarkMetrics(**raw_res["benchmark_metrics"]),
        equity_curve=[DynamicFactorEquityPoint(**pt) for pt in raw_res["equity_curve"]],
        rebalance_history=[DynamicFactorRebalanceEvent(**rh) for rh in raw_res["rebalance_history"]],
        factor_exposure_series=DynamicFactorExposureSeries(**raw_res["factor_exposure_series"]),
    )

