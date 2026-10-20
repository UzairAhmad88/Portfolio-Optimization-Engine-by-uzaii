"""
FastAPI router for Scenario Analysis, Stress Testing, and Sensitivity Analysis.
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
from app.scenarios.models import (
    ScenarioListItem,
    ScenarioRequest,
    ScenarioResponse,
    SensitivityRequest,
    SensitivityResponse,
)
from app.scenarios.service import (
    delete_scenario_run,
    execute_scenario_analysis,
    execute_sensitivity_analysis,
    get_scenario_run,
    list_scenario_runs,
)

router = APIRouter(prefix="/scenarios", tags=["Scenario Analysis & Stress Testing"])


@router.post(
    "",
    response_model=ScenarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute instantaneous scenario shock or stress test",
)
async def run_scenario_endpoint(
    request: ScenarioRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ScenarioResponse:
    """
    Executes a custom asset price shock, historical window replay, or covariance stress test.
    """
    try:
        return await run_in_threadpool(
            execute_scenario_analysis,
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
            detail=f"Scenario analysis execution failed: {str(e)}",
        )


@router.post(
    "/stress-test",
    response_model=ScenarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute supported portfolio stress test",
)
async def run_stress_test_endpoint(
    request: ScenarioRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ScenarioResponse:
    """
    Convenience endpoint for historical window or covariance stress testing.
    """
    return await run_scenario_endpoint(request, current_user, session)


@router.post(
    "/sensitivity",
    response_model=SensitivityResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute 1D or 2D parametric sensitivity analysis",
)
async def run_sensitivity_endpoint(
    request: SensitivityRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SensitivityResponse:
    """
    Executes a 1-factor curve or 2-factor grid sensitivity analysis over asset return shocks.
    """
    try:
        return await run_in_threadpool(
            execute_sensitivity_analysis,
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
            detail=f"Sensitivity analysis execution failed: {str(e)}",
        )


@router.get(
    "",
    response_model=list[ScenarioListItem],
    status_code=status.HTTP_200_OK,
    summary="List saved scenario runs",
)
async def list_scenarios_endpoint(
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
    dataset_id: Annotated[str | None, Query(description="Filter by dataset ID")] = None,
) -> list[ScenarioListItem]:
    """
    Lists saved scenario runs for the authenticated researcher.
    """
    return await run_in_threadpool(
        list_scenario_runs,
        session=session,
        user=current_user,
        dataset_id=dataset_id,
    )


@router.get(
    "/{scenario_id}",
    response_model=ScenarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve saved scenario run",
)
async def get_scenario_endpoint(
    scenario_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ScenarioResponse:
    """
    Retrieves full details of a saved scenario run with tenant isolation.
    """
    return await run_in_threadpool(
        get_scenario_run,
        session=session,
        scenario_id=scenario_id,
        user=current_user,
    )


@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete saved scenario run",
)
async def delete_scenario_endpoint(
    scenario_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """
    Deletes a saved scenario run owned by the authenticated researcher.
    """
    return await run_in_threadpool(
        delete_scenario_run,
        session=session,
        scenario_id=scenario_id,
        user=current_user,
    )
