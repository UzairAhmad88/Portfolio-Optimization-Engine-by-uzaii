"""
Service layer for Multi-Asset Class Allocation, Cash Drag Modeling & FX Hedging.
"""

from __future__ import annotations

import math
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
from app.quant.multi_asset import (
    convert_local_returns_to_base,
    decompose_multi_asset_fx_risk,
    run_multi_asset_walk_forward_backtest,
    solve_multi_asset_allocation,
)
from app.multi_asset.models import (
    AssetMetadata,
    FxRiskDecomposition,
    MultiAssetBacktestRequest,
    MultiAssetBacktestResponse,
    MultiAssetBenchmarkMetrics,
    MultiAssetEquityPoint,
    MultiAssetOptimizeRequest,
    MultiAssetOptimizeResponse,
    MultiAssetRebalanceEvent,
    MultiAssetSummaryMetrics,
)


def _load_asset_returns_for_multi_asset(
    dataset_id: str,
    current_user: UserModel,
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[pd.DataFrame, list[str], str]:
    """Loads cleaned asset returns matrix from persistent dataset, enforcing tenant permissions."""
    check_dataset_access(db, dataset_id, current_user)

    meta_assets = get_dataset_assets(dataset_id)
    if not meta_assets or len(meta_assets) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Multi-asset analysis requires a dataset with at least 2 distinct assets.",
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
            detail="Multi-asset analysis requires at least 2 distinct assets with valid price observations.",
        )

    returns_df = simple_returns(clean_prices).dropna()
    return returns_df, list(clean_prices.columns), currency or "USD"


def _resolve_asset_metadata(
    tickers: list[str],
    user_metadata: list[AssetMetadata],
    dataset_currency: str,
) -> tuple[list[str], list[str]]:
    """Resolves asset classes and currencies for each asset in tickers list."""
    meta_dict = {m.ticker: m for m in user_metadata}

    # Default heuristic: bonds/fixed income vs equities if ticker hints, else Equity
    asset_classes: list[str] = []
    asset_currencies: list[str] = []

    for tkr in tickers:
        if tkr in meta_dict:
            asset_classes.append(meta_dict[tkr].asset_class)
            asset_currencies.append(meta_dict[tkr].currency)
        else:
            # Heuristic default based on ticker name
            upper_tkr = tkr.upper()
            if any(k in upper_tkr for k in ["BND", "AGG", "TLT", "IEF", "SHY", "LQD", "HYG", "PIB"]):
                asset_classes.append("Fixed Income")
            elif any(k in upper_tkr for k in ["GLD", "SLV", "USO", "DBC", "GSG"]):
                asset_classes.append("Commodity")
            elif any(k in upper_tkr for k in ["VNQ", "IYR", "XLRE"]):
                asset_classes.append("Real Estate")
            else:
                asset_classes.append("Equity")

            asset_currencies.append(dataset_currency)

    return asset_classes, asset_currencies


