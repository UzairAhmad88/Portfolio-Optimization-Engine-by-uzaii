"""
FastAPI router for Monte Carlo simulation, probabilistic risk analysis, VaR & CVaR.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_active_user
from app.db.models import UserModel
from app.db.session import get_db
from app.market_data.service import DatasetNotFoundError
from app.risk_simulation.models import (
    MultiEstimatorComparison,
    RiskSimulationListItem,
    RiskSimulationRequest,
    RiskSimulationResponse,
    VaRCVaRStandaloneRequest,
)
from app.risk_simulation.service import (
    calculate_standalone_var_cvar,
    delete_risk_simulation,
    execute_risk_simulation,
    get_risk_simulation,
    list_risk_simulations,
)

router = APIRouter(prefix="/risk-simulations", tags=["Monte Carlo Risk Simulation & VaR/CVaR"])


@router.post(
    "",
    response_model=RiskSimulationResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Monte Carlo portfolio risk simulation",
)
async def run_simulation_endpoint(
    request: RiskSimulationRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RiskSimulationResponse:
    """
    Executes a multivariate Monte Carlo simulation (Normal or Student-t) generating
    terminal wealth distributions, empirical VaR/CVaR, and multi-estimator comparisons.
    """
    try:
        return await run_in_threadpool(
            execute_risk_simulation,
            req=request,
            user=current_user,
            session=session,
        )
    except DatasetNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk simulation execution failed: {str(e)}",
        )


@router.post(
    "/var-cvar",
    response_model=list[MultiEstimatorComparison],
    status_code=status.HTTP_200_OK,
    summary="Calculate analytical & empirical VaR and CVaR across confidence levels",
)
async def calculate_var_cvar_endpoint(
    request: VaRCVaRStandaloneRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[MultiEstimatorComparison]:
    """
    Computes standalone Parametric and Historical VaR and CVaR for a portfolio allocation.
    """
    try:
        return await run_in_threadpool(
            calculate_standalone_var_cvar,
            req=request,
            user=current_user,
            session=session,
        )
    except DatasetNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"VaR/CVaR calculation failed: {str(e)}",
        )


@router.get(
    "",
    response_model=list[RiskSimulationListItem],
    status_code=status.HTTP_200_OK,
    summary="List saved risk simulations for authenticated user",
)
async def list_simulations_endpoint(
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RiskSimulationListItem]:
    """
    Lists Monte Carlo simulation runs owned by the authenticated researcher.
    """
    return await run_in_threadpool(
        list_risk_simulations,
        user=current_user,
        session=session,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{run_id}",
    response_model=RiskSimulationResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve saved risk simulation run by ID",
)
async def get_simulation_endpoint(
    run_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RiskSimulationResponse:
    """
    Retrieves full simulation results and distributions for an owned run ID.
    """
    return await run_in_threadpool(
        get_risk_simulation,
        run_id=run_id,
        user=current_user,
        session=session,
    )


@router.delete(
    "/{run_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete saved risk simulation run",
)
async def delete_simulation_endpoint(
    run_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """
    Deletes a risk simulation run belonging to the authenticated researcher.
    """
    return await run_in_threadpool(
        delete_risk_simulation,
        run_id=run_id,
        user=current_user,
        session=session,
    )
