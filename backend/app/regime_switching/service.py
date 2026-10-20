"""
Application Service Layer for Regime-Switching HMM State Detection and Volatility Targeting.
Enforces multi-tenant authorization and dataset validation.
"""

from __future__ import annotations

import math
from typing import Any
import numpy as np
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.auth.dependencies import check_dataset_access
from app.backtesting.data import prepare_backtest_data
from app.db.models import UserModel
from app.portfolio.service import get_dataset_assets
from app.quant.regime_switching import (
    GaussianHMM,
    run_regime_switching_walk_forward_backtest,
)
from app.regime_switching.models import (
    RegimeDetectionRequest,
    RegimeDetectionResponse,
    RegimeTimelinePoint,
    RegimeBacktestRequest,
    RegimeBacktestResponse,
    RegimeBacktestSummary,
    RegimeEquityPoint,
    RegimeRebalanceEvent,
)


def execute_regime_detection(
    request: RegimeDetectionRequest,
    current_user: UserModel,
    db: Session,
) -> RegimeDetectionResponse:
    """
    Executes Gaussian HMM regime detection over historical price series.
    """
    # 1. Multi-tenant dataset security check
    check_dataset_access(db, request.dataset_id, current_user)

    # 2. Ingest clean price series
    requested_assets = request.tickers
    if not requested_assets:
        meta_assets = get_dataset_assets(request.dataset_id)
        if not meta_assets:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Dataset '{request.dataset_id}' contains no asset metadata.",
            )
        requested_assets = [a.asset_id for a in meta_assets]

    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=request.dataset_id,
        requested_assets=requested_assets,
        start_date=None,
        end_date=None,
        user=current_user,
        session=db,
        min_required_observations=20,
    )
    dates = [str(d) for d in clean_prices.index]

    if len(dates) < 30:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Insufficient historical data: {len(dates)} bars available (minimum 30 required).",
        )

    # Compute portfolio equal-weight return series
    price_matrix = clean_prices.values
    rets = np.zeros((len(dates) - 1, price_matrix.shape[1]), dtype=np.float64)
    for j in range(price_matrix.shape[1]):
        p = price_matrix[:, j]
        rets[:, j] = (p[1:] - p[:-1]) / np.maximum(1e-12, p[:-1])

    mkt_rets = np.mean(rets, axis=1)
    ret_dates = dates[1:]

    # 3. Fit Gaussian HMM
    M = request.num_states
    hmm = GaussianHMM(
        num_states=M,
        max_iter=request.max_iter,
        tol=request.tolerance,
        random_state=42,
    )
    hmm.fit(mkt_rets)

    # 4. Predict states and probabilities
    filtered_probs = hmm.predict_proba(mkt_rets, causal=True)
    smoothed_probs = hmm.predict_proba(mkt_rets, causal=False)
    viterbi_states = hmm.predict(mkt_rets)

    # 5. Build state labels
    if M == 2:
        state_labels = ["Low Volatility (Bull)", "High Volatility (Turbulent)"]
    else:
        state_labels = [
            "Low Volatility (Bull)",
            "Normal Volatility (Neutral)",
            "High Volatility (Turbulent/Crisis)",
        ]

    # Calculate annualized state volatilities
    state_vols_ann = [
        float(math.sqrt(hmm.covs_[i][0, 0] * 252.0)) for i in range(M)
    ]
    state_means = [float(hmm.means_[i][0]) for i in range(M)]

    timeline: list[RegimeTimelinePoint] = []
    for t in range(len(ret_dates)):
        st = int(viterbi_states[t])
        timeline.append(
            RegimeTimelinePoint(
                date=ret_dates[t],
                return_val=round(float(mkt_rets[t]), 5),
                state=st,
                state_label=state_labels[st],
                filtered_prob=[round(float(p), 4) for p in filtered_probs[t]],
                smoothed_prob=[round(float(p), 4) for p in smoothed_probs[t]],
            )
        )

    current_state = int(viterbi_states[-1])
    current_probs = [round(float(p), 4) for p in filtered_probs[-1]]

    return RegimeDetectionResponse(
        dataset_id=request.dataset_id,
        num_states=M,
        state_labels=state_labels,
        transition_matrix=[
            [round(float(val), 4) for val in row] for row in hmm.A_
        ],
        state_means=[round(m, 6) for m in state_means],
        state_volatilities_annual=[round(v, 4) for v in state_vols_ann],
        current_state=current_state,
        current_state_label=state_labels[current_state],
        current_regime_probabilities=current_probs,
        timeline=timeline,
    )