def execute_multi_asset_optimization(
    request: MultiAssetOptimizeRequest,
    current_user: UserModel,
    db: Session,
) -> MultiAssetOptimizeResponse:
    """Executes multi-asset allocation optimization under class limits and cash buffers."""
    returns_df, tickers, dataset_currency = _load_asset_returns_for_multi_asset(
        dataset_id=request.dataset_id,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    asset_classes, asset_currencies = _resolve_asset_metadata(
        tickers=tickers,
        user_metadata=request.assets_metadata,
        dataset_currency=dataset_currency,
    )

    R_loc = returns_df.to_numpy(dtype=np.float64)
    N = len(tickers)

    # Convert to base reporting currency
    R_base, R_unhedged = convert_local_returns_to_base(
        local_returns=R_loc,
        asset_currencies=asset_currencies,
        base_currency=request.base_currency,
        fx_returns={},
        hedge_ratios=request.hedge_ratios,
        carry_rates=request.carry_rates,
    )

    mu_base = np.mean(R_base, axis=0) * 252.0
    Sigma_base = np.cov(R_base, rowvar=False) * 252.0
    if N == 1:
        Sigma_base = np.array([[float(Sigma_base)]])

    w_risky, w_cash, is_feas, status_msg = solve_multi_asset_allocation(
        expected_returns=mu_base,
        covariance_matrix=Sigma_base,
        asset_classes=asset_classes,
        asset_class_limits=request.asset_class_limits,
        min_cash_weight=request.min_cash_weight,
        max_cash_weight=request.max_cash_weight,
        min_asset_weight=request.min_asset_weight,
        max_asset_weight=request.max_asset_weight,
        risk_free_rate=request.risk_free_rate,
        objective=request.objective,
    )

    # Calculate portfolio return, variance, and Sharpe
    port_ret = float(np.dot(w_risky, mu_base) + w_cash * request.risk_free_rate)
    port_var = float(w_risky @ Sigma_base @ w_risky)
    port_vol = math.sqrt(max(port_var, 1e-10))
    sharpe = (port_ret - request.risk_free_rate) / port_vol if port_vol > 1e-8 else 0.0

    # Class allocations
    unique_classes = sorted(list(set(asset_classes)))
    class_allocs: dict[str, float] = {}
    for c in unique_classes:
        idx = [i for i, ac in enumerate(asset_classes) if ac == c]
        class_allocs[c] = round(float(np.sum(w_risky[idx])), 4)
    class_allocs["Cash"] = round(float(w_cash), 4)

    # FX risk decomposition
    fx_decomp_dict = decompose_multi_asset_fx_risk(
        weights=w_risky,
        local_returns=R_loc,
        unhedged_base_returns=R_unhedged,
        asset_currencies=asset_currencies,
        base_currency=request.base_currency,
        fx_returns={},
        annualization_factor=252,
    )

    return MultiAssetOptimizeResponse(
        risky_weights={tickers[i]: round(float(w_risky[i]), 4) for i in range(N)},
        cash_weight=round(float(w_cash), 4),
        asset_class_allocations=class_allocs,
        expected_annual_return=round(port_ret, 4),
        annual_volatility=round(port_vol, 4),
        sharpe_ratio=round(sharpe, 4),
        fx_risk_decomposition=FxRiskDecomposition(**fx_decomp_dict),
        is_feasible=is_feas,
        solver_message=status_msg,
    )


def execute_multi_asset_backtest(
    request: MultiAssetBacktestRequest,
    current_user: UserModel,
    db: Session,
) -> MultiAssetBacktestResponse:
    """Executes chronological walk-forward multi-asset backtest with weight drift & friction."""
    returns_df, tickers, dataset_currency = _load_asset_returns_for_multi_asset(
        dataset_id=request.dataset_id,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    asset_classes, asset_currencies = _resolve_asset_metadata(
        tickers=tickers,
        user_metadata=request.assets_metadata,
        dataset_currency=dataset_currency,
    )

    try:
        raw_results = run_multi_asset_walk_forward_backtest(
            local_returns_df=returns_df,
            asset_classes=asset_classes,
            asset_currencies=asset_currencies,
            base_currency=request.base_currency,
            hedge_ratios=request.hedge_ratios,
            carry_rates=request.carry_rates,
            asset_class_limits=request.asset_class_limits,
            min_cash_weight=request.min_cash_weight,
            max_cash_weight=request.max_cash_weight,
            rebalance_frequency=request.rebalance_frequency,
            estimation_window=request.estimation_window,
            objective=request.objective,
            risk_free_rate=request.risk_free_rate,
            transaction_cost_bps=request.transaction_cost_bps,
            slippage_bps=request.slippage_bps,
            initial_capital=request.initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return MultiAssetBacktestResponse(
        summary=MultiAssetSummaryMetrics(**raw_results["summary"]),
        benchmark=MultiAssetBenchmarkMetrics(**raw_results["benchmark"]),
        fx_risk_decomposition=FxRiskDecomposition(**raw_results["fx_risk_decomposition"]),
        equity_curve=[MultiAssetEquityPoint(**pt) for pt in raw_results["equity_curve"]],
        rebalance_history=[MultiAssetRebalanceEvent(**ev) for ev in raw_results["rebalance_history"]],
        asset_class_allocation_history=raw_results["asset_class_allocation_history"],
    )
