"""
Service Layer for Multi-Asset Performance Attribution,
Brinson-Fachler Decomposition, and Systematic Factor Risk Attribution.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import check_dataset_access
from app.backtesting.data import prepare_backtest_data
from app.db.models import UserModel
from app.portfolio.service import get_dataset_assets
from app.quant.returns import simple_returns
from app.quant.factor_model import construct_synthetic_factors_from_returns
from app.quant.performance_attribution import (
    compute_multi_period_brinson_attribution,
    compute_factor_attribution,
)
from app.performance_attribution.models import (
    BrinsonAttributionRequest,
    BrinsonAttributionResponse,
    FactorAttributionRequest,
    FactorAttributionResponse,
)


def _load_attribution_data(
    dataset_id: str,
    requested_tickers: list[str],
    current_user: UserModel,
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
    min_observations: int = 10,
) -> tuple[pd.DataFrame, list[str]]:
    """Loads clean price data and maps bare tickers to full asset IDs."""
    check_dataset_access(db, dataset_id, current_user)

    meta_assets = get_dataset_assets(dataset_id)
    if not meta_assets or len(meta_assets) < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Attribution analysis requires a dataset with verified assets.",
        )

    # Build ticker resolution map (bare ticker -> asset_id)
    ticker_to_asset_id = {a.ticker: a.asset_id for a in meta_assets}
    ticker_to_asset_id.update({a.asset_id: a.asset_id for a in meta_assets})

    resolved_asset_ids = []
    if requested_tickers:
        for t in requested_tickers:
            if t in ticker_to_asset_id:
                resolved_asset_ids.append(ticker_to_asset_id[t])
            else:
                resolved_asset_ids.append(t)
    else:
        resolved_asset_ids = [a.asset_id for a in meta_assets]

    clean_prices, final_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=dataset_id,
        requested_assets=resolved_asset_ids,
        start_date=start_date,
        end_date=end_date,
        user=current_user,
        session=db,
        min_required_observations=min_observations,
    )

    if clean_prices.empty or len(clean_prices) < min_observations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Attribution requires at least {min_observations} observations.",
        )

    return clean_prices, final_assets


def execute_brinson_attribution(
    request: BrinsonAttributionRequest,
    current_user: UserModel,
    db: Session,
) -> BrinsonAttributionResponse:
    """Computes multi-period Brinson-Fachler attribution across segments with Cariño linking."""
    all_tickers = list(set(request.portfolio_weights.keys()) | set(request.benchmark_weights.keys()))
    if not all_tickers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Portfolio and benchmark weights cannot both be empty.",
        )

    clean_prices, final_assets = _load_attribution_data(
        dataset_id=request.dataset_id,
        requested_tickers=all_tickers,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
        min_observations=10,
    )

    # Normalize weights to available columns
    available_cols = list(clean_prices.columns)
    meta_assets = get_dataset_assets(request.dataset_id)
    asset_id_to_ticker = {a.asset_id: a.ticker for a in meta_assets}

    # Map bare tickers to columns
    ticker_to_col: dict[str, str] = {}
    for col in available_cols:
        ticker_to_col[col] = col
        if col in asset_id_to_ticker:
            ticker_to_col[asset_id_to_ticker[col]] = col

    norm_pw: dict[str, float] = {}
    norm_bw: dict[str, float] = {}

    for t, w in request.portfolio_weights.items():
        col = ticker_to_col.get(t)
        if col:
            norm_pw[col] = float(w)

    for t, w in request.benchmark_weights.items():
        col = ticker_to_col.get(t)
        if col:
            norm_bw[col] = float(w)

    if not norm_pw or not norm_bw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Specified tickers do not match assets present in dataset.",
        )

    # Build segment mapping
    raw_mapping = request.segment_mapping or {}
    segment_mapping: dict[str, str] = {}
    for col in available_cols:
        bare = asset_id_to_ticker.get(col, col)
        if col in raw_mapping:
            segment_mapping[col] = raw_mapping[col]
        elif bare in raw_mapping:
            segment_mapping[col] = raw_mapping[bare]
        else:
            # Fallback to asset market or category
            meta = next((a for a in meta_assets if a.asset_id == col), None)
            segment_mapping[col] = meta.market if meta and meta.market else "Equities"

    dates = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in clean_prices.index]
    price_matrix = clean_prices.values

    try:
        raw_res = compute_multi_period_brinson_attribution(
            price_matrix=price_matrix,
            dates=dates,
            tickers=available_cols,
            portfolio_weights=norm_pw,
            benchmark_weights=norm_bw,
            segment_mapping=segment_mapping,
            frequency=request.frequency,
            method=request.method,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Attribution calculation error: {str(e)}",
        )

    return BrinsonAttributionResponse(
        dataset_id=request.dataset_id,
        method=raw_res["method"],
        frequency=raw_res["frequency"],
        summary=raw_res["summary"],
        segment_attribution=raw_res["segment_attribution"],
        time_series=raw_res["time_series"],
    )


def execute_factor_attribution(
    request: FactorAttributionRequest,
    current_user: UserModel,
    db: Session,
) -> FactorAttributionResponse:
    """Computes systematic Barra factor active return and risk attribution."""
    all_tickers = list(set(request.portfolio_weights.keys()) | set(request.benchmark_weights.keys()))
    if not all_tickers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Portfolio and benchmark weights cannot both be empty.",
        )

    clean_prices, final_assets = _load_attribution_data(
        dataset_id=request.dataset_id,
        requested_tickers=all_tickers,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
        min_observations=30,
    )

    available_cols = list(clean_prices.columns)
    meta_assets = get_dataset_assets(request.dataset_id)
    asset_id_to_ticker = {a.asset_id: a.ticker for a in meta_assets}

    ticker_to_col: dict[str, str] = {}
    for col in available_cols:
        ticker_to_col[col] = col
        if col in asset_id_to_ticker:
            ticker_to_col[asset_id_to_ticker[col]] = col

    norm_pw: dict[str, float] = {}
    norm_bw: dict[str, float] = {}

    for t, w in request.portfolio_weights.items():
        col = ticker_to_col.get(t)
        if col:
            norm_pw[col] = float(w)

    for t, w in request.benchmark_weights.items():
        col = ticker_to_col.get(t)
        if col:
            norm_bw[col] = float(w)

    rets_df = simple_returns(clean_prices).dropna()
    asset_returns = rets_df.values

    # Construct factors
    model_key = "ff3" if request.factor_model == "fama_french_3" else (
        "carhart4" if request.factor_model == "carhart_4" else request.factor_model
    )
    factor_returns, factor_names = construct_synthetic_factors_from_returns(
        returns_df=asset_returns,
        factor_model=model_key,
        annualization_factor=request.annualization_factor,
    )

    try:
        raw_res = compute_factor_attribution(
            portfolio_weights=norm_pw,
            benchmark_weights=norm_bw,
            asset_returns=asset_returns,
            factor_returns=factor_returns,
            factor_names=factor_names,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Factor attribution calculation error: {str(e)}",
        )

    return FactorAttributionResponse(
        dataset_id=request.dataset_id,
        factor_model=request.factor_model,
        annualized_portfolio_return=raw_res["annualized_portfolio_return"],
        annualized_benchmark_return=raw_res["annualized_benchmark_return"],
        total_active_return=raw_res["total_active_return"],
        systematic_active_return=raw_res["systematic_active_return"],
        specific_active_return=raw_res["specific_active_return"],
        total_tracking_error=raw_res["total_tracking_error"],
        systematic_tracking_error=raw_res["systematic_tracking_error"],
        specific_tracking_error=raw_res["specific_tracking_error"],
        systematic_risk_percent=raw_res["systematic_risk_percent"],
        specific_risk_percent=raw_res["specific_risk_percent"],
        factor_contributions=raw_res["factor_contributions"],
    )
