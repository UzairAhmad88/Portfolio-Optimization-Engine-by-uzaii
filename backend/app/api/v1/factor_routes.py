"""
API Routes for Factor Attribution, Systematic Risk Decomposition & Factor-Constrained Optimization.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db.models import UserModel
from app.db.session import get_db
from app.factor_investing.models import (
    DynamicFactorBacktestRequest,
    DynamicFactorBacktestResponse,
    FactorAttributionRequest,
    FactorAttributionResponse,
    FactorConstrainedOptimizeRequest,
    FactorConstrainedOptimizeResponse,
)
from app.factor_investing.service import (
    execute_dynamic_factor_backtest,
    run_factor_attribution,
    run_factor_constrained_optimization,
)

router = APIRouter(prefix="/factor-investing", tags=["Factor Investing & Risk Attribution"])


@router.post(
    "/attribute",
    response_model=FactorAttributionResponse,
    summary="Compute multi-factor regression and Barra-style risk decomposition",
    description="Estimates factor loadings, Jensen's alphas, and performs exact systematic vs idiosyncratic risk variance attribution.",
)
def attribute_factor_risk(
    request: FactorAttributionRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> FactorAttributionResponse:
    return run_factor_attribution(
        request=request,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/optimize",
    response_model=FactorConstrainedOptimizeResponse,
    summary="Solve factor-constrained portfolio optimization",
    description="Optimizes portfolio allocations under linear factor exposure tilt bounds (e.g. Market Neutral, Value Tilt) using SLSQP.",
)
def optimize_factor_constrained(
    request: FactorConstrainedOptimizeRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> FactorConstrainedOptimizeResponse:
    return run_factor_constrained_optimization(
        request=request,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/backtest",
    response_model=DynamicFactorBacktestResponse,
    summary="Execute walk-forward dynamic factor backtest simulation",
    description="Simulates chronological dynamic factor rebalancing with rolling factor estimation, turnover costs, slippage friction, and factor exposure tracking.",
)
def backtest_dynamic_factors(
    request: DynamicFactorBacktestRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> DynamicFactorBacktestResponse:
    return execute_dynamic_factor_backtest(
        request=request,
        current_user=current_user,
        db=db,
    )

