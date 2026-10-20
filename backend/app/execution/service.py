"""Service layer for Optimal Trade Execution and Market Impact Modeling."""

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
from app.quant.execution import (
    compute_almgren_chriss_trajectory,
    compute_rebalance_market_impact,
)
from app.execution.models import (
    OptimalExecutionRequest,
    OptimalExecutionResponse,
    RebalanceImpactRequest,
    RebalanceImpactResponse,
)


def execute_optimal_trade_scheduling(
    request: OptimalExecutionRequest,
) -> OptimalExecutionResponse:
    """Computes Almgren-Chriss optimal trajectory and baseline trade schedules."""
    try:
        raw_result = compute_almgren_chriss_trajectory(
            order_size=request.order_size,
            asset_price=request.asset_price,
            daily_volume=request.daily_volume,
            daily_volatility=request.daily_volatility,
            bid_ask_spread=request.bid_ask_spread,
            horizon_periods=request.horizon_periods,
            trading_hours=request.trading_hours,
            risk_aversion=request.risk_aversion,
            temporary_impact_factor=request.temporary_impact_factor,
            permanent_impact_factor=request.permanent_impact_factor,
            volume_profile=request.volume_profile,
        )
        return OptimalExecutionResponse.model_validate(raw_result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


def execute_rebalance_market_impact(
    request: RebalanceImpactRequest,
    current_user: UserModel,
    db: Session,
) -> RebalanceImpactResponse:
    """Evaluates non-linear market impact and transaction friction across a portfolio rebalance."""
    # 1. Enforce tenant isolation and access control
    check_dataset_access(db, request.dataset_id, current_user)

    meta_assets = get_dataset_assets(request.dataset_id)
    if not meta_assets or len(meta_assets) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Market impact analysis requires a dataset with at least 2 distinct assets.",
        )

    asset_ids = [a.asset_id for a in meta_assets]
    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=request.dataset_id,
        requested_assets=asset_ids,
        start_date=None,
        end_date=None,
        user=current_user,
        session=db,
        min_required_observations=20,
    )

    if clean_prices.empty or len(clean_prices.columns) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Market impact analysis requires at least 2 distinct assets with valid price observations.",
        )

    returns_df = simple_returns(clean_prices).dropna()
    meta_by_id = {a.asset_id: a for a in meta_assets}

    tickers: list[str] = []
    display_tickers: dict[str, str] = {}
    for col in clean_prices.columns:
        asset_id = str(col)
        display_name = meta_by_id[asset_id].ticker if asset_id in meta_by_id else asset_id
        display_tickers[asset_id] = display_name
        tickers.append(asset_id)

    # Calculate historical annualized volatility for each asset
    volatility_dict: dict[str, float] = {}
    for asset_id in tickers:
        disp = display_tickers[asset_id]
        r_series = returns_df[asset_id].to_numpy(dtype=np.float64)
        vol_ann = float(np.std(r_series, ddof=1) * math.sqrt(252.0))
        volatility_dict[disp] = max(0.05, vol_ann)

    # Estimate Average Daily Dollar Volume (ADV)
    # Baseline heuristic: $10,000,000 adjusted by relative price level
    adv_dict: dict[str, float] = {}
    for asset_id in tickers:
        disp = display_tickers[asset_id]
        avg_price = float(clean_prices[asset_id].iloc[-1])
        adv_dict[disp] = max(1_000_000.0, avg_price * 100_000.0)

    # Calculate traded notional for each asset: |w_target - w_current| * equity
    current_weights = request.current_weights or {}
    traded_notionals: dict[str, float] = {}

    for asset_id in tickers:
        disp = display_tickers[asset_id]
        target_w = float(
            request.target_weights.get(disp, request.target_weights.get(asset_id, 0.0))
        )
        curr_w = float(
            current_weights.get(disp, current_weights.get(asset_id, 0.0))
        )
        delta_w = abs(target_w - curr_w)
        traded_notionals[disp] = delta_w * request.portfolio_equity

    # Compute non-linear market impact
    raw_impact = compute_rebalance_market_impact(
        traded_notionals=traded_notionals,
        adv_dict=adv_dict,
        volatility_dict=volatility_dict,
        spread_bps_dict=request.spread_bps_override,
        execution_horizon_days=request.execution_horizon_days,
        impact_model=request.impact_model,
    )

    return RebalanceImpactResponse.model_validate(raw_impact)
