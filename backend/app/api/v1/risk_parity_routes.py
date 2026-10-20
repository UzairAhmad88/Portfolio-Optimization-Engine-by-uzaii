"""
API Routes for Risk Parity and Hierarchical Risk Parity (HRP) under /api/v1/risk-parity.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db.models import UserModel
from app.db.session import get_db
from app.risk_parity.models import (
    RiskParityBacktestRequest,
    RiskParityBacktestResponse,
    RiskParityOptimizeRequest,
    RiskParityOptimizeResponse,
)
from app.risk_parity.service import (
    run_risk_parity_backtest,
    run_risk_parity_optimization,
)

router = APIRouter(prefix="/risk-parity", tags=["Risk Parity Optimization"])


@router.post(
    "/optimize",
    response_model=RiskParityOptimizeResponse,
    summary="Compute Risk Parity or Hierarchical Risk Parity portfolio allocation",
    description="Allocates capital across assets according to Equal Risk Contribution (ERC), Hierarchical Risk Parity (HRP), or Inverse-Variance.",
)
def optimize_risk_parity(
    request: RiskParityOptimizeRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> RiskParityOptimizeResponse:
    return run_risk_parity_optimization(
        request=request,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/backtest",
    response_model=RiskParityBacktestResponse,
    summary="Run chronological out-of-sample Risk Parity backtest",
    description="Estimates covariance and clusters in-sample, and simulates realized out-of-sample performance vs an equal-weight benchmark with transaction costs and slippage.",
)
def backtest_risk_parity(
    request: RiskParityBacktestRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> RiskParityBacktestResponse:
    return run_risk_parity_backtest(
        request=request,
        current_user=current_user,
        db=db,
    )