def execute_regime_backtest(
    request: RegimeBacktestRequest,
    current_user: UserModel,
    db: Session,
) -> RegimeBacktestResponse:
    """
    Executes walk-forward backtesting with regime-switching allocation and dynamic volatility targeting.
    """
    # 1. Multi-tenant security check
    check_dataset_access(db, request.dataset_id, current_user)

    # 2. Ingest clean prices
    requested_assets = request.tickers
    if not requested_assets:
        meta_assets = get_dataset_assets(request.dataset_id)
        if not meta_assets:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Dataset '{request.dataset_id}' contains no asset metadata.",
            )
        requested_assets = [a.asset_id for a in meta_assets]

    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=request.dataset_id,
        requested_assets=requested_assets,
        start_date=None,
        end_date=None,
        user=current_user,
        session=db,
        min_required_observations=20,
    )
    dates = [str(d) for d in clean_prices.index]
    tickers = list(clean_prices.columns)

    if len(dates) < request.lookback_window + 15:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Insufficient historical data: {len(dates)} bars available, but lookback "
                f"window requires {request.lookback_window} bars + buffer."
            ),
        )

    # Frequency mapping
    freq_map = {"daily": 1, "weekly": 5, "monthly": 21}
    rebal_days = freq_map.get(request.rebalance_frequency, 21)

    # 3. Run walk-forward backtest
    res = run_regime_switching_walk_forward_backtest(
        price_df=clean_prices.values,
        dates=dates,
        tickers=tickers,
        num_states=request.num_states,
        target_volatility=request.target_volatility,
        max_leverage=request.max_leverage,
        rebalance_frequency_days=rebal_days,
        transaction_cost_bps=request.transaction_cost_bps,
        lookback_window=request.lookback_window,
        risk_free_rate=request.risk_free_rate,
    )

    summary_raw = res["summary"]
    summary = RegimeBacktestSummary(
        initial_equity=summary_raw["initial_equity"],
        final_equity=summary_raw["final_equity"],
        cagr=summary_raw["cagr"],
        annualized_volatility=summary_raw["annualized_volatility"],
        sharpe_ratio=summary_raw["sharpe_ratio"],
        sortino_ratio=summary_raw["sortino_ratio"],
        max_drawdown=summary_raw["max_drawdown"],
        calmar_ratio=summary_raw["calmar_ratio"],
        benchmark_cagr=summary_raw["benchmark_cagr"],
        benchmark_volatility=summary_raw["benchmark_volatility"],
        benchmark_sharpe=summary_raw["benchmark_sharpe"],
        target_volatility=summary_raw["target_volatility"],
        max_leverage=summary_raw["max_leverage"],
        total_rebalances=summary_raw["total_rebalances"],
    )

    equity_points = [
        RegimeEquityPoint(
            date=pt["date"],
            portfolio_equity=pt["portfolio_equity"],
            benchmark_equity=pt["benchmark_equity"],
            cash_weight=pt["cash_weight"],
            leverage=pt["leverage"],
            regime_state=pt["regime_state"],
        )
        for pt in res["equity_curve"]
    ]

    rebal_events = [
        RegimeRebalanceEvent(
            date=ev["date"],
            regime_state=ev["regime_state"],
            regime_probs=ev["regime_probs"],
            scaling_factor=ev["scaling_factor"],
            cash_weight=ev["cash_weight"],
            turnover=ev["turnover"],
            fee_deducted=ev["fee_deducted"],
        )
        for ev in res["rebalance_events"]
    ]

    return RegimeBacktestResponse(
        dataset_id=request.dataset_id,
        summary=summary,
        equity_curve=equity_points,
        rebalance_events=rebal_events,
    )
