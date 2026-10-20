"""
API Routes for Copula Tail Dependency Estimation, Multivariate Simulation,
and Tail Risk Parity (TRP) Portfolio Allocation.
"""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db.models import UserModel
from app.db.session import get_db
from app.copula.models import (
    CopulaFitRequest,
    CopulaFitResponse,
    CopulaSimulateRequest,
    CopulaSimulateResponse,
    TailRiskParityRequest,
    TailRiskParityResponse,
    VineCopulaFitRequest,
    VineCopulaFitResponse,
    VineCopulaSimulateRequest,
    VineCopulaSimulateResponse,
    VineTailRiskParityRequest,
    VineTailRiskParityResponse,
    VineBacktestRequest,
    VineBacktestResponse,
)
from app.copula.service import (
    execute_copula_fit,
    execute_copula_simulation,
    execute_tail_risk_parity,
    execute_vine_copula_fit,
    execute_vine_copula_simulation,
    execute_vine_tail_risk_parity,
    execute_vine_backtest,
)

router = APIRouter(prefix="/copula", tags=["Copula Tail Risk & Allocation"])


@router.post(
    "/fit",
    response_model=CopulaFitResponse,
    status_code=status.HTTP_200_OK,
    summary="Fit copula models and compute asymmetric tail dependence matrices",
    description="Estimates pairwise Clayton, Gumbel, Student-t, and Gaussian copula parameters and tail dependence.",
)
def fit_copula_dependencies(
    request: CopulaFitRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CopulaFitResponse:
    return execute_copula_fit(request, current_user, db)


@router.post(
    "/simulate",
    response_model=CopulaSimulateResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate multivariate dependent returns under copula dependence",
    description="Generates dependent Monte Carlo scenarios preserving copula tail dependence and empirical margins.",
)
def simulate_copula_scenarios(
    request: CopulaSimulateRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CopulaSimulateResponse:
    return execute_copula_simulation(request, current_user, db)


@router.post(
    "/tail-risk-parity",
    response_model=TailRiskParityResponse,
    status_code=status.HTTP_200_OK,
    summary="Solve for Tail Risk Parity (TRP) allocation",
    description="Optimizes portfolio weights to equalize Euler tail risk contributions under simulated copula scenarios.",
)
def compute_tail_risk_parity(
    request: TailRiskParityRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TailRiskParityResponse:
    return execute_tail_risk_parity(request, current_user, db)


@router.post(
    "/optimize",
    response_model=TailRiskParityResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for Tail Risk Parity allocation optimization",
    description="Alias route for /tail-risk-parity for contracts and backward compatibility.",
)
def optimize_copula_tail_risk(
    request: TailRiskParityRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TailRiskParityResponse:
    return execute_tail_risk_parity(request, current_user, db)


# ============================================================================
# Regular Vine Copula (Stage 23) Endpoints
# ============================================================================

@router.post(
    "/vine/fit",
    response_model=VineCopulaFitResponse,
    status_code=status.HTTP_200_OK,
    summary="Fit Regular Vine Copula (C-Vine or D-Vine) tree decomposition",
    description="Decomposes multi-asset distribution into sequential pair-copula trees with automated family selection.",
)
def fit_vine_copula(
    request: VineCopulaFitRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VineCopulaFitResponse:
    return execute_vine_copula_fit(request, current_user, db)


@router.post(
    "/vine/simulate",
    response_model=VineCopulaSimulateResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate multivariate returns using fitted Regular Vine Copula",
    description="Simulates dependent scenarios using sequential probability integral transforms through vine trees.",
)
def simulate_vine_scenarios(
    request: VineCopulaSimulateRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VineCopulaSimulateResponse:
    return execute_vine_copula_simulation(request, current_user, db)


@router.post(
    "/vine/tail-risk-parity",
    response_model=VineTailRiskParityResponse,
    status_code=status.HTTP_200_OK,
    summary="Solve for Tail Risk Parity under Vine Copula simulation scenarios",
    description="Optimizes portfolio weights to equalize tail risk contributions under vine copula simulated returns.",
)
def compute_vine_tail_risk_parity(
    request: VineTailRiskParityRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VineTailRiskParityResponse:
    return execute_vine_tail_risk_parity(request, current_user, db)


@router.post(
    "/vine/backtest",
    response_model=VineBacktestResponse,
    status_code=status.HTTP_200_OK,
    summary="Dynamic walk-forward Vine Tail Risk Parity backtest",
    description="Simulates chronological out-of-sample portfolio performance under rolling vine copula TRP rebalancing.",
)
def run_vine_backtest(
    request: VineBacktestRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VineBacktestResponse:
    return execute_vine_backtest(request, current_user, db)

