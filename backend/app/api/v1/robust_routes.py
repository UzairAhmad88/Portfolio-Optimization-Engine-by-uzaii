"""
FastAPI router for robust portfolio optimization, parameter sensitivity,
and out-of-sample backtesting validation.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_active_user
from app.db.models import UserModel
from app.db.session import get_db
from app.robust.models import (
    RobustBacktestRequest,
    RobustBacktestResponse,
    RobustOptimizationRequest,
    RobustOptimizationResponse,
    SensitivityAnalysisRequest,
    SensitivityAnalysisResponse,
)
from app.robust.service import (
    execute_robust_backtest,
    execute_robust_optimization,
    execute_sensitivity_sweep,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/robust-optimization", tags=["Robust Portfolio Optimization"])


@router.post(
    "/optimize",
    response_model=RobustOptimizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate baseline and robust portfolio solutions under estimation uncertainty",
)
async def optimize_robust_endpoint(
    request: RobustOptimizationRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RobustOptimizationResponse:
    try:
        return await run_in_threadpool(
            execute_robust_optimization,
            request=request,
            current_user=current_user,
            session=session,
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as exc:
        logger.exception("Unexpected error in optimize_robust_endpoint: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error executing robust portfolio optimization.",
        )


@router.post(
    "/sensitivity",
    response_model=SensitivityAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate portfolio sensitivity over bounded uncertainty or constraint grids",
)
async def sensitivity_sweep_endpoint(
    request: SensitivityAnalysisRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SensitivityAnalysisResponse:
    try:
        return await run_in_threadpool(
            execute_sensitivity_sweep,
            request=request,
            current_user=current_user,
            session=session,
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as exc:
        logger.exception("Unexpected error in sensitivity_sweep_endpoint: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error executing sensitivity sweep.",
        )


@router.post(
    "/backtest",
    response_model=RobustBacktestResponse,
    status_code=status.HTTP_200_OK,
    summary="Run out-of-sample backtest comparing baseline vs robust portfolio allocations",
)
async def robust_backtest_endpoint(
    request: RobustBacktestRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RobustBacktestResponse:
    try:
        return await run_in_threadpool(
            execute_robust_backtest,
            request=request,
            current_user=current_user,
            session=session,
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as exc:
        logger.exception("Unexpected error in robust_backtest_endpoint: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error executing robust out-of-sample backtest.",
        )
