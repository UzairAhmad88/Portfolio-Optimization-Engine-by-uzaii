"""
FastAPI REST routes for Regime-Switching HMM State Detection & Dynamic Volatility Targeting.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db.models import UserModel
from app.db.session import get_db
from app.regime_switching.models import (
    RegimeDetectionRequest,
    RegimeDetectionResponse,
    RegimeBacktestRequest,
    RegimeBacktestResponse,
)
from app.regime_switching.service import (
    execute_regime_detection,
    execute_regime_backtest,
)

router = APIRouter(prefix="/regime-switching", tags=["Regime Switching"])


@router.post(
    "/detect",
    response_model=RegimeDetectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect latent market regimes using Gaussian HMM",
)
def detect_regimes(
    request: RegimeDetectionRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> RegimeDetectionResponse:
    """
    Fits a Gaussian Hidden Markov Model (HMM) on historical asset returns,
    extracting state transition matrices, regime beliefs, and timeline attribution.
    """
    return execute_regime_detection(request, current_user, db)


@router.post(
    "/backtest",
    response_model=RegimeBacktestResponse,
    status_code=status.HTTP_200_OK,
    summary="Walk-forward backtest of regime-switching allocation with volatility targeting",
)
def backtest_regimes(
    request: RegimeBacktestRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> RegimeBacktestResponse:
    """
    Executes a walk-forward chronological backtest with causal forward filtering,
    regime-conditioned covariance blending, and dynamic volatility targeting.
    """
    return execute_regime_backtest(request, current_user, db)
