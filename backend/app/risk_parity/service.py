"""
Service layer for Risk Parity and Hierarchical Risk Parity (HRP) portfolio optimization.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.backtesting.service import (
    BacktestSummaryMetrics,
    EquityPoint,
    RebalanceEvent,
    prepare_backtest_data,
    run_portfolio_simulation,
)
from app.db.models import UserModel
from app.portfolio.service import get_dataset_assets
from app.quant.covariance import covariance_matrix
from app.quant.returns import simple_returns
from app.quant.risk_parity import (
    calculate_risk_contributions,
    compute_risk_parity_diagnostics,
    solve_equal_risk_contribution,
    solve_hierarchical_risk_parity,
    solve_inverse_variance_portfolio,
)
from app.risk_parity.models import (
    RiskParityBacktestComparisonMetrics,
    RiskParityBacktestRequest,
    RiskParityBacktestResponse,
    RiskParityOptimizeRequest,
    RiskParityOptimizeResponse,
)

logger = logging.getLogger(__name__)


def _build_asset_resolver(canonical_assets: list[str]) -> dict[str, str]:
    """
    Builds a bidirectional map matching raw tickers (e.g. 'AAPL') to fully qualified
    identifiers (e.g. 'AAPL:US').
    """
    resolver: dict[str, str] = {}
    for canon in canonical_assets:
        resolver[canon] = canon
        resolver[canon.upper()] = canon
        parts = canon.split(":")
        ticker = parts[0]
        resolver[ticker] = canon
        resolver[ticker.upper()] = canon
    return resolver


def run_risk_parity_optimization(
    request: RiskParityOptimizeRequest,
    current_user: UserModel,
    db: Session,
) -> RiskParityOptimizeResponse:
    """
    Executes in-sample Risk Parity or HRP allocation over a tenant's dataset.
    """
    meta_assets = get_dataset_assets(request.dataset_id)
    asset_ids = [a.asset_id for a in meta_assets]
    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=request.dataset_id,
        requested_assets=asset_ids,
        start_date=None,
        end_date=None,
        user=current_user,
        session=db,
        min_required_observations=2,
    )
    if clean_prices.empty or len(clean_prices.columns) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Risk Parity optimization requires at least 2 distinct assets with valid price observations.",
        )

    resolved_assets = list(clean_prices.columns)
    n = len(resolved_assets)
    resolver = _build_asset_resolver(resolved_assets)

    # Compute daily simple returns and annualized covariance
    ret_df = simple_returns(clean_prices)
    cov_df = covariance_matrix(
        ret_df,
        ddof=1,
        handle_na="drop_any",
        annualized=True,
        periods_per_year=periods_per_year,
    )
    cov = cov_df.values.astype(np.float64)

    # Parse custom risk budgets if provided
    b_vec: np.ndarray | None = None
    if request.custom_risk_budgets:
        raw_b = np.array([
            request.custom_risk_budgets.get(a, request.custom_risk_budgets.get(a.split(":")[0], 0.0))
            for a in resolved_assets
        ], dtype=np.float64)
        sum_b = np.sum(raw_b)
        if sum_b <= 0 or np.any(raw_b <= 0):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Custom risk budgets must be strictly positive and sum to a positive value.",
            )
        b_vec = raw_b / sum_b

    # Execute requested method
    reordered_indices: list[int] | None = None

    if request.method == "erc":
        opt_res = solve_equal_risk_contribution(
            covariance=cov,
            risk_budgets=b_vec,
            min_weight=request.constraints.default_min_weight,
            max_weight=request.constraints.default_max_weight,
        )
    elif request.method == "hrp":
        opt_res = solve_hierarchical_risk_parity(
            covariance=cov,
            linkage_method=request.linkage_method,
        )
        reordered_indices = opt_res.get("reordered_indices")
    elif request.method == "inverse_variance":
        w_iv = solve_inverse_variance_portfolio(cov)
        mrc, trc, prc, port_vol = calculate_risk_contributions(w_iv, cov)
        diag = compute_risk_parity_diagnostics(w_iv, cov, prc)
        opt_res = {
            "weights": w_iv,
            "marginal_risk_contributions": mrc,
            "total_risk_contributions": trc,
            "percentage_risk_contributions": prc,
            "portfolio_volatility": port_vol,
            "risk_gini_coefficient": diag["risk_gini_coefficient"],
            "effective_number_of_bets": diag["effective_number_of_bets"],
            "diversification_ratio": diag["diversification_ratio"],
            "is_feasible": True,
            "solver_status": "optimal",
            "solver_message": "Inverse-variance allocation computed successfully.",
        }
    else:
        # Equal Weight
        w_ew = np.full(n, 1.0 / n, dtype=np.float64)
        mrc, trc, prc, port_vol = calculate_risk_contributions(w_ew, cov)
        diag = compute_risk_parity_diagnostics(w_ew, cov, prc)
        opt_res = {
            "weights": w_ew,
            "marginal_risk_contributions": mrc,
            "total_risk_contributions": trc,
            "percentage_risk_contributions": prc,
            "portfolio_volatility": port_vol,
            "risk_gini_coefficient": diag["risk_gini_coefficient"],
            "effective_number_of_bets": diag["effective_number_of_bets"],
            "diversification_ratio": diag["diversification_ratio"],
            "is_feasible": True,
            "solver_status": "optimal",
            "solver_message": "Equal-weight benchmark computed successfully.",
        }

    weights_dict = {asset: float(round(opt_res["weights"][i], 6)) for i, asset in enumerate(resolved_assets)}
    mrc_dict = {asset: float(round(opt_res["marginal_risk_contributions"][i], 6)) for i, asset in enumerate(resolved_assets)}
    trc_dict = {asset: float(round(opt_res["total_risk_contributions"][i], 6)) for i, asset in enumerate(resolved_assets)}
    prc_dict = {asset: float(round(opt_res["percentage_risk_contributions"][i], 6)) for i, asset in enumerate(resolved_assets)}

    return RiskParityOptimizeResponse(
        dataset_id=request.dataset_id,
        method=request.method,
        asset_order=resolved_assets,
        weights=weights_dict,
        marginal_risk_contributions=mrc_dict,
        total_risk_contributions=trc_dict,
        percentage_risk_contributions=prc_dict,
        portfolio_volatility=float(round(opt_res["portfolio_volatility"], 6)),
        risk_gini_coefficient=float(round(opt_res["risk_gini_coefficient"], 6)),
        effective_number_of_bets=float(round(opt_res["effective_number_of_bets"], 4)),
        effective_number_of_constituents=float(round(1.0 / max(np.sum(opt_res["weights"] ** 2), 1e-12), 4)),
        diversification_ratio=float(round(opt_res["diversification_ratio"], 4)),
        herfindahl_index=float(round(np.sum(opt_res["weights"] ** 2), 6)),
        reordered_indices=reordered_indices,
        is_feasible=opt_res["is_feasible"],
        solver_status=opt_res["solver_status"],
        solver_message=opt_res["solver_message"],
    )


def run_risk_parity_backtest(
    request: RiskParityBacktestRequest,
    current_user: UserModel,
    db: Session,
) -> RiskParityBacktestResponse:
    """
    Executes a chronological, leakage-free out-of-sample backtest of Risk Parity vs Equal Weight benchmark.
    """
    meta_assets = get_dataset_assets(request.dataset_id)
    asset_ids = [a.asset_id for a in meta_assets]
    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=request.dataset_id,
        requested_assets=asset_ids,
        start_date=None,
        end_date=None,
        user=current_user,
        session=db,
        min_required_observations=40,
    )
    if clean_prices.empty or len(clean_prices.columns) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Backtest requires at least 2 distinct assets with valid price observations.",
        )

    split_str = str(pd.to_datetime(request.split_date).strftime("%Y-%m-%d"))

    str_index = [str(d)[:10] for d in clean_prices.index]
    in_mask = [d <= split_str for d in str_index]
    out_mask = [d > split_str for d in str_index]

    in_sample_df = clean_prices.iloc[in_mask]
    out_sample_df = clean_prices.iloc[out_mask]

    if len(in_sample_df) < 30:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"In-sample training period must contain at least 30 observations. Found {len(in_sample_df)}.",
        )

    if len(out_sample_df) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Out-of-sample evaluation period must contain at least 10 observations. Found {len(out_sample_df)}.",
        )

    resolved_assets = list(clean_prices.columns)
    n = len(resolved_assets)

    # In-sample covariance calculation
    in_sample_ret = simple_returns(in_sample_df)
    cov_df = covariance_matrix(
        in_sample_ret,
        ddof=1,
        handle_na="drop_any",
        annualized=True,
        periods_per_year=periods_per_year,
    )
    cov = cov_df.values.astype(np.float64)

    # Compute in-sample strategy weights
    if request.method == "erc":
        opt_res = solve_equal_risk_contribution(cov)
        strat_weights = opt_res["weights"]
    elif request.method == "hrp":
        opt_res = solve_hierarchical_risk_parity(cov, linkage_method=request.linkage_method)
        strat_weights = opt_res["weights"]
    elif request.method == "inverse_variance":
        strat_weights = solve_inverse_variance_portfolio(cov)
    else:
        strat_weights = np.full(n, 1.0 / n, dtype=np.float64)

    ew_weights = np.full(n, 1.0 / n, dtype=np.float64)

    # Map weights to target dictionaries
    strat_weights_dict = {asset: float(strat_weights[i]) for i, asset in enumerate(resolved_assets)}
    ew_weights_dict = {asset: float(ew_weights[i]) for i, asset in enumerate(resolved_assets)}

    # Simulate Strategy Out-of-Sample
    strat_metrics, strat_equity, _ = run_portfolio_simulation(
        prices=out_sample_df,
        strategy_type="target_weights",
        target_weights=strat_weights_dict,
        rebalance_frequency=request.rebalance_frequency,
        initial_capital=request.initial_cash,
        transaction_cost_bps=request.transaction_cost_bps,
        slippage_bps=request.slippage_bps,
    )

    # Simulate Benchmark Out-of-Sample
    bench_metrics, bench_equity, _ = run_portfolio_simulation(
        prices=out_sample_df,
        strategy_type="target_weights",
        target_weights=ew_weights_dict,
        rebalance_frequency=request.rebalance_frequency,
        initial_capital=request.initial_cash,
        transaction_cost_bps=request.transaction_cost_bps,
        slippage_bps=request.slippage_bps,
    )

    # Build combined equity and drawdown timeseries
    equity_curve: list[dict[str, Any]] = []
    drawdown_curve: list[dict[str, Any]] = []

    for s_pt, b_pt in zip(strat_equity, bench_equity):
        date_str = str(s_pt.date)
        equity_curve.append({
            "date": date_str,
            "strategy": float(round(s_pt.portfolio_value_net, 2)),
            "benchmark": float(round(b_pt.portfolio_value_net, 2)),
        })
        drawdown_curve.append({
            "date": date_str,
            "strategy": float(round(s_pt.drawdown_net * 100.0, 4)),
            "benchmark": float(round(b_pt.drawdown_net * 100.0, 4)),
        })

    def _convert_metrics(m: BacktestSummaryMetrics) -> RiskParityBacktestComparisonMetrics:
        calmar = (
            float(round(m.annualized_return_net / abs(m.max_drawdown_net), 4))
            if abs(m.max_drawdown_net) > 1e-6
            else None
        )
        return RiskParityBacktestComparisonMetrics(
            annualized_return=float(round(m.annualized_return_net, 4)),
            annualized_volatility=float(round(m.volatility_annualized_net, 4)),
            sharpe_ratio=float(round(m.sharpe_ratio_net, 4)) if m.sharpe_ratio_net is not None else None,
            sortino_ratio=float(round(m.sortino_ratio_net, 4)) if m.sortino_ratio_net is not None else None,
            max_drawdown=float(round(m.max_drawdown_net, 4)),
            calmar_ratio=calmar,
            total_net_return=float(round(m.cumulative_return_net, 4)),
            total_transaction_costs=float(round(m.total_transaction_costs, 2)),
            total_slippage_costs=float(round(m.total_slippage_costs, 2)),
            rebalance_count=int(m.number_of_rebalances),
        )

    return RiskParityBacktestResponse(
        dataset_id=request.dataset_id,
        method=request.method,
        split_date=request.split_date,
        in_sample_end=str(in_sample_df.index[-1])[:10],
        out_of_sample_start=str(out_sample_df.index[0])[:10],
        out_of_sample_end=str(out_sample_df.index[-1])[:10],
        strategy_metrics=_convert_metrics(strat_metrics),
        equal_weight_benchmark_metrics=_convert_metrics(bench_metrics),
        strategy_weights={k: round(v, 6) for k, v in strat_weights_dict.items()},
        equity_curve=equity_curve,
        drawdown_curve=drawdown_curve,
    )
