"""FastAPI routes for Optimal Trade Execution & Market Impact Modeling (Stage 19)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db.models import UserModel
from app.db.session import get_db
from app.execution.models import (
    OptimalExecutionRequest,
    OptimalExecutionResponse,
    RebalanceImpactRequest,
    RebalanceImpactResponse,
)
from app.execution.service import (
    execute_optimal_trade_scheduling,
    execute_rebalance_market_impact,
)

router = APIRouter(prefix="/execution", tags=["Execution & Market Impact"])


@router.post(
    "/optimal-schedule",
    response_model=OptimalExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute Almgren-Chriss Optimal Execution Trajectory",
)
def get_optimal_execution_schedule(
    request: OptimalExecutionRequest,
    current_user: UserModel = Depends(get_current_active_user),
) -> OptimalExecutionResponse:
    """Computes the Almgren-Chriss optimal trade execution schedule balancing impact cost and timing risk."""
    return execute_optimal_trade_scheduling(request)


@router.post(
    "/rebalance-impact",
    response_model=RebalanceImpactResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Portfolio Rebalance Non-Linear Market Impact",
)
def evaluate_rebalance_impact(
    request: RebalanceImpactRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> RebalanceImpactResponse:
    """Evaluates non-linear market impact, bid-ask spread, and temporary/permanent price friction across a portfolio rebalance."""
    return execute_rebalance_market_impact(request, current_user, db)
