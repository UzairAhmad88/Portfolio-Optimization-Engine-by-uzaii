"""
Black-Litterman API routes under /api/v1/black-litterman.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.black_litterman.models import (
    BlackLittermanBacktestRequest,
    BlackLittermanBacktestResponse,
    BlackLittermanOptimizeRequest,
    BlackLittermanOptimizeResponse,
)
from app.black_litterman.service import (
    execute_black_litterman_backtest,
    execute_black_litterman_optimization,
)
from app.db.models import UserModel
from app.db.session import get_db

router = APIRouter(prefix="/black-litterman", tags=["Black-Litterman Optimization"])


@router.post(
    "/optimize",
    response_model=BlackLittermanOptimizeResponse,
    summary="Compute Black-Litterman Bayesian portfolio optimization",
    description="Derives equilibrium implied returns, incorporates analyst views, and solves optimal allocations.",
)
def optimize_black_litterman(
    request: BlackLittermanOptimizeRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> BlackLittermanOptimizeResponse:
    return execute_black_litterman_optimization(
        request=request,
        current_user=current_user,
        session=db,
    )


@router.post(
    "/backtest",
    response_model=BlackLittermanBacktestResponse,
    summary="Run chronological out-of-sample Black-Litterman backtest",
    description="Estimates implied returns and views on in-sample data and evaluates realized performance out-of-sample.",
)
def backtest_black_litterman(
    request: BlackLittermanBacktestRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> BlackLittermanBacktestResponse:
    return execute_black_litterman_backtest(
        request=request,
        current_user=current_user,
        session=db,
    )
